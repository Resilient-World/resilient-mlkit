"""Regression pins for the shared formula-derivation probe (E-017 resolution).

THESE TESTS ARE THE REGRESSION EVIDENCE required to change a gate: every
failure class the pre-2026-08-16 discriminator caught (or was documented as
needing to catch) must STILL be caught by the shared probe, and the E-017
false-positive class must not be. Each fixture below is built from a repo's
own documented construction, cited inline — nothing is invented here.

The three previously-caught / documented derivation classes:

  (a) resilient-surge's synthetic fixture: ``target = 0.3 * era5[..., 0] +
      0.1 * tide + N(0, 0.05)`` — the pre-2026-08-15 ``make_fixture_pack``
      construction, documented verbatim in
      ``resilient-surge/src/resilient_surge/training/sample_io.py`` (docstring
      of ``make_fixture_pack``: "Until 2026-08-15 this wrote ...", measured
      there at out-of-sample R^2 0.973/0.964/0.952).
  (b) resilient-blackout's ``formula_derived_target`` rows:
      ``tads_annual_failure_probability(volt_class, length_km) =
      1 - exp(-rate * (km * 0.621371) / 100)`` —
      ``resilient_blackout/core/fragility_registry.py:286-301``, rates from
      ``config/nerc_tads_rates.json`` (NERC State of Reliability aggregates,
      retrieved 2026-08-13 per that file).
  (c) resilient-choco's retired RNG bootstrap labels: 8 rows per country-year
      with identical features and ``label = mean_y + rng.normal(0.0, 0.4)`` —
      ``resilient-choco/docs/BLOCKERS.md`` ("Data integrity" section,
      yield_panel.py:645 finding); ``build_yield_panel`` now refuses
      ``bootstrap_per_country_year != 0``.

The false-positive class being eliminated (E-017, resilient-surge
``docs/ESCALATIONS.md``): observed windowed rows whose residual ratio lands
in (0.3, 0.5] with a heavily autocorrelated residual — verified CO-OPS storm
windows measured 2026-08-16 at ratios 0.348-0.499, acf1 0.730-0.959.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from resilient_mlkit.core.derivation import (
    FORMULA_RESIDUAL_RATIO,
    HARD_DERIVED_RATIO,
    KNN_DERIVED_RATIO,
    acf_bound,
    formula_derivation_probe,
)

# ---------------------------------------------------------------------------
# (a) the surge synthetic fixture construction
# ---------------------------------------------------------------------------


def _surge_fixture_split(rng: np.random.Generator, n: int, seq_len: int = 24):
    """The documented pre-2026-08-15 make_fixture_pack construction."""
    era5 = rng.normal(0, 1, size=(n, seq_len, 4)).astype(np.float32)
    graphcast = np.roll(era5, 1, axis=1)
    graphcast[:, 0, :] = 0.0
    ibtracs = rng.normal(0, 1, size=(n, seq_len, 5)).astype(np.float32)
    tide = np.repeat(
        (0.5 * np.sin(np.linspace(0, 4 * np.pi, seq_len))[None, :, None]).astype(np.float32),
        n,
        axis=0,
    )
    stacked = np.concatenate([era5, graphcast, ibtracs, tide], axis=2)
    target = (
        0.3 * era5[..., 0] + 0.1 * tide[..., 0] + rng.normal(0, 0.05, size=(n, seq_len))
    ).astype(np.float32)
    return stacked, target


def _surge_fixture_packs():
    rng = np.random.default_rng(42)
    inputs, targets = {}, {}
    for split, n in (("train", 16), ("val", 4), ("test", 4)):
        inputs[split], targets[split] = _surge_fixture_split(rng, n)
    return inputs, targets


def test_surge_synthetic_fixture_every_row_still_caught():
    inputs, targets = _surge_fixture_packs()
    result = formula_derivation_probe(inputs, targets)
    for split in ("train", "val", "test"):
        assert all(result[split]["derived"]), (
            f"{split}: the documented fixture construction must be caught row for row"
        )
        # The whole population sits at or below the hard floor, so the
        # structure excusal can never have applied to it.
        assert max(result[split]["residual_ratio"]) <= HARD_DERIVED_RATIO
        assert not any(result[split]["physics_excused"])


def test_exact_flag_can_never_be_cleared():
    inputs, targets = _surge_fixture_packs()
    # Make one val row completely underivable (independent noise target) and
    # mark it exact: the probe must keep it derived anyway.
    targets["val"] = targets["val"].copy()
    targets["val"][0] = np.random.default_rng(7).normal(0, 1, targets["val"].shape[1])
    result = formula_derivation_probe(
        inputs, targets, exact={"val": [True, False, False, False]}
    )
    assert result["val"]["derived"][0] is True


# ---------------------------------------------------------------------------
# the E-017 false-positive class: physically predictable observed windows
# ---------------------------------------------------------------------------


def _ar1(rng: np.random.Generator, n: int, t: int, phi: float) -> np.ndarray:
    out = np.zeros((n, t))
    innov = rng.normal(0, 1, size=(n, t))
    for k in range(1, t):
        out[:, k] = phi * out[:, k - 1] + math.sqrt(1 - phi * phi) * innov[:, k]
    return out


def _physics_like_packs(t: int = 336):
    """Observed-style windows: target = linear physics + smooth unmodelled sea.

    Shaped on the measured E-017 rows (t=336 hourly windows; flagged ratios
    0.348-0.499 with residual acf1 0.730-0.959): the linear map explains the
    inverse-barometer-like term, and what it cannot explain is autocorrelated
    geophysics, not generator noise.
    """
    rng = np.random.default_rng(2026)
    inputs, targets = {}, {}
    for split, n in (("train", 64), ("val", 16), ("test", 16)):
        msl = _ar1(rng, n, t, 0.98)
        wind = _ar1(rng, n, t, 0.95)
        noise_ch = rng.normal(0, 1, size=(n, t, 3))
        stacked = np.concatenate([msl[..., None], wind[..., None], noise_ch], axis=2)
        unmodelled = _ar1(rng, n, t, 0.97)
        # amplitudes chosen so the out-of-sample ratio lands in the ambiguous
        # band (0.3, 0.5] for the bulk of rows, like the measured storm rows
        target = -1.0 * msl + 0.35 * wind + 0.55 * unmodelled
        inputs[split], targets[split] = stacked, target
    return inputs, targets


def test_predictable_physics_rows_are_not_flagged():
    inputs, targets = _physics_like_packs()
    result = formula_derivation_probe(inputs, targets)
    in_band = 0
    for split in ("val", "test"):
        ratio = np.array(result[split]["residual_ratio"])
        acf1 = np.array(result[split]["residual_acf1"])
        band = (ratio > HARD_DERIVED_RATIO) & (ratio <= FORMULA_RESIDUAL_RATIO)
        in_band += int(band.sum())
        # the construction must actually exercise the ambiguous band ...
        assert acf1[band].min(initial=1.0) > result[split]["acf_bound"]
        # ... and every in-band structured row must be excused, none derived
        assert not any(np.array(result[split]["derived"])[band])
        assert all(np.array(result[split]["physics_excused"])[band])
    assert in_band >= 8, f"fixture must exercise the band; only {in_band} rows landed in it"


def test_hard_floor_backstop_smoothed_noise_cannot_hide_a_formula():
    """A derived target with SMOOTH small noise is caught despite high acf1."""
    rng = np.random.default_rng(99)
    inputs, targets = {}, {}
    t = 336
    for split, n in (("train", 32), ("val", 8), ("test", 8)):
        x = rng.normal(0, 1, size=(n, t, 5))
        smooth = _ar1(rng, n, t, 0.97)
        target = 0.7 * x[..., 0] + 0.2 * x[..., 1] + 0.12 * smooth
        inputs[split], targets[split] = x, target
    result = formula_derivation_probe(inputs, targets)
    for split in ("val", "test"):
        ratio = np.array(result[split]["residual_ratio"])
        acf1 = np.array(result[split]["residual_acf1"])
        assert ratio.max() <= HARD_DERIVED_RATIO, "fixture must sit under the hard floor"
        assert acf1.min() > result[split]["acf_bound"], "fixture residual must be structured"
        assert all(result[split]["derived"]), (
            "a formula plus smoothed noise under the hard floor must stay caught"
        )


def test_white_residual_in_band_is_still_derived():
    """Ratio in (0.3, 0.5] with an unstructured residual: no excusal applies."""
    rng = np.random.default_rng(5)
    inputs, targets = {}, {}
    t = 336
    for split, n in (("train", 32), ("val", 8), ("test", 8)):
        x = rng.normal(0, 1, size=(n, t, 4))
        target = 0.8 * x[..., 0] + 0.36 * rng.normal(0, 1, size=(n, t))  # white noise band
        inputs[split], targets[split] = x, target
    result = formula_derivation_probe(inputs, targets)
    for split in ("val", "test"):
        ratio = np.array(result[split]["residual_ratio"])
        band = (ratio > HARD_DERIVED_RATIO) & (ratio <= FORMULA_RESIDUAL_RATIO)
        assert band.sum() >= 4, "fixture must exercise the band"
        assert all(np.array(result[split]["derived"])[band])


# ---------------------------------------------------------------------------
# (b) the blackout TADS reconstruction
# ---------------------------------------------------------------------------

# config/nerc_tads_rates.json, by_voltage_class outage_rate (retrieved
# 2026-08-13 per that file's source record)
TADS_RATES = {"100-161": 2.4, "220-287": 1.5, "345": 0.9, "500": 0.6}


def _tads_split(rng: np.random.Generator, n: int):
    classes = list(TADS_RATES)
    cls = rng.integers(0, len(classes), n)
    km = np.exp(rng.uniform(np.log(0.5), np.log(150.0), n))
    onehot = np.eye(len(classes))[cls]
    x = np.column_stack([onehot, km])
    # fragility_registry.tads_annual_failure_probability, verbatim transform
    y = np.array(
        [
            1.0 - math.exp(-TADS_RATES[classes[c]] * (k * 0.621371) / 100.0)
            for c, k in zip(cls, km)
        ]
    )
    return x, y


def test_tads_reconstruction_still_caught():
    rng = np.random.default_rng(7)
    inputs, targets = {}, {}
    for split, n in (("train", 400), ("val", 120), ("test", 120)):
        inputs[split], targets[split] = _tads_split(rng, n)
    result = formula_derivation_probe(inputs, targets)
    for split in ("val", "test"):
        assert result[split]["knn_active"] is True
        assert float(np.median(result[split]["knn_ratio"])) <= KNN_DERIVED_RATIO
        assert all(result[split]["derived"]), (
            f"{split}: every closed-form TADS row must be caught"
        )


def test_observed_tabular_rows_are_not_flagged():
    """A genuinely observed tabular split (linear signal + real noise): 0 flags."""
    rng = np.random.default_rng(11)
    beta = rng.normal(0, 1, 6)
    inputs, targets = {}, {}
    for split, n in (("train", 400), ("val", 120), ("test", 120)):
        x = rng.normal(0, 1, size=(n, 6))
        inputs[split] = x
        targets[split] = x @ beta + rng.normal(0, 1, n)
    result = formula_derivation_probe(inputs, targets)
    for split in ("train", "val", "test"):
        assert result[split]["knn_active"] is False
        assert not any(result[split]["duplicate_inputs"])
        assert not any(result[split]["derived"])


def test_binary_observed_labels_never_trip_the_knn_probe():
    """Discrete targets (blackout Model B outage_flag style) are exempt."""
    rng = np.random.default_rng(13)
    inputs, targets = {}, {}
    for split, n in (("train", 400), ("val", 120), ("test", 120)):
        x = rng.normal(0, 1, size=(n, 5))
        p = 1.0 / (1.0 + np.exp(-x[:, 0]))
        inputs[split] = x
        targets[split] = (rng.random(n) < p).astype(np.float64)
    result = formula_derivation_probe(inputs, targets)
    for split in ("train", "val", "test"):
        assert result[split]["knn_active"] is False
        assert not any(result[split]["derived"])


# ---------------------------------------------------------------------------
# (c) the choco RNG bootstrap labels
# ---------------------------------------------------------------------------


def test_rng_bootstrap_labels_still_caught_and_real_rows_untouched():
    rng = np.random.default_rng(21)
    groups = 60  # country-years
    feats = rng.normal(0, 1, size=(groups, 11))
    means = 0.3 + 0.5 * rng.random(groups)  # yields in a realistic t/ha range
    # documented construction: 8 draws per country-year on identical features,
    # label = mean_y + rng.normal(0.0, 0.4)
    boot_x = np.repeat(feats, 8, axis=0)
    boot_y = np.repeat(means, 8) + rng.normal(0, 0.4, groups * 8)
    # alongside genuinely observed rows with unique features
    real_x = rng.normal(0, 1, size=(50, 11))
    real_y = 0.5 + 0.2 * real_x[:, 0] + rng.normal(0, 0.15, 50)
    x = np.vstack([boot_x, real_x])
    y = np.concatenate([boot_y, real_y])
    inputs = {"train": x, "val": x, "test": x}
    targets = {"train": y, "val": y, "test": y}
    result = formula_derivation_probe(inputs, targets)
    n_boot = groups * 8
    for split in ("val", "test"):
        derived = result[split]["derived"]
        assert all(derived[:n_boot]), "every bootstrap draw must be caught"
        assert not any(derived[n_boot:]), "no genuinely observed row may be flagged"


# ---------------------------------------------------------------------------
# probe contract
# ---------------------------------------------------------------------------


def test_mixed_shape_kinds_are_rejected():
    rng = np.random.default_rng(3)
    inputs = {"train": rng.normal(size=(8, 24, 3)), "val": rng.normal(size=(4, 3))}
    targets = {"train": rng.normal(size=(8, 24)), "val": rng.normal(size=4)}
    with pytest.raises(ValueError, match="share one shape kind"):
        formula_derivation_probe(inputs, targets)


def test_acf_bound_is_clamped():
    assert acf_bound(4) == 0.65
    assert acf_bound(24) == pytest.approx(3.0 / math.sqrt(24))
    assert acf_bound(336) == 0.35
