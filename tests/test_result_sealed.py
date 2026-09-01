"""M-02(b) — a verdict is decided once, and cannot be edited afterwards.

WHAT WAS DRIVEN AT 8517341, with the module's own ``__file__`` asserted:

    r = CheckResult.failed("R99", "phase-1", "the check measured a real failure")
    r.status                                  -> Status.FAIL
    r.status = Status.PASS                    -> succeeded
    r.evidence = {}                           -> succeeded
    r.to_dict()["status"]                     -> 'PASS'
    r.to_dict()["evidence"]                   -> {}

``CheckResult.__post_init__`` is the single most load-bearing invariant in the
package — a PASS may not rest on nothing, a non-pass must say why — and it ran
exactly once, at construction, after which every field it guards was an
ordinary mutable attribute. The guard was not weak; it was in the wrong place
on the timeline. A check that FAILED could be edited into a PASS by anything
holding the object, and the edited result serialised, stored and rendered as a
pass with no trace that it had ever been anything else.

``measurement.Measured`` had already met this exact defect from the other side
(``measurement.py:100``, ``:293``): ``passed`` was a read-only property, and
``m.status = Status.PASS`` reached ``passed``, ``render()`` and ``to_dict()``
anyway. Its repair re-validates on assignment. That is the right answer THERE,
because ``Measured`` is a builder a gate fills in. It is the wrong answer here:
re-validation only refuses states that are structurally illegal, so flipping a
FAIL that carries evidence into a PASS that carries the same evidence passes
re-validation and is still a forged verdict.

So this is a seal, not a re-check. A ``CheckResult`` is the record of one
measurement that already happened; there is no legitimate reason for its
verdict to change afterwards. The three provenance stamps the CLI applies
after construction (``repo``, ``git_sha``, ``nonce``) stay writable ONCE —
they are the run's labels, applied by the runner that knows them, and
re-stamping an already-stamped result with different values is refused too.
"""

from __future__ import annotations

import copy
import json

import pytest

import resilient_mlkit.core.result as result_module
from resilient_mlkit.core.result import (
    ALLOW_DIRTY_KEY,
    CheckResult,
    FabricationError,
    GateAggregate,
    Status,
    VerdictSealed,
)

RESULT_MODULE_FILE = result_module.__file__


def test_the_suite_is_driving_this_tree_s_core_result():
    assert RESULT_MODULE_FILE.endswith("resilient_mlkit/core/result.py")
    assert "site-packages" not in RESULT_MODULE_FILE


def failing() -> CheckResult:
    return CheckResult.failed(
        "R99", "phase-1", "the check measured a real failure",
        {"rows": 3, "overlaps": 1},
    )


# ---------------------------------------------------------------------------
# CONTROL A — the forgeries, each refused by name
# ---------------------------------------------------------------------------
def test_control_a_a_fail_cannot_be_assigned_into_a_pass():
    """The drive, exactly as it read at 8517341."""
    r = failing()
    assert r.status is Status.FAIL
    with pytest.raises(VerdictSealed, match="status"):
        r.status = Status.PASS
    assert r.status is Status.FAIL
    assert r.to_dict()["status"] == "FAIL"


def test_control_a_the_evidence_cannot_be_rebound_after_the_verdict():
    r = failing()
    with pytest.raises(VerdictSealed, match="evidence"):
        r.evidence = {}
    assert r.evidence == {"rows": 3, "overlaps": 1}


def test_control_a_the_evidence_cannot_be_emptied_in_place_either():
    """Rebinding is the loud spelling; mutation is the quiet one.

    A seal that only refused ``r.evidence = {}`` would be defeated by
    ``r.evidence.clear()``, which reaches the same state through a method call
    ``__setattr__`` never sees. ``measurement.py`` states this residual as open
    for its own metrics dict; here it is closed.
    """
    r = CheckResult.passed("R99", "phase-1", {"rows": 3})
    for mutate in (
        lambda: r.evidence.clear(),
        lambda: r.evidence.pop("rows"),
        lambda: r.evidence.popitem(),
        lambda: r.evidence.update({"rows": 0}),
        lambda: r.evidence.setdefault("rows", 0),
        lambda: r.evidence.__setitem__("rows", 0),
        lambda: r.evidence.__delitem__("rows"),
    ):
        with pytest.raises(VerdictSealed, match="evidence"):
            mutate()
    assert r.evidence == {"rows": 3}


def test_control_a_the_reason_cannot_be_rewritten():
    """The reason is why the verdict is what it is; editing it re-narrates it."""
    r = failing()
    with pytest.raises(VerdictSealed, match="reason"):
        r.reason = "actually everything was fine"
    assert r.reason == "the check measured a real failure"


