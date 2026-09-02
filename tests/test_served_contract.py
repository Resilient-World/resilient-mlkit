"""Control pairs for the served-model contract (``core.served``).

Every test here is one half of a matched pair. The POSITIVE control carries the
condition the clause exists to refuse; the NEGATIVE control is the SAME OBJECT
with the one thing changed that makes it legitimate. That pairing is the whole
point: a refusal that fires on the positive proves nothing on its own, because
a refusal that fires on everything also fires on the positive.

Four clauses, four pairs:

* the self-hash — a tampered payload against the same payload untouched;
* provenance — a data file whose bytes changed against the same file unchanged;
* the challenger decision — an unmeasurable comparison against a measurable one,
  and separately a measured loss, because the claim under test is that NA is
  distinguishable from BOTH of the other two;
* the serve-arm guard — a closed arm against an open one.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import resilient_mlkit.core.served as served_module
from resilient_mlkit.core.result import Status
from resilient_mlkit.core.served import (
    HIGHER_IS_BETTER,
    IMPOSSIBLE_MEASUREMENT,
    LOWER_IS_BETTER,
    NO_SKILL,
    NONNEGATIVE,
    POLARITY_UNDECLARED,
    ROW_SET_MISMATCH,
    ROW_SET_UNTIED,
    UNMEASURED_SKILL,
    ArtifactIntegrityError,
    ChallengerDecision,
    ClosedArm,
    Comparison,
    DataSource,
    Measurement,
    RecordedBar,
    ServeArms,
    ServedContractError,
    ServedModel,
    canonical_payload_sha256,
    challenger_decision,
    row_set_digest,
    seal,
    sha256_file,
    skill,
    verify_at_load,
)

# Which `core.served` this suite actually exercised. A control pair driven
# against a different installed copy of the package proves nothing about the
# tree under test, and the failure mode is silent -- see the standing
# `module.__file__` discipline. Printed on failure by pytest's assertion
# rewriting, and asserted so a stale wheel on the path cannot masquerade.
SERVED_MODULE_FILE = served_module.__file__


def test_the_suite_is_driving_this_tree_s_core_served():
    assert SERVED_MODULE_FILE.endswith("resilient_mlkit/core/served.py")
    assert "site-packages" not in SERVED_MODULE_FILE

# The artifact shape, parameterised on nothing that matters to the hash. The
# positive and negative controls differ by exactly one byte of one value.
PAYLOAD = {
    "artifact_type": "served_model",
    "model_id": "ridge_prior_residual_v3",
    "fit": {"family": "ridge", "alpha": 1.0, "features": ["a", "b"]},
    "training_data": [
        {"path": "data/panel.parquet", "sha256": "", "role": "training"},
    ],
    "recorded_bar": {
        "name": "persistence_t_minus_1",
        "metrics": ["mae", "rmse"],
        "description": "the county's own published value for year - 1",
    },
    "measurements": [
        {
            "arm": "val",
            "metric": "mae",
            "value": 71.36,
            "artifact": "reports/validation/observed_panel_model.json",
            "artifact_sha256": "f" * 64,
        },
    ],
}


@pytest.fixture
def panel(tmp_path):
    """A data file on disk, and a payload that pins its real bytes."""
    path = tmp_path / "data" / "panel.parquet"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"county,year,yield\n01001,2019,812\n")
    payload = json.loads(json.dumps(PAYLOAD))
    payload["training_data"][0]["sha256"] = sha256_file(path)
    return tmp_path, seal(payload)


# ---------------------------------------------------------------------------
# Clause 1 — the self-hash, verified at load
# ---------------------------------------------------------------------------
def test_self_hash_negative_control_untampered_artifact_loads(panel):
    """NEGATIVE. The sealed payload verifies and becomes a record."""
    root, payload = panel
    model = verify_at_load(payload, root=root)
    assert model.model_id == "ridge_prior_residual_v3"
    assert model.artifact_sha256 == payload["artifact_sha256"]
    assert model.recorded_bar.name == "persistence_t_minus_1"


def test_self_hash_positive_control_one_changed_value_refuses(panel):
    """POSITIVE. One field edited after sealing; everything else identical."""
    root, payload = panel
    tampered = json.loads(json.dumps(payload))
    tampered["fit"]["alpha"] = 1.0000001
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        verify_at_load(tampered, root=root)


def test_self_hash_positive_control_unhashed_artifact_refuses(panel):
    """POSITIVE. An artifact with no hash at all is refused, not accepted."""
    root, payload = panel
    unhashed = {k: v for k, v in payload.items() if k != "artifact_sha256"}
    with pytest.raises(ArtifactIntegrityError, match="carries no artifact_sha256"):
        verify_at_load(unhashed, root=root)


def test_self_hash_is_the_digest_the_fleet_already_committed():
    """The digest is the fleet's, not a new one.

    Three repos independently wrote the same computation, and every committed
    champion artifact carries its output. A contract that changed the digest
    would invalidate all of them, so the serialisation is pinned here as a
    literal expectation rather than left to whatever ``json.dumps`` defaults to.
    """
    body = {"b": 2, "a": 1}
    import hashlib

    expected = hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
    assert canonical_payload_sha256(body) == expected
    assert canonical_payload_sha256({**body, "artifact_sha256": "x"}) == expected


def test_self_hash_refuses_a_payload_that_cannot_be_serialised_canonically():
    """A NaN has no JSON spelling other readers can parse back."""
    with pytest.raises(ValueError):
        canonical_payload_sha256({"metric": float("nan")})


def test_load_from_disk_verifies(tmp_path, panel):
    root, payload = panel
    artifact = root / "champion.json"
    artifact.write_text(json.dumps(payload, indent=2))
    model = ServedModel.load(artifact, root=root)
    assert model.artifact_sha256 == payload["artifact_sha256"]

    artifact.write_text(json.dumps({**payload, "model_id": "other"}, indent=2))
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        ServedModel.load(artifact, root=root)


# ---------------------------------------------------------------------------
# Clause 2 — provenance against the data on disk
# ---------------------------------------------------------------------------
def test_provenance_negative_control_matching_bytes_verify(panel):
    """NEGATIVE. The file on disk is the file the record pins."""
    root, payload = panel
    model = verify_at_load(payload)
    verified = model.verify_provenance(root)
    assert verified["data/panel.parquet"] == payload["training_data"][0]["sha256"]


def test_provenance_positive_control_one_changed_byte_refuses(panel):
    """POSITIVE. Same path, same record, one byte of the data different."""
    root, payload = panel
    (root / "data" / "panel.parquet").write_bytes(
        b"county,year,yield\n01001,2019,813\n"
    )
    model = verify_at_load(payload)
    with pytest.raises(Exception, match="hashes to"):
        model.verify_provenance(root)


def test_provenance_positive_control_absent_file_refuses(panel):
    """POSITIVE. Absent is a refusal, not a pass by default."""
    root, payload = panel
    (root / "data" / "panel.parquet").unlink()
    model = verify_at_load(payload)
    with pytest.raises(Exception, match="is absent"):
        model.verify_provenance(root)


def test_verify_at_load_runs_provenance_when_given_a_root(panel):
    """The two refusals are one call, so a caller cannot do half of it."""
    root, payload = panel
    (root / "data" / "panel.parquet").write_bytes(b"different")
    with pytest.raises(Exception, match="hashes to"):
        verify_at_load(payload, root=root)


def test_a_record_pinning_no_data_is_refused(panel):
    root, payload = panel
    stripped = seal({**payload, "training_data": []})
    with pytest.raises(ArtifactIntegrityError, match="pins no training data"):
        verify_at_load(stripped, root=root)


def test_a_data_source_without_a_hash_pins_nothing():
    with pytest.raises(ArtifactIntegrityError, match="carries no sha256"):
        DataSource(path="data/panel.parquet", sha256="")


# ---------------------------------------------------------------------------
# Clause 3 — the challenger decision, where NA is neither PASS nor FAIL
# ---------------------------------------------------------------------------
BAR = "persistence_t_minus_1"
METRICS = ("mae", "rmse")

#: A real row set, and a real digest over it. The fixture computes the tie the
#: way an adopter must, rather than writing a placeholder that would be equal
#: to every other placeholder.
ROWS = [["01001", 2000 + i] for i in range(500)]
SAME_ROWS = row_set_digest(ROWS)
FEWER_ROWS = row_set_digest(ROWS[:-1])

#: An honest row-set tie, spelled once. Every control below that means to
#: exercise a clause OTHER than the row-set one carries it, so that the clause
#: under test is the only thing wrong with the comparison — a control with two
#: defects in it does not prove which one the gate reacted to.
TIED = {"candidate_row_digest": SAME_ROWS, "reference_row_digest": SAME_ROWS}


def comparisons(candidate, reference, **kw):
    """MAE and RMSE, declared for what they are, and tied to the rows.

    ``polarity``/``domain`` are declarations this helper makes on the caller's
    behalf because MAE and RMSE genuinely are lower-is-better and genuinely
    cannot be negative. The two row digests are equal because both figures here
    genuinely are computed over the same 500 rows. Every assertion in the tests
    below is unchanged by either; what changed on 2026-08-31 (M-01, M-06) is
    that the contract now requires both facts to be STATED rather than assumed,
    and both undeclared cases have their own pins —
    ``test_m01_control_a_an_undeclared_polarity_is_na_not_lower_is_better`` and
    ``test_m06_control_a_absent_digests_are_na_not_a_pass``.
    """
    return [
        Comparison(
            reference=BAR,
            metric=metric,
            candidate_value=candidate,
            reference_value=reference,
            n_rows=kw.pop("n_rows", 500),
            arm=kw.pop("arm", "val"),
            polarity=kw.pop("polarity", LOWER_IS_BETTER),
            domain=kw.pop("domain", NONNEGATIVE),
            candidate_row_digest=kw.pop("candidate_row_digest", SAME_ROWS),
            reference_row_digest=kw.pop("reference_row_digest", SAME_ROWS),
            **kw,
        )
        for metric in METRICS
    ]


def test_challenger_negative_control_measured_win_passes():
    """NEGATIVE. A measured, strictly positive skill is a PASS."""
    decision = challenger_decision(
        comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    assert decision.measured is True
    assert decision.skill["mae"] == pytest.approx(0.2)


def test_challenger_positive_control_measured_loss_fails():
    """POSITIVE (one half). A measured loss is a FAIL, and it keeps its number."""
    decision = challenger_decision(
        comparisons(120.0, 100.0), recorded_bar=BAR, metrics=METRICS
    )
    assert decision.status is Status.FAIL
    assert decision.promotable is False
    assert decision.measured is True
    assert decision.skill["mae"] == pytest.approx(-0.2)


def test_challenger_positive_control_unmeasurable_comparison_is_na_not_fail():
    """POSITIVE (the other half). The claim under test, stated directly.

    An unmeasured comparison must render as neither a pass nor a failure. The
    assertions below are the three things that would each, on their own, make
    the contract useless: an NA that is promotable, an NA that reads as FAIL,
    and an NA that carries a skill number somebody downstream could quote.
    """
    decision = challenger_decision(
        [
            Comparison(
                reference=BAR,
                metric=metric,
                candidate_value=80.0,
                reference_value=None,
                n_rows=500,
                arm="val",
                polarity=LOWER_IS_BETTER,
                domain=NONNEGATIVE,
                **TIED,
                unmeasured_reason="the bar could not be scored on these rows",
            )
            for metric in METRICS
        ],
        recorded_bar=BAR,
        metrics=METRICS,
    )
    assert decision.status is Status.NA
    assert decision.status is not Status.FAIL
    assert decision.promotable is False
    assert decision.measured is False
    assert all(v is None for v in decision.skill.values())
    assert decision.refusal_class == "UNMEASURED_SKILL"
    assert "not a pass" in decision.reason


def test_a_zero_reference_is_na_not_a_promotion():
    """The torrent/chokepoint divergence, decided.

    ``torrent/.../champion_challenger.py:128`` maps a zero baseline to a
    deviation of 0.0, which clears the tolerance and PROMOTES.
    ``chokepoint/.../champion_challenger.py:209-218`` returns NA on the same
    condition. The contract takes chokepoint's answer.
    """
    assert skill(0.0, 0.0, polarity=LOWER_IS_BETTER) is None
    decision = challenger_decision(
        comparisons(0.0, 0.0), recorded_bar=BAR, metrics=METRICS
    )
    assert decision.status is Status.NA
    assert decision.promotable is False


def test_not_being_compared_is_a_fail_not_an_na():
    """Not compared is a fact about the candidate, not about the instrument."""
    decision = challenger_decision(
        [
            Comparison(
                reference="some_other_reference",
                metric="mae",
                candidate_value=80.0,
                reference_value=100.0,
                n_rows=500,
                polarity=LOWER_IS_BETTER,
                domain=NONNEGATIVE,
            )
        ],
        recorded_bar=BAR,
        metrics=("mae",),
    )
    assert decision.status is Status.FAIL
    assert decision.refusal_class == "NOT_COMPARED"


def test_a_comparison_over_no_rows_is_na():
    decision = challenger_decision(
        comparisons(80.0, 100.0, n_rows=0), recorded_bar=BAR, metrics=METRICS
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == "NO_ROWS"


def test_a_reference_scored_on_different_rows_is_na():
    """The reference's digest is over 499 of the candidate's 500 rows.

    Written as unequal DIGESTS since M-06; it used to be written as
    ``row_matched=False``, an assertion the caller made. The clause under test
    is unchanged, and it is now driven by evidence rather than by the fixture
    telling the gate what to conclude.
    """
    decision = challenger_decision(
        comparisons(80.0, 100.0, reference_row_digest=FEWER_ROWS),
        recorded_bar=BAR,
        metrics=METRICS,
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == "ROW_SET_MISMATCH"


def test_evidence_from_the_wrong_arm_is_na_not_a_pass():
    """chokepoint's val-only refusal, in the contract."""
    decision = challenger_decision(
        comparisons(80.0, 100.0, arm="val"),
        recorded_bar=BAR,
        metrics=METRICS,
        deciding_arm="test",
        arm_refusal_note="a second read of one test block is not a second test.",
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == "ARM_MISMATCH"
    assert "second read" in decision.reason


def test_a_win_on_one_metric_and_a_loss_on_the_other_fails():
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 80.0, 100.0, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            ),
            Comparison(
                BAR, "rmse", 120.0, 100.0, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            ),
        ],
        recorded_bar=BAR,
        metrics=METRICS,
    )
    assert decision.status is Status.FAIL
    assert decision.skill["mae"] > 0.0
    assert decision.skill["rmse"] < 0.0


