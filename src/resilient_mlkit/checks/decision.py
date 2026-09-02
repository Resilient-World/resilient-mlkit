"""Phase 4 — DECISION VALIDITY.

D2 is the strongest check in the package. Run the full pipeline on a
pre-intervention period, or with treatment assignment permuted, and the
avoided-loss estimate must come back indistinguishable from the value it takes
when there is no signal. If it does not, the estimator is capturing something
other than the intervention, and no amount of tuning fixes that -- so a D2
failure is a hard stop for the repo rather than a finding to work around. It
costs cents on a Processing Job and can invalidate a model before a single
GPU-hour is bought.

"The value it takes when there is no signal" was written as a literal zero for
this package's whole life, and for an avoided-loss estimand that is right. It
is not right for every estimand an adopter may honestly place under the name
``placebo_test``, and round 8 measured what that costs: ``resilient-fray``'s
placebo estimand is SKILL AGAINST THE PERSISTENCE FLOOR, whose no-signal value
is emphatically not zero -- a shuffled-target run is expected to be far WORSE
than the floor, and fray's placebo CI is ``[-71.998, -53.146]``. Binding that
honest surrogate under this name would have tripped a SPURIOUS FLEET-WIDE HARD
STOP, so fray did not bind it, and its D2 read NA at head and at main while the
run's hard stops were the trainer's own in-script constructions. A gate nobody
can bind is not a strict gate; it is an absent one.

So the halt region is DECLARABLE now -- see ``PLACEBO_SECTION`` and
:func:`d2_placebo_test` -- and every path that widens it is paid for:

* the declaration lives in COMMITTED data, not in the dict the subject returns;
* a one-sided or shifted halt region requires a written ``estimand``, so the
  exemption cannot be anonymous;
* the sign of ``reference_effect`` must lie on the INDICTING side, so a repo
  cannot exempt the direction its own product claim lives in;
* the power bar, the non-finite guards and their order are untouched;
* and a repo that declares nothing gets exactly the rule it got before.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..core import artifact, declaration
from ..core.repo import BindingError, Repo
from ..core.result import ALLOW_DIRTY_KEY, CheckResult, CredentialRequired, Status
from ..core.served import ResamplingDeclaration, RowUnit, ServedContractError
from . import RunContext, check
from .readiness import (
    SINGLE_TRACK,
    TRACKS_KEY,
    SplitsUnreadable,
    normalise_tracked_splits,
)

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
#:
#: Defined once in ``core.declaration`` and re-exported under its historical
#: name. Two spellings of the same path is how two checks in one file come to
#: disagree about which file carries the standard.
REPO_CONFIG_RELPATH = declaration.REPO_CONFIG_RELPATH

#: The ``.mlkit/repo.toml`` section carrying D2's HALT REGION as data --
#: ``[placebo]`` / ``estimand``, ``null_value``, ``indicts`` -- beside the
#: ``placebo_test`` binding it adjudicates. Optional: a repo that declares
#: nothing is judged by ``DEFAULT_NULL`` and ``INDICTS_EITHER``, which is the
#: rule D2 carried before the section existed.
PLACEBO_SECTION = "placebo"

#: Which excursions from the declared null indict the estimator.
#:
#: ``either`` is the default and is the two-sided rule: an avoided-loss
#: estimate that comes back confidently POSITIVE on a period where nothing was
#: avoided is broken, and one that comes back confidently NEGATIVE is broken in
#: the same way. Naming the sign of the artefact is not the point.
#:
#: ``above``/``below`` exist for an estimand whose two sides are not
#: symmetric. fray's is the worked case: under "skill against the persistence
#: floor", a placebo that BEATS the floor is leakage and indicts, while a
#: placebo far BELOW it is what no signal looks like. Choosing one costs the
#: repo a written ``estimand`` and a ``reference_effect`` whose sign agrees --
#: see :func:`d2_placebo_test`.
INDICTS_EITHER = "either"
INDICTS_ABOVE = "above"
INDICTS_BELOW = "below"
INDICTS_VALUES = (INDICTS_EITHER, INDICTS_ABOVE, INDICTS_BELOW)

#: The value the estimand takes under no signal, when the repo declares none.
DEFAULT_NULL = 0.0

#: Every key ``[placebo]`` may carry. Anything else is a FAIL naming it.
PLACEBO_KEYS = frozenset({"estimand", "null_value", "indicts"})

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


@dataclass(frozen=True)
class HaltRegion:
    """The rule D2 takes its verdict by: which excursions from which null indict.

    Built either from a repo's committed ``[placebo]`` table or, when there is
    none, from ``DEFAULT_NULL``/``INDICTS_EITHER`` -- which is byte-for-byte the
    rule ``lo > 0 or hi < 0`` that D2 carried before this type existed.
    """

    null: float = DEFAULT_NULL
    indicts: str = INDICTS_EITHER
    estimand: str = ""
    declared: bool = False
    source: str = ""
    allow_dirty: bool = False

    @property
    def halts_above(self) -> bool:
        return self.indicts in (INDICTS_EITHER, INDICTS_ABOVE)

    @property
    def halts_below(self) -> bool:
        return self.indicts in (INDICTS_EITHER, INDICTS_BELOW)

    @property
    def is_default(self) -> bool:
        """True when this region is the one mlkit would have applied anyway.

        ``null == DEFAULT_NULL`` rather than ``not declared``: a repo that
        writes out the default explicitly gets the default's verdict AND the
        default's wording, because the two rules are the same rule.
        """
        return self.null == DEFAULT_NULL and self.indicts == INDICTS_EITHER

    def evidence(self) -> dict[str, object]:
        out: dict[str, object] = {"null_value": self.null, "indicts": self.indicts}
        if self.declared:
            out["placebo_declared_in"] = self.source
            if self.estimand:
                out["estimand"] = self.estimand
        if self.allow_dirty:
            out[ALLOW_DIRTY_KEY] = True
        return out


def read_halt_region(repo: Repo, ctx: RunContext) -> tuple[HaltRegion | None, str, str]:
    """``(region, "", "")``, or ``(None, na_reason, "")``, or ``(None, "", fail_reason)``.

    Three outcomes because they are three different instructions. An
    UNCOMMITTED declaration is an NA: the repo has written a standard whose
    bytes no reader can fetch, which is ``docs/ESCALATIONS.md`` E-M12's shape
    and is fixed by committing it. A MALFORMED declaration is a FAIL: the repo
    has written something mlkit cannot read as a rule at all. And no
    declaration is neither -- it is the default, silently, because that is what
    every repo in the fleet is running under today.
    """
    decl = declaration.read(repo, PLACEBO_SECTION, allow_dirty=ctx.allow_dirty)
    if decl.uncommitted:
        return None, (
            f"PLACEBO_UNDECLARED_AT_HEAD: {decl.detail}. The halt region is the "
            "standard D2 takes its verdict by, so it is read from the blob at HEAD "
            "and not from the working tree; a rule that is in nobody's git history "
            "cannot be fetched by the reader the verdict is quoted to. Commit it, or "
            "pass --allow-dirty for a diagnosis that cannot reach a PASS"
        ), ""
    if not decl.declared:
        return HaltRegion(), "", ""

    shape = declaration.table_and_keys(decl, PLACEBO_KEYS)
    if shape:
        return None, "", f"PLACEBO_MALFORMED: {shape}"

    table = dict(decl.value)
    estimand = table.get("estimand", "")
    if not isinstance(estimand, str):
        return None, "", (
            f"PLACEBO_MALFORMED: [{PLACEBO_SECTION}] estimand is a "
            f"{type(estimand).__name__}, not a string; it is prose naming what "
            "placebo_test estimates"
        )
    estimand = estimand.strip()

    indicts = table.get("indicts", INDICTS_EITHER)
    if indicts not in INDICTS_VALUES:
        return None, "", (
            f"PLACEBO_MALFORMED: [{PLACEBO_SECTION}] indicts is {indicts!r}; it must be "
            f"one of {', '.join(repr(v) for v in INDICTS_VALUES)}"
        )

    null: float = DEFAULT_NULL
    if "null_value" in table:
        parsed, problem = declaration.finite_number(
            table["null_value"], f"[{PLACEBO_SECTION}] null_value"
        )
        if parsed is None:
            return None, "", (
                f"PLACEBO_MALFORMED: {problem}. It is the value this estimand takes "
                "under no signal, and every comparison D2 makes is against it"
            )
        null = parsed

    region = HaltRegion(
        null=null,
        indicts=indicts,
        estimand=estimand,
        declared=True,
        source=decl.source,
        allow_dirty=decl.allow_dirty,
    )

    # A widened halt region may not be anonymous. `either` at a null of zero is
    # what mlkit applies to a repo that has declared nothing, so it needs no
    # justification; anything else is this repo asserting that its estimand's
    # no-signal value is somewhere other than where D2 assumes, and that
    # assertion has to be WRITTEN DOWN next to the number it licenses. mlkit
    # cannot adjudicate prose. What it can do is refuse an exemption nobody
    # signed their name to, and put the sentence in the evidence so the verdict
    # quotes the justification rather than only the result.
    if not region.is_default and not estimand:
        return None, "", (
            f"PLACEBO_ESTIMAND_UNDECLARED: [{PLACEBO_SECTION}] moves D2's halt region "
            f"(null_value={null:.6g}, indicts={indicts!r}) without declaring an "
            "`estimand`. The default -- a two-sided interval around zero -- is the one "
            "rule that needs no justification, because it is the one every repo is "
            "measured by. Moving it requires saying, in the same committed table, what "
            "this placebo estimates and why its no-signal value is not zero"
        )
    return region, "", ""


@check("D2", PHASE, "PLACEBO_TEST — estimate indistinguishable from its declared null")
def d2_placebo_test(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("placebo_test")
    except BindingError as exc:
        return CheckResult.na(
            "D2", PHASE,
            f"{exc}; the placebo run is a SageMaker Processing Job and the training "
            "plane has not been bootstrapped",
        )

    # The halt region is read AFTER `repo.resolve` has imported the subject's
    # module -- deliberately, and it does not matter. A module-body write to
    # `.mlkit/repo.toml` lands before any read taken inside this check, however
    # this check orders its own statements, so ordering is not the protection
    # and never was. Reading HEAD's blob is: the write makes the tree dirty and
    # `core.artifact` refuses it. `d3_uncertainty_coverage` below carries the
    # same note and the same control (E-M23).
    region, na_reason, fail_reason = read_halt_region(repo, ctx)
    if region is None:
        return (
            CheckResult.na("D2", PHASE, na_reason)
            if na_reason
            else CheckResult.failed("D2", PHASE, fail_reason)
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
    evidence = {
        "estimate": estimate,
        "ci_low": lo,
        "ci_high": hi,
        "run": out.get("run_id", ""),
        **region.evidence(),
    }

    # Distinguishable from the null == the interval excludes it, on a side this
    # repo has declared to be indicting. With no declaration `null` is 0.0 and
    # both sides indict, so this is `lo > 0 or hi < 0` -- the same expression,
    # with both of its operands and its sidedness now tied to something a
    # reader can fetch instead of to a literal only mlkit knew.
    if (region.halts_above and lo > region.null) or (region.halts_below and hi < region.null):
        boundary = "zero" if region.null == 0.0 else f"the declared null {region.null:.6g}"
        side = "" if region.is_default else (
            f", on the {region.indicts!r} side this repo declared indicting"
        )
        return CheckResult.failed(
            "D2", PHASE,
            f"placebo estimate {estimate:.6g} with CI [{lo:.6g}, {hi:.6g}] excludes "
            f"{boundary}{side}; "
            "the estimator is capturing something other than the intervention. "
            "HARD STOP — do not tune, do not scale, do not schedule a training run.",
            {**evidence, "halt": True},
        )

    # Everything below this line reasons about an interval that CONTAINS the
    # null -- or, under a one-sided declaration, sits on the side this repo
    # declared not to indict -- and a non-finite figure reaches here by failing
    # to be anything at all.
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

    # Whether the interval CONTAINS the null is a separate fact from whether it
    # indicts, and under a one-sided declaration they come apart: fray's
    # [-71.998, -53.146] contains no null at all and does not indict, because
    # the side it sits on is the side a shuffled-target run is expected to sit
    # on. Recorded rather than inferred, so a portfolio reader can see which of
    # the two a PASS rests on instead of assuming the older, narrower one.
    evidence["null_contained"] = bool(lo <= region.null <= hi)

    # Not indicting is necessary but nowhere near sufficient. An interval wide
    # enough to contain everything contains the null too, and would sail
    # through the package's self-described strongest check while proving
    # nothing. Passing requires enough power to have detected the effect the
    # real run claims -- otherwise this is a null result and a no-power result
    # wearing the same face.
    reference = out.get("reference_effect")
    if reference is None:
        standing = (
            "placebo interval contains zero"
            if region.is_default
            else "placebo interval does not indict under this repo's declared halt region"
        )
        return CheckResult.na(
            "D2", PHASE,
            f"{standing}, but no reference_effect was reported, "
            "so a true null cannot be told apart from a test with no power. "
            "Report the real-run effect size this placebo must be able to detect.",
            evidence,
        )
    # The SIGN is read out before `abs()` discards it, and it is read for one
    # reason only -- see the tie below. The power bar's operand is unchanged.
    reported = float(reference)
    reference = abs(reported)
    half_width = (hi - lo) / 2.0
    evidence.update({
        "reference_effect": reference,
        "reference_effect_reported": reported,
        "ci_half_width": half_width,
    })
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

    # THE TIE THAT PAYS FOR THE ONE-SIDED EXEMPTION.
    #
    # A one-sided halt region says: excursions this way indict, excursions that
    # way are what no signal looks like. That is a real and often correct claim
    # about an estimand -- and it is also, written down carelessly, a way to
    # exempt precisely the direction the placebo was going to fail in.
    #
    # There is one operand already in the dict that can be tied to it without
    # asking the subject anything new: `reference_effect` is the size of the
    # effect THE REAL RUN CLAIMS, measured from this same null, and D2 already
    # requires it. If the product's claim lives ABOVE the null, then a placebo
    # reproducing that claim would land above the null, and "above" is the side
    # that must indict. A repo declaring the opposite has exempted the only
    # direction its own D2 was testing, and every remaining verdict this check
    # could return would be vacuous.
    #
    # An effect of exactly zero fails this too. It lies on NEITHER side, so
    # there is nothing for a one-sided exemption to agree with -- and the
    # comparison is `> 0` rather than `>= 0` for that reason. The power bar
    # below refuses a zero reference as well, so the STATUS is FAIL either way
    # and only the diagnosis differs; under a one-sided declaration the
    # diagnosis this branch gives is the precise one, and `test_a_zero_
    # reference_effect_under_a_one_sided_region_names_the_sign` pins it. That
    # test exists because a mutation drive found `>=` here changed nothing any
    # control could see.
    #
    # Under the default two-sided region the sign is not read at all -- both
    # sides indict, so there is nothing to disagree with, and `abs()` is the
    # whole of the arithmetic exactly as it was.
    if not region.is_default:
        indicting_sign = (
            1.0 if region.indicts == INDICTS_ABOVE
            else -1.0 if region.indicts == INDICTS_BELOW
            else 0.0
        )
        if indicting_sign and not (reported * indicting_sign > 0):
            return CheckResult.failed(
                "D2", PHASE,
                f"PLACEBO_EXEMPTS_THE_CLAIM: [{PLACEBO_SECTION}] declares that only "
                f"excursions {region.indicts} the null {region.null:.6g} indict, but the "
                f"real-run effect this placebo must be able to detect is reported as "
                f"{reported:.6g}, which does not lie on the indicting side. The "
                "direction the product's claim lives in is the one direction D2 has to "
                "be able to refuse; exempting it makes every other verdict here vacuous. "
                "Either the declaration or the reported effect is the wrong way round",
                evidence,
            )

    # Disclosure, and deliberately NOT a gate. mlkit ties the null's finiteness,
    # its committedness, the estimand written beside it and -- one-sided -- its
    # DIRECTION against the real-run claim. It does not tie its MAGNITUDE, and
    # cannot: any bar on "how far from the estimate may a declared null sit"
    # would be an expected range mlkit invented (CLAUDE.md rule 2), and it would
    # refuse the one real case this contract was measured against -- fray's
    # placebo sits 2.743 reference-effects from its null, which is ordinary for
    # a skill-against-a-floor estimand. So the number a reviewer would need is
    # PRINTED instead: a runaway null shows up as a large figure in the
    # portfolio row rather than as a silent PASS. docs/ESCALATIONS.md E-M24
    # records that disclosure is not a gate, and what the gate would need (D1,
    # which is the signatory's).
    if reference:
        evidence["null_distance_in_reference_effects"] = abs(estimate - region.null) / reference

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


#: The ``.mlkit/repo.toml`` binding D6 adjudicates.
RESAMPLING_BINDING = "resampling_declaration"

#: What that binding must name about itself. Everything else D6 reports — the
#: counts, the digests, the relation, the verdict — mlkit DERIVES from the
#: assignment. A binding that reported its own `n_units` would be reporting the
#: operand of its own verdict, which is E-M21's shape (D3's `nominal`) in a new
#: file.
DECLARED_FIELDS = ("procedure", "draws", "policy", "blocking_unit", "unit", "arm")

#: The four things a row of the assignment has to say.
ROW_FIELDS = ("row_key", "arm", "block_key", "unit_key")

#: Optional, and the seventh DECLARED field: which of the repo's holdout
#: policies this declaration was taken under, by the name ``splits`` gives it.
#: Absent means "this repo has one, unnamed, partition".
TRACK_FIELD = "track"

#: ``splits`` declares several tracks and the declaration names none. mlkit
#: could pick the track whose blocks happen to match and report PASS; that is a
#: check selecting the operand of its own verdict, so it refuses instead.
TRACK_UNDECLARED = "TRACK_UNDECLARED"

#: The declaration names a track ``splits`` does not declare -- including the
#: case where ``splits`` declares no tracks at all.
TRACK_NOT_IN_SPLITS = "TRACK_NOT_IN_SPLITS"

#: Two declarations in one return value naming one track. Two intervals over
#: one partition are two answers to one question, and nothing here can say
#: which of them the repo promoted on.
DUPLICATE_TRACK_DECLARATION = "DUPLICATE_TRACK_DECLARATION"

#: What the binding may return: one declaration, or a sequence of them.
DECLARATION_SHAPE = (
    f"one mapping {{{', '.join(DECLARED_FIELDS)}[, {TRACK_FIELD}], assignment}}, "
    "or a sequence of them -- one per track"
)


def _row_units(raw: Any) -> list[RowUnit]:
    """``RowUnit``s from a binding's assignment, refusing anything unnamed."""
    units: list[RowUnit] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise ServedContractError(
                f"assignment[{i}] is a {type(entry).__name__}; every row must be a "
                f"mapping naming {list(ROW_FIELDS)}. A bare sequence can be handed "
                "over with the block and the unit the wrong way round, and every "
                "verdict below would be exactly reversed with nothing to see."
            )
        missing = [k for k in ROW_FIELDS if k not in entry]
        if missing:
            raise ServedContractError(f"assignment[{i}] is missing {missing}")
        units.append(
            RowUnit(
                row_key=entry["row_key"],
                arm=str(entry["arm"]),
                block_key=entry["block_key"],
                unit_key=entry["unit_key"],
            )
        )
    return units


