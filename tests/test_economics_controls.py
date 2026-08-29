"""E1/E2/E3 controls: does the scaling hard stop fire, and does it stay silent when it should.

E1 is the second of the two checks in this package whose verdict stops a repo
rather than handing back a finding. If the curve is flat between 10% and 25% of
the data, the bottleneck is labels and the GPU budget buys wall-clock. Like D2,
nothing in the suite had ever made `e1_scaling_probe` produce the
`evidence["halt"]` flag that `portfolio.resolve` keys the stop off.

Two pairings carry the weight here.

* **flat FIRES with `halt` / rising is SILENT.** The check's stated job, and the
  half that says the epsilon is a threshold rather than a blanket refusal.

* **the orientation contract, exercised both ways.** `economics.py:56` says
  curve values are larger-is-better by contract and that the binding orients its
  own metric. That sentence is either load-bearing or decorative, and the only
  way to tell is to report the SAME run twice — once as a raw error metric
  (falling as the data grows, because the model is improving) and once oriented
  — and show the two get different verdicts. They do: un-oriented halts the
  repo. This is a control on the contract, not on the arithmetic.

E3's pair is the one worth reading after those: a utilisation number with no
profiler trace is refused, because a number without a trace is a claim.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.economics import (
    e1_scaling_probe,
    e2_hparam_sanity,
    e3_efficiency_floor,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status
from resilient_mlkit.portfolio import BLOCKED, resolve

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))


def _repo(tmp_path, binding: str, fn_name: str, body: str, *, declare: bool = True) -> Repo:
    """A repo on disk whose `binding` is `body`, resolved the way the real repos are."""
    module = f"e_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\n{binding} = "{module}:{fn_name}"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _run_e1(tmp_path, body: str, *, declare: bool = True):
    repo = _repo(tmp_path, "scaling_probe", "scaling_probe", body, declare=declare)
    try:
        return e1_scaling_probe(repo, _ctx(tmp_path))
    finally:
        repo.release()


def _curve(at01: str, at10: str, at25: str) -> str:
    return f"""
        def scaling_probe():
            return {{0.01: {at01}, 0.10: {at10}, 0.25: {at25}}}
    """


# -- the hard stop: FIRES / SILENT ----------------------------------------


def test_positive_control_a_flat_curve_is_a_hard_stop(tmp_path):
    """FIRES: the reason E1 exists. Three times the data buys a quarter of a
    percent, so the full run buys nothing that a labelling budget would not."""
    result = _run_e1(tmp_path, _curve("0.40", "0.700", "0.7015"))
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "flat between 10% and 25%" in result.reason
    assert result.evidence["gain_10_to_25"] < 0.01


def test_positive_control_a_falling_curve_is_a_hard_stop(tmp_path):
    """FIRES: worse at 25% than at 10% is not merely flat, and is not exempt."""
    result = _run_e1(tmp_path, _curve("0.40", "0.70", "0.62"))
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert result.evidence["gain_10_to_25"] < 0


def test_negative_control_a_rising_curve_is_silent(tmp_path):
    """SILENT: the legitimate result, and the half without which the two above
    prove nothing — a check that halted on every curve would halt on this one."""
    result = _run_e1(tmp_path, _curve("0.40", "0.70", "0.82"))
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["gain_10_to_25"] > 0.01
    assert result.evidence["curve"][0.25] == 0.82


def test_the_flatness_bar_is_inclusive_at_the_boundary(tmp_path):
    """FIRES at exactly epsilon: the test is `gain <= 0.01`, so a curve gaining
    precisely one percent is flat by this check's definition.

    The fixture is 100.0 -> 101.0 rather than the more readable 1.00 -> 1.01
    because only the former divides to the double nearest 0.01; `(1.01 - 1.00)
    / 1.00` is 0.010000000000000009 and lands on the passing side. That is a
    property of binary floating point, not of the check, and the fixture is
    adapted to it rather than the threshold being moved to meet the fixture.
    """
    result = _run_e1(tmp_path, _curve("40.0", "100.0", "101.0"))
    assert result.status is Status.FAIL
    assert result.evidence["gain_10_to_25"] == 0.01
    assert result.evidence["halt"] is True


def test_negative_control_just_past_the_flatness_bar_is_silent(tmp_path):
    """SILENT: the other side of the same boundary, so the epsilon is a bar."""
    result = _run_e1(tmp_path, _curve("40.0", "100.0", "101.1"))
    assert result.status is Status.PASS
    assert result.evidence["gain_10_to_25"] > 0.01


def test_a_hard_stop_reaches_the_portfolio_as_BLOCKED(tmp_path):
    """FIRES, end to end: the real check produces the flag that stops the repo.

    tests/test_promotion_state.py asserts `resolve` honours an E1 halt built by
    hand. This is the join: binding on disk, check run through it, halt flag
    carried into the portfolio verdict.
    """
    result = _run_e1(tmp_path, _curve("0.40", "0.70", "0.70"))
    repo = _repo(tmp_path, "scaling_probe", "scaling_probe", _curve("0.1", "0.2", "0.3"))
    try:
        state = resolve(repo, {"E1": result})
    finally:
        repo.release()
    assert state.state == BLOCKED
    assert state.reason.startswith("E1 hard stop:")
    assert state.halted is True


def test_negative_control_a_rising_curve_does_not_block_the_portfolio(tmp_path):
    """SILENT, end to end: a passing E1 leaves `halted` false."""
    result = _run_e1(tmp_path, _curve("0.40", "0.70", "0.90"))
    repo = _repo(tmp_path, "scaling_probe", "scaling_probe", _curve("0.1", "0.2", "0.3"))
    try:
        state = resolve(repo, {"E1": result})
    finally:
        repo.release()
    assert state.halted is False


# -- the orientation contract, both ways ----------------------------------

#: One run, three fractions, reported as RMSE — lower is better, so the model
#: is improving as the data grows. Both tests below use these same numbers.
_RMSE = ("1.90", "1.40", "1.10")


def test_positive_control_an_unoriented_error_metric_halts_the_repo(tmp_path):
    """FIRES: the contract at economics.py:56 is load-bearing, and this is what
    happens when a binding ignores it.

    RMSE falling 1.40 -> 1.10 is a model getting better on more data. Reported
    raw, larger-is-better reads it as a curve going backwards, and the repo is
    halted for a scaling result that is in fact healthy. The check is right to
    do this: it cannot know which way a binding's metric points, so the only
    safe reading of an unoriented number is the one that stops rather than the
    one that spends. Naming the failure mode is the point — a binding author
    who sees this verdict has been told exactly what to fix.
    """
    result = _run_e1(tmp_path, _curve(*_RMSE))
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert result.evidence["gain_10_to_25"] < 0


def test_negative_control_the_same_run_oriented_is_silent(tmp_path):
    """SILENT: the identical measurement, oriented as the contract requires.

    Skill against the 1% anchor, `1 - rmse/rmse_at_1pct`, is the same three
    numbers with larger-is-better restored: 0.0 -> 0.2632 -> 0.4211. Nothing
    about the run changed; only the reporting did. The pair is what shows the
    contract is a real requirement on bindings rather than a comment.
    """
    result = _run_e1(
        tmp_path,
        """
        def scaling_probe():
            # Skill against the 1% anchor: larger is better, as the contract
            # requires the BINDING to arrange before reporting.
            rmse = {0.01: 1.90, 0.10: 1.40, 0.25: 1.10}
            anchor = rmse[0.01]
            return {frac: 1.0 - value / anchor for frac, value in rmse.items()}
        """,
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["gain_10_to_25"] > 0.01


def test_negative_control_a_negative_valued_but_oriented_metric_is_silent(tmp_path):
    """SILENT: negative log-loss is a legitimate larger-is-better metric, and
    the `abs(at10)` denominator is what keeps its gain positive. Without this,
    a repo could not report one without tripping the hard stop."""
    result = _run_e1(tmp_path, _curve("-2.40", "-2.00", "-1.20"))
    assert result.status is Status.PASS
    assert result.evidence["gain_10_to_25"] > 0.01


# -- malformed curves: NA is not PASS and not FAIL ------------------------


def test_a_missing_fraction_is_refused_by_name(tmp_path):
    """FIRES: a two-point curve cannot answer the question, and the reason says
    which point is absent rather than reporting a gain over what is there."""
    result = _run_e1(
        tmp_path,
        """
        def scaling_probe():
            return {0.10: 0.70, 0.25: 0.90}
        """,
    )
    assert result.status is Status.FAIL
    assert "0.01" in result.reason
    assert "missing fractions" in result.reason


def test_an_undeclared_binding_is_NA_rather_than_a_pass(tmp_path):
    """FIRES as NA: "no scaling probe has been run" must never render like "the
    curve was fine". A hard stop nobody measured is not a hard stop cleared."""
    result = _run_e1(tmp_path, _curve("0.4", "0.7", "0.9"), declare=False)
    assert result.status is Status.NA
    assert "no 'scaling_probe' binding declared" in result.reason


