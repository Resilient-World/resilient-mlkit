"""COMMITTED-READS: the instrument must be unable to quote a number not in git.

Pre-registered in ``reports/COMMITTED_READS_PREREGISTRATION.md``, which landed
in its own commit before any line of ``src/`` moved.

``docs/ESCALATIONS.md`` E-M12 is the case. The ``choco`` row of
``portfolio/FLEET_VERDICTS.md`` -- candidate, score, split, baseline score,
test-arm-spent -- resolved through
``models/observed_production_head.meta.json``, a file committed on no ref at all
in that clone and present only in its working tree. The instrument DETECTED
this: ``ArtifactRef.committed_at_head`` was computed, was ``False``, and was
printed in its own provenance column beside the number. Detection did not stop
the number, because a reader reads the score column first and the qualification
second.

So every control here is an attempt to make the reader produce a working-tree
figure, and every one comes in a pair. The FIRES half alone would be consistent
with a reader that refuses everything, which would be useless in a different
direction; the SILENT half alone would be consistent with the code as it was
before this file existed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit import portfolio
from resilient_mlkit.core.artifact import (
    ALLOW_DIRTY_KEY,
    NOT_COMMITTED,
    Cell,
    UncommittedRead,
    load,
)
from resilient_mlkit.core.fleet import (
    Absent,
    Adapter,
    Compare,
    Declared,
    Field,
    markdown_table,
    read_row,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult, FabricationError, Status

# --------------------------------------------------------------- fixtures

#: The committed figure. Distinctive enough that finding it in a table is
#: unambiguous, and nowhere near the working-tree one below.
COMMITTED_RMSE = 1.0
#: The figure written to the working tree and never committed. If this string
#: appears anywhere a verdict is emitted, the change under test has failed.
WORKING_TREE_RMSE = 74.16097783177521

ARTIFACT = {
    "model": {"name": "toy ridge"},
    "splits_scored": {
        "test": {
            "reference": {"name": "prior mean", "rmse": 1.5},
            "candidates": [{"name": "toy ridge", "rmse": COMMITTED_RMSE}],
        }
    },
    "test_scored": True,
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture()
def toy_repo(tmp_path: Path) -> Repo:
    """A git repo with one committed artifact and one that is on no ref."""
    root = tmp_path / "resilient-toy"
    (root / "reports").mkdir(parents=True)
    (root / "reports" / "scores.json").write_text(json.dumps(ARTIFACT))
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "artifacts")
    # The E-M12 shape: written after the commit, on disk, on no ref.
    (root / "reports" / "never_committed.json").write_text(
        json.dumps({"splits_scored": {"test": {"candidates": [{"rmse": WORKING_TREE_RMSE}]}}})
    )
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


def _dirty(repo: Repo, value: float = WORKING_TREE_RMSE) -> None:
    """Rewrite the committed artifact's score in the working tree only."""
    path = repo.path / "reports" / "scores.json"
    document = json.loads(path.read_text())
    document["splits_scored"]["test"]["candidates"][0]["rmse"] = value
    path.write_text(json.dumps(document))


# ------------------------------------------------------- CR-1: dirty file


def test_CR1_fires_a_dirty_artifact_does_not_yield_the_working_tree_number(
    toy_repo: Repo,
) -> None:
    """FIRES: edit the working-tree copy of a committed artifact and re-read it.

    The assertion that matters is the negative one. Whether the policy serves
    the HEAD bytes or refuses outright, what must never come back is the number
    sitting in the working tree.
    """
    _dirty(toy_repo)
    ref = load(toy_repo, "reports/scores.json")

    assert ref.dirty, "the divergence was not even detected"
    assert ref.committed_at_head
    assert NOT_COMMITTED in ref.error
    assert ref.document is None

    row = read_row(toy_repo, _adapter())
    assert not row.score.present
    assert row.score.value != WORKING_TREE_RMSE
    assert str(WORKING_TREE_RMSE) not in json.dumps(row.to_dict()), (
        "the working-tree figure reached the serialised row"
    )
    assert str(WORKING_TREE_RMSE) not in markdown_table([row]), (
        "the working-tree figure reached the table"
    )


