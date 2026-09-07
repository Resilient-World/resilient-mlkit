"""E-M44 — R9 evaluates and reports BOTH the legs it owns.

THE DEFECT. `r9_licence_gate` checks two licence conditions: that no source in
the manifest is unlisted, BLOCKED or EVAL-ONLY, and that every attribution
obligation in the signed allowlist is rendered into `NOTICE.md`. It `return`ed
on the first, so the second was unreachable on any repo that had a manifest
finding.

That is not a hypothetical. Measured across the eight adopter mains on
2026-09-07 with mlkit's own `policy.render_notice`: **five of eight NOTICE.md
files were stale and four were missing attribution sections outright** —
torrent 38 sections on disk against 48 obligations, surge 24 against 36, triage
11 against 21, blackout 6 against 11 — and torrent, surge and blackout all fail
R9 earlier, so their gaps were invisible. Only triage's R9 got far enough to
report it. These are unmet licence conditions, not formatting.

WHAT THE REPAIR MAY NOT DO, and what these tests hold it to:

* **Not weaken either leg.** Every input that failed R9 before still fails it.
  `N2` and `N7` assert the reason is BYTE-IDENTICAL to the pre-E-M44 check's on
  a repo whose NOTICE is current — a check that grew a new way to fail has to
  be shown not failing everything else it touches.
* **Not turn the NOTICE leg into a warning.** mlkit has no WARN status, on
  purpose, and this must not be the reason one gets invented. `N3` is
  NOTICE-only and it FAILS.
* **Name the obligations.** "NOTICE.md is stale" tells a repo nothing it can
  act on. The finding names the missing source ids so the repair is mechanical.

The arms in `reports/E_M44_R9_BOTH_LEGS_ARMS.json` are driven in SUBPROCESSES
by `scripts/e_m44_r9_both_legs_drive.py` — subprocesses because `N9` needs
`checks/readiness.py` and `core/policy.py` from `origin/main`, and because each
arm can then assert `resilient_mlkit.__file__` inside the tree it names.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import r9_licence_gate
from resilient_mlkit.core import policy
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import MAX_REASON, Status

ROOT = Path(__file__).resolve().parent.parent
ARMS = ROOT / "reports" / "E_M44_R9_BOTH_LEGS_ARMS.json"
DRIVE_SCRIPT = ROOT / "scripts" / "e_m44_r9_both_legs_drive.py"


def _drive_module():
    """The drive script, imported for its fixture builder.

    One definition of the fixture, shared by the committed arms and by the
    in-process tests below. Two builders would be two different ideas of what
    "a repo with a stale NOTICE" is, and the arms would stop being about the
    same thing these tests are.
    """
    spec = importlib.util.spec_from_file_location("_e_m44_drive", DRIVE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arms() -> dict[str, dict]:
    return {a["arm"]: a for a in json.loads(ARMS.read_text())["arms"]}


def _ctx(root: Path) -> RunContext:
    return RunContext(nonce="TEST000000", root=root, offline=True)


# -- the committed control record --------------------------------------------


def test_the_arms_cover_the_preregistered_set():
    assert set(_arms()) == {
        "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8",
        "N9-N1", "N9-N2", "N9-N5", "N9-N6", "N9-N7",
    }


@pytest.mark.parametrize(
    "arm,status",
    [("N1", "FAIL"), ("N2", "FAIL"), ("N3", "FAIL"), ("N4", "PASS"),
     ("N5", "FAIL"), ("N6", "FAIL"), ("N7", "NA"), ("N8", "FAIL")],
)
def test_each_driven_arm_reached_the_preregistered_status(arm, status):
    assert _arms()[arm]["status"] == status


def test_the_not_dead_arms_show_the_notice_gap_hidden_again():
    """N9. With `readiness.py` and `policy.py` at `origin/main`, the NOTICE leg
    is unreachable on exactly the repos this lane exists for.

    Without this the whole repair could be a fixture that always fails: three
    arms whose NOTICE gap the OLD check cannot see, driven on purpose.
    """
    arms = _arms()
    for arm in ("N9-N1", "N9-N5"):
        assert arms[arm]["status"] == "FAIL"
        assert arms[arm]["mentions_notice"] is False, (
            f"{arm} was supposed to hide the NOTICE gap and did not; the "
            "NOT-DEAD tree is not the pre-E-M44 check"
        )
    # The starkest of the three: a real, measured, undischarged attribution
    # obligation reported as "could not measure".
    assert arms["N9-N6"]["status"] == "NA"
    assert arms["N9-N6"]["mentions_notice"] is False
    assert arms["N6"]["status"] == "FAIL"


def test_the_manifest_only_arms_are_byte_identical_across_the_repair():
    """N2 and N7. Nothing moves for a repo whose NOTICE is current.

    This is the claim that separates a repair from a widening, and byte-
    identical is the only version of it worth making.
    """
    arms = _arms()
    assert arms["N2"]["reason"] == arms["N9-N2"]["reason"]
    assert arms["N7"]["reason"] == arms["N9-N7"]["reason"]


# -- in process --------------------------------------------------------------


@pytest.fixture(scope="module")
def build():
    return _drive_module()


def _repo(build, tmp_path: Path, **kw) -> Repo:
    return Repo(name="fixturerepo", path=build.build_repo(tmp_path, **kw))


def test_both_defects_are_reported_in_one_reason(build, tmp_path):
    """FIRES on both legs: the shape arabica, surge, torrent and blackout are in."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("blocked-panel", "BLOCKED")],
        sources=["blocked-panel"],
        notice=build.STALE_NOTICE,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "BLOCKED source(s) in the manifest: blocked-panel" in result.reason
    assert "missing attribution section(s)" in result.reason
    assert "blocked-panel" in result.reason
    assert result.evidence["notice_missing_attribution"] == ["blocked-panel"]
    assert result.evidence["manifest_leg"] == "evaluated"


