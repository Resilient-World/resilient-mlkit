"""R11 controls: does the check fire when it should, and stay silent when it should not.

Every test here is one half of a matched pair. The POSITIVE fixture carries the
defect; the NEGATIVE fixture is the SAME CODE with the one thing changed that
makes it honest -- almost always a single string. That pairing is the whole
point: a check that fires on the positive proves nothing on its own, because a
check that fires on everything also fires on the positive. R11's entire claim
is that it can tell a fabrication from a fixture, and the only evidence for
that claim is a fixture it stays quiet about.

The first pair is the incident itself: resilient-choco PR #160, five files
under ``scripts/`` whose targets were a closed-form function of RNG-drawn
features, stamped ``label_origin="observed_ccc"``, split into val and test,
past fifty-one green guard tests because that repo's generated-paths guard
polices ``src/`` and ``dvc.yaml`` only.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.core import fabricated_targets as ft

# The incident shape, parameterised on the one string that decides whether it
# is a fabrication or a fixture. Everything else -- the draw, the closed-form
# target, the split, the source id, the licence class -- is held identical
# between the positive and negative controls, so the only variable in the
# experiment is the provenance claim.
INCIDENT = """
    import numpy as np

    def build_regional_panel(feature_names, years, level):
        rng = np.random.default_rng(20260817)
        rows = []
        for i, y in enumerate(years):
            feat = rng.normal(loc=level, scale=0.08, size=len(feature_names))
            tonnes = 4500.0 * (i + 1) * (1.0 + 0.03 * (y - 2019)) \\
                + feat[1] * 1.5 - feat[0] * 20.0
            rows.append({{
                "year": y,
                "tonnes": tonnes,
                "split": "test",
                "source_id": "civ_ccc_regional",
                "label_origin": "{label_origin}",
                "feature_origin": "era5_monthly_reduction",
                "licence_class": "trainable",
            }})
        return rows
"""


def scan(src: str) -> list[ft.Finding]:
    return ft.scan_source(textwrap.dedent(src), "scripts/build_panel.py")


# ---------------------------------------------------------------------------
# The incident, both ways round
# ---------------------------------------------------------------------------


def test_positive_control_the_choco_pr160_shape_is_reported():
    """POSITIVE. resilient-choco PR #160.

    A target computed in closed form from RNG-drawn features, stamped
    ``label_origin="observed_ccc"`` and written into the test split.
    """
    findings = scan(INCIDENT.format(label_origin="observed_ccc"))

    assert len(findings) == 1, [f.render() for f in findings]
    finding = findings[0]
    assert finding.field == "tonnes"
    assert finding.severity == ft.TARGET_FABRICATED
    # The report must name the field that makes it a fabrication, not merely
    # say "something is wrong here".
    assert finding.claim_field == "label_origin"
    assert finding.claim_value == "observed_ccc"
    # ...and it must trace back to the draw, at the draw's own line.
    assert finding.origin_symbol == "feat"
    assert "normal" in finding.origin_call
    assert finding.origin_line < finding.line
    # The aggravating fact: this row was headed for an evaluation split.
    assert finding.split == "test"
    # The opaque stamps corroborate; none of them was the trigger.
    assert any("source_id" in c for c in finding.corroborating)
    assert any("licence_class" in c for c in finding.corroborating)


def test_negative_control_the_same_code_labelled_synthetic_is_silent():
    """NEGATIVE, and the single most important test in this file.

    Byte-for-byte the positive control with one string changed. The draw is
    still a draw and the target is still a closed form of the features; what
    has changed is that the record now says so. Building fixtures is a
    legitimate and necessary thing to do, and a check that cannot tell a
    fixture from a fabrication is a check that will be turned off.
    """
    assert scan(INCIDENT.format(label_origin="synthetic")) == []


def test_negative_control_simulated_and_generated_are_also_honest():
    """NEGATIVE. The declaration vocabulary is not a single magic word."""
    for word in ("simulated", "generated_fixture", "rng_draw", "demo_panel"):
        assert scan(INCIDENT.format(label_origin=word)) == [], word


def test_negative_control_an_opaque_stamp_alone_never_triggers():
    """NEGATIVE. ``source_id="civ_ccc_regional"`` names something; it claims nothing.

    Deciding whether that string denotes a real registry is a judgement about
    the world, and a gate that made it would be guessing. Only an explicit
    claim of observation triggers.
    """
    findings = scan(
        """
        import numpy as np

        def build(years):
            rng = np.random.default_rng(0)
            rows = []
            for y in years:
                tonnes = float(rng.normal(4500.0, 100.0))
                rows.append({
                    "year": y,
                    "tonnes": tonnes,
                    "source_id": "civ_ccc_regional",
                    "feature_origin": "era5_monthly_reduction",
                    "licence_class": "trainable",
                })
            return rows
        """
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Positive set — the shapes the defect takes once somebody has seen the check
# ---------------------------------------------------------------------------


def test_taint_through_a_module_local_helper_is_followed():
    """POSITIVE. The commonest refactor: lift the draw into a helper.

    Without one level of inter-procedural propagation this is the whole
    evasion, and it is the first thing anybody writes after being told their
    inline ``rng.normal`` was flagged.
    """
    findings = scan(
        """
        import numpy as np

        def _draw_features(n):
            rng = np.random.default_rng(7)
            return rng.normal(0.0, 1.0, size=n)

        def build(years):
            rows = []
            for y in years:
                feat = _draw_features(12)
                rows.append({
                    "year": y,
                    "yield_t_ha": 1.4 + 0.2 * feat[0],
                    "label_origin": "observed_ccc",
                })
            return rows
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].field == "yield_t_ha"
    assert findings[0].severity == ft.TARGET_FABRICATED
    assert "_draw_features()" in findings[0].origin_call


