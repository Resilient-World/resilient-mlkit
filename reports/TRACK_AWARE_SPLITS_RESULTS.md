# Results — TRACK-AWARE SPLITS

Every figure below was produced by running the code. The pre-registration
(`reports/TRACK_AWARE_SPLITS_PREREGISTRATION.md`) is the first commit on this
branch and nothing in it was edited after a measurement. Deviations are named
in §6.

- branch: `feat/track-aware-splits-contract`
- base: `feat/dependence-unit-contract` @ `24f23b8` (PR #32, open, unmerged)
- date measured: 2026-09-01
- raw artifacts: `reports/track_aware_splits/*.json`
- drivers: `scripts/drive_fray_two_track.py`,
  `scripts/drive_single_track_controls.py` — both assert
  `module.__file__` resolves under the tree they were pointed at, and refuse
  otherwise.

## 0. Which branch this was cut from, and why not from I1-M1's

This item's plan said to branch from the `feat/dependence-unit-contract` head
**after** item I1-M1, which owns the `UNIT_CROSSCUTS_ARMS` ladder in the same
file. At spawn, `git ls-remote --heads origin` in `resilient-mlkit` listed no
branch for I1-M1 (the open PRs were #31–#36; the loop branches
`feat/loop-mlkit-{1,3,4,5}` are from earlier rounds, checked by
`git log`). So this branch is cut from `24f23b8` directly. **It touches
neither `ResamplingDeclaration`'s refusal ladder nor any line I1-M1 would
change**, and its consequence is §5.

Colleague PRs checked at spawn, per the binding rules:

| repo | open PRs | what this item did with their files |
|---|---|---|
| mlkit | #31 #32 #33 #34 #35 #36 | branched FROM #32; #34's `README.md` count sentence and #31/#33's build-identity files untouched — this branch adds a paragraph elsewhere in `README.md` and does not touch that count |
| fray | #78 #79 | **read only.** No fray file is edited by this item; fray was driven in a throwaway `git worktree` at `66a1eb2` that has been removed |
| chokepoint | #101 #102 #103 #104 | **read only.** Only `mlkit_bindings:splits` was called, for split membership |
| torrent | none | **read only**, same |

## 1. CONTROL A — the firing control, on the real fray panel

Driven through mlkit's real binding path (a fixture repo on a temp path with a
`.mlkit/repo.toml`, `git init`, `Repo.resolve`) against split membership from
`resilient-fray`'s own `validation.yield_holdout.county_label_splits` and
`county_year_splits`, at `66a1eb2`. Panel: **43,383 rows** in both tracks.

| track | groups train / val / test |
|---|---|
| `county_block` (0.5° spatial blocks) | 399 / 133 / 133 |
| `crop_year` (crop years) | 96 / 5 / 5 |

| case | R3 base → head | D6 base → head |
|---|---|---|
| A-1 flat county-block `splits`, crop-year declaration | PASS → PASS | **FAIL → FAIL**, `BLOCKS_CONTRADICT_SPLITS` |
| A-2 tracked `splits`, both tracks declared | **FAIL → PASS** | **FAIL → PASS** |
| A-3 crop-year track, `unit="row"` | FAIL → PASS | FAIL → **FAIL**, `DEPENDENCE_UNIT_TOO_FINE` |
| A-3 crop-year track, `unit="county"` | FAIL → PASS | FAIL → **PASS** (§5) |
| A-4 tracked `splits`, declaration names no track | FAIL → PASS | FAIL → **FAIL**, `TRACK_UNDECLARED` |
| A-5 tracked `splits`, one of two tracks declared | FAIL → PASS | FAIL → PASS, gap recorded |

**A-1 is the recorded baseline and it does not move.** At both shas, verbatim:

> `BLOCKS_CONTRADICT_SPLITS: the declaration says arm 'val' holds 5 'crop_year'
> block(s) and \`splits\` says it holds 133 group(s). Only in the declaration:
> ['2016', '2017', '2018', '2019', '2020'].`

Five crop years judged against 133 spatial blocks — a partition the declaration
was never taken under. That is what "fray cannot wire D6 for its unseen-year
track" is, in the check's own words, and this branch does not make it go away:
a flat `splits` still gets exactly this answer.

**A-2 is the item.** At head each track is judged against its own partition:

| declared track | blocks tied to | units in arm | blocks in arm | groups in that track's `splits[val]` |
|---|---|---:|---:|---:|
| `county_block` | `splits.tracks.county_block` | 133 | 133 | 133 |
| `crop_year` | `splits.tracks.crop_year` | 5 | 5 | 5 |

