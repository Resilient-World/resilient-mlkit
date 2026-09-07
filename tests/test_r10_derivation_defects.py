"""E-M41 — the two mechanical defects that let non-metrics into the registry.

Both were found by reading the derivation rather than by reading the names, and
both are stated as facts about the AST rather than as rules about spelling.

D1 — NESTED-SCOPE LEAKAGE. ``_computes_a_figure`` collected a function's
returns and derived locals with ``ast.walk(fn)``, which descends into nested
``def``s and lambdas, so an outer function was credited with arithmetic
belonging to an inner one. ``resilient-arabica``'s
``scripts/val_predictions_group_interval.py:52 main(path) -> int`` does no
arithmetic in its own body; the ``skill()`` it defines does. That is how the
NAME ``main`` entered arabica's registry, and how the process exit status at
``src/validation/run_validate.py:577`` became an R10 finding. ``resilient-torrent``
had the same row from ``scripts/hydrology/run_basin_allocation_conformal.py:1197``.

D2 — A PATH JOIN READ AS DIVISION. ``_ARITHMETIC`` contains ``ast.Div`` and
``pathlib`` spells joining with the same operator.
``resilient-chokepoint``'s ``src/resilient_chokepoint/data/ingest/base.py:69
fetch()`` entered the registry entirely through
``self.cache_dir / f"{key}.json"``, and its ``except``-branch ``0`` at
``scripts/verify_d4_checkpoint_licences.py:133`` became an R10 finding.

Scoping ALONE would have cost real recall, so it is not scoping alone: a
function that RETURNS what a nested helper computed still derives its name.
That is also what separates ``e_value`` from ``main`` — ``main`` calls its
helper and then returns an exit code.
"""

from __future__ import annotations

import ast

from resilient_mlkit.core import metric_registry

_derive = metric_registry._names_in


def _names(source: str) -> set[str]:
    return set(_derive(source, "<t>"))


# --- D1 -------------------------------------------------------------------

#: arabica's shape, reduced: an argparse main that defines a scoring helper,
#: calls it, and returns an exit status.
_CLI_MAIN = '''
def main(path: str) -> int:
    payload = load(path)

    def skill(idx):
        rm = rmse(idx)
        rq = rmse_ref(idx)
        return float(1.0 - rm / rq)

    point = skill(all_of(payload))
    write(point)
    return 0
'''

#: The recall D1 must NOT cost: arabica's ``e_value``, reduced. The arithmetic
#: is in a nested helper and the return is BUILT FROM the helper's output.
_DELEGATING_METRIC = '''
def e_value(estimate, se):
    def _e_from_effect(effect):
        rr = exp(max(effect, 0.0) / 1.0)
        return rr + sqrt(rr * (rr - 1.0))

    return Result(point=_e_from_effect(estimate), ci=_e_from_effect(se))
'''


def test_d1_a_cli_main_no_longer_derives_a_metric_name() -> None:
    assert "main" not in _names(_CLI_MAIN)


def test_d1_control_the_nested_helper_still_derives_its_own_name() -> None:
    """The scoping removes a false attribution, not the coverage."""
    assert "skill" in _names(_CLI_MAIN)


def test_d1_a_function_that_returns_what_its_helper_computed_keeps_its_name() -> None:
    names = _names(_DELEGATING_METRIC)
    assert "evalue" in names
    assert "efromeffect" in names


def test_d1_calling_a_helper_is_not_enough_returning_its_value_is() -> None:
    """The whole difference between `e_value` and `main`, in one pair."""
    calls_only = '''
def report(a, b):
    def ratio(x, y):
        return x / y
    value = ratio(a, b)
    write(value)
    return 0
'''
    returns_it = '''
def report(a, b):
    def ratio(x, y):
        return x / y
    value = ratio(a, b)
    return value
'''
    assert "report" not in _names(calls_only)
    assert "report" in _names(returns_it)


# --- D2 -------------------------------------------------------------------

_PATH_JOIN = '''
def fetch(self, force=False):
    out = self.cache_dir / f"{self.key}.json"
    return out
'''

_PATH_JOIN_PLAIN_STRING = '''
def report_path(root, name):
    return root / "reports" / name
'''

_REAL_DIVISION = '''
def hit_rate(hits, total):
    return hits / total
'''


def test_d2_a_path_join_with_an_fstring_is_not_arithmetic() -> None:
    assert "fetch" not in _names(_PATH_JOIN)


def test_d2_a_path_join_with_a_string_literal_is_not_arithmetic() -> None:
    assert "reportpath" not in _names(_PATH_JOIN_PLAIN_STRING)


def test_d2_control_real_division_is_still_arithmetic() -> None:
    """The predicate must not be "any `/` is a path"."""
    assert "hitrate" in _names(_REAL_DIVISION)


def test_d2_the_predicate_is_a_type_fact_not_a_name_heuristic() -> None:
    """`REPO_ROOT / path`, both sides plain names, is NOT caught. Stated limit.

    Widening to "an operand whose name looks path-ish" would be exactly the
    spelling rule E-038 established does not converge. This test fails the day
    that changes, so the disclosure in `core/metric_registry.py` gets updated
    rather than the behaviour drifting.
    """
    source = '''
def resolved(path):
    return REPO_ROOT / path
'''
    assert "resolved" in _names(source)


# --- the anchor still runs ------------------------------------------------


def test_the_derivation_anchor_survives_both_repairs() -> None:
    """`_PROBE` is what says the derivation is running at all (E-038).

    Both repairs touch the exact code path the probe goes through, so a probe
    that stopped coming back would mean the registry had quietly emptied and
    R10 had fallen back to the word list.
    """
    assert metric_registry._anchor_failure() is None
    assert metric_registry._PROBE_EXPECTED <= _names(metric_registry._PROBE)


def test_own_body_does_not_descend_into_a_lambda_either() -> None:
    tree = ast.parse("def f(a):\n    g = lambda x: x / a\n    return 0\n")
    fn = tree.body[0]
    assert not any(
        isinstance(n, ast.BinOp) for n in metric_registry._own_body(fn)
    )