# -- the structural guarantees, tested as constructions that cannot be made --
def test_an_na_decision_cannot_be_given_a_skill_number():
    with pytest.raises(ServedContractError, match="reports skill values"):
        ChallengerDecision(
            status=Status.NA,
            reason="unmeasured",
            recorded_bar=BAR,
            metrics=("mae",),
            skill={"mae": 0.3},
        )


def test_a_pass_cannot_be_built_on_an_unmeasured_metric():
    with pytest.raises(ServedContractError, match="no measured skill"):
        ChallengerDecision(
            status=Status.PASS,
            reason="looks good",
            recorded_bar=BAR,
            metrics=("mae",),
            skill={"mae": None},
        )


def test_a_pass_cannot_be_built_on_a_losing_skill():
    with pytest.raises(ServedContractError, match="non-positive skill"):
        ChallengerDecision(
            status=Status.PASS,
            reason="looks good",
            recorded_bar=BAR,
            metrics=("mae",),
            skill={"mae": -0.1},
        )


def test_promotable_is_derived_and_cannot_be_set():
    """The field does not exist, so no caller can disagree with the status."""
    decision = ChallengerDecision(
        status=Status.NA,
        reason="unmeasured",
        recorded_bar=BAR,
        metrics=("mae",),
        skill={"mae": None},
    )
    assert decision.promotable is False
    with pytest.raises(AttributeError):
        decision.promotable = True  # type: ignore[misc]


