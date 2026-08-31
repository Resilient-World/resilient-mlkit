# Changelog

All eight model repos pin mlkit by git ref. Until now that ref was
`branch = "main"`, which means every commit here reached every repo the next
time anyone ran `uv lock` — an instrument change arriving as ambient drift.
Tags exist so that an instrument change is a deliberate, reviewable upgrade
instead.

Versions follow the shape of the risk to consumers, not the size of the diff:

* **major** — an existing check changes verdict on unchanged code.
* **minor** — a new check exists, or a report or CLI surface changes.
* **patch** — a defect in the instrument is fixed with no verdict change.

## v0.5.0 — 2026-08-29

Not yet tagged; the session lead cuts it after the adopters' verifiers pass.
The heading is written at the version the code declares.

**A retraction first, because it is the reason this entry reads differently.**
These notes were written on `feat/r10-served-contract` (PR #6), where the
release really was one new check and nothing else, and they said so in a
sentence asserting that no check's verdict moved. PR #7 then merged into the
same `main` (`21f7e6f`, landing after `9118b0e`) the non-finite repairs that
`docs/ESCALATIONS.md` E-M09 and E-M10 record, and that sentence stopped being
true before the tag was cut. It is withdrawn here rather than quietly dropped,
and `tests/test_version_declaration.py` now FIRES on it: the newest entry may
not restate it, and must name at least one of the checks whose verdict moved.

### R10 `FABRICATED_DEFAULTS` checked mlkit's word list, not the adopter's metrics (E-038)

**R10 changes verdict on unchanged repo code in three of the eight repos**, so
this belongs to the same major event as the seven checks below. Driven at every
repo's REMOTE main: `surge` (`8b71343`) and `blackout` (`141108c`) move PASS →
NA; `arabica` (`f659de5`) moves PASS → **FAIL** on a real finding. The other
five stay FAIL with every pre-existing finding intact at the same line, same
symbol, same severity — 0 lost and 0 severities changed across all eight.

**What was wrong.** `is_measured_name` keyed on `MEASURED_TOKENS`, a literal
list of words inside the check, and that list was silently also the entire
universe of names R10 would ever look at. A metric published under any other
word was never read, and R10 said PASS.

The cost is visible in surge's own source, not in the abstract. Of the twelve
public metric callables in `src/resilient_surge/evaluation/metrics.py`, the
word list saw eight and was blind to four — `peak_timing_error`,
`peak_magnitude_error`, `false_alarm_ratio`, `aal_bias`. In that same file
`f1_score`, `iou` and `hit_rate` raise `Unmeasured` on a 0/0 denominator, and
`false_alarm_ratio` returns `0.0` — a perfect no-false-alarm score reported
from nothing — on the identical degeneracy. **The repair had stopped exactly
where the word list stopped.** Spelling defeated it too: `csi` is IN the list
and `critical_success_index` never reaches it, because the tokeniser splits it
into `critical`/`success`/`index`.

**What changed.** `core/metric_registry.py` derives the universe from the
ADOPTER: every callable in the trees the repo declares under `[source]` that
arithmetically computes a number from its own parameters. No name list is
involved, so no rename evades it — the anti-rename control generates its metric
name from `secrets` at drive time and no edit to any vocabulary can satisfy it.

**Three verdicts, structurally distinct.** A finding at a name mlkit's
vocabulary knows is a FAIL exactly as before. A finding whose only measured
name came from the adopter's registry is `UNCLASSIFIED_NAME` and renders **NA
with the name quoted** — `satisfies_a_gate` reads polarity off the vocabulary,
so mlkit cannot claim a literal at a name it does not know is the value that
passes the gate, and `calculate_payout` returning `0.0` below its trigger is
correct domain behaviour. Before this, that case was SILENCE. A derivation
whose own anchor probe fails also renders NA.

**Measured at all eight remote mains, 2026-08-30.** Registry size, and how much
of it mlkit's vocabulary already knew: arabica 157 / 4, torrent 148 / 6, choco
138 / 4, chokepoint 110 / 1, blackout 109 / **0**, surge 103 / 7, triage 103 /
1, fray 50 / 1. **R10 was checking none of the 109 names blackout computes
figures under, and one of chokepoint's 110.** Fleet finding delta: 0 lost, 0
severities changed, 84 added — 81 in the new NA lane and 3 in the FAIL lane,
each named in `docs/ESCALATIONS.md` E-M18. New names that surfaced include
`false_alarm_ratio`, `critical_success_index`, `missed_detection_rate`,
`aal_bias` and `peak_magnitude_error` in surge; `_montiel_olea_effective_f =
0.0`, a weak-instrument F statistic, in chokepoint; and
`clr_loss_fraction = ....get("clr_loss_fraction", 0.0)` in arabica, a
coffee-leaf-rust loss fraction defaulting to "no rust", which is the arabica
flip.

**A limit, stated:** a computation performed entirely inside a call
(`float(np.divide(fp, fp + tp))`) leaves no arithmetic behind and derives no
name. Pinned by `test_residual_a_metric_computed_inside_a_call_is_still_invisible`,
which fails the day it closes.

### R11 `FABRICATED_TARGETS` was defeated by naming; it fires on four records it could not see

**R11 changes verdict on unchanged repo code in two repos**, so this is
another **major** entry by the scale at the top of this file. Measured over
every `.py` file in all fourteen `resilient-*` checkouts, 3,385 files walked:
findings go from **0 to 4**, resilient-arabica 0 → 1 and resilient-surge
0 → 3. Every other repo is unchanged at 0. All four were inspected one by one
and all four are real; none is an over-fire.

R11 asked whether the STRING beside a number sounded observed. Two ways past
that, both used in the fleet:

* **An opaque product name.** `ERA5LandBaselineLoader.iter_grid` in
  resilient-arabica draws all eight of `t2m, tmax, tmin, precip, rh, vpd,
  srad, wind` from `self.rng` and stamps the record `source="era5_land"`,
  which tokenised to `{era5, land, era5land}` — neither claim vocabulary, so
  OPAQUE, so silent. That repo recorded it as an honest negative in its E-051
  and left it standing, because the check as written had nothing to say. The
  same escape was open to any synthetic loader willing to name itself after a
  real product, and resilient-surge had three: `fetch_ntslf`, `fetch_bom` and
  `fetch_jcomm` each return `np.random.normal(...)` as `water_level_m`
  stamped with the name of a real tide-gauge network.
* **Stamp both.** A record declaring simulation in any provenance field was
  exempt even while another field claimed observation, and the module said so
  in its own docstring. Stating an evasion does not close it. arabica
  pre-registered `synthetic_weather_real_isd_fallback` as a repair label and
  its own control rejected it.

The repair is not another token in a list — the next loader will be called
something else. R11 now asks whether the values came from an RNG and whether
the label is contradicted by the construction it labels. A source stamp
naming an external dataset, on a record whose every value was manufactured in
this process (RNG draws, literals, literal-defaulted knobs, arithmetic over a
loop index), is `CONTRADICTED_SOURCE`. A value or a record that both claims
observation and declares simulation is `CONTRADICTED_STAMP`. The rule that
fired is carried on every finding, in the FAIL reason and as a new column in
`reports/fabricated_targets.md`.

**What did not change, and it is the half that matters.** An honestly-labelled
fixture is still silent, and the negative controls prove it against the same
constructions: byte-identical to the era5 positive control but stamped
`era5_land_shaped_synthetic_grid`; the `source="noaa_coops_synthetic"` loader
sitting twenty lines above `fetch_ntslf` in the same shipped surge file; a
real loader that reads a dataset and jitters it, wearing `source="era5_land"`.
That last one was written as a control and **fired**, which was a genuine
false positive in the first cut of this change — `_is_random_draw` answers
"contains a draw anywhere", so `float(row.t2m) + rng.normal(0, 0.01)` read as
manufactured. Fixed at the root, in two places: the manufactured-value rule
asks whether a node IS a draw rather than contains one, and the pass is no
longer seeded from the taint map.

Two tests in `tests/test_fabricated_targets.py` asserted the stamp-both
exemption and now assert the opposite. They were the specification of the
defect, not a threshold loosened to go green: no gate file, no holdout and no
range was touched, and the other twenty-three tests in that file are
unchanged and still pass.

### The principal event: seven checks change verdict on unchanged repo code

By the scale at the top of this file that is a **major** release, and it is
what a consumer upgrading to this version needs to read first. In every case a
binding reporting a figure that does not exist — `nan` or `inf`, which is what
a pandas or numpy count becomes when a groupby or a reindex misses a kind, and
what a diverged training loss reports — was waved through by the comparison
written to catch it.

| check | what now FAILS that used to PASS | recorded in |
|---|---|---|
| D2 | a `placebo_test` estimate or interval that is NaN | E-M09 |
| E1 | a `scaling_probe` curve carrying a NaN or infinite point | E-M09 |
| T2 | a loss curve like `[2.0, nan]`: `nan > 0.1 * first` is False, and so is `first <= 0` | E-M10 |
| R2 | the same input; R2 delegates to T2 and inherited it verbatim | E-M10 |
| D3 | `empirical = nan`: `abs(nan - nominal) > tol` is False | E-M10 |
| E3 | `gpu_util = nan`: `nan < GPU_UTIL_FLOOR` is False | E-M10 |
| R4 | `computed = nan`: `abs(nan - want) > tol` is False | E-M10 |

D2 and E1 are hard stops, so until this release both hard stops were unable to
fire against a measurement that does not exist. Two of the others are worse
than a plain hole: `min(nan, x)` is `nan` in Python, so the subject-declared
tolerance clamps in D3 and R4 — written so a binding may ask for something
stricter but never looser — accepted a declared `tol` of NaN as the loosest
tolerance there is. A repo could set its own pass mark to "accept anything"
using the mechanism built to stop it.

**No threshold was moved.** `FLATNESS_EPSILON`, `GPU_UTIL_FLOOR`,
`MAX_COVERAGE_TOL`, `MIN_COVERAGE_N`, `MAX_METRIC_TOL` and `MIN_HOLDOUT_GROUPS`
are byte-identical to `v0.4.0`. The controls are in
`tests/test_decision_controls.py`, `tests/test_economics_controls.py` and
`tests/test_nonfinite_controls.py`; the last of those was run against the tree
before the repair, where 13 of its 25 cases failed.

**What it costs the portfolio, and who pays it.** Any committed PASS for D2,
E1, T2, R2, D3, E3 or R4 was recorded under a check that could not fire on a
non-finite measurement, so it does not distinguish "measured and fine" from
"measured nothing". Re-running those phases across the eight repos and voiding
the verdicts that move is a portfolio re-measurement and a records change,
reserved to the signatory: E-M10 records it as recommended-and-not-run, and
nothing in this release does it.

**Why the number is still `0.5.0`.** Not because the reason above is minor —
because `0.5.0` is already what a major bump from `0.4.0` looks like under the
reading E-M08 recorded (on a `0.x` line the minimal reading of major is the
leading nonzero). The number this entry was written at does not move; its
justification does. It was claimed here as a minor release for R12, and it is a
major release for the seven checks above, with R12 the minor half of the same
tag. Whether this line's major should instead be `1.0.0` is the open question
E-M08 and E-M09 record, and it is the signatory's to settle — restated as
E-M11. **No tag is cut from this branch.**

### R12 `SERVED_CONTRACT`, the minor half of the same release

A new check exists, which is a **minor** event by the same scale, and it is
described in full below. It does change one thing every repo sees: the gating
set goes from 26 checks to 27, so READY now requires one more PASS. That is
what adding a gating check means, and the tripwire in
`tests/test_promotion_state.py` had to be edited by hand to permit it. A test
also asserts that the readiness order with R12 removed is byte-identical to the
order before that branch.

### One definition of "served" — `core/served.py`

The fleet had converged on one definition of *ready* and grown three of
*served*. Measured 2026-08-29:

* `resilient-chokepoint/src/resilient_chokepoint/mlops/champion_challenger.py`
  (267 lines) and `resilient-torrent/src/torrent/mlops/champion_challenger.py`
  (160 lines) — same filename, different SHAs, overlapping-but-not-identical
  APIs;
* per-product serving modules in chokepoint, fray and triage;
* eleven further files across fray and chokepoint carrying promotion logic.

The divergence was not cosmetic. `torrent/.../champion_challenger.py:128` maps
a zero baseline to a deviation of `0.0`, which clears the tolerance and
**promotes**; `chokepoint/.../champion_challenger.py:209-218` returns `NA` on
the identical condition. And two implementations hold the verdict as a bare
bool — `torrent ChallengerResult:39` (`promote`) and
`fray registry/models_of_record.py:177` (`clears`) — so an unmeasured
comparison and a measured loss are the same value, distinguishable only by
surrounding prose.

`core/served.py` is the **intersection** of what the four implementations
actually do, not a superset:

* `ServedModel` + `verify_at_load` — self-hash recomputed and refused on
  mismatch; pinned data hashed on disk and refused on mismatch.
* `ChallengerDecision` — `PASS` / `FAIL` / `NA`, where `promotable` is a
  *property* of the status and cannot be set apart from it, an `NA` is refused
  if it carries any skill number, and a `PASS` is refused if it lacks one.
* `ServeArms` — the arm policy as **data**. triage and fray close `test` and
  refuse it; chokepoint *requires* `test` to decide. A contract hard-coding
  "test is forbidden" would make a correct gate unadoptable.

Deliberately absent: a metric (five appear across the fleet as *the* decision
metric), and a router (`ShadowRouter` exists twice with opposite production
semantics — chokepoint's returns the champion's result, torrent's returns the
challenger's — and three repos have none).

**The digest is the fleet's, not a new one.** `canonical_payload_sha256` is
byte-for-byte the computation the three serving modules already perform.
Verified by execution, not by reading: `scripts/verify_served_hash_parity.py`
recomputes the digest for every committed champion artifact in the portfolio
and compares it to the hash each repo's own local function wrote. Measured
2026-08-29 on python 3.14.6, **5 artifacts compared, 5 matched, 0 differed**
(fray ×2, chokepoint ×2, triage ×1; the other three repos pin no artifact yet).
A contract that changed the digest would have invalidated all of them, and the
fix would have looked like "update the recorded hash".

### R12 `SERVED_CONTRACT` — no local re-implementation of the served model

R11's question one layer up. Walks every `.py` in the repo (serving code lives
under `scripts/` and `benchmarks/` in three of the target repos, outside the
declared `[source] trees`) and reports a file that decides a contract clause
without importing `resilient_mlkit.core.served`. The exemption is an **import**,
at one level of indirection — the depth R11 already uses for taint through
module-local helpers.

**Four detectors were narrowed or deleted by measurement.** Every one of these
was found by running the scanner across the eight repos and reading what it
named, not by reviewing it:

* SERVE_ARM matched `arm` as a **substring** and reported four files across
  choco, arabica and blackout on the words *farm* (`farm_size_col`,
  `farm_panel_parquet_path`) and *warming* (`_IPCC_WARMING`). Now token-bounded,
  and an inline refusal must additionally name a train/val/test arm or a
  declared arm policy — `chokepoint/.../forecasting/corridor_pooling.py:525`
  asserts an *ensemble's* arm ordering, which is a different sense of the word.
* SELF_HASH required the `json.dumps` to sit inside the `sha256` call's own
  subtree, so assigning it to a local first defeated the detector. The evasion
  was a newline; the rule is scope-based now.
* SELF_HASH also now requires the payload's **own hash field to be excluded**
  before hashing. Without that it reported `surge mlops/reproducibility.py:34`
  and `governance/audit_trail.py:176`, which fingerprint a run config and an
  audit row. A digest stored inside the object it covers must omit itself;
  nothing else needs to, and that is precisely the clause.
* The SELF_HASH **function-name list was deleted**, not trimmed. It found
  nothing the shape rule missed and produced two false positives on names
  alone: `torrent api/routers/v4_avoided_loss.py:29` (`_canonical_hash`, a
  request cache key) and `blackout mlops/checkpoint_sidecar.py:87`
  (`artifact_sha256`, a chunked file hash).

**And one blind spot was closed the same way.** The name vocabulary was silent
on `arabica registry/backbone_promotion.py:40` — *"whether challenger backbone
model qualifies for promotion over champion"* — because nobody had listed
`evaluate_backbone_gate`. Chasing names loses. The rule is now structural: a
function emitting both `"PASS"` and `"FAIL"` whose **declaration** (module
path, class, own name) sits in a promotion context. Declaration and not body —
matching any identifier in scope reported two validation scripts that merely
*call* a helper with `gate` in its name.

R12 across the eight repos, 2026-08-29, python 3.14.6, from
`reports/served_contract_fleet.json`:

| repo | verdict | findings | files named | walked |
|---|---|---|---|---|
| choco | FAIL | 2 | 1 | 398 |
| arabica | FAIL | 4 | 1 | 375 |
| fray | FAIL | 22 | 4 | 217 |
| torrent | FAIL | 7 | 2 | 533 |
| chokepoint | FAIL | 30 | 7 | 272 |
| surge | PASS | 0 | 0 | 328 |
| triage | FAIL | 14 | 7 | 416 |
| blackout | FAIL | 2 | 2 | 241 |

Both `champion_challenger.py` files are named, as is every `promotion_gate.py`
and all three per-product serving modules — the motivating finding, located
mechanically.

**surge's PASS is adjudicated, not assumed.** The pre-registration for this
round recorded that a PASS would be evidence of a blind scanner rather than of
a clean repo, because nothing has adopted the contract yet. surge has no
champion/challenger comparison at all: `grep -rl` for
`champion|challenger|promotable` over its `src/` and `scripts/` returns
nothing, and `mlops/model_registry.py:109` `promote()` is a registry *stage
transition* — it moves a version to production and decides nothing. surge
PASSes because it has no served-model contract to converge, which is a
different fact from having adopted one, and its first serving path will need to
import the contract.

**No adopter repo was edited.** `resilient-triage` is a colleague repo and was
read-only throughout. `scripts/scan_served_contract.py` exists precisely so the
fleet can be measured without the phase runner writing its finding lists into
the repos it measured.

### Committed reads: `mlkit portfolio` can no longer quote a number that is not in git

A **report and CLI surface** change, which is minor on the scale at the top of
this file, added to this entry because `v0.5.0` is not yet cut. No check's
threshold moved and no check in `PHASE_ORDER` changes verdict: nothing in
`checks/` reads through `core/artifact.py`.

`core.artifact.load()` obtained artifact bytes with `path.read_bytes()` and then
RECORDED whether git agreed — `committed_at_head` and `dirty` were computed, put
on the ref, and printed in `fleet.provenance_block`'s own column. `docs/ESCALATIONS.md`
E-M12 is what that disclosure bought: the `choco` row of
`portfolio/FLEET_VERDICTS.md` — candidate, score, split, baseline score,
test-arm-spent — was read out of `models/observed_production_head.meta.json`, a
file committed on no ref at all in that clone. The provenance column said `NO`
beside a number, and a reader reads the number first.

Bytes now come from `git cat-file blob HEAD:<relpath>`, and the two recorded
facts became the input to a refusal instead of a footnote:

| case | before | now |
|---|---|---|
| committed, clean | number, flagged `yes` | number — byte-identical, same sha256 |
| dirty against HEAD | working-tree number, flagged `YES` | `NA (not committed at HEAD: …)` |
| on disk, on no ref | working-tree number, flagged `NO` | `NA (not committed at HEAD: …)` |
| in no tree at all | `NA (artifact not found …)` | unchanged, and kept distinct |

**What a consumer sees.** Any fleet row whose declared artifact is not committed
in the repo that owns it turns from a figure into an NA carrying the file's
path. As of the last read that is choco's `main:` artifact and no other. The
number was never fetchable by anyone reading the table; what changes is that the
table now says so in the cell rather than in a column beside it.

**The escape hatch cannot escape.** `load(..., allow_dirty=True)` and
`mlkit portfolio --allow-dirty` read the working tree for local diagnosis and
mark everything that descends from the read — `ArtifactRef.allow_dirty_read`,
`Cell.allow_dirty`, `CheckResult.evidence["allow_dirty_read"]`. The marker
survives derivation in `_compare`, and four paths refuse it:
`CheckResult.__post_init__` for a PASS, `portfolio.resolve()`,
`fleet.markdown_table()` and `FleetRow.to_dict()`. The CLI prints cells one per
line, writes nothing and exits 2.

**`core/result.py` gains a third structural invariant** beside PASS-requires-evidence
and NA-requires-reason: a PASS may not rest on an allow-dirty read
(`UncommittedRead`, a subclass of `FabricationError` — a figure in nobody's git
history is unfalsifiable in the same way as one nobody measured). The six-status
enum is unchanged and no existing invariant was relaxed.

**`mlkit portfolio`'s provenance table gains a `read from` column** (`HEAD` or
`working tree`). The `Repos as they were read` table is untouched.

