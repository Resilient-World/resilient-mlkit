"""Reading a number out of a repo's committed artifact, and refusing to guess one.

This module is the mechanical half of ``mlkit portfolio``. It does three things
and deliberately nothing else:

* locate a repo-relative artifact IN GIT, hash the committed blob, and record
  which tree and which HEAD answered;
* resolve a declared pointer into the parsed document;
* return, for every field, either a value that came out of that document or an
  NA carrying the reason it could not.

THE INVARIANT
-------------
There is no code path here that produces a value from anything but a blob git
has at HEAD. A pointer that does not resolve yields ``Cell.missing(...)``,
never a default, never a zero, never the previous repo's value. That is the
whole point: ``portfolio/MODEL_QUALITY.md`` was hand-transcribed, and a
transcription error in a table of eight repos is invisible because nothing else
in the tree carries the same number to disagree with it.

COMMITTED READS, AND WHY DISCLOSURE WAS NOT ENOUGH
--------------------------------------------------
This module used to ``path.read_bytes()`` from the working tree and then RECORD
whether git agreed -- ``committed_at_head`` and ``dirty`` were computed, put on
the ref, and rendered in ``fleet.provenance_block``'s own column. That is
disclosure, and ``docs/ESCALATIONS.md`` E-M12 is what disclosure bought: the
``choco`` row of ``portfolio/FLEET_VERDICTS.md`` -- candidate, score, split,
baseline score, test-arm-spent -- was read out of
``models/observed_production_head.meta.json``, a file committed on NO ref at all
(``git log --all`` empty, ``.gitignore:82:/models/*``) and present only in that
clone's working tree. The provenance column said ``NO`` and the score column
said a number, and a reader who read left to right had already believed the
number before reaching the qualification.

So the bytes now come from ``git cat-file blob HEAD:<relpath>``, and the two
recorded facts become the INPUT TO A REFUSAL rather than a footnote to a figure:

1. committed at HEAD and clean -> the HEAD blob is hashed, parsed and served.
   Byte-identical to what the old path returned for this, the ordinary case.
2. present in the working tree but absent at HEAD, or present at HEAD and
   differing from the working tree -> ``ArtifactRef.error`` names the defect
   class and the file (``not committed at HEAD: <relpath>``), the document is
   never parsed, and every cell downstream is an NA carrying that reason.

The dirty case is refused rather than quietly served from HEAD. Serving HEAD
there would be reproducible and wrong in a subtler way: the table would quote a
figure that the operator generating it is, at that moment, editing away from.

THE ESCAPE HATCH, AND WHY IT CANNOT ESCAPE
------------------------------------------
``load(repo, relpath, allow_dirty=True)`` reads the working tree, because
diagnosing an artifact you have not committed yet is a real need and refusing it
would just push people back to ``cat``. What it may not do is reach a verdict.
The ref is marked ``allow_dirty_read``; the mark propagates to every ``Cell``
derived from it, and to ``CheckResult.evidence[ALLOW_DIRTY_KEY]``; and the three
paths that emit a verdict -- ``CheckResult.__post_init__`` for PASS,
``portfolio.resolve()``, and ``fleet``'s table and ``to_dict`` emission --
raise ``UncommittedRead`` on it. An allow-dirty number is usable in a terminal
and structurally unable to land in a row. ``tests/test_committed_reads.py``
holds all five halves of that claim; the comment you are reading is not the
enforcement.

WORKTREES
---------
Artifacts are looked for at the repo's own checkout's HEAD first. Several repos in this
portfolio keep the branch that carries their measurements in a linked worktree
(``git worktree list``) rather than at the root checkout -- resilient-surge's
model registry lives on ``feat/surgeistm-lora-finetune`` under ``.worktrees/``,
not on the branch its root has checked out. Reporting "artifact absent" for
those would be true of the checkout and misleading about the repo, so the
resolver falls back to linked worktrees and records WHICH tree answered. A row
sourced from a worktree is flagged; it is evidence about that worktree, not
about the repo's checked-out branch.

The search runs in two passes, and the order matters. The first pass asks every
tree for a COMMITTED blob and takes the first that has one; only if no tree has
it committed does the second pass look on disk, and everything the second pass
finds is refused (or, under ``allow_dirty``, marked). Doing it in one pass would
let an uncommitted file in the root checkout shadow a properly committed copy in
a linked worktree -- refusing a figure that is in git because a stale copy of it
is not.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .repo import Repo
from .result import ALLOW_DIRTY_KEY, UncommittedRead

__all__ = [
    "ALLOW_DIRTY_KEY",
    "ArtifactRef",
    "Cell",
    "UncommittedRead",
    "linked_worktrees",
    "load",
    "refuse_uncommitted",
    "resolve_pointer",
    "unresolved",
]

#: Marker for "this pointer did not resolve". Distinct from None, which is a
#: legitimate JSON value a pointer may legitimately land on.
_UNRESOLVED = object()

#: The one phrase every refusal in this module contains. Callers and controls
#: match on it, so it is a constant rather than five hand-typed strings that
#: drift apart. It names the defect CLASS -- E-M12's -- not the incident.
NOT_COMMITTED = "not committed at HEAD"


@dataclass(frozen=True)
class Cell:
    """One measured value, or one NA with the reason it is NA.

    A Cell is never both and never neither. ``source`` records the pointer the
    value came out of so a reader can go and look at the same bytes.
    """

    value: Any = None
    na_reason: str = ""
    source: str = ""
    #: True when this value descends from an ``allow_dirty`` read of the working
    #: tree. Carried on the Cell rather than looked up from the ref, because by
    #: the time a table is rendered the ref is three call frames away and the
    #: thing being printed is this. Every verdict-emitting path refuses it.
    allow_dirty: bool = False

    @property
    def present(self) -> bool:
        return not self.na_reason

    @classmethod
    def measured(cls, value: Any, source: str, *, allow_dirty: bool = False) -> Cell:
        return cls(value=value, source=source, allow_dirty=allow_dirty)

    @classmethod
    def missing(cls, reason: str, source: str = "") -> Cell:
        if not reason.strip():
            raise ValueError(
                "Cell.missing requires a reason. An unexplained NA looks like "
                "coverage and carries no information -- the exact failure this "
                "table exists to remove."
            )
        return cls(value=None, na_reason=reason, source=source)

    def render(self, *, digits: int | None = None) -> str:
        """Text for a table cell. NA always shows its reason, never a bare dash."""
        if not self.present:
            return f"NA ({self.na_reason})"
        if isinstance(self.value, bool):
            return "yes" if self.value else "no"
        if isinstance(self.value, float) and digits is not None:
            return f"{self.value:.{digits}f}"
        return str(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "na_reason": self.na_reason or None,
            "source": self.source or None,
            ALLOW_DIRTY_KEY: self.allow_dirty,
        }


@dataclass
class ArtifactRef:
    """One artifact file, located and hashed, with its git standing recorded."""

    repo: str
    relpath: str
    #: Absolute path the bytes correspond to, or None when nothing was found
    #: anywhere. Committed reads do not open it -- it is where a reader would
    #: look, not where these bytes came from; ``read_from`` says that.
    path: Path | None = None
    #: sha256 of the bytes read. Empty when the file was not found.
    sha256: str = ""
    bytes_: int = 0
    #: "" for the repo's own checkout, else the worktree path that answered.
    worktree: str = ""
    #: Branch and SHA of whichever tree answered.
    branch: str = ""
    git_sha: str = ""
    #: True when git has this path at that tree's HEAD.
    committed_at_head: bool = False
    #: True when the working-tree bytes differ from the HEAD blob.
    dirty: bool = False
    #: "HEAD" when the bytes are a committed blob, "working tree" when they came
    #: off disk under ``allow_dirty``, "" when nothing was read.
    read_from: str = ""
    #: True when these bytes came off disk under the ``allow_dirty`` escape
    #: hatch. Structural: every verdict path refuses a ref carrying it.
    allow_dirty_read: bool = False
    #: Parse failure, the committed-read refusal, or "artifact not found ..."
    #: when nothing was located in any tree.
    error: str = ""
    document: Any = field(default=None, repr=False)

    @property
    def found(self) -> bool:
        return self.path is not None and not self.error

    @property
    def off_checkout(self) -> bool:
        return bool(self.worktree)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "relpath": self.relpath,
            "path": str(self.path) if self.path else None,
            "sha256": self.sha256 or None,
            "bytes": self.bytes_ or None,
            "worktree": self.worktree or None,
            "branch": self.branch or None,
            "git_sha": self.git_sha or None,
            "committed_at_head": self.committed_at_head,
            "dirty": self.dirty,
            "read_from": self.read_from or None,
            ALLOW_DIRTY_KEY: self.allow_dirty_read,
            "error": self.error or None,
        }


def _git(cwd: Path, *args: str) -> tuple[int, str]:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
    )
    return out.returncode, out.stdout.strip()


def linked_worktrees(repo: Repo) -> list[Path]:
    """Every linked worktree of ``repo``, excluding the root checkout itself."""
    code, out = _git(repo.path, "worktree", "list", "--porcelain")
    if code != 0:
        return []
    root = repo.path.resolve()
    found: list[Path] = []
    for line in out.splitlines():
        if not line.startswith("worktree "):
            continue
        candidate = Path(line[len("worktree ") :]).resolve()
        if candidate != root:
            found.append(candidate)
    return found


def _hash(data: bytes) -> tuple[str, int]:
    return hashlib.sha256(data).hexdigest(), len(data)


def _head_blob(tree: Path, relpath: str) -> bytes | None:
    """The committed bytes of ``relpath`` at ``tree``'s HEAD, or None.

    None means git has no such path at HEAD -- the E-M12 case. It does NOT mean
    the file is absent from disk, and the two must not be conflated: a file that
    is on disk and on no ref is precisely the shape this module now refuses.
    """
    code, blob = _git(tree, "rev-parse", "--verify", "--quiet", f"HEAD:{relpath}")
    if code != 0 or not blob:
        return None
    out = subprocess.run(
        ["git", "-C", str(tree), "cat-file", "blob", blob],
        capture_output=True,
        check=False,
    )
    return out.stdout if out.returncode == 0 else None


def _git_standing(tree: Path, relpath: str, head_bytes: bytes | None) -> tuple[bool, bool, str, str]:
    """(committed_at_head, dirty, branch, sha) for ``relpath`` inside ``tree``.

    Retained verbatim in intent from before committed reads: the two booleans are
    still measured the same way. What changed is what they are FOR. They used to
    be disclosure printed beside a number that had already been served; they are
    now the input to the decision of whether a number is served at all.
    """
    _, branch = _git(tree, "rev-parse", "--abbrev-ref", "HEAD")
    _, sha = _git(tree, "rev-parse", "HEAD")
    if head_bytes is None:
        return False, False, branch, sha
    path = tree / relpath
    try:
        disk = path.read_bytes()
    except OSError:
        # Committed but not checked out (sparse checkout, or deleted in the
        # working tree). The commit is what we quote, so this is not dirty.
        return True, False, branch, sha
    return True, disk != head_bytes, branch, sha


def load(repo: Repo, relpath: str, *, allow_dirty: bool = False) -> ArtifactRef:
    """Locate, hash and parse one repo-relative artifact FROM COMMITTED STATE.

    Two passes. The first asks each tree -- the repo's own checkout, then each
    linked worktree -- for ``HEAD:<relpath>``, and the first tree that has it
    committed answers. Only if no tree has it committed does the second pass
    look on disk, and what it finds is refused with ``NOT_COMMITTED`` in the
    reason unless ``allow_dirty`` is set.

    ``allow_dirty=True`` reads the working tree for local diagnosis and marks
    the ref ``allow_dirty_read``. Verdict paths refuse a marked ref; see this
    module's docstring and ``core.result.UncommittedRead``.
    """
    ref = ArtifactRef(repo=repo.name, relpath=relpath)
    candidates: list[tuple[Path, str]] = [(repo.path, "")]
    candidates += [(w, str(w)) for w in linked_worktrees(repo)]

    # -- pass 1: the committed answer, wherever it lives ------------------
    for tree, marker in candidates:
        head_bytes = _head_blob(tree, relpath)
        if head_bytes is None:
            continue
        ref.path = tree / relpath
        ref.worktree = marker
        ref.read_from = "HEAD"
        ref.committed_at_head, ref.dirty, ref.branch, ref.git_sha = _git_standing(
            tree, relpath, head_bytes
        )
        if ref.dirty and not allow_dirty:
            ref.error = (
                f"{NOT_COMMITTED}: {relpath} — the working tree differs from the "
                f"blob at {ref.branch} {ref.git_sha[:12]}, so there are two "
                "candidate answers and this reader will not choose between them. "
                "Commit the artifact, or pass --allow-dirty for a diagnosis that "
                "cannot reach a verdict"
            )
            return ref
        if ref.dirty and allow_dirty:
            return _read_working_tree(ref, tree / relpath, relpath)
        ref.sha256, ref.bytes_ = _hash(head_bytes)
        try:
            ref.document = _parse(head_bytes, relpath)
        except Exception as exc:  # noqa: BLE001 - any parse failure is the same finding
            ref.error = f"{type(exc).__name__}: {exc}"
        return ref

    # -- pass 2: on disk and on no ref. The E-M12 shape. -------------------
    for tree, marker in candidates:
        path = tree / relpath
        if not path.is_file():
            continue
        ref.path = path
        ref.worktree = marker
        ref.committed_at_head = False
        ref.dirty = False
        _, ref.branch = _git(tree, "rev-parse", "--abbrev-ref", "HEAD")
        _, ref.git_sha = _git(tree, "rev-parse", "HEAD")
        if not allow_dirty:
            ref.error = (
                f"{NOT_COMMITTED}: {relpath} — present in the working tree of "
                f"{tree} ({path.stat().st_size} bytes) and absent from "
                f"{ref.branch or 'HEAD'}. A figure read from it can be quoted and "
                "cannot be fetched by the reader it is quoted to "
                "(docs/ESCALATIONS.md E-M12)"
            )
            return ref
        return _read_working_tree(ref, path, relpath)

    searched = ", ".join(str(t) for t, _ in candidates)
    ref.error = (
        f"artifact not found at {relpath} in the checkout or any linked worktree "
        f"(searched {len(candidates)} tree(s): {searched})"
    )
    return ref


def _read_working_tree(ref: ArtifactRef, path: Path, relpath: str) -> ArtifactRef:
    """The escape hatch's read. Marked at the point the bytes are taken."""
    ref.read_from = "working tree"
    ref.allow_dirty_read = True
    try:
        data = path.read_bytes()
    except OSError as exc:
        ref.error = f"unreadable: {exc}"
        return ref
    ref.sha256, ref.bytes_ = _hash(data)
    try:
        ref.document = _parse(data, relpath)
    except Exception as exc:  # noqa: BLE001 - any parse failure is the same finding
        ref.error = f"{type(exc).__name__}: {exc}"
    return ref


