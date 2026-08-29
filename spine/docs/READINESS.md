# READINESS.md — Phase 3, correctness

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

Twelve checks. `mlkit check --phase readiness` runs them **in the order below,
which is not numerical**. Run them one at a time and commit after each with the
check ID in the message.

## The order, and why it is this order

| # | Check | Why here |
|---|---|---|
| 1 | **R9** `LICENCE_GATE` | Cheapest check in the phase and the most decisive. A licence defect makes every downstream result moot, and it is the one defect class that gets *more* expensive the longer you train. It is also the only check that runs on every commit rather than every loop. Running it first costs seconds and can save the phase. |
| 2 | **R10** `FABRICATED_DEFAULTS` | A pure `ast` walk — no imports, no data, no network — so it is the cheapest check after R9, and decisive in the widest sense: a fabricated default invalidates every figure downstream of it, including the ones the other readiness checks measure. It also has to precede R1–R7, because those go through declared bindings and cannot see the code R10 reads. |
| 3 | **R11** `FABRICATED_TARGETS` | The same kind of walk, so the same cost. It runs before **R5** specifically: R5 counts rows by the provenance field R11 adjudicates, so an R5 PASS recorded after an R11 FAIL is a pass counted with a broken ruler. |
| 4 | **R12** `SERVED_CONTRACT` | The third `ast` walk, so the same cost again. It has no ordering *dependency* — nothing downstream counts anything by what R12 adjudicates — so its place here is the cost argument alone. |
| 5 | **R1** `CHECKPOINT_PROVENANCE` | Static. Answers "do we know what these weights are" before anything loads them. |
| 6 | **R2** `OVERFIT_ONE_BATCH` | The cheapest check that can prove the model is wired up at all. A model that cannot overfit one batch has a defect no amount of data will fix. |
| 7 | **R3** `BLOCKED_SPLITS` | Cheap, and if the splits leak, every metric measured after this point is meaningless. |
| 8 | **R4** `METRIC_KNOWN_ANSWER` | Cheap. If the metric cannot reproduce an analytically known value, it cannot evaluate a model either. |
| 9 | **R5** `DATA_PROVENANCE` | More expensive, and the most decisive of the data checks. |
| 10 | **R6** `DETERMINISM` | Requires two full runs, so it comes after the checks that would have invalidated them. |
| 11 | **R7** `REMOTE_PARITY` | Asserts region and image pinning; meaningless until the local path is known good. |
| 12 | **R8** `REPORT` | Reports on the eleven above, so it is necessarily last. |

The governing principle is cheapest-and-most-decisive-first: order by how much
downstream work a failure invalidates, divided by what the check costs to run.
Numerical order optimises for nothing.

## The checks

**R9 `LICENCE_GATE`** — every source and every checkpoint in the manifest
appears on the signed allowlist as ALLOWED. Zero EVAL-ONLY sources in any
training split. `NOTICE.md` regenerated and current. Fails the build.

R9 **is not satisfiable by editing `docs/DATA_POLICY.md` or
`docs/allowlist.yaml`.** If a source is not on the allowlist, either remove it
from the manifest or escalate. Regenerate `NOTICE.md` with `mlkit notice`.

**R10 `FABRICATED_DEFAULTS`** — no measured quantity takes a plausible numeric
default that then satisfies the gate consuming it. `max_smd = max(smds.values())
if smds else 0.0` reads as defensive programming right up until you notice that
0.0 is *perfect covariate balance* and that the empty dict is the branch which
actually runs. Walks the trees declared in `[source] trees` with `ast`; imports
nothing, so it sees code no binding exposes. Findings land in
`reports/fabricated_defaults.md`.

**R11 `FABRICATED_TARGETS`** — no value drawn from a random number generator
reaches a data record that is stamped with a provenance field claiming the
record was **observed**.

The stamp is the defect, not the draw. The same code stamped
`label_origin="synthetic"` is a fixture, which is a legitimate and necessary
thing to build, and R11 never reports it. What R11 reports is the specific
field and value that make a record a fabrication rather than an honestly
labelled simulation.

**R11 reads no declaration.** Unlike R10 it does not consult `[source] trees`,
because that list is exactly the surface an author controls: resilient-choco
PR #160 shipped five such files under `scripts/`, outside the declared trees and
outside that repo's own generated-paths guard, past 51 green tests. R11 walks
every `.py` in the repo. It also does not honour R10's synthetic-name excusal —
a file called `make_synthetic_panel.py` that stamps its rows `observed` is
contradicted by its own name, not excused by it.