Controls: `tests/test_committed_reads.py`, 20 in five pairs, each proven by
mutation — reverting `load()` to working-tree reads fails 7, disabling
`refuse_uncommitted` fails 3, dropping the PASS invariant 1, laundering the
marker in `_compare` 1. Four controls in `tests/test_fleet.py` that rewrote an
artifact without committing it now commit it, and the two git-standing controls
assert the refusal on top of the flag they already asserted; assertions were
added and none removed.

`portfolio/FLEET_VERDICTS.md`, `portfolio/FLEET_VERDICTS.json` and
`portfolio/MODEL_QUALITY.md` are byte-identical to `main` — the fleet was not
re-run, and re-measuring it under the new read semantics is E-M10's
signatory-reserved work.

## v0.4.0 — 2026-08-28

Not yet tagged. The heading is written at the version the code declares, not
retitled from "Unreleased" after a tag is cut — that retitling step is what
went missing at `v0.3.0`, and `tests/test_version_declaration.py` now fails the
suite whenever the newest heading here and `resilient_mlkit.__version__`
disagree.

**Why `0.4.0` and not the `0.3.1` `docs/ESCALATIONS.md` E-M08 proposed.** That
proposal predates this round's content. The scale at the top of this file says a
**major** release is one where "an existing check changes verdict on unchanged
code", and two checks below do exactly that. On a `0.x` line the minimal reading
of major is the leading nonzero, so `0.4.0`. Whether this line's major is
`0.4.0` or `1.0.0` is not written down anywhere and is the signatory's to
settle — recorded in E-M08 rather than decided here.

