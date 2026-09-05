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

## v0.7.0 — 2026-09-04

Not yet tagged; neither is `v0.6.0` below. Tag cutting is the signatory's
(E-M08); this heading exists because `tests/test_version_declaration.py`
holds `__version__` to the newest heading, and a new status is a CLI-surface
change, which this file's own scale calls **minor**. Plan v3 §7, items M-1
and M-3 (and M-2 where it lands on the same line).

### M-1 — `Status.UNMEASURABLE`: an armed check whose declared input this machine cannot supply

* **The defect, measured three ways on 2026-09-04.** torrent `main` `d34649f`:
  D2 renders FAIL with the reason "ENVIRONMENT REFUSAL, NOT A PLACEBO FINDING:
  the staged Caravan subset could not be read" — the binding's docstring says
  it chose FAIL because *"mlkit has no NA channel for a binding that raises"*.
  chokepoint `main` `512ab25`: R2/R3/R5/R6 refuse on pin mismatch from any
  clone without the pinned parquet. fray `main` `76f0dde`: E1 raises when the
  NASS extract's bytes differ from the pin. Each is correct fail-closed
  behaviour; each renders as an indictment or as an unarmed stop.
* **What is new.** A seventh terminal status, reason-required (there is still
  no SKIP and no WARN). `core.result.InputUnavailable(reason, input=,
  pin_expected=, pin_observed=)` is the `CredentialRequired` discipline for
  bytes: a binding raises it **only after** it has resolved its declaration
  and reached the byte it cannot read. `cli._run_phase` renders it
  `UNMEASURABLE` with `input` / `pin_expected` / `pin_observed` in evidence
  and never attaches `halt`. Raised at import time it is
  `PrematureInputRefusal` and renders **FAIL** naming
  `PREMATURE_INPUT_REFUSAL` (`Repo.resolve`), because dodging a check is the
  other face of the same trap. Every check that re-raised `CredentialRequired`
  (17 sites) re-raises `InputUnavailable` the same way.
