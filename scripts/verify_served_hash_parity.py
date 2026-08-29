#!/usr/bin/env python3
"""Does the contract's digest reproduce every committed champion hash in the fleet?

WHY THIS EXISTS
---------------
The refactor's prime directive is that behaviour must not change. For a served
model the behaviour that must not change is its IDENTITY: every committed
champion artifact in the fleet carries an ``artifact_sha256`` that its own
repo's local ``canonical_payload_sha256`` produced. If mlkit's contract computed
that digest even slightly differently — a different separator, a different key
ordering, ``allow_nan`` left at its default — then adopting the contract would
make every one of those artifacts fail its own load-time check, and the fix
would look like "update the recorded hash", which is exactly how a provenance
chain gets quietly rewritten.

So this asserts the identity directly. For each committed artifact it recomputes
the digest with ``resilient_mlkit.core.served.canonical_payload_sha256`` and
compares it to the hash the artifact already carries — the output of the repo's
own local function at the time it was written. No repo module is imported and
no repo file is modified; this reads JSON and hashes bytes.

Authorization: A-1 — local CPU, no cloud, no GPU, no spend. Nothing is fitted.

Usage:
    python scripts/verify_served_hash_parity.py [--root DIR] [--out FILE]

Exit code 0 when every artifact found reproduces, 2 otherwise, and 2 also when
no artifact was found at all: a parity report over nothing that prints green is
the defect this script exists to catch, applied to the script.
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

from resilient_mlkit import __version__  # noqa: E402
from resilient_mlkit.core.repo import PORTFOLIO, find_root  # noqa: E402
from resilient_mlkit.core.served import HASH_KEY, canonical_payload_sha256  # noqa: E402

#: Directories that hold a checkout's scratch copies rather than its tree. A
#: worktree carries a byte-identical duplicate of the same artifact, which would
#: inflate the count without adding evidence.
SKIP_PARTS = frozenset({".git", ".venv", "node_modules", ".worktrees", "__pycache__"})


def git_sha(path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def candidate_artifacts(repo: Path) -> list[Path]:
    """Every JSON under a ``models/`` tree that carries a self-hash."""
    found: list[Path] = []
    for path in sorted((repo / "models").rglob("*.json")) if (repo / "models").is_dir() else []:
        if SKIP_PARTS & set(path.parts):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get(HASH_KEY):
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "reports" / "served_hash_parity.json"
    )
    args = parser.parse_args(argv)

    root = args.root or find_root(REPO_ROOT)
    rows: list[dict[str, object]] = []
    for name in PORTFOLIO:
        repo = root / f"resilient-{name}"
        if not repo.is_dir():
            rows.append({
                "repo": name,
                "status": "NA",
                "reason": f"resilient-{name} is not checked out under {root}",
            })
            continue
        artifacts = candidate_artifacts(repo)
        if not artifacts:
            rows.append({
                "repo": name,
                "git_sha": git_sha(repo),
                "status": "NA",
                "reason": "no committed artifact under models/ carries an "
                          f"{HASH_KEY}; this repo serves nothing hash-pinned yet",
            })
            continue
        for path in artifacts:
            payload = json.loads(path.read_text(encoding="utf-8"))
            recorded = str(payload[HASH_KEY])
            recomputed = canonical_payload_sha256(payload)
            rows.append({
                "repo": name,
                "git_sha": git_sha(repo),
                "artifact": str(path.relative_to(repo)),
                "recorded_sha256": recorded,
                "recomputed_sha256": recomputed,
                "status": "MATCH" if recorded == recomputed else "DIFFER",
            })

    compared = [r for r in rows if r["status"] in {"MATCH", "DIFFER"}]
    matched = [r for r in compared if r["status"] == "MATCH"]
    differed = [r for r in compared if r["status"] == "DIFFER"]

    report = {
        "report_type": "served_hash_parity",
        "question": (
            "does resilient_mlkit.core.served.canonical_payload_sha256 reproduce the "
            "artifact_sha256 each repo's own local function already committed?"
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "mlkit_version": __version__,
        "mlkit_git_sha": git_sha(REPO_ROOT),
        "python": sys.version.split()[0],
        "portfolio_root": str(root),
        "artifacts_compared": len(compared),
        "matched": len(matched),
        "differed": len(differed),
        "rows": rows,
        "note": (
            "Duplicates inside .worktrees are excluded: a worktree carries a "
            "byte-identical copy of the same artifact and would inflate the count "
            "without adding evidence."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for row in rows:
        print(f"{row['status']:>6}  {row['repo']:<12} {row.get('artifact', row.get('reason', ''))}")
    print(f"\ncompared {len(compared)}; matched {len(matched)}; differed {len(differed)}")
    print(f"wrote {args.out}", file=sys.stderr)

    if not compared:
        print(
            "NO ARTIFACT COMPARED — this is not a pass. Parity is unmeasured.",
            file=sys.stderr,
        )
        return 2
    return 0 if not differed else 2


if __name__ == "__main__":
    raise SystemExit(main())
