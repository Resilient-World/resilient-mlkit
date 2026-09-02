"""Phase 4 — DECISION VALIDITY.

D2 is the strongest check in the package. Run the full pipeline on a
pre-intervention period, or with treatment assignment permuted, and the
avoided-loss estimate must come back indistinguishable from zero. If it does
not, the estimator is capturing something other than the intervention, and no
amount of tuning fixes that -- so a D2 failure is a hard stop for the repo
rather than a finding to work around. It costs cents on a Processing Job and
can invalidate a model before a single GPU-hour is bought.
"""

from __future__ import annotations

import math

from ..core import artifact, coverage_evidence
from ..core.repo import BindingError, Repo
from ..core.result import ALLOW_DIRTY_KEY, CheckResult, CredentialRequired
from . import RunContext, check

PHASE = "decision"

#: Loosest coverage tolerance D3 accepts, whatever a binding asks for.
MAX_COVERAGE_TOL = 0.05

#: Below this, the binomial standard error alone exceeds the tolerance, so the
#: measurement cannot support the verdict either way.
MIN_COVERAGE_N = 100

#: The ``.mlkit/repo.toml`` section carrying D3's nominal coverage level as
#: DATA -- ``[coverage]`` / ``nominal = 0.90`` -- beside the ``coverage``
#: binding it adjudicates. See :func:`d3_uncertainty_coverage`.
COVERAGE_SECTION = "coverage"

#: Where that section lives, as a repo-relative path for ``core.artifact``.
#: D3 reads it FROM COMMITTED STATE. ``repo.config()`` would read the working
#: tree, and the level is a pass mark rather than a scope declaration: see
#: :func:`d3_uncertainty_coverage` and docs/ESCALATIONS.md E-M12/E-M23.
REPO_CONFIG_RELPATH = ".mlkit/repo.toml"

#: How far the coverage binding's self-reported ``nominal`` may sit from the
#: declared level and still be the same number.
#:
#: This is a FLOAT REPRESENTATION allowance and emphatically not a tolerance.
#: A repo may compute its level as ``1 - alpha`` and hand back something whose
#: last bits differ from the literal in its config; that is one number written
#: two ways. Anything a person could mean by "a different level" is many orders
#: of magnitude above this -- the incident that motivated the check missed by
#: 1.2e-2. Widening it would turn the tie back into a second tolerance, which
#: is the thing being removed.
NOMINAL_AGREEMENT_EPS = 1e-12


@check("D1", PHASE, "COUNTERFACTUAL_SPEC — human sign-off", human_only=True)
def d1_counterfactual_spec(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D1", PHASE,
        "D1 specifies what the counterfactual means commercially and is reserved "
        "to the signatory; the agent may not write it",
    )


