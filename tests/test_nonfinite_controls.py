"""The NaN-comparison defect class, swept across the checks that were not repaired with D2 and E1.

`tests/test_decision_controls.py` and `tests/test_economics_controls.py`
established that a non-finite figure switches a check off: every comparison a
NaN takes part in is False, so a threshold test written as `value > bar` or
`value < floor` is False for a value that does not exist, and the check returns
PASS. Those two files fixed D2 and E1, the two hard stops.

The class does not stop at the hard stops. Verification of that branch drove
each remaining numeric check with a non-finite measurement and found four more
that returned PASS on it, plus one that crashed:

* **T2 / R2** — `[2.0, nan]`. A loss that diverged to NaN is the most common
  way a training run fails, and it is the exact thing T2 exists to catch.
  `first <= 0` and `last > 0.1 * first` are both False for a NaN, so the
  trajectory passed. R2 delegates to T2 and inherited it verbatim.
* **D3** — `empirical = nan` passed the coverage tolerance.
* **E3** — `gpu_util = nan` cleared the 80% floor.
* **R4** — `computed = nan` reproduced its analytic answer.
* **T4** — `int(float('nan'))` raised ValueError out of the check body, so the
  check produced no verdict at all and reached the runner as a crash.

Two of these are worse than a plain NaN hole, and they are the reason this file
tests tolerances separately from measurements. **`min(nan, x)` returns `nan` in
Python.** Both D3 and R4 clamp a subject-declared tolerance with
`min(declared, MAX)` precisely so a binding can ask for something stricter but
never looser. A declared tolerance of NaN walks straight through that clamp and
becomes the loosest tolerance there is — a subject setting its own pass mark to
"accept anything", using the mechanism written to stop it. The clamp is
exercised in both directions in the existing control files, and neither
direction is a NaN, so nothing caught it.

Every check below gets both halves. A test proving only firing is not coverage:
a guard that refuses everything is as broken as one that refuses nothing, and
the negative controls here are the ordinary finite cases that must stay silent.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import d3_uncertainty_coverage
from resilient_mlkit.checks.economics import e3_efficiency_floor
from resilient_mlkit.checks.readiness import r2_overfit, r4_metric_known_answer
from resilient_mlkit.checks.triage import t2_overfit_one_batch, t4_label_counts
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py. Two
#: repos naming their adapter module the same thing is the collision
#: `Repo.release()` exists for.
_SERIAL = iter(range(10_000))


def _run(tmp_path, check, binding: str, body: str):
    """Resolve `binding` through the real `.mlkit/repo.toml` path, then run `check`."""
    module = f"nf_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mlkit" / "repo.toml").write_text(
        f'[repo]\nname = "fixturerepo"\n\n[bindings]\n{binding} = "{module}:{binding}"\n'
    )
    repo = Repo(name="fixturerepo", path=tmp_path)
    try:
        return check(repo, RunContext(nonce="test-nonce", root=tmp_path, offline=True))
    finally:
        repo.release()


# -- T2 / R2: a loss that diverged is not a loss that collapsed -----------


def _losses(values: str) -> str:
    return f"""
        def overfit_one_batch():
            return [{values}]
    """


def _run_t2(tmp_path, values: str):
    return _run(tmp_path, t2_overfit_one_batch, "overfit_one_batch", _losses(values))


def test_negative_control_a_finite_collapsing_loss_is_untouched_by_the_guard(tmp_path):
    """SILENT: the guard must not disturb the ordinary passing trajectory."""
    result = _run_t2(tmp_path, "2.0, 0.2")
    assert result.status is Status.PASS
    assert result.evidence["loss_last"] == 0.2


def test_negative_control_a_finite_stalled_loss_still_fires_for_its_own_reason(tmp_path):
    """SILENT (as a finiteness guard): a stalled loss fails on the ratio bar, not on finiteness."""
    result = _run_t2(tmp_path, "2.0, 0.21")
    assert result.status is Status.FAIL
    assert "< 10x" in result.reason
    assert "not finite" not in result.reason


def test_positive_control_a_loss_that_diverged_to_nan_is_refused(tmp_path):
    """FIRES: `nan > 0.1 * 2.0` is False, so [2.0, nan] returned PASS before this guard.

    This is the headline case of the class. A NaN loss is what a training run
    reports when it diverges, and T2 is the check whose entire job is to notice
    that the model cannot drive one batch down.
    """
    result = _run_t2(tmp_path, "2.0, float('nan')")
    assert result.status is Status.FAIL
    assert "not finite" in result.reason
    assert "loss_last" in result.reason


def test_positive_control_a_loss_that_was_nan_from_the_first_step_is_refused(tmp_path):
    """FIRES, naming BOTH ends: `first <= 0` is also False for a NaN."""
    result = _run_t2(tmp_path, "float('nan'), float('nan')")
    assert result.status is Status.FAIL
    assert "loss_first" in result.reason
    assert "loss_last" in result.reason


def test_positive_control_an_infinite_loss_is_refused_as_non_finite(tmp_path):
    """FIRES: an infinite loss did fail before, but on the ratio bar, which read it as "barely moved".

    It is the same defect — a figure that does not exist — and it is now named
    as one rather than being described as a trajectory that did not fall enough.
    """
    result = _run_t2(tmp_path, "2.0, float('inf')")
    assert result.status is Status.FAIL
    assert "not finite" in result.reason


def test_positive_control_the_string_nan_is_refused_the_same_way(tmp_path):
    """FIRES: `float("nan")` is how a NaN arrives from CSV, JSON or a log line."""
    result = _run_t2(tmp_path, "2.0, 'nan'")
    assert result.status is Status.FAIL
    assert "not finite" in result.reason


def test_the_nan_refusal_travels_through_R2_delegation(tmp_path):
    """FIRES under R2's identity: R2 delegates to T2, so it inherited the hole and the repair."""
    result = _run(tmp_path, r2_overfit, "overfit_one_batch", _losses("2.0, float('nan')"))
    assert result.status is Status.FAIL
    assert result.check_id == "R2"
    assert result.phase == "readiness"
    assert "not finite" in result.reason


