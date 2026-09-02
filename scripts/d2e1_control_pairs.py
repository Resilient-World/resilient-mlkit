#!/usr/bin/env python3
"""End-to-end control-pair drive through the mlkit CLI, not through pytest.

The unit controls call `d2_placebo_test` / `e1_scaling_probe` directly. This
drives `mlkit check --phase decision|economics` against real git repos on disk,
because a check that fires in a test and not through the CLI has not fired
where it matters -- the CLI is what an adopter runs and what the readiness
tables are generated from.

Every run asserts `resilient_mlkit.__file__` first, so the verdicts below are
demonstrably this tree's and not a wheel installed elsewhere.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import resilient_mlkit
from resilient_mlkit.checks import RunContext, decision, economics
from resilient_mlkit.core.repo import Repo

for module in (resilient_mlkit, decision, economics):
    assert Path(module.__file__).resolve().is_relative_to(SRC), module.__file__
print(f"MODULE   resilient_mlkit.__file__ = {resilient_mlkit.__file__}")
print(f"MODULE   checks.decision.__file__ = {decision.__file__}")
print(f"MODULE   checks.economics.__file__ = {economics.__file__}")
print(f"VERSION  {resilient_mlkit.__version__}")
print()

# fray's measured figures (round 8 adjudication §2.4 and the unseen-year run).
LO, HI = -71.998, -53.146
EST = (LO + HI) / 2.0
REF = 151.74139194139195 - 128.9300068339915          # +22.81138510740044
AT10, AT25 = -151.29137, -138.13969

BINDINGS = f'''
def placebo_test():
    return {{"estimate": {EST!r}, "ci_low": {LO!r}, "ci_high": {HI!r},
            "reference_effect": {REF!r}, "run_id": "fray-placebo"}}


def placebo_beats_the_floor():
    """The same estimand, a placebo that SHOWS SKILL. This is leakage."""
    return {{"estimate": 17.0, "ci_low": 8.0, "ci_high": 26.0,
            "reference_effect": {REF!r}, "run_id": "fray-placebo-leak"}}


def scaling_probe():
    return {{0.05: -170.0, 0.10: {AT10!r}, 0.25: {AT25!r}}}


def scaling_probe_flat():
    """The same ladder, 10% -> 25% buying a quarter of a percent."""
    return {{0.05: -170.0, 0.10: {AT10!r}, 0.25: {AT10!r} * 0.9975}}
'''


def build(tmp: Path, *, placebo: str, probe: str, declare: bool) -> Repo:
    (tmp / "fray_bindings.py").write_text(BINDINGS)
    (tmp / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = (
        '[repo]\nname = "fray"\n\n[bindings]\n'
        f'placebo_test = "fray_bindings:{placebo}"\n'
        f'scaling_probe = "fray_bindings:{probe}"\n'
    )
    if declare:
        toml += (
            '\n[placebo]\n'
            'estimand = "skill against the persistence floor, lb/ac"\n'
            'null_value = 0.0\n'
            'indicts = "above"\n'
            '\n[scaling]\nfractions = [0.05, 0.10, 0.25]\n'
        )
    (tmp / ".mlkit" / "repo.toml").write_text(toml)
    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.invalid"),
        ("config", "user.name", "t"),
        ("add", "-A"),
        ("commit", "-qm", "fixture"),
    ):
        subprocess.run(["git", "-C", str(tmp), *args], check=True, capture_output=True)
    return Repo(name="fray", path=tmp)


def drive(label: str, *, placebo: str, probe: str, declare: bool) -> dict:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        repo = build(tmp, placebo=placebo, probe=probe, declare=declare)
        ctx = RunContext(nonce="drive", root=tmp, offline=True)
        try:
            d2 = decision.d2_placebo_test(repo, ctx)
            e1 = economics.e1_scaling_probe(repo, ctx)
        finally:
            repo.release()
    out = {
        "label": label,
        "D2": {"status": str(d2.status), "halt": d2.evidence.get("halt", False),
               "reason": (d2.reason or "")[:160]},
        "E1": {"status": str(e1.status), "halt": e1.evidence.get("halt", False),
               "reason": (e1.reason or "")[:160]},
    }
    print(f"--- {label}")
    print(f"    D2  {out['D2']['status']:4}  halt={out['D2']['halt']}  {out['D2']['reason']}")
    print(f"    E1  {out['E1']['status']:4}  halt={out['E1']['halt']}  {out['E1']['reason']}")
    print()
    return out


results = [
    drive("A  UNDECLARED, fray's honest figures — the SPURIOUS pair (§2.4)",
          placebo="placebo_test", probe="scaling_probe", declare=False),
    drive("B  DECLARED, the same figures — the honest pair",
          placebo="placebo_test", probe="scaling_probe", declare=True),
    drive("C  DECLARED, a placebo that beats the floor + a flat curve — NOT DEAD",
          placebo="placebo_beats_the_floor", probe="scaling_probe_flat", declare=True),
]

expected = [
    ("A", "FAIL", True, "FAIL", False),   # D2 spurious halt; E1 fails on CONTRACT (no halt)
    ("B", "PASS", False, "PASS", False),  # both silent on the declared contract
    ("C", "FAIL", True, "FAIL", True),    # both hard stops fire under the declaration
]
ok = True
for row, (name, d2s, d2h, e1s, e1h) in zip(results, expected):
    got = (row["D2"]["status"], row["D2"]["halt"], row["E1"]["status"], row["E1"]["halt"])
    want = (d2s, d2h, e1s, e1h)
    if got != want:
        print(f"MISMATCH {name}: got {got} want {want}")
        ok = False
print(json.dumps(results, indent=2))
print("\nALL THREE ROWS AS PREREGISTERED" if ok else "\nDIVERGENCE — see above")
sys.exit(0 if ok else 1)
