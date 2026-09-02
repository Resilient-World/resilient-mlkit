"""Every registered check, every in-scope repo, one JSON record per row.

CONTROL B leg 3 (the E-M18 shape): run this under the main interpreter and the
branch interpreter and diff the records. `resilient_mlkit.__file__` is asserted
against MLKIT_TREE on both sides, so a record can never be attributed to the
wrong tree.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import resilient_mlkit
from resilient_mlkit import checks as checks_mod
from resilient_mlkit.checks import PHASE_ORDER, RunContext
from resilient_mlkit.core.repo import Repo

tree = Path(os.environ["MLKIT_TREE"]).resolve()
assert Path(resilient_mlkit.__file__).resolve().parents[2] == tree, (
    f"interpreter is driving {resilient_mlkit.__file__}, not {tree}"
)

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
records = []
for repo_path in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    repo = Repo(name=repo_path.name.replace("resilient-", ""), path=repo_path)
    ctx = RunContext(nonce="i2m1-sweep", root=ROOT, offline=True)
    checks_mod.load_all()
    specs = [s for phase in PHASE_ORDER for s in checks_mod.for_phase(phase)]
    for spec in specs:
        try:
            result = spec.fn(repo, ctx)
            row = {
                "repo": repo.name,
                "check": result.check_id,
                "phase": result.phase,
                "status": result.status.name,
                "reason": result.reason,
                "evidence": result.evidence,
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "repo": repo.name,
                "check": spec.check_id,
                "raised": f"{type(exc).__name__}: {exc}",
            }
        records.append(row)
    repo.release()

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(records, indent=2, sort_keys=True, default=str) + "\n")
print(f"{resilient_mlkit.__file__} -> {len(records)} rows")
