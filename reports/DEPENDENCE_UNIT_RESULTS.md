# Results — the dependence unit as a declared, checked part of the contract

Every figure below was produced by running the code on this branch. The
preregistration is `reports/DEPENDENCE_UNIT_PREREGISTRATION.md`, committed as
the first commit on `feat/dependence-unit-contract` before any source edit
(`fefdc5e`, parent `origin/main` `6921e9a`).

- branch head at writing: `f3a3b16`
- base: `origin/main` `6921e9a` (`git ls-remote`, this session)
- interpreter: `/Users/david/Downloads/Claude Code/resilient-mlkit/.venv/bin/python`, 3.14.6
- **binding asserted in every driver.** `tests/test_dependence_unit.py` carries
  a module-level assertion that `core.served.__file__` resolves under this
  worktree's `src/`; each throwaway driver asserts the same for the module it
  drives. `resilient_mlkit` is installed into eight virtualenvs on this machine
  and an editable install elsewhere resolves first if `PYTHONPATH` is not what
  it should be, so a green run without that assertion says nothing about the
  tree under review.
- **compute**: no fits, no sweeps, no data reads, no network. Two throwaway
  worktrees under the scratchpad; no model repo was written to; no ledgered
  test read was opened or approached.

---

## H6 first — nothing that already existed moved

| | suite |
|---|---|
| `origin/main` `6921e9a`, own worktree | **912 passed** in 71.60s |
| this branch, before the new test file | **912 passed** in 53.72s |
| this branch, with `tests/test_dependence_unit.py` (random order) | **976 passed** in 85.10s |

976 = 912 + 64. No test on `main` was edited, weakened or deleted. One test on
`main` was edited to record a change it exists to force — see "the tripwire"
below — and both versions of its assertion are quoted in its own docstring.

### R3, the one existing check whose code this branch touched

`normalise_splits` and `SplitsUnreadable` are R3's parser **extracted**, so D6
reads "what the splits binding said" through the same code rather than through a
second copy. Driven at both shas, same driver, same inputs
(`scratchpad/drive_r3_pair.py`):

* **all eight repos on disk** — identical status, reason and evidence on both
  sides. `surge` is the one repo whose `splits` binding imports cleanly in
  mlkit's own environment and it PASSes identically on both, evidence
  `{n_train: 22, n_val: 5, n_test: 8}`. The other seven answer identically on
  both sides too, though for an environment reason (`ModuleNotFoundError: No
  module named 'pandas'` — mlkit's venv, not each repo's), so **those seven rows
  are a base-vs-branch comparison and not an exercise of the real bindings**.
  Stated rather than glossed.
* **ten synthetic cases**, chosen to cover every exit R3 has — the
  character-splitting defect its comment records (`{"train": "abc", …}` → FAIL
  naming three str splits), the `bytes` variant, a missing split, an overlap, a
  thin holdout, an empty split, a raising binding, a non-mapping return, a
  clean split, and an int/str key collision. **Byte-identical on both sides**:
  `diff` over the full JSON is empty.

---

## H1 / H2 / H3 — the control pair

Driven through `ResamplingDeclaration` directly (`scratchpad/drive_shapes.py`)
and asserted in `tests/test_dependence_unit.py`.

| shape | `relation` | `refusal` | units in arm | blocks in arm |
|---|---|---|---:|---:|
| **fray as run** — crop-year blocks, ROW units | `UNIT_FINER_THAN_BLOCK` | **`DEPENDENCE_UNIT_TOO_FINE`** | 1365 | 5 |
| **fray repaired** — crop-year blocks, CROP-YEAR units | `UNIT_IS_THE_BLOCK` | — | 5 | 5 |
| **chokepoint** — date blocks, CORRIDOR units | `UNIT_CROSSCUTS_ARMS` | — | 28 | 20 |
| coarser — crop-year blocks, year-pair units | `UNIT_COARSER_THAN_BLOCK` | — | 3 | 5 |
| a block straddling two arms | `UNIT_FINER_THAN_BLOCK` | **`BLOCKS_STRADDLE_ARMS`** | — | — |
| one unit in the arm | `UNIT_IS_THE_BLOCK` | **`SINGLE_UNIT`** | 1 | — |
| unit LABELLED as the blocking unit, content disagrees | `UNIT_CROSSCUTS_ARMS` | **`UNIT_LABEL_CONTRADICTS_CONTENT`** | — | — |