def test_control_a_the_identity_and_the_timestamp_are_sealed_too():
    r = failing()
    for field, value in (
        ("check_id", "R01"),
        ("phase", "phase-3"),
        ("measured_at", "1970-01-01T00:00:00+00:00"),
    ):
        with pytest.raises(VerdictSealed, match=field):
            setattr(r, field, value)


def test_control_a_a_stamped_result_cannot_be_restamped_onto_another_repo():
    """A result relabelled onto a different repo or SHA is a different claim."""
    r = failing()
    r.repo = "resilient-fray"
    r.git_sha = "41b496e"
    r.nonce = "n1"
    with pytest.raises(VerdictSealed, match="git_sha"):
        r.git_sha = "0000000"
    with pytest.raises(VerdictSealed, match="repo"):
        r.repo = "resilient-chokepoint"
    assert (r.repo, r.git_sha, r.nonce) == ("resilient-fray", "41b496e", "n1")


def test_control_a_the_allow_dirty_refusal_cannot_be_reached_by_mutation():
    """E-M12's refusal was construction-time only, and so was evadable.

    Building the PASS with the marker refuses. Building it without and adding
    the marker afterwards used to succeed, producing exactly the record E-M12
    exists to refuse: a pass resting on bytes in nobody's git history.
    """
    with pytest.raises(FabricationError):
        CheckResult.passed("R99", "phase-1", {"n": 1, ALLOW_DIRTY_KEY: True})
    r = CheckResult.passed("R99", "phase-1", {"n": 1})
    with pytest.raises(VerdictSealed, match="evidence"):
        r.evidence[ALLOW_DIRTY_KEY] = True
    assert ALLOW_DIRTY_KEY not in r.evidence


# ---------------------------------------------------------------------------
# CONTROL B — every legitimate path still works, unchanged
# ---------------------------------------------------------------------------
def test_control_b_every_named_constructor_still_constructs():
    assert CheckResult.passed("R1", "p", {"n": 1}).status is Status.PASS
    assert CheckResult.failed("R1", "p", "why").status is Status.FAIL
    assert CheckResult.na("R1", "p", "why").status is Status.NA
    assert CheckResult.deferred("R1", "p", "CDSAPI_KEY", "d").status is Status.DEFERRED
    assert CheckResult.escalated("R1", "p", "why").status is Status.ESCALATED


def test_control_b_the_factory_outputs_are_byte_identical_through_json():
    """The serialisation the fleet already commits is untouched."""
    r = CheckResult.na("R5", "phase-1", "no data pulled", {"n_sources": 0})
    payload = r.to_dict()
    assert payload["status"] == "NA"
    assert payload["evidence"] == {"n_sources": 0}
    assert json.loads(json.dumps(payload)) == payload


def test_control_b_the_cli_stamping_path_still_stamps():
    """cli.py:117-119 and :134-136 set these three after construction."""
    r = failing()
    r.repo = "resilient-mlkit"
    r.git_sha = "8517341"
    r.nonce = "abc"
    assert r.to_dict()["repo"] == "resilient-mlkit"
    assert r.to_dict()["git_sha"] == "8517341"
    assert r.to_dict()["nonce"] == "abc"
    # Idempotent re-stamping with the SAME value is not a relabelling.
    r.repo = "resilient-mlkit"
    assert r.repo == "resilient-mlkit"


def test_control_b_from_dict_round_trips():
    r = failing()
    r.repo, r.git_sha, r.nonce = "resilient-mlkit", "8517341", "abc"
    again = CheckResult.from_dict(r.to_dict())
    assert again.to_dict() == r.to_dict()


def test_control_b_post_init_normalisation_still_runs():
    """__post_init__ writes to its own fields; the seal closes after it."""
    r = CheckResult("R1", "p", "FAIL", "why")
    assert r.status is Status.FAIL
    assert r.measured_at


def test_control_b_redaction_still_happens_on_the_way_in():
    r = CheckResult.failed("R1", "p", "boom: authorization: hunter2 was rejected")
    assert "hunter2" not in r.reason
    assert "<redacted>" in r.reason


def test_control_b_to_dict_hands_out_a_mutable_copy_of_the_evidence():
    """A reader may edit its own copy; the record is not the copy."""
    r = CheckResult.passed("R1", "p", {"n": 1})
    payload = r.to_dict()
    payload["evidence"]["n"] = 99
    assert r.evidence == {"n": 1}


