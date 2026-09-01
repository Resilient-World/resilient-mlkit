# Results — making D2 and E1 bindable without making them weaker

Against `reports/D2E1_CONTRACT_PREREGISTRATION.md`, committed as `79c68f8`,
the first commit on `feat/m-d2e1-declared-contract`, off `main` at `6921e9a`
and **before any edit to `src/`**.

Every figure below was produced by running the commands quoted. Every driver
asserts `resilient_mlkit.__file__` before it measures anything, so the verdicts
are demonstrably this tree's.

```
MODULE resilient_mlkit.__file__          = /private/tmp/mlkit-d2e1/src/resilient_mlkit/__init__.py
MODULE checks.decision.__file__          = /private/tmp/mlkit-d2e1/src/resilient_mlkit/checks/decision.py
MODULE checks.economics.__file__         = /private/tmp/mlkit-d2e1/src/resilient_mlkit/checks/economics.py
VERSION 0.5.0
```

---

## 1. The control pair, through `mlkit check` itself

`scripts/d2e1_control_pairs_cli.sh` builds three throwaway checkouts under a
scratch root and runs the real CLI over them. `choco` and `fray` carry
**byte-identical bindings** returning fray's own measured figures; the only
difference between them is that fray's `.mlkit/repo.toml` **commits** the
declaration. `surge` carries fray's declaration over a placebo that beats the
floor and a curve flat across the declared top step.

```
$ VENV=/path/to/python bash scripts/d2e1_control_pairs_cli.sh
MODULE /private/tmp/mlkit-d2e1/src/resilient_mlkit/__init__.py
MODULE /private/tmp/mlkit-d2e1/src/resilient_mlkit/checks/decision.py
MODULE /private/tmp/mlkit-d2e1/src/resilient_mlkit/checks/economics.py
=== mlkit check --phase decision --root <scratch> ===
```

| repo | declaration | D2 | E1 |
|---|---|---|---|
| `choco` | **none** | **FAIL, halt=True** — "placebo estimate -62.572 with CI [-71.998, -53.146] excludes zero … HARD STOP" | **FAIL** — "scaling curve missing fractions: 0.01" |
| `fray` | `[placebo]` + `[scaling]` | **PASS** — `estimate=-62.572, ci_low=-71.998, ci_high=-53.146` | **PASS** — `gain_top_two=0.08692947918972509, from_fraction=0.1` |
| `surge` | the SAME declaration | **FAIL, halt=True** — "placebo estimate 17 with CI [8, 26] excludes zero, on the 'above' side this repo declared indicting … HARD STOP" | **FAIL, halt=True** — "curve is flat between 10% and 25% (gain +0.250% <= 1.0%) … HARD STOP" |

Read down the D2 column: **the same interval halts an undeclared repo and is
silent for a declared one, and the declared one is still halted by a placebo
that shows skill.** That is the finding closed and the check not dead, in one
table, with the estimator's own numbers.

`choco`'s two rows are §2.4 reproduced exactly:

* D2 is the **spurious fleet-wide hard stop** — mlkit's two-sided rule sees
  `hi < 0` on an estimand whose no-signal value is not zero, and this is why
  fray never bound `placebo_test`;
* E1 is the **failure on contract, not on substance** — the same curve that
  PASSes one row below is refused for want of a 1% rung fray's probe never ran.

And `fray`'s E1 evidence reads `gain_top_two=0.08692947918972509`, which is
§2.4's `+8.69%` measured by `mlkit` rather than restated.

`scripts/d2e1_control_pairs.py` drives the same three rows through the library
with the expected verdicts written into the script, and exits non-zero on any
divergence — so it is a check, not a printout:

```
$ python scripts/d2e1_control_pairs.py
…
ALL THREE ROWS AS PREREGISTERED
$ echo $?
0
```

---

## 2. The suite

```
$ cd /private/tmp/mlkit-d2e1 && PYTHONPATH=src python -m pytest -q
954 passed, 3 skipped in 136.20s
```

`main` at `6921e9a` is **909 passed, 3 skipped**. The 45 new tests are all in
`tests/test_declared_hard_stops.py`. **No test that exists on `main` was edited
or deleted** — `git diff --stat origin/main -- tests/` touches one file and it
is the new one.

```
$ .venv/bin/python -m ruff check src tests scripts     # ruff 0.16.5 (CI's pin)
All checks passed!
$ .venv/bin/python -m mypy src/resilient_mlkit         # mypy 2.3.1 (CI's pin)
Success: no issues found in 30 source files
```

**`ruff` found a defect the suite could not.** Two of the new controls were
written with the same function name, 500 lines apart, so Python bound the second
and the first — the D2 portfolio-BLOCKED control — **silently stopped
existing**: pytest reported 44 passing tests and ran 43. `F811`. Both are now
named for the check they drive, and both run. Recorded here rather than quietly
fixed, because a vanished test takes its own failure signal with it, which is
the defect class this package exists to refuse.

