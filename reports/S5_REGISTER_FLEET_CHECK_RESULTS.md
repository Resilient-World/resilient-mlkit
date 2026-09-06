# S-5 — `mlkit register --check-fleet` — RESULTS

**Driven 2026-09-06 against `reports/S5_REGISTER_FLEET_CHECK_PREREGISTRATION.md`
(commit `b05410c`, the first commit of this branch, written before any source
change).** Driver: `scripts/s5_register_fleet_drive.py`. Machine record:
`reports/S5_REGISTER_FLEET_DRIVE.json`.

Build: `1.1.0+src.175e1000c950`. Clones, all fresh from the remote on
2026-09-06 and never written to by the drive:

| repo | head |
|---|---|
| `resilient-chokepoint` | `ddb87faf2b4f1d44f70350657e9b3e27d51d169e` |
| `resilient-fray` | `5440702ca861a34b11db64e7571d1835f264c22e` |
| `resilient-torrent` | `39977c66327716ad860177c6279780736171c5b1` |

Every mutation below is committed into a LOCAL CLONE of one of these under the
drive's own workdir and thrown away with it. The checkouts themselves are read
only.

---

## B1 — the three current mains PASS, on one git object

```
$ mlkit register --check-fleet --root <fleet>
root: .../mlkit-v4/fleet
  resilient-chokepoint     HEAD ddb87faf2b4f  blob 9f6cb2b015f2  body b2dd5cc4895f61f9
  resilient-fray           HEAD 5440702ca861  blob 9f6cb2b015f2  body b2dd5cc4895f61f9
  resilient-torrent        HEAD 39977c663277  blob 9f6cb2b015f2  body b2dd5cc4895f61f9
  3 copies, IDENTICAL git blob 9f6cb2b015f2ba9ca9e8c696b310d1bd9767e738
  0 problem(s)
$ echo $?
0
```

The blob is the one the S-5 re-cut landed —
`9f6cb2b015f2ba9ca9e8c696b310d1bd9767e738` — and the canonical body is
`b2dd5cc4895f61f9aab1412057d1f575cb6ee79e7026d8a497d4326fac3c9bd9`, agreed by
**all three repos' own `canonical_body_sha256` implementations applied to all
three bodies**. Nine function-body pairs, one answer.

## B2–B4c — every mutation fires, and the field is named

One field of one copy, committed into a clone of the tree B1 passed on, so a
firing is attributable to the mutation and to nothing else. `resilient-chokepoint`
is the subject in every case.

| case | what changed | exit | reported |
|---|---|---|---|
| **B2** | one field edited, digest left stale | **1** | `SELF_INCONSISTENT canonical_body_sha256` **and** `DIVERGENT title` |
| **B3** | digest replaced, body untouched | **1** | `SELF_INCONSISTENT canonical_body_sha256` only — there is no field divergence to find, and none is invented |
| **B4** | one field edited **and the digest re-derived** | **1** | `DIVERGENT title` |
| **B4b** | E-080's own field: the repo zeroing its own entry, digest re-derived | **1** | `DIVERGENT source_files_quoting_the_replaced_sentence.resilient-chokepoint` |
| **B4c** | one declaration removed by id, digest re-derived | **1** | `DIVERGENT declarations[FR-D2-CONTROL-RESTATEMENT]` |

**B4 is the result that decides whether this command was worth building.** The
mutated copy re-derived its own digest with **its own committed function**, so it
is internally consistent: its own `verify_one_sided_placebo_register.py --mode
check` is green, and the constant its own suite pins still matches. That is
E-080's state, and it is the state in which four bodies were live at once while
every repo reported `0 problem(s)`. This is the first thing in the fleet that
says no.

**B4b names the field to the entry that actually drifted.** Not "the register
differs", not "`source_files_quoting_the_replaced_sentence` differs", but
`source_files_quoting_the_replaced_sentence.resilient-chokepoint`, with both
values printed:

