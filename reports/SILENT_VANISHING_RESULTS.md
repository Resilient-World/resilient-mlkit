# Results — closing the instrument's silent-vanishing paths

Answers `reports/SILENT_VANISHING_PREREGISTRATION.md`, committed at `d01ce30`
before the first source edit. Every figure below came out of a run on this
machine; nothing is reconstructed and nothing is estimated.

Branch `feat/loop-mlkit-5` off `main` = `3df724d`. Authorization **A-1**: local
CPU, no cloud, no GPU, no spend. Nothing was fitted, no split was scored, no
test arm was opened, and no model repo was written to.

Interpreter: the repo's own `.venv/bin/python`, **3.14.6**; pytest 9.1.1;
ruff 0.16.5; mypy as installed.

---

## What each change did, and how it was proven

### SV-1-REGISTRY — `95609b7`

`for_phase` ended `if cid in _REGISTRY`. An id `PHASE_ORDER` declares and the
registry does not hold was not reported missing; it stopped existing.

It now returns one spec per declared id, always. An unregistered id yields a
spec whose function FAILs with
`declared in PHASE_ORDER but absent from registry after load_all()`.

`tests/test_registry_completeness.py` — **13 passed, 0.95 s**.

| Half | What was forced | Result |
|---|---|---|
| positive | `T99_NEVER_REGISTERED` injected into `PHASE_ORDER["triage"]` | exactly one FAIL row, carrying that id and that reason, with evidence naming `checks.PHASE_ORDER`; `missing_from_registry() == ["T99_NEVER_REGISTERED"]` |
| negative | the real tree, all five phases | `missing_from_registry() == []`; no synthesized row anywhere; `for_phase` returns the registered specs in `PHASE_ORDER` order |

**Byte-identity of every existing verdict.** All 32 checks were run against a
fixture repo on a temp path, before and after the change, and the dumps are the
same bytes:

    sha256 88c2630268b59ec82ad414c9c0fdc2848bd0b69a906cb8f5c750513c84979543
      pre-change  (main 3df724d)
      post-change (this branch)

32 results across 5 phases in both — triage 5, selection 5, readiness 12,
decision 5, economics 5.

### SV-2-PHASE-EXIT — `5a2b3c4`

The printed fraction and the exit code both came from the results the run
collected, so numerator and denominator agreed by construction and the
comparison carried no information.

`tests/test_phase_denominator.py` — **4 passed, 1.32 s**.

| Half | What was forced | Result |
|---|---|---|
| positive | `for_phase` made lossy (R5 removed) | R5 returns FAIL **in R5's `PHASE_ORDER` slot**; it is the only synthesized row |
| positive | `_run_phase` made lossy | `cmd_check` exits **1**, stderr names both sides: `11 result(s) for 12 declared check(s)` |
| negative | complete readiness run, fixture repo | no `INCOMPLETE` on stderr; the exit code is the ladder's |

The negative half was measured on both trees through one probe rather than
argued:

| Tree | Printed | Exit |
|---|---|---|
| `main` 3df724d | `READINESS: 1/12 PASS  ESCALATED=1  NA=10` | 3 |
| this branch | `READINESS: 1/12 PASS  ESCALATED=1  NA=10` | 3 |

### SV-3-PORTFOLIO-EXIT — `f48334f`

`_cmd_portfolio` ended `return 0`. `README.md:144` promises exit `1` means
"something failed (CI gates on this)". For `--portfolio` that was false. The
README was not edited.

`tests/test_portfolio_exit.py` — **15 passed, 0.09 s**.

| Half | Input | Exit |
|---|---|---|
| positive | one BLOCKED repo among passing ones | 1 |
| positive | a hard stop (`evidence.halt`) | 1 |
| positive | an unrecognised terminal state | 1 (fail closed) |
| positive | an empty portfolio | nonzero |
| negative | all `READY-TO-TRAIN` | 0 |
| negative | `IN-PROGRESS` vs `AWAITING-SIGNOFF` | 3 vs 4 — kept distinct |

**On the real fleet, read-only** (`--portfolio` calls `store.load_all`, which
only reads; `store.save` is never reached):

