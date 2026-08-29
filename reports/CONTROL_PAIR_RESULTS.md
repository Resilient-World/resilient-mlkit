# Results — control pairs for the unchecked checks

Answers the pre-registration at `reports/CONTROL_PAIR_PREREGISTRATION.md`
(committed `f00bff3`, before any test below was written or run). Branch
`feat/loop-mlkit-3`, off `main` at `0ca5cae`.

## Provenance

Measured with `.venv/bin/python -m pytest <file> -q --timeout=180` on
Python 3.14.6, `resilient-mlkit` 0.4.0, at git SHA `48b6398`. No network, no
GPU, no data, no cloud call, and no fit: every fixture is a pure-Python function
written into a `tmp_path` and resolved through the same `.mlkit/repo.toml`
binding path the eight repos use. There is no seed to record because nothing
here is stochastic.

| File | sha256 | Controls | Result |
|---|---|---|---|
| `tests/test_decision_controls.py` | `b934cec7fee6d45c…` | 29 | 29 passed |
| `tests/test_economics_controls.py` | `c5d1e70cf1ef6b91…` | 29 | 29 passed |
| `tests/test_triage_controls.py` | `8f00ea75011e2126…` | 25 | 25 passed |
| `tests/test_selection_controls.py` | `6bd99c25bacfea35…` | 18 | 18 passed |
| `tests/test_readiness_controls.py` | `b64e66d1a10652e3…` | 32 | 32 passed |
| **total** | | **133** | **133 passed in 2.65 s** |

Source files changed:

| File | sha256 |
|---|---|
| `src/resilient_mlkit/checks/decision.py` | `0af887f10231d87f…` |
| `src/resilient_mlkit/checks/economics.py` | `88c18ba95a67b6ec…` |

Regression set, run focused at the same SHA — `tests/test_fleet.py`,
`test_r3_blocked_splits.py`, `test_r5_data_provenance.py`,
`test_fabricated_defaults.py` (R10, and the only R8 coverage in the suite),
`test_fabricated_targets.py` (R11), `test_promotion_state.py`,
`test_version_declaration.py`, `test_derivation.py`: **203 passed in 12.52 s**.
`ruff 0.16.5` clean on `src` and `tests`; `mypy 2.3.1` clean on 25 source files.

## Coverage before and after

Checks with a control-pair suite before this branch: R3, R5, R8 (partial, via
R10's fixtures), R10, R11. Checks with one after it: those, plus **T1, T2, T3,
T4, T5, S1, S2, S3, S4, R1, R2, R4, R6, R7, R9, D2, D3, E1, E2, E3**.

Not covered, and deliberately: D1, D4, D5, S5, E4, E5 are `human_only=True` and
return ESCALATED unconditionally. There is nothing for a pair to distinguish.

## The pre-registered predictions, answered

**Prediction 1 — the specified branches all exist and can be driven.** Held for
D2-1..D2-7 and E1-1..E1-7 with one exception, which was a defect in the fixture
and not in the check: `(1.01 - 1.00) / 1.00` is `0.010000000000000009` in binary
floating point, so the exact-epsilon boundary case landed on the passing side of
`gain <= 0.01`. The fixture was changed to `100.0 -> 101.0`, which divides to
the double nearest `0.01`. The threshold was not touched.

**Prediction 2 — a non-finite figure defeats both hard stops.** Confirmed, on
both, and this is the finding of the iteration. Measured at `245ee97` and
`548a686`, before either repair:

| Check | Binding reports | Verdict before | Verdict after |
|---|---|---|---|
| D2 | `estimate`/`ci_low`/`ci_high` = `nan` | **PASS** | FAIL, "non-finite estimate, ci_low, ci_high" |
| D2 | the same as the strings `"nan"` | **PASS** | FAIL, same reason |
| D2 | `estimate` = `nan`, interval finite | **PASS** | FAIL, "non-finite estimate" |
| D2 | `reference_effect` = `nan` | **PASS** | FAIL, "reference_effect is not finite" |
| D2 | interval `[-inf, +inf]` | FAIL (no power) | FAIL, "non-finite ci_low, ci_high" |
| E1 | curve at 10% and 25% = `nan` | **PASS** | FAIL, "not finite at fraction(s) 0.1, 0.25" |
| E1 | curve at 25% = `nan` | **PASS** | FAIL, "not finite at fraction(s) 0.25" |
| E1 | curve at 25% = `inf` | **PASS** | FAIL, "not finite at fraction(s) 0.25" |
| E1 | curve as the strings `"nan"` | **PASS** | FAIL, "not finite at fraction(s) 0.1, 0.25" |

Every comparison a NaN takes part in is False, so `lo > 0`, `hi < 0`,
`half_width >= reference` and `gain <= FLATNESS_EPSILON` are all False together.
Both hard stops — the only two verdicts in the package that stop a repo — could
be switched off by the absence of a number. The `inf` row is the sharpest: an
infinite point at 25% makes the gain read `+inf`, so the flattest possible probe
reported as the steepest.

Repairs are in `src/` (`591e25c`, `3647a04`), not in the tests, and each is
placed so it cannot downgrade an existing verdict: D2's guard sits *after* the
CI-excludes-zero branch, so `[-inf, -1]` still halts; E1's sits after the
missing-fractions refusal and before the gain is computed.

**Prediction 3 — no compute.** Held. Total wall-clock for all 133 controls is
2.65 s and nothing was fitted, downloaded or billed.

## Honest negatives

* **No defect was found in T1–T5, S1–S4, R1, R2, R4, R6, R7, R9, D3, E2 or
  E3.** All 104 controls over those eighteen checks passed on their first run.
  That is a weaker result than the two hard stops produced and it is reported as
  it stands; nothing was tuned to make one of them fire.
* **One coverage claim is limited by construction and says so in place.** R9's
  passing fixture renders `NOTICE.md` through the same `policy.render_notice`
  the check compares against, so that half asserts drift-freedom, not renderer
  correctness. The firing halves (absent, and hand-edited) are unaffected.
* **`__version__` is deliberately not bumped**, although the D2/E1 repairs earn
  a major bump under this repo's own scale. PR #6 is open and already claims
  `0.5.0` for different content. Recorded as `docs/ESCALATIONS.md` E-M09 rather
  than decided here.

## Recommended, not run

One full `.venv/bin/python -m pytest tests -q --timeout=180` in this repo's own
venv, with the output committed. The suite has never been executed end to end in
CI (E-M07), and everything above is focused runs of named files. That is the
right next measurement and it is a recommendation, not a result.
