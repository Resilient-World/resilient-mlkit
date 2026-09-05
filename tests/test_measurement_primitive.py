"""Controls for the exported repo-facing measurement primitive.

Pre-registered in ``reports/MEASUREMENT_EXPORT_PREREGISTRATION.md``, committed
before this file existed. Table MX-1..MX-8.

Every assertion comes in a pair. The primitive must FIRE — an NA cannot pass
through it, an unexplained NA cannot be built, a PASS with nothing behind it
cannot be built — and it must stay SILENT on the legitimate case: a real PASS
constructs, and the exported surface agrees with ``core.result`` on every one
of the six statuses. Firing alone would be consistent with a type that refuses
everything, which is as useless as one that refuses nothing.

The equivalence half (MX-6, MX-8) is the point of the whole module. A shared
primitive that quietly means something different from the canonical one is
worse than the hand copies it replaces, because it would look like convergence.
``scripts/verify_served_hash_parity.py`` makes the same argument about digests:
adopting a contract must not redefine an identity a repo already recorded.
"""

from __future__ import annotations

import pytest

from resilient_mlkit.core import result as core_result
from resilient_mlkit.measurement import (
    ALLOW_DIRTY_KEY,
    FabricationError,
    GateUnmeasured,
    Measured,
    MetricUnmeasured,
    Status,
    UncommittedRead,
    Unmeasured,
    ValidationUnmeasured,
)

# --------------------------------------------------------------- MX-1  NA never passes


def test_mx1_an_unmeasured_gate_is_not_a_pass() -> None:
    """FIRES: the one invariant every copy of this primitive was written for."""
    m = Measured.unmeasured("coverage", reason="no scored rows: calibration split empty")
    assert m.status is Status.NA
    assert m.passed is False
    assert m.measured is False
    assert m.unmeasured_reason == "no scored rows: calibration split empty"
    assert m.value is None, "an unmeasured gate must not offer a figure"


def test_mx1_passed_cannot_be_assigned_into_a_pass() -> None:
    """FIRES: ``passed`` is derived, so 'NA that passed' cannot be spelled.

    The three hand copies take ``passed`` as a constructor argument and correct
    it in ``__post_init__``. That is a state that exists for one statement.
    Here it never exists: the attribute is read-only.
    """
    m = Measured.unmeasured("coverage", reason="no rows")
    with pytest.raises(AttributeError):
        m.passed = True  # type: ignore[misc]
    assert m.passed is False


def test_mx1_direct_construction_of_na_is_refused_a_pass_too() -> None:
    """FIRES: the guard is on the type, not on the named constructor."""
    m = Measured("coverage", Status.NA, reason="input artifact absent")
    assert m.passed is False and m.status is Status.NA


# ------------------------------------------------- MX-2  a bare NA cannot be built


def test_mx2_an_na_without_a_reason_is_refused() -> None:
    """FIRES: an unexplained NA looks like coverage and carries no information."""
    with pytest.raises(FabricationError) as excinfo:
        Measured.unmeasured("coverage", reason="   ")
    assert "requires a reason" in str(excinfo.value)


def test_mx2_negative_control_an_na_with_a_reason_constructs() -> None:
    """SILENT: the rule is about the empty reason, not about NA."""
    m = Measured.unmeasured("coverage", reason="calibration split has 0 rows")
    assert m.status is Status.NA and m.reason


# --------------------------------------------- MX-3  a PASS with nothing behind it


def test_mx3_a_pass_with_no_metrics_is_refused() -> None:
    """FIRES: inherited from core.result, and none of the three copies has it."""
    with pytest.raises(FabricationError) as excinfo:
        Measured.ok("coverage", metrics={})
    assert "PASS requires evidence" in str(excinfo.value)


def test_mx3_negative_control_a_pass_with_metrics_constructs() -> None:
    """SILENT: a measured pass is not obstructed."""
    m = Measured.ok("coverage", metrics={"coverage": 0.94, "n_rows": 1200})
    assert m.passed is True
    assert m.metrics["n_rows"] == 1200


