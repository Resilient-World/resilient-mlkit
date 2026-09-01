"""Optional standards a repo DECLARES in ``.mlkit/repo.toml``, read from git.

D3's nominal coverage level was the first standard mlkit moved out of the dict
the subject hands the check and into committed data
(``docs/ESCALATIONS.md`` E-M21), and then out of the working tree and into the
blob at HEAD (E-M23). Both moves were forced by the same finding: **a gate is
only as tied as its loosest term**, and a standard the subject supplies at
measurement time is not a standard.

D2 and E1 now need the same thing, and they need one part of it that D3 does
not. D3's level is MANDATORY -- absent, the row is NA, because there is no
second operand to compare against. The declarations read through this module
are OPTIONAL: absent, the check keeps mlkit's own built-in rule, which is the
STRICTEST setting. That difference creates an ambiguity D3 never had, and it
is the whole reason this module exists rather than three lines inlined twice::

    ArtifactRef.error  ==  "the section is not declared"   ?
                       or  "the section is declared and is not in git"  ?

Those are opposite verdicts. The first is an ordinary repo that has declared
nothing and must get mlkit's default. The second is E-M12's shape -- a standard
whose bytes are in nobody's git history, unfetchable by the reader the verdict
is quoted to -- and must be an NA naming the file. ``ArtifactRef`` alone cannot
tell them apart, because a dirty tree, an uncommitted file and an absent file
all arrive as ``error``.

So the read is two-sided:

* the COMMITTED document decides what the declaration SAYS. Nothing else may.
* the WORKING TREE decides only whether a declaration was ATTEMPTED, and it is
  never read for content. Its single job is to turn "no declaration" into
  "an uncommitted declaration" when the repo has clearly written one.

Every fallback lands on the caller's default, and the caller's default is
mlkit's own rule. A repo cannot reach a looser standard by breaking something:
a malformed working-tree config, a deleted section in a dirty tree, a config
that is not a table -- all of them come back ``declared=False`` and the check
proceeds under the built-in rule it had before this module existed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from . import artifact
from .repo import BindingError, Repo

__all__ = [
    "Declaration",
    "REPO_CONFIG_RELPATH",
    "finite_number",
    "read",
    "table_and_keys",
]

#: Where a repo's declarations live, as a repo-relative path for
#: ``core.artifact``. One constant, imported by every check that reads it --
#: ``checks/decision.py`` re-exports it under its historical name. Two spellings
#: of the same path is how two checks come to disagree about which file is the
#: standard.
REPO_CONFIG_RELPATH = ".mlkit/repo.toml"


@dataclass(frozen=True)
class Declaration:
    """One optional ``[section]`` of ``.mlkit/repo.toml``, or the absence of one.

    Exactly one of three states, and the caller must handle all three:

    * ``uncommitted`` -- a declaration was attempted and is not in git. NA.
    * ``declared`` -- ``value`` is whatever the COMMITTED document holds under
      this section. It is deliberately un-typed here: validating it is the
      check's job, because only the check knows what its own section means.
    * neither -- nothing was declared. The caller applies mlkit's default.

    ``value`` is only ever the committed document's, never the working tree's,
    except under the ``--allow-dirty`` escape hatch -- and then ``allow_dirty``
    is set, ``CheckResult.__post_init__`` refuses any PASS carrying it, and
    ``portfolio.resolve`` refuses everything else.
    """

    section: str
    value: Any = None
    declared: bool = False
    uncommitted: bool = False
    #: Why it is uncommitted; empty otherwise. Reason text for the caller's NA.
    detail: str = ""
    allow_dirty: bool = False
    #: sha256 of the blob the declaration was read out of, so a verdict can
    #: quote the bytes that set its standard rather than only the path.
    blob_sha256: str = ""
    #: The linked worktree that answered, "" for the repo's own checkout.
    worktree: str = ""

    @property
    def source(self) -> str:
        """Human-readable provenance for the evidence dict."""
        where = f"{REPO_CONFIG_RELPATH}@{self.blob_sha256[:12]}" if self.blob_sha256 else REPO_CONFIG_RELPATH
        return f"{where} ({self.worktree})" if self.worktree else where


def _attempted_in_working_tree(repo: Repo, section: str) -> bool:
    """Did this repo WRITE a ``[section]`` into its working-tree config?

    Presence only. The value is never read, so nothing a repo puts on disk can
    reach a verdict through this function -- it can only ever convert a silent
    default into a refusal, which is the strict direction.

    A malformed working-tree config answers False rather than raising. That is
    deliberate and it is safe in one direction only: the committed read is
    still authoritative, and if the tree is malformed it is also dirty, so
    ``artifact.load`` has already refused. The alternative -- letting
    ``BindingError`` escape -- takes the whole run down over a file the check
    was only glancing at, which is the defect
    ``test_positive_control_a_binding_corrupting_the_config_mid_run_raises_nothing``
    pins for D3.
    """
    try:
        config = repo.config()
    except BindingError:
        return False
    return isinstance(config, dict) and section in config


def read(repo: Repo, section: str, *, allow_dirty: bool = False) -> Declaration:
    """The committed ``[section]`` of ``.mlkit/repo.toml``, or its honest absence."""
    attempted = _attempted_in_working_tree(repo, section)
    ref = artifact.load(repo, REPO_CONFIG_RELPATH, allow_dirty=allow_dirty)

    if ref.error:
        if attempted:
            return Declaration(
                section,
                uncommitted=True,
                detail=(
                    f"[{section}] is declared in the working tree and could not be "
                    f"read from committed state -- {ref.error}"
                ),
            )
        return Declaration(section)

    document = ref.document if isinstance(ref.document, dict) else {}
    if section not in document:
        if attempted:
            return Declaration(
                section,
                uncommitted=True,
                detail=(
                    f"[{section}] is present in the working tree of {repo.path} and "
                    f"absent from {ref.branch or 'HEAD'}:{REPO_CONFIG_RELPATH} "
                    f"({ref.git_sha[:12]})"
                ),
            )
        # Nothing declared anywhere. No verdict rests on these bytes, so no
        # marker rides out: an undeclared repo is exactly as it was before this
        # module existed, under every flag.
        return Declaration(section)

    return Declaration(
        section,
        value=document[section],
        declared=True,
        allow_dirty=ref.allow_dirty_read,
        blob_sha256=ref.sha256,
        worktree=ref.worktree,
    )


# -- shape refusals, shared by every check that reads a declaration ---------
#
# Both live here rather than in the two checks because a section validated two
# slightly different ways is two definitions of "declared", which is the same
# as none -- the argument CLAUDE.md rule 7 makes about the gates themselves,
# one level down.


def table_and_keys(decl: Declaration, allowed: frozenset[str]) -> str:
    """"" when the section is a table whose every key is known; else a refusal.

    ``[[placebo]]`` parses to a LIST, and ``.get`` on a list raises -- the shape
    ``test_a_coverage_section_that_is_not_a_table_is_NA_not_a_pass`` found for
    D3 by attacking the fix rather than by reading it. Every malformed shape a
    repo can write has to land on a refusal and never on a pass, and it has to
    do it without raising out of the check.

    Unknown keys are refused rather than ignored. Both fallbacks in this module
    are toward mlkit's strictest rule, so a typo cannot loosen anything -- which
    is exactly why it must not pass silently: a repo that wrote ``indict`` and
    believes it declared ``indicts`` is measuring under a rule it did not
    choose, and would read the resulting PASS as its own.
    """
    if not isinstance(decl.value, dict):
        kind = (
            "an array of tables"
            if isinstance(decl.value, list)
            else f"a {type(decl.value).__name__}"
        )
        return (
            f"[{decl.section}] in {REPO_CONFIG_RELPATH} is {kind}, not a table; "
            f"write it as `[{decl.section}]` with one key per line"
        )
    unknown = sorted(str(key) for key in decl.value if key not in allowed)
    if unknown:
        return (
            f"[{decl.section}] declares unknown key(s) {', '.join(unknown)}; the known "
            f"keys are {', '.join(sorted(allowed))}. A key mlkit does not read is a "
            "declaration you believe you made and did not"
        )
    return ""


def finite_number(value: Any, label: str) -> tuple[float | None, str]:
    """``(number, "")`` or ``(None, refusal)``. Refuses ``bool`` and non-finite.

    ``bool`` is an ``int`` in Python, so ``true`` reaches ``float()`` as a
    perfectly valid ``1.0`` -- a figure nobody wrote. And ``float()`` accepts
    NaN and the infinities, including as the strings ``"nan"``/``"inf"``, which
    is the defect class ``docs/ESCALATIONS.md`` E-M09/E-M10 record: every
    comparison a NaN takes part in is False, so a threshold set to NaN is the
    loosest threshold there is. Both are refused on TYPE, before the value is
    reasoned about.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f"{label} is a {type(value).__name__}, not a number"
    number = float(value)
    if not math.isfinite(number):
        return None, f"{label} is {number!r}, which is not a finite number"
    return number, ""
