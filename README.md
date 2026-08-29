# resilient-mlkit

The single measurement and gating tool for the Resilient avoided-loss model
portfolio. Built once; imported by all eight model repos; never reimplemented
per repo.

**Only mlkit emits numbers.** Any metric, loss, score, coverage figure or cost
that did not come out of a run of this CLI does not exist.

## Layout

- `src/resilient_mlkit/` — the package. 26 gating checks across 5 phases,
  plus 5 diagnostic triage checks.
- `src/resilient_mlkit/fleet_adapters.py` — one declared adapter per model of
  record, saying which committed artifact and which pointer carries each column
  of the fleet verdict table.
- `spine/` — the canonical docs and scaffolding synced into every model repo.
- `scripts/sync_spine.py` — propagates `spine/`. Canonical files are
  overwritten; seed files (escalations, blockers, allowlist, repo.toml) are
  written once and then owned by the repo. It imports the declaration of what
  "canonical" means from `core.spine`, so the syncer and the drift check cannot
  disagree about it.
- `portfolio/` — the fleet adjudications. `MODEL_QUALITY.md` is hand-written
  judgement; `FLEET_VERDICTS.md` and `SPINE_DRIFT.md` are generated and must not
  be hand-edited.
- `docs/ESCALATIONS.md` — findings the instrument measured in the model repos
  that cannot be fixed from here.

## Commands

| Command | Does |
|---|---|
| `mlkit check --phase PHASE` | run one phase against every repo found |
| `mlkit check --portfolio` | each repo's terminal readiness state |
| `mlkit portfolio` | regenerate the **measured** columns of the fleet verdict table by reading each repo's committed artifacts |
| `mlkit spine` | report canonical-spine drift per repo. **Report-only — never writes into a model repo** |
| `mlkit env` | can this interpreter measure each repo at all |
| `mlkit keys` | credentials the portfolio is waiting on |
| `mlkit notice` | regenerate `NOTICE.md` from the allowlist |
| `mlkit allowlist verify` | allowlist structure and signature |

`mlkit portfolio` and `mlkit check --portfolio` are different questions.
The first is model quality — does this thing beat its baseline. The second is
readiness — can this repo start a run. Neither answers the other.

```
mlkit portfolio --out portfolio/FLEET_VERDICTS.md
mlkit spine     --out portfolio/SPINE_DRIFT.md
```

Both write a `.json` twin beside the `.md`. Every figure in the verdict table
carries the artifact it came from, that artifact's sha256, and whether git has
those bytes at HEAD; a column a repo's artifacts do not carry reports `NA` with
the reason rather than being omitted.

## Statuses

| Status | Means |
|---|---|
| `PASS` | Measured, and correct. Requires non-empty evidence. |
| `FAIL` | Measured, and wrong. |
| `NA` | Could not be measured here, with a reason. Never a pass. |
| `STALE` | Measured at a different git SHA than the one checked out. |
| `ESCALATED` | Reserved to the human signatory. |

Three of the readiness checks import nothing and walk source with `ast`, which
is what lets them see code no binding exposes: **R10** `FABRICATED_DEFAULTS`
(a measured quantity given a plausible default that then satisfies the gate
consuming it), **R11** `FABRICATED_TARGETS` (a value drawn from an RNG,
flowed into a data record, and stamped with a provenance field claiming it was
observed), and **R12** `SERVED_CONTRACT` (a repo answering, in its own code,
the questions `core.served` exists to answer once — is this the artifact that
was measured, may this challenger be promoted, which arm may be served). R11
and R12 walk every Python file in the repo rather than the trees a repo
declares, because the declared-tree list is exactly the surface an author
controls.

R12 is rule 7 applied to serving. The fleet converged on one definition of
"ready" — these checks — and grew three of "served", including two files with
the same name and different SHAs whose gates return opposite verdicts on a
zero baseline. R12's exemption is an **import**, so adopting `core.served` is
what clears it; renaming is not.

`READY-TO-TRAIN` requires all 27 gating checks to pass. Six of them (S5, D1, D4, D5,
E4, E5) are human-only and always report `ESCALATED`, so **an agent cannot
drive a repo to READY-TO-TRAIN**. That is deliberate: those six are legal and
billing exposures, not code changes.

## Installing it into a model repo

mlkit runs from **the model repo's own environment**, not from its own. Phase-1
and phase-3 checks import that repo's real dataloaders and models, so they need
that repo's dependencies importable in the same interpreter.

Each of the eight model repos declares it as a PEP 735 dependency group:

```toml
[dependency-groups]
gates = ["resilient-mlkit"]

[tool.uv.sources]
resilient-mlkit = { git = "https://github.com/Resilient-World/resilient-mlkit.git", branch = "main" }
```

Install it alongside whatever extras that repo already needs:

```
uv sync --group gates --extra dev      # plus the repo's own extras
```

**Update the lock with `uv lock`, and be deliberate about `uv sync`.** A bare
`uv sync --group gates` syncs to exactly the default set plus that group and
uninstalls everything else — in resilient-surge on 2026-08-24 it silently removed
pytest, ruff, mypy, dvc, optuna, mlflow, cdsapi, h5py and netCDF4 before
`uv sync --all-extras --all-groups` restored them.

A group rather than an extra, deliberately: mlkit is never needed to import or
serve a model repo, only to measure it, and groups stay out of published
metadata. It is pinned by commit in each repo's `uv.lock`, which is what lets a
gate report be reproduced rather than depending on which machine ran it.

Until 2026-08-24 this repo had no remote and no model repo declared it, so mlkit
was pip-installed by hand — `docs/BLOCKERS.md` in resilient-surge records
`import resilient_mlkit -> ModuleNotFoundError` against the stated ground truth.
Requires Python >= 3.11 (`tomllib`); resilient-fray and resilient-blackout
declared `>=3.10` and were corrected, their CI having only ever tested 3.12.

## Usage

    mlkit env
    mlkit check --phase triage --repo blackout
    mlkit check --phase readiness
    mlkit check --portfolio
    mlkit notice --repo blackout
    mlkit allowlist verify

Exit codes: `0` all pass · `1` something failed (CI gates on this) · `3`
incomplete — unmeasured, stale or awaiting sign-off.

## Run it from the right interpreter, and check first

`mlkit env` answers one question per repo: can THIS interpreter import that
repo's bindings at all. Ask it before a phase, because the answer changes what
a phase run means.

    REPO        VERDICT       BINDINGS OK  MISSING FROM THIS INTERPRETER
    choco       UNMEASURABLE  0/10         numpy
    surge       MEASURABLE    11/11        -

**"Environment unmeasurable" is a different fact from FAIL.** A check that
could not run says nothing about the repo. In August 2026 a python 3.14 with
no numpy regenerated `reports/readiness.md` in at least four repos, replacing
measured PASSes with `ModuleNotFoundError` (resilient-chokepoint
`docs/ESCALATIONS.md` E-019). mlkit now refuses that write: R8 reports `NA`,
the prior report is preserved byte for byte, and the refusal is recorded in
`reports/readiness.UNMEASURABLE.md`.

A missing module that resolves inside the repo is the repo's own defect and
still fails. The guard protects measurements from bad interpreters; it does
not protect repos from themselves.

R10, R11 and R12 are never guarded — they parse source and import nothing, so
they measure correctly from any interpreter.
