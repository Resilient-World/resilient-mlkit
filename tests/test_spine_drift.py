"""Controls for the spine drift check.

Same discipline as the fleet reader's tests: every verdict is proved to fire on
the condition it names AND to stay silent on the others. A drift check that
reported DRIFTED for everything would look diligent and be useless, and one
that reported IN-SYNC for everything would be worse.

The verdict that matters most here is UNCLAIMED, and it is the one a naive
implementation gets wrong. A file WITHOUT the canonical banner is not drift:
``sync_spine.py`` refuses to overwrite it, so it does not get reverted at the
next sync -- it stays wrong permanently. Counting it as drift would put a
permanent divergence in the same bucket as a transient one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resilient_mlkit.core.spine import (
    ABSENT,
    CANONICAL_FILES,
    DRIFTED,
    IN_SYNC,
    MARKER,
    NO_SPINE_SOURCE,
    SEED_FILES,
    UNCLAIMED,
    compare,
    has_banner,
    summarise,
)

BANNERED = f"<!-- {MARKER}: authored in resilient-mlkit/spine -->\nline one\nline two\n"


@pytest.fixture()
def trees(tmp_path: Path) -> tuple[Path, Path]:
    """A spine and a repo, with every canonical file deployed in sync."""
    spine = tmp_path / "spine"
    repo = tmp_path / "resilient-toy"
    for src_rel, dest_rel in CANONICAL_FILES:
        (spine / src_rel).parent.mkdir(parents=True, exist_ok=True)
        (spine / src_rel).write_text(BANNERED)
        (repo / dest_rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / dest_rel).write_text(BANNERED)
    return spine, repo


def _verdict(spine: Path, repo: Path, relpath: str) -> str:
    by_path = {d.relpath: d for d in compare(spine, "toy", repo)}
    return by_path[relpath].verdict


# ------------------------------------------------------------- the banner


def test_the_banner_is_recognised_inside_the_window() -> None:
    assert has_banner(BANNERED)


def test_the_banner_is_not_recognised_beyond_the_window() -> None:
    """FIRES: a banner buried 4000 characters down would let the syncer
    overwrite a hand-written file, so the window is part of the contract."""
    assert not has_banner("x" * 6000 + MARKER)


def test_a_file_with_no_banner_is_not_recognised() -> None:
    assert not has_banner("just some prose\n")


# ------------------------------------------------------------- verdicts


def test_identical_files_are_IN_SYNC_and_nothing_else(trees: tuple[Path, Path]) -> None:
    """SILENT: the whole-repo negative control. If this ever fires, every other
    assertion in this file is meaningless."""
    spine, repo = trees
    drifts = compare(spine, "toy", repo)
    assert summarise(drifts) == {IN_SYNC: len(CANONICAL_FILES)}
    assert all(d.clean for d in drifts)
    assert all(d.changed_lines == 0 for d in drifts)


def test_a_bannered_file_whose_bytes_moved_is_DRIFTED(trees: tuple[Path, Path]) -> None:
    """FIRES: and reports how far it moved, so a one-word change is not
    presented the same way as a rewrite."""
    spine, repo = trees
    (repo / "CLAUDE.md").write_text(BANNERED.replace("line two", "line two, edited\nline three"))
    drifts = {d.relpath: d for d in compare(spine, "toy", repo)}
    d = drifts["CLAUDE.md"]
    assert d.verdict == DRIFTED
    assert d.changed_lines > 0
    assert d.sample
    assert d.spine_sha256 != d.deployed_sha256
    # The other five stay clean: drift in one file must not smear across the row.
    assert summarise(list(drifts.values())) == {DRIFTED: 1, IN_SYNC: len(CANONICAL_FILES) - 1}


def test_an_unbannered_file_is_UNCLAIMED_and_never_DRIFTED(trees: tuple[Path, Path]) -> None:
    """FIRES on the distinction that matters.

    sync_spine.py will not overwrite this file, so it is a PERMANENT divergence,
    not one the next sync fixes. Filing it under DRIFTED would hide that.
    """
    spine, repo = trees
    (repo / "docs" / "SELECTION.md").write_text("hand-written, no banner\n")
    d = {x.relpath: x for x in compare(spine, "toy", repo)}["docs/SELECTION.md"]
    assert d.verdict == UNCLAIMED
    assert d.verdict != DRIFTED
    assert "will not overwrite it" in d.detail


def test_an_unbannered_file_that_happens_to_match_is_still_IN_SYNC(
    trees: tuple[Path, Path],
) -> None:
    """SILENT: identity is decided on bytes, not on the banner.

    Without this control, UNCLAIMED could be firing on 'no banner' alone rather
    than on 'no banner AND different', and every matching file would be flagged.
    """
    spine, repo = trees
    unbannered = "no banner here\n"
    (spine / "docs" / "SELECTION.md").write_text(unbannered)
    (repo / "docs" / "SELECTION.md").write_text(unbannered)
    assert _verdict(spine, repo, "docs/SELECTION.md") == IN_SYNC


def test_a_missing_deployed_file_is_ABSENT(trees: tuple[Path, Path]) -> None:
    """FIRES: and is not confused with drift. The spine is not in force at all."""
    spine, repo = trees
    (repo / "docs" / "READINESS.md").unlink()
    d = {x.relpath: x for x in compare(spine, "toy", repo)}["docs/READINESS.md"]
    assert d.verdict == ABSENT
    assert d.deployed_sha256 == ""
    assert d.spine_sha256


def test_a_missing_spine_source_blames_this_repo_not_that_one(
    trees: tuple[Path, Path],
) -> None:
    """FIRES: an adapter-side defect must not be reported as the model repo's."""
    spine, repo = trees
    (spine / "docs" / "RUN_ECONOMICS.md").unlink()
    d = {x.relpath: x for x in compare(spine, "toy", repo)}["docs/RUN_ECONOMICS.md"]
    assert d.verdict == NO_SPINE_SOURCE
    assert "spine/" in d.detail


