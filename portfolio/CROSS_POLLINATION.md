# Cross-pollination report — six-repo evidence-discipline loop

**Date:** 2026-08-23
**Scope:** resilient-arabica, resilient-surge, resilient-torrent, resilient-choco, resilient-fray, resilient-chokepoint
**Rounds:** 2 (harvest → apply → harvest → apply)
**Seed:** a 13-item catalogue of measurement defects, each first found in one repo

---

## 0. What I verified myself, and what I am relaying

The rounds below produced a large number of measured claims. I re-derived the
load-bearing ones directly from the repositories rather than repeating them.
**Verified in this session, from the committed artifacts and from `git`:**

| Claim | Verified how |
|---|---|
| torrent's three shipped checkpoints and their warnings | read `checkpoints/exp_{a,b,c}/metrics.json` |
| torrent's selection-metric divergence (`val/nse_mean` = −681.67 vs reported median NSE = −0.319, same weights) | same files |
| torrent's linear ceiling (network 0.2471 vs ridge 0.5169, same 30 basins, test split) | `docs/benchmarks/hydrology_leaderboard.md` |
| surge's per-lead baseline table and its `comparability` block | `reports/train/observed_baselines.json` |
| surge's adapter −14.6% against its base | `outputs/surge_finetune/metrics.json` |
| surge's holdout rows (model beats every reference at 24 h on both test storms) | `reports/train/metrics.json` |
| surge's Makefile splitting on the space in the checkout path | read `Makefile:3–6` |
| choco's served head: 26 train rows, 200 leaves, model 1.4418 vs persistence 0.1995 on the same 42 rows | `models/observed_production_head.meta.json` |
| choco's conformal fan fix and the `train_rows`-positional baseline signature | read the two modules |
| arabica: 986 train / 3384 val / 3408 test, skill quoted only against the pooled train mean | `reports/train/yield_coffee_run.json` |
| arabica's leaderboard carries no model row and the four references' skills | `reports/validation/naive_baseline_leaderboard.md` |
| **arabica's round-2 remediation (e22fc66) is NOT on the branch of record** | `git merge-base --is-ancestor` → false |
| chokepoint: n_scored = 3, skill decomposition 0.531 of 0.791 | `reports/benchmarks/metrics.json` |
| chokepoint's SOTA ensemble is honestly all-NA with four warnings | `reports/hindcast/sota_metrics.json` |
| fray has **no** model checkpoint at all; baselines measured, `trained: false` | `models/`, `reports/validation/naive_baseline_leaderboard.json` |
| fray's R10 gate report is gitignored | `git check-ignore -v` |
| torrent's holdout ledger module exists, un-ignored, file not yet created | `.gitignore:97`, `ls` |