def test_a_binding_that_raises_is_a_FAIL_not_an_NA(tmp_path):
    """FIRES as FAIL: "not wired" and "wired and broken" are different distances
    from a real run and must not collapse into one another."""
    result = _run_e1(
        tmp_path,
        """
        def scaling_probe():
            raise RuntimeError("the 25% shard was never staged")
        """,
    )
    assert result.status is Status.FAIL
    assert "RuntimeError" in result.reason
    assert "never staged" in result.reason


def test_a_zero_valued_10_percent_point_halts_rather_than_dividing_by_it(tmp_path):
    """FIRES, conservatively, and the conservatism is deliberate.

    Relative gain from a zero baseline is undefined. `economics.py:58` reads
    `gain = ... if at10 else 0.0`, which sends it to the hard stop rather than
    to a ZeroDivisionError or a pass. Asserted here so the branch is pinned as
    intended behaviour rather than left as an accident of the expression.
    """
    result = _run_e1(tmp_path, _curve("0.0", "0.0", "0.9"))
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert result.evidence["gain_10_to_25"] == 0.0


# -- non-finite curves: the defect the controls found ---------------------


def test_positive_control_a_non_finite_curve_point_is_refused(tmp_path):
    """FIRES — and did not, before the repair committed alongside this file.

    Found by writing the control. `float("nan")` survives the curve parse, NaN
    is truthy so `if at10` takes the dividing branch, and `nan <= 0.01` is
    False — so a scaling probe that produced no number at 10% or 25% returns
    PASS, and the hard stop that exists to protect the GPU budget is switched
    off by a figure that does not exist. Same defect class as the R5 row-count
    guard repaired at 00210b6 and the D2 interval guard at 591e25c.
    """
    result = _run_e1(tmp_path, _curve("0.40", 'float("nan")', 'float("nan")'))
    assert result.status is Status.FAIL
    assert "finite" in result.reason
    assert "0.1" in result.reason