def test_a_notice_gap_alone_FAILS_and_does_not_become_a_warning(build, tmp_path):
    """FIRES: N3. An undischarged attribution obligation is a licence failure.

    mlkit has no WARN and no SKIP, deliberately (`core.result.Status`), and a
    check that quietly downgraded one of its two obligations would be inventing
    one.
    """
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")],
        sources=["sentinel2-l2a"],
        notice=build.STALE_NOTICE,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert result.evidence["notice_missing_attribution"] == ["sentinel2-l2a"]


def test_a_clean_repo_reports_nothing_and_still_passes(build, tmp_path):
    """The preserved case. A gate that only ever fails is not a gate."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=["sentinel2-l2a"],
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["notice_current"] is True
    assert result.evidence["allowlist_signed"] is True


def test_a_manifest_only_failure_keeps_its_reason_exactly(build, tmp_path):
    """N2 in process: the string a repo already reads must not move under it."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("blocked-panel", "BLOCKED")], sources=["blocked-panel"],
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.reason == "BLOCKED source(s) in the manifest: blocked-panel"


def test_the_notice_leg_runs_past_a_structurally_invalid_allowlist(build, tmp_path):
    """N5, and the repo it exists for.

    `resilient-surge`'s R9 fails at `defective_entries` — two entries declare
    `kind: code` — and its twelve missing attribution sections were behind that
    return. Whether NOTICE.md matches the allowlist on disk is answerable
    without trusting the determinations; whether a source is wrongly licensed
    is not, which is why the MANIFEST leg still does not run here.
    """
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("code-not-data", kind="code")],
        sources=["code-not-data"],
        notice=build.STALE_NOTICE,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "structurally invalid" in result.reason
    assert "missing attribution section(s)" in result.reason
    assert result.evidence["manifest_leg"].startswith("not evaluated")


def test_an_unmeasurable_manifest_leg_does_not_erase_a_measured_notice_failure(
    build, tmp_path
):
    """N6. The clause that moves torrent, triage and blackout in this environment.

    `notice_gap` needs no binding, no import of the repo's code and no data, so
    "this interpreter cannot import pandas" does not make an undischarged
    attribution obligation unknowable. Reporting NA here would throw away the
    half that WAS measured — the collapse `core.result.Status` exists to refuse.
    """
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=["sentinel2-l2a"],
        notice=build.STALE_NOTICE,
        binding="no_module_by_this_name_for_the_arm:manifest",
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "the manifest leg was NOT measured" in result.reason
    assert "ModuleNotFoundError" in result.reason
    assert "missing attribution section(s)" in result.reason