All five relations and all four refusals are reachable. The first two rows
differ in **one expression** — which key each row's `unit_key` carries — and
the verdict inverts. The refusal message names both units and both counts:

> the bootstrap resampled 1365 'row' unit(s) inside arm 'val', but holdout
> policy 'county_year_splits' keeps whole 'crop_year' blocks in one partition
> and that arm holds 5 of them. 5 block(s) are split across units (e.g. 2016
> spans 253 units). …

**H3 matters as much as H1.** If chokepoint's corridor bootstrap were refused,
the fleet's *correct* convention would be unadoptable — R12's stated failure
mode ("adopting the check would not clear it") one layer up. It is not refused,
and the number the procedure did **not** resample (20 date blocks in the fixture
arm) sits in the record beside the 28 it did.

## H4 — the constructing layer

Eleven derived fields — `n_rows`, `n_blocks_in_arm`, `n_units_in_arm`,
`n_rows_panel`, `row_digest`, `block_digest`, `unit_digest`,
`block_keys_in_arm`, `relation`, `refusal`, `detail` — each refuse assignment
with a `TypeError` naming the argument. There is no spelling of the derived
facts. Also refused, each by name: a missing assignment, a bare-tuple
assignment (block and unit are the same type and adjacent; a swap would reverse
every verdict silently), a duplicate row key, an empty assignment, an arm absent
from the assignment, `draws` of `0`, `-1`, `True`, `1.5` and `"4000"`, an unnamed
`procedure`/`policy`/`blocking_unit`/`unit`/`arm`, a row with no arm, and a
grouping key that is not JSON-serialisable.

**Every tie is content.** `row_digest` is recomputed in the tests through the
public `row_set_digest` over the same rows and compared. Two declarations over
one row set tie on `row_digest` and `block_digest` and differ on `unit_digest`;
two blockings of one row set tie on `row_digest` and differ on `block_digest`.

## H5 — the decision path

| comparison | status | refusal class |
|---|---|---|
| fray-shaped declaration, interval `[+0.05, +0.35]` | **NA** | `DEPENDENCE_UNIT_CONTRADICTS_POLICY` |
| clean declaration, point `+0.2`, interval `[−0.02, +0.41]` | **FAIL** | `INTERVAL_COVERS_ZERO` |
| clean declaration, point `+0.2`, interval `[+0.11, +0.29]` | **PASS** | `CLEARS_BAR` |
| clean declaration, interval resampled over other rows | **NA** | `RESAMPLING_ROWS_UNTIED` |
| clean declaration, point `−0.2` (lost), interval `[−0.4, −0.05]` | **FAIL** | `NO_SKILL` |
| **no interval at all** | **PASS** | `CLEARS_BAR` |

Row 2 is the finding, decided: a point estimate that clears and an interval that
does not. Row 5 proves the interval lane is asked **last** — a point-estimate
loss is not re-labelled by the presence of a bound. Row 6 is CONTROL B.

*(The values in rows 2–5 are skill ratios from fixture rows built in the test
file. The `[+16.016, +29.646]` / `[−1.289, +41.704]` pair is quoted from the
adjudication and appears nowhere in this branch's arithmetic; the only thing
borrowed from the real panel is shape — five val crop years, 1,365 val rows,
split 253/267/278/285/282.)*

`ChallengerDecision.to_dict()` on a decision with no declaration emits
`"resampling": "NA"` — a printed absence rather than a missing key — and hands
out a deep copy: mutating the returned declaration does not edit the decision's
own record (driven).

## H7 — D6 on the fleet, predicted before running

`d6_resampling_unit` driven directly against all eight portfolio repos on disk
(`scratchpad/drive_d6_fleet.py`; the check function is called directly, so
`core.store.save` never runs, and each repo's `.mlkit/` directory listing was
compared before and after and did not change):

| repo | D6 |
|---|---|
| choco, arabica, fray, torrent, chokepoint, surge, triage, blackout | **NA** — `no 'resampling_declaration' binding declared in .mlkit/repo.toml` |

