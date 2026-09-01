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


def test_positive_stamp_both_is_a_finding_not_an_exemption():
    """POSITIVE. This test used to assert the opposite, and that was the defect.

    A record carrying a simulation declaration in ANY provenance field was
    exempt, even when another field claimed observation. The module documented
    the hole itself -- "the cost is a narrow evasion (stamp both) and it is
    stated here rather than hidden" -- which meant the cheapest way past R11
    was to keep the observed claim R5 counts by and add a second field nothing
    counts by. Stating an evasion does not close it.

    R5 keys its provenance contract on ONE field. A second field saying
    ``synthetic`` does not make the first one true; it makes the record read
    one way to the counter and the other way to a human, which is the defect
    this module exists for rather than an exemption from it.

    The honest fixture is still silent, and that pair is one test down:
    ``test_negative_control_the_same_code_labelled_synthetic_is_silent``
    declares simulation and claims nothing.
    """
    findings = scan(
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
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].rule == ft.CONTRADICTED_STAMP
    # The OBSERVED stamp is reported, because that is the one that travels
    # into a manifest; the declaration is carried as the conflict.
    assert findings[0].claim_field == "label_origin"
    assert any("evidence_mode" in c for c in findings[0].corroborating)


def test_positive_one_value_that_both_claims_and_declares_is_a_finding():
    """POSITIVE. arabica's rejected pre-registration label, held as a control.

    ``synthetic_weather_real_isd_fallback`` was pre-registered in
    resilient-arabica as the repair for E-046 and rejected by the control
    written alongside it: ``classify_claim`` let the simulation token beat the
    observation token in the same string, so R11 went quiet while the label
    still said "real ISD" to every human who read it. That precedence rule is
    gone.
    """
    for label in ("synthetic_weather_real_isd_fallback",
                  "synthetic_farm_sensor_fallback",
                  "simulated_gauge_record"):
        findings = scan(INCIDENT.format(label_origin=label))
        assert len(findings) == 1, (label, [f.render() for f in findings])
        assert findings[0].rule == ft.CONTRADICTED_STAMP, label
        assert findings[0].claim_value == label


def test_positive_a_synthetic_loader_named_after_a_real_product_is_a_finding():
    """POSITIVE, and the shape R11 could not fire on at all.

    ``ERA5LandBaselineLoader.iter_grid`` in resilient-arabica, reduced. Every
    yielded field comes from ``self.rng``; the stamp is ``source="era5_land"``,
    which tokenises to ``{era5, land, era5land}`` and met neither claim
    vocabulary, so it classified OPAQUE and OPAQUE never triggered. The repo
    recorded it as an honest negative in E-051 and left it standing, because
    the check as written had nothing to say about it.

    Nothing about the string decides this. The record is a finding because
    every value on it was manufactured in this process, so the source it names
    cannot have supplied any of them.
    """
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            class ERA5LandBaselineLoader:
                def __init__(self, seed=44):
                    self.rng = np.random.default_rng(seed)

                def iter_grid(self, lat_min=-20.0, lat_max=22.0, resolution=0.5, days=365):
                    lats = np.arange(lat_min, lat_max + resolution, resolution)
                    for lat in lats:
                        for d in range(days):
                            seasonal = 4.0 * np.sin(2.0 * np.pi * (d % 365) / 365.0)
                            t2m = 22.0 + seasonal + self.rng.normal(0, 1.2)
                            precip = max(0.0, self.rng.gamma(2.0, 2.8))
                            yield GridSample(
                                lat=float(lat),
                                elevation=1000.0,
                                t2m=float(t2m),
                                precip=float(precip),
                                source="era5_land",
                            )
            """
        ),
        "src/training/finetune_aurora_coffee.py",
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].rule == ft.CONTRADICTED_SOURCE
    assert findings[0].claim_field == "source"
    assert findings[0].claim_value == "era5_land"


def test_negative_the_same_loader_declaring_itself_is_silent():
    """NEGATIVE, the matched half. One string, and it is a fixture again.

    This is the pair that says the new rule adjudicates the CONSTRUCTION and
    not the product name: the construction is byte-identical to the positive
    control above.
    """
    assert ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            class ERA5LandBaselineLoader:
                def __init__(self, seed=44):
                    self.rng = np.random.default_rng(seed)

                def iter_grid(self, lat_min=-20.0, lat_max=22.0, resolution=0.5, days=365):
                    lats = np.arange(lat_min, lat_max + resolution, resolution)
                    for lat in lats:
                        for d in range(days):
                            seasonal = 4.0 * np.sin(2.0 * np.pi * (d % 365) / 365.0)
                            t2m = 22.0 + seasonal + self.rng.normal(0, 1.2)
                            precip = max(0.0, self.rng.gamma(2.0, 2.8))
                            yield GridSample(
                                lat=float(lat),
                                elevation=1000.0,
                                t2m=float(t2m),
                                precip=float(precip),
                                source="era5_land_shaped_synthetic_grid",
                            )
            """
        ),
        "src/training/finetune_aurora_coffee.py",
    ) == []