def test_negative_control_a_passing_trajectory_still_passes_through_R2(tmp_path):
    """SILENT under R2: the delegation carries a PASS as faithfully as a FAIL."""
    result = _run(tmp_path, r2_overfit, "overfit_one_batch", _losses("2.0, 0.2"))
    assert result.status is Status.PASS
    assert result.check_id == "R2"


# -- T4: a count that is not a whole number is a finding, not a crash -----


def _run_t4(tmp_path, body: str):
    return _run(tmp_path, t4_label_counts, "label_counts", body)


def test_negative_control_ordinary_label_counts_are_silent(tmp_path):
    """SILENT: real counts still total and pass."""
    result = _run_t4(tmp_path, "def label_counts():\n    return {'a': 10, 'b': 4}\n")
    assert result.status is Status.PASS
    assert result.evidence["total"] == 14


def test_positive_control_a_nan_label_count_is_a_named_failure_not_a_crash(tmp_path):
    """FIRES: `int(float('nan'))` raised ValueError straight out of the check body.

    The runner's blanket handler turned that into a FAIL carrying a traceback in
    the reason field, so it did fail closed — but a check that dies of its input
    has not diagnosed it, and a traceback in a reason sets the column width for
    the whole portfolio table.
    """
    result = _run_t4(tmp_path, "def label_counts():\n    return {'a': float('nan')}\n")
    assert result.status is Status.FAIL
    assert "not a whole count" in result.reason
    assert "Traceback" not in result.reason


def test_negative_control_an_all_zero_count_still_fires_for_its_own_reason(tmp_path):
    """SILENT (as a finiteness guard): zero counts fail on emptiness, not on the new branch."""
    result = _run_t4(tmp_path, "def label_counts():\n    return {'a': 0}\n")
    assert result.status is Status.FAIL
    assert "every observed-label count is zero" in result.reason


# -- D3: coverage, and the tolerance clamp a NaN defeats ------------------


def _coverage(fields: str) -> str:
    return f"""
        def coverage():
            return {{{fields}}}
    """


def _run_d3(tmp_path, fields: str):
    return _run(tmp_path, d3_uncertainty_coverage, "coverage", _coverage(fields))


def test_negative_control_finite_matching_coverage_is_untouched_by_the_guard(tmp_path):
    """SILENT: the ordinary passing case."""
    result = _run_d3(tmp_path, "'nominal': 0.90, 'empirical': 0.90, 'n': 200")
    assert result.status is Status.PASS


def test_positive_control_a_non_finite_empirical_coverage_is_refused(tmp_path):
    """FIRES: `abs(nan - 0.90) > 0.05` is False, so unmeasured coverage passed."""
    result = _run_d3(tmp_path, "'nominal': 0.90, 'empirical': float('nan'), 'n': 200")
    assert result.status is Status.FAIL
    assert "non-finite" in result.reason
    assert "empirical" in result.reason


def test_positive_control_a_non_finite_nominal_coverage_is_refused(tmp_path):
    """FIRES: the nominal side is a figure too, and it was equally unguarded."""
    result = _run_d3(tmp_path, "'nominal': float('nan'), 'empirical': 0.90, 'n': 200")
    assert result.status is Status.FAIL
    assert "nominal" in result.reason


def test_positive_control_a_nan_tolerance_cannot_defeat_the_coverage_clamp(tmp_path):
    """FIRES: `min(nan, MAX_COVERAGE_TOL)` is nan, so a NaN tol is the loosest tol there is.

    The clamp exists so a binding may ask for something stricter but never
    looser. This is the input that inverted it, using the clamp itself. The
    coverage here (0.10 against a nominal 0.90) misses by 0.80 and must fail.
    """
    result = _run_d3(
        tmp_path, "'nominal': 0.90, 'empirical': 0.10, 'n': 200, 'tol': float('nan')"
    )
    assert result.status is Status.FAIL
    assert "non-finite tol" in result.reason