---

## 3. The mutation drive — the part that matters

A suite that passes first time is consistent with a suite that asserts nothing.
`scripts/d2e1_mutation_drive.py` applies **31 mutations** one at a time to
`src/`, runs the three control files against each, restores the file, and exits
non-zero on any mutation nothing caught.

```
$ python -u scripts/d2e1_mutation_drive.py
MODULE   resilient_mlkit.__file__ = …/src/resilient_mlkit/__init__.py
BASELINE rc=0 failed=[]
…
31/31 mutations caught
$ echo $?
0
```

**The first pass was 22/25, and the three holes were real.** They are recorded
because a report that only shows the final number is a report of the last run,
not of the work.

| hole (first pass) | what it meant | closed by |
|---|---|---|
| `halts_above` returns `True` for every region | **`indicts = "below"` was never exercised by any test.** The mutation is in the strict direction — a `"below"` repo would have been halted on excursions it declared exempt — so it cost no repo a wrong PASS. It cost the suite its claim to have tested the arm. | three `indicts = "below"` controls: fires beneath the null, silent above it, and the sign tie mirrored |
| the sign tie's `> 0` rewritten to `>= 0` | a `reference_effect` of exactly **zero** would fall through to the power bar, which also FAILs — so the STATUS never moved and no assertion could see it. The two diagnoses are not interchangeable: "your declaration and your claimed effect point different ways" and "your placebo was too small to tell" send a reader to different files. | a control asserting the SIGN diagnosis for a zero reference under a one-sided region, paired with one asserting the POWER diagnosis for the same zero under the default |
| `abs(estimate - null)` rewritten to `abs(estimate)` in the disclosure figure | every fixture asserting that number declared a null of `0.0`, where the two expressions **are the same expression** | an assertion in the shifted-null fixture (`null_value = -62.0`), the one place they differ: `0.0251` against `2.743` |

The 31 mutations, and the control that caught each:

| # | mutation | caught by |
|---|---|---|
| M1 | halt region ignored, always two-sided at zero | the fray-silent pair, the `below` pair, the allow-dirty control |
| M2 | a declared region never halts | `the_declared_halt_region_still_halts`, `a_shifted_null_still_has_two_sides`, `a_below_region_halts_…` |
| M3 | `halts_above` swallows `"below"` | `a_below_region_is_silent_on_an_interval_above_the_null` |
| M4 | `halts_below` always False | the two-sided controls in `test_decision_controls.py`, `frays_placebo_halts_…` |
| M5 | the `estimand` requirement removed | both `…_without_an_estimand_is_refused` controls |
| M6 | the sign tie removed | all three sign-tie controls |
| M7 | the sign tie accepts zero | `a_zero_reference_effect_under_a_one_sided_region_names_the_sign` |
| M8 | `null_value` finiteness not checked | `a_non_finite_null_…`, `a_boolean_null_…` |
| M9 | `indicts` value not checked | `an_unknown_indicts_value_is_refused_by_name` |
| M10 | `is_default` reads `declared` instead of the numbers | `declaring_the_default_explicitly_needs_no_estimand` |
| M11 | E1 reads the hardcoded 0.10/0.25 again | all four declared-ladder controls |
| M12 | E1's top-rung floor removed | `a_ladder_topping_out_below_mlkits_own_is_refused` |
| M13 | E1's top-step bar removed | `a_ladder_with_too_wide_a_top_step_is_refused` |
| M14 | the top-step bar off by one side | the four boundary controls, incl. mlkit's own ladder declared explicitly |
| M15 | the top-rung floor off by one side | `…_at_exactly_the_floor_is_allowed` and three more |
| M16 | ladder ordering not checked | `an_unordered_ladder_…`, `a_duplicated_rung_…` |
| M17 | rung count not checked | `a_two_rung_ladder_is_refused` |
| M18 | rung range not checked | `a_percentage_rung_is_refused` |
| M19 | missing fractions measured against the built-in ladder | all four declared-ladder controls |
| M20 | the working-tree attempt never noticed | both `an_uncommitted_…_is_NA_not_a_silent_default` |
| M21 | the declaration read from the WORKING TREE | both uncommitted controls, both module-body-write controls |
| M22 | unknown keys ignored | `an_unknown_key_is_refused_by_name` |
| M23 | the `bool`/type refusal removed | `a_boolean_null_…`, `a_boolean_rung_…` |
| M24 | the non-finite refusal removed | `a_non_finite_null_…`, `a_non_finite_rung_…` |
| M25 | an array of tables accepted | `an_array_of_tables_is_refused_rather_than_raising` |
| M26 | D2 treats an uncommitted halt region as the default | `an_uncommitted_halt_region_is_NA_…` |
| M27 | E1 treats an uncommitted ladder as the default | `an_uncommitted_ladder_is_NA_…` |
| M28 | `halts_below` swallows `"above"` | the fray-silent pair and three more |
| M29 | the sign tie hardcodes `"above"` | both `below`-side controls |
| M30 | `null_contained` not measured | the two one-sided silent controls |
| M31 | the disclosure figure divides from zero, not from the null | the shifted-null control |