def test_positive_a_fabricated_gauge_network_is_a_finding_and_its_honest_twin_is_not():
    """POSITIVE + NEGATIVE in one file, both from resilient-surge as shipped.

    ``fetch_ntslf`` claims in its docstring to fetch from the UK National Tidal
    and Sea Level Facility, performs no fetch, and returns
    ``water_level_m=np.random.normal(3.0, 0.3, 24)`` stamped ``source="ntslf"``.
    Twenty lines above it, the same construction stamped
    ``source="noaa_coops_synthetic"`` is an honest offline fixture.

    The caller's ``station_id`` flows onto the record untouched, and that must
    not excuse it: a source stamp is a claim about where the MEASUREMENTS came
    from, and an identifier passed through is not a measurement. Requiring
    every field to be manufactured is the same naming defeat one level down.
    """
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np
            import pandas as pd

            class GaugeIngestion:
                WMO_QC_GOOD = 1

                async def fetch_ntslf(self, station_id: str) -> pd.DataFrame:
                    '''Fetch from UK National Tidal and Sea Level Facility.'''
                    times = pd.date_range("2024-01-01", periods=24, freq="h")
                    return pd.DataFrame(
                        {
                            "station_id": [station_id] * 24,
                            "lat": [53.5],
                            "lon": [-3.0],
                            "timestamp": times,
                            "water_level_m": np.random.normal(3.0, 0.3, 24),
                            "qc_flag": [self.WMO_QC_GOOD] * 24,
                            "source": "ntslf",
                        }
                    )

                async def fetch_offline(self, station_id: str) -> pd.DataFrame:
                    '''Synthetic data for offline tests only.'''
                    times = pd.date_range("2024-01-01", periods=24, freq="h")
                    return pd.DataFrame(
                        {
                            "station_id": [station_id] * 24,
                            "lat": [53.5],
                            "lon": [-3.0],
                            "timestamp": times,
                            "water_level_m": np.random.normal(3.0, 0.3, 24),
                            "qc_flag": [self.WMO_QC_GOOD] * 24,
                            "source": "noaa_coops_synthetic",
                        }
                    )
            """
        ),
        "src/resilient_surge/assimilation/gauge_ingestion.py",
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].rule == ft.CONTRADICTED_SOURCE
    assert findings[0].claim_value == "ntslf"
    assert findings[0].field == "water_level_m"


def test_negative_a_real_loader_wearing_the_same_source_name_is_silent():
    """NEGATIVE, and the one this rule would be worthless without.

    Same stamp, same jitter, same everything -- except one value on the record
    was read from a file. The moment anything could have come from outside,
    the source label may well describe where it came from, and the rule stops.
    """
    assert scan(
        """
        import numpy as np
        import xarray as xr

        def load_grid(path, seed=0):
            rng = np.random.default_rng(seed)
            ds = xr.open_dataset(path)
            return [
                {
                    "t2m": float(row.t2m) + rng.normal(0, 0.01),
                    "elevation": 1000.0,
                    "source": "era5_land",
                }
                for row in ds
            ]
        """
    ) == []


def test_negative_an_opaque_stamp_on_data_passed_in_is_silent():
    """NEGATIVE. A parameter with no default is how data arrives.

    ``def build(years)`` may be handed a real index. The record is not wholly
    manufactured, so the opaque source id is not adjudicated -- which is what
    keeps ``test_negative_control_an_opaque_stamp_alone_never_triggers``
    green rather than a threshold being loosened to spare it.
    """
    assert scan(
        """
        import numpy as np

        def build(years):
            rng = np.random.default_rng(0)
            return [
                {"year": y, "tonnes": float(rng.normal(4500.0, 90.0)),
                 "source_id": "civ_ccc_regional"}
                for y in years
            ]
        """
    ) == []


def test_positive_hoisting_a_literal_out_of_the_function_is_still_a_finding():
    """POSITIVE x2. VERIFY-R11-A4, found by attacking the repair.

    The repair made ``CONTRADICTED_SOURCE`` read the construction instead of
    the label, and the construction was then defeated by a refactor with no
    semantic content: move one literal out of the function body. Both of
    these are the shipped ERA5 loader with ``22.0`` written somewhere else,
    and both were SILENT before this control existed.
    """
    module_level = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            BASE_T = 22.0

            class Loader:
                def __init__(self, seed=44):
                    self.rng = np.random.default_rng(seed)

                def iter_grid(self, days=365):
                    for d in range(days):
                        yield GridSample(
                            t2m=float(BASE_T + self.rng.normal(0, 1.2)),
                            precip=float(max(0.0, self.rng.gamma(2.0, 2.8))),
                            source="era5_land",
                        )
            """
        ),
        "src/loaders/grid.py",
    )
    assert len(module_level) == 1, [f.render() for f in module_level]
    assert module_level[0].rule == ft.CONTRADICTED_SOURCE

    class_attribute = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            class Loader:
                BASE_T = 22.0

                def __init__(self, seed=44):
                    self.rng = np.random.default_rng(seed)

                def iter_grid(self, days=365):
                    for d in range(days):
                        yield GridSample(
                            t2m=float(self.BASE_T + self.rng.normal(0, 1.2)),
                            precip=float(max(0.0, self.rng.gamma(2.0, 2.8))),
                            source="era5_land",
                        )
            """
        ),
        "src/loaders/grid.py",
    )
    assert len(class_attribute) == 1, [f.render() for f in class_attribute]
    assert class_attribute[0].rule == ft.CONTRADICTED_SOURCE


def test_negative_an_outer_binding_that_reads_a_file_is_not_a_constant():
    """NEGATIVE x3, the matched half of the control above.

    Seeding a scope with names bound outside it is only safe while the
    binding is provably manufactured. Each of these puts a file read where
    the literal was, and each must stay silent -- otherwise the seed has
    become an over-approximation, which is the one direction
    ``manufactured_of`` may never lean.
    """
    from_module = """
        import numpy as np
        import pandas as pd

        BASELINE = pd.read_csv("baseline.csv")

        class Loader:
            def __init__(self, seed=44):
                self.rng = np.random.default_rng(seed)

            def iter_grid(self, days=365):
                for d in range(days):
                    yield GridSample(
                        t2m=float(BASELINE.t2m.mean() + self.rng.normal(0, 1.2)),
                        source="era5_land",
                    )
    """
    from_class = """
        import numpy as np
        import pandas as pd

        class Loader:
            TABLE = pd.read_parquet("t.pq")

            def __init__(self, seed=44):
                self.rng = np.random.default_rng(seed)

            def iter_grid(self, days=365):
                for d in range(days):
                    yield GridSample(
                        t2m=float(self.TABLE.t2m.mean() + self.rng.normal(0, 1.2)),
                        source="era5_land",
                    )
    """
    shadowed = """
        import numpy as np
        import xarray as xr

        BASE_T = 22.0

        class Loader:
            def __init__(self, seed=44):
                self.rng = np.random.default_rng(seed)

            def iter_grid(self, path, days=365):
                BASE_T = xr.open_dataset(path).t2m.mean()
                for d in range(days):
                    yield GridSample(
                        t2m=float(BASE_T + self.rng.normal(0, 1.2)),
                        source="era5_land",
                    )
    """
    for src in (from_module, from_class, shadowed):
        assert scan(src) == [], src


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
    # A value that does BOTH is neither honest nor adjudicable as a hedge: it
    # reads SIMULATED to the gate and "real ISD" to a human. That precedence
    # rule was the stamp-both evasion, and it is now a finding of its own.
    assert ft.classify_claim("synthetic observed-style panel") == ft.CONTRADICTED
    assert ft.classify_claim("synthetic_weather_real_isd_fallback") == ft.CONTRADICTED
    # ...and a declaration with no observation token in it is still honest,
    # which is the property arabica's replacement labels were held to.
    assert ft.classify_claim("synthetic_farm_canopy_fixture") == ft.SIMULATED
    # Names something; adjudicates nothing.
    assert ft.classify_claim("civ_ccc_regional") == ft.OPAQUE
    assert ft.classify_claim("era5_monthly_reduction") == ft.OPAQUE
    assert ft.classify_claim("") == ft.OPAQUE


def test_identifier_vocabulary():
    """Identifiers key a record; they are not what a source stamp claims."""
    assert ft.is_identifier_field("station_id")
    assert ft.is_identifier_field("filename")
    assert ft.is_identifier_field("url")
    # Deliberately NOT identifiers: these can be the axis a real measurement
    # was taken along, and treating them as keys would let the rule adjudicate
    # records built from a caller's index.
    assert not ft.is_identifier_field("year")
    assert not ft.is_identifier_field("lat")
    assert not ft.is_identifier_field("water_level_m")


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


# ---------------------------------------------------------------------------
# T8-4 / E-M17: the source claim is adjudicated on the VALUE, not the field name
#
# CONTROL A must FIRE and CONTROL B must STAY SILENT, and neither half is worth
# anything without the other. A must fail on a tree where the value-side rule
# has been reverted to `if name not in PROVENANCE_FIELDS: return None`; B must
# hold on the clean tree with nothing else in the fleet table moved.
#
# The anti-renaming clause lives in CONTROL A: the 24 field names E-M17
# measured, PLUS one generated at test time. No frozenset can be extended to
# hold a name that does not exist until the test runs.
# ---------------------------------------------------------------------------

import secrets
from pathlib import Path

import pytest

#: The 24 field names measured in docs/ESCALATIONS.md E-M17, verbatim. Every
#: one of them carried "era5_land" on the module's own positive-control
#: construction and every one of them was SILENT.
EM17_MEASURED_FIELD_NAMES = (
    "data_product", "product", "feed", "provider", "network", "archive",
    "registry", "upstream", "repository", "portal", "reanalysis", "vendor",
    "series", "feed_name", "api", "corpus", "supplier", "channel", "stream",
    "obtained_from", "retrieved_from", "derived_from", "input_dataset", "basis",
)

#: The module's own positive control (``ERA5LandBaselineLoader.iter_grid`` in
#: resilient-arabica, reduced), parameterised on NOTHING BUT the name of the
#: field carrying the stamp. Every value on the yielded record is an RNG draw,
#: a literal, or arithmetic over a literal-defaulted parameter.
ERA5_LOADER = """
    import numpy as np

    class ERA5LandBaselineLoader:
        def __init__(self, seed=44):
            self.rng = np.random.default_rng(seed)

        def iter_grid(self, lat_min=-20.0, lat_max=22.0, resolution=0.5, days=365):
            lats = np.arange(lat_min, lat_max + resolution, resolution)
            for lat in lats:
                for d in range(days):
                    seasonal = 4.0 * np.sin(2.0 * np.pi * (d % 365) / 365.0)
                    t2m = 22.0 + seasonal + self.rng.normal(0, 1.2)
                    precip = max(0.0, self.rng.gamma(2.0, 2.8))
                    yield GridSample(
                        lat=float(lat),
                        elevation=1000.0,
                        t2m=float(t2m),
                        precip=float(precip),
                        {stamp_field}="{stamp_value}",
                    )
