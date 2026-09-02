"""The crosscut carve-out: proportional and fail-closed, not existential.

WHAT THIS IS FOR
----------------
`tests/test_dependence_unit.py` established the dependence-unit contract and is
**not modified by this file or this branch**. What it did not cover is the
carve-out's own quantifier. As shipped at `24f23b8`, the relation ladder asked

    if crosscutting:
        relation = UNIT_CROSSCUTS_ARMS

— *does ANY unit key appear in two arms* — and the refusal clause below it read
`elif not crosscutting and split_blocks:`. So one key answering yes silenced
`DEPENDENCE_UNIT_TOO_FINE` for every other key in the arm.

The wave-1 adversarial verifier of PR #32 measured both halves of that. It drove
`resilient-fray`'s panel with COUNTY unit keys and got **D6 PASS** — the wrong
answer in the repo the whole finding came from — and then flipped **one** val
row's `unit_key` to collide with a train row's, which turned a FAIL into a PASS
for the other 1,364 rows.

Amendment 1 to the preregistration
(`reports/DEPENDENCE_UNIT_PREREGISTRATION_AMENDMENT_1.md`) quotes the superseded
rule in full and states the replacement before it was coded. Its hypotheses are
H8–H13 and each one below names the hypothesis it drives.

SHAPE, NOT MEASUREMENT. The row counts here are fray's shape from the round-8
per-year table (253 + 267 + 278 + 285 + 282 = 1365 val rows over five crop
years) so that a failure message reads in the units of the finding. **No yield,
metric or interval from any real run appears in this file**, and nothing here
reads, opens or approaches a ledgered test read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import resilient_mlkit.core.served as served_module
from resilient_mlkit.core.served import (
    DEPENDENCE_UNIT_TOO_FINE,
    UNIT_CROSSCUTS_ARMS,
    UNIT_CROSSCUTS_BLOCK,
    UNIT_FINER_THAN_BLOCK,
    UNIT_IS_THE_BLOCK,
    UNIT_LABEL_CONTRADICTS_CONTENT,
    ResamplingDeclaration,
    RowUnit,
)

# The binding assertion the loop's rules require of every driver: `resilient_mlkit`
# is installed into eight virtualenvs on this machine and an editable install
# elsewhere resolves first if PYTHONPATH is not what it should be.
_EXPECTED = Path(__file__).resolve().parent.parent / "src" / "resilient_mlkit"
assert Path(served_module.__file__).resolve().parent.parent == _EXPECTED, (
    f"core.served resolved to {served_module.__file__}, not to {_EXPECTED}"
)

VAL_YEARS = {2016: 253, 2017: 267, 2018: 278, 2019: 285, 2020: 282}
TRAIN_YEARS = {2013: 40, 2014: 41, 2015: 42}
TEST_YEARS = {2021: 44, 2022: 45, 2023: 46, 2024: 47, 2025: 48}
ARMS = (("train", TRAIN_YEARS), ("val", VAL_YEARS), ("test", TEST_YEARS))


def fray_panel(*, unit: str) -> list[RowUnit]:
    """fray's county-year panel, blocked by crop year, resampled by ``unit``.

    ``"row"`` is what the run did, ``"crop_year"`` is the repair, and
    ``"county"`` is what the wave-1 verifier drove: a bare county index, which
    recurs across arms for the low indices every arm reaches and does not for
    the high ones only a big val year has.
    """
    rows: list[RowUnit] = []
    for arm, years in ARMS:
        for year, n in years.items():
            for county in range(n):
                key = {
                    "row": (year, county),
                    "crop_year": year,
                    "county": county,
                }[unit]
                rows.append(
                    RowUnit(
                        row_key=(year, county), arm=arm, block_key=year, unit_key=key
                    )
                )
    return rows


def chokepoint_panel(*, days: int = 120, corridors: int = 28) -> list[RowUnit]:
    """A time-blocked split in which EVERY unit crosses every arm."""
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
# H8 / H9 — CONTROL A: the escape must fire
# =========================================================================


def test_H8_the_county_unit_drive_that_recorded_PASS_now_refuses() -> None:
    """H8. The wave-1 verifier's own drive, at the shape it used.

    `reports/D6_CROSSCUT_BASE.json`, driven at `24f23b8` before this branch
    edited a source file, records this assignment as `UNIT_CROSSCUTS_ARMS`,
    refusal `NA`, **D6 PASS**. Forty-eight county indices reach every arm and
    two hundred and thirty-seven do not; the carve-out covered all 285.
    """
    d = declare(fray_panel(unit="county"), unit="county")

    assert d.refusal == DEPENDENCE_UNIT_TOO_FINE
    assert d.relation == UNIT_CROSSCUTS_BLOCK
    assert d.n_units_in_arm == 285
    assert (d.n_units_crosscutting_arms, d.n_units_local_to_arm) == (48, 237)
    assert d.n_blocks_split_by_local_units == 5
    # The proportion is in the message, because "some of them cross" is exactly
    # what a reader would otherwise expect the carve-out to have covered.
    assert "48 of the 285" in d.detail and "237 do not" in d.detail


def test_H9_one_colliding_key_moves_neither_the_verdict_nor_the_relation() -> None:
    """H9. The sharpest statement of the escape, as a control pair.

    fray as run refuses. fray as run with **one** of 1,365 val `unit_key`s
    edited to collide with a train key recorded `D6 PASS` at the base. Here the
    two answer identically — same refusal, same relation — and the only thing
    that moves is the count of keys on each side of the classification.
    """
    clean = fray_panel(unit="row")
    mutated = list(clean)
    train_key = next(r.unit_key for r in mutated if r.arm == "train")
    victim = next(i for i, r in enumerate(mutated) if r.arm == "val")
    mutated[victim] = RowUnit(
        row_key=mutated[victim].row_key,
        arm="val",
        block_key=mutated[victim].block_key,
        unit_key=train_key,
    )

    before, after = declare(clean), declare(mutated)
    assert before.refusal == after.refusal == DEPENDENCE_UNIT_TOO_FINE
    assert before.relation == after.relation == UNIT_FINER_THAN_BLOCK
    assert (before.n_units_crosscutting_arms, before.n_units_local_to_arm) == (0, 1365)
    assert (after.n_units_crosscutting_arms, after.n_units_local_to_arm) == (1, 1364)
    # ONE row differs between the two assignments, and that is the whole test.
    assert sum(1 for a, b in zip(clean, mutated) if a != b) == 1


def test_H9_the_escape_does_not_scale_back_in_from_the_other_end() -> None:
    """H9, driven as a ladder rather than at one point.

    Colliding 1, 10, 100 and 1,000 of the 1,365 val keys with train keys
    refuses every time. There is no count of collisions below "all of them"
    that buys silence, which is what "proportional" has to mean to be worth
    anything.
    """
    clean = fray_panel(unit="row")
    train_keys = [r.unit_key for r in clean if r.arm == "train"]
    val_ix = [i for i, r in enumerate(clean) if r.arm == "val"]
    for n in (1, 10, 100, 1000):
        rows = list(clean)
        for j in range(n):
            i = val_ix[j]
            rows[i] = RowUnit(
                row_key=rows[i].row_key,
                arm="val",
                block_key=rows[i].block_key,
                unit_key=train_keys[j % len(train_keys)],
            )
        d = declare(rows)
        assert d.refusal == DEPENDENCE_UNIT_TOO_FINE, n
        assert d.n_units_local_to_arm == 1365 - n, n


# =========================================================================
# H10 — CONTROL B: the carve-out the amendment did NOT take away
# =========================================================================


def test_H10_chokepoints_convention_keeps_its_documented_behaviour() -> None:
    """H10. Every corridor is in train, val AND test: the arm-local mass is
    empty, so the carve-out applies to the whole arm and nothing refuses.

    If this ever fails, the fleet's *correct* convention has been made
    unadoptable — the R12 failure mode the original preregistration named — and
    the amendment says to withdraw the branch rather than argue with it.
    """
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
    assert (d.n_units_in_arm, d.n_blocks_in_arm) == (28, 20)
    assert (d.n_units_crosscutting_arms, d.n_units_local_to_arm) == (28, 0)
    # And what a passing carve-out is carrying is PRINTED, not implied: all
    # twenty date blocks in the arm are split across corridors, and the
    # amendment does not claim to have closed that.
    assert d.n_blocks_split_by_crosscutting_units == 20
    assert d.n_blocks_split_by_local_units == 0
    assert d.to_dict()["n_blocks_split_by_crosscutting_units"] == 20


def test_H10_frays_repair_is_still_silent_and_still_the_block() -> None:
    """H10. The negative control the whole contract exists to keep silent."""
    d = declare(fray_panel(unit="crop_year"), unit="crop_year")
    assert d.refusal == ""
    assert d.relation == UNIT_IS_THE_BLOCK
    assert (d.n_units_crosscutting_arms, d.n_units_local_to_arm) == (0, 5)
    assert d.n_blocks_split_by_local_units == 0


def test_H10_the_label_remutation_of_the_carve_out_still_refuses_by_name() -> None:
    """H10. Both labels say 'corridor'; the assignment says the policy blocks
    on the date. Unchanged from the base, constant and detail alike."""
    d = declare(
        chokepoint_panel(),
        policy="time_blocked_split",
        blocking_unit="corridor",
        unit="corridor",
    )
    assert d.refusal == UNIT_LABEL_CONTRADICTS_CONTENT
    assert UNIT_CROSSCUTS_ARMS in d.detail


def test_the_label_clause_did_not_go_quiet_when_the_relation_became_local() -> None:
    """The regression the fix's own attack found, held as a test.

    Making the relation proportional moves this assignment's relation from
    `UNIT_CROSSCUTS_ARMS` to `UNIT_IS_THE_BLOCK` — the arm's two local-and-
    crosscutting units happen to sit one per block — and the label clause,
    written as `relation != UNIT_IS_THE_BLOCK`, would have gone SILENT on a
    case the base refuses. Driven at `24f23b8` this refuses with
    `UNIT_LABEL_CONTRADICTS_CONTENT`; the enumeration in
    `reports/D6_CROSSCUT_CONTAINMENT.json` finds 2,160 of 209,952 such cases
    when the `or crosscutting` half is removed, and 0 with it.

    `straddling` is empty here, so every block of this policy is in exactly one
    arm and a unit key with rows in two arms cannot be one of them.
    """
    rows = [
        RowUnit(row_key=0, arm="val", block_key=0, unit_key="u0"),
        RowUnit(row_key=1, arm="val", block_key=1, unit_key="u1"),
        RowUnit(row_key=2, arm="train", block_key=2, unit_key="u0"),
    ]
    d = declare(rows, policy="p", blocking_unit="B", unit="B")
    assert d.relation == UNIT_IS_THE_BLOCK
    assert d.refusal == UNIT_LABEL_CONTRADICTS_CONTENT
    assert d.n_units_crosscutting_arms == 1
    assert "have rows in another arm" in d.detail


# =========================================================================
# H12 — the constructing layer, for the four new derived facts
# =========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        "n_units_crosscutting_arms",
        "n_units_local_to_arm",
        "n_blocks_split_by_local_units",
        "n_blocks_split_by_crosscutting_units",
    ],
)
def test_H12_no_new_derived_fact_can_be_passed_in(field_name: str) -> None:
    """The four counts that make the carve-out a proportion are exactly as
    unspellable as the eleven that came before them. A caller who wants the
    arm-local mass to be empty has to hand over an assignment in which it is."""
    with pytest.raises(TypeError) as exc:
        declare(fray_panel(unit="crop_year"), unit="crop_year", **{field_name: 0})
    assert field_name in str(exc.value)


def test_H12_the_four_counts_are_arithmetically_tied_to_the_ones_beside_them() -> None:
    """A count nobody can cross-check is a count nobody has checked.

    The two unit counts partition the units in the arm; the two block counts
    are disjoint subsets of the blocks in it.
    """
    for d in (
        declare(fray_panel(unit="row")),
        declare(fray_panel(unit="county"), unit="county"),
        declare(fray_panel(unit="crop_year"), unit="crop_year"),
        declare(
            chokepoint_panel(),
            policy="time_blocked_split",
            blocking_unit="date",
            unit="corridor",
        ),
    ):
        assert (
            d.n_units_crosscutting_arms + d.n_units_local_to_arm == d.n_units_in_arm
        ), d.unit
        assert (
            d.n_blocks_split_by_local_units + d.n_blocks_split_by_crosscutting_units
            <= d.n_blocks_in_arm
        ), d.unit
        assert set(d.to_dict()) >= {
            "n_units_crosscutting_arms",
            "n_units_local_to_arm",
            "n_blocks_split_by_local_units",
            "n_blocks_split_by_crosscutting_units",
        }


# =========================================================================
# H13 — the narrowing at its own boundary, and the residual it does not close
# =========================================================================


def test_H13_one_val_only_unit_beside_a_crosscutting_mass_refuses() -> None:
    """H13. chokepoint's shape PLUS one corridor that exists only in `val`.

    The 28 real corridors still cross all three arms. The 29th is drawn as an
    independent replicate of a piece of every val date block, and it is not on
    an axis the split failed to partition — it lives entirely inside the arm.
    This PASSED at the base and refuses here; that is the cost of the narrowing,
    driven rather than asserted.
    """
    rows = chokepoint_panel()
    rows += [
        RowUnit(row_key=(day, 999), arm="val", block_key=day,
                unit_key="corridor-val-only")
        for day in range(80, 100)
    ]
    d = declare(rows, policy="time_blocked_split", blocking_unit="date",
                unit="corridor")
    assert d.refusal == DEPENDENCE_UNIT_TOO_FINE
    assert (d.n_units_crosscutting_arms, d.n_units_local_to_arm) == (28, 1)
    assert d.n_blocks_split_by_local_units == 20


def test_the_residual_hole_is_named_here_rather_than_left_to_be_discovered() -> None:
    """WHAT THIS BRANCH DOES NOT CLOSE, held as an assertion so it cannot rot.

    A unit that crosscuts EVERY arm is still refusal-free even when it is finer
    than the policy's blocks inside the arm. That is chokepoint's endorsed
    convention and fray-with-a-fully-crossing-county-index at the same time, and
    nothing measured in this round tells them apart — Amendment 1 §7. If a later
    change ever refuses this shape, this test fails and the person making that
    change has to say what measurement licensed it.

    What the amendment does add is the count: `n_blocks_split_by_crosscutting_units`
    says how many of the policy's blocks the silence is carrying.
    """
    # Every county index 0..39 exists in every crop year of every arm, so no
    # unit is arm-local — and each of the five val blocks is still cut into 40.
    rows = [
        RowUnit(row_key=(year, county), arm=arm, block_key=year, unit_key=county)
        for arm, years in ARMS
        for year in years
        for county in range(40)
    ]
    d = declare(rows, unit="county")
    assert d.refusal == ""
    assert d.relation == UNIT_CROSSCUTS_ARMS
    assert d.n_units_local_to_arm == 0
    assert d.n_blocks_split_by_crosscutting_units == 5
