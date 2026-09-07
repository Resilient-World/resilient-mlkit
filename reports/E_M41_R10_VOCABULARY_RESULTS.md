# E-M41 — RESULTS. A1–A7 against the rule fixed before the implementation existed.

Driven 2026-09-07 in a venv inside the working clone, with
`resilient_mlkit.__file__` asserted to resolve to this tree's `src/` before any
reading. Fleet copies are read-only clones at their landed mains: arabica
`2a65d9a5`, fray `cc8f4355`, torrent `dc6e577a`, chokepoint `5f78fe4c`.
**Nothing was pushed to any of them, and nothing in them was edited.**

Preregistration: `reports/E_M41_R10_VOCABULARY_PREREGISTRATION.md`, this
branch's first commit.

---

## The verdicts, before and after — R10 driven as a CHECK, not as a scanner

| repo | R10 before (v1.4.0) | R10 after (v2.0.0) | |
|---|---|---|---|
| arabica `2a65d9a5` | **NA**, 10 findings | **NA**, 9 findings | one CLI exit status stops being a finding; the other nine now say why they are NA |
| fray `cc8f4355` | PASS, 0 | PASS, 0 | unmoved |
| torrent `dc6e577a` | **FAIL**, 8 (7 NA-class + 1 `PUBLISHES_UNMEASURED`) | **FAIL**, 7 (6 + 1) | verdict unmoved; the `PUBLISHES_UNMEASURED` row is byte-identical |
| chokepoint `5f78fe4c` | **NA**, 1 finding | **PASS**, 0 findings | **VERDICT MOVED ON UNCHANGED CODE** |

chokepoint is why this release is **v2.0.0**. This repo's own scale calls
"an existing check changes verdict on unchanged code" a major, the measurement
found one, and it is taken as a major rather than argued down.

## The three rows that stopped being findings, each with the defect that removed it

| repo | row | removed by |
|---|---|---|
| arabica | `src/validation/run_validate.py:577 main = 1` | **D1** — the NAME `main` entered the registry from `scripts/val_predictions_group_interval.py:52`, whose `main` does no arithmetic of its own; its nested `skill()` does |
| torrent | `scripts/hydrology/sweep_r5_attainability_leaves.py:377 main = 0 / 1` | **D1** — same shape, from `scripts/hydrology/run_basin_allocation_conformal.py:1197` |
| chokepoint | `scripts/verify_d4_checkpoint_licences.py:133 fetch = 0` | **D2** — the NAME `fetch` entered from `src/resilient_chokepoint/data/ingest/base.py:69`, entirely through `self.cache_dir / f"{key}.json"` |

All three are argparse exit statuses and an I/O accessor's `except`-branch
return. None is a domain metric. **A5 holds: every disappearance is explained
by a stated mechanical defect, and no row disappeared for any other reason.**

## A4 — no adjudicated verdict moved anywhere

Every finding whose severity is `SATISFIES_GATE` or `PUBLISHES_UNMEASURED`,
before and after, as a set of `(path, line, symbol, literal, shape, sink,
severity)` tuples:

```
arabica     adjudicated 0 -> 0    moved 0
fray        adjudicated 0 -> 0    moved 0
torrent     adjudicated 1 -> 1    moved 0
chokepoint  adjudicated 0 -> 0    moved 0
                            TOTAL moved 0
```

**Zero added, zero removed, zero changed.** The classifier moved
`UNCLASSIFIED_NAME` rows and nothing else.

## A1 — no row, anywhere, has an empty reason or an empty repair

Asserted over every finding the four fleet copies produce (`empty-fields = 0`
in each), and held in the suite at repo scope over mlkit's own `src/` as well
as on fixtures. That second arm exists because E-M38's control caught exactly
this: a `repair` field dropped in `scan()`'s rebuild, passing on a fixture,
with nine real rows shipping `repair: ""`. Both fields are now filled in ONE
place, after the sort, so a fifth emission site cannot forget them.

An `UNCLASSIFIED_NAME` row now reads, in full:

