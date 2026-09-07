# E-M41 — R10 stops answering "I cannot tell" and saying nothing else: PREREGISTRATION

**Written 2026-09-07, BEFORE any code on this branch. This is the branch's first
commit.** Base: `main` at `a1037a4` (v1.4.0). Driven in a venv inside this
clone, with `resilient_mlkit.__file__` asserted to resolve to this tree's `src/`
before any reading was taken.

## The defect, as measured in the adopters (not recalled)

`resilient-arabica` repaired the four fabricated defaults that reached a gate in
its PR #169 (`SATISFIES_GATE` 4 → 0) and R10 then read **NA (10)**: ten residual
literals mlkit's classifier declines to judge. That is the honest outcome for
arabica and the wrong resting place for the fleet — a check that answers "I
cannot tell" about ten values, and says nothing about WHICH ten or WHY, is
measuring nothing about them.

Re-derived here rather than taken from arabica's record, by running R10's own
scanner over `resilient-arabica` `2a65d9a5` with the registry derived the way
the check derives it (`files_walked=406`, `findings=10`, all
`UNCLASSIFIED_NAME`):

```
src/analysis/biennial_cycle.py:213             spectral_biennial_power        = 0.0  metric function returns a literal
src/analysis/biennial_cycle.py:218             spectral_biennial_power        = 0.0  ternary fallback
src/finance/vm0042_adapter.py:339              _compute_ch4_reduction         = 0.0  metric function returns a literal
src/finance/vm0047_adapter.py:183              delta_si                       = 0.0  ternary fallback
src/hazards/cbd_ssp_projections.py:80          area_expansion_fraction        = 0.0  metric function returns a literal
src/hazards/clr_ssp_projections.py:115         area_expansion_fraction        = 0.0  metric function returns a literal
src/models/conformal/spatial_variogram_cqr.py:104 spatial_uncertainty_multiplier = 1.0  metric function returns a literal
src/validation/dynacof_parity.py:101           _bias_pct                      = 0.0  metric function returns a literal
src/validation/foundation_model_benchmark.py:279 acc                          = 0.0  metric function returns a literal
src/validation/run_validate.py:577             main                           = 1    ternary fallback
```

And, driven the same way at the other three fleet mains:

```
resilient-fray       cc8f4355  files=288  findings=0
resilient-torrent    dc6e577a  files=597  findings=8   7 UNCLASSIFIED_NAME + 1 PUBLISHES_UNMEASURED
resilient-chokepoint 5f78fe4c  files=341  findings=1   1 UNCLASSIFIED_NAME
```

## Two of these are not domain metrics at all, and the cause is mechanical

`main` is an argparse CLI entry point and `1` is a process exit status. It
reached R10 because `metric_registry` admitted the NAME `main` from
`scripts/val_predictions_group_interval.py:52`, and torrent has the same row
from `scripts/hydrology/run_basin_allocation_conformal.py:1197`. arabica's own
record proposed excluding CLI entry points from the derivation. That would work
and it would be a spelling rule. Reading the derivation instead finds two
**mechanical defects** that cause the admission, and fixing those is both
narrower and stronger:

**D1 — nested-scope leakage.** `metric_registry._computes_a_figure` collects a
function's returns and derived locals with `ast.walk(fn)`, which descends into
nested `def`s and lambdas. An outer function is therefore credited with
arithmetic belonging to an inner one. arabica's `main` does no arithmetic in its
own body; the nested `skill()` it defines does (`1.0 - rm / rq`). Nested
functions are already visited as candidates in their own right by `_names_in`,
so scoping this to the function's own body loses only the false attribution —
except for an outer function whose only arithmetic is inside a helper it defines
and calls. That residual will be MEASURED, disclosed and pinned by a test, not
assumed away.

**D2 — a path join read as division.** `_ARITHMETIC` contains `ast.Div`, and
`pathlib` spells path joining with the same operator. chokepoint's
`data/ingest/base.py:69 fetch()` enters the registry entirely because of
`self.cache_dir / f"{key}.json"`. A path is not a figure.

The predicate for D2 is a TYPE FACT, not a heuristic: a `/` with a string
literal or an f-string on either side cannot be numeric division, because
dividing a number by a string is a `TypeError`. If it runs at all it is
`Path.__truediv__`.

## The rest genuinely cannot be judged without repo-specific knowledge

`spectral_biennial_power`, `area_expansion_fraction`, `spatial_uncertainty_multiplier`,
`_bias_pct`, `delta_si`, `acc`, `_compute_ch4_reduction` — mlkit's vocabulary has
no polarity for any of them, and `satisfies_a_gate` reads polarity off the
vocabulary. Without a direction it cannot say whether `0.0` is the value that
would PASS the gate consuming it (`SATISFIES_GATE`) or one that would fail it
while still being published (`PUBLISHES_UNMEASURED`), so it asserts neither.
**That refusal is correct and stays.** What is not correct is that the refusal
carries no information: R10's reason is a count.

## What changes (fixed now; the diff is held to this list)

