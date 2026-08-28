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