def test_CR1_stays_silent_the_same_artifact_clean_reads_the_committed_number(
    toy_repo: Repo,
) -> None:
    """SILENT: untouched, the identical repo yields the committed figure."""
    ref = load(toy_repo, "reports/scores.json")
    assert ref.found and ref.committed_at_head and not ref.dirty
    assert ref.error == ""
    assert ref.read_from == "HEAD"

    row = read_row(toy_repo, _adapter())
    assert row.score.present and row.score.value == COMMITTED_RMSE
    assert str(COMMITTED_RMSE) in markdown_table([row])


def test_CR1_an_uncommitted_edit_is_invisible_to_the_reader(toy_repo: Repo) -> None:
    """FIRES on the mutation, SILENT on the read: the leakage-by-mutation shape.

    Corrupt the input after the cutoff -- here the cutoff is the commit -- and
    show that nothing downstream moves. The negative control is the line that
    proves the corruption landed at all: without it this test would also pass
    against a reader that had simply stopped reading the file.
    """
    before = load(toy_repo, "reports/scores.json").sha256
    _dirty(toy_repo, value=2.5)

    # Negative control: the corruption really is on disk.
    on_disk = json.loads((toy_repo.path / "reports" / "scores.json").read_text())
    assert on_disk["splits_scored"]["test"]["candidates"][0]["rmse"] == 2.5

    # …and the committed read is unmoved by it.
    diagnostic = load(toy_repo, "reports/scores.json", allow_dirty=True)
    assert diagnostic.document["splits_scored"]["test"]["candidates"][0]["rmse"] == 2.5

    _git(toy_repo.path, "checkout", "--", "reports/scores.json")
    after = load(toy_repo, "reports/scores.json")
    assert after.sha256 == before, "the committed bytes moved when only the disk did"
    assert after.document["splits_scored"]["test"]["candidates"][0]["rmse"] == COMMITTED_RMSE


# ------------------------------------------- CR-2: present on no ref at all


def test_CR2_fires_an_artifact_on_no_ref_is_NA_naming_the_file(toy_repo: Repo) -> None:
    """FIRES: the exact E-M12 choco shape -- on disk, in no commit."""
    ref = load(toy_repo, "reports/never_committed.json")

    assert not ref.found
    assert not ref.committed_at_head
    assert "not committed" in ref.error
    assert "reports/never_committed.json" in ref.error, (
        "the refusal must name the file, or nobody can act on it"
    )
    assert ref.document is None

    row = read_row(toy_repo, _adapter(artifacts={"main": "reports/never_committed.json"}))
    assert not row.score.present
    assert "not committed" in row.score.na_reason
    assert row.score.render().startswith("NA"), (
        "an unbacked figure rendered as though it were a value"
    )
    assert str(WORKING_TREE_RMSE) not in markdown_table([row])


def test_CR2_stays_silent_a_committed_artifact_carries_no_such_reason(
    toy_repo: Repo,
) -> None:
    """SILENT: the ordinary case is not refused, and says nothing about commits."""
    ref = load(toy_repo, "reports/scores.json")
    assert ref.found and ref.error == ""
    assert NOT_COMMITTED not in (ref.error or "")

    row = read_row(toy_repo, _adapter())
    for cell in row.cells:
        assert "not committed" not in (cell.na_reason or "")


def test_CR2_an_artifact_in_no_tree_at_all_still_says_where_it_looked(
    toy_repo: Repo,
) -> None:
    """SILENT on the new refusal, FIRES on the old one: the two stay distinct.

    "Absent everywhere" and "here but not in git" are different findings with
    different remedies -- write it, versus commit it -- and collapsing them into
    one message would cost the reader the remedy.
    """
    ref = load(toy_repo, "reports/no_such_file.json")
    assert not ref.found
    assert "artifact not found" in ref.error
    assert NOT_COMMITTED not in ref.error


# -------------------------------------- CR-3: no regression on the clean case


