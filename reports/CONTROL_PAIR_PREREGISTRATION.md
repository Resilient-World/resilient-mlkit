# Pre-registration — control pairs for the unchecked checks

Written and committed **before** any of the tests below were run, so that the
commit order shows the rule preceding the result. Branch `feat/loop-mlkit-3`,
off `main` at `0ca5cae`.

## Why

`mlkit` is the instrument the eight repos are measured with, and most of its
own checks have never been forced to fire. The suite has control pairs for
R3, R5, R10, R11 and R12 (`tests/test_r3_blocked_splits.py`,
`tests/test_r5_data_provenance.py`, `tests/test_fabricated_defaults.py`,
`tests/test_fabricated_targets.py`, `tests/test_served_contract.py`) and none
for the two checks whose verdict is a **hard stop for the whole repo**:
`D2` (placebo) and `E1` (scaling probe). A hard stop that cannot fire is worse
than no hard stop, because it reads as coverage.

## What each pair must show

A pair is only a pair if both halves are present. Firing alone is consistent
with a check that fires on everything; silence alone is consistent with a
check that fires on nothing.

### D2 — PLACEBO_TEST (hard stop)

| # | Fixture | Required verdict |
|---|---|---|
| D2-1 | placebo estimate with CI excluding zero, either side | FAIL **and** `evidence["halt"] is True` |
| D2-2 | powered null: CI straddles zero, `reference_effect` reported, half-width strictly smaller than it | PASS, no `halt` |
| D2-3 | underpowered null **with** `reference_effect`: half-width ≥ reference | FAIL, and **no** `halt` — a broken test is not a hard stop |
| D2-4 | null with **no** `reference_effect` | NA, naming `reference_effect` |
| D2-5 | binding absent | NA |
| D2-6 | binding raises | FAIL |
| D2-7 | D2-1's result fed to `portfolio.resolve` | `BLOCKED`, reason `"D2 hard stop: …"` |

`halt` is the field `portfolio.resolve` keys the hard stop off
(`src/resilient_mlkit/portfolio.py:52,68`). D2-3 vs D2-1 is the pair that says
the halt means what it says: two FAILs, only one of which stops the repo.

### E1 — SCALING_PROBE (hard stop)

| # | Fixture | Required verdict |
|---|---|---|
| E1-1 | curve flat between 10% and 25% (`gain_10_to_25 <= 0.01`) | FAIL **and** `evidence["halt"] is True` |
| E1-2 | curve rising well past the epsilon | PASS, no `halt` |
| E1-3 | orientation contract, **un-oriented**: an error metric reported raw, so the improving run reads as a falling curve | FAIL + halt |
| E1-4 | orientation contract, **oriented**: the same run reported larger-is-better | PASS |
| E1-5 | a declared fraction missing | FAIL naming it |
| E1-6 | binding absent | NA |
| E1-7 | E1-1's result fed to `portfolio.resolve` | `BLOCKED`, reason `"E1 hard stop: …"` |

E1-3/E1-4 are the same measurement under the two readings of the contract in
`economics.py:56`. If they do not differ, the contract is decorative.

## Falsification — what would make this work wrong

* Any fixture that has to be shaped to a threshold rather than to the check's
  own contract. Thresholds, ranges and holdouts are not touched here
  (CLAUDE.md rule 6); if a fixture cannot be made to fire without moving one,
  that is the finding and it gets reported, not tuned around.
* A pair where both halves pass for the same reason (e.g. both return NA)
  is not a pair, and is recorded as no coverage for that check.
* If a check turns out to be structurally unable to fire, the repair goes in
  `src/` with the check ID in the commit — never in the test.

## Predicted results, recorded before running

Recorded so that a green first run reads as a blind test rather than a clean
instrument:

1. **D2-1..D2-7 and E1-1..E1-7 are expected to pass as specified.** The
   branches they exercise are all visibly present in the two source files.
2. **A non-finite figure is predicted to defeat both hard stops.** `float()`
   accepts `nan`, and `nan > 0`, `nan < 0` and `nan <= 0.01` are all `False`,
   so a placebo or a scaling probe reporting NaN is predicted to reach `PASS`
   rather than either hard stop. This is the same defect class the R5 count
   guard was repaired for at `00210b6`. If the prediction holds, the repair is
   a root fix in `src/`, committed after the failing controls, and this repo's
   own scale makes that a **major** version event (an existing check changing
   verdict on unchanged code).
3. Nothing here measures a model, reads a split, or costs compute. Every
   fixture is a pure-Python function written into a temporary directory and
   resolved through the same `.mlkit/repo.toml` path the eight real repos use.

## Order of work after the hard stops

D3, E2, E3, then T1–T5, S1–S4, then R1, R2, R4, R6, R7, R9 — cheapest and
most decisive first, and stopping wherever the iteration stops rather than
thinning every pair to fit.
