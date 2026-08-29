"""R5 controls: does the provenance gate fire when it should, and stay silent when it should not.

R5 carries the one invariant CLAUDE.md calls non-negotiable: not a single
synthetic, simulated or formula-derived row in `val` or `test`. It is the check
standing between a model scored against a target it computed from its own
inputs and a promotion, so its silence is the failure mode that matters —
a fabricated evaluation reads exactly like a real one once R5 has passed it.

Every control here is paired, and one pairing carries most of the weight:

* **a synthetic row in `val` FIRES / a synthetic row in `train` is SILENT.**
  Synthetic training data is legitimate and common. A check that fired on it
  would be turned off inside a week, and the invariant would go with it. The
  pair is what says R5 is a statement about the evaluation splits specifically,
  rather than a blanket objection to simulation.

* **a non-`real` kind with a positive count FIRES / the same kind at zero is
  SILENT.** Repos report their provenance histogram with the kinds they track,
  present or not. Firing on a declared-but-empty `synthetic: 0` would make the
  check punish honest bookkeeping.

Two cases here were found by writing the controls rather than by reading the
check — a fractional count and a negative one. See their docstrings.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import r5_data_provenance
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))


def _prov_repo(tmp_path, body: str, *, declare: bool = True) -> Repo:
    """A repo on disk whose `provenance` binding is `body`."""
    module = f"r5_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\nprovenance = "{module}:provenance"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _run(tmp_path, body: str, *, declare: bool = True):
    repo = _prov_repo(tmp_path, body, declare=declare)
    try:
        return r5_data_provenance(repo, _ctx(tmp_path))
    finally:
        repo.release()


def _binding(train: str, val: str, test: str) -> str:
    return f"""
        def provenance():
            return {{"train": {train}, "val": {val}, "test": {test}}}
    """


CLEAN_TRAIN = '{"real": 800, "synthetic": 0}'
CLEAN_VAL = '{"real": 100, "synthetic": 0}'
CLEAN_TEST = '{"real": 100, "synthetic": 0}'


# -- the invariant: FIRES on a tainted holdout, SILENT on a tainted train --


def test_positive_control_one_synthetic_row_in_val_is_refused(tmp_path):
    """FIRES: one row is the threshold, because the invariant is absolute."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 100, "synthetic": 1}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert result.evidence["tainted"] == {"val": {"synthetic": 1}}
    assert "cannot be believed" in result.reason


def test_positive_control_a_derived_row_in_test_is_refused(tmp_path):
    """FIRES: any kind that is not `real`, not only the one spelled `synthetic`."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, CLEAN_VAL, '{"real": 100, "formula_derived": 4}'),
    )
    assert result.status is Status.FAIL
    assert result.evidence["tainted"] == {"test": {"formula_derived": 4}}


def test_negative_control_a_wholly_synthetic_train_split_is_silent(tmp_path):
    """SILENT: the control the whole invariant depends on being usable.

    Simulated training data is legitimate. If R5 fired here it would be
    switched off, and the val/test invariant would be switched off with it.
    """
    result = _run(
        tmp_path,
        _binding('{"real": 0, "synthetic": 5000}', CLEAN_VAL, CLEAN_TEST),
    )
    assert result.status is Status.PASS
    assert result.evidence["train"] == {"real": 0, "synthetic": 5000}


def test_negative_control_a_declared_kind_at_zero_is_silent(tmp_path):
    """SILENT: `synthetic: 0` is honest bookkeeping, not a tainted split."""
    result = _run(
        tmp_path,
        _binding(
            CLEAN_TRAIN,
            '{"real": 100, "synthetic": 0, "simulated": 0, "derived": 0}',
            CLEAN_TEST,
        ),
    )
    assert result.status is Status.PASS


def test_negative_control_a_holdout_of_only_real_rows_is_silent(tmp_path):
    """SILENT: the shape a repo is trying to reach. PASS carries the histogram."""
    result = _run(tmp_path, _binding(CLEAN_TRAIN, CLEAN_VAL, CLEAN_TEST))
    assert result.status is Status.PASS
    assert result.evidence["val"] == {"real": 100, "synthetic": 0}
    assert result.evidence["test"] == {"real": 100, "synthetic": 0}


def test_positive_control_a_holdout_with_no_real_rows_is_refused(tmp_path):
    """FIRES: an empty val is vacuously untainted, and measures nothing."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 0, "synthetic": 0}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "zero real rows" in result.reason


# -- counts must be counts ------------------------------------------------


def test_positive_control_a_fractional_synthetic_count_is_refused(tmp_path):
    """FIRES: a provenance histogram reported as proportions must not pass.

    Found by writing this control. R5 tested `int(n) > 0`, and `int()`
    truncates: measured against the check as it stood at 89e0ccf, the binding
    below reported PASS on a `val` that is one third simulated, because
    `int(0.5) == 0` cleared the taint test and `int(1.5) == 1` then satisfied
    the "at least one real row" test.

    The plausible route in is a repo reporting fractions rather than row counts
    — a difference in units that no other check would notice, and that turns
    the one non-negotiable invariant in the repo into a no-op.
    """
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 1.5, "synthetic": 0.5}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "val" in result.reason


def test_positive_control_a_negative_count_is_refused(tmp_path):
    """FIRES: a count below zero is a broken counter, and R5 read it as clean.

    Same root as the fractional case: `-5 > 0` is False, so a `val` reporting
    minus five synthetic rows was untainted by arithmetic. Measured at 89e0ccf,
    the binding below reported PASS.
    """
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 100, "synthetic": -5}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "synthetic" in result.reason


