# Pre-registration — closing the instrument's silent-vanishing paths

**Written before any source edit and before any run.** Commit order is the
evidence: this file lands first, and every number quoted afterwards has to be
one this document said in advance how to obtain. Nothing below states a result.

Check IDs: `SV-1-REGISTRY`, `SV-2-PHASE-EXIT`, `SV-3-PORTFOLIO-EXIT`,
`SV-4-PARITY-DISCOVERY`.

Authorization: **A-1** — local CPU, no cloud, no GPU, no spend. Nothing is
fitted. No model repo is written to.

---

## The defect class

Four places in this package turn *"a thing that should have been measured was
not"* into *"a thing that passed"*. Each is a different mechanism and the same
error: an absence renders as a success.

| # | Site | How the absence disappears |
|---|------|---------------------------|
| 1 | `checks/__init__.py:125` | `for_phase` filters out any id in `PHASE_ORDER` missing from `_REGISTRY`. A check that failed to import is not reported missing; it stops existing. |
| 2 | `cli.py` `cmd_check` | Totals and the exit code are derived from what ran. Eleven of twelve checks running prints `11/11 PASS` and exits `0`. |
| 3 | `cli.py` `_cmd_portfolio` | `return 0`, unconditionally. `README.md:144` says exit `1` means "something failed (CI gates on this)". For `--portfolio` that sentence is false today. |
| 4 | `scripts/verify_served_hash_parity.py:62-75` | Candidate discovery accepts only a JSON under `models/` with a **top-level** `artifact_sha256`. Three repos pin a champion in a shape it cannot see, and each is rendered `NA` with the reason *"this repo serves nothing hash-pinned yet"* — a claim about the repo that the scanner did not measure. |

Rule 7 forbids reimplementing mlkit's gates elsewhere; it does not forbid
repairing them here, and mlkit is where they are defined. No threshold, no
tolerance, no range and no holdout is touched by any of the four. `PHASE_ORDER`
membership is unchanged: no check is added and none removed.

---

## SV-1-REGISTRY — an unregistered id becomes a FAIL, not a gap

`for_phase(phase)` will return one entry per id in `PHASE_ORDER[phase]`, in
order, with no filtering. An id absent from `_REGISTRY` after `load_all()`
yields a synthesized spec whose function returns a **FAIL**-shaped
`CheckResult` carrying the reason

> `declared in PHASE_ORDER but absent from registry after load_all()`

A focused test asserts `set(PHASE_ORDER ids) ⊆ set(_REGISTRY)` after
`load_all()`, so the synthesized row is a backstop that the real tree never
exercises rather than a state anyone is expected to reach.

**Pass criterion.** With the real registry the returned specs are exactly the
registered ones, in `PHASE_ORDER` order. With a fixture id injected into
`PHASE_ORDER`, one FAIL-shaped row appears carrying that id and that reason.

## SV-2-PHASE-EXIT — the phase's denominator is `PHASE_ORDER`, not the run

`_run_phase` will, after running, compare the ids it produced against
`PHASE_ORDER[phase]` and append a FAIL for any id with no result. `cmd_check`
will additionally compare the number of results aggregated against
`len(PHASE_ORDER[phase]) * len(repos)` and return **1** on a mismatch, before
the existing status ladder is consulted.

The existing ladder is unchanged: `1` FAIL, `3` NA/STALE, `4`
DEFERRED/ESCALATED, `0` otherwise.

**Pass criterion.** A run whose phase loses a check exits `1` and prints a row
naming the lost id. A run with the complete registry produces byte-identical
per-check verdicts to the pre-change build and the same exit code.

## SV-3-PORTFOLIO-EXIT — the portfolio's exit code comes from the worst state

`_cmd_portfolio` will derive its exit code from the resolved terminal states,
first match wins, in this severity order — deliberately the same ladder
`cmd_check` already uses, so the two commands cannot disagree about what a
number means:

| Terminal state | Exit | Why |
|---|---|---|
| `BLOCKED` (a FAIL, or a hard stop) | `1` | what `README.md:144` already promises CI gates on |
| `IN-PROGRESS` (unmeasured or stale) | `3` | incomplete, matching `cmd_check`'s NA/STALE |
| `READY-PENDING-KEYS` | `4` | matching `cmd_check`'s DEFERRED |
| `AWAITING-SIGNOFF` | `4` | matching `cmd_check`'s ESCALATED |
| `READY-TO-TRAIN` | `0` | |
| anything else | `1` | fail closed; an unrecognised state is not a pass |

The README is **not** edited. It already states the contract; the code is what
is wrong.

In the same change, `portfolio.py:198`'s hand-written readiness column header
`R(9,10,11,1-8)` — which names eleven checks where twelve run — is **derived**
from `PHASE_ORDER` by compressing each phase's ids into runs of consecutive
numbers, in the order the phase runs them. No header text is written by hand.

**Pass criterion.** A fixture portfolio containing one `BLOCKED` repo exits
nonzero; an all-`READY-TO-TRAIN` fixture exits `0`. The rendered readiness
header names as many checks as `PHASE_ORDER["readiness"]` holds.

## SV-4-PARITY-DISCOVERY — see the three linear champions, and keep the two kinds apart

Discovery is extended along three axes and **no comparison rule is loosened**:

1. **Roots.** `models/` **and** `data/model_registry/`. Surge's champion
   registry lives at the latter and was never visited.
