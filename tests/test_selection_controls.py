"""S1-S4 controls: does the selection register gate fire, and stay silent when it should.

The selection phase reads one file, `docs/selection.yaml`, and its whole purpose
is to refuse a well-formatted document that says nothing. So the pairs here are
mostly about the difference between *present* and *filled in*: a task spec whose
keys all exist but whose values are empty strings, a candidate register with the
right number of entries and no Tier-1 baseline, a source list where every field
is there except the one that would settle a licence.

Three pairings carry the weight.

* **S1 fires on a key present with an empty value.** `str(spec.get(f) or
  "").strip()` is what makes "objective:" with nothing after it a missing field
  rather than a declared one. A spec can be completed by typing six colons, and
  this is the control that says it cannot.

* **S2's tier rule, exercised at each shortfall separately.** The register is
  incomplete without a Tier-0 trivial baseline, without a Tier-1 domain
  baseline, and with fewer than two Tier-2 entries — and the pass case has all
  three, so the refusals are of the shortfall and not of the shape.

* **S3 is NA offline, and NA is not PASS.** Nothing in this iteration is allowed
  to reach the network, so the SILENT half of S3's pair is deliberately the NA
  branch and the FIRES half is the shortfall the offline flag must not hide.
  The reason names the network, so the row cannot be read as "every URL
  resolved".
"""

from __future__ import annotations

from typing import Any

import yaml

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.selection import (
    REQUIRED_SOURCE_FIELDS,
    REQUIRED_TASK_SPEC,
    s1_task_spec,
    s2_candidate_register,
    s3_evidence_resolvable,
    s4_data_and_licence,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status


def _repo(tmp_path, document: Any | None) -> Repo:
    """A repo whose `docs/selection.yaml` is `document`, or absent when None."""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    if document is not None:
        text = document if isinstance(document, str) else yaml.safe_dump(document)
        (tmp_path / "docs" / "selection.yaml").write_text(text)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path, *, offline: bool = True) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=offline)


def _full_spec(**overrides: Any) -> dict[str, Any]:
    spec = {field: f"stated {field}" for field in REQUIRED_TASK_SPEC}
    spec.update(overrides)
    return spec


def _candidate(cid: str, tier: int, *, licence: str = "https://example.invalid/lic") -> dict:
    return {"id": cid, "tier": tier, "licence_url": licence}


def _full_register() -> list[dict]:
    return [
        _candidate("lag_1_persistence", 0),
        _candidate("gradient_boosted_baseline", 1),
        _candidate("foundation_a", 2),
        _candidate("foundation_b", 2),
    ]


def _source(sid: str, **overrides: Any) -> dict:
    src: dict[str, Any] = {field: f"{field}-value" for field in REQUIRED_SOURCE_FIELDS}
    src["id"] = sid
    src["verdict"] = "ALLOWED"
    src["licence_url"] = "https://example.invalid/lic"
    src.update(overrides)
    return src


# -- the file itself: NA, not a verdict -----------------------------------


def test_an_absent_register_is_NA_for_every_selection_check(tmp_path):
    """FIRES as NA, four times over: "this repo has not written a register" is
    unmeasured, not clean. A missing file that rendered like a pass would make
    the whole phase a formality."""
    repo = _repo(tmp_path, None)
    ctx = _ctx(tmp_path)
    for check in (s1_task_spec, s2_candidate_register, s3_evidence_resolvable, s4_data_and_licence):
        result = check(repo, ctx)
        assert result.status is Status.NA
        assert "does not exist" in result.reason