"""

#: One entry, copied in shape from the signed allowlist every model repo
#: keeps. ``gee-era5-land-daily`` is arabica's real entry id for ERA5-Land;
#: it is written into a tmp file here so the control does not depend on
#: another checkout being present, and so the registry it reads is one the
#: test can point at and a reader can see.
ALLOWLIST_FIXTURE = """\
version: 1
signature:
  signed: true
  signed_by: 'Fixture signatory'
  signed_at: '2026-08-22'
  entries_sha256: 'not-verified-by-read'
entries:
- id: gee-era5-land-daily
  kind: data
  status: ALLOWED
  licence_url: https://apps.ecmwf.int/datasets/licences/copernicus/
  retrieval_date: '2026-08-14'
- id: chirps-daily-precip
  kind: data
  status: ALLOWED
  licence_url: https://www.chc.ucsb.edu/data/chirps
  retrieval_date: '2026-08-14'
- id: fdp-coffee-probability-2025b
  kind: data
  status: ALLOWED
  licence_url: https://example.invalid/licence
  retrieval_date: '2026-08-14'
- id: ecmwf-aifs-single-1-0
  kind: weights
  status: ALLOWED
  licence_url: https://creativecommons.org/licenses/by/4.0/
  retrieval_date: '2026-08-14'
