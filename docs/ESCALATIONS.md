# Escalations raised by the instrument

Findings that `mlkit` measured in the eight model repos and that **cannot be
fixed from here**. Each is a write into another repo, a signatory decision, or
both. Nothing in this file has been acted on; it is a record so the findings do
not live only in a transcript.

Opened 2026-08-28 on `feat/r6-portfolio-tooling`.

---

## E-M01 — choco's candidate figure is not in git

**Measured by** `mlkit portfolio` (`portfolio/FLEET_VERDICTS.md`, nonce
`mlkit-20260828T205245Z-e792b3ccb899`).

`resilient-choco/models/observed_production_head.meta.json` exists on disk
(sha256 `779f80be4d58506a27089ea121a254030ff8864250e1b6cb17711e4f96aeeab8`,
39,172 bytes) and is **gitignored** — `.gitignore:82`, the pattern `/models/*`.
`git log --all -- models/observed_production_head.meta.json` returns nothing: it
has never been committed on any branch.

Every figure the fleet verdict table quotes for choco's retired climate head
comes out of that file. They are correct about one machine and cannot be
reproduced from the repository by anyone else. The served predictor's sidecar,
`models/observed_production_persistence.json(.meta.json)`, IS committed, so the
repo already has a `!` exception pattern to follow.

**Cannot be done from here**: adding a `.gitignore` exception and committing a
model sidecar is a write into resilient-choco.

**Proposed**: add the exception in the same form as its committed siblings and
commit the sidecar, or record explicitly that the head's figures are
irreproducible and should not be quoted.

---

## E-M02 — surge's model registry is not on the branch surge has checked out

**Measured by** `mlkit portfolio`.

`data/model_registry/index.json`,
`data/model_registry/per_lead_anchor_ols/model.json` and
`reports/holdout_reads.jsonl` resolve only in the linked worktree
`resilient-surge/.worktrees/pr55`, on branch `feat/surgeistm-lora-finetune`
(`de37eddfbea7`). The root checkout is on
`feat/observed-corpus-and-fabrication-gates` (`9eab2fe80177`) and carries none
of them.

