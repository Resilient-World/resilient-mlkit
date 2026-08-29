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
import re
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


def _commit(repo: Repo, message: str = "edit") -> None:
    """Land the working tree in git.

    Several controls below rewrite an artifact and re-read it. Since
    ``core.artifact.load`` reads ``HEAD:<relpath>`` rather than the working tree
    (``docs/ESCALATIONS.md`` E-M12), an edit that is not committed is not an
    edit the reader can see -- which is the point of the change and is itself
    asserted, both ways, in ``tests/test_committed_reads.py``.
    """
    _git(repo.path, "add", "-A")
    _git(repo.path, "commit", "-qm", message)


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


# --------------------------------- asserted-verdict corroboration controls
#
# Three of the twelve rows do not DERIVE `beats bar?` -- they point at a boolean
# the repo publishes itself (fray x2, surge). Read alone, that boolean resolves
# whether or not the score does, so a row could render `score: NA` beside
# `beats bar?: yes`, and it could contradict the two figures printed beside it
# without a reader ever seeing the disagreement. An asserted verdict is
# therefore admitted only when this row's own score and baseline reproduce it.
#
# Measured on the real fleet when this was added: all three asserted booleans
# ARE reproduced by the figures, so no verdict in the committed table changed --
# only the `source` string, which now records the corroboration.


def test_an_asserted_verdict_the_figures_reproduce_is_admitted(toy_repo: Repo) -> None:
    """SILENT: the artifact says True, and 1.0 < 1.5 says True too."""
    row = read_row(toy_repo, _adapter(beats=Field("main:test_scored")))
    assert row.beats.value is True
    assert "corroborated by this row's own figures" in row.beats.source


def test_an_asserted_verdict_the_figures_contradict_is_NA(toy_repo: Repo) -> None:
    """FIRES: same asserted True, but read as higher-is-better the two figures
    give False. Printing either alone would hide the disagreement."""
    row = read_row(
        toy_repo, _adapter(beats=Field("main:test_scored"), lower_is_better=False)
    )
    assert not row.beats.present
    assert "CONTRADICTION" in row.beats.na_reason
    assert row.score.value == 1.0  # the figures are still reported


def test_an_asserted_verdict_that_cannot_be_corroborated_is_NA_not_a_pass(
    toy_repo: Repo,
) -> None:
    """FIRES: this is the hole. The asserted boolean resolves fine, but with no
    baseline there is nothing to check it against, so it must not render as a
    pass beside an NA."""
    row = read_row(
        toy_repo,
        _adapter(
            beats=Field("main:test_scored"),
            baseline_score=Absent("this repo records no bar for this head"),
        ),
    )
    assert not row.beats.present
    assert "UNMEASURED here, not a pass" in row.beats.na_reason


def test_corroboration_can_never_turn_an_NA_into_a_pass(toy_repo: Repo) -> None:
    """SILENT: an asserted verdict that is itself NA stays NA, with its own
    reason intact. The corroboration step only ever removes passes."""
    row = read_row(toy_repo, _adapter(beats=Field("main:no_such_field")))
    assert not row.beats.present
    assert "CONTRADICTION" not in row.beats.na_reason


def test_a_derived_verdict_is_untouched_by_the_corroboration_step(
    toy_repo: Repo,
) -> None:
    """SILENT: `Compare()` rows never went through an assertion, so nothing here
    may change them. Without this, the two paths could drift apart."""
    row = read_row(toy_repo, _adapter())
    assert row.beats.value is True
    assert row.beats.source.startswith("derived:")


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


def test_an_uncommitted_artifact_is_refused_not_merely_flagged(toy_repo: Repo) -> None:
    """FIRES: a figure read from a file git does not have is not reproducible.

    This is the control for the finding this command was written to make --
    resilient-choco's head sidecar is gitignored and has never been committed.

    Named "…_is_flagged" until committed reads landed, when flagging turned out
    to be the whole defect: the flag was computed, printed in a provenance
    column, and the number served anyway. The assertions below are the old ones
    plus the refusal, never fewer.
    """
    ref = load(toy_repo, "reports/uncommitted.json")
    assert not ref.committed_at_head
    assert not ref.found, "an artifact on no ref must not present as found"
    assert "not committed at HEAD" in ref.error
    assert "reports/uncommitted.json" in ref.error
    assert ref.document is None, "the document of an uncommitted file was parsed"
    assert not ref.sha256, "hashing it would put an unfetchable sha in the table"


