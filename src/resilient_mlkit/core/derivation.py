"""Formula-derivation probes shared by every repo's R5 provenance binding.

WHY THIS EXISTS
---------------
R5 refuses any synthetic, simulated or formula-derived row in val or test. The
*declaration* half of that (a pack's own ``evidence_mode`` / target-provenance
metadata) belongs to each repo's binding. The *measurement* half — "is this
row's target a function of its own inputs?" — is a gate, and a gate must have
exactly one definition. Until 2026-08-16 the only measured implementation
lived in resilient-surge's ``mlkit_bindings._formula_derivation``; this module
is that probe promoted to the shared tool, with one defect fixed and two
detection gaps closed. The defect is E-017 (resilient-surge
``docs/ESCALATIONS.md``): an out-of-sample linear fit cannot separate "the
target is computed from the inputs" from "the target is physically predictable
from the inputs", and at the bottom of the observed distribution it flagged
verified NOAA CO-OPS storm windows as formula-derived.

EVERY CONSTANT BELOW IS PLACED BY MEASUREMENT, NOT BY TASTE. The two
populations, measured 2026-08-16 on resilient-surge (dataset 2026.08.2,
2,816 windowed rows, t=336) and on the documented pre-2026-08-15 synthetic
fixture construction (``sample_io.py`` docstring: ``target = 0.3*era5[...,0]
+ 0.1*tide + N(0, 0.05)``, t=24):

    ============================  =================  ====================
    population                    residual ratio      residual lag-1 acf
    ============================  =================  ====================
    formula-derived fixture rows  0.120 – 0.249       -0.294 – +0.394
    observed rows the old probe
    flagged (storm windows)       0.348 – 0.499       +0.730 – +0.959
    observed population medians   0.883 – 0.986       0.925 – 0.959
    ============================  =================  ====================

The two populations overlap in NEITHER column once both are read together,
and that is the discriminator: a derived target's residual under the
train-fitted map is the generator's own noise term — small AND unstructured —
while an observed target's residual is unmodelled geophysics — possibly small
in a storm window, but smooth, because the ocean does not produce white
hourly innovations. E-017 option 2 ("change the discriminator so it separates
'predictable' from 'derived' … or by requiring an exact functional match
rather than a variance ratio") is exactly this.

THE WINDOWED RULE (rows shaped ``(n, t, d)`` with targets ``(n, t)``)
--------------------------------------------------------------------
Fit one linear map from all input channels (plus intercept) to the target on
the train split only; apply it fixed to every split. Per row:

    ratio  = std(residual over the window) / std(target over the window)
    acf1   = lag-1 autocorrelation of the residual over the window

    derived iff  ratio <= FORMULA_RESIDUAL_RATIO (0.5)
        and NOT ( HARD_DERIVED_RATIO (0.3) < ratio        # ambiguous band
                  and t >= STRUCTURE_MIN_TIMESTEPS
                  and acf1 > acf_bound(t) )               # structured: physics

``acf_bound(t) = clamp(3/sqrt(t), 0.35, 0.65)`` — three standard errors of the
lag-1 autocorrelation of white noise of length t (se ~ 1/sqrt(t)), floored so
long windows cannot make the bound trivially small and capped so short ones
cannot excuse everything. At the measured populations: fixture rows (t=24,
bound 0.61) sit at acf1 <= 0.394 and are NOT excused; observed storm windows
(t=336, bound 0.35) sit at acf1 >= 0.730 and are excused. Rows at or below
the 0.3 hard floor are derived REGARDLESS of structure, so a formula plus a
small amount of smoothed noise cannot hide behind the excusal: the fixture
construction measures 0.120-0.249, entirely under the floor, and the flagged
observed rows measure 0.348-0.499, entirely above it.

The rejected alternative, measured before rejecting: an inverse-barometer-only
null (train-fitted restricted regression on the msl channel) separates the
same populations at full/null ratio 0.17 vs 0.574-0.644, but it requires each
repo to declare privileged physics channels, and it under-explains exactly the
storms that matter (wind setup: the flagged rows' IB-null ratios are
0.766-0.852, far above their full-fit 0.471-0.493). The residual-structure
test needs no domain declaration and separates more cleanly.

THE TABULAR RULES (rows shaped ``(n, d)`` with targets ``(n,)``)
----------------------------------------------------------------
A per-row ``|residual| / std(target)`` against 0.5 is NOT a usable tabular
test: for genuinely observed targets with a decent linear fit, roughly half
of all rows land under 0.5 by construction (the per-window std that makes the
windowed ratio a population statistic collapses to a single draw). So tabular
rows are never flagged by the linear probe. They are flagged by two probes
that measure the two documented tabular derivation classes directly
(measured 2026-08-16 on constructions taken from the repos' own records):

* NEAREST-NEIGHBOUR DETERMINISM — resilient-blackout's
  ``tads_annual_failure_probability`` reconstruction (a closed-form function
  of ``volt_class`` and ``length_km``; ``fragility_registry.py:286-301``,
  rates from ``config/nerc_tads_rates.json``). A deterministic smooth target
  is reproduced by its nearest train neighbour in standardised feature space:
  measured median knn ratio 0.0026-0.0042 on the reconstruction vs 0.44 on an
  observed-style control. Determinism is a property of the construction,
  evidenced by the population, never by one lucky row — so when a split's
  75th-percentile knn ratio is at or below KNN_DERIVED_RATIO the WHOLE split
  is derived (a row's large knn residual there measures local feature
  sparsity, not honesty: the measured reconstruction has median 0.003 with a
  lone long-line row at 0.18); when only the median clears the bound (a mixed
  split) rows are flagged individually; and the probe only applies to targets
  with enough distinct values (KNN_MIN_UNIQUE_TARGET_FRACTION) so that
  discrete/binary observed labels, where the nearest neighbour often shares
  the label honestly, can never trip it.

* DUPLICATE-INPUT LABEL DRAWS — resilient-choco's retired bootstrap
  augmentation (``docs/BLOCKERS.md``: 8 rows per country-year whose label is
  ``mean_y + rng.normal(0.0, 0.4)`` on identical features;
  ``src/data/yield_panel.py`` now refuses ``bootstrap_per_country_year != 0``).
  Rows whose full input vector is byte-identical to another row's while their
  targets differ are label draws, not observations: measured 480/480 caught
  on the documented construction, 0/500 on continuous observed-style
  controls, where exact float duplication does not occur.

Both tabular probes also run on windowed rows (a windowed pack can carry
duplicated windows); the linear-probe band-and-structure rule is windowed
only.

An ``exact`` flag passed by the binding (e.g. surge's graphcast-is-rolled-era5
bit-identity test) is OR'd in and can never be removed by any probe here:
measurement may only ADD taint.

WHAT THIS CHANGE DELIBERATELY DOES NOT DO. It does not move
FORMULA_RESIDUAL_RATIO off 0.5. It does not drop, re-window or re-split any
row. The structure excusal applies only inside the ambiguous band, only to
windowed rows long enough to measure structure, and the previously-caught
failures are pinned as unit tests in ``tests/test_derivation.py``: the surge
fixture construction, the blackout TADS reconstruction and the choco
bootstrap draws must all STILL be caught by this module, and the build fails
if any of them is not.

KNOWN RESIDUAL AMBIGUITY, stated rather than hidden: a target manufactured as
``formula(inputs) + structured noise scaled into the (0.3, 0.5] band`` is
observationally indistinguishable from physics by ANY residual test — that
target lies within its own noise of a physical relationship. The defence
against that construction is not this probe but the declaration layer
(lineage, licence and target-provenance records), which no measurement here
can promote to ``real``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: Out-of-sample residual-ratio threshold at or below which a row is a
#: derivation candidate. Unchanged from the original surge probe.
FORMULA_RESIDUAL_RATIO = 0.5

#: At or below this ratio a windowed row is derived regardless of residual
#: structure. Measured populations: derived fixture rows 0.120-0.249,
#: physics rows 0.348+ (2026-08-16, see module docstring).
HARD_DERIVED_RATIO = 0.3

#: Minimum window length for the residual-structure excusal; below this the
#: lag-1 autocorrelation of a window is too noisy to certify structure, and
#: the rule falls back to the plain ratio test (the pre-2026-08-16 behaviour).
STRUCTURE_MIN_TIMESTEPS = 16

#: Bounds for acf_bound(t).
ACF_BOUND_FLOOR = 0.35
ACF_BOUND_CEIL = 0.65

#: Nearest-neighbour determinism bound. A tabular split whose 75th-percentile
#: knn ratio is at or below this is a deterministic reconstruction and every
#: row of it is derived; a split where only the median clears it is mixed and
#: rows are flagged individually. Measured: median 0.0026-0.0042 / p90 <= 0.055
#: on the TADS reconstruction, median 0.44 on an observed-style control
#: (2026-08-16).
KNN_DERIVED_RATIO = 0.15

#: The nearest-neighbour probe only applies to targets that are effectively
#: continuous. Discrete labels (binary flags, class ids) make the nearest
#: neighbour share the label honestly, so they are exempt by construction.
KNN_MIN_UNIQUE_TARGET_FRACTION = 0.5

#: Cap on the train reference used by the nearest-neighbour probe; larger
#: train splits are strided down deterministically.
KNN_MAX_TRAIN_REFERENCE = 20000


def acf_bound(t: int) -> float:
    """Three white-noise standard errors of lag-1 autocorrelation, clamped."""
    return min(ACF_BOUND_CEIL, max(ACF_BOUND_FLOOR, 3.0 / (t**0.5)))


def _as_float64(arr: Any) -> Any:
    import numpy as np

    return np.asarray(arr, dtype=np.float64)


def _residual_acf1(residual: Any) -> Any:
    """Per-row lag-1 autocorrelation of an ``(n, t)`` residual array."""
    import numpy as np

    r = residual - residual.mean(axis=1, keepdims=True)
    num = (r[:, 1:] * r[:, :-1]).sum(axis=1)
    den = np.maximum((r**2).sum(axis=1), 1e-30)
    return num / den


def _duplicate_input_flags(inputs: Any, target: Any) -> list[bool]:
    """Rows whose input bytes duplicate another row's while targets differ."""
    import numpy as np

    n = inputs.shape[0]
    groups: dict[bytes, list[int]] = {}
    for i in range(n):
        groups.setdefault(np.ascontiguousarray(inputs[i]).tobytes(), []).append(i)
    flags = [False] * n
    for idx in groups.values():
        if len(idx) > 1:
            values = target[idx]
            if not bool(np.all(values == values[0])):
                for i in idx:
                    flags[i] = True
    return flags


