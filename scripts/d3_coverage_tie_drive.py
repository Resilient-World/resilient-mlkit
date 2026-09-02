"""Drive D3 against a real git repo whose committed .mlkit/repo.toml declares 0.90.

Usage: python drive_d3.py <case> [<outdir>]
Asserts resilient_mlkit.__file__ so the tree under test is never in doubt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import d3_uncertainty_coverage
from resilient_mlkit.core.repo import Repo

print(f"resilient_mlkit.__file__ = {resilient_mlkit.__file__}")
assert Path(resilient_mlkit.__file__).resolve().parents[2] == Path(
    os.environ["MLKIT_TREE"]
).resolve(), (
    f"interpreter is driving {resilient_mlkit.__file__}, not {os.environ['MLKIT_TREE']}"
)

CASE = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


BODIES = {
    # E-M23 residual 2's own payload, verbatim.
    "untied": '''
def coverage():
    return {"nominal": 0.90, "empirical": 0.90, "n": 1000000}
''',
    # A real tied artifact, persisted to JSON beside the module and returned
    # verbatim. `stomp_*` cases edit the PERSISTED artifact, not the code.
    "tied": None,
}


def rows_artifact(path: Path, *, n: int, covered: int, nominal: float) -> dict:
    from resilient_mlkit.core.served import row_set_digest

    rows = [{"row_id": f"holdout-{i:06d}", "covered": i < covered} for i in range(n)]
    payload = {
        "nominal": nominal,
        "empirical": covered / n,
        "n": n,
        "row_set_digest": row_set_digest([r["row_id"] for r in rows]),
        "rows": rows,
    }
    path.write_text(json.dumps(payload))
    return payload


TIED_MODULE = '''
import json
from pathlib import Path

def coverage():
    return json.loads(Path(__file__).with_name("evidence.json").read_text())
'''


def build(root: Path, case: str) -> None:
    (root / ".mlkit").mkdir(parents=True, exist_ok=True)
    (root / ".mlkit" / "repo.toml").write_text(
        '[repo]\nname = "fixturerepo"\n\n[bindings]\ncoverage = "b:coverage"\n'
        "\n[coverage]\nnominal = 0.90\n"
    )
    if case == "untied":
        (root / "b.py").write_text(BODIES["untied"])
    else:
        (root / "b.py").write_text(TIED_MODULE)
        payload = rows_artifact(root / "evidence.json", n=5000, covered=4477, nominal=0.90)
        if case == "tied":
            pass
        elif case == "stomp_empirical":
            payload["empirical"] = 0.90
        elif case == "stomp_n":
            payload["n"] = 1000000
        elif case == "stomp_digest":
            payload["row_set_digest"] = "0" * 64
        elif case == "stomp_covered_value":
            payload["rows"][0]["covered"] = "yes"
        elif case == "duplicate_row":
            payload["rows"][1]["row_id"] = payload["rows"][0]["row_id"]
        elif case == "both_forms":
            payload["groups"] = [{"group_id": "g", "n": 5000, "covered": 4477}]
        elif case == "no_digest":
            del payload["row_set_digest"]
        else:
            raise SystemExit(f"unknown case {case}")
        if case != "tied":
            (root / "evidence.json").write_text(json.dumps(payload))
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fixture")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root, CASE)
    repo = Repo(name="fixturerepo", path=root)
    try:
        result = d3_uncertainty_coverage(repo, RunContext(nonce="i2m1-control", root=root))
    finally:
        repo.release()

ev = dict(result.evidence)
ev.pop("rows", None)
record = {
    "case": CASE,
    "mlkit_file": resilient_mlkit.__file__,
    "status": result.status.name,
    "reason": result.reason,
    "evidence": ev,
}
print(json.dumps(record, indent=2, sort_keys=True, default=str))
if OUT is not None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