1. **`Finding` gains `reason` and `repair`**, filled at every severity, in
   `to_dict()`, in `evidence.top[*]`, and as two columns of
   `reports/fabricated_defaults.md`. Same shape and the same intent as E-M38's
   `SERVE_ARM` repair: the row must say WHAT is fabricated and WHAT to write.
   For an `UNCLASSIFIED_NAME` row, `reason` names the symbol, the literal, the
   registry origin that admitted the name, and the fact that no polarity is
   known; `repair` names the three exits in order — declare the polarity,
   read the value from a committed artifact, or refuse on that branch.
2. **R10's `CheckResult` reason for the NA case names the literals with their
   reasons** instead of a bare count.
3. **D1 and D2 are fixed in `metric_registry`.**
4. **`.mlkit/repo.toml` gains an optional `[metrics]` table** mapping a name the
   repo computes to `higher_is_better` / `lower_is_better` / `neutral`, which
   `satisfies_a_gate` consults for a REGISTRY-sourced name. This is the exit
   that lets a repo stop being NA.

## The acceptance rule, fixed before the implementation exists

The change is accepted only if ALL of A1–A7 hold. Any one failing means the
change does not land in this shape.

* **A1 — every finding says why and what to write.** No R10 finding, at any
  severity, has an empty `reason` or an empty `repair`, in `Finding`, in
  `to_dict()`, in `evidence.top[*]` and in the written report. Asserted at repo
  scope, not only on a fixture, because that is the shape E-M38's own control
  defect took (the field was dropped in `scan()`'s rebuild and nine real rows
  read `repair: ""`).
* **A2 — CONTROL, FIRES.** A planted fabricated default is still reported, by
  name and line, at each of the three severity paths: one whose name is in the
  vocabulary and satisfies its gate, one whose name is in the vocabulary and
  does not, and one whose name comes only from the registry.
* **A3 — CONTROL, SILENT.** The same quantity read from a committed artifact
  (`json.loads(path.read_text())["rmse"]`) is NOT reported. If this fired, the
  rule would forbid the repair every other row is told to make.
* **A4 — CONTROL, NO ADJUDICATED VERDICT MOVES.** Over the four fleet copies at
  their landed mains (arabica `2a65d9a5`, fray `cc8f4355`, torrent `dc6e577a`,
  chokepoint `5f78fe4c`), every finding whose severity BEFORE the change is
  `SATISFIES_GATE` or `PUBLISHES_UNMEASURED` is present AFTER with the same
  path, line, symbol, literal, shape, sink and severity. **Zero added, zero
  removed, zero changed.** The classifier may only move `UNCLASSIFIED_NAME`
  rows. Driven as a JSON diff, before and after, in one clone.
* **A5 — every disappearance is explained by a stated defect.** Any
  `UNCLASSIFIED_NAME` row that goes away must go away because D1 or D2 removed
  the NAME from the registry, and the record must say which, for each row. A row
  that vanishes for any other reason blocks the change.
* **A6 — the polarity declaration is monotone toward strictness.** Declaring a
  polarity may turn `UNCLASSIFIED_NAME` into `SATISFIES_GATE` or
  `PUBLISHES_UNMEASURED` — NA into FAIL. It may NEVER remove a finding, silence
  a name, or turn a FAIL into a PASS. There is deliberately no way to declare
  "this is not a metric": that would be a silencing channel, and a check with a
  silencing channel is a check that will be silenced. Asserted by a test that
  drives the same tree with and without the declaration.
* **A7 — mlkit's own suite.** Full target, failure sets by name, one clone per
  arm, run sequentially, against a `main` baseline. No failure only on the
  branch.

## The version bump, decided by this repo's own scale and not by the diff

This file's scale says **major** when *an existing check changes verdict on
unchanged code*. If D1 and D2 remove chokepoint's single finding, R10 there goes
from **NA to PASS** on code that did not change. That is a major, and it will be
taken as one — v2.0.0 — rather than argued down. If the measured drive shows no
adopter's R10 verdict moves, it is a minor. **The measurement decides, and it is
taken after the implementation, not before.**

## What is NOT done

* **No fourth severity for a "degenerate-input guard".** arabica's record asks
  for one — a value that is the mathematically defined answer for a present-but-
  degenerate input, behind an explicit adjacent guard. Separating that from an
  absent-value default requires mlkit to decide whether a guard tests absence or
  degeneracy, and `if not matched:` and `if baseline_area == 0:` are the same
  syntax wearing different meanings. A severity mlkit guesses wrong is worse
  than an NA it declines honestly. The `[metrics]` declaration reaches the same
  subset from the other side, by asking the repo rather than guessing: with a
  polarity, the guards whose value is ALSO the gate-satisfying one become
  reportable, and that is a smaller and far more interesting set than ten.
* **No adopter is edited.** The fleet copies are read-only clones. Nothing is
  pushed to arabica, fray, torrent or chokepoint.
* **No vocabulary word is added.** `MEASURED_TOKENS` is untouched: adding words
  is the thing E-038 established does not converge.
