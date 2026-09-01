"""The DEPENDENCE UNIT: does the refusal fire, and does it stay silent.

WHAT THIS IS FOR
----------------
Round-8 adjudication measured it in ``resilient-fray``. The repo's holdout
policy puts WHOLE CROP YEARS in one partition, so the exchangeable unit is the
crop year and VAL has five of them. The run's bootstrap resampled **1,365 rows**
as if independent. On one identical set of rows:

    resampling unit          point       95% CI                clears zero
    ROW (what was reported)  +22.811     [+16.016, +29.646]    yes
    CROP-YEAR block (5)      +22.811     [-1.289, +41.704]     NO

``resilient-chokepoint`` resamples its dependence unit — corridors, 28 of them,
predictions held fixed. fray resampled rows. **No gate was edited by anyone**:
fray's preregistration fixed the row bootstrap in advance and the run honoured
it exactly. The fleet held two conventions, and nothing in mlkit required
either one or required the choice to be stated.

Two figures above are QUOTED from that adjudication and appear nowhere in this
file's arithmetic. Every number the tests below assert on is produced by the
code under test from fixture rows built here. The one thing borrowed from the
real panel is SHAPE — five val crop years and 1,365 val rows, split
253/267/278/285/282 — so that a failure message reads in the units of the
finding. No yield, no metric and no interval from any real run appears here.

THE PAIRING THAT CARRIES THE WEIGHT
-----------------------------------
* **fray's shape FIRES / fray's repair is SILENT.** One field changes between
  them — which key each row's ``unit_key`` carries — and nothing else.
* **chokepoint's convention is SILENT.** If it were not, the fleet's *correct*
  convention would be unadoptable, which is R12's stated failure mode one layer
  up ("adopting the check would not clear it").
* **the guard is not dead.** Five single-fact remutations of the SILENT
  declaration each produce a different named verdict, so the silence is the
  code deciding rather than the code not looking.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

import resilient_mlkit.core.served as served_module
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import (
    RESAMPLING_BINDING,
    d6_resampling_unit,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status
from resilient_mlkit.core.served import (
    BLOCKS_STRADDLE_ARMS,
    DEPENDENCE_UNIT_CONTRADICTS_POLICY,
    DEPENDENCE_UNIT_TOO_FINE,
    INTERVAL_COVERS_ZERO,
    LOWER_IS_BETTER,
    NO_SKILL,
    RESAMPLING_ROWS_UNTIED,
    SINGLE_UNIT,
    UNIT_COARSER_THAN_BLOCK,
    UNIT_CROSSCUTS_ARMS,
    UNIT_IS_THE_BLOCK,
    UNIT_LABEL_CONTRADICTS_CONTENT,
    UNMEASURED,
    ChallengerDecision,
    Comparison,
    ResamplingDeclaration,
    RowUnit,
    ServedContractError,
    challenger_decision,
    row_set_digest,
)

# The binding assertion the loop's rules require of every driver. Without it a
# green run here says nothing about the tree under review: `resilient_mlkit` is
# installed into eight repos' virtualenvs and an editable install elsewhere on
# this machine resolves first if PYTHONPATH is not what it should be.
_EXPECTED = Path(__file__).resolve().parent.parent / "src" / "resilient_mlkit"
assert Path(served_module.__file__).resolve().parent.parent == _EXPECTED, (
    f"core.served resolved to {served_module.__file__}, not to {_EXPECTED}"
)

BAR = "persistence_t_minus_1"

#: fray's val partition, by crop year. SHAPE from the adjudication's per-year
#: table (253 + 267 + 278 + 285 + 282 = 1365), so that counts in a failure
#: message read in the units of the finding. Not a measurement: these are row
#: COUNTS of a synthetic fixture, and no figure computed from real rows appears
#: in this file.
VAL_YEARS = {2016: 253, 2017: 267, 2018: 278, 2019: 285, 2020: 282}
TRAIN_YEARS = {2013: 40, 2014: 41, 2015: 42}
TEST_YEARS = {2021: 44, 2022: 45, 2023: 46, 2024: 47, 2025: 48}

_SERIAL = iter(range(10_000))


# -- fixtures --------------------------------------------------------------


def fray_panel(*, unit: str = "row") -> list[RowUnit]:
    """The county-year panel, blocked by crop year, resampled by ``unit``.

    ``unit="row"`` is what the run did; ``unit="crop_year"`` is the repair.
    Exactly one expression differs between them.
    """
    rows: list[RowUnit] = []
    for arm, years in (
        ("train", TRAIN_YEARS), ("val", VAL_YEARS), ("test", TEST_YEARS)
    ):
        for year, n in years.items():
            for county in range(n):
                rows.append(
                    RowUnit(
                        row_key=(year, county),
                        arm=arm,
                        block_key=year,
                        unit_key=(year, county) if unit == "row" else year,
                    )
                )
    return rows


def chokepoint_panel(*, days: int = 120, corridors: int = 28) -> list[RowUnit]:
    """A time-blocked split whose resampling unit crosscuts every arm.

    Each corridor appears in train, val AND test, which is what separates it
    from a row: the split does not partition this axis at all.
    """
    rows: list[RowUnit] = []
    for day in range(days):
        arm = "train" if day < 80 else ("val" if day < 100 else "test")
        for c in range(corridors):
            rows.append(
                RowUnit(
                    row_key=(day, c), arm=arm, block_key=day, unit_key=f"corridor-{c}"
                )
            )
    return rows


def declare(assignment: list[RowUnit], **overrides) -> ResamplingDeclaration:
    kwargs = {
        "procedure": "bootstrap",
        "draws": 4000,
        "policy": "county_year_splits",
        "blocking_unit": "crop_year",
        "unit": "row",
        "arm": "val",
    }
    kwargs.update(overrides)
    return ResamplingDeclaration(assignment=assignment, **kwargs)


# =========================================================================
# 1. THE CONTROL PAIR — fray fires, fray's repair is silent
# =========================================================================


def test_positive_control_the_fray_shape_refuses_and_names_both_units() -> None:
    """FIRES: 1,365 row units drawn inside an arm the policy blocks into five."""
    d = declare(fray_panel(unit="row"))

    assert d.refusal == DEPENDENCE_UNIT_TOO_FINE
    assert d.contradicts_policy is True
    # Both units and both counts, or the message is not actionable.
    assert "'row'" in d.detail and "'crop_year'" in d.detail
    assert "1365" in d.detail and " 5 " in d.detail
    assert d.n_units_in_arm == 1365
    assert d.n_blocks_in_arm == 5
    assert d.n_rows == 1365


def test_negative_control_the_repair_is_silent() -> None:
    """SILENT: the same 1,365 rows, resampled by the unit the split defines.

    One expression differs from the test above — ``unit_key`` — and the verdict
    inverts. That is the whole of the finding, expressed as a control pair.
    """
    d = declare(fray_panel(unit="crop_year"), unit="crop_year")

    assert d.refusal == ""
    assert d.contradicts_policy is False
    assert d.relation == UNIT_IS_THE_BLOCK
    assert (d.n_units_in_arm, d.n_blocks_in_arm, d.n_rows) == (5, 5, 1365)


def test_negative_control_chokepoints_convention_is_silent() -> None:
    """SILENT: a unit whose keys appear in every arm is not manufactured from
    the holdout's own blocks, and refusing it would make the fleet's correct
    convention unadoptable."""
    d = declare(
        chokepoint_panel(),
        procedure="corridor-block bootstrap",
        draws=2000,
        policy="time_blocked_split",
        blocking_unit="date",
        unit="corridor",
    )

    assert d.refusal == ""
    assert d.relation == UNIT_CROSSCUTS_ARMS
    assert d.n_units_in_arm == 28
    # And the number that is NOT resampled is in the record beside it. A table
    # carrying only "28 corridors" is how a five-year holdout reads as 1,365
    # independent draws.
    assert d.n_blocks_in_arm == 20
    assert d.to_dict()["n_blocks_in_arm"] == 20


def test_the_contract_does_not_claim_the_crosscutting_case_is_accounted_for() -> None:
    """The disclosure, held as an assertion rather than left in prose.

    ``UNIT_CROSSCUTS_ARMS`` is recorded, not blessed: the declaration reports a
    relation and NO refusal, and the number of blocks the procedure did not
    resample is in the same dict. If a future change ever turned this into a
    silent PASS-shaped signal with the block count dropped, this fails.
    """
    d = declare(
        chokepoint_panel(),
        blocking_unit="date", unit="corridor", policy="time_blocked_split",
    )
    payload = d.to_dict()
    assert payload["relation"] == UNIT_CROSSCUTS_ARMS
    assert payload["refusal"] == UNMEASURED
    assert {"n_units_in_arm", "n_blocks_in_arm", "n_rows"} <= set(payload)


# =========================================================================
# 2. NOT DEAD — five single-fact remutations of the SILENT declaration
# =========================================================================


def _repaired_rows() -> list[RowUnit]:
    return fray_panel(unit="crop_year")


def test_not_dead_unit_back_to_the_row() -> None:
    """The one fact that made it silent, put back."""
    assert declare(fray_panel(unit="row")).refusal == DEPENDENCE_UNIT_TOO_FINE


def test_not_dead_a_block_moved_across_the_split() -> None:
    """One val row relabelled into a train crop year: the policy's own claim
    about itself stops holding, and that is refused BEFORE anything downstream
    of it is reasoned about."""
    rows = _repaired_rows()
    victim = next(i for i, r in enumerate(rows) if r.arm == "val")
    rows[victim] = RowUnit(
        row_key=rows[victim].row_key, arm="train",
        block_key=rows[victim].block_key, unit_key=rows[victim].unit_key,
    )
    d = declare(rows, unit="crop_year")
    assert d.refusal == BLOCKS_STRADDLE_ARMS
    assert "'crop_year'" in d.detail and "county_year_splits" in d.detail


def test_not_dead_every_val_row_in_one_unit() -> None:
    """A procedure that resamples one unit resamples the same thing every draw."""
    rows = [
        RowUnit(row_key=r.row_key, arm=r.arm, block_key=r.block_key,
                unit_key="ALL" if r.arm == "val" else r.unit_key)
        for r in _repaired_rows()
    ]
    d = declare(rows, unit="the_whole_arm")
    assert d.refusal == SINGLE_UNIT
    assert d.n_units_in_arm == 1


def test_not_dead_the_label_is_not_the_tie() -> None:
    """Both labels say 'corridor'; the assignment says the policy blocks on the
    date. A name is not a tie."""
    d = declare(
        chokepoint_panel(),
        policy="time_blocked_split", blocking_unit="corridor", unit="corridor",
    )
    assert d.refusal == UNIT_LABEL_CONTRADICTS_CONTENT
    assert UNIT_CROSSCUTS_ARMS in d.detail


def test_not_dead_a_coarser_unit_moves_the_relation_without_refusing() -> None:
    """Pairs of crop years formed inside the arm: fewer, larger clusters than
    the policy's partitions. Conservative, so recorded and not refused — and
    the relation is a DIFFERENT value, so the silence is a decision."""
    order = {}
    for r in _repaired_rows():
        order.setdefault(r.arm, [])
        if r.block_key not in order[r.arm]:
            order[r.arm].append(r.block_key)
    rows = [
        RowUnit(
            row_key=r.row_key, arm=r.arm, block_key=r.block_key,
            unit_key=(r.arm, order[r.arm].index(r.block_key) // 2),
        )
        for r in _repaired_rows()
    ]
    d = declare(rows, unit="crop_year_pair")
    assert d.refusal == ""
    assert d.relation == UNIT_COARSER_THAN_BLOCK
    assert d.n_units_in_arm == 3 and d.n_blocks_in_arm == 5


# =========================================================================
# 3. THE CONSTRUCTING LAYER — none of the derived facts is spellable
# =========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        "n_rows", "n_blocks_in_arm", "n_units_in_arm", "n_rows_panel",
        "row_digest", "block_digest", "unit_digest", "block_keys_in_arm",
        "relation", "refusal", "detail",
    ],
)
def test_no_derived_fact_can_be_passed_in(field_name: str) -> None:
    """`Comparison.row_matched`'s lesson (M-06) one level up: a caller who wants
    the answer to be 'the unit is the block' has to hand over an assignment in
    which it is. Every one of these is a TypeError NAMING the argument."""
    with pytest.raises(TypeError) as exc:
        declare(_repaired_rows(), **{field_name: "anything"})
    assert field_name in str(exc.value)


def test_the_assignment_is_required() -> None:
    """There is no declaration without content to derive it from."""
    with pytest.raises(TypeError) as exc:
        ResamplingDeclaration(
            procedure="bootstrap", draws=10, policy="p",
            blocking_unit="b", unit="u", arm="val",
        )
    assert "assignment" in str(exc.value)


def test_a_bare_tuple_assignment_is_refused_by_name() -> None:
    """The block and the unit are the same TYPE and adjacent. Handed over as a
    positional pair they can be swapped, and every verdict here would be
    exactly reversed with nothing to see."""
    with pytest.raises(ServedContractError, match="RowUnit"):
        declare([(2016, "val", 2016, 2016)])  # type: ignore[list-item]


def test_a_repeated_row_key_is_refused() -> None:
    rows = _repaired_rows()
    rows.append(rows[0])
    with pytest.raises(ServedContractError, match="repeats row key"):
        declare(rows, unit="crop_year")


def test_an_empty_assignment_is_refused() -> None:
    """Two declarations over nothing would be equal to each other."""
    with pytest.raises(ServedContractError, match="empty assignment"):
        declare([])


def test_an_arm_absent_from_the_assignment_is_refused() -> None:
    with pytest.raises(ServedContractError, match="no row in arm"):
        declare(_repaired_rows(), unit="crop_year", arm="calibration")


@pytest.mark.parametrize("draws", [0, -1, True, 1.5, "4000"])
def test_a_count_of_draws_that_is_not_a_count_is_refused(draws) -> None:
    """`True` is an `int` in Python and would have been one draw."""
    with pytest.raises(ServedContractError, match="draws"):
        declare(_repaired_rows(), unit="crop_year", draws=draws)


@pytest.mark.parametrize(
    "field_name", ["procedure", "policy", "blocking_unit", "unit", "arm"]
)
def test_an_unnamed_declaration_is_refused(field_name: str) -> None:
    kwargs = {"unit": "crop_year", field_name: "   "}
    with pytest.raises(ServedContractError, match=field_name):
        declare(_repaired_rows(), **kwargs)


def test_a_row_with_no_arm_is_refused() -> None:
    with pytest.raises(ServedContractError, match="names no arm"):
        RowUnit(row_key=1, arm="", block_key=1, unit_key=1)


def test_a_key_that_cannot_be_written_down_is_refused() -> None:
    """Two keys that fall back to repr() compare by memory address."""
    with pytest.raises(ServedContractError, match="JSON-serialisable"):
        declare([RowUnit(row_key=object(), arm="val", block_key=1, unit_key=1)])


# =========================================================================
# 4. EVERY TIE IS CONTENT — the digests are computable a second way
# =========================================================================


def test_the_row_digest_is_the_fleets_one_row_set_digest() -> None:
    """Recomputed here from the same rows through the public function, so the
    tie is content and not this class's private spelling."""
    rows = _repaired_rows()
    d = declare(rows, unit="crop_year")
    independently = row_set_digest(r.row_key for r in rows if r.arm == "val")
    assert d.row_digest == independently


