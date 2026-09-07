"""Drive E-M42's control arms and write ``reports/E_M42_HEADER_CONTROL_ARMS.json``.

The subject is one line: the ``mlkit build:`` line
:func:`resilient_mlkit.core.identity.header_lines` renders into every stamped
report in eight repositories. The question is whether that line names an
IDENTITY (reproducible on any machine) or a DIRECTORY (reproducible on one).

Every arm renders the header in a SUBPROCESS against a package tree that this
script materialises at a chosen absolute path, with **no mlkit distribution
installed** in the rendering interpreter -- otherwise an editable install's
import hook wins over ``PYTHONPATH`` and every arm silently measures the same
tree, which is how the first pass of this drive nearly reported success.

ARMS (fixed in ``reports/E_M42_REPORT_HEADER_PREREGISTRATION.md`` §3 before any
of them was driven):

* **A1a** source-tree import, two different absolute directories -> the two
  headers must be BYTE-IDENTICAL and carry no machine path.
* **A1b** the same, on a **sourceless / bytecode-only** install -- the branch
  where the digest cannot be taken and the header's words are all a reader has.
  This is the arm that fails on ``main``.
* **A2** two genuinely different mlkit REVISIONS -> the headers must DIFFER.
  Without it, "no path" could be bought by emptying the line, and a stamp that
  cannot tell two builds apart is the E-M24 defect this whole module exists to
  close.
* **A3** CHECK-NOT-DEAD: ``core/identity.py`` reverted to a given revision (the
  caller passes ``--not-dead-rev``), arm A1b re-driven -> it must FAIL.
* **DIGEST** the digest of a given package tree must be byte-identical before
  and after the change: the adopter-side check in five repos parses that token.

"Machine path" is judged by mlkit's own discriminator
(:func:`core.artifact.machine_paths_in_text`) and not by a second opinion
written here -- rule 7, and a control with its own definition of the defect
measures its own definition.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RENDER = r"""
import json
from resilient_mlkit.core import identity
identity.build_identity.cache_clear()
bi = identity.build_identity()
print(json.dumps({
    "header": identity.header_lines(),
    "stamp": bi.stamp,
    "unavailable": bi.unavailable,
    "vcs_reason": bi.vcs_reason,
    "source_sha256": bi.source_sha256,
    "files": bi.files,
}))
"""


def _materialise(src_pkg: Path, dest_checkout: Path, *, sourceless: bool, python: str) -> Path:
    """Put a copy of ``src_pkg`` at ``dest_checkout/src/resilient_mlkit``."""
    if dest_checkout.exists():
        shutil.rmtree(dest_checkout)
    (dest_checkout / "src").mkdir(parents=True)
    shutil.copytree(src_pkg, dest_checkout / "src" / "resilient_mlkit")
    for pycache in (dest_checkout / "src").rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    # A `pyproject.toml` beside `src/` is what makes `root_kind` read
    # `checkout` rather than `other`; the arms are about a source tree.
    (dest_checkout / "pyproject.toml").write_text(
        '[project]\nname = "resilient-mlkit"\nversion = "0.0.0"\n'
    )
    if sourceless:
        pkg = dest_checkout / "src" / "resilient_mlkit"
        subprocess.run(
            [python, "-c", (
                f"import compileall,sys; sys.exit(0 if compileall.compile_dir({str(pkg)!r},"
                " quiet=2, legacy=True, force=True) else 1)"
            )],
            check=True,
        )
        for py in pkg.rglob("*.py"):
            py.unlink()
        for pycache in pkg.rglob("__pycache__"):
            shutil.rmtree(pycache, ignore_errors=True)
    return dest_checkout / "src"


def _render(python: str, pythonpath: Path, cwd: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pythonpath)
    env.pop("PYTHONHOME", None)
    out = subprocess.run(
        [python, "-c", RENDER], capture_output=True, text=True, env=env, cwd=cwd, check=True
    )
    return json.loads(out.stdout)


def _offenders(text: str) -> list[tuple[str, str]]:
    from resilient_mlkit.core import artifact

    return artifact.machine_paths_in_text(text)


def _redact(lines: list[str]) -> list[str]:
    """Every machine-path token replaced by its length.

    The A3 arm's whole point is that the unrepaired renderer emits absolute
    paths, so its headers ARE machine paths -- and this artifact is COMMITTED.
    Writing them out verbatim would make the control artifact the defect it
    controls for, which is not a hypothetical: the first drive of this script
    did exactly that and ``machine_paths_in_text`` over the record caught it.
    The length is kept because it is what distinguishes the two directories
    without naming either.
    """
    out = []
    for line in lines:
        for _, token in _offenders(line):
            line = line.replace(token, f"<machine path redacted, {len(token)} chars>")
        out.append(line)
    return out


def _pair_arm(
    name: str, python: str, src_pkg: Path, work: Path, *, sourceless: bool, must_match: bool
) -> dict:
    a = _materialise(src_pkg, work / f"{name}_A" / "a" / "b" / "c" / "d" / "e" / "checkout",
                     sourceless=sourceless, python=python)
    b = _materialise(src_pkg, work / f"{name}_B" / "zz" / "checkout",
                     sourceless=sourceless, python=python)
    ra = _render(python, a, cwd="/")
    rb = _render(python, b, cwd=str(Path(tempfile.gettempdir())))
    ta, tb = "\n".join(ra["header"]), "\n".join(rb["header"])
    off = _offenders(ta) + _offenders(tb)
    identical = ta == tb
    return {
        "arm": name,
        "condition": "sourceless/bytecode-only install" if sourceless else "source-tree import",
        "dir_a_depth": len(a.parts),
        "dir_b_depth": len(b.parts),
        "headers_byte_identical": identical,
        "machine_path_tokens": len(off),
        "machine_path_positions": [p for p, _ in off],
        "header_a": _redact(ra["header"]),
        "header_b": _redact(rb["header"]),
        "stamp": ra["stamp"],
        "required": "headers byte-identical AND 0 machine path tokens",
        "agrees": (identical and not off) if must_match else (not identical or bool(off)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="the mlkit checkout being measured")
    ap.add_argument("--python", default=sys.executable,
                    help="an interpreter with NO resilient-mlkit distribution installed")
    ap.add_argument("--work", required=True, help="scratch directory for the materialised trees")
    ap.add_argument("--not-dead-rev", default="",
                    help="git revision whose core/identity.py is restored for arm A3")
    ap.add_argument("--a2-rev", default="",
                    help="git revision providing the SECOND build for arm A2")
    ap.add_argument("--out", default="reports/E_M42_HEADER_CONTROL_ARMS.json")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    pkg = repo / "src" / "resilient_mlkit"

    arms = [
        _pair_arm("A1a", args.python, pkg, work, sourceless=False, must_match=True),
        _pair_arm("A1b", args.python, pkg, work, sourceless=True, must_match=True),
    ]

    # A2 -- the identity must still tell two genuinely different builds apart.
    if args.a2_rev:
        other = work / "A2_other"
        if other.exists():
            shutil.rmtree(other)
        other.mkdir(parents=True)
        subprocess.run(
            f"git -C {repo} archive {args.a2_rev} src/resilient_mlkit | tar -x -C {other}",
            shell=True, check=True,
        )
        a = _materialise(pkg, work / "A2_here" / "checkout", sourceless=False, python=args.python)
        b = _materialise(other / "src" / "resilient_mlkit", work / "A2_there" / "checkout",
                         sourceless=False, python=args.python)
        ra, rb = _render(args.python, a, "/"), _render(args.python, b, "/")
        ta, tb = "\n".join(ra["header"]), "\n".join(rb["header"])
        arms.append({
            "arm": "A2",
            "condition": f"two mlkit revisions: working tree vs {args.a2_rev}",
            "headers_byte_identical": ta == tb,
            "stamp_here": ra["stamp"],
            "stamp_there": rb["stamp"],
            "machine_path_tokens": len(_offenders(ta) + _offenders(tb)),
            "required": "headers DIFFER (the stamp still identifies its build)",
            "agrees": ta != tb and ra["stamp"] != rb["stamp"],
        })

    # A3 -- CHECK-NOT-DEAD. Restore the pre-fix identity.py and re-drive A1b.
    if args.not_dead_rev:
        reverted = work / "A3_reverted"
        if reverted.exists():
            shutil.rmtree(reverted)
        shutil.copytree(pkg, reverted)
        old = subprocess.run(
            ["git", "-C", str(repo), "show",
             f"{args.not_dead_rev}:src/resilient_mlkit/core/identity.py"],
            capture_output=True, text=True, check=True,
        ).stdout
        (reverted / "core" / "identity.py").write_text(old)
        arm = _pair_arm("A3", args.python, reverted, work, sourceless=True, must_match=False)
        arm["condition"] = (
            f"CHECK-NOT-DEAD: core/identity.py reverted to {args.not_dead_rev}, "
            "sourceless install, two directories"
        )
        arm["required"] = "MUST FAIL arm A1b's assertion (headers differ or machine paths > 0)"
        arms.append(arm)

    # DIGEST -- the compared token must not move for a given tree.
    digest_probe = _render(args.python,
                           _materialise(pkg, work / "DIGEST" / "checkout",
                                        sourceless=False, python=args.python),
                           "/")
    record = {
        "artifact_schema": "resilient-mlkit/e-m42-header-control-arms/1",
        "generated_by": "scripts/e_m42_header_control_drive.py",
        "subject": "core.identity.header_lines() -- the `mlkit build:` line of every stamped report",
        "discriminator": "core.artifact.machine_paths_in_text (mlkit's own, not a second opinion)",
        "arms": arms,
        "digest_of_working_tree_package": digest_probe["source_sha256"],
        "digest_files": digest_probe["files"],
        "all_required_arms_agree": all(a["agrees"] for a in arms),
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = repo / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({a["arm"]: a["agrees"] for a in arms}, indent=1))
    print(f"wrote {out.name}")
    return 0 if record["all_required_arms_agree"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
