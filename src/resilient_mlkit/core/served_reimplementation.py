"""Static detection of a locally re-implemented served-model contract (R12).

WHAT THIS LOOKS FOR
-------------------
The serving analogue of R11's question. R11 asks *did this row come from a
random draw and get stamped as observed?* R12 asks:

    Does this file decide what is SERVED — whether an artifact is the one that
    was measured, whether a challenger may be promoted, or which arm may be
    scored — without routing through the one contract that defines those
    answers for the portfolio?

Rule 7 states the cost: *eight local copies of a gate is eight different
definitions of "ready", which is the same as none.* Measured 2026-08-29 the
fleet had converged on one definition of ready and grown three of "served" —
two files with the SAME NAME (``mlops/champion_challenger.py`` in chokepoint
and in torrent), different SHAs, overlapping-but-not-identical APIs, plus
eleven further files across fray and chokepoint carrying promotion logic. The
divergence is not cosmetic: ``torrent/.../champion_challenger.py:128`` PROMOTES
on a zero baseline where ``chokepoint/.../champion_challenger.py:209-218``
returns NA on the identical condition.

THE FOUR CLAUSES, AND THE SHAPES THAT IMPLEMENT THEM
-----------------------------------------------------
Each detector below maps to one clause of ``core.served``. A file that carries
a clause locally is a file that can disagree with the contract about it.

``SELF_HASH``
    A canonical-JSON sha256 recomputed over an artifact payload — the
    ``canonical_payload_sha256`` shape all three serving modules already carry
    verbatim.
``PROVENANCE``
    A hand-rolled verification that a file on disk is the file a record pins.
``PROMOTION_VERDICT``
    A gate function, a challenger/promotion result type, or a verdict record
    carrying ``promotable`` / ``promote`` / ``clears``. This is the clause where
    the fleet actually disagrees, and where two implementations collapse NA into
    a bool.
``SERVE_ARM``
    A local decision about which arm or split may be served.
``CHAMPION_RECORD`` / ``SHADOW_ROUTER``
    The record and router types. Reported at the lower severity: they are the
    shape of a local contract rather than a decision it makes, and a repo can
    legitimately want a thin typed wrapper — but only over the imported
    contract, which is exactly what the exemption below tests.

THE EXEMPTION: A USE, NOT AN IMPORT
------------------------------------
A file is silent when it BINDS a name from ``resilient_mlkit.core.served`` —
directly, or through one module in the same repo that does — **and then
references that name somewhere other than the import line**. A call, an
attribute access, a base class, a decorator, an annotation: anything that makes
the contract load-bearing. An import nobody uses exempts nothing.

That last sentence is the repair, and it is here because the check used to fail
it. The exemption was ``_imports_contract`` alone, and resilient-fray PROVED by
measurement what that bought: adding ONE line to
``src/registry/promotion_gate.py`` —

    from resilient_mlkit.core.served import challenger_decision  # noqa: F401

— took the file's findings from 4 to 0 without changing a single decision it
makes. fray refused to take R12 green that way and recorded it as ``E-035``.
A check that a dead import can silence rewards the one thing it exists to
forbid, so the exemption now asks the question it always meant to ask. The same
mutation is reproduced as a control in ``tests/test_served_reimplementation.py``
(``test_an_unused_import_does_not_exempt_*``); reverting this to the import test
fails those and nothing else.

One level of indirection is still honoured, matching the precedent R11 set for
taint propagation through module-local helpers: a repo that adopts the contract
will put it behind one thin adapter, and a check that fired on the adapter's
callers would make adoption impossible. The route is still established by
import — a module that imports the contract genuinely re-exports its symbols,
so ``from adapter import challenger_decision`` genuinely resolves to the
contract — but the file CARRYING a clause must still reference what it took
from that adapter.

WHAT "REFERENCES THAT NAME" HAD TO BE TIGHTENED TO (E-035-VERIFY)
-----------------------------------------------------------------
The first cut of the repair above closed E-035 for the ``from X import f``
spelling only, and adversarial re-measurement against the SAME fray file found
two ways through it. Both were forced end to end — ``scan_source``,
``scan_repo`` and ``r12_served_contract`` — before this paragraph was written:

* **The dotted spelling.** ``import resilient_mlkit.core.served`` binds the
  ROOT name ``resilient_mlkit``, and the exemption asked only whether that root
  was read. Fleet code reads it constantly for unrelated reasons — e.g.
  ``resilient_mlkit.core.result.CheckResult`` — so the unrelated read paid for
  the unused import and E-035's one-line mutation survived intact: fray's
  ``promotion_gate.py`` again went 4 findings -> 0, R12 FAIL -> PASS. A dotted
  import is now a PREFIX requirement: the referenced chain must reach the
  contract itself, not merely its root package.
* **Shadow-and-call.** Excluding ``Store`` nodes from the reference set was not
  enough. A file that imports ``challenger_decision``, rebinds it to a local
  gate, and then CALLS the rebinding still produces a ``Load`` of the name, so
  it earned the exemption — a local implementation wearing the contract's name,
  silent. A name that this file also binds itself no longer earns the
  exemption; see :func:`_rebound_names`.

Both are held as FIRES/SILENT pairs in
``tests/test_served_reimplementation.py`` (``test_a_dotted_import_*``,
``test_shadowing_*``). Reverting :func:`_uses` to the first cut fails exactly
the FIRES halves. Neither closure moves a finding: both scanners walk all 14
``resilient-*`` checkouts, 3379 files, and produce identical rows file-for-file.

THE SERVE ARM: THE EXEMPTION IS THE DECISION'S, NOT THE FILE'S (E-079)
-----------------------------------------------------------------------
Everything above scopes the exemption to the FILE, and resilient-torrent
measured what that buys. Driven three ways on the real
``resilient-torrent/mlkit_bindings.py`` (E-079, 2026-09-05, 588 files walked;
reproduced here at 597 files on 2026-09-06):

===========================================================  ========
tree                                                          findings
===========================================================  ========
PR #190 as authored — a local ``D6_DECIDING_ARM = "val"``            1
the repair — the arm obtained through ``ServeArms.require``          0
the repair PLUS the constant restored AND USED, helper dead          0
===========================================================  ========

The third row is the defect. Once a file binds and uses ANY ``core.served``
name, a serve-arm constant elsewhere in the same file went unreported — even
when that constant was the value the file actually served on. So a silent R12
did not establish that the arm flowed through the contract; one conforming
helper anywhere in the file bought silence for every serve-arm decision in it.
It is E-035's shape one layer out: there a dead IMPORT paid for a live local
gate, here a live helper pays for a local arm.

So for the ``SERVE_ARM`` clause the exemption is now a property of the VALUE:

    a serve-arm site is exempt where the value it decides is DERIVED from a
    bound ``core.served`` name — directly, through the one permitted level of
    repo-local indirection, or through a module-level binding or helper in this
    same file whose own value is so derived — and not where such a name merely
    appears somewhere else in the file.

:func:`_serve_arm_derivation` computes that derivation as a fixpoint over the
module's top level, so ``ARMS = _arms()`` where ``_arms()`` returns the
contract's ``ServeArms`` is exempt and ``ARMS = ("val", "train")`` in the same
file is not. The fixpoint is what keeps adoption possible: a repo that puts the
contract behind a helper, which is the shape torrent's repair actually has, must
not be reported for having written two statements instead of one.

**The other five clauses keep the file-scoped exemption unchanged.** E-079 is
about the serve arm; re-scoping the promotion clause would be a second change
wearing this one's clothes, and it is not made here. The change is therefore
strictly stronger: it can only ADD findings, never remove one.

WHAT A GREEN R12 DOES NOT CLAIM
-------------------------------
That the repo's serving path is correct. R12 is an ``ast`` walk: it can see
that a file references the contract, never that it routes through it
*correctly*. A file that calls ``challenger_decision`` and then throws the
verdict away is silent here and is a defect; so is one that references the name
only to satisfy this check. The bar this check sets is "the contract is
referenced", which is strictly higher than "the contract is imported" and
strictly lower than "the contract decides". That gap is stated rather than
papered over; closing it needs the repo's own served-report reproduction, which
is the adopter's verifier, not this check.

Concretely, and measured rather than supposed: these three remain SILENT and
are defects, on the real fray file —

    from resilient_mlkit.core.served import challenger_decision
    challenger_decision            # a bare read, or `_ = challenger_decision`

    if False:
        from resilient_mlkit.core.served import challenger_decision
    challenger_decision(block)     # a reference to a binding never executed

An ``ast`` walk cannot separate those from a real use without evaluating the
module, and a rule that guessed would fire on adopters. The evasion cost is now
a deliberate lie in the source rather than a tidy import line, which is the
most this check can honestly buy.

Nor does it claim to catch a re-implementation written in a language this does
not parse, or one loaded at runtime from a string. Both are outside an AST.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from . import fabrication

__all__ = [
    "CLAUSES",
    "CONTRACT_MODULE",
    "REIMPLEMENTED",
    "SERVE_ARM_CLAUSE",
    "SERVING_ADJACENT",
    "Finding",
    "ServeArmDerivation",
    "contract_importers",
    "iter_repo_python_files",
    "scan_repo",
    "scan_source",
    "scan_tree",
    "serve_arm_repair",
]

#: The dotted module every adopter must route through.
CONTRACT_MODULE = "resilient_mlkit.core.served"

#: Import spellings that count as routing through the contract.
_CONTRACT_IMPORT_TOKENS = (
    "resilient_mlkit.core.served",
    "resilient_mlkit.core",
    "resilient_mlkit",
)

# ---------------------------------------------------------------------------
# Severities
# ---------------------------------------------------------------------------

#: A clause of the contract DECIDED locally. This is what rule 7 is about.
REIMPLEMENTED = "CONTRACT_REIMPLEMENTED"

#: A serving type (champion record, shadow router) defined locally without the
#: contract behind it. The shape of a second definition, not yet a decision.
SERVING_ADJACENT = "SERVING_ADJACENT"

#: The one clause whose exemption is scoped to the DECISION rather than to the
#: file (E-079). Named rather than spelled inline so the two places that ask
#: about it cannot drift apart.
SERVE_ARM_CLAUSE = "SERVE_ARM"

CLAUSES = (
    "SELF_HASH",
    "PROVENANCE",
    "PROMOTION_VERDICT",
    SERVE_ARM_CLAUSE,
    "CHAMPION_RECORD",
    "SHADOW_ROUTER",
)

_CLAUSE_SEVERITY = {
    "SELF_HASH": REIMPLEMENTED,
    "PROVENANCE": REIMPLEMENTED,
    "PROMOTION_VERDICT": REIMPLEMENTED,
    "SERVE_ARM": REIMPLEMENTED,
    "CHAMPION_RECORD": SERVING_ADJACENT,
    "SHADOW_ROUTER": SERVING_ADJACENT,
}

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# There is deliberately NO function-name list for the self-hash clause, and the
# absence is a measurement rather than an oversight. One was tried — the six
# names three repos actually use, ``canonical_payload_sha256`` among them — and
# it produced two false positives on the first fleet run and nothing the shape
# rule had not already found:
#
#   * ``resilient-torrent/src/torrent/api/routers/v4_avoided_loss.py:29``
#     ``_canonical_hash`` hashes an API REQUEST to make a cache key;
#   * ``resilient-blackout/resilient_blackout/mlops/checkpoint_sidecar.py:87``
#     ``artifact_sha256`` is a chunked hash of a FILE's bytes.
#
# Neither is an artifact self-hash, and both were named exactly like one. The
# shape in ``_scan_hashing`` — canonical JSON, hashed, with the payload's own
# hash field excluded — is what the clause actually is, and it does not depend
# on what anybody called the function.

#: Function names that verify bytes on disk against a record's pin.
_PROVENANCE_FUNCTIONS = frozenset(
    {
        "verify_provenance",
        "verify_at_load",
        "verify_artifact",
        "verify_checkpoint",
        "verify_recorded_checkpoint",
        "verify_panel_provenance",
        "verify_covariate_provenance",
        "verify_source_files",
        "verify_training_data",
        "check_provenance",
    }
)

#: Function names that decide a promotion.
_GATE_FUNCTIONS = frozenset(
    {
        "challenger_gate",
        "challenger_decision",
        "evaluate_promotion",
        "evaluate_challenger",
        "promotion_gate",
        "run_promotion_gate",
        "challenger_clears_record",
        "clears_record",
        "is_promotable",
        "assert_promotable",
        "check_promotion",
        "decide_promotion",
    }
)

#: Class names that ARE a promotion verdict or the gate that produces one.
_GATE_CLASS_RE = re.compile(
    r"(?:^|[A-Z_])(?:ChampionChallenger|ChallengerResult|ChallengerDecision"
    r"|PromotionGate|PromotionResult|PromotionDecision|PromotionVerdict)",
)

#: Dict keys and dataclass fields that carry a promotion verdict.
_PROMOTION_KEYS = frozenset(
    {"promotable", "promote", "clears", "can_promote", "is_promotable", "promotion"}
)

#: Keys that make a dict a VERDICT rather than a configuration knob. A dict with
#: ``{"promote": False}`` and nothing else is a settings blob; a dict with a
#: promotion key AND a status or a reason is a gate's answer.
_VERDICT_COMPANION_KEYS = frozenset({"status", "reason", "verdict", "unmeasured_reason"})

#: The verdict vocabulary itself. A function that decides between these three is
#: deciding the thing ``core.served.ChallengerDecision`` exists to decide.
_VERDICT_VALUES = frozenset({"PASS", "FAIL"})

#: What makes a PASS/FAIL-emitting function a PROMOTION decision rather than a
#: table renderer. ``gate`` is matched on token boundaries so that
#: ``aggregate``, ``mitigate``, ``delegate`` and ``investigate`` do not qualify;
#: ``promot`` needs no boundary because no other word starts that way.
_VERDICT_CONTEXT_RE = re.compile(r"promot|champion|challenger|(?:^|_)gates?(?:$|_)")

#: Class names that ARE the served record or the router.
_CHAMPION_CLASS_RE = re.compile(r"Champion|ServedModel|ServedChampion|ModelOfRecord")
_ROUTER_CLASS_RE = re.compile(r"ShadowRouter|TrafficRouter|CanaryRouter|ShadowDeployment")

#: Methods that make a ``*Champion*`` class the served record rather than a
#: name that merely contains the word.
_RECORD_METHODS = frozenset(
    {"from_payload", "load", "load_track", "verify", "verify_checkpoint", "predict"}
)

#: Module-level constant names that declare a serve-arm policy.
_ARM_CONSTANT_RE = re.compile(
    r"^(?:[A-Z0-9_]*_)?(?:SERVEABLE|SERVABLE|SERVED|OPEN|CLOSED|DECIDING|ALLOWED)"
    r"_(?:ARMS?|SPLITS?)$|^(?:ARMS?|SERVE_ARMS)$"
)

#: An identifier that means "arm" — matched on TOKEN boundaries, never as a
#: substring. The first version of this used ``"arm" in name.lower()`` and
#: reported four files across choco, arabica and blackout on ``farm_size_col``,
#: ``farm_panel_parquet_path`` and ``_IPCC_WARMING``. A check that fires on the
#: word "warming" is a check somebody switches off.
_ARM_TOKEN_RE = re.compile(r"(?:^|_)arms?(?:$|_)")

#: The arms a serving decision is actually about. An inline refusal has to name
#: one of these, or a declared arm constant, before it is a serve-arm guard
#: rather than an assertion that happens to involve a variable called ``arm``:
#: ``chokepoint/.../forecasting/corridor_pooling.py:525`` checks that an
#: ENSEMBLE's arm set matches its declared order, which is a different sense of
#: the word and not this clause.
_ARM_VALUES = frozenset(
    {"train", "val", "valid", "validation", "test", "holdout", "dev", "eval"}
)

#: The artifact key the whole fleet already uses. Corroboration, never a
#: trigger on its own: a file may legitimately READ an artifact it did not
#: define, and reading is not re-implementing.
_ARTIFACT_HASH_KEY = "artifact_sha256"

#: Names and string values that identify the field an artifact's OWN hash lives
#: in. Excluding one of these from a payload before hashing it is the signature
#: of a SELF-hash, and it is what separates a re-implemented artifact digest
#: from an honest fingerprint — see ``_scan_hashing``.
_HASH_KEY_VALUES = frozenset(
    {
        "artifact_sha256", "artifact_hash", "payload_sha256", "self_sha256",
        "sha256", "hash", "checksum", "digest", "content_hash",
    }
)
_HASH_KEY_NAME_RE = re.compile(r"HASH_KEY|SHA256_KEY|DIGEST_KEY|CHECKSUM_KEY")

#: Directories skipped on the repo-wide walk. Same set R11 uses, so "this file
#: is source" has one definition across the instrument.
REPO_SKIP_DIRS: frozenset[str] = fabrication.SKIP_DIRS | frozenset(
    {
        ".worktrees", ".claude", ".idea", ".vscode", "vendor", "third_party",
        "_vendor", "docs", "site", "htmlcov", "wheels", ".direnv",
    }
)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Finding:
    """One clause of the served contract, implemented locally in one file."""

    path: str
    line: int
    clause: str
    severity: str
    symbol: str
    detail: str
    corroborating: tuple[str, ...] = ()
    #: The exact repair, naming the bound ``core.served`` name the value must
    #: derive from (E-M38). Empty for clauses whose repair is the file-level
    #: adoption the module docstring describes; filled for every ``SERVE_ARM``
    #: row, because that clause is decided per site and the consumer fixing it
    #: should not have to read this module to learn what "derived" means.
    repair: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "clause": self.clause,
            "severity": self.severity,
            "symbol": self.symbol,
            "detail": self.detail,
            "corroborating": list(self.corroborating),
            "repair": self.repair,
        }


# ---------------------------------------------------------------------------
# Import analysis
# ---------------------------------------------------------------------------
def _imported_modules(tree: ast.AST) -> set[str]:
    """Every dotted module name this file imports, however it spells it."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                names.add(base)
            for alias in node.names:
                names.add(f"{base}.{alias.name}" if base else alias.name)
    return names


