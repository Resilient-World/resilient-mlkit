"""The CI workflow must have a COMMITTED definition, not an inferred one.

WHY THIS FILE EXISTS
--------------------
`.github/workflows/ci.yml` runs ruff at its defaults. That was a deliberate
choice and it is kept: the alternative, a hand-picked `select` list, is a rule
set someone can quietly narrow. But "defaults" is not a fixed thing — ruff's
default rule set ships WITH THE RELEASE, so `pip install "ruff>=0.4"` means the
gate's definition is whatever the runner downloaded that morning.

That is not hypothetical here. Measured 2026-08-29 at mlkit `8647be9`:

    .venv/bin/ruff --version                  -> ruff 0.16.5
    .venv/bin/ruff check src tests scripts    -> Found 36 errors

against a workflow comment that claimed `-> all checks passed`. Four of those
36 were `RUF100 Unused noqa` on `# noqa: E402` and `# noqa: PLC0415`
suppressions written for rules the current defaults do not enable — the
suppressions had gone stale in place, and the only reason anyone noticed is
that the rule set moved underneath them. A committed workflow that would go red
on its first-ever run, describing itself as green, is exactly the defect class
this package exists to detect, aimed at this package.

The repair is in two halves and both matter:

* the 36 findings were fixed in `src/`, `tests/` and `scripts/` — none
  suppressed, no `[tool.ruff]` select added, nothing widened;
* the tool versions are PINNED EXACTLY, so "the defaults" names one rule set.

This file guards the second half, because it is the half that rots silently. A
pin that drifts back to a floor takes the gate's meaning with it and leaves the
comment above describing a workflow that no longer exists.

WHAT IS ASSERTED
----------------
1. Every gate-defining tool CI installs (`ruff`, `mypy`) is pinned with `==`.
2. POSITIVE CONTROL — a workflow that floors a tool is REJECTED.
3. NEGATIVE CONTROL — the same workflow, pinned, is ACCEPTED. Without it,
   assertion 1 is equally consistent with a checker that rejects everything.
4. The workflow does not claim to have run. GitHub Actions is failing
   account-wide on billing, so no run of it exists to claim.

SCOPE. The parser below is deliberately local to this test rather than added to
`resilient_mlkit`. mlkit is installed into eight model repos and every public
symbol added here is surface forced on all of them; this checks THIS repo's own
workflow file, which is not something the eight need to import.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

#: The workflow under test.
WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"

#: Tools whose version DEFINES what the gate means, so a floor makes the gate
#: unreproducible. `ruff` selects its own rule set; `mypy` selects its own
#: inference and error codes. Deliberately NOT a catch-all over every install:
#: `pip`, and the `types-*` stubs, do not decide whether code passes, and
#: demanding a pin on those would be ceremony rather than a control.
GATE_DEFINING = ("ruff", "mypy")

#: A pip requirement in a `run:` block: name, then its specifier if any.
_REQUIREMENT = re.compile(r'"([A-Za-z][A-Za-z0-9._-]*)\s*([<>=!~]=?[^"]*)?"')


def run_commands(workflow_text: str) -> list[str]:
    """Every `run:` script in the workflow, as text.

    Parsed as YAML rather than grepped, so a pin that is real but indented
    unusually still counts and one that is only mentioned in a comment does not.
    """
    doc = yaml.safe_load(workflow_text)
    out: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            script = step.get("run")
            if isinstance(script, str):
                out.append(script)
    return out


def unpinned_tools(workflow_text: str) -> list[str]:
    """Gate-defining tools this workflow installs WITHOUT an exact `==` pin.

    Returns the offenders, so a failure names what to fix rather than only
    asserting that something is wrong. An empty list is the clean verdict.
    """
    bad: list[str] = []
    for script in run_commands(workflow_text):
        for name, spec in _REQUIREMENT.findall(script):
            if name.lower() not in GATE_DEFINING:
                continue
            if not (spec or "").strip().startswith("=="):
                bad.append(f"{name}{spec or ' (no specifier at all)'}")
    return bad


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW.is_file(), f"{WORKFLOW} does not exist"
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_committed_workflow_pins_every_gate_defining_tool(workflow_text: str) -> None:
    """The real file. A floor here makes `ruff check` mean a different thing monthly."""
    offenders = unpinned_tools(workflow_text)
    assert offenders == [], (
        "these gate-defining tools are installed without an exact `==` pin, so "
        "what CI checks depends on the release date rather than on the committed "
        f"workflow: {offenders}"
    )


def test_the_workflow_actually_installs_the_tools_it_is_checked_for(
    workflow_text: str,
) -> None:
    """Guard against the check passing because nothing is installed at all.

    `unpinned_tools` returns `[]` both for a correctly pinned workflow and for
    one that installs no tools whatsoever. Without this, deleting the lint job
    would turn the control above green.
    """
    scripts = " ".join(run_commands(workflow_text))
    for tool in GATE_DEFINING:
        assert re.search(rf'"{tool}==', scripts), (
            f"the workflow never installs a pinned '{tool}', so the pin check "
            "above is passing over an absence rather than over a pin"
        )


def test_positive_control_a_floored_tool_is_rejected() -> None:
    """FIRES: the exact spelling this workflow carried before, must be caught."""
    floored = """
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pip install --upgrade pip "ruff>=0.4"
      - run: ruff check src tests scripts
"""
    assert unpinned_tools(floored) == ["ruff>=0.4"]


def test_positive_control_a_bare_tool_with_no_specifier_is_rejected() -> None:
    """FIRES: no specifier is a floor with the floor left off."""
    bare = """
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pip install "ruff"
"""
    assert unpinned_tools(bare) == ["ruff (no specifier at all)"]


def test_negative_control_the_same_workflow_pinned_is_accepted() -> None:
    """SILENT: identical but for the specifier. This is what separates a
    control from a checker that simply rejects everything it is shown."""
    pinned = """
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pip install --upgrade pip "ruff==0.16.5"
      - run: ruff check src tests scripts
"""
    assert unpinned_tools(pinned) == []


def test_negative_control_a_pin_in_a_comment_does_not_count() -> None:
    """SILENT on the pin, LOUD on the install: a comment is not an install.

    The parser reads `run:` scripts out of the YAML, so prose about pinning in
    the header cannot satisfy a check about what is executed.
    """
    commented = """
# We definitely pin "ruff==0.16.5" honest
name: CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pip install "ruff>=0.4"
"""
    assert unpinned_tools(commented) == ["ruff>=0.4"]


def test_non_gate_defining_installs_are_not_demanded_to_be_pinned() -> None:
    """SILENT: `pip` and the type stubs do not decide whether code passes.

    A check that demanded a pin on every string in every install line would
    fire constantly and be turned off, which is worse than not having it.
    """
    mixed = """
name: CI
on: [push]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - run: |
          python -m pip install --upgrade pip
          pip install -e "."
          pip install "mypy==2.3.1" "types-PyYAML>=6.0"
"""
    assert unpinned_tools(mixed) == []


def test_the_workflow_does_not_claim_a_run_it_never_had(workflow_text: str) -> None:
    """GitHub Actions is failing account-wide on billing; no run exists to cite.

    The header must say so. This is the same rule the rest of the portfolio
    runs under -- a number or a status you did not obtain by running does not
    exist -- applied to the workflow's own description of itself.
    """
    assert "UNVERIFIED AS COMMITTED" in workflow_text, (
        "the workflow no longer states that it has never executed. If it has now "
        "run, cite the run; if it has not, say so."
    )