def test_negative_control_an_integral_count_written_as_a_float_is_accepted(tmp_path):
    """SILENT: `100.0` rows is one hundred rows; the guard is about units, not types.

    Pairs with the fractional control above. Without this, the fix could have
    been "reject anything that is not an int", which would fire on every repo
    whose counter comes back out of a dataframe as a float64.
    """
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 100.0, "synthetic": 0.0}', CLEAN_TEST),
    )
    assert result.status is Status.PASS
    assert result.evidence["val"] == {"real": 100.0, "synthetic": 0.0}


def test_negative_control_a_count_written_as_a_digit_string_is_accepted(tmp_path):
    """SILENT: a count read out of JSON or a CSV cell arrives as text."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": "100", "synthetic": "0"}', CLEAN_TEST),
    )
    assert result.status is Status.PASS


def test_positive_control_a_count_that_is_not_a_number_is_refused(tmp_path):
    """FIRES: and as a diagnosis, not as an unhandled traceback."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 100, "synthetic": "some"}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "synthetic" in result.reason


# -- unmeasured vs. broken: these must not collapse -----------------------


def test_negative_control_no_declared_binding_is_NA_and_never_a_pass(tmp_path):
    """SILENT as a verdict, loud as a gap. NA is never 'would have failed'."""
    result = _run(tmp_path, "def provenance():\n    return {}\n", declare=False)
    assert result.status is Status.NA
    assert "no 'provenance' binding declared" in result.reason


def test_positive_control_a_binding_that_raises_is_FAIL_not_NA(tmp_path):
    """FIRES: a provenance ledger that will not load is a repo defect."""
    result = _run(
        tmp_path,
        """
        def provenance():
            raise ValueError("provenance ledger not written for this run")
        """,
    )
    assert result.status is Status.FAIL
    assert "ValueError" in result.reason


def test_positive_control_a_missing_split_is_reported_by_name(tmp_path):
    """FIRES: a provenance report with no `test` entry cannot clear `test`."""
    result = _run(
        tmp_path,
        """
        def provenance():
            return {"train": {"real": 800}, "val": {"real": 100}}
        """,
    )
    assert result.status is Status.FAIL
    assert "provenance missing splits: test" in result.reason


def test_positive_control_an_empty_provenance_report_is_never_a_pass(tmp_path):
    """FIRES: nothing declared is not the same as nothing synthetic."""
    result = _run(tmp_path, "def provenance():\n    return {}\n")
    assert result.status is Status.FAIL
    assert "missing splits" in result.reason


# -- the same defect class, one step further out ---------------------------
#
# The guard above reads a count with `float(raw)` and then tests
# `n != int(n)`. `float("nan")`, `float("inf")` and the strings "nan"/"inf"
# all SURVIVE the `float()` call, so they reach `int(n)` -- which raises
# ValueError for NaN and OverflowError for an infinity, out of the check and
# past its own diagnosis. That is the exact shape the guard was written to
# close: the check stops naming the split and kind at fault and names an
# interpreter error instead.
#
# It is not hypothetical arithmetic. NaN is what a pandas/numpy count produces
# when a groupby or a reindex misses a kind, and this fleet already uses
# float('nan') as an explicit "could not read this figure" sentinel -- see
# `absent_metric_encoding` in resilient-blackout's
# reports/train/weather_failure_all_in_scope_gate.json. A provenance histogram
# arriving with a NaN in it is a live shape here.
#
# A raising check is converted to FAIL by the CLI runner, so no false PASS was
# ever reachable through this path. The defect is in the reason: "unmeasured"
# has to be sayable about a count, and an unhandled OverflowError does not say
# it.


def test_positive_control_a_NaN_count_is_refused_by_name_not_by_traceback(tmp_path):
    """FIRES: and as a diagnosis. NaN is the shape a missing groupby key takes."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": float("nan"), "synthetic": 0}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "val" in result.reason and "real" in result.reason
    assert "ValueError" not in result.reason


def test_positive_control_an_infinite_count_is_refused_by_name(tmp_path):
    """FIRES: an infinity is not a row count either, and must not overflow out."""
    result = _run(
        tmp_path,
        _binding(CLEAN_TRAIN, '{"real": 100, "synthetic": float("inf")}', CLEAN_TEST),
    )
    assert result.status is Status.FAIL
    assert "val" in result.reason and "synthetic" in result.reason
    assert "OverflowError" not in result.reason


def test_positive_control_the_string_nan_is_refused_by_name(tmp_path):
    """FIRES: `float("nan")` succeeds on the string too, so a CSV cell reaches int()."""
    result = _run(tmp_path, _binding(CLEAN_TRAIN, '{"real": "nan"}', CLEAN_TEST))
    assert result.status is Status.FAIL
    assert "val" in result.reason and "real" in result.reason
    assert "ValueError" not in result.reason


def test_negative_control_a_large_finite_count_is_still_silent(tmp_path):
    """SILENT: the pair. The refusal must be of non-finiteness, not of magnitude.

    Without this, "reject anything float() cannot round-trip" would be
    satisfied by a guard that also rejected a legitimately large corpus.
    """
    result = _run(
        tmp_path,
        _binding('{"real": 10_000_000_000}', '{"real": 1_000_000}', '{"real": 1_000_000}'),
    )
    assert result.status is Status.PASS
