"""SV-1-REGISTRY — a check declared in PHASE_ORDER may not silently stop existing.

``for_phase`` used to end ``if cid in _REGISTRY``. That filter meant an id
``PHASE_ORDER`` declares and the registry does not hold was never reported
missing: the phase ran the remainder, counted the remainder, and printed a
green ``n/n``. An absence rendered as a success.

The pair below is the whole of the argument, and neither half is worth anything
alone:

* **Positive** — inject a fake id into ``PHASE_ORDER`` and the phase yields a
  FAIL-shaped row carrying that id and ``UNREGISTERED_REASON``, and the phase's
  exit code is 1. A guard that cannot be forced to fire measures nothing.
* **Negative** — with the real, complete registry no synthesized row appears at
  all, ``for_phase`` returns exactly the registered specs in ``PHASE_ORDER``
  order, and ``missing_from_registry()`` is empty. A guard that fires on the
  healthy tree is an alarm nobody will leave switched on.

The negative half is also the standing assertion the task asked for: after
``load_all()``, every id in ``PHASE_ORDER`` is in the registry.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from resilient_mlkit import checks as checks_pkg
from resilient_mlkit.checks import (
    PHASE_ORDER,
    PHASES,
    UNREGISTERED_REASON,
    RunContext,
    all_check_ids,
    for_phase,
    missing_from_registry,
)
from resilient_mlkit.cli import _run_phase
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status


@pytest.fixture(scope="module", autouse=True)
def _loaded() -> None:
    checks_pkg.load_all()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    path = tmp_path / "resilient-fixture"
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return Repo(name="fixture", path=path)


# -- negative half: the real tree ----------------------------------------


def test_phase_order_is_a_subset_of_the_registry() -> None:
    """The standing assertion. Every declared id actually registered."""
    assert missing_from_registry() == []
    assert set(all_check_ids()) <= set(checks_pkg._REGISTRY)


@pytest.mark.parametrize("phase", PHASES)
def test_for_phase_returns_one_spec_per_declared_id_in_order(phase: str) -> None:
    specs = for_phase(phase)
    assert [s.check_id for s in specs] == PHASE_ORDER[phase]


@pytest.mark.parametrize("phase", PHASES)
def test_no_synthesized_row_on_the_healthy_tree(phase: str, repo: Repo) -> None:
    """Negative control: nothing in a real phase run carries the synthesized reason."""
    ctx = RunContext(nonce="TEST", root=repo.path.parent, offline=True, timeout=5.0)
    results = _run_phase(repo, phase, ctx)
    assert [r.check_id for r in results] == PHASE_ORDER[phase]
    assert [r for r in results if r.reason == UNREGISTERED_REASON] == []


# -- positive half: force the absence ------------------------------------


def test_unregistered_id_becomes_a_fail_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: inject an id nothing registers; get a FAIL, not a gap."""
    injected = dict(PHASE_ORDER)
    injected["triage"] = [*PHASE_ORDER["triage"], "T99_NEVER_REGISTERED"]
    monkeypatch.setattr(checks_pkg, "PHASE_ORDER", injected)

    specs = for_phase("triage")
    assert [s.check_id for s in specs] == injected["triage"]
    assert missing_from_registry() == ["T99_NEVER_REGISTERED"]


def test_unregistered_id_fails_the_phase(
    repo: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The synthesized row is a FAIL with the registered reason, and it is the
    only synthesized row: the five real triage checks are untouched beside it."""
    injected = dict(PHASE_ORDER)
    injected["triage"] = [*PHASE_ORDER["triage"], "T99_NEVER_REGISTERED"]
    monkeypatch.setattr(checks_pkg, "PHASE_ORDER", injected)

    ctx = RunContext(nonce="TEST", root=repo.path.parent, offline=True, timeout=5.0)
    results = _run_phase(repo, "triage", ctx)

    assert [r.check_id for r in results] == injected["triage"]
    synthesized = [r for r in results if r.reason == UNREGISTERED_REASON]
    assert len(synthesized) == 1
    row = synthesized[0]
    assert row.check_id == "T99_NEVER_REGISTERED"
    assert row.status is Status.FAIL
    assert row.phase == "triage"
    # The evidence has to say where the id was declared, or the operator has
    # nowhere to go from the row.
    assert row.evidence["declared_in"] == "checks.PHASE_ORDER"
    assert "T99_NEVER_REGISTERED" not in row.evidence["registered_in_phase"]