2. **Shapes.** Two, labelled, and never conflated:
   * `canonical_self_hash` — a top-level `artifact_sha256`. Verified, as today,
     by recomputing `core.served.canonical_payload_sha256` over the payload
     with the hash field excluded. *The record hashes itself.*
   * `sidecar_coefficient_digest` — a top-level `artifact` object carrying both
     `path` and `sha256`. Verified by `core.served.sha256_file` over the bytes
     at `path`, resolved relative to the repo root. *The record pins a
     different file's bytes.* This is a weaker property than a self-hash: the
     record itself is unpinned, and the report must say so rather than let the
     two render alike.
   Only the **top-level** `artifact` object is followed. Digests nested deeper
   (torrent's `committed_val_row.artifact_sha256`, for instance) are out of
   scope here and are not silently swept in.
3. **Trees.** If a repo's root checkout yields no candidate, linked worktrees
   from `git worktree list --porcelain` are searched in order and the first
   tree that yields candidates answers, with the tree recorded on every row it
   produced. This mirrors the convention `core/artifact.py` already documents
   and exists so that "not on this branch right now" stops rendering as "this
   repo serves nothing". A row sourced off-checkout is evidence about that
   worktree and is flagged as such.

Statuses become `MATCH`, `DIFFER`, or `NA` **with the reason that is actually
true of what was searched**. A repo where the search ran and found nothing gets
a reason naming the roots searched and the two shapes looked for — not a claim
about what the repo serves. A sidecar whose referenced file is absent is `NA`,
never `MATCH` and never `DIFFER`: an unresolvable pin is unmeasured, not equal
and not unequal.

Exit code is unchanged in spirit: `0` when everything compared matched, `2`
otherwise, and `2` when nothing was compared at all.

**Pass criterion.** arabica, torrent and surge acquire rows with a measured
status and no "serves nothing hash-pinned yet" reason. choco and blackout —
which the pre-change scan shows carry neither shape — keep an `NA`, because
`NA` is correct for them and a scanner that cannot stay silent measures
nothing.

---

## Control pairs — each must be forced to fire and forced to stay silent

| Pair | Positive (must fire) | Negative (must stay silent) |
|---|---|---|
| P1 vanishing check | fixture id injected into `PHASE_ORDER` → one FAIL row with the registered reason, phase exit `1` | real registry → no synthesized row; every check's verdict byte-identical to the pre-change build |
| P2 phase denominator | `_run_phase` forced to drop a result → `cmd_check` exits `1` | complete run → same exit code as pre-change |
| P3 portfolio exit | fixture with a `BLOCKED` repo → nonzero | fixture all `READY-TO-TRAIN` → `0` |
| P4 parity mismatch | fixture registry JSON, nested `artifact.sha256`, referenced bytes altered → `DIFFER` | matching fixture → `MATCH` |
| P5 parity silence | — | a fixture repo carrying neither shape → `NA` with a reason naming what was searched, and no `MATCH` invented |

A pair with only one half is not reported as a pair.

---

## Must not change — baselines taken before the first edit

Recorded at `main` = `3df724d5376fe6cf0f1736db37c6dfef563eab31`.

sha256, `src/resilient_mlkit/checks/`:

    e55b34a1017d9af356cece6ce89c54728f1f2e90f7181a8a6e3ca345728d241e  __init__.py
    bb0538f645a31b6a2b658d5c5ac1c0d8b929509ee46cb07ae7b9918a1edb691a  decision.py
    c8e9ed51f860666f9b7ec3401e91586e7ca682604b01a02cf6d328158b6dd77d  economics.py
    1ce5cea69a89842ccfc2c6dd5db3f65f00c1fe630c5881f77eabca637a674afd  readiness.py
    7e617323dfd600a4954f61b2c29a24ab825281ec6d8a787c0bae29b2f279da6d  selection.py
    bf085947223327d162ee2ca81a29c556f1799cb845fe8c063e35c2d5134bf3a6  triage.py

`__init__.py` is the one file above that this work edits, and it edits
`for_phase` only. The other five are untouched, and their digests are restated
at the end unchanged. No threshold, tolerance or range is edited in any of them.

sha256, signing and fleet-adjudication files, none of which this work writes:

    06eddc07f184e6c7a5642a406cc5e84ebc288b41b01337f2f5cb7eb28846befb  spine/docs/allowlist.yaml
    ba3b0ef5d71e2a5f8ac8a5495dd59fa1767e745f6cd336147f53c0b5b312f4a3  portfolio/FLEET_VERDICTS.json
    e984c8151cc3687fd5fd298b4036984b37afdca002057b02db671ce1832dd104  portfolio/FLEET_VERDICTS.md
    4f1147de5bbda8b9b7dcef8a4cceb40476ad2e8c882b9c760f4c3bd1c0e0d4f5  portfolio/SPINE_DRIFT.json
    ec40d83625ef6a134e4aabb5e48aa87900458ad20f7cd885bf0e9b6935e527b1  portfolio/SPINE_DRIFT.md
    90a469ab3e820a61b4bfd96b7ab8c2c9d4f7f078421714876c59fd4b53b55943  portfolio/MODEL_QUALITY.md

`PHASE_ORDER` membership, restated so a diff to it is visible:
triage `T1 T2 T3 T4 T5`; selection `S1 S2 S3 S4 S5`; readiness
`R9 R10 R11 R12 R1 R2 R3 R4 R5 R6 R7 R8`; decision `D1 D2 D3 D4 D5`;
economics `E1 E2 E3 E4 E5`. Thirty-two ids, five phases.

The eight model repos are **read-only** to this work. `store.save` writes
`.mlkit/results/` into a repo, so no phase run is executed against a real model
repo here; every check-pipeline control uses a fixture `Repo` on a temp path.
The parity scanner opens files for reading and runs `git` read commands only.
No spine sync is run: `sync_spine.py` writes into eight repos and belongs to a
write-authorized phase, which this is not. Repo HEADs are recorded at the end
and compared.

## Registered in advance as *not* being done here

* The README's exit-code table is not edited. Code is brought to it.
* No gate file, threshold, tolerance, range or holdout is edited (rule 6).
* `docs/allowlist.yaml` and every signing file are untouched (rule 14). The
  proposal that the fleet converge on **one** champion-record shape is written
  to `docs/ESCALATIONS.md` as a proposal. Adopting it is the signatory's
  decision, not this agent's (rule 12).
* No training. Nothing is fitted, no split is read, and no test arm is opened.
