"""D2 controls: does the placebo hard stop fire when it should, and stay silent when it should not.

D2 is the check the package's own docstring calls its strongest, and it is one
of only two checks in `mlkit` whose verdict stops a repo outright rather than
handing back a finding to work on. `portfolio.resolve` keys that on one field:
`evidence["halt"]` (`src/resilient_mlkit/portfolio.py:52,68`). Until this file
existed, nothing anywhere in the suite had ever made `d2_placebo_test` produce
it. `tests/test_promotion_state.py` proves a halt outranks everything else, but
it builds the halting `CheckResult` by hand — so the two halves of the hard stop
were each tested and the join between them was not.

The pairing that carries the most weight here is D2-1 against D2-3:

* **a CI excluding zero FIRES with `halt` / an underpowered null FAILs without
  it.** Both are refusals and they are not the same instruction. "The estimator
  is measuring something other than the intervention" ends the repo; "this
  placebo had no power to detect the effect" says go and run a bigger placebo.
  A check that flagged both the same way would convert every weak probe into a
  halt, and would be switched off the first time that cost somebody a week.

* **a null with no `reference_effect` is NA, not PASS.** An interval wide enough
  to contain everything contains zero too. The check refuses to call that a pass
  and refuses to call it a failure, which is exactly the NA-distinct-from-both
  property the portfolio depends on.

One case here was found by writing the controls rather than by reading the
check: `test_positive_control_a_non_finite_placebo_interval_is_refused`. See its
docstring.
"""

from __future__ import annotations

import subprocess
import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import (
    COVERAGE_SECTION,
    MAX_COVERAGE_TOL,
    MIN_COVERAGE_N,
    NOMINAL_AGREEMENT_EPS,
    d2_placebo_test,
    d3_uncertainty_coverage,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import ALLOW_DIRTY_KEY, Status, UncommittedRead
from resilient_mlkit.portfolio import BLOCKED, resolve

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py. Two
#: repos both naming their adapter module the same thing is the collision
#: `Repo.release()` exists for, and a suite that reintroduced it would be
#: reading the first fixture's placebo under the second fixture's name.
_SERIAL = iter(range(10_000))


def _placebo_repo(tmp_path, body: str, *, declare: bool = True) -> Repo:
    """A repo on disk whose `placebo_test` binding is `body`.

    Written into a uniquely-named module and declared in `.mlkit/repo.toml`, so
    the check resolves and calls it through exactly the path it uses against the
    eight real repos rather than through a monkeypatch.
    """
    module = f"d2_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\nplacebo_test = "{module}:placebo_test"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path, *, allow_dirty: bool = False) -> RunContext:
    return RunContext(
        nonce="test-nonce", root=tmp_path, offline=True, allow_dirty=allow_dirty
    )


def _git(cwd, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _run(tmp_path, body: str, *, declare: bool = True):
    repo = _placebo_repo(tmp_path, body, declare=declare)
    try:
        return d2_placebo_test(repo, _ctx(tmp_path))
    finally:
        repo.release()


def _placebo(fields: str) -> str:
    return f"""
        def placebo_test():
            return {{{fields}}}
    """


# -- the hard stop: FIRES / SILENT ----------------------------------------


def test_positive_control_a_CI_excluding_zero_above_is_a_hard_stop(tmp_path):
    """FIRES: the whole reason D2 exists. An avoided-loss estimate the pipeline
    produces on a period where nothing was avoided is measuring something else."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.72, "ci_low": 0.31, "ci_high": 1.13, "run_id": "pl-1"'),
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "excludes zero" in result.reason
    assert result.evidence["ci_low"] == 0.31


def test_positive_control_a_CI_excluding_zero_below_is_equally_a_hard_stop(tmp_path):
    """FIRES: the sign of the artefact is not the point. An estimator that finds
    a confidently NEGATIVE effect where there is none is just as broken."""
    result = _run(
        tmp_path,
        _placebo('"estimate": -0.72, "ci_low": -1.13, "ci_high": -0.31'),
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason


def test_negative_control_a_powered_null_is_silent(tmp_path):
    """SILENT: the legitimate result. Without this the two above prove nothing —
    a check that halted on every placebo would halt on the correct one too."""
    result = _run(
        tmp_path,
        _placebo(
            '"estimate": 0.004, "ci_low": -0.05, "ci_high": 0.05, '
            '"reference_effect": 0.40, "run_id": "pl-ok"'
        ),
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["ci_half_width"] == 0.05
    assert result.evidence["reference_effect"] == 0.40


def test_a_hard_stop_reaches_the_portfolio_as_BLOCKED(tmp_path):
    """FIRES, end to end: the halt flag is not decorative.

    tests/test_promotion_state.py proves `resolve` honours a halt, using a
    CheckResult written by hand. This is the join it does not make: the real
    check, run against a real binding, produces the flag that stops the repo.
    """
    result = _run(tmp_path, _placebo('"estimate": 0.9, "ci_low": 0.4, "ci_high": 1.4'))
    repo = _placebo_repo(tmp_path, _placebo('"estimate": 0.0, "ci_low": 0.0, "ci_high": 0.0'))
    try:
        state = resolve(repo, {"D2": result})
    finally:
        repo.release()
    assert state.state == BLOCKED
    assert state.reason.startswith("D2 hard stop:")
    assert state.halted is True


def test_negative_control_a_powered_null_does_not_block_the_portfolio(tmp_path):
    """SILENT, end to end: a passing D2 leaves `halted` false."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.0, "ci_low": -0.02, "ci_high": 0.02, "reference_effect": 0.4'),
    )
    repo = _placebo_repo(tmp_path, _placebo('"estimate": 0.0, "ci_low": 0.0, "ci_high": 0.0'))
    try:
        state = resolve(repo, {"D2": result})
    finally:
        repo.release()
    assert state.halted is False
    assert not state.reason.startswith("D2 hard stop:")


# -- power: a failure that is NOT a hard stop -----------------------------


def test_an_underpowered_null_FAILS_without_halting_the_repo(tmp_path):
    """FIRES, and deliberately fires differently.

    This is the contract branch the task must pin rather than guess:
    `decision.py:88-96` returns FAIL — not NA, not PASS — when the interval
    contains zero but is no narrower than the effect the real run claims. And it
    does NOT set `halt`. That distinction is the whole point. A hard stop says
    the run cannot buy what it was meant to buy; this says the placebo was too
    small to tell, which is fixed by running a bigger placebo.
    """
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.02, "ci_low": -1.0, "ci_high": 1.0, "reference_effect": 0.4'),
    )
    assert result.status is Status.FAIL
    assert "halt" not in result.evidence
    assert "could not have detected" in result.reason
    assert result.evidence["ci_half_width"] == 1.0