The figures are real and the row records where they came from, but they are
evidence about that worktree, not about the branch a reader will check out. The
same pattern was already catalogued for resilient-arabica in round two
(catalogue #19) and closed by landing the work on the feature branch.

**Cannot be done from here**: merging or cherry-picking in resilient-surge.

---

## E-M03 — torrent and blackout declare no model of record in any committed artifact

**Measured by** `mlkit portfolio`; six of eight repos resolve this column, these
two do not.

* **torrent** — the ridge is named as the model of record in
  `docs/ESCALATIONS.md`, `docs/HYDROLOGY_VAL_RESULTS_AND_TEST_DECISION.md` and
  `CHANGELOG.md`. Prose only.
* **blackout** — `models/weather_failure_v1.joblib.provenance.json` records that
  checkpoint's family and sha256 but not its serving status, and
  `reports/train/weather_failure_all_in_scope_gate.json` records
  `registry_state.n_versions: 0` — nothing has ever been registered.

A model of record that exists only in prose cannot be read by a promotion gate,
which means the gate cannot enforce "beat the thing we actually ship". The other
six repos carry a `champion.json`, a registry entry or a `models_of_record.json`.

**Cannot be done from here**: writing a champion record is a write into those
repos, and in blackout's case the gate is currently refusing the candidate, so
what to register is a decision.

**CLOSED FOR TORRENT, 2026-08-29 (TORRENT-RECORD).** resilient-torrent wrote
the record itself: `models/hydrology_ridge/model.json` is committed on its
`main` (`promoted_at` 2026-08-29, re-emitted under `TORRENT-L4-PATHS`, verified
read-only with `git cat-file -e main:<path>` and byte-identical at that
checkout's HEAD). The fleet adapter now reads `record:served_model` and
torrent's two `model_of_record` cells are measured, not prose —
`reports/fleet_verdicts_torrent_record/` carries the before/after regeneration.
**The blackout half of this item is untouched and remains open.** Note what the
delay cost: the stale `Absent` reason went on asserting, in mlkit's own source,
that torrent had committed no such artifact, for as long as nobody re-checked
it. An `Absent` expires like a pointer and nothing in the tool notices.

---

## E-M04 — the canonical spine has not been synced since it last changed

**Measured by** `mlkit spine` (`portfolio/SPINE_DRIFT.md`, nonce
`mlkit-20260828T205847Z-a923e6f23166`): 48 comparisons, 32 IN-SYNC, 16 DRIFTED,
0 ABSENT, 0 UNCLAIMED.

All 16 drifts are the same two files in all eight repos, at identical deployed
sha256s:

| file | spine | deployed in all 8 | gap |
|---|---|---|---|
| `CLAUDE.md` | `8526df9dc9c454c2…` | `5aa52879d78cbcad…` | 31 lines; deployed copies predate the "Credentials are not blockers" section |
| `docs/READINESS.md` | `aed512c6a0498f0e…` | `00838426cbb8a011…` | 66 lines; deployed copies still say "Nine checks" and omit R10 and R11 from the canonical order |

That the eight drifted **identically** is the finding: this is one un-run sync,
not eight local edits. The READINESS gap is the one commit `0a0ddac` fixed in
the spine and never propagated.

**Cannot be done from here as a check**: `mlkit spine` is report-only by design.
Propagating is `python scripts/sync_spine.py`, which writes into eight repos and
is therefore a decision, not a side effect of looking.

**Re-measured on 2026-08-29 (R9-SPINE)** at the fleet as checked out that day,
and the classification asked for: **16 of 16 drifts are an unsynced spine, and
0 of 16 are a repo legitimately diverging.**

Two independent lines of evidence, both measured, neither a judgement:

1. **Byte identity across the fleet.** Grouping `portfolio/SPINE_DRIFT.json` by
   `relpath` and `deployed_sha256` gives exactly one deployed sha per file,
   shared by all eight repos:

   ```
   CLAUDE.md          DRIFTED  spine=8526df9dc9c454c2 deployed=5aa52879d78cbcad  n=8
   docs/READINESS.md  DRIFTED  spine=aed512c6a0498f0e deployed=00838426cbb8a011  n=8
   ```

   A repo that had diverged for its own reasons would carry bytes nobody else
   carries. Eight identical copies is one un-run sync, and it is not a claim
   about intent — it is what the shas say.

2. **Direction, at the line.** `core/spine.py` diffs spine-as-`want` against
   deployed-as-`got`, so a `-` line is spine-side. Every changed line in both
   files is spine-side content the repos never received, and each traces to a
   commit in this repo:

   * `CLAUDE.md`, 31 lines, from `eddbedb` (2026-08-14, "Add DEFERRED: a
     missing API key is not the same as a broken loader"). The spine gained the
     "Credentials are not blockers" section — rules 7–9 on `CredentialRequired`
     and READY-PENDING-KEYS — which renumbered the two rules after it. The eight
     deployed copies still carry the pre-`eddbedb` numbering.
   * `docs/READINESS.md`, 66 lines, from `0a0ddac` (2026-08-28, "the canonical
     order had drifted two checks behind"). The spine gained R10 and R11 and
     says "Eleven checks"; all eight deployed copies say "Nine checks" and omit
     both from the canonical order.

   Not one changed line originates in a model repo.

**Consequence, stated plainly:** the operator-facing document each repo's agents
read as binding describes a nine-check readiness phase, while `mlkit` runs
eleven. R10 and R11 are the two checks that catch fabricated defaults and
fabricated targets, and no repo's copy of the spine mentions either.

**Still the operator's call.** Nothing was synced. `scripts/sync_spine.py`
writes into eight repos, and the two files are byte-identical everywhere, so the
propagation is one decision covering all sixteen rather than sixteen judgements.

---

## E-M05 — chokepoint's pytest-timeout defect was already repaired; nothing owed

**Measured by execution on 2026-08-28**, at chokepoint
`d4867f0551d550c659fb5ad685e4f25b6f1ea6fb`:

```
.venv/bin/python -c "import pytest_timeout"   -> .venv/lib/python3.12/site-packages/pytest_timeout.py
pytest -c pyproject.toml <probe> --timeout=2  -> exit 1 in 3s, against a 30s sleep
pytest -c pyproject.toml <ini probe>          -> exit 0, getini("timeout") == '180'
```

The environment now satisfies the declaration that was already in
`pyproject.toml`; the round-six brief recorded it as absent. **Honest negative:
there was nothing left to sync.** No second declaration was added, and the
existing `[project.optional-dependencies] dev` entry
(`pytest-timeout>=2.3`, locked at 2.4.0 in `uv.lock`) is untouched.

One loose end, left alone deliberately: `resilient-chokepoint/tests/
test_pytest_timeout_active.py` exists in that repo as an **untracked** file. It
is a complete, well-formed control suite for exactly this defect and it is
someone else's in-flight work. Committing it from this task would collide with
whoever wrote it.

**Proposed**: whoever owns that working tree commits it.

---

## E-M06 — fray's model of record moved; the portfolio adjudication did not

**Measured by** `mlkit portfolio` on 2026-08-29 (`portfolio/FLEET_VERDICTS.md`,
regenerated at mlkit `036683e`), reconciled against `portfolio/MODEL_QUALITY.md`
by search: of 23 machine-read figures, 21 are found in that document's prose and
**1 is contradicted** by it. (The 23rd, `chokepoint/direction-head` baseline
`0.3482142857142857`, is an omission already noted in that file, not a conflict.)

| | machine reads | `MODEL_QUALITY.md` says |
|---|---|---|
| `fray/forecast_available` candidate | `forecast_available+nbr+wx_prior/hgb/leaves=127/lr=0.05/iter=400` | `forecast_available+nbr/k=15/hgb/leaves=63/lr=0.1/iter=300` |
| `fray/forecast_available` TEST MAE | `74.16097783177521` | `82.754` |
| bar (`persistence_t_minus_1`) | `113.06701205090663` | `113.067` — agrees |

resilient-fray restated the record at `87a1dbe` (*"SERVE-3/PROMOTE: the verified
weather winner gets a checkpoint, so it can be served"*). Read from
`reports/validation/models_of_record.json`, pointer
`tracks.forecast_available.test.mae_lb_ac`. **No mlkit adapter was edited**: the
pointer resolved against the new bytes and the figure moved on its own, which is
the property the command was built for and the first live confirmation of it.

**Provenance caveat.** `mlkit portfolio` reads the working tree, and fray's copy
of that file was DIRTY at read time; the generated table records this. The figure
is unaffected — `74.16097783177521` in fray's `HEAD` and working tree alike. The
uncommitted portion is the checkpoint block (`path`, `sha256`, `identity_check`)
from fray's in-flight promote work.

**What is stale.** `MODEL_QUALITY.md`'s adjudication for fray, *"I re-hashed both
checkpoints on disk myself (match); prereg → val-select → single test read commit
order verified"*, was formed against the superseded winner and does not transfer
to the new one. The row is marked SUPERSEDED and the belief left standing and
unedited, because overwriting another adjudicator's verdict from here would be
the same failure in the other direction.

**Cannot be done from here**: re-adjudicating means verifying fray's own promote
artifact (`reports/validation/weather_covariate_extension.promote.json`) and the
checkpoint hash it claims, then deciding whether the new record is believed. That
is a judgement, and `mlkit portfolio` deliberately regenerates only the measured
columns.

**Proposed**: whoever owns the portfolio adjudication re-runs it for
`fray/forecast_available` against the new record. `spatial_infill` is unaffected
(`71.35922343344701`, still matching the prose).

---

## E-M07 — the CI lint gate had no committed definition (FIXED HERE; recorded for the fleet)

**Measured by execution** on 2026-08-29 at mlkit `8647be9`, with this repo's own
venv:

```
.venv/bin/ruff --version                 -> ruff 0.16.5
.venv/bin/ruff check src tests scripts   -> Found 36 errors
```

against a workflow header claiming `-> all checks passed` for that exact command.
`.github/workflows/ci.yml` installed `ruff>=0.4` and ran it at DEFAULTS. Ruff's
default rule set ships with the release, so the floor meant the gate's definition
was whatever the runner downloaded that day, not what the repo committed. Four of
the 36 were `RUF100 unused noqa` on suppressions written for rules the current
defaults do not enable — the declarations had gone stale in place and nothing
could see it.

**Fixed in this repo** (`504d487`): all 36 findings repaired in `src/`, `tests/`
and `scripts/` with none suppressed and no `[tool.ruff]` select added; `ruff` and
`mypy` pinned exactly; `tests/test_ci_workflow.py` added, which FIRES on the
workflow as committed at `8647be9` (`['ruff>=0.4', 'mypy>=1.9']`) and is SILENT
on the repaired one.

**Recorded here because it is not this repo's problem alone.** Any repo in the
fleet whose CI floors a linter and runs it at defaults has the same latent
defect: a gate that changes meaning without a diff. **Cannot be done from here** —
checking or changing eight other repos' workflows is eight writes into those
repos. **Proposed**: each repo runs its own linter at its own pinned version and
compares the finding count against what its CI comments claim.

---

## E-M08 — the v0.3.0 tag ships version strings that read 0.2.0

**Measured by execution** on 2026-08-29 at mlkit `dfe2a10`:

```
git show v0.3.0:pyproject.toml | grep '^version'        -> version = "0.2.0"
git show v0.3.0:src/resilient_mlkit/cli.py | grep __version__
                                                        -> __version__ = "0.2.0"
git rev-parse 'v0.3.0^{commit}'                         -> d08d85ed796c...
```

The tag `v0.3.0` was cut by the session lead at the PR #3 merge, but neither
`pyproject.toml` nor `cli.__version__` was bumped on the branch it points at.
Every artifact `mlkit portfolio` and `mlkit spine` generate from that tag — and
from current `main` — stamps `"mlkit_version": "0.2.0"`, including the
regenerated `portfolio/FLEET_VERDICTS.json` and `portfolio/SPINE_DRIFT.json`
committed this round. The `mlkit_git_sha` field in the same artifacts is the
reliable identity and is unaffected.

**Cannot be done from here.** The tag is immutable and stays where it is.
Bumping the strings on a working branch cannot make the tagged tree
self-consistent, and choosing between the repairs — bump `main` to `0.3.0` and
accept that the tag's own tree still says otherwise, or bump past it and cut a
`v0.3.1` whose tree and tag agree — is a versioning decision for the release
that the eight repos pin by, which is the session lead's to make (CLAUDE.md
rule 12 reserves release decisions of record to the signatory's process).

**Proposed**: bump `version` and `__version__` to `0.3.1` in one commit on
`main` and cut `v0.3.1` from it, so the first tag whose tree and name agree is
also the first one the repos re-pin to. Recorded in the CHANGELOG's `v0.3.0`
entry so a reader of the tag finds the caveat next to the release notes.

**Partly closed on `feat/r9-gate-coverage` (R9-VERSION), by operator direction**
to bump `main` so the next tag is correct. What was done: the version is now
declared once, in `resilient_mlkit.__version__`; `pyproject.toml` reads it via
`[tool.setuptools.dynamic]` and `cli` imports it, so the three literals that
disagreed inside `v0.3.0` are one literal that cannot. `main` declares `0.4.0` — see below on why not `0.3.1`.
Measured by execution on this branch:

```
.venv/bin/pip install -e . --no-deps  ; .venv/bin/pip show resilient-mlkit
                                                   -> Version: 0.3.1
.venv/bin/mlkit --version                          -> mlkit 0.3.1
.venv/bin/python -m pytest tests/test_version_declaration.py -q
                                                   -> 12 passed
```

`tests/test_version_declaration.py` holds `__version__` against the newest
CHANGELOG heading and FIRES on both shapes that produced this escalation: a
second `__version__` literal in a module, and a newest heading reading
`Unreleased` rather than a version.

**The bump is `0.4.0`, not the `0.3.1` proposed above, and that is a
deviation worth reading.** The proposal predates this round's content. Two
readiness checks now change verdict on unchanged repo code (R3 on a `str`
split, R5 on a fractional or negative provenance count — both previously silent
PASSes, see the CHANGELOG), and the scale at the top of `CHANGELOG.md` calls
that a **major** release. On a `0.x` line the minimal reading of major is the
leading nonzero, so `0.4.0`.

**Still open, and still the signatory's:** the `v0.3.0` tag is untouched and its
own tree still reads `0.2.0`. Three things remain a release decision of record —
whether this line's major is `0.4.0` or `1.0.0`, which is written down nowhere;
cutting the tag; and when the eight repos re-pin to it.

---

## E-M09 — D2 and E1 now change verdict on unchanged code, and the version bump collides with an open PR

**Measured by** `.venv/bin/python -m pytest tests/test_decision_controls.py
tests/test_economics_controls.py -q` on `feat/loop-mlkit-3`, and by the
before/after tables recorded in the commit messages at `591e25c` (D2) and
`3647a04` (E1).

Two existing checks change verdict on unchanged repo code. A `placebo_test`
binding reporting a NaN estimate or interval went from **PASS** to **FAIL**, and
a `scaling_probe` binding reporting a NaN or infinite point on its curve went
from **PASS** to **FAIL**. Both are hard stops, and in both cases the pre-repair
behaviour was that the hard stop could not fire at all against a non-finite
figure. Neither repair moved a threshold; `FLATNESS_EPSILON`, `GPU_UTIL_FLOOR`,
`MAX_COVERAGE_TOL` and `MIN_COVERAGE_N` are untouched.

The scale at the top of `CHANGELOG.md` says an existing check changing verdict
on unchanged code is a **major** release. On the reading recorded in E-M08, that
is `0.5.0`.

**Cannot be done from here.** PR #6 (`feat/r10-served-contract`) is open and
already declares `0.5.0` in `resilient_mlkit.__version__` and in its newest
`CHANGELOG.md` heading, for different content — a new check, R12, which is a
*minor* event by the same scale. Bumping to `0.5.0` on this branch as well would
put two open PRs on the same version number and guarantee a conflict in the one
literal that exists precisely so it cannot disagree with itself (E-M08). So this
branch deliberately leaves `__version__` at `0.4.0` and adds no CHANGELOG
heading, and `tests/test_version_declaration.py` stays green either way, because
it compares the literal to the newest heading rather than requiring a bump.

**Proposed**, for whichever of the two PRs lands second: apply a single bump in
that merge, covering both PRs' content, with one CHANGELOG heading naming the
D2/E1 verdict change as the major reason and R12 as the minor one. Whether the
number is `0.5.0` or `1.0.0` is the same open question E-M08 records and is the
signatory's to settle. Until then, no tag should be cut from either branch.

## E-M10 — four more checks change verdict on unchanged code; every committed T2/R2/D3/E3/R4 PASS is void

**Measured by** `.venv/bin/python -m pytest tests/test_nonfinite_controls.py -q`
on `feat/loop-mlkit-3` (25 passed), and by the same file run against the tree at
`2d173a2` before the repair at `b85deb5` (13 failed, 12 passed).

Adversarial verification of the D2/E1 repair drove every remaining numeric check
in the package with a non-finite measurement. The class the D2/E1 repair names
does not stop at the two hard stops. Four more checks returned **PASS** on a
figure that does not exist, and now return **FAIL**:

| Check | Input that passed | Why it passed |
|---|---|---|
| T2 | `[2.0, nan]` | `nan > 0.1 * first` is False, and so is `first <= 0` |
| R2 | same | R2 delegates to T2 and inherited it verbatim |
| D3 | `empirical = nan` | `abs(nan - nominal) > tol` is False |
| E3 | `gpu_util = nan` | `nan < GPU_UTIL_FLOOR` is False |
| R4 | `computed = nan` | `abs(nan - want) > tol` is False |

Two of these are worse than a plain NaN hole. `min(nan, x)` is `nan` in Python,
so the subject-declared tolerance clamps in D3 and R4 — written so a binding may
ask for something stricter but never looser — accept a declared `tol` of NaN as
the loosest tolerance there is. A repo could set its own pass mark to "accept
anything" using the mechanism built to stop it. Neither existing control file
caught this, because both exercise the clamp only with finite tolerances.

T2 is the one with operational teeth: a loss that diverged to NaN is the single
most common way a training run fails, and T2 is the check whose whole job is to
notice that the model cannot drive one batch down.

No threshold was moved. `FLATNESS_EPSILON`, `GPU_UTIL_FLOOR`, `MAX_COVERAGE_TOL`,
`MIN_COVERAGE_N`, `MAX_METRIC_TOL` and `MIN_HOLDOUT_GROUPS` are byte-identical to
`main`.

**Consequence for the portfolio, not settled here.** Any committed PASS for T2,
R2, D3, E3 or R4 was recorded under a check that could not fire on a non-finite
measurement, so it does not distinguish "measured and fine" from "measured
nothing". The same is already true of D2 and E1 per E-M09. **Recommended, not
run:** `mlkit check --phase triage`, `--phase readiness`, `--phase decision` and
`--phase economics` across the eight repos, and void any of those five verdicts
that changes. That is a portfolio re-measurement and a records change, so it is
the signatory's to authorise, not the agent's.

**Version.** These repairs are the same *major* event E-M09 describes, for the
same reason, and they fold into the single bump E-M09 proposes for whichever of
PR #6 and PR #7 lands second. `__version__` is deliberately left at `0.4.0` here
too. No tag should be cut from either branch until E-M08/E-M09 are settled.

---

## E-M11 — the v0.5.0 heading is reconciled; the number itself is still the signatory's

**Measured by** `.venv/bin/python -m pytest tests/test_version_declaration.py -q
--timeout=180` on `feat/loop-mlkit-4` (python 3.14.6, pytest 9.1.1): **2 failed,
15 passed** against the `CHANGELOG.md` committed at `25cd618` (which is `main`'s
byte for byte), and **17 passed** after the heading was corrected.

**What was wrong.** `main` at `21f7e6f` carried a `v0.5.0` entry written on
`feat/r10-served-contract` (PR #6), where the release was one new check, R12,
and its body asserted that no check's verdict moved on unchanged code. PR #7
merged into the same `main` the non-finite repairs E-M09 (D2, E1) and E-M10 (T2,
R2, D3, E3, R4) record as doing exactly that. By the scale at the top of
`CHANGELOG.md` the release is **major**, and its only release note denied it.
`tests/test_version_declaration.py` compared the heading's NUMBER to
`__version__` and could not see a body that contradicted the tree.

**Done here (E-M09's prescribed reconciliation).** The `v0.5.0` body now names
the seven verdict-changing checks as the release's principal event, carries the
withdrawal of the claim rather than dropping it, and states that voiding the
affected committed verdicts is E-M10's signatory-reserved re-measurement. Two
new controls hold it: the newest entry may not restate the withdrawn claim, and
it must name at least one of the seven check ids.

**Not done here, and reserved.** The NUMBER is unchanged at `0.5.0`, because
`0.5.0` is already what a major bump from `0.4.0` looks like under E-M08's
recorded reading (on a `0.x` line the minimal reading of major is the leading
nonzero), so the correction is to the justification and not to the version.
`resilient_mlkit.__version__` is untouched at `0.5.0` and the two agree.

Three things remain a release decision of record and are **not** an agent's:

1. whether this line's major is `0.5.0` or `1.0.0` — the same open question
   E-M08 and E-M09 record, now with two rounds of major content behind it;
2. cutting the tag, which no branch in this round does;
3. E-M10's fleet re-measurement, and the voiding of any committed T2, R2, D2,
   D3, E1, E3 or R4 PASS that moves — a records change across eight repos.

**Proposed**: settle (1) before (2), because the tag the eight repos re-pin to
is the first artifact that makes the answer permanent. If the answer is `1.0.0`,
it is one edit to `__version__` and one heading, and the control added here
keeps the two from drifting apart while it is made.

## E-M12 — the choco fleet row was read from a file committed on no branch at all

**Raised by** the adversarial verification of `feat/loop-mlkit-4`, while
re-measuring that branch's own claim that "the other six repos' declared
artifacts are all present on their own `main`".

**Measured** read-only on 2026-08-29 in each repo's own clone -- `git cat-file
-e <ref>:<path>`, `git log --all -- <path>`, `git check-ignore -v`; no
checkout, no fetch, nothing written. Over the 17 distinct `(repo, path)` pairs
`src/resilient_mlkit/fleet_adapters.py` declares, 16 resolve on the ref the
adapter implies. The seventeenth does not:

    resilient-choco  models/observed_production_head.meta.json
      main                       -> ABSENT
      any ref (`log --all`)      -> no commit touches this path
      check-ignore               -> .gitignore:82:/models/*
      working tree               -> present, 39172 bytes

That path is the `main:` artifact of the `choco` adapter, and every choco cell
in `portfolio/FLEET_VERDICTS.md` that resolves through it -- candidate, score,
split, baseline score, test-arm-spent -- was therefore read from an untracked,
gitignored working-tree file. The adjacent `served:`
artifact (`models/observed_production_persistence.meta.json`) IS committed on
choco's `main`, which is why the row looks half-provenanced rather than
obviously unbacked.

**Why this is not the same defect as the branch dependence** already recorded
in `fleet_adapters.py`. blackout's and triage's evidence is committed, on a
named branch, with a sha256 in the provenance table; a reader can resolve it.
choco's cannot be resolved from any ref, so there is no branch to name and
`BRANCH_ONLY_EVIDENCE` is the wrong place for it. The verifier's new control
`test_negative_control_a_repo_whose_evidence_is_on_main_needs_no_note` is
silent on choco for exactly that reason, and correctly so -- it measures notes,
not provenance.

**Not done here, and why.**

1. No note was invented for the choco adapter. The honest note would assert
   where the evidence lives, and it lives nowhere resolvable; writing one would
   be the fabrication this repo's rules exist to stop.
2. `resilient-choco` has an open colleague PR (#160). Nothing in that repo was
   read except through `git cat-file`/`log`/`check-ignore`, and nothing was
   written. Whether the file should be committed, DVC-tracked, or the row
   withdrawn is that repo's decision, not this one's.
3. No control was added that shells out to sibling clones. `fleet_adapters.py`
   declares paths, not clones; a test that requires seven checkouts to be
   present would fail in CI for a reason that has nothing to do with the
   defect.

**Proposed**, for the signatory: fold the choco row into E-M10's authorised
fleet re-measurement rather than patching it separately, and treat the choco
verdict as unprovenanced until its `main:` artifact resolves from a ref. A
committed figure whose artifact exists on no branch is not distinguishable from
one nobody can check.

---

## E-M13 — the instrument's read semantics changed; the eight repos pin it by branch

**Raised by** `COMMITTED-READS` on `feat/loop-mlkit-1`, which closed the
mechanism behind E-M12: `core.artifact.load()` now reads
`git cat-file blob HEAD:<relpath>` and refuses to serve a figure git does not
have, rather than serving it with a provenance flag attached.

**Measured** locally, A-1, no cloud and nothing fitted:
`.venv/bin/python -m pytest tests/test_committed_reads.py tests/test_fleet.py
tests/test_promotion_state.py tests/test_fabricated_defaults.py -q
--timeout=180` → **152 passed** (python 3.14.6, pytest 9.1.1). The twenty new
controls are proven by mutation rather than by inspection: reverting `load()` to
working-tree reads fails 7 of them, disabling `refuse_uncommitted` fails 3,
dropping the new PASS invariant fails 1, and laundering the marker through
`_compare` fails 1.

**Why this needs a decision rather than a commit.** `CHANGELOG.md`'s opening
paragraph states the exposure plainly: all eight model repos pin mlkit with
`branch = "main"`, so every commit here reaches every repo the next time anyone
runs `uv lock` — an instrument change arriving as ambient drift. This change is
exactly the kind that must not arrive that way. A repo that upgrades without
noticing will see fleet cells that were numbers become
`NA (not committed at HEAD: …)`, and the correct reading of that NA is "commit
the artifact", not "the tool broke".

**Proposed**, and deliberately **not done here**:

1. Settle the open question E-M08, E-M09 and E-M11 all record — whether this
   line's major is `0.5.0` or `1.0.0` — and then cut the tag. Tag-cutting is a
   release decision of record and is the session lead's per E-M11; no branch in
   this round cuts one and `__version__` is untouched at `0.5.0`.
2. Move the eight adopters off `branch = "main"` and onto that tag, so that the
   next instrument change is a reviewable upgrade. This is eight repos'
   manifests, three of which have open colleague PRs (choco #160, blackout #129,
   triage #94), so it is a fleet-wide records change and not an agent's.
3. Fold the choco row into E-M10's authorised fleet re-measurement, as E-M12
   already proposed. Nothing about that changed here except that the row will
   now come back as an NA naming the file rather than as a figure nobody can
   fetch. `portfolio/FLEET_VERDICTS.md` and its `.json` twin were NOT
   regenerated on this branch and are byte-identical to `main`; the table stands
   as measured until that authorised run.

**What an adopter should do on upgrade**, once the tag exists: run
`mlkit portfolio` and read the NA reasons. Every `not committed at HEAD` names a
file that repo owns. The remedy is that repo's — commit it, DVC-track it, or
withdraw the row — and `mlkit portfolio --allow-dirty` will show what the
pointers resolve to in the meantime, while writing nothing and exiting non-zero.

---

## E-M14 — three champion-record shapes across eight repos; the fleet should converge on one

**Raised by** `SV-4-PARITY-DISCOVERY` on `feat/loop-mlkit-5`, which found that
`scripts/verify_served_hash_parity.py` could see only one of them and was
reporting the other two as "this repo serves nothing hash-pinned yet" — a claim
about three repos that the scanner had never measured and that was false for all
three.

**Measured** locally, A-1, nothing fitted, nothing written into any model repo:
`.venv/bin/python scripts/verify_served_hash_parity.py` at mlkit `f48334f`,
python 3.14.6, artifact `reports/served_hash_parity.json`
sha256 `5859c659babbb381dfb225c2b3ab154f13c531a2e3624c9497d90e4c1d5913cc`,
generated 2026-08-29T15:44:08Z. Eight artifacts compared, eight matched, none
differed, none unresolvable. The shapes, as measured:

| Shape | Repos | Where | What the digest covers |
|---|---|---|---|
| `canonical_self_hash` — top-level `artifact_sha256` | fray (×2), chokepoint (×2), triage | `models/<name>/champion*.json` | the record's own canonical JSON, every field |
| `sidecar_coefficient_digest` — top-level `artifact.{path,sha256}` | arabica, torrent, surge | `models/<name>/model.json`, and for surge `data/model_registry/<name>/model.json` | only the separate coefficient file's bytes |
| neither | choco, blackout | — | nothing pinned; NA is correct for these two |

**Why this is a decision and not a commit.** The two shapes are not two
spellings of one property. A `canonical_self_hash` covers the whole record: its
metrics, its split counts, its provenance prose and its licence quotations all
move the digest, so none of them can be edited after promotion without the
serve path refusing to construct. A `sidecar_coefficient_digest` covers the
coefficients and nothing else. Arabica's `model.json` carries `val_scoring`,
`split` row counts and a `training_provenance` block; torrent's carries a
`committed_val_row` with a median NSE and an `escalation` id; surge's carries
`metric_warnings` recording that the model loses to a baseline on val. **None
of that is under any digest today.** Those fields can be edited, and every
digest in the fleet still verifies.

Three further asymmetries the parity run surfaced, each of which a converged
shape would settle:

1. **Root.** Surge's registry is at `data/model_registry/`, everyone else's at
   `models/`. Any fleet tool that hardcodes one root silently omits the other,
   which is precisely the defect being reported here.
2. **Tree.** Triage's champion is committed on `.worktrees/e029` and is absent
   from its checked-out `main`. The row exists only because discovery now falls
   back to linked worktrees, and it is flagged `scope_note: evidence about that
   worktree`. A row that is true of one branch and not of the repo is not a
   fleet fact.
3. **Movement.** fray's two recorded digests are not the ones
   `reports/served_hash_parity.json` carried before this run —
   `b6a9b933…`/`cba79308…` at fray `3b1941f`, now `b862f7f5…`/`da2d0773…` at
   fray `aef69ed`. fray's own commit `5abe3aa` ("R10-REPIN: both champions
   re-serialized from a clean tree, and nothing measured moved") explains it and
   both still self-verify. This is recorded because a digest moving between two
   runs of a parity tool is exactly the event the tool exists to make visible,
   and it should be visible even when it is benign.

**Proposed**, for the signatory, and deliberately **not done here**:

1. Adopt `canonical_self_hash` as the fleet's one champion-record shape, with
   the coefficient pin kept *inside* the sealed record rather than instead of
   it — `core.served.seal()` over a payload that itself contains
   `artifact.{path,sha256}`. That is strictly additive for arabica, torrent and
   surge: no existing digest changes meaning, and the record's own fields come
   under a digest for the first time.
2. Settle one root and one filename. `models/<registered_name>/champion.json`
   is the majority shape; surge's registry is the outlier and the move is a
   path change in that repo, not a re-measurement.
3. Decide whether a champion committed only on a linked worktree counts as
   served. Triage is the live case. Either it lands on the branch the repo
   serves from, or the fleet reports it as out-of-scope — the current answer,
   a flagged row, is a disclosure and this repo has already learned once
   (E-M12) that disclosure beside a figure is not a control.

This is a fleet-wide records change touching eight repos, three of which have
open colleague PRs (choco #160, blackout #129, triage #94). Under CLAUDE.md
rule 12 the convergence decision is the signatory's. Nothing in this branch
changes any model repo: the scanner reads files and runs read-only `git`
commands, and no champion record anywhere was rewritten.

---

## E-M15 — `portfolio/FLEET_VERDICTS.md` can no longer be regenerated as a side effect

**Measured 2026-08-29** with `mlkit portfolio` (v0.5.0) against the eight
checkouts as they then stood, compared against the committed table generated
`2026-08-29T06:40:14+00:00` at mlkit `034122f`.

The committed table records the eight repos at the branches they had checked
out when it was written — arabica at `feat/observed-panel-and-fabrication-gates`,
blackout at `e021-decision`, triage at `e028-decision`, torrent at
`feat/r9-attributes-and-declared-scale`. Most have since moved, several to
`main`, and the artifacts the adapters name did not all move with them.
Measured cell by cell over the two JSON payloads (comparing each cell's
`value`, since the 0.4.0 payload predates the `allow_dirty_read` field and a
whole-dict comparison reports every cell as moved): **twelve cells' values
differ between the committed table and a regeneration today.** Two are this
branch's repair. The other ten were moved by the world:

* **six choco cells** go NA — E-M12's uncommitted artifact, unreadable since
  committed reads landed;
* **two blackout `model_of_record` cells** go NA, because
  `reports/train/weather_failure_all_in_scope_gate.json` is not on the branch
  that repo now has checked out;
* **two torrent `test_arm_spent` cells** move 1 → 5, because torrent's
  `reports/holdout_reads.jsonl` grew from 754 bytes to 36,787.

Measured coverage falls from 103 cells to 97, and triage's champion is now read
from a linked worktree rather than from its checkout.

Two consequences, and neither is fixable from here:

1. **Regenerating in place is now its own change, not a by-product.** Doing it
   inside this branch would have bundled the ten unrelated cell movements
   above — a measured-coverage drop from 103 cells to 97 — into a change about
   a measurement primitive, where nobody would read them. This branch therefore
   leaves `portfolio/FLEET_VERDICTS.md` byte-identical and puts the
   before/after regeneration under `reports/fleet_verdicts_torrent_record/`
   instead, where the two arms were run back to back against one identical set
   of checkouts (`repos_read` identical between the arms, asserted in
   `CELL_DIFF.txt`).
2. **`tests/test_fleet.py::test_the_declared_branches_match_the_committed_provenance_table`
   holds `BRANCH_ONLY_EVIDENCE` against the branch column of the committed
   table.** A regeneration moves that column and the control fails — correctly:
   the adapters' branch notes were written for `e021-decision` and
   `e028-decision` and the world has moved off them. The repair is to
   re-measure where blackout's and triage's evidence now lives and rewrite the
   notes to match, which is a claim about two repos that both carry open
   colleague PRs (blackout #129, triage #94).

**Recommended, not done here**: one deliberate regeneration commit that
re-measures the branch dependence first, updates the adapter notes and
`BRANCH_ONLY_EVIDENCE` from that measurement, and then writes the table — with
the ten moved cells read and explained one by one rather than absorbed. It is
not urgent and it is not a gate change; it is a re-reading, and it should not
be done in the same breath as anything else.

---

## E-M16 — surge's E-038 is CONFIRMED and NOT CLOSED: the token list it proposes fires on Conv2d flags and crop growth stages

**Raised** 2026-08-29 on `fix/r11-tokeniser-defeated-by-naming`, while repairing
R11's own naming defeat. resilient-surge asked the mlkit owner to close E-038
by adding fifteen tokens to `MEASURED_TOKENS`. This entry measures both halves
of that request and closes neither.

### The blind spot is real, and it is still open today

`resilient_mlkit.core.fabrication.is_measured_name` returns `False` for every
one of the seven score-shaped names E-038 lists:

    peak_obs_m  peak_pred_m  val_peak_timing_error  val_peak_magnitude_error
    pred_std    truth_std    train_mean_used_for_constant

Measured 2026-08-29 from this branch's `fabrication.py`. E-038's conclusion
stands: a green R10 in surge means "no fabricated default was found under a
name in the fleet token list", not "no fabricated default was found".

### E-038's counts are stale, and the corrected ones are recorded here

Re-running E-038's own procedure over the three artifacts it names, as they
stand in resilient-surge on 2026-08-29:

| quantity | E-038, 2026-08-23 | re-measured 2026-08-29 |
|---|---|---|
| numeric key names | 54 | 33 |
| recognised as measured | 17 | 15 |
| not recognised | 37 | 18 |

The artifacts changed between the two dates; `val_peak_timing_error` and
`val_peak_magnitude_error` now ship as `test_peak_timing_error` and
`test_peak_magnitude_error`, and `pred_std`, `truth_std` and
`train_mean_used_for_constant` are no longer present. All four surviving names
remain invisible to `is_measured_name`. **The defect is unchanged; only its
extent was overstated.**

### Why the proposed repair is not applied

E-038's fifteen tokens were applied to a throwaway copy of `fabrication.py`
and R10 was run over two repos' `src/` trees, current vocabulary against
proposed:

| repo | R10 findings, `src/` only, today | with E-038's tokens |
|---|---|---|
| resilient-surge | 0 | 9 |
| resilient-torrent | 1 | 9 |

Seventeen new findings on two `src/` trees, and inspecting them is the point:

* **Real, and serious.** `torrent/scs/ingest/usgs_nwis.py:112` —
  `discharge_cfs` returned from `fetch_discharge_cfs()` as `rng.normal(...)`.
  `surge/serve/hazard_obs_bias.py` — seven `bias_m <- 0.0` returns from
  absence and except branches of `coops_hazard_bias_m()`, which is a zero bias
  reported when the comparison could not be made.
* **Over-fire, from the same list.** `torrent/eo/prithvi_cafe/model.py:42` —
  `bias <- True`, passed as `Conv2d(bias=...)`. That is a layer flag.
  `torrent/scs/vulnerability/agricultural_damage.py:122,174` —
  `stage_factor <- 1.0`, where "stage" is a crop growth stage in a damage
  curve, not river stage. `bias`, `stage`, `setup` and `yield` are polysemous
  in this fleet, and three of the fifteen tokens put R10 onto PyTorch
  constructor arguments and agronomy.

A vocabulary change that fires on `Conv2d(bias=True)` is a check that gets
turned off, which costs more than the seven names it would gain. The list
cannot be adopted as proposed, and pruning it to the safe tokens is a decision
about R10's own definition of a measurement — not a by-product of an R11
branch whose controls establish nothing about R10.

### What should close it, and why it is not a longer list

This branch fixed the same shape one check over. R11 could not fire on a fully
synthetic loader stamped `source="era5_land"` because it read the LABEL rather
than the thing the label describes, and the repair was not another token: it
asks whether every value on the record was manufactured in this process. R10
has the same shape of defect. It decides whether a number is a measurement by
whether its NAME is in a list, so the cheapest evasion is a name not on the
list — and the next unrecognised metric will be called something else, exactly
as the next synthetic loader would have been.

The substantive repair is for R10 to ask of the VALUE what R11 now asks of the
record: was this number computed from anything, or was it written down? A
literal returned from a function that reads no input is a fabricated default
whatever it is called, and a number computed from real inputs is not one even
when its name is `bias`. That is a change to R10's trigger, it moves R10
across all fourteen repos, and it needs its own controls and its own fleet
delta.

Note also that R10 and R11 disagree about `usgs_nwis.py:112`, and R11 is right
there: the record is stamped `source="synthetic_ci_smoke"`, which declares what
it is, so R11 is correctly silent. A widened R10 would report it. That
disagreement is another thing the owner must settle before the vocabulary
lands.

**Status: E-038 CONFIRMED, NOT CLOSED.** Not blocked by anything in this
branch; blocked on an R10 change being scoped as its own work.

**UPDATE 2026-08-30 — that work is done, on
`fix/r10-metric-name-blindness-e-038`. See E-M18 below.** The fifteen tokens
were NOT adopted; `MEASURED_TOKENS` is byte-identical to this entry's version,
so the `Conv2d(bias=True)` and crop-growth-stage over-fire measured here cannot
occur. E-M16's own prescription — "ask of the VALUE what R11 now asks of the
record: was this number computed from anything, or was it written down" — is
what the repair implements, applied to the name's DECLARATION: a name enters
R10's universe when the repo itself computes a figure under it.

---

## E-M17 — R11's `CONTRADICTED_SOURCE` is still decided by a field-NAME list

**Raised by:** adversarial verification of the R11 repair
(`fix/r11-tokeniser-defeated-by-naming`, `74919f8`), 2026-08-29.
**Status: PARTIALLY CLOSED by T8-4 (`fix/e-m17-value-side-source-adjudication`),
2026-08-29. The field-NAME half is closed. Two measured residuals remain and
are recorded below.** Not a regression — the branch is a real improvement and
the four findings it discovers are all real. This is the residue.

### What was measured

The repair removed the naming defeat from the provenance VALUE: a wholly
manufactured record stamped `source="era5_land"` is now `CONTRADICTED_SOURCE`,
and the byte-identical record stamped `source="era5_land_shaped_synthetic_grid"`
is still silent. That half holds under attack — an invented value
(`label_origin="ccc_regional_returns_2019_2024"`) still fires, so the rule is
not reading a token list of product names.

The defeat moved up one level. A stamp only becomes a source claim when its
FIELD is in `SOURCE_NAMING_FIELDS`. Taking the module's own positive control
and renaming nothing but the field:

| field carrying `"era5_land"` on the identical wholly-manufactured record | R11 |
|---|---|
| `source` (the shipped control) | CONTRADICTED_SOURCE |
| `data_product`, `product`, `feed`, `provider`, `network`, `archive`, `registry`, `upstream`, `repository`, `portal`, `reanalysis`, `vendor`, `series`, `feed_name`, `api`, `corpus`, `supplier`, `channel`, `stream`, `obtained_from`, `retrieved_from`, `derived_from`, `input_dataset`, `basis` | SILENT (24 of 24) |

R5 does not close the gap. R5 reads whatever a repo's own `provenance()`
adapter returns as `{split: {kind: count}}`, so the field a repo keys its
manifest on is repo-local and arbitrary; a repo keying on `data_product` would
have its fabricated rows counted as `real` with R11 silent.

### Why the obvious repair is not applied

Extending `SOURCE_NAMING_FIELDS` is the repair this branch spent itself
arguing against one level down: the next stamp will be called something else.

Inverting the direction — on a wholly manufactured record, treat ANY opaque
string-constant field as a source claim — was applied to a throwaway copy in
scratch (not committed) and run over all fourteen `resilient-*` checkouts:

| | shipped rule | inverted probe |
|---|---|---|
| fleet findings | 4 | 29 |

Inspecting the 25 new ones, it is the E-038 pattern again — part discovery,
part noise from the same change:

* **Real, and serious.** `resilient-chokepoint/src/resilient_chokepoint/counterfactual/climate_model_runners.py:27,52,76,99` —
  `factual_throughput_mtpd` and `counterfactual_throughput_mtpd` built from
  four literals plus `rng.normal(0, 0.3)`, returned under
  `scenario_name="SSP1-2.6 vs SSP5-8.5 (CMIP6-driven)"` from a function whose
  docstring says "using CMIP6 temperature deltas". There is no CMIP6 in the
  module. `avoided_disruption_days` is derived from those numbers.
  `resilient-choco/scripts/train_cqr.py:294` — `yield_observed_t_ha` assigned
  from `rng.normal(...)`, on a record stamped `country_iso3="GHA"`.
* **Over-fire, from the same change.** `freq="h"`
  (surge `storm_loader.py:205`), `currency="USD"` (torrent
  `loss_metrics.py:76`), `country_code="GLO"` (triage), `generator_version="1.0.0"`
  (torrent `event_set.py:350`), `match_role="treated"` (blackout and
  chokepoint `did_impact.py`), and prose `note=` / `interpretation=` fields
  matched on the word "observed" appearing inside a sentence that was
  declaring the data synthetic — torrent `v4_orchestrator.py:1287` fires on a
  note whose text is "these annual maxima were DRAWN, not observed".

A rule that reports a units string and an honest disclaimer is a rule that
gets turned off. It cannot ship as measured.

### What should close it

The same question one level further in: not "is this field name a source
field", but "does this string name something outside the process, and does
anything in this module reach outside to it". A record naming a source in a
module that performs no read, no request and no client construction is
contradicted by the module whatever the field is called. That is a change to
what `CONTRADICTED_SOURCE` triggers on, it moves R11 across all fourteen
repos, and it needs its own controls, its own fleet delta and its own
false-positive budget — the units/version/prose classes above are what that
budget has to buy off.

**Reserved to the owner of R11, not to a verification branch.** The two real
findings named above are reported here rather than repaired: repairing them is
each repo's own change.

### What T8-4 closed, and how it was measured (2026-08-29)

`CONTRADICTED_SOURCE` no longer consults the field name at all on the second
pass. On a record `manufactured_of` already proves WHOLLY manufactured —
precondition unchanged — any string-valued field is a source claim when its
value (a) claims observation on `OBSERVED_CLAIM_TOKENS` **and is a label
rather than a sentence**, or (b) reproduces two or more parts of a product
name in the repo's own signed `docs/allowlist.yaml` (one part suffices when it
is a designator: letters and digits, four characters or more). The allowlist
is READ, never written; the controls assert it is byte-unchanged after a scan.

Neither `PROVENANCE_FIELDS`, `SOURCE_NAMING_FIELDS` nor `OBSERVED_CLAIM_TOKENS`
gained an entry, and a control asserts that none of the 24 field names above is
in any of them while the check fires on all 24 — plus a 25th name generated
from `secrets` at test time, which no list can be extended to hold.

| | before T8-4 | after T8-4 |
|---|---|---|
| the 24 measured field renames, module's own positive control | 0 of 24 fire | 24 of 24 fire |
| a field name generated at test time | silent | fires |
| fleet findings, all 14 `resilient-*` checkouts | 4 | 4, finding-for-finding identical |

The false-positive budget the inversion could not pay was bought two ways,
both measured rather than argued:

* Branch (a) reads a LABEL, not prose. Without that guard it fired on three
  honest disclaimers — `empirical_coverage_unmeasured_reason` and
  `interpretation` in `resilient-blackout`, `vintage_delta_verdict="MEASURED"`
  in `resilient-surge`. All three were false.
* Two of those three had a second, deeper cause: `manufactured_of` read
  `payload["k"] = "literal"` as proof that `payload` was built in-process,
  because the target-name helper reports the base of a subscript. Element
  writes now prove nothing about the container. That is a fix to the
  conservative pass itself and it makes R11 quieter, not louder.

### What measurably REMAINS open under E-M17

1. **A manufactured record naming a product in NO allowlist.** The chokepoint
   `climate_model_runners.py` case above is still invisible: no chokepoint
   allowlist entry mentions CMIP6 (measured 2026-08-29,
   `grep -c cmip6 resilient-chokepoint/docs/allowlist.yaml` → 0), so branch (b)
   has nothing to match, and the value claims no observation, so branch (a)
   does not fire. Repairing the record is chokepoint's change; closing the
   DETECTION needs a source of truth for "is this a real product" that the
   portfolio does not have where the product is not allowlisted.
2. **A one-part, letters-only product name** — `product="chirps"`,
   `"aurora"`, `"prithvi"`, `"soilgrids"`. Two parts is what separates a
   compound of a registered name from a word two pieces of code happen to
   share; `coffee` is a part of five of arabica's forty entries.
3. **A stamp applied outside the record's own scope** (`_stamp(row)`): the
   record arrives as a parameter, so it is not provably manufactured.
4. **A source value the folder cannot read.** `_string_of` folds constants,
   one Name hop, one Attribute hop off the enclosing class, `JoinedStr` and
   `BinOp(+)`. Four other spellings of the SAME literal were measured SILENT
   against this branch on the otherwise-firing `data_product=` positive
   (adversarial verification 2026-08-29, driven against the branch worktree,
   arabica's own allowlist as the registry):
   `"_".join(["era5", "land"])`, `"era5_%s" % "land"`,
   `"era5_{}".format("land")`, and a module-level `FEEDS = {"primary":
   "era5_land"}` read back as `FEEDS["primary"]`. Silence on an expression the
   folder cannot resolve is the module's stated and deliberate direction, so
   this is a limit rather than a defect — but it is a limit, it is four more
   spellings than the six the branch closed, and it is recorded here because
   it was not.

### Adversarial verification of this branch (2026-08-29)

The R11 repair itself held: control A fires on all 26 field names and goes
silent on 25 of 26 with the value-side branch deleted (`25 failed, 1 passed`,
reproduced independently); control B holds on both trees; the fleet sweep over
all 14 `resilient-*` checkouts is byte-identical to main at 4 findings.

One defect was found and is fixed on `verify/t8-4-r12-report-nameerror`: the
registry disclosure line was pasted into `_write_r12_report`, which has no
`registry` in scope. That writer is unconditional, so **R12 raised
`NameError: name 'registry' is not defined` on every repo** — measured PASS on
main and RAISED on the branch for the same fixture repo. `tests/` on the
branch was `6 failed, 696 passed`; the five `test_served_reimplementation.py`
failures are that NameError, and the file had not been run. After the fix:
`703 passed, 3 skipped`, and every readiness check matches main's status on
the same fixture. `::test_control_c_the_registry_disclosure_is_r11s_and_r12_still_runs`
drives both report writers and fails when the line is put back.

**Residual tests, expected to FAIL the day each is closed:**
`tests/test_fabricated_targets.py::test_residual_a_product_in_no_allowlist_is_still_invisible`
and `::test_residual_a_stamp_applied_in_a_helper_is_still_invisible`. Both
assert the current, wrong silence. When one goes red, update this section
rather than re-pinning the silence.

---

## E-M18 — E-038 is CLOSED: R10's metric-name universe is derived from the adopter

**Raised and closed** 2026-08-30 on `fix/r10-metric-name-blindness-e-038`.
E-M16 confirmed E-038 and refused to close it by extending `MEASURED_TOKENS`,
because the fifteen proposed tokens put R10 onto `Conv2d(bias=True)` and crop
growth stages. This entry records the repair that was taken instead, everything
it moved, and the two things it does NOT close.

### The blind spot, re-measured against surge's own registry

`src/resilient_surge/evaluation/metrics.py` at `8b71343` declares twelve public
metric callables. `is_measured_name` classifies eight and is blind to four:

    peak_timing_error   peak_magnitude_error   false_alarm_ratio   aal_bias

The consequence is in surge's source, not in the abstract. In that one file
`f1_score`, `iou` and `hit_rate` were repaired to raise `Unmeasured` on a 0/0
denominator; `false_alarm_ratio` still returns `0.0` on the identical
degeneracy — a perfect no-false-alarm score reported from nothing. **The repair
stopped exactly where the word list stopped.**

Spelling defeats the list independently of vocabulary: `csi` IS in
`MEASURED_TOKENS`, and `critical_success_index` never reaches it, because
`tokenise` splits it into `critical`/`success`/`index`.

### What the repair is

`core/metric_registry.py`. A name enters R10's universe for a repo when a
callable in the trees that repo declares under `[source]` computes a number
from its own parameters — an arithmetic `BinOp` at a return, after unwrapping
`float()`/`int()`/`round()`/`abs()`, both arms of a ternary, and one hop
through a local. No list of names is involved anywhere.

`MEASURED_TOKENS` is unchanged, and keeps one job: it is the only leg a FAIL
may rest on, because `satisfies_a_gate` reads polarity off those words.

### Three verdicts, and why the new one is NA rather than FAIL

* vocabulary name → FAIL, unchanged;
* registry-only name → severity `UNCLASSIFIED_NAME`, R10 renders **NA quoting
  the name**. mlkit has no polarity for a name it does not know, and
  `calculate_payout` returning `0.0` below its trigger is correct domain
  behaviour, not a fabrication. The wrong answer here is silence, which is what
  it used to be;
* the derivation's own anchor probe failing → NA.

### What moved, measured at the adopters' mains on 2026-08-30

Driven with `mlkit` at `7d36930` (main) and at this branch, in separate
interpreters, each asserting its own `resilient_mlkit.__file__` before
answering.

All eight repos at their REMOTE mains, R10's verdict on each:

| repo | main SHA | main R10 | branch R10 | registry | of those, mlkit's vocabulary knew |
|---|---|---|---|---|---|
| choco | `422b758` | FAIL, 1 defect | FAIL, 2 defects + 9 unclassified | 138 | 4 |
| arabica | `f659de5` | PASS | **FAIL, 2 defects** + 9 unclassified | 157 | 4 |
| fray | `89b7d04` | FAIL, 5 defects | FAIL, same 5 + 1 unclassified | 50 | 1 |
| torrent | `4a159ac` | FAIL, 1 defect | FAIL, same 1 + 15 unclassified | 148 | 6 |
| chokepoint | `52ac929` | FAIL, 2 defects | FAIL, same 2 + 6 unclassified | 110 | 1 |
| surge | `8b71343` | PASS | **NA**, 16 unclassified | 103 | 7 |
| triage | `7578f51` | FAIL, 3 defects | FAIL, same 3 + 11 unclassified | 103 | 1 |
| blackout | `141108c` | PASS | **NA**, 15 unclassified | 109 | **0** |

**The last column is E-038 as a number.** On blackout, R10 was checking NONE of
the 109 names that repo computes figures under. On chokepoint, 1 of 110. Every
green R10 in this fleet meant "no fabricated default under a name in mlkit's
word list", and on three repos that word list overlapped the repo's actual
metric surface by at most four names.

Finding-level diff across all eight: **0 lost, 0 severities changed, 84 added**
— 81 `UNCLASSIFIED_NAME` (the NA lane) and 3 in the FAIL lane, which are named
below. Accepted-set diff over a 482-name universe (mlkit's three token sets plus
every adopter's registry), both `config_context` values: **0 names newly
accepted**; 96 / 49 / 109 newly refused on surge / fray / chokepoint.

### Three additions land in the FAIL lane, and they are disclosed, not hidden

Widening the name question also widens SINK detection: a function whose name the
adopter's registry recognises as figure-producing now counts as returning a
figure, so a VOCABULARY-named symbol that previously reached no sink can now
reach one. Three such, and the severity still rests on the vocabulary leg — the
polarity claim is never made from a derived name:

* `arabica src/analysis/coffee_mediation_pipeline.py:140,141` —
  `clr_loss_fraction = biotic_baseline.get("clr_loss_fraction", 0.0)`, and the
  mediation effect `float(p - b)` is returned from
  `_resolve_mediator_scalar()`. A coffee-leaf-rust LOSS FRACTION defaulting to
  zero, i.e. "no rust", when the key is absent. **This flips arabica PASS →
  FAIL and it is a real finding of R10's own defect class.**
* `choco src/models/process/bma.py:50` — `score = sum(weights.get(k, 0.0) * v
  ...)`; a BMA weight missing from the weights file contributes zero silently.
  `PUBLISHES_UNMEASURED`; choco was already FAIL, so no verdict moved.

Repairing all three is those repos' change, not mlkit's (rule 7).

### surge's PASS did move, and it moved onto real defects

Reported plainly because a control said honest PASSes should not flip. The
sixteen sites are surge's own committed code, and at least five are the defect
class R10 exists to catch, each with a repaired sibling in the same file:

    evaluation/metrics.py:228                    false_alarm_ratio      = 0.0
    evaluation/metrics.py:156                    peak_magnitude_error   = 0.0
    evaluation/hindcast_suite/skill_metrics.py:70  false_alarm_ratio    = 0.0
    evaluation/hindcast_suite/skill_metrics.py:83  critical_success_index = 0.0
    evaluation/probabilistic/flood_event_metrics.py:89  false_alarm_rate = 0.0
    evaluation/probabilistic/flood_event_metrics.py:103 missed_detection_rate = 0.0
    evaluation/probabilistic/insurance_metrics.py:53    aal_bias        = 0.0

Repairing them is surge's change, not mlkit's (rule 7). Others in the sixteen —
`calculate_payout = 0.0` below a trigger, `rate_on_line = 0.0` — are plausibly
correct domain behaviour, which is exactly why the verdict is NA and not FAIL.

chokepoint's six include `_montiel_olea_effective_f = 0.0`, a weak-instrument
F statistic defaulting to zero, and `_evalue = 1.0`.

### WHAT THIS DOES NOT CLOSE

1. **A metric computed entirely inside a call.**
   `return float(np.divide(fp, fp + tp)) if (fp + tp) > 0 else 0.0` leaves no
   arithmetic `BinOp`, so the name never enters the registry and the `0.0` is
   not reported. Admitting any call would enrol every function in a repo.
   Stated as a limit and pinned by
   `tests/test_r10_metric_name_universe.py::test_residual_a_metric_computed_inside_a_call_is_still_invisible`,
   which fails the day it closes.
2. **`value = ... if ... else 0.0; return value`** is not attributed to the
   enclosing function by R10's scanner. This is an OLD R10 limit, not an E-038
   one: measured identical on `rmse`, a name the word list has always known.
   Pinned as a pair by
   `::test_residual_a_computed_local_returned_by_name_is_an_OLD_r10_limit`.
3. **E-M17 residual 4** (`"_".join([...])`, `%`, `.format`, dict read-back at a
   provenance stamp) is deliberately NOT closed here. It was examined and does
   not share this mechanism: E-038 is an enumerated NAME UNIVERSE in R10;
   residual 4 is the reach of R11's constant FOLDER in a different check with a
   different registry. Making an unresolvable expression a refusal there needs
   its own over-fire budget and its own control pair. It stays recorded under
   E-M17.

**Status: E-038 CLOSED. E-M16 superseded by this entry. E-M17 residual 4
unchanged and still open.**

---

## E-M19 — R10's `absence adjudicated as a pass` fired on honest NA guards; the fix's residual

**Raised and repaired** 2026-08-31 on `fix/r10-scan-or-absence-guard-false-positive`.
The false positive is CLOSED. The residual named at the bottom is OPEN.

### The false positive

`_scan_or` admitted any `or` expression containing an `is None` compare and
emitted `absence adjudicated as a pass` without ever reading the other
operand. The shape the check exists for is

```python
parallel_trends_ok = p_value is None or p_value > alpha
```

where the SECOND operand is the whole defect: it is the adjudication, and the
`is None` arm is what lets an unmeasured p-value satisfy it. Reading only the
first arm made the rule match its own opposite:

```python
# resilient-chokepoint scripts/fit_corridor_ensemble_weights.py:249
"holdout_mae": None if holdout_mae is None or np.isnan(holdout_mae) else round(holdout_mae, 6),
```

Every operand there is an absence test on the same figure, the taken branch
writes `None` rather than a number, and lines 380-382 of the same script
refuse to promote unless BOTH holdout figures were measured and beat the
margin. Absence refuses; it is not adjudicated as a pass.

### What it cost, before the repair

One tree, two verdicts. `reports/readiness.md` committed at chokepoint
`52ac929` records `R10 | PASS`; a fresh `mlkit check --phase readiness` at
mlkit `c65b2e7` over that same tree returned R10 FAIL naming
`fit_corridor_ensemble_weights.py:249` and `:252` and nothing else
(nonce `mlkit-20260831T042310Z-9843aed63cb2`). A green readiness table was
unreachable for chokepoint without editing chokepoint — which would have been
editing honest code to satisfy a broken instrument. mlkit is the fleet's only
source of numbers; a scanner that fires on honest NA guards makes every table
it touches red for a wrong reason, and that is how a reader learns to overrule
a red gate.

*Caveat recorded so it is not read as more than it is:* the committed
`readiness.md` at `52ac929` was itself produced on an earlier branch
(`feat/observed-trade-and-fabrication-gates`, SHA `11a06e57`, nonce
`mlkit-20260822T082253Z-7a18f55fd943`), not at `52ac929` with mlkit 0.5.0. It
is evidence that this shape once passed, not a same-run tie.

### Measured population, before touching anything

`fabrication.scan_file` over every `*.py` in the ten `resilient-*` checkouts,
mlkit at `c65b2e7`: 177 findings, of which **7 carried this shape and all 7
were guards of this family** —

| repo | site | other operand |
|---|---|---|
| chokepoint | `scripts/fit_corridor_ensemble_weights.py:249` | `np.isnan(holdout_mae)` |
| chokepoint | `scripts/fit_corridor_ensemble_weights.py:252` | `np.isnan(holdout_baseline_mae)` |
| fray | `scripts/stress_readout_county_yield.py:318` | `not eligible` |
| fray | `scripts/stress_readout_county_yield.py:444` | `best_precision is None` |
| fray | `scripts/stress_readout_county_yield.py:447` | `best_recall is None` |
| fray | `src/validation/error_decomposition.py:131` | `observed_mean <= 0.0` |
| backend | `api/services/investment_case.py:350` | `cumulative_expected_loss_usd is None` |

Not one is a fabrication; every one reports `None` where the figure is absent.
After the repair the identical walk returns 170 findings: those 7 gone, **0
added, 0 severities changed, every other finding at the same file, line,
symbol and shape**.

### The rule now

The admitting predicate — "does this `or` contain an `is None` arm" — is
copied byte-for-byte into `_has_none_arm`, so the narrowing provably applies
to what the shape does with an admitted expression and not to which
expressions are admitted. On top of it, at least one operand must sit OUTSIDE
the absence guard. The guard is four things and no more:

1. an `is None` test;
2. a degeneracy `Compare` — `len(folds) == 0`, `observed_mean <= 0.0`;
3. `not <name>` — an empty population;
4. a NaN/NA question about an ALREADY-GUARDED figure — `np.isnan(x)`,
   `pd.isna(x)`, `math.isnan(float(x))`, `not np.isfinite(x)`.

Leg 4 is name-scoped on purpose: `mae is None or np.isnan(other)` asks about a
second figure, adjudicates on it, and stays reportable.

### One draft was measured and discarded

The first draft delegated the guard test to `_is_absence_test`. That helper
ignores polarity for calls, so it reads `BASELINE.is_file()` as an absence
test — and `coverage is None or BASELINE.is_file()` is choco's
fixture-presence gate written as an `or`, a real self-passing gate. The draft
silenced it. Measured, discarded, and pinned:
`tests/test_fabricated_defaults.py::test_control_a_every_adjudicating_operand_still_fires[fixture-presence-as-a-verdict]`.

The rule was also deliberately NOT narrowed to "the other operand must be a
threshold `Compare`", which the work item proposed: `ok = run is None or
run.passed` adjudicates through an attribute and is the same defect. The
weaker and more faithful requirement — an operand outside the guard — keeps it.

### RESIDUAL, OPEN

A verdict whose other operand is itself a degeneracy test on the guarded
figure now goes silent:

```python
rmse_gate_passed = rmse is None or rmse <= 0.0   # silent since this change
rmse_gate_passed = rmse is None or rmse <  1e-9  # silent since this change
rmse_gate_passed = rmse is None or rmse == 0.0   # silent since this change
rmse_gate_passed = rmse is None or not rows      # silent since this change
```

All four fired before. They follow from this module's own long-standing
definition of a degeneracy test (`_is_absence_test`), which fray's
`error_decomposition.py:131` legitimately relies on, so the two cannot be
separated by structure alone. **There is no instance of any of the four
anywhere in the ten checkouts** — the fleet walk above is the measurement —
so nothing is lost today. Closing it needs a discriminator this repair does
not have: whether the `or` expression is the VALUE of the verdict or merely
the CONDITION selecting between two values. In all 7 false positives it was a
condition (an `IfExp` test or a comprehension filter); in the defect shape it
is the value. That is a second, independent narrowing with its own over-fire
budget and its own control pair, and it is not taken here.

**Status: the false positive CLOSED. The residual OPEN and unassigned.**

## E-M20 — the served contract decided promotions on three things nobody had to state, and a verdict nobody could not edit

**Raised:** 2026-08-31, round 8, G-SERVED train (M-01 → M-02 → M-03 → M-06), one branch.
**Status: the four holes CLOSED. Four residuals OPEN and disclosed below, each pinned by a test that fails the day it closes.**

### The four defects, driven at `8517341` before any repair

Every drive below asserted `resilient_mlkit.core.served.__file__` /
`resilient_mlkit.core.result.__file__` under the branch tree, so the numbers
belong to this checkout and not to an installed wheel.

| # | Drive | Result at `8517341` |
|---|---|---|
| 1 | `challenger_decision([Comparison(bar, "mape", -0.05, 0.20, 500, arm="val")], ...)` | **PASS**, `promotable=True`, `skill {'mape': 1.25}` |
| 2 | `challenger_decision([Comparison(bar, "r2", 0.10, 0.90, 500, arm="val")], ...)` | **PASS**, `promotable=True`, `skill {'r2': 0.8888888888888888}` |
| 3 | `ChallengerDecision(status=PASS, reason=..., recorded_bar=bar, metrics=(), skill={})` | constructed, `promotable=True` |
| 4 | `r = CheckResult.failed(...); r.status = Status.PASS; r.evidence = {}` | both assignments succeeded; `to_dict()["status"] == 'PASS'` |
| 5 | `Comparison(bar, "mae", 80.0, 100.0, 500, arm="val").row_matched` | `True`, with no row evidence of any kind; the decision **PASSed** |
| 6 | `hasattr(core.result, "GateAggregate")` | `False` |

Rows 1 and 2 are one root cause: `skill()` hard-coded `1 - candidate/reference`
— the lower-is-better formula — and applied it to whatever metric name the
caller passed, without asking which direction that metric runs in or what
values it can take. A model worse on r² by eight tenths promoted. A MAPE that
cannot exist promoted hardest of all, because the impossibility pushed the
quotient furthest.

Rows 3 and 4 are one shape: a guard placed at one point on the timeline, or on
one path into an object, and absent everywhere else. `challenger_decision()`
refused an empty metric set; the public verdict TYPE did not, and the function
could simply be stepped around. `CheckResult.__post_init__` holds this
package's most load-bearing invariants and held them exactly once, at
construction, after which every field it guards was an ordinary mutable
attribute. Neither guard was weak. Both were in the wrong place.

Row 5 is the same shape once more, spelled as a field default:
`row_matched: bool = True`. The gate's row-set clause was real and fired
correctly — on a value the CALLER supplied. So it protected exactly the
comparisons whose authors had already thought about row sets, and every
comparison that had never thought about them made the strongest possible claim
about them for free.

Row 6 is an absence: mlkit had no aggregate verdict type, so the adopter that
needed one wrote it. `resilient-fray/src/registry/promotion_gate.py` — mutable
`GateResult` at `:401`, `GateResult(passed=True)` at `:851`, narrowed with
`&=`. It starts at TRUE and is argued down; `passed` is a stored field and can
be assigned; and `&=` collapses three statuses into two, so NA has to become
one of them. That is rule 7's failure mode arriving one layer up.

### What closed them

* **M-01** — `LOWER_IS_BETTER` / `HIGHER_IS_BETTER`, `REAL` / `NONNEGATIVE`,
  declared as DATA on the `Comparison` in the shape `ServeArms` already makes
  the arm policy data. `skill()` takes a keyword-only `polarity` with **no
  default** and computes `candidate/reference - 1` for higher-is-better. New
  refusal classes `IMPOSSIBLE_MEASUREMENT` and `POLARITY_UNDECLARED`, kept
  apart because one sends a reader to the scorer and the other to the binding.
  **No name→polarity table**: that is E-038 (`core.metric_registry`)
  re-introduced at the point that decides promotions.
* **M-02** — `ChallengerDecision` refuses `metrics=()` as its FIRST clause, since
  every later clause is a comprehension over it and an empty tuple satisfies
  them all vacuously. `CheckResult` gains `VerdictSealed` and a `__setattr__`
  that refuses every verdict field after construction, plus `SealedEvidence`,
  a dict subclass refusing all seven mutating methods (a seal that refused only
  `r.evidence = {}` is defeated by `r.evidence.clear()`). The three runner
  stamps (`repo`, `git_sha`, `nonce`) stay writable once and refuse
  re-stamping onto a different value. A SEAL, not a re-validation: re-validation
  refuses only structurally illegal states, and a FAIL carrying evidence flipped
  to a PASS carrying the same evidence re-validates cleanly.
* **M-03** — `GateAggregate`, frozen, `passed` a property equal to
  `all(status is PASS)`. No field to assign, no initial value to leave standing,
  no accumulation step to skip. **NA is not PASS**, and neither are DEFERRED,
  STALE or ESCALATED. Refuses an empty check set, a repeated check id, and a
  bare bool posted in as a check.
* **M-06** — `row_set_digest()` as the one definition of the tie;
  `candidate_row_digest` / `reference_row_digest` refused unless empty or
  64 hex; `row_matched` becomes `field(init=False)`, derived, with a third
  state the old field could not hold — `None`, UNTIED, which is NA at the gate
  under the new class `ROW_SET_UNTIED`. `Comparison(..., row_matched=True)` is
  now a TypeError: the assertion cannot be spelled by anyone.

Each of the four was committed fire-then-fix where the pin could be made to
fail first, and every guard was mutated back out afterwards to prove the pins
are alive (twelve mutations, all killing at least one pin). Gate: mlkit full
pytest, **757 at `8517341` (re-measured on branch start) → 830**, nothing
pre-existing lost or weakened.

### Three further holes found by attacking the repairs, and closed in the same branch

Driven against the branch *after* M-01/M-02/M-03/M-06 landed:

* `ChallengerDecision(status=PASS, ..., skill={"m": float("nan")})` constructed
  and reported `promotable=True` — `float('nan') <= 0.0` is `False`, so a NaN
  skill satisfied the non-positive-skill clause. Non-finite skill is now
  refused on every status.
* a `skill` map WIDER than the declared metrics constructed cleanly, and
  `skill_vs_recorded_bar` then carried a figure for a metric the decision never
  examined, indistinguishable downstream from the ones it did. Refused.
* `decision.to_dict()["evidence"]["comparisons"][0]["skill"] = 99` edited the
  decision's own record: `dict(self.evidence)` is shallow and the comparisons
  live one level down. The boundary now deep-copies.

### RESIDUALS, OPEN

1. **An undeclared domain buys no domain check.** `domain` defaults to `REAL`,
   which claims nothing, so the negative-MAPE drive still reaches PASS when the
   caller declares polarity and leaves the domain alone. This is deliberately
   not `row_matched=True` in new clothes, and the difference is the direction of
   the default: `row_matched=True` asserted the STRONGEST claim on the caller's
   behalf, `domain=REAL` asserts the WEAKEST — the failure mode is an absent
   check, not a fabricated pass. There is no safe default (NONNEGATIVE is wrong
   for r², which legitimately goes negative). Making the domain mandatory as
   polarity is, is a second contract break with its own adopter cost and is not
   taken inside M-01. Pinned:
   `test_residual_b_an_undeclared_domain_buys_no_domain_check`.
2. **A declared polarity can be declared wrongly.** The contract checks that a
   direction was stated and cannot check that it is the right one for that
   metric; `mae` declared `higher_is_better` promotes a worse model. Closing it
   needs the name table that is E-038. What changed is auditability: the
   declaration travels in the decision's evidence, so a reader can see
   `mae / higher_is_better` and object. Nobody could audit the assumption it
   replaced, because it was never written down. Pinned:
   `test_residual_c_a_declared_polarity_can_be_declared_wrongly`.
3. **`n_rows` is still a caller assertion, untied to the digests.** M-06 tied the
   row SETS, not the row COUNT: a digest over two rows alongside `n_rows=500`
   passes, because the digest is opaque and carries no count. Closing it means
   carrying a signed count beside the digest, a further design step with its own
   adopter cost. Related and unclosable by any digest scheme: a caller who
   computes ONE digest and puts it on both sides has tied the declared row sets
   together without having scored the reference on them. The tie proves the two
   sides name the same rows; it cannot prove the scoring happened. Pinned:
   `test_residual_d_n_rows_is_still_a_caller_assertion_untied_to_the_digests`.
4. **`__dict__` surgery defeats the seal, as it defeats every frozen dataclass
   here.** `object.__setattr__(r, "status", PASS)`, `r.__dict__["status"] = PASS`
   and `del r.__dict__["_sealed"]` followed by an ordinary assignment all land.
   A two-signal seal that survived the `del` was written and MEASURED, and is
   not here: it also read "the evidence mapping is sealed" as proof of
   construction, and it broke the R2/T2 delegation at `checks/readiness.py:195`,
   which builds a CheckResult from another result's evidence — the dataclass
   `__init__` assigns `evidence` before `measured_at`, so the inherited seal was
   live while the new object was still being built. Six tests red. Subtle
   correctness inside a guard is its own defect class, so the single robust
   signal stands and the limit is stated. It is a LOUD limit: nothing reaches
   into `__dict__` by accident, and accident is what the seal exists to stop —
   one ordinary assignment in a check module, which now refuses. Pinned:
   `test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen`.
   Also open at one level down: nested evidence values stay mutable
   (`r.evidence["curve"]["a"] = 9.9`). Deep-freezing arbitrary evidence changes
   the type of every nested structure the eight repos store, a blast radius
   this repair did not measure. No nested edit can change `status`, add or
   remove a top-level evidence key, or turn an empty-evidence result into a
   passing one. Pinned:
   `test_residual_a_nested_evidence_value_is_still_mutable_in_place`.

### FOR THE FLEET — this is a BREAKING contract change, and the break is the point

M-01 and M-06 will move adopter rows. A comparison that declares no polarity is
now NA; a comparison with no row-set tie is now NA. Those rows were passing on
assertions nobody made deliberately, so the flip is the repair showing its work.

**No number is written here.** How many rows move, at which of the ten adopters,
is M-08's measurement — a dual-interpreter drive at each adopter's remote main,
before-tag versus candidate-tag. Predicting it numerically would be exactly the
fabrication M-08 exists to prevent (rule 2). The adopter-side repairs in our own
two repos are M-07; colleague repins remain their owners' calls, and the three
floating adopters (choco, triage, blackout, pinned on `branch=main`) inherit
this on their next re-lock with no review step — flagged in M-09.


---

## E-M21 — the seal M-02 built read a flag the caller it was guarding against could set

**Raised** 2026-08-31 by the adversarial verification of the G-SERVED train
(PR #23, `943c0fdf1a6af7b6f2a2af272a5a7b5f00e46f44`). Fixed here, in
`src/resilient_mlkit/core/result.py`. Not a write into another repo — recorded
because E-M20 states this residual, and states it incompletely.

### What E-M20 says

M-02(b) ships a seal on `CheckResult` and discloses one residual, in
`_is_sealed.__doc__` and pinned by
`tests/test_result_sealed.py::test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen`:

> Both are `__dict__` surgery, which defeats this exactly as it defeats every
> frozen dataclass in this package … That is a stated limit of Python, not a
> hole this class can close, and it is a **LOUD** limit: nothing edits a verdict
> that way by accident, and accident is what the seal exists to stop
> (`result.status = Status.PASS`, one ordinary assignment, in a check module —
> which now refuses).

Three defeats are named: `object.__setattr__`, `r.__dict__["status"] = …`, and
`del r.__dict__["_sealed"]`. All three name the machinery they subvert.

### What was measured

Driven at 943c0fd from a fresh worktree, with `core.result.__file__` asserted
in the driver:

```
r = CheckResult.failed("R99", "phase-1", "a real failure")
r._sealed = False           -> succeeded    ORDINARY assignment
r.status = Status.PASS      -> succeeded    ORDINARY assignment
r.evidence = {"forged": True} -> succeeded
r.to_dict()["status"]       -> 'PASS'

r2.evidence._sealed = False -> succeeded
r2.evidence["forged"] = True -> succeeded
```

`CheckResult.__setattr__` refused `_VERDICT_FIELDS` and rate-limited
`_STAMP_FIELDS`, then fell through to `object.__setattr__` for every other
name — including `_sealed`, the one attribute whose value decides whether
either clause runs at all. One layer down, `SealedEvidence` declared
`__slots__ = ("_sealed",)` and never overrode `__setattr__`, so its slot was
writable by the same syntax.

This is **not** the disclosed residual. It is not `__dict__` surgery, it does
not name the machinery it subverts, and it is strictly cheaper than either
disclosed defeat: it is the same spelling as the accident the seal was built to
stop, one line earlier.

### Where it reaches

M-03's `GateAggregate` derives `passed` from the results precisely so that a
caller holding the object cannot make it disagree with the checks it holds.
Measured, same drive:

```
agg = GateAggregate("promotion", (passing_R1, failing_R2))
agg.passed, agg.blocking      -> False, ('R2',)
failing_R2._sealed = False; failing_R2.status = Status.PASS
agg.passed, agg.blocking      -> True, ()
```

The derivation is correct; it was reading forged inputs. A derived verdict is
only as strong as the seal on what it derives from.

### The repair

`_SEAL_FLAG` is named once and refused by name in both places, before every
other clause. It does **not** read the evidence mapping's seal, so it does not
resurrect the R2/T2 ordering break at `checks/readiness.py:195` that the
two-signal seal hit and that E-M20 records as the reason no second signal
shipped. `seal()` and the copy hooks use `object.__setattr__` and are
unaffected.

Five pins in `tests/test_result_sealed.py` (three Control A, two Control B);
four failed before the fix and all pass after. Check-not-dead, whole suite:
removing the `CheckResult` clause → 3 failures; removing the `SealedEvidence`
clause → 1 failure. Suite 830 → 835, nothing pre-existing lost.

### What is still open, and is now the whole residual

`test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen` is
unchanged and still green: all three `__dict__` paths still land. That is
Python's boundary and every frozen dataclass in this package shares it —
`core.served`'s own frozen types call `object.__setattr__` in their
`__post_init__`. The residual list is now accurate rather than being the part
of it somebody happened to try.

Residual A (nested evidence values are mutable in place) is unchanged and
unaffected.

### The two E-M20 residuals this verification did NOT close

Both re-driven at 943c0fd and confirmed as E-M20 states them; neither is
touched here, and both are correctly disclosed:

1. **An undeclared domain buys no domain check.** `domain` defaults to `REAL`,
   which claims nothing, so the exact 8517341 defect reproduces whenever a
   caller declares polarity and leaves domain alone:
   `Comparison(bar, "mape", -0.05, 0.20, 500, polarity=LOWER_IS_BETTER, <tied>)`
   → `PASS`, `promotable=True`, skill `1.25`. Declaring `domain=NONNEGATIVE`
   refuses it by name. Making `domain` mandatory is a second contract break on
   top of M-01's, and belongs with M-08's measured blast radius rather than
   ahead of it.
2. **`n_rows` is untied to the digests.** A comparison may carry a digest over
   500 rows and report `n_rows=7`; `row_matched` is `True` and nothing
   contradicts it. The row *sets* are tied; the row *count* is still a
   caller's word.


---

## E-M21 — D3 compared a subject's coverage against a level the same subject supplied; the level is now DATA

**Raised and repaired** 2026-08-31 on `fix/m-05-d3-nominal-is-data` (round-8
item M-05), from `origin/main` `8517341`. The defect is CLOSED. Three residuals
at the bottom are OPEN, and one of them is a change every adopter with a
`coverage` binding must make before its D3 row is a verdict again.

### The defect

D3's verdict is `abs(empirical - nominal) > tol`. Until this branch, `nominal`,
`empirical` and `n` were all read out of the single dict the `coverage`
binding had just returned, and only `tol` was clamped by mlkit
(`checks/decision.py:158-173` at `8517341`). Both operands of the subtraction
came from the party the subtraction judges.

Tick 13 measured what that buys, independently in two repos in one tick, and
both were found by PRs that had carefully tied the OTHER operand:

* **arabica** set `nominal` equal to the empirical `0.8879423328964613` it had
  just measured, in both `coverage_for_d3` and `levels[alpha=0.1]`. D3 returned
  PASS on evidence reading
  `{'nominal': 0.8879423328964613, 'empirical': 0.8879423328964613, 'n': 1526,
  'tol': 0.05}`, erasing a shortfall of `-0.012057667103538727` that the repo
  had truthfully disclosed for its SERVED model of record — the exact outcome
  the PR had been opened to prevent. The second leg of that same PR re-derived
  the coverage from the rows, agreed to 1e-12, and raised nothing, because it
  was checking the operand nobody had touched.
* **surge** wrote a genuine `(nominal 0.95, qhat 0.32916248920222785, empirical
  0.9414295014880952)` triple, from a real and different calibrated level, into
  the level whose `alpha` field still said 0.1. Every individual number was
  real. Only the pairing was a lie, and nothing compared the pairing. 17 of 18
  mutation classes refused it; this was the 18th.

The general form, which is why this entry exists rather than two repo-local
ones: **when a verdict is a comparison, every operand needs a tie. Pinning
`tol` is not pinning `nominal`, and pinning `alpha` is not either. A gate is
only as tied as its loosest term.**

Driven at `8517341` before the repair, in an interpreter asserting its own
`resilient_mlkit.__file__`, through the real `.mlkit/repo.toml` resolution
path:

    repo.toml declares [coverage] nominal = 0.9
    binding returns nominal == empirical == 0.8879423328964613, n=1526
      -> PASS, evidence {'nominal': 0.8879423328964613, ...}

    repo.toml declares nothing
    same binding
      -> PASS, same evidence

The declared level on disk was not read at all.

### The repair

The level a set of prediction intervals promises is DATA now, declared in
`.mlkit/repo.toml` beside the binding it judges:

```toml
[coverage]
nominal = 0.90
```

and the binding's own `nominal` is a claim D3 ADJUDICATES rather than the
standard it judges by. Same reason `core.served.ServeArms` holds the serve-arm
policy as data: mlkit cannot know which level a product promises, and a check
that asked the subject would be asking the party with the motive.

Three verdicts, three different instructions:

* reported disagrees with declared -> **FAIL `NOMINAL_SELF_DECLARED`**, naming
  both operands and the gap.
* no declaration -> **NA `NOMINAL_UNDECLARED`**. Falling back to the binding's
  claim would be the old behaviour wearing a conditional, reachable by deleting
  two lines of config.
* they agree -> the ordinary coverage verdict, taken against the DECLARED
  level.

`NOMINAL_AGREEMENT_EPS = 1e-12` is a float-representation allowance and not a
tolerance: `1 - 0.1` is not the literal `0.9` and a repo may compute it. The
incident above missed by `1.2e-2`, ten orders of magnitude above the bar.

Ordering, each with its own control: the E-M09/E-M10 non-finite refusals stay
AHEAD of the declaration (a NaN disagrees with every level, so folding it in
would replace "this coverage was never measured" with "this level was
substituted"); `NOMINAL_SELF_DECLARED` fires BEFORE the `n < MIN_COVERAGE_N`
NA (a substituted level is not a measurement gap and does not become less true
on fewer rows); a declaration that is a bool, a string, non-finite, or outside
`(0, 1]` is refused as a declaration, since `bool` is an `int` and
`nominal = true` would otherwise arrive as a valid 1.0 promise nobody wrote.

### What the controls measured

    full suite   754 passed / 3 skipped at 8517341 (re-measured on branch start,
                 NOT round-3's 757)  ->  766 passed / 3 skipped

    CONTROL A    declared 0.90, binding reports nominal == empirical
                 0.8879423328964613     PASS -> FAIL NOMINAL_SELF_DECLARED
                 declaration absent      PASS -> NA   NOMINAL_UNDECLARED

    CONTROL B    honest binding, 0.89 against a declared 0.90, n=5000
                                                     PASS, unmoved
                 NaN tol            FAIL "non-finite tol",       unmoved
                 NaN empirical      FAIL "non-finite empirical", unmoved
                 NaN reported nom.  FAIL "non-finite nominal",   unmoved
                 n=40               NA   "too small to measure", unmoved
                 0.68 vs 0.90       FAIL "do not mean what they say", unmoved

    CONTROL C    seven mutations of the fix out of src/, each restoring
                 decision.py byte-identical afterwards; all seven are now
                 caught. The third was not, at first — see below.

### The control that caught the author

Mutating `abs(empirical - declared)` back to `abs(empirical - nominal)` left
the suite GREEN, while the test meant to hold that line asserted in its own
docstring that it distinguished the two. It did not, and could not: past the
agreement gate the operands agree to within `NOMINAL_AGREEMENT_EPS`, so for any
ordinary tolerance they are the same number. A label on a property nothing
measured, written into the commit that closed one.

They come apart in one reachable place. A binding may declare a tolerance
STRICTER than mlkit's, with no floor, so a `tol` below the representation
allowance makes the operand choice observable: reported `0.9000000000005001`
against a declared `0.9` with `tol = 1e-13` PASSes against the declaration and
FAILs against the copy. That is now the test, with both preconditions asserted
in its body.

### Residual 1 (OPEN, and it is every adopter's) — three live D3 rows go NA

Read-only measurement over the eight adopters' remote mains, 2026-08-31, via
the GitHub contents API — a fact about their configs, NOT a prediction of their
verdicts, which is round-8 item M-08's drive to make:

| repo | main | `coverage` binding | `[coverage] nominal` |
|---|---|---|---|
| choco | `fd44583` | absent | absent |
| arabica | `5b40d70` | `mlkit_bindings:served_model_coverage` | **absent** |
| fray | `41b496e` | absent | absent |
| torrent | `373d935` | `mlkit_bindings:served_model_coverage` | **absent** |
| chokepoint | `56854a4` | absent | absent |
| surge | `997d5ed` | `mlkit_bindings:served_model_coverage` | **absent** |
| triage | `806d4e0` | absent | absent |
| blackout | `4ffe52d` | absent | absent |

No adopter declares a level today, because until this branch there was nowhere
to declare one. **arabica, torrent and surge** therefore move from a D3 verdict
to NA `NOMINAL_UNDECLARED` when they take this version; the other five are
already NA for want of a binding and do not move. The NA is the honest state —
their level was never tied — and it is repaired by two lines of config each,
not by a code change. `spine/mlkit/repo.toml` documents the section for the
sync.

### Residual 2 (OPEN) — a binding can still echo the declaration

Nothing stops `coverage()` reading `.mlkit/repo.toml` and returning the level
it finds there. The cross-check would pass. What that buys the subject is
nothing: the pass mark is then the COMMITTED declaration, which is what the
empirical figure is measured against either way, and the exploit that mattered
— moving the mark to wherever the measurement landed — is dead. Recorded so the
next reader does not mistake the cross-check for the protection. The protection
is that the level is committed, reviewable and static.

### Residual 3 (OPEN) — nothing ties the declaration to what is SOLD

`[coverage] nominal = 0.90` is a promise made to mlkit. A repo could declare
0.80 while its dashboard, its README or its customer-facing artifact says 90%.
mlkit sees the config and cannot see the sales claim. This is the same class as
`ServeArms` and it is not closable from inside the instrument; it needs the
declared level to be the SAME literal the product's own serving path reads,
which is an adopter-side change and is not proposed here.

**Status: the defect CLOSED. Residual 1 is adopter work, enumerated above and
attached to M-08's drive. Residuals 2 and 3 OPEN and unassigned.**

**Note for the release entry:** D3 changes verdict on unchanged repo code, in
both directions (PASS -> FAIL for a substituted level, PASS -> NA for an
undeclared one). `CHANGELOG.md` is deliberately untouched here — its newest
heading must equal `resilient_mlkit.__version__`, and the bump belongs to the
tag — but by that file's own scale this is a MAJOR event and the entry that
cuts the tag must name D3.


---

## E-M23 — M-05's declared level was the pass mark, read off the working tree; it is a committed read now

**Raised and repaired** 2026-08-31 on `verify/m-05-declared-level-must-be-committed`
(round-8 M-05 adversarial verification), from `fix/m-05-d3-nominal-is-data`
`a48c975`. E-M21's defect stays closed. The bypass below is CLOSED. Two
residuals are OPEN and neither is new.

### The defect

E-M21 moved D3's nominal level out of the dict the subject returns and into
`.mlkit/repo.toml`, and staked the protection on a sentence in its own text:

> The protection is that the level is committed, reviewable and static.

Nothing enforced either half. `checks/decision.py` read the level with
`repo.config()`, which parses the WORKING TREE, and it read it after
`repo.resolve()` had already imported the subject's own module.

Driven at `a48c975`, in an interpreter asserting its own
`resilient_mlkit.__file__`, through the real `.mlkit/repo.toml` resolution
path, in a real git repo:

    HEAD:.mlkit/repo.toml   [coverage] nominal = 0.90
    working tree, uncommitted, nominal = 0.8879423328964613
    binding reports nominal == empirical == 0.8879423328964613, n=1526
      -> PASS
         evidence {'nominal': 0.8879423328964613,
                   'declared_nominal': 0.8879423328964613,
                   'reported_nominal': 0.8879423328964613, ...}
         no allow-dirty marker
         git status --porcelain: " M .mlkit/repo.toml"

    [coverage] never committed at all, present only in the working tree
      -> PASS, identical evidence

    a binding whose MODULE BODY rewrites .mlkit/repo.toml before returning
      -> PASS, identical evidence

That is the tick-13 exploit — the level set equal to the empirical figure the
binding just measured — restored intact by moving it one file across. The
verdict row carries `repo.git_sha`, so it reads as a figure taken at a commit
while its standard came from bytes on no ref.

It is `docs/ESCALATIONS.md` E-M12's shape, one check after `checks/selection.py`
was moved out of it. `core/artifact.py`'s own docstring names the precedent
verbatim: `selection.py` "read `docs/selection.yaml` with `Path.read_text()`
and S1-S4 emitted PASS from the working tree — the E-M12 shape itself, in the
check pipeline of the tool that exists to refuse it." In one run, in one tree,
S1 answered **NA** on a dirty register while D3 answered **PASS** on a dirty
pass mark.

The distinction that decides it: `repo.config()` is the right reader for what
it was already asked for — which binding to import (`[bindings]`), which trees
to walk (`[source]`), which region is declared (`[remote]`). Those say WHAT TO
LOOK AT, and mlkit is about to look at the working tree anyway. `[coverage]
nominal` says WHAT PASSES. That is the role `docs/selection.yaml` plays for
S1-S4, and E-M12 is the entry about that role.

### The repair

The level is read through `core.artifact.load(repo, ".mlkit/repo.toml")` —
`HEAD`'s blob, hashed, with the two-pass linked-worktree search and the
committed-read refusals the module already owns. Rule 7: the reader was
imported, not reimplemented. `core.artifact._parse` gained TOML beside JSON,
JSONL and YAML — four lines, additive, no existing suffix's behaviour touched.

Three outcomes:

* committed and clean -> the ordinary E-M21 verdict, unchanged.
* dirty, or on no ref at all -> **NA `NOMINAL_UNCOMMITTED`**, carrying
  `core.artifact`'s own `NOT_COMMITTED` diagnosis naming the file and the blob.
* `--allow-dirty` -> the working tree is read for diagnosis and the ref is
  marked; the marker rides into `evidence` under `ALLOW_DIRTY_KEY`, and
  `CheckResult.__post_init__` raises `UncommittedRead` rather than let it
  become a PASS. A FAIL under the hatch renders and is refused downstream by
  `portfolio.resolve`.

Reading HEAD's blob is what closes the import-time write, and reordering is
not: `repo.resolve()` imports the subject's module, so the subject's code runs
before any read the check takes, however the check orders its own statements.

### What the controls measured

    full suite   757 at 8517341 -> 771 at a48c975 -> 777 here
                 (+6 = exactly the new pins; zero pre-existing tests moved,
                  zero removed — collected node ids diffed, not counted)

    CONTROL A    uncommitted declaration substituting the empirical
                                              PASS -> NA NOMINAL_UNCOMMITTED
                 declaration only in the working tree
                                              PASS -> NA NOMINAL_UNCOMMITTED
                 binding writing the config from its module body
                                              PASS -> NA (not the subject's number)
                 binding writing malformed TOML mid-call
                          BindingError ESCAPING the check -> NA, no traceback

    CONTROL B    all ten E-M21 controls re-driven, evidence dicts compared
                 field by field: A1 FAIL NOMINAL_SELF_DECLARED, A2 NA
                 NOMINAL_UNDECLARED, honest PASS, the erased disclosure PASS,
                 NaN tol / NaN empirical / NaN nominal FAIL with their own
                 reasons, n=40 NA, 0.68-vs-0.90 FAIL, widened tol clamped —
                 ALL UNMOVED. Committed-clean is the ordinary case and it is
                 byte-identical.

    CONTROL C    4 mutations, decision.py / artifact.py restored and sha256
                 asserted byte-identical after each; 4/4 caught.

### Residual 1 (OPEN, unchanged from E-M21 residual 1, now larger)

No adopter declares a level, so arabica, torrent and surge still move to NA on
adoption. They must now COMMIT the declaration, which is the same two lines and
one `git add`. A repo running `mlkit check` on a dirty tree gets NA on D3 where
it used to get a verdict; that is the same bargain S1-S4 already make.

### Residual 2 (OPEN) — `empirical` and `n` are still the subject's alone

Driven here and left open because it is not M-05's scope: with an honest
committed 0.90, a binding returning `{"nominal": 0.90, "empirical": 0.90,
"n": 1000000}` PASSes, and nothing ties either figure to a row set. E-M21 named
the general form — "when a verdict is a comparison, every operand needs a tie"
— and tied one of the three. The row-digest work in round-8 M-06 is the shape
the remaining two need. **Unassigned.**

**Status: the bypass CLOSED. E-M21's residuals 2 and 3 stand as written.
Residual 2 above OPEN and unassigned.**

*Numbering note: E-M21 is contended (mlkit PR #24 and PR #26 both took it) and
E-M22 is taken by PR #25, all three still open at 2026-08-31. This entry took
E-M23 to leave those alone; if the merge order makes E-M23 collide it is a
heading rename and nothing else — no entry here is renumbered or rewritten.*
