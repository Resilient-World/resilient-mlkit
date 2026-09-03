# SOTA PLAN v2 — fray, chokepoint, torrent: from where they are to genuinely state of the art

**Written 2026-09-03, ~23:30Z, for the signatory.** This is a decision document, not an agent
to-do list. Every number in it is either (i) an `mlkit`- or trainer-emitted figure read from a
committed artifact or a PR record, with the path or PR beside it, (ii) an external figure with a
resolvable URL and a retrieval date, or (iii) an arithmetic bound derived from (i) and labelled as
a bound. Where a number does not exist it says **NA** and why. Nothing here was fitted, no gate
was touched, no ledgered read was prepared or spent.

The three per-repo reviews this plan builds on are
`loop/sota-reviews/{fray,chokepoint,torrent}.md` (all 2026-09-03). Where this plan disagrees with a
review or with a standing fleet finding it says so and by how much (§3).

---

## 0. Verification stamp — re-measured tonight, not recalled

| item | measured 2026-09-03 ~23:25Z | how |
|---|---|---|
| main heads | fray `b1800121` · chokepoint `b8344376` · torrent `8964c42b` · mlkit `3bf16dd0` | `git ls-remote` |
| open PRs | fray **#93** (E-057 prereg, MERGEABLE), **#94** (repin, CONFLICTING), **#95** (tonight's review, docs only) · chokepoint **#119** (run NOT COMPLETED, now **CONFLICTING** against post-#120 main) · torrent **#174** (E1 interval), **#175** (D2 refit, MERGEABLE, blocked on its own deviation (a)), **#176** (repin, CONFLICTING) · mlkit none | `gh pr list` |
| CI on main | fray, chokepoint, torrent: **every workflow red except fray License Boundary**; mlkit green. Cause unchanged: `MLKIT_READ_TOKEN` not minted | `gh run list` |
| hard-stop arming, from each repo's own `.mlkit/repo.toml` on main | **fray**: `placebo_test` (l.129) and `scaling_probe` (l.164) both declared · **chokepoint**: both declared (l.74, l.107) plus `[placebo] null_value = 0.0, indicts = "above"` (l.180–183) · **torrent**: **NEITHER**; only `coverage` (l.126) and `[coverage] nominal = 0.90` (l.148–149) | `gh api …/contents/.mlkit/repo.toml?ref=main` |
| mlkit pins | fray `c65b2e7` (0.5.0) · chokepoint `9d4e8780` (0.6.0) · torrent `3df724d5` | `pyproject.toml` on main |
| the in-flight chokepoint fine-tune | PID 16223, `run_foundation_finetune.py --stage val --fit-device mps`, launched 22:51:14Z on tree `b834437` == main, first log line `[hard-stops] {"D2": "ARMED/PASS", "E1": "ARMED/PASS"}`, C1 78/78, licence `sha256:ddcda3c7508b`. Alive at 34m35s (state UN, low CPU — consistent with GPU-bound work); `models/foundation_finetune/chronos2-ft-lr1e-6/` exists and is **empty**; no artifact written. **Outcome unknown.** It crosses the 60-minute mark at 23:51Z. | `ps`, `ls`, log tail |
| pinned chronos-2 inference API | `predict_df` documents `target` ("Column(s) with time series values to predict"), `future_df` ("future values of covariates"), `id_column` ("Column identifying different time series"); the capability table lists multivariate forecasting, cross-learning across items, past-only covariates, known future covariates, max context 8192. Licence Apache-2.0. — https://huggingface.co/amazon/chronos-2/raw/29ec3766d36d6f73f0696f85560a422f50e8498c/README.md, retrieved 2026-09-03 | WebFetch |

Two corrections to the brief I was handed: fray now has **three** open PRs, not two; chokepoint
#119 is CONFLICTING, not UNKNOWN. Everything else in the brief's measured block re-verified.

---

## 1. The honest position — where each model actually is, against what bar

Read this section before anything else. The fleet's summaries have repeatedly quoted the best
number in each repo as if it were the served number, and the served number as if it had been
measured on the product's question. Neither is true anywhere.

### 1.1 fray — county cotton yield, avoided-loss trigger

**Model of record on the question the product asks (an unseen crop year): NULL.** Nothing has ever
been fitted and promoted on the unseen-year split. The bar on that split is a persistence floor:
`persistence_t_minus_1` VAL MAE 151.741 / RMSE 195.063 (2016–2020, 1,365 rows), TEST MAE 141.720 /
RMSE 189.689 (2021–2025, **1,270 rows, HELD**) (`reports/validation/unseen_year_floors.json`).

The training of record (2026-09-02, `unseen_year_track_fit.val.json`, code `dac1b215`) selected
`forecast_available/hgb/leaves=31/lr=0.1/iter=200` — 26 features, **no weather of any kind** —
at VAL MAE 128.930, skill **+22.811 lb/ac** over the floor, and it is **NOT PROMOTABLE**: the
crop-year-block bootstrap (the declared dependence unit) gives **[−1.289, +41.704]**, which covers
zero; over 200 bootstrap seeds only 9/200 clear zero; one VAL year (2016, −21.768) opens the
interval. The 45-origin rolling backtest inside TRAIN (may not promote by prereg) puts the effect
at mean **+16.570**, year-block bootstrap **[11.123, 21.932]**, 6/45 origins negative. So the
best honest sentence about fray's forecast skill is: *roughly +16 lb/ac over persistence, real-
looking, not decidable on five VAL years.*

What **is** a hardened record is the **spatial** track (fill in an unobserved county in an observed
year): `spatial_infill` hgb TEST MAE 71.359 vs floor 113.067; served `forecast_available+nbr+wx_prior`
TEST MAE 74.161 (`models_of_record.json`). But the served champion, scored on the unseen-year VAL
frame, is **137.718 (skill +14.023) — 8.79 lb/ac worse than the no-weather base**, 13th of 20
weather candidates (`unseen_year_track_fit.val.json`, `val_table`). The API additionally defaults
to `yield_backend="mechanistic"` (`src/api/config.py:70`, E-038b OPEN), the one backend with **no**
measured out-of-sample skill (`hindcast_open_data.json`: `status: incomplete`, 0 events scored).
**The most-validated model is served neither by default nor for the question it is asked.**

The avoided-loss layer: trigger vs RMA indemnities on 122 county-years (2019–2020) gives Youden
**J = 0.1206, county-block CI [−0.0584, +0.3013] — covers zero**, and that was scored on the
*optimistic* spatial track (`avoided_loss_basis_risk.statement.md`). No interval of any kind has
been measured on an unseen crop year; the spatial conformal at α=0.2 **FAILS** for the served
track (0.7738 vs 0.80, `county_yield_conformal.json`).

Hard stops: **both armed and PASS on main**, re-driven today by the review to the digit — D2
−0.945 [−4.239, +2.441] (this is the forward-year gridMET *wiring* placebo, not a placebo on the
selected model); E1 curve {0.01: −22.571, 0.10: +7.050, 0.25: +12.631}, gain 79.18%.

### 1.2 chokepoint — daily transit flow through 28 maritime chokepoints

**Served at h=7: `hgb_d3`**, a depth-3, 200-iteration gradient-boosted tree on 18 features
predicting the log departure from a trailing mean, promoted on the ONE h=7 test read
(2026-08-28): TEST MAE 0.196464 vs `trailing_mean_h` 0.229360, skill **+0.143424, corridor-block
CI [0.107288, 0.177464]**, 14,756 rows / 28 corridors (`daily_flow_test.json`). That is a real,
modest, hardened product. **Served at h=14: the trailing 14-day mean** — a floor.

**Best on VAL, never served: zero-shot `amazon/chronos-2` @ `29ec3766`, zero fitted parameters**,
selected at every ladder horizon (`foundation_full_val_ladder.json`, regenerated 2026-09-03,
six horizons bit-identical to the 2026-09-01 original):

| h | chronos-2 skill vs trailing mean | corridor-block 95% CI | clears? |
|---:|---:|---|---|
| 1 | +0.249652 | [+0.234665, +0.265818] | yes |
| 3 | +0.231012 | [+0.208843, +0.251132] | yes |
| 7 | +0.175749 | [+0.147470, +0.202902] | yes (hgb_d3 on VAL: +0.137636) |
| 14 | +0.097421 | [+0.047399, +0.146755] | yes (no fitted candidate clears) |
| 21 | +0.061411 | [−0.003712, +0.126471] | **no** |
| 28 | +0.067684 | [−0.015547, +0.146086] | **no** |

The gap between "served" and "best" is not engineering: it is **E-022 (2026-08-28) / E-048
(2026-09-01)**, a signatory decision on spending the held h=14 read (or re-blocking), unanswered
for six days. The served uncertainty is the operator-facing defect: marginal coverage holds
(0.8090 / 0.9001 / 0.9495 at 0.80 / 0.90 / 0.95) while **10 / 10 / 9 of 28 corridors are below
nominal**, worst 0.2721 at α=0.2 (`daily_flow_conformal_val.md`).

