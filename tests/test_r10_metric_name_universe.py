"""E-038 — R10's metric-name universe is the ADOPTER's, not mlkit's word list.

THE DEFECT, RESTATED FROM THE MEASUREMENT
-----------------------------------------
``resilient-surge`` at ``8b71343`` declares twelve public metric callables in
``src/resilient_surge/evaluation/metrics.py``. R10's ``MEASURED_TOKENS`` saw
eight of them and was blind to four: ``peak_timing_error``,
``peak_magnitude_error``, ``false_alarm_ratio`` and ``aal_bias``. Anything
published under a blind name was never checked and R10 said PASS.

The consequence is visible in surge's own source and is not hypothetical. In
that one file ``f1_score``, ``iou`` and ``hit_rate`` raise ``Unmeasured`` on a
0/0 denominator — R10 could see those names — while ``false_alarm_ratio``
returns ``0.0``, a perfect no-false-alarm score reported from nothing, on the
identical degeneracy. The repair stopped exactly where the word list stopped.

WHAT THE CONTROLS HERE MUST DO
------------------------------
CONTROL A fires: a fabricated value under a blind name is silent on the old
rule and caught on the new one, with the name quoted.

The ANTI-RENAME control generates its metric name from ``secrets`` at drive
time. No list an implementer can edit — not ``MEASURED_TOKENS``, not a fixture,
not anything in the diff — can satisfy it, because the name does not exist
until the test runs. This is the clause that makes the fix a rule rather than
a longer list, and it is the same device E-M17's repair was held to.

CONTROL B stays silent: the vocabulary leg is untouched, so every finding R10
made before is made now, at the same line, with the same severity; a repo whose
registry adds nothing gets a byte-identical answer; and the config vetoes are
not a thing a derived name can walk around.

THE STRICTER PROOF is mechanical: the new accepted set is a subset of the old
one, checked over the union of both name universes rather than asserted.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from resilient_mlkit.core import fabrication, metric_registry

# The module binding is asserted, not assumed: an editable install in this
# portfolio routinely points at a DIFFERENT checkout, and a control that
# measured another tree would be worthless.
_HERE = Path(__file__).resolve().parent
_EXPECTED = _HERE.parent / "src" / "resilient_mlkit" / "core" / "fabrication.py"


def test_this_suite_binds_to_the_worktree_not_an_installed_package() -> None:
    assert Path(fabrication.__file__).resolve() == _EXPECTED, (
        f"bound to {fabrication.__file__}, expected {_EXPECTED}"
    )
    assert (
        Path(metric_registry.__file__).resolve()
        == _HERE.parent / "src" / "resilient_mlkit" / "core" / "metric_registry.py"
    )


# ---------------------------------------------------------------------------
# The measured blind spot, replayed as a fixture
# ---------------------------------------------------------------------------

#: Verbatim from ``resilient-surge`` ``src/resilient_surge/evaluation/metrics.py``
#: at 8b71343 — one name R10 CAN see and three it cannot, with the shape that
#: makes the difference legible: the visible one raises on 0/0, the invisible
#: ones return a perfect score.
SURGE_METRICS = '''
import numpy as np


class Unmeasured(RuntimeError):
    pass


def hit_rate(mask_true, mask_pred) -> float:
    """Hit rate (recall / probability of detection) for inundation."""
    tp = np.sum(mask_true & mask_pred)
    fn = np.sum(mask_true & ~mask_pred)
    if (tp + fn) == 0:
        raise Unmeasured("hit rate is unmeasured")
    return float(tp / (tp + fn))


def false_alarm_ratio(mask_true, mask_pred) -> float:
    """False Alarm Ratio for inundation."""
    fp = np.sum(~mask_true & mask_pred)
    tp = np.sum(mask_true & mask_pred)
    return float(fp / (fp + tp)) if (fp + tp) > 0 else 0.0


def peak_magnitude_error(y_true, y_pred) -> float:
    """Difference between predicted and observed peak magnitude."""
    if len(y_true) == 0 or len(y_pred) == 0:
        return 0.0
    return float(np.max(y_pred) - np.max(y_true))


def aal_bias(observed_aal: float, predicted_aal: float) -> float:
    """Relative AAL bias: (predicted - observed) / observed."""
    if observed_aal == 0:
        return 0.0
    return (predicted_aal - observed_aal) / observed_aal
'''

#: The four names E-038 measured as invisible, plus the spelling defeat:
#: ``csi`` IS in MEASURED_TOKENS, and ``critical_success_index`` still never
#: reaches it, because the tokeniser splits it into critical/success/index.
BLIND_NAMES = (
    "peak_timing_error",
    "peak_magnitude_error",
    "false_alarm_ratio",
    "aal_bias",
    "critical_success_index",
)

#: Names from the same file that the vocabulary DOES cover. These are the
#: check-not-dead half: they must go on firing exactly as they did.
COVERED_NAMES = ("hit_rate", "f1_score", "iou", "crps", "rmse", "coverage")


def _write(tmp_path: Path, name: str, body: str) -> Path:
    root = tmp_path / "src"
    root.mkdir(exist_ok=True)
    path = root / name
    path.write_text(body)
    return root


@pytest.mark.parametrize("name", BLIND_NAMES)
def test_the_measured_blind_spot_is_real_on_the_old_rule(name: str) -> None:
    """The premise. Every one of these is a metric R10's word list cannot see."""
    assert not fabrication.is_measured_name(name), (
        f"{name} is now in MEASURED_TOKENS — E-038 was closed by extending the "
        "word list, which is the defect, not the repair. Delete the entry and "
        "let the derivation do it."
    )


