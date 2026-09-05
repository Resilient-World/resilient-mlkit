"""M-3 controls: the merged-tree drive, and "MERGED is not in main".

Three defects this week existed ONLY in the combination of two individually
correct changes (torrent E-069; chokepoint #122; the stacked-merge trap, three
times), and each was found by a person building the merged tree by hand. These
controls are the rows fixed in ``reports/M3_MERGED_TREE_DRIVE_PREREGISTRATION.md``
before the code was written.

The fixture reproduces the SHAPE of E-069 with mlkit's own D2: ``head`` adds a
``placebo_test`` binding whose payload PASSES under the default region and
reports a positive real-run effect; ``base`` declares ``[placebo] indicts =
"below"`` with an estimand. Each is fine alone -- PASS on head, NA on base
(no binding) -- and on the merge D2 is FAIL ``PLACEBO_EXEMPTS_THE_CLAIM``: the
declaration exempts the very direction the binding's claim lives in. Nothing
but the combination is wrong.

Every git operation here is the real thing: ``git merge-tree --write-tree``,
``git commit-tree``, ``git worktree``. A conflict is refused with exit 2 and
nothing is left behind.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from resilient_mlkit import cli
from resilient_mlkit.core import merged

ANCESTOR_TOML = """\
[repo]
name = "torrent"

[bindings]
# (no bindings yet)

# padding so the two branches' hunks are far apart and git merges them cleanly
# padding line 2
# padding line 3
# padding line 4
# padding line 5
# padding line 6

[source]
trees = ["src"]
"""

PLACEBO_TABLE = """
[placebo]
estimand = "skill against the persistence floor; a placebo far below it is what no signal looks like"
indicts = "below"
"""

BINDING_MODULE = """\
def placebo_test():
    # PASSES under the default two-sided region: contains zero, half-width
    # 0.11 < reference effect 1.0. The claim lives ABOVE the null.
    return {"estimate": 0.01, "ci_low": -0.1, "ci_high": 0.12, "reference_effect": 1.0}