"""


def assert_bound_to_this_worktree() -> Path:
    """Print and ASSERT which fabricated_targets.py is under test.

    A control that passed against an installed wheel while the worktree said
    something else would be a control that measures the wrong file. The
    binding is printed so it appears in ``pytest -s`` output and asserted so
    it cannot be wrong silently.
    """
    bound = Path(ft.__file__).resolve()
    expected = (
        Path(__file__).resolve().parent.parent
        / "src" / "resilient_mlkit" / "core" / "fabricated_targets.py"
    ).resolve()
    print(f"R11 module binding under test: {bound}")
    assert bound == expected, (
        f"R11 controls are bound to {bound}, not to this worktree's "
        f"{expected}. The controls would be measuring another copy of the "
        "module; fix PYTHONPATH or the editable install before reading any "
        "verdict below."
    )
    return bound


@pytest.fixture
def registry(tmp_path) -> ft.SourceRegistry:
    """A repo-shaped tree carrying a signed allowlist, read as a registry."""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "allowlist.yaml").write_text(ALLOWLIST_FIXTURE)
    loaded = ft.load_source_registry(tmp_path)
    assert loaded.present and len(loaded.entries) == 4, loaded
    return loaded


def scan_loader(stamp_field: str, registry: ft.SourceRegistry,
                stamp_value: str = "era5_land") -> list[ft.Finding]:
    return ft.scan_source(
        textwrap.dedent(
            ERA5_LOADER.format(stamp_field=stamp_field, stamp_value=stamp_value)
        ),
        "src/training/finetune_aurora_coffee.py",
        registry,
    )


# ---------------------------------------------------------------------------
# CONTROL A — must FIRE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stamp_field",
    ("source",) + EM17_MEASURED_FIELD_NAMES + ("__generated_at_test_time__",),
)
def test_control_a_the_source_claim_survives_any_field_name(stamp_field, registry):
    """CONTROL A. E-M17's exact defeat, re-run across 26 field names.

    The construction is byte-identical in every case and is 100% RNG draws,
    literals and arithmetic over literal-defaulted parameters. Only the NAME
    of the field carrying ``"era5_land"`` changes. Before T8-4 the first case
    fired and the other 24 measured names were silent, 24 of 24.

    The last parameter is not a name at all until the test runs: it is
    generated fresh from ``secrets``, so it cannot be in
    ``SOURCE_NAMING_FIELDS``, ``PROVENANCE_FIELDS``, or any other list an
    implementer could extend. If this control can be satisfied by adding
    names to a frozenset, this case is the one that says so.

    Each finding must carry all four things a reader needs to check it without
    re-deriving the rule: the field name it saw, the value, WHICH branch
    matched, and the construction that contradicts the claim.
    """
    assert_bound_to_this_worktree()
    if stamp_field == "__generated_at_test_time__":
        stamp_field = f"z{secrets.token_hex(8)}"
        assert stamp_field not in ft.PROVENANCE_FIELDS
        assert stamp_field not in ft.SOURCE_NAMING_FIELDS

    findings = scan_loader(stamp_field, registry)

    assert len(findings) == 1, (
        f"R11 is SILENT on the wholly manufactured ERA5 loader when the stamp "
        f"is called {stamp_field}=. Findings: {[f.render() for f in findings]}"
    )
    finding = findings[0]
    assert finding.rule == ft.CONTRADICTED_SOURCE
    assert finding.claim_field == stamp_field, finding.render()
    assert finding.claim_value == "era5_land", finding.render()
    if stamp_field == "source":
        # The pre-existing field-name path. Unchanged by T8-4, and it is here
        # so a regression in the OLD half is caught by the NEW control.
        assert finding.matched_on == ""
    else:
        assert finding.matched_on == (
            "allowlist:gee-era5-land-daily [ALLOWED] via era5+land"
        ), finding.render()
    assert "wholly manufactured in this process" in finding.construction
    assert "rng.gamma" in finding.origin_call or "rng.normal" in finding.origin_call


def test_control_a_fires_on_the_pandas_column_shape_under_a_renamed_column(registry):
    """CONTROL A, second syntax. The stamp bolted on as a frame column.

    ``_frame_records`` used to collect only columns whose NAME was a declared
    provenance field, so the identical rename defeated it there too -- one
    syntax over from the case above and invisible to it.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np
            import pandas as pd

            def build(days=365, seed=0):
                rng = np.random.default_rng(seed)
                frame = pd.DataFrame({"t2m": rng.normal(22.0, 1.2, days)})
                frame["data_product"] = "era5_land"
                return frame
            """
        ),
        "src/loaders/grid.py",
        registry,
    )
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].claim_field == "data_product"
    assert findings[0].matched_on.startswith("allowlist:gee-era5-land-daily")


def test_control_a_fires_on_a_bare_observation_claim_under_a_renamed_field(registry):
    """CONTROL A, branch (a). No allowlist entry involved.

    ``label_origin="observed_ccc"`` is the incident. Renamed to a field name
    nothing has heard of, the OBSERVED vocabulary still reads the value --
    which is the half that has to work in a repo whose allowlist does not
    happen to name the product being impersonated.
    """
    assert_bound_to_this_worktree()
    findings = scan_loader("thing_we_pulled_it_from", registry,
                           stamp_value="observed_ccc")
    assert len(findings) == 1, [f.render() for f in findings]
    assert findings[0].rule == ft.CONTRADICTED_SOURCE
    assert findings[0].matched_on == "observed-token:observed"


# ---------------------------------------------------------------------------
# CONTROL B — must STAY SILENT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("freq", "h"),                      # surge storm_loader.py:205
        ("currency", "USD"),                # torrent loss_metrics.py:76
        ("country_code", "GLO"),            # triage
        ("generator_version", "1.0.0"),     # torrent event_set.py:350
        ("match_role", "treated"),          # blackout + chokepoint did_impact.py
        ("crop", "coffee"),                 # one part of fdp-coffee-probability-2025b
        ("freq_label", "daily"),            # one part of chirps-daily-precip
    ],
)
def test_control_b_the_measured_over_fire_cases_stay_silent(field_name, value, registry):
    """CONTROL B. The seven values that made the naive inversion unshippable.

    Every one of these sits on a WHOLLY MANUFACTURED record -- the same
    precondition the real findings satisfy -- so the record's construction
    cannot be what separates them. Only the value can.

    ``generator_version="1.0.0"`` is the sharpest of them: its tokens are
    ``1``, ``0`` and the adjacent join ``10``, and ``10`` is also the join of
    the trailing ``-1-0`` in the allowlisted ``ecmwf-aifs-single-1-0``. Without
    the naming-token filter the registry branch scores 2 and fires on a version
    string. ``crop="coffee"`` and ``freq_label="daily"`` are the one-part
    collisions: both words are parts of real allowlist entries, and one shared
    word is not a name.
    """
    assert_bound_to_this_worktree()
    findings = scan_loader(field_name, registry, stamp_value=value)
    assert findings == [], (
        f'R11 fired on {field_name}="{value}", which is not a source claim: '
        f"{[f.render() for f in findings]}"
    )


def test_control_b_an_honest_disclaimer_naming_observation_stays_silent(registry):
    """CONTROL B. torrent ``v4_orchestrator.py:1287``, as shipped.

    The note says the annual maxima "were DRAWN, not observed" -- the most
    honest thing an author can write about a synthetic fallback -- and it
    contains the word ``observed``. Two independent guards keep R11 quiet
    here, and the test asserts the record is silent with BOTH in place:
    ``evidence_mode="synthetic"`` is the record-level honesty rule, and the
    note's own text declares itself, so the value-side branch skips it too.

    A rule that reports an honest disclaimer teaches authors to delete the
    disclaimer. That is the opposite of what R11 is for.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def _return_period_map(mode="synthetic"):
                rng = np.random.default_rng(44)
                drawn = rng.lognormal(4.5, 0.6, size=50)
                return {
                    "method": "synthetic_lognormal_annual_maxima",
                    "evidence_mode": "synthetic",
                    "n_annual_maxima": int(len(drawn)),
                    "source": "numpy.random.default_rng(44).lognormal(4.5, 0.6)",
                    "hydrology_mode": mode,
                    "note": (
                        "these annual maxima were DRAWN, not observed. Every return "
                        "period derived from this map, and every stage, depth and "
                        "avoided-loss figure downstream of it, is synthetic."
                    ),
                }
            """
        ),
        "src/torrent/engine/v4_orchestrator.py",
        registry,
    )
    assert findings == [], [f.render() for f in findings]


def test_control_b_an_honest_NA_disclaimer_is_not_a_source_claim(registry):
    """CONTROL B. The three false findings the first cut of branch (a) made.

    resilient-blackout writes exactly the disclaimer this instrument asks for
    -- "No observational asset-level labels exist to score against" -- on a
    record whose numbers ARE drawn, because the honest thing to report is that
    nothing was measured. ``observational`` is in the observed vocabulary.
    Reading a sentence as a provenance stamp is how a check starts firing on
    honesty; ``is_label_value`` is the guard, and this is its control.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def calibrate(alpha=0.1, method="split"):
                rng = np.random.default_rng(42)
                residuals = np.abs(rng.normal(0, 20, 500))
                threshold = float(np.quantile(residuals, 1 - alpha))
                return {
                    "method": method,
                    "alpha": alpha,
                    "threshold": round(threshold, 3),
                    "empirical_coverage_status": "NA",
                    "empirical_coverage_unmeasured_reason": (
                        "no labelled holdout supplied to this task; empirical "
                        "coverage is unmeasured"
                    ),
                }
            """
        ),
        "resilient_blackout/api/tasks.py",
        registry,
    )
    assert findings == [], [f.render() for f in findings]


def test_control_b_writing_one_key_does_not_make_the_container_manufactured(registry):
    """CONTROL B. The root cause behind two of those three false findings.

    ``payload["vintage_delta_verdict"] = "MEASURED"`` writes one literal into
    one key. ``manufactured_of`` used to read that as proof that ``payload``
    -- forty other values, including a live NOAA CO-OPS fetch and ``_git()``
    output -- was built in-process, which is the over-approximation that pass
    documents it must never make.

    The pair: the same subscript write, once on a container holding an
    external read (silent), once on a container that really was built from
    literals and a draw (a finding). If the first half of this pair ever goes
    red, R11 is inventing manufactured-ness again.
    """
    assert_bound_to_this_worktree()
    external = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def measure(seed=0):
                rng = np.random.default_rng(seed)
                stations = fetch_coops_verified_heights()
                payload = {
                    "stations": stations,
                    "sample": rng.choice(stations, size=3),
                }
                payload["vintage_delta_verdict"] = "MEASURED"
                return payload
            """
        ),
        "scripts/measure_coops_vintage_delta.py",
        registry,
    )
    assert external == [], [f.render() for f in external]

    manufactured = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def measure(seed=0, n=3):
                rng = np.random.default_rng(seed)
                heights = rng.normal(3.0, 0.3, n)
                payload = {"water_level_m": heights, "gauge_count": n}
                payload["source"] = "ntslf"
                return payload
            """
        ),
        "scripts/fake_gauges.py",
        registry,
    )
    assert len(manufactured) == 1, [f.render() for f in manufactured]
    assert manufactured[0].claim_value == "ntslf"


def test_control_b_a_loader_that_reads_real_data_is_silent_under_every_name(registry):
    """CONTROL B, and the one this rule would be worthless without.

    Same stamp value, same jitter, same everything -- except one value on the
    record was read from a file. Renaming the field must not change that: if
    the value-side branch fired here it would fire on every real loader in the
    fleet that happens to name its own source.
    """
    assert_bound_to_this_worktree()
    for field_name in ("source", "data_product", f"z{secrets.token_hex(6)}"):
        findings = ft.scan_source(
            textwrap.dedent(
                f"""
                import numpy as np
                import xarray as xr

                def load_grid(path, seed=0):
                    rng = np.random.default_rng(seed)
                    ds = xr.open_dataset(path)
                    return [
                        {{
                            "t2m": float(row.t2m) + rng.normal(0, 0.01),
                            "elevation": 1000.0,
                            "{field_name}": "era5_land",
                        }}
                        for row in ds
                    ]
                """
            ),
            "src/loaders/era5.py",
            registry,
        )
        assert findings == [], (field_name, [f.render() for f in findings])


def test_control_b_the_same_loader_declaring_itself_is_silent_under_every_name(registry):
    """CONTROL B. One string, and it is a fixture again -- under any field name.

    ``era5_land_shaped_synthetic_grid`` reproduces the same two parts of
    ``gee-era5-land-daily`` that ``era5_land`` does. If the registry branch
    ignored the value's own declaration, renaming the field would turn every
    honestly-labelled fixture in the fleet into a finding.
    """
    assert_bound_to_this_worktree()
    for field_name in ("source", "data_product", f"z{secrets.token_hex(6)}"):
        findings = scan_loader(
            field_name, registry, stamp_value="era5_land_shaped_synthetic_grid"
        )
        assert findings == [], (field_name, [f.render() for f in findings])


def test_control_b_the_repair_is_not_a_longer_field_name_list(registry):
    """CONTROL B. The mechanism, asserted directly.

    E-M17 exists because the check read a list of field names. If the repair
    were "add the 24 names", this test is what would catch it: none of them
    may be in either frozenset, and the check must still fire on all 24. The
    two halves together say the findings above came from the value.
    """
    assert_bound_to_this_worktree()
    leaked = [
        n for n in EM17_MEASURED_FIELD_NAMES
        if n in ft.PROVENANCE_FIELDS or n in ft.SOURCE_NAMING_FIELDS
    ]
    assert leaked == [], (
        "E-M17's field names were added to the frozensets instead of the rule "
        f"being moved to the value: {leaked}"
    )


def test_control_b_an_absent_registry_is_reported_not_silently_skipped(tmp_path):
    """CONTROL B. Renaming the file the check reads must not be a silent skip.

    Branch (b) cannot fire without a registry. A check that loses a conjunct
    and goes on printing PASS is the failure mode this module keeps finding in
    other people's checks, so R11's evidence carries what it read and whether
    it was there. R9 and T5 escalate on the same absence; this is the line
    that makes it visible where it changed what was measured.
    """
    from resilient_mlkit.checks.readiness import r11_fabricated_targets

    assert_bound_to_this_worktree()
    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n',
        {"scripts/build_panel.py": "x = 1\n"},
    )
    result = r11_fabricated_targets(repo, _ctx(tmp_path))
    assert result.evidence["source_registry"] == {
        "path": "docs/allowlist.yaml",
        "present": False,
        "entries": 0,
        "parse_error": "",
    }

    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "allowlist.yaml").write_text(ALLOWLIST_FIXTURE)
    result = r11_fabricated_targets(repo, _ctx(tmp_path))
    assert result.evidence["source_registry"]["present"] is True
    assert result.evidence["source_registry"]["entries"] == 4
    report_text = (tmp_path / "reports" / "fabricated_targets.md").read_text()
    assert "real-source registry" in report_text
    assert "4 signed entries" in report_text


def test_the_registry_reads_the_allowlist_and_never_writes_it(tmp_path, registry):
    """The registry is READ. Extending it is reserved to the human signatory.

    Asserted by bytes: the file this rule depends on is unchanged after a full
    scan. An agent that "closed" a finding by adding an allowlist entry would
    be doing the one thing CLAUDE.md rule 14 forbids.
    """
    assert_bound_to_this_worktree()
    before = (tmp_path / "docs" / "allowlist.yaml").read_bytes()
    scan_loader("data_product", registry)
    ft.scan_repo(tmp_path)
    assert (tmp_path / "docs" / "allowlist.yaml").read_bytes() == before


def test_the_registry_match_needs_two_parts_of_a_name_not_one(registry):
    """The threshold, held as a unit fact rather than inferred from a scan."""
    assert_bound_to_this_worktree()
    assert registry.match("era5_land") is not None
    assert registry.match("era5land") is not None          # joined spelling
    assert registry.match("ERA5-Land") is not None         # any separator
    assert registry.match("coffee") is None                # one part of an entry
    assert registry.match("daily") is None                 # one part of an entry
    assert registry.match("1.0.0") is None                 # digits are not a name
    assert registry.match("USD") is None
    assert registry.match("h") is None
    hit = registry.match("era5_land")
    assert hit.entry == "gee-era5-land-daily"
    assert hit.parts == ("era5", "land")


# ---------------------------------------------------------------------------
# T8-4 ATTACK CONTROLS — the evasions found by attacking the repair, not by
# reading it. Every one of these was LIVE against the first cut of the
# value-side rule; each is paired with the honest twin that must stay silent,
# because a rule that fires on all five spellings and cannot tell a fixture
# from a fabrication has bought nothing.
# ---------------------------------------------------------------------------

SPELLING_ATTACKS = [
    # (label, the record's stamp entry, must fire)
    ("plain", '"source": "era5_land"', True),
    ("renamed field", '"zq7lk": "era5_land"', True),
    ("shortest spelling", '"zq7lk": "ERA5"', True),
    ("joined spelling", '"zq7lk": "era5land"', True),
    ("f-string with no placeholder", '"zq7lk": f"era5_land"', True),
    ("string concatenation", '"zq7lk": "era5" + "_land"', True),
    ("list-valued stamp", '"sources": ["era5_land"]', True),
    ("tuple under a renamed field", '"zq7lk": ("era5_land",)', True),
    # ... and the honest twin of each, one string different.
    ("honest twin, plain", '"source": "era5_land_shaped_synthetic_grid"', False),
    ("honest twin, renamed", '"zq7lk": "era5_land_shaped_synthetic_grid"', False),
    ("honest twin, list", '"sources": ["era5_land_shaped_synthetic_grid"]', False),
    ("honest twin, f-string", '"zq7lk": f"era5_land_shaped_synthetic_grid"', False),
    # An f-string this module cannot fold is unreadable, and unreadable is
    # always the quiet direction.
    ("unresolvable placeholder", '"zq7lk": f"era5_{d}"', False),
]

SPELLING_RECORD = """
    import numpy as np

    def build(days=365, seed=0):
        rng = np.random.default_rng(seed)
        return [
            {{"t2m": float(22.0 + rng.normal(0, 1.2)), {stamp}}}
            for d in range(days)
        ]
