# Do these models beat their baselines?

**Adjudicated 2026-08-23/24, through three rounds** (eight repos; round three
covered torrent, chokepoint, blackout and triage) by independent verification
against the committed artifacts. Every number below was read out of an artifact on
disk or recomputed by me from the artifact's raw per-unit table; none is taken from
an agent's prose. Where I recomputed or re-ran something myself, I say so.
The previous four-repo adjudication (2026-08-23) that this file replaces concluded
no model beat its bar; three of those four verdicts have genuinely flipped since,
and the flips survive the refutation checks below.

## Verdict table

**Revised 2026-08-24 after round THREE.** Scores are the committed test/holdout
readings; "model of record" (MoR) states what the repo now actually serves or
registers as the production predictor.

| repo | model score (test/holdout) | strongest admissible baseline | beats it? | promoted model of record | do I believe it? |
|---|---|---|---|---|---|
| resilient-arabica | RMSE **1.056760**, skill **+0.0257** (unchanged; read spent) | expanding per-unit prior mean **1.084686** | **Yes** | **Yes — the 11-feature history ridge**, with model card; GRU promotion bar now wired to it | **Yes** — round-2 hardening verified: Surigao 0.001 ha is the PSA-published value (checked at source, px API, 2026-08-23), win chain intact on the feature branch |
| resilient-triage | test RMSE **173.408**, skill **+0.0546** vs persistence **183.423** (2nd read; arm CLOSED at two, not re-read in round three) | previous-week persistence | **Yes** | **Yes — cbdiff_pois PROMOTED AND SERVED** (round three): `champion.json`, self-hash `ec8bd643…` verified by me, behind `/v1/weekly-mortality/*`; persistence demoted to *recorded bar* behind a challenger gate that returns NA rather than PASS on an unmeasured comparison | **Yes** — all three E-029 preconditions discharged on measurement; converged fit moves val skill by **3.33e-16** and LOCO by **9.21e-15**, so the suspension clause did not trigger; serving path reproduces val RMSE at absolute difference **0.0** through a different code path |
| resilient-torrent | **two separate answers, both val**: ME-LSTM at 10 epochs, n=8 seeds, mean **0.2226**, 95% interval *on the mean* **[0.1996, 0.2455]**; the same config at 30 declared epochs, n=3, mean **0.3734**, interval **[0.3106, 0.4363]** | `persistence_lag3` val **0.26484** | **10 epochs: No — 0 of 8 draws, whole interval below the bar. 30 epochs: Yes — 3 of 3, whole interval above.** Neither beats the repo's own ridge (**0.4521**, same 65 rows, `same_rows: true`) | **The ridge is the model of record** (E-030) — not the network. No ME-LSTM promotion; test arm left unspent | **Yes** — interval is correctly on the MEAN, with the range printed beside it and an explicit note that it is *not* a prediction interval for the next seed. Two of its own claims retracted in-tree mid-round |
| resilient-fray | **SUPERSEDED — do not quote this row for `forecast_available`.** It reads TEST MAE **82.754** (forecast_available, neighbour-extended) / **71.359** (spatial_infill). `mlkit portfolio` measured fray's committed record on 2026-08-29 as **74.16097783177521** for `forecast_available`; the `71.359` for `spatial_infill` still matches. See *Does the machine agree with the hand transcription?* below and **E-M06** | `persistence_t_minus_1` **113.067** | **Yes, both tracks, both metrics** (the machine confirms `beats` still true for both, against the same floor) | **Yes — both track winners registered** as models of record, hash-pinned, bar enforced in code | **STALE for `forecast_available`.** The belief recorded here — *"I re-hashed both checkpoints on disk myself (match); prereg → val-select → single test read commit order verified"* — was formed against the winner that has since been replaced. It is left standing, unedited and marked, because re-adjudicating fray's new record is judgement and was **not** performed here. `spatial_infill` is unaffected |
| resilient-blackout | in-scope extension test ROC AUC **0.6776** vs planning anchor **0.6412** (single sealed read, *cited* in round three, not re-run); persistence **0.6899** on the shared subset | persistence **0.6899** (not like-for-like: needs the outage feed E-021 reserves) | **Beats its anchor (+0.0364); still loses to persistence by 0.0096** | **No — THE PROMOTION GATE REFUSED**, and was left refusing. `weather_failure_v1.joblib` (13 columns, mtime 2026-08-21) is still what ships | **Yes, and the refusal is the round's best result** — the gate refuses the *shipped* model with an **identical failing set and identical mapped metrics**, which proves the refusal is about the gate, not the candidate (E-022) |
| resilient-chokepoint | train LOCO advantage **−0.0398 mtpd** (p=0.498); design's in-sample oracle ceiling **+0.0527**, below the claimed **+0.0580** scale-matched; coarsened target T2 AUC **0.7143** vs its own reference **0.6984**, p=0.610 | operational `scale_x_train_mean_depth` (T2: `corridor_scale_only`) | **No, and now stronger than "unestablished": the claim as made is ABOVE the design's information ceiling**, so no episode count produces it. Coarsening the target did not rescue it | **No promotion**; the operational baseline remains the served predictor and the bar | **Yes** — and it is the only repo that separates *absent* from *underpowered* by measurement rather than by assertion (see round three) |
| resilient-surge | NN holdout **0.175095 m** | `per_lead_anchor_ols` **0.163736 m** | **No** | **Yes — the OLS itself promoted**: registry production slot, sha256-verified fail-closed serve path, gate strengthened to refuse NN checkpoints on their own holdout warnings | **Yes** — no new test read spent (ledger still 3), warnings recorded in the artifact, not suppressed |
| resilient-choco | climate head **2.6898** vs lag-1 **0.2277** log-RMSE (unchanged) | lag-1 persistence | **No** | **Yes — lag-1 persistence is the served predictor of record**, NA-with-reason on cold start; head retired with `NOT_PROMOTABLE=True`; challenger gate requires measured positive skill vs it | **Yes** — val 0.199526 / test 0.227719 verified; test figures asserted byte-equal to the single 2026-08-23 read, not re-read |

Cycle score (round three): **six of eight repos now serve a predictor that beats
or IS its operational baseline.** Three beat it with a real model (arabica, fray,
and now **triage**, promoted this round); two ARE the baseline, honestly promoted
as the product (surge, choco); one serves a *learned* reference that beats the
admissible bar while the neural candidate does not (**torrent**, where the ridge
is the model of record). **Two serve a predictor that does not beat its
reference**: blackout (still below persistence on test, and its promotion gate
refused this round's candidate) and chokepoint (the operational baseline is the
served predictor and the challenger measures worse than it). Zero fabricated
numbers found in any of the three rounds; every headline figure in this table was
reproduced from a committed artifact on disk.

---

## Refutation checks on the repos that improved materially

### resilient-arabica (skill −0.0015 → +0.0257 on test) — VERIFIED, stands

* **Artifact integrity**: `reports/validation/yield_reference_skill.json` in worktree
  `wf_62f9a612-3c8-4` hashes to `b5db6841…4b6739ad` — exactly the sha in the claim.
  Val skill +0.05067 (CI [+0.0322, +0.0681]), test +0.025746 (CI [+0.0186, +0.0490]),
  BR +0.0343 / PH +0.0245: all match to the reported precision.
* **Target-period features?** No. All 11 features are strictly-prior label history;
  I re-ran `tests/validation/test_unit_history.py` myself against the repo venv:
  **8/8 pass**, including the within-unit label-shuffle positive control (skill
  collapses <0.01) and both tamper-direction tests.
* **Test touched during selection?** No. Commit order is `b222cb6` (config committed,
  selection on val by a pre-declared rule) → `08a6a79` (single test read) → `1ebbd8b`
  (mypy fix). The artifact records `test_scored: true` once.