def test_the_same_rows_under_two_units_tie_on_rows_and_differ_on_units() -> None:
    """The operand that must match matches; the operand that must distinguish
    them distinguishes them."""
    as_run = declare(fray_panel(unit="row"))
    repaired = declare(fray_panel(unit="crop_year"), unit="crop_year")
    assert as_run.row_digest == repaired.row_digest
    assert as_run.block_digest == repaired.block_digest
    assert as_run.unit_digest != repaired.unit_digest


def test_the_block_digest_distinguishes_two_blockings_of_one_row_set() -> None:
    rows = _repaired_rows()
    by_year = declare(rows, unit="crop_year")
    by_row = declare(
        [RowUnit(row_key=r.row_key, arm=r.arm, block_key=r.row_key,
                 unit_key=r.unit_key) for r in rows],
        unit="crop_year", blocking_unit="row",
    )
    assert by_year.row_digest == by_row.row_digest
    assert by_year.block_digest != by_row.block_digest


# =========================================================================
# 5. THE COMPARISON — an interval cannot be declared without its unit
# =========================================================================


def _val_row_digest(rows: list[RowUnit] | None = None) -> str:
    """The rows a figure on the val arm is computed over, digested the one way.

    The comparison and the declaration have to tie to the SAME rows, so this is
    the single place the fixture computes them.
    """
    rows = rows if rows is not None else _repaired_rows()
    return row_set_digest(r.row_key for r in rows if r.arm == "val")