* **What reads it.** `environment.from_results` treats an UNMEASURABLE row as
  it treats a missing third-party module — the run is UNMEASURABLE, with both
  digests in the bindings map — so `report.guarded_write` refuses to overwrite
  a binding-dependent report from such a run (readiness.md today; an
  adopter's hard_stops.md through the same writer). A missing module that
  resolves inside the repo is still the repo's defect and still FAILs.
  `portfolio.resolve` reads it as unmeasured (IN_PROGRESS; never READY, never
  BLOCKED). `mlkit check` exits **3**, not 1. Glyph `U`.
* **`core.arming.arm_state(declared, status)`** — the one definition of
  `armed` / `halt_required` / `indicted` an adopter's hard-stops module
  renders. torrent and chokepoint each typed `armed = status in {PASS, FAIL}`
  and `halt_required = status == FAIL`; both lines read an UNMEASURABLE stop
  as unarmed and non-halting. Exported at the top level with
  `InputUnavailable`.
* **Verdict change on unchanged adopter code: none from this build alone.**
  No adopter binding raises `InputUnavailable` yet; every existing PASS/FAIL
  row renders as before (suite 1195 → 1221, zero assertions removed; the nine
  deleted test lines are the six-status pins, each replaced by a seven-status
  pin, and one fall-through in a test helper that rendered any unknown status
  as ESCALATED — made strict). Adoption rides on each repo's next repin PR.
* Preregistration and controls: `reports/M1_UNMEASURABLE_PREREGISTRATION.md`,
  `tests/test_unmeasurable_status.py` (C1–C9, both directions, plus a
  check-not-dead pair that rebinds the runner clause and shows the status
  vanish).

## v0.6.0 — 2026-09-01

Not yet tagged. `v0.5.0` **is** tagged — annotated tag object `15a188b` on
commit `8517341`, cut 2026-08-31 (`git for-each-ref refs/tags`, this checkout,
2026-09-01) — and the line above this one used to deny it. That denial is
corrected in the `v0.5.0` entry below rather than deleted, for the same reason
the retraction there was written out in full.

**Why this entry exists at all.** Measured on `main` at `6921e9a`, before any
edit on this branch:

    git rev-list v0.5.0..HEAD --count       -> 36
    git diff --shortstat v0.5.0..HEAD       -> 21 files, +5438 -97
    git diff v0.5.0..HEAD -- CHANGELOG.md   -> EMPTY
    git show v0.5.0:src/.../__init__.py     -> __version__ = "0.5.0"
    resilient_mlkit.__version__ at 6921e9a  -> "0.5.0"

Thirty-six commits of check semantics with the release notes untouched and the
version string sitting still on both sides of the tag. `resilient-chokepoint`
pins mlkit at `8517341`, which is that tag; `resilient-fray` pins `c65b2e7`.
Every artifact any of those three trees writes stamps the same
`"mlkit_version": "0.5.0"`, and the checks underneath are not the same checks.
That is E-M08 one level up: E-M08 was three copies of the version inside one
tree, repaired by holding the copies against each other; nothing then held the
version against the release history, so the string could go stale in place.
`tests/test_tag_distance.py` now fires on exactly that state.

**Why `0.6.0`.** By the scale at the top of this file this is a **major**
release — existing checks D3, R11 and the served-contract promotion decision
all change verdict on unchanged repo code, and each is measured below. Whether
major on a `0.x` line means `0.6.0` or `1.0.0` is still not written down
anywhere and is still the signatory's to settle (E-M08); the `v0.4.0` entry
below took the minimal reading — bump the leading nonzero — and `0.6.0` is that
same reading applied to `0.5.0`. It is also the minimum this file's policy
allows, since a new check exists. An agent takes the floor and records the
question; it does not settle it.

**What is NOT claimed.** No adopter was re-measured for this entry. The fleet
verdict tables under `portfolio/` are untouched, and the per-repo consequences
quoted below are the measurements the linked commits made when they landed, not
a re-run. `mlkit portfolio` and `mlkit spine` were not executed for this
release note.

### Existing checks that change verdict on unchanged repo code

* **D3 `UNCERTAINTY_COVERAGE`** (`11a5bcd`, drive `99ec8a2`). The nominal level
  is now read from `.mlkit/repo.toml` `[coverage] nominal` and the binding's own
  `nominal` is adjudicated against it. A binding reporting its own level as the
  standard was PASS and is now FAIL `NOMINAL_SELF_DECLARED`; with no
  declaration it is NA `NOMINAL_UNDECLARED`. `4bd42d6` records a read-only
  survey of the eight adopters at their remote mains on 2026-08-31: three of
  them (`arabica`, `torrent`, `surge`) carry a live D3 row and none of the eight
  declares a level, because until that branch there was nowhere to declare one.
  Two lines of config each repairs it.
* **R11 `FABRICATED_TARGETS`** (`0960974`, `f5cd91c`, `59e9ddf`, `8846aba`).
  Four further spellings of the E-M17 residual-4 stamp now fold, and a stamp the
  scanner cannot read is no longer treated as clean: R11 serves three verdicts,
  and the unreadable case is NA `UNREADABLE_STAMP`, not PASS. The R11 report's
  two counts are split so an unadjudicated row is neither read as a defect nor
  dilutes one. `f5cd91c` measured the over-fire budget read-only across the
  fleet before landing: 0 new findings, 0 gone, and no repo's R11 verdict moved
  on that measurement.
* **The served-contract promotion decision**, `core.served.challenger_decision`
  (`66c456b`, `7884be5`). A metric's direction and domain are DECLARED; an
  undeclared polarity is NA `POLARITY_UNDECLARED` and an out-of-domain
  comparison is NA `IMPOSSIBLE_MEASUREMENT`, both of which were PASS with
  `promotable=True`. `row_matched` is derived from row-set identity evidence
  instead of being assertable, giving NA `ROW_SET_UNTIED` and NA
  `ROW_SET_MISMATCH` where an untied comparison used to pass. `7884be5` states
  the adopter consequence in its own words — this is "the change most likely to
  flip adopter R12 rows from PASS to NA until those repos tie their rows, and
  THAT FLIP IS THE POINT".

### New surface

* `VerdictSealed` (`205aeb5`): a `CheckResult` is sealed once its verdict is
  formed, and the empty-metric verdict is refused rather than returned. `66fec9b`
  closes the follow-on that the seal read a flag the caller it guarded against
  could set.
* `GateAggregate` (`ab31233`): the gate verdict is a property equal to
  `all(r.status is Status.PASS)` — no stored field to assign, no initial `True`
  to leave standing, and **NA is not PASS**. This is the symbol the eight repos
  must import instead of writing their own aggregation (rule 7).
* `tests/test_tag_distance.py`: the check this entry is the repair for.

### Escalations recorded in this span

`E-M20`, `E-M22` and `E-M23` were appended, plus two entries both numbered
`E-M21` (`4bd42d6` and `b29fad3` allocated the same id independently). The
duplicate is left as committed — renumbering an escalation after the fact
breaks every reference to it — and is recorded here so the next reader knows
`E-M21` resolves to two entries, not one.

### The CI header stopped being true

`.github/workflows/ci.yml` claimed the workflow had never executed. It has;
see that file's header for the run ids and the retrieval date.

## v0.5.0 — 2026-08-29

Tagged 2026-08-31 as `v0.5.0` — annotated tag object `15a188b` on commit
`8517341` (`git for-each-ref refs/tags`, retrieved 2026-09-01). This line
read "Not yet tagged" until `v0.6.0`, which is one release too long: the
heading is written at the version the code declares, and nothing made the
sentence underneath it move when the tag was cut.

**A retraction first, because it is the reason this entry reads differently.**
These notes were written on `feat/r10-served-contract` (PR #6), where the
release really was one new check and nothing else, and they said so in a
sentence asserting that no check's verdict moved. PR #7 then merged into the
same `main` (`21f7e6f`, landing after `9118b0e`) the non-finite repairs that
`docs/ESCALATIONS.md` E-M09 and E-M10 record, and that sentence stopped being
true before the tag was cut. It is withdrawn here rather than quietly dropped,
and `tests/test_version_declaration.py` now FIRES on it: the newest entry may
not restate it, and must name at least one of the checks whose verdict moved.

### Every report now names the mlkit that wrote it, and adopters can check it (E-M24)

**Nothing in this section moves a check's verdict** — the release's verdict
changes are the ones the sections below record, and this is not one of them.
What it adds is a report header line, two keys in two machine payloads, one
CLI subcommand and one public function. It deliberately does **not** add a
readiness row: doing so would move every adopter's table, which is a decision
for the signatory and not a side effect of a repair.

**What was wrong.** `resilient-fray` pins mlkit by rev `c65b2e7`; mlkit main is
`6921e9a`. Forty commits apart, nine source files different — `+50/-5` in
`checks/readiness.py`, the file that emits R1–R12, and `+373/-13` in
`core/served.py`, the promotion verdict — and **both trees declare
`__version__ = "0.5.0"`**. Every adopter readiness table was therefore
"readiness under whichever mlkit happened to be installed", with nothing in the
report able to say which. `cli._self_sha()` did not close it: it shells `git
rev-parse HEAD` in mlkit's own directory, which in an adopter's environment is
`site-packages` and not a git worktree, so it returned `""` and the header read
`NA (not a git worktree)` — empty in exactly the case that needed it.

**What is new.** `resilient_mlkit.__build__`, e.g. `0.5.0+src.4f2a91c0be3d`: a
length-framed sha256 over every file the running package was loaded from,
excluding compiled bytecode. It moves iff the shipped source moves, and it is
computable from a wheel, an sdist or an editable install. It lives **beside**
`__version__` and never inside it — release naming and tag cutting stay the
signatory's, and `tests/test_version_declaration.py` is untouched.

**Where it appears.** `reports/readiness.md`, `reports/fabricated_defaults.md`,
`reports/fabricated_targets.md`, `reports/served_contract.md`, the
`*.UNMEASURABLE.md` refusal file, `portfolio/FLEET_VERDICTS.md` and the spine
report each gain two header lines. Both `.json` twins, and both
`scripts/*.py` payloads, gain `mlkit_build` beside `mlkit_version`
(**additive**; `artifact_schema` is unchanged, so a consumer pinned to
`resilient-mlkit/fleet-verdicts/1` keeps reading it).

**For adopters.** `mlkit identity` says which build is installed;
`mlkit identity --verify REPORT…` says whether a report was written by it —
`MATCH` / `MISMATCH` / `UNSTAMPED` / `CONFLICTING` / `INDETERMINATE`, exiting
`0` only on all-`MATCH`, `3` on any `MISMATCH`, `1` otherwise. Reports written
before this exists verify `UNSTAMPED`, which is an absence and not a mismatch:
the fact is not recoverable from the file, only from re-running the phase.
Design note: `docs/BUILD_IDENTITY.md`.

### The two builds E-M24 could still fail to tell apart (E-M25)

Adversarial verification of the section above drove two ways an mlkit build
still went unnamed. Both are closed; both carry a fires/silent pair and a
revert that kills a named test.

**A digest that covered none of the running code.** The digest excludes
`__pycache__` and `*.pyc` — bytecode moves for reasons that are not source
changes. In a *sourceless* install (`.py` compiled to `.pyc` in place and
removed, which CPython still imports) that exclusion excludes every executing
file and the digest falls through to whatever data the package ships. Measured
2026-09-01 on two copies of `src/resilient_mlkit` differing only in
`checks/readiness.py`: both digested `py.typed` alone, `files=1`, both stamped
`0.5.0+src.5b9327f66528`, and a real R10 report written by the first verified
**`MATCH`** against the second — the E-M24 defect inside the fix for it.
`core/identity.py` now requires that the file `core/identity.py` was *actually
loaded from* be one of the files hashed; where it is not, the build declines to
name an identity (`+src.unknown`, every comparison `INDETERMINATE`) instead of
naming a plausible one. Re-driven after the repair: `files=0`, `known False`,
both trees. **A source-shipping install is unaffected**, including the
existing rule that stray bytecode does not move the digest.

**The one readiness table that is composed rather than measured.**
`mlkit check --portfolio` renders R1–R12 out of `.mlkit/results/*.json` and
exits on it. The store recorded the repo's git SHA and nothing about mlkit, and
`store.load` staled only on the SHA. Measured 2026-09-01: 27 PASSes written by
`0.5.0+src.b1686b22efc6` were read back at an unchanged repo SHA by
`0.5.0+src.48480b572359` and rendered `R(9-12,1-8) PPPPPPPPPPPP` /
`READY-TO-TRAIN` at exit 0, with nothing naming either build. `save()` now
records `mlkit_build`, and `load()` stales a PASS whose stored build is absent,
unknown, or different — the same rule, and the same PASS/ESCALATED-only scope,
as the existing git-SHA rule, so a FAIL from another build is still reported
rather than hidden. Re-driven after the repair: 27 `S`, `IN-PROGRESS`, exit 3;
the same store read by the build that wrote it still resolves `READY-TO-TRAIN`.
`render_portfolio` also emits the E-M24 header lines, so the table names the
build that rendered it.

**This one does move verdicts, and says so.** A stored PASS carrying no
`mlkit_build` — which is every results file written before this — reads STALE
until the phase is re-run. That is the same treatment a result with no git SHA
has always had, for the same reason: it cannot be tied to anything. The
portfolio legend now reads `S=stale(repo SHA or mlkit build moved)`, because
`SHA moved` would send a reader looking at the wrong thing.

### D6 `RESAMPLING_UNIT`, and the dependence unit inside `core.served`

**New check, new gating check, and one contract surface widened.** Nothing here
re-decides a comparison that carries no interval — measured, not asserted: the
suite is 912 passed at `6921e9a` and 912 passed with these lanes added, and
every existing lane of `challenger_decision` is unreachable-by-construction from
the new ones.

**What it is for.** Round-8 adjudication measured it in `resilient-fray`. That
repo's holdout policy puts whole crop years in one partition, so the
exchangeable unit is the crop year and its val arm has five of them. The run's
bootstrap resampled 1,365 rows as if independent. On one identical set of rows:
`[+16.016, +29.646]` under the unit the run resampled — clears zero — against
`[-1.289, +41.704]` under the unit its own split implies — does not.
`resilient-chokepoint` resamples its dependence unit (corridor block). **No gate
had been edited by anyone**: fray's preregistration fixed the row bootstrap in
advance and the run honoured it exactly. Two conventions, one fleet, and nothing
in this instrument required either or required the choice to be stated.

**What landed.**

* `core.served.RowUnit` and `core.served.ResamplingDeclaration`. Six labels are
  declared; the counts, three `row_set_digest` ties, the relation and the
  refusal are all `init=False` and derived from an assignment covering the whole
  panel. `ResamplingDeclaration(..., n_units_in_arm=5)` is a `TypeError` naming
  the argument — `Comparison.row_matched` (M-06) one level up.
* `Comparison` gains `skill_interval_low` / `skill_interval_high` /
  `resampling`. An interval with no declaration raises; a declaration with no
  interval raises; an interval that does not contain its own point estimate
  raises.
* `challenger_decision` gains `RESAMPLING_ROWS_UNTIED` (NA),
  `DEPENDENCE_UNIT_CONTRADICTS_POLICY` (NA) and `INTERVAL_COVERS_ZERO` (FAIL,
  asked only after the point estimate has already cleared).
  `ChallengerDecision.to_dict()` emits a top-level `resampling` key that reads
  `"NA"` when nobody declared one — a printed absence, not a missing key.
* `D6 RESAMPLING_UNIT` in the decision phase, resolving a new
  `resampling_declaration` binding and tying its declared blocks to the `splits`
  binding R3 already reads. `checks.readiness.normalise_splits` is R3's parser
  EXTRACTED, not copied; R3's verdicts are byte-identical across all eight repos
  and ten synthetic edge cases, driven at both shas.

**Consumer impact, measured.** `PHASE_ORDER["decision"]` goes from five ids to
six, so the phase prints `0/6` where it printed `0/5`, and the gating set goes
27 → 28 (`tests/test_promotion_state.py`'s deliberate tripwire, edited with the
reason written in). D6 answers NA wherever the binding is absent, which is all
eight repos today — driven directly against each of them, NA 8/8, PASS 0/8, and
a PASS anywhere would have been evidence the check is blind. Every repo already
carried several NAs, so no repo's terminal state moves; only the count in its
message does.

**One artifact's BYTES move, and no verdict does.**
`ChallengerDecision.to_dict()` gains a top-level `resampling` key and each
comparison in `evidence` gains three. Grepped across the fleet rather than
assumed: `resilient-fray/src/registry/promotion_gate.py:360` embeds a decision
dict inside the promotion record it writes at `:928` and the release bundle at
`:910`, so fray's promotion records gain four keys reading `"NA"` the first time
it repins. `resilient-chokepoint` serialises no `ChallengerDecision`. Nothing
about `canonical_payload_sha256` or a served-model artifact's own hash changes;
every committed `artifact_sha256` in the fleet is unaffected.

**Adoption is a write into other repos and is not done here** — see
`docs/ESCALATIONS.md` E-M30 and E-M31.

### D6's crosscut carve-out is proportional and fail-closed, not existential

**A verdict change inside a check that has not shipped yet, and the reason it is
recorded here rather than folded into the entry below.** The dependence-unit
contract as first written asked `if crosscutting:` — *does any unit key appear
in more than one arm* — and one key answering yes silenced
`DEPENDENCE_UNIT_TOO_FINE` for every other key in the arm. Its own adversarial
verifier drove `resilient-fray`'s panel with COUNTY unit keys and recorded **D6
PASS**, the wrong answer in the repo the finding came from, and then turned a
FAIL into a PASS for 1,364 rows by editing the `unit_key` of **one**. Both
drives are in `reports/D6_CROSSCUT_BASE.json`, taken at the base sha before a
source file was edited.

Each unit key is now classified on its own. A block of the holdout policy that
is split with at least one **arm-local** piece refuses; `UNIT_CROSSCUTS_ARMS` is
reported only when the arm-local mass is empty. Four counts join the record —
`n_units_crosscutting_arms`, `n_units_local_to_arm`,
`n_blocks_split_by_local_units`, `n_blocks_split_by_crosscutting_units` — so the
carve-out is a proportion a reader can see rather than an existence claim.

**chokepoint's convention is unchanged and that was the falsification
condition**: 28 of 28 corridors cross every arm, so the carve-out covers the
whole arm, relation `UNIT_CROSSCUTS_ARMS`, no refusal, `28` units still printed
beside `20` blocks.

**Measured, not asserted.** 209,952 assignments enumerated at the base sha and
at the head and diffed by content: **0 cases that refuse at the base are silent
at the head**, 6,912 silent cases now refuse, and 6,912 refuse on both sides
under an earlier, more specific constant
(`UNIT_LABEL_CONTRADICTS_CONTENT → DEPENDENCE_UNIT_TOO_FINE`). The
preregistered claim that the constant would also be preserved is **falsified,
and said so** in `reports/D6_CROSSCUT_RESULTS.md` §4.1. Suite 977 → 991 with no
existing test edited.

**One regression was found in this fix by attacking it, not by shipping it.**
Making the relation proportional would on its own have loosened
`UNIT_LABEL_CONTRADICTS_CONTENT`: with that half removed, 2,160 of the 209,952
cases go from refusing to silent (`reports/D6_CROSSCUT_CONTAINMENT_NOT_DEAD.json`).

**What is still not closed, named rather than left to be found**: a unit that
crosscuts *every* arm remains refusal-free even when it is finer than the
policy's blocks inside the arm. chokepoint's endorsed bootstrap has that exact
shape, and nothing measured in this round tells the two apart.

#### Amendment: `splits` may declare PER-TRACK partitions, and D6 judges each track against its own

Written on `feat/track-aware-splits-contract`, branched from this same
`feat/dependence-unit-contract` head. **This is what "adoption is more than a
`repo.toml` line" turned out to mean**, and it was measured rather than
argued: `resilient-fray` runs TWO holdout policies over ONE county-year panel —
`county_label_splits` (unseen COUNTY, groups = 0.5° spatial block ids) and
`county_year_splits` (unseen future YEAR, groups = crop years) — and the repo's
own source says so. With one `splits` key holding one partition, D6 compared
the crop-year declaration's five blocks against the county track's **133**
groups and returned `BLOCKS_CONTRADICT_SPLITS`, for a partition the
declaration was never taken under. The reverse was equally true. **There was no
wiring of `splits` under which both of fray's tracks could be judged**, so the
contract above was structurally unadoptable by the repo whose row bootstrap
motivated it.

* `checks.readiness.normalise_tracked_splits`: `splits` may return
  `{"tracks": {name: {train, val, test}}}`. The envelope is recognised only
  when `tracks` is the mapping's **only** key — never by "the values look
  nested", because `{"train": {"a": 1}}` is a flat splits whose group ids are
  that dict's keys. A mapping carrying both shapes is refused by name.
* `R3` runs **every existing clause on every track**, through the same
  `_judge_one_partition` code, at the same `MIN_HOLDOUT_GROUPS`. One clause is
  new and exists only under tracks: `TRACKS_ARE_THE_SAME_PARTITION`.
* `ResamplingDeclaration` gains a seventh **declared** field, `track` — a
  pointer into another binding, which is why it is declared rather than
  derived. `to_dict()` emits it only when set.
* `resampling_declaration` may return a **sequence** of declarations, one per
  track; the worst verdict is D6's. New refusals: `TRACK_UNDECLARED`,
  `TRACK_NOT_IN_SPLITS`, `DUPLICATE_TRACK_DECLARATION`.

**No verdict moves for a single-track adopter, and this one is a byte
comparison rather than a reading.** Every check in this package that reads
`splits` (grepped: R3 and D6, and no third) was driven at both shas against the
REAL split membership `resilient-torrent` (211/71/70 basins) and
`resilient-chokepoint` (20/4/4 corridors) publish from their own
`mlkit_bindings:splits`, in six cases covering the block unit, the row unit and
an absent binding. The two result files hash to the same sha256
(`28e0db98fc879445cf0c7d88456bd2acdb46b2867b7bc6ed678ff6762342f3ef`). Suite:
977 passed at the base commit, 1,017 at this one, 0 failed.

**What is NOT closed, named rather than left to be found.**
`UNIT_CROSSCUTS_ARMS` still silences `DEPENDENCE_UNIT_TOO_FINE`
unconditionally, so a COUNTY unit on fray's crop-year track — a county
contributes rows to all three arms there — is judged PASS at this head. That
ladder belongs to a separate item and this branch does not touch it; the
outcome was pre-registered as expected before it was measured. See
`docs/ESCALATIONS.md` E-M34.

### D2 and E1 became bindable: the halt region and the fraction ladder are DECLARED data

**Neither check changes verdict on unchanged repo code, in any of the eight
repos, and that is measured rather than asserted.** `grep -c '^\[placebo\]|^\[scaling\]'`
over all eight `.mlkit/repo.toml` files returns **0** for every one, and so
does `grep -c '^placebo_test =|^scaling_probe ='` — so D2 and E1 are NA
everywhere in the fleet today, and both stay NA on this release. What moves is
that they can now be *armed*.

**What was wrong.** Round 8's adjudication measured `resilient-fray`'s D2 and E1
as NA at head and at main, and found the reason was mlkit's contract, not
fray's wiring:

* D2 halted on `lo > 0 or hi < 0` — a two-sided interval around a literal zero.
  fray's placebo estimand is *skill against the persistence floor*, whose
  no-signal value is not zero: a shuffled-target run is expected to land far
  below the floor, and fray's placebo CI is `[-71.998, -53.146]`. Binding that
  honest surrogate under `placebo_test` would have tripped a **spurious
  fleet-wide hard stop**, so fray did not bind it.
* E1 required the fractions `{0.01, 0.10, 0.25}` and nothing else. fray's probe
  ran 10% and 25%. Under mlkit's own **relative** rule that curve is comfortably
  not flat — `(-138.13969 − −151.29137) / |−151.29137|` = `+0.08693`, against a
  1% bar — so E1 would have **failed on contract, not on substance**.

A hard stop nobody can arm reads as coverage and is not coverage. Both repos'
hard stops that round were the trainers' own in-script constructions: genuine,
honestly computed, and not the fleet's gates.

**What changed.** Two optional sections of `.mlkit/repo.toml`, read **from the
blob at HEAD** through `core.artifact` — the discipline E-M21/E-M23 forced on
D3's nominal level, for the same reason:

```toml
[placebo]  estimand / null_value / indicts     # D2's halt region
[scaling]  fractions                            # E1's ladder
```

**What pays for the widening.** None of it optional:

* **Undeclared is unchanged.** Defaults are `0.0`/`"either"` and
  `(0.01, 0.10, 0.25)`. Every fallback — absent section, malformed working-tree
  config, dirty tree with the section deleted — lands on the strictest setting,
  so a repo cannot loosen anything by breaking something.
* **Committed or it does not exist.** A section in the working tree and not at
  HEAD is NA naming the file; malformed is FAIL; an unknown key is FAIL naming
  it. A binding that rewrites the config from its own module body cannot move
  the standard.
* **A moved halt region cannot be anonymous.** Shifting `null_value` off zero or
  `indicts` off `"either"` requires a written `estimand` in the same table, and
  that sentence rides in the verdict's evidence.
* **The exemption must point the same way as the claim.** Under a one-sided
  region the sign of `reference_effect` — the real run's effect, already
  required, already measured from the same null — must lie on the *indicting*
  side. A repo that exempts the direction its product's claim lives in has
  exempted the only direction D2 was testing, and that is a FAIL.
* **A declared ladder cannot buy a pass.** Its top rung may not sit below 0.25,
  and its top two rungs may be no further apart than mlkit's own
  `0.25 / 0.10 = 2.5` — the one way widening a ladder could make a flat curve
  look steep. At least three rungs, strictly increasing, each in `(0, 1]`.
* **No threshold moved.** `FLATNESS_EPSILON`, the D2 power bar and its strict
  boundary, and every non-finite refusal and its ordering are untouched. No test
  that existed on `main` was edited; `tests/test_declared_hard_stops.py` adds 45
  controls and `tests/test_spine_seed_is_adoptable.py` adds 4, so the suite goes
  **909 → 958**. *(The 39/948 first written here was typed before the three
  `indicts = "below"` controls and the two F811-renamed duplicates were counted;
  both figures are now `grep -c '^def test_'` and `pytest -q`, re-measured, and
  the earlier pair is withdrawn rather than quietly overwritten — a count nobody
  re-ran is the same defect class as a restated benchmark figure.)*
* **The seed file was refusing the adopter, and that was found by driving it.**
  `spine/mlkit/repo.toml` shipped `[placebo]` and `[scaling]` as live tables
  with every key commented out. `read_fraction_ladder` refuses a `[scaling]`
  with no `fractions` — deliberately — so a repo that adopted the seed verbatim
  and bound `scaling_probe` got `E1 FAIL SCALING_MALFORMED: [scaling] fractions
  is absent` on a curve E1 never read: a FAIL ON CONTRACT, the exact failure
  mode this whole entry exists to remove, reintroduced by its own template. The
  empty `[placebo]` was wrong in the same direction and milder — `declared` is
  True for an empty table, so `placebo_declared_in` rode in the evidence of a
  repo that had declared nothing. Both headers are commented out now, and
  `tests/test_spine_seed_is_adoptable.py` drives the real seed bytes through D2
  and E1 and requires them to agree with a minimal config, with both halves
  computed rather than typed, plus two check-not-dead controls that re-arm each
  header. No check, threshold or existing test moved.

`evidence["gain_10_to_25"]` is now emitted **only** when the ladder really is
`(0.10, 0.25)`; `gain_top_two`, `from_fraction` and `to_fraction` are always
emitted. A key naming two fractions that were not the ones measured is a
fabricated label on a real number, which is the one thing a reader does not
check.

### R10 `absence adjudicated as a pass` fired on honest NA-reporting guards (E-M19)

**R10 changes verdict on unchanged repo code in one repo**, in the direction
that removes a finding: `chokepoint` moves FAIL → NA. It belongs to the same
major event as the sections below, and it is the correction of a defect in one
of them.

**What was wrong.** `_scan_or` admitted any `or` expression holding an
`is None` arm and never asked what that arm was OR'd with. The shape it exists
for is `p_value is None or p_value > alpha` — an unmeasured p-value satisfying
a parallel-trends gate — and the second operand is the whole defect: it is the
adjudication, and the `is None` arm is what lets a missing figure pass it.
Without that requirement the rule also matched

```python
"holdout_mae": None if holdout_mae is None or np.isnan(holdout_mae) else round(holdout_mae, 6)
```

where every operand is an absence test on the same figure, the taken branch
writes `None` rather than a number, and the promotion decision forty lines
below refuses unless both holdout figures were measured and beat the margin
(`chokepoint scripts/fit_corridor_ensemble_weights.py:249,252,380-382`).
Absence there REFUSES. R10 called it a pass.

**Measured, not asserted.** `scan_file` over every `*.py` in the ten
`resilient-*` checkouts, before the fix: this shape had **7 matches and all
seven were guards of that family** — chokepoint x2, `fray` x4
(`scripts/stress_readout_county_yield.py:318,444,447`,
`src/validation/error_decomposition.py:131`), `backend` x1
(`api/services/investment_case.py:350`). Not one was a fabrication. After the
fix the same walk returns 0 of them and **nothing else in the fleet moves**.

**The rule now.** An `is None` arm is required exactly as before — the
admitting predicate is copied byte-for-byte into `_has_none_arm` so that the
narrowing provably applies to what the shape DOES with an expression, not to
which expressions it sees. On top of it, at least one operand must sit outside
the absence guard, where the guard is four things and no more: an `is None`
test; a degeneracy `Compare` (`len(folds) == 0`, `observed_mean <= 0.0`);
`not <name>`; and a NaN/NA question about an already-guarded figure
(`np.isnan(x)`, `pd.isna(x)`, `math.isnan(float(x))`, `not np.isfinite(x)`).

Deliberately NOT "the other operand must be a threshold `Compare`":
`ok = run is None or run.passed` adjudicates through an attribute and is the
same defect, and `coverage is None or BASELINE.is_file()` is choco's
fixture-presence gate in `or` form. Both still fire. An earlier draft
delegated the guard test to `_is_absence_test`, which ignores polarity for
calls and read `BASELINE.is_file()` as absence; that draft silenced the choco
shape and was measured and discarded. Both halves are pinned as a control pair
in `tests/test_fabricated_defaults.py` (8 fixtures red against the pre-fix
scanner, 7 more that must stay green on both).

**The operand test alone was a refactor recipe, and is now conjoined with a
position test.** Reading only the operands cannot hold, because every leg of
the guard is name-blind by construction. `not <name>` is a guard whatever the
name means, and a `Compare` counts as a degeneracy test whenever its left side
merely MENTIONS a size — `n_violations <= 10` qualifies, at any magnitude, on
any quantity, not only on the guarded one. So

```python
mae_exceeded = holdout_mae is not None and holdout_mae > threshold
mae_gate_ok  = holdout_mae is None or not mae_exceeded
```

decides exactly what `holdout_mae is None or holdout_mae <= threshold` decides
— an absent `holdout_mae` still passes — and the operand test alone silenced
it. Driven end-to-end: that rewrite planted into `chokepoint`'s promotion
decision at remote `main` `74f4ab1` (throwaway worktree) makes `promoted` come
out `True` with `holdout_mae` `None` and no reason recorded, and R10 read the
tree as **NA, 0 findings**. Pre-fix `main` `c65b2e7` named it; so does the rule
below (`FAIL`, 1 `SATISFIES_GATE`, `fit_corridor_ensemble_weights.py:385`).

The guard-operand test is therefore required **together with** the position:
the expression must also sit where absence is REPORTED rather than
adjudicated — the test of `None if <guard> else <computed figure>`, or an `if`
clause of a comprehension. All seven fleet sites are in one of those two
positions (six the first, `backend` the second); a bare boolean assignment is
a verdict and stays reportable. The silence set is a strict subset of the
operand-only one, so nothing the operand test kept is lost. Pinned as
CONTROL C in `tests/test_fabricated_defaults.py`: four fixtures, all four red
against the operand-only scanner, three of them green against pre-fix `main`
(the fourth is E-M18 itself).

Residual, still open as **E-M19**: `rmse_gate_passed = rmse is None or rmse <=
0.0` written directly into an NA report — `None if rmse is None or rmse <= 0.0
else <figure>` — is silent, because that is `fray
src/validation/error_decomposition.py:131` verbatim. Separating those two
needs to read what the guarded figure MEANS, which this module cannot do. No
instance of the silenced form outside the honest family exists in any of the
ten checkouts; the fleet walk is the measurement.

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

### D3's coverage evidence is recounted, not accepted (E-M23 residual 2)

**D3 changes verdict on unchanged adopter code**, PASS → NA
`COVERAGE_UNTIED`, wherever a `coverage` binding does not yet carry the
operands its figures were computed from. By the scale at the top of this file
that is a MAJOR event and it is named first, not buried.

`docs/ESCALATIONS.md` E-M23 residual 2, pinned and unassigned since
2026-08-31: with an honest COMMITTED `[coverage] nominal = 0.90`, a binding
returning `{"nominal": 0.90, "empirical": 0.90, "n": 1000000}` PASSed. E-M21
tied the `nominal` operand to committed state and clamped `tol` to mlkit's;
`empirical` and `n` stayed where tick 13 found them — two scalars asserted over
a row set nobody named. Re-driven at `6921e9a` rather than quoted, and eight
other forgeries PASS the same way; all nine recordings are committed under
`reports/d3_coverage_tie/` with their `main.*` twins.

The evidence contract now carries a `row_set_digest` —
`core.served.row_set_digest`, the fleet's one definition, imported and not
reimplemented — beside exactly one of `rows` (`{"row_id": ..., "covered":
True}`) or `groups` (`{"group_id": ..., "n": ..., "covered": ...}`).
`core/coverage_evidence.py` re-derives `n` and `empirical` from them and D3
takes its verdict on the recount. Four named outcomes: NA `COVERAGE_UNTIED`
(operands or digest missing, naming which), FAIL `COVERAGE_ROWS_MALFORMED`,
FAIL `COVERAGE_ROW_SET_MISMATCH`, FAIL `COVERAGE_SELF_REPORTED` naming the
re-derived figure. Never a silent PASS and never a silent FAIL.

**What it does not buy**: the rows are still the subject's, and a binding that
generates rows to match a figure satisfies this contract. The tie makes the two
figures re-derivable and gives the row set a name the rest of the fleet can
compare against; tying that name to COMMITTED state — the shape the nominal
level now has — is the next tie and is recorded OPEN in E-M34 rather than
half-built.

**Adopters**: `mlkit check --phase decision` reports the missing operand by
name. None of the three in-scope repos reaches D3 today, so no in-scope row
moves; a repo with a live D3 row moves to NA until its binding carries the
rows.

Suite 909 → 948 (+39, the new controls file; collected node ids diffed against
main, zero removed). Every registered check driven over three repos in two
interpreters produced records with the same sha256 either side.

**Merge note, because a verdict change in the wrong entry is a verdict change
nobody reads.** This section is written under `v0.5.0` because that is the
newest heading on the `main` it branched from. mlkit PR #40 (loop item I2-M2)
adds a `v0.6.0` heading above it; the two branches merge CLEANLY and the merged
suite is green (964 passed / 3 skipped, measured), and git has no way to notice
that this section then describes the release *below* the one that carries it.
**Whoever merges the two must move this section under the newest heading** — a
block move, no text change. It is called out here as well as in the PR body
because the file is where the person resolving the conflict is looking.

## v0.4.0 — 2026-08-28

Never tagged, and now never will be: the release line goes `v0.3.0` ->
`v0.5.0` (`git tag --list` reads exactly `v0.2.0`, `v0.3.0`, `v0.5.0`;
retrieved 2026-09-01), so this entry's content shipped inside the `v0.5.0`
tag. The sentence here said "Not yet tagged" and stayed technically true
by never being revisited. The heading is written at the version the code
declares, not retitled from "Unreleased" after a tag is cut — that retitling step is what
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
