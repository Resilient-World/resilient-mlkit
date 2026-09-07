"""resilient-mlkit — the one measurement and gating tool for the portfolio.

Built once, imported everywhere. Never reimplemented per repo: eight
divergent copies of a gate is eight different definitions of "ready", which is
the same as having none.
"""

from .core.arming import ArmState, arm_state
from .core.identity import (
    BuildIdentity,
    IdentityMatch,
    build_identity,
    verify_report,
    verify_report_text,
)
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
#: BUMPED 1.3.0 -> 1.4.0 on 2026-09-06 (E-M40): `core.contention` and the
#: `resilient_mlkit.pytest_contention` plugin are new surface -- minor by this
#: file's own scale. No existing check's predicate moved, and the plugin is
#: opt-in (no `pytest11` entry point), so a consumer that upgrades the pin and
#: changes nothing else sees no verdict move at all.
#: BUMPED 1.4.0 -> 2.0.0 on 2026-09-07 (E-M41): R10 changes verdict on
#: UNCHANGED repo code, which this file's scale calls MAJOR and which is taken
#: as one rather than argued down. Measured, not predicted:
#: `resilient-chokepoint` `5f78fe4c` moves **R10 NA -> PASS**, because its one
#: finding stood at `fetch`, a name that entered the metric registry only
#: because `self.cache_dir / f"{key}.json"` is a `BinOp(Div)`. `resilient-arabica`
#: `2a65d9a5` moves NA(10) -> NA(9) and `resilient-torrent` `dc6e577a` FAIL(8)
#: -> FAIL(7), both by the same class of repair; `resilient-fray` `cc8f4355` is
#: unmoved at PASS. NO row that mlkit's own vocabulary adjudicates moved
#: anywhere: zero added, zero removed, zero changed across all four.
#: BUMPED 2.0.0 -> 2.1.0 on 2026-09-07 (E-M42): MINOR, decided by measurement
#: and not by preference. The identity repair on its own is a patch -- a defect
#: fixed, no verdict moved -- but two REPORT SURFACES change, which this file's
#: scale calls minor: `core.report.guarded_write` gains a machine-path refusal
#: (`<report>.NAMES_A_MACHINE.md`), and R10's report gains the line `files under
#: a declared tree the derivation could not READ: N` that E-038's lost verify
#: commit added. Driven over all EIGHT adopter remote mains, five phases each,
#: before and after: **272 adjudicated rows, 0 added, 0 removed, 0 status
#: moved**, and the only text that moved anywhere is that one line, reading `0`
#: on every repo. It is not a major because no check's verdict moves; the
#: version rule was fixed in `reports/E_M42_REPORT_HEADER_PREREGISTRATION.md`
#: §6 before the drive, with the major clause written out in case it did.
#: BUMPED 2.1.0 -> 2.2.0 on 2026-09-07 (E-M43): MINOR. A CLI SURFACE changes and
#: no check is touched. `mlkit allowlist verify` now exits non-zero on an
#: UNSIGNED allowlist and on an invocation that matched NO repository -- two
#: verdicts it already printed and whose exit status was 0, so a CI step gating
#: on the return code passed an unratified licence position, and passed a run
#: that had read nothing. `mlkit notice` returns 1 when it REFUSED to write a
#: NOTICE.md, and `mlkit keys` refuses to describe a portfolio it did not read.
#: Driven over all EIGHT adopter remote mains, five phases each, before and
#: after: **272 rows, 0 added, 0 removed, 0 status moved, 0 reasons moved** --
#: preregistered as zero movement, because an exit code is not a verdict.
#: BUMPED 2.2.0 -> 3.0.0 on 2026-09-07 (E-M44): MAJOR, by this file's own scale
#: and taken as one rather than argued down -- an existing check changes verdict
#: on UNCHANGED repo code. R9 owns two licence obligations and returned on the
#: first, so the NOTICE.md attribution leg was unreachable on any repo with a
#: manifest finding. Measured over all eight adopter remote mains, five phases
#: each, before and after: **272 rows, 0 added, 0 removed, 3 STATUS moved,
#: 2 reason moved**, and every one of the five is a repo whose committed
#: NOTICE.md does not discharge obligations its own signed allowlist records.
#: `resilient-torrent` NA -> FAIL (10 missing attribution sections),
#: `resilient-triage` NA -> FAIL (10), `resilient-blackout` NA -> FAIL (5);
#: `resilient-surge` FAIL -> FAIL with 12 named, `resilient-arabica`
#: FAIL -> FAIL with the drift named. choco, fray and chokepoint do not move:
#: their NOTICE.md is current. No row moved anywhere else, and R8 -- the row
#: that writes the report R9's reason lands in -- did not move on any repo.
__version__ = "3.0.0"

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
    # M-1. The CredentialRequired discipline for bytes: raised by a binding
    # that resolved its declaration and cannot read the input it is declared
    # over; rendered UNMEASURABLE, never FAIL and never NA.
    "InputUnavailable",
    "PrematureInputRefusal",
    "Status",
    "VerdictSealed",
    "__build__",
    "__version__",
    "arm_state",
    "build_identity",
    "verify_report",
    "verify_report_text",
]
