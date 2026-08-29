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

Every path below was resolved against the repo checkouts on 2026-08-28, and
torrent's ``record`` artifact on 2026-08-29 when it was added; the adapters
carry no figures, so a pointer that later moves reports NA naming the pointer
rather than serving a stale number.

An ``Absent`` reason expires the same way a pointer does, and nothing in the
tool notices. Torrent's ``model_of_record`` was ``Absent`` with the reason
"no committed JSON artifact in resilient-torrent declares a model of record";
that was true when it was written and stopped being true when
``models/hydrology_ridge/model.json`` landed on torrent's ``main``
(``promoted_at`` 2026-08-29, re-emitted under ``TORRENT-L4-PATHS``). A false
``Absent`` is worse than an empty column: it is a written claim about another
repo that a reader has no reason to re-check. The repair is TORRENT-RECORD,
pre-registered in ``reports/MEASUREMENT_EXPORT_PREREGISTRATION.md``.

WHERE THE EVIDENCE LIVES
------------------------
An adapter names a path, not a branch, and a reader of this file alone would
assume the path is on the repo's ``main``. For three entries it is not, and each
says so in its note: surge's artifacts sit in a linked worktree rather than on
the branch that repo has checked out, and blackout's two entries and triage's
read artifacts committed only on ``e021-decision`` and ``e028-decision``.
Measured read-only on 2026-08-29 with ``git cat-file -e <ref>:<path>`` in each
repo's own clone -- no checkout, no fetch, nothing written: present on those
branches, absent on each repo's ``main``. ``portfolio/FLEET_VERDICTS.md``
records the same fact in its provenance table;
``tests/test_fleet.py::test_every_branch_only_adapter_says_its_evidence_is_not_on_main``
holds the two in agreement.

