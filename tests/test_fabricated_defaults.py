"""R10 unit tests, built from the real defect shapes of the August 2026 sweep.

Every POSITIVE fixture below is the pre-fix source of a defect that actually
shipped in one of the eight repos, reduced to its smallest reproducing form and
cited to the file and line it came from. Every NEGATIVE fixture is a legitimate
configuration default or a correct repair taken from the same trees. The two
sets together are what the check was tuned against; a change that makes any
negative fire is a regression whatever it does to the positives, because a
check that cries wolf gets disabled and a disabled check still looks like
coverage.
"""

from __future__ import annotations

import textwrap

import pytest

from resilient_mlkit.core.fabrication import (
    Finding,
    is_measured_name,
    satisfies_a_gate,
    scan_source,
    tokenise,
)


def scan(src: str) -> list[Finding]:
    return scan_source(textwrap.dedent(src), "module.py")


def symbols(src: str) -> set[str]:
    return {f.symbol for f in scan(src)}


# ---------------------------------------------------------------------------
# Positive set — the real defect shapes
# ---------------------------------------------------------------------------


def test_empty_smd_dict_reports_perfect_balance():
    """resilient-fray src/analysis/validate_smd.py:38 (pre-fix).

    ``max_smd = max(smds.values()) if smds else 0.0`` reported perfect
    covariate balance for an empty covariate dict, and 0.0 cleared the
    ``<= threshold`` gate on the very next line.
    """
    findings = scan(
        """
        def check_balance(df, covariate_cols, threshold=0.1):
            smds = {}
            for col in covariate_cols:
                smds[col] = compute_smd(df, col)
            max_smd = max(smds.values()) if smds else 0.0
            return {"smds": smds, "max_smd": max_smd, "pass": max_smd <= threshold}
        """
    )
    assert [f.symbol for f in findings] == ["max_smd"]
    assert findings[0].shape == "ternary fallback"
    assert findings[0].literal == "0.0"
    assert findings[0].severity == "SATISFIES_GATE"


def test_degenerate_branch_returns_a_perfect_p_value():
    """resilient-fray src/analysis/validate_parallel_trends.py:21-38 (pre-fix).

    Every degenerate branch returned ``{'slope_diff': 0.0, 'f_pvalue': 1.0,
    'pass': True}`` -- the strongest possible evidence of parallel trends,
    emitted for a test that never ran.
    """
    found = symbols(
        """
        def validate_parallel_trends(panel):
            if panel is None:
                return {"slope_diff": 0.0, "f_pvalue": 1.0, "pass": True}
            return _run_test(panel)
        """
    )
    # ``slope_diff`` is outside the vocabulary by design -- "slope" names no
    # measured quantity on its own -- but the p-value beside it is the figure
    # the gate reads, and one hit is enough to surface the branch.
    assert "f_pvalue" in found


def test_spatial_cv_r2_default_sits_above_its_own_threshold():
    """resilient-arabica src/validation/run_validate.py:235 (pre-fix), CRITICAL.

    An empty fold list reported ``spatial_cv_r2`` 0.85 and PASSED a ``> 0.65``
    gate having fitted nothing: the invented default sat above the bar it was
    checked against.
    """
    findings = scan(
        """
        def run_spatial_cv(df, folds):
            r2s = [fit(f) for f in folds]
            mean_r2 = float(np.mean(r2s)) if r2s else 0.85
            passed = mean_r2 > 0.65
            return {"spatial_cv_r2": mean_r2, "passed": passed}
        """
    )
    assert any(f.symbol == "mean_r2" and f.literal == "0.85" for f in findings)
    assert all(f.severity == "SATISFIES_GATE" for f in findings if f.symbol == "mean_r2")


def test_pretrend_pvalue_hardcoded_in_the_live_branch():
    """resilient-arabica src/analysis/subfield_did.py:198 (pre-fix), MAJOR.

    ``pretrend_pvalue=0.50 if n_periods > 2 else None`` cleared a ``p >= 0.10``
    gate although no pre-trend test ran anywhere in that branch.
    """
    findings = scan(
        """
        def estimate_subfield_did(panel, n_periods):
            return SubfieldDiDResult(
                att=att,
                parallel_trends_ok=True,
                pretrend_pvalue=0.50 if n_periods > 2 else None,
            )
        """
    )
    assert any(f.symbol == "pretrend_pvalue" and f.literal == "0.5" for f in findings)