def test_stamp_lifted_into_a_module_constant_and_spread_is_followed():
    """POSITIVE. ``{**PROVENANCE, "tonnes": t}`` hides the stamp one level up."""
    findings = scan(
        """
        import numpy as np

        PROVENANCE = {
            "source_id": "civ_ccc_regional",
            "label_origin": "observed_ccc",
            "licence_class": "trainable",
        }

        def build(years):
            rng = np.random.default_rng(1)
            return [
                {**PROVENANCE, "year": y, "tonnes": float(rng.normal(4500.0, 90.0))}
                for y in years
            ]
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].claim_field == "label_origin"


def test_dataframe_column_stamp_is_followed():
    """POSITIVE. The pandas shape: data in at construction, stamp bolted on after."""
    findings = scan(
        """
        import numpy as np
        import pandas as pd

        def build(years):
            rng = np.random.default_rng(3)
            tonnes = rng.normal(4500.0, 120.0, size=len(years))
            frame = pd.DataFrame({"year": years, "tonnes": tonnes})
            frame["label_origin"] = "observed_ccc"
            frame["licence_class"] = "trainable"
            return frame
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].claim_field == "label_origin"
    assert findings[0].field == "frame"


def test_a_constructor_call_is_a_record_too():
    """POSITIVE. Not every record is a dict literal."""
    findings = scan(
        """
        import numpy as np

        def build(sites):
            rng = np.random.default_rng(5)
            out = []
            for site in sites:
                out.append(PanelRow(
                    site=site,
                    production=float(rng.lognormal(8.0, 0.3)),
                    label_origin="observed_ccc",
                ))
            return out
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].field == "production"
    assert findings[0].claim_field == "label_origin"


def test_a_synthetic_filename_does_not_excuse_a_false_stamp():
    """POSITIVE, and the design decision that separates R11 from R10.

    R10 stays quiet inside a file whose name declares it a generator, because
    a draw there is doing what the name says. R11 must not, because the stamp
    is a claim about the DATA and the filename is not. A file called
    ``make_synthetic_panel.py`` that stamps its rows ``observed`` is not
    excused by its own name; it is contradicted by it.
    """
    source = textwrap.dedent(
        """
        import numpy as np

        def make_synthetic_panel(years):
            rng = np.random.default_rng(11)
            return [
                {"year": y, "target": float(rng.normal(1.0, 0.1)), "kind": "real"}
                for y in years
            ]
        """
    )
    findings = ft.scan_source(source, "scripts/make_synthetic_panel.py")
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].claim_field == "kind"
    assert findings[0].claim_value == "real"


def test_a_fabricated_feature_beside_an_honest_target_is_ranked_lower():
    """POSITIVE, lower severity. The draw reaches an input, not the target."""
    findings = scan(
        """
        import numpy as np

        def build(rows_in):
            rng = np.random.default_rng(2)
            out = []
            for row in rows_in:
                out.append({
                    "rainfall_mm": float(rng.gamma(2.0, 30.0)),
                    "tonnes": row.tonnes,
                    "feature_origin": "observed station network",
                })
            return out
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].severity == ft.INPUT_FABRICATED
    assert findings[0].field == "rainfall_mm"