"""


@pytest.mark.parametrize(
    ("label", "stamp", "fires"),
    [pytest.param(*case, id=case[0].replace(" ", "-")) for case in SPELLING_ATTACKS],
)
def test_attack_the_value_is_read_however_it_is_spelled(label, stamp, fires, registry):
    """ATTACK. Five ways to write the same three tokens, and the honest twins.

    The brief for this check is that it survive REFORMATTING. ``f"era5_land"``,
    ``"era5" + "_land"`` and ``["era5_land"]`` are the same claim the parser
    already holds; a rule that read one and not the others was reading the
    layout again, which is the defect E-M17 is an instance of. All three were
    live evasions of the first cut of this repair.

    Folding, never evaluation: an f-string whose placeholder this module
    cannot resolve makes the whole value unreadable and the check silent.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(SPELLING_RECORD.format(stamp=stamp)),
        "src/loaders/grid.py",
        registry,
    )
    if fires:
        assert len(findings) == 1, (label, [f.render() for f in findings])
        assert findings[0].rule == ft.CONTRADICTED_SOURCE
    else:
        assert findings == [], (label, [f.render() for f in findings])


def test_attack_hoisting_the_stamp_into_a_constant_is_still_a_finding(registry):
    """ATTACK. The cheapest refactor with no semantic content: hoist the string.

    VERIFY-R11-A4 made this argument about NUMERIC constants -- moving
    ``22.0`` into the module or the class body turned the finding off, because
    a constant is exactly as manufactured wherever it is written down. The
    identical hoist worked on the STAMP: ``SOURCE = "era5_land"`` at module
    level, or ``FEED = "era5_land"`` in the class body, and R11 went silent on
    a loader that was still 100% noise.

    The class case resolves against the ENCLOSING class only. The third
    fixture is the control for that: a sibling class holding the same
    attribute name must not lend its value, or the rule would invent findings
    out of a name collision.
    """
    assert_bound_to_this_worktree()
    module_level = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            SOURCE = "era5_land"

            def build(days=365, seed=0):
                rng = np.random.default_rng(seed)
                return [
                    {"t2m": float(22.0 + rng.normal(0, 1.2)), "zq7lk": SOURCE}
                    for d in range(days)
                ]
            """
        ),
        "src/loaders/grid.py",
        registry,
    )
    assert len(module_level) == 1, [f.render() for f in module_level]
    assert module_level[0].claim_value == "era5_land"

    class_level = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            class Loader:
                FEED = "era5_land"

                def build(self, days=365, seed=0):
                    rng = np.random.default_rng(seed)
                    return [
                        {"t2m": float(22.0 + rng.normal(0, 1.2)), "zq7lk": self.FEED}
                        for d in range(days)
                    ]
            """
        ),
        "src/loaders/grid.py",
        registry,
    )
    assert len(class_level) == 1, [f.render() for f in class_level]

    borrowed = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            class Real:
                FEED = "era5_land"

            class Other:
                def build(self, days=365, seed=0):
                    rng = np.random.default_rng(seed)
                    return [
                        {"t2m": float(22.0 + rng.normal(0, 1.2)), "zq7lk": self.FEED}
                        for d in range(days)
                    ]
            """
        ),
        "src/loaders/grid.py",
        registry,
    )
    assert borrowed == [], [f.render() for f in borrowed]


# ---------------------------------------------------------------------------
# M-04 STAGE 0 — E-M17 residual 4, the four spellings NOTHING RECORDS TODAY
#
# The residual was written down in the escalation and driven by hand; no test
# held it, so the silence was carried by prose and could have closed or
# regressed without anything going red. These four pins exist so the SILENCE
# is a measured, committed fact before Stage 1 changes it, and so Stage 1's
# flip is visible in a diff rather than asserted in a commit message.
#
# All four are the SAME three tokens as the plain literal that fires one test
# above -- ``era5``, ``land`` -- written four other ways. The reference case
# is included in the same table so the fixture itself is proved live: a table
# where every row is silent is also what a broken fixture looks like.
# ---------------------------------------------------------------------------

RESIDUAL4_MODULE_DICT_READBACK = """
    import numpy as np

    FEEDS = {"primary": "era5_land"}

    def build(days=365, seed=0):
        rng = np.random.default_rng(seed)
        return [
            {"t2m": float(22.0 + rng.normal(0, 1.2)), "zq7lk": FEEDS["primary"]}
            for d in range(days)
        ]