def test_a_decision_cannot_take_a_status_outside_pass_fail_na():
    with pytest.raises(ServedContractError, match="not one of them"):
        ChallengerDecision(
            status=Status.DEFERRED,
            reason="waiting on a key",
            recorded_bar=BAR,
            metrics=("mae",),
            skill={"mae": None},
        )


def test_a_refusal_must_say_why():
    with pytest.raises(ServedContractError, match="must say why"):
        ChallengerDecision(
            status=Status.FAIL,
            reason="",
            recorded_bar=BAR,
            metrics=("mae",),
            skill={"mae": -0.1},
        )


def test_a_gate_with_no_decision_metric_is_refused():
    with pytest.raises(ServedContractError, match="decides on nothing"):
        challenger_decision(comparisons(80.0, 100.0), recorded_bar=BAR, metrics=())


def test_decision_serialises_na_without_a_number():
    decision = challenger_decision(
        comparisons(80.0, None), recorded_bar=BAR, metrics=METRICS
    )
    payload = decision.to_dict()
    assert payload["status"] == "NA"
    assert payload["promotable"] is False
    assert payload["skill_vs_recorded_bar"] == {"mae": "NA", "rmse": "NA"}


# ---------------------------------------------------------------------------
# Clause 4 — the serve-arm guard
# ---------------------------------------------------------------------------
ARMS = ServeArms(
    open={"val", "train"},
    closed={
        "test": "the test arm is closed at two reads (2026-08-23 and 2026-08-24); "
                "a third read needs a signatory-accepted read recorded in "
                "docs/ESCALATIONS.md"
    },
)


