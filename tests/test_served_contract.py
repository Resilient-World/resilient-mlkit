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

import json

import pytest

from resilient_mlkit.core.result import Status
from resilient_mlkit.core.served import (
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
    seal,
    sha256_file,
    skill,
    verify_at_load,
)

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


def comparisons(candidate, reference, **kw):
    return [
        Comparison(
            reference=BAR,
            metric=metric,
            candidate_value=candidate,
            reference_value=reference,
            n_rows=kw.pop("n_rows", 500),
            arm=kw.pop("arm", "val"),
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
    assert skill(0.0, 0.0) is None
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
    decision = challenger_decision(
        comparisons(80.0, 100.0, row_matched=False),
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
            Comparison(BAR, "mae", 80.0, 100.0, 500, arm="val"),
            Comparison(BAR, "rmse", 120.0, 100.0, 500, arm="val"),
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
# M-01 — metric polarity and domain (HOLE 1), DEFECT PINS
#
# These three tests record, executably, the behaviour the contract has TODAY
# at 8517341, before the M-01 fix. No test in this suite recorded it; that is
# the E-M17-residual discipline (pin the silence before repairing it). The fix
# commit REWRITES each of these into the refusal it earns — a pin that
# survives the fix unchanged means the fix did not land.
# ---------------------------------------------------------------------------
def test_m01_defect_pin_a_negative_mape_candidate_promotes():
    """DEFECT (fray E-035 residual 3). mape is nonnegative by definition; a
    candidate of -0.05 is an impossible reading. Today skill() folds it into
    1 - (-0.05/0.20) = 1.25 and the decision PASSES on it."""
    decision = challenger_decision(
        [Comparison(BAR, "mape", -0.05, 0.20, 100, arm="val")],
        recorded_bar=BAR,
        metrics=("mape",),
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    assert decision.skill["mape"] == pytest.approx(1.25)


def test_m01_defect_pin_a_worse_higher_is_better_candidate_promotes():
    """DEFECT. r2 is higher-is-better; a candidate at 0.10 against a champion
    at 0.90 is a much worse model. Today the contract silently assumes every
    metric is lower-is-better, computes 1 - 0.10/0.90 = +0.8889, and PROMOTES
    the worse model."""
    decision = challenger_decision(
        [Comparison(BAR, "r2", 0.10, 0.90, 100, arm="val")],
        recorded_bar=BAR,
        metrics=("r2",),
    )
    assert decision.status is Status.PASS
    assert decision.promotable is True
    assert decision.skill["r2"] == pytest.approx(1.0 - 0.10 / 0.90, rel=1e-12)


def test_m01_defect_pin_polarity_is_nowhere_declarable():
    """DEFECT. Neither Comparison nor challenger_decision accepts a polarity
    or domain declaration, so no caller CAN say which direction is better."""
    fields = {f.name for f in Comparison.__dataclass_fields__.values()}
    assert "polarity" not in fields
    assert "domain" not in fields