def test_an_edited_artifact_is_flagged_dirty_and_refused(toy_repo: Repo) -> None:
    """FIRES: working-tree bytes that differ from the committed blob."""
    path = toy_repo.path / "reports" / "scores.json"
    path.write_text(json.dumps({**ARTIFACT, "test_scored": False}))
    ref = load(toy_repo, "reports/scores.json")
    assert ref.committed_at_head and ref.dirty
    # …and the two recorded facts now decide, rather than annotate.
    assert not ref.found
    assert "not committed at HEAD" in ref.error
    assert ref.document is None


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
    _commit(toy_repo, "a figure with more digits than a table usually keeps")
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


# ------------------------------------ no figure may be typed into an adapter
#
# The reader exists because a hand-transcribed number has no error detection.
# That guarantee survives only while the DECLARATIONS stay free of figures: one
# `score=Declared("74.16097783177521")` and the table is back to being typed in,
# except now it is typed in somewhere nobody reads and rendered with the
# authority of a machine.
#
# This is live right now. fray's `forecast_available` record is being restated
# this round to the verified weather winner. mlkit must pick that up by reading
# whatever fray commits, and must not carry the figure itself.


def _adapter_source() -> str:
    import resilient_mlkit.fleet_adapters as mod

    return Path(mod.__file__).read_text(encoding="utf-8")


def numeric_literals(source: str) -> list[str]:
    """Every int/float literal in real code in ``source``.

    An `ast` walk, so comments and docstrings are out of scope by construction
    and the prose above may discuss figures freely. Booleans are excluded:
    `lower_is_better=True` is a property of the metric, not a value of it.
    """
    import ast

    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            out.append(f"line {node.lineno}: {node.value!r}")
    return out


def test_no_adapter_declaration_contains_a_numeric_literal() -> None:
    """FIRES on a typed-in figure. This is the guarantee the whole command rests on."""
    found = numeric_literals(_adapter_source())
    assert found == [], (
        "fleet_adapters.py contains numeric literals. Nothing in an adapter is a "
        "measurement -- an adapter is a path, a pointer, a corroborated label or a "
        "written reason. A number here is a hand-transcribed figure wearing the "
        f"generated table's authority: {found}"
    )


def test_positive_control_a_typed_in_figure_is_caught() -> None:
    """FIRES: the exact mistake the note above warns about, in miniature.

    Without this, the test above is equally consistent with a walker that finds
    nothing because it is looking in the wrong place.
    """
    smuggled = (
        'X = Adapter(\n'
        '    repo="fray",\n'
        '    lower_is_better=True,\n'
        '    score=Declared("74.16097783177521"),\n'
        '    baseline_score=74.16097783177521,\n'
        ')\n'
    )
    found = numeric_literals(smuggled)
    assert len(found) == 1, found
    assert "74.16097783177521" in found[0]


def test_negative_control_a_figure_in_prose_is_not_a_declaration() -> None:
    """SILENT: an adapter may explain itself, including about numbers.

    `blackout/vs-persistence` says "the 89,774-row persistence subset" in its
    note, and must keep being able to. Only executable literals count.
    """
    prose_only = (
        '"""fray moved to the winner at TEST MAE 74.16097783177521."""\n'
        'X = Adapter(\n'
        '    # persistence scores only 89,774 of the 101,424 rows\n'
        '    note="like-for-like on the 89,774-row subset",\n'
        '    lower_is_better=False,\n'
        ')\n'
    )
    assert numeric_literals(prose_only) == []


def test_a_declared_label_that_is_a_bare_figure_cannot_be_admitted(
    toy_repo: Repo,
) -> None:
    """The other door into the same room, closed by corroboration.

    `Declared` takes a string, so a figure CAN be typed as one and slip past a
    numeric-literal walk. It still must not reach the table: a label is admitted
    only when the pointer it is declared against echoes it, and no pointer
    echoes a bare number. NA with a reason, never the figure.

    On the shape of the assertion. This test first asserted that the figure
    appears nowhere in the rendered cell, and that FAILED -- the NA reason
    quotes the rejected label back, verbatim and by design. Quoting what was
    refused is the behaviour that makes the refusal checkable, so the test was
    wrong and the code was right. What is asserted instead is the property that
    actually matters: the figure never becomes the cell's VALUE, and the cell
    renders as an NA rather than as a number.
    """
    row = read_row(toy_repo, _adapter(metric=Declared("74.16097783177521")))
    assert not row.metric.present
    assert "not echoed" in row.metric.na_reason
    assert row.metric.value != "74.16097783177521"
    assert row.metric.render().startswith("NA"), (
        "a bare figure declared as a label rendered as though it were a value"
    )