def test_control_b_a_result_can_still_be_copied_and_the_copy_is_sealed_too():
    """deepcopy works, and does not launder the verdict.

    `copy`'s generic reconstruction replays a dict subclass's items through
    `__setitem__`, so the first draft of this seal made `deepcopy` raise on
    every CheckResult in the package. Measured, and fixed at the root with
    `__copy__`/`__deepcopy__` that rebuild and then re-seal -- rather than by
    letting the clone come back writable, which would have made
    `copy.deepcopy(r)` the one-line way around everything above.
    """
    r = failing()
    for clone in (copy.copy(r), copy.deepcopy(r)):
        assert clone.to_dict() == r.to_dict()
        with pytest.raises(VerdictSealed):
            clone.status = Status.PASS
        with pytest.raises(VerdictSealed):
            clone.evidence["rows"] = 99


def test_control_b_measured_wrapper_still_builds_over_a_sealed_result():
    """measurement.Measured constructs CheckResults on every assignment."""
    from resilient_mlkit.measurement import Measured

    m = Measured(name="gate", metrics={"n": 1})
    assert m.passed is True
    assert m.to_result().status is Status.PASS


# ---------------------------------------------------------------------------
# RESIDUAL, disclosed rather than half-closed
# ---------------------------------------------------------------------------
def test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen():
    """STATED LIMIT, and the same one every frozen dataclass here has.

    All three of these land, and no Python-level seal stops them:
    `object.__setattr__(r, "status", ...)`, `r.__dict__["status"] = ...`, and
    `del r.__dict__["_sealed"]` followed by an ordinary assignment.
    `core.served`'s own frozen dataclasses call `object.__setattr__` in their
    `__post_init__`, so this is Python's boundary rather than this class's.

    A two-signal seal that survived the `del` was written and MEASURED: it also
    read "the evidence mapping is sealed" as proof of construction, and it broke
    the R2/T2 delegation at `checks/readiness.py:195`, which builds a new
    CheckResult from another result's evidence — the dataclass `__init__`
    assigns `evidence` before `measured_at`, so the inherited seal was live
    while the new object was still being built. Six tests red. It is not here.

    What matters is that this is a LOUD limit. Nothing reaches into `__dict__`
    by accident, and accident is what the seal exists to stop: one ordinary
    assignment in a check module, which now refuses. Pinned so the disclosure
    is a measurement, and so a future repair that closes it fails here and
    updates the text instead of re-pinning the silence.
    """
    a = failing()
    a.__dict__["status"] = Status.PASS
    assert a.to_dict()["status"] == "PASS"

    b = failing()
    object.__setattr__(b, "status", Status.PASS)
    assert b.to_dict()["status"] == "PASS"

    c = failing()
    del c.__dict__["_sealed"]
    c.status = Status.PASS
    assert c.to_dict()["status"] == "PASS"


def test_residual_a_nested_evidence_value_is_still_mutable_in_place():
    """STATED LIMIT. The seal is one level deep.

    ``r.evidence["curve"][0.25] = 9`` edits a figure inside a plain dict the
    caller put there, and the seal does not see it. Deep-freezing arbitrary
    evidence would change the type of every nested structure the eight repos
    put in their evidence, which is a blast radius M-02 did not measure and so
    did not take.

    What is closed is the verdict itself: no nested edit can change ``status``,
    add or remove a top-level evidence key, or turn an empty-evidence result
    into a passing one. This test FAILS the day the residual closes, so the
    disclosure gets updated rather than the silence re-pinned.
    """
    r = CheckResult.passed("R1", "p", {"curve": {"0.25": 0.82}})
    r.evidence["curve"]["0.25"] = 9.9
    assert r.evidence["curve"]["0.25"] == 9.9
    assert r.status is Status.PASS


# ---------------------------------------------------------------------------
# E-M21 — the seal flag was itself unsealed (verifier finding, 2026-08-31)
# ---------------------------------------------------------------------------
# M-02(b) shipped with this disclosure, in `_is_sealed.__doc__` and pinned by
# `test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen` above:
#
#     "Both are `__dict__` surgery, which defeats this exactly as it defeats
#      every frozen dataclass in this package. ... it is a LOUD limit: nothing
#      edits a verdict that way by accident, and accident is what the seal
#      exists to stop (`result.status = Status.PASS`, one ordinary assignment,
#      in a check module -- which now refuses)."
#
# The disclosure was incomplete, and measured so with the module's own
# `__file__` asserted at 943c0fd:
#
#     r = CheckResult.failed("R99", "phase-1", "a real failure")
#     r._sealed = False        # ORDINARY assignment. Not __dict__ surgery.
#     r.status = Status.PASS   # ORDINARY assignment.
#     r.to_dict()["status"]    -> 'PASS'
#
# `__setattr__` refused `_VERDICT_FIELDS` and rate-limited `_STAMP_FIELDS`, and
# passed everything else — including the one attribute whose value decides
# whether either of those clauses runs at all. The guard read a flag the caller
# it was guarding against could set.
#
# The same hole, one layer down: `SealedEvidence` declared `__slots__ =
# ("_sealed",)` and never overrode `__setattr__`, so `r.evidence._sealed =
# False` re-opened the mapping and `r.evidence["forged"] = True` landed.
#
# This is NOT the disclosed residual. `object.__setattr__` and `__dict__[...]`
# name the machinery they are subverting; `obj._sealed = False` is the same
# syntax as the accident the seal exists to stop, and it is strictly cheaper
# than either disclosed defeat. It is closed below; the three disclosed
# `__dict__` paths stay open and stay pinned, unchanged, above.


