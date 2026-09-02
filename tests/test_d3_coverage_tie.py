"""D3's coverage evidence must tie to a row set (E-M23 residual 2).

The escalation, on `main` at `6921e9a`, verbatim:

    with an honest committed 0.90, a binding returning
    {"nominal": 0.90, "empirical": 0.90, "n": 1000000} PASSes, and nothing
    ties either figure to a row set.

That payload is the first test in this file, and it is driven through the real
binding-resolution path against a real git repo whose `.mlkit/repo.toml`
COMMITS an honest `nominal = 0.90` -- so nothing here is measuring the nominal
refusals, which have their own controls in `tests/test_decision_controls.py`.

Both directions, everywhere. A tie that refused every payload would be as
useless as one that refused none, and the negative controls in this file are
the honest artifacts that must keep passing: a per-row tie, a per-group tie, a
tie over a coverage that genuinely misses (which must still FAIL for its own
reason, not for the tie's), and the boundary at `MIN_COVERAGE_N`.

The forge that builds tied fixtures lives HERE and not in `src/`: it
manufactures operands to match a claimed figure, which is precisely what the
tie exists to refuse, and a library that shipped it would ship the bypass with
the gate.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import MIN_COVERAGE_N, d3_uncertainty_coverage
from resilient_mlkit.core import coverage_evidence
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status
from resilient_mlkit.core.served import row_set_digest

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))

DECLARED = 0.90


# -- fixtures --------------------------------------------------------------


def tied_rows(n: int, covered: int, *, prefix: str = "holdout") -> dict:
    """A coverage payload whose figures are what its rows say.

    Not a library function, and deliberately never one: see the module
    docstring. The digest comes from `core.served.row_set_digest`, the one
    definition -- a second spelling here would prove agreement with itself.
    """
    rows = [{"row_id": f"{prefix}-{i:06d}", "covered": i < covered} for i in range(n)]
    return {
        "nominal": DECLARED,
        "empirical": covered / n,
        "n": n,
        "row_set_digest": row_set_digest([r["row_id"] for r in rows]),
        "rows": rows,
    }


def tied_groups(sizes: list[tuple[int, int]]) -> dict:
    """The same, in the per-declared-group form, from `(n, covered)` cells."""
    groups = [
        {"group_id": f"cell-{i}", "n": size, "covered": hits}
        for i, (size, hits) in enumerate(sizes)
    ]
    total = sum(g["n"] for g in groups)
    covered = sum(g["covered"] for g in groups)
    return {
        "nominal": DECLARED,
        "empirical": covered / total,
        "n": total,
        "row_set_digest": row_set_digest([g["group_id"] for g in groups]),
        "groups": groups,
    }


def _git(cwd, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def run_d3(tmp_path, payload: dict, *, nominal: object = DECLARED):
    """Drive D3 against a repo that returns `payload` from its coverage binding.

    The payload is written to a JSON artifact beside the module and returned
    verbatim, rather than being spelled into the module body. That is what
    lets a control STOMP ONE FIELD of a real tied artifact and change nothing
    else -- the persisted rows stay exactly as they were, which is the point
    of the refusal being able to name what they re-derive to.
    """
    module = f"d3tie_bindings_{next(_SERIAL)}"
    (tmp_path / "evidence.json").write_text(json.dumps(payload))
    (tmp_path / f"{module}.py").write_text(
        textwrap.dedent(
            """
            import json
            from pathlib import Path

            def coverage():
                return json.loads(Path(__file__).with_name("evidence.json").read_text())
            """
        )
    )
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = f'[repo]\nname = "fixturerepo"\n\n[bindings]\ncoverage = "{module}:coverage"\n'
    if nominal is not None:
        toml += f"\n[coverage]\nnominal = {nominal}\n"
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "fixture")
    repo = Repo(name="fixturerepo", path=tmp_path)
    try:
        return d3_uncertainty_coverage(
            repo, RunContext(nonce="test-nonce", root=tmp_path, offline=True)
        )
    finally:
        repo.release()


# -- FIRES: the escalation's own payload ----------------------------------


def test_positive_control_the_escalation_payload_no_longer_passes(tmp_path):
    """FIRES as NA: `{"nominal": 0.90, "empirical": 0.90, "n": 1000000}`.

    Driven at `6921e9a` against this same fixture -- honest committed 0.90, no
    dirty tree, no substituted level -- this returns PASS with evidence
    `{'nominal': 0.9, 'empirical': 0.9, 'n': 1000000, 'tol': 0.05,
    'declared_nominal': 0.9, 'reported_nominal': 0.9}`. A million rows that
    never existed, and the check had no way to ask.
    """
    result = run_d3(tmp_path, {"nominal": DECLARED, "empirical": 0.90, "n": 1_000_000})
    assert result.status is Status.NA
    assert coverage_evidence.UNTIED in result.reason
    # The refusal must name the missing operands, or an adopter cannot act on it.
    assert coverage_evidence.ROWS_KEY in result.reason
    assert coverage_evidence.GROUPS_KEY in result.reason
    assert coverage_evidence.DIGEST_KEY in result.reason
    assert "E-M23" in result.reason


def test_operands_without_a_digest_are_untied_too(tmp_path):
    """FIRES as NA: rows with no name cannot be held against any other figure."""
    payload = tied_rows(500, 450)
    del payload[coverage_evidence.DIGEST_KEY]
    result = run_d3(tmp_path, payload)
    assert result.status is Status.NA
    assert coverage_evidence.UNTIED in result.reason
    assert coverage_evidence.DIGEST_KEY in result.reason


def test_an_untied_payload_is_NA_and_not_a_FAIL(tmp_path):
    """FIRES as NA rather than FAIL, and the distinction is the instruction.

    "You did not supply this" is a gap an adopter fills in their own repo; "you
    supplied something else" is a claim that was checked and lost. E-M21 drew
    that line for the nominal level and this is the same line. Reporting a
    missing operand as FAIL would put every adopter into a red row on the day
    the contract landed, and the first response to a red row nobody can fix is
    to stop reading the column.
    """
    result = run_d3(tmp_path, {"nominal": DECLARED, "empirical": 0.90, "n": 5000})
    assert result.status is Status.NA
    assert result.status is not Status.FAIL


# -- FIRES: a tied artifact with one field stomped ------------------------


def test_positive_control_a_stomped_empirical_is_refused_by_the_rows(tmp_path):
    """FIRES: the artifact is genuinely tied and ONE figure was overwritten.

    This is the shape the tie exists for. The rows are real, the digest is
    real and matches them, `n` is right -- and `empirical` says 0.90 where the
    rows say 0.8954. The refusal must name the re-derived figure, because a
    refusal that only says "these disagree" leaves the reader to guess which
    side to believe.
    """
    payload = tied_rows(5000, 4477)
    payload["empirical"] = 0.90
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.SELF_REPORTED in result.reason
    assert "0.8954" in result.reason
    assert "4477" in result.reason
    assert result.evidence["derived_empirical"] == 0.8954
    assert result.evidence["derived_covered"] == 4477


def test_positive_control_a_stomped_n_is_refused_by_the_rows(tmp_path):
    """FIRES: the denominator is an operand too, and it was the escalation's."""
    payload = tied_rows(5000, 4500)
    payload["n"] = 1_000_000
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.SELF_REPORTED in result.reason
    assert "1000000" in result.reason
    assert result.evidence["derived_n"] == 5000