def test_exp_of_an_effect_size_is_not_a_p_value():
    """resilient-chokepoint causal/event_study.py:93 (pre-fix), CRITICAL.

    An empty panel returned ``pre_trend_pvalue = 1.0``: "parallel trends hold",
    from a test with no statistic, no null distribution and no data.
    """
    findings = scan(
        """
        def event_study(panel):
            pre_values = panel.get("pre", [])
            pre_trend_pvalue = 1.0 if not pre_values else exp(-abs(mean(pre_values)))
            parallel_trends_ok = pre_trend_pvalue > 0.05
            return {"pre_trend_pvalue": pre_trend_pvalue, "ok": parallel_trends_ok}
        """
    )
    assert any(f.symbol == "pre_trend_pvalue" and f.literal == "1.0" for f in findings)


def test_coverage_payload_built_when_the_calibrator_is_absent():
    """resilient-choco src/registry/promotion_gate.py:126,137 (pre-fix), CRITICAL.

    ``gate_coverage`` built ``{"empirical_coverage": 0.90}`` out of thin air
    when models/cqr_calibrator.joblib was absent -- which was every run this
    repo ever did -- validated that payload against itself, and returned PASS.
    """
    found = symbols(
        """
        def gate_coverage():
            calibrator = MODELS / "cqr_calibrator.joblib"
            if not calibrator.is_file():
                payload = {"validation": {"empirical_coverage": 0.90}}
            else:
                obj = ConformalCalibrator.load(calibrator)
                payload = {"validation": {"empirical_coverage": float(obj.coverage)}}
            cov = float(payload["validation"]["empirical_coverage"])
            return True, cov, f"coverage {cov:.3f}"
        """
    )
    assert "empirical_coverage" in found


def test_gate_returning_true_when_its_fixture_is_missing():
    """resilient-choco src/registry/promotion_gate.py:57,170,214,239 (pre-fix).

    ``if not BASELINE.is_file(): return True, float("nan"), "skipped"`` --
    the gate's own contract says PASS, and the figure beside it is decoration.
    """
    findings = scan(
        """
        def gate_crps_regression(checkpoint):
            if not BASELINE_CRPS_PATH.is_file():
                return True, float("nan"), "baseline fixture missing - skipped"
            return _measure(checkpoint)
        """
    )
    assert any(f.shape.startswith("gate returns PASS") for f in findings)


def test_champion_and_challenger_mape_both_defaulted():
    """resilient-choco src/registry/promotion_gate.py:268,272 (pre-fix).

    An absent leaderboard reported a challenger 25% better than a champion and
    auto-promoted; neither number came from a model.
    """
    findings = scan(
        """
        def gate_train_metrics(champion_mape: float = 0.20, challenger_mape: float = 0.15):
            promoted = challenger_mape < champion_mape
            return promoted
        """
    )
    assert {f.symbol for f in findings} == {"champion_mape", "challenger_mape"}
    assert all(f.shape == "parameter default" for f in findings)


def test_csi_returns_one_on_an_empty_comparison():
    """resilient-torrent benchmark_hydrographnet.py:78 and three siblings.

    Four independent CSI implementations returned a perfect 1.0 when the
    comparison was empty; one of them backed a declared CI gate of
    ``csi_005 >= 0.85``.
    """
    findings = scan(
        """
        def compute_csi(pred, target, threshold):
            tp = np.sum(pred & target)
            fp = np.sum(pred & ~target)
            fn = np.sum(~pred & target)
            if tp + fp + fn == 0:
                return 1.0
            return float(tp / (tp + fp + fn))
        """
    )
    assert any(f.symbol == "compute_csi" and f.literal == "1.0" for f in findings)


def test_metric_named_only_in_its_docstring_is_still_recognised():
    """resilient-torrent benchmark_mswegnn.py:320 (pre-fix).

    ``_critical_success_index`` spells the metric out in the name and
    abbreviates it in the docstring; only the acronym is in the vocabulary.
    """
    findings = scan(
        '''
        def _critical_success_index(ref, pred, threshold=0.05):
            """Critical Success Index (CSI) = TP / (TP + FN + FP)."""
            denominator = tp + fn + fp
            if denominator == 0.0:
                return 1.0
            return tp / denominator
        '''
    )
    assert any(f.literal == "1.0" for f in findings)