# ---------------------------------------------------------------------------
# Negative set — the code that must never fire
# ---------------------------------------------------------------------------


def test_negative_an_observed_record_with_no_rng_anywhere_is_silent():
    """NEGATIVE. Real data, honestly stamped. The overwhelming majority case."""
    assert scan(
        """
        def build(reader):
            return [
                {
                    "year": r.year,
                    "tonnes": r.tonnes,
                    "source_id": "civ_ccc_regional",
                    "label_origin": "observed_ccc",
                    "licence_class": "trainable",
                }
                for r in reader
            ]
        """
    ) == []


def test_negative_a_draw_with_no_provenance_stamp_is_silent():
    """NEGATIVE. Data augmentation, jitter, a bootstrap. No claim, no finding."""
    assert scan(
        """
        import numpy as np

        def jitter(rows):
            rng = np.random.default_rng(0)
            return [{"year": r.year, "tonnes": r.tonnes + rng.normal(0, 1)} for r in rows]
        """
    ) == []


def test_negative_a_drawn_seed_beside_observed_data_is_configuration():
    """NEGATIVE. ``seed`` is a knob, not a measurement.

    Reuses R10's configuration vocabulary rather than growing a second one:
    two definitions of "this is configuration" is the same as none.
    """
    assert scan(
        """
        import numpy as np

        def build(reader):
            rng = np.random.default_rng(0)
            seed = int(rng.integers(0, 2**31))
            batch_size = int(rng.integers(16, 64))
            return [
                {
                    "tonnes": r.tonnes,
                    "seed": seed,
                    "batch_size": batch_size,
                    "label_origin": "observed_ccc",
                }
                for r in reader
            ]
        """
    ) == []


def test_negative_a_draw_in_another_function_does_not_taint_this_record():
    """NEGATIVE, and it guards a real implementation trap.

    ``ast.walk`` queues the children of everything it visits, so a scope walk
    built on it carries every nested function's body into the enclosing scope
    and lets a draw over here taint a record over there. Scope boundaries are
    enforced on the descent; this is the test that says so.
    """
    assert scan(
        """
        import numpy as np

        def make_fixture(n):
            rng = np.random.default_rng(0)
            tonnes = rng.normal(4500.0, 100.0, size=n)
            return tonnes

        def load_observed(reader):
            return [
                {"tonnes": r.tonnes, "label_origin": "observed_ccc"}
                for r in reader
            ]
        """
    ) == []


def test_negative_a_record_declaring_itself_anywhere_is_not_adjudicated():
    """NEGATIVE, with its cost stated.

    A record carrying a simulation declaration in any provenance field is
    never reported, even when another field claims observation. The narrow
    evasion (stamp both) is accepted deliberately: adjudicating internally
    inconsistent metadata is review work, and the alternative is a check that
    fires on honest fixtures.
    """
    assert scan(
        """
        import numpy as np

        def build(years):
            rng = np.random.default_rng(0)
            return [
                {
                    "tonnes": float(rng.normal(4500.0, 90.0)),
                    "label_origin": "observed_ccc",
                    "evidence_mode": "synthetic",
                }
                for y in years
            ]
        """
    ) == []


def test_negative_a_simulation_word_outside_a_provenance_field_does_not_excuse():
    """POSITIVE in effect: the excusal vocabulary is read from stamps only.

    A ``"note": "synthetic"`` beside a false ``label_origin`` would otherwise
    be a one-word evasion. Notes do not travel into a manifest; stamps do.
    """
    findings = scan(
        """
        import numpy as np

        def build(years):
            rng = np.random.default_rng(0)
            return [
                {
                    "tonnes": float(rng.normal(4500.0, 90.0)),
                    "note": "synthetic panel for testing",
                    "label_origin": "observed_ccc",
                }
                for y in years
            ]
        """
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].claim_field == "label_origin"