def test_negative_control_a_stricter_finite_tolerance_is_still_honoured(tmp_path):
    """SILENT as a finiteness refusal: a real stricter tol still works and still fires on its own terms."""
    result = _run_d3(
        tmp_path, "'nominal': 0.90, 'empirical': 0.905, 'n': 200, 'tol': 0.001"
    )
    assert result.status is Status.FAIL
    assert "non-finite" not in result.reason
    assert result.evidence["tol"] == 0.001


# -- E3: the utilisation floor -------------------------------------------


def _run_e3(tmp_path, fields: str):
    return _run(
        tmp_path, e3_efficiency_floor, "efficiency",
        f"def efficiency():\n    return {{{fields}}}\n",
    )


def test_negative_control_a_finite_utilisation_above_the_floor_is_silent(tmp_path):
    """SILENT: the ordinary passing case is undisturbed."""
    result = _run_e3(tmp_path, "'gpu_util': 0.95, 'profiler_trace': 's3://b/t.json'")
    assert result.status is Status.PASS


def test_negative_control_a_finite_utilisation_below_the_floor_fires_on_the_floor(tmp_path):
    """SILENT as a finiteness refusal: a real low number still fails for the floor's own reason."""
    result = _run_e3(tmp_path, "'gpu_util': 0.40, 'profiler_trace': 's3://b/t.json'")
    assert result.status is Status.FAIL
    assert "below the 80% floor" in result.reason
    assert "non-finite" not in result.reason


def test_positive_control_a_non_finite_utilisation_is_refused(tmp_path):
    """FIRES: `nan < 0.80` is False, so a profiler that reported nothing cleared the floor."""
    result = _run_e3(tmp_path, "'gpu_util': float('nan'), 'profiler_trace': 's3://b/t.json'")
    assert result.status is Status.FAIL
    assert "non-finite gpu_util" in result.reason


# -- R4: known answers, and the tolerance clamp a NaN defeats -------------


def _cases(body: str) -> str:
    return f"""
        def metric_known_answer():
            return [{body}]
    """


def _run_r4(tmp_path, body: str):
    return _run(tmp_path, r4_metric_known_answer, "metric_known_answer", _cases(body))


def test_negative_control_a_metric_reproducing_its_answer_is_untouched_by_the_guard(tmp_path):
    """SILENT: the ordinary passing case."""
    result = _run_r4(tmp_path, "{'name': 'rmse', 'computed': 1.0, 'expected': 1.0}")
    assert result.status is Status.PASS
    assert result.evidence["failed"] == 0


def test_positive_control_a_non_finite_computed_metric_is_refused(tmp_path):
    """FIRES: `abs(nan - 1.0) > tol` is False, so a metric that computed nothing reproduced its answer."""
    result = _run_r4(tmp_path, "{'name': 'rmse', 'computed': float('nan'), 'expected': 1.0}")
    assert result.status is Status.FAIL
    assert "not finite" in result.reason


def test_positive_control_a_non_finite_expected_value_is_refused(tmp_path):
    """FIRES: an analytic answer that is not a number is not a known answer."""
    result = _run_r4(tmp_path, "{'name': 'rmse', 'computed': 1.0, 'expected': float('nan')}")
    assert result.status is Status.FAIL
    assert "not finite" in result.reason


def test_positive_control_a_nan_tolerance_cannot_defeat_the_metric_clamp(tmp_path):
    """FIRES: same `min(nan, MAX_METRIC_TOL)` inversion as D3, on a case that misses by 4.0."""
    result = _run_r4(
        tmp_path,
        "{'name': 'rmse', 'computed': 5.0, 'expected': 1.0, 'tol': float('nan')}",
    )
    assert result.status is Status.FAIL
    assert "declared tol is not finite" in result.reason


def test_negative_control_a_declared_tolerance_of_zero_is_finite_and_honoured(tmp_path):
    """SILENT as a finiteness refusal: 0.0 is a legitimate, maximally strict tolerance.

    Worth pinning separately because 0.0 is falsy, and a guard written as
    `if not declared_tol` rather than `if not math.isfinite(declared_tol)`
    would reject the strictest tolerance a binding can ask for.
    """
    result = _run_r4(
        tmp_path, "{'name': 'rmse', 'computed': 1.0, 'expected': 1.0, 'tol': 0.0}"
    )
    assert result.status is Status.PASS


def test_negative_control_a_finite_disagreement_still_fires_for_its_own_reason(tmp_path):
    """SILENT as a finiteness refusal: a real disagreement still reports as a disagreement."""
    result = _run_r4(tmp_path, "{'name': 'rmse', 'computed': 2.0, 'expected': 1.0}")
    assert result.status is Status.FAIL
    assert "got 2, expected 1" in result.reason
    assert "not finite" not in result.reason