def test_the_reader_follows_the_artifact_when_the_recorded_figure_changes(
    toy_repo: Repo,
) -> None:
    """The fray case, exercised: rewrite the artifact, re-read, get the new number.

    Read twice off the same declaration with the file changed in between. If any
    figure were baked into the adapter or cached across reads, the two scores
    would agree -- and the second would be quietly wrong.

    The edit is COMMITTED between the two reads, and that is now load-bearing
    rather than incidental: the reader follows the artifact's committed state,
    so an uncommitted edit is deliberately invisible to it. The half of that
    claim this test does not make -- that the uncommitted edit changes nothing
    downstream -- is made in ``tests/test_committed_reads.py``.
    """
    adapter = _adapter()
    before = read_row(toy_repo, adapter)

    path = toy_repo.path / "reports" / "scores.json"
    document = json.loads(path.read_text())
    document["splits_scored"]["test"]["candidates"][0]["rmse"] = 74.16097783177521
    path.write_text(json.dumps(document))
    _commit(toy_repo, "the recorded figure changes")

    after = read_row(toy_repo, adapter)
    assert before.score.value != after.score.value, (
        "the score did not move when the artifact did, so it is not being read "
        "from the artifact"
    )
    assert after.score.value == 74.16097783177521
    assert after.score.present


# ---------------------------------- evidence that lives only on a side branch
#
# `portfolio/FLEET_VERDICTS.md` records, per repo, the branch the table was read
# from. Every one of the eight was read off a non-`main` branch, so "branch is
# not main" does not discriminate; what discriminates is whether the artifact
# the adapter names exists on that repo's `main` at all. Measured read-only on
# 2026-08-29 in each repo's own clone -- no checkout, no fetch, nothing written:
#
#   git -C resilient-blackout cat-file -e e021-decision:reports/train/weather_failure_test_read.json   -> present
#   git -C resilient-blackout cat-file -e main:reports/train/weather_failure_test_read.json            -> absent
#   git -C resilient-blackout cat-file -e {e021-decision,main}:reports/train/weather_failure_all_in_scope_gate.json
#                                                                                                     -> present / absent
#   git -C resilient-triage   cat-file -e {e028-decision,main}:models/weekly_mortality/champion.json   -> present / absent
#
# and the same probe against the other six repos' declared artifacts found all
# of them present on their own `main` (arabica, choco, fray, torrent,
# chokepoint, surge). So the branch dependence is blackout's and triage's, and
# it is a fact about the EVIDENCE, not about which branch someone happened to
# have checked out.
#
# surge already carries a note of this shape for the adjacent case -- its
# artifacts were read from a linked worktree rather than from the branch the
# repo root had checked out -- and that note is the pattern copied here. The
# provenance table records all of this; the point of putting it in
# `fleet_adapters.py` is that a reader of the adapter alone must not assume the
# evidence is on `main`.

#: repo -> the branch its declared artifacts are committed on, for the repos
#: whose artifacts are NOT on that repo's `main`. Corroborated below against
#: the branch `portfolio/FLEET_VERDICTS.md` records reading each repo from.
BRANCH_ONLY_EVIDENCE = {
    "blackout": "e021-decision",
    "triage": "e028-decision",
}

FLEET_VERDICTS_MD = Path(__file__).resolve().parent.parent / "portfolio" / "FLEET_VERDICTS.md"

