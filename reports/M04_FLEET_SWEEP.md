# M-04 — R11 fleet sweep, E-M17 residual 4

Read-only. Nothing in any fleet repo was written, committed, or pushed.
Every number below was produced by running `resilient_mlkit`; nothing here is
estimated, and a figure that was not measured is written `NA` with its reason.

## Method

Two interpreters per repo, one per side of the change, each with its own
`PYTHONPATH` pointing at a DIFFERENT `resilient-mlkit` checkout and each
**asserting its own `resilient_mlkit.__file__`** before it scans anything —
the E-M18 dual-interpreter shape. A sweep that imported one mlkit and
attributed the result to the other would measure nothing, and the assertion
is what rules that out rather than the invocation looking right.

- **BEFORE side** — a fresh clone of `resilient-mlkit` at `main` =
  `8517341dbd11731d10be20cd4b186b4be32f609b`, bound as
  `.../m04-fleet/resilient-mlkit/src/resilient_mlkit`.
- **AFTER side** — this branch's worktree, bound as
  `.../mlkit-m04/src/resilient_mlkit`. The table below was produced with
  **both Stage 1 (the folds) and Stage 2 (the `UNREADABLE_STAMP` NA lane)
  enabled** — the budget that gates Stage 2 is a budget for the thing that
  actually ships, so it was measured with it turned on. Stage 1 alone was
  measured separately at the Stage-1 commit and gave the same `0 → 0`.
- **Repos** — every checkout freshly cloned at its **remote `main`**
  (`git clone --depth 1 --single-branch --branch main`), because local
  checkouts in this workspace are stale: the local `resilient-blackout`
  `pyproject.toml` does not mention mlkit at all, while its remote main does.
- **Per repo** — `ft.load_source_registry(root)` then `ft.scan_repo(root,
  registry)`; every `Finding` reduced to
  `(path, line, field, claim_field, claim_value, rule, severity, matched_on)`
  and the two sides compared as sets.

## Result — the whole fleet at its remote mains

| repo | remote `main` | .py files scanned | allowlist entries read | R11 findings BEFORE | AFTER | NEW | GONE |
|---|---|---|---|---|---|---|---|
| `resilient-arabica` | `5b40d703fe` | 388 | 40 | 0 | 0 | 0 | 0 |
| `resilient-backend` | `c76ebde7fd` | 491 | 0 (no `docs/allowlist.yaml`) | 0 | 0 | 0 | 0 |
| `resilient-blackout` | `4ffe52d9d7` | 253 | 11 | 0 | 0 | 0 | 0 |
| `resilient-choco` | `fd44583d77` | 401 | 56 | 0 | 0 | 0 | 0 |
| `resilient-chokepoint` | `56854a470f` | 281 | 13 | 0 | 0 | 0 | 0 |
| `resilient-fray` | `41b496e64b` | 228 | 15 | 0 | 0 | 0 | 0 |
| `resilient-mlkit` | `8517341dbd` | 32 | 0 (no `docs/allowlist.yaml`) | 0 | 0 | 0 | 0 |
| `resilient-surge` | `997d5ed49c` | 351 | 36 | 0 | 0 | 0 | 0 |
| `resilient-torrent` | `373d93501c` | 551 | 49 | 0 | 0 | 0 | 0 |
| `resilient-triage` | `806d4e067e` | 418 | 22 | 0 | 0 | 0 | 0 |
| **total** | | **3394** | | **0** | **0** | **0** | **0** |

**Over-fire budget, Stage 1 + Stage 2: 0 new findings over 3394 Python files.**
No repo's R11 verdict moves in either direction — none gains a
`CONTRADICTED_SOURCE` FAIL from a folded spelling, and none is taken to NA by
the `UNREADABLE_STAMP` lane. Under the M-04 plan row this is the budget that
decides whether Stage 2 ships; it is not ugly, so it does.

### What this sweep does NOT cover, stated rather than implied