# ------------------------------------- MX-4  a PASS may not rest on a dirty read


def test_mx4_a_pass_on_an_allow_dirty_read_is_refused() -> None:
    """FIRES: E-M12's rule reaches the repo gate site unchanged."""
    with pytest.raises(UncommittedRead):
        Measured.ok("coverage", metrics={"coverage": 0.94, ALLOW_DIRTY_KEY: True})


def test_mx4_negative_control_an_na_may_record_a_dirty_read() -> None:
    """SILENT: the refusal is on the PASS, not on the marker.

    Without this half the rule would be indistinguishable from "the marker is
    forbidden", which would stop a gate from recording the very fact that makes
    its NA correct.
    """
    m = Measured.unmeasured(
        "coverage",
        reason="read from the working tree; nothing at HEAD",
        metrics={ALLOW_DIRTY_KEY: True},
    )
    assert m.status is Status.NA and m.metrics[ALLOW_DIRTY_KEY] is True


# ------------------------------------------- MX-5  the six states render distinctly


def _render(status: Status) -> str:
    if status is Status.PASS:
        return Measured.ok("g", metrics={"x": 1}).render()
    if status is Status.FAIL:
        return Measured.failed("g", reason="0.81 below the bar").render()
    if status is Status.NA:
        return Measured.unmeasured("g", reason="input absent").render()
    if status is Status.DEFERRED:
        return Measured.deferred("g", credential="CDSAPI_KEY", detail="request built").render()
    if status is Status.STALE:
        return Measured.stale("g", reason="measured at another sha").render()
    if status is Status.UNMEASURABLE:
        return Measured.unmeasurable(
            "g", reason="staged panel absent", input="data/panel.parquet",
            pin_expected="aa", pin_observed="",
        ).render()
    # Strict, not a fall-through. Until M-1 this line rendered ANY status it
    # did not name as ESCALATED, so a seventh status arrived and the
    # "six renderings are pairwise distinct" pin below stayed green over six
    # distinct strings drawn from seven statuses -- dead coverage of exactly
    # the shape that pin's docstring warns about.
    assert status is Status.ESCALATED, f"_render does not know {status!r}"
    return Measured.escalated("g", reason="reserved to the signatory").render()


def test_mx5_na_does_not_render_like_a_pass() -> None:
    """FIRES: mlkit's own portfolio defect, at the surface repos will import."""
    assert _render(Status.NA) != _render(Status.PASS)
    assert not _render(Status.NA).startswith("PASS")
    assert "unmeasured" in _render(Status.NA)


def test_mx5_na_does_not_render_like_a_fail() -> None:
    """FIRES: "nobody could measure this" is not "this missed the bar"."""
    assert _render(Status.NA) != _render(Status.FAIL)
    assert not _render(Status.NA).startswith("FAIL")


def test_mx5_deferred_does_not_render_like_na() -> None:
    """FIRES: the collapse core/result.py's docstring calls expensive."""
    assert _render(Status.DEFERRED) != _render(Status.NA)
    assert "credential" in _render(Status.DEFERRED)


def test_mx5_stale_does_not_render_like_na_or_pass() -> None:
    """FIRES: measured against another tree is its own thing."""
    assert _render(Status.STALE) not in {_render(Status.NA), _render(Status.PASS)}
    assert "another tree" in _render(Status.STALE)


def test_mx5_escalated_does_not_render_like_na_or_fail() -> None:
    """FIRES: signatory-reserved is not a failure and not an absence."""
    assert _render(Status.ESCALATED) not in {_render(Status.NA), _render(Status.FAIL)}
    assert "signatory" in _render(Status.ESCALATED)


def test_mx5_all_seven_renderings_are_pairwise_distinct() -> None:
    """FIRES: the states asserted above, plus every pair not named separately.

    Counted against ``len(Status)`` rather than a literal, so a status added to
    the enum and not to ``_render`` fails HERE (``_render`` now asserts on an
    unknown status) instead of collapsing into a neighbour's rendering.
    """
    rendered = [_render(s) for s in Status]
    assert len(Status) == 7
    assert len(set(rendered)) == len(Status), f"two statuses render alike: {rendered}"


