"""R13 QUOTED_RULE_PARITY controls (M-2), fixed in the prereg before the code.

The check reads CLAUDE.md's hard-stop bullets at HEAD, every prior bullet on
the tree's own history, and the S-5 register's vocabulary; it types nothing.
Every fixture here is a real git repo, because the superseded clauses come
from ``git log -- CLAUDE.md`` and the exemptions from a committed register.

K1/K1'/K2 -- the historical torrent case and the three mains -- are driven by
``scripts/r13_fleet_drive.py`` on real clones and recorded in
``reports/R13_FLEET_DRIVE.json``; the synthetic pair below (K9) reproduces
the same dynamic on a fixture whose history this test writes.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.parity import (
    FINDING_COPY,
    FINDING_STALE,
    W_COPY,
    W_STALE,
    clause_digest,
    hard_stop_bullets,
    r13_quoted_rule_parity,
    tokens,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

OLD_CLAUDE = """\
# CLAUDE.md

## Hard stops

Halt this repo immediately, without tuning or scaling, and report:

- a **D2** placebo estimate whose confidence interval excludes zero;
- an **E1** scaling curve that is flat between 10% and 25% of the data.

Both mean the planned run cannot buy what it is meant to buy.
"""

NEW_CLAUDE = """\
# CLAUDE.md

## Hard stops

Halt this repo immediately, without tuning or scaling, and report:

- a **D2** placebo estimate whose confidence interval excludes the declared
  null **in the direction the preregistered `[placebo]` declaration indicts**
  (S-5);
- an **E1** scaling curve that is flat between 10% and 25% of the data.

