"""M-3 REPAIR controls: a merged tree that cannot supply an input says so.

The adjudicator's finding, 2026-09-05. ``core.merged.checkout`` builds its
worktree from tree objects, so it holds COMMITTED content only. Every
data-bearing check in the fleet -- chokepoint D2/D6/E1, fray D2/D3/D6/E1,
torrent D2/E1 -- resolves a binding that reads a gitignored panel, so through
``mlkit check --merged-with`` those bindings reached a byte that was not there
and ``cli._run_phase``'s generic handler rendered **FAIL**. Measured on a real
fray clone at ``a18c447`` before this change: the merged decision phase gave
``D2 PASS`` and ``D3 PASS`` off committed evidence whose inputs were not
present, and ``D6 FAIL`` / ``E1 FAIL`` reading
``scaling_probe raised TemporalSplitIdentityMismatch`` -- an environment
failure in the shape ``hard_stops.py`` reads as a fired stop.

That is the same class of defect fray #115 landed: an artifact recording that a
promotion-gate re-run was NOT identical when the re-run's inputs were absent
and it had measured nothing.

The rows below are those fixed in
``reports/validation/v3-stack-repair-drive-writer-and-m3-unmeasurable.prereg.json``
(B1-B7) before the code was written.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

from resilient_mlkit import cli
from resilient_mlkit.checks import RunContext
from resilient_mlkit.core import inputs
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import InputUnavailable, Status

TOML = """\
[repo]
name = "torrent"

[bindings]
placebo_test = "guard_bindings:placebo_test"

[source]
trees = ["src"]
"""

BINDINGS = """\
def placebo_test():
    # Reads nothing: whether this runs at all is the only thing under test.
    return {"estimate": 0.01, "ci_low": -0.1, "ci_high": 0.12, "reference_effect": 1.0}