def test_positive_control_a_stomped_digest_is_refused(tmp_path):
    """FIRES: figures computed over one row set and attributed to another."""
    payload = tied_rows(5000, 4500)
    payload[coverage_evidence.DIGEST_KEY] = "0" * 64
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.DIGEST_MISMATCH in result.reason
    assert "0" * 64 in result.reason


def test_positive_control_a_digest_that_is_not_a_sha256_is_refused(tmp_path):
    """FIRES: `core.served`'s own reasoning -- two placeholders are equal."""
    payload = tied_rows(500, 450)
    payload[coverage_evidence.DIGEST_KEY] = "TODO"
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.DIGEST_MISMATCH in result.reason
    assert "not a sha256" in result.reason


# -- FIRES: operands that cannot be recounted -----------------------------


@pytest.mark.parametrize("covered", ["yes", 0.5, None, float("nan"), [1]])
def test_positive_control_a_covered_flag_that_is_not_an_indicator_is_refused(
    tmp_path, covered
):
    """FIRES: truthiness is how a string, a NaN or a 0.5 becomes "covered".

    `bool("yes")`, `bool(0.5)` and `bool(float("nan"))` are all True, and a
    count assembled out of truthiness is not a measurement. `None` and `[1]`
    are here because the failure must be a NAMED refusal rather than a
    TypeError escaping the check -- the shape fray's I1-F1 verifier found
    reaching a consumer as a bare traceback.
    """
    payload = tied_rows(500, 450)
    payload["rows"][0]["covered"] = covered
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "rows[0]" in result.reason


