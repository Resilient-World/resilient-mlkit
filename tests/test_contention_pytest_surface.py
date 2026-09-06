"""The pytest surface, proved by EXECUTION rather than by reading the plugin.

The one property that makes this plugin safe to install in eight repositories
is that it cannot make a red suite green. That is a claim about what pytest
does when the plugin is loaded, and the only thing that can settle it is
running pytest twice — with the plugin and without it — over the same test file
and comparing the outcomes.

So every control here runs a throwaway test file in a subprocess with its own
rootdir and an empty ini, exactly as ``tests/test_pytest_timeout_active.py``
does, so that nothing inherits this repo's options and nothing writes into this
tree.

WHAT IS ASSERTED
----------------
1. The marker is REGISTERED: a marked test runs clean under ``--strict-markers``,
   which rejects any marker no plugin declared.
2. The session's contention line appears at the TOP of the log (a killed run
   never reaches the summary, and a killed run is exactly the one somebody
   needs to date later).
3. The same line, with the whole session's reading, appears at the BOTTOM.
4. **A failing wall-clock budget still FAILS with the plugin loaded**, with no
   skip and no xfail — and the outcome is IDENTICAL to the same file run
   without the plugin.
5. A passing test still passes, so 4 is not "the plugin fails everything".
6. The fixture hands a test a real span, and the record reaches the report's
   ``user_properties`` where a JUnit consumer can read it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN = "resilient_mlkit.pytest_contention"

#: Wall-clock ceiling for each control subprocess. These files contain one or
#: two trivial tests; anything near this bound is wedged, not working.
SUBPROCESS_CEILING_S = 120

FAILING_BUDGET_TEST = """
import time

import pytest


@pytest.mark.wall_clock_budget(0.01)
def test_a_budget_that_is_missed():
    time.sleep(0.05)
    assert False, "the budget was missed and this test says so"
"""

PASSING_TEST = """
def test_returns_immediately():
    assert True
"""

FIXTURE_TEST = """
from resilient_mlkit.core.contention import classify


def test_the_fixture_hands_over_a_real_span(wall_clock_budget):
    with wall_clock_budget(60.0, "a fast child") as span:
        pass
    record = span.record
    assert record.wall_s >= 0.0
    assert record.what == "a fast child"
    print("SUPPORTS", classify(record).value)
    print("ONELINE", record.one_line())