def test_an_underpowered_null_does_not_block_the_portfolio_as_a_hard_stop(tmp_path):
    """SILENT for the halt specifically: it blocks as a FAIL, not as a hard stop.

    Both states are BLOCKED, and they carry different instructions. The reason
    string is what tells a reader which one they are looking at.
    """
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.02, "ci_low": -1.0, "ci_high": 1.0, "reference_effect": 0.4'),
    )
    repo = _placebo_repo(tmp_path, _placebo('"estimate": 0.0, "ci_low": 0.0, "ci_high": 0.0'))
    try:
        state = resolve(repo, {"D2": result})
    finally:
        repo.release()
    assert state.halted is False
    assert state.reason.startswith("D2 failed:")


def test_a_reference_effect_of_zero_is_refused(tmp_path):
    """FIRES: `reference_effect: 0` would make any interval "narrower than the
    effect" vacuously true. The check refuses it explicitly."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.0, "ci_low": -0.01, "ci_high": 0.01, "reference_effect": 0.0'),
    )
    assert result.status is Status.FAIL
    assert "halt" not in result.evidence


def test_the_power_bar_is_strict_at_the_boundary(tmp_path):
    """FIRES at exactly equal: `half_width >= reference` is a refusal, so a
    placebo that is precisely as wide as the effect it must detect does not pass."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.0, "ci_low": -0.4, "ci_high": 0.4, "reference_effect": 0.4'),
    )
    assert result.status is Status.FAIL
    assert result.evidence["ci_half_width"] == 0.4


def test_negative_control_just_inside_the_power_bar_is_silent(tmp_path):
    """SILENT: the other side of the same boundary, so the bar is a bar and not
    a blanket refusal."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.0, "ci_low": -0.39, "ci_high": 0.39, "reference_effect": 0.4'),
    )
    assert result.status is Status.PASS


def test_negative_control_a_lower_bound_of_exactly_zero_does_not_exclude_zero(tmp_path):
    """SILENT: `lo > 0` is strict. An interval touching zero contains it, and the
    hard stop is reserved for one that does not."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.5, "ci_low": 0.0, "ci_high": 1.0, "reference_effect": 4.0'),
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence


# -- NA is not PASS and not FAIL ------------------------------------------


def test_a_null_without_a_reference_effect_is_NA_naming_what_is_missing(tmp_path):
    """FIRES as NA: the contract branch at `decision.py:80-86`.

    A wide interval contains zero for the same reason it contains everything.
    Reporting that as PASS is how the package's self-described strongest check
    would sail through while proving nothing, so it is neither a pass nor a
    failure — it is unmeasured, and it says which figure would make it
    measurable.
    """
    result = _run(tmp_path, _placebo('"estimate": 0.0, "ci_low": -5.0, "ci_high": 5.0'))
    assert result.status is Status.NA
    assert "reference_effect" in result.reason
    assert "no power" in result.reason
    assert "halt" not in result.evidence


def test_an_undeclared_binding_is_NA_rather_than_a_pass(tmp_path):
    """FIRES as NA: "this repo has not wired a placebo" is not "the placebo was
    clean". A missing hard stop must never render as a cleared one."""
    result = _run(
        tmp_path, _placebo('"estimate": 0.0, "ci_low": -0.1, "ci_high": 0.1'), declare=False
    )
    assert result.status is Status.NA
    assert "no 'placebo_test' binding declared" in result.reason


def test_a_binding_that_raises_is_a_FAIL_not_an_NA(tmp_path):
    """FIRES as FAIL, and the distinction from the case above is the point.

    "Not wired yet" and "wired and broken" are different distances from a real
    run. A portfolio table that renders them identically cannot say which.
    """
    result = _run(
        tmp_path,
        """
        def placebo_test():
            raise RuntimeError("the processing job never started")
        """,
    )
    assert result.status is Status.FAIL
    assert "RuntimeError" in result.reason
    assert "never started" in result.reason