> `… holds 2 distinct values across the copies: resilient-chokepoint =
> ["src/some/file_that_quotes_the_replaced_clause.py"]; resilient-fray,
> resilient-torrent = []`

The values are grouped by VALUE rather than reported as "these two differ from
that one", because a divergence has **no innocent party** until a person says
which copy the document is — and E-080's four-way drift is what happens when
each side assumes it is the innocent one.

**B4c names the missing declaration by id.** A positional comparison would have
said `declarations[3]`, and on a deletion in the middle would have said every
index after it, sending a reader to the wrong place. The dropped id here is
`FR-D2-CONTROL-RESTATEMENT`; E-080's real instance was
`FR-D2-NASS-45ORIGIN-ABOVE` live in exactly one copy.

## B5 — the three implementations agree

Every repo's `canonical_body_sha256` is applied to every repo's body and the
results are recorded per copy in `computed_by`. A copy on which they disagree is
reported as `IMPLEMENTATIONS_DISAGREE` **instead of** any digest verdict, because
a digest verdict taken with an ambiguous definition is not a verdict. On the
three current mains they agree, on every body, at
`b2dd5cc4895f61f9…`. Held as a test (`test_implementations_that_disagree_are_…`)
with one fixture's function replaced, so the branch is exercised rather than
asserted.

## B6 — one copy REFUSES

```
REFUSED: 1 copy/copies of docs/one_sided_placebo_register.json found under
<root> (resilient-chokepoint). The invariant this checks lives BETWEEN the
repos, so a run over fewer than two copies measures nothing — and reporting it
green would be the strongest possible version of the defect it exists to catch
(E-080)
$ echo $?
2
```

Exit **2**, distinct from **1**, so a caller can tell "the copies disagree" from
"there were not enough copies to ask". They need different actions, and a single
non-zero code would have made "get the other checkouts" look like "resolve a
drift".

## B7 — the silent half, after every mutation

The unmutated fleet is re-driven **last**, on the same clones every mutation ran
against and after each was reset:

```
B1_unmutated                       exit=0   blob 9f6cb2b015f2   0 problems
B1_unmutated_after_every_mutation  exit=0   blob 9f6cb2b015f2   0 problems
```

Identical. So no firing above is an artefact of the clones, and the check is not
one that fires on everything.

## B8 — the suite

One clone, `PYTHONPATH=<clone>/src`, `python -m pytest tests -q`, no `-k`
filter:

```
main   1d9df13 : 1272 passed, 3 skipped
branch          : 1288 passed, 3 skipped
failures ONLY on the branch : NONE
failures ONLY on main       : NONE
```

Identical failure sets — both empty — and **+16 passing**, all of them
`tests/test_register_fleet.py`. No existing test changed.

`ruff check src tests scripts` at the pinned `0.16.5`: output **byte-identical**
to `main`'s. `mypy src/resilient_mlkit`: 3 errors, **the same 3 as `main`**
(`module_bindings.py:178` ×2, `identity.py:487`), all pre-existing.

## What is proposed rather than done

`docs/S5_REGISTER_FLEET_CHECK.md` §3 carries the exact pre-landing obligation
paragraph for `resilient-fray`, `resilient-chokepoint` and `resilient-torrent`,
with `docs/one_sided_placebo_register.md` named as its home in each. **No sibling
repo is edited by this branch**, and the plan reserves those edits to the agents
who own those repos.

The obligation is weaker than a gate, and the document says so on its face: the
two shapes that would make it a gate — a credentialed fleet CI job, or making the
repos readable to one another (E-M37's S-10 question) — are both the signatory's
under rules 12 and 13, and are named rather than taken.

## What this branch did not do

* It created, edited and re-pinned nothing in any register, declaration, halt
  region or digest, in any repo. It reads and compares.
* It added no CI job, scheduled task, credential, token, secret, or
  cost-incurring resource.
* It printed no credential. The register carries none, and the command emits only
  register fields, digests, repo names and paths.
* It read no holdout: the whole check is a read of committed JSON.