def test_positive_control_a_non_finite_25_percent_point_alone_is_refused(tmp_path):
    """FIRES: one missing point is enough. The gain is NaN either way, and a NaN
    gain compares False against the epsilon in both directions."""
    result = _run_e1(tmp_path, _curve("0.40", "0.70", 'float("nan")'))
    assert result.status is Status.FAIL
    assert "finite" in result.reason
    assert "0.25" in result.reason


def test_positive_control_an_infinite_curve_point_is_refused(tmp_path):
    """FIRES: an infinite score is not a score. Unguarded it yields an infinite
    gain, which sails past a flatness test looking like the best possible run."""
    result = _run_e1(tmp_path, _curve("0.40", "0.70", 'float("inf")'))
    assert result.status is Status.FAIL
    assert "finite" in result.reason


def test_positive_control_the_string_nan_is_refused_the_same_way(tmp_path):
    """FIRES: `float()` accepts the string, so a JSON round-trip that stringified
    the figure gets the same refusal rather than a different one."""
    result = _run_e1(tmp_path, _curve("0.40", '"nan"', '"nan"'))
    assert result.status is Status.FAIL
    assert "finite" in result.reason


def test_negative_control_ordinary_curves_are_untouched_by_the_finiteness_guard(tmp_path):
    """SILENT: the guard must not cost either verdict it sits in front of.

    A finiteness check written slightly wrong — applied to the wrong point, or
    before the curve is complete — turns every E1 into a FAIL, and no other test
    in this file would distinguish that from the hard stop firing correctly. So
    both live verdicts are re-asserted against the guard specifically.
    """
    flat = _run_e1(tmp_path, _curve("0.40", "0.70", "0.70"))
    rising = _run_e1(tmp_path, _curve("0.40", "0.70", "0.90"))
    assert flat.status is Status.FAIL and flat.evidence["halt"] is True
    assert "finite" not in flat.reason
    assert rising.status is Status.PASS


# -- E2: a sweep that is not logged is not evidence ------------------------


def _run_e2(tmp_path, body: str, *, declare: bool = True):
    repo = _repo(tmp_path, "hparam_sanity", "hparam_sanity", body, declare=declare)
    try:
        return e2_hparam_sanity(repo, _ctx(tmp_path))
    finally:
        repo.release()


_E2_COMPLETE = """
        def hparam_sanity():
            return {
                "lr_range": [1e-5, 3e-3],
                "throughput_curve": [[8, 120.0], [16, 210.0], [32, 340.0]],
                "winning_config": {"lr": 3e-4, "batch": 32},
                "mlflow_run_id": "a1b2c3d4",
            }
    """


