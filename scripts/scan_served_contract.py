#!/usr/bin/env python3
"""Run R12's scanner across the fleet, read-only, and write ONE report here.

Why this exists rather than ``mlkit check --phase readiness``
------------------------------------------------------------
The phase runner writes each check's finding list INTO the repo it measured —
R11 writes ``reports/fabricated_targets.md`` there, and R12 writes
``reports/served_contract.md``. That is right when a repo runs its own gate and
wrong here: ``resilient-triage`` is a colleague repo and is read-only in this
round, and running the phase would also import every other repo's bindings for
checks this round has nothing to do with.

So this calls the scanner directly. It reads Python files, parses them, and
writes exactly one file, in mlkit's own ``reports/``. No repo other than mlkit
is touched.

Authorization: A-1 — local CPU, no cloud, no GPU, no spend. Nothing is fitted;
this is an ``ast`` walk.

Usage:
    python scripts/scan_served_contract.py [--root DIR] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resilient_mlkit import __version__
from resilient_mlkit.core import identity as identity_mod
from resilient_mlkit.core.repo import PORTFOLIO, find_root
from resilient_mlkit.core.served_reimplementation import (
    CONTRACT_MODULE,
    REIMPLEMENTED,
    scan_repo,
)


def git_sha(path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "reports" / "served_contract_fleet.json"
    )
    args = parser.parse_args(argv)

    root = args.root or find_root(REPO_ROOT)
    repos: list[dict[str, object]] = []
    for name in PORTFOLIO:
        path = root / f"resilient-{name}"
        if not path.is_dir():
            repos.append({
                "repo": name,
                "verdict": "NA",
                "reason": f"resilient-{name} is not checked out under {root}",
            })
            continue
        findings, walked = scan_repo(path)
        reimplemented = [f for f in findings if f.severity == REIMPLEMENTED]
        files: list[str] = []
        for f in findings:
            if f.path not in files:
                files.append(f.path)
        repos.append({
            "repo": name,
            "git_sha": git_sha(path),
            "files_walked": walked,
            "verdict": "FAIL" if findings else ("PASS" if walked else "NA"),
            "reason": "" if walked else "no Python files walked; unmeasured",
            "findings": len(findings),
            "contract_reimplemented": len(reimplemented),
            "files_named": files,
            "clauses": sorted({f.clause for f in findings}),
            "detail": [f.to_dict() for f in findings],
        })

    report = {
        "report_type": "served_contract_fleet_scan",
        "question": (
            "which repos decide a served-model contract clause locally instead of "
            f"routing through {CONTRACT_MODULE}?"
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "mlkit_version": __version__,
        "mlkit_git_sha": git_sha(REPO_ROOT),
        # E-M24: which mlkit's scanner produced these findings. The scanner is
        # core/served_reimplementation.py, which also moved between the two
        # builds that declare the same version.
        "mlkit_build": identity_mod.build_identity().to_dict(),
        "python": sys.version.split()[0],
        "portfolio_root": str(root),
        "contract_module": CONTRACT_MODULE,
        "note": (
            "READ-ONLY across the fleet: this script parses Python and writes one "
            "file, inside mlkit. No repo other than mlkit is modified. A PASS here "
            "today would be evidence the scanner is blind rather than evidence a "
            "repo is clean -- nothing has adopted the contract yet."
        ),
        "repos": repos,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for entry in repos:
        print(
            f"{entry['verdict']:>4}  {entry['repo']:<12} "
            f"findings={entry.get('findings', '-'):<4} "
            f"files={len(entry.get('files_named', []) or [])!s:<3} "
            f"walked={entry.get('files_walked', '-')}"
        )
    print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