The fine-tune: **nothing has ever been fitted on this track.** Two cpu attempts died at the
60-minute harness ceiling inside the first fit; one was killed on instruction; the mps attempt is
live now (§0). Its 200-step probe — the E1 that armed it — measures the fine-tune **below
zero-shot at every rung** (25% +0.171380 vs zero-shot +0.175749; 10% +0.159345; 1% +0.036690,
`e1_chronos2_scaling_ladder.json`), like-for-like (h=7, 11,704 rows, same bar 0.21695570743823606).

Hard stops: **both armed and PASS on main** — D2 −0.0034459 [−0.0047494, −0.0023532] under
`indicts = "above"`; E1 gain 0.07553. Both caveats in §3.

### 1.3 torrent — 3-day-lead daily streamflow

**Model of record: a closed-form ridge** (alpha 1.0, 60 hand-built lag features of ERA5-Land
forcing **plus the basin's own observed discharge**, one global target centring), a *de-facto*
record (`models/hydrology_ridge/model.json` says in its own text that promotion is reserved to
the signatory; E-030 unsigned). VAL median per-basin NSE **0.4520685140972679** over 65 scored
basins vs the admissible bar `persistence_lag3` 0.26484; wins 44/65, median paired **+0.27464**
— **a point estimate; no basin-block interval on that margin exists anywhere on main.** TEST was
read once (2026-08-23, **30 of 70 basins** — 38 test basins publish no streamflow in 2016–2020,
E-024): 0.5169 vs 0.2486.

The median hides the tail: VAL **mean NSE −2.949**, minimum on the full fit **−202.1**, fraction
positive 0.831; served conformal at nominal 0.90 covers **0.858381 with 18 of 34 basins below**
(`hydrology_ridge_conformal_val.md`); D3 is wired and honestly reports this.

Two facts that bound every torrent number: every forecast-branch input is the ERA5-Land
**reanalysis of the days being forecast** — "a perfect-forecast assumption and always was"
(`docs/HYDROLOGY_CLAIM.md` §4) — and the **product claim is undecided** (E-025, gauged vs
ungauged, open since 2026-08-22). On the ungauged information set nothing beats a constant:
forcing-only ridge VAL 0.0448, TEST −0.1498 (below `doy_climatology` 0.1476); forcing-only ME-LSTM
−0.3190.

**Hard stops: BOTH NA ON MAIN.** `.mlkit/repo.toml` declares neither `placebo_test` nor
`scaling_probe` (re-read tonight). The only E1 measurement is a hand-run script on unmerged
#174 (gain **−12.867%** vs the +1.0% bar — CLAUDE.md's second hard stop, *as the fleet is
treating it*; its basin-block interval **[−21.64%, +2.51%] contains the bar**, and the 1% rung is
two basins). The only D2 that ever existed on a branch was proved inert (symmetric about zero by
construction; fires 0.0400 under a total leak); its replacement (#175) fires 1.000 under a total
leak and is held on a design choice justified by a number that exists only in prose.
**No torrent result produced today can be trusted as a training result, and no torrent fit may
start until this changes (§7.3).**

### 1.4 In one table

| repo | served | best measured | bar on the product question | interval on the deciding unit | stops on main |
|---|---|---|---|---|---|
| fray | spatial champion (wrong track) / mechanistic default (no OOS skill) | no-weather hgb, +22.811 VAL, +16.6 on 45 origins | persistence floor; **model_of_record NULL** | covers zero (5 crop years) | D2 ✓ E1 ✓ |
| chokepoint | hgb_d3 h=7 (+0.143 test); trailing mean h=14 | zero-shot chronos-2, all horizons | trailing_mean_h | clears at h≤14, covers zero at h=21/28 (28 corridors) | D2 ✓ E1 ✓ (marginal) |
| torrent | ridge with observed discharge (unsigned) | same | persistence_lag3 | **never computed** | **D2 NA, E1 NA** |

---

## 2. What "state of the art" can mean here — and what it cannot

Avoided-loss forecasting on these panels is not a leaderboard task. There is no external figure
for any of the three that can be quoted as "the number to beat" on the same panel, unit and split.
Below, the honest external situation per repo, then the operational definition the plan uses.

### 2.1 External comparators (URL + retrieval date, or NA with the reason)

**fray.**
- CY-Bench (Kallenberg et al., ESSD 18, 3997, 2026 — https://essd.copernicus.org/articles/18/3997/2026/, retrieved 2026-09-03) covers maize and wheat only; **cotton absent; no U.S. county level. NA.**
- USDA NASS *Crop Production*, Aug 12 2025 (https://esmis.nal.usda.gov/usda-esmis/files/tm70mv177/6m313n48h/bk12b9684/crop0825.pdf, retrieved 2026-09-03), table "Reliability of August 1 Crop Production Forecasts": **upland cotton RMSE 9.7%, 90% CI 16.7%** — a *national production* forecast (yield × area, August-1 cutoff, twenty-year basis). The only operational, citable U.S. cotton forecast baseline. **Not a county yield RMSE and must not be quoted as one.**
- NASS sampling CVs for upland cotton yield (https://www.nass.usda.gov/Publications/Methodology_and_Data_Quality/Crop_Production/02_2026/cranqm26.pdf, retrieved 2026-09-03): U.S. 2.3% (2024), 5.3% (2025); states 1.4–14.0% (2025). A label-noise floor, not a baseline.
- Mitra et al., arXiv:2312.02299 (retrieved 2026-09-03): field-scale, simulated rows, no LOYO. **Not comparable.**

**chokepoint.** No published benchmark of chokepoint transit-flow forecasting is cited anywhere in the repo with a URL, and rule 3 forbids reconstructing one. **NA.** What is citable is that the VAL-best predictor is an unmodified current-generation open-weights series foundation model (chronos-2, Apache-2.0, README above; technical report https://arxiv.org/abs/2510.15821, retrieved 2026-09-01 per `docs/foundation_corpus_provenance.md`), with `google/timesfm-2.5-200m-pytorch` second at every horizon. No figure from either model card is a figure about this panel.

**torrent.** Undefined until E-025 is decided. If gauged: Kratzert et al. 2019, HESS 23:5089 (https://hess.copernicus.org/articles/23/5089/2019/, retrieved 2026-09-03) — 531 CAMELS-US basins, EA-LSTM ensemble **median NSE 0.74**, regional VIC 0.31, mHM 0.53 — a *simulation* with no lead time and no gauge input, so it bounds the forcing-only information set (where torrent scores 0.0448). **Not the same task.** If ungauged: Nearing et al. 2024, Nature 627:559 (https://pmc.ncbi.nlm.nih.gov/articles/PMC10954541/, retrieved 2026-09-03) — 5,680 gauges, event-based scoring vs GloFAS v4; per-gauge NSE/KGE in an Extended Data figure, **NA as a number**. Architecture family: Liu et al. 2025, HESS 29:6811 (https://hess.copernicus.org/articles/29/6811/2025/, retrieved 2026-09-03), LSTM median KGE 0.75 on 3,434 basins, beating the best transformer by 0.11 — a family-level statement only. Dataset scale: Caravan v1.6 (https://zenodo.org/api/records/15529786, CC-BY-4.0, retrieved 2026-09-03); the staged tree is 352 gauges.

### 2.2 The operational definition this plan uses

A model here is "state of the art" when, **and only when**, all of the following hold on the
product's own question:

1. **Decidable superiority** over the operational alternative (the persistence/trailing/climatology
   floor a buyer would otherwise use), with a bootstrap interval **on the declared dependence
   unit** that clears zero, on a frame powered to see an effect of the size the record shows.
2. **An interval whose coverage holds per block** (per crop year, per corridor, per basin), not
   just pooled — because the product sells the interval, not the point.
3. **Trustworthy production**: hard stops armed on the tree that fitted, D6 declaring the unit as a
   machine check, every operand tied, the test read spent once on the final candidate.
4. **Legibility**: at least one instrument a domain reader outside the fleet would recognise
   (fray: a production-weighted August-1 RMSE% beside NASS's 9.7%; chokepoint: corridor-conditional
   coverage; torrent: forecast forcing, not reanalysis), reported and NA-honest.

Against that definition, today: fray meets none (1 undecidable, 2 no interval on the track, 3 D6
absent, 4 absent); chokepoint meets 1 at h≤14 on VAL only and none of the rest; torrent meets none
and cannot be scored on 1 until E-025.

---

## 3. Three kinds of work, and the standing findings engaged

The fleet keeps conflating three things. Every item in §4–§6 is tagged with one:

- **(a) makes the model better** — a new covariate, a new learner, more steps, a new target.
- **(b) makes an improvement measurable** — the deciding frame, the estimand, the dependence
  unit, the promotion rule, the interval. On this fleet (b) has been the binding constraint in all
  three repos while effort went to (a).
- **(c) makes a result trustworthy** — arming, ties, controls, provenance, CI, the ledger.

### 3.1 The eight standing findings — where I build on them, where they are wrong

1. **"The binding constraint in two of three repos is the deciding frame, not the learner."**
   Right in conclusion for all three; wrong in mechanism for two, and over-broad for one.
   - fray: right as stated — five crop years cannot resolve +16 lb/ac (K=15 at 80% on the
     headline operands, PR #93). But "not covariates" is over-broad: covariates are provably not
     the route to *clearing zero on five years* and are the only measured route to *more skill*
     (gridMET water block +7.080 [2.517, 11.506] on 45 origins). The correct sentence is **"not
     covariates until the frame can see them."**
   - chokepoint: the h=21/28 closure is **not** "too few blocks" — 28 corridors *is* the PortWatch
     universe and there is no 29th. It is between-corridor heterogeneity on a pooled,
     large-corridor-weighted estimand (`daily_flow.py:439–490`). The only lever is a **rule
     change** (a different estimand), which is a signatory prereg decision, not data, covariates
     or steps. The practical consequence is identical: do not spend compute on h=21/28.
   - torrent: the frame that binds *first* is the **claim** frame (E-025), second the **target**
     frame (§3.1.3), and only third the 65-basin frame — which has been shown to bind the
     E1 ±10% question and the ridge-vs-LSTM question, and has **never been tested** on the
     ridge-vs-persistence question because that interval was never computed.
2. **"Chokepoint's fine-tune is expected to show no improvement."** Agree, well-evidenced. Add:
   even a positive verdict inherits E1's 5.45% and a D2 that never touched this learner (§3.2),
   and cannot reach the product without the E-022 read. Its ceiling on *served* skill is zero
   until a read is authorised.
3. **"Torrent has no trainable shape that is both runnable and not already refuted … a single
   global ridge does not transfer — a model-class finding."** The numbers are right; **the label is
   premature and the cheaper diagnosis was skipped.** E-027 already measured that the target is
   standardised by *one global mean* while mean specific discharge spans 80× across training
   basins; a mean collapse with a flat fraction-below-zero is the signature of a *target-scale*
   defect, not of an estimator that cannot hold heterogeneous catchments. The closed-form remedy
   (per-basin train-period standardisation or `log1p`, still a ridge, seconds) has never been
   tried. And "refuted" overstates the LSTM: the 30-epoch arm is behind on the *seed* unit (n=3);
   C1/C2/C3 are **unrun** (killed twice, E-033), not refuted. Say "unrun and behind on the wrong
   unit." It remains true that none of them is worth compute *before* the free diagnostic.
4. **"E1's pass on chokepoint is marginal."** Agree, and it is worse: mlkit judges the point
   estimate only (`economics.py:187–275`); the interval never enters the verdict; three replicates
   per rung against D2's 64; refits resampled → [−0.417%, +26.586%], P(flat) = 5.45%; and the
   rung axis (more windows) is orthogonal to the constraint that closes h=21/28.
5. **"D6 is NA on chokepoint."** Agree, and adoption is not a formality: `mlkit_bindings:splits`
   returns the corridor-blocked 20/4/4 partition while the served product, the ladder, D2, E1 and
   the fine-tune prereg all use the time-blocked all-28 `SPLIT_BOUNDS`. **R3/R5 PASS is measured
   on a split the product does not use.** D6 would refuse by name; that is the reason to do it.
   The same is true of fray (D6 absent from its pin; the crop-year unit lives in a script) and
   torrent (promotion rule `model_of_record.decide` adjudicates on **seed** stdev).
6. **"CLAUDE.md's literal D2 hard stop reads as fired on chokepoint."** Agree — and **it reads as
   fired on fray too.** fray's own target-shuffle placebo arm has CI [−87.515, −33.242]
   (excludes zero) and does not halt because `scripts/train_unseen_year_track.py:1648` declares the
   region one-sided. chokepoint's exemption is a declared `[placebo]` table; fray's is a line in a
   script because its pinned mlkit cannot express `HaltRegion`. Both are preregistered, argued
   from the estimand's arithmetic, and load-bearing (chokepoint control D proves it). Neither is a
   loosened gate. **Both belong in front of the signatory together (§6, S-5).**
7. **"CI is red on main in all three model repos."** Confirmed tonight. Unblocked only by the token.
8. **"fray and torrent still pin an mlkit without HaltRegion or the polarity contract."** Confirmed
   (c65b2e7, 3df724d5). Add the consequence the fleet measured on 2026-09-02: on those pins
   `core/served.py skill()` is polarity-blind — `skill(0.10, 0.90)` returns **+0.8889 and promotes**.
   Tonight's numbers are not corrupted (fray's metric is MAE; torrent's D2 is a margin) but the
   defect is armed and waiting on any higher-is-better comparison. The repin is a (c) item with a
   live defect behind it, not housekeeping.

### 3.2 Findings the plan adds (measured by the reviews, not previously stated fleet-wide)

- **chokepoint D2 is armed on `hgb_d3`, not on the learner the run trains.** `[placebo].estimand`
  names the tabular candidate; the fine-tune's leak channels (window construction at the train
  bound, 512-day contexts reaching into 2019, the quantile head) are asserted by runner controls,
  never placebo-tested. D2 is a real stop on the tabular pipeline and a *proxy* stop on the
  fine-tune.
- **fray's E1 trainer arm is fail-open**: `halts = bool(flat) if flat is not None else None`
  (`train_unseen_year_track.py:1324`) and the decision reads `bool(e1.get("halts"))` — an
  unmeasured curve proceeds with `no_hard_stop_fired: True`. mlkit's own binding refuses a None
  rung, so the exposure is the trainer's in-run verdict only. Same class as the D2 `n_paired==0`
  guard already replaced with a named `SystemExit`.
- **The chokepoint panel exists on one laptop** (E-051): `daily_chokepoints.parquet` is not in git
  or DVC; IMF PortWatch has revised the history inside the pinned window (+51,766 transits,
  +0.95%). Every chokepoint gate refuses correctly from a clean clone — nothing in that repo can
  be re-measured anywhere else. **fray's 141 MB NASS extract is in the same state** (E-055; both
  pinned URLs 404; the review reproduced the run only by transporting the physical file).
- **fray's committed `reports/pytest_suite_summary.txt` says green (1128 passed, dated
  2026-07-26); PR #93 measured main at 107–120 failed / ~2,080 passed, non-deterministic under
  load.** A stale green summary beside a measured red is theatre; it escaped the freshness walk by
  naming no SHA (E-041).
- **The cross-corridor experiment on chokepoint is runnable through the published API** (§0):
  `id_column` cross-learning and covariates are documented capabilities of the pinned checkpoint.
  "More covariates are provably not the route" was generalised from fray's gridMET result; for a
  series foundation model on chokepoint it is **unmeasured, not refuted**.

---

## 4. The programme, ranked by expected value

Every item carries: **kind** (a/b/c) · **what changes** · **what measures it** · **acceptance
criterion** · **cost** (compute from a measured rate or an arithmetic bound, labelled; wall-clock
is an *estimate of agent effort, not a measurement*) · **what would falsify the claim that it
helped** · **owner** (agent / signatory). No item without an acceptance criterion.

Ranking principle: an item that changes what the repo can *claim* or *serve* outranks one that
changes a VAL number; an item costing a signature outranks one costing a night; anything the
measured evidence says will not pay is in §5, not here.

### RANK 1 — chokepoint: adopt D6 and declare the split of record  [b, c]

- **What changes**: a `resampling_declaration` binding in `mlkit_bindings.py` reporting
  `{procedure, draws, policy, blocking_unit=corridor, unit, arm, assignment, track}` for the
  daily-flow product; `splits` made track-aware (mlkit #38 contract) so the time-blocked all-28
  partition is the split of record for `daily_flow` and the corridor-blocked 20/4/4 for
  `episode_response`; a recorded decision naming which split governs which product.
- **What measures it**: `mlkit check --phase decision` renders D6 as PASS or a **named refusal**;
  R3/R5 re-measured on the daily-flow partition.
- **Acceptance**: D6 is no longer NA; injecting a row-unit declaration makes D6 refuse
  `DEPENDENCE_UNIT_TOO_FINE`; injecting a declaration whose track is not in `splits()` refuses by
  name; every other verdict row byte-identical before/after; no test deleted.
- **Cost**: zero compute (mlkit D6 reads declarations); one prereg note; agent effort estimate
  under a day. The decision line is the signatory's (**S-2**).
- **Falsifier**: if the daily-flow R5 audit on the time-blocked partition finds a synthetic or
  duplicated row that the corridor-blocked audit missed, that is a *finding*, not a failure of the
  item — but if D6 passes with the unit still recoverable as rows, the binding is theatre.
- **Owner**: agent builds; signatory records the split decision.

### RANK 2 — chokepoint: the E-022 / E-048 decision on the held h=14 (and h=1/h=3) arms  [b]

- **What changes**: what is served at h=14 (today: a trailing mean). Option (a): spend the
  prepared h=14 read (14,560 rows, `prepared_test_arm` PREPARED — UNOPENED) on zero-shot
  chronos-2 under the pre-registered ladder rule. Option (c): re-block with a fresh test period
  as PortWatch publishes past 2026-08-16 — zero compute, costs calendar time, **requires E-051
  resolved first** so the old bytes survive.
- **What measures it**: the existing pre-registered rule (`foundation_full_val_ladder` §rules):
  test skill vs `trailing_mean_h` with a corridor-block CI; the challenger gate in `champion.json`
  currently records chronos-2 as `EVIDENCE_IS_VAL_ONLY`.
- **Acceptance**: the h=14 corridor-block CI on test clears zero → chronos-2 becomes the served
  h=14 model. **If it does not clear, the read is spent, the arm is closed, and that is the
  result** — no second candidate at h=14.
- **Cost**: zero fitting; forward passes on 14,560 rows (the ladder's six-horizon foundation
  passes cost 86 min per E-056 — one horizon is a fraction of that, **NA until timed**); one
  multiplicity spend (12 comparisons declared, none corrected).
- **Falsifier**: the VAL h=14 interval [+0.047, +0.147] is the narrowest of the four clearing
  arms; a test interval covering zero is the honest failure mode and must be published as such.
- **Owner**: **signatory only (S-1)**. Zero-parameter model, no selection question — the decision
  is purely whether to spend the read now or after a re-block. My recommendation, on the merits:
  resolve E-051 first, then choose (c) if PortWatch's revision makes the pinned bytes un-servable
  anyway, else (a). Either is defensible; leaving it unanswered is not — the served product has
  lagged the measured best for six days on this alone.

### RANK 3 — fray: E-057, adopt Frame 2 (nested forward-chaining over the 50 origins) as the unseen-year promotion frame  [b]

- **What changes**: the deciding frame moves from five VAL crop years to K forward origins
  (1971–2020 supplies 50 admissible ones without touching 2021–2025), with **candidate selection
  inside each fold** (the reporting instrument already exists as the 45-origin backtest; without
  in-fold selection it is "the reporting instrument with a promotion label bolted on" — PR #93).
  Promotion condition: crop-year-block bootstrap over origins clears zero. TRAIN's last decade is
  not sacrificed (that is Frame 1's cost).
- **What measures it**: the trainer's own origin loop, extended; mlkit D2 (forward-year placebo)
  and E1 re-driven on the new frame; the row-bootstrap condition retained (decorative, harmless).
- **Acceptance**: prereg is the branch's **first commit**; K ≥ 15 (80% power on the headline
  operands μ 22.150, σ 28.018; **K ≥ 19 at the 45-origin σ's chi-square upper limit** — choose
  K with the arithmetic visible, PR #93 does it); a frozen-selection positive control reproduces
  the committed 45-origin figures (mean +16.570, block CI [11.123, 21.932]) to 1e-12; the
  forward-year placebo is silent on the new frame; an injected target leak halts. Then the
  verdict — cleared or not — is published as the deciding verdict.
- **Cost**: the full 60-candidate menu, both placebo arms, E1 and the 45-origin backtest run in
  **2m30s on CPU** (STATE, 2026-09-02); 50 folds × a menu each is an **arithmetic bound of ~2 h
  CPU, not a measurement**. Agent effort estimate: 2–4 days including controls. No new data.
- **Falsifier**: if the block interval over ≥15 origins covers zero, the ~+16 lb/ac effect is not
  decidable at this size either — publish it; do not add origins post hoc (rule 6: K is chosen
  before the run and written in the prereg).
- **Owner**: **signatory decides E-057 (S-3)**; agent implements. This is the single
  highest-leverage decision on fray; PR #93 already carries the arithmetic. Merging #93 is
  merging a preregistration, not a change of frame.

### RANK 4 — torrent: a basin-block interval on the model-of-record margin  [b] — zero fits

- **What changes**: nothing in the model. A committed artifact carrying the paired basin-block
  bootstrap of `NSE(ridge) − NSE(persistence_lag3)` (median paired difference and fraction of
  basins beaten) over the 65 VAL basins, from the per-basin arrays already committed
  (`linear_reference_val_recheck.json` `per_basin_nse`; the val baselines block).
- **What measures it**: `src/torrent/hydrology/scaling_interval.py` on #174 already implements a
  paired basin-block bootstrap with 12 refusal paths and `module.__file__` asserted; run it once
  in `--mode measure` under a prereg that fixes the estimand, 20k draws, seed.
- **Acceptance**: the interval exists and is tied to the operand digests. **If it covers zero,
  E-030's holder is not a record and the plan's torrent branch reverts to "the floor is the
  record."** If it clears, E-030 becomes signable (S-7) — but not signed by this item.
- **Cost**: minutes; no fit; no read. This item is admissible under the standing E1 halt because
  it fits nothing.
- **Falsifier**: the per-basin operands must re-derive from the served path (`|diff| = 0.0` is
  already established for the point metric via `hydrology_ridge_served_val.json`); a mismatch is
  a refusal, not a number.
- **Owner**: agent.

### RANK 5 — fleet: repin fray and torrent to mlkit `3bf16dd`, re-measured against today's main  [c]

- **What changes**: `pyproject.toml` rev; adoption of `HaltRegion`/`[placebo] indicts`, the
  polarity contract (`core.served` — a live promotion defect on both pins, §3.1.8), track-aware
  `splits`, D6, and `[scaling]` declarability. #94 (112 commits stale, CONFLICTING, A/B taken
  when fray declared neither stop) and #176 (53 stale, CONFLICTING, headline overtaken by
  `140a3f2`) are closed and redone, or rebased and re-measured cell by cell — **never merged on
  their stale measurements.**
- **What measures it**: readiness/decision/economics tables before vs after on the same tree;
  the polarity test surface (chokepoint went 101 passed → 23 failed / 78 passed on its repin and
  those 23 were true findings; expect the same shape).
- **Acceptance**: every verdict row identical except (i) D6 NA appears (strictly stricter), (ii)
  polarity-undeclared comparisons become NA refusals rather than promotions; D2/E1 controls fire
  on injected leak/flat curve and are silent on the honest tree *through the new pin*; zero test
  deletions; **for torrent, the `[scaling]` ladder is either left at the default or declared
  blind in the same PR — never chosen after looking at the known 0.25→0.50 (+5.92%) step.**
- **Cost**: zero training compute; the fray gate phases take ~3.5 min per drive (measured); agent
  effort estimate 1–2 days per repo because of the polarity assertions.
- **Falsifier**: a verdict row moving in the *promoting* direction under the repin is a stop
  (report, do not proceed); any test deleted or reworded is a refusal.
- **Owner**: agent; but it gates fray's D6 (#88's declared-`[placebo]` design can return only
  after it) and torrent's honest D2 (one-sided region), so it sits above the torrent arming.

### RANK 6 — torrent: arm D2 honestly (#175 unblocked) and bind E1 — before any torrent fit  [c]

- **What changes**: #175's refit placebo lands **after** its deviation (a) — permutation across
  the train block rather than within basin, the choice that turns a would-be halt into a pass —
  is backed by `measure_within_basin_permutation.py` + a committed artifact reproducing the prose
  figure (+0.2017 [+0.1400, +0.2747]) or refuting it; under the repin, `[placebo] indicts =
  "above"` is declared for the refit placebo (prereg §8 says it is the honest region); a
  `scaling_probe` binding is added over the ridge's existing E1 ladder **with the default
  fractions**.
- **What measures it**: mlkit D2/E1 rendered on main. Note what E1 will say: **the honest binding
  makes the standing halt real** — gain −12.867% ≤ 1% → E1 FAIL → torrent is halted by a machine,
  not by prose. That is the correct state and it is the point of arming.
- **Acceptance**: D2 fires 1.000 under a total leak and A1/A2 (already measured on #175), silent on
  the honest tree at the nominal false-halt rate (0.062 measured for the double resample);
  E1 renders a verdict (expected FAIL) and control C1 (rungs capped) also FAILs, R1 (ladder
  deleted) refuses; `hard_stops.md` derived at run time, never typed.
- **Cost**: the within-basin measurement is one refit-class run (the ridge is closed-form; E1
  ran six fractions in one sitting — minutes); agent effort estimate 1–2 days.
- **Falsifier**: if the within-basin permutation does *not* beat the bar on a healthy tree, the
  deviation's justification is gone and #175 must use within-basin permutation — even if that
  halts. A design decision that avoids a hard stop cannot rest on an uncommitted number.
- **Owner**: agent; signatory rules on **S-8** (whether the E1 halt, once armed, applies to
  enlarging the evaluation frame, which is RANK 9's justification).

### RANK 7 — chokepoint: corridor-conditional coverage as the operator-facing axis  [b]

- **What changes**: the allocation cycle is re-registered against the regenerated ladder (the
  old prereg pins sha `5ba6a78b`; main's ladder is `8d09d35b`; the verifier correctly refuses —
  `test_the_new_verifier_refuses_a_mutated_operand` is red on main *by design*). Then the
  allocation arm (chasing the oracle frontier by allocation rather than width) is re-adjudicated
  for a **servable** band.
- **What measures it**: `foundation_corridor_allocation` runner; the servability rule (no empty
  intervals) already preregistered; per-corridor coverage table at α=0.2.
- **Acceptance**: corridors below nominal at α=0.2 go from 10/28 (served) or 13/28 (chronos-2
  marginal) toward **28/28 within tolerance**, at a pooled width ≤ the oracle-frontier bound the
  diagnostic already measured (0.972–1.007× the pooled width spent), with zero empty intervals.
  **A pooled improvement with the below-nominal count rising is a FAIL** (it happened once, in
  the per-corridor CQR arm: pooled MAE improved 0.038 mtpd at h=7 while corridors below nominal
  went 10 → 13 of 28 — basis risk in disguise).
- **Cost**: conformal calibration only — no fits; forward passes cached; minutes to an hour.
- **Falsifier**: if no servable arm reaches 28/28, the honest statement is "corridor-conditional
  coverage at this width is not attainable with these predictors" — and that is what an
  avoided-loss buyer needs to know before any point-model swap.
- **Owner**: agent; **signatory re-registers the prereg (S-4)** — an agent may not edit a pin in
  a preregistration to make a check pass.

### RANK 8 — fray: an interval on the unseen-year track, per crop year  [b]

- **What changes**: a rolling conformal instrument on the Frame-2 origins — calibrate on
  residuals from origins < Y, evaluate coverage on origin Y — reported **per origin**, not pooled;
  a `coverage` binding for the unseen-year track so mlkit D3 renders instead of NA; the #81/#82
  writer contract (every scalar recomputable) reused.
- **What measures it**: D3 and the per-year table.
- **Acceptance**: coverage at α=0.2 within tolerance on **each** evaluated origin; the pooled
  figure reported beside it and not used as the verdict. Today's spatial α=0.2 FAIL (0.7738 vs
  0.80) stays legible and is not the bar for this track.
- **Cost**: minutes per origin (residual quantiles over ≤ 1,365 rows); no new fits beyond RANK 3.
- **Falsifier**: a pooled pass with ≥ 1 origin failing is a fail; a hand-written
  `{"quantile_adjustment": …}` must be refused by the wired gate (#83).
- **Owner**: agent; depends on RANK 3.

### RANK 9 — torrent: enlarge the *evaluation* frame with the union rule (E-062), justified as blocks, not as LSTM data  [b]

- **What changes**: staging the signed-but-unstaged Caravan extensions (`caravan-v1.6`,
  `grdc-caravan-v0.6`, DE/DK/CH/IL/CZ/ES — all ALLOWED in `docs/allowlist.yaml`) under the
  **union** selection rule so the committed 65 VAL / 34 conformal / 30 TEST evaluation basins
  remain a subset by construction (the current `basins_per_subdataset` 32→128 lever is a
  *stride* that silently drops 131 of 352 gauges and moves every split — E-062). VAL blocks
  71 → ~277 (`scale_cost_1375.json`).
- **What measures it**: RANK 4's interval re-measured on the enlarged frame; the E1 ladder
  re-measured **with the default fractions** (the 1% rung stops being two basins); D3 on ~34→more
  calibration blocks; a nesting test asserting the old evaluation ids ⊂ new.
- **Acceptance**: the nesting test passes; the ridge refit reproduces the 65-basin figures on the
  old subset to 1e-12 (positive control); the new intervals are published whichever way they
  fall. **The ME-LSTM is not part of this item.**
- **Cost**: download ~10 h at the measured ~199 KB/s; the ridge is closed-form (seconds);
  no LSTM epochs (the 3.09 h/seed figure belongs to a different item and is not incurred).
- **Falsifier**: if the E1 curve on the enlarged frame is still flat/negative under the default
  ladder, the halt stands on a frame that can resolve it — and "do not scale" becomes a
  *finding* rather than a point estimate.
- **Owner**: agent; **signatory amends `caravan_scale_1375.yml` to the union form (S-9) and rules
  on S-8** before it runs.

### RANK 10 — torrent: the target-normalised ridge diagnostic, VAL only  [a→b]

- **What changes**: the same estimator, 60 features, alpha, split; the only change is the target
  scale (per-basin train-period standardisation, or `log1p`), inverted before scoring so the
  observation scored is `obs_raw` — the R5 argument round 5 §C2 already made for
  `residual_reference`.
- **What measures it**: median, mean, p05, fraction-below-zero, and the paired basin-block CI of
  each *change* vs the served ridge, from RANK 4's instrument.
- **Acceptance (pre-declared, either way is a result)**: if the mean and p05 move by more than
  their paired basin-block interval while the median's change interval covers zero, the
  "model-class" reading is **refuted at zero cost** and the tail was a target defect; if nothing
  moves outside its interval, the tail is structural and the model-class question is next.
  Nothing is promoted by this item; E-030 stands until signed.
- **Cost**: seconds of CPU. **It is a fit in a repo whose E1 halt, once armed (RANK 6), is
  FAIL.** CLAUDE.md says halt "without tuning or scaling"; this is neither, but it is a fit, so it
  runs only after **S-8** records that a target-parameterisation diagnostic is permitted under the
  halt. Sequence: RANK 4 → RANK 6 → S-8 → this.
- **Falsifier**: a target transform that "helps" only because inversion was skipped (scoring a
  standardised observation) is R5's mirror — the runner must assert `obs_raw` is what is scored.
- **Owner**: agent, after S-8.

### RANK 11 — fray: NASS Crop Progress & Condition as a preregistered in-season block, adjudicated on the origin instrument first  [a]

- **What changes**: ingest state-level weekly `COTTON, UPLAND – CONDITION, MEASURED IN PCT
  EXCELLENT/GOOD/…` rows — **already inside the signed allowlist** (E-048, resolved 2026-08-31,
  same keyless bulk file, same terms; ~9,127 weekly rows in one 8 MB slice) — with a
  release-date embargo enforced by a test, joined to county rows by state and season.
- **What measures it**: the Frame-2 / 45-origin paired instrument (where gridMET's +6.248
  [0.341, 11.749] was visible) **before** it touches VAL; the forward-year placebo (condition of
  year t+1) as the leak control.
- **Acceptance**: paired year-block CI of the condition block vs the base clears zero on the
  origin instrument; the forward-year placebo is silent; the embargo test fails if any row dated
  after the origin's information cutoff reaches the fit. **Year coverage and publication lag are
  NA until the loader measures them; do not guess how far back condition ratings run.**
- **Cost**: loader engineering (estimate 1–2 days); fit minutes.
- **Falsifier**: the same block scored *with* the embargo removed should improve further if the
  signal is real-time information; if it improves only without the embargo, it was leakage.
- **Owner**: agent. Ranked below the frame items because, on five VAL years, it cannot change the
  decision (gridMET moved the VAL median +0.0619 and the interval not at all); under Frame 2 it can.

### RANK 12 — fray: gridMET water block re-adjudicated under Frame 2  [a]

- **What changes**: nothing new is built; the block already exists (`src/training/gridmet_extension.py`)
  and is already measured +7.080 [2.517, 11.506] (`pre_water`) on 45 origins; `pre_heat` +4.422
  [−1.878, 10.286] does not clear; `prior_all` −2.993. Under Frame 2 the block enters the
  in-fold menu.
- **What measures it / Acceptance**: the same paired year-block CI clearing zero with selection
  inside the fold; if it clears there and the in-fold winner carries it, it is promoted with the
  frame, not separately.
- **Cost**: none beyond RANK 3. **Falsifier**: the forward-year placebo (bound as mlkit D2) must
  remain silent — if it starts to fire under in-fold selection, the join is leaking. **Owner**: agent.

### RANK 13 — chokepoint: zero-shot chronos-2 with cross-corridor context  [a] — the one model-side experiment worth a prereg

- **What changes**: forward passes only. `predict_df` with `id_column` over all 28 corridors
  jointly (cross-learning across items is a documented capability of the pinned checkpoint, §0),
  optionally past covariates (calls, tanker share); **no `future_df` of the target**. Same ladder
  rules, same bars, same corridor-block interval, VAL only. The structural fact a univariate
  context cannot see — Red Sea diversions reappearing at the Cape — is exactly what the val block
  opens with (`foundation_corpus_window.md` names 2024-01-01 as a regime boundary).
- **What measures it**: the full-val ladder runner; a **paired** corridor-block interval vs
  univariate zero-shot (the paired full-grid interval vs `hgb_d3` is currently NA — it must be
  computed for this experiment rather than subtracting two CIs).
- **Acceptance**: at h=7 and h=14, the paired CI vs univariate zero-shot lies above zero **and**
  the CI vs `trailing_mean_h` still clears; a **shuffled-assignment control** (each corridor's
  context paired with randomly permuted other corridors) must not help; a **future-leak control**
  (any future value of the target in context) must be refused by name.
- **Cost**: NA until a smoke times a joint 28-series pass; the univariate ladder's foundation
  passes cost 86 min for six horizons per predictor (E-056). No fit, so D2/E1 do not gate it.
- **Falsifier**: if it wins only at h=1 (where the whole menu is within 0.03 skill and "anything
  that isn't seasonal-naive does about equally well"), it is not a model-class result.
- **Owner**: agent; prereg first commit.

### RANK 14 — torrent: real forecast forcing (`caravan-multimet-forecasts`, ALLOWED, unstaged)  [a→d, legibility]

- Stage MultiMet (IFS-HRES / GraphCast as available) into the forecast branch at lead 3 and
  re-score the ridge. Acceptance: the perfect-forecast optimism measured as a paired basin-block
  Δ vs the reanalysis-forced number, published whichever sign; the served number becomes a
  *forecast*. Cost: staging (NA until measured; the Caravan union download is ~10 h at 199 KB/s,
  MultiMet size unknown); fit seconds. Falsifier: if the Δ is zero, the forcing was never the
  binding input at lead 3 (the basin's own discharge was) — also a result. Owner: agent, after
  E-025 (S-6). It is also what makes the Flood Hub comparison, refuted today on input mismatch
  (E-014/E-023), even conceivable — and even then it would be in-sample on this test window.

### RANK 15 — fray: the external legibility instrument (production-weighted August-1 RMSE%)  [d]

- Preregister: production-weight county forecasts to state and national upland-cotton production
  at an August-1 information cutoff over the Frame-2 origins (1971–2020, TRAIN/VAL only) and
  score RMSE% against NASS final estimates, reported **beside** NASS's own 9.7% / 16.7%
  (crop0825.pdf, above) with NASS's definitional paragraph **quoted, not paraphrased**, by the
  loader. Acceptance: the number exists with its unit and caveats; **it is a report, not a
  promotion criterion**; NA until run. Cost: minutes once RANK 3 exists. Falsifier: the
  twenty-year basis and August-1 cutoff must match NASS's definition or the comparison is not
  made. Owner: agent. This is the first number in fray that means something to a cotton merchant
  or an underwriter.

### RANK 16 — fleet hygiene bundle (each small, each a (c) item)  

- **fray**: replace the E1 fail-open (`:1324`) with a named `SystemExit`; retire or SHA-stamp
  `reports/pytest_suite_summary.txt`; R1's three `baselines/*.pt` — provenance or removal is a
  rule-15 signatory call (**S-12**); make the served-model contract emit the unseen-year track's
  measured NA rather than the spatial figure (E-038b default backend is **S-11**).
- **chokepoint**: regenerate the three gate reports on post-#120 main so R10/R11/R12 have walked
  `hard_stops.py` (minutes); land the E-056 *entry* on main (it exists only on #119's branch);
  rebase or close #119 (CONFLICTING) — it is a run record, not code; R9's two unallowlisted ids
  (`commercial-ais`, `customer-network`) — allowlist or remove is **S-13**.
- **torrent**: regenerate `reports/readiness.md` on main (108 commits / 38 source files stale; its
  own freshness test fails on main); resolve the R12 ambiguity (the stale table says FAIL 7, #166
  measured PASS on `373d935`); re-base `model_of_record.decide` on the basin block (it adjudicates
  on seed stdev — conservative today by accident of a large gap); R9's six BLOCKED sources are
  **S-13**.
- Acceptance for all: verdict rows identical except the named row; regeneration, never restamp;
  every fix re-fires when reintroduced alone.

### One-epoch-fragility — the standing reporting template for every fitted item above

Every item that fits reports, on the **declared dependence unit** (crop year / corridor / basin —
never rows): the selected candidate, the menu median, the five next-best, and the bootstrap CI.
Promotion requires the CI to clear zero, never the point estimate. Where a menu was not scored,
all four read NA — a median over an unscored menu is a fabricated value (chokepoint #119 did this
correctly). Current state: fray selected +22.811 / median +15.976 / five next-best +22.723,
+22.718, +22.584, +22.563, +22.542 / block CI [−1.289, +41.704]; chokepoint (VAL, zero-shot)
per horizon as in §1.2, e.g. h=7 selected +0.175749 / median +0.103956 / next timesfm +0.166441,
hgb_d3 +0.137636, ridge_momentum_only +0.122151, ridge_a10 +0.103956, ridge_a1 +0.097329; torrent
**all NA** (no candidate has ever carried a basin-block interval).

---

## 5. What NOT to do — and what to STOP

Each of these is something the fleet is, or has been, drawn to. The evidence beside it is the
reason.

1. **STOP the chokepoint fine-tune line beyond the run now in flight.** The 200-step probe sits
   below zero-shot at every rung; clause (3) needs a paired corridor CI *above* zero-shot; the
   gating E1 has P(flat) = 5.45% under refit resampling; D2 never touched this learner; and even
   a win changes nothing served without the E-022 read. If the in-flight run returns an empty
   verdict list, close the line. If it returns a non-empty list, §7.2 applies before anyone quotes
   it. Do not queue lr sweeps, longer contexts, or a second seed behind it. If someone insists,
   E-055's cheaper experiment — a **compute-scaling probe at the fixed 25% rung (200 → 600 →
   1,800 steps)** to see whether the level even crosses zero-shot — is the right one and needs
   its own prereg.
2. **Do not build a training plane** (R7, SageMaker, `Dockerfile.training`, the Fulcrum bundle,
   `docs/RUN_ECONOMICS.md`'s canonical text describing a plane that does not exist). fray's whole
   menu is 2m30s on CPU; torrent's record is closed-form; chokepoint's only long job is the one in
   item 1. Rule 12 reserves the resources anyway. Bootstrapping infrastructure for a 2.5-minute
   scikit-learn fit is the most expensive thing on the table that buys nothing.
3. **Do not touch fray's deep/foundation chain** (dual-stream GRU, Galileo adapter, AlphaEarth;
   `docs/SOTA_REVIEW.md` §6; E-019). Its satellite-era rows (2,478–5,517) sit between the E1
   rungs where the base learner is *below the floor* (1%: −22.571) and +7 (10%); on five VAL years
   nothing can be promoted regardless of skill; the E-019 blocker is signatory-only.
4. **Do not spend any ledgered read on the current frames.** fray: 9/200 seeds clear zero on VAL —
   a 1,270-row read of a candidate VAL did not clear buys an uninterpretable, unrepeatable
   number. chokepoint h=1/h=3: nothing served hangs on them; h=14 is RANK 2 and the signatory's.
   torrent: a second read of any arm before RANK 4 exists would be spent on a point estimate.
5. **Do not widen fray's menu, add capacity, or add ERA5 monthly weather.** Measured: menu 50→60
   moved the median +0.0619 and the decision not at all; leaves=127/iter=400 (50,800 params) is
   *worse* than leaves=31/iter=200 on five years; both ERA5 families are the worst in the menu.
6. **Do not run the ME-LSTM ladder (C1 60-epoch × 5 seeds, ~9 h floor for three 30-epoch seeds
   at 3.09 h/seed) or fine-tune `google-floodhub-base`.** The former is behind the ridge on the
   wrong unit and cannot be interpreted before RANK 4 and RANK 10; the latter is NA on two
   measured gates (16 required inputs absent; trained through 2023, which contains the test window).
7. **Do not chase chokepoint h=21/28 with covariates, steps or a bigger model.** The interval is a
   population property of 28 heterogeneous corridors under a pooled estimand; changing it is a
   rule change (§3.1.1) that the signatory would have to apply retroactively to h=7's champion.
   Do not revive the dormant `gnn`/`hgnn`/`deep-model-alignment` branches: the pooling cycle
   measured `per_corridor_hgb_d3` at −0.372 [−0.631, −0.200] and no pooling arm clears.
8. **Do not treat "driven three times, byte-identical" as evidence of arming.** E1's probe reads a
   committed JSON in 2.6 s; D2 is fully seeded. Three drives prove the tree did not change. Stop
   putting it in headlines.
9. **Do not count control N (chokepoint E1 companion) toward "8/8".** The companion curve is already
   rising; the mutation cannot discriminate; the artifact records `identical_to: "S1"`. 7/8.
10. **Do not declare torrent's `[scaling]` ladder after looking at the curve.** 0.25→0.50 (+5.92%)
    is in a PR body; choosing fractions now is choosing the gate to pass (rule 6). Default or blind.
11. **Do not pass any structured result to another agent through a truncated inline stringify;
    do not read "MERGED" as "in main"; do not resolve conflicts whole-file.** Each cost this
    campaign a night or a PR (STATE: three truncation blindings; torrent #167/#169/#170 landing in
    each other's branches; the `--theirs` that discarded 15 refusals).

---

## 6. What only the signatory can do

Nothing below is agent-executable, and each blocks a ranked item. Listed with what it unblocks.

| id | decision | unblocks | my recommendation (on the merits, yours to take or refuse) |
|---|---|---|---|
| **S-1** | **E-022 / E-048**: spend the held chokepoint h=14 read on zero-shot chronos-2 (a), or re-block with a fresh test period (c) — and, separately, whether h=1/h=3 are ever opened | RANK 2; the only action that changes what chokepoint serves | resolve E-051 first; then (c) if the PortWatch revision makes the pinned bytes unservable, else (a). Do not open h=1/h=3 — nothing served hangs on them |
| **S-2** | record the split of record per chokepoint product (time-blocked all-28 for `daily_flow`; corridor-blocked for `episode_response`) | RANK 1 (D6) | yes, exactly as the product already behaves |
| **S-3** | **E-057**: adopt Frame 2 (nested forward-chaining over the 50 origins) as fray's unseen-year promotion frame; fix K before the run | RANK 3, 8, 11, 12, 15 | Frame 2, K chosen at the 45-origin σ's upper limit (19) unless you accept 80% power at 15; merge #93 as the preregistration |
| **S-4** | re-register the chokepoint allocation prereg against the regenerated ladder sha `8d09d35b` (the verifier refuses the moved operand by name and an agent may not edit the pin) | RANK 7 | yes — the refusal is correct behaviour, and it is the only thing keeping corridor-conditional coverage un-runnable |
| **S-5** | **CLAUDE.md's literal D2 sentence vs the preregistered one-sided regions** on chokepoint (`[placebo] indicts = "above"`, the measured CI [−0.0047, −0.0024] excludes zero) and on fray (`train_unseen_year_track.py:1648`, CI [−87.5, −33.2] excludes zero). Amend the rule's text to "excludes the declared null in the direction the preregistered `[placebo]` declaration indicts", or record the ratification as a decision, or refuse it — in which case both repos are halted today | the standing of every chokepoint and fray hard-stop verdict | amend the text; both exemptions were declared when the stop was *armed*, are argued from the estimand's arithmetic, and chokepoint's is proved load-bearing by control D. But it is a divergence you own, not an agent |
| **S-6** | **E-025**: torrent's product claim — gauged (the only track with a model that beats a floor) or ungauged (no model beats a constant; the external comparator is Nearing 2024) | RANK 14 and the meaning of every torrent number; the word "SOTA" | gauged, explicitly, with the ungauged track recorded as "floor is the record" until something beats it |
| **S-7** | **E-030**: sign or refuse the ridge as torrent's model of record, *after* RANK 4, with the tail (mean −2.949, min −202.1, 18/34 basins under-covered) on its face | the served contract | sign only if RANK 4's basin-block interval clears; otherwise the floor is the record |
| **S-8** | whether torrent's E1 halt (−12.867% on a point estimate whose interval contains the bar) permits (i) enlarging the *evaluation* frame (RANK 9) and (ii) a target-parameterisation diagnostic fit (RANK 10). Both are responsive to the halt's finding; neither is tuning or scaling the learner; both are fits in a halted repo | RANK 9, RANK 10 | permit both, in writing, with RANK 9 justified as blocks and RANK 10 as diagnosis; refuse any learner run until E1 is re-measured on the enlarged frame under the default ladder |
| **S-9** | **E-062**: amend `caravan_scale_1375.yml` to the union selection rule (or make `_select_gauges` nested by construction) | RANK 9 | yes; the stride form drops 131 of 352 staged gauges |
| **S-10** | **MLKIT_READ_TOKEN**: mint the cross-repo read credential (rule 12/13) | CI in all three model repos measuring anything; #92/#116/#173 are merged and waiting | do it first; it costs a minute and every green board since 2026-08-28 has been a laptop's |
| **S-11** | **E-038b**: fray's API default `yield_backend="mechanistic"` — the one backend with no measured OOS skill — and what the API serves for the forecast question at all, given the spatial champion is 8.79 lb/ac worse than the no-weather base on unseen years | the served contract; RANK 16 | serve nothing for the unseen-year question until RANK 3 promotes something; until then the API should say NA on that question rather than a number from the wrong track |
| **S-12** | rule 15: fray's three `baselines/*.pt` (R1 FAIL) — provenance or removal | R1 | remove; they are not on the record's path |
| **S-13** | rule 14: chokepoint's `commercial-ais`/`customer-network` and torrent's six BLOCKED sources in the manifests — allowlist or remove | R9 in both repos; "9/12" can never be "12/12" without this | remove unless a licence URL exists |
| **S-14** | **E-051 / E-055**: durable storage of the two panel files every committed verdict rests on (chokepoint `daily_chokepoints.parquet` sha `8644a58e…`, 77,980 rows; fray NASS extract sha `5c80c0d3…`, 141,304,960 bytes) — a `us-west-2` bucket / DVC remote is a cost-incurring resource (rule 12) | reproducibility of everything; RANK 2(c) | do it before anything else in chokepoint; if the laptop goes, the measurements go with it |
| **S-15** | the 60-minute harness ceiling: if the in-flight test shows it is global, either you run the single command in your own terminal or you authorise a **preregistered** mid-fit checkpoint/resume in the runner (whole-config granularity today) | any run longer than an hour | decide after 23:51Z tonight (§7.2) |

Also reserved and **not** requested by this plan: any allowlist addition (rule 14; none is
needed — every source the plan uses is ALLOWED already), D1/D4/D5, E4/E5, IAM/billing.

---

## 7. What would make the next long training run worth starting — per repo

The last one produced no number: two cpu attempts died at the 60-minute ceiling inside the first
fit (2.14 h/config on cpu by the run's own probe; 4.44 h by the adjudicator's marginal re-measure
on the same machine — a machine-state artefact, not a stable quantity; 1.58 h/config on mps,
measured at the marginal rate), and the probe that armed it measures the fine-tune below
zero-shot at every rung. The general lesson: **a long run is worth starting only when (i) the
frame can adjudicate its result, (ii) the stops are armed on the learner it trains, and (iii) a
win would change something served.** Applied:

### 7.1 fray — do not train; there is no long run to start

fray's runnable tracks are minutes-scale and deterministic (the full menu in 2m30s reproduces the
model of record bit-identically on all eight figures). An overnight re-run moves nothing. The
next fit worth doing is RANK 3 under Frame 2 — **hours of CPU by arithmetic bound, not a night**
— and its preconditions are: E-057 signed (S-3); the prereg as first commit with K fixed; both
stops re-driven on the exact tree (D2 forward-year placebo silent, E1 rising) — they are armed
today; the E1 fail-open at `:1324` closed first. What it buys: the ~+16 lb/ac effect becomes
*decidable*. What it cannot buy: more skill (that is RANK 11/12, adjudicated on the same frame).
The only overnight-scale trainer in the repo refuses at t=0 (DVC-absent panel + E-019) and should
stay refused (§5.3).

### 7.2 chokepoint — read the in-flight run first; then, almost certainly, do not train again

The mps run (PID 16223) crosses the ceiling at **23:51Z**. Decision tree, written before the
outcome is known:

- **It dies at ~60 min.** The ceiling is global to this machine's sessions, not subagent-scoped.
  Then S-15: the user runs `scripts/run_foundation_finetune.py --stage val --fit-device mps
  --cache-dir <outside the repo>` in their own terminal (~3.2 h for both configurations by the
  measured mps rate), or authorises a preregistered mid-fit resume. **Nothing else about the run
  changes** — 3,000 steps is the registered configuration; a shorter run is a different
  experiment wearing the run of record's name. Clear the half-fit checkpoint before any relaunch
  (a partial left in place is a trap for the resume cache).
- **It completes with an empty verdict list.** That is the rule working. Close the fine-tune line
  (§5.1). The model of record remains zero-shot chronos-2. Everything in RANK 1, 2, 7, 13 proceeds
  unchanged — none of them depended on this outcome.
- **It completes with a non-empty verdict list** (some (config, horizon) pairs clearing all three
  clauses). Before anyone quotes it: (1) the artifact's `hard_stops` block must read
  `derived_at_run_time: true` with both ARMED/PASS — the E-056 fix is on `b834437` and the first
  log line shows it working; (2) `scripts/verify_foundation_finetune.py` exits 0 with its
  independent resampler; (3) the verdict is read as a **list**, not as the h=7 point MAE; (4) it
  inherits E1's 5.45% and D2's proxy status, so **a D2 placebo on chronos-2 itself** (fit on
  windows whose targets are permuted within corridor, score honest val — one more 200-step-class
  fit) and an E1 re-run with enough replicates that the refit-resampled interval excludes the
  threshold on the same side as the point estimate are preconditions to any promotion; (5) it
  still reaches the product only through S-1. Fragility on the corridor unit (selected, menu
  median, five next-best, CI) is reported from the artifact's persisted per-(predictor, corridor)
  operands, or NA.

Preconditions for **any** further chokepoint fine-tune after this one: all of (1)–(5) above,
plus an accepted answer to "what does it buy" given that h≥21 is frame-capped and h≤14 is a
zero-parameter model's already. My expectation, stated so it can be falsified by the artifact:
**the verdict list is empty.**

### 7.3 torrent — do not train; arm, measure, decide

No torrent fit of any kind should start until, in order: RANK 4 (no fit) → RANK 5 repin →
RANK 6 arming (D2 refit placebo, E1 bound with the default ladder; the E1 verdict will be FAIL
and torrent will be halted by a machine, which is the honest state) → S-8. Then RANK 10 (seconds)
and RANK 9 (a download and a closed-form refit). The ME-LSTM ladder (C1) is worth ~9 h only if
RANK 10 leaves the tail structural **and** RANK 9's enlarged frame re-measures E1 as rising under
the default ladder **and** S-6 says gauged. Three conditions, none met today.

**Prominently, as instructed: torrent's hard stops are NA on main.** Any torrent training result
produced before RANK 6 lands — including tonight's, had one run — cannot be trusted, and the
report of such a run must say so in its first line rather than in a footnote.

---

## 8. Sequencing — what runs in parallel, what waits, and the first two weeks

Collision groups (items sharing files run serially):

- **fray-frame**: RANK 3 → 8 → 12 → 11 → 15 (all touch the unseen-year trainer; RANK 3's PR owns
  it). RANK 5 (fray repin) and RANK 16-fray in parallel with the frame work on separate files.
- **chokepoint-gates**: RANK 1 and RANK 16-chokepoint (bindings, reports) in parallel; RANK 7
  after S-4; RANK 13 in parallel with all of it (its own runner, forward passes only); RANK 2 is a
  signature.
- **torrent-arming**: RANK 4 now; RANK 5 (torrent repin) → RANK 6 → S-8 → RANK 10 → RANK 9.
- **fleet**: S-10 (token) any time; S-14 (durable panels) before anything else in chokepoint.

Standing constraints carried: ledgered reads HELD except by S-1; ≤ 2 concurrent foreground
trainings fleet-wide (only chokepoint's in-flight run and, later, RANK 3 qualify); prereg is the
first commit of any new instrument; every fit reports fragility on the declared unit;
`module.__file__` asserted in every driver; regeneration never restamp; every operand of a
verdict comparison tied; a same-block artifact is not an independent witness.

**Week 1 (signatures first, then zero-compute measurement):** S-10, S-14, S-5, S-2, S-3, S-6,
S-8, S-9 on the signatory's desk with this document. Agents: RANK 4 (torrent interval — minutes),
RANK 1 (D6 + split of record, pending S-2 text), RANK 16 hygiene in all three, RANK 5 repins
re-measured, RANK 13 prereg + smoke timing. Read the in-flight chokepoint result under §7.2.

**Week 2 (frame work):** RANK 3 under S-3; RANK 6 under the repin; RANK 7 under S-4; RANK 10
under S-8; RANK 9's download started under S-9. RANK 2 whenever S-1 lands.

**After:** RANK 8, 11, 12, 15 on fray's new frame; RANK 14 after S-6; C1 only if §7.3's three
conditions hold.

---

## 9. Risks the signatory should see in one place

1. **The measurements exist on one laptop.** Both panels (S-14). Every chokepoint gate refuses
   correctly from a clone; fray's run reproduces only by transporting a physical file. Permanent,
   honest, total refusal is the failure mode.
2. **A powered frame finally clears zero for a ~+16 lb/ac fray model and it is promoted into an
   avoided-loss product whose only measured trigger discrimination covers zero (J = 0.12
   [−0.06, +0.30]) and whose only measured coverage fails (0.7738 vs 0.80).** A decidable point
   forecast without a coverage-holding interval is a persistence forecast with a confidence it has
   not earned. RANK 8 must land with RANK 3, not after it.
3. **Chokepoint's operator-facing defect is coverage, not MAE**, and swapping point predictors
   (S-1) does not fix it — chronos-2 is 13/28 corridors below nominal vs the served 10/28. RANK 7
   is not optional if the product is sold as avoided loss.
4. **E1 on chokepoint is a hard stop with a 1-in-18 chance of sitting on the other side of its
   own threshold.** A halt that did not fire at 5.45% is "no halt at this replicate count."
5. **CLAUDE.md and `.mlkit/repo.toml` disagree on chokepoint and fray** (S-5). Until closed in
   writing, a reader of CLAUDE.md alone concludes both repos are halted.
6. **Torrent is running promotion machinery on a pin with a polarity-blind `skill()`** and no
   stops; its only halt is prose on an unmerged branch. Nothing about the ridge is wrong; nothing
   about it is *established* on the declared unit either.
7. **CI is green nowhere that matters** and a committed summary says it is. Every "CI-parity" claim
   since 2026-08-28 has meant parity with a blessed laptop.
8. **The E-025 decision has been open twelve days across nine rounds of val work.** Until it is
   made, every torrent hour is spent on a task whose bar is undefined.

---

## 10. What this plan deliberately does not claim

- It does not claim any model is close to state of the art. On the definition in §2.2, none is.
- It does not estimate how much skill any (a) item will buy. Those numbers do not exist until
  `mlkit` emits them; the plan states the acceptance criterion and the falsifier instead.
- It does not quote any external figure as "the number to beat"; none is on this task and panel.
- It does not recommend spending a ledgered read on any current frame.
- It does not assume the in-flight chokepoint run's outcome. §7.2 stands either way.

---

## Appendix A — sources

Per-repo reviews: `loop/sota-reviews/fray.md`, `chokepoint.md`, `torrent.md` (2026-09-03), each
listing the committed artifacts it read at `b1800121` / `b834437` / `8964c42b`. Campaign record:
`loop/STATE.md` (last 1,500 lines) and `loop/adjudication3.md` (2026-09-03). Tonight's own
measurements: §0. External URLs with retrieval dates: §2.1 and §0. mlkit check definitions:
`resilient-mlkit` @ `3bf16dd` `checks/decision.py` (D2 `HaltRegion` l.133, D6 l.832–1020),
`checks/economics.py` (E1 `FLATNESS_EPSILON = 0.01`, l.187–275), as read by the reviews.

## Appendix B — the figures most likely to be misquoted, with their exact operands

| figure | value | where | what it is NOT |
|---|---|---|---|
| fray unseen-year skill | +22.811 lb/ac (VAL, five years) | `unseen_year_track_fit.val.json` | not promotable; block CI [−1.289, +41.704] |
| fray effect size | +16.570 mean, block CI [11.123, 21.932] | 45-origin backtest, same artifact | may not promote (TRAIN rows, config selected on VAL) |
| fray D2 | −0.945 [−4.239, +2.441] | mlkit decision, re-driven 2026-09-03 | a wiring placebo on the gridMET join, not on the selected model |
| chokepoint served skill | +0.143424 [0.107288, 0.177464] at h=7 | `daily_flow_test.json` | not chronos-2; not h=14 |
| chokepoint best VAL | chronos-2 +0.175749 [0.147470, 0.202902] at h=7 | `foundation_full_val_ladder.json` | VAL only; never served; paired vs hgb_d3 on the full grid is NA |
| chokepoint D2 | −0.0034459 [−0.0047494, −0.0023532] | mlkit decision | excludes zero; PASS only under the declared one-sided region |
| chokepoint E1 | gain 0.07553 (point) | mlkit economics | refits resampled → [−0.004, +0.266], P(flat) 5.45% |
| torrent record | median NSE 0.4520685140972679 (VAL, 65 basins) | `linear_reference_val_recheck.json` | a point estimate; no basin-block interval; mean −2.949 |
| torrent E1 | −12.867% (point) | #174 | interval [−21.64%, +2.51%] contains the bar; not bound in mlkit on any branch |
| torrent D2 | NA on main | `.mlkit/repo.toml` | the branch placebo that existed was inert by construction |
