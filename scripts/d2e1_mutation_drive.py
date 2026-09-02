#!/usr/bin/env python3
"""Mutation drive: break each new branch, confirm a named control fires.

A suite that passes first time is consistent with a suite that asserts
nothing. This applies one mutation at a time to the SOURCE, runs the control
files, and records which tests fail. A mutation nothing catches is a hole.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

#: The repo this script lives in. Derived, never hardcoded: a driver that
#: names one machine's checkout is evidence about that machine.
ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable

D2 = ROOT / "src/resilient_mlkit/checks/decision.py"
E1 = ROOT / "src/resilient_mlkit/checks/economics.py"
DECL = ROOT / "src/resilient_mlkit/core/declaration.py"

MUTATIONS = [
    ("M1 halt region ignored, always two-sided at zero", D2,
     "if (region.halts_above and lo > region.null) or (region.halts_below and hi < region.null):",
     "if lo > 0 or hi < 0:"),
    ("M2 declared region never halts", D2,
     "if (region.halts_above and lo > region.null) or (region.halts_below and hi < region.null):",
     "if region.is_default and (lo > region.null or hi < region.null):"),
    ("M3 halts_above swallows 'below'", D2,
     "        return self.indicts in (INDICTS_EITHER, INDICTS_ABOVE)",
     "        return True"),
    ("M4 halts_below always false", D2,
     "        return self.indicts in (INDICTS_EITHER, INDICTS_BELOW)",
     "        return False"),
    ("M5 estimand no longer required", D2,
     "    if not region.is_default and not estimand:",
     "    if False:"),
    ("M6 sign tie removed", D2,
     "        if indicting_sign and not (reported * indicting_sign > 0):",
     "        if False:"),
    ("M7 sign tie accepts zero", D2,
     "        if indicting_sign and not (reported * indicting_sign > 0):",
     "        if indicting_sign and not (reported * indicting_sign >= 0):"),
    ("M8 null_value finiteness not checked", D2,
     "        if parsed is None:",
     "        if False:"),
    ("M9 indicts value not checked", D2,
     "    if indicts not in INDICTS_VALUES:",
     "    if False:"),
    ("M10 is_default reads 'declared' instead of the numbers", D2,
     "        return self.null == DEFAULT_NULL and self.indicts == INDICTS_EITHER",
     "        return not self.declared"),
    ("M11 E1 reads the hardcoded 0.10/0.25 again", E1,
     "    second, top = fractions[-2], fractions[-1]",
     "    second, top = 0.10, 0.25"),
    ("M12 E1 top-rung floor removed", E1,
     "    if top < MIN_TOP_FRACTION:",
     "    if False:"),
    ("M13 E1 top-step bar removed", E1,
     "    if top / second > MAX_TOP_STEP + TOP_STEP_EPS:",
     "    if False:"),
    ("M14 E1 top-step bar off by one side", E1,
     "    if top / second > MAX_TOP_STEP + TOP_STEP_EPS:",
     "    if top / second >= MAX_TOP_STEP:"),
    ("M15 E1 top-rung floor off by one side", E1,
     "    if top < MIN_TOP_FRACTION:",
     "    if top <= MIN_TOP_FRACTION:"),
    ("M16 E1 ordering not checked", E1,
     "    if any(b <= a for a, b in pairwise(rungs)):",
     "    if False:"),
    ("M17 E1 rung count not checked", E1,
     "    if len(rungs) < MIN_RUNGS:",
     "    if False:"),
    ("M18 E1 rung range not checked", E1,
     "        if not 0.0 < value <= 1.0:",
     "        if False:"),
    ("M19 E1 missing fractions measured against the built-in ladder", E1,
     "    missing = [f for f in fractions if f not in curve]",
     "    missing = [f for f in DEFAULT_FRACTIONS if f not in curve]"),
    ("M20 working-tree attempt never noticed, so uncommitted silently defaults", DECL,
     "    attempted = _attempted_in_working_tree(repo, section)",
     "    attempted = False"),
    ("M26 D2 treats an uncommitted halt region as the default", D2,
     "    if decl.uncommitted:\n        return None, (",
     "    if False:\n        return None, ("),
    ("M27 E1 treats an uncommitted ladder as the default", E1,
     "    if decl.uncommitted:\n        return None, {}, (",
     "    if False:\n        return None, {}, ("),
    ("M28 halts_below swallows 'above'", D2,
     "        return self.indicts in (INDICTS_EITHER, INDICTS_BELOW)",
     "        return True"),
    ("M29 sign tie hardcodes 'above'", D2,
     "        if indicting_sign and not (reported * indicting_sign > 0):",
     "        if indicting_sign and not (reported > 0):"),
    ("M30 null_contained not measured", D2,
     '    evidence["null_contained"] = bool(lo <= region.null <= hi)',
     '    evidence["null_contained"] = True'),
    ("M31 null distance divides by the wrong operand", D2,
     '        evidence["null_distance_in_reference_effects"] = abs(estimate - region.null) / reference',
     '        evidence["null_distance_in_reference_effects"] = abs(estimate) / reference'),
    ("M21 declaration read from the WORKING TREE", DECL,
     "    ref = artifact.load(repo, REPO_CONFIG_RELPATH, allow_dirty=allow_dirty)",
     "    ref = artifact.load(repo, REPO_CONFIG_RELPATH, allow_dirty=True)"),
    ("M22 unknown keys ignored", DECL,
     "    if unknown:",
     "    if False:"),
    ("M23 bool/type refusal removed from finite_number", DECL,
     "    if isinstance(value, bool) or not isinstance(value, (int, float)):",
     "    if not isinstance(value, (int, float, str)):"),
    ("M24 non-finite refusal removed from finite_number", DECL,
     "    if not math.isfinite(number):",
     "    if False:"),
    ("M25 array-of-tables accepted", DECL,
     "    if not isinstance(decl.value, dict):",
     "    if False:"),
]

TESTS = [
    "tests/test_declared_hard_stops.py",
    "tests/test_decision_controls.py",
    "tests/test_economics_controls.py",
]


def run() -> tuple[int, list[str]]:
    out = subprocess.run(
        [PY, "-m", "pytest", *TESTS, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    failed = sorted({
        line.split("::")[1].split(" ")[0]
        for line in out.stdout.splitlines()
        if line.startswith(("FAILED ", "ERROR "))
    })
    return out.returncode, failed


def main() -> int:
    import resilient_mlkit
    assert pathlib.Path(resilient_mlkit.__file__).resolve().is_relative_to(ROOT / "src"), (
        resilient_mlkit.__file__
    )
    print(f"MODULE   resilient_mlkit.__file__ = {resilient_mlkit.__file__}")
    baseline_code, baseline_failed = run()
    print(f"BASELINE rc={baseline_code} failed={baseline_failed}")
    if baseline_code != 0:
        print("baseline is not green; aborting")
        return 1

    holes = []
    for name, path, old, new in MUTATIONS:
        original = path.read_text()
        if original.count(old) != 1:
            print(f"!! {name}: anchor appears {original.count(old)} times — NOT APPLIED")
            holes.append(name)
            continue
        path.write_text(original.replace(old, new, 1))
        try:
            code, failed = run()
        finally:
            path.write_text(original)
        if code == 0:
            print(f"HOLE   {name}: nothing caught it")
            holes.append(name)
        else:
            print(f"caught {name}: {', '.join(failed[:4])}{' …' if len(failed) > 4 else ''}")

    print()
    print(f"{len(MUTATIONS) - len(holes)}/{len(MUTATIONS)} mutations caught")
    if holes:
        print("HOLES:")
        for h in holes:
            print("  -", h)
    return 1 if holes else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    sys.exit(main())
