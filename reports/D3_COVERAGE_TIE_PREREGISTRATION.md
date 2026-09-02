# D3 COVERAGE TIE — pre-registration

**Written before the change it governs.** Commit order is the evidence: this
file lands in its own commit, and no line of `src/` moves until it has.

**Authorization:** A-1 — local CPU only. Nothing is fitted here, no fleet run
is authorised, and no test row is read anywhere. `portfolio/FLEET_VERDICTS.md`
and its `.json` twin are untouched by this work and stand as measured.

**Item:** recursive-loop I2-M1 — close `docs/ESCALATIONS.md` E-M23 residual 2.

## The defect this closes

E-M23 residual 2, OPEN and unassigned on `main` at `6921e9a`:

> Driven here and left open because it is not M-05's scope: with an honest
> committed 0.90, a binding returning `{"nominal": 0.90, "empirical": 0.90,
> "n": 1000000}` PASSes, and nothing ties either figure to a row set. E-M21
> named the general form — "when a verdict is a comparison, every operand needs
> a tie" — and tied one of the three. The row-digest work in round-8 M-06 is
> the shape the remaining two need.

D3's verdict is `abs(empirical - declared) > tol`. E-M21/E-M23 moved the
`nominal` operand out of the subject's dict and into committed state, and
clamped `tol` to mlkit's. `empirical` and `n` were left exactly where tick 13
found them: scalars the subject asserts, over a row set nobody names, that no
reader can re-derive. A binding that returns the level it was asked to hit,
over a million rows it never had, is indistinguishable from one that measured.

## The rule this installs

> **A coverage verdict is taken on figures mlkit re-derived, or it is not
> taken.** `empirical` and `n` must arrive with the operands they were computed
> from and a `row_set_digest` naming the rows those operands claim to be.
> Evidence that does not carry them yields a NAMED refusal that says which
> operand is missing — never a silent PASS, and never a silent FAIL.

## The contract, fixed in advance

**R-D3T1 — the evidence shape.** The `coverage` binding's dict carries, beside
`nominal` / `empirical` / `n`:

* `row_set_digest` — `core.served.row_set_digest` over the keys below. mlkit's
  ONE definition of that digest, imported and not reimplemented (rule 7), so
  D3's evidence can be compared to a served comparison's
  `candidate_row_digest` / `reference_row_digest` rather than to nothing.
* exactly one of:
  * `rows` — a sequence of `{"row_id": <json-serialisable>, "covered": <0|1>}`,
    one per held-out row; or
  * `groups` — a sequence of `{"group_id": <json-serialisable>, "n": <int>,
    "covered": <int>}`, one per cell of a partition the subject declares.

  `n` is re-derived as the row count (or `sum(group n)`), `empirical` as
  `covered / n`, and the digest over the `row_id`s (or the `group_id`s).

**R-D3T2 — the four refusals, all named.**

| marker | verdict | fires when |
|---|---|---|
| `COVERAGE_UNTIED` | **NA** | no `rows`/`groups`, or no `row_set_digest`. The message names the missing operand. |
| `COVERAGE_ROWS_MALFORMED` | **FAIL** | the operands are present and not re-derivable: wrong container, missing field, a `covered` that is not an indicator, a non-serialisable key, a repeated key, an empty set, `covered > n`. |
| `COVERAGE_ROW_SET_MISMATCH` | **FAIL** | the reported `row_set_digest` is not a sha256, or is not the digest of the keys handed over. |
| `COVERAGE_SELF_REPORTED` | **FAIL** | the reported `empirical` or `n` is not what those operands re-derive to. The message names the re-derived figure. |

NA for the missing operand and FAIL for the contradicted one is deliberate and
is E-M21's own distinction: "we did not supply this" is a gap an adopter fills,
"we supplied something else" is a claim that was checked and lost.