def test_both_sides_of_a_headline_comparison_invented():
    """resilient-surge evaluation/hindcast_suite/leaderboard.py:125,127 (pre-fix).

    ``avg_rmse.get("adcirc", 0.30)`` invented the competitor baseline and
    ``avg_rmse.get(best_model, 0.0)`` invented the winner's score; on an empty
    leaderboard this reported "0.00m, 100% improvement vs ADCIRC".
    """
    findings = scan(
        """
        def generate_summary(avg_rmse, best_model):
            adcirc_rmse = avg_rmse.get("adcirc", 0.30)
            best_rmse = avg_rmse.get(best_model, 0.0)
            improvement = (adcirc_rmse - best_rmse) / adcirc_rmse * 100
            return {
                "adcirc_rmse_24h_m": adcirc_rmse,
                "best_rmse_24h_m": best_rmse,
                "improvement_vs_adcirc_pct": improvement,
            }
        """
    )
    assert {"adcirc_rmse", "best_rmse"} <= {f.symbol for f in findings}


def test_empty_bias_audit_reports_no_critical_bias():
    """resilient-surge governance/model_card.py:90 (pre-fix).

    ``bias_audit_results.get("max_disparity", 0.0) < 0.20`` made an EMPTY bias
    audit report no_critical_bias True. ``max_`` must not veto here: the
    maximum observed disparity is a measurement, not a threshold.
    """
    findings = scan(
        """
        def compliance_checks(bias_audit_results):
            no_critical_bias = bias_audit_results.get("max_disparity", 0.0) < 0.20
            return {"no_critical_bias": no_critical_bias, "all_pass": no_critical_bias}
        """
    )
    assert any(f.symbol == "max_disparity" for f in findings)


def test_champion_and_challenger_rmse_default_to_a_perfect_score():
    """resilient-triage api/routers/mlops_router.py:150-151 (pre-fix).

    A challenger with no recorded RMSE was served as
    ``{"challenger_rmse": 0.0, "improvement_pct": 100.0}``. 0.0 is not
    "no score"; it is a perfect score.
    """
    found = symbols(
        """
        def compare(pair):
            champion_rmse = pair.get("champion_rmse", 0.0)
            challenger_rmse = pair.get("challenger_rmse", 0.0)
            improvement_pct = (champion_rmse - challenger_rmse) / champion_rmse * 100
            return {
                "champion_rmse": champion_rmse,
                "challenger_rmse": challenger_rmse,
                "improvement_pct": improvement_pct,
            }
        """
    )
    assert {"champion_rmse", "challenger_rmse"} <= found


def test_missing_refuter_effect_becomes_a_passing_verdict():
    """resilient-triage causal/dag.py:209-210 (pre-fix).

    A refuter exposing neither p_value nor new_effect had new_effect defaulted
    to 0.0, giving p_value 1.0 and passed True.
    """
    found = symbols(
        """
        def extract_refutation(refutation_result):
            new_effect = getattr(refutation_result, "new_effect", 0.0)
            p_value = 1.0 if abs(new_effect) < 1e-6 else 0.01
            passed = p_value > 0.05
            return {"p_value": p_value, "passed": passed}
        """
    )
    assert "new_effect" in found or "p_value" in found


def test_cate_and_se_drawn_from_a_random_generator():
    """resilient-chokepoint analysis/heterogeneity.py:66-86 (pre-fix), CRITICAL.

    CATEs were ``rng.normal(0.5, 0.3)``, standard errors ``rng.uniform(0.1,
    0.25)``, and significance was stamped as ``|cate| > 1.96*se`` on those
    draws -- a significance verdict on noise, in a module documented as using
    a causal forest.
    """
    findings = scan(
        """
        def estimate_chokepoint_cate(chokepoints, seed=0):
            rng = np.random.default_rng(seed)
            for cp in chokepoints:
                cate = rng.normal(0.5, 0.3)
                se = rng.uniform(0.1, 0.25)
                profiles.append(ChokepointCATE(cate=cate, se=se, significant=abs(cate) > 1.96 * se))
        """
    )
    assert {"cate", "se"} <= {f.symbol for f in findings}
    assert all(f.shape == "drawn from an RNG" for f in findings if f.symbol in {"cate", "se"})