def _tracks_once(repo: Repo, cache: dict[str, Any]) -> tuple[Any, tuple[str, str, dict[str, Any]] | None]:
    """``splits`` resolved and parsed AT MOST ONCE per D6 run.

    Returns ``(tracks, None)`` or ``(None, (kind, text, extra_evidence))``. The
    three failure kinds are the three NA outcomes D6 already gave for an
    untied operand; they are returned rather than raised so that a run over
    several declarations reports the same NA on each of them from one read of
    the binding, instead of importing and calling it once per track.
    """
    if "v" in cache:
        return cache["v"]
    try:
        splits_fn = repo.resolve("splits")
    except BindingError as exc:
        cache["v"] = (None, ("binding", str(exc), {}))
        return cache["v"]
    try:
        tracks = normalise_tracked_splits(splits_fn())
    except SplitsUnreadable as exc:
        cache["v"] = (None, ("unreadable", exc.reason, dict(exc.evidence)))
        return cache["v"]
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        cache["v"] = (None, ("raised", f"splits raised {type(exc).__name__}: {exc}", {}))
        return cache["v"]
    cache["v"] = (tracks, None)
    return cache["v"]


def _judge_declaration(
    out: Mapping[str, Any], repo: Repo, cache: dict[str, Any]
) -> CheckResult:
    """ONE resampling declaration, judged. See :func:`d6_resampling_unit`."""
    missing = [f for f in (*DECLARED_FIELDS, "assignment") if f not in out]
    if missing:
        return CheckResult.failed(
            "D6", PHASE,
            f"{RESAMPLING_BINDING} did not report " + ", ".join(missing),
        )

    try:
        declaration = ResamplingDeclaration(
            procedure=str(out["procedure"]),
            # NOT coerced. `int("4000")` would accept a string count and
            # `int(True)` a boolean one; the contract refuses both by name and
            # coercing here would step around its own refusal.
            draws=out["draws"],
            policy=str(out["policy"]),
            blocking_unit=str(out["blocking_unit"]),
            unit=str(out["unit"]),
            arm=str(out["arm"]),
            assignment=_row_units(out["assignment"]),
            # NOT coerced either, and for the same reason one level up: `str()`
            # here would turn a track named `None` or `12` into a name that
            # `splits` can never produce, and the mismatch would read as
            # TRACK_NOT_IN_SPLITS instead of as the type error it is. The
            # declaration refuses a non-string by name.
            track=out.get(TRACK_FIELD, ""),
        )
    except ServedContractError as exc:
        return CheckResult.failed(
            "D6", PHASE, f"the resampling declaration is malformed: {exc}"
        )
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "D6", PHASE,
            f"building the resampling declaration raised {type(exc).__name__}: {exc}",
        )

    evidence: dict[str, Any] = declaration.to_dict()
    if declaration.refusal:
        return CheckResult.failed(
            "D6", PHASE, f"{declaration.refusal}: {declaration.detail}", evidence
        )

    # -- the other operand -------------------------------------------------
    #
    # Everything above reasons about ONE declaration, and a declaration
    # compared only to itself is not compared. `splits` is the repo's other
    # statement of the same partition, and R3 already adjudicates it.
    tracks, err = _tracks_once(repo, cache)
    if err is not None:
        kind, text, extra = err
        if kind == "binding":
            return CheckResult.na(
                "D6", PHASE,
                f"BLOCKS_UNTIED: the declaration is self-consistent ({declaration.relation}"
                f", {declaration.n_units_in_arm} {declaration.unit!r} unit(s) over "
                f"{declaration.n_blocks_in_arm} {declaration.blocking_unit!r} block(s) in "
                f"arm {declaration.arm!r}) and its blocks are tied to nothing outside it "
                f"-- {text}. A binding that reports `block_key = row_key` describes a "
                "policy with no blocks, passes clause 1 in silence, and is caught only "
                "here. Declare `splits` (R3 reads the same one).",
                evidence,
            )
        if kind == "unreadable":
            return CheckResult.na(
                "D6", PHASE,
                f"BLOCKS_UNTIED: the declared blocks cannot be tied to `splits` -- "
                f"{text}",
                {**evidence, **extra},
            )
        return CheckResult.na("D6", PHASE, f"BLOCKS_UNTIED: {text}", evidence)

    # -- which partition is this declaration's? -----------------------------
    #
    # A repo with one holdout policy declares no track and lands on the
    # SINGLE_TRACK key, which is where every adopter before tracks existed
    # lands; nothing below it moves. A repo with several declares them, and the
    # declaration has to say which one it was taken under -- mlkit will not
    # pick the track whose blocks happen to match.
    named = sorted(t for t in tracks if t != SINGLE_TRACK)
    is_tracked = list(tracks) != [SINGLE_TRACK]
    if is_tracked and not declaration.track:
        return CheckResult.failed(
            "D6", PHASE,
            f"{TRACK_UNDECLARED}: `splits` declares {len(named)} tracks "
            f"({named}) and this declaration names none. Two holdout policies "
            "over one panel are two different partitions, so 'the blocks agree "
            "with splits' has no meaning until the declaration says WHICH "
            "splits. mlkit will not choose the track whose blocks happen to "
            f"match: declare `{TRACK_FIELD}`.",
            {**evidence, "tracks_in_splits": named},
        )
    if declaration.track and not is_tracked:
        return CheckResult.failed(
            "D6", PHASE,
            f"{TRACK_NOT_IN_SPLITS}: the declaration was taken on track "
            f"{declaration.track!r} and `splits` declares no tracks at all -- it "
            f"returned one flat partition. Return "
            f"{{{TRACKS_KEY!r}: {{{declaration.track!r}: {{train, val, test}}, ...}}}} "
            "from `splits`, or drop the track from the declaration; a track "
            "named on one side only is tied to nothing.",
            {**evidence, "tracks_in_splits": []},
        )
    if declaration.track and declaration.track not in tracks:
        return CheckResult.failed(
            "D6", PHASE,
            f"{TRACK_NOT_IN_SPLITS}: the declaration was taken on track "
            f"{declaration.track!r} and `splits` declares {named}; an interval "
            "judged against a partition nobody published is judged against "
            "nothing.",
            {**evidence, "tracks_in_splits": named},
        )
    track_key = declaration.track if is_tracked else SINGLE_TRACK
    splits = tracks[track_key]
    tied_to = f"splits.{TRACKS_KEY}.{track_key}" if is_tracked else "splits"

    if declaration.arm not in splits:
        return CheckResult.failed(
            "D6", PHASE,
            f"the declaration was taken on arm {declaration.arm!r} and `splits` "
            f"declares {sorted(splits)}; a resampling on an arm the split does not "
            "have is a resampling of rows nobody held out",
            {**evidence, "splits_arms": sorted(splits)},
        )

    declared_blocks = set(declaration.block_keys_in_arm)
    from_splits = splits[declaration.arm]
    if declared_blocks != from_splits:
        only_declared = sorted(declared_blocks - from_splits)
        only_splits = sorted(from_splits - declared_blocks)
        return CheckResult.failed(
            "D6", PHASE,
            f"BLOCKS_CONTRADICT_SPLITS: the declaration says arm "
            f"{declaration.arm!r} holds {len(declared_blocks)} "
            f"{declaration.blocking_unit!r} block(s) and `splits` says it holds "
            f"{len(from_splits)} group(s). "
            + (f"Only in the declaration: {only_declared[:5]}. " if only_declared else "")
            + (f"Only in splits: {only_splits[:5]}. " if only_splits else "")
            + "The unit an interval was resampled over is judged against the "
            "partition, so the two have to be the same partition.",
            {
                **evidence,
                "n_blocks_declared": len(declared_blocks),
                "n_groups_in_splits": len(from_splits),
                "only_in_declaration": only_declared[:20],
                "only_in_splits": only_splits[:20],
            },
        )

    return CheckResult.passed(
        "D6", PHASE, {**evidence, "blocks_tied_to": tied_to, "n_groups_in_splits": len(from_splits)}
    )


