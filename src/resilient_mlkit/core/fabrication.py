"""Static detection of fabricated defaults for measured quantities (R10).

The defect class this module exists to catch, stated once:

    A measured quantity is given a PLAUSIBLE NUMERIC DEFAULT when its real
    input is absent, and that default then satisfies the gate that consumes
    it. The gate reports PASS having measured nothing.

Three separate hand sweeps across this portfolio each found instances the
previous sweep had missed. Hand-auditing does not converge on this pattern,
because every instance looks locally reasonable: ``max_smd = max(smds.values())
if smds else 0.0`` reads as defensive programming right up until you notice
that 0.0 is *perfect covariate balance* and that the empty dict is the branch
which actually runs. This module makes the sweep mechanical.

Design, in order of importance:

**Precision over recall.** A check that cries wolf gets disabled, and a
disabled check is worse than no check because it still looks like coverage.
The rule is therefore built as an ALLOWLIST of measured-quantity names rather
than a denylist of suspicious literals. ``timeout``, ``batch_size``,
``learning_rate``, ``n_retries`` and ``seed`` are not in the vocabulary, so a
default for any of them can never fire this check however it is written.
Configuration defaults are not defects; measured quantities are.

**A default alone is not a defect.** ``rmse = d.get("rmse", 0.0)`` inside a
plotting helper harms nobody. It becomes a defect when the value reaches a
gate, a metric or a report -- somewhere a reader will take it for a
measurement. Every candidate must therefore also be shown to reach a sink.

**Names, not values.** The rule keys on the NAME of the quantity being
defaulted, because the name is what encodes "this is a measurement". The
literal carries no information on its own: 0.0 is a perfect RMSE and a
meaningless timeout; 1.0 is a perfect p-value and a sensible scale factor.

What this module does NOT claim to catch, stated so that a green R10 is not
read as more than it is: substitution of one real array for another (scoring
a baseline ensemble against itself), a challenger arm manufactured by scaling
the champion's predictions, and uncertainty bands manufactured by multiplying
a point estimate. Those are the same defect class but they leave no numeric
literal behind, and a rule broad enough to catch them would flag ordinary
code. They remain a matter for review.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

#: The two AST nodes that carry a signature. Several scanners need
#: ``.args``/``.body``/a docstring, which ``ast.AST`` does not promise, and
#: annotating them as bare AST hid that from the type checker.
_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
#: Statements ``_scan_guarded_statement`` is dispatched for, from ``scan()``.
_StatementNode = ast.Assign | ast.AnnAssign | ast.Return


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: Tokens naming a MEASURED quantity -- something a model, an estimator or a
#: statistical test produces. Every entry was drawn from a defect actually
#: found in this portfolio, or is the direct sibling of one.
#:
#: Names are split on non-alphanumerics and on camelCase boundaries, then
#: lowercased; a symbol matches when ANY token is in this set. Nothing generic
#: enough to name a knob belongs here -- there is deliberately no "rate", no
#: "size", no "count", no "threshold" and no "alpha".
MEASURED_TOKENS: frozenset[str] = frozenset(
    {
        # -- inferential statistics -------------------------------------
        "pvalue", "pvalues", "pval", "pvals", "tstat", "fstat", "tstatistic",
        "fstatistic", "zscore", "chi2", "significance", "significant",
        "pretrend", "pretrends", "placebo", "wald", "ftest",
        # -- error metrics ----------------------------------------------
        "rmse", "mae", "mape", "mse", "smape", "wape", "msle", "rmsle",
        "crps", "crpss", "brier", "logloss", "nll", "mad", "medae",
        "loss", "losses",
        # -- skill / agreement ------------------------------------------
        "r2", "rsq", "rsquared", "auc", "auroc", "auprc", "aupr", "f1",
        "iou", "jaccard", "dice", "csi", "pod", "far", "kge", "nse",
        "precision", "recall", "sensitivity", "specificity", "accuracy",
        "skill", "correlation", "pearson", "spearman", "kendall",
        "concordance", "hitrate", "score", "scores",
        # -- calibration / uncertainty ----------------------------------
        "coverage", "calibration", "picp", "pit", "sharpness", "pinball",
        "quantileloss", "miscoverage", "ece", "prob", "probs",
        "probability", "probabilities",
        # -- causal / effect estimates ----------------------------------
        "smd", "att", "atet", "ate", "cate", "itt", "effect", "effectsize",
        "uplift", "elasticity", "estimand", "counterfactual", "disparity",
        "balance", "parallel", "confound", "rr", "relativerisk", "odds",
        # -- dispersion and intervals -----------------------------------
        "stderr", "stderror", "se", "sem", "cilow", "cihigh", "cilower",
        "ciupper", "ciwidth",
        # -- portfolio-specific gated figures ---------------------------
        "avoidedloss", "expectedloss", "basisrisk", "improvement",
        "regression", "attenuation", "exceedance", "latency",
    }
)

#: Tokens that make a symbol CONFIGURATION and veto a match outright. None of
#: these ever names something a model measured.
HARD_CONFIG_TOKENS: frozenset[str] = frozenset(
    {
        "seed", "timeout", "retry", "retries", "batch", "epoch", "epochs",
        "lr", "learning", "momentum", "decay", "dropout", "patience",
        "workers", "worker", "port", "host", "chunk", "buffer", "dpi",
        "verbosity", "verbose", "config", "cfg", "conf", "param", "params",
        "setting", "settings", "opt", "opts", "option", "options",
        "hyperparam", "hyperparams", "kwargs", "argv", "env", "discount",
        # Estimator STRUCTURE, not estimator output. ``PanelOLS(y, x,
        # entity_effects=True, time_effects=True)`` was the single largest
        # false-positive family in the first measured run: "effects" there
        # names a fixed-effects specification, not an effect size.
        "entity", "time", "unit", "cluster", "engine", "solver", "method",
        "mode", "kind", "type", "flag", "enable", "use", "include",
        # Counts of things, which are not the measurement made over them.
        "pixels", "cells", "rows", "records", "samples", "obs", "nobs",
    }
)

#: Tokens that usually mark a THRESHOLD a human chose rather than a figure a
#: model produced. These veto only in a configuration context (a parameter
#: default, a module-level constant, or a value read out of a config object),
#: because ``min_r2`` read from a config file is a knob while ``max_smd``
#: computed from a covariate table is a measurement, and the two are
#: indistinguishable by name alone.
THRESHOLD_TOKENS: frozenset[str] = frozenset(
    {
        "min", "max", "threshold", "thresh", "target", "required", "tol",
        "tolerance", "floor", "ceiling", "cap", "limit", "budget", "bound",
        "default", "nominal", "allowed", "acceptable", "warn", "alert",
        "abort", "prior", "weight", "alpha", "beta", "drop", "horizon",
        "window", "period", "years", "months", "days", "hours", "n", "num",
        "count", "size", "scale", "factor", "step", "steps", "iter", "iters",
        # Known-answer constants: a published or literature figure written
        # into the code is evidence, not a fabrication -- provided it is
        # named as such.
        "true", "truth", "expected", "reference", "published", "literature",
        "benchmark", "known", "analytic", "theoretical",
    }
)

#: Markers of an EXTENSIVE quantity -- a monetary total, a sum over assets, a
#: net present value. These were the largest residual false-positive family:
#: an exposure with no assets really does carry zero expected annual loss, and
#: an empty portfolio really does have zero NPV. Zero is the arithmetic answer
#: there, not a stand-in for one. An INTENSIVE estimate over an empty set --
#: a p-value, a coverage, an effect size -- has no such answer, which is why
#: this veto is scoped to the extensive names and to zero literals only.
EXTENSIVE_TOKENS: frozenset[str] = frozenset(
    {
        "usd", "eur", "gbp", "dollars", "total", "totals", "sum", "aggregate",
        "cumulative", "npv", "capex", "opex", "aal", "eal", "revenue",
        "premium", "payout", "notional", "annual", "portfolio",
    }
)

#: Names of containers whose members are, by construction, reported.
_SINK_CONTAINERS = re.compile(
    r"(?i)\b(metrics?|results?|report|reports|summary|evidence|payload|"
    r"card|scorecard|row|rows|entry|entries|record|records|output|outputs|"
    r"gate|gates|verdict|findings|checks?)\b"
)

#: Calls whose arguments become published figures.
_SINK_CALLS = re.compile(
    r"(?i)(log_metrics?|set_metrics?|record_metrics?|write_report|to_markdown|"
    r"to_dict|to_json|report|summar|publish|emit|dump|render|append)"
)

#: Functions whose RETURN value is consumed as a gate, a metric or a report.
#: Deliberately excludes ``run_`` and ``main``: those return exit codes and
#: orchestrate, they do not produce figures, and including them made every
#: ``return 0`` in a CLI look like a fabricated metric.
_SINK_FUNCS = re.compile(
    r"(?i)(^|_)(gate|check|validate|verify|assert|evaluate|score|"
    r"benchmark|metric|metrics|report|summary|summarise|summarize|compute|"
    r"calc|calculate|estimate|calibrat|backtest|promote|audit)"
)

#: Functions that ARE gates: their return value is a verdict, so a literal
#: ``True`` returned from a branch that measured nothing is a fabricated pass.
#: Narrower than ``_SINK_FUNCS`` on purpose -- ``compute_`` and ``run_`` are
#: not verdicts.
_GATE_FUNCS = re.compile(r"(?i)(^|_)(gate|check|validate|verify|assert)")

#: Code that declares itself a generator of made-up data. Drawing from an RNG
#: there is the stated purpose, not a fabrication.
#: Bare "synth" is deliberately absent: ``synthdid`` is synthetic
#: difference-in-differences, a real estimator, and matching it hid a genuine
#: defect (resilient-fray src/analysis/synthdid.py:63).
_SYNTHETIC_NAMES = re.compile(
    r"(?i)(synthetic|simulate|simulation|fixture|mock|stub|demo|"
    r"example|sample_data|dummy|fake|toy|placeholder|seed_data|make_)"
)

#: Names holding a pass/fail verdict. A fabricated value reaching one of these
#: is the defect in its purest form.
_VERDICT_NAMES = re.compile(
    r"(?i)(^|_)(pass|passed|passes|ok|okay|valid|gate|green|promote|"
    r"promotable|approved|accept|accepted|significant|allpass|nocritical)"
)

#: Attribute names that draw a pseudo-random number.
_RNG_DRAWS = frozenset(
    {
        "normal", "uniform", "random", "random_sample", "randn", "rand",
        "randint", "standard_normal", "lognormal", "poisson", "binomial",
        "gamma", "beta", "exponential", "choice", "gauss", "normalvariate",
        "triangular", "weibull", "laplace",
    }
)
_RNG_ROOTS = frozenset({"random", "rng", "npr", "default_rng", "generator", "np", "torch"})

#: Metrics where a LARGER value is the better one, so a large default is what
#: satisfies the gate. p-values sit here: a large p is "no evidence against
#: the null", which is exactly what a parallel-trends gate wants to see.
_HIGHER_IS_BETTER = frozenset(
    {
        "r2", "rsq", "rsquared", "auc", "auroc", "auprc", "aupr", "f1",
        "iou", "jaccard", "dice", "csi", "pod", "kge", "nse", "precision",
        "recall", "sensitivity", "specificity", "accuracy", "skill",
        "correlation", "pearson", "spearman", "kendall", "concordance",
        "hitrate", "coverage", "picp", "score", "scores", "pvalue", "pvalues",
        "pval", "pvals", "significance", "improvement", "uplift", "parallel",
        "balance", "calibration", "prob", "probs", "probability",
        "probabilities", "attenuation",
    }
)

#: Metrics where a SMALLER value is the better one; here a near-zero default
#: is the perfect score that satisfies the gate.
_LOWER_IS_BETTER = frozenset(
    {
        "rmse", "mae", "mape", "mse", "smape", "wape", "msle", "rmsle",
        "crps", "brier", "logloss", "nll", "mad", "medae", "loss", "losses",
        "smd", "disparity", "miscoverage", "ece", "far", "pinball",
        "quantileloss", "sharpness", "avoidedloss", "expectedloss",
        "basisrisk", "regression", "latency", "exceedance",
    }
)


def satisfies_a_gate(symbol: str, literal: str) -> bool:
    """True when this default is the value that would PASS the gate.

    The defect is not "a measured name has a default". It is "a measured name
    has a default *that satisfies the gate consuming it*". A CSI that returns
    0.0 on an empty comparison is wrong, but it fails every CSI gate and so
    reports no confidence it did not earn; a CSI that returns 1.0 reports a
    perfect model. Only the second one is this defect class, and separating
    them is most of what keeps R10 quiet enough to be read.

    Polarity is read off the name. Unknown polarity is treated as dangerous,
    because ``se = 0.0`` yields a zero-width confidence interval that excludes
    zero -- the exact shape of a hard-stop gate, manufactured from nothing.
    """
    if literal == "True":
        return True
    if literal == "False":
        return False
    try:
        value = float(literal.split(" / ")[0])
    except ValueError:
        return True  # non-numeric shapes (RNG draws) are always suspect
    tokens = set(tokenise(symbol))
    if tokens & {"auc", "auroc", "auprc", "aupr"}:
        return value > 0.5  # 0.5 IS the no-skill point; it passes nothing
    if tokens & _HIGHER_IS_BETTER:
        return value >= 0.5
    if tokens & _LOWER_IS_BETTER:
        # Small errors pass an error gate; a sentinel like 999.0 does not.
        return abs(value) < 1.0
    return True


_TOKEN_SPLIT = re.compile(r"[^0-9a-zA-Z]+")
_CAMEL_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])")


def tokenise(name: str) -> list[str]:
    """Split an identifier into lowercase tokens.

    ``pre_trend_pvalue`` -> ``[pre, trend, pvalue]``; ``maxSMD`` ->
    ``[max, smd]``; ``r2_oos`` -> ``[r2, oos]``.

    Digits stay attached to the letters preceding them, so ``r2``, ``f1`` and
    ``chi2`` survive as single tokens instead of degrading into a bare ``r``
    that would match half the identifiers in a codebase.
    """
    parts: list[str] = []
    for chunk in _TOKEN_SPLIT.split(name):
        if not chunk:
            continue
        for piece in _CAMEL_SPLIT.split(chunk):
            if piece:
                parts.append(piece.lower())
    # Adjacent pairs are joined as well, because the portfolio writes the same
    # quantity both ways: ``pretrend_pvalue`` is one token but ``p_value`` is
    # two, and ``std_err``, ``ci_low``, ``effect_size`` and ``r_squared`` all
    # only become recognisable once rejoined.
    parts.extend(a + b for a, b in zip(parts, parts[1:]))
    # Depluralise, so that ``scores``, ``probs`` and ``rrs`` reach the same
    # vocabulary entry as their singulars.
    parts.extend(p[:-1] for p in list(parts) if len(p) > 2 and p.endswith("s"))
    return parts


def is_measured_name(name: str, *, config_context: bool = False) -> bool:
    """True when ``name`` denotes a measured quantity rather than a knob.

    ``config_context`` marks sites where a threshold would legitimately live
    (a parameter default, a module constant, a value read from a config
    mapping); there the threshold vocabulary vetoes as well.
    """
    tokens = set(tokenise(name))
    if not tokens:
        return False
    if HARD_CONFIG_TOKENS & tokens:
        return False
    if config_context and THRESHOLD_TOKENS & tokens:
        return False
    return bool(MEASURED_TOKENS & tokens)


def _is_extensive(name: str) -> bool:
    return bool(EXTENSIVE_TOKENS & set(tokenise(name)))


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One site where a measured quantity takes a fabricated value."""

    path: str
    line: int
    symbol: str
    shape: str
    literal: str
    sink: str
    snippet: str
    #: SATISFIES_GATE when the fabricated value is the one that PASSES the
    #: gate consuming it -- the full defect. PUBLISHES_UNMEASURED when the
    #: value would fail its gate but is still emitted as a measurement, which
    #: misreports rather than falsely reassures. Both are defects; only the
    #: first can turn a red gate green, so they are ranked apart.
    severity: str = "SATISFIES_GATE"

    def render(self) -> str:
        return (
            f"{self.path}:{self.line}  {self.symbol} <- {self.literal} "
            f"[{self.severity}; {self.shape}; {self.sink}]\n      {self.snippet}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "symbol": self.symbol,
            "shape": self.shape,
            "literal": self.literal,
            "sink": self.sink,
            "snippet": self.snippet,
            "severity": self.severity,
        }