* **Same baseline, same rows?** Yes — expanding prior mean, first-year rows excluded
  from BOTH sides (339 NA rows recorded with reason per split, identical counts both
  sides).
* **Leak-sized?** No. +2.6% RMSE is lag-feature-sized. The gain replicated from val
  at half size — shrinkage, not collapse, and not a leak signature.
* **Caveats that stand**: one area-rounding row (PH Surigao del Norte 2023) carries
  86.9% of test squared error — the artifact warns; MAE skill (+0.0418), per-country
  and unit-bootstrap readings all agree, so the headline survives. **Catalogue #19
  CLOSED 2026-08-24**: when adjudicated, commit `1ebbd8b` lived on branch
  `worktree-wf_62f9a612-3c8-4` only and the feature branch (then `da819ed`) did not
  contain it. Re-measured after the delivery sweep: all three commits of the win
  chain (`b222cb6` → `08a6a79` → `1ebbd8b`) are ancestors of `2f47a81`, which is the
  live tip of `refs/heads/feat/observed-panel-and-fabrication-gates` on the remote
  (verified by `git ls-remote`, not by a remote-tracking ref -- these repos fetch
  only `main`, so `git branch -r --contains` reports every feature branch as absent
  and is not evidence of anything). The artifact's separate warning that the GRU
  checkpoint is absent from that worktree still stands and is a different fact.
* **What would change my mind**: the flagged row's treatment changing between
  reference and model sides (it doesn't — same rows both sides); or a future re-read
  of this test block after any further iteration (the read is spent).

### resilient-torrent (NSE 0.2471 → 0.3647) — VERIFIED, stands as one draw

* **I recomputed the headline** from the artifact's 30 per-basin NSE values:
  median 0.36467334974752313, mean −3.4767, fraction positive 0.767 — all match.
  Baseline 0.2485603278795256 present in the same file, same scorer, same rows,
  2 basins NA with recorded reasons.
* **New features?** None — commit `d91473a` touches only `cli.py` and two training
  configs (lr, clip, milestones, seed, epochs). The gain lands where the pre-existing
  ridge diagnostic (0.5169) said headroom existed, and stops short of it — the
  opposite of a leak signature.
* **Test touched during selection?** No — `reports/holdout_reads.jsonl` first entry
  is the one read, at the committed checkpoint sha `021d59c9bf91cbaa…`, git sha
  `d91473a`. Selection was on val across four candidates.
* **Gates loosened?** No — the promotion gate **still refuses** the artifact
  (`selection_metric_differs_from_reported_metric`, verified in
  `melstm_d_test_gate.json`) and was left refusing. That refusal is correct: the
  run's own monitor selects on a different quantity than the reported metric, so the
  shipped epoch was chosen externally on recorded val artifacts.
* **Believe it?** The bar is cleared on this draw. But val margin over persistence is
  +0.015 against a test margin of +0.116, mean NSE is −3.48 (two catastrophic
  basins), and the ridge still leads by 0.15. A genuinely better model, not yet a
  stable or shippable one. **What would change my mind**: a retrain under the
  fixed median-basin monitor scoring materially differently, which the repo's own
  BLOCKERS.md already demands before promotion.

### resilient-fray (no model → MAE 71.36/84.57 vs floor 113.07) — VERIFIED, stands

* **Artifact committed on the feature branch** (`01432e2` on
  `feat/full-belt-panel-and-fabrication-gates`, main checkout — no worktree gap).
  Floor, both track scores, and all-splits baseline table verified in
  `reports/validation/observed_panel_model.json`; 8,879 test rows on both sides.
* **Target-period features?** The one real asymmetry — the calendar-year feature
  learning same-year cross-county shocks under a spatial split — is *disclosed and
  ablated*: the `forecast_available` track drops it and still beats the floor by 25%
  MAE. I treat **84.57** as the honest operational claim and 71.36 as a
  spatial-infill claim only, exactly as the artifact itself labels them.
* **Shuffle control**: present in the committed artifact
  (`shuffled_target_control`: val MAE 171.46 after within-county shuffle refit —
  worse than the 117.12 floor). Features rebuilt from the shuffled panel, so the
  control exercises the full pipeline.
* **Selection/test discipline**: selection rule declared (val MAE, capacity
  tie-break), test scored once per track; `metric_warnings []` comes from machinery
  whose rules all fire on a positive control.
* **What would change my mind**: evidence the expanding-window climatology features
  see the row's own year (the mutation test — feature vector byte-identical under a
  1e9 target — says they don't); or VAL/TEST divergence appearing at this capacity
  (currently 70.3 vs 71.4 MAE, no memorisation signature).

### resilient-blackout (AUC 0.6533 → 0.7820 vs persistence 0.6816) — VERIFIED, but read it as an information win with a scope condition

* Numbers verified in committed `weather_failure_short_lead_metrics.json` (commit
  `cca9305`, branch `feat/conformal-risk-control-causal-impact-suite`): model 0.7820
  / persistence 0.6816 on the identical 71,042 rows, 8,762 NA with reason.
* **Target-period features?** No, measured: the same-day probe flipped 20,000 labels
  and **0 of 19,172** compared history cells moved (828 lag-window collisions
  excluded and counted); the k=0 positive control trips it; shuffle test collapses
  lag1 to ~0.5 with a discriminating control for the leak direction.
* **The honest framing the artifact itself keeps**: a logistic on the same 22
  columns scores 0.7825 — `no_gain_over_linear_ceiling` fires. The +0.10 AUC is the
  lagged-outage information, which is admissible precisely when the operator holds
  day-t−1 records — the same precondition persistence itself carries. Whether that
  deployment is in scope is escalated (E-021), not decided; the shipped planning
  checkpoint is byte-identical to before and still records `loses_to_persistence`.
* **Verdict**: beats the baseline like-for-like, yes, and I believe it. But calling
  this "the model got better" would be wrong — the feature contract got honest about
  what a short-lead issuer holds. Test split remains sealed.

### resilient-chokepoint (first model to nominally beat the baseline) — DOWNGRADED

* Arithmetic verified in committed `episode_skill.json` (`b694526`): val 0.5751 vs
  0.6115 (5 episodes, 2 corridors), test 0.1549 vs 0.2595 (2 episodes, 2 corridors),
  selection on val, test read once.
* But on the only split with enough corridors to resample, the selected model is
  **worse** than the baseline (LOCO −0.045 mtpd) and the permutation null reproduces
  the observed pattern (p=0.390, 200 draws). Two test episodes cannot overrule that.
* The agent's own artifact verdict — "NOMINAL, NOT ESTABLISHED … do not promote, do
  not quote the test skill without this sentence" — is exactly right, and
  `beats_baseline_now: true` in the summary JSON is the one field in this cycle I
  reject as written. What this session genuinely delivered is measurement machinery
  (22 episodes vs the old n=3 straddled hindcast, a real availability leak found by
  its own positive control and fixed at the root). **What would change my mind**:
  more corridors (E-020) and the pinned configuration holding its margin on episodes
  detected after this read.

---

## The honest losses (verified as honest)

* **resilient-surge** — 0.182847 → 0.175095 m is real progress (now beats
  train_mean and the 7-term forcing OLS on the holdout), but the per-lead anchor
  damping stands at 0.163736 and the model loses to it in every lead bucket.
  Verified: pre-registration commit `748e07a` with deliberately empty results, then
  read #3 in `reports/holdout_reads.jsonl`, results in ANCHORED_RESIDUAL.md §8.5.
  The parallel collapse of the 8-term linear reference behind the 2-term version of
  itself on the same two storms is strong evidence for the data-ceiling reading.
  E-037 correctly bars further reads; the fix is more storms or real forecast
  forcings — signatory decisions, not tuning.
* **resilient-choco** — the exposure-covariate hypothesis is closed by measurement:
  offered to the optimiser, `shipped_exposure_split_count = 0`, importances exactly
  0.0 (verified in the run sidecar `models/observed_production_head.meta.json`;
  note the sidecar itself is untracked — the numbers are pinned in committed
  docs/ESCALATIONS.md and tests, but the JSON should be committed or DVC-tracked).
  Four independent refutations of beatability now stand. The only unlock is
  administrative (FAOSTAT ALLOWED on the signed allowlist since 2026-08-17 vs code
  still enforcing EVAL-ONLY) and is correctly escalated (E-045), not applied.
* **resilient-triage** — val improved honestly (+0.0173 → +0.0236, and I verified
  the shuffled-target artifact collapses to −0.0063), but the one committed test
  read governs: −0.0054. The ridge at +0.0248 on the same rows locates the deficit
  in spline transferability across the longitude envelope — a fixable fit problem,
  escalated (E-027) rather than iterated against a spent holdout.

---

## Evidence discipline vs model quality — the distinction this programme exists for

**Evidence discipline is now uniformly excellent across all eight repos**: declared
selection rules committed before test reads, append-only holdout ledgers, positive
leakage controls that demonstrably fire, refusals recorded as NA-with-reason, gates
left refusing when they refuse correctly, and three agents reporting their own
models' losses with the same care as the winners reported wins. I found zero
fabricated numbers and zero loosened gates in this cycle.

**Genuinely good models are rarer.** Ranked by how much model there actually is:

1. **fray** — the one unambiguous case of model class buying real skill (25–37%
   MAE over the floor, on top of a ridge that already beat it): capacity was the
   deficit and trees closed it.
2. **torrent** — a real training fix (+0.12 NSE) measured against a linear
   diagnostic that predicted the headroom; still 0.15 below that diagnostic.
3. **blackout** — a large number that is ~entirely feature information; the model
   architecture contributes +0.0009 over logistic.
4. **arabica** — a small, real, well-defended +2.6%; everything the model knows
   beyond the unit's own mean.
5. **chokepoint / surge / choco / triage** — no established model skill; the assets
   are the measurement harnesses and the closed hypotheses.

The failure mode this file guards against — mistaking a beautifully documented
holdout ledger for a model worth shipping — is live in exactly two places this
cycle: chokepoint's `beats_baseline_now: true` (the discipline is world-class; the
skill claim is not established) and any temptation to quote fray's 71.36 or
blackout's 0.7820 without their information-set conditions.

