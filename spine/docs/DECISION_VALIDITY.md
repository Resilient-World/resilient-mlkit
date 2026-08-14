# DECISION_VALIDITY.md — Phase 4

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

This phase asks whether the number the model produces means what the business
thinks it means. It runs **before** any long training run, because everything it
can invalidate costs cents to test and thousands to discover later.

## D1 `COUNTERFACTUAL_SPEC` — human sign-off

What "avoided loss" means for this model, in terms someone could disagree with:
what the counterfactual world is, who bears the loss, over what horizon, and what
would make the claim false. **Non-delegable.** `mlkit` reports D1 ESCALATED
unconditionally.

## D2 `PLACEBO_TEST` — the strongest check in the package

Run the full pipeline on a pre-intervention period, or with treatment assignment
permuted. The avoided-loss estimate must come back **indistinguishable from
zero** — its confidence interval must contain zero.

It runs as a SageMaker Processing Job for cents, logged to MLflow under this
repo's experiment, and it can invalidate a model before a single GPU-hour is
bought.

> **HARD STOP.** If the placebo estimate is distinguishable from zero, halt this
> repo immediately. State it plainly. Do not tune, do not scale, do not schedule
> a training run.
>
> A non-zero placebo means the estimator is capturing something other than the
> intervention. That is not a tuning problem and adjusting the estimator until
> the placebo passes is the precise opposite of what the check is for.

## D3 `UNCERTAINTY_COVERAGE`

Empirical coverage of the prediction intervals on the blocked holdout, against
nominal. A 90% interval that covers 62% of held-out outcomes is not a
conservative 90% interval; it is a wrong one, and downstream pricing built on it
is wrong by the same margin.

Measured on a Processing Job, logged to MLflow.

## D4 `SENSITIVITY` — human sign-off

Which assumptions the estimate is most sensitive to, and how far each can move
before the decision flips. **Non-delegable.**

## D5 `EXTERNAL_ANCHOR` — human sign-off

What independent, external evidence the estimate is anchored against. **Non-
delegable.**

## Passing

`mlkit check --phase decision` reports a placebo estimate with its confidence
interval, and empirical interval coverage against nominal. D1, D4 and D5 report
ESCALATED until the signatory writes them.

**Failing D2 means no GPU budget.**
