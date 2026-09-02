"""D2/E1 under a DECLARED contract: does each hard stop still fire, and stay silent.

`tests/test_decision_controls.py` and `tests/test_economics_controls.py` prove
both hard stops fire under mlkit's built-in rule. Neither file is touched by
this one, and neither needed to be: an undeclared repo is judged by exactly the
rule it was judged by before, so those 79 controls are also the negative control
for this whole file. What they cannot cover is the new surface -- a repo that
DECLARES its own halt region or its own fraction ladder -- and a hard stop that
a declaration can switch off is not a hard stop.

Three pairings carry the weight here.

* **the same interval, halting or silent depending only on the declaration.**
  `[-71.998, -53.146]` is fray's measured placebo. With no `[placebo]` section
  it is a hard stop, and that is the spurious fleet-wide halt round 8's
  adjudication predicted (§2.4) for a repo that bound this honest surrogate
  under mlkit's two-sided rule. With fray's estimand declared -- skill against
  the persistence floor, whose no-signal value is not zero -- it is a PASS. The
  pair is the finding being closed, asserted rather than described.

* **the declared halt region still halts.** Same declaration, a placebo that
  BEATS the floor: `[+8.0, +26.0]`. FAIL with `halt`. Without this half the
  test above is indistinguishable from having deleted D2 for fray.

* **the two ways a declared ladder could buy a pass are refused as
  declarations.** A ladder topping out below 25%, and a ladder whose top step
  is wider than mlkit's own, are FAILs before any curve is read -- so the
  refusal cannot be dodged by also reporting a steep curve, which is the shape
  the second half of each pair asserts.

Every fixture here is a real git repo whose `.mlkit/repo.toml` is COMMITTED,
resolved through `repo.resolve()`, which is the path the eight real repos take.
The uncommitted-declaration controls exist because that is the difference
between a standard and a sentence: `docs/ESCALATIONS.md` E-M12/E-M23.
"""

from __future__ import annotations

import subprocess
import textwrap

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import (
    DEFAULT_NULL,
    INDICTS_EITHER,
    PLACEBO_SECTION,
    d2_placebo_test,
    read_halt_region,
)
from resilient_mlkit.checks.economics import (
    DEFAULT_FRACTIONS,
    MAX_TOP_STEP,
    MIN_TOP_FRACTION,
    SCALING_SECTION,
    e1_scaling_probe,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import ALLOW_DIRTY_KEY, Status, UncommittedRead
from resilient_mlkit.portfolio import BLOCKED, resolve

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py. Two
#: repos naming their adapter module the same thing is the collision
#: `Repo.release()` exists for.
_SERIAL = iter(range(10_000))


# -- fray's measured figures, from round 8's adjudication -------------------
#
# Quoted rather than invented, because the case this file closes is a specific
# one and a fixture shaped to the check instead of to the incident proves
# nothing about the incident. Source: scratchpad adjudication §2.4 and the
# training-round record for `resilient-fray`'s unseen-year track.

#: fray's placebo CI. Its estimand is skill against the persistence floor, so a
#: shuffled-target run is expected to land far BELOW the floor, and it does.
_FRAY_PLACEBO_LO = -71.998
_FRAY_PLACEBO_HI = -53.146
_FRAY_PLACEBO_EST = (_FRAY_PLACEBO_LO + _FRAY_PLACEBO_HI) / 2.0

#: The real run's effect the placebo must be able to detect: VAL MAE
#: 128.9300068339915 against the persistence floor 151.74139194139195, in lb/ac.
#: Positive, because skill against a floor is larger-is-better -- which is what
#: ties it to `indicts = "above"`.
_FRAY_REFERENCE = 151.74139194139195 - 128.9300068339915

#: fray's scaling curve, oriented larger-is-better, at 10% and 25%.
_FRAY_AT_10 = -151.29137
_FRAY_AT_25 = -138.13969


def _git(cwd, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _repo(
    tmp_path,
    binding: str,
    body: str,
    *,
    section: str = "",
    declaration: str = "",
    commit_declaration: bool = True,
) -> Repo:
    """A git repo with `binding` wired and, optionally, `[section]` declared.

    `commit_declaration=False` writes the section into the working tree only,
    AFTER the commit -- the E-M12 shape, and the only way to exercise the
    refusal that separates a committed standard from a sentence on disk.
    """
    module = f"decl_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    base = f'[repo]\nname = "fixturerepo"\n\n[bindings]\n{binding} = "{module}:{binding}"\n'
    block = f"\n[{section}]\n{textwrap.dedent(declaration)}\n" if section else ""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".mlkit" / "repo.toml").write_text(base + (block if commit_declaration else ""))
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "fixture")
    if not commit_declaration and block:
        (tmp_path / ".mlkit" / "repo.toml").write_text(base + block)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path, *, allow_dirty: bool = False) -> RunContext:
    return RunContext(
        nonce="test-nonce", root=tmp_path, offline=True, allow_dirty=allow_dirty
    )