"""

#: (label, source, fires) -- ``fires`` is the MEASURED behaviour, not the
#: desired one. Driven at 8517341 with the module binding asserted.
RESIDUAL4_SPELLINGS = [
    (
        "reference literal",
        SPELLING_RECORD.format(stamp='"zq7lk": "era5_land"'),
        True,
    ),
    (
        "str.join of constants",
        SPELLING_RECORD.format(stamp='"zq7lk": "_".join(["era5", "land"])'),
        False,
    ),
    (
        "percent format of constants",
        SPELLING_RECORD.format(stamp='"zq7lk": "era5_%s" % "land"'),
        False,
    ),
    (
        "str.format of constants",
        SPELLING_RECORD.format(stamp='"zq7lk": "era5_{}".format("land")'),
        False,
    ),
    (
        "module-dict read-back",
        RESIDUAL4_MODULE_DICT_READBACK,
        False,
    ),
]


@pytest.mark.parametrize(
    ("label", "source", "fires"),
    [
        pytest.param(*case, id=case[0].replace(" ", "-").replace(".", "-"))
        for case in RESIDUAL4_SPELLINGS
    ],
)
def test_residual_4_the_unfolded_spellings_are_still_silent(
    label, source, fires, registry
):
    """RESIDUAL, pinned so the day it closes is visible.

    E-M17 residual 4. ``_string_of`` folds ``+``, f-strings, module names and
    class attributes; it does not fold ``str.join``, ``%``-format,
    ``str.format`` or a constant-key read-back of a module dict. Each is the
    hoist argument VERIFY-R11-A4 already won for numeric constants and that
    ``test_attack_hoisting_the_stamp_into_a_constant_is_still_a_finding``
    already won for ``SOURCE = "era5_land"``, one syntax over.

    This test asserts the CURRENT behaviour on purpose, firing row included.
    When Stage 1 folds these, the ``False`` rows flip to ``True`` in this
    table and E-M17 gets updated -- the silence is not to be re-pinned.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(source), "src/loaders/grid.py", registry
    )
    if fires:
        assert len(findings) == 1, (label, [f.render() for f in findings])
        assert findings[0].rule == ft.CONTRADICTED_SOURCE
        assert findings[0].claim_value == "era5_land"
    else:
        assert findings == [], (
            f"{label}: E-M17 residual 4 has moved. Update the escalation and "
            "this table rather than re-pinning the silence: "
            f"{[f.render() for f in findings]}"
        )


