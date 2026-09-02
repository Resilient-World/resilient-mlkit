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
4. The workflow's description of its own execution is CITED, not asserted. Until
   v0.6.0 this file demanded the string "UNVERIFIED AS COMMITTED", because on
   2026-08-28 Actions was failing account-wide on billing and no run existed.
   Runs exist now — `main` at `6921e9a` is green at run `33499020378`, retrieved
   2026-09-01 — so that demand had become a demand for a false sentence, and a
   control that forces the header to lie is worse than no control.

   What replaces it is a CONJUNCTION and is strictly more than the old string
   test could see: the header must NOT deny having run, AND it must cite at
   least one run of THIS repo by URL, AND it must carry a retrieval date. The
   old assertion could not tell a truthful citation from no citation at all; it
   only checked that the file was modest. This one checks that it is sourced.

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


#: A run of THIS repo's Actions, by URL. The repo is part of the pattern on
#: purpose: a run id alone is a bare integer, and a link to some other
#: repository's green tick is not evidence about this workflow.
_RUN_URL = re.compile(
    r"https://github\.com/Resilient-World/resilient-mlkit/actions/runs/(\d+)"
)

#: An ISO date. The portfolio rule is that a retrieved fact carries the date it
#: was retrieved, because a run list is a live resource.
_RETRIEVAL_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")

#: Sentences that DENY having executed. Kept as patterns rather than one
#: literal so the denial cannot come back in a synonym.
_DENIALS = (
    re.compile(r"UNVERIFIED\s+AS\s+COMMITTED"),
    re.compile(r"has\s+never\s+executed", re.IGNORECASE),
    re.compile(r"no\s+run\s+of\s+it\s+is\s+being\s+claimed", re.IGNORECASE),
)


def run_citations(workflow_text: str) -> list[str]:
    """The run ids this workflow's header cites, in order of appearance."""
    return _RUN_URL.findall(workflow_text)


def denies_having_run(workflow_text: str) -> bool:
    """True when the header still says the workflow has never executed."""
    return any(p.search(workflow_text) for p in _DENIALS)


def test_the_workflow_describes_its_own_execution_from_evidence(
    workflow_text: str,
) -> None:
    """The real file. Both halves, because either alone is satisfiable by deletion.

    This is the same rule the rest of the portfolio runs under -- a status you
    did not obtain by running does not exist -- applied to the workflow's own
    description of itself. It was satisfied on 2026-08-28 by admitting there was
    nothing to cite. It is satisfied now by citing.
    """
    assert not denies_having_run(workflow_text), (
        "the workflow header still says it has never executed, while runs of it "
        "exist and are linked from the repository's Actions tab (main at "
        "6921e9a, run 33499020378, retrieved 2026-09-01). A header describing a "
        "workflow that no longer exists is this package's own defect class "
        "aimed at this package"
    )
    cited = run_citations(workflow_text)
    assert cited, (
        "the workflow header no longer denies having run and cites no run "
        "either, which is an unsourced claim rather than a corrected one; link "
        "at least one https://github.com/Resilient-World/resilient-mlkit/"
        "actions/runs/<id>"
    )
    assert _RETRIEVAL_DATE.search(workflow_text), (
        f"the header cites runs {cited} with no retrieval date; a run list is a "
        "live resource and a citation without a date cannot be checked against "
        "the state it was read in"
    )


def test_positive_control_a_header_denying_a_run_it_had_is_caught() -> None:
    """FIRES: the header exactly as it stood before v0.6.0."""
    stale = (
        "# UNVERIFIED AS COMMITTED. GitHub Actions is failing account-wide on\n"
        "# billing, so this workflow has never executed and no run of it is\n"
        "# being claimed.\n"
    )
    assert denies_having_run(stale)
    assert run_citations(stale) == []


def test_positive_control_an_unsourced_green_claim_is_caught() -> None:
    """FIRES: dropping the denial without adding the citation. This is the hole
    the old string assertion could not see -- it was equally happy with a file
    that said nothing about its runs at all."""
    unsourced = "# CI for resilient-mlkit. It passes.\n"
    assert not denies_having_run(unsourced)
    assert run_citations(unsourced) == []


def test_positive_control_another_repos_run_is_not_evidence_about_this_one() -> None:
    """FIRES: a green tick borrowed from elsewhere is not this workflow's."""
    borrowed = (
        "# Green, see\n"
        "# https://github.com/Resilient-World/resilient-fray/actions/runs/1234\n"
        "# retrieved 2026-09-01\n"
    )
    assert run_citations(borrowed) == []


def test_negative_control_a_cited_header_is_accepted() -> None:
    """SILENT: a denial-free header with a run of this repo and a date."""
    cited = (
        "# THIS WORKFLOW HAS EXECUTED. Retrieved 2026-09-01 with `gh run list`.\n"
        "#   33499020378  main  6921e9a  success\n"
        "#   https://github.com/Resilient-World/resilient-mlkit/actions/runs/33499020378\n"
    )
    assert not denies_having_run(cited)
    assert run_citations(cited) == ["33499020378"]
    assert _RETRIEVAL_DATE.search(cited)