def test_negative_control_a_complete_logged_sweep_is_silent(tmp_path):
    """SILENT: the shape E2 is asking for, so the refusals below mean something."""
    result = _run_e2(tmp_path, _E2_COMPLETE)
    assert result.status is Status.PASS
    assert result.evidence["throughput_points"] == 3
    assert result.evidence["mlflow_run_id"] == "a1b2c3d4"


def test_positive_control_a_sweep_with_no_mlflow_run_id_is_refused(tmp_path):
    """FIRES: the branch that matters. A sweep nobody can retrieve is a claim
    about a sweep, and it is refused even when every other field is present."""
    result = _run_e2(tmp_path, _E2_COMPLETE.replace('"a1b2c3d4"', '""'))
    assert result.status is Status.FAIL
    assert "MLflow" in result.reason
    assert "to be evidence" in result.reason


def test_positive_control_a_missing_field_is_refused_by_name(tmp_path):
    """FIRES: and names what is absent, so the verdict is actionable."""
    result = _run_e2(
        tmp_path,
        """
        def hparam_sanity():
            return {"lr_range": [1e-5, 3e-3], "mlflow_run_id": "a1b2c3d4"}
        """,
    )
    assert result.status is Status.FAIL
    assert "throughput_curve" in result.reason
    assert "winning_config" in result.reason


def test_an_undeclared_hparam_binding_is_NA(tmp_path):
    """FIRES as NA: an unrun sweep is unmeasured, not clean."""
    result = _run_e2(tmp_path, _E2_COMPLETE, declare=False)
    assert result.status is Status.NA
    assert "no 'hparam_sanity' binding declared" in result.reason


# -- E3: a utilisation number without a trace is a claim -------------------


def _run_e3(tmp_path, body: str, *, declare: bool = True):
    repo = _repo(tmp_path, "efficiency", "efficiency", body, declare=declare)
    try:
        return e3_efficiency_floor(repo, _ctx(tmp_path))
    finally:
        repo.release()


def test_negative_control_a_traced_run_above_the_floor_is_silent(tmp_path):
    """SILENT: high utilisation, with a trace behind it, passes."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.93, "profiler_trace": "s3://…/profiler/trace.json"}
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["gpu_util"] == 0.93


def test_the_efficiency_floor_is_inclusive_at_the_boundary(tmp_path):
    """SILENT at exactly the floor: the test is `util < 0.80`, so 80% passes."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.80, "profiler_trace": "trace.json"}
        """,
    )
    assert result.status is Status.PASS


def test_positive_control_a_utilisation_number_without_a_trace_is_refused(tmp_path):
    """FIRES: the branch worth having. A utilisation figure with nothing behind
    it is a claim, and it is refused at a value that would otherwise pass — so
    the refusal is of the missing trace and not of the number."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.93}
        """,
    )
    assert result.status is Status.FAIL
    assert "no profiler trace" in result.reason
    assert "is a claim" in result.reason


def test_positive_control_starved_gpu_is_refused_with_the_dataloader_remedy(tmp_path):
    """FIRES: below the floor and attributed, the remedy names storage and
    explicitly rules out a bigger instance — the whole reason E3 has a remedy
    clause rather than only a threshold."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.31, "profiler_trace": "trace.json",
                    "dataloader_bound": True}
        """,
    )
    assert result.status is Status.FAIL
    assert "FSx for Lustre" in result.reason
    assert "not a larger instance type" in result.reason
    assert result.evidence["dataloader_bound"] is True


def test_the_remedy_is_withheld_when_the_cause_is_unattributed(tmp_path):
    """FIRES, differently: the same shortfall with no attribution must not be
    told to buy storage. An unattributed cause gets "profile before changing
    anything", which is the other half of the remedy branch."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.31, "profiler_trace": "trace.json"}
        """,
    )
    assert result.status is Status.FAIL
    assert "profile before changing anything" in result.reason
    assert "FSx" not in result.reason


def test_an_undeclared_efficiency_binding_is_NA(tmp_path):
    """FIRES as NA: no measurement is not a measurement above the floor."""
    result = _run_e3(
        tmp_path,
        """
        def efficiency():
            return {"gpu_util": 0.93, "profiler_trace": "trace.json"}
        """,
        declare=False,
    )
    assert result.status is Status.NA
    assert "no 'efficiency' binding declared" in result.reason