def _imports_contract(imported: set[str]) -> bool:
    """True when this file reaches ``core.served`` by any import spelling.

    ``from resilient_mlkit.core import served`` yields
    ``resilient_mlkit.core.served`` from the alias pass above, and
    ``import resilient_mlkit.core.served as s`` yields it directly. A bare
    ``import resilient_mlkit`` does NOT count: it reaches the package, not the
    contract, and counting it would let any repo silence this check with one
    unrelated import.

    Importing is necessary for the exemption and NOT sufficient for it. This
    predicate answers only "can this module see the contract", which is the
    right question for :func:`contract_importers` — a module that imports a
    symbol re-exports it, so it is a genuine route whether or not it uses it
    itself. Whether a file is EXEMPT is :func:`_uses_contract`.
    """
    return any(
        name == CONTRACT_MODULE or name.startswith(CONTRACT_MODULE + ".")
        for name in imported
    )


def _is_contract_module(name: str) -> bool:
    return name == CONTRACT_MODULE or name.startswith(CONTRACT_MODULE + ".")


def _bindings_from(
    tree: ast.AST, is_source: Callable[[str], bool]
) -> tuple[set[str], set[str]]:
    """What a USE of this file's imports would have to look like.

    Returns ``(names, prefixes)``.

    ``names`` are bindings that land in the module namespace as a bare name, so
    a use is a ``Load`` of that name:

    * ``from X import f``            binds ``f``
    * ``from X import f as g``       binds ``g``
    * ``from pkg import X``          binds ``X``     (module-object import)
    * ``import X.Y.Z as c``          binds ``c``

    ``prefixes`` are the one spelling whose binding is NOT what a use
    references. ``import X.Y.Z`` binds the root ``X``, but a use is the whole
    dotted chain ``X.Y.Z...``. Treating the root as the requirement was the
    E-035 hole this repair closed only halfway: it made ANY read of ``X`` --
    ``resilient_mlkit.core.result.CheckResult``, say, which fleet code has for
    reasons unrelated to serving -- pay for an unused
    ``import resilient_mlkit.core.served``, so the one-line evasion survived
    intact for that spelling. Verified by measurement on
    resilient-fray's ``src/registry/promotion_gate.py``: 4 findings -> 0.
    """
    names: set[str] = set()
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not is_source(alias.name):
                    continue
                if alias.asname:
                    names.add(alias.asname)
                else:
                    prefixes.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                full = f"{base}.{alias.name}" if base else alias.name
                if is_source(base) or is_source(full):
                    names.add(alias.asname or alias.name)
    return names, prefixes