def test_a_malformed_register_is_NA_naming_the_parse_failure(tmp_path):
    """FIRES as NA: broken YAML is not a licence verdict either way."""
    repo = _repo(tmp_path, "task_spec: [unclosed\n")
    result = s1_task_spec(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "malformed YAML" in result.reason


# -- S1: the task is pinned down before candidates are compared -----------


def test_negative_control_a_complete_task_spec_is_silent(tmp_path):
    """SILENT: all six fields stated."""
    repo = _repo(tmp_path, {"task_spec": _full_spec()})
    result = s1_task_spec(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["fields"] == len(REQUIRED_TASK_SPEC)


def test_positive_control_a_missing_task_spec_field_is_named(tmp_path):
    """FIRES: and names the field, so the verdict is actionable."""
    spec = _full_spec()
    del spec["decision_threshold"]
    repo = _repo(tmp_path, {"task_spec": spec})
    result = s1_task_spec(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "decision_threshold" in result.reason


def test_positive_control_a_field_present_but_empty_is_still_missing(tmp_path):
    """FIRES: the pairing that matters. A key with nothing after it looks
    complete to any check that tests for presence, and this one does not.

    Six colons is not a task specification, and a gate that accepted them would
    be satisfied by the shape of an answer rather than by an answer.
    """
    repo = _repo(tmp_path, {"task_spec": _full_spec(holdout="   ", primary_metric=None)})
    result = s1_task_spec(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "holdout" in result.reason
    assert "primary_metric" in result.reason


def test_positive_control_an_absent_task_spec_key_is_refused(tmp_path):
    """FIRES: a register with candidates and no task spec is a comparison with
    no question behind it."""
    repo = _repo(tmp_path, {"candidates": _full_register()})
    result = s1_task_spec(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "absent or empty" in result.reason


# -- S2: three mandatory tiers, each licence-identified -------------------


def test_negative_control_a_complete_register_is_silent(tmp_path):
    """SILENT: one Tier-0, one Tier-1, two Tier-2, all licence-identified."""
    repo = _repo(tmp_path, {"candidates": _full_register()})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["tier_1"] == 1
    assert result.evidence["tier_2"] == 2


def test_positive_control_a_register_with_no_tier_1_baseline_is_refused(tmp_path):
    """FIRES: the tier rule this phase exists to defend. No foundation model
    enters a training config until something domain-specific has been beaten,
    and a register with four impressive Tier-2 entries and no Tier-1 has not
    made that comparison possible."""
    register = [c for c in _full_register() if c["tier"] != 1]
    register.append(_candidate("foundation_c", 2))
    repo = _repo(tmp_path, {"candidates": register})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "no Tier-1 domain-specific baseline" in result.reason
    assert result.evidence["tier_2"] == 3


def test_positive_control_a_register_with_no_trivial_baseline_is_refused(tmp_path):
    """FIRES, by a separate branch: without a do-almost-nothing entry there is
    nothing to say whether any of the rest earned its complexity."""
    repo = _repo(tmp_path, {"candidates": [c for c in _full_register() if c["tier"] != 0]})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "no Tier-0" in result.reason


def test_positive_control_a_single_tier_2_entry_is_refused_by_count(tmp_path):
    """FIRES: one foundation model is a preference, not a comparison."""
    register = [c for c in _full_register() if c["id"] != "foundation_b"]
    repo = _repo(tmp_path, {"candidates": register})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "only 1 Tier-2 entries" in result.reason


def test_positive_control_a_candidate_without_a_licence_URL_is_refused(tmp_path):
    """FIRES, and only after the tiers are satisfied, so this is genuinely the
    licence branch: a candidate identified by name alone is not licence-
    identified, and "MIT" is not a URL."""
    register = _full_register()
    register[2]["licence_url"] = "MIT"
    repo = _repo(tmp_path, {"candidates": register})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "without a licence URL" in result.reason
    assert "foundation_a" in result.reason


def test_positive_control_an_empty_register_is_refused(tmp_path):
    repo = _repo(tmp_path, {"candidates": []})
    result = s2_candidate_register(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "register is empty" in result.reason


# -- S3: offline is NA, and NA is not a pass ------------------------------


def test_S3_offline_is_NA_naming_the_network(tmp_path):
    """FIRES as NA: the branch that keeps this iteration honest. No URL was
    probed, so the row must not read as "every URL resolved"."""
    repo = _repo(tmp_path, {"candidates": _full_register()})
    result = s3_evidence_resolvable(repo, _ctx(tmp_path, offline=True))
    assert result.status is Status.NA
    assert "no network available" in result.reason


def test_S3_with_no_citable_URLs_is_NA_rather_than_a_vacuous_pass(tmp_path):
    """FIRES as NA, and by a different branch than offline: a register with
    nothing to resolve satisfies "every URL resolved" vacuously, which is the
    one way to make a link checker meaningless.

    Reached with `offline=False` and no URLs in the document, so no request is
    made — the check returns before probing anything.
    """
    repo = _repo(
        tmp_path,
        {"candidates": [{"id": "lag_1", "tier": 0, "licence_url": "not-a-url"}]},
    )
    result = s3_evidence_resolvable(repo, _ctx(tmp_path, offline=False))
    assert result.status is Status.NA
    assert "no citable URLs" in result.reason


# -- S4: every source characterised and verdicted -------------------------


def test_negative_control_a_fully_characterised_source_is_silent(tmp_path):
    """SILENT: every required field present, with a verdict."""
    repo = _repo(tmp_path, {"sources": [_source("sentinel2_l2a")]})
    result = s4_data_and_licence(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["n_sources"] == 1
    assert result.evidence["verdicts"] == {"ALLOWED": 1}


def test_positive_control_a_source_missing_a_field_is_named_with_the_field(tmp_path):
    """FIRES: each of these fields exists because omitting it has cost somebody
    a training run, and the reason names both the source and what is absent."""
    repo = _repo(
        tmp_path,
        {"sources": [_source("sentinel2_l2a", us_west_2=None, staging_cost="")]},
    )
    result = s4_data_and_licence(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "sentinel2_l2a" in result.reason
    assert "us_west_2" in result.reason
    assert "staging_cost" in result.reason


def test_positive_control_a_source_with_no_verdict_is_refused(tmp_path):
    """FIRES, and by the branch after completeness: a source can be fully
    described and still have no licence determination, and a described source
    is not a cleared one.

    The verdict key is deleted rather than emptied so the check reaches its
    UNSET branch rather than its missing-field branch — the two are different
    findings and this pins the one it names.
    """
    src = _source("sentinel2_l2a")
    src["verdict"] = "UNSET"
    repo = _repo(tmp_path, {"sources": [src]})
    result = s4_data_and_licence(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "no licence verdict" in result.reason
    assert result.evidence["verdicts"]["UNSET"] == 1


def test_positive_control_no_sources_at_all_is_refused(tmp_path):
    """FIRES: an unpopulated source list is not a clean one."""
    repo = _repo(tmp_path, {"sources": []})
    result = s4_data_and_licence(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "no sources characterised" in result.reason
