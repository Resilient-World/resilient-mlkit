"""The seed `.mlkit/repo.toml` an adopter copies must not refuse the adopter.

`spine/mlkit/repo.toml` is a SEED file: written once into a new repo and then
owned by it (`core/spine.py`, the "written once if absent, then owned by the
repo and NEVER overwritten" list). Nothing else in the suite drives it, and it
is the one file in the tree whose bytes become another repo's CONFIGURATION
rather than another repo's documentation.

That gap had a cost, found by driving the seed rather than reading it. The
branch that made D2's halt region and E1's ladder declarable added two sections
to the seed with their KEYS commented out and their HEADERS live:

    [scaling]
    # fractions = [0.01, 0.10, 0.25]

`read_fraction_ladder` refuses a `[scaling]` table with no `fractions` -- by
design, and `test_a_scaling_section_with_no_fractions_is_refused` pins that
refusal with a written rationale. So a repo that adopted the seed verbatim and
bound `scaling_probe` got

    E1 FAIL  SCALING_MALFORMED: [scaling] fractions is absent

on a curve E1 never read: a FAIL ON CONTRACT, which is the exact failure mode
round 8's adjudication (§2.4) recorded for fray and which the declarable ladder
exists to remove. `[placebo]` was milder and wrong in the same direction --
`region.declared` is True for an empty table, so a repo that declared nothing
had `placebo_declared_in` in every D2 verdict's evidence.

Both headers are commented out now. This file is the control that keeps them
that way: it builds a repo out of the REAL seed bytes, wires the two bindings,
commits, and asserts that D2 and E1 land on mlkit's built-in rule -- the same
verdict the same bindings get in a repo with no seed at all.

The comparison operand is not a copy of the expectation: both halves of every
assertion below are computed in this test, one from the seed file on disk and
one from a minimal config built here, and they are required to agree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import d2_placebo_test
from resilient_mlkit.checks.economics import e1_scaling_probe
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

SEED = Path(__file__).resolve().parent.parent / "spine" / "mlkit" / "repo.toml"

_SERIAL = iter(range(10_000))

#: A probe and a placebo that both PASS under mlkit's built-in rule, so that any
#: refusal this test sees comes from the seed and not from the figures. The
#: curve carries all three built-in rungs and rises 8.69% across the top step;
#: the placebo's interval contains zero and is narrower than the reference.
_BINDINGS_BODY = """
def placebo_test():
    return {
        "estimate": -0.2,
        "ci_low": -4.0,
        "ci_high": 3.6,
        "reference_effect": 22.81138510740044,
        "run_id": "seed-adoptability",
    }


def scaling_probe():
    return {0.01: -190.0, 0.10: -151.29137, 0.25: -138.13969}
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _repo_from(tmp_path: Path, config_text: str, name: str) -> Repo:
    """A committed git repo whose `.mlkit/repo.toml` is `config_text`."""
    root = tmp_path / name
    (root / ".mlkit").mkdir(parents=True)
    module = f"seed_bindings_{next(_SERIAL)}"
    (root / f"{module}.py").write_text(_BINDINGS_BODY)
    text = config_text.replace(
        "[bindings]\n",
        f'[bindings]\nplacebo_test = "{module}:placebo_test"\n'
        f'scaling_probe = "{module}:scaling_probe"\n',
        1,
    )
    assert f'"{module}:placebo_test"' in text, "the [bindings] anchor was not found"
    (root / ".mlkit" / "repo.toml").write_text(text)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "adopted the seed")
    return Repo(name=name, path=root)


def _verdicts(tmp_path: Path, config_text: str, name: str):
    repo = _repo_from(tmp_path, config_text, name)
    ctx = RunContext(nonce="seed-test", root=tmp_path, offline=True)
    try:
        return d2_placebo_test(repo, ctx), e1_scaling_probe(repo, ctx)
    finally:
        repo.release()


#: The smallest config that wires the same two bindings and declares nothing
#: else. This is the OTHER OPERAND: whatever the seed produces must equal what
#: this produces, and neither side is a literal typed into an assertion.
_MINIMAL = '[repo]\nname = "minimal"\n\n[bindings]\n'