def _run_d2(tmp_path, fields: str, *, declaration: str = "", commit: bool = True, **kw):
    body = f"""
        def placebo_test():
            return {{{fields}}}
    """
    repo = _repo(
        tmp_path,
        "placebo_test",
        body,
        section=PLACEBO_SECTION if declaration else "",
        declaration=declaration,
        commit_declaration=commit,
    )
    try:
        return d2_placebo_test(repo, _ctx(tmp_path, **kw))
    finally:
        repo.release()


def _run_e1(tmp_path, curve: str, *, declaration: str = "", commit: bool = True, **kw):
    body = f"""
        def scaling_probe():
            return {{{curve}}}
    """
    repo = _repo(
        tmp_path,
        "scaling_probe",
        body,
        section=SCALING_SECTION if declaration else "",
        declaration=declaration,
        commit_declaration=commit,
    )
    try:
        return e1_scaling_probe(repo, _ctx(tmp_path, **kw))
    finally:
        repo.release()


#: fray's declaration, as a repo would commit it.
_FRAY_PLACEBO_DECL = """
    estimand = "skill against the persistence floor, lb/ac"
    null_value = 0.0
    indicts = "above"
"""


# == D2 ====================================================================
# -- the pair that closes the finding: same interval, two declarations ------


def test_positive_control_frays_placebo_halts_the_fleet_when_nothing_is_declared(tmp_path):
    """FIRES: the spurious hard stop §2.4 predicted, reproduced.

    This is what would have happened had fray bound its honest placebo under
    `placebo_test` with no `[placebo]` section: mlkit's two-sided rule sees
    `hi < 0`, calls the estimator broken, and halts the repo. Every number here
    is fray's own. The verdict is wrong about fray and RIGHT about the rule --
    which is exactly why the rule had to become declarable rather than looser.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": {_FRAY_PLACEBO_EST!r}, "ci_low": {_FRAY_PLACEBO_LO!r}, '
        f'"ci_high": {_FRAY_PLACEBO_HI!r}, "reference_effect": {_FRAY_REFERENCE!r}',
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "excludes zero" in result.reason
    assert result.evidence["null_value"] == DEFAULT_NULL
    assert result.evidence["indicts"] == INDICTS_EITHER


def test_negative_control_the_same_interval_is_silent_once_the_estimand_is_declared(
    tmp_path,
):
    """SILENT: the identical measurement, judged against the declared estimand.

    Nothing about the placebo changed -- same estimate, same interval, same
    reference effect. Only the committed declaration did, and it says what the
    test above could not know: under "skill against the persistence floor" a
    shuffled-target run is EXPECTED to land far below the floor, and only a
    placebo that BEATS it indicts. The pair is the whole finding.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": {_FRAY_PLACEBO_EST!r}, "ci_low": {_FRAY_PLACEBO_LO!r}, '
        f'"ci_high": {_FRAY_PLACEBO_HI!r}, "reference_effect": {_FRAY_REFERENCE!r}',
        declaration=_FRAY_PLACEBO_DECL,
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["indicts"] == "above"
    assert result.evidence["estimand"].startswith("skill against the persistence floor")
    # The interval does not contain the null and is not required to: it sits on
    # the side the repo declared not to indict, and the evidence says so rather
    # than leaving a reader to assume the older, narrower reason for a PASS.
    assert result.evidence["null_contained"] is False
    # Disclosure, not a gate (docs/ESCALATIONS.md E-M24): mlkit does not
    # adjudicate how far a declared null may sit from the estimate, so it prints
    # the number a reviewer would need. 62.572 / 22.811… = 2.743, which is
    # ordinary for a skill-against-a-floor estimand -- and a runaway null would
    # read as an enormous figure here instead of as a silent PASS.
    assert round(result.evidence["null_distance_in_reference_effects"], 3) == 2.743


def test_positive_control_the_declared_halt_region_still_halts(tmp_path):
    """FIRES: the not-dead half. Same declaration, a placebo that beats the floor.

    `[+8.0, +26.0]` is a shuffled-target run showing real skill against the
    bar, which is leakage and is the precise thing D2 exists to refuse. Without
    this control the test above is indistinguishable from having switched D2
    off for every repo that writes a `[placebo]` section.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": 17.0, "ci_low": 8.0, "ci_high": 26.0, '
        f'"reference_effect": {_FRAY_REFERENCE!r}',
        declaration=_FRAY_PLACEBO_DECL,
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "'above' side this repo declared indicting" in result.reason


def test_the_declared_D2_hard_stop_reaches_the_portfolio_as_BLOCKED(tmp_path):
    """FIRES, end to end: a declared halt region produces the flag that stops the repo.

    The join `tests/test_decision_controls.py` makes for the built-in rule,
    made again for the declared one. A halt that does not reach
    `portfolio.resolve` is a red row, not a stop.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 17.0, "ci_low": 8.0, "ci_high": 26.0, "reference_effect": 22.8',
        declaration=_FRAY_PLACEBO_DECL,
    )
    repo = _repo(tmp_path, "placebo_test", "def placebo_test():\n    return {}\n")
    try:
        state = resolve(repo, {"D2": result})
    finally:
        repo.release()
    assert state.state == BLOCKED
    assert state.reason.startswith("D2 hard stop:")
    assert state.halted is True