def test_a_missing_interval_bound_is_refused_by_name(tmp_path):
    """FIRES: an estimate with no interval cannot be told apart from zero, and
    the reason names the field that is absent."""
    result = _run(tmp_path, _placebo('"estimate": 0.4, "ci_low": -0.1'))
    assert result.status is Status.FAIL
    assert "ci_high" in result.reason


# -- non-finite figures: the defect the controls found --------------------


def test_positive_control_a_non_finite_placebo_interval_is_refused(tmp_path):
    """FIRES — and did not, before the repair committed alongside this file.

    Found by writing the control, not by reading the check. `float("nan")`
    survives the field parse, and `nan > 0` and `nan < 0` are both False, so a
    NaN interval walks past the hard stop. It then walks past the power bar too,
    because `nan >= reference` is False as well, and the check returns PASS on a
    placebo that measured nothing at all.

    NaN is not hypothetical here: it is what a pandas/numpy estimator returns
    when a groupby or a reindex misses a stratum, and it is the same defect
    class repaired for R5's row counts at 00210b6 ("a NaN is not a row count
    either"). A hard stop that a NaN can switch off is not a hard stop.
    """
    result = _run(
        tmp_path,
        """
        def placebo_test():
            nan = float("nan")
            return {"estimate": nan, "ci_low": nan, "ci_high": nan,
                    "reference_effect": 0.4}
    """,
    )
    assert result.status is Status.FAIL
    assert "finite" in result.reason
    assert "ci_low" in result.reason


def test_positive_control_a_non_finite_reference_effect_is_refused(tmp_path):
    """FIRES: the power bar is `half_width >= reference`, and a NaN reference
    makes that False whatever the interval is — so the requirement is satisfied
    by a figure that does not exist."""
    result = _run(
        tmp_path,
        """
        def placebo_test():
            return {"estimate": 0.0, "ci_low": -1e9, "ci_high": 1e9,
                    "reference_effect": float("nan")}
    """,
    )
    assert result.status is Status.FAIL
    assert "finite" in result.reason
    assert "reference_effect" in result.reason


def test_positive_control_a_non_finite_estimate_alone_is_refused(tmp_path):
    """FIRES: an interval can be perfectly narrow around a point estimate that
    does not exist, and PASS requires evidence — a NaN is not evidence."""
    result = _run(
        tmp_path,
        """
        def placebo_test():
            return {"estimate": float("nan"), "ci_low": -0.01, "ci_high": 0.01,
                    "reference_effect": 0.4}
    """,
    )
    assert result.status is Status.FAIL
    assert "finite" in result.reason
    assert "estimate" in result.reason


def test_positive_control_the_string_nan_is_refused_the_same_way(tmp_path):
    """FIRES: `float("nan")` accepts the string too, so a JSON round-trip that
    stringified the figure gets the same refusal rather than a different one."""
    result = _run(
        tmp_path,
        _placebo('"estimate": "nan", "ci_low": "nan", "ci_high": "nan", '
                 '"reference_effect": 0.4'),
    )
    assert result.status is Status.FAIL
    assert "finite" in result.reason


def test_negative_control_a_very_wide_but_finite_interval_still_reads_as_no_power(tmp_path):
    """SILENT for the finiteness guard specifically: an infinite-looking but
    finite interval is still judged on power, so the refusal above is of
    non-finiteness and not of magnitude."""
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.0, "ci_low": -1e12, "ci_high": 1e12, "reference_effect": 0.4'),
    )
    assert result.status is Status.FAIL
    assert "could not have detected" in result.reason
    assert "finite" not in result.reason


def test_negative_control_an_ordinary_finite_placebo_is_untouched_by_the_guard(tmp_path):
    """SILENT: the guard added for the cases above must not cost the pass case.

    This is the same fixture as the powered-null control, asserted again against
    the guard specifically, because a finiteness check written slightly wrong
    (testing the wrong field, or testing before the fields are read) turns every
    D2 into a FAIL and nothing else in this file would notice.
    """
    result = _run(
        tmp_path,
        _placebo('"estimate": 0.004, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": 0.4'),
    )
    assert result.status is Status.PASS
    assert result.evidence["estimate"] == 0.004


# -- D3: the coverage tolerance is mlkit's, not the binding's -------------
#
# D3's pairs are the same shape as R4's and for the same reason: a binding may
# ask for something stricter than mlkit and never for something looser, because
# a subject that sets its own pass mark sets no pass mark. The other pair here
# is the underpowered one — below MIN_COVERAGE_N the binomial standard error
# alone exceeds the tolerance, so the measurement cannot support a verdict in
# either direction and the honest answer is NA.
#
# Every fixture below declares its nominal level in `.mlkit/repo.toml`, because
# that is where the level lives (E-M21). `nominal=None` is the undeclared repo,
# and it has its own control further down.