**Relayed, not independently re-derived:** the round-2 before/after deltas that
required re-running a scorer (surge's −14.3 % holdout change from checkpoint
selection; choco's CRPSS sweep; fray's 58.7 % split-overlap measurement;
chokepoint's 2–7× corridor-scale overstatement). These are attributed to the
round that measured them, not asserted as mine. Where a round's own claim was
contradicted by what I read, I say so — twice below.

---

## 1. Which practices propagated, to which repos, and what each measured

### 1.1 The seed catalogue, after two rounds

Legend: **✔** implemented with a positive control · **~** implemented, no
control or partial · **✖** open · **—** genuinely exempt (§2)

| # | Practice | arabica | surge | torrent | choco | fray | chokepoint |
|---|---|---|---|---|---|---|---|
| 1 | Warning that can fire | ✔¹ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 2 | Test asserts executions, not records | ✖² | ✔ | — | ✔ | ✔ | ✔ |
| 3 | Trivial baseline in the artifact | ~³ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 4 | Fine-tune scored against its base | ✔¹ | ✔ | ✔ | ✖⁴ | ✔ | — |
| 5 | Score the weights you ship | ~⁵ | ✔ | ✔ | ✔ | ~ | ✔ |
| 6 | Holdout is opt-in | ✖ | ✔ | ✔ | ✔ | ✔ | — |
| 7 | Holdout policy derived, not asserted | ✔¹ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 8 | Leakage guard on the consumed split | ✔¹ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 9 | Capacity against rows | ✔¹ | ✔ | ✔ | ✔ | ~⁶ | ~⁶ |
| 10 | Refuse and record, never impute | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 11 | Never claim an unstat-ed artifact | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| 12 | Declared params that nothing consumes | ✔¹ | ✔ | ✔ | ✔ | ✔ | ~ |
| 13 | Units checked against the label | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

¹ arabica's round-2 work is real and tested — **but it is committed on a
separate worktree branch (`e22fc66`) that is not an ancestor of
`feat/observed-panel-and-fabrication-gates`.** On the branch of record,
`src/registry/promotion_gate.py` still contains no `gate_metric_warnings` and
`grep -rn metric_warnings src/` returns nothing. This is the single largest
delivery gap in the programme and it is invisible from either branch alone.

² unfixed in `optuna_prithvi` / `optuna_agrifm`, whose objectives are
`lr*10 + weight_decay` — closed-form functions of their own search variables.
The correct action there is deletion or renaming, not a completed-trial assertion.

³ measured for four references in `skill_score.py`; the trainer quotes skill
against a fifth and weakest one, and no artifact contains both.

⁴ five foundation backbones, no base comparison. Not runnable: the segmentation
panel is generated and the DVC stage passes `--synthetic`.

⁵ clean by construction on the shipped DVC trainer; three non-DVC trainers
still `trainer.test()` on in-memory weights and ship a different epoch.

⁶ recorded honestly; the ratio itself is unmeasurable (fray has no panel on the
checkout, chokepoint cannot import lightning).

### 1.2 What each propagation actually measured

These are the numbers the practices produced. Every one of them was previously
invisible.

**Item 1 — a warning that can fire, and a gate that reads it.**
- *arabica* — the collapse detector tested `pred_std == 0.0`, which only ever
  worked because the head was `clamp(min=0)`. E-040 replaced it with `softplus`.
  Measured: `softplus(β=10)` at `[-5.0, -5.0+1e-6]` returns two distinct floats,
  exact zeros 0. The predicate had been unfirable since E-040 and no test made
  any warning fire. The shipped `metric_warnings: []` is therefore the output of
  a check that could not fail; the corrected function returns
  `['collapse_check_unmeasured']` on the same row.
- *torrent* — `attach_baselines` had taken `model_median_nse` since it was
  written and **both call sites passed `None`**, so `no_skill_vs_*` had never
  fired in production. Once `model_scoring.py` supplied a real score it fired on
  3 of 3 shipped artifacts.
- *fray* — the two adapter trainers passed `{train_base_rate: {brier: …}}` to a
  function that only reads `mae_lb_ac`/`rmse_lb_ac`. Measured: an adapter with
  holdout Brier 1.0 against a base rate of 0.25 — four times worse than the
  constant — returned `[]`, which fray's own convention reads as
  *checked, nothing fired*.
- *surge* — the harness worked perfectly and the registry never opened it.
  `assert_shippable` checked six things and none of them was
  `metric_warnings`, `adapter_vs_base`, or `baselines`. After the fix it refuses
  the shipped run of record on two `no_skill_vs_persistence` warnings, and
  `export_surge_onnx.py` exits without writing.
- *chokepoint* — `metric_warnings` gained its first reader; the headline
  hindcast figure is now blocked by `aggregate_includes_training_corridors`,
  which is the correct state.

**Item 5 — score the weights you ship.** The sharpest measured consequence in
the fleet. Surge fixed it inside `train.py` in round 1; round 2 found the fix
had not reached the two committed scorers that produced **every published
number**. Rescoring the holdout on the epoch the run actually selected
(`epoch=003`, not `last.ckpt` after 100 epochs) moved mean 24 h RMSE
0.244209 → 0.209344, **−14.3 %**, and flipped the sign of val skill against
`train_mean`. Torrent had no checkpoint callback anywhere in its hydrology path;
adding one plus `describe_scored_weights` is what surfaced the selection-metric
divergence (§3.1).

**Item 13 — units.** Four live dimensional defects were found and fixed:
- choco: `g m⁻²` divided by 1e6 and labelled `t ha⁻¹`, in **two** mechanistic
  cores. CASEJ yield 0.000401 → 1.914625 t/ha.
- torrent: Caravan `streamflow` is mm/day, stamped `m3 s-1` on the GRRR archive.
  The error is basin-dependent — ×0.18 to ×1700 across torrent's own staged
  subset — so no downstream constant can absorb it.
- surge: TWL summed `setup + runup` where Stockdon Eq. 19 runup *already
  contains* setup. Overstated by 0.2677 m at the repo's own test vector, 29.3 %
  of the wave term. Four existing assertions passed under the double count.
- fray: ERA5-Land volumetric soil water (a fraction) rescaled to 0–100 and named
  `soil_moisture_deficit_mm`, consumed by thresholds in millimetres. Measured
  across the entire reachable range of θ: the irrigated drought factor was
  **1.000 at every value**, and the 200 mm rainfed floor was unreachable.

---

## 2. Genuine exemptions, and why

Exemptions matter as much as adoptions: forcing a practice into a repo that
cannot support it manufactures a check about nothing.

| Repo | Exempt from | Why, measured |
|---|---|---|
| torrent | #2 (HPO execution test) | No Optuna, hyperopt, Ray Tune or sklearn search exists in `src/`, `scripts/` or `tests/`. Building one to close a row would certify a search that does not exist. The item's *generalisation* — a count is not an execution — is implemented better here than anywhere, as `probe_splits`. |
| torrent | #6 in the trainer | `trainer.test` and `test_step` appear nowhere; the module defines only `training_step` and `validation_step`. The defect could not occur. The *rail* was added anyway, and the leaderboard's `--split test` default — which was the live gap — was closed. |
| chokepoint | #6 entirely | `labelled_batch('val')` and `('test')` both raise `ScenarioUnmeasured`. The entire derivable-label universe is **3 rows on 2 corridors, all in train**. A `--final-eval` flag would be theatre; the honest action was the opposite — state the split composition per case and warn that the aggregate includes training corridors. |
| chokepoint | #4 | Nothing here adapts a pretrained checkpoint. |
| chokepoint | #24 (like-for-like) | Discharged in one sentence rather than machinery: all three of its references see strictly less than the model, so every comparison it publishes is already like-for-like. |
| choco | #28 (buffer-consequence warning) | `observed_panel_split` blocks whole `group_id`s with no exclusion radius; there is no `train_rows_dropped_by_buffer` quantity to warn about. |
| choco | #17 (per-split statistic divergence) | The served head is a `GradientBoostingRegressor` on unstandardised features. Trees are scale-free; there is no per-split normalisation dictionary, so torrent's failure cannot occur. |
| choco | #16 (split identity) | There is exactly one splitter, called once, with the gates and trainer reading the same config. Nothing to reconcile. |
| choco | #27 (linear ceiling) | Answered three ways already and better by `ceiling_probe`: 98.6 % of log-production variance is between-unit; a leaky unit-level oracle scores 0.1735 against persistence's 0.1995. |
| arabica | #5 on the shipped path | The checkpoint is written only inside `if val_rmse < best_rmse` and `_best_metrics_block` reports the same epoch. No path can diverge. Re-verified rather than taken on trust. |
| fray | #4 (round 1 only) | The exemption **expired mid-task**: `ce4c974` landed a fail-closed harness on a sha256-pinned base. Round 2 correctly dropped a drafted `backbone_pretrained: false` field that would, after that commit, have asserted the opposite of the truth. |
| surge | #15, #16 | No re-splitting exists anywhere in `src/` or `scripts/`; the pack's `splits.json` is fixed at build time and every consumer reads the same three directories. Fray's defect needs two splitters; surge has none at scoring time. |

Two exemptions were **wrongly claimed and corrected by measurement**:
choco's round-2 commit message asserted that `dvc repro` spent the segmentation
holdout on every run; reading the stage's own command showed it passes
`--synthetic` and returns before a datamodule exists. The holdout was being
spent by *manual* runs. The correction was propagated into the code comments and
the test docstring, not just the message. And round 1's claim that
`metric_warnings` had "exactly one reader in arabica" was false on the branch of
record, where it has zero.

---

## 3. What the loop discovered that was not in the seed catalogue

This is the test of whether the recursion earned its cost. Twenty-six distinct
practices emerged that no round-1 seed item states. Ranked by transferable value.

### Tier 1 — changes what a measurement *means*

**3.1 `selected_on` must name the same quantity the artifact reports.**
*torrent.* Found only because catalogue #5's fix put both numbers in one file.
Verified: `exp_a_control/metrics.json` records `selected_on: val/nse_mean`,
`best_score: −681.670166`, and `median_nse: −0.318985` — the same weights, the
same split, two quantities three orders of magnitude apart. The checkpoint that
ships is not the epoch that maximised the metric anyone quotes. R4 known-answer
testing does not catch it: the leaf `_nse` is pinned correctly at 0.6 on a hand
computed vector. **Every repo that has adopted item #5 gets this diagnostic for
free** — open the artifact and check whether `best_score` and the headline
metric are the same kind of number.

**3.2 The linear ceiling row.** *torrent.* Catalogue #3 asks *does the model beat
doing nothing*. It cannot answer *is the deficit in the data or in the training*,
and those call for opposite responses. `linear_reference.py` fits a deliberately
weak ridge on exactly the windows the network trains on, from summaries of
exactly its inputs, scored through the same `nse`. Verified on the shipped
board: network **0.2471**, `ridge_with_observed_discharge` **0.5169**, same 30
basins, same split. The network is 0.27 NSE *below its own linear ceiling*. That
is a diagnosis, not a score, and it was invisible to the entire seed catalogue.
Surge, choco, arabica and fray all have a deep model losing to (or tying) a
baseline and none of them can currently answer this question.

**3.3 Record the information asymmetry between the model and each reference.**
*surge.* Catalogue #3 warns when the model loses to a trivial reference; it says
nothing about whether the reference is information-comparable, so a fair loss and
an unfair one render identically. `observed_baselines.json` states per baseline
what it sees, sets `like_for_like`, and draws the conclusion in the artifact.
Verified on val at 24 h: persistence 0.130007, climatology 0.215142, model
0.214811, zero 0.269156. One reading says the model loses to the strongest
reference by 65 %; the other says it is *indistinguishable from a monthly
climatology* while beating "predict nothing" by 20 %. Both are true and only the
pair is informative. `strongest_like_for_like_baseline` should be a required
field wherever #3 is adopted — and `strongest_baseline` must be *re-derived per
split*, because surge measured the ordering **inverting** between val and test.

**3.4 Fixing a units error can convert a magnitude defect into a saturation
defect.** *choco, E-042.* Correcting the 1e4 factor made `y_raw` 7.33 t/ha
against a water cap of 3.5, so RUE, CO₂ fertilisation, VPD stress, temperature
stress, shade LAI and tree age now have **no effect on the output at any
precipitation above ~975 mm/yr**. Measured: the 400→600 ppm CO₂ response is
*exactly zero* at 2784, 1670, 1253, 1113 and 974 mm/yr and only reappears at 835.
The repo went from the wrong magnitude with live physiology to the right
magnitude with dead physiology, and only the second is visible. **Any commit
correcting a scale factor must re-check every clip, cap and min/max downstream
and assert which side of them the quantity now lands on.** Deliberately not
tuned: the two parameters that would make every test green are cited to a
published paper.

**3.5 A suite of relative assertions cannot detect a constant multiplicative
error, however large.** *choco.* Every assertion on `y_mech` was a ratio or a
`<`/`>` comparison plus one `> 0.0`, which is exactly how a 1e4 error survived in
two mechanistic cores. Any term feeding a labelled output needs at least one
**absolute-magnitude** assertion pinning it to the label's units and range.

**3.6 The stipulation-held-constant reference.** *chokepoint.* Where a prediction
factorises as `measured_scale × stipulated_parameter`, add a third reference that
varies only the measured factor. Verified in the shipped artifact: headline skill
+0.7915, `skill_from_measured_corridor_scale` +0.5306,
`skill_from_stated_activity_drop` +0.2609. Two thirds of the reported skill is a
corridor-size lookup against a pinned panel — and that scale also sets the
label's own scale. Applies wherever a repo multiplies a measured magnitude by a
hand-typed coefficient.

**3.7 Sweep the spread literal of a probabilistic reference — and report the
sign.** *choco.* A CRPS reference has *two* invented degrees of freedom, not one.
Holding model, rows and baseline centre fixed and sweeping only `noise_scale`
across a decade moved `crpss_climatology` from −0.6460 to +0.1671: **the range
crosses zero**. A magnitude change reads as noise; a sign change is a different
claim about the world.

### Tier 2 — makes an existing check honest

**3.8 A guard must record the size of the set it examined — per comparison.**
Torrent verified `split_provenance({'adaptation_basins': [...]})` returning
`basin_blocked: True` having compared **zero** pairs, on the one path whose
holdout is explicitly temporal. Surge measured its train/val temporal guard
iterating an intersection that is empty on the productive pack: 181 train groups,
32 val groups, **0 comparisons**. The round-2 refinement matters: a *summed*
counter goes non-zero as soon as one of N comparisons runs, so
`vacuous` must be per-pair. Arabica caught exactly that trap with a positive
control that asserted `vacuous is True` and failed.

**3.9 An absent field refuses.** A summary with no `metric_warnings` **key** is
unmeasured, not clean. Originated in surge, now in five repos. It is what stops
an artifact written before the caveat block from reading as a pass. The round-2
sequel is sharper: an artifact is assurance only as of the **predicate** that
produced it — adopting a corrected caveat function retroactively invalidates
every empty warning list the old one wrote, and nothing anywhere records which
predicate version wrote a given list.

**3.10 A baseline that failed to score must block, not vanish.** *fray.* The
per-baseline `except Exception` that makes a leaderboard robust is exactly what
disarms the promotion rule: a model at MAE 550 lb/ac against a persistence floor
recorded as `na_reason` returned `[]`, so the gate passed. *The floor could not
be measured* and *the model cleared the floor* rendered identically.

**3.11 Split identity: prove the scorer used the trainer's split.** *fray.* A
group-disjointness guard proves the **splitter** is honest, not that the
**evaluator** used the same split. Measured on fray's own county panel: the
trainer splits at seed 42, `production_gates` re-split at seed 11, and **7,124 of
the 12,134 rows the gate scored as held out (58.7 %) were training rows**;
121 of 200 "holdout" blocks were training blocks — with `SPATIAL_R2_GATE = 0.85`
applied to that. Both splitters pass every disjointness test in isolation.

**3.12 Append-only holdout-read ledger.** "Read the holdout once" is a discipline
no artifact can contradict. Torrent's leaderboard defaulted `--split test` and
had already been read against three configurations while `cli.py` printed the
discipline to stdout and recorded nothing. Surge's ledger works and cost
something on day one: two reads, the second because a path fix landed between
them — which is precisely the point.

**3.13 Probe element 0 of every declared split before spending an epoch.**
*torrent.* Its val split built 778 windows and raised `KeyError` on element 0,
and mlkit R2, R3 and R5 were all green over it because every binding that touches
data touches **train**. `probe_splits` returns the finding, `assert_splits_indexable`
raises — the same measure-then-decide separation as `metric_warnings` vs a gate.

**3.14 The withdrawal pattern.** *chokepoint.* Deleting an unprovenanced fitted
artifact destroys the audit trail; relabelling it in place still loads it. What
works: a `withdrawn: true` header carrying the defect, measurement and date, the
old document verbatim underneath, and a **loader** that refuses, falls back to
the declared config, and records the refusal *on the returned object* where an
artifact writer can copy it. A log line does not reach the artifact.

**3.15 `fraction_of_units_beaten` alongside the margin.** *torrent.* A −0.0087
margin reads as a near-tie; measured, `exp_c` beats `persistence_lag3` on 19 of
65 basins — **29 %**. And the row that looks like a clean win (+0.2277) is 39 of
63, a much weaker claim. Both sides already carry per-unit arrays in four repos.

### Tier 3 — makes a gate real

**3.16 A gate that cannot be invoked is silent, not red.** *fray, then surge.*
Every Make path function treats its argument as a whitespace-separated list; the
checkout lives under a path containing a space, so `REPO_ROOT` resolved to
`/Users/david/Downloads/` and `make lint`, `make typecheck`, `make test` and
`make ci` all exited "Permission denied" before running a single check. Verified
in surge's `Makefile:3–6`. That is why sixteen instances of one exception-naming
convention had time to accumulate — the gate was never running. The round-1
diagnosis ("red long enough to accumulate sixteen instances") was one level too
shallow.

**3.17 A change to the build graph can loosen a gate with no gate file edited.**
*surge.* Declaring `checkpoints/` instead of `checkpoints/last.ckpt` as a stage
output is unambiguously an improvement, and it silently **deleted an mlkit R1
FAIL row**, because the binding filters stage outs by weights suffix and a
directory has none. Any commit touching `deps:`/`outs:` must re-run every binding
that parses the pipeline and diff the row set.

**3.18 A phantom stage, and its complement the merge-preserving writer.** choco
and surge both shipped `cmd: python -c "print('reports/train/metrics.json')"`
with that path declared as a `metrics:` output — `dvc repro` exits 0, `dvc
metrics show` renders whatever a human last left there. The tell is `dvc.lock`:
the stage had never appeared in it. The complement is worse and the catalogue
misses it: choco's file *did* have a writer, one that sets two keys and preserves
everything else forever, which is how a hand-typed `lora_f1: 1.0` sat beside
genuinely produced fields across every run.

**3.19 The fabrication walker's green is scoped to a vocabulary.** Four repos
measured this independently, each from a different angle:
- *surge* planted six fabricated defaults in identical `dict.get(name, literal)`
  shape; the walker found **two** (`rmse`, `iou` tokens) and walked past
  `peak_timing_error_h`, `peak_magnitude_error_m`, `total_water_level_m`,
  `runup_r2pct_m`. The repo's own historical fabrication contained values the
  walker structurally cannot see.
- *torrent*: `val/pbias` and `train/pbias` are logged from a real implementation
  into every artifact; `is_measured_name('pbias')` is False while `nse` and `kge`
  are True.
- *choco*: `tokenise('miou') == {'miou'}` — the leading *m* is not split. The two
  fabricated numbers withdrawn in round 2 were `lora_f1: 1.0` and
  `lora_miou: 1.0`, same line, same script. The walker sees one and not the other.
- *choco, second and deeper*: `HARD_CONFIG_TOKENS` is checked **before**
  `MEASURED_TOKENS`, so `oracle_unit_level_rmse` is invisible *despite containing
  `rmse`*. That is a rule-ordering defect; no token addition fixes it.
- *chokepoint*: a fabricated default on a **scenario identifier**
  (`lookup.get(ssp, 1.1)`), which no expansion toward metric nouns reaches.

**3.20 A test that survives the removal of the artifact its subject requires is a
test of the fallback.** *chokepoint.* All three SOTA leakage tests passed for
months with no fragility artifact on disk — they were exercising
`min(1.0, max(0.05, intensity))`, not the ensemble. Fray found the mirror image:
a refusal test pins the **first** refusal, so provisioning any one input silently
converts it from a contract assertion into a historical accident — and in both of
fray's cases the newly reachable path contained a real defect.

**3.21 A tautological assertion removes the incentive to read the function's
inputs.** *chokepoint.* `assert mult >= 1.0` where the `except` branch returns
1.0. Fixing it exposed a served climate multiplier whose 60-day input history was
`rng.normal(0, 5 % of baseline, 60)`, seeded 42, feeding the public
`chokepoint_risk_score`. Nobody had read it because the test looked like coverage.

**3.22 An environment failure must be graded ERROR, never NA.** *chokepoint.*
One readiness run replaced a specific measured `R1 FAIL` naming three checkpoints
with `R1..R6 NA — ModuleNotFoundError: No module named 'numpy'` — six real
verdicts downgraded to unmeasured by an interpreter misconfiguration, rendered
identically to *the repo does not declare this*, overwritten with no archive. The
same file is sitting uncommitted in fray's working tree right now.

**3.23 A report that asserts an artifact's *absence* as a literal.** *arabica.*
Catalogue #11 forbids writing `true` for an absent file; the mirror is unguarded
and arguably worse because it reads as scrupulousness. Verified: the committed
leaderboard says, in bold, **"the shipped CQR/yield checkpoints are absent from
this checkout"** — a string literal, true when written — while
`models/yield_surrogate_coffee.pt` sits on disk. Nothing regenerates it: the
generator is in neither `dvc.yaml` nor the `Makefile`.

**3.24 A gate whose subject is a placeholder needs a mechanical trip-wire.**
*arabica.* `run_blocked_skill` gates `min(skill['ridge_static_floor']) > 0.65`
with a scrupulously honest note saying the subject is *not* the sequence model
and that the real checkpoint should be scored here once one exists. It now
exists. The honesty is what makes it dangerous: it converts a permanent hole into
something that reads as a tracked TODO. The fix is an assertion that the real
artifact does **not** exist, so the gate fails the day it appears.

**3.25 A scanner living in the tree it scans must exclude itself.** Surge's
params reconciliation reported `train.mode` as evidenced by code — because its own
docstring names `train.mode` while explaining that nothing reads it. Chokepoint's
`KNOWN_UNCONSUMED` pin found every orphan it named, itself. Both are catalogue
#18 one level up, and chokepoint's was invisible until the file was *committed*,
because `git grep` does not see untracked files.

**3.26 Method and process findings that cost real time.**
- Rebase when your local commits are only yours; **merge** when they are not.
  Surge's rebase tried to replay two other agents' commits and asked for conflict
  resolution *inside* `run_provenance.baseline_scores`, the most safety-critical
  function in that repo.
- `git push` from any agent in a shared tree publishes every other agent's local
  commits on that branch. Commit only what you would be content to see pushed
  immediately.
- **Measure the fix before you document it.** One round wrote a plausible 25 %
  improvement into a docstring and then measured 2.6 % — in a module whose entire
  subject is not inventing numbers.
- A positive control can be silently vacuous through its fixture's *units*
  (surge: an "overlapping" window offset by one hour, in a fixture whose windows
  span 23 raw units). Assert the planted condition **is** what you think it is.
- An AST gate must be AST, not grep, in both directions: a grep that reads prose
  as code *manufactures* findings against real measurements.

---

## 4. The single most important thing still missing, per repo

| Repo | The one thing |
|---|---|
| **arabica** | **Land the round-2 work on the branch of record.** `e22fc66` is not an ancestor of `feat/observed-panel-and-fabrication-gates`; on that branch `metric_warnings` still has zero readers, the leakage guard is still a partition tautology, and the leaderboard still asserts a false absence. Then the substantive gap: **score `models/yield_surrogate_coffee.pt` on the blocked-year splits against `unit_mean` and `persistence`.** Everything else about this repo is downstream of the fact that its shipped checkpoint has never been scored against a reference that could beat it. |
| **surge** | **More than two storms on the holdout.** The test-split result is the only positive model signal in the fleet and it rests on 320 rows at one lead, and it *contradicts* the val result. Until val and test agree, surge has a promising measurement, not a model. |
| **torrent** | **Close the 0.27 NSE gap to its own ridge, or conclude the ME-LSTM is the wrong architecture at this data volume.** Torrent is the only repo that can state its problem this precisely, and it has not acted on it. Second: the checkpoint is selected on a quantity the artifact does not report (§3.1). |
| **choco** | **Nothing engineering can fix.** The served head is fitted on **26 rows**; `ceiling_probe` measures 98.6 % of log-production variance as between-unit; E-042 says the physics core is inert across every realistic cocoa climate. The missing thing is data, and that is a procurement and signatory decision. The honest next step is to stop improving the model and record why. |
| **fray** | **A checkpoint.** `models/` holds `baselines.dvc` and nothing else. Split identity, capacity records, adapter-vs-base, the blocked county MAPE, the CRPS gate — all of it is unit-tested with positive controls and **none of it has ever run against real weights**. Fray has the fleet's best split-identity implementation and zero evidence that any of it works end to end. |
| **chokepoint** | **A holdout.** `labelled_batch('val')` and `('test')` both raise; three derivable labels on two corridors, all in train. Until a holdout exists, every practice here is being exercised against three numbers. |
| **fleet** | **The mlkit `MEASURED_TOKENS` gap *and* the rule-ordering defect** (§3.19). Four repos measured a miss independently. R10's `findings: 0` currently means "no fabrication whose name overlaps a fleet token list", which is not what anyone reads it as. Signatory-reserved; raised as E-018/E-044. |

---

## 5. The verdict, without hedging

These are two different claims and conflating them is the failure this whole
programme exists to prevent.

### 5.1 Evidence discipline

**World class — the artifact states what it does not know, a gate reads it, and a
positive control proves the gate fires:**

- **resilient-torrent.** The strongest in the fleet. Eleven of thirteen catalogue
  items with positive controls; it *originated* three of them; and it produced
  three of the loop's best new practices (the linear ceiling, the split probe,
  the leaderboard that emits an NA row naming the mismatch rather than a number).
  Its metrics artifact refuses to be invalid JSON, its staging record is
  authoritative over the filesystem, and its evaluation of a third-party
  checkpoint prints two independently-measured refusal gates instead of a score.