def _dotted(node: ast.AST) -> str | None:
    """``a.b.c`` for an attribute chain rooted at a plain name; None otherwise."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _referenced_names(tree: ast.AST) -> set[str]:
    """Every name this file READS.

    ``ast.Name`` in a ``Load`` context covers every shape that makes a binding
    load-bearing, because Python spells all of them the same way at the root: a
    call (``f(...)``), an attribute chain (``served.ServeArms`` — the chain's
    root is a ``Name``), a base class, a decorator, a default, an annotation, a
    re-assignment's right-hand side. A ``Store`` is excluded on purpose: a file
    that rebinds the imported name is shadowing the contract, not using it.
    """
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _referenced_chains(tree: ast.AST) -> set[str]:
    """Every dotted chain this file READS, e.g. ``pkg.core.served.decide``."""
    chains: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            dotted = _dotted(node)
            if dotted:
                chains.add(dotted)
    return chains


def _rebound_names(tree: ast.AST) -> set[str]:
    """Names this file BINDS to something of its own.

    Excluding the import statements themselves, which are the binding under
    test. A name that is imported from the contract and then assigned, defined,
    or deleted is a local definition wearing the contract's name; references to
    it after that point resolve to the local thing, so they are not evidence
    the contract is load-bearing. ``_referenced_names`` skipping ``Store``
    nodes was never enough on its own: the file that shadows AND THEN CALLS the
    shadowed name still had a ``Load``, and so still earned the exemption.
    """
    rebound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            rebound.add(node.id)
            continue
        # def / async def / class / `except E as name` all bind through `.name`.
        name = getattr(node, "name", None)
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler),
        ) and isinstance(name, str):
            rebound.add(name)
    return rebound


def _uses(tree: ast.AST, is_source: Callable[[str], bool]) -> bool:
    """True when this file binds a name from an accepted module AND uses it."""
    names, prefixes = _bindings_from(tree, is_source)
    if not names and not prefixes:
        return False
    rebound = _rebound_names(tree)
    if (names - rebound) & _referenced_names(tree):
        return True
    if not prefixes:
        return False
    # The rebind rule above is deliberately NOT applied to a dotted prefix. Its
    # root is a package name, and a module inside package ``serve`` defining
    # ``def serve(...)`` is a name collision, not an evasion; meanwhile the
    # requirement a prefix imposes is already the strong one — the whole chain
    # down to the contract has to be read — so there is nothing for a shadow to
    # buy. Excluding rebound roots here fired on the repo-local adapter route
    # instead, which is the trade the module docstring forbids.
    chains = _referenced_chains(tree)
    return any(
        any(chain == prefix or chain.startswith(prefix + ".") for chain in chains)
        for prefix in prefixes
    )


def _uses_contract(tree: ast.AST) -> bool:
    """True when this file binds a contract name AND references it.

    The FILE-level exemption predicate, which after E-079 exempts the five
    clauses that are shapes rather than serve-arm values. See the module
    docstring's E-035 note for why this is not ``_imports_contract``, and its
    E-079 note for why the serve arm no longer asks this question.
    """
    return _uses(tree, _is_contract_module)


def _reads(node: ast.AST, names: Iterable[str], prefixes: Iterable[str]) -> bool:
    """Does this subtree READ one of these bindings?

    The same notion of "reads" :func:`_uses` applies, restricted to one subtree
    instead of the whole module: a ``Load`` of a bare name, or a dotted chain
    that reaches the whole prefix. ``Store`` is excluded for the same reason it
    is there — a subtree that rebinds a name is not one that took a value from
    it.
    """
    names = frozenset(names)
    prefixes = frozenset(prefixes)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            if sub.id in names:
                return True
        elif isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load):
            chain = _dotted(sub)
            if chain and any(
                chain == prefix or chain.startswith(prefix + ".") for prefix in prefixes
            ):
                return True
    return False


@dataclass(frozen=True)
class ServeArmDerivation:
    """Which names in one file carry a value that came from the contract.

    ``names`` and ``prefixes`` are the contract's own bindings, in the two
    spellings :func:`_bindings_from` distinguishes. ``derived`` is the fixpoint
    over the module's top level: every module-level function, class or binding
    whose own body or value reads something already in the set. A serve-arm
    site is exempt when it reads any of the three.
    """

    names: frozenset[str] = frozenset()
    prefixes: frozenset[str] = frozenset()
    derived: frozenset[str] = frozenset()
    #: The subset of ``derived`` bound by ``def``/``class``, so a repair can
    #: spell them as a call (``_d6_serve_arms().require(...)``) rather than as
    #: a value.
    callables: frozenset[str] = frozenset()

    def covers(self, node: ast.AST | None) -> bool:
        """Is this serve-arm value derived from a bound ``core.served`` name?"""
        if node is None:
            return False
        return _reads(node, self.names | self.derived, self.prefixes)

    def policies(self) -> list[str]:
        """Derived names that speak of arms, spelled as a reader would use them.

        These are the values a ``SERVE_ARM`` repair can derive from: a
        ``SERVE_ARMS = ServeArms(...)`` binding or a helper returning one. A
        derived name that does not speak of arms (a coverage helper, a
        polarity constant) is contract-derived but is not an arm policy, and
        offering ``.require`` on it would be a wrong repair with a confident
        voice.
        """
        arms = [
            n for n in sorted(self.derived)
            if _ARM_CONSTANT_RE.match(n) or _ARM_TOKEN_RE.search(n.lower())
        ]
        # A declared policy constant before a helper, so the example names
        # the shape torrent's own adoption has.
        arms.sort(key=lambda n: (n in self.callables, n))
        return [f"{n}()" if n in self.callables else n for n in arms]


#: The one import a serve-arm repair needs when the file binds no contract name.
_SERVE_ARMS_IMPORT = "from resilient_mlkit.core.served import ServeArms"


def serve_arm_repair(
    derivation: ServeArmDerivation, symbol: str, *, arm: str | None, inline: bool
) -> str:
    """The exact repair for one ``SERVE_ARM`` finding (E-M38).

    Names, in order of preference: the serve-arm policy this file already takes
    from ``core.served`` (``SERVE_ARMS``, or a helper returning one); failing
    that, the ``ServeArms`` the file binds and has not declared a policy with;
    failing that, the import it lacks. Every branch ends in the same two
    tokens — a ``ServeArms`` and its ``.require`` — because that is the only
    shape the exemption is granted to. What no branch offers is a way to keep
    the local value: a serve-arm value is the contract's, or it is this file's.

    The closing sentence names the other honest exit E-M38 leaves open — that
    the word is being used in a different sense — and says how a repo says so
    where the check can see it (a rename out of the pattern), so the finding
    cannot be read as demanding ``ServeArms`` for an evaluation-arm table.
    """
    arm_repr = f'"{arm}"' if arm else '"<arm>"'
    policies = derivation.policies()
    binds_serve_arms = "ServeArms" in derivation.names
    declare = (
        f"SERVE_ARMS = ServeArms(open=frozenset({{{arm_repr}}}), "
        'closed={"<arm>": "<why it is closed>"})'
    )
    if policies:
        best = policies[0]
        because = (
            f"{best} is the serve-arm policy this file already takes from "
            "core.served"
            + (f" (also: {', '.join(policies[1:])})" if len(policies) > 1 else "")
        )
        if inline:
            head = (
                f"replace the inline test with the contract's guard, "
                f"`{best}.require(<the arm being tested>)`; {because}"
            )
        else:
            head = (
                f"derive {symbol} from {best}: `{symbol} = {best}.require({arm_repr})`; "
                f"{because}, and a bare literal beside it is E-079's third row"
            )
    else:
        # Bound names only -- not the derived helpers, which are this file's
        # own, and not the route module's whole namespace. Capped: the point
        # is "you already reach the contract", not an inventory.
        bound = sorted(derivation.names)
        shown = ", ".join(bound[:4]) + (f", +{len(bound) - 4} more" if len(bound) > 4 else "")
        if binds_serve_arms:
            have = "declare the policy with the ServeArms this file already binds"
        elif bound:
            have = (
                f"this file binds {shown} from core.served (or from a module in "
                f"this repo that imports it) but no serve-arm policy; add "
                f"`{_SERVE_ARMS_IMPORT}` and declare one"
            )
        else:
            have = (
                f"this file binds no core.served name; add `{_SERVE_ARMS_IMPORT}` "
                "and declare the policy"
            )
        if inline:
            head = (
                f"{have}, `{declare}`, then test the arm through the contract's "
                "guard, `SERVE_ARMS.require(<the arm being tested>)`"
            )
        else:
            head = (
                f"{have}, `{declare}`, then derive "
                f"`{symbol} = SERVE_ARMS.require({arm_repr})`"
            )
    guard = (
        "ServeArms.require also refuses an UNDECLARED arm, which a test against "
        "one name does not. "
    ) if inline else ""
    subject = "the constant this test reads" if inline else symbol
    return (
        f"REPAIR: {head}. {guard}"
        f"If {subject} is not a serve arm at all (an evaluation-arm table, a "
        "column-label assertion), rename it out of R12's arm-constant pattern -- "
        "`<SERVEABLE|SERVED|OPEN|CLOSED|DECIDING|ALLOWED>_ARM(S)`/`_SPLIT(S)`, or a "
        "bare `ARM`/`ARMS`/`SERVE_ARMS` -- and record why in the repo's own "
        "escalation register; mlkit keeps no exemption list (E-M38)"
    )


def _serve_arm_derivation(
    tree: ast.AST, importers: set[str] | None = None
) -> ServeArmDerivation:
    """The E-079 predicate: what in this file carries the contract's value.

    Both routes count — a direct ``core.served`` binding and one taken from a
    repo-local module that imports the contract — because the file-level
    exemption honours both and narrowing one without the other would fire on
    the adoption path rather than on the evasion.

    The fixpoint is small and deliberate. torrent's own repair is
    ``d6_deciding_arm()`` returning ``_d6_serve_arms().require("val")``: two
    statements, one contract. A rule that demanded the contract's name appear
    IN the serve-arm expression itself would report that adoption, which is the
    trade the module docstring forbids. What it will not do is treat a helper
    the value never consults as evidence about the value — which is exactly the
    row E-079 measured at 0.
    """
    names, prefixes = _bindings_from(tree, _is_contract_module)
    if importers:
        route_names, route_prefixes = _bindings_from(tree, lambda n: n in importers)
        names |= route_names
        prefixes |= route_prefixes
    # A name this file also binds itself is a local definition wearing the
    # contract's name; references to it resolve to the local thing. Same rule
    # `_uses` applies, and for the same reason (shadow-and-call).
    names -= _rebound_names(tree)

    derived: set[str] = set()
    callables: set[str] = set()
    changed = True
    while changed:
        changed = False
        pool = names | derived
        for stmt in getattr(tree, "body", []):
            if isinstance(
                stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                if stmt.name in derived:
                    continue
                if _reads(stmt, pool, prefixes):
                    derived.add(stmt.name)
                    callables.add(stmt.name)
                    changed = True
                continue
            targets: list[ast.Name]
            value: ast.expr | None
            if isinstance(stmt, ast.Assign):
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                targets = [stmt.target]
                value = stmt.value
            else:
                continue
            if value is None or not _reads(value, pool, prefixes):
                continue
            for target in targets:
                if target.id not in derived:
                    derived.add(target.id)
                    changed = True
    return ServeArmDerivation(
        names=frozenset(names),
        prefixes=frozenset(prefixes),
        derived=frozenset(derived),
        callables=frozenset(callables),
    )


def _uses_route(tree: ast.AST, importers: set[str]) -> bool:
    """True when this file binds a name from a repo-local contract importer
    AND references it. The one permitted level of indirection."""
    if not importers:
        return False
    return _uses(tree, lambda name: name in importers)


def _module_aliases(path: Path, root: Path) -> set[str]:
    """Dotted names by which this file could be imported from inside its repo.

    Every suffix of its path, because repos put their packages under ``src/``,
    under a package directory, or at the root, and all three spellings appear in
    the fleet. Over-generating aliases makes the exemption slightly wider, which
    is the safe direction for a check that must not fire on adopted code.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:  # pragma: no cover - path outside the repo
        relative = path
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    aliases: set[str] = set()
    for start in range(len(parts)):
        tail = parts[start:]
        if tail:
            aliases.add(".".join(tail))
    return aliases