def test_attack_a_malformed_registry_is_reported_not_treated_as_empty(tmp_path):
    """ATTACK. Corrupt the file the check reads and see whether it skips quietly.

    A registry that fails to parse is indistinguishable from an empty one
    unless somebody records the difference. R9 FAILS on the same parse error;
    R11 carries it in its own evidence, because it is R11's conjunct that
    stopped working.
    """
    from resilient_mlkit.checks.readiness import r11_fabricated_targets

    assert_bound_to_this_worktree()
    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n',
        {"scripts/build_panel.py": "x = 1\n"},
    )
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "allowlist.yaml").write_text("entries: [ this is not: yaml: {\n")
    result = r11_fabricated_targets(repo, _ctx(tmp_path))
    reg = result.evidence["source_registry"]
    assert reg["present"] is True
    assert reg["entries"] == 0
    assert reg["parse_error"], reg
    assert "parse error" in (tmp_path / "reports" / "fabricated_targets.md").read_text()


def test_residual_a_product_in_no_allowlist_is_still_invisible(registry):
    """RESIDUAL, pinned so the day it closes is visible.

    The chokepoint shape: ``scenario_name="SSP1-2.6 vs SSP5-8.5
    (CMIP6-driven)"`` on throughput deltas built from four literals plus
    ``rng.normal``, in a module with no CMIP6 in it. No chokepoint allowlist
    entry mentions CMIP6, so branch (b) has nothing to match; the value claims
    no observation, so branch (a) does not fire either.

    This test asserts the CURRENT, WRONG behaviour on purpose. It is the
    residual test E-M17 asks for: when someone closes the gap, this test goes
    red and that is the signal to update E-M17, not to re-pin the silence.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def compare(baseline=42.0, seed=0):
                rng = np.random.default_rng(seed)
                factual = baseline * 1.02 + rng.normal(0, 0.3)
                counterfactual = baseline * 0.87 + rng.normal(0, 0.3)
                return {
                    "factual_throughput_mtpd": float(factual),
                    "counterfactual_throughput_mtpd": float(counterfactual),
                    "scenario_name": "SSP1-2.6 vs SSP5-8.5 (CMIP6-driven)",
                }
            """
        ),
        "src/resilient_chokepoint/counterfactual/climate_model_runners.py",
        registry,
    )
    assert findings == [], (
        "E-M17's remaining half has been closed. Update the escalation and the "
        "module docstring rather than re-pinning this silence: "
        f"{[f.render() for f in findings]}"
    )