**R-D3T3 — where it sits in D3, and what that is chosen against.** The tie runs
AFTER the non-finite guards and after the whole committed-`nominal` block
(`NOMINAL_UNCOMMITTED`, `NOMINAL_UNDECLARED`, the type/range refusals,
`NOMINAL_SELF_DECLARED`), and BEFORE the `MIN_COVERAGE_N` NA and the coverage
verdict. Both halves are load-bearing:

* a substituted pass mark is a FAIL and must not be downgraded to an
  untied-evidence NA — the same reason `NOMINAL_SELF_DECLARED` already fires
  before the small-holdout NA;
* the small-holdout NA and the coverage verdict are then taken on the
  **re-derived** `n` and `empirical`, so no verdict in this check rests on a
  figure that was merely asserted.

**R-D3T4 — the agreement allowance.** `n` must match exactly. `empirical` is
compared to the re-derived quotient within `1e-12`, which is
`NOMINAL_AGREEMENT_EPS`'s reasoning and not a second tolerance: a subject may
compute the mean one way and mlkit divides the other, and that is one number
written twice. Anything a person could mean by "a different coverage" is many
orders of magnitude above it — the incident that motivated D3's first tie
missed by 1.2e-2.

**R-D3T5 — no threshold, range, holdout or existing test is touched.**
`MAX_COVERAGE_TOL`, `MIN_COVERAGE_N`, `NOMINAL_AGREEMENT_EPS` and every other
check's semantics stand as committed. No test that exists on `main` loses an
assertion. Fixtures that assert a verdict D3 can only reach past the tie gain a
conforming tie and keep their assertion verbatim, which is exactly what E-M21
did to these same fixtures when the level became a declaration.

## What this does NOT close, declared before it is measured

* The group form ties `empirical` and `n` to a **declared partition**, not to
  individual rows. A subject that fabricates internally consistent group counts
  is refused by nothing here.
* The row set itself is still the subject's. The digest names it; it does not
  prove the rows are the holdout. Tying `[coverage]` to a **committed** digest
  — the shape `nominal` now has — is the next tie, and it is left open rather
  than half-built.
* Adopters that do not carry the operands move D3 PASS → NA
  `COVERAGE_UNTIED` on unchanged code. That is a verdict change on unchanged
  repo code, in the refusing direction, and it is E-M21 residual 1's bargain
  again.

## The controls, and what each must show

**CONTROL A — must fire.**

* A1: the escalation's own payload `{"nominal": 0.90, "empirical": 0.90,
  "n": 1000000}` against an honest committed `nominal = 0.90` — PASS on `main`,
  and on this branch NA `COVERAGE_UNTIED` whose message names `row_set_digest`
  and `rows`.
* A2: a payload with a real, tied row set, persisted as a JSON artifact, whose
  `empirical` alone is stomped — FAIL `COVERAGE_SELF_REPORTED`, and the message
  names the figure re-derived from the persisted rows.
* A3: one stomped `n`; A4: one stomped `row_set_digest`; A5: a `covered` that
  is not an indicator; A6: a repeated `row_id`; A7: both `rows` and `groups`.

**CONTROL B — must stay silent.**

* B1: a properly tied artifact built from real fixture rows PASSes at the same
  nominal, with the same tolerance, and its evidence carries the digest.
* B2: the full suite is green at the baseline count (`909 passed / 3 skipped`,
  the 3 gated on a `resilient-torrent` sibling checkout) plus exactly the new
  tests, with collected node ids diffed rather than counted.
* B3: a before/after dual-interpreter sweep over every check in the package
  with `resilient_mlkit.__file__` asserted on both sides — no other check's
  verdict, reason or evidence moves.

**CONTROL C — check-not-dead.** Each refusal is re-driven with the branch's own
guard mutated one at a time; every mutation must be caught, and `decision.py`
and `coverage_evidence.py` restored with sha256 asserted byte-identical after
each.

*Failure of any CONTROL A leg, or any movement in CONTROL B, refutes this
change. It is recorded here before the measurement so that it cannot be
renegotiated afterwards.*