Both mean the planned run cannot buy what it is meant to buy.
"""

TOML = '[repo]\nname = "torrent"\n\n[source]\ntrees = ["src", "scripts"]\n'


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _commit(path: Path, msg: str) -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", msg)
    return _git(path, "rev-parse", "HEAD")


def _repo(tmp_path: Path, claude: str = NEW_CLAUDE, *, history: bool = True) -> Repo:
    """A repo whose CLAUDE.md was amended OLD -> NEW in git (when history=True)."""
    path = tmp_path / "resilient-torrent"
    (path / "src").mkdir(parents=True)
    (path / ".mlkit").mkdir()
    _git(path, "init", "-q", "-b", "main")
    (path / ".mlkit" / "repo.toml").write_text(TOML)
    (path / "src" / "ok.py").write_text("def f():\n    return 1\n")
    if history:
        (path / "CLAUDE.md").write_text(OLD_CLAUDE)
        _commit(path, "pre-amendment CLAUDE.md")
    (path / "CLAUDE.md").write_text(claude)
    _commit(path, "CLAUDE.md as measured")
    return Repo("torrent", path)


def _run(repo: Repo):
    return r13_quoted_rule_parity(repo, RunContext(nonce="t", root=repo.path.parent, offline=True))


def _add(repo: Repo, rel: str, body: str) -> None:
    p = repo.path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body))
    _commit(repo.path, f"add {rel}")


# ---------------------------------------------------------------------------
# the clause reader, and the digest that ignores formatting
# ---------------------------------------------------------------------------


def test_hard_stop_bullets_are_read_with_continuation_lines_and_markup_stripped():
    bullets = hard_stop_bullets(NEW_CLAUDE)
    assert bullets is not None and len(bullets) == 2
    assert bullets[0].startswith("a D2 placebo estimate whose confidence interval excludes the declared null")
    assert "**" not in bullets[0] and "`" not in bullets[0]
    assert hard_stop_bullets("# nothing\n\n## Other\n- x\n") is None


def test_the_clause_digest_is_over_tokens_so_reflow_and_requoting_are_silent():
    a = tokens('a **D2** placebo estimate whose confidence interval excludes zero;')
    b = tokens("a d2 placebo\n  estimate  whose 'confidence interval' EXCLUDES zero.")
    assert a == b and clause_digest(a) == clause_digest(b)


# ---------------------------------------------------------------------------
# silent on a clean tree; NA without a document
# ---------------------------------------------------------------------------


def test_silent_on_a_tree_with_no_quotation(tmp_path):
    r = _run(_repo(tmp_path))
    assert r.status is Status.PASS, r.reason
    assert r.evidence["findings"] == []
    assert [c["marker"] for c in r.evidence["clauses"]] == ["D2", "E1"]
    assert [c["marker"] for c in r.evidence["superseded_clauses"]] == ["D2"]
    assert r.evidence["window_tokens"] == {"stale": W_STALE, "second_copy": W_COPY}


def test_k7_no_claude_md_is_na(tmp_path):
    repo = _repo(tmp_path, history=False)
    (repo.path / "CLAUDE.md").unlink()
    _commit(repo.path, "drop CLAUDE.md")
    r = _run(repo)
    assert r.status is Status.NA and "CLAUDE.md" in r.reason


# ---------------------------------------------------------------------------
# K9 / K1-shape -- a file quoting the OLD bullet after the amendment: STALE
# ---------------------------------------------------------------------------


def test_k9_a_stale_quotation_fires_and_names_the_commit_the_clause_came_from(tmp_path):
    repo = _repo(tmp_path)
    old_sha = _git(repo.path, "rev-list", "--max-parents=0", "HEAD")
    _add(repo, "src/hard_stops.py", '''
        STOPS = {"D2": "a D2 placebo estimate whose confidence interval excludes zero (CLAUDE.md, Hard stops)"}
    ''')
    r = _run(repo)
    assert r.status is Status.FAIL
    kinds = {(f["kind"], f["clause"]) for f in r.evidence["findings"]}
    assert (FINDING_STALE, "D2") in kinds
    stale = [f for f in r.evidence["findings"] if f["kind"] == FINDING_STALE][0]
    # line 2: textwrap.dedent keeps the fixture's leading newline.
    assert stale["path"] == "src/hard_stops.py" and stale["line"] == 2
    assert stale["window"] == "confidence interval excludes zero"
    assert stale["clause_source"] == old_sha, "the superseded clause is tied to the commit it came from"
    assert "STALE_QUOTATION" in r.reason and "src/hard_stops.py:2" in r.reason


def test_k1_prime_the_same_file_before_the_amendment_is_a_second_copy_not_stale(tmp_path):
    """The E-069 dynamic: on the branch the sentence was CURRENT. The stale
    class is silent there; the generalised no-second-copy class is not."""
    repo = _repo(tmp_path, claude=OLD_CLAUDE, history=False)
    _add(repo, "src/hard_stops.py", '''
        STOPS = {"D2": "a D2 placebo estimate whose confidence interval excludes zero (CLAUDE.md, Hard stops)"}
    ''')
    r = _run(repo)
    kinds = {f["kind"] for f in r.evidence["findings"]}
    assert kinds == {FINDING_COPY}
    assert r.status is Status.FAIL


# ---------------------------------------------------------------------------
# K3 / K4 -- a docstring quoting the CURRENT clause verbatim, and its reflow
# ---------------------------------------------------------------------------


def test_k3_a_docstring_quoting_the_current_clause_verbatim_is_a_second_copy(tmp_path):
    repo = _repo(tmp_path)
    _add(repo, "scripts/report.py", '''
        """This repo halts on a D2 placebo estimate whose confidence interval excludes
        the declared null in the direction the preregistered [placebo] declaration
        indicts, and on an E1 scaling curve that is flat between 10% and 25% of the data."""
    ''')
    r = _run(repo)
    assert r.status is Status.FAIL
    found = {(f["kind"], f["clause"]) for f in r.evidence["findings"]}
    assert found == {(FINDING_COPY, "D2"), (FINDING_COPY, "E1")}
    assert not any(f["kind"] == FINDING_STALE for f in r.evidence["findings"])


def test_k4_reflowing_and_requoting_the_quotation_changes_nothing(tmp_path):
    a = _repo(tmp_path / "a")
    _add(a, "scripts/report.py", '''
        MSG = "an E1 scaling curve that is flat between 10% and 25% of the data"
    ''')
    b = _repo(tmp_path / "b")
    _add(b, "scripts/report.py", """
        MSG = (
            'an **E1** scaling'
            "  curve that is FLAT between 10%"
            ' and 25% of the data'
        )
    """)
    ra, rb = _run(a), _run(b)
    assert ra.status is rb.status is Status.FAIL
    fa, fb = ra.evidence["findings"][0], rb.evidence["findings"][0]
    assert fa["clause_sha256"] == fb["clause_sha256"]
    assert fa["kind"] == fb["kind"] == FINDING_COPY


# ---------------------------------------------------------------------------
# K5 -- the useless-scanner falsifier: paraphrase, vocabulary, two-sided predicate
# ---------------------------------------------------------------------------


def test_k5_a_paraphrase_naming_the_rule_is_not_a_copy(tmp_path):
    repo = _repo(tmp_path)
    _add(repo, "src/hard_stops.py", '''
        """S-5 amended the D2 sentence so that the halt region is the one the
        preregistered [placebo] declaration indicts rather than a fixed two-sided
        region around zero; read the current wording in CLAUDE.md. The placebo,
        the interval, the confidence, the halt: all named here, none quoted.
        A scaling curve flat at the top is the E1 stop's subject."""

        def halts(lo, hi):
            return lo > 0.0 or hi < 0.0   # the default two-sided region, written out
    ''')
    r = _run(repo)
    assert r.status is Status.PASS, r.evidence["findings"]


# ---------------------------------------------------------------------------
# K6 -- the register's vocabulary exempts, and removing the listing re-fires
# ---------------------------------------------------------------------------


def _register(files: list[str]) -> str:
    return json.dumps({
        "repo_identity": {"torrent": "resilient-torrent"},
        "the_rule_it_replaces": "a D2 placebo estimate whose confidence interval excludes zero",
        "source_files_quoting_the_replaced_sentence": {"resilient-torrent": files},
        "how_this_is_enforced": {"scanner": "scripts/verify_register.py --mode check"},
    })


def test_k6_a_register_listed_site_is_registered_not_failing_and_unlisting_refires(tmp_path):
    repo = _repo(tmp_path)
    _add(repo, "src/hard_stops.py", '''
        STOPS = {"D2": "a D2 placebo estimate whose confidence interval excludes zero"}
    ''')
    _add(repo, "scripts/verify_register.py", '''
        """Scans for the replaced clause: a D2 placebo estimate whose confidence interval
        excludes zero, and for the amended one: excludes the declared null in the
        direction the preregistered [placebo] declaration indicts (S-5)."""
    ''')
    _add(repo, "docs/one_sided_placebo_register.json", _register(["src/hard_stops.py"]))
    r = _run(repo)
    assert r.status is Status.PASS, r.reason
    assert r.evidence["register_at_head"] is True
    assert {s["path"] for s in r.evidence["registered_sites"]} == {"src/hard_stops.py"}
    assert {s["path"] for s in r.evidence["enforcement_sites"]} == {"scripts/verify_register.py"}
    assert r.evidence["findings"] == []

    # check-not-dead: the listing removed, the same tree FAILS by name
    _add(repo, "docs/one_sided_placebo_register.json", _register([]))
    r2 = _run(repo)
    assert r2.status is Status.FAIL
    assert {f["path"] for f in r2.evidence["findings"]} == {"src/hard_stops.py"}
    assert {s["path"] for s in r2.evidence["enforcement_sites"]} == {"scripts/verify_register.py"}


# ---------------------------------------------------------------------------
# K8 -- reports/ is disclosed, never failed
# ---------------------------------------------------------------------------


def test_k8_an_artifact_quoting_a_superseded_clause_is_disclosed_not_failed(tmp_path):
    repo = _repo(tmp_path)
    doc_sha = _run(repo).evidence["claude_md_sha256"]
    _add(repo, "reports/old.json", json.dumps({
        "claude_md_literal_reading": "a D2 placebo estimate whose confidence interval excludes zero",
    }))
    _add(repo, "reports/tied.json", json.dumps({
        "clause": "an E1 scaling curve that is flat between 10% and 25% of the data",
        "claude_md": {"sha256": doc_sha},
    }))
    _add(repo, "reports/untied.md", "halts on an E1 scaling curve that is flat between 10% and 25% of the data\n")
    r = _run(repo)
    assert r.status is Status.PASS, r.reason
    standing = {a["path"]: a["standing"] for a in r.evidence["artifacts"]}
    assert standing == {"reports/old.json": "stale", "reports/tied.json": "tied", "reports/untied.md": "untied"}
    assert r.evidence["artifact_counts"] == {"tied": 1, "untied": 1, "stale": 1}


# ---------------------------------------------------------------------------
# the verdict surface: committed at HEAD, mlkit_bindings.py included, working tree ignored
# ---------------------------------------------------------------------------


def test_mlkit_bindings_at_the_root_is_on_the_verdict_surface(tmp_path):
    repo = _repo(tmp_path)
    _add(repo, "mlkit_bindings.py", '''
        DOC = "an E1 scaling curve that is flat between 10% and 25% of the data"
    ''')
    r = _run(repo)
    assert r.status is Status.FAIL
    assert r.evidence["findings"][0]["path"] == "mlkit_bindings.py"
    assert "mlkit_bindings.py" in r.evidence["verdict_trees"]


def test_an_uncommitted_working_tree_quotation_is_not_read(tmp_path):
    repo = _repo(tmp_path)
    (repo.path / "src" / "wt.py").write_text(
        'X = "an E1 scaling curve that is flat between 10% and 25% of the data"\n'
    )
    r = _run(repo)
    assert r.status is Status.PASS, "R13 reads committed blobs at HEAD, never the working tree"
