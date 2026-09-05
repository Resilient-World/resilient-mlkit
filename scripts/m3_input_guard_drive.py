"""M-3 REPAIR drive of record: the merged-tree input guard, on a real clone.

What it drives, against a real model-repo clone and a real base ref:

* **BEFORE** — the merged drive under a SECOND mlkit source tree (``--baseline``,
  normally the stack head this repair sits on), so the rows this repair changes
  are measured rather than remembered.
* **UNDECLARED** — the merged drive under THIS mlkit, on the clone as it stands.
* one arm per ``--arm LABEL=<toml-fragment-file>``: the fragment is appended to
  ``.mlkit/repo.toml`` on a scratch branch cut from the clone's HEAD, committed
  (never pushed), and the merged drive run on it. Use these for
  "declared-and-absent" and for the check-not-dead "declared-and-present".
* **PLAIN** — the same phases WITHOUT ``--merged-with``, under both mlkits, so
  the silence claim ("the guard is armed only on a merged-tree drive") is a
  diff and not a sentence.

Every row is what the CLI printed. Nothing here computes a verdict.

Usage::

    python scripts/m3_input_guard_drive.py \\
        --root /path/containing/resilient-fray --repo fray --base main \\
        --phase decision --phase economics \\
        --python /path/to/resilient-fray/.venv/bin/python \\
        --baseline /path/to/mlkit-at-49-head/src \\
        --arm declared-absent=/tmp/absent.toml \\
        --arm declared-present=/tmp/present.toml \\
        --out reports/validation/M3_INPUT_GUARD_FRAY_DRIVE.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.core import artifact, identity

HERE = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^([A-Z]\d{1,2})\s+([A-Z]+)\s*(.*)$")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=m3drive",
         "-c", "user.email=m3drive@local", *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _drive(python: str, mlkit_src: Path, root: Path, repo: str, phase: str,
           base: str | None) -> list[dict]:
    """One CLI run; the phase table's rows, exactly as printed."""
    cmd = [python, "-m", "resilient_mlkit.cli", "check", "--root", str(root),
           "--repo", repo, "--phase", phase]
    if base:
        cmd += ["--merged-with", base]
    out = subprocess.run(
        cmd, capture_output=True, text=True, check=False,
        env={"PYTHONPATH": str(mlkit_src), "PATH": _path(), "HOME": _home()},
    )
    rows = []
    for line in out.stdout.splitlines():
        m = ROW.match(line)
        if m and m.group(1)[0] in "TSRDE":
            rows.append({"check": m.group(1), "status": m.group(2),
                         "detail": m.group(3)[:240]})
    return rows


def _path() -> str:
    import os
    return os.environ.get("PATH", "")


def _home() -> str:
    import os
    return os.environ.get("HOME", "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="the directory CONTAINING resilient-<repo>")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", required=True, help="the base ref to merge with")
    ap.add_argument("--phase", action="append", required=True)
    ap.add_argument("--python", required=True, help="the model repo's own venv interpreter")
    ap.add_argument("--baseline", required=True, help="a SECOND mlkit src tree: the before")
    ap.add_argument("--arm", action="append", default=[], metavar="LABEL=TOML-FRAGMENT")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    at = Path(resilient_mlkit.__file__).resolve()
    if not at.is_relative_to(HERE / "src"):
        raise SystemExit(f"resilient_mlkit imported from {at}, not this checkout; refusing")

    root = Path(args.root).resolve()
    clone = root / f"resilient-{args.repo}"
    here_src = HERE / "src"
    baseline_src = Path(args.baseline).resolve()

    start_ref = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    start_sha = _git(clone, "rev-parse", "HEAD")
    base_sha = _git(clone, "rev-parse", args.base)

    arms: list[dict] = []
    for label, src, base in (
        ("BEFORE (merged, mlkit at --baseline)", baseline_src, args.base),
        ("UNDECLARED (merged, mlkit repaired)", here_src, args.base),
    ):
        arms.append({
            "arm": label, "merged_with": base, "head_sha": start_sha,
            "phases": {p: _drive(args.python, src, root, args.repo, p, base)
                       for p in args.phase},
        })

    for spec in args.arm:
        label, _, fragment = spec.partition("=")
        text = Path(fragment).read_text()
        branch = f"m3-drive-{label}"
        _git(clone, "checkout", "-q", "-B", branch, start_sha)
        config = clone / ".mlkit" / "repo.toml"
        config.write_text(config.read_text() + text)
        _git(clone, "commit", "-qam", f"scratch (never pushed): {label}")
        arms.append({
            "arm": f"{label} (merged, mlkit repaired)",
            "merged_with": args.base,
            "head_sha": _git(clone, "rev-parse", "HEAD"),
            "toml_fragment": text,
            "phases": {p: _drive(args.python, here_src, root, args.repo, p, args.base)
                       for p in args.phase},
        })
        _git(clone, "checkout", "-q", start_ref)
        _git(clone, "branch", "-qD", branch)

    plain = {}
    for label, src in (("BEFORE", baseline_src), ("REPAIRED", here_src)):
        plain[label] = {p: _drive(args.python, src, root, args.repo, p, None)
                        for p in args.phase}
    plain["identical"] = plain["BEFORE"] == plain["REPAIRED"]

    payload = {
        "artifact_schema": "resilient-mlkit/m3-input-guard-drive/1",
        "generated_by": "scripts/m3_input_guard_drive.py",
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "mlkit_version": resilient_mlkit.__version__,
        "mlkit_build": identity.build_identity().to_dict(),
        "subject": {
            "repo": args.repo,
            "head_sha": start_sha,
            "head_ref": start_ref,
            "base_ref": args.base,
            "base_sha": base_sha,
            "note": (
                "the clone's scratch branches are cut from head_sha, committed and "
                "deleted by this script, and are NEVER pushed; every arm's TOML "
                "fragment is carried verbatim so a reader can rebuild it from the "
                "public base_sha"
            ),
        },
        "merged_arms": arms,
        "plain_drive_silence": plain,
    }
    out = Path(args.out).resolve()
    written = artifact.write_artifact(out.parent, out.name, payload)
    print(json.dumps({a["arm"]: {p: [(r["check"], r["status"]) for r in rows]
                                 for p, rows in a["phases"].items()} for a in arms}, indent=1))
    print(f"plain drive identical BEFORE vs REPAIRED: {plain['identical']}")
    print(f"wrote {written.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