# ---------------------------------------------------------------------------
# Literal and expression classification
# ---------------------------------------------------------------------------


def _numeric_literal(node: ast.AST | None) -> str | None:
    """Render ``node`` when it is a plausible number, else None.

    NaN and infinity are deliberately NOT fabricated defaults: NaN is one of
    the two correct repairs (the other being an exception), because it fails
    every comparison and so cannot satisfy a gate. ``None`` likewise.
    Booleans ARE included -- ``parallel_trends_ok = True`` in a branch where
    no test ran is the same defect wearing a different type.
    """
    if node is None:
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _numeric_literal(node.operand)
        if inner is None:
            return None
        return "-" + inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            # ``False`` is not a fabrication: it withholds a pass. Flagging it
            # meant flagging the REPAIRS -- ``parallel_trends_ok=False`` beside
            # an unmeasured_reason, ``checks["rmse"] = False``. A rule that
            # fires on the fix is worse than no rule.
            return "True" if node.value else None
        if isinstance(node.value, (int, float)):
            value = float(node.value)
            if value != value or value in (float("inf"), float("-inf")):
                return None
            if value != 0.0 and abs(value) < 1e-4:
                # 1e-6, 1e-9 and friends are divide-by-zero guards, not
                # plausible figures. Nobody reads ``mad = 1e-6`` as a measured
                # median absolute deviation.
                return None
            return repr(node.value)
    return None