@pytest.mark.parametrize("name", COVERED_NAMES)
def test_the_names_the_vocabulary_already_covered_are_still_covered(name: str) -> None:
    assert fabrication.is_measured_name(name)


# ---------------------------------------------------------------------------
# CONTROL A — must fire
# ---------------------------------------------------------------------------


def test_control_a_the_surge_blind_spot_is_silent_before_and_caught_after(
    tmp_path: Path,
) -> None:
    """E-038's own measurement, replayed on surge's own code.

    Pre-fix (no registry passed) R10 is SILENT on ``false_alarm_ratio``,
    ``peak_magnitude_error`` and ``aal_bias`` while catching nothing at all.
    Post-fix it names all three.
    """
    root = _write(tmp_path, "metrics.py", SURGE_METRICS)

    before = fabrication.scan_tree([root], base=tmp_path)
    assert before == [], (
        "the old rule was supposed to be silent here; if it is not, this "
        f"fixture no longer replays E-038: {[f.render() for f in before]}"
    )

    registry = metric_registry.derive([root], base=tmp_path)
    after = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    caught = {f.symbol for f in after}
    assert {"false_alarm_ratio", "peak_magnitude_error", "aal_bias"} <= caught, caught
    # Every one of them is quoted by name and none is asserted as a defect,
    # because mlkit cannot read the polarity of a name it does not know.
    for finding in after:
        assert finding.severity == fabrication.UNCLASSIFIED_NAME, finding.render()
        assert finding.symbol in finding.render()


def test_control_a_generalised_a_name_invented_at_drive_time_is_refused(
    tmp_path: Path,
) -> None:
    """THE ANTI-RENAME CONTROL.

    The metric name is generated from ``secrets`` inside the test body. It is
    in no list, no fixture and no diff — it did not exist when this file was
    written. If the derivation is real the check fires; if someone "closed"
    E-038 by adding words to a vocabulary, it cannot.
    """
    invented = "zq" + secrets.token_hex(6)
    body = f'''
def {invented}(observed, predicted) -> float:
    """A quantity this repo computes, under a name nothing has ever seen."""
    if observed == 0:
        return 0.0
    return (predicted - observed) / observed
'''
    root = _write(tmp_path, "invented_metric.py", body)

    assert not fabrication.is_measured_name(invented)
    assert fabrication.scan_tree([root], base=tmp_path) == []

    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.contains(invented)
    findings = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    assert [f.symbol for f in findings] == [invented], [f.render() for f in findings]
    assert findings[0].severity == fabrication.UNCLASSIFIED_NAME


def test_control_a_the_invented_name_survives_being_respelled(tmp_path: Path) -> None:
    """The registry folds identifiers, so camelCase is not an escape either."""
    stem = "qx" + secrets.token_hex(5)
    body = f'''
def {stem}_bias(observed, predicted) -> float:
    """Declared here."""
    return (predicted - observed) / observed


def report(observed, predicted) -> dict:
    metrics = {{}}
    metrics["{stem}Bias"] = 0.0 if observed is None else predicted / observed
    return metrics
'''
    root = _write(tmp_path, "respelled.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    findings = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    assert any(f.symbol == f"{stem}Bias" for f in findings), [
        f.render() for f in findings
    ]