def test_em21_the_seal_flag_cannot_be_cleared_by_ordinary_assignment():
    """CONTROL A. The flag that decides whether the guard runs is guarded."""
    r = failing()
    with pytest.raises(VerdictSealed, match="_sealed"):
        r._sealed = False
    assert r._is_sealed() is True
    with pytest.raises(VerdictSealed):
        r.status = Status.PASS
    assert r.to_dict()["status"] == "FAIL"


def test_em21_the_evidence_seal_flag_cannot_be_cleared_by_ordinary_assignment():
    """CONTROL A. Same hole one layer down, in the evidence mapping."""
    r = failing()
    with pytest.raises(VerdictSealed, match="_sealed"):
        r.evidence._sealed = False
    with pytest.raises(VerdictSealed):
        r.evidence["forged"] = True
    assert dict(r.evidence) == {"rows": 3, "overlaps": 1}


def test_em21_a_flipped_verdict_cannot_flip_a_gate_aggregate():
    """CONTROL A. Why it matters: M-03 derives its verdict from these objects.

    ``GateAggregate.passed`` is a property over the results, precisely so that
    nobody can make the aggregate disagree with the checks it holds. That
    guarantee is only as strong as the checks' own seal: with the seal flag
    writable, two ordinary assignments to a member FAIL flipped
    ``passed`` False -> True and emptied ``blocking``.
    """
    ok = CheckResult.passed("R1", "p", {"n": 1})
    lost = CheckResult.failed("R2", "p", "the check measured a real failure")
    agg = GateAggregate("promotion", (ok, lost))
    assert agg.passed is False and agg.blocking == ("R2",)

    with pytest.raises(VerdictSealed):
        lost._sealed = False
    with pytest.raises(VerdictSealed):
        lost.status = Status.PASS

    assert agg.passed is False
    assert agg.blocking == ("R2",)


def test_em21_control_b_construction_and_the_runner_s_stamps_are_unmoved():
    """CONTROL B (must stay silent). The repair touches one attribute name.

    Every legitimate path still constructs, the runner's write-once stamps
    still apply, and the serialisation is byte-identical to what the same
    inputs produced before the repair.
    """
    built = [
        CheckResult.passed("R1", "p", {"n": 1}),
        CheckResult.failed("R2", "p", "why"),
        CheckResult.na("R3", "p", "why"),
        CheckResult.deferred("R4", "p", "KEY", "detail"),
        CheckResult.escalated("R5", "p", "why"),
    ]
    for r in built:
        assert r._is_sealed() is True
        payload = r.to_dict()
        assert CheckResult.from_dict(payload).to_dict() == payload
        assert json.loads(json.dumps(payload)) == payload

    r = built[1]
    r.repo = "resilient-mlkit"
    r.git_sha = "8517341"
    r.nonce = "n1"
    assert (r.repo, r.git_sha, r.nonce) == ("resilient-mlkit", "8517341", "n1")
    with pytest.raises(VerdictSealed, match="re-stamp"):
        r.git_sha = "943c0fd"

    # The R2/T2 delegation shape: a new result built from ANOTHER result's
    # already-sealed evidence mapping. This is what broke the two-signal seal
    # M-02 measured and reverted; the repair here must not resurrect it.
    inherited = CheckResult("R9", "p", Status.PASS, "", built[0].evidence)
    assert inherited.status is Status.PASS
    assert dict(inherited.evidence) == {"n": 1}
    assert inherited._is_sealed() is True


def test_em21_control_b_copies_still_round_trip_and_stay_sealed():
    """CONTROL B. ``copy``/``deepcopy`` of a formed verdict keep working."""
    r = failing()
    for clone in (copy.copy(r), copy.deepcopy(r)):
        assert clone.to_dict() == r.to_dict()
        with pytest.raises(VerdictSealed):
            clone.status = Status.PASS
        with pytest.raises(VerdictSealed):
            clone._sealed = False