def test_mx5_unmeasurable_does_not_render_like_na_fail_or_pass() -> None:
    """FIRES (M-1): armed-and-input-absent is its own thing in a column."""
    rendered = _render(Status.UNMEASURABLE)
    assert rendered not in {_render(Status.NA), _render(Status.FAIL), _render(Status.PASS)}
    assert rendered.startswith("UNMEASURABLE")
    assert "armed" in rendered


def test_mx5_negative_control_only_pass_leads_with_pass() -> None:
    """SILENT: the distinctness rule does not forbid PASS from saying PASS."""
    assert _render(Status.PASS).startswith("PASS")
    for status in Status:
        if status is not Status.PASS:
            assert not _render(status).startswith("PASS"), status


def test_mx5_to_dict_keeps_na_structurally_distinct() -> None:
    """FIRES and SILENT in one shape: the serialised form carries the same fact."""
    na = Measured.unmeasured("g", reason="input absent").to_dict()
    ok = Measured.ok("g", metrics={"x": 1}).to_dict()
    assert na["status"] == "NA" and na["passed"] is False and na["measured"] is False
    assert "unmeasured_reason" in na
    assert ok["status"] == "PASS" and ok["passed"] is True and ok["measured"] is True
    assert "unmeasured_reason" not in ok


# ----------------------------- MX-6  equivalence with core.result on every state
#
# Adoption must not silently redefine a verdict. Each row builds the same
# outcome twice -- once through the exported surface, once through
# ``core.result`` directly -- and requires them to agree.

_CASES = [
    ("PASS", lambda: Measured.ok("g", metrics={"x": 1}),
     lambda: core_result.CheckResult.passed("g", "repo-gate", {"x": 1})),
    ("FAIL", lambda: Measured.failed("g", reason="below the bar", metrics={"x": 1}),
     lambda: core_result.CheckResult.failed("g", "repo-gate", "below the bar", {"x": 1})),
    ("NA", lambda: Measured.unmeasured("g", reason="input absent"),
     lambda: core_result.CheckResult.na("g", "repo-gate", "input absent")),
    ("DEFERRED", lambda: Measured.deferred("g", credential="CDSAPI_KEY", detail="request built"),
     lambda: core_result.CheckResult.deferred("g", "repo-gate", "CDSAPI_KEY", "request built")),
    ("STALE", lambda: Measured.stale("g", reason="another sha"),
     lambda: core_result.CheckResult("g", "repo-gate", Status.STALE, "another sha")),
    ("ESCALATED", lambda: Measured.escalated("g", reason="signatory"),
     lambda: core_result.CheckResult.escalated("g", "repo-gate", "signatory")),
    # M-1. Built through the export and through core.result from the SAME
    # InputUnavailable operands, so the reason text and the evidence keys
    # (input / pin_expected / pin_observed / unmeasurable) must agree exactly.
    ("UNMEASURABLE",
     lambda: Measured.unmeasurable(
         "g", reason="staged panel absent", input="data/panel.parquet",
         pin_expected="aa11", pin_observed="",
     ),
     lambda: core_result.CheckResult.unmeasurable(
         "g", "repo-gate",
         core_result.InputUnavailable(
             "staged panel absent", input="data/panel.parquet",
             pin_expected="aa11", pin_observed="",
         ),
     )),
]


@pytest.mark.parametrize("label,build_exported,build_core", _CASES, ids=[c[0] for c in _CASES])
def test_mx6_the_exported_surface_agrees_with_core_result(
    label: str, build_exported, build_core
) -> None:
    """SILENT: no state may mean something different through the export."""
    exported = build_exported()
    canonical = build_core()
    assert exported.status is canonical.status, label
    assert exported.reason == canonical.reason, label
    assert exported.metrics == canonical.evidence, label
    assert exported.passed == (canonical.status is Status.PASS), label