def refuse_uncommitted(marked: bool, what: str) -> None:
    """Raise if ``marked``. One sentence, one place, so every path says it alike.

    ``what`` names the thing being refused, e.g. ``"check S3 of resilient-fray"``
    or ``"the fleet verdict row choco"``. The precedent is
    ``scripts/verify_served_hash_parity.py``, which exits non-zero when there was
    nothing to verify: a green report over nothing is the defect, so the tool
    refuses rather than reporting.
    """
    if not marked:
        return
    raise UncommittedRead(
        f"{what} descends from an --allow-dirty read of the working tree. That "
        "escape hatch exists for local diagnosis and may not reach a verdict: "
        "the bytes behind this number are in nobody's git history, so no reader "
        "can fetch what it claims. Commit the artifact and re-measure."
    )


def _parse(data: bytes, relpath: str) -> Any:
    """JSON, or a list of records for ``.jsonl``.

    Takes BYTES rather than a path, because after committed reads the bytes are
    a git blob and there may be no file on disk carrying them. JSONL is here
    because two repos record their test-arm ledger that way, and a ledger's
    value is entirely in its line count.
    """
    text = data.decode("utf-8", errors="strict")
    if relpath.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Walk a dotted pointer. Numeric segments index lists.

    Returns ``_UNRESOLVED`` rather than raising, so the caller can turn a miss
    into an NA carrying the pointer that missed.
    """
    if pointer == "":
        return document
    current = document
    for segment in pointer.split("."):
        if isinstance(current, list):
            if not segment.lstrip("-").isdigit():
                return _UNRESOLVED
            index = int(segment)
            if not -len(current) <= index < len(current):
                return _UNRESOLVED
            current = current[index]
            continue
        if isinstance(current, dict):
            if segment not in current:
                return _UNRESOLVED
            current = current[segment]
            continue
        return _UNRESOLVED
    return current


def unresolved(value: Any) -> bool:
    return value is _UNRESOLVED
