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
disagreed inside `v0.3.0` are one literal that cannot. `main` declares `0.3.1`.
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

**Still open, and still the signatory's:** the `v0.3.0` tag is untouched and its
own tree still reads `0.2.0`. Cutting `v0.3.1` from `main`, and deciding when
the eight repos re-pin to it, remains a release decision of record.