"""


def _git(path: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _commit_all(path: Path, message: str) -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD")


def _e069_shaped_repo(tmp_path: Path, *, conflict: bool = False) -> tuple[Path, Path, dict[str, str]]:
    """``<root>/resilient-torrent`` with branches ancestor / base / head."""
    root = tmp_path / "root"
    repo = root / "resilient-torrent"
    (repo / ".mlkit").mkdir(parents=True)
    (root / "resilient-fray").mkdir()  # a second sibling so find_root() is never consulted
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".mlkit" / "repo.toml").write_text(ANCESTOR_TOML)
    shas = {"ancestor": _commit_all(repo, "ancestor")}

    _git(repo, "checkout", "-q", "-b", "base")
    if conflict:
        (repo / ".mlkit" / "repo.toml").write_text(
            ANCESTOR_TOML.replace("# (no bindings yet)", 'coverage = "other:coverage"')
        )
    else:
        (repo / ".mlkit" / "repo.toml").write_text(ANCESTOR_TOML + PLACEBO_TABLE)
    shas["base"] = _commit_all(repo, "base: declare the halt region")

    _git(repo, "checkout", "-q", "-b", "head", shas["ancestor"])
    (repo / ".mlkit" / "repo.toml").write_text(
        ANCESTOR_TOML.replace("# (no bindings yet)", 'placebo_test = "m3_bindings:placebo_test"')
    )
    (repo / "m3_bindings.py").write_text(textwrap.dedent(BINDING_MODULE))
    shas["head"] = _commit_all(repo, "head: bind placebo_test")
    return root, repo, shas


def _d2(capsys) -> tuple[str, str]:
    """The D2 row (status, detail) from the printed phase table."""
    out = capsys.readouterr().out
    for line in out.splitlines():
        if line.startswith("D2 "):
            parts = line.split(None, 2)
            return parts[1], (parts[2] if len(parts) > 2 else "")
    raise AssertionError(f"no D2 row in:\n{out}")


def _check(root: Path, *extra: str) -> int:
    return cli.main([
        "check", "--phase", "decision", "--root", str(root), "--repo", "torrent",
        "--offline", *extra,
    ])


# ---------------------------------------------------------------------------
# T1 -- fires ONLY on the merge
# ---------------------------------------------------------------------------


def test_t1_the_defect_exists_only_in_the_combination(tmp_path, capsys):
    root, repo, shas = _e069_shaped_repo(tmp_path)

    # head alone: PASS
    assert _git(repo, "rev-parse", "HEAD") == shas["head"]
    rc_head = _check(root)
    status, _ = _d2(capsys)
    assert status == "PASS", status
    assert rc_head == 3  # the other decision rows are NA/ESCALATED; nothing failed

    # base alone: NA (no binding)
    _git(repo, "checkout", "-q", "base")
    rc_base = _check(root)
    status, detail = _d2(capsys)
    assert status == "NA" and "placebo_test" in detail
    assert rc_base == 3

    # the merge: FAIL, and by the name the combination earns
    _git(repo, "checkout", "-q", "head")
    rc_merge = _check(root, "--merged-with", "base")
    captured = capsys.readouterr().out
    d2 = [ln for ln in captured.splitlines() if ln.startswith("D2 ")][0]
    assert "FAIL" in d2 and "PLACEBO_EXEMPTS_THE_CLAIM" in d2, d2
    assert rc_merge == 1
    assert "MERGED-TREE DRIVE" in captured
    assert shas["head"][:12] in captured and shas["base"][:12] in captured
    assert "NOT saved to .mlkit/results/" in captured


# ---------------------------------------------------------------------------
# T2 -- a conflict is refused, never resolved, and leaves nothing behind
# ---------------------------------------------------------------------------


def test_t2_a_conflict_is_refused_with_exit_2_and_nothing_is_left_behind(tmp_path, capsys):
    root, repo, _ = _e069_shaped_repo(tmp_path, conflict=True)
    rc = _check(root, "--merged-with", "base")
    err = capsys.readouterr().err
    assert rc == 2
    assert "REFUSED" in err and ".mlkit/repo.toml" in err
    assert "does not resolve a conflict" in err
    assert len(_git(repo, "worktree", "list").splitlines()) == 1
    assert not (repo / ".mlkit" / "results").exists()


def test_t2_build_raises_merge_conflict_naming_the_path(tmp_path):
    _, repo, shas = _e069_shaped_repo(tmp_path, conflict=True)
    with pytest.raises(merged.MergeConflict) as exc:
        merged.build(repo, "base")
    assert exc.value.paths == [".mlkit/repo.toml"]
    assert exc.value.head_sha == shas["head"] and exc.value.base_sha == shas["base"]


# ---------------------------------------------------------------------------
# T3 -- silent when the merged tree IS the branch tree
# ---------------------------------------------------------------------------


def test_t3_a_contained_base_yields_the_head_tree_and_identical_statuses(tmp_path, capsys):
    root, repo, shas = _e069_shaped_repo(tmp_path)
    m = merged.build(repo, shas["ancestor"])
    assert m.identical_to_head is True
    assert m.merge_tree == m.head_tree

    rc_plain = _check(root)
    plain = [ln for ln in capsys.readouterr().out.splitlines() if ln[:2] in ("D1", "D2", "D3", "D4", "D5", "D6")]
    rc_merged = _check(root, "--merged-with", shas["ancestor"])
    out = capsys.readouterr().out
    merged_rows = [ln for ln in out.splitlines() if ln[:2] in ("D1", "D2", "D3", "D4", "D5", "D6")]
    assert rc_plain == rc_merged == 3
    assert [ln.split()[:2] for ln in plain] == [ln.split()[:2] for ln in merged_rows]
    assert "merged tree == HEAD tree" in out


# ---------------------------------------------------------------------------
# T4 / T5 -- no side effect on the real repo; the stamp names both parents
# ---------------------------------------------------------------------------


def test_t4_t5_the_stamp_names_both_parents_and_the_real_store_is_untouched(tmp_path, capsys):
    root, repo, shas = _e069_shaped_repo(tmp_path)
    out_json = tmp_path / "merged.json"
    rc = _check(root, "--merged-with", "base", "--json-out", str(out_json))
    capsys.readouterr()
    assert rc == 1
    assert not (repo / ".mlkit" / "results").exists(), "a merged drive must not write the real store"
    assert len(_git(repo, "worktree", "list").splitlines()) == 1
    assert _git(repo, "rev-parse", "HEAD") == shas["head"], "no branch may move"

    payload = json.loads(out_json.read_text())
    assert payload["artifact_schema"] == "resilient-mlkit/merged-tree-drive/1"
    assert payload["phase"] == "decision" and payload["base_ref"] == "base"
    (row,) = payload["repos"]
    assert row["repo"] == "torrent"
    assert row["head_sha"] == shas["head"] and row["base_sha"] == shas["base"]
    assert row["identical_to_head"] is False
    assert len(row["merge_tree"]) == 40 and len(row["merge_commit"]) == 40
    parents = _git(repo, "rev-list", "--parents", "-n", "1", row["merge_commit"]).split()[1:]
    assert parents == [shas["head"], shas["base"]]
    tree = _git(repo, "rev-parse", f"{row['merge_commit']}^{{tree}}")
    assert tree == row["merge_tree"]
    d2 = [r for r in row["results"] if r["check_id"] == "D2"][0]
    assert d2["status"] == "FAIL" and "PLACEBO_EXEMPTS_THE_CLAIM" in d2["reason"]
    assert d2["git_sha"] == row["merge_commit"], "results are stamped with the synthetic commit"


def test_the_synthetic_commit_is_deterministic_for_one_tree_pair(tmp_path):
    _, repo, _ = _e069_shaped_repo(tmp_path)
    a = merged.build(repo, "base")
    b = merged.build(repo, "base")
    assert a.merge_commit == b.merge_commit and a.merge_tree == b.merge_tree


# ---------------------------------------------------------------------------
# A1 / A2 / A3 -- ancestry: MERGED is a status word
# ---------------------------------------------------------------------------


def _stacked_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """main <- feature (base branch) <- side, with side merged INTO feature only."""
    repo = tmp_path / "stacked"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n")
    shas = {"main": _commit_all(repo, "on main")}
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "b.txt").write_text("b\n")
    shas["feature"] = _commit_all(repo, "on feature")
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "c.txt").write_text("c\n")
    shas["side"] = _commit_all(repo, "on side")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side into feature (reported MERGED)", "side")
    shas["feature_merge"] = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    return repo, shas


def test_a1_a2_a_commit_merged_into_a_feature_branch_is_not_in_main(tmp_path, capsys):
    repo, shas = _stacked_repo(tmp_path)
    rc = cli.main(["ancestry", "--path", str(repo), "--base", "main", shas["side"]])
    out = capsys.readouterr()
    assert rc == 1
    assert "NOT CONTAINED" in out.out and "status word" not in out.out
    assert "not in main" in out.err.lower() or "NOT in main" in out.err

    rc = cli.main(["ancestry", "--path", str(repo), "--base", "feature", shas["side"]])
    assert rc == 0
    assert "CONTAINED" in capsys.readouterr().out

    rc = cli.main(["ancestry", "--path", str(repo), "--base", "main", shas["main"], "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["rows"][0]["verdict"] == "CONTAINED"
    assert payload["rows"][0]["commit_sha"] == shas["main"]


def test_a2_one_uncontained_commit_among_contained_ones_fails_the_whole_call(tmp_path, capsys):
    repo, shas = _stacked_repo(tmp_path)
    rc = cli.main(["ancestry", "--path", str(repo), "--base", "main", shas["main"], shas["side"], "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert [r["verdict"] for r in payload["rows"]] == ["CONTAINED", "NOT CONTAINED"]


def test_a3_an_unresolvable_ref_asserts_nothing_and_exits_2(tmp_path, capsys):
    repo, shas = _stacked_repo(tmp_path)
    rc = cli.main(["ancestry", "--path", str(repo), "--base", "no-such-ref", shas["main"]])
    err = capsys.readouterr().err
    assert rc == cli.ANCESTRY_UNRESOLVABLE_EXIT == 2
    assert "REFUSED" in err and "no-such-ref" in err
    rc = cli.main(["ancestry", "--path", str(repo), "--base", "main", "deadbeefdeadbeef"])
    assert rc == 2
    with pytest.raises(merged.GitUnavailable):
        merged.contained(repo, "main", "deadbeefdeadbeef")


def test_containment_fields_is_one_row_per_commit(tmp_path):
    repo, shas = _stacked_repo(tmp_path)
    rows = merged.containment_fields(repo, "main", [shas["main"], shas["side"]])
    assert [r["contained"] for r in rows] == [True, False]
    assert all(r["base_sha"] == shas["main"] for r in rows)
