"""Controls for the environment probe and the report-write refusal.

The incident these close: a Python 3.14 interpreter with no numpy regenerated
``reports/readiness.md`` in at least four repos, replacing measured PASSes with
ModuleNotFoundError (resilient-chokepoint ``docs/ESCALATIONS.md`` E-019). Every
individual result in that run was honest -- the checks really could not run --
and the composite was still a lie, because a readiness report reads as a
statement about the repo when that one was a statement about the shell.

Two claims are under test, and each needs both halves:

* The probe fires on a missing THIRD-PARTY module and stays silent on a
  missing REPO-LOCAL one. Getting that backwards would be worse than having no
  probe at all: it would let "environment unmeasurable" swallow genuine repo
  defects, which is the same overwrite with the sign flipped.
* The writer preserves the prior report BYTE FOR BYTE when the environment is
  unmeasurable, and writes normally when it is not. Preservation is asserted
  on sha256, because "we did not mean to change it" is not evidence.
"""

from __future__ import annotations

import hashlib
import textwrap

from resilient_mlkit.core import environment, report
from resilient_mlkit.core.repo import Repo

BINDING_TOML = """\
[repo]
name = "fixture"

[bindings]
provenance = "{module}:provenance"
"""


def make_repo(tmp_path, module_name: str, body: str, *, binding: str | None = None) -> Repo:
    """A minimal repo declaring one binding that points at ``module_name``."""
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mlkit" / "repo.toml").write_text(
        BINDING_TOML.format(module=binding or module_name)
    )
    (tmp_path / f"{module_name}.py").write_text(textwrap.dedent(body))
    return Repo(name="fixture", path=tmp_path)


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


MEASURED_REPORT = "# Readiness report — resilient-fixture\n\n| R5 | PASS | measured |\n"


# ---------------------------------------------------------------------------
# The probe
# ---------------------------------------------------------------------------


def test_positive_a_missing_third_party_module_makes_the_environment_unmeasurable(tmp_path):
    """POSITIVE. The incident: the interpreter, not the repo, is what is broken.

    ``numpy`` is not a directory in any of these repos, so its absence is a
    fact about the interpreter. The probe reaches that conclusion from the
    module's own name and the repo's own layout -- there is no hardcoded list
    of "real" packages to go stale.
    """
    repo = make_repo(
        tmp_path, "mlkit_bindings_missing_dep",
        """
        import numpy_that_does_not_exist_xyz  # noqa: F401

        def provenance():
            return {}
        """,
    )
    try:
        probe = environment.probe(repo)
    finally:
        repo.release()

    assert probe.verdict == environment.UNMEASURABLE
    assert probe.measurable is False
    assert probe.missing_modules == ("numpy_that_does_not_exist_xyz",)
    assert probe.bindings["provenance"].startswith("missing:")
    assert "cannot import" in probe.reason


def test_negative_a_working_environment_is_measurable(tmp_path):
    """NEGATIVE. The binding imports; nothing is refused."""
    repo = make_repo(
        tmp_path, "mlkit_bindings_ok",
        """
        def provenance():
            return {"train": {"real": 1}}
        """,
    )
    try:
        probe = environment.probe(repo)
    finally:
        repo.release()

    assert probe.verdict == environment.MEASURABLE
    assert probe.measurable is True
    assert probe.bindings == {"provenance": "ok"}
    assert probe.missing_modules == ()


def test_negative_a_missing_REPO_LOCAL_module_is_a_repo_defect_not_an_excuse(tmp_path):
    """NEGATIVE, and the one that decides whether this guard is safe to have.

    ``import src.data.absent`` failing is the REPO's defect. If the probe
    called that an unmeasurable environment, every genuine import defect in
    the portfolio would silently stop its report from being regenerated and
    the stale report would keep reading PASS. The guard must protect
    measurements from bad interpreters without protecting repos from
    themselves.
    """
    (tmp_path / "src" / "data").mkdir(parents=True)
    repo = make_repo(
        tmp_path, "mlkit_bindings_repo_defect",
        """
        from src.data import absent_module  # noqa: F401

        def provenance():
            return {}
        """,
    )
    try:
        probe = environment.probe(repo)
    finally:
        repo.release()

    assert probe.verdict == environment.MEASURABLE
    assert probe.measurable is True
    assert probe.missing_modules == ()
    assert probe.repo_defects == ("provenance",)
    assert probe.bindings["provenance"].startswith("repo-defect:")


