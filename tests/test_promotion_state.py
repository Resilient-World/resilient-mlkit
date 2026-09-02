"""Controls for the terminal-state resolver — the function that grants promotion.

Every check in this package exists to feed one decision: `portfolio.resolve`,
which turns a bag of results into READY-TO-TRAIN, READY-PENDING-KEYS,
AWAITING-SIGNOFF, IN-PROGRESS or BLOCKED. A check that fires correctly into a
resolver that then reads the wrong word off it has caught nothing, so this is
the last place a bad result can still become a promotion, and it had no tests.

The pairs here are about precedence, because precedence is where a resolver
goes wrong quietly. Two orderings carry the weight, and both are easy to get
backwards:

* **unmeasured outranks a pending signature.** Six checks are reserved to the
  signatory and ALWAYS report ESCALATED. If escalation won, every repo would
  read AWAITING-SIGNOFF — "done, just needs a countersignature" — the moment it
  had run its phases, however little was actually measured. The pair is an NA
  beside an ESCALATED (IN-PROGRESS) against an ESCALATED alone (AWAITING).

* **a measured failure blocks wherever it is found, but only the gating set
  decides readiness.** Triage diagnoses and is deliberately outside the gating
  set; a triage FAIL still blocks. The pair is a triage FAIL (BLOCKED) against a
  triage NA (which must NOT hold a repo back), and without both, "triage is not
  a gate" and "triage is ignored" are the same code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from resilient_mlkit.checks import PHASE_ORDER
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult
from resilient_mlkit.portfolio import (
    AWAITING,
    BLOCKED,
    IN_PROGRESS,
    READY,
    READY_PENDING_KEYS,
    gating_ids,
    resolve,
)

#: The six checks reserved to the human signatory (CLAUDE.md rule 12). They
#: always report ESCALATED, which is why escalation must not outrank NA.
HUMAN_ONLY = ("S5", "D1", "D4", "D5", "E4", "E5")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(name="fixturerepo", path=tmp_path)


def _phase_of(check_id: str) -> str:
    return next(p for p, ids in PHASE_ORDER.items() if check_id in ids)


def _all_passing() -> dict[str, CheckResult]:
    """A result for every gating check, all PASS. The only route to READY."""
    return {
        cid: CheckResult.passed(cid, _phase_of(cid), {"measured": True})
        for cid in gating_ids()
    }


# -- the shape of the gating set ------------------------------------------


def test_the_gating_set_is_the_four_non_triage_phases() -> None:
    """Pinned because widening or narrowing it silently redefines READY.

    The literal moved from 26 to 27 when R12 (``SERVED_CONTRACT``) joined the
    readiness phase. That is what this tripwire is for: adding a gating check
    redefines READY for every repo, and it should not be possible to do it
    without editing this line and saying so. R12 is a gating check on purpose —
    a repo whose serving path defines "promotable" for itself is not ready to
    train against a bar it can reinterpret.

    It moved again, from 27 to 28, when D6 (``RESAMPLING_UNIT``) joined the
    decision phase on 2026-09-01, and this paragraph is the "saying so".
    ``assert len(ids) == 27`` → ``assert len(ids) == 28``; the assertion is the
    same exact equality on a set one larger, and nothing else in this file
    moved. D6 is a gating check on purpose, for R12's reason one layer up: a
    repo whose interval rests on a resampling unit that contradicts its own
    holdout policy has a promotion bar it can reinterpret. Round-8 adjudication
    measured the size of that reinterpretation in ``resilient-fray`` — one
    identical set of 1,365 rows, ``[+16.016, +29.646]`` under the unit the run
    resampled and ``[-1.289, +41.704]`` under the unit its own split implies.

    WHAT THIS DOES TO THE FLEET, measured rather than reasoned: nothing, today.
    D6 answers NA wherever the ``resampling_declaration`` binding is absent,
    which is every repo, and every repo already carries several NAs (D2, D3,
    E1, E2, E3, R7 at minimum), so every repo was already IN-PROGRESS by the
    branch above. What changes is the count in that state's message —
    ``N of 27`` becomes ``N+1 of 28``.

    This is the ONLY place the number is written. The READY message below reads
    it back from ``gating_ids()`` rather than repeating it, because two copies
    of a count is how the version literal went stale in E-M08.
    """
    ids = gating_ids()
    assert len(ids) == 28
    assert set(PHASE_ORDER["triage"]).isdisjoint(ids), "triage diagnoses; it does not gate"
    for cid in HUMAN_ONLY:
        assert cid in ids, f"{cid} is reserved to the signatory and must still gate"


# -- READY: FIRES / SILENT -------------------------------------------------


def test_negative_control_every_gating_check_passing_is_READY(repo: Repo) -> None:
    """SILENT: the one input that may produce READY. Without it nothing below means anything."""
    state = resolve(repo, _all_passing())
    assert state.state == READY
    assert f"all {len(gating_ids())} gating checks pass" in state.reason


def test_positive_control_one_missing_gating_result_is_not_READY(repo: Repo) -> None:
    """FIRES: a check that never ran is unmeasured, not clean."""
    results = _all_passing()
    del results["R5"]
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "R5" in state.reason


def test_positive_control_one_NA_in_the_gating_set_is_not_READY(repo: Repo) -> None:
    """FIRES: 'could not be measured here' can never be counted as a pass."""
    results = _all_passing()
    results["R5"] = CheckResult.na("R5", "readiness", "no provenance binding declared")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "first unmeasurable: R5" in state.reason


# -- precedence: unmeasured outranks a pending signature -------------------


def test_positive_control_an_NA_beside_an_ESCALATED_is_IN_PROGRESS(repo: Repo) -> None:
    """FIRES: the precedence that is easy to get backwards, and expensive when it is.

    If escalation won here the repo would read AWAITING-SIGNOFF — a state that
    says the engineering is finished — while one of its gating checks had
    measured nothing at all.
    """
    results = _all_passing()
    results["R3"] = CheckResult.na("R3", "readiness", "no splits binding declared")
    for cid in HUMAN_ONLY:
        results[cid] = CheckResult.escalated(cid, _phase_of(cid), "reserved to the signatory")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "also await sign-off" in state.reason


def test_negative_control_ESCALATED_alone_is_AWAITING_SIGNOFF(repo: Repo) -> None:
    """SILENT: nothing unmeasured, so a pending signature is the whole story.

    The pair for the test above. Without it, "unmeasured outranks escalation"
    would be satisfied by a resolver that never returns AWAITING at all.
    """
    results = _all_passing()
    for cid in HUMAN_ONLY:
        results[cid] = CheckResult.escalated(cid, _phase_of(cid), "reserved to the signatory")
    state = resolve(repo, results)
    assert state.state == AWAITING
    for cid in HUMAN_ONLY:
        assert cid in state.reason


def test_negative_control_DEFERRED_alone_is_READY_PENDING_KEYS(repo: Repo) -> None:
    """SILENT: wired end to end and stopped at a key. Not READY, and not unmeasured."""
    results = _all_passing()
    results["R7"] = CheckResult.deferred(
        "R7", "readiness", "CDSAPI_KEY", "request built; key consumed at the boundary",
        {"exercised": "request built"},
    )
    state = resolve(repo, results)
    assert state.state == READY_PENDING_KEYS
    assert "CDSAPI_KEY" in state.reason


def test_positive_control_DEFERRED_beside_an_NA_is_still_IN_PROGRESS(repo: Repo) -> None:
    """FIRES: a key pending does not excuse a check that measured nothing."""
    results = _all_passing()
    results["R7"] = CheckResult.deferred(
        "R7", "readiness", "CDSAPI_KEY", "request built", {"exercised": "request built"}
    )
    results["R3"] = CheckResult.na("R3", "readiness", "no splits binding declared")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "wired awaiting keys" in state.reason


# -- a measured failure blocks wherever it is found ------------------------


def test_positive_control_one_FAIL_in_the_gating_set_is_BLOCKED(repo: Repo) -> None:
    """FIRES: and the reason must carry the failing check's own words."""
    results = _all_passing()
    results["R5"] = CheckResult.failed(
        "R5", "readiness", "non-real rows present in evaluation splits (val: synthetic=1)"
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert state.reason.startswith("R5 failed:")
    assert "synthetic=1" in state.reason


def test_positive_control_a_triage_FAIL_blocks_even_though_triage_does_not_gate(
    repo: Repo,
) -> None:
    """FIRES: outside the gating set is not outside the truth.

    Every gating check passes here. The only failure is in triage, which is not
    part of the "everything passes" test — and the repo is still BLOCKED,
    because a measured failure is a measured failure.
    """
    results = _all_passing()
    results["T2"] = CheckResult.failed("T2", "triage", "one-batch overfit did not converge")
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "T2 failed" in state.reason


def test_negative_control_a_triage_NA_does_not_hold_a_repo_back(repo: Repo) -> None:
    """SILENT: the pair that keeps triage diagnostic rather than ignored.

    Without this control, "a triage FAIL blocks" and "triage is scanned for
    everything" are the same implementation, and a repo would sit at IN-PROGRESS
    forever over a diagnostic that was never meant to gate.
    """
    results = _all_passing()
    results["T4"] = CheckResult.na("T4", "triage", "no GPU on this host")
    state = resolve(repo, results)
    assert state.state == READY


def test_a_second_failure_is_counted_not_hidden(repo: Repo) -> None:
    """The reason names one check and says how many more there are."""
    results = _all_passing()
    results["R3"] = CheckResult.failed("R3", "readiness", "groups appear in more than one split")
    results["R5"] = CheckResult.failed("R5", "readiness", "non-real rows in val")
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "R3 failed" in state.reason and "+1 more" in state.reason


# -- hard stops outrank everything ----------------------------------------


def test_positive_control_a_halt_outranks_a_full_set_of_passes(repo: Repo) -> None:
    """FIRES: D2 and E1 hard stops are not fixable by tuning the thing that failed.

    The halt is carried in evidence rather than in the status, so a check can
    halt the repo while reporting its own measured verdict. This must beat every
    other branch, including an otherwise complete set of passes.
    """
    results = _all_passing()
    results["D2"] = CheckResult.passed(
        "D2", "decision",
        {"halt": True, "placebo_ci": [0.4, 0.9]},
        "placebo estimate's CI excludes zero",
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert state.reason.startswith("D2 hard stop:")
    assert state.halted is True


def test_negative_control_no_halt_flag_leaves_the_verdict_alone(repo: Repo) -> None:
    """SILENT: evidence that merely mentions a placebo is not a hard stop."""
    results = _all_passing()
    results["D2"] = CheckResult.passed("D2", "decision", {"placebo_ci": [-0.2, 0.3]})
    state = resolve(repo, results)
    assert state.state == READY
    assert state.halted is False


def test_positive_control_a_halt_outranks_a_FAIL_and_names_the_hard_stop(repo: Repo) -> None:
    """FIRES: a hard stop and a failure together must report the hard stop.

    They are not the same instruction. A FAIL says fix it; a hard stop says the
    planned run cannot buy what it was meant to buy, and no amount of fixing the
    failing check changes that.
    """
    results = _all_passing()
    results["R5"] = CheckResult.failed("R5", "readiness", "non-real rows in val")
    results["E1"] = CheckResult.passed(
        "E1", "economics", {"halt": True}, "scaling curve flat between 10% and 25%"
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "hard stop" in state.reason


# -- no remembered count of the gating set (E-M09 round; checks/__init__.py's rule)
#
# `checks/__init__.py` records the discipline in its own docstring: its count is
# obtained by COUNTING the registry, "not by remembering, which is the only way
# a number in a docstring is ever worth anything". `portfolio.py` was the place
# that still remembered. Its module docstring read "S1-S5, R1-R11, D1-D5,
# E1-E5: twenty-six checks" after R12 joined `PHASE_ORDER`, so the module that
# DEFINES the gating set described a set one check smaller than the one it
# returns, and nothing in the suite could see it.
#
# The rule here is deliberately not "portfolio.py must contain no numbers". It
# is: any count of checks stated in that file must equal the registry's. A file
# that states none passes trivially, which is the shape the repair takes.

_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}

#: A count immediately qualifying the word "checks": `26 checks`,
#: `twenty-six checks`, `27 gating checks`. The f-string
#: `f"all {len(all_ids)} gating checks pass"` is not matched, and must not be:
#: it is the derived count and is the correct way to state one.
_COUNT_OF_CHECKS = re.compile(
    r"\b([A-Za-z]+(?:-[A-Za-z]+)?|\d+)\s+(?:gating\s+)?checks\b", re.IGNORECASE
)


def _as_int(token: str) -> int | None:
    """The integer a token names, or None when it names no number at all."""
    if token.isdigit():
        return int(token)
    word = token.lower()
    if word in _UNITS:
        return _UNITS[word]
    if word in _TENS:
        return _TENS[word]
    if "-" in word:
        tens, _, unit = word.partition("-")
        if tens in _TENS and unit in _UNITS and _UNITS[unit] < 10:
            return _TENS[tens] + _UNITS[unit]
    return None


def stated_check_counts(source: str) -> list[tuple[str, int]]:
    """Every literal count of checks written into ``source``.

    Returns `(token, value)` pairs so a failure names the words to fix rather
    than only the number they came to.
    """
    out: list[tuple[str, int]] = []
    for token in _COUNT_OF_CHECKS.findall(source):
        value = _as_int(token)
        if value is not None:
            out.append((token, value))
    return out


def _portfolio_source() -> str:
    import resilient_mlkit.portfolio as mod

    return Path(mod.__file__).read_text(encoding="utf-8")


def test_portfolio_states_no_gating_count_the_registry_contradicts() -> None:
    """FIRES on `main` at 21f7e6f: the docstring says twenty-six, the registry 27."""
    expected = len(gating_ids())
    wrong = [
        (token, value)
        for token, value in stated_check_counts(_portfolio_source())
        if value != expected
    ]
    assert wrong == [], (
        f"portfolio.py states a count of checks the registry contradicts "
        f"(checks.PHASE_ORDER gates {expected}): {wrong}. Defer to the registry "
        "rather than restating it — a remembered count rots in place, which is "
        "what checks/__init__.py's own docstring says and why it counts instead"
    )


# -- controls for the above ------------------------------------------------


def test_positive_control_a_stale_count_reinserted_is_caught() -> None:
    """FIRES: the exact sentence that was in portfolio.py, on a copy in memory."""
    stale = (
        '"""Terminal-state resolution.\n\n'
        "The gating set is S1-S5, R1-R11, D1-D5, E1-E5: twenty-six checks.\n"
        '"""\n'
    )
    found = stated_check_counts(stale)
    assert found == [("twenty-six", 26)]
    assert found[0][1] != len(gating_ids()), (
        "this control assumes the registry does not gate 26 checks; if it ever "
        "does, the fixture below must move, not the assertion"
    )


def test_negative_control_the_right_count_written_out_is_silent() -> None:
    """SILENT: a literal count is only a defect while it disagrees.

    Without this pair the check above is indistinguishable from a rule banning
    digits, which would be a different (and worse) rule.
    """
    right = f"The gating set is {len(gating_ids())} checks.\n"
    found = stated_check_counts(right)
    assert [value for _, value in found] == [len(gating_ids())]


def test_negative_control_a_derived_count_is_not_a_literal() -> None:
    """SILENT: `f"all {len(all_ids)} gating checks pass"` is the correct shape."""
    derived = 'return RepoState(repo, results, READY, f"all {len(all_ids)} gating checks pass")\n'
    assert stated_check_counts(derived) == []


def test_the_parser_can_see_a_count_at_all() -> None:
    """A finder that finds nothing would make every assertion above vacuous."""
    assert stated_check_counts("twenty-seven gating checks") == [("twenty-seven", 27)]
    assert stated_check_counts("26 checks") == [("26", 26)]
    assert stated_check_counts("triage checks") == []


# -- the README's copy of the same count (E-M32)
#
# E-M32 recorded that `README.md` states the gating-check count in prose and
# that NOTHING reads it. Adding D6 proved the point twice over: the sentence at
# `README.md:114` was updated 27 -> 28 and the one in the Layout section nine
# lines above it was NOT, so the file shipped saying `27 gating checks ... 32 in
# the registry` in one paragraph and `28 gating checks` in the next -- and the
# stale pair is the one that claims to be MEASURED, `len(gating_ids())` and
# `len(all_check_ids())` with a retrieval date. A remembered number wearing a
# measurement's clothes is worse than one that admits it is prose.
#
# The rule is the same one `test_portfolio_states_no_gating_count_the_registry
# _contradicts` applies to `portfolio.py`, and deliberately no wider: only the
# two phrasings that state a TOTAL are held. "Three of the readiness checks"
# (`README.md:88`) is a subset count, is correct, and must stay legal -- which
# is why this reads `gating checks` and `in the registry` rather than reusing
# `stated_check_counts`, whose regex matches any count of checks at all.

#: `28 gating checks`, `twenty-eight gating checks`. Requires the word
#: "gating", so a subset count of some other kind of check is not matched.
_README_GATING = re.compile(
    r"\b([A-Za-z]+(?:-[A-Za-z]+)?|\d+)\s+gating\s+checks\b", re.IGNORECASE
)
#: `33 in the registry` — the whole registry, triage included.
_README_REGISTRY = re.compile(
    r"\b([A-Za-z]+(?:-[A-Za-z]+)?|\d+)\s+in\s+the\s+registry\b", re.IGNORECASE
)


def _readme_source() -> str:
    import resilient_mlkit

    root = Path(resilient_mlkit.__file__).resolve().parents[2]
    return (root / "README.md").read_text(encoding="utf-8")


def _stated(pattern: re.Pattern[str], source: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for token in pattern.findall(source):
        value = _as_int(token)
        if value is not None:
            out.append((token, value))
    return out


def test_the_readme_states_no_check_count_the_registry_contradicts() -> None:
    """FIRES at 24f23b8: README says both `27 gating checks` and `28 gating checks`."""
    from resilient_mlkit.checks import all_check_ids, load_all

    load_all()
    source = _readme_source()
    gating, registry = len(gating_ids()), len(all_check_ids())

    wrong_gating = [(t, v) for t, v in _stated(_README_GATING, source) if v != gating]
    wrong_registry = [
        (t, v) for t, v in _stated(_README_REGISTRY, source) if v != registry
    ]
    assert wrong_gating == [], (
        f"README.md states a gating-check count the registry contradicts "
        f"(checks.PHASE_ORDER gates {gating}): {wrong_gating}"
    )
    assert wrong_registry == [], (
        f"README.md states a registry size the registry contradicts "
        f"({registry} checks are registered): {wrong_registry}"
    )


def test_the_readme_actually_states_both_counts() -> None:
    """Not-dead. Without this the check above passes on a README stating neither.

    That is the whole failure mode of a scanner: E-M32 exists because a count
    nothing reads goes stale in place, and a reader that finds no count is
    indistinguishable from a file with no stale count in it.
    """
    source = _readme_source()
    assert _stated(_README_GATING, source), "README states no gating-check count"
    assert _stated(_README_REGISTRY, source), "README states no registry size"


def test_the_readme_parsers_do_not_match_a_subset_count() -> None:
    """Negative control: `README.md:88`'s "Three of the readiness checks" is legal.

    Without this pair the check above is indistinguishable from a rule banning
    every number near the word "checks" in the README, which would forbid the
    correct sentence along with the wrong one.
    """
    assert _stated(_README_GATING, "Three of the readiness checks import nothing") == []
    assert _stated(_README_GATING, "28 gating checks") == [("28", 28)]
    assert _stated(_README_REGISTRY, "5 diagnostic triage checks: 33 in the registry") == [
        ("33", 33)
    ]
