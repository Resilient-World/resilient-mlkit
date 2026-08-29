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

import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import (
    MAX_COVERAGE_TOL,
    MIN_COVERAGE_N,
    d2_placebo_test,
    d3_uncertainty_coverage,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status
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


def _ctx(tmp_path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


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


def _coverage_repo(tmp_path, body: str, *, declare: bool = True) -> Repo:
    module = f"d3_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\ncoverage = "{module}:coverage"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _run_d3(tmp_path, body: str, *, declare: bool = True):
    repo = _coverage_repo(tmp_path, body, declare=declare)
    try:
        return d3_uncertainty_coverage(repo, _ctx(tmp_path))
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