def test_positive_control_a_repeated_row_id_is_refused(tmp_path):
    """FIRES: `n` stops being a count of held-out rows.

    Stricter than `core.served.row_set_digest`, which deliberately does not
    collapse duplicates. There a repeated key distinguishes two comparisons;
    here the digest is the only handle on WHICH rows a figure covers, and a
    repeated key is either one row counted twice or two rows sharing a name.
    """
    payload = tied_rows(500, 450)
    payload["rows"][1]["row_id"] = payload["rows"][0]["row_id"]
    payload[coverage_evidence.DIGEST_KEY] = row_set_digest(
        [r["row_id"] for r in payload["rows"]]
    )
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "more than once" in result.reason


def test_positive_control_both_forms_at_once_are_refused(tmp_path):
    """FIRES: two descriptions of one row set can disagree.

    A check that picked one would be choosing which of the subject's answers
    to believe, which is the defect one level up.
    """
    payload = tied_rows(500, 450)
    payload["groups"] = [{"group_id": "g", "n": 500, "covered": 500}]
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert coverage_evidence.ROWS_KEY in result.reason
    assert coverage_evidence.GROUPS_KEY in result.reason


def test_positive_control_a_row_that_does_not_say_which_row_it_is_is_refused(tmp_path):
    """FIRES: a row with no id cannot be joined to anything, digest or not."""
    payload = tied_rows(500, 450)
    del payload["rows"][7]["row_id"]
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "rows[7]" in result.reason


def test_positive_control_rows_that_are_not_a_sequence_are_refused(tmp_path):
    """FIRES as a named refusal, not as a TypeError out of the check body."""
    payload = tied_rows(500, 450)
    payload["rows"] = 5
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "not a sequence" in result.reason


def test_positive_control_an_empty_row_set_is_refused(tmp_path):
    """FIRES: `core.served`'s own refusal, carried through by name.

    A digest over no rows identifies nothing and two of them would be equal to
    each other, so an empty tie is a tie that always holds.
    """
    payload = tied_rows(500, 450)
    payload["rows"] = []
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "identifies nothing" in result.reason


def test_positive_control_a_group_covering_more_rows_than_it_holds_is_refused(tmp_path):
    """FIRES: 600 covered of 500 is not a count over one row set."""
    payload = tied_groups([(500, 450), (500, 400)])
    payload["groups"][0]["covered"] = 600
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "more rows were covered" in result.reason


def test_positive_control_a_non_integer_group_count_is_refused(tmp_path):
    """FIRES: a group's counts are integers or they are not counts."""
    payload = tied_groups([(500, 450), (500, 400)])
    payload["groups"][0]["n"] = 500.5
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "groups[0]" in result.reason


def test_positive_control_a_repeated_group_id_is_refused(tmp_path):
    """FIRES: a partition cell counted twice is not a partition."""
    payload = tied_groups([(500, 450), (500, 400)])
    payload["groups"][1]["group_id"] = payload["groups"][0]["group_id"]
    payload[coverage_evidence.DIGEST_KEY] = row_set_digest(
        [g["group_id"] for g in payload["groups"]]
    )
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.MALFORMED in result.reason
    assert "more than once" in result.reason


# -- SILENT: honest artifacts keep their verdicts -------------------------


def test_negative_control_a_tied_row_artifact_passes_at_the_same_nominal(tmp_path):
    """SILENT: the ordinary case. Without this the file proves nothing.

    Same declared level, same tolerance, same coverage as the payload the
    first test refuses -- the ONLY difference is that these figures are what
    the rows say. The evidence carries the digest so that this coverage claim
    and a challenger comparison over the same rows can be compared, which is
    what `core.served.row_set_digest` is for.
    """
    payload = tied_rows(5000, 4500)
    result = run_d3(tmp_path, payload)
    assert result.status is Status.PASS
    assert result.evidence["empirical"] == 0.90
    assert result.evidence["n"] == 5000
    assert result.evidence["derived_empirical"] == 0.90
    assert result.evidence["derived_n"] == 5000
    assert result.evidence["tie_unit"] == "row"
    assert result.evidence[coverage_evidence.DIGEST_KEY] == payload[
        coverage_evidence.DIGEST_KEY
    ]


