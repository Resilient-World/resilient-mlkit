"""resilient-mlkit — the one measurement and gating tool for the portfolio.

Built once, imported everywhere. Never reimplemented per repo: eight
divergent copies of a gate is eight different definitions of "ready", which is
the same as having none.
"""

from .core.identity import (
    BuildIdentity,
    IdentityMatch,
    build_identity,
    verify_report,
    verify_report_text,
)
from .core.arming import ArmState, arm_state
from .core.result import (
    CheckResult,
    CredentialRequired,
    GateAggregate,
    GateAggregateError,
    InputUnavailable,
    PrematureInputRefusal,
    Status,
    VerdictSealed,
)

#: The single declaration of this package's version.
#:
#: It was three declarations until E-M08: ``pyproject.toml``, this module and
#: ``cli.__version__`` each carried their own literal, and the ``v0.3.0`` tag
#: was cut with all three still reading ``0.2.0``. Three copies of a fact is
#: three chances for it to be wrong and no way to tell which one is. Here is
#: the copy: ``pyproject.toml`` reads it through ``[tool.setuptools.dynamic]``
#: and ``cli`` imports it, so a bump is one edit and a mismatch is
#: unconstructible rather than merely discouraged.
#: BUMPED 0.5.0 -> 0.6.0 for a reason this comment must outlive: `v0.5.0` was
#: cut at `8517341` and `main` reached `6921e9a` 36 commits and +5438/-97 later
#: with this literal unmoved on both sides and `git diff v0.5.0..HEAD --
#: CHANGELOG.md` empty. chokepoint pins `8517341` and fray pins `c65b2e7`; all
#: three trees stamped `"mlkit_version": "0.5.0"` into every artifact they
#: wrote, across a span in which D3, R11 and `core.served.challenger_decision`
#: all change verdict on unchanged repo code. A version that cannot separate
#: two instruments is not naming one. `tests/test_tag_distance.py` fires on
#: that state, so it cannot recur unseen; cutting the tag stays the
#: signatory's, and this literal is not one.
#: BUMPED 0.6.0 -> 0.7.0 on 2026-09-04 (plan v3 M-1): a seventh terminal
#: status is a CLI-surface change, which CHANGELOG.md's own scale calls minor.
#: Neither v0.6.0 nor v0.7.0 is tagged; the tag stays the signatory's.
__version__ = "0.7.0"

#: The version is NOT the identity, and E-M24 is the measurement that says so:
#: fray runs mlkit ``c65b2e7`` and mlkit main is ``6921e9a`` -- 40 commits, 9
#: source files, ``+50/-5`` in ``checks/readiness.py`` and ``+373/-13`` in
#: ``core/served.py`` -- and both trees declare exactly the string above. A
#: number the signatory cuts at release time cannot move when gate semantics
#: move between releases, and it must not be made to: tag cutting is theirs.
#:
#: So the identity lives HERE, beside it, and is measured rather than declared
#: -- a length-framed sha256 over the files the running package was loaded
#: from. It moves iff the shipped source moves. ``resilient_mlkit.__build__``
#: is the token that goes into every report header mlkit writes; see
#: ``core/identity.py`` and ``docs/BUILD_IDENTITY.md``.
#:
#: Resolved through ``__getattr__`` (PEP 562) rather than assigned here, so
#: that importing mlkit does not walk its own package tree until something
#: actually asks for the identity.


def __getattr__(name: str) -> object:
    if name == "__build__":
        return build_identity().stamp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # M-1. The one definition of armed / halt_required / indicted an adopter's
    # hard-stops module renders; torrent and chokepoint each typed their own.
    "ArmState",
    "BuildIdentity",
    "CheckResult",
    "CredentialRequired",
    # M-1. The CredentialRequired discipline for bytes: raised by a binding
    # that resolved its declaration and cannot read the input it is declared
    # over; rendered UNMEASURABLE, never FAIL and never NA.
    "InputUnavailable",
    "PrematureInputRefusal",
    "arm_state",
    # The gate verdict an adopter must NOT hand-roll. Exported at the top level
    # because the alternative -- a repo writing its own -- is the measured
    # defect it exists to retire (fray promotion_gate.py:401/:851).
    "GateAggregate",
    "GateAggregateError",
    # The adopter-side half of E-M24: given a report, which mlkit wrote it, and
    # is that the mlkit installed here? Exported at the top level for the same
    # reason GateAggregate is -- the alternative is eight repos each deciding
    # for themselves what "the same instrument" means.
    "IdentityMatch",
    "Status",
    "VerdictSealed",
    "__build__",
    "__version__",
    "build_identity",
    "verify_report",
    "verify_report_text",
]