# ---------------------------------------------------------------------------
# Vocabulary units
# ---------------------------------------------------------------------------


def test_claim_classification():
    assert ft.classify_claim("observed_ccc") == ft.OBSERVED
    assert ft.classify_claim("observedCCC") == ft.OBSERVED
    assert ft.classify_claim("real") == ft.OBSERVED
    assert ft.classify_claim("NOAA CO-OPS gauge record") == ft.OBSERVED
    assert ft.classify_claim("synthetic") == ft.SIMULATED
    assert ft.classify_claim("bootstrap_resample") == ft.SIMULATED
    # A declaration beats a claim, so an honestly-hedged label stays silent.
    assert ft.classify_claim("synthetic observed-style panel") == ft.SIMULATED
    # Names something; adjudicates nothing.
    assert ft.classify_claim("civ_ccc_regional") == ft.OPAQUE
    assert ft.classify_claim("era5_monthly_reduction") == ft.OPAQUE
    assert ft.classify_claim("") == ft.OPAQUE


def test_target_and_config_vocabularies():
    assert ft.is_target_field("tonnes")
    assert ft.is_target_field("y")
    assert ft.is_target_field("yield_t_ha")
    assert not ft.is_target_field("rainfall_mm")
    assert ft.is_config_field("seed")
    assert ft.is_config_field("batch_size")
    assert not ft.is_config_field("tonnes")


def test_tests_directory_is_not_walked(tmp_path):
    """The exclusion that makes this very file possible.

    A test asserting the check fires has to CONTAIN the defect it asserts on.
    Scanning ``tests/`` would make every control fixture a finding, and test
    data does not enter a manifest, so nothing measured is lost by the
    exclusion. The scripts directory beside it must still be walked.
    """
    body = textwrap.dedent(
        """
        import numpy as np
        def build():
            rng = np.random.default_rng(0)
            return {"tonnes": float(rng.normal(1, 1)), "label_origin": "observed_ccc"}
        """
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_panel.py").write_text(body)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "build_panel.py").write_text(body)
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "vendored.py").write_text(body)

    findings = ft.scan_repo(tmp_path)
    assert [f.path for f in findings] == ["scripts/build_panel.py"]


# ---------------------------------------------------------------------------
# The CHECK, not the scanner
#
# Everything above exercises `core.fabricated_targets` directly. That leaves the
# wrapper untested, and the wrapper is where the consequential decisions live:
# what counts as unmeasurable, whether the walk is scoped to declared trees, and
# whether R11 reaches R5 before R5 counts rows by a field R11 has just shown to
# be false. A scanner that is right inside a check that never calls it on the
# right files is a check that measures nothing.
# ---------------------------------------------------------------------------


def _repo(tmp_path, toml: str, files: dict[str, str]):
    from resilient_mlkit.core.repo import Repo

    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    for rel, body in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body))
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path):
    from resilient_mlkit.checks import RunContext

    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def test_r11_is_registered_and_gates_and_runs_before_R5():
    """The ordering claim in the module docstring, held as an assertion.

    R11 must precede R5, and the reason is not tidiness: R5 counts rows by the
    provenance field R11 exists to falsify. An R5 PASS recorded after an R11
    FAIL is a pass counted with a ruler the previous check just broke, and a
    reader of the readiness table has no way to see that from the two verdicts
    side by side.
    """
    from resilient_mlkit.checks import PHASE_ORDER, load_all
    from resilient_mlkit.portfolio import gating_ids

    load_all()
    order = PHASE_ORDER["readiness"]
    assert "R11" in order
    assert order.index("R11") < order.index("R5")
    # Third, after the licence gate and the other pure AST walk: same cost, and
    # it invalidates the inputs of everything after it.
    assert order[:3] == ["R9", "R10", "R11"]
    assert "R11" in gating_ids()