## Open follow-ups

*(Round-1 list, kept for the record — superseded by the round-two list at the
bottom of this file. Items 1 and 2 are resolved: the arabica worktree win is
merged and on the remote branch, and torrent retrained under the fixed monitor.)*

1. **arabica**: merge `worktree-wf_62f9a612-3c8-4` (`1ebbd8b`) into
   `feat/observed-panel-and-fabrication-gates` — the winning artifact is not on the
   feature branch yet (catalogue #19).
2. **torrent**: retrain under a median-basin-NSE monitor before any promotion; the
   gate is right to refuse until then.
3. **choco**: commit or DVC-track `models/observed_production_head.meta.json`;
   signatory decision on E-045 (FAOSTAT posture).
4. **blackout**: signatory decision on E-021 (short-lead scope).
5. **chokepoint**: E-020 — more corridors, or wait for the next detected episode to
   falsify the pinned config for free.
6. **surge/triage**: holdout reads are spent; E-037/E-027 gate any further work.

---

# Round two — adjudicated 2026-08-24 against the committed artifacts

Every claim below was verified by me directly: remote tips via `git ls-remote`
(never local refs), numbers read out of the committed artifact at the claimed
sha (never from agent prose), commit ordering for every pre-registration, and
independent re-hashing where a hash was claimed. All eight claimed commits are
the exact remote tips of their claimed branches.

## Delivery (the failure mode that struck twice in round one): CLOSED

| repo | branch | remote tip | = claimed commit? |
|---|---|---|---|
| triage | `feat/dlnm-common-contract-production-readiness-v2` | `2f14098` | yes |
| torrent | `feat/caravan-scale-and-fabrication-gates` | `377c36f` | yes |
| chokepoint | `feat/observed-trade-and-fabrication-gates` | `390149b` | yes |
| blackout | `feat/conformal-risk-control-causal-impact-suite` | `cef5e8b` | yes |
| surge | `feat/surgeistm-lora-finetune` | `de37edd` | yes |
| choco | `review/observed-labels-fixes` | `e6591c6` | yes |
| arabica | `feat/observed-panel-and-fabrication-gates` | `924b7f1` | yes |
| fray | `feat/full-belt-panel-and-fabrication-gates` | `4e18038` | yes |

Round one's open follow-up #1 (arabica worktree win not on the feature branch)
is resolved: `1ebbd8b` and the adjudicated merge `cca023e` are ancestors of the
remote tip. Fray's two previously-local measurement commits (`f749c09`,
`01432e2`) are likewise on the remote branch now.

## Per-repo verification

### triage — the fit-problem diagnosis confirmed by measurement; win, not yet promoted

* Pre-registration `ec7534a` (189-candidate selection artifact, `selected_on:
  "val"`, `test_read: false`, argmin-val rule) precedes the test-read commit
  `2f14098`. Selected candidate identity (cbdiff_pois, exposure_df=10,
  lag_df=4, penalty=1.0, `poisson_converged: false` recorded) is byte-identical
  between selection and read artifacts.
* Test read verified: model RMSE **173.40814** vs persistence **183.42262**
  on 26,000 scored rows (1,060 refused with per-reason counts), skill
  **+0.05460**; log-scale +0.0506 agrees. Val +0.04121 matches.
  `test_read_multiplicity.reads_of_this_test_arm: 2` is recorded *inside* the
  artifact with both reads named; the arm is declared closed.
* One label discrepancy in the agent's report, not in the artifact: the claimed
  shuffle collapse "−0.0004" is `skill_vs_own_anchor` after the within-geo
  shuffle; vs the best reference the shuffled skill is **−0.2939**. Both
  readings say collapse — the leakage conclusion stands, the quoted number was
  the milder of the two.
* Promotion correctly NOT taken: `2f14098` touches only docs, the report and
  tests. Persistence remains the recorded operational bar; champion promotion
  is prepared as signatory material in E-028.

### torrent — round 1's win retracted by its own root fix; honest negative

* Root fix verified: the gate report `melstm_f_s1234_val_gate.json` runs a
  `selection_consistency` check and its **sole refusal is
  `no_skill_vs_persistence_lag3`** (model 0.23207 vs baseline 0.26484) — the
  `selection_metric_differs_from_reported_metric` refusal is gone because the
  monitor now logs the same number the artifact reports (both present in the
  run artifact, equal to ~5e-9).
* All three seed artifacts verified: 0.23207 / 0.25978 / 0.20665 vs bar
  0.26484 on identical windows — 0 of 3 clears. Pre-registration `616deb2`
  (candidate = seed-1234 only, test read conditional on val > 0.26484) precedes
  the results commit; the condition failed, and `reports/holdout_reads.jsonl`
  still contains exactly **one** read (the round-1 `d91473a` read). No test
  read was spent. Round 1's 0.3647 must now be read as one favourable draw
  selected on a mismatched monitor; this file's round-1 caveat ("as one draw")
  was the right instinct and is now the verdict.

### chokepoint — the downgrade is now a measurement, at 4.6x the evidence

* Pre-registration `8526f16` (parameterised episode rule, uniform-threading
  contract test, declared relaxed tier and decision rule) precedes results
  `390149b`. Decision rule in the artifact: supported iff relaxed-train LOCO
  advantage > 0 AND p <= 0.05 — **not met**: −0.0398 mtpd, p=0.498 (1000
  draws). Primary tier reproduces round 1 (−0.0450, p=0.429 vs the old 200-draw
  0.390). 98 scoreable episodes / 25 corridors / 21 refusals with reasons; both
  tiers record `holdout_read: NONE` and the only test read remains 2026-08-23's.
