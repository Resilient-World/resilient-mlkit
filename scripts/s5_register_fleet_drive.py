#!/usr/bin/env python3
"""Drive `mlkit register --check-fleet` against real checkouts and real mutations.

The driver for `reports/S5_REGISTER_FLEET_CHECK_PREREGISTRATION.md`. It makes
local clones of the checkouts under `--root`, commits ONE mutation into one
clone per case, runs the check, and prints one JSON document.

The cases, and which acceptance condition each is
------------------------------------------------
`B1_unmutated`
    the three current mains, untouched. Must PASS, must report one git blob.
    This is the SILENT half of every FIRES case below: each mutation is applied
    to a clone of exactly this tree, so a firing is attributable to the
    mutation and to nothing else.
`B2_field_changed_digest_stale`
    one field edited, the stored digest left as it was. Must FAIL.
`B3_digest_changed_only`
    the body untouched, the stored digest replaced. Must FAIL naming
    `canonical_body_sha256`.
`B4_field_changed_digest_rederived`
    **the case that decides whether this command is worth landing.** One field
    edited AND the digest re-derived with the repo's OWN function, so the copy
    is internally consistent and its own `--mode check` is green — which is
    exactly the state E-080 found four times over. Must FAIL, naming the field.
`B4b_e080_field`
    B4 aimed at the field that actually drifted:
    `source_files_quoting_the_replaced_sentence.<repo>`.
`B4c_declaration_removed`
    a declaration deleted by id and the digest re-derived — E-080's
    `FR-D2-NASS-45ORIGIN-ABOVE` shape. Must name the missing id, not a
    positional index.
`B6_single_copy`
    a root holding ONE copy. Must REFUSE (exit 2), never report "1 copy, 0
    divergences, PASS".

Nothing here writes to the checkouts under `--root`. Every mutation is
committed into a clone under `--workdir` and thrown away with it.

Usage
-----
    python scripts/s5_register_fleet_drive.py \
        --root <dir of resilient-* checkouts> --workdir <scratch> [--out results.json]
"""

from __future__ import annotations

import argparse
import copy as _copy
import json
import shutil
import subprocess
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.core import identity as identity_mod
from resilient_mlkit.core import register as register_mod

E080_FIELD = "source_files_quoting_the_replaced_sentence"


class Refused(RuntimeError):
    """A refusal, named. Never a silent fallback to a weaker measurement."""


def git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise Refused(f"git {' '.join(args)} in {root} failed: {out.stderr.strip()}")
    return out.stdout


def clone_fleet(root: Path, into: Path) -> list[Path]:
    """Local clones of every checkout under ``root`` that carries the register."""
    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True)
    out: list[Path] = []
    for src in register_mod.iter_register_repos(root):
        dest = into / src.name
        subprocess.run(
            ["git", "clone", "--quiet", "--local", "--no-hardlinks", str(src), str(dest)],
            check=True,
            capture_output=True,
        )
        out.append(dest)
    if not out:
        raise Refused(f"no register-carrying checkout found under {root}")
    return out


def reset(clone: Path) -> None:
    git(clone, "checkout", "--quiet", "--", ".")
    git(clone, "reset", "--hard", "--quiet", "HEAD")


def commit_register(clone: Path, body: dict, message: str) -> None:
    path = clone / register_mod.REGISTER_RELPATH
    path.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    git(clone, "add", register_mod.REGISTER_RELPATH)
    git(clone, "-c", "user.name=s5-drive", "-c", "user.email=s5@drive.invalid",
        "commit", "--quiet", "-m", message)


def read_body(clone: Path) -> dict:
    _head, _blob, body = register_mod.load_copy(clone)
    return body


def repo_digest_function(clone: Path, scratch: Path):
    """That repo's OWN canonical_body_sha256, so the mutation is re-derived the
    way the repo would re-derive it — never with a digest this driver computes."""
    return register_mod._load_digest_function(clone, scratch)


