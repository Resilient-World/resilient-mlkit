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
