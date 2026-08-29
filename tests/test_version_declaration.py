"""The declared version and the newest CHANGELOG heading must agree (E-M08).

The defect this pins, measured on this repo: `v0.3.0` was tagged at a commit
whose `pyproject.toml` and `cli.__version__` both still read `0.2.0`, so every
artifact `mlkit portfolio` and `mlkit spine` generated from that tag stamped
`"mlkit_version": "0.2.0"`. Nothing was wrong with any single file. The version
was written down in three places, each copy was individually plausible, and
nothing in the repo ever compared them — which is the same shape as a metric
with three definitions and no reconciliation.

Two things are held here, and they are different:

* **One literal.** `pyproject.toml` reads the version through
  `[tool.setuptools.dynamic]` and `cli` imports it, so `resilient_mlkit
  .__version__` is the only place the number is written. A second literal
  anywhere is the defect returning, and `second_version_literals()` finds it.
* **The literal agrees with the release notes.** A bump with no CHANGELOG entry
  is a release nobody can read, and a CHANGELOG entry ahead of the code is a
  release note for a version that does not exist. `newest_changelog_version()`
  reads the top heading and the suite compares it.

The second is deliberately strict about the shape the repo used to use: a
newest heading reading `## Unreleased`, retitled to a version by hand after the
tag is cut, is rejected. That retitling step is precisely the step that went
missing, and a control that tolerates the shape of the incident is not a
control.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

import resilient_mlkit
from resilient_mlkit import cli

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"

#: Modules that must NOT carry a version literal of their own. `__init__` is
#: absent from this list because `__init__` is where the one literal lives.
NO_LITERAL_MODULES = ("cli.py", "portfolio.py", "fleet_adapters.py")

#: A top-level CHANGELOG heading, e.g. `## v0.3.1 — 2026-08-28`.
_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)

#: A version heading specifically. Anything else at the top -- `Unreleased`,
#: `Next`, a date alone -- is not a version and is reported as such.
_VERSION_HEADING = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)\b")

#: A module-level assignment of `__version__` to a string literal.
_VERSION_LITERAL = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def newest_changelog_version(changelog_text: str) -> str | None:
    """The version named by the topmost `##` heading, or None if it names none.

    None is the honest answer for `## Unreleased`: there is a newest entry, and
    it does not say which version it describes. Callers must not read that as
    "matches whatever the code declares".
    """
    first = _HEADING.search(changelog_text)
    if first is None:
        return None
    match = _VERSION_HEADING.match(first.group("title"))
    return match.group("version") if match else None


def second_version_literals(sources: dict[str, str]) -> list[str]:
    """Files in ``{name: source}`` that assign ``__version__`` to a literal.

    Returns the offenders so a failure names the file to fix. An empty list is
    the clean verdict: every one of these modules gets the version by import.
    """
    return [
        f"{name}:{value}"
        for name, source in sources.items()
        for value in _VERSION_LITERAL.findall(source)
    ]


@pytest.fixture(scope="module")
def changelog_text() -> str:
    assert CHANGELOG.is_file(), f"{CHANGELOG} does not exist"
    return CHANGELOG.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


# -- the real repo ---------------------------------------------------------


def test_the_declared_version_and_the_newest_changelog_entry_agree(
    changelog_text: str,
) -> None:
    """The assertion E-M08 asked for, against the files as committed."""
    newest = newest_changelog_version(changelog_text)
    assert newest is not None, (
        "the newest CHANGELOG heading does not name a version (an `Unreleased` "
        "heading retitled by hand after the tag is cut is how v0.3.0 came to "
        "ship 0.2.0); write the heading at the version the code declares"
    )
    assert newest == resilient_mlkit.__version__, (
        f"CHANGELOG's newest entry is v{newest} but the package declares "
        f"{resilient_mlkit.__version__}; one of them is describing a release "
        "that does not exist"
    )


def test_pyproject_does_not_carry_its_own_version_literal(pyproject: dict) -> None:
    """The static literal here is the copy that was wrong inside the v0.3.0 tag."""
    project = pyproject["project"]
    assert "version" not in project, (
        "pyproject declares a static version; it is then a second copy of a "
        "number that already lives in resilient_mlkit.__version__, and two "
        "copies is how E-M08 happened"
    )
    assert "version" in project.get("dynamic", []), (
        "pyproject neither declares a static version nor lists it as dynamic, "
        "so the built distribution has no version at all"
    )


def test_the_build_backend_is_pointed_at_the_one_literal(pyproject: dict) -> None:
    """`dynamic = ["version"]` means nothing without the attr that resolves it."""
    dynamic = pyproject.get("tool", {}).get("setuptools", {}).get("dynamic", {})
    assert dynamic.get("version", {}).get("attr") == "resilient_mlkit.__version__", (
        "the dynamic version must resolve from resilient_mlkit.__version__; "
        f"got {dynamic.get('version')!r}"
    )


def test_no_module_carries_a_second_version_literal() -> None:
    """cli.__version__ was a separate literal, and it stamped every artifact."""
    package = ROOT / "src" / "resilient_mlkit"
    sources = {
        name: (package / name).read_text(encoding="utf-8")
        for name in NO_LITERAL_MODULES
        if (package / name).is_file()
    }
    assert sources, "no modules were read; this control would pass over an absence"
    assert second_version_literals(sources) == []


def test_cli_stamps_artifacts_with_the_same_object_the_package_declares() -> None:
    """Not merely an equal string: artifacts must not be able to drift at all."""
    assert cli.__version__ is resilient_mlkit.__version__


# -- controls --------------------------------------------------------------


def test_positive_control_a_changelog_behind_the_code_is_caught() -> None:
    """FIRES: the v0.3.0 shape, where the notes name a version the code does not."""
    behind = "# Changelog\n\n## v0.2.0 — 2026-08-28\n\nnotes\n"
    assert newest_changelog_version(behind) == "0.2.0"
    assert newest_changelog_version(behind) != "0.3.1"


def test_positive_control_an_unreleased_heading_names_no_version() -> None:
    """FIRES: the exact heading that was retitled by hand, and once was not."""
    unreleased = "# Changelog\n\n## Unreleased\n\nnotes\n\n## v0.2.0 — 2026-08-28\n"
    assert newest_changelog_version(unreleased) is None


def test_negative_control_a_matching_newest_heading_is_accepted() -> None:
    """SILENT: a heading written at the version the code declares."""
    ok = "# Changelog\n\npreamble\n\n## v9.9.9 — 2026-08-28\n\nnotes\n\n## v9.9.8\n"
    assert newest_changelog_version(ok) == "9.9.9"


def test_negative_control_prose_mentioning_an_older_version_is_not_a_heading() -> None:
    """SILENT: `v0.3.0` in a sentence must not outrank the heading above it."""
    prose = (
        "# Changelog\n\n## v0.3.1 — 2026-08-28\n\n"
        "The v0.3.0 tag is unchanged and still ships 0.2.0 in its own tree.\n"
        "## v0.3.0 — 2026-08-28\n"
    )
    assert newest_changelog_version(prose) == "0.3.1"


def test_positive_control_a_second_literal_is_caught() -> None:
    """FIRES: cli.py exactly as it was before this commit."""
    offenders = second_version_literals(
        {"cli.py": 'from . import checks\n\n__version__ = "0.2.0"\n\n\ndef main():\n    pass\n'}
    )
    assert offenders == ["cli.py:0.2.0"]


def test_negative_control_an_imported_version_is_not_a_literal() -> None:
    """SILENT: the repaired shape, and a docstring mention, must both pass."""
    clean = (
        '"""Prints `mlkit {__version__}` in every header."""\n'
        "from . import __version__\n\n"
        "print(f'mlkit {__version__}')\n"
    )
    assert second_version_literals({"cli.py": clean}) == []


def test_negative_control_an_indented_assignment_is_not_a_declaration() -> None:
    """SILENT: a local named `__version__` inside a function is not the package's."""
    local = "def probe():\n    __version__ = '0.0.1'\n    return __version__\n"
    assert second_version_literals({"probe.py": local}) == []