# -- `indicts = "below"`, the mirror image ---------------------------------
#
# Written after a mutation drive: making `halts_above` return True for every
# region left the whole suite green, because nothing exercised `"below"` at
# all. The mutation is in the STRICT direction -- a `"below"` repo would have
# been halted on excursions it declared exempt -- so it cost no repo a wrong
# PASS. It cost the suite its claim to have tested the branch, which is the
# same defect one level up: an untested arm is not a strict arm, it is an
# unmeasured one.

#: A repo whose product claim is a REDUCTION, so its real-run effect is
#: negative and only excursions BELOW the null indict.
_BELOW_DECL = """
    estimand = "reduction in avoided-loss error against the served baseline"
    null_value = 0.0
    indicts = "below"
"""


def test_positive_control_a_below_region_halts_on_an_interval_beneath_the_null(tmp_path):
    """FIRES: `indicts = "below"`, CI `[-1.13, -0.31]`.

    The mirror of the `"above"` hard stop. A placebo reproducing the reduction
    the product claims is the same leakage, pointing the other way.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": -0.72, "ci_low": -1.13, "ci_high": -0.31, "reference_effect": -0.4',
        declaration=_BELOW_DECL,
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "'below' side this repo declared indicting" in result.reason


def test_negative_control_a_below_region_is_silent_on_an_interval_above_the_null(tmp_path):
    """SILENT: the same declaration, CI `[+0.31, +1.13]`.

    The exempt side for this estimand, and the half that makes the control
    above a pair rather than a blanket refusal. It is also the half a mutation
    that widened `halts_above` to every region would break, which is why it is
    written as an assertion instead of left implied by the `"above"` tests.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.72, "ci_low": 0.31, "ci_high": 1.13, "reference_effect": -4.0',
        declaration=_BELOW_DECL,
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["null_contained"] is False


def test_positive_control_a_below_region_with_a_positive_claim_is_refused(tmp_path):
    """FIRES: the sign tie, mirrored. `indicts = "below"` with a POSITIVE effect.

    Without this the tie is only tested in one direction, and a fix that hard
    coded `reported > 0` would satisfy every other control in this file.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": 0.4',
        declaration=_BELOW_DECL,
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_EXEMPTS_THE_CLAIM" in result.reason


# -- a genuinely non-zero null, both sides ---------------------------------


def test_positive_control_a_shifted_null_still_has_two_sides(tmp_path):
    """FIRES: `null_value = -62.0`, `indicts = "either"`, CI `[-40, -30]`.

    A declared null does not make D2 one-sided. The interval excludes −62 from
    ABOVE, and the estimator is as broken as one that excluded zero from above.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": -35.0, "ci_low": -40.0, "ci_high": -30.0, "reference_effect": 22.8',
        declaration="""
            estimand = "skill against the persistence floor, lb/ac"
            null_value = -62.0
            indicts = "either"
        """,
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "excludes the declared null -62" in result.reason


def test_negative_control_the_shifted_null_inside_the_interval_is_silent(tmp_path):
    """SILENT: the same declaration, an interval that contains −62.

    The other half of the shifted-null pair. Without it the branch above is
    consistent with a check that halts on every interval not containing zero.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": {_FRAY_PLACEBO_EST!r}, "ci_low": {_FRAY_PLACEBO_LO!r}, '
        f'"ci_high": {_FRAY_PLACEBO_HI!r}, "reference_effect": {_FRAY_REFERENCE!r}',
        declaration="""
            estimand = "skill against the persistence floor, lb/ac"
            null_value = -62.0
            indicts = "either"
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["null_contained"] is True
    assert result.evidence["null_value"] == -62.0
    # The distance is measured FROM THE DECLARED NULL, not from zero, and this
    # is the only fixture where the two differ. Found by mutation: rewriting
    # `abs(estimate - region.null)` to `abs(estimate)` left every other
    # assertion of this figure green, because every other one declares a null
    # of 0.0 and the two expressions are then the same expression.
    # |-62.572 - (-62.0)| / 22.811… = 0.0251, against |−62.572| / 22.811… = 2.743.
    assert round(result.evidence["null_distance_in_reference_effects"], 4) == 0.0251


# -- what the one-sided exemption costs -------------------------------------