def _coverage_repo(
    tmp_path,
    body: str,
    *,
    declare: bool = True,
    nominal: object = 0.90,
    commit: bool = True,
) -> Repo:
    """A git repo whose COMMITTED `.mlkit/repo.toml` declares `nominal`.

    The declaration is committed rather than merely written, because D3 now
    reads the level through ``core.artifact`` -- from ``HEAD:.mlkit/repo.toml``,
    not from the working tree. Before that, these fixtures wrote the file and
    the check parsed it off disk with ``repo.config()``, so the pass mark every
    control here measures against was bytes in nobody's git history: the
    ``docs/ESCALATIONS.md`` E-M12 shape, one check after S1-S4 were moved out
    of it.

    Nothing about what the controls ASSERT changed; the fixture became a repo.
    ``commit=False`` is the uncommitted declaration, used by the controls that
    exercise the refusal itself.
    """
    module = f"d3_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\ncoverage = "{module}:coverage"\n'
    if nominal is not None:
        toml += f"\n[{COVERAGE_SECTION}]\nnominal = {nominal}\n"
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".mlkit" / "repo.toml").write_text(
        toml if commit else '[repo]\nname = "fixturerepo"\n'
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "fixture")
    if not commit:
        (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _run_d3(
    tmp_path,
    body: str,
    *,
    declare: bool = True,
    nominal: object = 0.90,
    commit: bool = True,
    allow_dirty: bool = False,
):
    repo = _coverage_repo(
        tmp_path, body, declare=declare, nominal=nominal, commit=commit
    )
    try:
        return d3_uncertainty_coverage(repo, _ctx(tmp_path, allow_dirty=allow_dirty))
    finally:
        repo.release()


def _coverage(fields: str) -> str:
    return f"""
        def coverage():
            return {{{fields}}}
    """


def test_negative_control_coverage_matching_nominal_is_silent(tmp_path):
    """SILENT: empirical within tolerance of nominal, on enough points."""
    result = _run_d3(tmp_path, _coverage('"nominal": 0.90, "empirical": 0.89, "n": 5000'))
    assert result.status is Status.PASS
    assert result.evidence["tol"] == MAX_COVERAGE_TOL


def test_positive_control_intervals_that_do_not_cover_are_refused(tmp_path):
    """FIRES: 68% empirical against a 90% nominal means the prediction intervals
    do not mean what they say, and everything quoted from them is narrower than
    the truth."""
    result = _run_d3(tmp_path, _coverage('"nominal": 0.90, "empirical": 0.68, "n": 5000'))
    assert result.status is Status.FAIL
    assert "do not mean what they say" in result.reason


def test_positive_control_a_binding_cannot_widen_its_own_coverage_tolerance(tmp_path):
    """FIRES: the branch that makes D3 a gate.

    The binding asks for `tol: 0.50`, under which a 22-point coverage miss would
    pass. `min(declared, MAX_COVERAGE_TOL)` clamps it to 0.05 and the check
    fires anyway, printing mlkit's tolerance rather than the one it was handed.
    """
    result = _run_d3(
        tmp_path, _coverage('"nominal": 0.90, "empirical": 0.68, "n": 5000, "tol": 0.50')
    )
    assert result.status is Status.FAIL
    assert result.evidence["tol"] == MAX_COVERAGE_TOL


def test_positive_control_a_stricter_declared_tolerance_is_honoured(tmp_path):
    """FIRES on the other side of the clamp: a binding may be stricter than
    mlkit, so `tol: 0.005` fires on a 1-point miss that mlkit alone allows.
    Without this half, the clamp is indistinguishable from a fixed threshold."""
    result = _run_d3(
        tmp_path, _coverage('"nominal": 0.90, "empirical": 0.89, "n": 5000, "tol": 0.005')
    )
    assert result.status is Status.FAIL
    assert result.evidence["tol"] == 0.005


def test_a_holdout_too_small_to_measure_coverage_is_NA_not_a_pass(tmp_path):
    """FIRES as NA: below MIN_COVERAGE_N the binomial standard error alone
    exceeds the tolerance, so the measurement cannot support a verdict either
    way. Calling that PASS would be a coverage claim resting on noise."""
    result = _run_d3(tmp_path, _coverage('"nominal": 0.90, "empirical": 0.90, "n": 40'))
    assert result.status is Status.NA
    assert "too small to measure coverage" in result.reason
    assert result.evidence["n"] == 40


def test_negative_control_exactly_the_minimum_n_is_measurable(tmp_path):
    """SILENT at the boundary: the test is `n < MIN_COVERAGE_N`, so the floor
    itself measures — the NA above is of the shortfall, not of small holdouts."""
    result = _run_d3(
        tmp_path, _coverage(f'"nominal": 0.90, "empirical": 0.90, "n": {MIN_COVERAGE_N}')
    )
    assert result.status is Status.PASS


def test_a_missing_coverage_field_is_refused_by_name(tmp_path):
    """FIRES: coverage with no n is a proportion with no denominator."""
    result = _run_d3(tmp_path, _coverage('"nominal": 0.90, "empirical": 0.90'))
    assert result.status is Status.FAIL
    assert "did not report n" in result.reason


def test_an_undeclared_coverage_binding_is_NA(tmp_path):
    """FIRES as NA: unmeasured coverage is not calibrated coverage."""
    result = _run_d3(
        tmp_path, _coverage('"nominal": 0.90, "empirical": 0.90, "n": 5000'), declare=False
    )
    assert result.status is Status.NA
    assert "no 'coverage' binding declared" in result.reason


# -- D3: the nominal level is DATA, not the subject's own claim (E-M21) ----
#
# Tick 13's finding, found independently in two repos in one tick: TIE ONE
# OPERAND, LEAVE THE OTHER. D3's verdict is `abs(empirical - nominal) > tol`,
# and until this section existed BOTH operands were read out of the single dict
# the subject had just handed the check. Two repos tied `empirical` to the
# observed rows -- carefully, with controls of their own -- and left `nominal`,
# the other term of the same subtraction, tied only to a copy of itself.
#
# The arabica figures below are that incident's, verbatim: `nominal` set equal
# to the empirical 0.8879423328964613 in both `coverage_for_d3` and
# `levels[alpha=0.1]`, D3 returning PASS on evidence reading
# `{'nominal': 0.8879423328964613, 'empirical': 0.8879423328964613, ...}`,
# erasing a shortfall of -0.012057667103538727 the repo had truthfully
# disclosed for its served model of record. The second leg of that PR re-derived
# the coverage from the rows, agreed to 1e-12, and raised nothing -- because it
# was checking the operand that had not been touched.
#
# The pairing that carries the weight here is the first pair: the SAME rows and
# the SAME empirical figure, differing only in whether the callable restates the
# declared level or replaces it. If both were PASS or both were FAIL the check
# would not be reading the declaration at all.

#: The level the repo promises, and the coverage it actually got, from the
#: tick-13 arabica incident (scratchpad STATE.md, TICK 13).
_ARABICA_DECLARED = 0.90
_ARABICA_EMPIRICAL = 0.8879423328964613


def test_positive_control_a_self_declared_nominal_cannot_replace_the_declared_level(
    tmp_path,
):
    """FIRES: the tick-13 exploit, with the repo's real promise on disk.

    `.mlkit/repo.toml` declares 90% intervals. The callable reports its nominal
    as the empirical coverage it just measured. Every individual number here is
    genuine -- 0.8879423328964613 really was the coverage -- and only the
    PAIRING is a lie, which is exactly the shape surge's half of the incident
    took. Nothing compared the pairing until this branch.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_EMPIRICAL!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=_ARABICA_DECLARED,
    )
    assert result.status is Status.FAIL
    assert "NOMINAL_SELF_DECLARED" in result.reason
    # A refusal that does not print both operands cannot be acted on.
    assert result.evidence["declared_nominal"] == _ARABICA_DECLARED
    assert result.evidence["reported_nominal"] == _ARABICA_EMPIRICAL


def test_negative_control_the_honest_disclosure_the_exploit_erased_is_silent(tmp_path):
    """SILENT: the same rows, the same empirical, the level told truthfully.

    This is the half that makes the test above a control rather than a blanket
    refusal of coverage bindings. The shortfall of -0.0121 is inside mlkit's
    0.05 tolerance, so the honest report PASSes and the substituted one does
    not -- the verdict moves on the substitution alone.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_DECLARED!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=_ARABICA_DECLARED,
    )
    assert result.status is Status.PASS
    assert result.evidence["declared_nominal"] == _ARABICA_DECLARED
    # The honest binding restates the declared level; the shortfall stays
    # visible in `empirical`, which is the disclosure the exploit erased.
    assert result.evidence["reported_nominal"] == _ARABICA_DECLARED
    assert result.evidence["empirical"] == _ARABICA_EMPIRICAL


