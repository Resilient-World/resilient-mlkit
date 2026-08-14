# SELECTION.md — Phase 2, selection

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

The register itself lives in **`docs/selection.yaml`**, which is machine-read by
`mlkit`. This document is the protocol; that file is the evidence. They are
separate on purpose — parsing prose for structured determinations is how a gate
ends up passing on a well-written paragraph that decides nothing.

## S1 `TASK_SPEC`

Pin the task down before comparing anything against it. Required fields:

- `objective` — what commercial decision this model informs
- `unit_of_analysis` — what one row is
- `label_definition` — what the target means, in observable terms
- `holdout` — the spatially blocked holdout, defined precisely enough to rebuild
- `primary_metric` — the one metric that decides
- `decision_threshold` — the value at which the answer changes

A task spec without a decision threshold is a description, not a specification.

## S2 `CANDIDATE_REGISTER`

Three mandatory tiers. The register is incomplete without all of them:

| Tier | What it is | Minimum |
|---|---|---|
| **0** | Trivial or heuristic baseline — climatology, persistence, majority class | 1 |
| **1** | Domain-specific baseline — the thing a competent practitioner would build | 1 |
| **2** | Foundation model | 2 |

Every candidate carries a **licence URL** and a **retrieval date**, verified
from the checkpoint's own licence file — not the paper, not the README, not a
blog post.

**The tier rule.** No Tier-2 foundation model enters a training config until it
has beaten the Tier-1 domain-specific baseline on this repo's own spatially
blocked holdout. A register without a Tier-1 baseline is incomplete regardless
of how strong the Tier-2 entries look. Four foundation-model backbones wired up
is not the same as four chosen.

## S3 `EVIDENCE_RESOLVABLE`

Every URL in the register returns 200. Every checkpoint has been downloaded and
loaded, with state-dict key counts printed by `mlkit`.

Delete any candidate whose evidence does not resolve, and say which and why.
**Do not substitute a different URL to make a citation resolve** — that
converts a broken citation into a false one.

## S4 `DATA_AND_LICENCE`

Per source: URI, licence URL, retrieval date, ALLOWED/BLOCKED/EVAL-ONLY verdict,
attribution obligation, coverage vs AOI, native resolution, revisit, latency,
GB, `us-west-2` availability, staging cost, and the observed-label counts
measured at T4. Per candidate checkpoint: the same licence treatment.

Where a source is EVAL-ONLY, **say so explicitly rather than omitting it**. An
omitted source reads as an absent one.

## S5 `DECISION_RECORD`

**Human sign-off. Non-delegable.** An agent may not write S5, and `mlkit`
reports it ESCALATED unconditionally. The same applies to every allowlist
addition: the agent proposes in `docs/ESCALATIONS.md`, the signatory signs.

## Passing

`mlkit check --phase selection` reads `S3: N/N RESOLVED` and
`S4: N/N LICENCE-VERDICTED`. List every UNKNOWN and every proposed allowlist
addition separately at the end of the run.