def _comparison(**overrides) -> Comparison:
    digest = _val_row_digest()
    kwargs = {
        "reference": BAR, "metric": "mae",
        "candidate_value": 80.0, "reference_value": 100.0,
        "n_rows": 1365, "arm": "val", "polarity": LOWER_IS_BETTER,
        "candidate_row_digest": digest, "reference_row_digest": digest,
    }
    kwargs.update(overrides)
    return Comparison(**kwargs)  # type: ignore[arg-type]


def _val_declaration(rows: list[RowUnit] | None = None, **overrides):
    rows = rows if rows is not None else _repaired_rows()
    kwargs = {"unit": "crop_year"}
    kwargs.update(overrides)
    return declare(rows, **kwargs)


def test_an_interval_with_no_declaration_raises() -> None:
    """The whole of 'an adopter cannot silently use the weaker convention' at
    this layer: the weaker convention is still spellable, and it is no longer
    silent."""
    with pytest.raises(ServedContractError, match="no resampling declaration"):
        _comparison(skill_interval_low=0.1, skill_interval_high=0.3)


def test_a_declaration_with_no_interval_raises() -> None:
    with pytest.raises(ServedContractError, match="no interval"):
        _comparison(resampling=_val_declaration())


def test_half_an_interval_raises() -> None:
    with pytest.raises(ServedContractError, match="one interval endpoint"):
        _comparison(skill_interval_low=0.1, resampling=_val_declaration())


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_bound_raises(bad: float) -> None:
    """A NaN compares False to zero in both directions, which is the one
    question an interval is asked."""
    with pytest.raises(ServedContractError, match="non-finite interval"):
        _comparison(
            skill_interval_low=bad, skill_interval_high=0.3,
            resampling=_val_declaration(),
        )


