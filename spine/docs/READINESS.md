# READINESS.md — Phase 3, correctness

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

Nine checks. `mlkit check --phase readiness` runs them **in the order below,
which is not numerical**. Run them one at a time and commit after each with the
check ID in the message.

## The order, and why it is this order

| # | Check | Why here |
|---|---|---|
| 1 | **R9** `LICENCE_GATE` | Cheapest check in the phase and the most decisive. A licence defect makes every downstream result moot, and it is the one defect class that gets *more* expensive the longer you train. It is also the only check that runs on every commit rather than every loop. Running it first costs seconds and can save the phase. |
| 2 | **R1** `CHECKPOINT_PROVENANCE` | Static. Answers "do we know what these weights are" before anything loads them. |
| 3 | **R2** `OVERFIT_ONE_BATCH` | The cheapest check that can prove the model is wired up at all. A model that cannot overfit one batch has a defect no amount of data will fix. |
| 4 | **R3** `BLOCKED_SPLITS` | Cheap, and if the splits leak, every metric measured after this point is meaningless. |
| 5 | **R4** `METRIC_KNOWN_ANSWER` | Cheap. If the metric cannot reproduce an analytically known value, it cannot evaluate a model either. |
| 6 | **R5** `DATA_PROVENANCE` | More expensive, and the most decisive of the data checks. |
| 7 | **R6** `DETERMINISM` | Requires two full runs, so it comes after the checks that would have invalidated them. |
| 8 | **R7** `REMOTE_PARITY` | Asserts region and image pinning; meaningless until the local path is known good. |
| 9 | **R8** `REPORT` | Reports on the eight above, so it is necessarily last. |

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

## Passing

`mlkit check --phase readiness` must end with `READINESS: 9/9 PASS`, nothing
FAIL and nothing STALE. STALE means a result was measured at a different git
SHA than the one checked out; it is not a pass, and the remedy is to re-run.
