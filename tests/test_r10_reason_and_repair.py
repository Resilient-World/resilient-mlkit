"""E-M41 — every R10 row says WHAT is fabricated and WHAT to write instead.

`reports/E_M41_R10_VOCABULARY_PREREGISTRATION.md` fixed A1–A7 before any of
this existed. This file is A1, A2, A3 and A6 as executable arms; A4 and A5 are
a fleet drive and live in `reports/E_M41_R10_VOCABULARY_RESULTS.md`.

The shape is E-M38's, and so is the trap it guards: there, `Finding` gained a
`repair` field, the value was dropped in `scan()`'s rebuild, and nine real rows
shipped reading `repair: ""` until a control caught it. So the assertion here
is over EVERY finding a scan produces, at repo scope, not over one fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resilient_mlkit.core import fabrication, metric_registry

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- A2: the three severity paths, each planted deliberately ---------------

#: SATISFIES_GATE. `rmse` is in mlkit's vocabulary, it is lower-is-better, and
#: 0.0 is a perfect error score — the value that would pass the gate.
_PLANTED_SATISFIES = '''
def score_outage_model(metrics):
    rmse = metrics.get("rmse") if metrics else 0.0
    return {"rmse": rmse}
'''

#: PUBLISHES_UNMEASURED. `auc` is in the vocabulary and higher-is-better, so
#: 0.0 would FAIL its gate — but it is still emitted as a measurement.
_PLANTED_PUBLISHES = '''
def score_challenger(fitted):
    auc = fitted.auc if fitted else 0.0
    return {"auc": auc}
'''

#: UNCLASSIFIED_NAME. `spectral_biennial_power` is a name only the ADOPTER's
#: registry supplies; mlkit's vocabulary has no polarity for it. Taken from
#: resilient-arabica src/analysis/biennial_cycle.py, which is where the ten
#: residual literals that motivated E-M41 actually live.
_PLANTED_UNCLASSIFIED = '''
def spectral_biennial_power(yields, total):
    if len(yields) < 8:
        return 0.0
    return float(sum(yields) / total)
'''

#: A3. The same quantity READ FROM A COMMITTED ARTIFACT. This is the repair
#: every other row is told to make, so if it fired the rule would forbid its
#: own instruction.
_READ_FROM_ARTIFACT = '''
import json
from pathlib import Path

def score_outage_model(artifact: Path):
    record = json.loads(artifact.read_text())
    rmse = record["rmse"]
    return {"rmse": rmse}
'''


class _Registry:
    """The smallest thing satisfying fabrication's registry protocol."""

    def __init__(self, *names: str) -> None:
        self._names = {metric_registry.normalise(n) for n in names}

    def contains(self, name: str) -> bool:
        return metric_registry.normalise(name) in self._names

    def origin(self, name: str) -> str | None:
        return f"{name} <- <planted>:1"


def test_a2_control_fires_on_a_vocabulary_name_whose_default_passes_its_gate() -> None:
    findings = fabrication.scan_source(_PLANTED_SATISFIES, "planted")
    assert [f.severity for f in findings] == ["SATISFIES_GATE"]
    assert findings[0].symbol == "rmse"


def test_a2_control_fires_on_a_vocabulary_name_whose_default_fails_its_gate() -> None:
    findings = fabrication.scan_source(_PLANTED_PUBLISHES, "planted")
    assert [f.severity for f in findings] == ["PUBLISHES_UNMEASURED"]
    assert findings[0].symbol == "auc"


def test_a2_control_fires_on_a_registry_only_name() -> None:
    findings = fabrication.scan_source(
        _PLANTED_UNCLASSIFIED, "planted", _Registry("spectral_biennial_power")
    )
    assert [f.severity for f in findings] == [fabrication.UNCLASSIFIED_NAME]
    assert findings[0].symbol == "spectral_biennial_power"


def test_a3_control_stays_silent_on_a_value_read_from_a_committed_artifact() -> None:
    assert fabrication.scan_source(_READ_FROM_ARTIFACT, "planted") == []


@pytest.mark.parametrize(
    ("source", "registry"),
    [
        (_PLANTED_SATISFIES, None),
        (_PLANTED_PUBLISHES, None),
        (_PLANTED_UNCLASSIFIED, _Registry("spectral_biennial_power")),
    ],
)
def test_a1_every_planted_row_carries_a_reason_and_a_repair(source, registry) -> None:
    findings = fabrication.scan_source(source, "planted", registry)
    assert findings
    for finding in findings:
        assert finding.reason.strip(), finding
        assert finding.repair.strip(), finding
        assert finding.symbol in finding.reason
        assert finding.literal in finding.reason
        payload = finding.to_dict()
        assert payload["reason"] == finding.reason
        assert payload["repair"] == finding.repair
        # Serialisable: the evidence dict and the JSON artifacts carry it.
        json.dumps(payload)


