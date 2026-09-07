"""E-M42 — the ``mlkit build:`` line names an identity, and the writer refuses a machine.

THE DEFECT, in two halves.

**Half one, the site.** ``identity.running_code_is_covered_or_reason`` is the
FOURTH producer of a reason string that lands in ``BuildIdentity.unavailable``
and is rendered by ``context_line()`` into the ``mlkit build:`` header of every
stamped report. M-5 repaired the other three and repaired ``context_line``
itself; it did not read this one, and
``test_p10_no_identity_field_names_a_directory_on_any_branch`` — whose name
claims *any* branch — enumerates ``digest_tree``, ``_vcs_of_installed_dist``
and ``one_tree_or_reason`` and stops there. So a test asserting the general
claim was passing over the one branch that broke it. Both raw absolute paths
are asserted gone here, and the omitted producer is added to the enumeration.

**Half two, the producer.** ``core.report.guarded_write`` wrote the four
stamped reports with a bare ``path.write_text``, so mlkit's own machine-path
refusal — shipped by M-5, and offered to every adopter — has never guarded the
artifact mlkit itself puts in eight repositories. The guard is now at the
write, and it is driven BOTH ways: a poisoned rendering must be refused with
the prior report preserved byte for byte, and a clean rendering must be written
exactly as before, because a guard that only ever refuses is a guard that
deletes reporting.

**What must NOT move**, and is asserted rather than assumed: the compared token
itself. Five repos parse ``- measured by mlkit: `X`` `` in a committed test,
so ``STAMP_PREFIX``, ``DIGEST_CHARS`` and the digest of a given tree are held
here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from resilient_mlkit.core import artifact, identity, report

ARMS = Path(__file__).resolve().parent.parent / "reports" / "E_M42_HEADER_CONTROL_ARMS.json"


# -- half one: the site ------------------------------------------------------


def test_the_omitted_reason_producer_names_no_directory(tmp_path):
    """The branch M-5 missed, forced on a tree whose files are not the running ones."""
    tree = tmp_path / "deep" / "deeper" / "src" / "resilient_mlkit"
    tree.mkdir(parents=True)
    (tree / "py.typed").write_text("")
    (tmp_path / "deep" / "deeper" / "pyproject.toml").write_text("[project]\n")

    reason = identity.running_code_is_covered_or_reason(tree)

    assert reason, "the running module is not under this tree, so this must refuse"
    assert artifact.machine_paths_in_text(reason) == [], reason
    assert str(tmp_path) not in reason
    # It still says WHAT happened, in words: the condition, not the location.
    assert "sourceless" in reason
    assert "`resilient_mlkit` (checkout)" in reason


def test_every_reason_producer_including_the_one_p10_omitted(tmp_path):
    """The enumeration `test_p10_..._on_any_branch` should always have had."""
    absent = tmp_path / "no-such-tree" / "resilient_mlkit"
    present = tmp_path / "src" / "resilient_mlkit"
    present.mkdir(parents=True)
    (present / "py.typed").write_text("")
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    reasons = [
        identity.digest_tree(absent)[2],
        identity._vcs_of_installed_dist(absent)[2],
        identity.one_tree_or_reason(absent),
        identity.running_code_is_covered_or_reason(present),
        identity.running_code_is_covered_or_reason(absent),
    ]
    for reason in reasons:
        assert artifact.machine_paths_in_text(reason) == [], reason
        assert str(tmp_path) not in reason


def test_a_file_inside_the_tree_is_named_relative_and_one_outside_is_named_in_words(tmp_path):
    root = tmp_path / "src" / "resilient_mlkit"
    (root / "core").mkdir(parents=True)
    inside = root / "core" / "identity.pyc"
    inside.write_text("")

    assert identity._within(inside, root) == "core/identity.pyc"

    outside = tmp_path / "elsewhere" / "identity.pyc"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    said = identity._within(outside, root)
    assert "OUTSIDE" in said
    assert str(tmp_path) not in said
    assert artifact.machine_paths_in_text(said) == []


def test_the_live_header_carries_no_machine_path():
    text = "\n".join(identity.header_lines())
    assert artifact.machine_paths_in_text(text) == [], text


# -- what must not move ------------------------------------------------------


def test_the_compared_token_is_unchanged_in_shape():
    """Five repos parse this line in a committed test. It is not this PR's to move."""
    assert identity.STAMP_PREFIX == "- measured by mlkit: "
    assert identity.DIGEST_CHARS == 12
    assert identity.UNKNOWN_DIGEST == "unknown"
    ident = identity.build_identity()
    assert ident.stamp_line() == f"{identity.STAMP_PREFIX}`{ident.stamp}`"
    assert identity.header_lines()[0] == ident.stamp_line()