def test_positive_control_a_one_sided_region_that_exempts_the_claim_is_refused(tmp_path):
    """FIRES: `indicts = "above"` beside a NEGATIVE `reference_effect`.

    This is the branch that pays for one-sidedness, and it is the one a naive
    implementation leaves out. A repo whose product claim is a DECREASE, that
    declares only increases to be indicting, has exempted the only direction
    its own placebo could have failed in -- every remaining verdict D2 could
    return is then vacuous. `reference_effect` is already required, already
    measured from this same null, and nothing else in the dict can be tied to
    the declaration without asking the subject for something new.

    A FAIL and not a halt: the repo is not condemned, its declaration and its
    reported effect merely point opposite ways and one of them is wrong.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": -62.5, "ci_low": -71.998, "ci_high": -53.146, '
        '"reference_effect": -22.8',
        declaration=_FRAY_PLACEBO_DECL,
    )
    assert result.status is Status.FAIL
    assert "halt" not in result.evidence
    assert "PLACEBO_EXEMPTS_THE_CLAIM" in result.reason
    assert result.evidence["reference_effect_reported"] == -22.8
    # The power bar's operand is untouched: still the magnitude.
    assert result.evidence["reference_effect"] == 22.8


def test_a_zero_reference_effect_under_a_one_sided_region_names_the_sign(tmp_path):
    """FIRES with the SIGN diagnosis, not the power one. Found by mutation.

    An effect of exactly zero lies on neither side, so a one-sided exemption
    has nothing to agree with. The power bar below refuses a zero reference
    too, so the STATUS is FAIL whichever branch catches it -- which is why
    rewriting the tie's `> 0` to `>= 0` left the whole suite green when the
    mutation drive tried it. The two diagnoses are not interchangeable: "your
    declaration and your claimed effect point different ways" and "your placebo
    was too small to tell" send a reader to different files.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": -62.5, "ci_low": -71.998, "ci_high": -53.146, '
        '"reference_effect": 0.0',
        declaration=_FRAY_PLACEBO_DECL,
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_EXEMPTS_THE_CLAIM" in result.reason
    assert "does not lie on the indicting side" in result.reason
    assert "could not have detected" not in result.reason


def test_negative_control_a_zero_reference_effect_under_the_default_is_the_power_bar(
    tmp_path,
):
    """SILENT for the sign tie: the SAME zero, with nothing declared.

    The other half of the pair above. Under the default the sign is never read,
    so this is the pre-existing power-bar refusal, word for word -- the branch
    `tests/test_decision_controls.py::test_a_reference_effect_of_zero_is_refused`
    already pins, re-asserted here against the new tie specifically.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.01, "ci_high": 0.01, "reference_effect": 0.0',
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_EXEMPTS_THE_CLAIM" not in result.reason
    assert "could not have detected" in result.reason


def test_negative_control_the_default_region_never_reads_the_sign(tmp_path):
    """SILENT: the SAME negative `reference_effect`, with nothing declared.

    The pair that says the sign tie is a cost of the exemption and not a new
    requirement on every repo. Under the default both sides indict, so there is
    nothing for a sign to disagree with, and `abs()` is the whole of the
    arithmetic exactly as it was on main.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": -0.40',
    )
    assert result.status is Status.PASS
    assert result.evidence["reference_effect"] == 0.40


def test_positive_control_a_moved_halt_region_without_an_estimand_is_refused(tmp_path):
    """FIRES: `indicts = "above"` with no `estimand` written beside it.

    mlkit cannot adjudicate prose, so this branch does not try to. What it
    refuses is an ANONYMOUS exemption: the default is the one rule that needs
    no justification because it is the one every repo is measured by, and
    moving it means saying, in the same committed table, what this placebo
    estimates. The sentence then rides in the evidence, so the verdict quotes
    the justification and not only the result.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": {_FRAY_PLACEBO_EST!r}, "ci_low": {_FRAY_PLACEBO_LO!r}, '
        f'"ci_high": {_FRAY_PLACEBO_HI!r}, "reference_effect": {_FRAY_REFERENCE!r}',
        declaration='indicts = "above"\n',
    )
    assert result.status is Status.FAIL
    assert "halt" not in result.evidence
    assert "PLACEBO_ESTIMAND_UNDECLARED" in result.reason


def test_positive_control_a_shifted_null_without_an_estimand_is_refused_too(tmp_path):
    """FIRES: the other half of the same requirement. Moving the null is moving
    the halt region even with both sides still indicting."""
    result = _run_d2(
        tmp_path,
        '"estimate": -62.5, "ci_low": -71.998, "ci_high": -53.146, "reference_effect": 22.8',
        declaration="null_value = -62.0\n",
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_ESTIMAND_UNDECLARED" in result.reason


def test_negative_control_declaring_the_default_explicitly_needs_no_estimand(tmp_path):
    """SILENT: `null_value = 0.0` / `indicts = "either"` written out in full.

    The bar is on MOVING the region, not on writing a `[placebo]` section. A
    repo that spells out the default is running mlkit's rule and gets mlkit's
    wording -- `is_default` is a property of the numbers, not of whether the
    table exists.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": 0.4',
        declaration='null_value = 0.0\nindicts = "either"\n',
    )
    assert result.status is Status.PASS
    assert result.evidence["null_value"] == 0.0


# -- the declaration is COMMITTED or it does not exist ----------------------


def test_positive_control_an_uncommitted_halt_region_is_NA_not_a_silent_default(tmp_path):
    """FIRES as NA: the declaration is in the working tree and on no ref.

    Two wrong answers were available here and both are refused. Reading it
    would make the halt region bytes no reader can fetch -- E-M12's shape, the
    one D3's level was moved out of at E-M23. Ignoring it and applying the
    default would be worse in a quieter way: the repo would be measured under a
    rule it believes it replaced, and would read the resulting verdict as its
    own.
    """
    result = _run_d2(
        tmp_path,
        f'"estimate": {_FRAY_PLACEBO_EST!r}, "ci_low": {_FRAY_PLACEBO_LO!r}, '
        f'"ci_high": {_FRAY_PLACEBO_HI!r}, "reference_effect": {_FRAY_REFERENCE!r}',
        declaration=_FRAY_PLACEBO_DECL,
        commit=False,
    )
    assert result.status is Status.NA
    assert "PLACEBO_UNDECLARED_AT_HEAD" in result.reason
    assert ".mlkit/repo.toml" in result.reason
    assert "halt" not in result.evidence