---

## 4. The invariants, each against its evidence

| | invariant | evidence |
|---|---|---|
| **I1** | an undeclared repo sees no change at all | `tests/test_decision_controls.py` + `tests/test_economics_controls.py`, **79 controls, unmodified, all pass**. Plus `choco`'s two CLI rows above, which are `main`'s verdicts on fray's figures. |
| **I2** | the defaults ARE the current rule | `test_an_undeclared_repo_reads_the_built_in_region` asserts `(null, indicts) == (0.0, "either")` and `is_default` on the reader directly; `DEFAULT_FRACTIONS == (0.01, 0.10, 0.25)`; M1/M11 confirm the check reads them. |
| **I3** | the declaration is COMMITTED or it does not exist | four controls: uncommitted → NA (D2 and E1), module-body write at import → not PASS (D2 and E1). M20/M21/M26/M27. |
| **I4** | a one-sided halt region costs something | `…a_moved_halt_region_without_an_estimand_is_refused`, `…a_shifted_null_without_an_estimand_is_refused_too`, and the negative half `declaring_the_default_explicitly_needs_no_estimand`. M5/M10. |
| **I5** | the exemption must point the same way as the claim | `a_one_sided_region_that_exempts_the_claim_is_refused` (above/negative), `a_below_region_with_a_positive_claim_is_refused` (below/positive), `a_zero_reference_effect_…_names_the_sign`, and the negative half `the_default_region_never_reads_the_sign`. M6/M7/M29. |
| **I6** | the power bar is untouched | `test_decision_controls.py`'s five power controls, including the strict boundary at `half_width == reference`, all unmodified and green. `evidence["reference_effect"]` is still the magnitude — asserted alongside the new signed key in the sign-tie control. |
| **I7** | a declared ladder may not buy a pass by widening its top step | `a_ladder_with_too_wide_a_top_step_is_refused` and `a_ladder_topping_out_below_mlkits_own_is_refused`, each with a **steep** curve reported so the refusal is of the declaration; both boundaries held from the other side, including mlkit's own ladder declared explicitly. M12–M15. |
| **I8** | the ladder must still be a ladder | six controls: two rungs, unordered, duplicated, percentage, boolean, non-finite. M16–M18, M23, M24. |
| **I9** | unknown keys are refused | `an_unknown_key_is_refused_by_name` (`indict` for `indicts`). M22. |

The prereg's own predictions, scored:

* *"I expect the whole existing suite to pass untouched"* — **held.** 909 → 954,
  nothing edited.
* *"I expect the sign tie to be the branch most likely to be wrong first time"*
  — **half right.** The tie worked; its **zero boundary** was the untestable
  one, and it took a mutation to see that.
* *"I expect `gain_10_to_25` to force a decision"* — **held**, and the plan
  recorded in the prereg is what shipped: `gain_top_two` always,
  `gain_10_to_25` only when the ladder is `(0.10, 0.25)`.
* *"no change to `portfolio.resolve`, `Status`, or any threshold"* — **held.**
  `git diff --stat origin/main -- src/` touches three files, one of them new.

---

## 5. What this does NOT close

Recorded in full in `docs/ESCALATIONS.md` **E-M24**, in short here:

1. **No repo is actually armed.** Read on 2026-09-01 across all eight
   `.mlkit/repo.toml` files: **zero** declare a `placebo_test` or a
   `scaling_probe` binding, and **zero** carry a `[placebo]` or `[scaling]`
   section. D2 and E1 are NA fleet-wide and stay NA — which is also why **no
   verdict anywhere moves on this release**. Binding them needs the training
   plane, which needs IAM and billing: CLAUDE.md rule 12, the signatory's.
2. **The MAGNITUDE of a declared `null_value` is not adjudicated.** Direction is
   tied; distance is not. No bar was invented, because any bar would be a
   fabricated expected range (rule 2) and would have refused the one genuine
   case this contract was measured against — fray's placebo sits `2.743`
   reference-effects from its null. What ships is disclosure, not a gate:
   `evidence["null_distance_in_reference_effects"]`. The honest second operand
   is **D1**, which is the signatory's to write.
3. **The spine's two canonical docs changed**, so all eight deployed copies read
   DRIFTED until `scripts/sync_spine.py` runs — eight writes into other repos.