* `ridge_depth_a100` at +0.1055 LOCO skill on the relaxed train frame verified
  in the artifact — correctly logged as a post-hoc lead requiring a fresh
  pre-registered cycle, and `metric_warnings` carries the
  not-distinguishable-from-null caveat. Allowlist mis-pin escalated (E-021
  chokepoint), not acted on.

### blackout — in-scope ceiling extended; scope call still with the signatory

* Pre-registration `6b9ea8e` (ladder + selection rule in code + selected
  config) precedes the read commit `cef5e8b`, which adds only docs and the
  test-read artifact. I recomputed the ladder file's sha256 at `6b9ea8e`:
  `9f165a28…` — exactly the pin inside the test-read artifact.
* Ladder verified: base 0.65223/0.62926 reproduces the round-1 pinned val
  numbers; `all_in_scope` selected at val 0.68486 (delta +0.0326 > the
  pre-declared +0.005). Test read verified: all_in_scope **0.67762**/0.42530
  (subset 0.68028/0.44689), anchor 0.64117/0.38741, persistence
  **0.68988**/0.40917, climatology 0.52980, linear ceiling 0.64605. ERA5/ISD/
  IBTrACS recorded NA with reasons. The val-vs-test persistence disagreement is
  reported in the artifact, not smoothed.
* `docs/MODEL_CARD.md` diff between `cca9305` and `cef5e8b`: empty. E-021
  material prepared (`docs/E021_DECISION_MATERIAL.md`), no recommendation, no
  decision. Shipped checkpoint untouched.

### surge — the reference promoted, mechanically, with the artifact treatment

* Registry verified: `data/model_registry/index.json` holds
  `surge-residual-forecaster` v1.0.0 → `per_lead_anchor_ols`, val 0.175231 /
  test 0.163736, with **both** val metric warnings
  (`no_skill_vs_anchor_plus_forcing_ols`, `loses_to_strongest_baseline`)
  recorded in the registry entry itself, alongside the measured context that
  the val ordering did not transfer (8-term OLS 0.160829 val → 0.182072 test).
* Serve path verified in code: `serve/dependencies.get_model_of_record`
  resolves the registry production version to `ReferenceSurgeRunner`, which
  verifies coefficients.npz sha256 against the artifact's own pin and fails
  closed; the ONNX runner's docstring subordinates it explicitly.
* Gate diff verified strengthened-only: `assert_base_run_shippable` gains a
  refusal on non-empty `holdout_metrics.json` warnings; nothing loosened.
  `holdout_reads.jsonl` has exactly 3 lines — the promotion's test evidence is
  copied verbatim from read #3, no read spent. The val extensions run
  (`reports/val_linear_extensions.json`) records `test_split_read: false` and
  every candidate's `spend_test_read: false` under the pre-declared 3-condition
  rule (best candidate anchor+|U|², 5/5 val events but 16/22 LOEO, margin
  0.0104 < 0.0144).

### choco — the reference promoted as the served product; head retired, not deleted

* Artifact pair committed at `e6591c6` (`observed_production_persistence.json`
  + sha256-carrying `.meta.json`, `served_predictor_of_record: true`). Numbers
  verified: val lag-1 **0.199526** (42 scored / 10 abstained with reason), test
  **0.227719** (33 / 9); paired-on-identical-rows baselines: train-mean 2.3395
  vs 0.1995 (skill 0.9147), lag-2 0.1508 vs 0.0953 (0.3681), lag-3 0.2131 vs
  0.0922 (0.5674) — lag-1 dominates the family on shared rows. Served
  (Licence-Ouverte) subset recorded separately and honestly: 0.4719 val /
  0.3268 test. The test block is asserted equal to the single 2026-08-23 read
  (`test_read_cross_check`), not a second look.
* `observed_head.py` carries `SERVING_STATUS="retired"`, `NOT_PROMOTABLE=True`,
  a measured `RETIREMENT_REASON`. `gate_beats_served_reference` exists, is
  wired into `run_promotion_gate`, treats unmeasured as NA-never-pass, and a
  committed test proves the retired head fails it on its own sidecar.

### arabica — the round-1 win hardened; ridge is the model of record

* Chain verified on the remote branch: `cca023e` (merge of the winning
  worktree) → `a9208ff` (source check) → `3d16274` (model card) → `924b7f1`
  (promotion wiring). `reports/validation/yield_reference_skill.json` untouched
  since the merge — the spent test read was not regenerated.
* Surigao del Norte: evidence file committed with the resolvable px API URL,
  retrieval date 2026-08-23, table ids, and metadata (`UNITS=hectares`,
  `DECIMALS=15`); the 0.001 ha is PSA's own published value, so the row
  correctly stays in the test split. The card
  (`docs/MODEL_CARD_YIELD_PRIOR_RESIDUAL.md`) states what the ridge beats and
  what it does not claim.
* Promotion bar verified: the trainer writes `no_skill_vs_model_of_record` /
  `model_of_record_not_measured` into `metric_warnings`, and
  `gate_training_metric_warnings` refuses on ANY non-empty warning list — the
  new codes are blocking by construction, no gate edit was needed or made.

### fray — records registered and immediately, properly, superseded once