def test_insufficient_data_constructs_a_perfect_result_object():
    """resilient-chokepoint mlops/champion_challenger.py:79-90 (pre-fix).

    Zero comparisons returned ``champion_rmse=0.0`` (a perfect model) with
    ``p_value=1.0``.
    """
    found = symbols(
        """
        def evaluate(self):
            if len(self._champion_responses) < 30:
                return ChallengerResult(
                    champion_rmse=0.0,
                    challenger_rmse=0.0,
                    p_value=1.0,
                    recommendation="insufficient data",
                )
            return self._real_evaluate()
        """
    )
    assert {"champion_rmse", "challenger_rmse", "p_value"} <= found


def test_pit_p_value_keyed_by_its_dict_key_not_its_local_name():
    """resilient-choco src/validation/calibration_metrics.py:197 (pre-fix).

    ``pit_p = float(data.get("pit_chi2_p", 1.0))`` names the quantity by its
    key and gates on the local ``pit_p``; the two aliases have to be joined up
    or the sink is invisible.
    """
    findings = scan(
        """
        def validate_calibration(data, enforce_distribution=True):
            ok = True
            pit_p = float(data.get("pit_chi2_p", 1.0))
            if enforce_distribution and pit_p < PIT_CHI2_MIN_P:
                ok = False
            return ok
        """
    )
    assert any(f.symbol == "pit_chi2_p" for f in findings)


def test_producer_call_names_the_quantity_when_the_local_does_not():
    """resilient-surge products/regulatory/parametric_trigger_bond.py:153.

    ``el = self.compute_expected_loss(ep) if ep else 0.05`` is anonymous at the
    assignment; only the displaced producer says what 0.05 is standing in for.
    """
    findings = scan(
        """
        def generate_term_sheet(self, ep_curve=None):
            el = self.compute_expected_loss(ep_curve) if ep_curve else 0.05
            return {"expected_loss_pct": el * 100, "instrument_type": "Catastrophe Bond"}
        """
    )
    assert findings, "the displaced producer names the quantity"