> `` `spectral_biennial_power` `` is not in mlkit's metric vocabulary. It
> reached R10 only because this repo computes a figure under that name
> (`spectral_biennial_power <- src/analysis/biennial_cycle.py:201`), and no
> polarity is declared for it — so mlkit cannot say whether 0.0 is the value
> that would PASS the gate consuming it or one that would fail it, and it
> asserts neither. This row is NA: not a pass, and not, on this evidence, a
> finding against the code.

with the repair naming the three exits: declare the direction under
`[metrics]`, read the value from a committed artifact, or refuse on that
branch.

## A2 and A3 — the classifier still fires, and stays silent where it must

| arm | planted | required | read |
|---|---|---|---|
| A2a | `rmse = metrics.get("rmse") if metrics else 0.0`, returned from `score_outage_model()` | FIRES | `SATISFIES_GATE` |
| A2b | `auc = fitted.auc if fitted else 0.0` | FIRES | `PUBLISHES_UNMEASURED` |
| A2c | `spectral_biennial_power` returning `0.0` on `len(yields) < 8`, name from the registry only | FIRES | `UNCLASSIFIED_NAME` |
| A3 | the same `rmse`, `json.loads(artifact.read_text())["rmse"]` | SILENT | 0 findings |

A3 is the arm that matters. "Read it from a committed artifact" is the repair
every other row is told to make; if that fired, the rule would forbid its own
instruction.

## A6 — declaring a polarity can only ever make R10 stricter

| arm | read |
|---|---|
| no `[metrics]` table | row stays `UNCLASSIFIED_NAME`, R10 NA |
| `higher_is_better` / `lower_is_better` / `neutral` | same row, same line, now a verdict — never removed |
| a declaration for `rmse`, a name the VOCABULARY judges | ignored; `rmse` stays `SATISFIES_GATE` |
| `= "not_a_metric"` | refused by name, row stays NA |
| an empty table | findings byte-identical to no table at all |

There is no fourth value. A declaration channel that can take a name out of
R10's reach is a channel that will be used to take names out of R10's reach.

### The exit driven end to end, on a throwaway copy of arabica

A copy of arabica `2a65d9a5` — never pushed, never a branch, deleted after —
with a `[metrics]` table declaring the direction of the nine residual names, in
the directions arabica's own analysis argues for each:

```
R10  NA (9 findings, 0 adjudicated)   ->   FAIL (9 findings, 4 SATISFIES_GATE, 5 PUBLISHES_UNMEASURED)

SATISFIES_GATE  src/hazards/cbd_ssp_projections.py:80            area_expansion_fraction        = 0.0
SATISFIES_GATE  src/hazards/clr_ssp_projections.py:115           area_expansion_fraction        = 0.0
SATISFIES_GATE  src/models/conformal/spatial_variogram_cqr.py:104 spatial_uncertainty_multiplier = 1.0
SATISFIES_GATE  src/validation/dynacof_parity.py:101             _bias_pct                      = 0.0
PUBLISHES_UNMEASURED  biennial_cycle.py:213 / :218, vm0042_adapter.py:339,
                      vm0047_adapter.py:183, foundation_model_benchmark.py:279
```

**The four the classifier adjudicates as gate-satisfying are exactly the four
arabica's own record identified by hand as returning the best-case value** —
`area_expansion_fraction` (no hazard expansion), `spatial_uncertainty_multiplier`
(the identity, i.e. the narrowest interval), `_bias_pct` (zero bias). Given the
polarity, the classifier reproduces the human judgement, and the remaining five
are correctly the neutral and conservative ones. That is the "much smaller and
much more interesting set than ten" arabica asked for, reached by asking the
repo rather than by mlkit guessing what a degenerate-input guard looks like.

Whether arabica should adopt the table, and in which directions, is arabica's
decision and is not made here.

## What the derivation repairs cost, measured per repo and disclosed in full

D2 removes path builders. Every one of the 54 names it drops across the fleet
is a path, a store, a writer or a download target — `cachepath`, `yearstore`,
`zippath`, `manifestpath`, `ckptweightspath`, `writereport`. None is a metric,
so this is precision gained at no recall cost.

D1 is the one with a cost, and it is stated rather than smoothed:

| repo | registry v1.4.0 | v2.0.0 | lost to D1 | lost to D2 | vocabulary-known |
|---|---|---|---|---|---|
| arabica | 163 | 147 | 3 | 13 | 5 → 5 |
| fray | 68 | 58 | 0 | 10 | 1 → 1 |
| torrent | 158 | 145 | 5 | 8 | 6 → 6 |
| chokepoint | 145 | 117 | 5 | 23 | 1 → 1 |

D1's 13 names, in full: arabica `compute_indices`, `main`,
`standardized_mean_differences`; torrent `beta_scaled`, `fit`, `fit_power_law`,
`generate_triangular_mesh`, `main`; chokepoint `compute_irr`,
`corridor_block_paired_skill_delta`, `gbm`, `permutation_null_direction`,
`ridge_depth`.

Two of the thirteen (`main`, `main`) are the intended removals. The other
eleven are functions that DO delegate to a helper but whose result reaches the
return through two or more hops of locals — `standardized_mean_differences`
goes `_smd` → a list comprehension → a DataFrame → `.max()` → the return, and
the existing rule is deliberately one hop. **Today that costs zero findings**:
none of the eleven carries a fabricated literal, and the fleet diff above shows
no row lost at any of them. It is nonetheless real recall, it is written here
rather than left to be discovered, and
`tests/test_r10_derivation_defects.py` pins the boundary in both directions
(calls-a-helper-and-returns-an-exit-code stays OUT; returns-what-the-helper-computed
stays IN) so the day it moves the disclosure gets updated instead of the
behaviour drifting.

The E-038 anchor probe survives both repairs and is asserted to — it goes
through the same code path, so a probe that stopped coming back would mean the
registry had quietly emptied and R10 had fallen back to the word list.

## A7 — mlkit's own suite

Full target, one clone per arm with its own venv, run **sequentially**, no
`-k`, identical flags:

```
MAIN    a1037a4d / tree ae566680  1364 passed, 3 skipped, 0 FAILED  212.92s  load1 16.02 after
BRANCH  4e60e5a8 / tree a91bafff  1389 passed, 3 skipped, 0 FAILED  186.26s  load1 16.65 after
BRANCH' 5d3eb8dc / tree c7fb08db  1389 passed, 3 skipped, 0 FAILED  168.54s  load1 12.92 -> 14.77
only-on-branch NONE   only-on-main NONE   BOTH failure sets EMPTY
```

BRANCH' is the arm re-driven on the FINAL tree, because the results and
escalation documents landed after the first branch arm and this repo's suite
reads its own docs. A tree that was not tested does not land.
`+25 passing` = the 25 tests added (15 in `test_r10_reason_and_repair.py`, 10
in `test_r10_derivation_defects.py`). Each arm asserted
`resilient_mlkit.__file__` inside its own clone before running — the shared venv
on this host carries an editable path to a different checkout and would have
silently measured that one.

CI is red on every branch of every private repo in this fleet — every workflow
fails in 3–5 s with zero steps executed — so it discriminates nothing and the
measured by-name suite comparison is the gate.

## What was left undone, with the reason

* **No fourth severity for a degenerate-input guard.** arabica's record asks
  for one. Separating "the input is present and degenerate and this is the
  defined answer" from "the input is absent and a plausible number stands in"
  means deciding whether `if not matched:` tests absence or degeneracy — the
  same syntax wearing two meanings. A severity mlkit guesses wrong is worse
  than an NA it declines honestly, and `[metrics]` reaches the interesting
  subset from the other side.
* **`REPO_ROOT / path` is still read as division** when both operands are plain
  names. Widening D2 to "an operand whose name looks path-ish" is the spelling
  rule E-038 established does not converge. Stated limit, pinned by a test.
* **No adopter adopted `[metrics]`.** The declaration exists and is driven end
  to end on a throwaway copy; putting it into a repo is that repo's decision,
  because it turns NA rows into FAIL rows.
* **No vocabulary word was added.** `MEASURED_TOKENS`, `_HIGHER_IS_BETTER` and
  `_LOWER_IS_BETTER` are byte-unchanged.
* **The tag is not cut.** v2.0.0 is declared in `__init__.py` and in the
  changelog; cutting the tag stays the signatory's (E-M08).