def test_an_inverted_interval_raises() -> None:
    with pytest.raises(ServedContractError, match="lower bound is above"):
        _comparison(
            skill_interval_low=0.4, skill_interval_high=0.1,
            resampling=_val_declaration(),
        )


def test_an_interval_that_does_not_contain_its_own_point_raises() -> None:
    """Every operand needs a tie. An interval on a DIFFERENT quantity than the
    one the gate decides — a margin in the metric's own units, say — is untied
    while looking tied. Skill here is 1 - 80/100 = 0.2."""
    with pytest.raises(ServedContractError, match="does not contain its own point"):
        _comparison(
            skill_interval_low=16.016, skill_interval_high=29.646,
            resampling=_val_declaration(),
        )


def test_a_declaration_on_another_arm_raises() -> None:
    with pytest.raises(ServedContractError, match="was measured on arm"):
        _comparison(
            arm="test", skill_interval_low=0.1, skill_interval_high=0.3,
            resampling=_val_declaration(),
        )


def test_a_comparison_carrying_a_declaration_must_name_its_own_arm() -> None:
    with pytest.raises(ServedContractError, match="names no arm of its own"):
        _comparison(
            arm="", skill_interval_low=0.1, skill_interval_high=0.3,
            resampling=_val_declaration(),
        )