* Commit order verified: `971f568` (register both round-1 winners, hash-verified
  copy of the committed measurement) → `d6f5a8e` (pre-registration: 20-candidate
  menu + decision rule, before any fit) → `e93a67e` (val phase: winner 82.753 vs
  incumbent 84.666, margin 1.913 > 1.0; within-county shuffle collapses to
  171.63 vs floor 117.12) → `4ea08b7` (single test read: **82.754 / 114.685**,
  strictly clears the record's 84.565 / 118.185 on both metrics) → `4e18038`
  (promotion with supersession chain recorded).
* I re-hashed both registered checkpoints on disk myself:
  `d7952493…` (spatial_infill) and `8c90a48b…` (forecast_available+nbr) — both
  match the record exactly. The record rule requires strict improvement on both
  metrics via the same scorer/split, selected on val, test once; the
  dual-stream NN is explicitly not superseded and E-019 untouched.

## Who has a promoted model of record now — stated plainly

* **Beats the baseline and is promoted**: **arabica** (history ridge, +2.6%
  RMSE over the prior mean, card + wired promotion bar) and **fray** (both
  track records, 27–37% MAE over the persistence floor, hash-pinned and
  bar-enforced in code).
* **IS the baseline, honestly promoted as the product**: **surge**
  (per_lead_anchor_ols in the registry production slot, sha-verified serve
  path) and **choco** (lag-1 persistence as the served predictor of record,
  NA-with-reason coverage policy).
* **Measured winner, promotion reserved for the signatory**: **triage**
  (+0.0546 on the closed second read; persistence remains the recorded bar
  until the signatory promotes the winner — E-028).
* **No promotable model**: **torrent** (the fixed selection metric retracts the
  round-1 win, 0/3 seeds clear persistence_lag3; the ridge diagnostic remains a
  reserved scope decision), **blackout** (extension held on test but E-021
  scope call pending; nothing served changed), **chokepoint** (honest negative
  at the panel's measured ceiling of 98 episodes; next move is signatory data,
  E-021 chokepoint).

## Discipline verdict, round two

The two failure modes round one flagged are both closed: delivery-means-remote
held in all eight repos, and the one repo whose win rested on a selection
mismatch (torrent) retracted its own win when the mismatch was fixed — the
strongest possible evidence the machinery is real. Three test reads were spent
this round (triage, blackout, fray), each on a configuration committed in a
prior commit, each recorded with multiplicity; four possible reads were
declined because pre-registered preconditions failed (torrent, surge x3
extensions, chokepoint under both tiers). No gate was loosened; two were
strengthened (surge holdout-warnings refusal, choco/fray/arabica
beat-the-record bars). The one imprecision found in eight reports — triage
quoting the anchor-relative shuffle skill (−0.0004) where the
reference-relative figure is −0.294 — is conservative in direction and does
not touch the conclusion.

## Open follow-ups after round two

1. **triage**: signatory decision on promoting cbdiff_pois (E-028); test arm
   closed — any future candidate needs post-2026-08-24 ISO weeks or a fresh
   signatory-accepted read.
2. **torrent**: the next honest lever is a declared larger training budget
   (curves still rising at epoch 9); finetune path still selects on the pooled
   metric and stays gate-refused (BLOCKERS.md). Ridge serving remains E-025.
3. **blackout**: E-021 scope decision, now with decision material covering both
   scopes; IBTrACS is named in the model card but absent from the signed
   allowlist.
4. **chokepoint**: signatory decision on Daily_Ports_Data (E-021 chokepoint);
   ridge_depth_a100 needs a fresh pre-registered cycle before it may be
   claimed.
5. **surge**: route-level integration of the model of record into the HTTP
   hazard path (currently registry + dependency level); E-040 maturity tier.
6. **choco**: E-045 FAOSTAT serving posture; the >=4–5 CCC crop-year data
   requirement is the standing unlock (E-046).
7. **fray**: DVC stage for the extension checkpoint; tmp_path fix for the
   pytest fixture overwrites of release_evidence/.
8. **arabica**: the run-B GRU weights still live only in the stale worktree;
   promoting them is exactly what the new bar exists to test — leave them
   unpromoted until a run clears it.

---

# Round three — adjudicated 2026-08-24

Four repos reported this round: **torrent, chokepoint, blackout, triage**. I read
every artifact named in each report off disk, recomputed the load-bearing
arithmetic, and tried to refute each claimed improvement. **All four commits are on
their remote branches** (`git ls-remote`, verified individually):

| repo | commit | remote ref |
|---|---|---|
| torrent | `583185bf…` | `refs/heads/feat/caravan-scale-and-fabrication-gates` (+ `refs/pull/131/head`) |
| chokepoint | `04d81fec…` | `refs/heads/feat/observed-trade-and-fabrication-gates` (+ `refs/pull/71/head`) |
| blackout | `bc731166…` | `refs/heads/feat/conformal-risk-control-causal-impact-suite` (+ `refs/pull/129/head`) |
| triage | `afb33e9b…` | `refs/heads/feat/dlnm-common-contract-production-readiness-v2` (+ `refs/pull/94/head`) |

No stranded worktree work this round. Two agents (chokepoint, triage) reported
being handed an isolated worktree of **resilient-arabica** for work targeting a
different repo, worked in the correct repo instead, and said so in their reports.
**That orchestration bug is real and should be fixed** — both agents caught it, but
a less careful run would have committed cross-repo.

## The four commissioned questions, answered

### torrent — was the test arm left unspent? Is the interval honest? Is the ridge on the same rows?

**Yes, yes, and yes.**

* **Test arm unspent.** `reports/holdout_reads.jsonl` holds exactly **one** line,
  and `git log` on that path returns exactly one commit (`e7f04bd`, the round-1
  read at 2026-08-24T00:06:32Z). The 25 commits of round four (10:19→13:26) do not
  touch it. Two candidates cleared the bar on val and **neither read was spent** —
  which is the whole value of the rule, since it bound on a day the answer was
  favourable.
* **The interval is on the MEAN and says so.** `seed_summary_n8_val.json` reports
  `interval_on_the_mean: [0.1996, 0.2455]` built from `sem = 0.0097`, with `range:
  [0.1722, 0.2598]` printed separately and this note in the artifact: *"It is not
  the range of the draws, and it is NOT a prediction interval for the next seed."*
  I recomputed mean, sample stdev, sem and the t-critical from the eight raw values
  — all match to printed precision. `n_seeds_clearing_the_reference: 0`.
* **The ridge is scored on the same rows, by the same scorer.** `compare-rows` is a
  real cell-by-cell check, not an assumption: `row_parity_ridge_vs_melstm_val.json`
  reports `same_rows: true`, `disagreements: []`, 65 basins paired, ridge beating
  the network on **52/65** with median paired difference **+0.17096**. The round-1
  ridge figure re-verifies **bit-identically** (`0.4520685140972679` both sides,
  median paired difference **exactly 0.0** across all 65 basins).

**Refutation attempts that failed to overturn anything**: the 30-epoch gain is not
a scorer artefact (same YAML but two fields, same `naive_baselines.nse` path, same
65 rows); the gate that admits the 30-epoch artifact does so with `n_refusals: 0`
and the new `margin_vs_seed_variance` check actually ran with evidence attached
(margin +0.0928 against stdev 0.0253 — I verified both from the artifacts).

**Two findings the report did not make:**

1. **The holdout ledger under-counts.** Its own module docstring promises *"one line
   per test-split scoring"*. But `reports/train/linear_reference_test.json` exists on
   disk (mtime 2026-08-22 23:55), carries `scored_split: "test"`, scores the ridge on
   the test years at median NSE **0.5168819663634092** — and has **no ledger line**,
   `holdout_read: null`, and no `holdout_reads_before_this_one` key. It is also
   untracked (`/reports/*` is gitignored and this file was never force-added). So the
   `linear-reference` command is a second door onto the test split that the ledger
   does not count, exactly the failure mode the ledger was built to prevent for
   `score`. **This round did not create it and did not touch it** — but it means
   "one read" is the count for the *network*, not for the repo.
2. **E-030 promotes the ridge as model of record on val evidence**, while an
   uncommitted, unledgered test figure for that same ridge (0.5169) sits on disk. The
   right fix is to decide whether `linear-reference --split test` is a holdout read
   (it is), ledger it retroactively with its true date, and commit the artifact — not
   to quote 0.5169 as if it were certified. I have **not** carried 0.5169 into the
   verdict table for that reason.

**What is weaker than it reads, as the agent itself says**: the 30-epoch arm has
n=3 against the n=8 given to the arm being disproved, one of its three curves is
still rising at epoch 29, and it is still a reduced run against `params.yaml`'s
declared 50 production epochs. The eight-member ensemble's own spread is genuinely
unmeasurable from eight seeds, and its mean NSE is **−7.01** against a median of
0.2982 — on `GRDC_5204250` the members score −0.10 to −3903.69 and the ensemble
−468.26. Ensembling dilutes catastrophic failures; it does not fix them.

### chokepoint — is the power analysis honest about absent vs underpowered? Was the target redefinition pre-registered with its own baseline?

**Yes to both, and this is the most methodologically careful artifact in the cycle.**

The analysis does not give one verdict, it gives two, and keeps them apart:

* **For the claim as made — ABSENT, not underpowered.** The effect claimed
  (**+0.0580 mtpd** scale-matched, +0.1046 raw) is *larger than the design's own
  in-sample information ceiling* (**+0.0527 mtpd**), where the ceiling is what an
  oracle gets from knowing each corridor's mean episode depth exactly. Crucially
  this argument is **estimator-free**, which matters because the five SE estimators
  for the same statistic disagree by 5x (naive 0.0156 → jackknife-with-refit 0.0790)
  and a verdict resting on one of them would have been a verdict about the estimator.
  An independent second line agrees: `gbm_depth`'s learning curve has OLS slope
  **−0.00096 mtpd per added corridor** and **0% of subsets positive at full n**.
* **For the residual effect — genuinely UNDERPOWERED, and labelled a hypothesis, not
  a claim.** `ridge_depth_a100` at +0.0152 mtpd has a climbing learning curve
  (0.50 → 1.00 of subsets positive as corridors go 4 → 18) and would need
  **699–11,571 episodes (182–3,019 clusters)** at 80% power against the 98 episodes
  / 28 corridors the allowed source holds. The artifact refuses to permutation-test
  it because it was found by reading the full grid: *"testing the grid leader after
  seeing the grid is selection on the result."*

**T2 pre-registration verified at the commit level.** `9ff4154` adds
`scripts/run_episode_direction_target.py` and **nothing else** — 625 lines, zero
artifacts, zero reports. Its message fixes claimant (`gbc_direction`), reference
(`corridor_scale_only`, the T2 analogue of the magnitude baseline), the `base_rate`
do-nothing floor, 300 draws, seed 20260824, and the decision rule, all before any
T2 number existed. The single registered execution lands two commits later. T2 came
with its own baseline and its own null, and it **failed its own rule** (+0.0159 AUC,
p=0.610). The higher-scoring `logit_l2_C0.1` (0.7242) is reported and explicitly
**untested**, for the same anti-selection reason. `docs/allowlist.yaml` and
`ALLOWLIST_SIGNING.md` are untouched across all four commits (verified by diff).

**One refutation that partially lands.** The verdict string says *"no corridor-level
feature vector can produce an effect that size on this frame at any n."* That is
true as scoped — but the claimant's features are **per-episode** 180-day pre-episode
windows, which are not corridor-constant, and depth's ICC of 0.735 leaves **26.5% of
variance within corridors** that a time-varying feature could in principle reach. So
the oracle ceiling does not strictly bound the actual claimant. The agent names this
in its own assessment ("not a universal impossibility proof… a different feature
vector would have a different ceiling"), and the verdict survives regardless on the
two independent legs — the declining learning curve and the negative point estimate
— but **the "at any n" phrasing is stronger than the ceiling alone supports** and
should be scoped in the artifact, not only in the covering note.

**The finding worth escalating on its own**: E-021's premise was that
Daily_Ports_Data multiplies the corridor universe ~64x. Measured live 2026-08-24 it
is 2,065 ports — but only **180 countries**. The power arithmetic's unit is the
independent *cluster*; if the blocking unit must be the country, the dataset is
below **every** requirement and would buy a bigger panel that still cannot settle
the question. That question costs nothing now and a great deal after ~2.9 GiB is
wired in.

### blackout — did the promotion gate pass or refuse, and was it left unmodified?

**It REFUSED, it was left refusing, and the refusal is the most valuable thing the
round produced.**

* **Unmodified, verified three ways**: `resilient_blackout/mlops/registry.py` has
  mtime **2026-08-13** and its last commit is `fe2a459` (2026-08-13) — it is not in
  this round's diffstat at all. The thresholds in source (`rmse 50.0/25.0`,
  `coverage_90 0.80/0.88`, `calibration_error 0.05`) match the recorded artifact
  exactly, and a new test asserts recorded thresholds equal the declared defaults so
  a future "pass" obtained by moving a threshold fails.
* **The diagnosis is proven by the baseline, not asserted.** The agent ran the gate
  on the *shipped* model too, and both read **identical** mapped metrics
  (`rmse 1233.3712393143185`, `coverage_90 0.667`, `mae 878.2146721314421`) and
  produced an **identical failing set**. Identical figures for two different models
  is the signature of a fall-through: `metrics_for_promotion_gate` maps nothing from
  a classifier payload and falls back to Model A's MW-scale hindcast metrics. The
  gate is comparing **1233.371 megawatts of load-shed hindcast error** against a
  threshold of **50.0** whose unit is undocumented. Declining rather than passing on
  a silently substituted metric is correct behaviour — establishing a baseline before
  claiming a regression is exactly the rule, and it was followed.
* **Nothing was served.** `models/weather_failure_v1.joblib` still has mtime
  2026-08-21; the candidate went to its own path (2026-08-24). `ModelRegistry` holds
  **0 versions** for `weather_failure` — there was nothing for a promotion to move.
* **The test arm was cited, not re-read.** Every test figure I checked comes out of
  the committed `weather_failure_test_read.json` (read at 2026-08-24T07:13:02Z, a
  *prior* commit): selected 0.6776 full / **0.6803** on the persistence subset,
  anchor 0.6412/0.6474, linear ceiling 0.6461, climatology 0.5298, persistence
  **0.6899**. The claimed +0.0364 over the shipped contract is 0.6776 − 0.6412 ✓.

**The judgement call I want to endorse explicitly.** On val the extension genuinely
edges persistence (0.6845 vs 0.6816), so the unmodified `loses_to_persistence` rule
correctly does **not** fire there. Forcing it would have been fabrication; editing
it quiet would have been suppression. The agent did neither: it applied the *same
unmodified rule function* to the committed test figures, where persistence is still
ahead, and recorded the firing under `persistence_context`. An empty val warning
list sitting alone would have read as "nothing is wrong". This is the right call.

**Deviation, disclosed and correct.** The task text described `all_in_scope` as 24
columns; the ladder and the pre-registration define it as **29**, and 29 is what the
single sealed read certified. Serving 24 would have been selecting a configuration
after the fact on a rung with no val number. The agent followed the escalation, said
so in the model card, and recorded that two of the six blocks earn nothing on their
own rungs (0.6486 and 0.6523 against the base's 0.6522) so trimming them is real
future work needing its own ladder. Also corrected honestly: the round-2 "0.7825 vs
0.7820" configuration-B comparison was across **two different row sets**; the
same-rows figure is 0.7825 vs 0.7834 (+0.0009, still inside the 0.01 epsilon, so the
conclusion is unchanged and slightly better supported).

### triage — were all three preconditions met before anything was promoted? Did the converged fit differ? Was the closed arm respected?

**All three met; the fit did not differ materially, so the suspension clause
correctly did not trigger; and the closed arm was respected.**

* **E-029's actual text** (verified at `a50ce65`): *"If the converged fit differs
  **materially** from the scored one on val or LOCO, promotion is suspended and
  returns here for a fresh decision."* The measured deltas are **3.33e-16** on val
  skill and **9.21e-15** on LOCO, against a materiality band of 0.0050 — thirteen
  orders of magnitude inside it. Val RMSE agrees to **15 significant figures**
  (228.1945918020624 vs 228.19459180206232) across a **hundredfold** change in
  iteration budget. Suspension was not owed.
* **The tolerance was never relaxed.** Every rung of the cap ladder (50 → 200 → 1000
  → 5000) carries `tolerance: 1e-09`; only `max_iter` moved. This is the correct
  shape — raising a cap is not loosening a gate.
* **The convergence "failure" was a red herring, and the artifact proves it rather
  than asserting it.** The step trace falls 1.577e-01 → 1.868e-04 → 1.506e-07 →
  3.200e-08 in four iterations and then wanders on the float64 round-off floor at
  ~1e-08 for thousands more. The 1e-9 crossing at iteration 2775 is the walk dipping
  under a tolerance that sits at or below the numerical floor of this design — not
  the fit improving. **Generalisable lesson**: `converged: false` on a
  ridge-penalised IRLS with an ill-conditioned gram is not by itself evidence of an
  unstable fit; the decision-relevant check is whether the scored metric moves when
  the budget changes.
* **Closed arm respected.** Both new artifacts carry `test_arm_read: false`, a split
  guard refuses any non-train/non-val row, and `serve_weekly_mortality.py` refuses
  `--arm test` outright. Every test figure is read from the committed
  `dlnm_fit_family_test_read.json` and the champion records `reads_of_this_arm: 2`
  and `arm_status: CLOSED` in the artifact itself.
* **I verified the self-hash myself.** `champion.json` minus its `artifact_sha256`
  field, serialised canonically (`sort_keys=True`, compact separators), hashes to
  **`ec8bd643dc433bd5798bc531f8d4cd19b8abe48aa51fa6b94bc0a201e1e2ad56`** — exactly
  the claimed value. A tampered or unhashed artifact is refused on load.
* **Cross-path parity is the strongest check here**: the serving path builds features
  with `core.dlnm.build_cross_basis` while the benchmark used a row-wise-Kronecker
  einsum, and the served val RMSE reproduces the measured one at **absolute
  difference 0.0** over 22,244 rows. A serving path that re-implemented the fitting
  path would have made this vacuous.

**Two things recorded honestly that a less careful run would have smoothed**: only
**5 of 16** LOCO folds met 1e-9 at the converged cap (pooled skill still reproduces
to 9.21e-15, same floor, same reason) — the raw fact is in the artifact next to the
judgement, so a reader can disagree. And the single test read **scored the
50-iteration fit, not the converged one**; the converged fit's equivalence to the
tested model rests on val and LOCO alone. That is inference, not a test measurement,
and `fitted_at_the_50_iteration_cap_note` says so in the artifact.

**One weakness in the pre-registration, worth naming.** E-029 said "materially"
without a number; the ±0.0050 band was chosen by the agent and landed in the **same
commit** as the result. The script asserts its docstring literals against the
committed selection artifact, which is a good self-check but is not temporal proof —
unlike chokepoint's `9ff4154`, which pre-registered in a commit that executed
nothing. Here it is not load-bearing: at deltas of 1e-16 *any* sane band gives the
same verdict. But the pattern to copy across the fleet is chokepoint's.

## Who serves a predictor that beats or IS its operational baseline — stated plainly

**Beats its baseline with a real model, and it is promoted and served (3):**

* **resilient-triage** — *new this round.* `cbdiff_pois` is served behind
  `/v1/weekly-mortality/*`; previous-week persistence is demoted from served
  predictor to **recorded bar**, enforced by a challenger gate that FAILs on an
  absent comparison and returns **NA, never PASS**, on an unmeasured one. Skill
  **+0.0546** on the closed test read, **+0.0412** on val (optimistic by
  construction, and the artifact says so).
* **resilient-arabica** — 11-feature history ridge, +2.6% RMSE over the expanding
  prior mean.
* **resilient-fray** — both track records, 25–37% MAE over the persistence floor,
  hash-pinned and bar-enforced in code.

**Serves a predictor that beats the admissible bar, but it is a *learned reference*,
not the neural model (1):**

* **resilient-torrent** — the **ridge** is the model of record (E-030): val median
  basin NSE **0.4521** vs the admissible `persistence_lag3` **0.26484**, beating it
  on 44/65 basins, on rows verified identical. The ME-LSTM loses to it on 52/65 even
  after the 30-epoch fix closed half the gap. Two caveats that must travel with this:
  the ridge's mean NSE is **−2.95** against the network's −0.099 — the median win
  carries a tail; and `persistence_lag1` scores **0.7173**, above everything, but is
  **not computable at issue time at lead 3**, so it is correctly recorded as the
  autocorrelation ceiling and not as a bar. That non-blocking note is the right
  treatment, not a dodge.

**IS the baseline, honestly promoted as the product (2):**

* **resilient-surge** — `per_lead_anchor_ols` in the registry production slot.
* **resilient-choco** — lag-1 persistence as the served predictor of record.

**Serves a predictor that does NOT beat its reference (2):**

* **resilient-blackout** — the shipped 13-column planning model scores **0.6474** on
  the test persistence subset against persistence's **0.6899**; the authorised
  29-column extension reaches **0.6803** and still loses by 0.0096. **The promotion
  gate refused both**, identically, and was left refusing. Nothing changed about what
  ships. The persistence comparison is flagged not-like-for-like (it needs the
  day-t−1 outage feed E-021 reserves), which is a real caveat — but it is a caveat
  that argues for a *scope decision*, not for reading the model as ahead.
* **resilient-chokepoint** — the operational `scale_x_train_mean_depth` is the served
  predictor and the challenger measures **−0.0398 mtpd** against it. As of this round
  the claim is not merely unestablished but excluded: it sits **above the design's
  own information ceiling**.

## Discipline verdict, round three

**No test read was spent this round, in any of the four repos.** Torrent had two
candidates clear the bar on val and declined both prepared reads. Triage, blackout
and chokepoint cited committed artifacts as files. That is four opportunities to
re-read a closed arm, declined four times, on a day when three of the four answers
were favourable — the rule binding when it costs something is the only evidence that
it binds at all.

**No gate was edited, loosened, widened or narrowed.** One gate refused an agent's
own artifact and was left refusing (blackout), with the refusal diagnosed by running
the gate on the shipped baseline rather than by arguing with it. One gate was
*strengthened* (torrent's new `margin_vs_seed_variance`, whose threshold is the
configuration's own measured seed stdev rather than a tuned constant, and which
emits a non-blocking note when no sample exists so "nobody sized the variance"
cannot render as "the variance is small"). One tolerance that arguably sits below
its design's numerical floor was **left alone** rather than relaxed (triage), with
the appropriate-tolerance question escalated to the signatory.

**Three agents retracted or corrected their own claims in-tree.** Torrent retracted
an interval note that was true at n=3 and false at n=8, and a whole-suite figure it
had committed as measured but taken under pytest-process contention — replacing it
with three clean sequential runs and a written account of how the bad ones happened.
Blackout corrected a round-2 comparison that had been made across two different row
sets. Chokepoint corrected E-021's "~1,800 ports / ~64x" to a measured 2,065 / 73.8x
and then showed why the port count is the wrong denominator anyway. **Superseded
claims were marked in place rather than deleted** (torrent's E-027 point 4), which is
the behaviour that makes the record trustworthy over time.

**Zero fabricated numbers.** Every figure I checked — and I checked the load-bearing
ones in all four repos, recomputing several from raw per-unit tables — reproduced
from a committed artifact.

## Open follow-ups after round three

1. **Orchestration bug (fleet).** Two of four agents were handed an isolated
   worktree of **resilient-arabica** for work targeting chokepoint and triage. Both
   detected it and worked in the correct repo. Fix the harness before a less careful
   run commits cross-repo.
2. **torrent — ledger completeness.** `linear-reference --split test` writes no
   ledger line and no `holdout_reads_before_this_one`. Route it through the same
   ledger as `score`, retro-record the 2026-08-22 ridge read at its true date, and
   commit `linear_reference_test.json` (currently untracked under a `/reports/*`
   gitignore). Until then "one read" describes the network only.
3. **torrent — the 30-epoch arm needs the n=8 treatment** it gave the arm it was
   disproving, and one of its three curves is still rising at epoch 29. Also still
   open: the finetune path selects on pooled `val/nse_mean` and stays gate-refused
   (deliberately left, correctly, as unverifiable without a full finetune run);
   E-025's gauged/ungauged claim decision; E-024's 30-of-70 test denominator.
4. **chokepoint — scope the ceiling claim.** Carry the "corridor-level features"
   qualifier from the covering note into the verdict string itself. Then answer the
   blocking E-021 question **before** any ingest: is the blocking unit the port
   (2,065) or the country (**180**)? At country, the dataset is below every
   requirement. Note also there is **no capacity column** — the port analogue is
   import+export tonnage, a different physical quantity needing its own
   pre-registration, not an ingest rename.
5. **blackout — E-022 is now the blocking item**, and it is a signatory decision, not
   an engineering one: a declared classifier Stage-1/2 contract with a real decision
   threshold, a ruling on which reference it is set against (climatology, not
   persistence), and Model B being registered at all. Until then no classifier in
   this repo can pass a gate built for a regression/interval contract, and two of the
   fallback hindcast metrics are marked `"status": "stale"` by their own provenance.
6. **triage — copy chokepoint's pre-registration shape.** Put the materiality band in
   a commit that executes nothing. Separately: the 1e-9 IRLS tolerance sits at or
   below this design's round-off floor — the right response if a future fit misses it
   is a signatory ruling on an appropriate tolerance for the conditioning, not a
   raised cap and not a quietly relaxed `tol`. Environment gaps (`httpx`, `slowapi`,
   `mlflow`, `celery`, `optuna` absent) leave the HTTP wire format and the
   `api/app.py` mount verified by inspection only.
7. **Carried forward, unchanged**: arabica's run-B GRU weights still live only in a
   stale worktree; surge's route-level integration (E-040); choco's FAOSTAT serving
   posture (E-045); fray's DVC stage for the extension checkpoint.

---

# Machine-read reconciliation (2026-08-28, round six)


Everything above this line is the hand-written adjudication and is unchanged.
This section is appended, not substituted: the judgement column above is a
judgement and cannot be regenerated. The measured columns can be, and now are.

`mlkit portfolio` reads each repo's committed artifacts through a declared
adapter (`src/resilient_mlkit/fleet_adapters.py`) and writes
[`portfolio/FLEET_VERDICTS.md`](FLEET_VERDICTS.md) with its `.json` twin. Every
figure there carries the artifact path, its sha256, and whether git has those
bytes at HEAD.

- generated: `2026-08-28T20:54:40+00:00`, run nonce `mlkit-20260828T205434Z-e5ab199ea393`
- mlkit `0.2.0` at `44e7c64ac4d3fd75a0a026aaffed624911ce8e2d`
- 12 rows over 8 repos; **99** cells
  measured, **9** NA-with-reason, **0** fabricated

## Does the machine agree with the hand transcription?

**No longer — and catching that is the entire reason this command exists.**

Measured 2026-08-29 against `portfolio/FLEET_VERDICTS.json` as regenerated at
mlkit `036683e`. Of the **23** numeric figures the generated table carries,
**21** are found in the prose above and **2** are not:

| figure | machine reads | prose says | verdict |
|---|---|---|---|
| `fray/forecast_available` score | `74.16097783177521` | `82.754` | **CONTRADICTED** |
| `chokepoint/direction-head` baseline score | `0.3482142857142857` | — | omitted, not contradicted |

The second was already known and is listed as "not quoted above" in the table
below. The first is new, and it is a real divergence rather than a rounding.

**What happened.** resilient-fray moved its `forecast_available` model of record
to the verified weather-covariate winner (fray `87a1dbe`, *"SERVE-3/PROMOTE: the
verified weather winner gets a checkpoint, so it can be served"*). The record now
reads:

- candidate `forecast_available+nbr+wx_prior/hgb/leaves=127/lr=0.05/iter=400`
- TEST MAE `74.16097783177521`, against the same `persistence_t_minus_1` floor
  of `113.06701205090663`

The prose above still describes the superseded
`forecast_available+nbr/k=15/hgb/leaves=63/lr=0.1/iter=300` at `82.754`. Nothing
in mlkit was edited to follow it: the adapter declares a pointer, the pointer
resolved against the new bytes, and the figure changed by itself. A hand-copied
table would have gone on reporting `82.754` indefinitely, and every re-read of it
would have confirmed the wrong number.

**Provenance caveat, stated rather than buried.** `mlkit portfolio` reads the
working tree. At the time of this run fray's
`reports/validation/models_of_record.json` was DIRTY, and the generated table
records that in its `dirty` column. The figure itself is *not* affected: checked
directly, `tracks.forecast_available.test.mae_lb_ac` is
`74.16097783177521` in fray's `HEAD` and in its working tree alike. The
uncommitted part of that file is the checkpoint block — `path`, `sha256` and an
`identity_check` for the newly serialised `.joblib` — which is fray's in-flight
promote work and no part of any figure quoted here.

**Two things are owed and neither was done here.**

1. The adjudication in the summary table at the top of this file — including
   *"I re-hashed both checkpoints on disk myself (match)"* — was performed
   against the **superseded** winner. It does not transfer. This file is not
   rewritten to pretend it does: re-adjudicating fray's new record means
   verifying fray's own promote artifact and its checkpoint hash, which is a
   judgement, and judgement is not a field lookup.
2. Raised as **E-M06** in `docs/ESCALATIONS.md`.

Everything below this line still stands: on the other 21 figures the hand
transcription was arithmetically correct.

| figure | measured, full precision | appears above as |
|---|---|---|
| `choco/—` score | `2.689773` | `2.6898` |
| `choco/—` baseline score | `0.227719` | `0.227719` |
| `arabica/—` score | `1.05676` | `1.05676` |
| `arabica/—` baseline score | `1.084686` | `1.084686` |
| `torrent/melstm-10ep-n8-val` score | `0.2225867683526302` | `0.2226` |
| `torrent/melstm-10ep-n8-val` baseline score | `0.26484161185831745` | `0.26484` |
| `torrent/ridge-vs-melstm-val` score | `0.23206894549246004` | `0.23207` |
| `torrent/ridge-vs-melstm-val` baseline score | `0.4520685140972679` | `0.45206851` |
| `chokepoint/level-head` score | `0.2594909570948433` | `0.2595` |
| `chokepoint/direction-head` score | `0.6984126984126984` | `0.6984` |
| `surge/—` score | `0.175095` | `0.175095` |
| `surge/—` baseline score | `0.163736` | `0.163736` |
| `triage/—` score | `173.40814487545612` | `173.40814` |
| `triage/—` baseline score | `183.42262422319413` | `183.42262` |
| `blackout/vs-planning-anchor` score | `0.6776159815675701` | `0.67762` |
| `blackout/vs-planning-anchor` baseline score | `0.6411684390728368` | `0.64117` |
| `blackout/vs-persistence` score | `0.6802774287447294` | `0.68028` |
| `blackout/vs-persistence` baseline score | `0.689877078726717` | `0.68988` |
| `fray/spatial_infill` score | `71.35922343344701` | `71.359` |
| `fray/spatial_infill` baseline score | `113.06701205090663` | `113.067` |
| `fray/forecast_available` score | `74.16097783177521` | `82.754` — **CONTRADICTED**, see above |
| `fray/forecast_available` baseline score | `113.06701205090663` | `113.067` |
| `chokepoint/direction-head` baseline score | `0.3482142857142857` | not quoted above |

## What the hand-written table could not show

The arithmetic was right. Provenance is where the transcribed table was blind,
because a retyped figure carries no record of where it came from:

1. **choco's candidate figure is not in git.**
   `models/observed_production_head.meta.json` — the artifact carrying the retired
   climate head's same-rows test RMSE — is gitignored (`.gitignore:82`, `/models/*`)
   and has never been committed on any branch. The number above is correct about a
   file on one machine and cannot be reproduced from the repository by anyone else.
   The served predictor's sidecar, by contrast, IS committed.

2. **surge's registry is on a branch surge does not have checked out.**
   `data/model_registry/`, `per_lead_anchor_ols/model.json` and
   `reports/holdout_reads.jsonl` resolve only in the linked worktree
   `.worktrees/pr55`, on `feat/surgeistm-lora-finetune`. The figures are real and
   they are evidence about that worktree.

3. **torrent and blackout have no committed artifact declaring a model of record.**
   Both are named as such in prose (ESCALATIONS, CHANGELOG, decision docs) and
   nowhere that a reader — or a gate — can resolve as a field. The other six repos
   have one; these two are the exception, and the generated table reports NA with
   that reason rather than repeating the prose.

4. **blackout's two comparisons are on different row sets, and the table above
   places them side by side.** The model scores 0.6776 on all 101,424 test rows;
   persistence scores 0.689877 on the 89,774 it can score at all. The like-for-like
   figure is the model's 0.680277 on that same subset, which is where the −0.0096
   the text quotes actually comes from. The generated table keeps them as two rows
   so the frames cannot be read across.

Regenerate with:

```
mlkit portfolio --out portfolio/FLEET_VERDICTS.md
```