def test_positive_control_a_binding_writing_its_own_halt_region_at_import_cannot_move_it(
    tmp_path,
):
    """FIRES: the binding's MODULE BODY writes `[placebo]` into the config.

    `repo.resolve()` imports that module, so the write lands BEFORE any read
    taken inside the check -- ordering is not the protection and never was.
    Reading HEAD's blob is: the write makes the tree dirty and `core.artifact`
    refuses it. Same drive as D3's control at E-M23, one check across.

    Without the committed read this would be a PASS on a rule that appeared
    during the measurement, and the interval it exempts is fray's.
    """
    repo = _repo(
        tmp_path,
        "placebo_test",
        f'''
        import pathlib
        _p = pathlib.Path(__file__).parent / ".mlkit" / "repo.toml"
        _p.write_text(
            _p.read_text()
            + '\\n[{PLACEBO_SECTION}]\\nestimand = "self-serving"\\nindicts = "above"\\n'
        )

        def placebo_test():
            return {{
                "estimate": {_FRAY_PLACEBO_EST!r},
                "ci_low": {_FRAY_PLACEBO_LO!r},
                "ci_high": {_FRAY_PLACEBO_HI!r},
                "reference_effect": {_FRAY_REFERENCE!r},
            }}
        ''',
    )
    try:
        result = d2_placebo_test(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is not Status.PASS
    assert result.evidence.get("estimand") != "self-serving"


def test_allow_dirty_diagnoses_a_halt_region_and_structurally_cannot_pass(tmp_path):
    """FIRES: the escape hatch buys a diagnosis and cannot buy a PASS.

    `--allow-dirty` exists so an operator can debug a declaration they have not
    committed; refusing it outright pushes people back to `cat`. What it may
    not do is reach a verdict, and it does not: the marker rides in `evidence`
    and `CheckResult.__post_init__` raises. Both halves are here because a
    marker nothing refuses is a footnote, which is the whole of E-M12.
    """
    repo = _repo(
        tmp_path,
        "placebo_test",
        f"""
        def placebo_test():
            return {{
                "estimate": {_FRAY_PLACEBO_EST!r},
                "ci_low": {_FRAY_PLACEBO_LO!r},
                "ci_high": {_FRAY_PLACEBO_HI!r},
                "reference_effect": {_FRAY_REFERENCE!r},
            }}
        """,
        section=PLACEBO_SECTION,
        declaration=_FRAY_PLACEBO_DECL,
        commit_declaration=False,
    )
    try:
        try:
            d2_placebo_test(repo, _ctx(tmp_path, allow_dirty=True))
        except UncommittedRead as exc:
            assert "PASS may not rest on an --allow-dirty read" in str(exc)
        else:  # pragma: no cover - the guard not firing is the defect
            raise AssertionError("an --allow-dirty PASS was not refused")

        # The other half: a FAIL under the hatch is a usable diagnosis and it
        # carries the marker, so `portfolio.resolve` refuses it downstream.
        config = tmp_path / ".mlkit" / "repo.toml"
        config.write_text(
            config.read_text().replace('indicts = "above"', 'indicts = "below"')
        )
        failing = d2_placebo_test(repo, _ctx(tmp_path, allow_dirty=True))
    finally:
        repo.release()
    assert failing.status is Status.FAIL
    assert failing.evidence[ALLOW_DIRTY_KEY] is True


# -- malformed declarations are refused, never defaulted -------------------


def test_an_array_of_tables_is_refused_rather_than_raising(tmp_path):
    """FIRES: `[[placebo]]` parses to a LIST, and `.get` on a list raises.

    Found for D3 by attacking the fix rather than by reading it, and the same
    shape is available here. It has to land on a refusal, and it has to do it
    without taking the whole run down with a traceback pointing at mlkit.
    """
    repo = _repo(
        tmp_path,
        "placebo_test",
        'def placebo_test():\n    return {"estimate": 0.0, "ci_low": -1.0, "ci_high": 1.0}\n',
    )
    config = tmp_path / ".mlkit" / "repo.toml"
    config.write_text(config.read_text() + f'\n[[{PLACEBO_SECTION}]]\nindicts = "above"\n')
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "array of tables")
    try:
        result = d2_placebo_test(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is Status.FAIL
    assert "PLACEBO_MALFORMED" in result.reason
    assert "not a table" in result.reason
    assert "Traceback" not in (result.reason or "")


def test_an_unknown_key_is_refused_by_name(tmp_path):
    """FIRES: `indict` is not `indicts`, and the fallback would be SILENT.

    Both fallbacks in this contract are toward mlkit's strictest rule, so a typo
    cannot loosen anything -- which is exactly why it must not pass quietly. A
    repo that believes it declared a one-sided region and did not would read a
    two-sided PASS as evidence for a rule it never applied.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": 0.4',
        declaration='estimand = "x"\nindict = "above"\n',
    )
    assert result.status is Status.FAIL
    assert "unknown key(s) indict" in result.reason


def test_a_non_finite_null_is_refused_on_type(tmp_path):
    """FIRES: `null_value = nan` makes `lo > null` and `hi < null` both False.

    The loosest halt region there is, wearing a declaration's clothes -- the
    E-M09/E-M10 defect class, arriving through the new surface. TOML has a
    literal `nan`, so this is reachable by typing it.
    """
    result = _run_d2(
        tmp_path,
        '"estimate": 5.0, "ci_low": 4.0, "ci_high": 6.0, "reference_effect": 0.4',
        declaration='estimand = "x"\nnull_value = nan\n',
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_MALFORMED" in result.reason
    assert "finite" in result.reason


def test_a_boolean_null_is_refused_on_type(tmp_path):
    """FIRES: `bool` is an `int`, so `null_value = true` is a perfectly valid
    `1.0` -- a halt region nobody wrote."""
    result = _run_d2(
        tmp_path,
        '"estimate": 0.0, "ci_low": -0.05, "ci_high": 0.05, "reference_effect": 0.4',
        declaration='estimand = "x"\nnull_value = true\n',
    )
    assert result.status is Status.FAIL
    assert "not a number" in result.reason


def test_an_unknown_indicts_value_is_refused_by_name(tmp_path):
    """FIRES: `indicts = "neither"` would be an exemption of both sides, which
    is D2 deleted. It is not a spelling mlkit accepts."""
    result = _run_d2(
        tmp_path,
        '"estimate": 5.0, "ci_low": 4.0, "ci_high": 6.0, "reference_effect": 0.4',
        declaration='estimand = "x"\nindicts = "neither"\n',
    )
    assert result.status is Status.FAIL
    assert "PLACEBO_MALFORMED" in result.reason
    assert "'either', 'above', 'below'" in result.reason


def test_an_undeclared_repo_reads_the_built_in_region(tmp_path):
    """SILENT as a declaration: `read_halt_region` on a repo with no section.

    Asserted on the reader directly, because every other control in this file
    reaches it through a verdict and could not tell "the default was applied"
    apart from "the declaration happened to agree".
    """
    repo = _repo(tmp_path, "placebo_test", "def placebo_test():\n    return {}\n")
    try:
        region, na_reason, fail_reason = read_halt_region(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert (na_reason, fail_reason) == ("", "")
    assert region is not None
    assert (region.null, region.indicts) == (DEFAULT_NULL, INDICTS_EITHER)
    assert region.is_default is True
    assert region.declared is False


# == E1 ====================================================================

#: A ladder a repo might honestly declare: it tops out above mlkit's 0.25 and
#: its top step is exactly mlkit's own 2.5x.
_LADDER = "fractions = [0.02, 0.20, 0.50]\n"


def test_positive_control_a_declared_ladder_still_halts_on_a_flat_top(tmp_path):
    """FIRES: the not-dead half for E1. Flat between 20% and 50% is a hard stop.

    2.5x the data for a quarter of a percent. The verdict, the epsilon and the
    halt flag are the same ones the built-in ladder produces; only which two
    rungs they are measured between moved, and that moved because the repo
    committed the ladder its probe actually ran.
    """
    result = _run_e1(
        tmp_path, "0.02: 0.40, 0.20: 0.700, 0.50: 0.7015", declaration=_LADDER
    )
    assert result.status is Status.FAIL
    assert result.evidence["halt"] is True
    assert "HARD STOP" in result.reason
    assert "flat between 20% and 50%" in result.reason
    assert result.evidence["gain_top_two"] < 0.01
    assert (result.evidence["from_fraction"], result.evidence["to_fraction"]) == (0.20, 0.50)


def test_negative_control_the_same_ladder_rising_is_silent(tmp_path):
    """SILENT: the other half. Without it the control above is consistent with
    a check that refuses every declared ladder."""
    result = _run_e1(
        tmp_path, "0.02: 0.40, 0.20: 0.70, 0.50: 0.82", declaration=_LADDER
    )
    assert result.status is Status.PASS
    assert "halt" not in result.evidence
    assert result.evidence["gain_top_two"] > 0.01


def test_the_declared_E1_hard_stop_reaches_the_portfolio_as_BLOCKED(tmp_path):
    """FIRES, end to end: a declared ladder produces the flag that stops the repo.

    Renamed from `test_the_declared_hard_stop_reaches_the_portfolio_as_BLOCKED`,
    which is what the D2 control 500 lines above is called. Two module-level
    functions of the same name are one function: Python bound the second and
    the D2 control SILENTLY STOPPED EXISTING -- pytest reported 44 passing
    tests and ran 43. Found by `ruff check` (F811), not by the suite, which is
    the point: a test that vanishes takes its own failure signal with it.
    """
    result = _run_e1(tmp_path, "0.02: 0.40, 0.20: 0.70, 0.50: 0.70", declaration=_LADDER)
    repo = _repo(tmp_path, "scaling_probe", "def scaling_probe():\n    return {}\n")
    try:
        state = resolve(repo, {"E1": result})
    finally:
        repo.release()
    assert state.state == BLOCKED
    assert state.reason.startswith("E1 hard stop:")
    assert state.halted is True


def test_negative_control_frays_measured_curve_passes_on_its_own_ladder(tmp_path):
    """SILENT: the second half of §2.4's E1 finding, with fray's own numbers.

    The curve is `-151.29137 -> -138.13969` oriented larger-is-better: a gain
    of +8.69%, comfortably past mlkit's 1% bar. Under the built-in ladder this
    repo FAILS ON CONTRACT for want of a 1% rung it never ran -- the control
    below is that half -- and neither verdict has anything to do with the
    substance of the curve. This one is measured on the ladder fray declares.
    """
    result = _run_e1(
        tmp_path,
        f"0.05: -170.0, 0.10: {_FRAY_AT_10!r}, 0.25: {_FRAY_AT_25!r}",
        declaration="fractions = [0.05, 0.10, 0.25]\n",
    )
    assert result.status is Status.PASS
    assert result.evidence["gain_top_two"] > 0.086
    # The name is literally true here, so the historical key is kept.
    assert result.evidence["gain_10_to_25"] == result.evidence["gain_top_two"]


def test_positive_control_the_same_curve_fails_on_contract_with_no_ladder_declared(
    tmp_path,
):
    """FIRES: §2.4's E1 finding, reproduced. A FAIL that is not about the curve.

    Identical measurements, no `[scaling]` section, so mlkit requires a 1% rung
    fray's probe never ran. The refusal names the missing fraction, which is
    honest and is also the point: a repo reading this verdict learns nothing
    about whether its run buys anything.
    """
    result = _run_e1(
        tmp_path, f"0.05: -170.0, 0.10: {_FRAY_AT_10!r}, 0.25: {_FRAY_AT_25!r}"
    )
    assert result.status is Status.FAIL
    assert "missing fractions" in result.reason
    assert "0.01" in result.reason
    assert "halt" not in result.evidence


# -- the two ways a ladder could buy a pass, refused as declarations --------


def test_positive_control_a_ladder_with_too_wide_a_top_step_is_refused(tmp_path):
    """FIRES: `[0.01, 0.02, 0.25]` asks whether 12.5x the data helps.

    THE anti-gaming branch. The verdict is the relative gain across the top
    step, so widening that step is the one way a declared ladder could make a
    flat curve look steep -- more data always buys something if you ask for
    enough more. Refused BEFORE the curve is read, which is why the fixture
    reports a steep curve and is refused anyway.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.10, 0.02: 0.20, 0.25: 0.90",
        declaration="fractions = [0.01, 0.02, 0.25]\n",
    )
    assert result.status is Status.FAIL
    assert "SCALING_TOP_STEP_TOO_WIDE" in result.reason
    assert "halt" not in result.evidence
    assert "gain_top_two" not in result.evidence