# ---------------------------------------------------------- report-only


def test_comparing_writes_nothing_into_the_repo(trees: tuple[Path, Path]) -> None:
    """The load-bearing claim of `mlkit spine`. A checker that repaired what it
    found would destroy a hand-written file on a canonical filename, which is
    the exact case UNCLAIMED exists to report rather than fix.
    """
    spine, repo = trees
    (repo / "CLAUDE.md").write_text("hand-written, no banner\n")
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    before_names = set(before)

    compare(spine, "toy", repo)

    after = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert set(after) == before_names, "the drift check created or removed a file"
    assert after == before, "the drift check modified a file"


# ------------------------------------------------------ the declaration


def test_seed_files_are_never_treated_as_canonical() -> None:
    """A signed allowlist and an accumulating escalations log are the two files
    an automated process must never overwrite. If either appeared in
    CANONICAL_FILES, sync_spine.py would revert signed determinations.
    """
    canonical_dests = {dest for _, dest in CANONICAL_FILES}
    seed_dests = {dest for _, dest in SEED_FILES}
    assert not canonical_dests & seed_dests
    assert "docs/allowlist.yaml" in seed_dests
    assert "docs/ESCALATIONS.md" in seed_dests


def test_the_syncer_and_the_checker_read_the_same_declaration() -> None:
    """Two definitions of 'canonical' is the same as none. sync_spine.py must
    import this one rather than keep its own copy."""
    source = (Path(__file__).resolve().parent.parent / "scripts" / "sync_spine.py").read_text()
    assert "from resilient_mlkit.core.spine import" in source
    assert "CANONICAL_FILES = (" not in source, "sync_spine.py re-declares CANONICAL_FILES"
    assert "SEED_FILES = (" not in source, "sync_spine.py re-declares SEED_FILES"


def test_every_spine_file_this_repo_declares_actually_exists() -> None:
    """The spine is this package's own tree, so a declaration pointing at a file
    that is not there is a defect here and detectable without any model repo."""
    spine = Path(__file__).resolve().parent.parent / "spine"
    missing = [
        src for src, _ in (*CANONICAL_FILES, *SEED_FILES) if not (spine / src).is_file()
    ]
    assert not missing, f"declared but absent from spine/: {missing}"