@check("D2", PHASE, "PLACEBO_TEST — estimate indistinguishable from zero")
def d2_placebo_test(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("placebo_test")
    except BindingError as exc:
        return CheckResult.na(
            "D2", PHASE,
            f"{exc}; the placebo run is a SageMaker Processing Job and the training "
            "plane has not been bootstrapped",
        )
    try:
        out = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("D2", PHASE, f"placebo_test raised {type(exc).__name__}: {exc}")

    for field in ("estimate", "ci_low", "ci_high"):
        if field not in out:
            return CheckResult.failed("D2", PHASE, f"placebo_test did not report {field}")

    estimate = float(out["estimate"])
    lo, hi = float(out["ci_low"]), float(out["ci_high"])
    evidence = {"estimate": estimate, "ci_low": lo, "ci_high": hi, "run": out.get("run_id", "")}

    # Distinguishable from zero == the interval excludes zero.
    if lo > 0 or hi < 0:
        return CheckResult.failed(
            "D2", PHASE,
            f"placebo estimate {estimate:.6g} with CI [{lo:.6g}, {hi:.6g}] excludes zero; "
            "the estimator is capturing something other than the intervention. "
            "HARD STOP — do not tune, do not scale, do not schedule a training run.",
            {**evidence, "halt": True},
        )

    # Everything below this line reasons about an interval that CONTAINS zero,
    # and a non-finite figure reaches here by failing to be anything at all.
    # `float()` accepts NaN and the infinities, including as the strings
    # "nan"/"inf", and every comparison a NaN takes part in is False -- so
    # `lo > 0`, `hi < 0` and, further down, `half_width >= reference` are all
    # False together, and a placebo that measured nothing walks past the hard
    # stop, past the power bar, and out as a PASS. NaN is what a pandas or
    # numpy estimator returns when a groupby or a reindex misses a stratum.
    # Same defect class as the R5 row-count guard, and refused the same way:
    # by name, before the value is reasoned about.
    non_finite = [
        name
        for name, value in (("estimate", estimate), ("ci_low", lo), ("ci_high", hi))
        if not math.isfinite(value)
    ]
    if non_finite:
        return CheckResult.failed(
            "D2", PHASE,
            "placebo_test reported a non-finite " + ", ".join(non_finite)
            + "; a placebo that did not resolve to a finite estimate and interval "
            "has not tested anything, and must not be read as a null result",
            evidence,
        )

    # Containing zero is necessary but nowhere near sufficient. An interval
    # wide enough to contain everything contains zero too, and would sail
    # through the package's self-described strongest check while proving
    # nothing. Passing requires enough power to have detected the effect the
    # real run claims -- otherwise this is a null result and a no-power result
    # wearing the same face.
    reference = out.get("reference_effect")
    if reference is None:
        return CheckResult.na(
            "D2", PHASE,
            "placebo interval contains zero, but no reference_effect was reported, "
            "so a true null cannot be told apart from a test with no power. "
            "Report the real-run effect size this placebo must be able to detect.",
            evidence,
        )
    reference = abs(float(reference))
    half_width = (hi - lo) / 2.0
    evidence.update({"reference_effect": reference, "ci_half_width": half_width})
    # The power bar is `half_width >= reference`. A NaN reference makes that
    # False for every interval, so the requirement would be satisfied by a
    # figure that does not exist -- the one thing this branch was added to stop.
    if not math.isfinite(reference):
        return CheckResult.failed(
            "D2", PHASE,
            "reference_effect is not finite; the power requirement cannot be "
            "satisfied by an effect size that was never measured",
            evidence,
        )
    if reference == 0 or half_width >= reference:
        return CheckResult.failed(
            "D2", PHASE,
            f"placebo CI half-width {half_width:.6g} is not smaller than the reference "
            f"effect {reference:.6g}; the test could not have detected the real effect, "
            "so containing zero is uninformative",
            evidence,
        )
    return CheckResult.passed("D2", PHASE, evidence)


@check("D3", PHASE, "UNCERTAINTY_COVERAGE — empirical coverage matches the DECLARED nominal")
def d3_uncertainty_coverage(repo: Repo, ctx: RunContext) -> CheckResult:
    """Empirical coverage against the level this repo DECLARED it promises.

    D3's verdict is ``abs(empirical - nominal) > tol``, and for most of this
    package's life BOTH operands of that subtraction arrived in the single dict
    the subject had just handed the check. Only ``tol`` was mlkit's. Tick 13
    measured what that buys, independently in two repos in one tick:

    * arabica set ``nominal`` equal to the empirical ``0.8879423328964613`` it
      had just measured, in both ``coverage_for_d3`` and ``levels[alpha=0.1]``.
      D3 returned PASS on evidence reading ``nominal == empirical``, erasing a
      shortfall of ``-0.012057667103538727`` the repo had truthfully disclosed
      for its SERVED model of record. The second leg of that same PR re-derived
      the coverage from the rows, agreed to 1e-12, and raised nothing -- it was
      checking the operand nobody had touched.
    * surge wrote a genuine ``(nominal, qhat, empirical)`` triple from a
      DIFFERENT calibrated level into the level whose ``alpha`` still said 0.1.
      Every individual number was real; only the pairing was a lie, and nothing
      compared the pairing.

    Pinning ``tol`` pinned nothing about ``nominal``, and pinning ``alpha``
    pinned nothing either. A gate is only as tied as its loosest term.

    So the level is DATA now, declared in ``.mlkit/repo.toml`` beside the
    binding it judges::

        [coverage]
        nominal = 0.90   # the level these prediction intervals promise

    which is the same reason ``core.served.ServeArms`` keeps the serve-arm
    policy as data: mlkit cannot know which level a product promises, and a
    check that asked the subject would be asking the party with the motive.
    The binding still reports its own ``nominal``, and that report is now
    something this check ADJUDICATES rather than the standard it judges by.

    Three verdicts follow, and they are deliberately different instructions:

    * the reported level disagrees with the declared one -> FAIL
      ``NOMINAL_SELF_DECLARED``. The subject substituted its own pass mark.
    * no declaration exists -> NA ``NOMINAL_UNDECLARED``. There is no second
      operand, and falling back to the subject's claim would be the old
      behaviour wearing a conditional.
    * they agree -> the ordinary coverage verdict, measured against the
      DECLARED level.

    And the declaration is read FROM COMMITTED STATE, through
    ``core.artifact.load``. E-M21 shipped this level read with
    ``repo.config()`` -- the working tree -- while asserting that its whole
    protection was that the level is "committed, reviewable and static". An
    uncommitted one-line edit put the tick-13 exploit straight back (E-M23), so
    the level now comes from ``HEAD:.mlkit/repo.toml`` or the row is NA
    ``NOMINAL_UNCOMMITTED``; ``--allow-dirty`` reads the working tree for
    diagnosis and structurally cannot reach a PASS.

    **And the other two operands are recounted, not accepted** (E-M23 residual
    2). Tying ``nominal`` left ``empirical`` and ``n`` where tick 13 found
    them: with an honest committed ``0.90``, a binding returning
    ``{"nominal": 0.90, "empirical": 0.90, "n": 1000000}`` PASSed, over a row
    set nobody named. The evidence now carries the operands those two figures
    were computed from, and ``core.coverage_evidence`` recounts them::

        [coverage]
        nominal = 0.90                     # committed, as above

        {"nominal": 0.90, "empirical": 0.89, "n": 5000,
         "row_set_digest": "<core.served.row_set_digest over the keys below>",
         "rows":   [{"row_id": "...", "covered": True}, ...]}   # or
         "groups": [{"group_id": "...", "n": 500, "covered": 447}, ...]}

    ``n`` is the row count (or the sum of the group counts), ``empirical`` is
    ``covered / n``, and both are re-derived here; the digest is
    ``core.served``'s one spelling of that name, so a coverage claim and a
    challenger comparison can be held against each other. Four named outcomes,
    and the NA/FAIL split is E-M21's own distinction between a gap an adopter
    fills and a claim that was checked and lost:

    * no operands, or no digest -> NA ``COVERAGE_UNTIED``, naming what is
      missing.
    * operands that cannot be recounted -> FAIL ``COVERAGE_ROWS_MALFORMED``.
    * a digest that is not the digest of the keys handed over -> FAIL
      ``COVERAGE_ROW_SET_MISMATCH``.
    * a reported ``empirical`` or ``n`` that is not what the operands
      re-derive to -> FAIL ``COVERAGE_SELF_REPORTED``, naming the re-derived
      figure.

    What this does NOT establish is written down in
    ``core.coverage_evidence``'s own docstring and in
    ``reports/D3_COVERAGE_TIE_PREREGISTRATION.md``: the row set is still the
    subject's, and the group form ties the figures to a declared partition
    rather than to individual rows.
    """
    try:
        fn = repo.resolve("coverage")
    except BindingError as exc:
        return CheckResult.na(
            "D3", PHASE,
            f"{exc}; coverage is measured on the blocked holdout via a Processing Job "
            "and the training plane has not been bootstrapped",
        )
    try:
        out = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("D3", PHASE, f"coverage raised {type(exc).__name__}: {exc}")

    for field in ("nominal", "empirical", "n"):
        if field not in out:
            return CheckResult.failed("D3", PHASE, f"coverage did not report {field}")

    nominal, empirical, n = float(out["nominal"]), float(out["empirical"]), int(out["n"])
    # mlkit owns this tolerance. A binding may ask for something stricter but
    # never looser -- a subject that sets its own pass mark sets no pass mark.
    declared_tol = float(out.get("tol", MAX_COVERAGE_TOL))
    # `min(nan, x)` returns nan in Python, so a declared tolerance of NaN walks
    # straight through the clamp above and makes `abs(empirical - nominal) > tol`
    # False for every input -- the loosest tolerance there is, wearing the
    # clamp's clothes. Refused before it is clamped, not after.
    if not math.isfinite(declared_tol):
        return CheckResult.failed(
            "D3", PHASE,
            "coverage declared a non-finite tol; a tolerance that is not a number "
            "cannot be clamped and would accept any coverage at all",
            {"nominal": nominal, "empirical": empirical, "n": n, "tol": declared_tol},
        )
    tol = min(declared_tol, MAX_COVERAGE_TOL)
    evidence = {"nominal": nominal, "empirical": empirical, "n": n, "tol": tol}

    # Same NaN-comparison defect the D2 guard above refuses: a non-finite
    # coverage figure makes the tolerance comparison False and returns PASS.
    non_finite = [
        name for name, value in (("nominal", nominal), ("empirical", empirical))
        if not math.isfinite(value)
    ]
    if non_finite:
        return CheckResult.failed(
            "D3", PHASE,
            "coverage reported a non-finite " + ", ".join(non_finite)
            + "; intervals whose coverage did not resolve to a number have not been "
            "measured, and must not be read as covering",
            evidence,
        )

    # -- the other operand ------------------------------------------------
    #
    # Everything above this point reasons about figures the SUBJECT reported,
    # and refuses the ones that did not resolve to a number. Those refusals
    # come first on purpose: a NaN disagrees with every declared level, so
    # folding them into the disagreement branch below would replace "this
    # coverage was never measured" with "this level was substituted" and make
    # the E-M09/E-M10 non-finite guards unreachable through D3.
    #
    # Below this point the declared level enters, and the subject's `nominal`
    # stops being the standard.
    # ... and it enters FROM COMMITTED STATE, through `core.artifact`.
    #
    # `repo.config()` reads the working tree. That is right for the things it
    # was already asked for -- which binding to import, which trees to walk,
    # which region is declared -- because those say WHAT TO LOOK AT and mlkit
    # is about to look at the working tree anyway. The nominal level is not
    # that. It is the PASS MARK the verdict is measured against, which is the
    # role `docs/selection.yaml` plays for S1-S4, and E-M12 is what reading
    # that role off the working tree bought: a verdict quoting bytes that are
    # in nobody's git history, unfetchable by the reader it is quoted to.
    #
    # Driven at `a48c975`, before this read moved: `[coverage] nominal = 0.90`
    # committed, an UNCOMMITTED one-line edit to 0.8879423328964613, and a
    # binding reporting that same figure as both its nominal and its empirical
    # -> PASS, evidence `declared_nominal: 0.8879423328964613`, no marker, and
    # `git status` showing ` M .mlkit/repo.toml` that no check read. The
    # tick-13 exploit, restored by moving it one file across. A binding writing
    # `.mlkit/repo.toml` from its own module body did the same without leaving
    # the edit for a person to find in a diff they had reviewed.
    ref = artifact.load(repo, REPO_CONFIG_RELPATH, allow_dirty=ctx.allow_dirty)
    if ref.error:
        return CheckResult.na(
            "D3", PHASE,
            f"NOMINAL_UNCOMMITTED: the declared level could not be read from "
            f"committed state -- {ref.error}. The level these intervals promise is "
            "the standard D3 measures against, so it is read from the blob at HEAD "
            "and not from the working tree; otherwise the standard is whatever the "
            "file said at the instant the check looked, which is what the binding's "
            "own `nominal` already was",
            evidence,
        )
    # One assignment rather than one per exit, so the marker cannot be dropped
    # on three paths out of nine. A PASS carrying it is refused by
    # `CheckResult.__post_init__`; every later result here is built from this
    # dict, so every later result inherits it.
    if ref.allow_dirty_read:
        evidence = {**evidence, ALLOW_DIRTY_KEY: True}
    document = ref.document if isinstance(ref.document, dict) else {}
    section = document.get(COVERAGE_SECTION)
    raw = section.get("nominal") if isinstance(section, dict) else None
    if raw is None:
        return CheckResult.na(
            "D3", PHASE,
            f"NOMINAL_UNDECLARED: no `nominal` under [{COVERAGE_SECTION}] in "
            ".mlkit/repo.toml, so the only nominal level available is the one the "
            "coverage binding reported about itself -- and D3's verdict is a "
            "comparison whose other operand would then come from the same dict. "
            "Declare the level these intervals promise, e.g. "
            f"`[{COVERAGE_SECTION}]` / `nominal = 0.90`. Reading the subject's "
            "claim as the standard is what docs/ESCALATIONS.md E-M21 records "
            "being exploited in two repos in one tick.",
            evidence,
        )
    # `bool` is an `int` in Python, so `nominal = true` would reach `float()`
    # as a perfectly valid 1.0 -- a 100% promise nobody wrote. Refused on type,
    # before anything is read out of it, for the same reason `float("0.90")`
    # would have accepted a string level without anyone noticing.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return CheckResult.failed(
            "D3", PHASE,
            f"the declared nominal coverage {raw!r} is a {type(raw).__name__}, not a "
            f"number; [{COVERAGE_SECTION}] nominal must be the probability these "
            "intervals promise, written as a number",
            {**evidence, "declared_nominal": raw},
        )
    declared = float(raw)
    if not math.isfinite(declared) or not 0.0 < declared <= 1.0:
        return CheckResult.failed(
            "D3", PHASE,
            f"the declared nominal coverage {declared!r} is not a coverage level; "
            "declare a probability in (0, 1] -- 0.90 for 90% intervals, not 90. "
            "A level outside that range makes every possible coverage miss it, so "
            "the repo would fail D3 forever with a message about its intervals "
            "rather than about its declaration",
            {**evidence, "declared_nominal": declared},
        )

    evidence["declared_nominal"] = declared
    evidence["reported_nominal"] = nominal
    # `nominal` in the evidence is the level the verdict was taken against, so
    # that an artifact quoting it quotes the standard rather than the claim.
    evidence["nominal"] = declared

    # This fires BEFORE the small-holdout NA below. "We could not measure this"
    # reads as a gap to fill, and a substituted level is not a gap -- it does
    # not become less true on fewer rows, and reporting NA would hide it.
    gap = abs(nominal - declared)
    if gap > NOMINAL_AGREEMENT_EPS:
        return CheckResult.failed(
            "D3", PHASE,
            f"NOMINAL_SELF_DECLARED: the coverage binding reported a nominal level "
            f"of {nominal!r} against the {declared!r} declared under "
            f"[{COVERAGE_SECTION}] in .mlkit/repo.toml (differ by {gap:.6g}). The "
            "level a set of intervals promises is not the subject's to restate at "
            "measurement time: setting it equal to the empirical coverage returns "
            "PASS on any coverage at all, which is how a disclosed shortfall was "
            "erased for a served model of record (E-M21). Either the declaration "
            "is stale or these are not the intervals it describes; both need a "
            "person, not a tolerance",
            evidence,
        )

    # -- the third and fourth operands ------------------------------------
    #
    # E-M21 named the general form -- "when a verdict is a comparison, every
    # operand needs a tie" -- and tied one of the three. `empirical` and `n`
    # arrived, until here, exactly as tick 13 found them: two scalars the
    # subject asserts over a row set nobody names. E-M23 residual 2 recorded
    # what that buys, driven at `a48c975`: against an HONEST committed 0.90, a
    # binding returning `{"nominal": 0.90, "empirical": 0.90, "n": 1000000}`
    # PASSed, and nothing in this check could tell it from a measurement.
    #
    # `core.coverage_evidence.derive` recounts the figures from the operands
    # they were computed on and names the rows in `core.served`'s one spelling
    # of that name. Absent operands are NA and contradicted ones are FAIL,
    # which is E-M21's own distinction between a gap an adopter fills and a
    # claim that was checked and lost.
    #
    # Placement is deliberate on both sides. It runs AFTER the whole committed-
    # `nominal` block, because a substituted pass mark is a FAIL and must not
    # be downgraded to an untied-evidence NA -- the same reasoning that already
    # puts NOMINAL_SELF_DECLARED before the small-holdout NA. It runs BEFORE
    # the two verdicts below, because those are the verdicts: taking them on
    # `empirical` and `n` as reported, having just established that the rows
    # say something else, would be quoting the figure the subject preferred.
    try:
        derived = coverage_evidence.derive(out)
    except coverage_evidence.CoverageUntied as untied:
        return CheckResult.na(
            "D3", PHASE,
            f"{untied.marker}: {untied.detail}",
            evidence,
        )
    except coverage_evidence.CoverageRefused as refused:
        return CheckResult.failed(
            "D3", PHASE,
            f"{refused.marker}: {refused.detail}",
            evidence,
        )
    evidence[coverage_evidence.DIGEST_KEY] = derived.digest
    evidence["tie_unit"] = derived.unit
    evidence["derived_covered"] = derived.covered
    evidence["derived_n"] = derived.n
    evidence["derived_empirical"] = derived.empirical
    mismatch = coverage_evidence.disagreement(
        derived, reported_empirical=empirical, reported_n=n
    )
    if mismatch is not None:
        return CheckResult.failed(
            "D3", PHASE,
            f"{coverage_evidence.SELF_REPORTED}: {mismatch}",
            evidence,
        )
    # The two verdicts below are taken on the DERIVED figures, not the reported
    # ones. Past the gate above they agree -- exactly for `n`, to within
    # EMPIRICAL_AGREEMENT_EPS for `empirical` -- so mutating this back leaves
    # the suite green; that is a property of agreement and not a licence, and
    # `tests/test_d3_coverage_tie.py` pins the one place they come apart.
    #
    # Unlike `nominal` above, `empirical` in the evidence is NOT overwritten.
    # The declared level is a DIFFERENT SOURCE and rightly displaces the
    # subject's copy. The derived coverage has the same source as the reported
    # one -- the subject's own operands -- so overwriting would buy no
    # independence and would quietly redefine the field E-M21's own control
    # reads as "the shortfall the exploit erased, still disclosed". The
    # recount is reported beside it, under its own name.
    n, empirical = derived.n, derived.empirical

    if n < MIN_COVERAGE_N:
        return CheckResult.na(
            "D3", PHASE,
            f"n={n} is too small to measure coverage to ±{tol:.2f}; "
            f"need at least {MIN_COVERAGE_N} held-out points",
            evidence,
        )

    # `declared`, not `nominal`. Past the gate above the two agree to within
    # NOMINAL_AGREEMENT_EPS, so for any ordinary tolerance this is the same
    # comparison either way -- mutating it back leaves the suite green unless
    # something reaches the one place they come apart. A binding may declare a
    # tolerance STRICTER than mlkit's with no floor, and a `tol` below the
    # representation allowance makes the operand choice observable; the
    # committed declaration is the standard there too.
    if abs(empirical - declared) > tol:
        return CheckResult.failed(
            "D3", PHASE,
            f"empirical coverage {empirical:.3f} vs declared nominal {declared:.3f} "
            f"on n={n} exceeds tolerance {tol:.3f}; the prediction intervals do not "
            "mean what they say",
            evidence,
        )
    return CheckResult.passed("D3", PHASE, evidence)


@check("D4", PHASE, "SENSITIVITY — human sign-off", human_only=True)
def d4_sensitivity(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D4", PHASE, "D4 is reserved to the signatory; the agent may not write it"
    )


@check("D5", PHASE, "EXTERNAL_ANCHOR — human sign-off", human_only=True)
def d5_external_anchor(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D5", PHASE, "D5 is reserved to the signatory; the agent may not write it"
    )
