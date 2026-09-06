"""S-5 controls: does `register --check-fleet` fire on the drift nothing could see?

Every test here is one half of a matched pair, and the pairs all hold the same
variable: **one field of one copy of one document**. The fixtures are three
throwaway git repositories carrying the register and the repo's own
`canonical_body_sha256`, because that is the shape the real thing has — the
digest is the REPO's definition and mlkit calls it rather than owning a second
one (rule 7).

The control that decides whether this check is worth having is
`test_a_field_changed_with_the_digest_rederived_is_still_a_divergence`. E-080's
drift had every copy internally consistent and every repo's own scanner
reporting `0 problem(s)`; a check that only re-derives each copy's own digest
reproduces that blindness with more code. So the SILENT half of that pair is
the unmutated fleet and the FIRES half is a copy that would pass its OWN
verifier.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit import cli
from resilient_mlkit.core import register as reg

# The digest function as the three repos commit it, byte-identical across
# `resilient-fray`, `resilient-chokepoint` and `resilient-torrent` at their
# 2026-09-06 mains. Copied rather than imported: these fixtures must stand up
# without any sibling checkout present, and a fixture that imported mlkit's own
# idea of the digest would be testing mlkit against itself.
VERIFIER = '''#!/usr/bin/env python3
"""A repo's committed S-5 verifier, reduced to the function this check calls."""

import hashlib
import json