def run(root: Path) -> dict:
    report = register_mod.check_fleet(root)
    d = report.to_dict()
    d["exit_code"] = 2 if report.refusal else (1 if report.problems else 0)
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    args.workdir.mkdir(parents=True, exist_ok=True)
    scratch = args.workdir / "verifiers"
    scratch.mkdir(exist_ok=True)
    fleet = args.workdir / "fleet"
    clones = clone_fleet(args.root.resolve(), fleet)
    subject = clones[0]  # the clone every mutation is applied to
    digest_of = repo_digest_function(subject, scratch)

    cases: dict[str, object] = {}

    cases["B1_unmutated"] = run(fleet)

    # B2 — one field edited, digest left stale.
    reset(subject)
    body = read_body(subject)
    body["title"] = body["title"] + " (MUTATED BY THE DRIVE)"
    commit_register(subject, body, "B2: one field edited, digest left stale")
    cases["B2_field_changed_digest_stale"] = run(fleet)

    # B3 — digest replaced, body untouched.
    reset(subject)
    git(subject, "reset", "--hard", "--quiet", "HEAD~1")
    body = read_body(subject)
    body[register_mod.DIGEST_FIELD] = "0" * 64
    commit_register(subject, body, "B3: the digest replaced, the body untouched")
    cases["B3_digest_changed_only"] = run(fleet)

    # B4 — one field edited AND the digest re-derived with the repo's own
    # function. Internally consistent, and E-080's shape.
    reset(subject)
    git(subject, "reset", "--hard", "--quiet", "HEAD~1")
    body = read_body(subject)
    body["title"] = body["title"] + " (MUTATED BY THE DRIVE)"
    body[register_mod.DIGEST_FIELD] = digest_of(body)
    commit_register(subject, body, "B4: one field edited and the digest re-derived")
    cases["B4_field_changed_digest_rederived"] = run(fleet)

    # B4b — the field that actually drifted, in the way it actually drifted:
    # a repo zeroing its OWN entry.
    reset(subject)
    git(subject, "reset", "--hard", "--quiet", "HEAD~1")
    body = read_body(subject)
    quoting = body.get(E080_FIELD)
    if not isinstance(quoting, dict) or subject.name not in quoting:
        raise Refused(
            f"{subject.name}: {E080_FIELD} does not carry an entry for this repo, so "
            "E-080's own drift cannot be reproduced against it"
        )
    mutated = _copy.deepcopy(quoting)
    mutated[subject.name] = ["src/some/file_that_quotes_the_replaced_clause.py"]
    body[E080_FIELD] = mutated
    body[register_mod.DIGEST_FIELD] = digest_of(body)
    commit_register(subject, body, "B4b: E-080's own field, re-derived")
    cases["B4b_e080_field"] = run(fleet)

    # B4c — a declaration removed by id, digest re-derived. E-080's
    # FR-D2-NASS-45ORIGIN-ABOVE shape: a narrowing live in one copy only.
    reset(subject)
    git(subject, "reset", "--hard", "--quiet", "HEAD~1")
    body = read_body(subject)
    declarations = body.get("declarations")
    if not isinstance(declarations, list) or len(declarations) < 2:
        raise Refused(f"{subject.name}: declarations is not a list of two or more")
    dropped = declarations[-1]
    body["declarations"] = declarations[:-1]
    body[register_mod.DIGEST_FIELD] = digest_of(body)
    commit_register(subject, body, "B4c: one declaration removed, digest re-derived")
    cases["B4c_declaration_removed"] = run(fleet)
    cases["B4c_dropped_declaration_id"] = str(
        dropped.get("id") or dropped.get("declaration_id") or "<unkeyed>"
    )

    # B6 — one copy is not a fleet.
    reset(subject)
    git(subject, "reset", "--hard", "--quiet", "HEAD~1")
    lonely = args.workdir / "lonely"
    if lonely.exists():
        shutil.rmtree(lonely)
    lonely.mkdir()
    shutil.copytree(subject, lonely / subject.name, symlinks=True)
    cases["B6_single_copy"] = run(lonely)

    # And the unmutated fleet once more, LAST, so the silent half is shown to
    # be silent on the same clones the mutations ran against rather than only
    # before they were touched.
    reset(subject)
    cases["B1_unmutated_after_every_mutation"] = run(fleet)

    payload = {
        "report_type": "s5_register_fleet_check_drive",
        "generated_by": "scripts/s5_register_fleet_drive.py",
        "mlkit_version": resilient_mlkit.__version__,
        # `mlkit_version` cannot identify a build (E-M24).
        "mlkit_build": identity_mod.build_identity().to_dict(),
        "root": str(args.root.resolve()),
        "mutated_clone": subject.name,
        "cases": cases,
    }
    text = json.dumps(payload, indent=1, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
