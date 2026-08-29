"""Controls for the fleet verdict reader.

Every assertion here comes in a pair: the thing FIRES when it should, and stays
SILENT when it should not. A check with only the first half is consistent with a
check that fires on everything, which measures nothing.

The reader's whole claim is negative -- that it cannot produce a number it did
not read. Most of what follows is therefore an attempt to make it produce one:
a pointer that misses, a label that has drifted from the quantity it names, a
comparison with a missing side, an artifact that is not in git. Each must come
back as NA carrying its reason, never as a default and never as the previous
row's value.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit.core.artifact import Cell, load, resolve_pointer, unresolved
from resilient_mlkit.core.fleet import (
    Absent,
    Adapter,
    Compare,
    Declared,
    Field,
    corroborates,
    counts,
    markdown_table,
    na_summary,
    read_row,
)
from resilient_mlkit.core.repo import Repo

# --------------------------------------------------------------- fixtures


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


ARTIFACT = {
    "model": {"name": "toy ridge"},
    "splits_scored": {
        "test": {
            "reference": {"name": "prior mean", "rmse": 1.5},
            "candidates": [{"name": "toy ridge", "rmse": 1.0, "auc": 0.9}],
        }
    },
    "test_scored": True,
    "nothing": None,
    "not_a_list": 7,
}


@pytest.fixture()
def toy_repo(tmp_path: Path) -> Repo:
    """A git repo with one committed artifact and one uncommitted one."""
    root = tmp_path / "resilient-toy"
    (root / "reports").mkdir(parents=True)
    (root / "reports" / "scores.json").write_text(json.dumps(ARTIFACT))
    (root / "reports" / "ledger.jsonl").write_text(
        '{"split": "test", "n": 1}\n{"split": "test", "n": 2}\n'
    )
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "artifacts")
    # Written after the commit: on disk, absent from git.
    (root / "reports" / "uncommitted.json").write_text(json.dumps({"x": 1}))
    return Repo(name="toy", path=root)


def _adapter(**overrides: object) -> Adapter:
    base: dict[str, object] = {
        "repo": "toy",
        "entry": "",
        "artifacts": {"main": "reports/scores.json"},
        "metric": Declared("rmse"),
        "lower_is_better": True,
        "model_of_record": Field("main:model.name"),
        "candidate": Field("main:splits_scored.test.candidates.0.name"),
        "score": Field("main:splits_scored.test.candidates.0.rmse"),
        "split": Declared("test"),
        "baseline_name": Field("main:splits_scored.test.reference.name"),
        "baseline_score": Field("main:splits_scored.test.reference.rmse"),
        "beats": Compare(),
        "test_arm_spent": Field("main:test_scored", transform="bool"),
    }
    base.update(overrides)
    return Adapter(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------- Cell


def test_a_cell_cannot_be_NA_without_a_reason() -> None:
    """FIRES: an unexplained NA is refused at construction."""
    with pytest.raises(ValueError):
        Cell.missing("   ")


def test_a_cell_with_a_reason_is_accepted() -> None:
    """SILENT: the same constructor with a reason is fine."""
    cell = Cell.missing("the artifact does not carry this")
    assert not cell.present
    assert "does not carry" in cell.render()


# ---------------------------------------------------------------- pointer


def test_pointer_walks_dicts_and_indexes_lists() -> None:
    assert resolve_pointer(ARTIFACT, "splits_scored.test.candidates.0.rmse") == 1.0
    assert resolve_pointer(ARTIFACT, "") is ARTIFACT


@pytest.mark.parametrize(
    "pointer",
    [
        "splits_scored.val.reference.rmse",       # key absent
        "splits_scored.test.candidates.9.rmse",   # index past the end
        "splits_scored.test.candidates.name",     # non-numeric index into a list
        "not_a_list.0",                           # index into a scalar
    ],
)
def test_a_pointer_that_misses_is_unresolved_rather_than_defaulted(pointer: str) -> None:
    """FIRES: every way of missing returns the sentinel, not 0, None or ''."""
    assert unresolved(resolve_pointer(ARTIFACT, pointer))


# ---------------------------------------------------------------- reading


def test_a_declared_row_reads_every_column_off_disk(toy_repo: Repo) -> None:
    """SILENT: the happy path produces values, and they are the file's values."""
    row = read_row(toy_repo, _adapter())
    assert row.score.value == 1.0
    assert row.baseline_score.value == 1.5
    assert row.model_of_record.value == "toy ridge"
    assert row.test_arm_spent.value is True
    assert na_summary([row]) == []
    assert counts([row])["cells_na"] == 0