One correction to an earlier reading of that probe, which claimed the other six
repos' artifacts were "all present on their own ``main``". Re-measured the same
way on 2026-08-29 over the distinct ``(repo, path)`` pairs these adapters
declare, and re-run again the same day once torrent's ``record`` artifact took
the count from 17 pairs to 18: 17 of the 18 resolve on the ref their note
implies -- but the one that does not, ``choco``'s ``main`` artifact
``models/observed_production_head.meta.json`` is committed on NO ref in that
clone -- ``git -C resilient-choco log --all -- <path>`` is empty and
``git check-ignore -v`` reports ``.gitignore:82:/models/*``. It exists only in
choco's working tree, so the choco row of the fleet table was read from an
untracked file. That is a different defect from branch dependence (there is no
branch to name), it is not what ``BRANCH_ONLY_EVIDENCE`` encodes, and choco has
an open colleague PR, so it is recorded here and escalated rather than
"fixed" by inventing a note for it.

COMMITTED READS
---------------
Every path below is resolved against a repo's COMMITTED state --
``core.artifact.load`` reads ``HEAD:<relpath>`` rather than the working tree,
and refuses rather than serving a figure git does not have. Two consequences
for a reader of this file:

* A declared path that is on disk and on no ref no longer yields a number. It
  yields ``NA (not committed at HEAD: <relpath> …)``, in every column that
  resolves through it. That is what the choco ``main:`` artifact does now, and
  the row reading NA is the finding rather than a gap in the tool -- nothing was
  invented and nothing was deleted to produce it.
* Pointing an adapter at an uncommitted output is therefore not a way to get a
  row filled in early. If a figure matters enough to appear in the fleet table,
  it has to be committed in the repo that measured it.

The escape hatch, ``mlkit portfolio --allow-dirty``, exists for looking at an
artifact you have not committed yet. It writes no file, emits no table, and
exits non-zero; nothing read through it can land in a row.
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
            "column is the retired climate head that lost to it. "
            "NOT COMMITTED: the `main:` artifact of this adapter is committed on no "
            "ref in resilient-choco -- `git log --all` over it is empty and "
            "`.gitignore` excludes the models tree (docs/ESCALATIONS.md E-M12). "
            "Since committed reads landed, every column resolving through it "
            "reports NA rather than a working-tree figure. This note states what "
            "the reader does, not where the evidence lives; it lives nowhere "
            "resolvable, and asserting otherwise is the fabrication E-M12 declined "
            "to commit. Whether the file is committed, DVC-tracked or the row "
            "withdrawn is resilient-choco's decision"
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
            "no test-read counter exists for THIS track. The sibling "
            "`forecast_available` track's test artifact carries `test_reads_spent`, "
            "keyed by track name, and this row now reads it; spatial_infill's "
            "`source.kind` is `base-menu` and the measurement it names, "
            "reports/validation/observed_panel_model.json, has no equivalent field. "
            "That TEST was scored once per track is asserted in `record_rule` prose, "
            "which is not machine-readable. The gap is the counter, not the "
            "provenance"
        ),
    ),
    Adapter(
        repo="fray",
        entry="forecast_available",
        artifacts={
            "main": "reports/validation/models_of_record.json",
            # models_of_record.json names this file itself, at
            # tracks.forecast_available.source.test_artifact.path, as the
            # artifact its TEST figures came from -- and that file carries the
            # test-read counter this row used to report Absent. Following the
            # chain the record itself declares is not guessing at a schema.
            "test_artifact": "reports/validation/weather_covariate_extension.json",
        },
        metric=Declared("mae"),
        lower_is_better=True,
        model_of_record=Field("main:tracks.forecast_available.candidate"),
        candidate=Field("main:tracks.forecast_available.candidate"),
        score=Field("main:tracks.forecast_available.test.mae_lb_ac"),
        split=Declared("test"),
        baseline_name=Declared("persistence_t_minus_1", against="baseline"),
        baseline_score=Field("main:baselines_on_test.persistence_t_minus_1.mae_lb_ac"),
        beats=Field("main:tracks.forecast_available.beats_persistence_on_test.mae_lb_ac"),
        # Keyed by track name, so this is this row's count and not the repo's.
        test_arm_spent=Field("test_artifact:test_reads_spent.forecast_available"),
    ),
    # ---------------------------------------------------------------- torrent
    Adapter(
        repo="torrent",
        entry="melstm-10ep-n8-val",
        artifacts={
            "main": "reports/train/seed_summary_n8_val.json",
            "ledger": "reports/holdout_reads.jsonl",
            # The model of record, which this column reported Absent until
            # 2026-08-29 on the ground that torrent had committed no such
            # artifact. It has: this file is on torrent's `main`, carries
            # `promoted_at`, and pins the served coefficients by sha256.
            # mlkit already reads it elsewhere --
            # scripts/verify_served_hash_parity.py names it as one of the three
            # sidecar-pinned champions in the fleet.
            "record": "models/hydrology_ridge/model.json",
        },
        metric=Field("main:metric"),
        lower_is_better=False,
        # `served_model` and not `name`: `name` is the registry's label for the
        # service ("hydrology-riverine-forecaster"), while `served_model` is the
        # identifier the repo's other artifacts use for the same object -- it is
        # verbatim the `left.name` of row_parity_ridge_vs_melstm_val.json, the
        # bar the sibling row's network is measured against. Reading the label
        # would put a service identity where a champion belongs, which is the
        # mistake the superseded Absent reason was written to avoid.
        model_of_record=Field("record:served_model"),
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
            # The two artifacts row_parity names as `left.artifact` and
            # `right.artifact`. Both are declared so the provenance block
            # carries both sha256s: the split below is read from `right`, the
            # side whose figure this row reports, and a reader can check the
            # other side against the same table rather than taking the
            # artifact's own `same_rows: true` on trust.
            "left": "reports/train/linear_reference_val_recheck.json",
            "right": "reports/train/melstm_f_s1234_val.json",
            "record": "models/hydrology_ridge/model.json",
        },
        metric=Declared("nse"),
        lower_is_better=False,
        # Same pointer as the melstm-10ep-n8-val row, and the value it reads is
        # the same string as this row's `baseline_name` (`main:left.name`).
        # That is the fact, not a duplication: the ridge IS the model of record
        # and it IS the bar the network was measured against.
        model_of_record=Field("record:served_model"),
        candidate=Field("main:right.name"),
        score=Field("main:right.median_nse"),
        # row_parity itself carries no split field, and the split appears in its
        # FILENAME, which no adapter should read as data. It does not have to:
        # the artifact names `right.artifact`, and that artifact records the
        # split as a field.
        split=Field("right:provenance.scored_split"),
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
        note=(
            "BRANCH-DEPENDENT: this artifact is committed on `e028-decision`, the "
            "branch resilient-triage had checked out when the fleet table was "
            "generated, and it is NOT on that repo's `main` -- do not read this "
            "row as main-committed evidence. The provenance table in "
            "portfolio/FLEET_VERDICTS.md records the branch and the sha256"
        ),
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
        # The gate artifact's `shipped_baseline` block carries `label: "baseline:
        # the artifact currently served"` and names the model. That is a
        # committed artifact declaring what is served, which is what this column
        # asks for -- the same reading as choco's, where the model of record is
        # the served predictor and the candidate is the challenger measured
        # against it. The registry tension is real and is recorded in the note
        # rather than resolved here.
        model_of_record=Field("gate:shipped_baseline.model"),
        candidate=Field("main:preregistration.selected_rung"),
        score=Field("main:test.selected_all_in_scope.roc_auc"),
        split=Declared("test"),
        baseline_name=Field("main:preregistration.anchor_rung"),
        baseline_score=Field("main:test.anchor_planning_base.roc_auc"),
        beats=Compare(),
        test_arm_spent=Field("main:read_at"),
        note=(
            "the pre-registered anchor comparison, on all 101,424 test rows. The "
            "model of record is SERVED but not REGISTERED: the same gate artifact "
            "records `registry_state.n_versions: 0` with the note that nothing has "
            "ever been registered for this model, so a promotion would have nothing "
            "to move. BRANCH-DEPENDENT: both artifacts are committed on "
            "`e021-decision`, the branch resilient-blackout had checked out when "
            "the fleet table was generated, and neither is on that repo's `main` -- "
            "do not read this row as main-committed evidence"
        ),
    ),
    Adapter(
        repo="blackout",
        entry="vs-persistence",
        artifacts={
            "main": "reports/train/weather_failure_test_read.json",
            # Declared here too. It was on the sibling row only, which is why
            # this row reported the served model Absent while the artifact
            # naming it sat one row above.
            "gate": "reports/train/weather_failure_all_in_scope_gate.json",
        },
        metric=Declared("roc_auc"),
        lower_is_better=False,
        # The gate artifact's `shipped_baseline` block carries `label: "baseline:
        # the artifact currently served"` and names the model. That is a
        # committed artifact declaring what is served, which is what this column
        # asks for -- the same reading as choco's, where the model of record is
        # the served predictor and the candidate is the challenger measured
        # against it. The registry tension is real and is recorded in the note
        # rather than resolved here.
        model_of_record=Field("gate:shipped_baseline.model"),
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
            "is the only frame in which the two are comparable. BRANCH-DEPENDENT: "
            "both artifacts are committed on `e021-decision`, the branch "
            "resilient-blackout had checked out when the fleet table was generated, "
            "and neither is on that repo's `main` -- do not read this row as "
            "main-committed evidence"
        ),
    ),
)


def for_repo(name: str) -> tuple[Adapter, ...]:
    return tuple(a for a in ADAPTERS if a.repo == name)
