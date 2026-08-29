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