def test_an_undeclared_nominal_level_is_NA_not_a_silent_fallback(tmp_path):
    """FIRES as NA: with no declaration there is no second operand.

    The tempting fallback -- "no declaration, so trust the binding's nominal" --
    is the pre-branch behaviour wearing a conditional, and it is the one a repo
    reaches by deleting four characters from its own config. An undeclared level
    is not a licence to read the subject's claim as the standard.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_EMPIRICAL!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=None,
    )
    assert result.status is Status.NA
    assert "NOMINAL_UNDECLARED" in result.reason
    assert COVERAGE_SECTION in result.reason


def test_there_is_no_default_level_and_the_declared_one_sets_the_bar(tmp_path):
    """FIRES: a declared 0.99 that a 0.90 empirical misses by 0.09.

    What this pins is that D3 carries no level of its own -- the bar is
    whatever the repo committed. It does NOT distinguish which of the two
    now-equal operands the final comparison uses; see the boundary test below,
    which does.
    """
    result = _run_d3(
        tmp_path, _coverage('"nominal": 0.99, "empirical": 0.90, "n": 5000'), nominal=0.99
    )
    assert result.status is Status.FAIL
    assert "do not mean what they say" in result.reason
    assert result.evidence["declared_nominal"] == 0.99


def test_the_final_comparison_uses_the_declared_level_not_the_reported_copy(tmp_path):
    """FIRES only if the last comparison reads `declared`. Found by mutation.

    The first version of this section could not tell the two apart, and said in
    its docstring that it could. Rewriting `abs(empirical - declared)` back to
    `abs(empirical - nominal)` left the whole suite green, because by the time
    that line runs the agreement gate has forced the two within 1e-12 of each
    other -- for any ordinary tolerance they ARE the same number.

    They come apart in exactly one place, and it is reachable: a binding may
    declare a tolerance STRICTER than mlkit's, with no floor, so a `tol` below
    `NOMINAL_AGREEMENT_EPS` makes the representation allowance wider than the
    tolerance. Here the reported level sits 5.0004e-13 above the declared one —
    inside the allowance, so the substitution branch is silent — and `tol` is
    1e-13. Against the declared level the miss is 0.0 and this PASSes; against
    the reported copy it is 5.0004e-13 and it would FAIL. The committed
    declaration is the standard even when the subject's copy is nearer.
    """
    reported = 0.9 + 5e-13
    assert abs(reported - 0.9) < NOMINAL_AGREEMENT_EPS, "precondition: inside the allowance"
    assert abs(reported - 0.9) > 1e-13, "precondition: outside the tolerance below"
    result = _run_d3(
        tmp_path,
        _coverage(f'"nominal": {reported!r}, "empirical": 0.9, "n": 5000, "tol": 1e-13'),
        nominal=0.9,
    )
    assert result.status is Status.PASS
    assert result.evidence["tol"] == 1e-13
    assert result.evidence["reported_nominal"] == reported
    assert result.evidence["declared_nominal"] == 0.9


def test_a_float_representation_difference_is_not_a_disagreement(tmp_path):
    """SILENT: `1 - 0.1` is not the literal `0.9`, and a repo may compute it.

    The agreement bar is a representation allowance, not a tolerance: a
    disagreement smaller than 1e-12 is the same number written two ways. The
    incident this section pins missed by 0.0121, ten orders of magnitude above
    the bar, and the test below holds the bar's other side.
    """
    result = _run_d3(
        tmp_path,
        _coverage('"nominal": 1 - 0.1, "empirical": 0.89, "n": 5000'),
        nominal=0.9,
    )
    assert result.status is Status.PASS


def test_a_disagreement_just_above_the_representation_bar_is_refused(tmp_path):
    """FIRES: the other side of the allowance, so it is a bar and not a hole.

    1e-9 is far too small to matter to any coverage claim, and it is refused
    anyway, because the question this branch asks is not "is the level close"
    but "did the subject restate the level or replace it".
    """
    result = _run_d3(
        tmp_path,
        _coverage('"nominal": 0.900000001, "empirical": 0.89, "n": 5000'),
        nominal=0.9,
    )
    assert result.status is Status.FAIL
    assert "NOMINAL_SELF_DECLARED" in result.reason
    assert abs(0.900000001 - 0.9) > NOMINAL_AGREEMENT_EPS


def test_a_declared_level_that_is_not_a_probability_is_refused_by_name(tmp_path):
    """FIRES: `nominal = 90` is the percentage/probability confusion.

    Read as a level, 90 makes `abs(empirical - 90) > tol` true for every
    possible coverage, so the repo would fail D3 forever with a message about
    its intervals rather than about its config. A declaration that is not a
    probability is refused as a declaration.
    """
    result = _run_d3(
        tmp_path, _coverage('"nominal": 90, "empirical": 0.90, "n": 5000'), nominal=90
    )
    assert result.status is Status.FAIL
    assert "not a coverage level" in result.reason


def test_a_non_numeric_declared_level_is_refused_by_name(tmp_path):
    """FIRES: a string level. `float("0.90")` would have accepted it silently,
    and `bool` is an `int` in Python, so `nominal = true` would have declared a
    100% promise. Both are refused on type before anything is read from them."""
    result = _run_d3(
        tmp_path,
        _coverage('"nominal": 0.90, "empirical": 0.90, "n": 5000'),
        nominal='"0.90"',
    )
    assert result.status is Status.FAIL
    assert "not a number" in result.reason


def test_a_boolean_declared_level_is_refused_by_name(tmp_path):
    """FIRES: `nominal = true` is `1.0` to `float()` and a valid probability."""
    result = _run_d3(
        tmp_path,
        _coverage('"nominal": 1.0, "empirical": 1.0, "n": 5000'),
        nominal="true",
    )
    assert result.status is Status.FAIL
    assert "not a number" in result.reason


def test_negative_control_the_non_finite_refusals_outrank_the_declaration(tmp_path):
    """SILENT as a declaration verdict: a NaN empirical is still refused as NaN.

    Ordering control. A broken measurement gets the diagnosis that names what
    broke; folding it into NOMINAL_SELF_DECLARED (NaN disagrees with every
    declared level) would replace a precise refusal with a misleading one, and
    would make the E-M09/E-M10 non-finite guards unreachable through D3.
    """
    result = _run_d3(
        tmp_path,
        _coverage('"nominal": float("nan"), "empirical": 0.90, "n": 200'),
        nominal=0.90,
    )
    assert result.status is Status.FAIL
    assert "non-finite" in result.reason
    assert "NOMINAL_SELF_DECLARED" not in result.reason


def test_the_declared_level_range_holds_at_both_of_its_edges(tmp_path):
    """FIRES at 0 and is SILENT at 1, so the range is a range and not a slogan.

    `nominal = 0` promises nothing and would make every coverage a pass;
    `nominal = 1` is an odd but coherent promise -- every point inside the
    interval -- and refusing it would fail an honest repo on a bound nobody
    argued for. Both edges are driven because a bound with only one side tested
    can be moved to either.
    """
    zero = _run_d3(
        tmp_path, _coverage('"nominal": 0, "empirical": 0.90, "n": 5000'), nominal=0
    )
    assert zero.status is Status.FAIL
    assert "not a coverage level" in zero.reason

    one = _run_d3(
        tmp_path, _coverage('"nominal": 1.0, "empirical": 0.99, "n": 5000'), nominal=1
    )
    assert one.status is Status.PASS
    assert one.evidence["declared_nominal"] == 1.0


def test_a_coverage_section_that_is_not_a_table_is_NA_not_a_pass(tmp_path):
    """FIRES as NA: `[[coverage]]` parses to a LIST, and `.get` on a list raises.

    Found by attacking the fix rather than by reading it. Every malformed shape
    a repo can write -- an array of tables, a scalar under another name, a
    mis-cased `[Coverage]` -- has to land on a refusal or an NA and never on a
    pass, and it has to do it without raising out of the check, which would
    take the whole run down rather than one row.
    """
    repo = _coverage_repo(
        tmp_path, _coverage('"nominal": 0.90, "empirical": 0.90, "n": 5000'), nominal=None
    )
    config = repo.config_path
    config.write_text(config.read_text() + "\n[[coverage]]\nnominal = 0.9\n")
    # Committed, because an UNCOMMITTED malformed section would land on
    # NOMINAL_UNCOMMITTED and this control would stop measuring the shape it
    # was written for.
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "array of tables")
    try:
        result = d3_uncertainty_coverage(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is Status.NA
    assert "NOMINAL_UNDECLARED" in result.reason


def test_a_substituted_nominal_outranks_the_small_holdout_NA(tmp_path):
    """FIRES: n=40 is below the floor AND the level was replaced.

    NA would be the wrong answer: "we could not measure this" reads as a gap to
    fill, and hides that the level itself was rewritten. The substitution does
    not become less true on fewer rows.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_EMPIRICAL!r}, "empirical": {_ARABICA_EMPIRICAL!r}, "n": 40'
        ),
        nominal=_ARABICA_DECLARED,
    )
    assert result.status is Status.FAIL
    assert "NOMINAL_SELF_DECLARED" in result.reason