def test_negative_control_a_tied_group_artifact_passes(tmp_path):
    """SILENT: the per-declared-group form, for a holdout too big to list.

    A million-row holdout cannot be handed to a check row by row, and a
    contract nobody can satisfy is a contract nobody adopts. What this form
    ties is stated in the preregistration and is deliberately weaker: the
    figures are re-derived from a DECLARED PARTITION, not from rows.
    """
    payload = tied_groups([(400_000, 360_000), (600_000, 540_000)])
    result = run_d3(tmp_path, payload)
    assert result.status is Status.PASS
    assert result.evidence["derived_n"] == 1_000_000
    assert result.evidence["derived_empirical"] == 0.90
    assert result.evidence["tie_unit"] == "group"


def test_negative_control_a_tied_coverage_that_misses_still_fails_for_its_own_reason(
    tmp_path,
):
    """SILENT as a tie refusal: the coverage verdict is untouched.

    A tie that turned every failing coverage into a tie failure would have
    erased the check it was added to. 0.68 against a declared 0.90 misses by
    0.22 and must fail for missing, with the tie silent.
    """
    payload = tied_rows(5000, 3400)
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert "do not mean what they say" in result.reason
    assert coverage_evidence.SELF_REPORTED not in result.reason
    assert coverage_evidence.UNTIED not in result.reason


def test_the_small_holdout_NA_is_taken_on_the_derived_n(tmp_path):
    """SILENT: `MIN_COVERAGE_N` is unchanged and now measures a counted n.

    The boundary is not moved by this branch -- it is applied to a figure that
    was recounted rather than asserted, which is the point of the ordering.
    """
    result = run_d3(tmp_path, tied_rows(MIN_COVERAGE_N - 1, MIN_COVERAGE_N - 1))
    assert result.status is Status.NA
    assert "too small to measure coverage" in result.reason

    at_the_line = tmp_path / "at-the-line"
    at_the_line.mkdir()
    boundary = run_d3(at_the_line, tied_rows(MIN_COVERAGE_N, MIN_COVERAGE_N))
    assert boundary.status is Status.FAIL  # 1.00 coverage misses a declared 0.90
    assert "too small" not in boundary.reason


def test_a_float_representation_difference_is_not_a_disagreement(tmp_path):
    """SILENT: one number written two ways.

    `EMPIRICAL_AGREEMENT_EPS` is a representation allowance and not a second
    tolerance: a subject may average an indicator array where mlkit divides
    two integers. The companion test below is the half that makes this one a
    control -- a difference a person could mean is refused.
    """
    payload = tied_rows(5000, 4500)
    payload["empirical"] = 0.90 + 1e-15
    result = run_d3(tmp_path, payload)
    assert result.status is Status.PASS


def test_a_difference_above_the_allowance_is_refused(tmp_path):
    """FIRES at 1e-9, far below anything a coverage claim could mean.

    The pair with the test above is what pins the allowance to a
    representation difference. Widening it would turn the tie into a second
    tolerance, which is the thing being removed.
    """
    payload = tied_rows(5000, 4500)
    payload["empirical"] = 0.90 + 1e-9
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert coverage_evidence.SELF_REPORTED in result.reason


# -- ordering, which is a decision and not an accident --------------------


def test_a_substituted_nominal_outranks_an_untied_payload(tmp_path):
    """FIRES as FAIL NOMINAL_SELF_DECLARED, not as NA COVERAGE_UNTIED.

    The tick-13 exploit with no operands at all. Both refusals are available
    and the order decides which one a reader gets: a substituted pass mark is
    a claim that was checked and lost, and reporting it as "you did not supply
    rows" would file the incident under paperwork. Same reasoning as
    NOMINAL_SELF_DECLARED already outranking the small-holdout NA.
    """
    result = run_d3(
        tmp_path,
        {"nominal": 0.8879423328964613, "empirical": 0.8879423328964613, "n": 1526},
    )
    assert result.status is Status.FAIL
    assert "NOMINAL_SELF_DECLARED" in result.reason