"""


def _run(
    tmp_path: Path, body: str, *, with_plugin: bool, declare_marker: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run one throwaway test file, with or without the plugin registered.

    ``declare_marker`` puts the marker in the throwaway INI instead of getting
    it from the plugin. It exists for exactly one control — the A5 comparison
    below — where both arms must have IDENTICAL configuration so that the only
    difference between them is whether the plugin is loaded. Without it the
    no-plugin arm errors at COLLECTION on the unknown marker (exit 2), and a
    comparison of 1 against 2 would prove nothing about verdicts.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    test_file = tmp_path / "test_control.py"
    test_file.write_text(body, encoding="utf-8")
    ini_file = tmp_path / "pytest.ini"
    # --strict-markers in the throwaway ini too: an unregistered marker must be
    # an error here, or assertion 1 proves nothing.
    ini = "[pytest]\naddopts = --strict-markers\n"
    if declare_marker:
        ini += "markers =\n    wall_clock_budget(seconds): declared in the ini for this control\n"
    ini_file.write_text(ini, encoding="utf-8")
    argv = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-p",
        "no:cacheprovider",
        "-c",
        str(ini_file),
        "--rootdir",
        str(tmp_path),
        "-rA",
    ]
    if with_plugin:
        argv += ["-p", PLUGIN]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=SUBPROCESS_CEILING_S,
    )


def test_the_marker_is_registered_so_strict_markers_accepts_it(tmp_path: Path) -> None:
    """An unregistered marker is an error under --strict-markers, by design."""
    proc = _run(tmp_path, PASSING_TEST.replace(
        "def test_returns_immediately",
        "import pytest\n\n\n@pytest.mark.wall_clock_budget(1.0)\ndef test_returns_immediately",
    ), with_plugin=True)
    output = proc.stdout + proc.stderr
    assert "not found in `markers`" not in output, output
    assert proc.returncode == 0, output


def test_the_marker_is_NOT_known_without_the_plugin(tmp_path: Path) -> None:
    """The falsification control for the test above.

    Without it, "the marker is registered" is equally consistent with
    "--strict-markers is not in force in the throwaway ini".
    """
    proc = _run(tmp_path, PASSING_TEST.replace(
        "def test_returns_immediately",
        "import pytest\n\n\n@pytest.mark.wall_clock_budget(1.0)\ndef test_returns_immediately",
    ), with_plugin=False)
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output
    assert "'wall_clock_budget' not found in `markers`" in output, output


def test_the_contention_line_is_printed_at_the_top_of_the_log(tmp_path: Path) -> None:
    """A run that is killed mid-way never reaches the summary."""
    proc = _run(tmp_path, PASSING_TEST, with_plugin=True)
    output = proc.stdout + proc.stderr
    assert "mlkit contention:" in output, output
    assert "cpu, load1" in output, output
    assert "VOID" in output, output


def test_the_whole_session_record_is_printed_at_the_bottom(tmp_path: Path) -> None:
    proc = _run(tmp_path, PASSING_TEST, with_plugin=True)
    output = proc.stdout + proc.stderr
    assert "mlkit contention record" in output, output
    assert "session wall" in output, output
    assert "reaped children" in output, output
    assert "run arms SEQUENTIALLY" in output or "SEQUENTIALLY" in output, output


def test_A5_a_failing_budget_still_fails_and_the_outcome_is_unchanged(
    tmp_path: Path,
) -> None:
    """THE control this plugin exists to survive.

    Same file, run twice: once with the plugin and once without. The outcome
    must be identical, and it must be a FAILURE. If the plugin can turn this
    red into anything else — a pass, a skip, an xfail — then the fleet's
    landing rule ("nothing only-on-branch") would compare a real regression on
    one arm against a skip on the other and see agreement.
    """
    without = _run(
        tmp_path / "a",
        with_plugin=False,
        body=FAILING_BUDGET_TEST,
        declare_marker=True,
    )
    with_ = _run(
        tmp_path / "b",
        with_plugin=True,
        body=FAILING_BUDGET_TEST,
        declare_marker=True,
    )

    assert without.returncode != 0, without.stdout + without.stderr
    assert with_.returncode == without.returncode, (
        "loading the plugin changed the process exit code for a failing "
        f"budget test: {without.returncode} -> {with_.returncode}\n"
        + with_.stdout
        + with_.stderr
    )
    output = with_.stdout + with_.stderr
    assert "1 failed" in output, output
    for softer in (" skipped", " xfailed", " xpassed"):
        assert softer not in output, f"the plugin softened the verdict:\n{output}"


def test_A5_a_passing_test_still_passes(tmp_path: Path) -> None:
    """So the control above is not "the plugin fails everything"."""
    proc = _run(tmp_path, PASSING_TEST, with_plugin=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 passed" in proc.stdout + proc.stderr


def test_the_fixture_hands_a_test_a_real_span(tmp_path: Path) -> None:
    proc = _run(tmp_path, FIXTURE_TEST, with_plugin=True)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "SUPPORTS PASS" in output, output
    assert "ONELINE CONTENTION a fast child" in output, output


def test_the_record_reaches_the_report_as_a_user_property(tmp_path: Path) -> None:
    """A JUnit consumer can read the record without parsing terminal text."""
    test_file = tmp_path / "test_control.py"
    test_file.write_text(FAILING_BUDGET_TEST, encoding="utf-8")
    ini_file = tmp_path / "pytest.ini"
    ini_file.write_text("[pytest]\naddopts = --strict-markers\n", encoding="utf-8")
    xml = tmp_path / "report.xml"
    subprocess.run(
        [
            sys.executable, "-m", "pytest", str(test_file), "-p", "no:cacheprovider",
            "-c", str(ini_file), "--rootdir", str(tmp_path), "-p", PLUGIN,
            f"--junitxml={xml}",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=SUBPROCESS_CEILING_S,
    )
    assert xml.is_file()
    text = xml.read_text(encoding="utf-8")
    assert "mlkit_contention" in text, text
    assert "mlkit_contention_supports" in text, text