@pytest.mark.parametrize("label,build_exported,build_core", _CASES, ids=[c[0] for c in _CASES])
def test_mx6_to_result_round_trips_into_a_checkresult(
    label: str, build_exported, build_core
) -> None:
    """SILENT: what a gate hands mlkit is the canonical type, unchanged."""
    round_tripped = build_exported().to_result()
    canonical = build_core()
    assert isinstance(round_tripped, core_result.CheckResult)
    for key in ("check_id", "phase", "status", "reason", "evidence"):
        assert round_tripped.to_dict()[key] == canonical.to_dict()[key], f"{label}/{key}"


def test_mx6_every_status_is_covered_by_the_equivalence_cases() -> None:
    """FIRES if a seventh status is added and this battery is not extended.

    Without it the parametrisation above would keep passing while silently
    testing five sixths of the vocabulary -- the shape of dead coverage this
    fleet has shipped before.
    """
    assert {label for label, _, _ in _CASES} == {s.value for s in Status}


def test_mx6_negative_control_the_battery_can_fail() -> None:
    """FIRES: the comparison is real, not a tautology over one object.

    An NA built through the export is compared against a PASS built through
    core.result; if the assertions above could not distinguish two statuses,
    this would not raise.
    """
    exported = Measured.unmeasured("g", reason="input absent")
    canonical = core_result.CheckResult.passed("g", "repo-gate", {"x": 1})
    assert exported.status is not canonical.status
    assert exported.metrics != canonical.evidence


# ------------------------------------------- MX-8  Status is not a fourth definition


def test_mx8_status_is_the_canonical_enum_itself() -> None:
    """SILENT: identity, not agreement. A copy that agrees today is still a copy."""
    assert Status is core_result.Status
    # Seven since M-1 (2026-09-04): UNMEASURABLE, appended, every earlier
    # member in its earlier position. There is still no SKIP and no WARN.
    assert len(Status) == 7
    assert [s.value for s in Status] == [
        "PASS", "FAIL", "NA", "DEFERRED", "STALE", "ESCALATED", "UNMEASURABLE",
    ]
    assert not {"SKIP", "WARN"} & {s.value for s in Status}


def test_mx8_the_three_state_copies_are_missing_four_of_them() -> None:
    """FIRES: records what the copies cannot say, so the reason is checkable.

    blackout's ``EstimateResult``, triage's ``Measured`` and choco's
    ``ValidationResult`` each carry PASS/FAIL/NA only. These four states have
    no expression there, which is why converging on this module is a gain and
    not a rename. (Three until M-1; the fourth is the one torrent's binding
    had to spell as a FAIL whose reason begins "ENVIRONMENT REFUSAL".)
    """
    three_state = {"PASS", "FAIL", "NA"}
    missing = {s.value for s in Status} - three_state
    assert missing == {"DEFERRED", "STALE", "ESCALATED", "UNMEASURABLE"}


# ------------------------------------------- the raise-instead-of-default family


def test_the_unmeasured_exception_family_is_exported_under_the_copies_names() -> None:
    """SILENT: converging is an import change, not a rewrite of call sites."""
    for exc in (GateUnmeasured, MetricUnmeasured, ValidationUnmeasured):
        assert issubclass(exc, Unmeasured)
        assert issubclass(exc, RuntimeError)


def test_raising_is_the_alternative_to_a_substituted_default() -> None:
    """FIRES: a caller cannot accidentally read a plausible number instead."""
    def correlation(variance: float) -> float:
        if variance == 0.0:
            raise MetricUnmeasured("constant series: a correlation is undefined")
        return 0.5

    with pytest.raises(Unmeasured):
        correlation(0.0)
    assert correlation(1.0) == 0.5, "SILENT: a measurable input still measures"


# ------------------------------------------------------------------ MX-9 / MX-10
# Added by adversarial verification of this branch (VERIFY-MX9, VERIFY-MX10).
# Both controls FAIL against the first version of measurement.py and pass here.