@check("D6", PHASE, "RESAMPLING_UNIT — the unit resampled vs the holdout policy")
def d6_resampling_unit(repo: Repo, ctx: RunContext) -> CheckResult:
    """The dependence unit an interval rests on, checked against the split.

    THE FINDING. Round-8 adjudication, measured in ``resilient-fray``: the
    repo's holdout policy puts whole crop years in one partition, so the
    exchangeable unit is the crop year and VAL has five of them. The run's
    bootstrap resampled 1,365 ROWS as if independent. On one identical set of
    rows the interval moves from ``[+16.016, +29.646]`` — clears zero — to
    ``[-1.289, +41.704]`` — does not. ``resilient-chokepoint`` resamples its
    dependence unit (corridor block). fray resampled rows. **Nothing in mlkit
    required consistency, and nothing required the choice to be stated.**

    So D6 asks two questions and passes only when both are answered:

    1. **Does the declaration contradict itself?** mlkit builds the
       :class:`~resilient_mlkit.core.served.ResamplingDeclaration` here, from
       the assignment the binding returns, and derives the counts, the digests,
       the relation and the refusal. A unit that stays inside the deciding arm
       and splits one of the policy's blocks is
       ``DEPENDENCE_UNIT_TOO_FINE`` → FAIL.
    2. **Are the declared blocks the repo's actual partition?** The declaration
       alone cannot answer this, and the gap is real: a binding that sets
       ``block_key = row_key`` describes a policy with no blocks at all, which
       is perfectly self-consistent and silent. So the blocks are tied to the
       ``splits`` binding — a SECOND declaration of the same partition, which
       R3 already reads and judges. Disagreement is FAIL; an absent or
       unreadable ``splits`` is NA, because a verdict resting on an untied
       operand is the one thing three ticks of this loop have paid for.

    NA, not PASS, is the answer for a repo that has not wired the binding, in
    the same way D2 and D3 answer NA without theirs. That is visible in the
    fleet table and is never a pass.

    TWO TRACKS OVER ONE PANEL. ``resilient-fray`` runs two holdout policies
    over one county-year panel — unseen COUNTY and unseen future YEAR — and
    while ``splits`` could publish only one partition, no wiring existed under
    which both tracks could be judged: the crop-year declaration's blocks were
    compared against spatial block ids and landed on
    ``BLOCKS_CONTRADICT_SPLITS`` for a partition it was never taken under. So
    ``splits`` may now publish per-track partitions
    (:func:`~resilient_mlkit.checks.readiness.normalise_tracked_splits`), the
    declaration may name its ``track``, and the binding may return a SEQUENCE
    of declarations — one per track — whose worst verdict is D6's. A repo with
    one partition declares no track and every word above still describes it,
    byte for byte.
    """
    try:
        fn = repo.resolve(RESAMPLING_BINDING)
    except BindingError as exc:
        # LEFT EXACTLY AS IT WAS, deliberately. `redact` bounds every reason at
        # MAX_REASON = 400 characters and this one already spends 397 of them,
        # so naming the optional `track` and the sequence shape here would
        # TRUNCATE the sentence that tells an adopter what to declare -- a
        # message that stops mid-word is worse guidance than one that is merely
        # incomplete. The new shape is documented where there is room for it:
        # `spine/mlkit/repo.toml` (which this very sentence points the reader
        # at), :data:`DECLARATION_SHAPE`, and this function's docstring.
        return CheckResult.na(
            "D6", PHASE,
            f"{exc}; an interval or a promotion that rests on a resampling procedure "
            "must declare the unit that procedure drew. Declare "
            f"`{RESAMPLING_BINDING}` returning "
            f"{{{', '.join(DECLARED_FIELDS)}, assignment}}, where `assignment` is "
            f"one mapping per panel row naming {list(ROW_FIELDS)}.",
        )
    try:
        raw = fn()
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "D6", PHASE, f"{RESAMPLING_BINDING} raised {type(exc).__name__}: {exc}"
        )

    cache: dict[str, Any] = {}

    # ONE declaration -- the shape every adopter has today. Judged and
    # returned directly, so its status, reason and evidence are the bytes it
    # produced before tracks existed.
    if isinstance(raw, Mapping):
        return _judge_declaration(dict(raw), repo, cache)

    # A SEQUENCE of declarations -- one per track. Refused by type rather than
    # coerced: `dict()` accepts a list of pairs, so a bare sequence used to be
    # silently reassembled into "a declaration" whose fields came from
    # wherever the pairs happened to land.
    if isinstance(raw, str | bytes) or not isinstance(raw, Iterable):
        return CheckResult.failed(
            "D6", PHASE,
            f"{RESAMPLING_BINDING} returned a {type(raw).__name__}; it must return "
            f"{DECLARATION_SHAPE}",
        )
    entries = list(raw)
    if not entries:
        return CheckResult.failed(
            "D6", PHASE,
            f"{RESAMPLING_BINDING} returned an empty sequence; a repo that declares "
            "no resampling at all leaves the binding undeclared and is NA, which is "
            "visible in the fleet table. An empty sequence is a wired binding that "
            "measured nothing, and it would read as a run with no findings.",
        )
    bad = [i for i, e in enumerate(entries) if not isinstance(e, Mapping)]
    if bad:
        return CheckResult.failed(
            "D6", PHASE,
            f"{RESAMPLING_BINDING}[{bad[0]}] is a {type(entries[bad[0]]).__name__}; "
            f"every entry must be a mapping {{{', '.join(DECLARED_FIELDS)}"
            f"[, {TRACK_FIELD}], assignment}}",
        )
    entries = [dict(e) for e in entries]

    # Two declarations naming one track are two intervals over one partition.
    # Checked BEFORE any of them is judged, because otherwise the aggregate
    # below would report the worst of two answers to one question as though it
    # were one answer.
    # Compared by repr, not by value: a track key is whatever the binding put
    # there, an unhashable one (a list) would raise in a set, and two entries
    # that both name nothing collide on `""` exactly as two that both name
    # `"crop_year"` do.
    names = [e.get(TRACK_FIELD, "") for e in entries]
    seen: set[str] = set()
    duplicated: list[str] = []
    for n in names:
        key = repr(n)
        if key in seen and key not in duplicated:
            duplicated.append(key)
        seen.add(key)
    duplicated.sort()
    if duplicated:
        return CheckResult.failed(
            "D6", PHASE,
            f"{DUPLICATE_TRACK_DECLARATION}: {len(entries)} declarations and "
            f"track(s) {duplicated} named more than once. Two intervals over one "
            "partition are two answers to one question, and nothing here can say "
            "which one the repo promoted on.",
            {"n_declarations": len(entries), "declared_tracks": [repr(n) for n in names]},
        )

    results = [_judge_declaration(e, repo, cache) for e in entries]
    per_declaration = [
        {
            "track": str(name),
            "status": r.status.value,
            "reason": r.reason,
            "evidence": r.evidence,
        }
        for name, r in zip(names, results, strict=True)
    ]
    evidence: dict[str, Any] = {
        "n_declarations": len(entries),
        "declarations": per_declaration,
    }

    tracks, err = _tracks_once(repo, cache)
    if err is None:
        in_splits = sorted(t for t in tracks if t != SINGLE_TRACK)
        evidence["tracks_in_splits"] = in_splits
        # RECORDED, NOT REFUSED, and the prereg says so in advance: mlkit
        # cannot know whether a track produced an interval at all, so a track
        # nobody declared a resampling for is a gap in what D6 judged rather
        # than a defect it found. Naming it is the whole point -- an unjudged
        # track that appeared nowhere would be exactly the silence this branch
        # exists to end.
        evidence["tracks_without_declaration"] = [
            t for t in in_splits if t not in {str(n) for n in names}
        ]

    # The joined reason is bounded by MAX_REASON like every other reason, so a
    # repo with several failing tracks can lose the tail of the sentence. Each
    # per-declaration reason is kept WHOLE in evidence["declarations"] above --
    # the summary is what truncates, never the record.
    fails = [(n, r) for n, r in zip(names, results, strict=True) if r.status is Status.FAIL]
    if fails:
        return CheckResult.failed(
            "D6", PHASE,
            "; ".join(f"track {str(n)!r}: {r.reason}" for n, r in fails),
            evidence,
        )
    nas = [(n, r) for n, r in zip(names, results, strict=True) if r.status is Status.NA]
    if nas:
        return CheckResult.na(
            "D6", PHASE,
            "; ".join(f"track {str(n)!r}: {r.reason}" for n, r in nas),
            evidence,
        )
    return CheckResult.passed("D6", PHASE, evidence)


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