def canonical_body_sha256(doc: dict) -> str:
    body = {k: v for k, v in doc.items() if k != "canonical_body_sha256"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
'''

#: The register, reduced to the shapes the check has to reason about: plain
#: fields, the nested per-repo map that actually drifted, and a keyed list.
BODY: dict = {
    "artifact_schema": "one_sided_placebo_register/1",
    "item": "S-5",
    "title": "The one-sided placebo register",
    "source_files_quoting_the_replaced_sentence": {
        "resilient-fray": [],
        "resilient-chokepoint": [],
        "resilient-torrent": [],
    },
    "declarations": [
        {"id": "CP-D2-ABOVE", "repo": "resilient-chokepoint", "indicts": "above"},
        {"id": "FR-D2-SHUFFLE-ABOVE", "repo": "resilient-fray", "indicts": "above"},
        {"id": "FR-D2-NASS-45ORIGIN-ABOVE", "repo": "resilient-fray", "indicts": "above"},
    ],
}

REPOS = ("resilient-fray", "resilient-chokepoint", "resilient-torrent")


def digest(body: dict) -> str:
    """The fixture's own digest, computed the way the fixture's verifier does."""
    payload = {k: v for k, v in body.items() if k != "canonical_body_sha256"}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    import hashlib

    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sealed(body: dict) -> dict:
    out = dict(body)
    out["canonical_body_sha256"] = digest(out)
    return out


def make_repo(root: Path, body: dict, *, verifier: str = VERIFIER) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "scripts").mkdir(exist_ok=True)
    (root / reg.REGISTER_RELPATH).write_text(
        json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / reg.VERIFIER_RELPATH).write_text(verifier, encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    for args in (
        ["add", "-A"],
        [
            "-c", "user.name=fixture", "-c", "user.email=f@x.invalid",
            "commit", "--quiet", "-m", "fixture",
        ],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return root


def make_fleet(tmp_path: Path, bodies: dict[str, dict] | None = None) -> Path:
    root = tmp_path / "fleet"
    root.mkdir()
    for name in REPOS:
        body = (bodies or {}).get(name, sealed(BODY))
        make_repo(root / name, body)
    return root


def recommit(repo: Path, body: dict) -> None:
    (repo / reg.REGISTER_RELPATH).write_text(
        json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=fixture", "-c", "user.email=f@x.invalid",
            "commit", "--quiet", "-m", "mutation",
        ],
        check=True,
        capture_output=True,
    )


def kinds(report) -> set[str]:
    return {p.kind for p in report.problems}


def fields(report, kind: str) -> set[str]:
    return {p.field_path for p in report.problems if p.kind == kind}


# ---------------------------------------------------------------------------
# The pair the check exists for
# ---------------------------------------------------------------------------
def test_three_copies_of_one_document_pass(tmp_path):
    """SILENT. Three copies, identical bodies, each sealed with its own digest."""
    report = reg.check_fleet(make_fleet(tmp_path))
    assert report.ok
    assert report.refusal is None
    assert report.problems == ()
    assert len(report.copies) == 3
    assert report.one_blob is not None, (
        "identical content must be the identical git object; if it is not, the "
        "fixture is writing the file differently in each repo and no pair below "
        "is a pair"
    )
    assert {c.agreed_digest for c in report.copies} == {digest(BODY)}


def test_a_field_changed_with_the_digest_rederived_is_still_a_divergence(tmp_path):
    """FIRES. **The control that decides whether this check is worth having.**

    One copy edits one field and RE-DERIVES its own digest, so it is internally
    consistent, its own `--mode check` is green, and its own suite passes on the
    constant it pinned. That is E-080's state, four times over. The only reader
    who can see it is one holding every copy.
    """
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["title"] = "The one-sided placebo register (drifted)"
    recommit(root / "resilient-chokepoint", sealed(body))

    report = reg.check_fleet(root)
    assert not report.ok
    assert reg.SELF_INCONSISTENT not in kinds(report), (
        "the mutated copy re-derived its own digest, so the per-repo check every "
        "repo already runs is GREEN on it; if this fires the pair is not testing "
        "what it claims to"
    )
    assert kinds(report) == {reg.DIVERGENT}
    assert fields(report, reg.DIVERGENT) == {"title"}
    detail = next(p.detail for p in report.problems)
    assert "resilient-chokepoint" in detail
    assert "resilient-fray, resilient-torrent" in detail


def test_a_stale_digest_is_self_inconsistent_and_the_field_is_still_named(tmp_path):
    """FIRES on BOTH kinds: the copy edited a field and did not re-seal it."""
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["title"] = "The one-sided placebo register (drifted)"
    body["canonical_body_sha256"] = digest(BODY)  # the OLD digest, left behind
    recommit(root / "resilient-torrent", body)

    report = reg.check_fleet(root)
    assert kinds(report) == {reg.SELF_INCONSISTENT, reg.DIVERGENT}
    assert fields(report, reg.SELF_INCONSISTENT) == {"canonical_body_sha256"}
    assert fields(report, reg.DIVERGENT) == {"title"}


def test_a_digest_changed_alone_is_reported_and_nothing_else_is(tmp_path):
    """FIRES. The body is untouched, so there is no field divergence to find."""
    root = make_fleet(tmp_path)
    body = sealed(BODY)
    body["canonical_body_sha256"] = "0" * 64
    recommit(root / "resilient-fray", body)

    report = reg.check_fleet(root)
    assert kinds(report) == {reg.SELF_INCONSISTENT}
    assert [p.repo for p in report.problems] == ["resilient-fray"]


def test_a_missing_declaration_is_named_by_its_id_not_its_index(tmp_path):
    """FIRES. E-080's `FR-D2-NASS-45ORIGIN-ABOVE`: live in one copy only.

    Positional comparison would report "declarations[2] differs" and, on a
    deletion in the middle, every index after it — which names the drift so
    badly that a reader would go looking in the wrong place.
    """
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["declarations"] = [
        d for d in BODY["declarations"] if d["id"] != "FR-D2-NASS-45ORIGIN-ABOVE"
    ]
    recommit(root / "resilient-chokepoint", sealed(body))

    report = reg.check_fleet(root)
    assert fields(report, reg.DIVERGENT) == {"declarations[FR-D2-NASS-45ORIGIN-ABOVE]"}


def test_a_declaration_edited_in_place_names_the_field_inside_it(tmp_path):
    """FIRES, one level deeper: the id resolves, the field under it does not."""
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["declarations"] = [
        {**d, "indicts": "below"} if d["id"] == "CP-D2-ABOVE" else d
        for d in BODY["declarations"]
    ]
    recommit(root / "resilient-torrent", sealed(body))

    report = reg.check_fleet(root)
    assert fields(report, reg.DIVERGENT) == {"declarations[CP-D2-ABOVE].indicts"}


def test_the_field_that_actually_drifted_is_named_to_the_repo_entry(tmp_path):
    """FIRES. A repo zeroing its OWN entry — E-080's mechanism, exactly."""
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["source_files_quoting_the_replaced_sentence"] = {
        **BODY["source_files_quoting_the_replaced_sentence"],
        "resilient-fray": ["src/registry/promotion_gate.py"],
    }
    recommit(root / "resilient-fray", sealed(body))

    report = reg.check_fleet(root)
    assert fields(report, reg.DIVERGENT) == {
        "source_files_quoting_the_replaced_sentence.resilient-fray"
    }


# ---------------------------------------------------------------------------
# Refusals: the states where a verdict would be worse than none
# ---------------------------------------------------------------------------
def test_one_copy_refuses_rather_than_reporting_no_divergence(tmp_path):
    """A fleet check over one copy is not a fleet check.

    The tempting failure is "1 copy, 0 divergences, PASS", which would be the
    strongest possible version of the defect this exists to catch.
    """
    root = tmp_path / "lonely"
    root.mkdir()
    make_repo(root / "resilient-fray", sealed(BODY))

    report = reg.check_fleet(root)
    assert not report.ok
    assert report.refusal is not None
    assert "fewer than two copies" in report.refusal
    assert report.problems == ()


def test_no_copies_refuses_too(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    report = reg.check_fleet(root)
    assert report.refusal is not None


def test_a_repo_with_no_digest_function_is_refused_not_skipped(tmp_path):
    """A copy that carries no definition of the digest cannot be compared.

    Skipping it would let a repo drop its verifier and drop out of the check.
    """
    root = make_fleet(tmp_path)
    make_repo(
        root / "resilient-extra",
        sealed(BODY),
        verifier="def something_else():\n    return 1\n",
    )
    with pytest.raises(reg.RegisterUnreadable) as exc:
        reg.check_fleet(root)
    assert "canonical_body_sha256" in str(exc.value)


def test_implementations_that_disagree_are_reported_against_the_instrument(tmp_path):
    """One repo's own digest function returns something else.

    That is not a finding about the DOCUMENT — it means the fleet has two
    definitions of the digest, and no digest verdict is worth reading until a
    person settles which one it is. Reported as its own kind, and reported on
    every copy, because every copy's digest is now ambiguous.
    """
    root = make_fleet(tmp_path)
    (root / "resilient-torrent" / reg.VERIFIER_RELPATH).write_text(
        "def canonical_body_sha256(doc):\n    return 'f' * 64\n", encoding="utf-8"
    )
    subprocess.run(
        ["git", "-C", str(root / "resilient-torrent"), "add", "-A"],
        check=True, capture_output=True,
    )
    subprocess.run(
        [
            "git", "-C", str(root / "resilient-torrent"),
            "-c", "user.name=fixture", "-c", "user.email=f@x.invalid",
            "commit", "--quiet", "-m", "a second definition of the digest",
        ],
        check=True, capture_output=True,
    )

    report = reg.check_fleet(root)
    assert reg.IMPLEMENTATIONS_DISAGREE in kinds(report)
    assert {p.repo for p in report.problems if p.kind == reg.IMPLEMENTATIONS_DISAGREE} == {
        "resilient-fray", "resilient-chokepoint", "resilient-torrent"
    }
    assert reg.SELF_INCONSISTENT not in kinds(report), (
        "a digest verdict taken with an ambiguous definition is not a verdict; "
        "the instrument problem is reported INSTEAD of one, not alongside it"
    )


def test_the_working_tree_is_not_read(tmp_path):
    """The invariant is about the document three repos LAND, not three edits.

    A dirty working tree must not make this fire, and must not make it pass
    either: the answer comes from `HEAD` in both directions.
    """
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["title"] = "an uncommitted edit"
    (root / "resilient-fray" / reg.REGISTER_RELPATH).write_text(
        json.dumps(sealed(body), indent=1) + "\n", encoding="utf-8"
    )
    report = reg.check_fleet(root)
    assert report.ok, "an uncommitted edit moved a verdict; this reads HEAD"

    recommit(root / "resilient-fray", sealed(body))
    assert not reg.check_fleet(root).ok, (
        "committing the SAME edit must fire; otherwise the test above passes "
        "because nothing can fire at all"
    )


def test_a_non_git_directory_is_refused_by_name(tmp_path):
    root = tmp_path / "fleet"
    root.mkdir()
    for name in REPOS[:2]:
        make_repo(root / name, sealed(BODY))
    loose = root / "resilient-loose"
    (loose / "docs").mkdir(parents=True)
    (loose / reg.REGISTER_RELPATH).write_text(json.dumps(sealed(BODY)), encoding="utf-8")
    with pytest.raises(reg.RegisterUnreadable) as exc:
        reg.check_fleet(root)
    assert "resilient-loose" in str(exc.value)


# ---------------------------------------------------------------------------
# Through the command line, which is what anyone actually runs
# ---------------------------------------------------------------------------
def test_the_cli_exit_codes_separate_disagreement_from_measuring_nothing(tmp_path):
    root = make_fleet(tmp_path)
    assert cli.main(["register", "--check-fleet", "--root", str(root)]) == 0

    body = dict(BODY)
    body["title"] = "drifted"
    recommit(root / "resilient-chokepoint", sealed(body))
    assert cli.main(["register", "--check-fleet", "--root", str(root)]) == 1

    lonely = tmp_path / "lonely"
    lonely.mkdir()
    make_repo(lonely / "resilient-fray", sealed(BODY))
    assert (
        cli.main(["register", "--check-fleet", "--root", str(lonely)])
        == cli.REGISTER_REFUSED_EXIT
    )


def test_the_cli_requires_the_mode_to_be_named(tmp_path):
    """One mode, named rather than defaulted, so a second cannot inherit callers."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["register", "--root", str(tmp_path)])
    assert exc.value.code != 0


def test_the_cli_json_payload_names_the_field_and_who_holds_what(tmp_path, capsys):
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["title"] = "drifted"
    recommit(root / "resilient-chokepoint", sealed(body))

    cli.main(["register", "--check-fleet", "--root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["identical_blob"] is None
    assert [p["field"] for p in payload["problems"]] == ["title"]
    assert payload["copies"][0]["computed_by"], (
        "each copy must record what EVERY repo's function computed over it; that "
        "cross-application is what makes 'one answer' a measurement"
    )


# ---------------------------------------------------------------------------
# E-M39: the committable artifact, and the consumer-side pin
# ---------------------------------------------------------------------------
# `--check-fleet` answered E-080 with a command somebody must remember to run.
# E-M39 named that as the residual: an obligation is weaker than a check. The
# closure that is an agent's to build is not CI (rule 12/13) but a PIN: the run
# writes a sealed artifact, the consumer commits it beside the register, and a
# test in the consumer asserts `verify_artifact(...) == []`. Then a register
# edit with no fresh run is a red test in the repo that made the edit -- the
# blob at HEAD is not among the blobs the artifact compared.
#
# Every pair below holds one variable: the register at HEAD, the artifact's
# body, or the run's verdict.

from resilient_mlkit.core import artifact as artifact_mod


def _write(root: Path, out: Path) -> tuple[int, dict]:
    """``(exit code, the artifact as written)``. The document is returned as
    the file holds it -- a helper that tucked the exit code INTO the dict broke
    the seal it was about to test, which is the seal working."""
    rc = cli.main(["register", "--check-fleet", "--root", str(root), "--out", str(out)])
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_the_artifact_is_sealed_carries_no_machine_path_and_verifies_in_every_repo(tmp_path):
    """SILENT: three copies of one document, the artifact written by the run."""
    root = make_fleet(tmp_path)
    out = tmp_path / "artifact.json"
    rc, doc = _write(root, out)
    assert rc == 0
    assert doc["artifact_schema"] == reg.ARTIFACT_SCHEMA
    assert doc["verdict"] == "PASS" and doc["ok"] is True
    assert doc[reg.PROOF_FIELD] == reg.proof_sha256(doc)
    assert len(doc["copies"]) == 3 and doc["identical_blob"]
    assert "root" not in doc and all("path" not in c for c in doc["copies"])
    assert artifact_mod.machine_paths(doc) == [], "a committed file may carry no machine path"
    assert doc["mlkit"]["version"] == cli.__version__
    for name in REPOS:
        assert reg.verify_artifact(doc, root / name) == []
        assert reg.verify_artifact(out, root / name) == []


def test_a_register_edit_committed_without_a_fresh_run_fails_the_pin_in_that_repo(tmp_path):
    """FIRES. The hook E-M39 asked for, on the shape that matters: an edit that
    is internally consistent (digest re-derived), so the repo's own scanner is
    green -- and the pin is red, because HEAD's blob was never compared."""
    root = make_fleet(tmp_path)
    out = tmp_path / "artifact.json"
    _, doc = _write(root, out)
    body = dict(BODY)
    body["title"] = "edited after the fleet check"
    recommit(root / "resilient-fray", sealed(body))

    problems = reg.verify_artifact(doc, root / "resilient-fray")
    assert len(problems) == 1, problems
    assert "at HEAD is blob" in problems[0] and "never compared" in problems[0]
    assert reg.ARTIFACT_RELPATH in problems[0], "the message says how to close the loop"
    # The two repos that did not move still verify: the pin names the mover.
    assert reg.verify_artifact(doc, root / "resilient-chokepoint") == []
    assert reg.verify_artifact(doc, root / "resilient-torrent") == []


def test_the_loop_closes_a_fresh_run_after_the_edit_verifies_again(tmp_path):
    """SILENT again, and the register is now edited in all three (one document)."""
    root = make_fleet(tmp_path)
    out = tmp_path / "artifact.json"
    body = dict(BODY)
    body["title"] = "the edit, landed in three repositories"
    for name in REPOS:
        recommit(root / name, sealed(body))
    rc, doc = _write(root, out)
    assert rc == 0
    for name in REPOS:
        assert reg.verify_artifact(doc, root / name) == []


def test_an_uncommitted_register_edit_does_not_move_the_pin_the_same_edit_committed_does(tmp_path):
    """The pin reads HEAD like the check it pins. A pair, not an assertion."""
    root = make_fleet(tmp_path)
    _, doc = _write(root, tmp_path / "artifact.json")
    body = dict(BODY)
    body["title"] = "working-tree only"
    repo = root / "resilient-torrent"
    (repo / reg.REGISTER_RELPATH).write_text(json.dumps(sealed(body), indent=1) + "\n")
    assert reg.verify_artifact(doc, repo) == []
    recommit(repo, sealed(body))
    assert reg.verify_artifact(doc, repo) != []


def test_an_artifact_edited_by_hand_to_read_pass_fails_on_its_seal(tmp_path):
    """FIRES. The seal is what stops a FAIL artifact being retyped as a PASS."""
    root = make_fleet(tmp_path)
    body = dict(BODY)
    body["title"] = "drifted"
    recommit(root / "resilient-chokepoint", sealed(body))
    out = tmp_path / "artifact.json"
    rc, doc = _write(root, out)
    assert rc == 1 and doc["verdict"] == "FAIL"

    forged = dict(doc)
    forged["verdict"], forged["ok"], forged["problems"] = "PASS", True, []
    problems = reg.verify_artifact(forged, root / "resilient-fray")
    assert any(reg.PROOF_FIELD in p and "edited" in p for p in problems), problems
    # And the honest FAIL artifact is refused on its verdict, seal intact.
    honest = reg.verify_artifact(doc, root / "resilient-fray")
    assert any("verdict is 'FAIL'" in p for p in honest), honest
    assert not any(reg.PROOF_FIELD in p for p in honest)


def test_a_refused_run_writes_an_artifact_that_verifies_nothing_and_names_no_path(tmp_path):
    """A run over one copy is written down as REFUSED -- and carries no --root path,
    because the refusal sentence lands in a committed file."""
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    make_repo(lonely / "resilient-fray", sealed(BODY))
    out = tmp_path / "artifact.json"
    rc, doc = _write(lonely, out)
    assert rc == cli.REGISTER_REFUSED_EXIT
    assert doc["verdict"] == "REFUSED" and doc["copies"] == []
    assert str(lonely) not in json.dumps(doc)
    assert artifact_mod.machine_paths(doc) == []
    problems = reg.verify_artifact(doc, lonely / "resilient-fray")
    assert any("REFUSED" in p for p in problems)
    assert any("fewer than two" in p for p in problems)


def test_a_document_that_is_not_a_fleet_check_artifact_is_named_as_such(tmp_path):
    root = make_fleet(tmp_path)
    problems = reg.verify_artifact({"artifact_schema": "something/else"}, root / "resilient-fray")
    assert problems and "not a fleet-check artifact" in problems[0]
    missing = reg.verify_artifact(tmp_path / "absent.json", root / "resilient-fray")
    assert problems and len(missing) == 1


def test_the_verify_cli_exit_codes_and_the_repo_flag(tmp_path, capsys):
    root = make_fleet(tmp_path)
    out = tmp_path / "artifact.json"
    _write(root, out)
    capsys.readouterr()
    assert cli.main([
        "register", "--verify-artifact", str(out), "--repo", str(root / "resilient-fray"),
    ]) == 0
    assert "licenses" in capsys.readouterr().out

    body = dict(BODY)
    body["title"] = "edited"
    recommit(root / "resilient-fray", sealed(body))
    assert cli.main([
        "register", "--verify-artifact", str(out), "--repo", str(root / "resilient-fray"), "--json",
    ]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["problems"]) == 1 and "never compared" in payload["problems"][0]

    assert cli.main([
        "register", "--verify-artifact", str(tmp_path / "absent.json"), "--repo", str(root),
    ]) == cli.REGISTER_REFUSED_EXIT
    with pytest.raises(SystemExit):
        cli.main(["register", "--check-fleet", "--root", str(root), "--verify-artifact", str(out)])


def test_the_written_artifact_agrees_with_the_json_report_on_every_shared_field(tmp_path, capsys):
    """The artifact is the report in committable clothes, not a second opinion."""
    root = make_fleet(tmp_path)
    out = tmp_path / "artifact.json"
    _, doc = _write(root, out)
    capsys.readouterr()
    cli.main(["register", "--check-fleet", "--root", str(root), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert doc["identical_blob"] == report["identical_blob"]
    assert doc["ok"] == report["ok"]
    assert [c["blob"] for c in doc["copies"]] == [c["blob"] for c in report["copies"]]
    assert [c["agreed_digest"] for c in doc["copies"]] == [c["agreed_digest"] for c in report["copies"]]