def test_CR3_a_committed_clean_artifact_loads_byte_identically(toy_repo: Repo) -> None:
    """SILENT: the committed read reproduces the bytes and the sha of the file.

    This is the whole no-regression claim for the ordinary case, made against
    the file rather than against a recorded constant: the blob mlkit now hashes
    must be the same bytes ``path.read_bytes()`` used to hash.
    """
    import hashlib

    disk = (toy_repo.path / "reports" / "scores.json").read_bytes()
    ref = load(toy_repo, "reports/scores.json")

    assert ref.sha256 == hashlib.sha256(disk).hexdigest()
    assert ref.bytes_ == len(disk)
    assert ref.document == json.loads(disk)
    assert ref.branch and ref.git_sha
    assert not ref.allow_dirty_read


def test_CR3_a_jsonl_ledger_is_still_parsed_line_by_line(toy_repo: Repo) -> None:
    """SILENT: JSONL kept its meaning when parsing moved from path to bytes.

    ``_parse`` used to switch on ``path.suffix``; committed reads gave it bytes
    and no path, so the switch moved to the relpath. A ledger silently parsed as
    one JSON document would raise, but a ledger parsed as a single record would
    report a length of nothing -- and a test-arm count is exactly a line count.
    """
    (toy_repo.path / "reports" / "ledger.jsonl").write_text(
        '{"split": "test", "n": 1}\n{"split": "test", "n": 2}\n'
    )
    _git(toy_repo.path, "add", "-A")
    _git(toy_repo.path, "commit", "-qm", "ledger")

    ref = load(toy_repo, "reports/ledger.jsonl")
    assert ref.found
    assert isinstance(ref.document, list) and len(ref.document) == 2


# ------------------------- CR-4: an allow-dirty number cannot become a verdict


def _repo_state_results(**evidence: object) -> dict[str, CheckResult]:
    return {
        "S1": CheckResult(
            "S1", "selection", Status.NA, "reason", dict(evidence), repo="toy"
        )
    }


def test_CR4_fires_resolve_refuses_a_result_carrying_the_allow_dirty_marker(
    tmp_path: Path,
) -> None:
    """FIRES: a terminal state may not be computed from working-tree bytes."""
    repo = Repo(name="toy", path=tmp_path)
    with pytest.raises(UncommittedRead) as caught:
        portfolio.resolve(repo, _repo_state_results(**{ALLOW_DIRTY_KEY: True}))
    assert "allow-dirty" in str(caught.value)
    assert "S1" in str(caught.value)


def test_CR4_stays_silent_resolve_accepts_the_identical_result_unmarked(
    tmp_path: Path,
) -> None:
    """SILENT: same result, same status, no marker -- resolves as it always did."""
    repo = Repo(name="toy", path=tmp_path)
    state = portfolio.resolve(repo, _repo_state_results(measured=1))
    assert state.state == portfolio.IN_PROGRESS
    assert "unmeasured" in state.reason


def test_CR4_fires_a_PASS_carrying_the_marker_cannot_be_constructed() -> None:
    """FIRES: at the dataclass boundary, in ``core/result.py``'s own style.

    The strongest place to put this is the constructor, because a PASS that
    cannot exist cannot be counted, rendered, serialised or forwarded by code
    nobody has written yet.
    """
    with pytest.raises(FabricationError):
        CheckResult.passed("S1", "selection", {ALLOW_DIRTY_KEY: True, "n": 3})


def test_CR4_stays_silent_the_same_PASS_without_the_marker_is_accepted() -> None:
    """SILENT: the invariant is about the marker, not about evidence in general."""
    result = CheckResult.passed("S1", "selection", {"n": 3})
    assert result.status is Status.PASS


def test_CR4_fires_a_marked_row_can_be_neither_printed_nor_serialised(
    toy_repo: Repo,
) -> None:
    """FIRES: the verdict-emission path, for the fleet table rather than a check.

    Both exits are held, because a consumer that cannot print a row will happily
    read the same number out of the JSON twin.
    """
    _dirty(toy_repo)
    row = read_row(toy_repo, _adapter(), allow_dirty=True)
    assert row.allow_dirty
    assert row.score.value == WORKING_TREE_RMSE, "the diagnosis read nothing"

    with pytest.raises(UncommittedRead):
        markdown_table([row])
    with pytest.raises(UncommittedRead):
        row.to_dict()