def test_mx9_status_cannot_be_reassigned_into_an_evidence_free_pass() -> None:
    """FIRES: the forbidden state, spelled through `status` instead of `passed`.

    `passed` is a read-only property, which stops `m.passed = True`. It does
    not stop `m.status = Status.PASS`, and before the `__setattr__` guard that
    assignment produced an NA that reported `passed is True`, rendered as
    `PASS ... - <the NA's reason>` and carried no metrics at all.
    """
    na = Measured.unmeasured("coverage", reason="no scored rows")
    with pytest.raises(FabricationError, match="PASS requires evidence"):
        na.status = Status.PASS
    # Refused BEFORE the write: the outcome is unchanged, not half-corrected.
    assert na.status is Status.NA
    assert na.passed is False
    assert not na.render().startswith("PASS")


def test_mx9_a_pass_cannot_be_reassigned_onto_an_allow_dirty_read() -> None:
    """FIRES: rebinding metrics onto a PASS re-applies the uncommitted-read refusal."""
    ok = Measured.ok("coverage", metrics={"coverage": 0.91})
    with pytest.raises(UncommittedRead):
        ok.metrics = {"coverage": 0.91, ALLOW_DIRTY_KEY: True}
    assert ok.metrics == {"coverage": 0.91}


def test_mx9_reassigning_a_reason_away_from_a_non_pass_is_refused() -> None:
    """FIRES: an NA may not be emptied of the reason that makes it honest."""
    na = Measured.unmeasured("coverage", reason="no scored rows")
    with pytest.raises(FabricationError, match="requires a reason"):
        na.reason = ""
    assert na.reason == "no scored rows"


def test_mx9_negative_control_a_legal_reassignment_still_lands() -> None:
    """SILENT: the guard re-validates; it does not freeze the object.

    Same field, same object, same kind of write as the three FIRES above --
    the only difference is that the result is a legal one. Without this half,
    the guard is consistent with "refuse every assignment".
    """
    na = Measured.unmeasured("coverage", reason="no scored rows")
    na.reason = "no scored rows: the calibration split is empty"
    assert na.reason == "no scored rows: the calibration split is empty"
    na.status = Status.FAIL  # legal: FAIL needs a reason, and it has one
    assert na.status is Status.FAIL and na.passed is False
    ok = Measured.ok("coverage", metrics={"coverage": 0.91})
    ok.metrics = {"coverage": 0.93, "n_rows": 40}
    assert ok.metrics == {"coverage": 0.93, "n_rows": 40} and ok.passed is True
    # And the fields that carry no verdict are not guarded at all.
    ok.notes = ["re-read after the split was rebuilt"]
    assert ok.notes == ["re-read after the split was rebuilt"]


_LEAKY = "Authorization: Bearer ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def test_mx10_the_fields_this_module_adds_are_redacted_too() -> None:
    """FIRES: `gate_description` and `notes` do not exist on CheckResult.

    core.result redacts `reason` and nothing else, because `reason` is the only
    free text it has. These two are this module's own additions and both reach
    `to_dict()`, so before this they were an unredacted route from an
    interpolated exception to a transcript -- CLAUDE.md rule 13.
    """
    out = Measured.unmeasured(
        "coverage",
        reason="no rows",
        gate_description=f"gate {_LEAKY}",
        notes=[f"note {_LEAKY}", "clean note"],
    ).to_dict()
    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in out["gate"]
    assert "<redacted>" in out["gate"]
    assert not any("ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA" in n for n in out["notes"])


def test_mx10_negative_control_clean_free_text_survives_intact() -> None:
    """SILENT: redaction removes credentials, not prose.

    Same two fields, same call, text that carries no secret -- so the control
    above is not satisfied by a function that blanks everything.
    """
    out = Measured.unmeasured(
        "coverage",
        reason="no rows",
        gate_description="empirical coverage >= 0.9",
        notes=["read from reports/val/coverage.json"],
    ).to_dict()
    assert out["gate"] == "empirical coverage >= 0.9"
    assert out["notes"] == ["read from reports/val/coverage.json"]