def _knn_ratios(train_x: Any, train_y: Any, eval_x: Any, eval_y: Any, *, self_reference: bool) -> Any:
    """|target - nearest train neighbour's target| / std(eval targets).

    Features are standardised by train statistics. When ``self_reference`` is
    true (evaluating the train split against itself) each row's own index is
    excluded, so an exact self-match can never vouch for itself; a distance-0
    NON-self match (a duplicated input row) is left in deliberately.
    """
    import numpy as np

    mean = train_x.mean(axis=0)
    scale = np.maximum(train_x.std(axis=0), 1e-12)
    ref = (train_x - mean) / scale
    if not self_reference and ref.shape[0] > KNN_MAX_TRAIN_REFERENCE:
        stride = int(np.ceil(ref.shape[0] / KNN_MAX_TRAIN_REFERENCE))
        ref = ref[::stride]
        train_y = train_y[::stride]
    query = (eval_x - mean) / scale
    denom = max(float(np.std(eval_y)), 1e-12)
    out = np.empty(query.shape[0], dtype=np.float64)
    chunk = max(1, int(2e7) // max(ref.shape[0], 1))
    for start in range(0, query.shape[0], chunk):
        stop = min(start + chunk, query.shape[0])
        d2 = ((query[start:stop, None, :] - ref[None, :, :]) ** 2).sum(axis=2)
        if self_reference:
            for row, j in enumerate(range(start, stop)):
                d2[row, j] = np.inf
        nn = d2.argmin(axis=1)
        out[start:stop] = np.abs(eval_y[start:stop] - train_y[nn]) / denom
    return out


def formula_derivation_probe(
    inputs: Mapping[str, Any],
    targets: Mapping[str, Any],
    *,
    train_split: str = "train",
    exact: Mapping[str, Sequence[bool]] | None = None,
    residual_ratio_threshold: float = FORMULA_RESIDUAL_RATIO,
    hard_derived_ratio: float = HARD_DERIVED_RATIO,
    knn_derived_ratio: float = KNN_DERIVED_RATIO,
) -> dict[str, Any]:
    """Measure, per row and per split, whether a target is derived from its inputs.

    ``inputs[split]`` is ``(n, t, d)`` (windowed) or ``(n, d)`` (tabular);
    ``targets[split]`` is ``(n, t)`` or ``(n,)`` correspondingly. All splits
    must share one kind. ``exact[split]``, when given, is a per-row bool the
    binding measured outside this probe (e.g. a bit-identity reconstruction);
    it is OR'd into ``derived`` and nothing here can clear it.

    Returns a dict with, per split: ``n``, ``kind``, ``residual_ratio``,
    ``residual_acf1`` (windowed only), ``physics_excused`` (windowed only),
    ``knn_ratio``/``knn_active`` (tabular only), ``duplicate_inputs`` and
    ``derived``; plus top-level ``coefficients`` of the train-fitted map and
    the decision constants used. The decision rules and every constant are
    argued in the module docstring against the 2026-08-16 measurements.
    """
    import numpy as np

    if train_split not in inputs or train_split not in targets:
        raise ValueError(f"train split '{train_split}' missing from inputs/targets")

    kinds = {split: _as_float64(inputs[split]).ndim for split in inputs}
    if set(kinds.values()) - {2, 3}:
        raise ValueError(f"inputs must be (n, d) or (n, t, d); got ndims {kinds}")
    if len(set(kinds.values())) != 1:
        raise ValueError(f"all splits must share one shape kind; got {kinds}")
    windowed = kinds[train_split] == 3

    def design(split: str) -> Any:
        x = _as_float64(inputs[split])
        flat = x.reshape(-1, x.shape[-1]) if windowed else x
        return np.concatenate([flat, np.ones((flat.shape[0], 1))], axis=1)

    train_y = _as_float64(targets[train_split]).ravel()
    coefficients, *_ = np.linalg.lstsq(design(train_split), train_y, rcond=None)

    out: dict[str, Any] = {
        "coefficients": [float(c) for c in coefficients],
        "constants": {
            "residual_ratio_threshold": float(residual_ratio_threshold),
            "hard_derived_ratio": float(hard_derived_ratio),
            "knn_derived_ratio": float(knn_derived_ratio),
            "structure_min_timesteps": STRUCTURE_MIN_TIMESTEPS,
        },
    }

    train_x_flat = _as_float64(inputs[train_split]).reshape(
        _as_float64(inputs[train_split]).shape[0], -1
    )

    for split in inputs:
        x = _as_float64(inputs[split])
        y = _as_float64(targets[split])
        n = x.shape[0]
        exact_flags = [bool(v) for v in (exact or {}).get(split, [False] * n)]
        if len(exact_flags) != n:
            raise ValueError(f"exact['{split}'] has {len(exact_flags)} flags for {n} rows")

        predicted = design(split) @ coefficients
        duplicates = _duplicate_input_flags(x.reshape(n, -1), y.reshape(n, -1))
        record: dict[str, Any] = {"n": int(n), "kind": "windowed" if windowed else "tabular"}
        record["duplicate_inputs"] = duplicates

        if windowed:
            t = x.shape[1]
            residual = y - predicted.reshape(n, t)
            ratio = np.std(residual, axis=1) / np.maximum(np.std(y, axis=1), 1e-12)
            acf1 = _residual_acf1(residual)
            bound = acf_bound(t)
            excused = [
                bool(
                    hard_derived_ratio < ratio[i] <= residual_ratio_threshold
                    and t >= STRUCTURE_MIN_TIMESTEPS
                    and acf1[i] > bound
                )
                for i in range(n)
            ]
            linear_derived = [
                bool(ratio[i] <= residual_ratio_threshold and not excused[i]) for i in range(n)
            ]
            record.update(
                {
                    "residual_ratio": [float(v) for v in ratio],
                    "residual_acf1": [float(v) for v in acf1],
                    "acf_bound": float(bound),
                    "physics_excused": excused,
                }
            )
            knn_flags = [False] * n
        else:
            residual = np.abs(y - predicted)
            ratio = residual / max(float(np.std(y)), 1e-12)
            # Reported as evidence only: a single-draw |residual|/std against a
            # 0.5 threshold would flag half of any honestly-fit observed split.
            record["residual_ratio"] = [float(v) for v in ratio]
            linear_derived = [False] * n
            unique_fraction = len(np.unique(train_y)) / max(len(train_y), 1)
            if unique_fraction >= KNN_MIN_UNIQUE_TARGET_FRACTION:
                knn = _knn_ratios(
                    train_x_flat,
                    train_y,
                    x,
                    y,
                    self_reference=(split == train_split),
                )
                if np.quantile(knn, 0.75) <= knn_derived_ratio:
                    # the construction itself is deterministic: all rows derived
                    active, knn_flags = True, [True] * n
                elif np.median(knn) <= knn_derived_ratio:
                    # mixed split: flag the reconstructable rows individually
                    active = True
                    knn_flags = [bool(v <= knn_derived_ratio) for v in knn]
                else:
                    active, knn_flags = False, [False] * n
                record.update(
                    {"knn_ratio": [float(v) for v in knn], "knn_active": active}
                )
            else:
                knn_flags = [False] * n
                record.update({"knn_ratio": None, "knn_active": False})

        record["derived"] = [
            bool(exact_flags[i] or linear_derived[i] or knn_flags[i] or duplicates[i])
            for i in range(n)
        ]
        out[split] = record

    return out