def test_positive_control_r11_fails_on_the_incident_and_writes_the_full_list(tmp_path):
    """FIRES: the choco PR #160 shape, through the check rather than the scanner."""
    from resilient_mlkit.checks.readiness import (
        R11_REPORT_RELPATH,
        r11_fabricated_targets,
    )
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n',
        {"scripts/build_panel.py": INCIDENT.format(label_origin="observed_ccc")},
    )
    result = r11_fabricated_targets(repo, _ctx(tmp_path))

    assert result.status is Status.FAIL
    assert result.evidence["target_fabricated"] == 1
    assert result.evidence["files_walked"] == 1
    # The row declared `split: "test"`, so this is R5's invariant broken at the
    # source. The reason has to say so, because that is what changes the
    # reader's next action.
    assert result.evidence["stamped_into_holdout"] == 1
    assert "R5's invariant" in result.reason
    assert "label_origin" in result.reason

    written = (tmp_path / R11_REPORT_RELPATH).read_text()
    assert "TARGET_FABRICATED" in written
    assert "scripts/build_panel.py" in written
    assert "test-nonce" in written


def test_negative_control_r11_passes_on_the_same_repo_labelled_synthetic(tmp_path):
    """SILENT: one string different, and the repo is building fixtures.

    The scanner-level pair for this exists above. It is repeated at the check
    level because a wrapper is perfectly capable of turning a clean scan into a
    FAIL -- or of reporting PASS while walking nothing -- and neither would show
    up in a scanner test.
    """
    from resilient_mlkit.checks.readiness import (
        R11_REPORT_RELPATH,
        r11_fabricated_targets,
    )
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n',
        {"scripts/build_panel.py": INCIDENT.format(label_origin="synthetic")},
    )
    result = r11_fabricated_targets(repo, _ctx(tmp_path))

    assert result.status is Status.PASS
    assert result.evidence["findings"] == 0
    # A PASS is only worth anything if something was walked. Without this the
    # control is satisfied by an empty repo.
    assert result.evidence["files_walked"] == 1
    assert "(none)" in (tmp_path / R11_REPORT_RELPATH).read_text()


def test_r11_walks_the_undeclared_tree_that_R10_cannot_see(tmp_path):
    """The pair that is R11's entire reason for existing.

    Same repo, same fixture, two checks. `[source] trees = ["src"]` is clean,
    and the fabrication is in `scripts/` -- which is where the real incident
    was. R10 is scoped to the declared trees, correctly, and reports PASS. R11
    is not scoped, and reports FAIL.

    Run together they say something neither says alone: R10 passing is a
    statement about the declared trees and nothing more, and if R11 did not
    exist that PASS would be the only signal in the table.
    """
    from resilient_mlkit.checks.readiness import (
        r10_fabricated_defaults,
        r11_fabricated_targets,
    )
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n',
        {
            "src/model.py": "def predict(x):\n    return x * 2.0\n",
            "scripts/build_panel.py": INCIDENT.format(label_origin="observed_ccc"),
        },
    )
    ctx = _ctx(tmp_path)

    r10 = r10_fabricated_defaults(repo, ctx)
    assert r10.status is Status.PASS
    assert r10.evidence["files_walked"] == 1, "R10 saw src/ only, which is right"

    r11 = r11_fabricated_targets(repo, ctx)
    assert r11.status is Status.FAIL
    assert r11.evidence["files_walked"] == 2, "R11 saw both, which is the point"
    assert r11.evidence["target_fabricated"] == 1


def test_r11_is_NA_not_PASS_when_there_is_no_python_to_walk(tmp_path):
    """A walk over nothing that reports green is the defect, applied to the check."""
    from resilient_mlkit.checks.readiness import r11_fabricated_targets
    from resilient_mlkit.core.result import Status

    repo = _repo(tmp_path, '[repo]\nname = "x"\n', {"README.md": "no code here\n"})
    result = r11_fabricated_targets(repo, _ctx(tmp_path))

    assert result.status is Status.NA
    assert "unmeasured, not established" in result.reason
    assert result.evidence["files_walked"] == 0


def test_r11_needs_no_declared_tree_at_all(tmp_path):
    """SILENT on the config, loud on the code: there is no NA-by-omission path.

    R10 goes NA when a repo declares no `[source] trees`, and that is right for
    R10. R11 must not inherit it, because the declared-tree list is exactly the
    surface an author controls -- an author who could make R11 quiet by
    deleting a line of TOML would have a gate they can switch off.
    """
    from resilient_mlkit.checks.readiness import r11_fabricated_targets
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n',
        {"scripts/build_panel.py": INCIDENT.format(label_origin="observed_ccc")},
    )
    result = r11_fabricated_targets(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert result.evidence["files_walked"] == 1