def _dotted(node: ast.AST) -> list[str]:
    """Attribute/Name chain as a list of lowercase parts."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr.lower())
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id.lower())
    elif isinstance(current, ast.Call):
        parts.extend(_dotted(current.func))
    return parts


def _is_random_draw(node: ast.AST) -> str | None:
    """Render the RNG call when ``node`` manufactures a figure from noise."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        chain = _dotted(sub.func)
        if not chain:
            continue
        draw = chain[0]
        if draw in _RNG_DRAWS and (set(chain[1:]) & _RNG_ROOTS or draw == "random"):
            return ".".join(reversed(chain)) + "(...)"
    return None


_AGGREGATES = frozenset({"sum", "nansum", "len", "count", "size", "total", "nnz"})


def _is_aggregate(node: ast.AST) -> bool:
    """True when the displaced computation is a sum or a count."""
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        return name in _AGGREGATES
    return False


def _mentions_size(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "len":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in {"size", "shape", "sum", "count"}:
            return True
        if isinstance(sub, ast.Name) and (sub.id.startswith("n_") or sub.id in {"n", "count"}):
            return True
    return False


_ABSENCE_CALLS = {"exists", "is_file", "is_dir", "isfile", "isdir", "empty", "any"}


def _is_absence_test(node: ast.AST) -> bool:
    """True when ``node`` tests for the ABSENCE of the real input.

    This is what separates "no measurement was taken" from an ordinary
    business branch. ``if not path.exists()``, ``if x is None``,
    ``if len(folds) == 0``, ``if len(responses) < 30``, ``if denominator ==
    0.0`` and ``if champ_rmse < 1e-10`` all say the same thing: the input this
    figure was to be computed from is not here, or is degenerate.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return True
    if isinstance(node, ast.Compare):
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, ast.Is) and isinstance(comparator, ast.Constant) \
                    and comparator.value is None:
                return True
            if not isinstance(comparator, ast.Constant) or isinstance(comparator.value, bool) \
                    or not isinstance(comparator.value, (int, float)):
                continue
            if isinstance(op, (ast.Eq, ast.Lt, ast.LtE)):
                if isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Mod):
                    continue  # `epoch % 10 == 0` is a schedule, not emptiness
                if _mentions_size(node.left):
                    return True
                # A comparison against zero or an epsilon is a degeneracy
                # test: "there is nothing here to divide by / to score".
                if abs(float(comparator.value)) < 1e-6:
                    return True
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in _ABSENCE_CALLS:
            return True
    if isinstance(node, ast.BoolOp):
        return any(_is_absence_test(v) for v in node.values)
    return False


_CONFIG_SOURCES = re.compile(
    r"(?i)\b(config|cfg|conf|params?|settings?|options?|opts?|args|kwargs|"
    r"env|environ|defaults?|toml|yaml|ini)\b"
)


def _reads_config(node: ast.AST) -> bool:
    """True when the non-default half of the expression reads configuration."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and _CONFIG_SOURCES.search(sub.id):
            return True
        if isinstance(sub, ast.Attribute) and _CONFIG_SOURCES.search(sub.attr):
            return True
    return False


# ---------------------------------------------------------------------------
# The scanner
# ---------------------------------------------------------------------------


_UNMEASURED_MARKERS = re.compile(
    r"(?i)(unmeasured|not_measured|na_reason|_status$|^status$|"
    r"reason|skipped|unavailable|undefined)"
)


def _declares_itself_unmeasured(value: ast.AST) -> bool:
    """True when a constructed result already marks itself as not measured."""
    if not isinstance(value, (ast.Call, ast.Dict)):
        return False
    names: list[str] = []
    values: list[ast.AST] = []
    if isinstance(value, ast.Call):
        names = [kw.arg for kw in value.keywords if kw.arg]
        values = [kw.value for kw in value.keywords]
    else:
        names = [
            k.value for k in value.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        values = list(value.values)
    if any(_UNMEASURED_MARKERS.search(n) for n in names):
        return True
    for sub_value in values:
        for sub in ast.walk(sub_value):
            if isinstance(sub, ast.Attribute) and sub.attr in {"nan", "inf", "NaN", "NAN"}:
                return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                    and sub.func.id == "float" and sub.args \
                    and isinstance(sub.args[0], ast.Constant) \
                    and str(sub.args[0].value).strip().lower().lstrip("+-") in {"nan", "inf", "infinity"}:
                return True
    return False


@dataclass
class _Candidate:
    node: ast.AST
    #: Names considered when deciding whether this IS a measurement.
    symbols: list[str]
    shape: str
    literal: str
    config_context: bool = False
    #: Names considered when looking for the sink. Usually the same list, but
    #: an explicit ``.get("pit_chi2_p", 1.0)`` names the quantity by its key
    #: while the threshold comparison downstream uses the local ``pit_p``, so
    #: the two questions need different alias sets.
    sink_symbols: list[str] | None = None


class _ModuleScanner:
    def __init__(self, path: str, source: str, tree: ast.Module) -> None:
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        self.parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[id(child)] = parent
        self._sink_cache: dict[int, dict[str, str]] = {}
        self._findings: list[Finding] = []
        self._seen: set[tuple[int, int, str]] = set()

    # -- tree helpers ------------------------------------------------------

    def snippet(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 0)
        if 1 <= line <= len(self.lines):
            return self.lines[line - 1].strip()[:170]
        return ""

    def ancestors(self, node: ast.AST) -> Iterator[ast.AST]:
        current = self.parents.get(id(node))
        while current is not None:
            yield current
            current = self.parents.get(id(current))

    def enclosing_function(self, node: ast.AST) -> ast.AST:
        for parent in self.ancestors(node):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return parent
        return self.tree

    def at_module_level(self, node: ast.AST) -> bool:
        return self.enclosing_function(node) is self.tree

    # -- sinks -------------------------------------------------------------

    def sinks_of(self, node: ast.AST) -> dict[str, str]:
        scope = self.enclosing_function(node)
        key = id(scope)
        if key not in self._sink_cache:
            self._sink_cache[key] = self._build_sinks(scope)
        return self._sink_cache[key]

    def _build_sinks(self, scope: ast.AST) -> dict[str, str]:
        """Symbols in ``scope`` that reach a gate, a metric or a report.

        A symbol qualifies when it is compared against something (a gate), is
        stored under a reported key or into a reported container (a metric),
        is handed to a reporting call, is returned from a function whose name
        says it produces a figure, or is passed as a keyword argument naming a
        measured quantity (a result object being constructed).
        """
        sinks: dict[str, str] = {}
        scope_name = getattr(scope, "name", "<module>")
        returns_figure = bool(_SINK_FUNCS.search(scope_name)) or is_measured_name(scope_name)

        def note(sym: str, why: str) -> None:
            if sym and sym not in sinks:
                sinks[sym] = why

        def names_in(node: ast.AST) -> set[str]:
            out: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    out.add(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.add(sub.value)
            return out

        for sub in ast.walk(scope):
            if sub is not scope and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # a nested function's sinks are its own

            if isinstance(sub, ast.Compare):
                for side in [sub.left, *sub.comparators]:
                    for sym in names_in(side):
                        note(sym, "compared against a threshold")

            elif isinstance(sub, ast.Dict):
                verdict_sibling = any(
                    isinstance(k, ast.Constant) and isinstance(k.value, str)
                    and _VERDICT_NAMES.search(k.value)
                    for k in sub.keys if k is not None
                )
                why = (
                    "reported in a dict carrying a pass/fail verdict"
                    if verdict_sibling else "reported under a metric key"
                )
                for key, value in zip(sub.keys, sub.values):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        note(key.value, why)
                    for sym in names_in(value):
                        note(sym, why)

            elif isinstance(sub, ast.Assign):
                for target in sub.targets:
                    if isinstance(target, ast.Subscript):
                        holders = names_in(target.value)
                        if any(_SINK_CONTAINERS.search(h) for h in holders):
                            slot = target.slice
                            if isinstance(slot, ast.Constant) and isinstance(slot.value, str):
                                note(slot.value, "stored into a metrics/report mapping")
                            for sym in names_in(sub.value):
                                note(sym, "stored into a metrics/report mapping")
                    elif isinstance(target, (ast.Name, ast.Attribute)):
                        tname = target.id if isinstance(target, ast.Name) else target.attr
                        if _VERDICT_NAMES.search(tname):
                            for sym in names_in(sub.value):
                                note(sym, f"decides the verdict '{tname}'")

            elif isinstance(sub, ast.Call):
                func = sub.func
                fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if fname and _SINK_CALLS.search(fname):
                    for arg in list(sub.args) + [k.value for k in sub.keywords]:
                        for sym in names_in(arg):
                            note(sym, f"passed to {fname}()")
                for kw in sub.keywords:
                    if kw.arg and (is_measured_name(kw.arg) or _VERDICT_NAMES.search(kw.arg)):
                        why = f"passed as {fname or 'result'}({kw.arg}=...)"
                        note(kw.arg, why)
                        for sym in names_in(kw.value):
                            note(sym, why)

            elif isinstance(sub, ast.Return) and sub.value is not None and returns_figure:
                for sym in names_in(sub.value):
                    note(sym, f"returned from {scope_name}()")

        return sinks

    def _direct_sink(self, node: ast.AST) -> str | None:
        """A sink the expression sits inside, with no intermediate variable."""
        for parent in self.ancestors(node):
            if isinstance(parent, ast.Compare):
                return "compared against a threshold"
            if isinstance(parent, ast.Assign):
                for target in parent.targets:
                    if isinstance(target, ast.Subscript):
                        holder = target.value
                        name = holder.attr if isinstance(holder, ast.Attribute) \
                            else getattr(holder, "id", "")
                        if name and _SINK_CONTAINERS.search(name):
                            return "stored into a metrics/report mapping"
            if isinstance(parent, ast.Dict):
                if any(
                    isinstance(k, ast.Constant) and isinstance(k.value, str)
                    and _VERDICT_NAMES.search(k.value)
                    for k in parent.keys if k is not None
                ):
                    return "reported in a dict carrying a pass/fail verdict"
                return "reported under a metric key"
            if isinstance(parent, ast.keyword) and parent.arg and (
                is_measured_name(parent.arg) or _VERDICT_NAMES.search(parent.arg)
            ):
                return f"passed as {parent.arg}=..."
            if isinstance(parent, ast.Call):
                func = parent.func
                fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if fname and _SINK_CALLS.search(fname):
                    return f"passed to {fname}()"
            if isinstance(parent, ast.Return):
                scope = self.enclosing_function(parent)
                name = getattr(scope, "name", "")
                if name and (_SINK_FUNCS.search(name) or is_measured_name(name)):
                    return f"returned from {name}()"
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                return None
        return None

    # -- symbol resolution -------------------------------------------------

    def _context_symbols(self, node: ast.AST) -> list[str]:
        """Names the expression's value will be known by, most specific first."""
        out: list[str] = []
        current: ast.AST = node
        for parent in self.ancestors(node):
            if isinstance(parent, ast.Assign) and parent.targets:
                target = parent.targets[0]
                if isinstance(target, ast.Name):
                    out.append(target.id)
                elif isinstance(target, ast.Attribute):
                    out.append(target.attr)
                elif isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) \
                        and isinstance(target.slice.value, str):
                    out.append(target.slice.value)
            elif isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
                out.append(parent.target.id)
            elif isinstance(parent, ast.keyword) and parent.arg:
                out.append(parent.arg)
            elif isinstance(parent, ast.Dict):
                for key, value in zip(parent.keys, parent.values):
                    if value is current and isinstance(key, ast.Constant) \
                            and isinstance(key.value, str):
                        out.append(key.value)
            elif isinstance(parent, ast.Return):
                name = getattr(self.enclosing_function(parent), "name", "")
                if name:
                    out.append(name)
            elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                break
            current = parent
        return out

    @staticmethod
    def _producer_symbols(node: ast.AST | None) -> list[str]:
        """Names of whatever WOULD have produced the figure.

        ``self.compute_expected_loss(ep) if ep else 0.05`` is anonymous at the
        assignment (``el = ...``) but the call it replaces names the quantity
        exactly. Reading the displaced producer is often the only way to learn
        what the literal is standing in for.
        """
        if node is None:
            return []
        out: list[str] = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute):
                    out.append(func.attr)
                elif isinstance(func, ast.Name):
                    out.append(func.id)
            elif isinstance(sub, ast.Attribute):
                out.append(sub.attr)
        return out

    # -- emission ----------------------------------------------------------

    def _emit(self, cand: _Candidate) -> None:
        """Report the candidate when it is BOTH a measurement and reaches a sink.

        The two tests run over the candidate's whole alias list rather than
        over one chosen name, because the name that says "measurement" and the
        name that reaches the sink are often different:
        ``el = self.compute_expected_loss(ep) if ep else 0.05`` is named for
        its producer and sunk under ``el``. Both halves are still required.
        """
        measured = [
            s for s in cand.symbols
            if s and is_measured_name(s, config_context=cand.config_context)
        ]
        if not measured:
            return
        if self._in_synthetic_context(cand.node):
            # A file or function that declares itself a demo, a fixture or a
            # synthetic generator is not claiming to have measured anything.
            # ``demo_end_to_end.py`` formatting ``payload.get(k, 0)`` into a
            # markdown line is not the defect this check is looking for.
            return
        if cand.literal in ("0", "0.0", "-0.0") and _is_extensive(measured[0]):
            return
        sinks = self.sinks_of(cand.node)
        aliases = cand.sink_symbols if cand.sink_symbols is not None else cand.symbols
        sink = next((sinks[s] for s in aliases if s in sinks), None)
        if sink is None:
            sink = self._direct_sink(cand.node)
        if sink is None:
            return
        symbol = measured[0]
        line = getattr(cand.node, "lineno", 0)
        col = getattr(cand.node, "col_offset", 0)
        key = (line, col, symbol)
        if key in self._seen:
            return
        self._seen.add(key)
        self._findings.append(
            Finding(
                path=self.path,
                line=line,
                symbol=symbol,
                shape=cand.shape,
                literal=cand.literal,
                sink=sink,
                snippet=self.snippet(cand.node),
                severity=(
                    "SATISFIES_GATE" if satisfies_a_gate(symbol, cand.literal)
                    else "PUBLISHES_UNMEASURED"
                ),
            )
        )

    # -- the walk ----------------------------------------------------------

    def scan(self) -> list[Finding]:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                self._scan_call(node)
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                self._scan_or(node)
            elif isinstance(node, ast.IfExp):
                self._scan_ifexp(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_param_defaults(node)
                self._scan_metric_literal_return(node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)):
                self._scan_guarded_statement(node)
                self._scan_random_draw(node)
                if isinstance(node, ast.Return) and node.value is not None:
                    self._scan_gate_pass_literal(node)
        self._findings.sort(key=lambda f: (f.path, f.line, f.symbol))
        return self._findings

    # -- shapes ------------------------------------------------------------

    def _scan_call(self, node: ast.Call) -> None:
        func = node.func
        # d.get("key", <num>)
        if isinstance(func, ast.Attribute) and func.attr == "get" and len(node.args) == 2:
            literal = _numeric_literal(node.args[1])
            if literal is None:
                return
            key = node.args[0]
            symbols: list[str] = []
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                # An explicit literal key names the quantity best, so it goes
                # first. The assignment target still follows it: surge's
                # ``adcirc_rmse = avg_rmse.get("adcirc", 0.30)`` invented a
                # competitor's score under a key that says nothing.
                symbols.append(key.value)
            symbols.extend(self._context_symbols(node))
            symbols.extend(self._producer_symbols(key))
            self._emit(_Candidate(
                node, symbols, "dict.get default", literal,
                config_context=_reads_config(func.value) or self.at_module_level(node),
                sink_symbols=symbols + self._context_symbols(node),
            ))
            return
        # getattr(obj, "attr", <num>)
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) == 3:
            literal = _numeric_literal(node.args[2])
            if literal is None:
                return
            key = node.args[1]
            symbols = []
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                symbols.append(key.value)
            symbols.extend(self._context_symbols(node))
            self._emit(_Candidate(
                node, symbols, "getattr default", literal,
                config_context=_reads_config(node.args[0]) or self.at_module_level(node),
            ))

    def _scan_or(self, node: ast.BoolOp) -> None:
        literal = _numeric_literal(node.values[-1])
        if literal is not None:
            symbols = self._context_symbols(node) + self._producer_symbols(node.values[0])
            self._emit(_Candidate(
                node, symbols, "`or` fallback", literal,
                config_context=_reads_config(node.values[0]) or self.at_module_level(node),
            ))
            return
        # `x is None or x > threshold` -- absence adjudicated as a pass.
        if not any(
            isinstance(v, ast.Compare)
            and any(isinstance(o, ast.Is) for o in v.ops)
            and any(isinstance(c, ast.Constant) and c.value is None for c in v.comparators)
            for v in node.values
        ):
            return
        symbols = self._context_symbols(node)
        for symbol in symbols[:1]:
            if _VERDICT_NAMES.search(symbol) or is_measured_name(symbol):
                self._emit(_Candidate(
                    node, [symbol], "absence adjudicated as a pass", "True",
                ))
                return

    def _scan_ifexp(self, node: ast.IfExp) -> None:
        """``<measured> = <computation> if <input present> else <literal>``.

        No absence-test requirement here: the vocabulary already restricts
        this to measured quantities, and requiring a recognisable absence test
        loses ``0.50 if n_periods > 2 else None`` and ``0.0 if mask.sum() == 0
        else ...`` -- both real defects from this wave.
        """
        body_lit = _numeric_literal(node.body)
        else_lit = _numeric_literal(node.orelse)
        if body_lit is None and else_lit is None:
            return
        if body_lit is not None and else_lit is not None:
            # Both arms are literals: nothing is computed on either path.
            # ``correlation = 1.0 if rmse <= 1e-12 else 0.0`` is a verdict on a
            # degenerate series, not a correlation. Restricted to degeneracy
            # tests, because ``1.0 if score > q else 0.0`` is a perfectly
            # correct indicator function and must not be flagged.
            if not _is_absence_test(node.test):
                return
            symbols = self._context_symbols(node)
            self._emit(_Candidate(
                node, symbols, "both ternary arms are literals",
                f"{body_lit} / {else_lit}",
                config_context=self.at_module_level(node),
            ))
            return
        literal = body_lit if body_lit is not None else else_lit
        producer = node.orelse if body_lit is not None else node.body
        if literal in ("0", "0.0", "-0.0") and _is_aggregate(producer):
            # ``total = sum(losses) if losses else 0.0`` is arithmetic, not
            # fabrication: the sum of an empty collection is zero.
            return
        symbols = self._context_symbols(node) + self._producer_symbols(producer)
        self._emit(_Candidate(
            node, symbols, "ternary fallback", literal or "",
            config_context=_reads_config(producer) or self.at_module_level(node),
        ))

    def _scan_param_defaults(self, fn: _FunctionNode) -> None:
        """``def gate(champion_mape=0.20, challenger_mape=0.15)``.

        A caller omitting the argument gets a figure nobody measured, and the
        gate then compares two invented numbers.

        Reported only when the parameter reaches a GATE sink -- compared
        against something, or deciding a verdict. A parameter default is the
        canonical home of a threshold, so anything weaker than "this number
        decides a pass" produces more noise than signal: it flagged
        ``n_placebo=100``, ``coverage_horizon_years=1`` and published
        known-answer constants, none of which are defects.
        """
        args = fn.args
        pairs: list[tuple[ast.arg, ast.expr]] = []
        positional = list(args.posonlyargs) + list(args.args)
        if args.defaults:
            for arg, default in zip(positional[len(positional) - len(args.defaults):], args.defaults):
                pairs.append((arg, default))
        for arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
            # kw_defaults holds None for keyword-only args with no default --
            # a hole in the list, not a `None` literal default.
            if kw_default is not None:
                pairs.append((arg, kw_default))
        if not pairs or not fn.body:
            return
        sinks = self._build_sinks(fn)
        for arg, default in pairs:
            literal = _numeric_literal(default)
            if literal is None:
                continue
            # A parameter default IS the canonical home of a threshold, so the
            # threshold vocabulary vetoes here.
            if not is_measured_name(arg.arg, config_context=True):
                continue
            if not satisfies_a_gate(arg.arg, literal):
                continue
            sink = sinks.get(arg.arg)
            if sink is None or not (
                sink.startswith("compared against") or sink.startswith("decides the verdict")
            ):
                continue
            line = getattr(default, "lineno", getattr(fn, "lineno", 0))
            key = (line, getattr(default, "col_offset", 0), arg.arg)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._findings.append(Finding(
                path=self.path, line=line, symbol=arg.arg, shape="parameter default",
                literal=literal, sink=sink, snippet=self.snippet(arg),
            ))

    def _scan_metric_literal_return(self, fn: _FunctionNode) -> None:
        """``def compute_csi(...): ... return 1.0``.

        Four independent CSI implementations in this portfolio returned a
        perfect 1.0 on an empty comparison. The function's own NAME is the
        measured quantity, so a literal returned from its degenerate branch is
        a figure nobody computed.

        Three restrictions keep this precise: the returned literal must be a
        float (an ``int`` return is an exit code, not a metric), the return
        must sit under an absence or degeneracy guard (otherwise a piecewise
        lookup table reads as a defect), and the docstring fallback matches
        only an uppercase acronym.
        """
        name = getattr(fn, "name", "")
        if not is_measured_name(name, config_context=True) \
                and not self._docstring_names_a_metric(fn):
            return
        for sub in ast.walk(fn):
            if sub is not fn and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not isinstance(sub, ast.Return) or sub.value is None:
                continue
            literal = _numeric_literal(sub.value)
            if literal is None:
                continue
            if isinstance(sub.value, ast.Constant) and isinstance(sub.value.value, int) \
                    and not isinstance(sub.value.value, bool):
                continue
            if self._absence_guard(sub) is None:
                continue
            if not satisfies_a_gate(name, literal):
                continue
            line = getattr(sub, "lineno", 0)
            key = (line, getattr(sub, "col_offset", 0), name)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._findings.append(Finding(
                path=self.path, line=line, symbol=name,
                shape="metric function returns a literal", literal=literal,
                sink=f"returned from {name}()", snippet=self.snippet(sub),
            ))

    @staticmethod
    def _docstring_names_a_metric(fn: _FunctionNode) -> bool:
        """``def _critical_success_index(...): '''... (CSI) = TP/(TP+FN+FP)'''``.

        Some metric implementations spell the quantity out in the name and
        abbreviate it only in the docstring. Only an UPPERCASE acronym counts:
        matching prose would fire on every docstring containing the words
        "score", "loss" or "coverage", which is most of them.
        """
        doc = ast.get_docstring(fn) or ""
        first = doc.strip().splitlines()[0] if doc.strip() else ""
        if not first:
            return False
        for word in re.findall(r"\b[A-Z][A-Za-z0-9]{1,6}\b", first):
            if word.isupper() or re.fullmatch(r"[A-Z][a-z]?[A-Z][A-Za-z0-9]*", word):
                if word.lower() in MEASURED_TOKENS:
                    return True
        return False

    def _scan_gate_pass_literal(self, node: ast.Return) -> None:
        """A gate returning a bare ``True`` from a branch that measured nothing.

        ``if not BASELINE.is_file(): return True, float("nan"), "skipped"``
        is the whole defect class in one line: the gate's own contract says
        PASS, and the figure beside it is decoration. Restricted to functions
        whose name declares them gates, which is what makes it precise.
        """
        fn = self.enclosing_function(node)
        name = getattr(fn, "name", "")
        if not _GATE_FUNCS.search(name):
            return
        guard = self._absence_guard(node)
        if guard is None:
            return
        value = node.value
        first = value.elts[0] if isinstance(value, ast.Tuple) and value.elts else value
        if not (isinstance(first, ast.Constant) and first.value is True):
            return
        line = getattr(node, "lineno", 0)
        key = (line, getattr(node, "col_offset", 0), name)
        if key in self._seen:
            return
        self._seen.add(key)
        self._findings.append(Finding(
            path=self.path, line=line, symbol=name,
            shape=f"gate returns PASS from an {guard} branch", literal="True",
            sink=f"the return value of {name}()", snippet=self.snippet(node),
        ))

    # NOTE: an earlier revision also flagged any measured quantity assigned
    # inside an ``except`` handler ("an estimator raised and a number appeared
    # anyway"). It was removed after measurement: on the post-fix portfolio it
    # fired 17 times and the majority were the CORRECT repairs -- assignments
    # of ``"NA"``, of an unmeasured-reason string, and of
    # ``BalanceReport(passed=False)``. A rule that flags the fix is worse than
    # no rule, and it bought exactly one true positive. Substitution inside an
    # exception handler stays a matter for review, not for R10.

    def _scan_random_draw(self, node: ast.AST) -> None:
        """A measured quantity drawn from an RNG and then reported as measured."""
        if self._in_synthetic_context(node):
            return
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)) else None
        if value is None:
            return
        # Keyword arguments of a returned/assigned constructor count too.
        targets: list[tuple[list[str], ast.AST]] = []
        if isinstance(node, ast.Assign) and node.targets:
            targets.append((self._names_of_target(node.targets[0]), value))
        elif isinstance(node, ast.AnnAssign):
            targets.append((self._names_of_target(node.target), value))
        if isinstance(value, ast.Call):
            for kw in value.keywords:
                if kw.arg:
                    targets.append(([kw.arg], kw.value))
        if isinstance(value, ast.Dict):
            for key, val in zip(value.keys, value.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    targets.append(([key.value], val))
        for names, expr in targets:
            draw = _is_random_draw(expr)
            if draw is None:
                continue
            self._emit(_Candidate(node, names, "drawn from an RNG", draw))

    def _in_synthetic_context(self, node: ast.AST) -> bool:
        """True inside a function that declares itself a synthetic generator.

        ``def synthetic_calibration_data()`` drawing from an RNG is doing
        exactly what its name says. The defect is an RNG draw inside
        ``estimate_chokepoint_cate`` -- a function that claims to estimate.
        """
        for parent in self.ancestors(node):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if _SYNTHETIC_NAMES.search(parent.name):
                    return True
                for sub in ast.walk(parent):
                    if isinstance(sub, ast.Call):
                        fn = sub.func
                        fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                        if fname in {"require_test_fixture", "require_fixture"}:
                            # The route refuses to serve outside a fixture; its
                            # numbers are declared not to be measurements.
                            return True
        return bool(_SYNTHETIC_NAMES.search(Path(self.path).stem))

    @staticmethod
    def _names_of_target(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Attribute):
            return [target.attr]
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) \
                and isinstance(target.slice.value, str):
            return [target.slice.value]
        return []

    def _scan_guarded_statement(self, node: _StatementNode) -> None:
        """Literals assigned or returned where no measurement happened.

        Fires only inside an ``except`` handler or a branch guarded by an
        absence test, because outside those a literal is usually a genuine
        constant rather than a stand-in for a figure.
        """
        guard = self._absence_guard(node)
        if guard is None:
            return
        shape = f"{guard}-branch literal"

        value: ast.expr | None
        targets: list[ast.expr]
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value, targets = node.value, [node.target]
        else:
            value, targets = node.value, []
        if value is None:
            return

        # A result object or mapping built in the absence branch: every
        # measured field it carries is fabricated -- UNLESS the structure
        # already says so. A constructor carrying an unmeasured reason, a NaN
        # or an infinite interval is the correct repair, and flagging it would
        # punish the fix.
        if not _declares_itself_unmeasured(value):
            self._emit_structure(node, value, shape)

        literal = _numeric_literal(value)
        if literal is None:
            return
        if targets and self._is_accumulator(node, targets[0]):
            # `val_loss = 0.0` followed by `val_loss += ...` is an
            # accumulator's zero element, not a stand-in for a measurement.
            return
        if targets:
            names = self._names_of_target(targets[0])
        else:
            names = [getattr(self.enclosing_function(node), "name", "")]
        self._emit(_Candidate(node, names, shape, literal))

    def _emit_structure(self, anchor: ast.AST, value: ast.AST, shape: str, depth: int = 0) -> None:
        """Walk a dict/constructor built in an absence branch."""
        if depth > 3:
            return
        if isinstance(value, ast.Dict):
            for key, val in zip(value.keys, value.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    literal = _numeric_literal(val)
                    if literal is not None:
                        self._emit(_Candidate(val, [key.value], shape, literal))
                    else:
                        self._emit_structure(anchor, val, shape, depth + 1)
                else:
                    self._emit_structure(anchor, val, shape, depth + 1)
        elif isinstance(value, ast.Call):
            # Only a CLASS constructor's keywords name reported fields. An
            # ordinary function call's keywords are that function's own
            # parameters -- ``pm.stats.hdi(s_post, prob=0.95)`` sets a library
            # option, it does not publish a probability.
            func = value.func
            callee = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if not (callee[:1].isupper() or callee.startswith("_") and callee[1:2].isupper()):
                return
            for kw in value.keywords:
                if not kw.arg:
                    continue
                literal = _numeric_literal(kw.value)
                if literal is not None:
                    self._emit(_Candidate(kw.value, [kw.arg], shape, literal))
                else:
                    self._emit_structure(anchor, kw.value, shape, depth + 1)
        elif isinstance(value, ast.Tuple):
            for element in value.elts:
                literal = _numeric_literal(element)
                if literal is not None:
                    name = getattr(self.enclosing_function(anchor), "name", "")
                    self._emit(_Candidate(element, [name], shape, literal))

    def _is_accumulator(self, node: ast.AST, target: ast.AST) -> bool:
        names = set(self._names_of_target(target))
        if not names:
            return False
        scope = self.enclosing_function(node)
        for sub in ast.walk(scope):
            if isinstance(sub, ast.AugAssign) and set(self._names_of_target(sub.target)) & names:
                return True
        return False

    def _absence_guard(self, node: ast.AST) -> str | None:
        """Name the absence guard this statement sits under, if any."""
        current: ast.AST = node
        for parent in self.ancestors(node):
            if isinstance(parent, ast.ExceptHandler):
                return "except"
            if isinstance(parent, ast.If):
                if current in parent.body and _is_absence_test(parent.test):
                    return "absence"
                if current in parent.orelse and not _is_absence_test(parent.test):
                    # `if smds: ... else: 0.0` -- the else arm IS the empty case.
                    if isinstance(parent.test, (ast.Name, ast.Attribute, ast.Call, ast.Compare)):
                        return "absence"
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                return None
            current = parent
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Directories never walked: vendored dependencies, build output, caches, and
#: the repo's own tests. Tests are excluded because a fixture is SUPPOSED to
#: contain hand-written figures -- that is what makes it a fixture -- and
#: including them would bury the findings that matter.
SKIP_DIRS = frozenset(
    {
        ".git", ".venv", "venv", "env", "node_modules", "site-packages",
        "dist-packages", "__pycache__", ".mypy_cache", ".pytest_cache",
        ".ruff_cache", "build", "dist", ".eggs", "tests", "test",
        ".ipynb_checkpoints", ".tox", ".dvc", "migrations",
    }
)


def iter_python_files(
    roots: Iterable[Path], skip: Iterable[str] = SKIP_DIRS
) -> Iterator[Path]:
    """Walk Python files under ``roots``, skipping ``skip`` directories.

    ``skip`` is a parameter rather than a constant read so that R11 can widen
    the exclusion set for its repo-wide walk without changing what R10
    measures on the trees a repo declares. Two walkers would be two
    definitions of "this file is source".
    """
    skip = frozenset(skip)
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in skip for part in path.parts):
                continue
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                continue
            if path.name == "conftest.py":
                continue
            yield path


def scan_source(source: str, display: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return _ModuleScanner(display, source, tree).scan()


def scan_file(path: Path, display: str | None = None) -> list[Finding]:
    """Findings for one Python file. Unreadable or unparseable files yield none."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_source(source, display or str(path))


def scan_tree(roots: Iterable[Path], base: Path | None = None) -> list[Finding]:
    """Findings across every Python file under ``roots``."""
    findings: list[Finding] = []
    for path in iter_python_files(roots):
        display = str(path)
        if base is not None and path.is_relative_to(base):
            display = str(path.relative_to(base))
        findings.extend(scan_file(path, display))
    findings.sort(key=lambda f: (f.path, f.line, f.symbol))
    return findings
