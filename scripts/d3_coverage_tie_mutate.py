"""CONTROL C: mutate each guard alone; every mutation must be caught.

Usage: python scripts/d3_coverage_tie_mutate.py <out.json> [<repo root>]
Runs against the checkout it lives in unless a root is given, and drives that
checkout's own `.venv/bin/python`.

A control that cannot die is not a control. Each mutation below removes ONE
guard, the suite is re-run, and the file is restored with its sha256 asserted
byte-identical afterwards -- so a mutation cannot survive into the branch.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
CE = ROOT / "src/resilient_mlkit/core/coverage_evidence.py"
DEC = ROOT / "src/resilient_mlkit/checks/decision.py"
PYTEST = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-x",
          "tests/test_d3_coverage_tie.py", "tests/test_decision_controls.py",
          "tests/test_nonfinite_controls.py"]

MUTATIONS = [
    ("M1 untied refusal removed", CE,
     '''    if not has_rows and not has_groups:
        raise CoverageUntied(''',
     '''    if False:
        raise CoverageUntied('''),
    ("M2 digest requirement removed", CE,
     '''    if DIGEST_KEY not in payload:
        raise CoverageUntied(''',
     '''    if False:
        raise CoverageUntied('''),
    ("M3 digest comparison removed", CE,
     "    if derived.digest != claimed:",
     "    if False:"),
    ("M4 sha256 shape check removed", CE,
     "    if not isinstance(claimed, str) or not _SHA256_HEX.fullmatch(claimed):",
     "    if False:"),
    ("M5 n comparison removed", CE,
     "    if reported_n != derived.n:",
     "    if False:"),
    ("M6 empirical comparison removed", CE,
     "    if gap > EMPIRICAL_AGREEMENT_EPS:",
     "    if False:"),
    ("M7 indicator becomes truthiness", CE,
     "    if value is True:\n        return 1",
     "    if True:\n        return int(bool(value))"),
    ("M8 duplicate-key refusal removed", CE,
     "            raise CoverageRefused(\n                MALFORMED,\n                f\"{unit} key {key!r} appears more than once.",
     "            raise SystemExit(\n                MALFORMED,\n                f\"{unit} key {key!r} appears more than once."),
    ("M9 both-forms refusal removed", CE,
     "    if has_rows and has_groups:",
     "    if False and has_rows and has_groups:"),
    ("M10 group covered>n refusal removed", CE,
     "        if hits > size:",
     "        if False:"),
    ("M11 tie not called at all", DEC,
     "        derived = coverage_evidence.derive(out)",
     "        derived = coverage_evidence.DerivedCoverage(\n            unit='row', n=n, covered=round(empirical * n), digest='x' * 64\n        )"),
    ("M12 untied reported as FAIL not NA", DEC,
     "    except coverage_evidence.CoverageUntied as untied:\n        return CheckResult.na(",
     "    except coverage_evidence.CoverageUntied as untied:\n        return CheckResult.failed("),
    ("M13 self-reported refusal ignored", DEC,
     "    if mismatch is not None:",
     "    if False:"),
    ("M14 verdicts taken on the reported figures", DEC,
     "    n, empirical = derived.n, derived.empirical",
     "    n, empirical = n, empirical"),
]

records = []
for name, path, old, new in MUTATIONS:
    original = path.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode()
    assert old in text, f"{name}: mutation target not found (the code moved)"
    path.write_bytes(text.replace(old, new, 1).encode())
    try:
        proc = subprocess.run(
            PYTEST, cwd=ROOT, capture_output=True, text=True, check=False
        )
        caught = proc.returncode != 0
        tail = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAILED") or " passed" in ln or " failed" in ln]
    finally:
        path.write_bytes(original)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before, f"{name}: {path} not restored ({before} -> {after})"
    records.append({
        "mutation": name,
        "file": path.name,
        "caught": caught,
        "first_failures": tail[:3],
        "sha256_restored": after,
    })
    print(f"{'CAUGHT ' if caught else 'SURVIVED'} {name}  {tail[:1]}")

out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if out:
    out.write_text(json.dumps(records, indent=2) + "\n")
print(f"\n{sum(r['caught'] for r in records)}/{len(records)} mutations caught")
