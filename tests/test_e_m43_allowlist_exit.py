"""E-M43 — `mlkit allowlist verify` exits on every verdict it prints.

THE DEFECT, in two halves, and one clause that turned out not to be one.

**Half one.** An **UNSIGNED** allowlist printed `… entries, UNSIGNED` and left
the exit status at 0. CLAUDE.md rule 14 makes the signature the determination:
an agent proposes, a human signs, and every check built on the allowlist reports
ESCALATED rather than PASS precisely so that an unratified licence position
cannot be read as a ratified one. The one command whose entire job is to say
whether those determinations hold could not fail on their absence.

**Half two.** An invocation matching **no repository at all** printed nothing
and returned 0. Five sibling commands (`check`, `portfolio`, `spine`, `notice`,
`env`) already refused that with exit 2; `allowlist` had no guard, so "I read
no allowlist" and "every allowlist is fine" were the same answer. That is the
fleet's own *a check that cannot fail measures nothing* living inside the kit
that teaches it.

**The clause that was not a defect, kept here so the correction is visible
rather than the omission.** This lane was handed "flip one character of
`entries_sha256` and the command prints INVALID and still returns 0". Against
the PROCESS it returns 1 and always has: `cmd_allowlist` sets `rc = 1` on
`parse_error`, and `_verify_signature` writes the digest mismatch there. The 0
is a property of a PIPELINE — `… | head`, `… | tee` — where the shell reports
the last stage. Arm C2P drives that, and `test_the_digest_flip_already_exited_
non_zero_and_must_keep_doing_so` pins the behaviour that was already right, so
that it cannot become the defect it was reported as.

The arms in `reports/E_M43_ALLOWLIST_EXIT_ARMS.json` are driven in
SUBPROCESSES by `scripts/e_m43_allowlist_exit_drive.py` and read back here, so
the committed record cannot drift away from the code. The in-process tests
below are the same claims held against the function directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit.cli import NOTHING_MATCHED_EXIT, main
from resilient_mlkit.core import policy

ARMS = Path(__file__).resolve().parent.parent / "reports" / "E_M43_ALLOWLIST_EXIT_ARMS.json"


def _arms() -> dict[str, dict]:
    return {a["arm"]: a for a in json.loads(ARMS.read_text())["arms"]}


# -- the committed control record --------------------------------------------


def test_the_control_arms_are_committed_and_cover_the_preregistered_set():
    got = set(_arms())
    assert got == {"C1", "C2", "C2P", "C3", "C4", "C5", "C6", "C7", "C8a", "C8b"}


@pytest.mark.parametrize(
    "arm,expected",
    [("C1", 0), ("C2", 1), ("C3", 1), ("C4", 1), ("C5", 1), ("C6", 2), ("C7", 2)],
)
def test_each_driven_arm_exited_as_preregistered(arm, expected):
    assert _arms()[arm]["exit_code"] == expected


def test_the_not_dead_arms_show_both_halves_of_the_defect_returning_zero():
    """C8. With `cli.py` reverted, UNSIGNED and no-repo-matched both exit 0.

    Without this the fix could be tautological: two arms that pass because the
    conditions never arose. They arise, and on `main`'s code they return 0.
    """
    arms = _arms()
    assert arms["C8a"]["exit_code"] == 0
    assert arms["C8a"]["output_contains"]["UNSIGNED"] is True
    assert arms["C8b"]["exit_code"] == 0
    assert arms["C8b"]["stdout_lines"] == 0
    assert arms["C8b"]["stderr_lines"] == 0


def test_the_pipeline_arm_records_where_the_reported_zero_actually_came_from():
    """C2P. The command exits 1; the PIPELINE reports 0. Both are on the record."""
    arms = _arms()
    assert arms["C2"]["exit_code"] == 1
    assert arms["C2"]["mutation"]["differ"] is True
    assert arms["C2P"]["exit_code"] == 0


def test_the_control_record_names_no_directory():
    """The refusal quotes the root it searched, and this artifact is committed.

    A record objecting to invisible failures must not put a machine path in the
    repository to make its point. Positions and lengths, never the token.
    """
    from resilient_mlkit.core import artifact

    assert artifact.machine_paths_in_text(ARMS.read_text(), check_exists=False) == []
    c6 = _arms()["C6"]
    assert c6["stderr_named_the_root"] is True
    assert c6["root_token_length"] > 0


# -- the same claims, in process ---------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _root(tmp_path: Path, *, signed: bool = True, names=("arabica",)) -> Path:
    root = tmp_path / "portfolio"
    root.mkdir()
    for name in names:
        repo = root / f"resilient-{name}"
        (repo / "docs").mkdir(parents=True)
        entry = policy.Entry(
            id=f"{name}-source", kind="data", status="ALLOWED",
            licence_url="https://example.invalid/l", retrieval_date="2026-09-07",
        )
        digest = policy.entries_digest({entry.id: entry})
        (repo / policy.ALLOWLIST_RELPATH).write_text(
            "entries:\n"
            f"  - id: {entry.id}\n    kind: data\n    status: ALLOWED\n"
            f"    licence_url: {entry.licence_url}\n"
            f'    retrieval_date: "{entry.retrieval_date}"\n'
            "signature:\n"
            f"  signed: {'true' if signed else 'false'}\n"
            "  signed_by: signatory@example.invalid\n"
            '  signed_at: "2026-09-07"\n'
            f'  entries_sha256: "{digest}"\n'
        )
        _git(root, "init", "-q", str(repo))
        _git(repo, "config", "user.email", "t@example.invalid")
        _git(repo, "config", "user.name", "t")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "fixture")
    return root


def test_a_valid_signed_allowlist_still_exits_zero(tmp_path):
    """The case whose exit code the repair must PRESERVE.

    A guard bought by failing everywhere is not a guard; it is a broken command
    that happens to be red.
    """
    assert main(["allowlist", "verify", "--root", str(_root(tmp_path))]) == 0


def test_an_unsigned_allowlist_exits_non_zero_and_says_the_determinations_are_unratified(
    tmp_path, capsys
):
    """FIRES: half one. Printed and exited 0 before this."""
    rc = main(["allowlist", "verify", "--root", str(_root(tmp_path, signed=False))])
    assert rc == 1
    assert "UNSIGNED" in capsys.readouterr().out


def test_matching_no_repository_exits_two_and_refuses_out_loud(tmp_path, capsys):
    """FIRES: half two, and with its OWN exit code.

    2, not 1: "an allowlist was read and it is bad" and "nothing was read" are
    different problems with different fixes, and a caller that cannot tell them
    apart cannot act on either.
    """
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    rc = main(["allowlist", "verify", "--root", str(empty)])
    assert rc == NOTHING_MATCHED_EXIT == 2
    err = capsys.readouterr().err
    assert "REFUSED, not a pass" in err
    assert str(empty) in err


def test_naming_a_repo_that_is_not_checked_out_is_also_nothing_measured(tmp_path, capsys):
    """The subtler shape: a valid root, a valid repo name, and no intersection."""
    rc = main(["allowlist", "verify", "--root", str(_root(tmp_path)), "--repo", "choco"])
    assert rc == NOTHING_MATCHED_EXIT
    assert "--repo choco" in capsys.readouterr().err


def test_the_digest_flip_already_exited_non_zero_and_must_keep_doing_so(tmp_path, capsys):
    """PINS behaviour that was already right, because it was reported as broken.

    The mutation is applied in Python and asserted to have changed the bytes.
    A BSD `sed` BRE has no `\\?`, and this fleet has already spent one corrupted-
    digest control that corrupted nothing and read as a live check.
    """
    root = _root(tmp_path)
    target = root / "resilient-arabica" / policy.ALLOWLIST_RELPATH
    before = target.read_text()
    old = before.split('entries_sha256: "')[1][:64]
    new = ("a" if old[0] != "a" else "b") + old[1:]
    after = before.replace(old, new)
    assert after != before, "the mutation changed nothing; this test would test nothing"
    target.write_text(after)
    _git(root / "resilient-arabica", "commit", "-qam", "flip")

    assert main(["allowlist", "verify", "--root", str(root)]) == 1
    assert "entries_sha256 does not match" in capsys.readouterr().out


def test_a_missing_allowlist_and_a_defective_entry_both_still_exit_non_zero(tmp_path, capsys):
    """The two branches that were already non-zero, pinned beside the two new ones."""
    root = _root(tmp_path)
    (root / "resilient-arabica" / policy.ALLOWLIST_RELPATH).unlink()
    assert main(["allowlist", "verify", "--root", str(root)]) == 1
    assert "MISSING" in capsys.readouterr().out


# -- the same shape, hunted across the other subcommands ----------------------


def test_notice_exits_non_zero_when_it_refused_to_write_one(tmp_path, capsys):
    """`mlkit notice` printed REFUSED and returned 0.

    R9's own remedy text sends an agent into this command, which makes its exit
    status a gate whether or not anyone declared it one:
    `mlkit notice && git commit -am regenerate` committed nothing and reported
    success.
    """
    root = _root(tmp_path)
    (root / "resilient-arabica" / "NOTICE.md").write_text(
        "# NOTICE\n\nhand-written attribution mlkit did not generate\n"
    )
    rc = main(["notice", "--root", str(root)])
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().out


def test_notice_still_exits_zero_when_it_wrote_every_notice(tmp_path):
    """The preserved case, again: a writer that only ever fails writes nothing."""
    assert main(["notice", "--root", str(_root(tmp_path))]) == 0


def test_keys_refuses_to_describe_a_portfolio_it_did_not_read(tmp_path, capsys):
    """`mlkit keys` said "Nothing in the portfolio is waiting on a key" from an
    empty root — a statement about eight repositories made from reading none."""
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    assert main(["keys", "--root", str(empty)]) == NOTHING_MATCHED_EXIT
    assert "REFUSED, not a pass" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["check", "portfolio", "spine", "notice", "env", "keys",
                                     "allowlist"])
def test_every_repo_walking_command_refuses_an_empty_selection(tmp_path, command):
    """One definition of "nothing matched", used by all seven.

    Six copies of a guard is six chances for the seventh command not to have
    one, which is exactly how `allowlist` came to have none.
    """
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    argv = [command, "--root", str(empty)]
    if command == "check":
        argv.append("--portfolio")
    assert main(argv) == NOTHING_MATCHED_EXIT
