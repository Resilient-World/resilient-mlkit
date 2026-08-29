"""R3 controls: does the holdout gate fire when it should, and stay silent when it should not.

R3 is one of four checks whose silence is the whole risk. If it reports PASS on
a split that leaks, every number downstream of it is measured against data the
model has seen, and nothing later in the pipeline can recover that. So each
control here comes in a pair: a FIRES case built from the shape of the leak,
and a SILENT case built from the shape that is legitimate and must not be
reported.

The pairing is the point. A check that fails everything is as useless as one
that fails nothing, and only the pair tells them apart. In particular:

* leakage FIRES / disjointness SILENT — the check's stated job;
* a one-group holdout FIRES / a two-group holdout SILENT — the floor exists
  because narrowing the holdout is the cheapest way to turn an R3 FAIL green,
  and that is holdout narrowing (CLAUDE.md rule 6) arriving as a passing check;
* an undeclared binding is NA / a declared one that raises is FAIL — these must
  not collapse into each other. "This repo has not wired splits yet" and "this
  repo's split loader is broken" are different distances from a real run, and a
  portfolio table that renders them identically cannot say which.

One case here is a defect found by writing the control rather than by reading
the code: `test_positive_control_a_split_given_as_a_bare_string_is_refused`.
See the docstring on that test.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import MIN_HOLDOUT_GROUPS, r3_blocked_splits
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

#: Bumped per fixture so no two tests share a module in `sys.modules`. Two
#: repos both naming their adapter `mlkit_bindings` is the exact collision
#: `Repo.release()` exists for, and a test suite that reintroduces it would be
#: measuring the first fixture's splits under the second fixture's name.
_SERIAL = iter(range(10_000))


def _splits_repo(tmp_path, body: str, *, declare: bool = True) -> Repo:
    """A repo on disk whose `splits` binding is `body`.

    `body` is the source of a function named `splits`, dedented and written
    into a uniquely-named module, so the check resolves and calls it exactly
    the way it resolves the eight real repos' adapters.
    """
    module = f"r3_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\nsplits = "{module}:splits"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _run(tmp_path, body: str, *, declare: bool = True):
    repo = _splits_repo(tmp_path, body, declare=declare)
    try:
        return r3_blocked_splits(repo, _ctx(tmp_path))
    finally:
        repo.release()


# -- leakage: FIRES / SILENT ----------------------------------------------


def test_positive_control_a_group_in_train_and_test_is_reported(tmp_path):
    """FIRES: the leak R3 exists for. A site trained on cannot also score it."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ["site_a", "site_b", "site_c"],
                "val": ["site_d", "site_e"],
                "test": ["site_f", "site_a"],
            }
        """,
    )
    assert result.status is Status.FAIL
    assert "train&test" in result.reason
    assert result.evidence["overlaps"] == {"train&test": 1}


def test_positive_control_a_group_shared_by_val_and_test_is_reported(tmp_path):
    """FIRES: selection and reporting on the same site is still a leak."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ["a", "b"],
                "val": ["c", "d"],
                "test": ["d", "e"],
            }
        """,
    )
    assert result.status is Status.FAIL
    assert result.evidence["overlaps"] == {"val&test": 1}


def test_negative_control_three_disjoint_splits_are_silent(tmp_path):
    """SILENT: the legitimate shape. Without this, the controls above prove nothing."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ["a", "b", "c"],
                "val": ["d", "e"],
                "test": ["f", "g"],
            }
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence == {"n_train": 3, "n_val": 2, "n_test": 2}