def test_the_seed_declares_neither_optional_section_as_a_live_table(tmp_path):
    """FIRES on a live `[placebo]` or `[scaling]` header in the seed.

    Read as TOML, not as text: a commented header is absent from the parsed
    document, which is the only fact the checks act on.
    """
    import tomllib

    document = tomllib.loads(SEED.read_text())
    live = sorted(s for s in ("placebo", "scaling") if s in document)
    assert live == [], (
        f"spine/mlkit/repo.toml declares {live} as a live table with its keys "
        "commented out. An adopter copying this seed inherits a declaration it "
        "did not make: [scaling] is refused outright (SCALING_MALFORMED) and "
        "[placebo] rides in every D2 verdict's evidence as placebo_declared_in. "
        "Comment the header out with the keys, or uncomment both together."
    )


def test_a_repo_adopting_the_seed_verbatim_gets_mlkits_built_in_verdicts(tmp_path):
    """FIRES if the seed changes a verdict a bare config would not change.

    This is the control that would have caught the defect: it drives the seed's
    real bytes through the same two checks and requires them to agree, status
    and reason, with the minimal config.
    """
    seed_d2, seed_e1 = _verdicts(tmp_path, SEED.read_text(), "seeded")
    bare_d2, bare_e1 = _verdicts(tmp_path, _MINIMAL, "bare")

    assert (seed_d2.status, seed_d2.reason) == (bare_d2.status, bare_d2.reason), (
        f"seed D2 {seed_d2.status} {seed_d2.reason!r} != bare D2 "
        f"{bare_d2.status} {bare_d2.reason!r}"
    )
    assert (seed_e1.status, seed_e1.reason) == (bare_e1.status, bare_e1.reason), (
        f"seed E1 {seed_e1.status} {seed_e1.reason!r} != bare E1 "
        f"{bare_e1.status} {bare_e1.reason!r}"
    )
    # Both sides PASS, so the equality above is not two identical refusals
    # agreeing with each other -- the shape a "same verdict" assertion degrades
    # into once something starts failing upstream of both.
    assert seed_d2.status is Status.PASS, seed_d2.reason
    assert seed_e1.status is Status.PASS, seed_e1.reason


def test_positive_control_a_live_scaling_header_in_the_seed_is_caught(tmp_path):
    """CHECK-NOT-DEAD: re-arm the defect and both controls above must fire.

    Without this, `test_a_repo_adopting_the_seed_verbatim...` is consistent with
    a test that passes because nothing in the seed can ever matter.
    """
    import tomllib

    remutated = SEED.read_text().replace(
        "# [scaling]\n# fractions = [0.01, 0.10, 0.25]",
        "[scaling]\n# fractions = [0.01, 0.10, 0.25]",
        1,
    )
    assert "scaling" in tomllib.loads(remutated), "the remutation did not take"

    seed_d2, seed_e1 = _verdicts(tmp_path, remutated, "remutated")
    bare_d2, bare_e1 = _verdicts(tmp_path, _MINIMAL, "bare2")

    assert seed_e1.status is Status.FAIL
    assert "SCALING_MALFORMED" in seed_e1.reason
    assert "fractions is absent" in seed_e1.reason
    assert bare_e1.status is Status.PASS, bare_e1.reason
    # D2 is unmoved by the scaling remutation; the pair is E1's alone.
    assert (seed_d2.status, seed_d2.reason) == (bare_d2.status, bare_d2.reason)


def test_positive_control_a_live_placebo_header_in_the_seed_is_caught(tmp_path):
    """CHECK-NOT-DEAD for the milder half: an empty `[placebo]` still marks."""
    import tomllib

    remutated = SEED.read_text().replace(
        '# [placebo]\n# estimand   = "skill against the persistence floor, lb/ac"',
        '[placebo]\n# estimand   = "skill against the persistence floor, lb/ac"',
        1,
    )
    assert "placebo" in tomllib.loads(remutated), "the remutation did not take"

    seed_d2, _ = _verdicts(tmp_path, remutated, "remutated_p")
    bare_d2, _ = _verdicts(tmp_path, _MINIMAL, "bare3")

    # Same VERDICT -- the empty table is the default region -- but the evidence
    # now claims a declaration the adopter never made, and that is the defect.
    assert seed_d2.status is bare_d2.status is Status.PASS
    assert "placebo_declared_in" in seed_d2.evidence
    assert "placebo_declared_in" not in bare_d2.evidence