def test_negative_control_a_top_step_at_exactly_mlkits_own_is_allowed(tmp_path):
    """SILENT at the boundary: `[0.01, 0.20, 0.50]` is a step of exactly 2.5x.

    The other side of the bar, so it is a bar and not a blanket refusal of
    declared ladders. mlkit's own `0.25 / 0.10` is 2.5 exactly in doubles, and
    a repo may ask a question exactly as hard as mlkit's -- never an easier one.
    """
    assert MAX_TOP_STEP == 2.5
    result = _run_e1(
        tmp_path,
        "0.01: 0.10, 0.20: 0.70, 0.50: 0.90",
        declaration="fractions = [0.01, 0.20, 0.50]\n",
    )
    assert result.status is Status.PASS


def test_negative_control_the_built_in_ladder_declared_explicitly_is_allowed(tmp_path):
    """SILENT: `[0.01, 0.10, 0.25]` written out must not be refused by its own bar.

    Found by attacking the fix: `0.25 / 0.10` is the constant the bar is made
    of, so a strict `>` against a value computed the other way round would have
    refused mlkit's own ladder as too wide. It does not, and that is asserted
    rather than assumed.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration=f"fractions = {list(DEFAULT_FRACTIONS)}\n",
    )
    assert result.status is Status.PASS
    assert result.evidence["gain_10_to_25"] == result.evidence["gain_top_two"]


def test_positive_control_a_ladder_topping_out_below_mlkits_own_is_refused(tmp_path):
    """FIRES: `[0.01, 0.05, 0.10]` never asks E1's question at all.

    A curve still rising at 10% says nothing about whether the run you would
    actually buy is worth buying, and 10% is where the built-in ladder STARTS.
    Refused as a declaration, with a steep curve reported, so the refusal is of
    the ladder and not of the measurement.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.10, 0.05: 0.40, 0.10: 0.90",
        declaration="fractions = [0.01, 0.05, 0.10]\n",
    )
    assert result.status is Status.FAIL
    assert "SCALING_TOP_TOO_LOW" in result.reason
    assert "halt" not in result.evidence