def test_negative_control_a_group_repeated_inside_one_split_is_not_a_leak(tmp_path):
    """SILENT: a duplicate within a split is a loader quirk, not shared data."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ["a", "a", "b", "c"],
                "val": ["d", "e"],
                "test": ["f", "g"],
            }
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["n_train"] == 3


def test_negative_control_similar_but_distinct_group_names_are_not_a_leak(tmp_path):
    """SILENT: `site_a1` and `site_a2` share a prefix and share no data."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ["site_a1", "site_a2"],
                "val": ["site_a3", "site_a4"],
                "test": ["site_a5", "site_a6"],
            }
        """,
    )
    assert result.status is Status.PASS


# -- the holdout floor: FIRES / SILENT ------------------------------------


def test_positive_control_a_single_group_holdout_is_refused(tmp_path):
    """FIRES: disjoint but uninformative — the cheapest way to fake an R3 pass."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": ["a", "b", "c"], "val": ["d"], "test": ["e", "f"]}
        """,
    )
    assert result.status is Status.FAIL
    assert "holdout too thin" in result.reason
    assert result.evidence["min_holdout_groups"] == MIN_HOLDOUT_GROUPS
    # The failure must name the split, or the reader cannot act on it.
    assert "val has 1 group" in result.reason


def test_negative_control_a_two_group_holdout_is_at_the_floor_and_silent(tmp_path):
    """SILENT: two is thin and it is the floor, so it must not be reported.

    This pair is what makes the floor a floor rather than a preference. If the
    check fired at two as well, the constant would be unfalsifiable from
    outside.
    """
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": ["a", "b"], "val": ["c", "d"], "test": ["e", "f"]}
        """,
    )
    assert result.status is Status.PASS
    assert MIN_HOLDOUT_GROUPS == 2


def test_positive_control_an_empty_train_split_is_refused(tmp_path):
    """FIRES: nothing was trained on, so nothing downstream means anything."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": [], "val": ["c", "d"], "test": ["e", "f"]}
        """,
    )
    assert result.status is Status.FAIL
    assert "empty" in result.reason


# -- a bare string is not a set of groups ---------------------------------


def test_positive_control_a_split_given_as_a_bare_string_is_refused(tmp_path):
    """FIRES: a string split must never be character-split into groups.

    Found by writing this control, not by reading the check. R3 built its group
    sets with `set(map(str, v))`, which accepts a string and iterates it by
    CHARACTER. Measured against the check as it stood before this commit, the
    binding below returned three short disjoint strings and R3 reported PASS
    with `n_train=3, n_val=2, n_test=2` — three "groups" that are the letters
    of the word `abc`. Nothing about the data had been measured, and the pass
    was indistinguishable from a real one.

    It is a silence rather than a crash, which is what makes it worth a control:
    a longer or overlapping set of strings (paths, say) would have shared
    characters and FAILED loudly, so the defect only shows itself on the inputs
    where it does the damage.
    """
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": "abc", "val": "de", "test": "fg"}
        """,
    )
    assert result.status is Status.FAIL
    assert "str" in result.reason
    assert "train" in result.reason


def test_negative_control_a_tuple_or_set_of_groups_is_accepted(tmp_path):
    """SILENT: the guard must reject strings only, not every non-list container."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {
                "train": ("a", "b"),
                "val": {"c", "d"},
                "test": (g for g in ["e", "f"]),
            }
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence == {"n_train": 2, "n_val": 2, "n_test": 2}


def test_negative_control_group_ids_that_are_numbers_are_accepted(tmp_path):
    """SILENT: several repos key groups by integer site id, and that is fine."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": [1, 2, 3], "val": [4, 5], "test": [6, 7]}
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["n_train"] == 3


# -- unmeasured vs. broken: these must not collapse -----------------------


def test_negative_control_no_declared_binding_is_NA_and_never_a_pass(tmp_path):
    """SILENT as a verdict, loud as a gap: unmeasured is not clean."""
    result = _run(tmp_path, "def splits():\n    return {}\n", declare=False)
    assert result.status is Status.NA
    assert "no 'splits' binding declared" in result.reason


def test_positive_control_a_binding_that_raises_is_FAIL_not_NA(tmp_path):
    """FIRES: a broken split loader is a repo defect, not an unmeasurable environment.

    Reported as FAIL deliberately. Rendering it NA would let a repo whose
    dataloader does not run sit in the same column as one that simply has no
    GPU, and the portfolio's whole job is to keep those apart.
    """
    result = _run(
        tmp_path,
        """
        def splits():
            raise RuntimeError("group index not built")
        """,
    )
    assert result.status is Status.FAIL
    assert "RuntimeError" in result.reason
    assert "group index not built" in result.reason


def test_positive_control_a_missing_split_is_reported_by_name(tmp_path):
    """FIRES: two splits is not a blocked split, however disjoint they are."""
    result = _run(
        tmp_path,
        """
        def splits():
            return {"train": ["a", "b"], "val": ["c", "d"]}
        """,
    )
    assert result.status is Status.FAIL
    assert "splits missing: test" in result.reason