def test_a1_an_unclassified_row_says_why_no_verdict_and_names_the_three_exits() -> None:
    finding = fabrication.scan_source(
        _PLANTED_UNCLASSIFIED, "planted", _Registry("spectral_biennial_power")
    )[0]
    assert "not in mlkit's metric vocabulary" in finding.reason
    assert "asserts neither" in finding.reason
    assert "[metrics]" in finding.repair
    assert "committed artifact" in finding.repair
    assert "refuse" in finding.repair


def test_a1_a_defect_row_says_the_repair_and_refuses_the_placeholder() -> None:
    finding = fabrication.scan_source(_PLANTED_SATISFIES, "planted")[0]
    assert "committed artifact" in finding.repair
    assert "nan" in finding.repair.lower()
    assert "convenient" in finding.repair


def test_a1_at_repo_scope_no_row_this_repo_produces_has_an_empty_field() -> None:
    """The E-M38 trap: a fixture can pass while every real row reads "".

    mlkit's own `src/` is a Python tree R10 can walk, so it is a real
    population of findings produced by the real emission sites.
    """
    roots = [REPO_ROOT / "src"]
    registry = metric_registry.derive(roots, base=REPO_ROOT)
    findings = fabrication.scan_tree(roots, base=REPO_ROOT, registry=registry)
    for finding in findings:
        assert finding.reason.strip(), finding
        assert finding.repair.strip(), finding


# --- A6: declaring a polarity can only ever make R10 stricter --------------


def test_a6_declaring_a_polarity_turns_na_into_a_verdict() -> None:
    registry = _Registry("spectral_biennial_power")
    before = fabrication.scan_source(_PLANTED_UNCLASSIFIED, "planted", registry)
    assert [f.severity for f in before] == [fabrication.UNCLASSIFIED_NAME]

    declared = metric_registry.polarities_from(
        {"metrics": {"spectral_biennial_power": "higher_is_better"}}
    )
    after = fabrication.scan_source(
        _PLANTED_UNCLASSIFIED, "planted", registry, declared
    )
    assert [f.severity for f in after] == ["PUBLISHES_UNMEASURED"]
    assert len(after) == len(before)
    assert after[0].line == before[0].line


def test_a6_a_declaration_can_never_remove_a_row_or_silence_a_name() -> None:
    registry = _Registry("spectral_biennial_power")
    for direction in sorted(fabrication.DECLARED_POLARITIES):
        declared = metric_registry.polarities_from(
            {"metrics": {"spectral_biennial_power": direction}}
        )
        findings = fabrication.scan_source(
            _PLANTED_UNCLASSIFIED, "planted", registry, declared
        )
        assert len(findings) == 1, direction
        assert findings[0].severity != fabrication.UNCLASSIFIED_NAME, direction


def test_a6_there_is_no_declaration_meaning_not_a_metric() -> None:
    """A silencing channel is the one thing this declaration must not be."""
    assert fabrication.DECLARED_POLARITIES == {
        "higher_is_better",
        "lower_is_better",
        "neutral",
    }
    declared = metric_registry.polarities_from(
        {"metrics": {"spectral_biennial_power": "not_a_metric"}}
    )
    assert declared.polarity("spectral_biennial_power") is None
    assert declared.refused == ("spectral_biennial_power = 'not_a_metric'",)
    findings = fabrication.scan_source(
        _PLANTED_UNCLASSIFIED, "planted", _Registry("spectral_biennial_power"), declared
    )
    assert [f.severity for f in findings] == [fabrication.UNCLASSIFIED_NAME]


def test_a6_a_declaration_cannot_re_aim_a_name_the_vocabulary_already_judges() -> None:
    """`rmse` is mlkit's, not the adopter's. 0.0 stays the gate-passing value."""
    declared = metric_registry.polarities_from({"metrics": {"rmse": "higher_is_better"}})
    findings = fabrication.scan_source(
        _PLANTED_SATISFIES, "planted", _Registry("rmse"), declared
    )
    assert [f.severity for f in findings] == ["SATISFIES_GATE"]


def test_a6_an_absent_metrics_table_changes_nothing() -> None:
    registry = _Registry("spectral_biennial_power")
    empty = metric_registry.polarities_from({})
    assert empty.directions == {}
    with_empty = fabrication.scan_source(
        _PLANTED_UNCLASSIFIED, "planted", registry, empty
    )
    without = fabrication.scan_source(_PLANTED_UNCLASSIFIED, "planted", registry)
    assert [f.to_dict() for f in with_empty] == [f.to_dict() for f in without]
