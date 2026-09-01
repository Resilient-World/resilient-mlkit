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

## D6 `RESAMPLING_UNIT` — the unit resampled vs the holdout policy

An interval, or a promotion decision that rests on one, must declare the unit
its resampling procedure drew. mlkit refuses a declaration that contradicts the
holdout policy the same repo declares.

The rule, in one sentence: *a resampling procedure draws units and treats them
as exchangeable; a holdout policy that keeps a block whole has asserted the
block's rows are NOT exchangeable — that is the entire reason it refuses to
split them. So a unit that stays inside the deciding arm and splits one of the
policy's blocks has manufactured independent replicates out of exactly the rows
the policy refused to separate.*

What this is worth, measured: round-8 adjudication rebuilt one repo's val
predictions and re-did its interval under three units. On **one identical set
of 1,365 rows**, resampling ROWS gave `[+16.016, +29.646]` — clears zero — and
resampling the CROP-YEAR blocks the split itself defines gave
`[-1.289, +41.704]` — does not. No gate had been edited by anyone; the run's
own preregistration fixed the row bootstrap in advance and the run honoured it
exactly. Two repos in the fleet held two conventions and nothing required
either.

Declare it as a binding:

```
[bindings]
resampling_declaration = "mlkit_bindings:resampling_declaration"
```

returning `{procedure, draws, policy, blocking_unit, unit, arm, assignment}`,
where `assignment` is one mapping per panel row naming `row_key`, `arm`,
`block_key` and `unit_key`. Everything else — the counts, the digests, the
relation, the verdict — mlkit derives from that assignment; a binding that
reported its own unit count would be reporting the operand of its own verdict.

D6 then asks a second question the declaration cannot answer about itself: it
ties the declared blocks to the `splits` binding R3 already reads. A binding
that sets `block_key = row_key` describes a policy with no blocks at all, which
is self-consistent and silent, and is caught only against that second
declaration. An absent or unreadable `splits` is NA, never PASS.

A unit whose keys appear in more than one arm — a corridor under a time-blocked
split, say — is **recorded, not refused**: the split does not partition that
axis, so the policy's blocks say nothing about it. The declaration reports the
relation and puts the blocks the procedure did *not* resample in the record
beside the units it did.

## Passing

`mlkit check --phase decision` reports a placebo estimate with its confidence
interval, empirical interval coverage against nominal, and the dependence unit
every interval was resampled over. D1, D4 and D5 report ESCALATED until the
signatory writes them.

**Failing D2 means no GPU budget.**