def test_serve_arm_negative_control_an_open_arm_is_served():
    """NEGATIVE. The guard is silent on the arm the product serves."""
    assert ARMS.require("val") == "val"
    assert ARMS.require("train") == "train"
    assert ARMS.is_open("val") is True


def test_serve_arm_positive_control_a_closed_arm_refuses():
    """POSITIVE. Same guard, same call, the closed arm."""
    with pytest.raises(ClosedArm, match="closed at two reads"):
        ARMS.require("test")
    assert ARMS.is_open("test") is False


def test_serve_arm_positive_control_an_undeclared_arm_refuses():
    """An arm nobody declared is not a licence to guess which rows were meant."""
    with pytest.raises(ClosedArm, match="not declared by this product"):
        ARMS.require("holdout")


def test_a_product_may_declare_test_as_its_deciding_arm():
    """The policy is data. chokepoint decides on test; that must stay expressible."""
    arms = ServeArms(open={"test"}, closed={"val": "val evidence does not decide here"})
    assert arms.require("test") == "test"
    with pytest.raises(ClosedArm):
        arms.require("val")


def test_an_arm_cannot_be_open_and_closed_at_once():
    with pytest.raises(ServedContractError, match="both open and closed"):
        ServeArms(open={"val"}, closed={"val": "closed"})


def test_a_closure_must_carry_a_reason():
    with pytest.raises(ServedContractError, match="carry no reason"):
        ServeArms(open={"val"}, closed={"test": "  "})


def test_a_policy_with_no_open_arm_serves_nothing():
    with pytest.raises(ServedContractError, match="serves nothing"):
        ServeArms(open=set())


# ---------------------------------------------------------------------------
# The record's own invariants
# ---------------------------------------------------------------------------
def test_a_measurement_without_a_value_must_say_why():
    with pytest.raises(ArtifactIntegrityError, match="no value and no reason"):
        Measurement(arm="test", metric="mae", value=None)


def test_a_measurement_with_a_value_must_cite_its_artifact():
    with pytest.raises(ArtifactIntegrityError, match="no artifact path and sha256"):
        Measurement(arm="val", metric="mae", value=71.36)


def test_an_unmeasured_measurement_is_legitimate_with_a_reason():
    m = Measurement(
        arm="test", metric="mae", value=None,
        unmeasured_reason="the test arm is closed at two reads",
    )
    assert m.measured is False


def test_a_non_finite_measurement_is_not_a_measurement():
    with pytest.raises(ArtifactIntegrityError, match="not a measurement"):
        Measurement(
            arm="val", metric="mae", value=float("inf"),
            artifact="reports/x.json", artifact_sha256="f" * 64,
        )


def test_a_recorded_bar_must_name_a_metric():
    with pytest.raises(ArtifactIntegrityError, match="names no decision metric"):
        RecordedBar(name="persistence", metrics=())


# ---------------------------------------------------------------------------
# M-01 — polarity and domain are DECLARED, never assumed (HOLE 1)
# ---------------------------------------------------------------------------
# Driven at 8517341 before this block existed, with
# `resilient_mlkit.core.served.__file__` asserted in the driver:
#
#   mape -0.05 vs 0.20 -> PASS, promotable=True, skill {'mape': 1.25}
#   r2    0.10 vs 0.90 -> PASS, promotable=True, skill {'r2': 0.8888888888888888}
#
# Both are the same root cause: `skill()` hard-coded `1 - candidate/reference`,
# which is the lower-is-better formula, and applied it to every metric name a
# caller passed without asking what direction that metric runs in or what
# values it can take. A model that is worse on r2 by eight tenths promotes, and
# an arithmetically impossible MAPE promotes hardest of all.
#
# The repair does NOT introduce a metric-name table. E-038 is the standing
# lesson: a guard that enumerates the names it expects is blind to every name
# outside the list, and `csi` in a word list does not catch
# `critical_success_index`. Polarity and domain are DATA the caller declares
# on the comparison, in the same shape `ServeArms` already makes the arm policy
# data, and a comparison that declares neither is NA rather than assumed.