# -- D3: and the declaration is read FROM COMMITTED STATE (E-M23) ---------
#
# The section above moved D3's pass mark out of the dict the subject returns
# and into `.mlkit/repo.toml`. It was read with `repo.config()`, which reads
# the WORKING TREE, and the escalation that shipped with it staked the whole
# protection on a property nothing enforced: "the level is committed,
# reviewable and static".
#
# Driven at `a48c975`, in an interpreter asserting its own
# `resilient_mlkit.__file__`, through the real resolution path:
#
#     committed  [coverage] nominal = 0.90
#     working tree, uncommitted, nominal = 0.8879423328964613
#     binding reports nominal == empirical == 0.8879423328964613, n=1526
#       -> PASS, evidence {'declared_nominal': 0.8879423328964613, ...},
#          no allow-dirty marker, `git status` reading ` M .mlkit/repo.toml`
#
# The tick-13 exploit, restored by moving it one file across, and available to
# a repo that never commits the section at all. That is `docs/ESCALATIONS.md`
# E-M12's shape exactly -- the shape `checks/selection.py` was moved out of
# one release earlier, when S1-S4 stopped reading `docs/selection.yaml` with
# `Path.read_text()` -- and in the same run, in the same tree, S1 answered NA
# on a dirty register while D3 answered PASS on a dirty pass mark.
#
# The level is read through `core.artifact.load` now: HEAD's blob, or an NA
# naming the file, or -- under `--allow-dirty` -- a marked read that
# `CheckResult.__post_init__` refuses to let become a PASS.