def test_CR4_the_marker_survives_derivation(toy_repo: Repo) -> None:
    """FIRES: `beats` is computed, not read, and must not launder the marker.

    A comparison of two working-tree numbers is a working-tree verdict. If the
    marker were dropped in ``_compare`` the one column that is arithmetic would
    become the way out of the refusal.
    """
    _dirty(toy_repo, value=0.1)
    row = read_row(toy_repo, _adapter(), allow_dirty=True)
    assert row.beats.present and row.beats.value is True
    assert row.beats.allow_dirty, "a derived cell laundered the allow-dirty marker"


def test_CR4_stays_silent_an_unmarked_row_prints_and_serialises(toy_repo: Repo) -> None:
    """SILENT: allow_dirty=True over a CLEAN repo marks nothing and refuses nothing.

    The flag is not the marker. What marks a row is a read that actually came
    off the working tree; asking for permission that was not needed must leave
    the row exactly as it was.
    """
    row = read_row(toy_repo, _adapter(), allow_dirty=True)
    assert not row.allow_dirty
    assert str(COMMITTED_RMSE) in markdown_table([row])
    assert row.to_dict()["score"]["value"] == COMMITTED_RMSE


def test_CR4_a_marked_cell_is_refused_even_where_a_column_is_declared_absent(
    toy_repo: Repo,
) -> None:
    """FIRES: an Absent column does not dilute the row's refusal.

    A row can be part NA and part measured. The refusal is a property of any
    marked figure on it, not of the row being complete.
    """
    _dirty(toy_repo)
    row = read_row(
        toy_repo,
        _adapter(model_of_record=Absent("no champion registered")),
        allow_dirty=True,
    )
    assert not row.model_of_record.present
    assert row.allow_dirty
    with pytest.raises(UncommittedRead):
        markdown_table([row])


# ------------------------ CR-5: the escape hatch works, outside the verdict path


def test_CR5_stays_silent_allow_dirty_returns_the_working_tree_bytes(
    toy_repo: Repo,
) -> None:
    """SILENT: diagnosis of an artifact that is on no ref is exactly what it is for.

    Refusing this outright would push people back to ``cat`` and a hand-typed
    number, which is the failure one layer down.
    """
    ref = load(toy_repo, "reports/never_committed.json", allow_dirty=True)

    assert ref.found, "the escape hatch did not open"
    assert ref.error == ""
    assert ref.allow_dirty_read
    assert ref.read_from == "working tree"
    assert ref.document["splits_scored"]["test"]["candidates"][0]["rmse"] == WORKING_TREE_RMSE
    assert ref.sha256 and ref.bytes_


def test_CR5_a_cell_from_a_diagnosis_read_still_renders_for_a_human(
    toy_repo: Repo,
) -> None:
    """SILENT: the marker refuses verdicts, not eyes.

    ``Cell.render`` is what a terminal prints. If the marker blocked rendering
    too, ``--allow-dirty`` would print nothing and the hatch would be closed in
    fact while open in the help text.
    """
    row = read_row(
        toy_repo,
        _adapter(artifacts={"main": "reports/never_committed.json"}),
        allow_dirty=True,
    )
    assert row.score.render() == str(WORKING_TREE_RMSE)
    assert row.score.allow_dirty


def test_CR5_a_marked_cell_declares_itself_in_its_own_dict(toy_repo: Repo) -> None:
    """SILENT: the marker is on the Cell, not inferred from context.

    ``Cell`` is passed around by value and outlives the ``ArtifactRef`` it came
    from. A marker that had to be looked up on the ref would be a marker the
    renderer three frames away could not see.
    """
    marked = Cell.measured(1.0, "src", allow_dirty=True)
    assert marked.to_dict()[ALLOW_DIRTY_KEY] is True
    assert Cell.measured(1.0, "src").to_dict()[ALLOW_DIRTY_KEY] is False