| Tree | Exit |
|---|---|
| `main` 3df724d | **0** — eight repos, every one BLOCKED |
| this branch | **1**, stderr: `PORTFOLIO EXIT 1: 8 repo(s) resolved and not every one is READY-TO-TRAIN (BLOCKED)` |

That is the defect, on the live portfolio: eight BLOCKED repos exiting green.

**The header.** `R(9,10,11,1-8)` named one id fewer than
`PHASE_ORDER["readiness"]` holds. It is now derived and reads `R(9-12,1-8)`.
Diffing the whole rendered table between the two trees, nonce lines stripped:
**the only difference is the header string and the column width it forces.**
Every one of the eight repos' cells is byte-identical.

An existing gate caught this change's own prose —
`test_promotion_state.py::test_portfolio_states_no_gating_count_the_registry_contradicts`
fired on a spelled-out count in a new docstring. **The docstring was fixed, not
the gate.**

### SV-4-PARITY-DISCOVERY — `23c6151`

`scripts/verify_served_hash_parity.py` accepted one shape and reported three
repos as `NA — "this repo serves nothing hash-pinned yet"`, a claim about those
repos it had never measured.

`tests/test_served_hash_parity_discovery.py` — **21 passed, 1.63 s**.

| Half | What was forced | Result |
|---|---|---|
| positive | sidecar fixture, referenced bytes altered after the digest was taken | `DIFFER`, exit 2 |
| negative | same fixture untouched | `MATCH`, exit 0 |
| positive | self-hash fixture, one field edited, **no coefficient file touched** | `DIFFER` — the property a sidecar digest does not have |
| negative | same record untouched | `MATCH` |
| negative | a repo carrying neither shape | `NA`, no `MATCH` invented, exit 2, and the reason contains no claim about what the repo serves |
| negative | a candidate present in the checkout | worktree fallback suppressed; no duplicate row |
| positive | a sidecar pinning a file that is not there | `NA` with no recomputed digest, exit 2 |

**Refutation — the tests fail against the code they replace.** The same
three-repo fixture run through `main`'s scanner:

    PRE-CHANGE SCANNER exit: 2
      arabica  NA  no committed artifact under models/ carries an artifact_sha256; this repo serves nothing…
      torrent  NA  (same)
      surge    NA  (same)
      artifacts_compared: 0

**Regenerated `reports/served_hash_parity.json`** — sha256
`5859c659babbb381dfb225c2b3ab154f13c531a2e3624c9497d90e4c1d5913cc`,
mlkit `f48334f`, python 3.14.6, generated `2026-08-29T15:44:08Z`.
**8 compared, 8 matched, 0 differed, 0 unresolvable.**

| repo | status | kind | artifact |
|---|---|---|---|
| choco | NA | — | searched, nothing found; NA is correct |
| arabica | MATCH | sidecar | `models/yield_model_of_record/model.json` |
| fray | MATCH | self-hash | `models/county_yield/champion_forecast_available.json` |
| fray | MATCH | self-hash | `models/county_yield/champion_spatial_infill.json` |
| torrent | MATCH | sidecar | `models/hydrology_ridge/model.json` |
| chokepoint | MATCH | self-hash | `models/daily_flow/champion.json` |
| chokepoint | MATCH | self-hash | `models/episode_response/champion.json` |
| surge | MATCH | sidecar | `data/model_registry/per_lead_anchor_ols/model.json` |
| triage | MATCH | self-hash | `models/weekly_mortality/champion.json` (worktree `.worktrees/e029`, flagged) |
| blackout | NA | — | searched, nothing found; NA is correct |

No row was hand-written. The file was produced by running the scanner.

---

## Things found on the way that were not in the plan

**A second vanishing path inside the fix.** `SKIP_PARTS` was tested against the
**absolute** path. A linked worktree at `<repo>/.worktrees/<name>` has
`.worktrees` in every descendant's parts, so every candidate inside one was
skipped and the repo rendered NA. Triage's champion — which is committed on
`.worktrees/e029` and absent from its checked-out `main` — was invisible until
the test was made relative to the tree being scanned. Same defect class as the
one being fixed, one layer down.

