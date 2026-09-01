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
from dataclasses import dataclass

from ..core import artifact, declaration
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
    # Zero fails it too, and for the same reason it fails the power bar below:
    # an effect of exactly zero lies on neither side, so there is nothing for
    # the exemption to agree with.
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
                f"{reported:.6g}, which lies on the exempt side. The direction the "
                "product's claim lives in is the one direction D2 has to be able to "
                "refuse; exempting it makes every other verdict here vacuous. Either "
                "the declaration or the reported effect is the wrong way round",
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