### The version is declared once

`pyproject.toml`, `resilient_mlkit/__init__.py` and `resilient_mlkit/cli.py`
each carried their own `0.2.0` literal, and `v0.3.0` was tagged with all three
still unbumped (`docs/ESCALATIONS.md` E-M08). `pyproject.toml` now reads the
value through `[tool.setuptools.dynamic]` and `cli` imports it, so there is one
literal in the repo. Verified by execution against this branch: `pip install -e
. --no-deps` then `pip show resilient-mlkit` reports `Version: 0.4.0`, and
`mlkit --version` prints `mlkit 0.4.0`.

The `v0.3.0` tag is unchanged and still ships `0.2.0` in its own tree; that is
recorded in the entry below and is not repaired by this bump.

### Two silent defects in readiness checks, found by writing their controls

Neither was found by reading the code. Both were found by writing a control
pair — a case the check must fire on beside one it must stay silent on — and
watching the positive case pass.

**R3 counted the letters of a string as sites.** `set(map(str, v))` accepts a
`str` and iterates it by character, so a `splits` binding returning `{"train":
"abc", "val": "de", "test": "fg"}` was reported PASS with `n_train=3, n_val=2,
n_test=2`: three disjoint "groups" above the holdout floor, and nothing about
the data measured. It failed loudly on long strings, which share characters, and
silently on short ones — so it only misbehaved where it did damage. R3 now
refuses a `str` or `bytes` split by name rather than coercing it; tuples, sets
and generators are unaffected.