def test_m01_control_a_a_negative_value_for_a_nonnegative_metric_refuses():
    """CONTROL A. The drive that returned PASS/1.25 at 8517341."""
    decision = challenger_decision(
        [
            Comparison(
                reference=BAR,
                metric="mape",
                candidate_value=-0.05,
                reference_value=0.20,
                n_rows=500,
                arm="val",
                polarity=LOWER_IS_BETTER,
                domain=NONNEGATIVE,
                **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mape",),
    )
    assert decision.status is Status.NA
    assert decision.promotable is False
    assert decision.refusal_class == IMPOSSIBLE_MEASUREMENT
    assert "mape" in decision.reason and "-0.05" in decision.reason
    assert all(v is None for v in decision.skill.values())


def test_m01_control_a_an_impossible_reference_refuses_too():
    """Both operands are checked. A bar nobody could have measured is not a bar."""
    decision = challenger_decision(
        [
            Comparison(
                reference=BAR,
                metric="mape",
                candidate_value=0.05,
                reference_value=-0.20,
                n_rows=500,
                arm="val",
                polarity=LOWER_IS_BETTER,
                domain=NONNEGATIVE,
                **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mape",),
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == IMPOSSIBLE_MEASUREMENT


def test_m01_control_a_an_undeclared_polarity_is_na_not_lower_is_better():
    """CONTROL A. The r2 drive: 0.10 vs 0.90 PASSed at 8517341 on skill 0.8889.

    Undeclared is NA, not "probably lower-is-better". The silent assumption is
    the defect; replacing it with a different silent assumption would be the
    same defect wearing the other sign.
    """
    decision = challenger_decision(
        [Comparison(BAR, "r2", 0.10, 0.90, 500, arm="val", **TIED)],
        recorded_bar=BAR,
        metrics=("r2",),
    )
    assert decision.status is Status.NA
    assert decision.promotable is False
    assert decision.refusal_class == POLARITY_UNDECLARED
    assert "r2" in decision.reason
    assert all(v is None for v in decision.skill.values())


def test_m01_control_a_a_declared_higher_is_better_loss_fails():
    """CONTROL A. Same numbers, now declared: a worse model is a FAIL."""
    decision = challenger_decision(
        [
            Comparison(
                BAR, "r2", 0.10, 0.90, 500, arm="val",
                polarity=HIGHER_IS_BETTER, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("r2",),
    )
    assert decision.status is Status.FAIL
    assert decision.promotable is False
    assert decision.refusal_class == NO_SKILL
    # candidate/reference - 1, not 1 - candidate/reference.
    assert decision.skill["r2"] == pytest.approx(0.10 / 0.90 - 1.0)
    assert decision.skill["r2"] < 0.0


def test_m01_a_declared_higher_is_better_win_passes_on_the_right_formula():
    """The other half of the same clause: a genuinely better r2 promotes."""
    decision = challenger_decision(
        [
            Comparison(
                BAR, "r2", 0.90, 0.10, 500, arm="val",
                polarity=HIGHER_IS_BETTER, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("r2",),
    )
    assert decision.status is Status.PASS
    assert decision.skill["r2"] == pytest.approx(0.90 / 0.10 - 1.0)


def test_m01_control_b_an_honest_lower_is_better_loss_still_fails():
    """CONTROL B (must not move). 0.25 against a 0.20 bar is still a loss."""
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 0.25, 0.20, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mae",),
    )
    assert decision.status is Status.FAIL
    assert decision.refusal_class == NO_SKILL


def test_m01_control_b_an_honest_lower_is_better_win_promotes_bit_identically():
    """CONTROL B (must not move), to the bit.

    0.2500000000000001 is what `1 - 0.15/0.20` evaluates to in IEEE754 double,
    and it is what this gate emitted at 8517341. `pytest.approx` would pass on
    a repair that quietly changed the arithmetic, so the comparison is exact.
    """
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 0.15, 0.20, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mae",),
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    assert decision.skill["mae"] == 1.0 - 0.15 / 0.20
    assert repr(decision.skill["mae"]) == "0.2500000000000001"


def test_m01_control_b_the_zero_reference_and_non_finite_refusals_are_unmoved():
    """CONTROL B (must not move). The refusals that already existed still fire."""
    assert skill(0.0, 0.0, polarity=LOWER_IS_BETTER) is None
    assert skill(1.0, -1.0, polarity=LOWER_IS_BETTER) is None
    assert skill(float("nan"), 1.0, polarity=LOWER_IS_BETTER) is None
    assert skill(float("inf"), 1.0, polarity=LOWER_IS_BETTER) is None
    assert skill(1.0, float("nan"), polarity=HIGHER_IS_BETTER) is None
    assert skill(None, 1.0, polarity=LOWER_IS_BETTER) is None
    assert skill(1.0, None, polarity=HIGHER_IS_BETTER) is None
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 0.0, 0.0, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mae",),
    )
    assert decision.status is Status.NA
    assert decision.refusal_class == UNMEASURED_SKILL


def test_m01_an_undeclared_polarity_makes_skill_unmeasurable_at_the_function():
    """The refusal is in `skill()` itself, not only in the decision wrapper.

    A caller reaching past `challenger_decision` to the primitive gets the same
    answer, so the clause cannot be stepped around by importing one level down.
    """
    assert skill(0.15, 0.20) is None
    assert skill(0.15, 0.20, polarity=None) is None


def test_m01_a_comparison_cannot_declare_a_polarity_that_is_not_one():
    with pytest.raises(ServedContractError, match="polarity"):
        Comparison(BAR, "mae", 0.15, 0.20, 500, arm="val", polarity="lower")


def test_m01_a_comparison_cannot_declare_a_domain_that_is_not_one():
    with pytest.raises(ServedContractError, match="domain"):
        Comparison(
            BAR, "mae", 0.15, 0.20, 500, arm="val",
            polarity=LOWER_IS_BETTER, domain="positive-ish",
        )


def test_m01_the_declaration_travels_in_the_evidence():
    """A reader of the record can see what direction the gate decided in.

    A polarity that lives only in the deciding process is a polarity nobody can
    audit afterwards, which is how the assumption survived unexamined.
    """
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 0.15, 0.20, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            )
        ],
        recorded_bar=BAR,
        metrics=("mae",),
    )
    row = decision.to_dict()["evidence"]["comparisons"][0]
    assert row["polarity"] == LOWER_IS_BETTER
    assert row["domain"] == NONNEGATIVE


# ---------------------------------------------------------------------------
# M-02(a) — a verdict object refuses construction-time forgery (HOLE 2a)
# ---------------------------------------------------------------------------
# Driven at 8517341:
#
#   ChallengerDecision(status=Status.PASS, reason="nothing was compared",
#                      recorded_bar=BAR, metrics=(), skill={})
#     -> PASS, promotable=True, metrics=()
#
# `challenger_decision()` refuses an empty metric set ("a gate that decides on
# nothing passes everything") -- but that refusal lives in the FUNCTION, and
# the verdict TYPE is public, constructible, and was reachable around it. Every
# guard in `__post_init__` is written as a comprehension over `self.metrics`,
# so all of them are vacuously satisfied by an empty tuple: no metric is
# missing from `skill`, none is unmeasured, none has non-positive skill. The
# object that exists to make "PASS" mean something rendered a PASS that meant
# nothing, and `promotable` -- correctly derived, doing its job -- said True.


def test_m02a_control_a_a_decision_over_no_metric_cannot_be_constructed():
    """CONTROL A. The drive that returned a promotable PASS at 8517341."""
    with pytest.raises(ServedContractError, match="declares no metric"):
        ChallengerDecision(
            status=Status.PASS,
            reason="nothing was compared",
            recorded_bar=BAR,
            metrics=(),
            skill={},
        )


def test_m02a_control_a_the_empty_metric_set_is_refused_on_every_status():
    """Not a PASS-only clause. An NA over no metric is equally uninformative."""
    for status, reason in (
        (Status.PASS, "everything is fine"),
        (Status.FAIL, "it lost"),
        (Status.NA, "could not measure"),
    ):
        with pytest.raises(ServedContractError, match="declares no metric"):
            ChallengerDecision(
                status=status, reason=reason, recorded_bar=BAR,
                metrics=(), skill={},
            )


def test_m02a_control_b_the_function_level_refusal_is_unmoved():
    """CONTROL B. The guard that already existed still fires, with its wording."""
    with pytest.raises(ServedContractError, match="decides on nothing"):
        challenger_decision(comparisons(80.0, 100.0), recorded_bar=BAR, metrics=())


def test_m02a_control_b_every_decision_the_function_builds_still_builds():
    """CONTROL B. All eight lanes of challenger_decision construct as before."""
    lanes = {
        "CLEARS_BAR": challenger_decision(
            comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS),
        "NO_SKILL": challenger_decision(
            comparisons(120.0, 100.0), recorded_bar=BAR, metrics=METRICS),
        "NO_ROWS": challenger_decision(
            comparisons(80.0, 100.0, n_rows=0), recorded_bar=BAR, metrics=METRICS),
        "UNMEASURED_SKILL": challenger_decision(
            comparisons(80.0, None), recorded_bar=BAR, metrics=METRICS),
        "ARM_MISMATCH": challenger_decision(
            comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS,
            deciding_arm="test"),
        "NOT_COMPARED": challenger_decision(
            comparisons(80.0, 100.0), recorded_bar="another_bar",
            metrics=METRICS),
    }
    assert {k: v.refusal_class for k, v in lanes.items()} == {
        k: k for k in lanes
    }
    assert lanes["CLEARS_BAR"].promotable is True
    assert all(v.promotable is False for k, v in lanes.items() if k != "CLEARS_BAR")


def test_m02a_control_b_a_one_metric_decision_is_still_legitimate():
    """The refusal is about ZERO metrics, not about small metric sets."""
    d = ChallengerDecision(
        status=Status.PASS, reason="won", recorded_bar=BAR,
        metrics=("mae",), skill={"mae": 0.2},
    )
    assert d.promotable is True


# ---------------------------------------------------------------------------
# M-06 — `row_matched` is derived from row-set identity, never asserted
# ---------------------------------------------------------------------------
# Driven at 8517341:
#
#   c = Comparison(bar, "mae", 80.0, 100.0, 500, arm="val")
#   c.row_matched                       -> True
#   challenger_decision([c], ...)       -> PASS, promotable=True
#
# The gate's row-set clause was real and it fired correctly -- on a value the
# CALLER supplied, defaulting to True. So the clause protected exactly the
# comparisons whose authors had already thought about row sets, and every
# comparison that had never thought about them made the strongest possible
# claim about them for free. `row_matched: bool = True` is the whole defect in
# one line of a field list.
#
# It is now derived from two content digests and has no init parameter at all:
# both present and equal -> True; present and unequal -> False; either absent
# -> None, which is UNTIED and is NA at the gate. That third state is the one
# the old field could not hold, and it is the one almost every real comparison
# in the fleet is actually in.


def test_m06_control_a_the_caller_assertion_cannot_be_spelled_any_more():
    """CONTROL A. There is no argument to pass, so there is nothing to assert."""
    with pytest.raises(TypeError, match="row_matched"):
        Comparison(
            BAR, "mae", 80.0, 100.0, 500, arm="val",
            polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
            row_matched=True,  # type: ignore[call-arg]
        )


def test_m06_control_a_unequal_digests_are_a_mismatch_whatever_the_caller_wants():
    """CONTROL A. Content decides. The caller has no vote left to cast."""
    c = Comparison(
        BAR, "mae", 80.0, 100.0, 500, arm="val",
        polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
        candidate_row_digest=SAME_ROWS, reference_row_digest=FEWER_ROWS,
    )
    assert c.row_matched is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.row_matched = True  # frozen; type: ignore[misc]
    decision = challenger_decision(
        comparisons(80.0, 100.0, reference_row_digest=FEWER_ROWS),
        recorded_bar=BAR, metrics=METRICS,
    )
    assert decision.status is Status.NA
    assert decision.promotable is False
    assert decision.refusal_class == ROW_SET_MISMATCH


def test_m06_control_a_absent_digests_are_na_not_a_pass():
    """CONTROL A. The drive that returned PASS at 8517341, verbatim."""
    c = Comparison(BAR, "mae", 80.0, 100.0, 500, arm="val",
                   polarity=LOWER_IS_BETTER, domain=NONNEGATIVE)
    assert c.row_matched is None
    decision = challenger_decision([c], recorded_bar=BAR, metrics=("mae",))
    assert decision.status is Status.NA
    assert decision.promotable is False
    assert decision.refusal_class == ROW_SET_UNTIED
    assert all(v is None for v in decision.skill.values())


def test_m06_control_a_one_side_tied_is_still_untied():
    """A tie needs two ends. One digest ties a figure to nothing."""
    for kw in (
        {"candidate_row_digest": SAME_ROWS},
        {"reference_row_digest": SAME_ROWS},
    ):
        c = Comparison(BAR, "mae", 80.0, 100.0, 500, arm="val",
                       polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **kw)
        assert c.row_matched is None
        d = challenger_decision([c], recorded_bar=BAR, metrics=("mae",))
        assert d.refusal_class == ROW_SET_UNTIED


def test_m06_control_a_untied_and_mismatched_are_different_refusals():
    """The two facts stay apart, in the class and in the serialisation.

    Collapsing "nobody said" into "they differ" sends a reader looking for a
    row split that does not exist; collapsing it the other way is the defect
    this item closes.
    """
    untied = challenger_decision(
        [Comparison(BAR, "mae", 80.0, 100.0, 500, arm="val",
                    polarity=LOWER_IS_BETTER, domain=NONNEGATIVE)],
        recorded_bar=BAR, metrics=("mae",),
    )
    mismatched = challenger_decision(
        [Comparison(BAR, "mae", 80.0, 100.0, 500, arm="val",
                    polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
                    candidate_row_digest=SAME_ROWS,
                    reference_row_digest=FEWER_ROWS)],
        recorded_bar=BAR, metrics=("mae",),
    )
    assert untied.refusal_class == ROW_SET_UNTIED
    assert mismatched.refusal_class == ROW_SET_MISMATCH
    assert untied.refusal_class != mismatched.refusal_class


def test_m06_control_a_a_placeholder_tie_is_refused_by_name():
    """Two placeholders are equal to each other, so a tie in anything but
    content is a tie that always holds."""
    for digest in ("same", "", " " * 64, "Z" * 64, "a" * 63, "A" * 64):
        if digest == "":
            continue
        with pytest.raises(ServedContractError, match="not a sha256"):
            Comparison(
                BAR, "mae", 80.0, 100.0, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
                candidate_row_digest=digest, reference_row_digest=digest,
            )


def test_m06_control_b_equal_digests_give_the_bit_identical_honest_skill():
    """CONTROL B (must not move). The honest path is unchanged, to the bit."""
    decision = challenger_decision(
        comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    assert decision.skill["mae"] == 1.0 - 80.0 / 100.0
    assert repr(decision.skill["mae"]) == "0.19999999999999996"
    fine = challenger_decision(
        comparisons(0.15, 0.20), recorded_bar=BAR, metrics=METRICS
    )
    assert repr(fine.skill["mae"]) == "0.2500000000000001"


def test_m06_control_b_the_negative_row_count_refusal_is_unmoved():
    with pytest.raises(ServedContractError, match="not a row count"):
        Comparison(BAR, "mae", 80.0, 100.0, -1, arm="val",
                   polarity=LOWER_IS_BETTER, domain=NONNEGATIVE, **TIED)


def test_m06_control_b_row_set_digest_is_order_invariant_and_content_sensitive():
    """The one definition of the tie, exercised as a definition."""
    assert row_set_digest(ROWS) == row_set_digest(list(reversed(ROWS)))
    assert row_set_digest(ROWS) != row_set_digest(ROWS[:-1])
    # A row scored twice on one side is a real difference in what was compared.
    assert row_set_digest(ROWS) != row_set_digest([*ROWS, ROWS[0]])
    assert len(row_set_digest(ROWS)) == 64
    with pytest.raises(ServedContractError, match="identifies nothing"):
        row_set_digest([])


def test_m06_the_digests_and_the_derivation_travel_in_the_evidence():
    decision = challenger_decision(
        comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS
    )
    row = decision.to_dict()["evidence"]["comparisons"][0]
    assert row["candidate_row_digest"] == SAME_ROWS
    assert row["reference_row_digest"] == SAME_ROWS
    assert row["row_matched"] is True
    untied_row = Comparison(
        BAR, "mae", 80.0, 100.0, 500, arm="val",
        polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
    ).to_dict()
    # "NA", never False: an untied comparison is not a mismatched one.
    assert untied_row["row_matched"] == "NA"
    assert untied_row["candidate_row_digest"] == "NA"


# ---------------------------------------------------------------------------
# FOUND BY ATTACKING THE ABOVE — three holes in the repairs themselves
# ---------------------------------------------------------------------------
# Each of these was reachable on the branch AFTER M-01/M-02/M-03/M-06 landed
# and before this block, driven with core.served.__file__ asserted. They are
# in the surface this train built, so they are this train's to close.


def test_attack_a_pass_cannot_carry_a_nan_skill():
    """`float('nan') <= 0.0` is False, so a NaN skill cleared the bar clause.

    Driven: ChallengerDecision(status=PASS, ..., skill={"m": nan}) constructed
    and reported promotable=True.
    """
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ServedContractError, match="non-finite skill"):
            ChallengerDecision(
                status=Status.PASS, reason="won", recorded_bar=BAR,
                metrics=("mae",), skill={"mae": value},
            )


def test_attack_a_non_finite_skill_is_refused_on_a_fail_too():
    """Not a PASS-only clause: a FAIL reporting NaN reports nothing."""
    with pytest.raises(ServedContractError, match="non-finite skill"):
        ChallengerDecision(
            status=Status.FAIL, reason="lost", recorded_bar=BAR,
            metrics=("mae",), skill={"mae": float("nan")},
        )


def test_attack_the_skill_map_cannot_be_wider_than_the_declared_metrics():
    """A figure nobody decided on, sitting where decided figures sit.

    Driven: skill={"mae": 0.2, "other": -9.0} on metrics=("mae",) constructed,
    and `skill_vs_recorded_bar` carried the -9.0 downstream indistinguishably.
    """
    with pytest.raises(ServedContractError, match="reports skill for"):
        ChallengerDecision(
            status=Status.PASS, reason="won", recorded_bar=BAR,
            metrics=("mae",), skill={"mae": 0.2, "other": -9.0},
        )


def test_attack_to_dict_does_not_hand_out_the_decision_s_own_evidence():
    """`dict(evidence)` was shallow, and the comparisons live one level down.

    Driven: `d.to_dict()["evidence"]["comparisons"][0]["skill"] = 99` changed
    what `d.to_dict()` returned on the next call.
    """
    d = challenger_decision(
        comparisons(80.0, 100.0), recorded_bar=BAR, metrics=METRICS
    )
    before = d.to_dict()["evidence"]["comparisons"][0]["skill"]
    handed_out = d.to_dict()
    handed_out["evidence"]["comparisons"][0]["skill"] = 99
    handed_out["evidence"]["arm"] = "test"
    assert d.to_dict()["evidence"]["comparisons"][0]["skill"] == before
    assert d.to_dict()["evidence"]["arm"] == "val"


# ---------------------------------------------------------------------------
# RESIDUALS — measured, disclosed, and pinned so they fail when they close
# ---------------------------------------------------------------------------
def test_residual_b_an_undeclared_domain_buys_no_domain_check():
    """STATED LIMIT. `domain` defaults to REAL, which claims nothing.

    A caller who declares polarity but leaves the domain alone gets the
    polarity clause and not the impossibility clause, so the negative-MAPE
    drive still reaches PASS under `domain=REAL`.

    This is deliberately NOT the `row_matched=True` defect wearing new clothes,
    and the difference is the direction of the default. `row_matched=True`
    asserted the STRONGEST claim on the caller's behalf; `domain=REAL` asserts
    the WEAKEST one — every real number is admissible — so the failure mode is
    an absent check, not a fabricated pass. There is no safe default here:
    NONNEGATIVE would be wrong for r2, which legitimately goes negative.

    Making the domain mandatory (as polarity is) is a second contract break
    with its own adopter cost, and it is not taken inside M-01. Recorded in
    mlkit docs/ESCALATIONS.md E-M20.
    """
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mape", -0.05, 0.20, 500, arm="val",
                polarity=LOWER_IS_BETTER, **TIED,  # domain left at REAL
            )
        ],
        recorded_bar=BAR, metrics=("mape",),
    )
    assert decision.status is Status.PASS
    assert decision.skill["mape"] == 1.25


def test_residual_c_a_declared_polarity_can_be_declared_wrongly():
    """STATED LIMIT. The contract checks that a direction was declared, and
    cannot check that it is the right one for that metric.

    Closing this needs a name->polarity table, which is the E-038 defect
    (`core.metric_registry`) re-introduced at the point that decides
    promotions. The declaration travels in the evidence instead, so a reader
    auditing the record can see `mae / higher_is_better` and object; nobody
    could audit the assumption it replaced, because it was never written down.
    """
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 100.0, 80.0, 500, arm="val",
                polarity=HIGHER_IS_BETTER, domain=NONNEGATIVE, **TIED,
            )
        ],
        recorded_bar=BAR, metrics=("mae",),
    )
    assert decision.status is Status.PASS
    assert decision.to_dict()["evidence"]["comparisons"][0]["polarity"] == (
        HIGHER_IS_BETTER
    )


