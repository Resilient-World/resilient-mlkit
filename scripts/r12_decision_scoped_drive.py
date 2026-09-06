#!/usr/bin/env python3
"""Drive R12's serve-arm exemption against the REAL shapes E-079 and E-035 named.

This is the driver for `reports/R12_DECISION_SCOPED_EXEMPTION_PREREGISTRATION.md`.
It builds each shape as a throwaway copy of a real checkout, scans it with
whichever `resilient_mlkit` is importable, and prints one JSON document. It
decides nothing and writes nothing into either repo.

The four shapes, and why each exists
------------------------------------
``torrent_A_as_authored``
    resilient-torrent's ``mlkit_bindings.py`` with a module-level
    ``D6_DECIDING_ARM = "val"`` and NO ``core.served`` name anywhere in the
    file. E-079's row 1: the defect PR #190 shipped, which R12 reported.
``torrent_B_repair``
    the file exactly as torrent ``main`` has it: the arm comes from
    ``ServeArms.require``. E-079's row 2.
``torrent_C_constant_used_helper_dead``
    the repair PLUS the constant restored AND USED, with ``_d6_serve_arms``
    left dead. E-079's row 3, measured at **0** and the reason this driver
    exists: a single conforming helper bought silence for the serve-arm
    decision the file actually makes.
``fray_E035_dead_import`` / ``fray_E035_pre_adoption``
    resilient-fray's ``src/registry/promotion_gate.py`` at its PRE-ADOPTION
    blob (the parent of the P0-6 adoption commit), with and without the one
    line E-035 measured: ``from resilient_mlkit.core.served import
    challenger_decision  # noqa: F401``. The dead import must buy nothing.

Every shape is a whole-repo scan, because the exemption is a repo-level fact:
one file can be exempted by a route through another.

Usage
-----
    python scripts/r12_decision_scoped_drive.py \
        --torrent <path to a resilient-torrent checkout> \
        --fray <path to a resilient-fray checkout> \
        --workdir <a scratch directory> [--out results.json]

`--fleet <dir>` additionally scans every ``resilient-*`` checkout under `dir`
and reports each one's finding set, which is what the before/after superset
comparison in acceptance condition A5/A6 is taken over.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.core import identity as identity_mod
from resilient_mlkit.core import served_reimplementation as sr

TORRENT_REL = "mlkit_bindings.py"
FRAY_REL = "src/registry/promotion_gate.py"

#: The exact block torrent ``main`` carries. Matched verbatim: if it has moved,
#: this driver REFUSES rather than guessing where the arm now comes from.
TORRENT_REPAIR_BLOCK = '''def _d6_serve_arms() -> Any:
    """The arms this D6 declaration may decide on, as the served contract's data."""
    from resilient_mlkit.core.served import ServeArms

    return ServeArms(
        open={"val"},
        closed={
            "test": (
                "the hydrology test arm is a ledgered holdout; reading it to decide a "
                "resampling unit would spend a read that is the signatory's alone"
            ),
            "train": (
                "the fitted arm cannot adjudicate the dependence unit it was fitted "
                "under; the residuals it leaves are not evidence about blocking"
            ),
        },
    )


def d6_deciding_arm() -> str:
    """The arm D6 decides on, obtained THROUGH the contract so the refusal is mlkit's."""
    return _d6_serve_arms().require("val")
'''

TORRENT_AS_AUTHORED_BLOCK = '''D6_DECIDING_ARM = "val"


def d6_deciding_arm() -> str:
    """The arm D6 decides on."""
    return D6_DECIDING_ARM
'''

TORRENT_CONSTANT_USED_HELPER_DEAD_BLOCK = '''D6_DECIDING_ARM = "val"


def _d6_serve_arms() -> Any:
    """The arms this D6 declaration may decide on, as the served contract's data."""
    from resilient_mlkit.core.served import ServeArms

    return ServeArms(
        open={"val"},
        closed={
            "test": (
                "the hydrology test arm is a ledgered holdout; reading it to decide a "
                "resampling unit would spend a read that is the signatory's alone"
            ),
            "train": (
                "the fitted arm cannot adjudicate the dependence unit it was fitted "
                "under; the residuals it leaves are not evidence about blocking"
            ),
        },
    )


def d6_deciding_arm() -> str:
    """The arm D6 decides on."""
    return D6_DECIDING_ARM