**R5 did arithmetic on proportions as though they were row counts.** `int()`
truncates, so `{"real": 1.5, "synthetic": 0.5}` in `val` cleared the taint test
(`int(0.5) == 0`) and then satisfied "at least one real row" (`int(1.5) == 1`):
a val split one third simulated, reported PASS against the one invariant
`CLAUDE.md` calls non-negotiable. `{"real": 100, "synthetic": -5}` passed for the
same reason. R5 now validates the histogram as whole non-negative row counts
first and refuses what it cannot read; `100.0` and `"100"` are still accepted, so
a counter arriving as float64 or out of a CSV cell is unaffected.

Both are verdict changes on unchanged repo code — a repo whose binding returns
either shape moves from PASS to FAIL. Neither shape can produce a correct pass,
so this is a defect repair rather than a tightening, and no repo is known to
report either. Recorded here so an upgrade is not a surprise.

**A third, of the same class, found by adversarially re-running the above.**
The count guard those two defects produced reads `float(raw)` and then tests
`n != int(n)`. `float("nan")`, `float("inf")` and the strings `"nan"` / `"inf"`
all survive the `float()` call and reach `int()`, which raises `ValueError` for
a NaN and `OverflowError` for an infinity — out of the check, past its own
diagnosis. `math.isfinite` is now tested first, so those four shapes are
refused as malformed counts naming the split and the kind. No false PASS was
ever reachable here: the CLI runner converts a raising check into a FAIL. The
defect was in the reason, which named an interpreter error instead of the split
and kind at fault — the exact behaviour the guard was written to end. NaN is
what a pandas or numpy count becomes when a groupby or a reindex misses a kind,
and this fleet already uses `float('nan')` as an explicit "could not read this
figure" sentinel, so it is a live shape rather than an argument about types.
A large finite count (`10_000_000_000`) still passes, so the refusal is of
non-finiteness and not of magnitude.