def test_residual_a_stamp_applied_in_a_helper_is_still_invisible(registry):
    """RESIDUAL, pinned. The record is not provably manufactured across a call.

    ``_stamp(row)`` receives its record as a parameter with no default, which
    is how data arrives, so ``manufactured_of`` cannot prove the record was
    built in-process and CONTRADICTED_SOURCE stays quiet. That is the
    conservative lean working as designed, and it is also an evasion. Under-
    report, stated rather than papered over.
    """
    assert_bound_to_this_worktree()
    findings = ft.scan_source(
        textwrap.dedent(
            """
            import numpy as np

            def _stamp(row):
                row["zq7lk"] = "era5_land"
                return row

            def build(days=365, seed=0):
                rng = np.random.default_rng(seed)
                return [
                    _stamp({"t2m": float(22.0 + rng.normal(0, 1.2))})
                    for d in range(days)
                ]
            """
        ),
        "src/loaders/grid.py",
        registry,
    )
    assert findings == [], (
        "the inter-procedural under-report has been closed; update the module "
        f"docstring rather than re-pinning it: {[f.render() for f in findings]}"
    )


def test_the_registry_designator_rule_and_its_noise_budget(registry):
    """One token can name a product only when it mixes letters and digits.

    ``era5`` and ``sentinel2`` are product designators; ``coffee``, ``daily``
    and ``global`` are words that happen to appear in an entry id. ``co2`` is
    the reason for the length floor -- it is a part of a real allowlist entry
    and also the name of a gas, and matching ``species="CO2"`` would be the
    ``currency="USD"`` class of noise all over again.
    """
    assert_bound_to_this_worktree()
    assert registry.match("ERA5") is not None
    assert registry.match("era5") is not None
    assert registry.match("chirps") is None      # letters only, one part
    assert registry.match("coffee") is None
    assert registry.match("co2") is None         # designator, below the floor
    assert registry.match("v1") is None
    assert registry.match("2017") is None        # digits only


# ---------------------------------------------------------------------------
# CONTROL C — the registry disclosure landed in R11's report, and ONLY there
# ---------------------------------------------------------------------------
def test_control_c_the_registry_disclosure_is_r11s_and_r12_still_runs(tmp_path):
    """Both readiness report writers are DRIVEN, not read.

    The registry line this change adds is a fact about R11's value-side source
    rule. It was also pasted into ``_write_r12_report``, which has no
    ``registry`` in scope, so every call of R12 -- on every repo, findings or
    none, since that writer is unconditional -- raised
    ``NameError: name 'registry' is not defined``. R12's own control suite
    caught it in five places; it reached a pushed branch because that file was
    not run.

    So this control runs BOTH checks end to end against a minimal repo and
    asserts the disclosure is where it belongs. A report writer is only
    reachable by execution: nothing about reading it says whether its names
    are bound.
    """
    assert_bound_to_this_worktree()
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import (
        r11_fabricated_targets,
        r12_served_contract,
    )
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "plain.py").write_text("VALUE = 1\n")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "allowlist.yaml").write_text(ALLOWLIST_FIXTURE)
    repo = Repo(name="fixture", path=tmp_path)
    ctx = RunContext(nonce="test-nonce", root=tmp_path)

    r11 = r11_fabricated_targets(repo, ctx)
    r12 = r12_served_contract(repo, ctx)
    assert r11.status is Status.PASS, r11.reason
    assert r12.status is Status.PASS, r12.reason

    r11_report = (tmp_path / "reports" / "fabricated_targets.md").read_text()
    r12_report = (tmp_path / "reports" / "served_contract.md").read_text()
    assert "real-source registry" in r11_report, r11_report
    assert "docs/allowlist.yaml" in r11_report, r11_report
    assert "real-source registry" not in r12_report, (
        "R12 is the served-model contract check. It does not adjudicate "
        "source claims and has no registry to disclose; a line saying it does "
        "is a fact about a different measurement.\n" + r12_report
    )
    assert r11.evidence["source_registry"]["present"] is True
    assert "source_registry" not in r12.evidence