'''

#: E-035's own one-line mutation, quoted from the escalation entry.
FRAY_DEAD_IMPORT = (
    "from resilient_mlkit.core.served import challenger_decision  # noqa: F401\n"
)


class Refused(RuntimeError):
    """A refusal, named. Never a silent fallback to a weaker measurement."""


def git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise Refused(f"git {' '.join(args)} in {root} failed: {out.stderr.strip()}")
    return out.stdout


def stage(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"), symlinks=True)
    return dest


def rows(findings) -> list[dict[str, object]]:
    return [
        {
            "path": f.path,
            "line": f.line,
            "clause": f.clause,
            "severity": f.severity,
            "symbol": f.symbol,
        }
        for f in findings
    ]


def scan(root: Path) -> dict[str, object]:
    findings, walked = sr.scan_repo(root)
    return {"files_walked": walked, "findings": len(findings), "rows": rows(findings)}


def torrent_shapes(torrent: Path, work: Path) -> dict[str, object]:
    text = (torrent / TORRENT_REL).read_text(encoding="utf-8")
    if TORRENT_REPAIR_BLOCK not in text:
        raise Refused(
            f"{torrent}/{TORRENT_REL} does not carry the #190 repair block verbatim; "
            "the shapes E-079 named cannot be rebuilt from a tree that has moved, "
            "and this driver will not guess at a substitute"
        )
    out: dict[str, object] = {}
    for name, block in (
        ("torrent_A_as_authored", TORRENT_AS_AUTHORED_BLOCK),
        ("torrent_B_repair", TORRENT_REPAIR_BLOCK),
        ("torrent_C_constant_used_helper_dead", TORRENT_CONSTANT_USED_HELPER_DEAD_BLOCK),
    ):
        dest = stage(torrent, work / name)
        (dest / TORRENT_REL).write_text(
            text.replace(TORRENT_REPAIR_BLOCK, block, 1), encoding="utf-8"
        )
        out[name] = scan(dest)
    return out


def fray_shapes(fray: Path, work: Path) -> dict[str, object]:
    """E-035's mutation, on the real file at the blob it was measured against.

    The adoption commit is found by content, not by a typed sha: the parent of
    the newest commit that introduced ``resilient_mlkit.core.served`` into the
    gate. If no such commit exists in this checkout the driver refuses.
    """
    log = git(fray, "log", "--format=%H", "--follow", "--", FRAY_REL).split()
    adoption = None
    for sha in log:
        blob = git(fray, "show", f"{sha}:{FRAY_REL}")
        parent_blob = ""
        try:
            parent_blob = git(fray, "show", f"{sha}^:{FRAY_REL}")
        except Refused:
            parent_blob = ""
        if "resilient_mlkit.core.served" in blob and (
            "resilient_mlkit.core.served" not in parent_blob
        ):
            adoption = sha
    if adoption is None:
        raise Refused(
            f"{fray}: no commit in the history of {FRAY_REL} introduces "
            "resilient_mlkit.core.served, so E-035's pre-adoption blob cannot be named"
        )
    pre = git(fray, "show", f"{adoption}^:{FRAY_REL}")
    out: dict[str, object] = {
        "adoption_commit": adoption,
        "pre_adoption_commit": git(fray, "rev-parse", f"{adoption}^").strip(),
    }
    for name, source in (
        ("fray_E035_pre_adoption", pre),
        ("fray_E035_dead_import", FRAY_DEAD_IMPORT + pre),
    ):
        dest = stage(fray, work / name)
        (dest / FRAY_REL).write_text(source, encoding="utf-8")
        out[name] = scan(dest)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--torrent", type=Path, help="a resilient-torrent checkout")
    ap.add_argument("--fray", type=Path, help="a resilient-fray checkout")
    ap.add_argument("--fleet", type=Path, help="a directory of resilient-* checkouts")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    args.workdir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "report_type": "r12_decision_scoped_exemption_drive",
        "generated_by": "scripts/r12_decision_scoped_drive.py",
        "mlkit_file": resilient_mlkit.__file__,
        "mlkit_version": resilient_mlkit.__version__,
        # `mlkit_version` cannot identify a build (E-M24): two builds 40 commits
        # apart answer it identically. The identity travels beside it.
        "mlkit_build": identity_mod.build_identity().to_dict(),
        "scanner_file": sr.__file__,
    }
    if args.torrent:
        payload["torrent_head"] = git(args.torrent, "rev-parse", "HEAD").strip()
        payload["torrent"] = torrent_shapes(args.torrent.resolve(), args.workdir)
    if args.fray:
        payload["fray_head"] = git(args.fray, "rev-parse", "HEAD").strip()
        payload["fray"] = fray_shapes(args.fray.resolve(), args.workdir)
    if args.fleet:
        fleet: dict[str, object] = {}
        for child in sorted(args.fleet.iterdir()):
            if child.is_dir() and child.name.startswith("resilient-"):
                fleet[child.name] = scan(child)
        payload["fleet"] = fleet

    text = json.dumps(payload, indent=1, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