**fray's committed digests moved, and both still verify.** The previous
`served_hash_parity.json` recorded `b6a9b933…` and `cba79308…` at fray
`3b1941f`. This run records `b862f7f5…` and `da2d0773…` at fray `aef69ed`.
fray's own commit `5abe3aa` ("R10-REPIN: both champions re-serialized from a
clean tree, and nothing measured moved") accounts for it, and both records
self-verify. Recorded rather than passed over: a digest moving between two runs
of a parity tool is the event the tool exists to make visible, and it should be
visible even when it turns out to be benign.

**The fleet moved underneath the run.** `resilient-torrent`, `resilient-surge`
and `resilient-fray` all advanced HEAD during this session under other agents'
work. Each parity row carries the SHA of the tree at the moment it was read;
torrent's HEAD moved again after its row was written (`a60f159` in the report,
`9269c86` afterwards). The bytes and the digest in a row are consistent with
each other; the row's SHA is a timestamp of the read, not a claim that the repo
still sits there.

---

## Deviation from the pre-registration, stated rather than absorbed

The pre-registration said the parity scanner's exit code would be "`0` when
everything compared matched, `2` otherwise, and `2` when nothing was compared at
all". As shipped, an **unresolvable pin** — a record pinning a coefficient file
that is not on disk — also exits `2`, and it is `NA` rather than `MATCH` or
`DIFFER`.

This is stricter than registered, not looser. An unresolvable pin is itself a
silent-vanishing path: under the registered rule a repo whose champion pinned a
missing file would have rendered NA and exited green. Recorded here because a
pre-registration is only worth something if departures from it are visible.

---

## Must not change — restated after the work

`src/resilient_mlkit/checks/` — five of six files byte-identical to the
baseline; `__init__.py` changed as pre-registered:

    bb0538f645a31b6a2b658d5c5ac1c0d8b929509ee46cb07ae7b9918a1edb691a  decision.py    unchanged
    c8e9ed51f860666f9b7ec3401e91586e7ca682604b01a02cf6d328158b6dd77d  economics.py   unchanged
    1ce5cea69a89842ccfc2c6dd5db3f65f00c1fe630c5881f77eabca637a674afd  readiness.py   unchanged
    7e617323dfd600a4954f61b2c29a24ab825281ec6d8a787c0bae29b2f279da6d  selection.py   unchanged
    bf085947223327d162ee2ca81a29c556f1799cb845fe8c063e35c2d5134bf3a6  triage.py      unchanged
    e55b34a…  ->  4c88d36…                                            __init__.py    for_phase only

**No threshold, tolerance or range moved.** Across the entire branch,
`git diff main...HEAD -- src/resilient_mlkit/checks/` removes exactly **one**
line, and it carries no number:

    -    return [_REGISTRY[cid] for cid in PHASE_ORDER[phase] if cid in _REGISTRY]

**`PHASE_ORDER` membership** — identical to baseline. 32 ids, 5 phases. The
registry's key set is identical. `missing_from_registry()` is `[]`.

**Signing and fleet-adjudication files** — `shasum -c` against the baseline:

    spine/docs/allowlist.yaml       OK
    portfolio/FLEET_VERDICTS.json   OK
    portfolio/FLEET_VERDICTS.md     OK
    portfolio/SPINE_DRIFT.json      OK
    portfolio/SPINE_DRIFT.md        OK
    portfolio/MODEL_QUALITY.md      OK

**The eight model repos** — read-only. No phase run was executed against any of
them: the latest write under any `resilient-*/.mlkit/results/` is
`2026-08-29T07:04:47` local, before this session's first commit at
`2026-08-29T08:32:48-07:00`. Every check-pipeline control used a fixture `Repo`
on a temp path; the parity scanner opens files for reading and runs read-only
`git` commands. No spine sync was run.

**Lint and types** — ruff 0.16.5 reports **no new findings**: the four on
`scripts/verify_served_hash_parity.py` (`EXE001` plus three `RUF100`) are the
same four `main` reports on the same file, and the `served_reimplementation.py`
findings are `main`'s. The single mypy error
(`served_reimplementation.py:689`) is present on `main` unchanged.

**Focused tests** — `--timeout=180`, no full suite run:

    test_registry_completeness  test_phase_denominator  test_portfolio_exit
    test_served_hash_parity_discovery  test_promotion_state  test_committed_reads
    test_served_contract  test_fleet
      -> 190 passed in 14.26 s

A full-suite run is **recommended and not performed here**.