def test_negative_no_bindings_declared_is_undeclared_not_unmeasurable(tmp_path):
    """NEGATIVE. Nothing was imported, so nothing is concluded — and reports still write.

    A repo with no bindings produces a report made of "binding not declared"
    NAs, and a working interpreter and a broken one agree on those. Refusing
    to write it would make every unwired repo permanently unreportable.
    """
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text('[repo]\nname = "fixture"\n')
    probe = environment.probe(Repo(name="fixture", path=tmp_path))

    assert probe.verdict == environment.UNDECLARED
    assert probe.measurable is True


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------


def test_positive_an_unmeasurable_environment_preserves_the_prior_report(tmp_path):
    """POSITIVE. The measured report survives the broken interpreter, byte for byte."""
    out = tmp_path / "reports" / "readiness.md"
    out.parent.mkdir(parents=True)
    out.write_text(MEASURED_REPORT)
    before = sha(out)

    probe = environment.EnvironmentProbe(
        environment.UNMEASURABLE,
        "this interpreter (python 3.14.6) cannot import numpy",
        {"provenance": "missing:numpy"},
        ("numpy",),
        (),
        "3.14.6",
    )
    written = report.guarded_write(
        out, "# Readiness report\n\n| R5 | FAIL | ModuleNotFoundError: numpy |\n",
        probe=probe, depends_on_bindings=True, nonce="test-nonce", git_sha="deadbee",
    )

    assert written.written is False
    assert written.preserved is True
    # The claim is byte-identity, so the evidence is a digest, not an intention.
    assert sha(out) == before
    assert written.sha256 == written.prior_sha256 == before
    assert out.read_text() == MEASURED_REPORT

    # The refusal is recorded beside the report, under its own name. A refusal
    # written into `readiness.md` would be the very failure being closed,
    # wearing an apology.
    refusal = tmp_path / "reports" / "readiness.UNMEASURABLE.md"
    assert written.refusal_path == refusal
    body = refusal.read_text()
    assert "not a report" in body.lower()
    assert "UNMEASURABLE" in body
    assert "numpy" in body
    assert before in body  # the digest of what was preserved
    assert "python 3.14.6" in body


def test_positive_with_no_prior_report_nothing_is_written_in_its_place(tmp_path):
    """POSITIVE. Absence is honest; a report full of import errors is not.

    There was nothing to destroy, and that is not a reason to write a
    non-measurement into the filename a measurement is read from.
    """
    out = tmp_path / "reports" / "readiness.md"
    probe = environment.EnvironmentProbe(
        environment.UNMEASURABLE, "cannot import numpy", {}, ("numpy",), (), "3.14.6"
    )
    written = report.guarded_write(
        out, "# nonsense\n", probe=probe, depends_on_bindings=True
    )

    assert written.written is False
    assert out.exists() is False
    assert written.prior_sha256 is None
    assert (tmp_path / "reports" / "readiness.UNMEASURABLE.md").is_file()


def test_negative_a_measurable_environment_writes_normally(tmp_path):
    """NEGATIVE. The guard must not be a brake on the working case."""
    out = tmp_path / "reports" / "readiness.md"
    out.parent.mkdir(parents=True)
    out.write_text(MEASURED_REPORT)

    probe = environment.EnvironmentProbe(
        environment.MEASURABLE, "python 3.12.13 imported all 1 declared binding(s)",
        {"provenance": "ok"}, (), (), "3.12.13",
    )
    written = report.guarded_write(
        out, "# fresh\n", probe=probe, depends_on_bindings=True
    )

    assert written.written is True
    assert written.preserved is False
    assert out.read_text() == "# fresh\n"
    assert (tmp_path / "reports" / "readiness.UNMEASURABLE.md").exists() is False


