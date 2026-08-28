"""Where each repo keeps the numbers the fleet verdict table quotes.

One declaration per model of record. Nothing here is a measurement: every entry
is a path, a pointer, a label corroborated against a pointer, or a written
reason why a column cannot be filled from this repo's committed artifacts.

HOW TO CHANGE ONE
-----------------
Point it at a different artifact or a different pointer. Do not hard-code a
value, and do not delete a field to make a row look complete -- an ``Absent``
with its reason is the correct output for "this repo has not written that down",
and it is the finding, not a gap in the tool.

Every path below was resolved against the repo checkouts on 2026-08-28; the
adapters carry no figures, so a pointer that later moves reports NA naming the
pointer rather than serving a stale number.
"""

from __future__ import annotations

from .core.fleet import Absent, Adapter, Compare, Declared, Field

#: Every declared adapter, in the portfolio's canonical repo order.
ADAPTERS: tuple[Adapter, ...] = (
    # ------------------------------------------------------------------ choco
    Adapter(
        repo="choco",
        entry="",
        artifacts={
            "main": "models/observed_production_head.meta.json",
            "served": "models/observed_production_persistence.meta.json",
        },
        metric=Declared("rmse"),
        lower_is_better=True,
        model_of_record=Field("served:predictor"),
        candidate=Field("main:model_family"),
        # The paired block is the only same-rows comparison in this repo: the
        # head's own test_log_rmse is scored over 42 rows and persistence over
        # 33, so the two headline figures next to each other would not be a
        # comparison. `model_rmse_same_rows` is the head restricted to the rows
        # persistence can score.
        score=Field("main:training_summary.paired_persistence_test.lags.lag_1.model_rmse_same_rows"),
        split=Field("main:training_summary.test_baselines.split"),
        baseline_name=Field("served:predictor"),
        baseline_score=Field(
            "main:training_summary.paired_persistence_test.lags.lag_1.persistence_rmse"
        ),
        beats=Compare(),
        test_arm_spent=Field("main:training_summary.test_scored", transform="bool"),
        note=(
            "the served predictor of record is the reference itself; the candidate "
            "column is the retired climate head that lost to it"
        ),
    ),
    # ---------------------------------------------------------------- arabica
    Adapter(
        repo="arabica",
        entry="",
        artifacts={"main": "reports/validation/yield_reference_skill.json"},
        metric=Declared("rmse"),
        lower_is_better=True,
        model_of_record=Field("main:model.name"),
        candidate=Field("main:splits_scored.test.candidates.0.name"),
        score=Field("main:splits_scored.test.candidates.0.rmse"),
        split=Declared("test"),
        baseline_name=Field("main:splits_scored.test.reference.name"),
        baseline_score=Field("main:splits_scored.test.reference.rmse"),
        beats=Compare(),
        test_arm_spent=Field("main:test_scored", transform="bool"),
    ),
    # ------------------------------------------------------------------- fray
    # Two tracks, two information sets, two models of record. One row would have
    # to drop one of them, and which one it dropped would be a judgement the
    # table then hid.
    Adapter(
        repo="fray",
        entry="spatial_infill",
        artifacts={"main": "reports/validation/models_of_record.json"},
        metric=Declared("mae"),
        lower_is_better=True,
        model_of_record=Field("main:tracks.spatial_infill.candidate"),
        candidate=Field("main:tracks.spatial_infill.candidate"),
        score=Field("main:tracks.spatial_infill.test.mae_lb_ac"),
        split=Declared("test"),
        baseline_name=Declared("persistence_t_minus_1", against="baseline"),
        baseline_score=Field("main:baselines_on_test.persistence_t_minus_1.mae_lb_ac"),
        beats=Field("main:tracks.spatial_infill.beats_persistence_on_test.mae_lb_ac"),
        test_arm_spent=Absent(
            "models_of_record.json carries no test-read counter or ledger; that TEST "
            "was scored once per track is asserted in `record_rule` prose, which is "
            "not a machine-readable field"
        ),
    ),
    Adapter(
        repo="fray",
        entry="forecast_available",
        artifacts={"main": "reports/validation/models_of_record.json"},
        metric=Declared("mae"),
        lower_is_better=True,
        model_of_record=Field("main:tracks.forecast_available.candidate"),
        candidate=Field("main:tracks.forecast_available.candidate"),
        score=Field("main:tracks.forecast_available.test.mae_lb_ac"),
        split=Declared("test"),
        baseline_name=Declared("persistence_t_minus_1", against="baseline"),
        baseline_score=Field("main:baselines_on_test.persistence_t_minus_1.mae_lb_ac"),
        beats=Field("main:tracks.forecast_available.beats_persistence_on_test.mae_lb_ac"),
        test_arm_spent=Absent(
            "models_of_record.json carries no test-read counter or ledger; that TEST "
            "was scored once per track is asserted in `record_rule` prose, which is "
            "not a machine-readable field"
        ),
    ),
    # ---------------------------------------------------------------- torrent
    Adapter(
        repo="torrent",
        entry="melstm-10ep-n8-val",
        artifacts={
            "main": "reports/train/seed_summary_n8_val.json",
            "ledger": "reports/holdout_reads.jsonl",
        },
        metric=Field("main:metric"),
        lower_is_better=False,
        model_of_record=Absent(
            "no committed JSON artifact in resilient-torrent declares a model of "
            "record. The ridge is named as one in prose only (docs/ESCALATIONS.md, "
            "docs/HYDROLOGY_VAL_RESULTS_AND_TEST_DECISION.md, CHANGELOG.md), and "
            "prose is not a field an adapter can read"
        ),
        candidate=Field("main:config"),
        score=Field("main:mean"),
        split=Field("main:split"),
        baseline_name=Field("main:reference.name"),
        baseline_score=Field("main:reference.median_nse"),
        beats=Compare(),
        test_arm_spent=Field("ledger:", transform="len"),
        note=(
            "score is the mean of 8 per-seed val medians; the artifact's own "
            "interval_note warns that the recorded interval is on the MEAN and is "
            "not a prediction interval for the next seed"
        ),
    ),
    Adapter(
        repo="torrent",
        entry="ridge-vs-melstm-val",
        artifacts={
            "main": "reports/train/row_parity_ridge_vs_melstm_val.json",
            "ledger": "reports/holdout_reads.jsonl",
        },
        metric=Declared("nse"),
        lower_is_better=False,
        model_of_record=Absent(
            "no committed JSON artifact in resilient-torrent declares a model of "
            "record; see the melstm-10ep-n8-val row"
        ),
        candidate=Field("main:right.name"),
        score=Field("main:right.median_nse"),
        split=Absent(
            "row_parity_ridge_vs_melstm_val.json records the compared rows, the "
            "scored basin counts and `same_rows`, but no split field; the split "
            "appears in the FILENAME only, which no adapter should read as data"
        ),
        baseline_name=Field("main:left.name"),
        baseline_score=Field("main:left.median_nse"),
        beats=Compare(),
        test_arm_spent=Field("ledger:", transform="len"),
        note="the ridge is the `left` side here: the network is measured against it",
    ),
    # ------------------------------------------------------------- chokepoint
    Adapter(
        repo="chokepoint",
        entry="level-head",
        artifacts={"main": "models/episode_response/champion.json"},
        metric=Declared("mae"),
        lower_is_better=True,
        model_of_record=Field("main:model_id"),
        candidate=Field("main:heads.level.name"),
        score=Field("main:measurements.level_head_on_the_episode_holdouts.test_mae_mtpd"),
        split=Declared("test"),
        baseline_name=Field("main:recorded_bars.level.name"),
        baseline_score=Absent(
            "the level head IS the recorded bar — `recorded_bars.level."
            "is_the_champion_head_itself` is true — so there is no separate bar "
            "figure to read. The challenger that failed against it is recorded "
            "under `challengers_that_failed`, not as a bar"
        ),
        beats=Compare(),
        test_arm_spent=Field("main:measurements.level_head_on_the_episode_holdouts.test_read"),
    ),
    Adapter(
        repo="chokepoint",
        entry="direction-head",
        artifacts={"main": "models/episode_response/champion.json"},
        metric=Declared("auc"),
        lower_is_better=False,
        model_of_record=Field("main:model_id"),
        candidate=Field("main:heads.direction.name"),
        score=Field("main:measurements.direction_head_pooled_loco_auc.auc"),
        split=Field("main:measurements.direction_head_pooled_loco_auc.frame"),
        baseline_name=Field("main:measurements.the_do_nothing_floor_the_direction_head_beats.reference"),
        baseline_score=Field("main:measurements.the_do_nothing_floor_the_direction_head_beats.auc"),
        beats=Compare(),
        test_arm_spent=Field("main:measurements.direction_head_pooled_loco_auc.holdout_read"),
        note=(
            "scored leave-one-corridor-out on the TRAIN frame, not on a holdout; the "
            "artifact says so in `frame` and the split column carries it verbatim"
        ),
    ),
    # ------------------------------------------------------------------ surge
    Adapter(
        repo="surge",
        entry="",
        artifacts={
            "main": "data/model_registry/per_lead_anchor_ols/model.json",
            "index": "data/model_registry/index.json",
            "ledger": "reports/holdout_reads.jsonl",
        },
        metric=Declared("rmse"),
        lower_is_better=True,
        model_of_record=Field("index:surge-residual-forecaster.0.model_path"),
        candidate=Declared("neural_model"),
        # `strongest_baseline_on_test.model_rmse` carries the same figure but
        # names it only by position; this key names the quantity, so the
        # candidate label can be corroborated against it.
        score=Field("main:test_evidence.neural_model_rmse_on_same_slices"),
        split=Declared("test"),
        baseline_name=Field("main:test_evidence.strongest_baseline_on_test.name"),
        baseline_score=Field("main:test_evidence.strongest_baseline_on_test.rmse"),
        beats=Field("main:test_evidence.strongest_baseline_on_test.model_beats_it"),
        test_arm_spent=Field("main:test_evidence.holdout_reads_so_far"),
        note=(
            "these artifacts are NOT on the branch resilient-surge has checked out; "
            "they live on feat/surgeistm-lora-finetune in a linked worktree, which "
            "the artifact block records"
        ),
    ),
    # ----------------------------------------------------------------- triage
    Adapter(
        repo="triage",
        entry="",
        artifacts={"main": "models/weekly_mortality/champion.json"},
        metric=Declared("rmse"),
        lower_is_better=True,
        model_of_record=Field("main:model_id"),
        candidate=Field("main:model_id"),
        score=Field("main:measurements.test.rmse_model"),
        split=Declared("test"),
        baseline_name=Field("main:measurements.test.best_reference"),
        baseline_score=Field("main:measurements.test.rmse_persistence"),
        beats=Compare(),
        test_arm_spent=Field("main:measurements.test.reads_of_this_arm"),
    ),
    # --------------------------------------------------------------- blackout
    Adapter(
        repo="blackout",
        entry="vs-planning-anchor",
        artifacts={
            "main": "reports/train/weather_failure_test_read.json",
            "gate": "reports/train/weather_failure_all_in_scope_gate.json",
        },
        metric=Declared("roc_auc"),
        lower_is_better=False,
        model_of_record=Absent(
            "no committed artifact in resilient-blackout declares a served model of "
            "record. models/weather_failure_v1.joblib.provenance.json records that "
            "checkpoint's family and sha256 but not its serving status, and the gate "
            "artifact records `registry_state.n_versions: 0` — nothing has ever been "
            "registered for this model"
        ),
        candidate=Field("main:preregistration.selected_rung"),
        score=Field("main:test.selected_all_in_scope.roc_auc"),
        split=Declared("test"),
        baseline_name=Field("main:preregistration.anchor_rung"),
        baseline_score=Field("main:test.anchor_planning_base.roc_auc"),
        beats=Compare(),
        test_arm_spent=Field("main:read_at"),
        note="the pre-registered anchor comparison, on all 101,424 test rows",
    ),
    Adapter(
        repo="blackout",
        entry="vs-persistence",
        artifacts={"main": "reports/train/weather_failure_test_read.json"},
        metric=Declared("roc_auc"),
        lower_is_better=False,
        model_of_record=Absent(
            "no committed artifact in resilient-blackout declares a served model of "
            "record; see the vs-planning-anchor row"
        ),
        candidate=Field("main:preregistration.selected_rung"),
        # Persistence can only score the 89,774 rows with a contiguous previous
        # county-day. The model's figure on all 101,424 rows and persistence's on
        # 89,774 are not a comparison; `roc_auc_on_persistence_subset` is.
        score=Field("main:test.selected_all_in_scope.roc_auc_on_persistence_subset"),
        split=Declared("test"),
        baseline_name=Field("main:test.persistence_reference.reference"),
        baseline_score=Field("main:test.persistence_reference.roc_auc"),
        beats=Compare(),
        test_arm_spent=Field("main:read_at"),
        note=(
            "like-for-like: both sides on the 89,774-row persistence subset, which "
            "is the only frame in which the two are comparable"
        ),
    ),
)


def for_repo(name: str) -> tuple[Adapter, ...]:
    return tuple(a for a in ADAPTERS if a.repo == name)
