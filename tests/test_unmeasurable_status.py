"""M-1 controls: an armed check whose declared input this machine cannot supply.

The defect, measured in the adopters on 2026-09-04 (plan v3 §7 M-1): torrent's
D2 on ``main`` renders FAIL with the reason "ENVIRONMENT REFUSAL, NOT A PLACEBO
FINDING: the staged Caravan subset could not be read", because a binding that
raised had no other channel. chokepoint's R2/R3/R5/R6 refuse on pin mismatch
from any clone without the parquet. Each is fail-closed and correct, and each
renders as if the repo were indicted (FAIL) or as if the stop were unarmed (NA
is also what "no binding declared" renders as).

Every control here is one of the rows fixed in
``reports/M1_UNMEASURABLE_PREREGISTRATION.md`` BEFORE the code was written,
and each is driven in both directions: the status must appear where the input
is absent AFTER the declaration resolved, and must NOT appear where the input
is present (byte-identical PASS), where the defect is the repo's own (FAIL,
unchanged), or where the refusal is raised before anything was resolved
(FAIL, by name). C8 removes the runner clause and shows the status vanish, so
the clause is proved to be what produces it rather than assumed.

Fixtures resolve through ``Repo.resolve`` and run through ``cli._run_phase``,
which is the path the eight real repos take.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import pytest

from resilient_mlkit import cli
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import d2_placebo_test
from resilient_mlkit.checks.economics import e1_scaling_probe
from resilient_mlkit.core import environment, report
from resilient_mlkit.core.arming import arm_state
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import (
    INPUT_KEY,
    PIN_EXPECTED_KEY,
    PIN_OBSERVED_KEY,
    UNMEASURABLE_KEY,
    CheckResult,
    FabricationError,
    GateAggregate,
    InputUnavailable,
    PrematureInputRefusal,
    Status,
)
from resilient_mlkit.portfolio import BLOCKED, IN_PROGRESS, READY, resolve

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))

PIN = "aa11bb22"

#: A payload D2 PASSES on under the default two-sided region: interval
#: contains zero, half-width 0.11 < reference effect 1.0.
PASSING_PLACEBO = '{"estimate": 0.01, "ci_low": -0.1, "ci_high": 0.12, "reference_effect": 1.0}'

#: A curve E1 PASSES on: +50% from 10% to 25%.
PASSING_CURVE = "{0.01: 0.2, 0.10: 0.4, 0.25: 0.6}"


def _pinned_binding(fn_name: str, payload: str) -> str:
    """A binding shaped like torrent's: resolve the declaration, read the pin,
    then stop at the byte it cannot read. ``InputUnavailable`` is raised INSIDE
    the function body, after import, which is the only admissible place."""
    return f"""
        import pathlib
        from resilient_mlkit import InputUnavailable

        PIN = "{PIN}"

        def {fn_name}():
            panel = pathlib.Path(__file__).with_name("panel.bin")
            if not panel.exists():
                raise InputUnavailable(
                    "the staged panel could not be read",
                    input="panel.bin", pin_expected=PIN, pin_observed="",
                )
            observed = panel.read_text().strip()
            if observed != PIN:
                raise InputUnavailable(
                    "the staged panel does not match the pin",
                    input="panel.bin", pin_expected=PIN, pin_observed=observed,
                )
            return {payload}
    """


def _repo(tmp_path: Path, binding: str, fn_name: str, body: str, *, name: str = "fixturerepo") -> Repo:
    module = f"m1_bindings_{next(_SERIAL)}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mlkit" / "repo.toml").write_text(
        f'[repo]\nname = "{name}"\n\n[bindings]\n{binding} = "{module}:{fn_name}"\n'
    )
    return Repo(name=name, path=tmp_path)


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _run(repo: Repo, phase: str, check_id: str) -> CheckResult:
    """Through the runner, which is where the status is produced."""
    try:
        results = cli._run_phase(repo, phase, _ctx(repo.path))
    finally:
        repo.release()
    by_id = {r.check_id: r for r in results}
    return by_id[check_id]


# ---------------------------------------------------------------------------
# C1 / C2 -- D2: FIRES where the input is absent, SILENT (byte-identical) where present
# ---------------------------------------------------------------------------


def test_c1_d2_renders_unmeasurable_naming_the_pin_when_the_input_is_absent(tmp_path):
    repo = _repo(tmp_path, "placebo_test", "placebo_test", _pinned_binding("placebo_test", PASSING_PLACEBO))
    r = _run(repo, "decision", "D2")
    assert r.status is Status.UNMEASURABLE, r.reason
    assert "UNMEASURABLE HERE, NOT A FINDING" in r.reason
    assert "panel.bin" in r.reason and PIN in r.reason
    assert r.evidence[UNMEASURABLE_KEY] is True
    assert r.evidence[INPUT_KEY] == "panel.bin"
    assert r.evidence[PIN_EXPECTED_KEY] == PIN
    assert r.evidence[PIN_OBSERVED_KEY] == ""
    # Nothing is indicted: the key portfolio.resolve turns into BLOCKED is absent.
    assert "halt" not in r.evidence
    assert "NOT A PLACEBO FINDING" not in r.reason  # the adopter no longer has to say it


def test_c1_d2_renders_unmeasurable_with_both_digests_on_a_pin_mismatch(tmp_path):
    repo = _repo(tmp_path, "placebo_test", "placebo_test", _pinned_binding("placebo_test", PASSING_PLACEBO))
    (tmp_path / "panel.bin").write_text("deadbeef\n")
    r = _run(repo, "decision", "D2")
    assert r.status is Status.UNMEASURABLE
    assert r.evidence[PIN_EXPECTED_KEY] == PIN
    assert r.evidence[PIN_OBSERVED_KEY] == "deadbeef"
    assert PIN in r.reason and "deadbeef" in r.reason
    assert "halt" not in r.evidence


def test_c2_d2_passes_byte_identically_when_the_input_is_present(tmp_path):
    """SILENT. The same binding with the bytes present is a PASS whose verdict
    fields equal a PASS taken from a binding that never had a pin path at all --
    the InputUnavailable path adds nothing to a measured verdict."""
    pinned = _repo(tmp_path / "a", "placebo_test", "placebo_test", _pinned_binding("placebo_test", PASSING_PLACEBO))
    (tmp_path / "a" / "panel.bin").write_text(f"{PIN}\n")
    with_pin = _run(pinned, "decision", "D2")

    plain = _repo(tmp_path / "b", "placebo_test", "placebo_test", f"""
        def placebo_test():
            return {PASSING_PLACEBO}
    """)
    without_pin = _run(plain, "decision", "D2")

    assert with_pin.status is Status.PASS, with_pin.reason
    assert without_pin.status is Status.PASS, without_pin.reason
    a, b = with_pin.to_dict(), without_pin.to_dict()
    for key in ("check_id", "phase", "status", "reason", "evidence"):
        assert a[key] == b[key], key
    assert UNMEASURABLE_KEY not in a["evidence"]


# ---------------------------------------------------------------------------
# C3 / C4 -- the other direction: a repo defect is still FAIL; a premature refusal is FAIL by name
# ---------------------------------------------------------------------------


def test_c3_a_repo_local_import_error_at_call_time_is_still_a_fail(tmp_path):
    """The suppression-in-the-other-direction trap environment.py documents:
    the binding's lazy import of ITS OWN missing module is the repo's defect."""
    repo = _repo(tmp_path, "placebo_test", "placebo_test", """
        def placebo_test():
            from this_repos_own_missing_module import load  # noqa: F401
            return {}
    """)
    (tmp_path / "src").mkdir()
    r = _run(repo, "decision", "D2")
    assert r.status is Status.FAIL
    assert "ModuleNotFoundError" in r.reason
    assert r.status is not Status.UNMEASURABLE


def test_c4_an_input_unavailable_raised_at_import_time_is_refused_by_name(tmp_path):
    """A module that refuses before it has resolved anything has dodged the
    check. It renders FAIL naming PREMATURE_INPUT_REFUSAL -- never UNMEASURABLE,
    and never NA (which is what a BindingError would have rendered)."""
    repo = _repo(tmp_path, "placebo_test", "placebo_test", """
        from resilient_mlkit import InputUnavailable
        raise InputUnavailable("panel absent", input="panel.bin", pin_expected="x")

        def placebo_test():
            return {}
    """)
    with pytest.raises(PrematureInputRefusal):
        try:
            d2_placebo_test(repo, _ctx(tmp_path))
        finally:
            repo.release()
    r = _run(repo, "decision", "D2")
    assert r.status is Status.FAIL
    assert "PREMATURE_INPUT_REFUSAL" in r.reason
    assert r.status is not Status.UNMEASURABLE and r.status is not Status.NA


def test_c4_the_import_probe_reads_a_premature_refusal_as_a_repo_defect(tmp_path):
    repo = _repo(tmp_path, "placebo_test", "placebo_test", """
        from resilient_mlkit import InputUnavailable
        raise InputUnavailable("panel absent", input="panel.bin")
    """)
    try:
        probe = environment.probe(repo)
    finally:
        repo.release()
    assert probe.verdict != environment.UNMEASURABLE
    assert probe.bindings["placebo_test"].startswith("repo-defect:")


# ---------------------------------------------------------------------------
# C5 -- E1: the same pair
# ---------------------------------------------------------------------------


def test_c5_e1_renders_unmeasurable_when_the_input_is_absent_and_passes_when_present(tmp_path):
    absent = _repo(tmp_path / "a", "scaling_probe", "scaling_probe", _pinned_binding("scaling_probe", PASSING_CURVE))
    r_absent = _run(absent, "economics", "E1")
    assert r_absent.status is Status.UNMEASURABLE, r_absent.reason
    assert r_absent.evidence[PIN_EXPECTED_KEY] == PIN and "halt" not in r_absent.evidence

    present = _repo(tmp_path / "b", "scaling_probe", "scaling_probe", _pinned_binding("scaling_probe", PASSING_CURVE))
    (tmp_path / "b" / "panel.bin").write_text(f"{PIN}\n")
    r_present = _run(present, "economics", "E1")
    assert r_present.status is Status.PASS, r_present.reason
    assert r_present.evidence["gain_top_two"] == pytest.approx(0.5)


def test_c5_e1_direct_call_lets_input_unavailable_propagate_to_the_runner(tmp_path):
    """The check re-raises rather than catching it as 'scaling_probe raised'."""
    repo = _repo(tmp_path, "scaling_probe", "scaling_probe", _pinned_binding("scaling_probe", PASSING_CURVE))
    with pytest.raises(InputUnavailable):
        try:
            e1_scaling_probe(repo, _ctx(tmp_path))
        finally:
            repo.release()


# ---------------------------------------------------------------------------
# C6 / C7 -- the environment probe and the report writer
# ---------------------------------------------------------------------------


def _unmeasurable_result(check_id: str = "D2") -> CheckResult:
    return CheckResult.unmeasurable(
        check_id, "decision",
        InputUnavailable("staged panel absent", input="data/panel.parquet",
                         pin_expected=PIN, pin_observed=""),
    )


def test_c6_an_unmeasurable_result_makes_the_run_unmeasurable_and_names_the_pin(tmp_path):
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text('[repo]\nname = "fixture"\n')
    repo = Repo("fixture", tmp_path)
    probe = environment.from_results(repo, {"D2": _unmeasurable_result()})
    assert probe.verdict == environment.UNMEASURABLE
    assert probe.measurable is False
    assert "D2 (input)" in probe.bindings
    assert PIN in probe.bindings["D2 (input)"]
    assert "data/panel.parquet" in probe.bindings["D2 (input)"]
    assert probe.missing_modules == ()


def test_c6_guarded_write_refuses_and_preserves_the_prior_report_byte_for_byte(tmp_path):
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text('[repo]\nname = "fixture"\n')
    repo = Repo("fixture", tmp_path)
    out = tmp_path / "reports" / "hard_stops.md"
    out.parent.mkdir()
    out.write_text("# hard stops\n\n| D2 | PASS | measured on the machine with the bytes |\n")
    before = hashlib.sha256(out.read_bytes()).hexdigest()

    probe = environment.from_results(repo, {"D2": _unmeasurable_result()})
    written = report.guarded_write(
        out, "# hard stops\n\n| D2 | UNMEASURABLE | absent here |\n",
        probe=probe, depends_on_bindings=True, nonce="n", git_sha="s",
    )
    assert written.written is False and written.preserved is True
    assert hashlib.sha256(out.read_bytes()).hexdigest() == before
    assert written.refusal_path is not None and written.refusal_path.exists()
    refusal = written.refusal_path.read_text()
    assert PIN in refusal and "data/panel.parquet" in refusal


def test_c7_a_repo_local_missing_module_does_not_make_the_run_unmeasurable(tmp_path):
    """SILENT. A FAIL whose reason names the repo's own missing module stays a
    repo defect; the probe does not swallow it."""
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text('[repo]\nname = "fixture"\n')
    (tmp_path / "src" / "ownpkg").mkdir(parents=True)
    repo = Repo("fixture", tmp_path)
    fail = CheckResult.failed("D2", "decision", "placebo_test raised ModuleNotFoundError: No module named 'ownpkg.loader'")
    probe = environment.from_results(repo, {"D2": fail})
    assert probe.verdict != environment.UNMEASURABLE
    assert probe.measurable is True
    assert "D2" in probe.repo_defects


# ---------------------------------------------------------------------------
# C8 -- check-not-dead: without the runner clause, the fixture is a crash
# ---------------------------------------------------------------------------


def test_c8_removing_the_runner_clause_turns_c1_into_an_unhandled_exception(tmp_path, monkeypatch):
    """The status is produced by the `except InputUnavailable` clause in
    cli._run_phase and nowhere else. Make that clause unreachable (its
    exception name rebound to a class nothing raises) and C1's fixture falls
    through to the generic handler -- FAIL, "unhandled exception"."""

    class _NeverRaised(Exception):
        pass

    monkeypatch.setattr(cli, "InputUnavailable", _NeverRaised)
    repo = _repo(tmp_path, "placebo_test", "placebo_test", _pinned_binding("placebo_test", PASSING_PLACEBO))
    r = _run(repo, "decision", "D2")
    assert r.status is Status.FAIL
    assert "unhandled exception" in r.reason
    # (The traceback text is length-bounded by core.result.MAX_REASON, so the
    # class name is not asserted on; the status flip is the whole control.)
    assert r.status is not Status.UNMEASURABLE


# ---------------------------------------------------------------------------
# C9 -- structural: reason required, never a pass, round-trips, and the portfolio reads it as unmeasured
# ---------------------------------------------------------------------------


def test_c9_unmeasurable_requires_a_reason_and_is_never_a_pass():
    with pytest.raises(FabricationError):
        CheckResult("D2", "decision", Status.UNMEASURABLE, "")
    r = _unmeasurable_result()
    gate = GateAggregate("stops", (r,))
    assert gate.passed is False
    assert gate.blocking == ("D2",)
    assert CheckResult.from_dict(r.to_dict()).status is Status.UNMEASURABLE
    assert not {"SKIP", "WARN"} & {s.value for s in Status}


def test_c9_the_portfolio_reads_unmeasurable_as_in_progress_never_blocked_or_ready(tmp_path):
    from resilient_mlkit.checks import PHASES, PHASE_ORDER, load_all

    load_all()
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text('[repo]\nname = "fixture"\n')
    repo = Repo("fixture", tmp_path)
    # Every gating check passing except D2, which is unmeasurable here.
    results: dict[str, CheckResult] = {}
    for phase in PHASES:
        for cid in PHASE_ORDER[phase]:
            results[cid] = CheckResult.passed(cid, phase, {"x": 1})
    results["D2"] = _unmeasurable_result()
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert state.state not in (BLOCKED, READY)
    assert "D2" in state.reason and "unmeasur" in state.reason.lower()

    # And with D2 measured the same set is READY: the row was the only thing in the way.
    results["D2"] = CheckResult.passed("D2", "decision", {"x": 1})
    assert resolve(repo, results).state == READY


def test_c9_cmd_check_exits_3_not_1_on_an_unmeasurable_row(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _repo(root / "resilient-torrent", "placebo_test", "placebo_test",
          _pinned_binding("placebo_test", PASSING_PLACEBO), name="torrent")
    (root / "resilient-fray").mkdir()  # a second sibling so find_root() is not consulted
    rc = cli.main(["check", "--phase", "decision", "--root", str(root), "--repo", "torrent", "--offline"])
    assert rc == 3


# ---------------------------------------------------------------------------
# arm_state -- the one definition an adopter's hard-stops module renders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declared,status,armed,halt,indicted",
    [
        (True, Status.PASS, True, False, False),
        (True, Status.FAIL, True, True, True),
        (True, Status.UNMEASURABLE, True, True, False),
        (True, Status.NA, False, False, False),
        (True, Status.DEFERRED, False, False, False),
        (False, Status.FAIL, False, False, False),
        (False, Status.UNMEASURABLE, False, False, False),
    ],
)
def test_arm_state_is_the_single_definition(declared, status, armed, halt, indicted):
    st = arm_state(declared, status)
    assert (st.armed, st.halt_required, st.indicted) == (armed, halt, indicted)
    assert arm_state(declared, status.value) == st  # a string status reads the same
    assert st.to_dict()["status"] == status.value


def test_arm_state_unmeasurable_is_armed_and_halting_but_not_indicted():
    """The line torrent and chokepoint each typed -- `armed = status in {PASS,
    FAIL}` -- reads an UNMEASURABLE stop as unarmed and non-halting. Both wrong."""
    st = arm_state(True, Status.UNMEASURABLE)
    assert st.armed and st.halt_required and not st.indicted