def test_negative_a_static_analysis_report_is_never_guarded(tmp_path):
    """NEGATIVE. R10 and R11 parse source; they import nothing.

    Their findings are exactly as valid from a numpy-less interpreter as from
    a working one, so refusing them would suppress a real measurement in the
    name of protecting measurements. The caller states which kind of report it
    is, at the call site, in one argument.
    """
    out = tmp_path / "reports" / "fabricated_targets.md"
    probe = environment.EnvironmentProbe(
        environment.UNMEASURABLE, "cannot import numpy", {}, ("numpy",), (), "3.14.6"
    )
    written = report.guarded_write(
        out, "# measured by ast\n", probe=probe, depends_on_bindings=False
    )

    assert written.written is True
    assert out.read_text() == "# measured by ast\n"


def test_negative_an_absent_probe_writes(tmp_path):
    """NEGATIVE. No evidence of a broken environment is not evidence of one."""
    out = tmp_path / "reports" / "readiness.md"
    written = report.guarded_write(
        out, "# fresh\n", probe=None, depends_on_bindings=True
    )
    assert written.written is True
    assert out.read_text() == "# fresh\n"


# ---------------------------------------------------------------------------
# End to end, through R8 itself
# ---------------------------------------------------------------------------


def test_r8_returns_NA_and_preserves_when_the_environment_cannot_measure(tmp_path):
    """The two facts kept apart, in the check that writes the file.

    R8 reports NA, not FAIL. "This environment cannot measure this repo" is
    not a verdict on the repo, and recording it as one would put a red mark on
    eight repos every time somebody ran mlkit from the wrong shell — which is
    how a gate stops being read.
    """
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r8_report
    from resilient_mlkit.core.result import CheckResult, Status

    repo = make_repo(
        tmp_path, "mlkit_bindings_e2e",
        """
        import numpy_that_does_not_exist_xyz  # noqa: F401

        def provenance():
            return {}
        """,
    )
    out = tmp_path / "reports" / "readiness.md"
    out.parent.mkdir(parents=True)
    out.write_text(MEASURED_REPORT)
    before = sha(out)

    ctx = RunContext(nonce="test-nonce", root=tmp_path)
    ctx.prior["R5"] = CheckResult.failed(
        "R5", "readiness", "provenance raised ModuleNotFoundError: numpy"
    )
    try:
        result = r8_report(repo, ctx)
    finally:
        repo.release()

    assert result.status is Status.NA
    assert "refused" in result.reason
    assert result.evidence["environment"]["verdict"] == environment.UNMEASURABLE
    assert sha(out) == before
    assert out.read_text() == MEASURED_REPORT
    assert (tmp_path / "reports" / "readiness.UNMEASURABLE.md").is_file()


def test_r8_writes_when_the_environment_is_measurable(tmp_path):
    """The matched half: a working interpreter regenerates the report as before."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r8_report
    from resilient_mlkit.core.result import CheckResult, Status

    repo = make_repo(
        tmp_path, "mlkit_bindings_e2e_ok",
        """
        def provenance():
            return {"train": {"real": 1}}
        """,
    )
    out = tmp_path / "reports" / "readiness.md"
    out.parent.mkdir(parents=True)
    out.write_text(MEASURED_REPORT)

    ctx = RunContext(nonce="test-nonce", root=tmp_path)
    ctx.prior["R5"] = CheckResult.passed("R5", "readiness", {"val": {"real": 12}})
    try:
        result = r8_report(repo, ctx)
    finally:
        repo.release()

    assert result.status is Status.PASS
    assert result.evidence["environment"]["verdict"] == environment.MEASURABLE
    assert "R5" in out.read_text()
    assert out.read_text() != MEASURED_REPORT
    assert (tmp_path / "reports" / "readiness.UNMEASURABLE.md").exists() is False