def test_negative_control_a_ladder_topping_out_at_exactly_the_floor_is_allowed(tmp_path):
    """SILENT at the boundary: the test is `top < MIN_TOP_FRACTION`, so 0.25 itself
    measures. Otherwise the refusal above would also refuse mlkit's own ladder."""
    assert MIN_TOP_FRACTION == 0.25
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration=f"fractions = [0.01, 0.10, {MIN_TOP_FRACTION}]\n",
    )
    assert result.status is Status.PASS


def test_a_two_rung_ladder_is_refused(tmp_path):
    """FIRES: "a two-point curve cannot answer the question" is a refusal E1
    already makes. Declaring a ladder is not a way around it."""
    result = _run_e1(
        tmp_path, "0.10: 0.70, 0.25: 0.90", declaration="fractions = [0.10, 0.25]\n"
    )
    assert result.status is Status.FAIL
    assert "SCALING_MALFORMED" in result.reason
    assert "at least 3" in result.reason


def test_an_unordered_ladder_is_refused(tmp_path):
    """FIRES: E1 reads the LAST two rungs as the top of the ladder.

    `[0.25, 0.10, 0.01]` would silently take the verdict between 10% and 1% --
    a curve read backwards, whose gain is negative for every improving run and
    positive for every worsening one. Ordering is part of the contract, so it
    is checked rather than assumed.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="fractions = [0.25, 0.10, 0.01]\n",
    )
    assert result.status is Status.FAIL
    assert "not strictly increasing" in result.reason


def test_a_duplicated_rung_is_refused(tmp_path):
    """FIRES: `[0.01, 0.25, 0.25]` divides a gain of zero over the same point,
    which is a hard stop reported for a probe that measured one rung twice."""
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.25: 0.90",
        declaration="fractions = [0.01, 0.25, 0.25]\n",
    )
    assert result.status is Status.FAIL
    assert "not strictly increasing" in result.reason


def test_a_percentage_rung_is_refused(tmp_path):
    """FIRES: `fractions = [1, 10, 25]` is the percentage/fraction confusion.

    Read as fractions those are 100%, 1000% and 2500% of the data. The refusal
    says so, rather than reporting a curve missing every point.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="fractions = [1, 10, 25]\n",
    )
    assert result.status is Status.FAIL
    assert "must lie in (0, 1]" in result.reason