# ---------------------------------------------------------------------------
# Negative set — legitimate configuration and correct repairs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            """
            def train(cfg):
                batch_size = cfg.get("batch_size", 32)
                learning_rate = cfg.get("learning_rate", 3e-4)
                n_epochs = cfg.get("n_epochs", 100)
                seed = cfg.get("seed", 1234)
                timeout = cfg.get("timeout", 30.0)
                n_retries = cfg.get("retries", 3)
                return run(batch_size, learning_rate, n_epochs, seed, timeout, n_retries)
            """,
            id="training-knobs",
        ),
        pytest.param(
            """
            def gate(metrics, cfg):
                min_r2 = cfg.get("min_r2", 0.85)
                max_rmse = cfg.get("max_rmse", 1.2)
                return metrics["r2"] >= min_r2 and metrics["rmse"] <= max_rmse
            """,
            id="thresholds-read-from-config",
        ),
        pytest.param(
            """
            def gate_coverage(*, nominal_coverage: float = 0.90, tolerance: float = 0.02):
                empirical = measure_coverage()
                return abs(empirical - nominal_coverage) <= tolerance
            """,
            id="nominal-threshold-parameters",
        ),
        pytest.param(
            """
            def estimate(panel):
                try:
                    att, se = fit(panel)
                except FitError as exc:
                    return DiDResult(
                        att=float("nan"),
                        se=float("inf"),
                        parallel_trends_ok=False,
                        unmeasured_reason=f"the fit failed ({exc}); no ATT was estimated.",
                    )
                return DiDResult(att=att, se=se, parallel_trends_ok=True)
            """,
            id="the-correct-repair-nan-and-a-reason",
        ),
        pytest.param(
            """
            def run_gate(metrics):
                checks = {}
                if "rmse" not in metrics:
                    checks["rmse"] = False
                    messages["rmse"] = "RMSE comparison not available"
                return checks
            """,
            id="withholding-a-pass-is-not-fabricating-one",
        ),
        pytest.param(
            """
            def robust_threshold(df, threshold):
                median = df["level"].median()
                mad = np.median(np.abs(df["level"] - median))
                if mad == 0:
                    mad = 1e-6
                return np.abs(df["level"] - median) > threshold * mad
            """,
            id="epsilon-divide-by-zero-guard",
        ),
        pytest.param(
            """
            def train_epoch(model, val_loader):
                for epoch in range(10):
                    if val_loader is not None and epoch % 10 == 0:
                        val_loss = 0.0
                        for batch in val_loader:
                            val_loss += step(batch)
                        history["val_loss"].append(val_loss)
            """,
            id="accumulator-initialiser",
        ),
        pytest.param(
            """
            def portfolio_totals(events):
                losses = [e["loss_usd"] for e in events]
                total_loss_usd = sum(losses) if losses else 0.0
                return {"total_loss_usd": total_loss_usd}
            """,
            id="sum-over-an-empty-set-really-is-zero",
        ),
        pytest.param(
            """
            def fit_panel(y, x):
                mod = PanelOLS(y, x, entity_effects=True, time_effects=True)
                return mod.fit(cov_type="clustered")
            """,
            id="fixed-effects-specification-is-not-an-effect-size",
        ),
        pytest.param(
            """
            def synthetic_calibration_data(n, seed=0):
                rng = np.random.default_rng(seed)
                y_prob = rng.beta(2, 5, n)
                return y_prob
            """,
            id="a-declared-synthetic-generator",
        ),
        pytest.param(
            """
            def indicator(score, q):
                return 1.0 if score > q else 0.0
            """,
            id="an-indicator-function-is-not-a-fallback",
        ),
        pytest.param(
            """
            def build_report(scs_metrics):
                return E1FinancialEffects(
                    discount_rate=float(scs_metrics.get("discount_rate", 0.03)),
                    time_horizon_years=int(scs_metrics.get("time_horizon_years", 30)),
                )
            """,
            id="a-discount-rate-is-a-knob",
        ),
        pytest.param(
            """
            def hdi_compat(samples):
                try:
                    return pm.stats.hdi(samples, hdi_prob=0.95)
                except TypeError:
                    return pm.stats.hdi(samples, prob=0.95)
            """,
            id="a-library-keyword-is-not-a-published-figure",
        ),
        pytest.param(
            """
            def main(argv=None):
                if not run_all():
                    return 1
                return 0
            """,
            id="an-exit-code-is-not-a-metric",
        ),
    ],
)
def test_legitimate_defaults_do_not_fire(source):
    assert scan(source) == []


# ---------------------------------------------------------------------------
# Component behaviour
# ---------------------------------------------------------------------------


def test_tokenise_rejoins_split_names():
    assert "pvalue" in tokenise("p_value")
    assert "stderr" in tokenise("std_err")
    assert "smd" in tokenise("maxSMD")
    assert "r2" in tokenise("r2_oos")


@pytest.mark.parametrize(
    "name",
    ["max_smd", "empirical_coverage", "pre_trend_pvalue", "challenger_rmse", "spatial_cv_r2"],
)
def test_measured_names(name):
    assert is_measured_name(name)


@pytest.mark.parametrize(
    "name",
    ["batch_size", "learning_rate", "n_retries", "seed", "timeout", "entity_effects"],
)
def test_configuration_names(name):
    assert not is_measured_name(name)


def test_threshold_names_are_measurements_outside_a_config_context():
    # ``max_smd = max(smds.values())`` measures; ``min_r2 = cfg.get(...)`` configures.
    assert is_measured_name("max_smd")
    assert not is_measured_name("max_smd", config_context=True)


@pytest.mark.parametrize(
    "symbol,literal,expected",
    [
        ("empirical_coverage", "0.9", True),   # a coverage gate wants a high number
        ("empirical_coverage", "0.0", False),  # 0.0 coverage fails every gate
        ("challenger_rmse", "0.0", True),      # 0.0 error is a perfect model
        ("challenger_rmse", "999.0", False),   # a sentinel that fails
        ("pretrend_pvalue", "1.0", True),      # "no evidence against the null"
        ("pretrend_pvalue", "0.0", False),
        ("roc_auc", "0.5", False),             # 0.5 IS the no-skill point
        ("att_se", "0.0", True),               # zero-width CI: unknown polarity
        ("parallel_trends_ok", "True", True),
    ],
)
def test_polarity_decides_whether_a_default_satisfies_its_gate(symbol, literal, expected):
    assert satisfies_a_gate(symbol, literal) is expected


def test_a_default_that_reaches_nothing_is_not_reported():
    """The rule is "reaches a gate, metric or report", not "has a default"."""
    assert scan(
        """
        def plot(history):
            rmse = history.get("rmse", 0.0)
            axis.set_ylim(0, rmse * 1.1)
        """
    ) == []


def test_findings_carry_enough_to_adjudicate_in_seconds():
    finding = scan(
        """
        def gate(metrics):
            coverage = metrics.get("empirical_coverage", 0.9)
            return coverage >= 0.88
        """
    )[0]
    assert finding.line == 3
    assert finding.symbol == "empirical_coverage"
    assert finding.literal == "0.9"
    assert finding.sink == "returned from gate()"
    assert "metrics.get" in finding.snippet
    assert finding.to_dict()["severity"] == "SATISFIES_GATE"


# ---------------------------------------------------------------------------
# The check contract
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


def test_r10_is_registered_and_gates():
    from resilient_mlkit.checks import PHASE_ORDER, load_all
    from resilient_mlkit.portfolio import gating_ids

    load_all()
    assert "R10" in PHASE_ORDER["readiness"]
    # Second, right after the licence gate: it is the cheapest check in the
    # phase and it invalidates every figure downstream of a hit.
    assert PHASE_ORDER["readiness"][:2] == ["R9", "R10"]
    assert PHASE_ORDER["readiness"][-1] == "R8", "R8 reports, so it stays last"
    assert "R10" in gating_ids()


def test_r10_is_na_not_pass_when_no_source_tree_is_declared(tmp_path):
    from resilient_mlkit.checks.readiness import r10_fabricated_defaults
    from resilient_mlkit.core.result import Status

    repo = _repo(tmp_path, '[repo]\nname = "fixturerepo"\n', {})
    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    # Walking nothing and reporting green is the very defect R10 exists to
    # catch, so an undeclared tree can never be a pass.
    assert result.status is Status.NA
    assert "no [source] trees declared" in result.reason


def test_r10_is_na_when_the_declared_tree_does_not_exist(tmp_path):
    from resilient_mlkit.checks.readiness import r10_fabricated_defaults
    from resilient_mlkit.core.result import Status

    repo = _repo(tmp_path, '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n', {})
    assert r10_fabricated_defaults(repo, _ctx(tmp_path)).status is Status.NA


def test_r10_fails_on_a_fabricated_default_and_writes_the_full_list(tmp_path):
    from resilient_mlkit.checks.readiness import (
        R10_REPORT_RELPATH,
        r10_fabricated_defaults,
    )
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n',
        {
            "src/gate.py": """
                def gate_coverage(bundle):
                    empirical_coverage = bundle.get("empirical_coverage", 0.90)
                    return empirical_coverage >= 0.88
            """
        },
    )
    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "empirical_coverage" in result.reason
    assert result.evidence["satisfies_gate"] == 1
    report = (tmp_path / R10_REPORT_RELPATH).read_text()
    assert "empirical_coverage" in report and "SATISFIES_GATE" in report


def test_r10_passes_on_a_clean_tree(tmp_path):
    from resilient_mlkit.checks.readiness import r10_fabricated_defaults
    from resilient_mlkit.core.result import Status

    repo = _repo(
        tmp_path,
        '[repo]\nname = "x"\n[source]\ntrees = ["src"]\n',
        {
            "src/gate.py": """
                class GateUnmeasured(RuntimeError):
                    pass

                def gate_coverage(bundle, *, nominal_coverage: float = 0.90):
                    if "empirical_coverage" not in bundle:
                        raise GateUnmeasured("no calibrator; coverage is unmeasured")
                    return abs(bundle["empirical_coverage"] - nominal_coverage) <= 0.02
            """
        },
    )
    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["findings"] == 0
    assert result.evidence["files_walked"] == 1