def test_a_pointer_that_misses_becomes_NA_naming_the_pointer(toy_repo: Repo) -> None:
    """FIRES: and the reason carries the pointer, so it is actionable."""
    row = read_row(toy_repo, _adapter(score=Field("main:splits_scored.test.candidates.0.mae")))
    assert not row.score.present
    assert "candidates.0.mae" in row.score.na_reason
    assert "does not resolve" in row.score.na_reason
    assert row.score.value is None


def test_a_pointer_landing_on_null_is_NA_not_the_value_None(toy_repo: Repo) -> None:
    """FIRES: `null` in an artifact is an absence, not a measurement of nothing."""
    row = read_row(toy_repo, _adapter(score=Field("main:nothing")))
    assert not row.score.present
    assert "null" in row.score.na_reason


def test_a_missing_artifact_is_NA_and_names_where_it_looked(toy_repo: Repo) -> None:
    """FIRES: a declared file that is not there does not silently vanish."""
    row = read_row(toy_repo, _adapter(artifacts={"main": "reports/nope.json"}))
    assert not row.score.present
    assert "artifact not found" in row.score.na_reason
    assert row.main is not None and not row.main.found


def test_an_undeclared_alias_is_NA_rather_than_falling_back_to_main(toy_repo: Repo) -> None:
    """FIRES: a typo'd alias must not silently read the main artifact instead."""
    row = read_row(toy_repo, _adapter(score=Field("ledger:0.n")))
    assert not row.score.present
    assert "undeclared artifact alias" in row.score.na_reason


def test_absent_puts_its_declared_reason_in_the_table(toy_repo: Repo) -> None:
    row = read_row(
        toy_repo,
        _adapter(model_of_record=Absent("this repo has never registered a champion")),
    )
    assert not row.model_of_record.present
    assert "never registered a champion" in row.model_of_record.na_reason
    assert any("never registered" in line for line in na_summary([row]))


def test_absent_refuses_to_be_declared_without_a_reason() -> None:
    with pytest.raises(ValueError):
        Absent("")


def test_len_transform_counts_a_jsonl_ledger(toy_repo: Repo) -> None:
    """SILENT: a ledger's value is its line count, and two lines read as 2."""
    row = read_row(
        toy_repo,
        _adapter(
            artifacts={"main": "reports/scores.json", "ledger": "reports/ledger.jsonl"},
            test_arm_spent=Field("ledger:", transform="len"),
        ),
    )
    assert row.test_arm_spent.value == 2


def test_len_transform_on_something_with_no_length_is_NA(toy_repo: Repo) -> None:
    """FIRES: rather than coercing, or reporting 1."""
    row = read_row(toy_repo, _adapter(test_arm_spent=Field("main:not_a_list", transform="len")))
    assert not row.test_arm_spent.present
    assert "no length" in row.test_arm_spent.na_reason


def test_bool_transform_refuses_a_truthy_non_boolean(toy_repo: Repo) -> None:
    """FIRES: `7` is not `True`, and a test-arm flag must not be inferred from truthiness."""
    row = read_row(toy_repo, _adapter(test_arm_spent=Field("main:not_a_list", transform="bool")))
    assert not row.test_arm_spent.present
    assert "not a boolean" in row.test_arm_spent.na_reason


# ------------------------------------------------------------- comparison


def test_compare_fires_when_the_candidate_loses(toy_repo: Repo) -> None:
    """FIRES: 1.5 does not beat 1.0 when lower is better."""
    row = read_row(
        toy_repo,
        _adapter(
            score=Field("main:splits_scored.test.reference.rmse"),
            baseline_score=Field("main:splits_scored.test.candidates.0.rmse"),
            metric=Declared("rmse", against="baseline"),
        ),
    )
    assert row.beats.value is False
    assert "derived" in row.beats.source