def test_an_undeclared_level_outranks_an_untied_payload(tmp_path):
    """FIRES as NA NOMINAL_UNDECLARED: the standard is missing before the operands are."""
    result = run_d3(
        tmp_path, {"nominal": 0.90, "empirical": 0.90, "n": 5000}, nominal=None
    )
    assert result.status is Status.NA
    assert "NOMINAL_UNDECLARED" in result.reason


def test_a_non_finite_empirical_outranks_the_tie(tmp_path):
    """FIRES as the E-M09/E-M10 non-finite refusal, with its own reason.

    A NaN cannot equal any re-derived quotient, so folding it into the tie
    would replace "this coverage was never measured" with "these operands
    disagree" and make the finiteness guard unreachable through D3 -- the
    hazard `checks/decision.py` already names for the nominal block.
    """
    payload = tied_rows(500, 450)
    payload["empirical"] = float("nan")
    result = run_d3(tmp_path, payload)
    assert result.status is Status.FAIL
    assert "non-finite" in result.reason
    assert coverage_evidence.SELF_REPORTED not in result.reason


# -- the module on its own terms ------------------------------------------


def test_the_digest_is_core_served_s_definition_and_not_a_second_one():
    """One definition, or two artifacts can never be compared (rule 7).

    `core.coverage_evidence` must not compute a digest of its own: a coverage
    claim and a challenger comparison tie to each other only if both spell the
    digest the same way.
    """
    derived = coverage_evidence.derive(tied_rows(10, 9))
    assert derived.digest == row_set_digest([f"holdout-{i:06d}" for i in range(10)])
    source = (coverage_evidence.__file__ or "")
    assert source.endswith("coverage_evidence.py")
    text = Path(source).read_text(encoding="utf-8")
    assert "hashlib" not in text, (
        "coverage_evidence hashes something itself; the digest has one "
        "definition and it lives in core.served"
    )


def test_the_two_refusal_classes_are_distinct_types():
    """An adopter's gap and a subject's contradiction are different exceptions."""
    with pytest.raises(coverage_evidence.CoverageUntied):
        coverage_evidence.derive({"nominal": 0.9, "empirical": 0.9, "n": 10})
    with pytest.raises(coverage_evidence.CoverageRefused):
        coverage_evidence.derive(
            {"rows": [], coverage_evidence.DIGEST_KEY: "a" * 64}
        )
    assert not issubclass(
        coverage_evidence.CoverageUntied, coverage_evidence.CoverageRefused
    )
    assert not issubclass(
        coverage_evidence.CoverageRefused, coverage_evidence.CoverageUntied
    )


@pytest.mark.parametrize(
    "value,expected", [(True, 1), (False, 0), (1, 1), (0, 0), (1.0, 1), (0.0, 0)]
)
def test_the_indicators_that_are_accepted(value, expected):
    """SILENT: the six spellings of covered/not-covered that count."""
    payload = {
        "rows": [{"row_id": "a", "covered": value}],
        coverage_evidence.DIGEST_KEY: row_set_digest(["a"]),
    }
    assert coverage_evidence.derive(payload).covered == expected


def test_derive_refuses_a_numpy_style_indicator_by_name():
    """FIRES, with a cost this branch accepts rather than hides.

    A `numpy.bool_` is not a Python `bool`, and mlkit has no numpy dependency
    to recognise one with -- eight repos would inherit it. The adopter's fix is
    `bool(x)` at the yield site. Simulated here with a stand-in that is truthy
    and is not a bool, because the test suite must not require numpy either.
    """

    class TruthyNotABool:
        def __bool__(self) -> bool:
            return True

    payload = {
        "rows": [{"row_id": "a", "covered": TruthyNotABool()}],
        coverage_evidence.DIGEST_KEY: row_set_digest(["a"]),
    }
    with pytest.raises(coverage_evidence.CoverageRefused) as excinfo:
        coverage_evidence.derive(payload)
    assert excinfo.value.marker == coverage_evidence.MALFORMED
    assert "truthiness" in excinfo.value.detail