# ---------------------------------------------------------------------------
# CONTROL B — must stay silent
# ---------------------------------------------------------------------------


def test_control_b_a_covered_name_still_fires_and_still_fires_as_a_defect(
    tmp_path: Path,
) -> None:
    """Check-not-dead on a KNOWN R10 refusal.

    ``max_smd = max(...) if smds else 0.0`` reaching a report is R10's founding
    finding. It must still be a SATISFIES_GATE defect, not softened into the
    new NA lane, whether or not a registry is present.
    """
    body = '''
def gate(smds) -> dict:
    max_smd = max(smds.values()) if smds else 0.0
    return {"metrics": {"max_smd": max_smd}, "passed": max_smd < 0.1}
'''
    root = _write(tmp_path, "balance.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    for label, kwargs in (("no registry", {}), ("with registry", {"registry": registry})):
        findings = fabrication.scan_tree([root], base=tmp_path, **kwargs)
        assert [f.symbol for f in findings] == ["max_smd"], (label, findings)
        assert findings[0].severity == "SATISFIES_GATE", label


def test_control_b_a_repo_whose_registry_adds_nothing_gets_the_same_answer(
    tmp_path: Path,
) -> None:
    """A registry that overlaps the vocabulary entirely must move nothing."""
    body = '''
def compute_rmse(y, yhat) -> float:
    """Vocabulary already knows this name."""
    if len(y) == 0:
        return 0.0
    return float(((y - yhat) ** 2).mean() ** 0.5)
'''
    root = _write(tmp_path, "err.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    before = fabrication.scan_tree([root], base=tmp_path)
    after = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    assert [f.to_dict() for f in before] == [f.to_dict() for f in after]
    assert before, "fixture stopped firing; it is no longer a control"


def test_control_b_a_derived_name_cannot_walk_around_a_config_veto(
    tmp_path: Path,
) -> None:
    """``seed`` is vetoed by the vocabulary. Computing it must not un-veto it.

    Without this, the registry is a hole in the precision that
    ``HARD_CONFIG_TOKENS`` was measured to buy.
    """
    body = '''
def seed(run_index) -> int:
    """A repo that computes its seed does not thereby publish a metric."""
    return run_index * 7919


def report(cfg) -> dict:
    metrics = {}
    metrics["seed"] = cfg.get("seed", 0)
    return metrics
'''
    root = _write(tmp_path, "seeding.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.contains("seed"), "fixture no longer exercises the veto"
    assert fabrication.scan_tree([root], base=tmp_path, registry=registry) == []


def test_control_b_the_stricter_proof_new_accepts_a_subset_of_old(
    tmp_path: Path,
) -> None:
    """Mechanical, over the union of both universes — not asserted in prose.

    ACCEPTED means "this name is not a measured quantity, so R10 says nothing
    about a literal standing at it". The new rule must accept a SUBSET: every
    name the old rule refused is still refused, and at least one name it
    accepted is now refused.
    """
    root = _write(tmp_path, "metrics.py", SURGE_METRICS)
    registry = metric_registry.derive([root], base=tmp_path)

    universe = sorted(
        set(fabrication.MEASURED_TOKENS)
        | set(fabrication.HARD_CONFIG_TOKENS)
        | set(fabrication.THRESHOLD_TOKENS)
        | set(registry.names)
        | set(BLIND_NAMES)
        | set(COVERED_NAMES)
        | {"half_box_deg", "stride", "seq_len", "lat_min", "deductible_pct"}
    )
    for config_context in (False, True):
        old_accepted = {
            n for n in universe
            if not fabrication.is_measured_name(n, config_context=config_context)
        }
        new_accepted = {
            n for n in universe
            if fabrication.measured_name_source(
                n, config_context=config_context, registry=registry
            ) is None
        }
        assert new_accepted <= old_accepted, sorted(new_accepted - old_accepted)
    # And it is a PROPER subset: coverage was actually added.
    strictly_lost = {
        n for n in universe
        if not fabrication.is_measured_name(n)
        and fabrication.measured_name_source(n, registry=registry) is not None
    }
    assert strictly_lost >= {"false_alarm_ratio", "peak_magnitude_error", "aal_bias"}


# ---------------------------------------------------------------------------
# The anchor — a derivation that returns nothing must refuse, not fall back
# ---------------------------------------------------------------------------


def test_the_anchor_probe_is_recovered_on_every_derivation(tmp_path: Path) -> None:
    """The ``/health`` anchor, in this module's terms.

    A blind walk returns an empty set and looks exactly like a clean repo. The
    probe is a fixed source carrying one name the vocabulary knows and one it
    does not, run through the SAME derivation on every call.
    """
    root = _write(tmp_path, "anything.py", "X = 1\n")
    assert metric_registry.derive([root], base=tmp_path).refusal is None
    assert metric_registry._anchor_failure() is None


def test_check_not_dead_a_broken_derivation_refuses_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Kill the derivation; the anchor must notice rather than report empty.

    Without this the anchor is decoration: a probe nobody can make fail proves
    nothing about a probe that would fail if the walk broke.
    """
    monkeypatch.setattr(
        metric_registry, "_names_in", lambda source, display: {}
    )
    root = _write(tmp_path, "metrics.py", SURGE_METRICS)
    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.names == frozenset()
    assert registry.refusal is not None
    assert "E-038" in registry.refusal


def test_an_honestly_empty_registry_is_not_a_refusal(tmp_path: Path) -> None:
    """A repo that genuinely computes no figure must keep the verdict it had.

    Refusing on emptiness alone made R10 NA on two of its own fixture repos
    (``test_r10_passes_on_a_clean_tree`` and
    ``test_r10_fails_on_a_fabricated_default_and_writes_the_full_list``), which
    is a check going dark on trees it used to read correctly. The refusal is
    anchored on the probe instead, and emptiness is DISCLOSED rather than
    adjudicated.
    """
    root = _write(tmp_path, "nothing_computed.py", "X = 1\n\n\ndef go():\n    return X\n")
    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.names == frozenset()
    assert registry.files == 1
    assert registry.refusal is None
    assert registry.to_dict()["derived_names"] == 0


def test_an_empty_tree_is_not_a_refusal(tmp_path: Path) -> None:
    """R10 already NAs on a tree with no Python; this must not double-report."""
    root = tmp_path / "src"
    root.mkdir()
    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.files == 0
    assert registry.refusal is None


# ---------------------------------------------------------------------------
# Attacks on the repair itself
# ---------------------------------------------------------------------------

#: Every shape that was tried against the derivation, with the verdict
#: measured rather than assumed. Three of these were SILENT on the first draft
#: and are closed here; one is silent still and is pinned below.
EVASIONS = {
    "annotation deleted": '''
def false_alarm_ratio(mask_true, mask_pred):
    fp = (~mask_true & mask_pred).sum()
    tp = (mask_true & mask_pred).sum()
    return float(fp / (fp + tp)) if (fp + tp) > 0 else 0.0
''',
    "staticmethod on a class": '''
class SkillMetrics:
    @staticmethod
    def false_alarm_ratio(y, yhat) -> float:
        return float((~y & yhat).sum() / yhat.sum()) if yhat.sum() else 0.0
''',
    "private def, public alias": '''
def _false_alarm_ratio(y, yhat) -> float:
    return float((~y & yhat).sum() / yhat.sum()) if yhat.sum() else 0.0


false_alarm_ratio = _false_alarm_ratio
''',
    "string annotation": '''
def false_alarm_ratio(y, yhat) -> "float":
    return float((~y & yhat).sum() / yhat.sum()) if yhat.sum() else 0.0
''',
    "float | None annotation": '''
def false_alarm_ratio(y, yhat) -> float | None:
    return float((~y & yhat).sum() / yhat.sum()) if yhat.sum() else 0.0
''',
}


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_attack_the_shape_of_the_declaration_is_not_an_escape(
    label: str, tmp_path: Path
) -> None:
    """Respelling the DECLARATION must not take the name out of the universe.

    ``annotation deleted`` is the one that mattered: the first draft required
    ``-> float``, so removing one token silenced R10 on surge's own
    ``false_alarm_ratio``. A restriction that cheap to satisfy is not a
    restriction.
    """
    root = _write(tmp_path, "m.py", EVASIONS[label])
    assert fabrication.scan_tree([root], base=tmp_path) == [], label
    registry = metric_registry.derive([root], base=tmp_path)
    assert registry.contains("false_alarm_ratio"), label
    findings = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    assert findings, label
    assert all(f.severity == fabrication.UNCLASSIFIED_NAME for f in findings), label


def test_attack_declared_in_one_file_and_fabricated_in_another(tmp_path: Path) -> None:
    """The registry is the REPO's, not the file's. Moving the sink is no escape."""
    root = tmp_path / "src"
    root.mkdir()
    (root / "declared.py").write_text(
        "def false_alarm_ratio(y, yhat) -> float:\n"
        "    return float((~y & yhat).sum() / yhat.sum())\n"
    )
    (root / "elsewhere.py").write_text(
        "def summarise(bundle) -> dict:\n"
        "    metrics = {}\n"
        '    metrics["false_alarm_ratio"] = bundle.get("false_alarm_ratio", 0.0)\n'
        "    return metrics\n"
    )
    registry = metric_registry.derive([root], base=tmp_path)
    findings = fabrication.scan_tree([root], base=tmp_path, registry=registry)
    assert [(f.path, f.symbol) for f in findings] == [
        ("src/elsewhere.py", "false_alarm_ratio")
    ], [f.render() for f in findings]


def test_residual_a_metric_computed_inside_a_call_is_still_invisible(
    tmp_path: Path,
) -> None:
    """PINNED WRONG SILENCE. Fails the day it closes — update the docs then.

    ``float(np.divide(fp, fp + tp))`` leaves no arithmetic ``BinOp`` at the
    return, so the name never enters the registry and the ``0.0`` fallback is
    not reported. Admitting any call would enrol every function in the repo,
    so this is a stated limit. It is recorded in
    ``core/metric_registry.py`` under "WHAT STILL EVADES THIS".
    """
    body = '''
import numpy as np


def false_alarm_ratio(mask_true, mask_pred) -> float:
    fp = (~mask_true & mask_pred).sum()
    tp = (mask_true & mask_pred).sum()
    return float(np.divide(fp, fp + tp)) if (fp + tp) > 0 else 0.0
'''
    root = _write(tmp_path, "m.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    assert not registry.contains("false_alarm_ratio"), (
        "the call-shaped computation is now derived — E-038's residual has "
        "closed. Update core/metric_registry.py and this test rather than "
        "re-pinning the silence."
    )
    assert fabrication.scan_tree([root], base=tmp_path, registry=registry) == []


def test_residual_a_computed_local_returned_by_name_is_an_OLD_r10_limit(
    tmp_path: Path,
) -> None:
    """Not a regression: R10 is equally silent here on a VOCABULARY name.

    ``value = ... if ... else 0.0; return value`` is not a shape R10's scanner
    attributes to the enclosing function, and that was true before E-038 --
    measured on ``rmse``, which the word list has always known. Pinning the
    pair keeps the two limits from being confused with each other.
    """
    shape = '''
def {name}(y, yhat) -> float:
    value = ((y - yhat) ** 2).mean() ** 0.5 if len(y) else 0.0
    return value
'''
    vocabulary_root = _write(tmp_path, "known.py", shape.format(name="rmse"))
    assert fabrication.scan_tree([vocabulary_root], base=tmp_path) == []

    other = tmp_path / "other"
    other.mkdir()
    (other / "derived.py").write_text(shape.format(name="false_alarm_ratio"))
    registry = metric_registry.derive([other], base=tmp_path)
    assert registry.contains("false_alarm_ratio"), "the NAME is derived"
    assert fabrication.scan_tree([other], base=tmp_path, registry=registry) == []


def test_the_derivation_does_not_enrol_knobs_or_payload_keys(tmp_path: Path) -> None:
    """The precision leg, measured rather than argued.

    An earlier draft derived the universe from every numeric-leaf key in the
    repo's committed JSON. On surge that surface held 471 names and produced 28
    findings, 23 of them knobs. Restriction (2) — the callable must COMPUTE its
    figure — is what excludes them, so it is pinned here.
    """
    body = '''
HALF_BOX_DEG = 0.25


def build(cfg) -> dict:
    return {
        "half_box_deg": cfg.get("half_box_deg", HALF_BOX_DEG),
        "stride": cfg.get("stride", 24),
        "lat_min": cfg.get("lat_min", 0.0),
        "deductible_pct": cfg.get("deductible_pct", 0.0),
    }


def stride(cfg) -> int:
    """Returns a knob unchanged: reads, does not compute."""
    return cfg["stride"]
'''
    root = _write(tmp_path, "knobs.py", body)
    registry = metric_registry.derive([root], base=tmp_path)
    assert not (
        registry.names
        & {"halfboxdeg", "stride", "latmin", "deductiblepct", "build"}
    ), sorted(registry.names)
