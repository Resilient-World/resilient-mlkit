# RUN_ECONOMICS.md — Phase 5

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

The last gate before scaling. All runs go through SageMaker with managed spot
enabled, in `us-west-2`, logged to MLflow, and carrying the
`resilient:model`, `resilient:run-id` and `resilient:phase` cost allocation
tags.

Every probe is capped at the credit and wall-clock limits declared per repo.
**Exceeding a cap is a FAIL, not a tradeoff.**

## E1 `SCALING_PROBE` — the highest-leverage check here

Runs at 1%, 10% and 25% of the data, as Processing Jobs or short Training Jobs,
all logged to MLflow.

> **HARD STOP.** If the curve is flat across the top step of the ladder, halt
> immediately and say so. The full run buys nothing: the bottleneck is labels,
> not compute.
>
> This is the check most worth running first, because the money it saves is the
> money you were about to spend.

`mlkit` treats a **relative** gain of ≤1% across the top two rungs as flat —
`(top − second) / |second|`, not an absolute band in the metric's own units.
Metrics are oriented larger-is-better by the repo's own binding before they
reach `mlkit`.

### Declaring a ladder

`{0.01, 0.10, 0.25}` is the default, and with no declaration the verdict is
taken between 10% and 25% exactly as before. Declare your own when your probe
runs different fractions:

```toml
[scaling]
fractions = [0.01, 0.10, 0.25]
```

A repo whose probe never ran a 1% rung used to **FAIL E1 on contract** with a
curve that was comfortably not flat, which tells nobody anything about whether
the run buys something. Two rules keep a declared ladder honest, and both refuse
the **declaration**, before any curve is read:

* the top rung may not sit **below 0.25**. E1 asks whether the run you would
  actually buy is worth buying, and a ladder topping out at 5% never asks it.
* the top two rungs may be **no further apart than `mlkit`'s own 2.5×**.
  Widening that step is the one way a declared ladder could make a flat curve
  look steep — more data always buys something if you ask for enough more.

At least three rungs, strictly increasing, each in `(0, 1]`, read from the blob
at HEAD; an uncommitted ladder is NA, not a silent default. **The 1% flatness
threshold is `mlkit`'s and is not declarable** — a subject that sets its own
pass mark sets no pass mark.

## E2 `HPARAM_SANITY`

An LR range test and a batch-size/throughput curve via SageMaker AMT, logged to
MLflow with the winning config registered. A sweep that was not logged is not
evidence.

## E3 `EFFICIENCY_FLOOR`

GPU utilisation ≥ 80%, with an attached profiler trace, and the dataloader
demonstrated not to be the bottleneck.

> If utilisation is below the floor because the dataloader is starving the GPU,
> the remedy is **FSx for Lustre or Mountpoint for S3** — propose it in
> `docs/ESCALATIONS.md`. **Do not request a larger instance type.** Buying
> compute to solve an I/O problem is the most common way a credit allocation
> evaporates, and it makes the utilisation number worse, not better.

A utilisation figure without an attached trace is a claim, and `mlkit` fails it
as one.

## E4 `CREDIT_BUDGET_AND_KILL` — human sign-off

Per-repo credit allocation declared and tagged, an AWS Budgets alarm wired, the
managed-spot decision recorded against R7 resume, and automatic termination if
validation has not improved by X after N steps. **Denominated in credits, with
the dollar equivalent stated** — credits create a powerful illusion of free
compute, and the allocation is what makes the tradeoff visible again.

Billing action. **Non-delegable.**

## E5 `RUN_HYPOTHESIS` — human sign-off

Each planned run states what it will tell you that you do not already know, and
what result would change your mind. Runs are ordered by information per dollar.
**Human-written by design.**

## Passing

`mlkit check --phase economics` reports a scaling curve at 1/10/25%, an LR
range-test result, a batch-size vs throughput table, and measured GPU
utilisation with an attached profiler trace path.