#: A row of the "Repos as they were read" table: `| triage | `e028-decision` | ...`
_READ_AS = re.compile(r"^\|\s*([a-z]+)\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE)


def provenance_branches(markdown: str) -> dict[str, str]:
    """repo -> branch, from the committed provenance table."""
    return dict(_READ_AS.findall(markdown))


def entries_missing_branch_note(adapters, required: dict[str, str]) -> list[str]:
    """Adapter keys that depend on a side branch without saying so.

    The marker is deliberately concrete: the note must name the branch AND the
    word `main`, because "reads from e021-decision" alone still leaves a reader
    to infer what that means for `main`.
    """
    return [
        a.key
        for a in adapters
        if a.repo in required
        and not (required[a.repo] in (a.note or "") and "main" in (a.note or ""))
    ]


def test_every_branch_only_adapter_says_its_evidence_is_not_on_main() -> None:
    """FIRES on `main` at 21f7e6f, where only surge's entry carried such a note."""
    from resilient_mlkit.fleet_adapters import ADAPTERS

    covered = {a.repo for a in ADAPTERS}
    assert set(BRANCH_ONLY_EVIDENCE) <= covered, "declared repos have no adapter"
    missing = entries_missing_branch_note(ADAPTERS, BRANCH_ONLY_EVIDENCE)
    assert missing == [], (
        "these adapters name artifacts that are committed only on a side branch "
        f"of the repo they read, and do not say so: {missing}. "
        "portfolio/FLEET_VERDICTS.md's provenance table records it; a reader of "
        "fleet_adapters.py alone would assume main-committed evidence"
    )


def test_the_declared_branches_match_the_committed_provenance_table() -> None:
    """The note may not name a branch the generated table contradicts."""
    assert FLEET_VERDICTS_MD.is_file(), f"{FLEET_VERDICTS_MD} does not exist"
    recorded = provenance_branches(FLEET_VERDICTS_MD.read_text(encoding="utf-8"))
    assert recorded, "no provenance rows parsed; this control would pass over an absence"
    for repo, branch in BRANCH_ONLY_EVIDENCE.items():
        assert recorded.get(repo) == branch, (
            f"{repo}: the adapter note is written for `{branch}` but the committed "
            f"provenance table read it from {recorded.get(repo)!r}"
        )


# -- controls for the two above --------------------------------------------


def test_positive_control_a_deleted_branch_note_is_caught() -> None:
    """FIRES: the blackout/triage entries exactly as `main` carried them."""
    import dataclasses

    from resilient_mlkit.fleet_adapters import ADAPTERS

    stripped = tuple(
        dataclasses.replace(a, note="") if a.repo in BRANCH_ONLY_EVIDENCE else a
        for a in ADAPTERS
    )
    missing = entries_missing_branch_note(stripped, BRANCH_ONLY_EVIDENCE)
    assert sorted(missing) == sorted(
        a.key for a in ADAPTERS if a.repo in BRANCH_ONLY_EVIDENCE
    )


def test_positive_control_a_note_naming_the_wrong_branch_is_caught() -> None:
    """FIRES: a marker is only a marker while it names the right branch."""
    import dataclasses

    from resilient_mlkit.fleet_adapters import ADAPTERS

    wrong = tuple(
        dataclasses.replace(a, note="committed on some-other-branch, not on main")
        if a.repo == "triage"
        else a
        for a in ADAPTERS
    )
    assert entries_missing_branch_note(wrong, BRANCH_ONLY_EVIDENCE) == ["triage"]


def test_negative_control_a_repo_whose_evidence_is_on_main_needs_no_note() -> None:
    """SILENT: an adapter outside ``BRANCH_ONLY_EVIDENCE`` is never flagged.

    Without this pair the rule above is indistinguishable from "every adapter
    must carry a note", which would make the note meaningless.

    Strengthened during adversarial verification. The earlier shape passed a
    pre-filtered slice (the non-required adapters, notes as committed) and
    asserted the result was empty. That did catch the break its docstring
    names -- dropping ``entries_missing_branch_note``'s ``a.repo in required``
    guard makes it fail -- but its silence and the rule's firing were measured
    on DIFFERENT inputs, so "silent" could still have meant "given nothing to
    object to": blanking the notes of those same adapters does not change its
    result either way.

    This shape fixes that by using one input for both halves. Every note on the
    WHOLE adapter tuple is blanked; the rule must fire (the three
    branch-dependent entries are flagged) and, on that same input, must stay
    silent for every adapter whose evidence is on its own ``main``.
    """
    import dataclasses

    from resilient_mlkit.fleet_adapters import ADAPTERS

    on_main = [a.key for a in ADAPTERS if a.repo not in BRANCH_ONLY_EVIDENCE]
    assert on_main, "no adapters left to control against"

    blanked = tuple(dataclasses.replace(a, note="") for a in ADAPTERS)
    flagged = entries_missing_branch_note(blanked, BRANCH_ONLY_EVIDENCE)

    assert flagged, "same-input positive: a blanked note must fire for the required repos"
    assert not (set(flagged) & set(on_main)), (
        "an adapter whose evidence is on its repo's own main was flagged for "
        f"missing a branch note: {sorted(set(flagged) & set(on_main))}"
    )