"""


def _repo(tmp_path: Path, *, inputs_table: str = "", stage: bool = False) -> tuple[Path, Repo]:
    root = tmp_path / "root"
    path = root / "resilient-torrent"
    (path / ".mlkit").mkdir(parents=True)
    (root / "resilient-fray").mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "main"], check=True)
    (path / ".mlkit" / "repo.toml").write_text(TOML + inputs_table)
    (path / "guard_bindings.py").write_text(textwrap.dedent(BINDINGS))
    if stage:
        (path / "data").mkdir()
        (path / "data" / "panel.parquet").write_bytes(b"rows")
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t",
         "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-q", "-m", "seed"], check=True, capture_output=True)
    return root, Repo("torrent", path)


# ---------------------------------------------------------------------------
# B1 -- what a repo declares, and the three answers it can give
# ---------------------------------------------------------------------------


def test_b1_undeclared_declared_empty_and_declared_paths_are_three_answers(tmp_path):
    _, undeclared = _repo(tmp_path / "a")
    assert inputs.declared(undeclared, "placebo_test") is None

    _, empty = _repo(tmp_path / "b", inputs_table='\n[inputs]\nplacebo_test = []\n')
    assert inputs.declared(empty, "placebo_test") == []

    _, named = _repo(
        tmp_path / "c", inputs_table='\n[inputs]\nplacebo_test = ["data/panel.parquet"]\n'
    )
    assert inputs.declared(named, "placebo_test") == ["data/panel.parquet"]


@pytest.mark.parametrize(
    "table",
    [
        '\n[inputs]\nplacebo_test = "data/panel.parquet"\n',   # a string, not a list
        '\n[inputs]\nplacebo_test = [1, 2]\n',                  # not paths
        '\n[inputs]\nplacebo_test = [""]\n',                    # an empty path
    ],
)
def test_b1_a_malformed_declaration_answers_none_and_so_REFUSES(tmp_path, table):
    """A repo may not reach a looser outcome by breaking this file."""
    _, repo = _repo(tmp_path, inputs_table=table)
    assert inputs.declared(repo, "placebo_test") is None
    repo.require_declared_inputs = True
    with pytest.raises(InputUnavailable):
        repo.resolve("placebo_test")


def test_b2_absent_names_what_the_tree_does_not_carry(tmp_path):
    _, repo = _repo(tmp_path, stage=True)
    assert inputs.absent(repo, ["data/panel.parquet"]) == []
    assert inputs.absent(repo, ["data/gone.parquet"]) == ["data/gone.parquet"]
    # An absolute path, and one that climbs out of the tree, are ABSENT: a
    # declaration mlkit cannot resolve against the tree it is driving has
    # established nothing about that tree.
    assert inputs.absent(repo, ["/etc/hosts"]) == ["/etc/hosts"]
    assert inputs.absent(repo, ["../resilient-fray"]) == ["../resilient-fray"]


# ---------------------------------------------------------------------------
# B2 / B3 -- the guard: UNMEASURABLE, never FAIL and never PASS
# ---------------------------------------------------------------------------


def _decision(root: Path, *extra: str) -> int:
    return cli.main([
        "check", "--phase", "decision", "--root", str(root), "--repo", "torrent",
        "--offline", *extra,
    ])


def _row(capsys, check_id: str) -> tuple[str, str]:
    out = capsys.readouterr().out
    for line in out.splitlines():
        if line.startswith(f"{check_id} "):
            parts = line.split(None, 2)
            return parts[1], (parts[2] if len(parts) > 2 else "")
    raise AssertionError(f"no {check_id} row in:\n{out}")


def test_b3_an_undeclared_binding_on_a_merged_tree_is_UNMEASURABLE(tmp_path, capsys):
    root, _ = _repo(tmp_path)
    rc = _decision(root, "--merged-with", "main")
    status, detail = _row(capsys, "D2")
    assert status == "UNMEASURABLE", (status, detail)
    assert "declares no inputs" in detail
    assert "[inputs]" in detail
    # exit 3: unmeasured is not green, and it is NOT the FAIL exit -- CI gating
    # on 1 must not read an absent panel as a broken repo (M-1).
    assert rc == 3


def test_b2_a_declared_input_the_tree_does_not_carry_is_UNMEASURABLE(tmp_path, capsys):
    root, _ = _repo(tmp_path, inputs_table='\n[inputs]\nplacebo_test = ["data/panel.parquet"]\n')
    rc = _decision(root, "--merged-with", "main")
    status, detail = _row(capsys, "D2")
    assert status == "UNMEASURABLE", (status, detail)
    assert "data/panel.parquet" in detail
    assert rc == 3


def test_b7_an_unmeasurable_row_indicts_nothing_and_carries_the_input(tmp_path):
    _, repo = _repo(tmp_path, inputs_table='\n[inputs]\nplacebo_test = ["data/panel.parquet"]\n')
    repo.require_declared_inputs = True
    ctx = RunContext(nonce="n", root=repo.path.parent, offline=True)
    results = {r.check_id: r for r in cli._run_phase(repo, "decision", ctx)}
    d2 = results["D2"]
    assert d2.status is Status.UNMEASURABLE
    assert "halt" not in d2.evidence          # nothing is indicted, ever
    assert d2.evidence["input"] == "data/panel.parquet"
    assert d2.evidence["inputs_absent"] == ["data/panel.parquet"]
    assert d2.evidence["drive"] == "merged-worktree"


# ---------------------------------------------------------------------------
# B4 -- CHECK-NOT-DEAD: present inputs are DRIVEN, not refused
# ---------------------------------------------------------------------------


def test_b4_check_not_dead_a_declared_input_that_is_present_runs_the_check(tmp_path, capsys):
    root, _ = _repo(
        tmp_path, inputs_table='\n[inputs]\nplacebo_test = ["data/panel.parquet"]\n', stage=True
    )
    _decision(root, "--merged-with", "main")
    status, detail = _row(capsys, "D2")
    assert status == "PASS", (status, detail)
    assert "estimate=0.01" in detail


def test_b4_check_not_dead_an_empty_declaration_is_a_positive_declaration(tmp_path, capsys):
    root, _ = _repo(tmp_path, inputs_table='\n[inputs]\nplacebo_test = []\n')
    _decision(root, "--merged-with", "main")
    status, detail = _row(capsys, "D2")
    assert status == "PASS", (status, detail)


# ---------------------------------------------------------------------------
# B5 -- SILENCE: a plain drive is untouched
# ---------------------------------------------------------------------------


def test_b5_the_guard_is_armed_only_on_a_merged_tree_drive(tmp_path, capsys):
    """The same undeclared repo, driven plainly, renders exactly what it did."""
    root, repo = _repo(tmp_path)
    assert repo.require_declared_inputs is False
    _decision(root)
    status, detail = _row(capsys, "D2")
    assert status == "PASS", (status, detail)
    assert "estimate=0.01" in detail


def test_b5_only_the_merged_worktree_repo_carries_the_flag(tmp_path):
    """Structural: `cmd_check` sets it on the drive repo and on nothing else."""
    body = (Path(cli.__file__)).read_text()
    assert "Repo(repo.name, worktree, require_declared_inputs=True)" in body
    assert body.count("require_declared_inputs=True") == 1


# ---------------------------------------------------------------------------
# B6 -- the refusal is mlkit's, and is NOT the premature one
# ---------------------------------------------------------------------------


def test_b6_the_guard_is_not_a_premature_input_refusal(tmp_path):
    """A SUBJECT module refusing during its own import still renders FAIL.

    The two refusals must stay distinguishable: `PrematureInputRefusal` is a
    binding dodging a check it has not resolved anything for, and it is a FAIL
    by name. This guard is mlkit's own, raised before the import, over the
    repo's own committed declaration -- UNMEASURABLE.
    """
    root, repo = _repo(tmp_path, inputs_table='\n[inputs]\nplacebo_test = []\n')
    (repo.path / "guard_bindings.py").write_text(
        "from resilient_mlkit import InputUnavailable\n"
        "raise InputUnavailable('refusing at import time')\n"
    )
    repo.require_declared_inputs = True
    ctx = RunContext(nonce="n", root=root, offline=True)
    d2 = {r.check_id: r for r in cli._run_phase(repo, "decision", ctx)}["D2"]
    assert d2.status is Status.FAIL
    assert "PREMATURE_INPUT_REFUSAL" in d2.reason


def test_b6_the_undeclared_refusal_masks_a_merge_defect_and_names_the_remedy(tmp_path, capsys):
    """The stated COST of the fail-closed choice, driven rather than described.

    ``tests/test_merged_tree_drive.py`` T1 reproduces E-069: a defect that
    exists only in the combination of two individually-correct branches, and
    that fires as D2 FAIL on the merged tree. Strip the fixture's `[inputs]`
    declaration and that FAIL becomes UNMEASURABLE -- the finding is not lost,
    it is not yet established, and the row says which line of TOML establishes
    it. This is the price of never rendering an absent input as a verdict, and
    it is one line per binding.
    """
    from tests import test_merged_tree_drive as t1

    root, repo, shas = t1._e069_shaped_repo(tmp_path)
    config = repo / ".mlkit" / "repo.toml"

    rc = _decision(root, "--merged-with", "base")
    status, _ = _row(capsys, "D2")
    assert status == "FAIL" and rc == 1

    # Remove the declaration on HEAD ONLY: git takes the deletion, base is
    # untouched there, and no hunk conflicts -- so the merged tree is exactly
    # the T1 tree minus the one line, and nothing else moved.
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "refs/heads/head"],
                   check=True, capture_output=True)
    config.write_text(config.read_text().replace("[inputs]\nplacebo_test = []\n", ""))
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qam", "head: drop the [inputs] declaration"],
        check=True, capture_output=True)
    assert shas["head"]  # named so the fixture's own shas stay visible in the record

    rc = _decision(root, "--merged-with", "base")
    status, detail = _row(capsys, "D2")
    assert status == "UNMEASURABLE", (status, detail)
    assert "declares no inputs" in detail and "[inputs]" in detail
    assert rc == 3