def test_the_digest_of_a_fixed_tree_is_the_length_framed_sha256_it_always_was(tmp_path):
    """Recomputed here from the documented construction, not from the function."""
    root = tmp_path / "resilient_mlkit"
    (root / "core").mkdir(parents=True)
    (root / "core" / "a.py").write_bytes(b"alpha")
    (root / "py.typed").write_bytes(b"")

    h = hashlib.sha256()
    for rel, data in (("core/a.py", b"alpha"), ("py.typed", b"")):
        h.update(len(rel.encode()).to_bytes(8, "big"))
        h.update(rel.encode())
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)

    sha, files, unavailable = identity.digest_tree(root)
    assert (sha, files, unavailable) == (h.hexdigest(), 2, "")


# -- half two: the producer, driven both ways --------------------------------


def _clean_report() -> str:
    return "\n".join(["# Readiness report — fixture", "", *identity.header_lines(), ""])


def test_p2_silent_a_clean_report_is_written_exactly_as_before(tmp_path):
    path = tmp_path / "reports" / "readiness.md"
    text = _clean_report()

    result = report.guarded_write(path, text, probe=None, depends_on_bindings=False)

    assert result.written is True
    assert result.preserved is False
    assert path.read_text() == text
    assert result.refusal_path is None


def test_p1_fires_a_report_naming_a_machine_is_refused_and_the_prior_is_preserved(tmp_path):
    path = tmp_path / "reports" / "readiness.md"
    path.parent.mkdir(parents=True)
    prior_text = "# Readiness report — fixture\n\nmeasured, and still here\n"
    path.write_text(prior_text)
    prior_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    poisoned = (
        "# Readiness report — fixture\n\n"
        "- mlkit build: sha256 `abc` over 33 shipped file(s) in "
        f"`{tmp_path}/mlkit-inst/resilient_mlkit`\n"
    )

    result = report.guarded_write(path, poisoned, probe=None, depends_on_bindings=False)

    assert result.written is False
    assert result.preserved is True
    # Byte for byte. "we did not mean to change it" is not evidence.
    assert path.read_text() == prior_text
    assert result.sha256 == prior_sha == result.prior_sha256
    assert result.refusal_path is not None
    assert result.refusal_path.name.endswith(report.MACHINE_PATH_SUFFIX)
    assert "name an absolute directory" in result.reason


def test_p1_the_refusal_record_names_positions_and_never_the_token(tmp_path):
    """The file objecting to a machine path must not itself carry one."""
    path = tmp_path / "reports" / "readiness.md"
    offender = f"{tmp_path}/mlkit-inst/resilient_mlkit"
    poisoned = f"# R\n\n- mlkit build: in `{offender}`\n"

    result = report.guarded_write(path, poisoned, probe=None, depends_on_bindings=False)

    assert result.refusal_path is not None
    recorded = result.refusal_path.read_text()
    assert offender not in recorded
    assert artifact.machine_paths_in_text(recorded) == []
    # It is still USEFUL: the position is there, so the offender is findable.
    offenders = artifact.machine_paths_in_text(poisoned)
    assert offenders
    assert offenders[0][0] in recorded
    assert "not a report" in recorded


def test_p1_fires_even_when_the_environment_is_measurable_and_the_report_is_static(tmp_path):
    """The two refusals are independent; neither is a special case of the other."""
    path = tmp_path / "reports" / "fabricated_defaults.md"
    poisoned = f"# R10\n\n| `{tmp_path}/x` | 1 |\n"

    result = report.guarded_write(
        path, poisoned, probe=None, depends_on_bindings=False, nonce="n", git_sha="s"
    )

    assert result.written is False
    assert not path.exists(), "nothing may be written in the report's own name"
    assert result.refusal_path is not None and result.refusal_path.exists()


def test_the_stamped_report_writers_do_not_bypass_the_guard():
    """Every stamped report goes through guarded_write, or the guard guards nothing."""
    readiness = (
        Path(identity.__file__).resolve().parent.parent / "checks" / "readiness.py"
    ).read_text()
    assert "report.guarded_write(" in readiness
    assert ".write_text(" not in readiness, (
        "a stamped report written with a bare write_text is outside the E-M42 guard"
    )


# -- the driven arms, read back so they cannot drift from the code -----------


@pytest.mark.skipif(not ARMS.is_file(), reason="control artifact not driven in this tree")
def test_the_driven_arms_agree_and_the_not_dead_arm_actually_failed():
    record = json.loads(ARMS.read_text())
    arms = {a["arm"]: a for a in record["arms"]}

    assert record["all_required_arms_agree"] is True

    # A1a / A1b: two directories, one header, no machine path.
    for name in ("A1a", "A1b"):
        assert arms[name]["headers_byte_identical"] is True
        assert arms[name]["machine_path_tokens"] == 0
    assert arms["A1b"]["condition"].startswith("sourceless")

    # A2: the identity still tells two builds apart.
    assert arms["A2"]["headers_byte_identical"] is False
    assert arms["A2"]["stamp_here"] != arms["A2"]["stamp_there"]

    # A3: with the fix reverted, A1b's assertion fails — on BOTH counts.
    assert arms["A3"]["headers_byte_identical"] is False
    assert arms["A3"]["machine_path_tokens"] > 0

    assert artifact.machine_paths_in_text(json.dumps(record)) == []