def test_an_unmeasurable_manifest_leg_with_a_current_notice_is_still_NA(build, tmp_path):
    """N7. The other direction: nothing measured, nothing asserted."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=["sentinel2-l2a"],
        binding="no_module_by_this_name_for_the_arm:manifest",
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "ModuleNotFoundError" in result.reason
    assert "NOTICE" not in result.reason


def test_an_absent_notice_names_the_obligations_it_should_have_carried(build, tmp_path):
    """N8. "Never generated" and "generated and drifted" stay different states."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=["sentinel2-l2a"], notice=None,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert result.reason.startswith("NOTICE.md is absent")
    assert "sentinel2-l2a" in result.reason


def test_an_empty_manifest_with_a_current_notice_is_still_NA(build, tmp_path):
    """Declaring no data is the one way to make a licence gate meaningless, and
    it is still explicitly not a pass — and still not a FAIL either."""
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=[], notice="generated",
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "measures nothing" in result.reason


# -- the finding text itself -------------------------------------------------


def test_the_notice_clause_comes_first_so_truncation_cannot_hide_it_again(
    build, tmp_path
):
    """The newly-visible half must survive `MAX_REASON`.

    Putting it last would be the same defect a second time: invisible by
    truncation instead of by `return`. Driven with a manifest finding long
    enough to consume the whole field on its own.
    """
    many = [build._entry(f"blocked-source-{i:03d}", "BLOCKED") for i in range(40)]
    repo = _repo(
        build, tmp_path,
        entries=many, sources=[e["id"] for e in many], notice=build.STALE_NOTICE,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert len(result.reason) <= MAX_REASON
    assert result.reason.startswith("NOTICE.md is stale")
    assert "missing attribution section(s) for 40 source(s)" in result.reason
    # And the whole list is still available where nothing truncates it.
    assert len(result.evidence["notice_missing_attribution"]) == 40


def test_the_reason_names_at_most_six_ids_and_says_how_many_more(build, tmp_path):
    """A markdown table cell is not a list. Six, then a count, then the evidence."""
    many = [build._entry(f"unattributed-{i:02d}") for i in range(10)]
    repo = _repo(
        build, tmp_path,
        entries=many, sources=[e["id"] for e in many], notice=build.STALE_NOTICE,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert "(and 4 more)" in result.reason
    assert result.reason.count("unattributed-") == policy.NOTICE_IDS_IN_REASON


def test_a_notice_section_with_no_obligation_is_reported_too(build, tmp_path):
    """The mirror of a missing section: an attribution nothing licenses.

    A NOTICE.md that credits a source the allowlist does not carry is a claim
    about a licence relationship the signatory has not recorded.
    """
    repo = _repo(
        build, tmp_path,
        entries=[build._entry("sentinel2-l2a")], sources=["sentinel2-l2a"],
        notice="# NOTICE\n\n## sentinel2-l2a\n\n## a-source-nobody-signed\n",
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "with no allowlist obligation: a-source-nobody-signed" in result.reason
    assert result.evidence["notice_extra_attribution"] == ["a-source-nobody-signed"]


def test_the_notice_leg_is_skipped_when_the_document_did_not_parse(tmp_path):
    """A gap computed from zero entries is an artefact of the parse failure.

    `parse_error` covers two different things — a document that could not be
    read, and one that read fine but whose signature does not hold up — and
    only the second leaves entries to render from. Reporting "every obligation
    is missing" because the YAML is broken would be a finding about the parser.
    """
    root = tmp_path / "resilient-fixturerepo"
    (root / "docs").mkdir(parents=True)
    (root / policy.ALLOWLIST_RELPATH).write_text("entries: [unclosed\n")
    (root / policy.NOTICE_RELPATH).write_text("# NOTICE\n")
    repo = Repo(name="fixturerepo", path=root)
    allowlist = policy.load(repo)
    assert allowlist.document_parsed is False
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "malformed YAML" in result.reason
    assert "NOTICE" not in result.reason