- **Which ten.** The eight repos that name `resilient-mlkit` in their
  `pyproject.toml` (arabica, blackout, choco, chokepoint, fray, surge,
  torrent, triage), plus `resilient-backend` and mlkit itself — the same ten
  `resilient-*` checkouts E-M19's fleet walk enumerated, so the population is
  comparable to the last committed sweep rather than newly chosen here.
  `resilient-frontend`, `resilient-mentra`, `resilient-provenance` and
  `resilient-transect` have no `pyproject.toml` and are not adopters.
- Each repo was cloned at `--depth 1`, so this measures each remote `main` as
  it stands, not its history.
- R11's own conservative preconditions are unchanged by this branch; a record
  this check did not adjudicate before is not adjudicated now for any reason
  other than the four spellings.

## Control pair for the harness itself

A sweep reporting `0` on both sides is exactly what a **dead** harness also
reports. Both halves were driven.

### Control — no false delta (same rev on BOTH sides)

`BEFORE` and `AFTER` both bound to `8517341`, all ten repos:

```
TOTAL NEW: 0
TOTAL GONE: 0
```

### Control — the harness is NOT dead (planted fabricators, real repo tree)

A **copy** of the `resilient-fray` clone (the fray checkout itself untouched)
with one file added, `src/m04_planted_control.py`, holding seven records that
are each 100% `rng.normal` plus literals: five stamped `zq7lk=` with the same
claim written five ways (the plain literal, `"_".join(["era5", "land"])`,
`"era5_%s" % "land"`, `"era5_{}".format("land")`, `FEEDS["primary"]`) and two
with a drawn `yield_tonnes` target under an unresolvable `source=`
(`f"era5_{region}"` and `FEEDS[which]`). fray's own signed
`docs/allowlist.yaml` was the registry, unmodified.

| side | mlkit bound | .py files | findings |
|---|---|---|---|
| BEFORE (`8517341`) | `m04-fleet/resilient-mlkit/src/resilient_mlkit` | 229 | **1** |
| AFTER (this branch) | `mlkit-m04/src/resilient_mlkit` | 229 | **7** |

The AFTER side's seven, as reported:

```
line  9  CONTRADICTED_SOURCE  INPUT_FABRICATED  zq7lk = era5_land
line 17  CONTRADICTED_SOURCE  INPUT_FABRICATED  zq7lk = era5_land
line 26  CONTRADICTED_SOURCE  INPUT_FABRICATED  zq7lk = era5_land
line 34  CONTRADICTED_SOURCE  INPUT_FABRICATED  zq7lk = era5_land
line 43  CONTRADICTED_SOURCE  INPUT_FABRICATED  zq7lk = era5_land
line 51  UNREADABLE_STAMP     UNREADABLE_STAMP  source = f'era5_{region}'
line 60  UNREADABLE_STAMP     UNREADABLE_STAMP  source = FEEDS[which]
```

The BEFORE side finds the plain literal and misses the other six — which is
E-M17 residual 4 and its residue, driven at fleet scale on a real repo tree
rather than on a fixture string. So the `0 → 0` on the actual fleet is a
measured zero, not a harness that scans nothing, and **both** new lanes are
demonstrably live inside this harness.

## Reading of the budget

Stage 1 changes what R11 can READ, not what it is willing to adjudicate: the
preconditions (`manufactured_of`, the honesty rule, branch (a)/(b)) are
untouched. Stage 2 adds a verdict that did not exist, and it is scoped by
four conjuncts each of which has its own silent control in the suite.

The fleet result is consistent with both — no honest record in 3394 files
carries a folded-constant provenance stamp that reaches the registry, and no
wholly-manufactured record with a drawn target carries an unresolvable
source-naming field — and the planted control shows the new reach is real
where each shape exists.

**What a zero budget does not prove.** It says nothing moved on ten trees as
they stand today; it does not say nothing will move when a repo next writes
one of these shapes. That is the intended behaviour, not a side effect: an
adopter that writes `source=f"era5_{region}"` over a drawn target will see R11
go NA, and the fix is to resolve the value or declare the record's provenance
beside it. The three adopters pinned to `branch = "main"` (choco, triage,
blackout) inherit this on their next re-lock with no review step — that is
M-08/M-09's enumeration to carry, and it is repeated here so it is not
discovered by a re-lock.