def _rewrite_worktree_nominal(tmp_path, nominal: object) -> None:
    """Edit the declared level in the working tree, leaving HEAD alone."""
    config = tmp_path / ".mlkit" / "repo.toml"
    text = config.read_text()
    head, _, _ = text.partition(f"[{COVERAGE_SECTION}]")
    config.write_text(f"{head}[{COVERAGE_SECTION}]\nnominal = {nominal}\n")


def test_positive_control_an_uncommitted_declaration_cannot_move_the_pass_mark(tmp_path):
    """FIRES as NA: the tick-13 exploit, one file across. PASS before this branch.

    HEAD says the intervals promise 0.90. The working tree says they promise
    the 0.8879423328964613 the binding just measured, and the binding agrees
    with the working tree, so the substitution branch above sees two numbers
    that match. The only thing that separates this from an honest repo is
    which of the two files a reader would have reviewed.
    """
    repo = _coverage_repo(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_EMPIRICAL!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=_ARABICA_DECLARED,
    )
    _rewrite_worktree_nominal(tmp_path, repr(_ARABICA_EMPIRICAL))
    try:
        result = d3_uncertainty_coverage(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is Status.NA
    assert "NOMINAL_UNCOMMITTED" in result.reason
    assert ".mlkit/repo.toml" in result.reason


def test_positive_control_a_declaration_that_is_only_in_the_working_tree_is_NA(tmp_path):
    """FIRES as NA: a pass mark on no ref at all. PASS before this branch.

    `commit=False` is a repo whose HEAD carries no `[coverage]` section and
    whose working tree carries one. Nothing about that file can be fetched by
    the reader the verdict is quoted to, which is what makes it the same
    failure as a number nobody measured.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_EMPIRICAL!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=_ARABICA_EMPIRICAL,
        commit=False,
    )
    assert result.status is Status.NA
    assert "NOMINAL_UNCOMMITTED" in result.reason


def test_positive_control_a_binding_writing_the_declaration_at_import_cannot_move_it(
    tmp_path,
):
    """FIRES: the binding's MODULE BODY rewrites the config. PASS before this branch.

    Reading the declaration after the subject's code has run is not reading
    data, it is reading the subject. `repo.resolve()` imports this module, so
    a module-level write lands before any read taken inside the check, however
    the check orders its own statements. Reading HEAD's blob is what closes it,
    not reordering.
    """
    repo = _coverage_repo(
        tmp_path,
        f'''
        import pathlib
        _p = pathlib.Path(__file__).parent / ".mlkit" / "repo.toml"
        _p.write_text(
            _p.read_text().split("[{COVERAGE_SECTION}]")[0]
            + "[{COVERAGE_SECTION}]\\nnominal = {_ARABICA_EMPIRICAL!r}\\n"
        )

        def coverage():
            return {{
                "nominal": {_ARABICA_EMPIRICAL!r},
                "empirical": {_ARABICA_EMPIRICAL!r},
                "n": 1526,
                "tol": 0.05,
            }}
        ''',
        nominal=_ARABICA_DECLARED,
    )
    try:
        result = d3_uncertainty_coverage(repo, _ctx(tmp_path))
    finally:
        repo.release()
    # The write made the tree dirty, so the committed read refuses before it
    # ever reaches the substituted level. Either answer is a refusal; what is
    # pinned is that it is not a PASS and not the subject's number.
    assert result.status is not Status.PASS
    assert result.evidence.get("declared_nominal") != _ARABICA_EMPIRICAL


def test_positive_control_a_binding_corrupting_the_config_mid_run_raises_nothing(
    tmp_path,
):
    """SILENT as a crash: `repo.config()` re-parsed the file after the subject ran.

    At `a48c975` a binding that wrote malformed TOML during its own call made
    `repo.config()` raise `BindingError` OUT of the check -- the CLI's generic
    handler turns that into a FAIL with four frames of traceback, which is a
    diagnosis pointing at mlkit. Reading HEAD's blob means the subject's
    working-tree vandalism is not on the path at all.
    """
    repo = _coverage_repo(
        tmp_path,
        '''
        import pathlib

        def coverage():
            p = pathlib.Path(__file__).parent / ".mlkit" / "repo.toml"
            p.write_text("this is not = = toml [[[")
            return {"nominal": 0.90, "empirical": 0.90, "n": 5000}
        ''',
        nominal=0.90,
    )
    try:
        result = d3_uncertainty_coverage(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is not Status.PASS  # the tree is dirty; NA names it
    assert "Traceback" not in (result.reason or "")


def test_negative_control_a_committed_clean_declaration_is_untouched(tmp_path):
    """SILENT: the ordinary honest repo, and no marker on its evidence.

    Without this half the committed read is indistinguishable from a blanket
    refusal of every coverage binding.
    """
    result = _run_d3(
        tmp_path,
        _coverage(
            f'"nominal": {_ARABICA_DECLARED!r}, "empirical": {_ARABICA_EMPIRICAL!r}, '
            '"n": 1526, "tol": 0.05'
        ),
        nominal=_ARABICA_DECLARED,
    )
    assert result.status is Status.PASS
    assert result.evidence["declared_nominal"] == _ARABICA_DECLARED
    assert ALLOW_DIRTY_KEY not in result.evidence


def test_allow_dirty_reads_the_working_tree_and_structurally_cannot_pass(tmp_path):
    """FIRES: the escape hatch diagnoses and cannot reach a verdict.

    `--allow-dirty` exists so an operator can debug a declaration they have not
    committed yet; refusing that outright just pushes people back to `cat`.
    What it may not do is buy a PASS, and it does not: the marker rides in
    `evidence` and `CheckResult.__post_init__` raises `UncommittedRead`, which
    the CLI records as a FAIL. Both halves are here because a marker nothing
    refuses is a footnote, which is the whole of E-M12's finding.
    """
    repo = _coverage_repo(
        tmp_path,
        _coverage('"nominal": 0.90, "empirical": 0.90, "n": 5000'),
        nominal=0.90,
    )
    _rewrite_worktree_nominal(tmp_path, "0.90")
    try:
        try:
            d3_uncertainty_coverage(repo, _ctx(tmp_path, allow_dirty=True))
        except UncommittedRead as exc:
            assert "PASS may not rest on an --allow-dirty read" in str(exc)
        else:  # pragma: no cover - the guard not firing is the defect
            raise AssertionError("an --allow-dirty PASS was not refused")

        # The other half: a FAIL under the hatch is a usable diagnosis, and it
        # carries the marker so `portfolio.resolve` refuses it downstream.
        _rewrite_worktree_nominal(tmp_path, "0.99")
        failing = d3_uncertainty_coverage(repo, _ctx(tmp_path, allow_dirty=True))
    finally:
        repo.release()
    assert failing.status is Status.FAIL
    assert failing.evidence[ALLOW_DIRTY_KEY] is True
    assert failing.evidence["declared_nominal"] == 0.99