def test_compare_stays_silent_when_the_candidate_wins(toy_repo: Repo) -> None:
    """SILENT: 1.0 beats 1.5 when lower is better."""
    assert read_row(toy_repo, _adapter()).beats.value is True


def test_compare_respects_the_declared_direction(toy_repo: Repo) -> None:
    """The SAME two numbers flip verdict when higher is better. If they did not,
    `lower_is_better` would not be doing anything."""
    lower = read_row(toy_repo, _adapter(lower_is_better=True)).beats.value
    higher = read_row(toy_repo, _adapter(lower_is_better=False)).beats.value
    assert lower is True and higher is False


def test_compare_with_a_missing_side_is_NA_not_a_verdict(toy_repo: Repo) -> None:
    """FIRES: half a comparison is not a comparison."""
    row = read_row(
        toy_repo,
        _adapter(baseline_score=Absent("this repo records no bar for this head")),
    )
    assert not row.beats.present
    assert "no comparison is possible" in row.beats.na_reason


def test_compare_refuses_non_numeric_operands(toy_repo: Repo) -> None:
    row = read_row(toy_repo, _adapter(score=Field("main:model.name")))
    assert not row.beats.present


# ------------------------------------------------- declared-label controls


def test_corroborates_matches_any_segment_not_only_the_leaf() -> None:
    assert corroborates("test", "main:splits_scored.test.candidates.0.rmse")
    assert corroborates("mae", "main:level_head.test_mae_mtpd")
    assert not corroborates("rmse", "main:level_head.test_mae_mtpd")


def test_a_declared_label_the_pointer_echoes_is_admitted(toy_repo: Repo) -> None:
    """SILENT: 'test' is on the score pointer's path, so the label stands."""
    row = read_row(toy_repo, _adapter())
    assert row.split.value == "test"
    assert row.metric.value == "rmse"
    assert "corroborated" in row.split.source


def test_a_declared_label_the_pointer_does_not_echo_is_NA(toy_repo: Repo) -> None:
    """FIRES: the number is still reported, but not under a heading the artifact
    does not support. This is the control that stops a real figure being filed
    under the wrong split."""
    row = read_row(toy_repo, _adapter(split=Declared("val")))
    assert row.score.value == 1.0
    assert not row.split.present
    assert "not echoed" in row.split.na_reason


def test_a_metric_label_that_has_drifted_from_the_quantity_is_NA(toy_repo: Repo) -> None:
    """FIRES: pointing at `auc` while calling it `rmse` reports the number without
    a metric rather than mislabelling it."""
    row = read_row(
        toy_repo,
        _adapter(score=Field("main:splits_scored.test.candidates.0.auc"), metric=Declared("rmse")),
    )
    assert row.score.value == 0.9
    assert not row.metric.present
    assert "drifted apart" in row.metric.na_reason


def test_declared_against_an_absent_pointer_is_NA(toy_repo: Repo) -> None:
    row = read_row(
        toy_repo,
        _adapter(
            score=Absent("nothing scored"),
            split=Declared("test"),
        ),
    )
    assert not row.split.present
    assert "no score pointer" in row.split.na_reason


def test_declared_rejects_an_unknown_anchor() -> None:
    with pytest.raises(ValueError):
        Declared("test", against="holdout")


# ------------------------------------------------------------ git standing


def test_a_committed_artifact_is_recorded_as_committed(toy_repo: Repo) -> None:
    """SILENT: the ordinary case must not be flagged."""
    ref = load(toy_repo, "reports/scores.json")
    assert ref.found and ref.committed_at_head and not ref.dirty and not ref.off_checkout


def test_an_uncommitted_artifact_is_flagged(toy_repo: Repo) -> None:
    """FIRES: a figure read from a file git does not have is not reproducible.

    This is the control for the finding this command was written to make --
    resilient-choco's head sidecar is gitignored and has never been committed.
    """
    ref = load(toy_repo, "reports/uncommitted.json")
    assert ref.found
    assert not ref.committed_at_head
    assert ref.sha256


