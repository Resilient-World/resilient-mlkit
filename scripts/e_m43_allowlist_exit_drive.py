"""Drive E-M43's control arms and write ``reports/E_M43_ALLOWLIST_EXIT_ARMS.json``.

The subject is one integer: the status ``mlkit allowlist verify`` leaves behind.
The command has always PRINTED the right thing. What it could not do is let a
caller that gates on ``$?`` see two of the four verdicts it prints -- an
UNSIGNED allowlist, and an invocation that matched no repository at all.

Every arm runs the CLI in a **subprocess**, as ``python -m
resilient_mlkit.cli``, and reads ``returncode`` directly. That is deliberate on
two counts:

* A subprocess's ``returncode`` is the process's own. The observation that
  started this lane -- "prints INVALID and returns 0" -- did not reproduce
  against the process; it reproduces against a PIPELINE, where the shell
  reports the last stage. Arm ``C2P`` drives that on purpose so the distinction
  is on the record as a measurement rather than as an argument.
* Each arm first asserts, in that same subprocess, that
  ``resilient_mlkit.__file__`` resolves inside the package tree the arm names,
  and exits 9 if it does not. A venv with an editable install can otherwise
  serve a different checkout to every arm and the drive reports agreement
  having measured one tree N times.

Every fixture mutation is applied in **Python** and asserts the text actually
changed before the command runs. BSD ``sed`` has no ``\\?`` in a BRE, and this
fleet has already spent one "corrupted digest" control that corrupted nothing.

ARMS, fixed in ``reports/E_M43_M44_GATE_DEFECT_PREREGISTRATION.md`` §1 before
any of them was driven:

===== ============================================== ========
arm    condition                                      required
===== ============================================== ========
C1     two repos, valid and signed                    rc 0
C2     one hex char of ``entries_sha256`` flipped     rc 1
C2P    the same command in a PIPELINE                 shell reports 0
C3     ``signature.signed: false``                    rc 1
C4     ``docs/allowlist.yaml`` absent                 rc 1
C5     an entry with no ``retrieval_date``            rc 1
C6     ``--root`` with no ``resilient-*`` under it    rc 2
C7     ``--repo`` naming a repo not checked out       rc 2
C8     NOT-DEAD: ``cli.py`` reverted, C3 and C6 again rc 0 and 0
===== ============================================== ========

**The artifact names no directory.** C6's refusal quotes the root it searched,
which is a machine path by construction, and this file is committed. The record
keeps a boolean and the token's LENGTH -- enough to show the sentence named the
root, without putting a directory in the repository. ``machine_paths_in_text``
is run over the finished artifact before it is written, and the write is
refused if it finds one.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resilient_mlkit.core import artifact, policy

#: The pre-flight every arm runs before the CLI does anything, so that an arm
#: measuring the wrong checkout refuses instead of agreeing.
ASSERT_TREE = (
    "import pathlib,sys,resilient_mlkit as m\n"
    "want=pathlib.Path(sys.argv[1]).resolve()\n"
    "got=pathlib.Path(m.__file__).resolve()\n"
    "sys.exit(0 if want in got.parents else 9)\n"
)

ENTRY = {
    "kind": "data",
    "status": "ALLOWED",
    "licence_url": "https://example.invalid/licence",
    "retrieval_date": "2026-09-07",
    "attribution": "Attribution for the fixture source",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _allowlist_yaml(entries: list[dict], *, signed: bool) -> str:
    """Render a fixture allowlist, with a digest computed over its own entries.

    Built as text rather than dumped from a dict so that a mutation arm can
    prove it changed the bytes it meant to change.
    """
    lines = ["entries:"]
    for e in entries:
        lines.append(f"  - id: {e['id']}")
        for field in ("kind", "status", "licence_url", "retrieval_date", "attribution"):
            lines.append(f"    {field}: {json.dumps(e[field])}")
    parsed = {
        e["id"]: policy.Entry(
            id=e["id"], kind=e["kind"], status=e["status"],
            licence_url=e["licence_url"], retrieval_date=e["retrieval_date"],
            attribution=e["attribution"],
        )
        for e in entries
    }
    lines += [
        "signature:",
        f"  signed: {'true' if signed else 'false'}",
        "  signed_by: signatory@example.invalid",
        '  signed_at: "2026-09-07"',
        f'  entries_sha256: "{policy.entries_digest(parsed)}"',
    ]
    return "\n".join(lines) + "\n"


def _make_root(base: Path, *, names: tuple[str, ...] = ("arabica", "fray")) -> Path:
    """A throwaway portfolio root: git repos with valid, signed allowlists."""
    root = base
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        repo = root / f"resilient-{name}"
        (repo / "docs").mkdir(parents=True)
        entries = [{"id": f"{name}-source-one", **ENTRY}]
        (repo / policy.ALLOWLIST_RELPATH).write_text(_allowlist_yaml(entries, signed=True))
        _git(base, "init", "-q", str(repo))
        _git(repo, "config", "user.email", "t@example.invalid")
        _git(repo, "config", "user.name", "t")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "fixture")
    return root


def _rewrite(path: Path, transform) -> None:
    """Apply ``transform`` to a file's text and REFUSE a no-op mutation."""
    before = path.read_text()
    after = transform(before)
    if after == before:
        raise SystemExit(f"MUTATION DID NOTHING on {path.name}; the arm would test nothing")
    path.write_text(after)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _run(tree: Path, argv: list[str]) -> tuple[int, str, str]:
    """Run the CLI from ``tree`` in a subprocess, after asserting the tree."""
    env = {"PYTHONPATH": str(tree), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    pre = subprocess.run(
        [sys.executable, "-c", ASSERT_TREE, str(tree)],
        capture_output=True, text=True, env=env, check=False,
    )
    if pre.returncode != 0:
        raise SystemExit(
            f"REFUSED: resilient_mlkit does not resolve inside the named tree "
            f"(pre-flight exit {pre.returncode}); every arm would measure another checkout"
        )
    proc = subprocess.run(
        [sys.executable, "-m", "resilient_mlkit.cli", *argv],
        capture_output=True, text=True, env=env, check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _materialise(tree_dst: Path, *, cli_from_rev: str | None) -> Path:
    """Copy this checkout's package tree, optionally reverting ``cli.py``."""
    shutil.copytree(REPO_ROOT / "src" / "resilient_mlkit", tree_dst / "resilient_mlkit")
    if cli_from_rev:
        blob = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{cli_from_rev}:src/resilient_mlkit/cli.py"],
            capture_output=True, text=True, check=True,
        ).stdout
        target = tree_dst / "resilient_mlkit" / "cli.py"
        if target.read_text() == blob:
            raise SystemExit(
                f"REFUSED: cli.py at {cli_from_rev} is identical to this tree's; "
                "the NOT-DEAD arm would revert nothing"
            )
        target.write_text(blob)
    for cache in (tree_dst / "resilient_mlkit").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return tree_dst


def _redact_roots(text: str, roots: list[Path]) -> str:
    """Replace every fixture directory with a length-preserving placeholder.

    Both the literal path and its ``resolve()``d form: on macOS ``--root`` is
    resolved before it is printed, so redacting only the literal leaves the
    ``/private`` prefix behind -- which is how a redaction comes to look like
    it worked while a directory is still in the file.
    """
    forms = {str(p) for p in roots} | {str(p.resolve()) for p in roots}
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, f"<root:{len(form)} chars>")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--not-dead-rev", default="origin/main",
                    help="revision whose cli.py the NOT-DEAD arm reverts to")
    ap.add_argument("--out", default=str(REPO_ROOT / "reports" / "E_M43_ALLOWLIST_EXIT_ARMS.json"))
    args = ap.parse_args()

    arms: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        live = _materialise(tmpdir / "tree-live", cli_from_rev=None)
        dead = _materialise(tmpdir / "tree-not-dead", cli_from_rev=args.not_dead_rev)
        roots: list[Path] = [tmpdir]

        def record(arm: str, condition: str, required: str, rc: int, out: str, err: str,
                   contains: str | None = None, tree: str = "live") -> None:
            body = _redact_roots(out + err, roots)
            arms.append({
                "arm": arm,
                "tree": tree,
                "condition": condition,
                "required": required,
                "exit_code": rc,
                "stdout_lines": len(out.strip().splitlines()),
                "stderr_lines": len(err.strip().splitlines()),
                "output_contains": {contains: (contains in out + err)} if contains else {},
                "output_names_a_directory": bool(
                    artifact.machine_paths_in_text(out + err, check_exists=False)
                ),
                "output_redacted": body.strip().splitlines(),
            })

        # -- C1: the case whose exit code must be PRESERVED ------------------
        root = _make_root(tmpdir / "c1")
        roots.append(root)
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root)])
        record("C1", "two repos, both valid and signed", "rc 0", rc, out, err,
               "signed by")

        # -- C2: one hex character of entries_sha256 flipped ------------------
        root = _make_root(tmpdir / "c2")
        roots.append(root)
        target = root / "resilient-arabica" / policy.ALLOWLIST_RELPATH
        flipped: dict[str, str] = {}

        def flip(text: str) -> str:
            m = re.search(r'entries_sha256: "([0-9a-f]{64})"', text)
            if not m:
                raise SystemExit("REFUSED: no entries_sha256 to flip; the arm would test nothing")
            old = m.group(1)
            new = ("a" if old[0] != "a" else "b") + old[1:]
            flipped["old"], flipped["new"] = old, new
            return text.replace(old, new)

        _rewrite(target, flip)
        _commit(root / "resilient-arabica", "flip")
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root)])
        record("C2", "one hex character of entries_sha256 flipped, mutation verified",
               "rc 1, the reason names the digest", rc, out, err,
               "entries_sha256 does not match")
        arms[-1]["mutation"] = {
            "recorded_prefix": flipped["new"][:12], "computed_prefix": flipped["old"][:12],
            "differ": flipped["new"] != flipped["old"],
        }

        # -- C2P: the same command in a PIPELINE ------------------------------
        # Not a defect in the tool. The clause this lane was handed said the
        # command "prints INVALID and returns 0"; against the process it
        # returns 1, and this arm is where the 0 actually comes from.
        piped = (
            f"{sys.executable} -m resilient_mlkit.cli allowlist verify "
            f"--root {root} 2>&1 | head -20 >/dev/null"
        )
        pipeline = subprocess.run(
            ["/bin/sh", "-c", piped],
            capture_output=True, text=True, check=False,
            env={"PYTHONPATH": str(live), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
        )
        record("C2P", "C2's command piped into `head`; the SHELL reports $? of the last stage",
               "0 — a property of the pipeline, not of the command",
               pipeline.returncode, "", "")

        # -- C3: unsigned -----------------------------------------------------
        root = _make_root(tmpdir / "c3")
        roots.append(root)
        target = root / "resilient-arabica" / policy.ALLOWLIST_RELPATH
        _rewrite(target, lambda t: t.replace("signed: true", "signed: false"))
        _commit(root / "resilient-arabica", "unsign")
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root)])
        record("C3", "signature.signed: false", "rc 1, output says UNSIGNED", rc, out, err,
               "UNSIGNED")

        # -- C4: missing ------------------------------------------------------
        root = _make_root(tmpdir / "c4")
        roots.append(root)
        (root / "resilient-arabica" / policy.ALLOWLIST_RELPATH).unlink()
        _commit(root / "resilient-arabica", "remove allowlist")
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root)])
        record("C4", "docs/allowlist.yaml absent", "rc 1, output says MISSING", rc, out, err,
               "MISSING")

        # -- C5: a defective entry, correctly signed --------------------------
        # Signed over its own entries, so the arm tests the DEFECT branch and
        # not the digest branch it would otherwise trip first.
        root = tmpdir / "c5"
        root.mkdir()
        roots.append(root)
        repo = root / "resilient-arabica"
        (repo / "docs").mkdir(parents=True)
        bad = dict(ENTRY, id="undated-source", retrieval_date="")
        (repo / policy.ALLOWLIST_RELPATH).write_text(_allowlist_yaml([bad], signed=True))
        _git(root, "init", "-q", str(repo))
        _git(repo, "config", "user.email", "t@example.invalid")
        _git(repo, "config", "user.name", "t")
        _commit(repo, "fixture")
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root)])
        record("C5", "an entry with no retrieval_date, under a valid signature",
               "rc 1, output names the defect", rc, out, err, "retrieval_date is missing")

        # -- C6: no repository matched ----------------------------------------
        empty = tmpdir / "c6-empty"
        empty.mkdir()
        roots.append(empty)
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(empty)])
        record("C6", "--root at a directory holding no resilient-* checkout",
               "rc 2, and a refusal on stderr naming the root", rc, out, err,
               "REFUSED, not a pass")
        arms[-1]["stderr_named_the_root"] = str(empty) in err
        arms[-1]["root_token_length"] = len(str(empty))

        # -- C7: --repo naming a repo that is not checked out ------------------
        root = _make_root(tmpdir / "c7")
        roots.append(root)
        rc, out, err = _run(live, ["allowlist", "verify", "--root", str(root), "--repo", "choco"])
        record("C7", "--root valid, --repo names a portfolio repo not checked out there",
               "rc 2", rc, out, err, "REFUSED, not a pass")

        # -- C8: NOT-DEAD ------------------------------------------------------
        rc_unsigned, out, err = _run(dead, ["allowlist", "verify", "--root", str(tmpdir / "c3")])
        record("C8a", f"NOT-DEAD: cli.py reverted to {args.not_dead_rev}, C3 re-driven",
               "rc 0 — the defect, on purpose", rc_unsigned, out, err, "UNSIGNED", tree="not-dead")
        rc_empty, out, err = _run(dead, ["allowlist", "verify", "--root", str(empty)])
        record("C8b", f"NOT-DEAD: cli.py reverted to {args.not_dead_rev}, C6 re-driven",
               "rc 0 and NO output — the defect, on purpose", rc_empty, out, err,
               tree="not-dead")

    payload = {
        "preregistration": "reports/E_M43_M44_GATE_DEFECT_PREREGISTRATION.md",
        "escalation": "E-M43",
        "subject": "mlkit allowlist verify — the exit status must carry every verdict it prints",
        "not_dead_rev_label": args.not_dead_rev,
        "arms": arms,
    }
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    offenders = artifact.machine_paths_in_text(text, check_exists=False)
    if offenders:
        raise SystemExit(
            f"REFUSED: the control artifact names {len(offenders)} machine path(s) at "
            + ", ".join(pos for pos, _ in offenders[:5])
            + " — a record objecting to invisible failures must not itself carry a directory"
        )
    Path(args.out).write_text(text)
    print(f"{len(arms)} arms -> {args.out}")
    for a in arms:
        print(f"  {a['arm']:5s} exit={a['exit_code']}  {a['required']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