def test_a_boolean_rung_is_refused_on_type(tmp_path):
    """FIRES: `bool` is an `int`, so `true` would be a rung at 100% of the data."""
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="fractions = [0.01, 0.10, true]\n",
    )
    assert result.status is Status.FAIL
    assert "not a number" in result.reason


def test_a_non_finite_rung_is_refused_on_type(tmp_path):
    """FIRES: TOML has a literal `nan`, and `nan not in curve` makes every probe
    report a missing fraction rather than a malformed declaration."""
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="fractions = [0.01, 0.10, nan]\n",
    )
    assert result.status is Status.FAIL
    assert "finite" in result.reason


def test_a_ladder_that_is_not_an_array_is_refused(tmp_path):
    """FIRES: `fractions = 0.25` is a rung, not a ladder."""
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="fractions = 0.25\n",
    )
    assert result.status is Status.FAIL
    assert "SCALING_MALFORMED" in result.reason
    assert "float" in result.reason


def test_a_scaling_section_with_no_fractions_is_refused(tmp_path):
    """FIRES: an empty `[scaling]` is a declaration that declares nothing.

    Defaulting would be the quiet wrong answer: the repo wrote the section
    believing it had said something, and would read the built-in ladder's
    verdict as its own.
    """
    result = _run_e1(
        tmp_path,
        "0.01: 0.40, 0.10: 0.70, 0.25: 0.90",
        declaration="# nothing here yet\n",
    )
    assert result.status is Status.FAIL
    assert "fractions is absent" in result.reason


def test_positive_control_an_uncommitted_ladder_is_NA_not_a_silent_default(tmp_path):
    """FIRES as NA: a ladder in the working tree and on no ref.

    The same refusal D2's halt region gets, for the same reason: which two
    points a hard stop is measured between is the standard, and a standard in
    nobody's git history cannot be fetched by the reader it is quoted to.
    """
    result = _run_e1(
        tmp_path, "0.02: 0.40, 0.20: 0.70, 0.50: 0.82", declaration=_LADDER, commit=False
    )
    assert result.status is Status.NA
    assert "SCALING_UNDECLARED_AT_HEAD" in result.reason
    assert ".mlkit/repo.toml" in result.reason


def test_positive_control_a_binding_writing_its_own_ladder_at_import_cannot_move_it(
    tmp_path,
):
    """FIRES: the module body writes `[scaling]` before any read inside the check.

    Without the committed read this is a PASS on a ladder that appeared during
    the measurement, and the curve it rescues is flat between 10% and 25%.
    """
    repo = _repo(
        tmp_path,
        "scaling_probe",
        f'''
        import pathlib
        _p = pathlib.Path(__file__).parent / ".mlkit" / "repo.toml"
        _p.write_text(
            _p.read_text() + "\\n[{SCALING_SECTION}]\\nfractions = [0.01, 0.20, 0.50]\\n"
        )

        def scaling_probe():
            return {{0.01: 0.10, 0.10: 0.70, 0.20: 0.75, 0.25: 0.7015, 0.50: 0.95}}
        ''',
    )
    try:
        result = e1_scaling_probe(repo, _ctx(tmp_path))
    finally:
        repo.release()
    assert result.status is not Status.PASS
    assert result.evidence.get("to_fraction") != 0.50
