"""Prove mlkit's declared pytest timeout is ACTIVE, by execution not by reading config.

WHY THIS FILE EXISTS
--------------------
Measured 2026-08-28, before this change: ``resilient-mlkit/pyproject.toml``
declared neither ``pytest-timeout`` nor a ``timeout`` ini value, and
``.venv/bin/python -c "import pytest"`` raised ``ModuleNotFoundError`` — this
package's own venv could not run its own tests at all. Both are now declared
(``[project.optional-dependencies] test`` and ``[tool.pytest.ini_options]``).

A declaration is not the thing, though. ``timeout`` is an ini key pytest itself
does not know: with the plugin absent, pytest ignores it silently and the
config file reads as though a limit is in force while nothing bounds anything.
That is the same defect class this package exists to catch — a declared config
no stage consumes — and reading ``pyproject.toml`` cannot distinguish the two.
Only running can, so this file runs it.

The control structure here follows the one already proven in
``resilient-chokepoint/tests/test_pytest_timeout_active.py``; the pattern is
reused rather than reinvented, and the constants are this package's own.

WHAT IS ASSERTED
----------------
1. ``pytest_timeout`` imports AND the running session has it registered as the
   ``timeout`` plugin. Installed-but-unregistered enforces nothing.
2. The ``timeout`` ini value this session runs under is a positive number. The
   number is read from the config rather than repeated here, so this file does
   not become a second place it is declared.
3. POSITIVE CONTROL — a test that sleeps past its limit FAILS, and fails fast.
4. NEGATIVE CONTROL — a fast test under the same tiny limit PASSES. Without it,
   the positive control is equally consistent with "the runner fails
   everything".
5. FALSIFICATION CONTROL — with the plugin disabled, the same sleeping test is
   NOT killed. That is what an inert declaration looks like, and it is what
   this package measured on 2026-08-28.

The controls run pytest in a subprocess with their own rootdir and an empty
ini, so they cannot inherit this repo's options and cannot write into the tree.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

#: Limit the subprocess controls run under, in seconds. Small so the positive
#: control resolves fast; nothing in this repo's real suite uses it.
CONTROL_TIMEOUT_S = 1

#: How long the positive control's test sleeps. Comfortably past the limit, so
#: a pass cannot be an artifact of scheduling jitter.
CONTROL_SLEEP_S = 15

#: Wall-clock ceiling for the whole subprocess. If the plugin were inert the
#: sleeping test would run to completion; this bound sits far below that, so the
#: positive control cannot pass by simply waiting the sleep out.
SUBPROCESS_CEILING_S = 10


def test_pytest_timeout_is_installed_and_registered(pytestconfig: pytest.Config) -> None:
    """The plugin imports AND this very session has it registered."""
    import pytest_timeout  # noqa: PLC0415

    assert Path(pytest_timeout.__file__).is_file()
    assert pytestconfig.pluginmanager.hasplugin("timeout"), (
        "pytest_timeout is importable but pytest has not registered it as the "
        "'timeout' plugin, so the declared ini value enforces nothing."
    )


def test_declared_timeout_ini_value_is_a_positive_number(
    pytestconfig: pytest.Config,
) -> None:
    """The session this test runs in has a usable ``timeout`` ini value.

    ``getini`` raises for an option no plugin registered, so this call is
    itself a probe: it cannot succeed while the declaration is inert.
    """
    raw = pytestconfig.getini("timeout")
    assert raw not in (None, ""), (
        "no 'timeout' ini value is visible to this session. Either the plugin is "
        "not registered or the ini option was removed from pyproject.toml."
    )
    assert float(raw) > 0.0, f"declared timeout {raw!r} does not bound anything"


def _run_control(
    tmp_path: Path, body: str, *, disable_plugin: bool = False
) -> tuple[int, str, float]:
    """Run one throwaway test file in a subprocess under ``CONTROL_TIMEOUT_S``."""
    test_file = tmp_path / "test_control.py"
    test_file.write_text(body, encoding="utf-8")
    # An empty ini so the subprocess inherits none of this repo's options --
    # including its own timeout, which would otherwise mask the one under test.
    ini_file = tmp_path / "pytest.ini"
    ini_file.write_text("[pytest]\n", encoding="utf-8")
    argv = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-q",
        "-p",
        "no:cacheprovider",
        "-c",
        str(ini_file),
        "--rootdir",
        str(tmp_path),
    ]
    if disable_plugin:
        # No --timeout either: that flag is registered BY the plugin, so passing
        # it with the plugin off is a usage error rather than a control.
        argv += ["-p", "no:timeout"]
    else:
        argv.append(f"--timeout={CONTROL_TIMEOUT_S}")
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=SUBPROCESS_CEILING_S,
    )
    return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - started


def test_positive_control_a_sleeping_test_fails_on_timeout(tmp_path: Path) -> None:
    """A test that sleeps past the limit must FAIL, and must fail QUICKLY."""
    code, output, elapsed = _run_control(
        tmp_path,
        "import time\n\n\ndef test_sleeps_past_the_limit():\n"
        f"    time.sleep({CONTROL_SLEEP_S})\n",
    )
    assert code != 0, (
        "a test that slept past the declared limit exited 0. The timeout is inert.\n"
        f"{output}"
    )
    assert "timeout" in output.lower(), (
        "the run failed, but not with a timeout — so this proves nothing about the "
        f"timeout plugin.\n{output}"
    )
    assert elapsed < CONTROL_SLEEP_S, (
        f"the subprocess took {elapsed:.1f}s, at or past the {CONTROL_SLEEP_S}s sleep. "
        "It ran the sleep to completion instead of interrupting it, which is what an "
        "inert timeout looks like."
    )


def test_negative_control_a_fast_test_passes_under_the_same_limit(tmp_path: Path) -> None:
    """The same runner, the same tiny limit, a test that finishes: it must PASS."""
    code, output, _elapsed = _run_control(
        tmp_path,
        "def test_returns_immediately():\n    assert True\n",
    )
    assert code == 0, (
        "a test that returns immediately failed under the same timeout. The positive "
        f"control above cannot then be attributed to the timeout.\n{output}"
    )
    assert "timeout" not in output.lower().replace("--timeout", ""), (
        f"a fast test was reported as timing out:\n{output}"
    )


def test_falsification_control_without_the_plugin_the_sleeping_test_is_not_killed(
    tmp_path: Path,
) -> None:
    """With the plugin off, the SAME sleeping test runs on and hits our own ceiling.

    This is what mlkit looked like on 2026-08-28: no plugin, no ini key, and
    nothing bounding a wedged test. Without this control the positive control is
    consistent with "pytest kills long tests by itself", which it does not.
    """
    with pytest.raises(subprocess.TimeoutExpired):
        _run_control(
            tmp_path,
            "import time\n\n\ndef test_sleeps_past_the_limit():\n"
            f"    time.sleep({CONTROL_SLEEP_S})\n",
            disable_plugin=True,
        )