def test_an_edited_artifact_is_flagged_dirty(toy_repo: Repo) -> None:
    """FIRES: working-tree bytes that differ from the committed blob."""
    path = toy_repo.path / "reports" / "scores.json"
    path.write_text(json.dumps({**ARTIFACT, "test_scored": False}))
    ref = load(toy_repo, "reports/scores.json")
    assert ref.found and ref.committed_at_head and ref.dirty


def test_an_artifact_only_in_a_linked_worktree_is_found_and_flagged(toy_repo: Repo) -> None:
    """FIRES: located, and marked as evidence about that worktree, not this branch.

    resilient-surge keeps its model registry on a branch the root checkout does
    not have. Reporting "absent" would be true of the checkout and misleading
    about the repo; reporting it without the flag would be worse.
    """
    _git(toy_repo.path, "checkout", "-q", "-b", "side")
    (toy_repo.path / "reports" / "side_only.json").write_text(json.dumps({"y": 2}))
    _git(toy_repo.path, "add", "-A")
    _git(toy_repo.path, "commit", "-qm", "side artifact")
    _git(toy_repo.path, "checkout", "-q", "-")
    _git(toy_repo.path, "worktree", "add", "-q", str(toy_repo.path / "wt"), "side")

    ref = load(toy_repo, "reports/side_only.json")
    assert ref.found
    assert ref.off_checkout
    assert ref.branch == "side"

    # Negative control: a file present in BOTH trees is served from the root
    # checkout, not from the worktree, so the flag stays off.
    assert not load(toy_repo, "reports/scores.json").off_checkout


# --------------------------------------------------------------- rendering


def test_the_table_prints_the_reason_for_every_NA(toy_repo: Repo) -> None:
    """An NA cell that renders as a bare dash is the failure this table exists
    to remove: it looks like coverage and carries nothing."""
    row = read_row(toy_repo, _adapter(model_of_record=Absent("no champion registered")))
    table = markdown_table([row])
    assert "no champion" in table
    assert "NA" in table


def test_a_float_is_printed_at_full_precision_not_rounded(toy_repo: Repo) -> None:
    """A table cell that silently rounds is a second transcription error."""
    path = toy_repo.path / "reports" / "scores.json"
    doc = json.loads(path.read_text())
    doc["splits_scored"]["test"]["candidates"][0]["rmse"] = 1.056759999999
    path.write_text(json.dumps(doc))
    assert "1.056759999999" in markdown_table([read_row(toy_repo, _adapter())])


# ------------------------------------------------- the real declarations


def test_every_declared_adapter_is_structurally_valid() -> None:
    """Reads no repo: this is about the declarations themselves.

    An adapter with no `main` artifact, or an `Absent` with no reason, is a
    defect in this package and must not wait for a checkout to surface.
    """
    from resilient_mlkit.core.repo import PORTFOLIO
    from resilient_mlkit.fleet_adapters import ADAPTERS

    assert ADAPTERS, "no adapters declared"
    seen: set[str] = set()
    for adapter in ADAPTERS:
        assert adapter.repo in PORTFOLIO, f"{adapter.repo} is not a portfolio repo"
        assert "main" in adapter.artifacts
        assert adapter.key not in seen, f"duplicate adapter key {adapter.key}"
        seen.add(adapter.key)
        for name in ("model_of_record", "candidate", "score", "split",
                     "baseline_name", "baseline_score", "beats", "test_arm_spent", "metric"):
            spec = getattr(adapter, name)
            assert isinstance(spec, (Field, Absent, Compare, Declared)), (
                f"{adapter.key}.{name} is not a declared spec"
            )
            if isinstance(spec, Field):
                assert spec.pointer, f"{adapter.key}.{name} has an empty pointer"
                assert spec.transform in ("", "len", "float", "bool")


def test_every_portfolio_repo_has_at_least_one_adapter() -> None:
    """A repo with no adapter drops out of the table silently, which is exactly
    the invisible omission the generated table is meant to prevent."""
    from resilient_mlkit.core.repo import PORTFOLIO
    from resilient_mlkit.fleet_adapters import ADAPTERS

    covered = {a.repo for a in ADAPTERS}
    assert covered == set(PORTFOLIO), f"repos with no declared adapter: {set(PORTFOLIO) - covered}"