### Coverage for the checks that gate promotion

`tests/` held eight files against 29 modules, and the gaps were not where a
coverage percentage would have pointed. R3 and R5 had no tests at all; R11 had a
thoroughly tested scanner inside an untested check; and `portfolio.resolve` —
the function that turns results into READY-TO-TRAIN — had none.

Five new suites, every check in FIRES/SILENT pairs, because a check that fires
on everything is as useless as one that fires on nothing and only the pair tells
them apart. The pairings that carry the weight:

* a synthetic row in `val` FIRES / a wholly synthetic `train` split is SILENT —
  simulated training data is legitimate, and a check that fired on it would be
  switched off, taking the val/test invariant with it;
* a one-group holdout FIRES / a two-group holdout is SILENT — the floor is what
  stops holdout narrowing arriving as a green check;
* R11 FAILS on a fabrication under `scripts/` while R10 PASSES on the same repo
  — measured on one fixture, and it is R11's whole reason for existing;
* an NA beside an ESCALATED is IN-PROGRESS / an ESCALATED alone is
  AWAITING-SIGNOFF — falsified by inverting the precedence in `portfolio.py`,
  which turned both controls red, and restored.

### `mlkit portfolio` — four NA cells were the adapter, not the repo

Every `NA` reason was re-read against the repo's committed artifacts and
classified: field genuinely absent, or adapter looking in the wrong place.
Measured on the fleet as checked out on 2026-08-29: **cells NA-with-reason 9 →
5, cells measured 99 → 103**, rows unchanged at 12. `fray/forecast_available`'s
test-arm count, `torrent/ridge-vs-melstm-val`'s split and both `blackout` rows'
model of record were all present in artifacts the row already named or sat
beside. The five that remain are genuinely absent and say so more precisely.