R3 at head reports both tracks: `county_block` 399/133/133, `crop_year`
96/5/5, and `group_ids_shared_between_tracks = {"county_block&crop_year": 0}` —
recorded, interpreted nowhere.

**A-3 (`row`) fires**, naming the track:

> `track 'crop_year': DEPENDENCE_UNIT_TOO_FINE: the bootstrap resampled 1365
> 'row' unit(s) inside arm 'val', but holdout policy 'county_year_splits' keeps
> whole 'crop_year' blocks in one partition and that arm holds 5 of them.`

1,365 val rows over 5 crop years — the shape of the round-8 finding, reached
for the first time through a `splits` binding fray could actually publish.

**A-4 fires.** The crop-year declaration's blocks match the `crop_year` track
EXACTLY, so a reader that searched for a matching track would report PASS. It
returns `TRACK_UNDECLARED` instead.

**A-5's gap is recorded, not refused**: `tracks_without_declaration =
["county_block"]`, as the pre-registration said it would be.

## 2. CONTROL B — the silent control, as bytes

Every check in this package that reads the `splits` binding is R3 and D6.
Grepped, not assumed:

```
$ grep -rn 'resolve("splits")' src/
src/resilient_mlkit/checks/decision.py:492:        splits_fn = repo.resolve("splits")
src/resilient_mlkit/checks/readiness.py:458:        fn = repo.resolve("splits")
```

Both were driven at base and head against the REAL split membership
`resilient-torrent` (211/71/70 GRDC basins) and `resilient-chokepoint`
(20/4/4 corridors) return from their own `mlkit_bindings:splits`, in three
cases each: the block unit (the adopter's own convention), the row unit (the
bootstrap the contract exists to refuse), and no `resampling_declaration`
binding at all.

| case | R3 | D6 |
|---|---|---|
| torrent, block unit | PASS | PASS |
| torrent, row unit | PASS | FAIL |
| torrent, no binding | PASS | NA |
| chokepoint, block unit | PASS | PASS |
| chokepoint, row unit | PASS | FAIL |
| chokepoint, no binding | PASS | NA |

```
$ diff controlB_base.json controlB_head.json     # (no output)
$ shasum -a 256 controlB_base.json controlB_head.json
28e0db98fc879445cf0c7d88456bd2acdb46b2867b7bc6ed678ff6762342f3ef  controlB_base.json
28e0db98fc879445cf0c7d88456bd2acdb46b2867b7bc6ed678ff6762342f3ef  controlB_head.json
```

**Byte-identical: status, reason and evidence, on all six cases.**

**One near-miss, disclosed because it was real for an hour.** The first head
build extended D6's NA-when-unbound guidance to name the new optional field.
`core.result.redact` bounds every reason at `MAX_REASON = 400` and that
sentence already spent 397, so the longer text came back **truncated
mid-word** — visible in the first diff of this control, which is why the
control exists. `MAX_REASON` was not touched. The sentence was put back
exactly as it was and the new shape is documented where there is room:
`spine/mlkit/repo.toml` (which that very sentence points the reader at),
`DECLARATION_SHAPE`, `README.md`, and D6's own docstring.

**Suite.** 977 passed at `24f23b8`; **1,017 passed** at this head; 0 failed at
either. `ruff check src/ tests/` clean.

## 3. The strictly-stricter claim, attacked

| claim | how it was checked | outcome |
|---|---|---|
| `MIN_HOLDOUT_GROUPS` not moved | `git diff 24f23b8..HEAD -- src/` shows the constant untouched; under tracks it is applied once **per track** | holds — `test_r3_FIRES_when_ONE_track_is_below_the_holdout_floor` fires on a track a one-partition read would have missed |
| the refusal ladder untouched | `git diff 24f23b8..HEAD -- src/` over `core/served.py` is +42/−5 and matches nothing in `straddling` / `crosscutting` / `split_blocks` / `refusal =`; the only additions to `__post_init__` are the two `track` type checks, above the ladder and before `draws` | holds |
| no threshold, range or floor edited | `git diff 24f23b8..HEAD -- src/ \| grep -E "^[+-].*(MIN_HOLDOUT_GROUPS\|MAX_REASON\|MAX_COVERAGE_TOL\|MAX_METRIC_TOL\|MIN_COVERAGE_N) *="` is **empty** | holds |
| flat inputs unchanged | CONTROL B byte comparison, plus `test_r3_single_track_evidence_has_no_track_shaped_key` and `test_d6_single_track_pass_is_tied_to_splits_by_that_exact_word` | holds |
| the tracked shape can only PASS by clearing every clause on every track | five R3 firing/silent pairs | holds |
| a bare sequence is no longer silently `dict()`-ed into a declaration | `test_d6_refuses_a_shape_it_cannot_read_by_type` | **stricter than base** — at `24f23b8` a list of pairs could have been reassembled into a declaration whose fields came from wherever the pairs landed |

### The hole a second track could have opened one layer up

`Comparison` ties its interval to its declaration by ARM, and **both** of
fray's tracks have an arm called `val`. So the name-level tie cannot separate
them, and a declaration borrowed from the wrong track would sit inside a
`Comparison` that raises nothing.

It does not need a new name to compare, because the tie one layer up is by
CONTENT: `challenger_decision` compares `resampling.row_digest` against
`candidate_row_digest`, and the two tracks' val arms are different rows.
Driven rather than argued —
`test_a_declaration_from_the_WRONG_TRACK_is_caught_by_CONTENT_at_the_gate`
asserts `RESAMPLING_ROWS_UNTIED` for the borrowed declaration and not for the
own one, so a future change that drops the digest tie fails that test instead
of passing quietly.

### The guard is not dead

Six single-fact remutations of the SILENT two-track declaration, each
producing a **different** named verdict: `DEPENDENCE_UNIT_TOO_FINE`,
`BLOCKS_CONTRADICT_SPLITS` (wrong track), `TRACK_UNDECLARED`,
`TRACK_NOT_IN_SPLITS`, `UNIT_LABEL_CONTRADICTS_CONTENT`, and
`BLOCKS_CONTRADICT_SPLITS` again from moving `splits` rather than the
declaration. The test asserts the six messages are pairwise distinct.

## 4. What moved in the artifacts

`ResamplingDeclaration.to_dict()` emits `track` **only when it is non-empty**,
so no current adopter's evidence bytes change — that is what makes §2 a
`shasum` rather than a reading. D6's evidence gains `tracks_in_splits`,
`tracks_without_declaration`, `declarations` and `n_declarations` **only** on
the tracked or sequence paths, and `blocks_tied_to` reads the literal string
`"splits"` on the single-track path exactly as before.

## 5. WHAT THIS BRANCH DID NOT CLOSE

**The county half of CONTROL A stays silent, exactly as pre-registered in §6
of the pre-registration, before it was measured.**

`ResamplingDeclaration`'s ladder asks `elif not crosscutting and split_blocks:`
before it will say `DEPENDENCE_UNIT_TOO_FINE`, so a unit whose keys appear in
more than one arm is exempt unconditionally. On fray's crop-year track a county
contributes rows to train, val and test years, so:

| declared unit | derived relation | units in arm | blocks in arm | D6 at this head |
|---|---|---:|---:|---|
| `crop_year` | `UNIT_IS_THE_BLOCK` | 5 | 5 | PASS |
| `row` | `UNIT_FINER_THAN_BLOCK` | 1,365 | 5 | **FAIL** |
| `county` | `UNIT_CROSSCUTS_ARMS` | **344** | 5 | **PASS** |

344 counties drawn as exchangeable replicates inside an arm whose policy says
it holds five dependent blocks, and the check is silent. Recorded as
`docs/ESCALATIONS.md` **E-M33**. It is not repaired here because that ladder is
item I1-M1's target and two parallel edits to one refusal is how a refusal ends
up with two definitions.

**Also not closed, and named rather than left to be found:**

* **mlkit does not compare group ids across tracks for leakage.** Two tracks
  are two vocabularies; the shared-id count is in R3's evidence and is
  interpreted nowhere. A repo that genuinely shares a vocabulary between tracks
  gets no cross-track holdout check from this contract.
* **A track with no declaration is recorded, never refused.** mlkit cannot
  know whether a track produced an interval.
* **No fray, chokepoint or torrent file is changed by this item.** fray's
  repin-and-bind — publishing the tracked `splits` and the two declarations for
  real — waits on the user's mlkit merges, and this branch is not merged.
* **The ledgered test reads are HELD.** No model was loaded, no prediction or
  metric was computed on any row of any `test` partition. Split *membership* is
  what R3 and D6 already read on `main` through the `splits` binding.

## 6. Deviation from the pre-registration

One, and it is a subtraction. §2.5's table listed `TRACK_UNDECLARED` /
`TRACK_NOT_IN_SPLITS` as separate rows and §3 point 3 collapsed them into one
bullet; the implementation has both as distinct named constants, which is what
the table said. No control pair was added, removed or weakened. The nine
declared control pairs are all driven: A-1..A-3 in §1, B-1/B-2 in §2, and
B-3..B-9 as the named tests in `tests/test_track_aware_splits.py`.