def test_residual_d_n_rows_is_still_a_caller_assertion_untied_to_the_digests():
    """STATED LIMIT. M-06 tied the row SETS; it did not tie the row COUNT.

    A digest over two rows alongside `n_rows=500` passes: the digest is opaque
    and carries no count, and `n_rows` feeds only the NO_ROWS lane. Closing it
    means either deriving `n_rows` from the digest input (which the digest does
    not retain) or carrying a signed count beside it, which is a further design
    step with its own adopter cost. Recorded in mlkit docs/ESCALATIONS.md E-M20.
    """
    two = row_set_digest(ROWS[:2])
    decision = challenger_decision(
        [
            Comparison(
                BAR, "mae", 80.0, 100.0, 500, arm="val",
                polarity=LOWER_IS_BETTER, domain=NONNEGATIVE,
                candidate_row_digest=two, reference_row_digest=two,
            )
        ],
        recorded_bar=BAR, metrics=("mae",),
    )
    assert decision.status is Status.PASS
    assert decision.n_rows == 500


# -- E-M35: extracting the canonical key spelling changed no digest ---------


def test_row_set_digest_is_byte_identical_after_the_canonical_key_extraction():
    """The six digests below were measured BEFORE `_row_key_canonical` existed.

    `row_set_digest` is the fleet's join key: every committed artifact that
    names a row set names it with one of these values, so a refactor that
    moved the canonical spelling into its own function has to prove it moved
    nothing else. These are the values printed by the pre-extraction function
    at `1dfacb6`, pasted here and not recomputed.
    """
    from resilient_mlkit.core.served import row_set_digest

    measured_before = {
        "b31ac2e5b858e7c4c988bf10a77f40c3bcb0a19143efdb7889bc66bd07183d64": [
            "a", "b", "c"
        ],
        "ad53e8806d17c82d38902738d1d47d96bddaade27513466322efa0f793149dd0": [1, 2, 3],
        "9eaa6aa6f8e8705c9bba54ba3f8350dd1b1bbd77e8dd7b47f3166075421b4555": [
            {"a": 1, "b": 2}, {"c": 3}
        ],
        "799a92191712ddfb2ba8e2a16041d3d65a589e7fdee413b0ae37a97190a8e15c": [
            [1, 2], [3, 4]
        ],
        "ba2df4903a2c14e86dc3bcca58911b44ac1d2514b7227bf6eb08cfb978f55a1b": ["x"],
    }
    for expected, keys in measured_before.items():
        assert row_set_digest(keys) == expected, keys
    assert row_set_digest([f"r-{i:06d}" for i in range(1000)]) == (
        "585b91e52c29877047721ac0003a50ba87f212e78eac286a1b4bc502ecd1957d"
    )