R11 is **not satisfiable by relabelling a stamp you have not verified.** If the
rows really are observed, the draw feeding them is the defect; fix the data
path. If they are not, say `synthetic` and let R5 count them honestly.
Findings land in `reports/fabricated_targets.md`.

**R12 `SERVED_CONTRACT`** — no repo defines "served" for itself. Four
questions belong to `resilient_mlkit.core.served` and to nothing else: is this
the artifact that was measured, is this the data it was measured on, may this
challenger be promoted, and which arm may be served.

**Why this is a check and not a style note.** Measured 2026-08-29 the fleet had
converged on one definition of *ready* — these checks — and grown three of
*served*, including two files with the same name (`mlops/champion_challenger.py`
in chokepoint and in torrent), different SHAs, and overlapping-but-not-identical
APIs. The divergence was not cosmetic. `torrent/.../champion_challenger.py:128`
maps a zero baseline to a deviation of `0.0`, which clears the tolerance and
**promotes**; `chokepoint/.../champion_challenger.py:209-218` returns `NA` on
the identical condition. Two repos, one situation, opposite verdicts. That is
rule 7's stated failure mode one layer up: three definitions of "served" is the
same as none.

**The exemption is an import, not a name.** A file that imports the contract —
or imports a module in the same repo that does — is silent whatever shapes it
carries. Adopting is what clears R12; renaming is not, and a repo may keep a
thin typed wrapper over `ServedModel` because the wrapper imports it.

**What a green R12 does not claim.** That the serving path is correct. R12 is
an `ast` walk: it sees that a file routes through the contract, never that it
routes through it *correctly*. A file that imports `core.served` and then
ignores the decision it returns is silent here and is a defect; closing that
gap is the adopter's own served-report reproduction. Findings land in
`reports/served_contract.md`.

**R1 `CHECKPOINT_PROVENANCE`** — every checkpoint has a URI, a content hash,
and a licence URL. A checkpoint you cannot hash is a checkpoint you cannot
prove you trained from.

**R2 `OVERFIT_ONE_BATCH`** — loss on a single batch falls by at least 10× over
the trajectory. Failure here is a wiring defect, not a tuning problem.

**R3 `BLOCKED_SPLITS`** — train, val and test share no group. Spatially blocked,
not randomly assigned: neighbouring tiles are not independent samples, and a
random split silently reports memorisation as generalisation.

**R4 `METRIC_KNOWN_ANSWER`** — each metric reproduces an analytically known
value on a constructed case, within a declared tolerance.

**R5 `DATA_PROVENANCE`** — no synthetic, simulated or formula-derived row in
`val` or `test`, under any circumstance. This is the check that catches a target
computed from the model's own inputs, which is the failure mode that produces
beautiful scores and worthless models.

**R6 `DETERMINISM`** — two runs at the same seed produce identical results.

**R7 `REMOTE_PARITY`** — `us-west-2`, an ECR image pinned by digest, and the
same `mlkit` entrypoint locally and remotely. A config pointing at another
region is a defect to fix, not a policy to change.

**R8 `REPORT`** — generates `reports/readiness.md` from the measured results of
this run.

R8 **refuses to write** when the interpreter running mlkit cannot import this
repo's bindings. In August 2026 a python 3.14 with no numpy regenerated this
file in at least four repos, replacing measured PASSes with
`ModuleNotFoundError`. "Environment unmeasurable" is a different fact from
FAIL — a check that could not run says nothing about the repo — so R8 reports
`NA`, leaves the prior report byte for byte, and writes
`reports/readiness.UNMEASURABLE.md` saying why. Run mlkit from this repo's own
environment and the report regenerates as before. Ask first with `mlkit env`.

A missing module that resolves *inside* this repo is this repo's own defect and
still fails. The guard protects measurements from bad interpreters; it does not
protect a repo from itself.

## Passing

`mlkit check --phase readiness` must end with `READINESS: 11/11 PASS`, nothing
FAIL and nothing STALE. STALE means a result was measured at a different git
SHA than the one checked out; it is not a pass, and the remedy is to re-run.