# =========================================================================
# 6. THE DECISION PATH
# =========================================================================


def _decide(comparison: Comparison) -> ChallengerDecision:
    return challenger_decision(
        [comparison], recorded_bar=BAR, metrics=("mae",), deciding_arm="val"
    )


def test_a_contradicting_unit_is_NA_naming_both_units() -> None:
    """FIRES: the fray artifact, decided. NA and not FAIL — the candidate may be
    perfectly good; what cannot be adjudicated is the evidence about it."""
    decision = _decide(
        _comparison(
            skill_interval_low=0.05, skill_interval_high=0.35,
            resampling=declare(fray_panel(unit="row")),
        )
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == DEPENDENCE_UNIT_CONTRADICTS_POLICY
    assert decision.promotable is False
    assert DEPENDENCE_UNIT_TOO_FINE in decision.reason
    assert "'row'" in decision.reason and "'crop_year'" in decision.reason
    # An NA carries no skill number, as it never has.
    assert set(decision.skill.values()) == {None}


def test_a_positive_point_whose_interval_covers_zero_FAILS() -> None:
    """FIRES: the fray case, once the unit is right. The point estimate is the
    number; the interval is whether the number is distinguishable from no
    effect, and promotion rests on the second."""
    decision = _decide(
        _comparison(
            skill_interval_low=-0.02, skill_interval_high=0.41,
            resampling=_val_declaration(),
        )
    )
    assert decision.status is Status.FAIL
    assert decision.refusal_class == INTERVAL_COVERS_ZERO
    assert decision.promotable is False
    # The skill IS reported on a FAIL — it was measured, and it is positive.
    assert decision.skill["mae"] == pytest.approx(0.2)
    assert "crop_year" in decision.reason


def test_an_interval_clearing_zero_on_the_declared_unit_PASSES() -> None:
    """SILENT: the only shape this contract promotes."""
    decision = _decide(
        _comparison(
            skill_interval_low=0.11, skill_interval_high=0.29,
            resampling=_val_declaration(),
        )
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    payload = decision.to_dict()
    assert payload["resampling"][0]["unit"] == "crop_year"
    assert payload["resampling"][0]["relation"] == UNIT_IS_THE_BLOCK
    assert payload["resampling"][0]["n_units_in_arm"] == 5


def test_an_interval_resampled_over_other_rows_is_NA() -> None:
    """The point estimate and the bound around it must be about the same rows."""
    decision = _decide(
        _comparison(
            skill_interval_low=0.11, skill_interval_high=0.29,
            resampling=_val_declaration(),
        )
    )
    assert decision.status is Status.PASS  # the tie holds for the arm's rows...

    other = _comparison(
        skill_interval_low=0.11, skill_interval_high=0.29,
        candidate_row_digest=row_set_digest(["somewhere", "else"]),
        reference_row_digest=row_set_digest(["somewhere", "else"]),
        resampling=_val_declaration(),
    )
    decision = _decide(other)
    assert decision.status is Status.NA
    assert decision.refusal_class == RESAMPLING_ROWS_UNTIED


def test_a_lost_point_estimate_still_reports_NO_SKILL() -> None:
    """The interval lane is asked LAST. A comparison that lost on the point
    estimate is not re-labelled by the presence of a bound."""
    decision = _decide(
        _comparison(
            candidate_value=120.0,  # skill 1 - 120/100 = -0.2
            skill_interval_low=-0.4, skill_interval_high=-0.05,
            resampling=_val_declaration(),
        )
    )
    assert decision.status is Status.FAIL
    assert decision.refusal_class == NO_SKILL


# -- CONTROL B: nothing without an interval moved --------------------------


def test_control_b_a_comparison_with_no_interval_decides_exactly_as_before() -> None:
    """SILENT: the three new lanes are unreachable without an interval, which is
    every comparison this gate decided before 2026-09-01."""
    decision = _decide(_comparison())
    assert decision.status is Status.PASS
    assert decision.refusal_class == "CLEARS_BAR"
    assert decision.skill["mae"] == pytest.approx(0.2)


def test_control_b_silence_is_PRINTED_rather_than_missing() -> None:
    """A promotion that rests on an interval and reports `"resampling": "NA"`
    has said, in the record a person reads, that nobody declared what was
    resampled — which is the state round-8 adjudication had to reconstruct by
    hand from a trainer's source."""
    payload = _decide(_comparison()).to_dict()
    assert payload["resampling"] == UNMEASURED
    assert payload["evidence"]["comparisons"][0]["resampling"] == UNMEASURED
    assert payload["evidence"]["comparisons"][0]["skill_interval"] == UNMEASURED


def test_control_b_the_decision_hands_out_a_copy_of_its_declaration() -> None:
    """A verdict hands out what it decided on; it does not hand out the thing it
    decided on. Driven for the new key the way `evidence` already was."""
    decision = _decide(
        _comparison(
            skill_interval_low=0.11, skill_interval_high=0.29,
            resampling=_val_declaration(),
        )
    )
    payload = decision.to_dict()
    payload["resampling"][0]["unit"] = "TAMPERED"
    payload["evidence"]["comparisons"][0]["resampling"]["n_units_in_arm"] = 1365
    again = decision.to_dict()
    assert again["resampling"][0]["unit"] == "crop_year"
    assert again["evidence"]["comparisons"][0]["resampling"]["n_units_in_arm"] == 5


# =========================================================================
# 7. D6 — the check, and the operand the declaration cannot supply
# =========================================================================


def _d6_repo(tmp_path: Path, body: str, *, declare_binding: bool = True,
             declare_splits: bool = True) -> Repo:
    """A repo on disk whose bindings are `body`, resolved the real way."""
    module = f"d6_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n\n[bindings]\n'
    if declare_binding:
        toml += f'{RESAMPLING_BINDING} = "{module}:resampling_declaration"\n'
    if declare_splits:
        toml += f'splits = "{module}:splits"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    subprocess.run(
        ["git", "-C", str(tmp_path), "init", "-q"], check=True, capture_output=True
    )
    return Repo(name="fixturerepo", path=tmp_path)


#: A binding module that builds fray's panel in the fixture repo's own source.
#: `unit` and `block` are the two expressions the controls vary.
_BINDINGS = '''
    VAL_YEARS = {2016: 253, 2017: 267, 2018: 278, 2019: 285, 2020: 282}
    TRAIN_YEARS = {2013: 40, 2014: 41, 2015: 42}
    TEST_YEARS = {2021: 44, 2022: 45, 2023: 46, 2024: 47, 2025: 48}
    ARMS = (("train", TRAIN_YEARS), ("val", VAL_YEARS), ("test", TEST_YEARS))

    UNIT = %(unit)r
    BLOCK = %(block)r
    SPLIT_YEARS = %(split_years)r

    def _rows():
        out = []
        for arm, years in ARMS:
            for year, n in years.items():
                for county in range(n):
                    out.append({
                        "row_key": [year, county],
                        "arm": arm,
                        "block_key": [year, county] if BLOCK == "row" else year,
                        "unit_key": [year, county] if UNIT == "row" else year,
                    })
        return out

    def resampling_declaration():
        return {
            "procedure": "bootstrap",
            "draws": 4000,
            "policy": "county_year_splits",
            "blocking_unit": BLOCK,
            "unit": UNIT,
            "arm": "val",
            "assignment": _rows(),
        }

    def splits():
        return {
            "train": sorted(TRAIN_YEARS),
            "val": SPLIT_YEARS if SPLIT_YEARS is not None else sorted(VAL_YEARS),
            "test": sorted(TEST_YEARS),
        }
'''


def _run_d6(tmp_path: Path, *, unit="crop_year", block="crop_year",
            split_years=None, **repo_kwargs):
    repo = _d6_repo(
        tmp_path,
        _BINDINGS % {"unit": unit, "block": block, "split_years": split_years},
        **repo_kwargs,
    )
    try:
        return d6_resampling_unit(
            repo, RunContext(nonce="t", root=tmp_path, offline=True, timeout=5.0)
        )
    finally:
        repo.release()


def test_d6_positive_control_the_fray_shape_FAILS(tmp_path: Path) -> None:
    """FIRES: through the real binding path, not a monkeypatch."""
    result = _run_d6(tmp_path, unit="row")
    assert result.status is Status.FAIL
    assert DEPENDENCE_UNIT_TOO_FINE in result.reason
    assert result.evidence["n_units_in_arm"] == 1365
    assert result.evidence["n_blocks_in_arm"] == 5


def test_d6_negative_control_the_repair_PASSES(tmp_path: Path) -> None:
    """SILENT: one expression differs from the test above."""
    result = _run_d6(tmp_path)
    assert result.status is Status.PASS
    assert result.evidence["relation"] == UNIT_IS_THE_BLOCK
    assert result.evidence["blocks_tied_to"] == "splits"
    assert result.evidence["n_groups_in_splits"] == 5


def test_d6_the_fabricated_blocking_unit_is_caught_by_the_OTHER_operand(
    tmp_path: Path,
) -> None:
    """The gap the declaration cannot close, closed here.

    ``block_key = row_key`` describes a policy with no blocks at all. It is
    perfectly self-consistent — the unit does not split anything, so clause 1 is
    SILENT and the declaration reports no refusal. It is caught only because the
    blocks are tied to ``splits``, a second declaration of the same partition
    that R3 already reads: 1,365 declared blocks against 5 groups.
    """
    # First, the disclosure: the declaration ALONE does not object.
    alone = declare(
        [RowUnit(row_key=r.row_key, arm=r.arm, block_key=r.row_key,
                 unit_key=r.unit_key) for r in fray_panel(unit="row")],
        blocking_unit="crop_year",
    )
    assert alone.refusal == ""

    result = _run_d6(tmp_path, unit="row", block="row")
    assert result.status is Status.FAIL
    assert "BLOCKS_CONTRADICT_SPLITS" in result.reason
    assert result.evidence["n_blocks_declared"] == 1365
    assert result.evidence["n_groups_in_splits"] == 5


def test_d6_a_split_that_disagrees_by_one_group_FAILS(tmp_path: Path) -> None:
    """Not only a gross mismatch: the sets must be equal, and the message names
    which side each difference is on."""
    result = _run_d6(tmp_path, split_years=[2016, 2017, 2018, 2019, 2099])
    assert result.status is Status.FAIL
    assert result.evidence["only_in_declaration"] == ["2020"]
    assert result.evidence["only_in_splits"] == ["2099"]


def test_d6_without_the_binding_is_NA_and_says_what_to_declare(
    tmp_path: Path,
) -> None:
    """NA, never PASS — the answer D2 and D3 give for their own absent bindings."""
    result = _run_d6(tmp_path, declare_binding=False)
    assert result.status is Status.NA
    assert RESAMPLING_BINDING in result.reason


def test_d6_without_splits_is_NA_even_though_the_declaration_is_clean(
    tmp_path: Path,
) -> None:
    """A verdict resting on an untied operand is the thing three ticks of this
    loop paid for. The declaration is clean and the answer is still not PASS."""
    result = _run_d6(tmp_path, declare_splits=False)
    assert result.status is Status.NA
    assert "BLOCKS_UNTIED" in result.reason
    assert result.evidence["relation"] == UNIT_IS_THE_BLOCK