- **resilient-surge.** The strongest *promotion gate* in the fleet — three
  refusals including the absent-field rule, with the repo's own bad artifact as
  the refusal fixture — plus the comparability note, the per-split
  `strongest_baseline`, the base-load key check, and a working holdout ledger.
- **resilient-choco, on the served path only.** The observed-panel → head →
  promotion-gate path is as good as anything in the fleet. The conformal/CV stack
  beside it was the opposite (an invented ensemble fan, a climatology pooling the
  test rows, a persistence baseline imputing the row's own label) and is now
  fixed. That asymmetry is itself the lesson: remediation converged on the
  DVC-reachable trainer and left the evaluation code next to it unswept.

**Good, but scoped to almost nothing:**

- **resilient-chokepoint.** The discipline is genuinely excellent — refusal at
  the type level, planted-known-bad testing, the withdrawal pattern, the
  stipulation decomposition. It is applied to **three measured cases**, one of
  which is a training corridor. Rigour over an evidence base this thin is
  necessary and is not the same as evidence.

**Not yet:**

- **resilient-fray.** It has the fleet's best split-identity machinery and its
  `make lint`, `make typecheck` and `make ci` could not execute at all in this
  checkout. Its R10 gate report is **gitignored**, so every plan quoting its SHA
  was quoting a file that exists on one machine. Nothing it built has run against
  a checkpoint.
- **resilient-arabica.** It has the best provenance module in the fleet
  (`supersede_summary`, `file_record`, the offline test guard that documents
  itself as a mitigation) — adopted by **one of three** DVC trainers, with its own
  R1 gate naming the two it missed. On the branch of record, `metric_warnings`
  has zero readers, the group-disjointness guard is a provable tautology, and a
  committed report asserts in bold that a file which exists does not.

### 5.2 Model quality

**No repo in this fleet has demonstrated skill against the operational reference
on a held-out set at a defensible sample size.** Stated per repo, from the
committed artifacts:

- **torrent — the model loses.** Median basin NSE: `exp_a` **−0.319**,
  `exp_b` **−0.448**, `exp_c` **+0.256**. The admissible bar at lead 3 is
  `persistence_lag3`, which scores **0.2486** on the test split against the best
  network's **0.2471**. And a ridge on the same inputs and the same windows
  scores **0.5169**. Torrent is the only repo that can say *why*: the deficit is
  in the training, not in the features. It measured that and published it.
- **choco — the model loses, badly and structurally.** Val log-RMSE **1.4418**
  against `country_previous_year` **0.1995** on the same 42 rows: a **7.2×** loss,
  skill **−6.23**. It beats a pooled constant (2.0329). It was fitted on 26 rows
  with 200 leaves. Its own ceiling probe says no exposure feature can close more
  than ~13 % of a 622 % gap. This is a fact about the panel, honestly recorded.
- **arabica — unknown, and that is the finding.** `val_rmse 0.583234`, skill
  **+0.1827** against the *pooled train mean* — the weakest of the four
  references arabica itself measures, and one its own leaderboard shows losing to
  `unit_mean` by **−1.4331**. The leaderboard states in bold that no trained
  sequence model has a scored entry. Both "the model beats its baseline" and "no
  trained model has been scored" are currently true of arabica, which is exactly
  the situation catalogue #3 exists to make impossible.
- **surge — the only positive signal, and it is unresolved.** On **val**
  (5 storms, 1,024 rows) it loses to persistence at all three leads and is
  statistically indistinguishable from a monthly climatology: at 6/24/48 h the
  model scores 0.225810 / 0.214811 / 0.215184 against climatology's
  0.224081 / 0.215142 / 0.216631 — it *loses* at 6 h and wins by under 1 % at the
  other two. On **test** (2 storms, 320 rows, 24 h only) it beats every reference,
  with skill +0.197 and +0.103 against climatology. Two storms is not a
  demonstration. Separately, its LoRA adapter is **14.6 % worse** than the base it
  adapted (`adapter_skill_vs_base: −0.145873`), which the repo measured, wrote
  down, and now refuses to promote.
- **fray — there is no model.** `models/` contains `baselines.dvc` and a README.
  The floor is measured (test MAE **113.07 lb/ac** for persistence,
  **222.71** for the train constant); nothing has been scored against it.
- **chokepoint — there is no model in the machine-learning sense.** The shipped
  predictor is `measured_corridor_capacity × hand-typed_activity_drop`. It beats
  both references (skill **+0.791** / **+0.745**) on **three** cases, one of which
  is a training corridor, and its own decomposition attributes **0.531 of the
  0.791** to the corridor-size lookup. Its SOTA ensemble is honestly all-NA with
  four warnings, because refusing the unlabelled fallback emptied the leaderboard.

**The plain summary.** Three of six repos have world-class evidence discipline
(torrent, surge, choco-on-the-served-path). Zero of six have a model that has
demonstrated skill against its operational reference on a holdout of defensible
size. One repo — surge — has a genuine positive signal on two storms that
contradicts its own validation result and must be resolved before it is quoted.
Two repos have no model at all. One repo's model loses to copying last year's
number by a factor of seven. One repo's model is a quarter of an NSE below the
ridge you could fit in ten lines on the same data.

That is the correct output of this programme. Every one of those statements was
unavailable eighteen commits ago, and several of them were actively contradicted
by the artifacts these repos were shipping. A fleet that can say precisely how
its models fail is worth more than a fleet that reports numbers nobody can check
— but it is not the same as a fleet with good models, and nothing in this report
should be read as claiming otherwise.

---

## 6. Open, reserved, or measured-and-not-acted-on

- **Reserved to the signatory:** arabica's 50 km buffer and block geometry (a
  holdout-narrowing decision); arabica's `params.yaml` batch_size/lr
  reconciliation; surge's declared fine-tune base (`params.yaml` names the epoch
  its own run rejected); choco's `train.batch_size`/`lr` (declared 8/3e-4, running
  64/1e-3); every `docs/allowlist.yaml`; the mlkit `MEASURED_TOKENS` change.
- **Measured, named, unfixed:** arabica's eight non-DVC scripts that draw from an
  RNG and write into `reports/` or `config/`, the `neuralgcm` adapter branch that
  logs "real inference" and returns a synthetic ensemble, and the two closed-form
  HPO modules the runbook tells operators to run; torrent's return-period map
  fitted on 50 `rng.lognormal` draws, ungated, feeding the avoided-loss chain, and
  its unlabelled `stage = 0.5 + sqrt(Q/10)` rating-curve fallback; choco's
  `optuna_galileo` objective, which calls a real benchmark and never passes it the
  trial; fray's 40 uncited hazard weights, now inert on the training path, and the
  single uncited three-constant heat curve that is the model's entire hazard
  response as a result; chokepoint's ICIO branch graded `measured` on an
  unaudited artifact.
- **Housekeeping that keeps costing time:** three of six repos have test suites
  or tooling that write into the tracked tree; two have gate reports whose header
  SHA is stale; one has a committed gate report with no SHA at all, which cannot
  be aged; several are being edited by concurrent agents in shared worktrees.