### `mlkit spine` — the 16 drifts classified

No behaviour change; the classification is recorded in `docs/ESCALATIONS.md`
E-M04. All 16 are an unsynced spine and none is a repo diverging, on two
measured grounds: one deployed sha256 per file shared by all eight repos, and
every changed line traceable to a spine-side commit here. Nothing was synced —
that is a fleet-wide write.

## v0.3.0 — 2026-08-28

Tagged at `d08d85e` (the merge of PR #3). This entry was retitled from
"Unreleased" after the tag was cut; the tag itself is immutable and its tree
matches what is described here. One known discrepancy in the tag, recorded
rather than repaired: `pyproject.toml` and `cli.__version__` inside `v0.3.0`
still read `0.2.0`, so artifacts generated from that tag stamp
`mlkit_version: 0.2.0`. The `mlkit_git_sha` field in every generated artifact
is the reliable identity. Whether to bump and cut a corrective tag is the
session lead's call — see `docs/ESCALATIONS.md` E-M08.

Two new read-only surfaces. Neither changes any check's verdict, so a repo that
upgrades sees no gate move.

### `mlkit portfolio`

Regenerates the measured columns of `portfolio/MODEL_QUALITY.md` by reading each
repo's committed artifacts through a declared adapter, rather than by hand. A
figure that exists in exactly one other place has no error detection; a wrong
digit is indistinguishable from a right one. The generated table carries, for
every cell, the artifact path, its sha256, whether git has those bytes at HEAD,
and — where the artifact does not carry the column — `NA` with the reason.

Repos do not share an artifact schema and are not made to. Each declares its own
pointers in `fleet_adapters.py`. Labels (metric, split) are corroborated
mechanically against the pointer they are declared for, so a label that drifts
from the quantity it names reports NA instead of mislabelling a real number;
`036683e` additionally rejects a `Declared` label that is itself a bare figure,
closing the door that guard left open for a typed-in number.

**An asserted verdict is not a measured one** (`1ca63dd`, found by adversarial
verification of the branch before merge). Three rows point `beats bar?` at a
boolean the repo publishes itself, and the first reader passed it straight
through: a `true` rendered beside `score: NA`, and a `true` contradicting the
row's own two figures, both silently. Fixed at the root in `core/fleet.py`: an
asserted verdict is admitted only when the score and baseline on that row
reproduce it, and is otherwise NA with the reason — strictly more conservative,
since corroboration can turn an asserted pass into NA and never an NA into a
pass. Measured on the real fleet at merge: no verdict changed; all three
asserted booleans are reproduced by their rows' figures, and the artifact's
`source` strings now record the corroboration. Five FIRES/SILENT controls in
`tests/test_fleet.py`.

### `mlkit spine`

Reports canonical-spine drift per repo, with five verdicts that are kept
distinct on purpose: `IN-SYNC`, `DRIFTED` (banner present, bytes moved — the
next sync reverts it), `ABSENT`, `UNCLAIMED` (a file WITHOUT the banner on a
canonical filename, which the syncer will not touch, so it diverges
permanently), and `NO-SPINE-SOURCE`. **Report-only: it never writes into a model
repo.** `scripts/sync_spine.py` remains the only writer and now imports its
declaration of "canonical" from `core.spine`, so the two cannot disagree.

### Also

* `pytest-timeout` declared and a 180s `timeout` set in
  `[tool.pytest.ini_options]`, with `tests/test_pytest_timeout_active.py`
  proving by execution that it is enforced rather than inert.
* `pytest` and `numpy` declared in a `test` extra. Neither is a runtime
  dependency and neither reaches the eight repos, which install mlkit without
  the extra.
* `.github/workflows/ci.yml` — ruff, mypy, and pytest on 3.11 and 3.12.
  **Unverified: GitHub Actions is failing account-wide on billing and this
  workflow has never run.**
* mypy is now clean over the package (25 files) and ruff passes at its
  defaults; four pre-existing type errors and one unused import were fixed.

## v0.2.0 — 2026-08-28

Two blind spots, both proven by real incidents, both closed.

### What changes for a repo that upgrades

**A new gating check, R11, can turn a green readiness phase red.** That is
the point of it, and it is the reason this is a tag rather than a push to
main. Read `reports/fabricated_targets.md` before assuming a regression.

**`READY-TO-TRAIN` now requires 26 gating checks, not 25.** The portfolio
table's readiness column is now `R(9,10,11,1-8)`.

**`reports/readiness.md` may stop being regenerated.** If mlkit is run from
an interpreter that cannot import the repo's own bindings, R8 now reports
`NA`, leaves the existing report untouched, and writes
`reports/readiness.UNMEASURABLE.md` beside it saying why. This is not a
failure of the repo; run mlkit from the repo's own environment and the report
regenerates as before.

**Nothing needs to change in a repo to adopt this.** No new binding, no new
declaration in `.mlkit/repo.toml`. R11 deliberately does not read
`[source] trees`.

### Added

**R11 `FABRICATED_TARGETS` — no RNG-derived row stamped as observed.**

Detects, by AST analysis in any Python file anywhere in the repo, a value
drawn from a random number generator that flows into the numbers written onto
a data record which is then stamped with a provenance field claiming those
numbers were observed.

The stamp is the defect. The same code stamped `label_origin="synthetic"` is
a fixture and is never reported. `source_id="civ_ccc_regional"` names
something and adjudicates nothing — reported as corroboration, never as the
trigger. Every finding names the specific field and value that make the record
a fabrication rather than an honestly-labelled simulation.

Why it is not part of R10: R10 walks the trees a repo *declares*, and that
list is exactly the surface an author controls. resilient-choco PR #160
shipped five files under `scripts/` — outside the declared trees, outside
that repo's own generated-paths guard, past 51 green tests. R10 would also
have excused them, because it stays quiet inside a file whose *name* declares
it a generator; R11 does not, since the stamp is a claim about the data and
the filename is not.

Runs **before R5** in `PHASE_ORDER`, because R5 counts rows by the very
provenance field R11 shows to be false. An R5 PASS recorded after an R11 FAIL
is a pass counted with a broken ruler.

Writes `reports/fabricated_targets.md`.

**`mlkit env`** — reports, per repo, whether the current interpreter can
measure it at all, before any phase has tried to write over something
measured. Exits 1 if any repo is unmeasurable here.

### Changed

**mlkit refuses to write a binding-dependent report from an environment that
cannot import the repo's bindings.** A python 3.14 with no numpy regenerated
`reports/readiness.md` in at least four repos, replacing measured PASSes with
`ModuleNotFoundError` (resilient-chokepoint `docs/ESCALATIONS.md` E-019).
Every individual result in that run was honest; the composite was still a lie,
because a readiness report reads as a statement about the repo when that one
was a statement about the shell.

"Environment unmeasurable" is now a distinct fact from FAIL. The prior report
is preserved byte for byte and the refusal is recorded in its own file.

The discriminator needs no list of "real" packages: a missing module that
resolves to a path inside the repo is the *repo's* defect and stays a FAIL; one
that does not is a dependency absent from the interpreter. Both directions are
controlled — letting "unmeasurable" swallow genuine import defects would be the
same overwrite with the sign flipped.

Two probes, because one has a hole. Bindings in this portfolio import lazily,
so they import cleanly from a broken interpreter and fail only when called:
measured 2026-08-28 from the numpy-less 3.14.6, seven repos read UNMEASURABLE
and **resilient-surge read MEASURABLE at 11/11 bindings imported** — the one
repo in eight the guard would have missed. `assess()` also reads the results
the run already produced, which is what actually happened rather than what
might.

R10's and R11's reports are **not** guarded: they parse source and import
nothing, so they are measured correctly from any interpreter.

**`fabrication.iter_python_files`** takes a `skip` parameter so R11 can widen
the exclusion set for its repo-wide walk without changing what R10 measures on
declared trees. Existing calls are unaffected.

### Measured on this release

R11 across the eight repos, 2026-08-28, python 3.12.13:

| repo | HEAD | files walked | findings |
|---|---|---|---|
| choco | d0a0357 | 398 | 0 |
| arabica | bb69ee2 | 375 | **2** |
| fray | 20ec9f5 | 199 | 0 |
| torrent | 007d9b8 | 528 | 0 |
| chokepoint | 9faa0d3 | 254 | 0 |
| surge | 9eab2fe | 328 | 0 |
| triage | f444308 | 416 | 0 |
| blackout | ed80086 | 241 | 0 |

2,739 files, 2 findings. Both in
`resilient-arabica/src/training/finetune_aurora_coffee.py`, at lines 108 and
167: `CoffeeStationSample` records with 8 of 12 data fields drawn from
`self.rng`, over stations whose own coordinates come from
`_build_synthetic_stations`, stamped `source="weather_real_isd"` and
`source="farm_sensor"`. R10 finds nothing in that file. These are arabica's to
adjudicate, not this instrument's.

The 2,737 files that produced nothing are the population-scale negative
control: precision over recall, because a check that cries wolf gets disabled
and a disabled check still looks like coverage.

### Tests

`tests/` grows from 2 files to 4. Every new check ships a matched pair — the
positive fixture and the same code with the one thing changed that makes it
honest. 105 tests pass (was 91).

## v0.1.0

Initial instrument: 25 gating checks across five phases, R10
`FABRICATED_DEFAULTS`, the shared R5 formula-derivation probe, and the spine
synced into every model repo.