**NA 8/8, PASS 0/8**, exactly as preregistered. A PASS anywhere in that run
would have been evidence the check is blind, not evidence a repo is clean.

End to end through the CLI on a fixture root:

```
DECISION: 0/6 PASS  ESCALATED=3  NA=3        exit 3
D6     NA         fray: no 'resampling_declaration' binding declared in .mlkit/repo.toml; …
```

## The tripwire, and what it cost

`tests/test_promotion_state.py` holds `assert len(gating_ids()) == 27` with a
docstring saying, in as many words, that adding a gating check "should not be
possible … without editing this line and saying so". D6 is in the decision
phase, so it is a gating check, and the tripwire fired. The literal moves to
`28` and the "saying so" is written into the same docstring beside the R12
`26 → 27` move it already records; both versions of the assertion are quoted
there. The assertion is the same exact equality on a set one larger.

**Fleet consequence, measured rather than reasoned**: nothing changes state
today. D6 answers NA wherever the binding is absent, and every repo already
carries several NAs (D2, D3, E1, E2, E3, R7 at minimum), so every repo was
already `IN-PROGRESS` by `portfolio.resolve`'s NA branch. What moves is the
count in that state's message, `N of 27` → `N+1 of 28`, and the decision phase's
denominator, `0/5` → `0/6`.

---

## WHAT THIS DOES NOT ESTABLISH

Four honest limits, none of them papered over.

1. **The unit side is tied to the rows and to nothing else.** The declared
   BLOCKS are tied to a second declaration — the `splits` binding R3 already
   reads — which is what catches `block_key = row_key`. The declared UNITS have
   no such second witness: a repo that hands over an assignment saying it drew
   corridors when it drew rows has fabricated its input, and this contract does
   not detect that. What it does is put `n_units_in_arm` beside `n_rows` and
   `n_blocks_in_arm` in the record, so a reader sees `unit='row_index',
   n_units=3, n_rows=1365` rather than the word "bootstrap".

2. **`UNIT_CROSSCUTS_ARMS` is recorded, not blessed.** A corridor bootstrap does
   not account for the temporal axis a time-blocked split partitions. Refusing
   it would refuse the convention the adjudication endorsed, on a standard no
   measurement in this round supports, and inventing that standard here is not
   this branch's to do. It is held as an assertion, not left in prose:
   `test_the_contract_does_not_claim_the_crosscutting_case_is_accounted_for`.

3. **No threshold on the number of units.** "Five clusters is too few" is a
   judgement this instrument does not make and has no basis to make. The single
   arithmetic refusal is `n_units < 2`, which is not a threshold: one unit
   cannot be resampled. Everything else is reported and left to the interval's
   own width.

4. **A frozen dataclass is not a sealed object.** `object.__setattr__` can
   overwrite a derived field after construction, exactly as it can for
   `Comparison.row_matched` and every other frozen type in this module. That is
   a property of the language, and the guarantee here is the same one those
   types already make: there is no *declared* way to spell it and no argument
   that accepts it.

## Residuals left open, with reasons

* **Adoption in fray and chokepoint** — `docs/ESCALATIONS.md` E-M24 and E-M25.
  Both are writes into other repos, and both repos' relevant files are owned by
  open, unmerged evidence PRs (fray #78, chokepoint #101). This branch touches
  no file either of them touches.
* **README's second copy of the gating count** — E-M26. Updated to 28 here;
  the honest fix (generate it, or hold it against `gating_ids()` in a test) is a
  separate change with its own control pair.
* **No R12 clause for the new surface.** A re-implementation scanner for
  `ResamplingDeclaration` is a fleet-wide change to `core.served_reimplementation`
  and would ship an unmeasured scanner clause alongside a contract nothing has
  adopted yet. Deliberately out of scope; recorded in the preregistration.
* **The spine is now DRIFTED in eight repos, on purpose.**
  `spine/docs/DECISION_VALIDITY.md` is a CANONICAL file and it gained a D6
  section, so `mlkit spine` will report the deployed copies as `DRIFTED` until
  `scripts/sync_spine.py` runs. That is what DRIFTED means and it is accurate;
  the sync is a write into eight repos and this branch does not perform it.
  `spine/mlkit/repo.toml` is a SEED file, so its new binding contract reaches
  new repos only and overwrites nobody.