def contract_importers(root: Path, paths: Iterable[Path] | None = None) -> set[str]:
    """Dotted names of every module in this repo that imports the contract.

    Pass one of the two-pass scan. A file importing any of these is treated as
    routing through the contract at one level of indirection.
    """
    files = list(paths) if paths is not None else list(iter_repo_python_files(root))
    importers: set[str] = set()
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        if _imports_contract(_imported_modules(tree)):
            importers |= _module_aliases(path, root)
    return importers


# ---------------------------------------------------------------------------
# The scanner
# ---------------------------------------------------------------------------
class _ModuleScanner:
    def __init__(
        self,
        display: str,
        tree: ast.Module,
        derivation: ServeArmDerivation | None = None,
    ) -> None:
        self.display = display
        self.tree = tree
        #: E-079. What in this file carries the contract's value, so a
        #: serve-arm site can be exempted on its own derivation rather than on
        #: the file's. ``None`` means "ask nothing", which is what a caller
        #: that wants every shape reported passes.
        self.derivation = derivation or ServeArmDerivation()
        self.findings: list[Finding] = []
        self.corroborating: list[str] = []

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _is_sha256_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "sha256":
            return True
        return bool(isinstance(func, ast.Name) and func.id == "sha256")

    @staticmethod
    def _is_canonical_dumps(node: ast.AST) -> bool:
        """A ``json.dumps(..., sort_keys=True)`` — canonical serialisation."""
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "dumps":
            return False
        return any(
            kw.arg == "sort_keys"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )

    def _string_constants(self) -> set[str]:
        return {
            n.value
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }

    def _record(
        self, node: ast.AST, clause: str, symbol: str, detail: str, repair: str = ""
    ) -> None:
        self.findings.append(
            Finding(
                path=self.display,
                line=getattr(node, "lineno", 0),
                clause=clause,
                severity=_CLAUSE_SEVERITY[clause],
                symbol=symbol,
                detail=detail,
                corroborating=tuple(sorted(set(self.corroborating))),
                repair=repair,
            )
        )

    # -- the walk --------------------------------------------------------
    def scan(self) -> list[Finding]:
        constants = self._string_constants()
        if _ARTIFACT_HASH_KEY in constants:
            self.corroborating.append(f'string "{_ARTIFACT_HASH_KEY}"')

        self._scan_hashing()
        self._scan_functions()
        self._scan_classes()
        self._scan_verdict_functions()
        self._scan_verdict_dicts()
        self._scan_arm_policy()

        # Corroboration is collected as the walk goes, so rebuild each finding
        # with the full set rather than the set as it stood at the moment the
        # finding was made. Deduplicated on the way: two detectors reaching the
        # same symbol is one fact about the file, and printing it twice
        # overstates how much there is to fix.
        corroborating = tuple(sorted(set(self.corroborating)))
        seen: set[tuple[int, str, str]] = set()
        findings: list[Finding] = []
        for f in self.findings:
            key = (f.line, f.clause, f.symbol)
            if key in seen:
                continue
            seen.add(key)
            # `replace`, not a field-by-field copy: the copy this used to be
            # silently dropped `repair` the day the field was added, and a
            # rebuild that has to be told about every field is a rebuild that
            # will forget the next one too.
            findings.append(dataclasses.replace(f, corroborating=corroborating))
        findings.sort(key=lambda f: (f.line, f.clause, f.symbol))
        return findings

    @staticmethod
    def _excludes_own_hash_field(scope: ast.AST) -> bool:
        """Is a hash field being removed from the payload before it is hashed?

        This is the one thing that separates an artifact SELF-hash from an
        honest fingerprint, and it is why the detector is not simply "sha256 of
        canonical JSON". All three serving modules in the fleet write the same
        line — ``{k: v for k, v in payload.items() if k != HASH_KEY}`` — because
        a digest stored inside the object it covers has to exclude itself.

        A canonical hash WITHOUT that exclusion is a fingerprint over a config,
        a run record or an audit row, which is a legitimate and common thing to
        compute. Measured 2026-08-29, ``resilient-surge`` has two of them
        (``mlops/reproducibility.py:34-36``, ``governance/audit_trail.py:
        176-179``) and neither is a served-model artifact digest. Firing on
        those would make R12 a check that cries wolf, and a check that cries
        wolf gets disabled.
        """
        for node in ast.walk(scope):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, (ast.NotEq, ast.Eq, ast.NotIn, ast.In)) for op in node.ops):
                continue
            for operand in [node.left, *node.comparators]:
                if isinstance(operand, ast.Constant) and operand.value in _HASH_KEY_VALUES:
                    return True
                if isinstance(operand, ast.Name) and _HASH_KEY_NAME_RE.search(operand.id):
                    return True
                if isinstance(operand, ast.Attribute) and _HASH_KEY_NAME_RE.search(
                    operand.attr
                ):
                    return True
        return False

    def _scan_hashing(self) -> None:
        """A canonical-JSON sha256 that excludes its own hash field is a self-hash.

        Both spellings are caught, because the difference between them is a
        newline: the digest taken in one expression, and the digest taken over a
        local that a previous statement assigned. The scope for the second is
        the enclosing function, which is where every real instance of this lives.
        """
        scopes: list[ast.AST] = [
            n for n in ast.walk(self.tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for scope in scopes:
            sha_calls = [n for n in ast.walk(scope) if self._is_sha256_call(n)]
            if not sha_calls:
                continue
            canonical = [n for n in ast.walk(scope) if self._is_canonical_dumps(n)]
            if not canonical:
                continue
            if not self._excludes_own_hash_field(scope):
                continue
            self._record(
                sha_calls[0],
                "SELF_HASH",
                "sha256 over canonical JSON with the hash field excluded",
                "recomputes an artifact self-hash locally; core.served."
                "canonical_payload_sha256 is the one definition of that digest, and "
                "it reproduces every committed artifact hash in the fleet byte for "
                "byte",
            )

    def _scan_functions(self) -> None:
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            bare = node.name.lstrip("_")
            if bare in _PROVENANCE_FUNCTIONS:
                self._record(
                    node, "PROVENANCE", node.name,
                    "verifies bytes against a record locally; core.served."
                    "verify_at_load and DataSource.verify are the contract's refusals",
                )
            if bare in _GATE_FUNCTIONS:
                self._record(
                    node, "PROMOTION_VERDICT", node.name,
                    "decides a promotion locally; core.served.challenger_decision is "
                    "the one gate, and it is the clause the fleet actually disagrees on",
                )

    def _scan_classes(self) -> None:
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {
                b.name for b in node.body
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if _GATE_CLASS_RE.search(node.name):
                self._record(
                    node, "PROMOTION_VERDICT", node.name,
                    "a local promotion-verdict type; core.served.ChallengerDecision "
                    "keeps NA structurally distinct from FAIL, which a bool cannot",
                )
            elif _ROUTER_CLASS_RE.search(node.name):
                self._record(
                    node, "SHADOW_ROUTER", node.name,
                    "a local traffic router; ShadowRouter is defined twice in the "
                    "fleet with OPPOSITE production semantics (one returns the "
                    "champion's result, one returns the challenger's)",
                )
            elif _CHAMPION_CLASS_RE.search(node.name) and (methods & _RECORD_METHODS):
                self._record(
                    node, "CHAMPION_RECORD", node.name,
                    f"a local served-model record (methods {sorted(methods & _RECORD_METHODS)}); "
                    "core.served.ServedModel is the portfolio's record type",
                )
            # A dataclass field carrying the verdict. torrent's ChallengerResult
            # is exactly this: `promote: bool`, no status, so an unmeasured
            # comparison and a measured loss are the same value.
            for body_node in node.body:
                if (
                    isinstance(body_node, ast.AnnAssign)
                    and isinstance(body_node.target, ast.Name)
                    and body_node.target.id in _PROMOTION_KEYS
                ):
                    self._record(
                        body_node, "PROMOTION_VERDICT",
                        f"{node.name}.{body_node.target.id}",
                        "a promotion verdict held as a record field; unless it is "
                        "derived from a three-valued status, an unmeasured "
                        "comparison and a measured loss are the same value",
                    )

    def _scan_verdict_functions(self) -> None:
        """A function that decides PASS/FAIL about a promotion, whatever it is called.

        The name vocabularies above are a losing game on their own, and this
        module found that out by measurement: they were silent on
        ``resilient-arabica/src/registry/backbone_promotion.py:40``
        (``evaluate_backbone_gate`` — "whether challenger backbone model
        qualifies for promotion over champion") and on
        ``src/registry/promotion_gate.py:359`` (``evaluate_all_gates``), because
        neither name was in the list. Chasing more names would have kept losing.

        So this rule is structural: a function scope that emits both ``"PASS"``
        and ``"FAIL"`` as string constants, and whose OWN NAME, enclosing class
        or module path puts it in a promotion context, is a promotion decision
        no matter what it is called. Both halves are required — the constants
        alone would report every report renderer in the fleet.

        The context is deliberately the declaration and not the body. Matching
        any identifier anywhere in the scope was measurably too loose: it
        reported ``resilient-choco/src/validation/giews_drought_validation.py``
        and ``resilient-fray/src/validation/belt_drought_barometer.py``, neither
        of which decides a promotion — they merely CALL a helper with "gate" in
        its name. Where a function is declared is a claim about what it is;
        what it happens to call is not.
        """
        enclosing: dict[ast.AST, str] = {}
        for cls in ast.walk(self.tree):
            if isinstance(cls, ast.ClassDef):
                for body_node in cls.body:
                    enclosing[body_node] = cls.name

        for scope in ast.walk(self.tree):
            if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            constants = {
                n.value for n in ast.walk(scope)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            }
            if not _VERDICT_VALUES <= constants:
                continue
            context = "|".join(
                part.lower()
                for part in (self.display, enclosing.get(scope, ""), scope.name)
                if part
            )
            if not _VERDICT_CONTEXT_RE.search(context):
                continue
            self._record(
                scope, "PROMOTION_VERDICT", scope.name,
                "decides PASS/FAIL on a promotion locally; core.served."
                "challenger_decision is the one gate, and it is the clause where the "
                "fleet's implementations actually disagree",
            )

    def _scan_verdict_dicts(self) -> None:
        """A dict literal that IS a gate's answer, rather than a settings blob."""
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = {
                k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            promotion = keys & _PROMOTION_KEYS
            if promotion and (keys & _VERDICT_COMPANION_KEYS):
                self._record(
                    node, "PROMOTION_VERDICT",
                    f"{{{', '.join(sorted(promotion))}, ...}}",
                    "a promotion verdict assembled as a bare dict; core.served."
                    "ChallengerDecision enforces that PASS carries measured skill and "
                    "that NA carries none",
                )

    def _scan_arm_policy(self) -> None:
        """A local decision about which arm may be served.

        The exemption asked here is the DECISION's, not the file's (E-079). A
        constant whose VALUE comes from the contract is the contract's policy
        spelled in this file; a constant whose value is a bare tuple is this
        file's policy, whatever else the file imports and uses.
        """
        for node in self.tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            if self.derivation.covers(value):
                continue
            # The literal, when there is one, so the repair can spell the arm
            # the file actually serves rather than a placeholder.
            arm = (
                value.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
                else None
            )
            for target in targets:
                if isinstance(target, ast.Name) and _ARM_CONSTANT_RE.match(target.id):
                    self._record(
                        node, "SERVE_ARM", target.id,
                        "declares a serve-arm policy locally; core.served.ServeArms "
                        "makes the policy data and the refusal mechanical, which is "
                        "what lets two repos disagree about which arm is closed "
                        "without disagreeing about the guard",
                        repair=serve_arm_repair(
                            self.derivation, target.id, arm=arm, inline=False
                        ),
                    )

        for if_node in ast.walk(self.tree):
            if not isinstance(if_node, ast.If):
                continue
            if not any(isinstance(sub, ast.Raise) for sub in ast.walk(if_node)):
                continue
            names = [
                getattr(sub, "id", "") or getattr(sub, "attr", "")
                for sub in ast.walk(if_node.test)
            ]
            if not any(_ARM_TOKEN_RE.search(n.lower()) for n in names if n):
                continue
            # Naming a variable ``arm`` is not enough. The refusal has to be
            # ABOUT a serve arm: it must name one of the arms a model is scored
            # on, or a declared arm policy. Without this the check reported an
            # ensemble's arm-ordering assertion as a serving decision.
            about_serving = any(
                _ARM_CONSTANT_RE.match(n) for n in names if n
            ) or any(
                isinstance(sub, ast.Constant)
                and isinstance(sub.value, str)
                and sub.value.lower() in _ARM_VALUES
                for sub in ast.walk(if_node.test)
            )
            if not about_serving:
                continue
            # E-079 again, for the inline shape: a refusal expressed through
            # the contract's arm data (`SERVE_ARMS.require(arm)`, or a test
            # against a policy this file took from it) is the contract's guard
            # written out; one against a local tuple is this file's.
            if self.derivation.covers(if_node):
                continue
            self._record(
                if_node, "SERVE_ARM", "if <arm> ... raise",
                "refuses an arm inline; core.served.ServeArms.require is the "
                "contract's guard and refuses an UNDECLARED arm too, which an "
                "inline test against one name does not",
                repair=serve_arm_repair(
                    self.derivation, "if <arm> ... raise", arm=None, inline=True
                ),
            )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def _parse(path: Path) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _findings_for(
    display: str, tree: ast.Module, importers: set[str] | None = None
) -> list[Finding]:
    """One module's findings, with both exemptions applied.

    Two exemptions, deliberately different in scope (E-079):

    * the five clauses that are SHAPES — a self-hash, a provenance check, a
      promotion verdict, a champion record, a router — are exempt when the FILE
      binds and uses a ``core.served`` name, directly or through one repo-local
      route. Unchanged.
    * a ``SERVE_ARM`` site is exempt when the VALUE IT DECIDES is derived from
      such a name. That is decided per site, inside the scanner, by
      :class:`ServeArmDerivation`, so a file may be silent about its promotion
      logic and named for its arm constant in the same pass.

    The narrowing is one-directional: every finding the file-scoped rule
    reported is still reported, and serve-arm sites that were silenced only by
    something else in the file are now added.
    """
    derivation = _serve_arm_derivation(tree, importers)
    findings = _ModuleScanner(display, tree, derivation).scan()
    file_exempt = _uses_contract(tree) or _uses_route(tree, importers or set())
    if file_exempt:
        findings = [f for f in findings if f.clause == SERVE_ARM_CLAUSE]
    return findings


def scan_source(source: str, display: str) -> list[Finding]:
    """Findings for one module's source, without the repo-local route.

    The route exemption is a repo-level fact (it needs the other files), so
    this lower-level entry point knows only about direct ``core.served``
    bindings. :func:`scan_tree` and :func:`scan_repo` add the route.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return _findings_for(display, tree)


def iter_repo_python_files(root: Path) -> Iterator[Path]:
    return fabrication.iter_python_files([root], skip=REPO_SKIP_DIRS)


def _is_the_contract(path: Path) -> bool:
    """The contract itself, and its own scanner, are not re-implementations."""
    parts = path.parts
    return (
        "resilient_mlkit" in parts
        and path.name in {"served.py", "served_reimplementation.py"}
    )


def scan_tree(
    root: Path, paths: Iterable[Path] | None = None
) -> tuple[list[Finding], int]:
    """Two-pass scan of a tree. Returns ``(findings, files_walked)``.

    Pass one collects the modules that import the contract — importing is what
    makes a module a genuine re-export route, so that pass stays on
    :func:`_imports_contract`. Pass two reports every file that carries a clause
    and does not USE a name it took from the contract or from one of those
    modules. The difference between the two passes is the E-035 repair: a route
    is established by import, an exemption is earned by a reference.

    Since E-079 the second pass no longer decides per FILE for every clause: a
    serve-arm site is exempted on its own derivation. See :func:`_findings_for`.
    """
    root = Path(root)
    files = list(paths) if paths is not None else list(iter_repo_python_files(root))
    files = [p for p in files if not _is_the_contract(p)]
    importers = contract_importers(root, files)

    findings: list[Finding] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        display = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        findings.extend(_findings_for(display, tree, importers))
    findings.sort(key=lambda f: (f.severity != REIMPLEMENTED, f.path, f.line))
    return findings, len(files)


def scan_repo(root: Path) -> tuple[list[Finding], int]:
    """Findings across every Python file in a repo, with the import exemption."""
    return scan_tree(Path(root))


def count_python_files(root: Path) -> int:
    return sum(1 for _ in iter_repo_python_files(Path(root)))


@dataclass(frozen=True)
class RepoSummary:
    """What one repo's scan found, in the shape the check reports."""

    files_walked: int
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def reimplemented(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == REIMPLEMENTED)

    @property
    def adjacent(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == SERVING_ADJACENT)

    @property
    def files(self) -> tuple[str, ...]:
        seen: list[str] = []
        for f in self.findings:
            if f.path not in seen:
                seen.append(f.path)
        return tuple(seen)


def summarise(root: Path) -> RepoSummary:
    findings, walked = scan_repo(Path(root))
    return RepoSummary(files_walked=walked, findings=tuple(findings))
