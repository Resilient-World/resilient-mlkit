"""Reading a number out of a repo's committed artifact, and refusing to guess one.

This module is the mechanical half of ``mlkit portfolio``. It does three things
and deliberately nothing else:

* locate a repo-relative artifact, hash it, and say whether the bytes it hashed
  are the bytes git has at HEAD;
* resolve a declared pointer into the parsed document;
* return, for every field, either a value that came out of that document or an
  NA carrying the reason it could not.

THE INVARIANT
-------------
There is no code path here that produces a value from anything but a file on
disk. A pointer that does not resolve yields ``Cell.missing(...)``, never a
default, never a zero, never the previous repo's value. That is the whole point:
``portfolio/MODEL_QUALITY.md`` was hand-transcribed, and a transcription error
in a table of eight repos is invisible because nothing else in the tree carries
the same number to disagree with it.

WORKTREES
---------
Artifacts are looked for in the repo's own checkout first. Several repos in this
portfolio keep the branch that carries their measurements in a linked worktree
(``git worktree list``) rather than at the root checkout -- resilient-surge's
model registry lives on ``feat/surgeistm-lora-finetune`` under ``.worktrees/``,
not on the branch its root has checked out. Reporting "artifact absent" for
those would be true of the checkout and misleading about the repo, so the
resolver falls back to linked worktrees and records WHICH tree answered. A row
sourced from a worktree is flagged; it is evidence about that worktree, not
about the repo's checked-out branch.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .repo import Repo

#: Marker for "this pointer did not resolve". Distinct from None, which is a
#: legitimate JSON value a pointer may legitimately land on.
_UNRESOLVED = object()


@dataclass(frozen=True)
class Cell:
    """One measured value, or one NA with the reason it is NA.

    A Cell is never both and never neither. ``source`` records the pointer the
    value came out of so a reader can go and look at the same bytes.
    """

    value: Any = None
    na_reason: str = ""
    source: str = ""

    @property
    def present(self) -> bool:
        return not self.na_reason

    @classmethod
    def measured(cls, value: Any, source: str) -> Cell:
        return cls(value=value, source=source)

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
        }


@dataclass
class ArtifactRef:
    """One artifact file, located and hashed, with its git standing recorded."""

    repo: str
    relpath: str
    #: Absolute path actually read, or None when nothing was found anywhere.
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
    #: Parse failure, or "artifact not found ..." when nothing was located.
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


def _hash(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _git_standing(tree: Path, relpath: str, disk_sha: str) -> tuple[bool, bool, str, str]:
    """(committed_at_head, dirty, branch, sha) for ``relpath`` inside ``tree``."""
    _, branch = _git(tree, "rev-parse", "--abbrev-ref", "HEAD")
    _, sha = _git(tree, "rev-parse", "HEAD")
    code, blob = _git(tree, "rev-parse", f"HEAD:{relpath}")
    if code != 0 or not blob:
        return False, False, branch, sha
    # Compare the committed blob's own sha256 against what we hashed on disk.
    out = subprocess.run(
        ["git", "-C", str(tree), "cat-file", "blob", blob],
        capture_output=True,
        check=False,
    )
    committed_sha = hashlib.sha256(out.stdout).hexdigest() if out.returncode == 0 else ""
    return True, bool(committed_sha and committed_sha != disk_sha), branch, sha


def load(repo: Repo, relpath: str) -> ArtifactRef:
    """Locate, hash and parse one repo-relative artifact.

    The repo's own checkout is tried first; linked worktrees are tried only if
    it is absent there, and the answering worktree is recorded on the result.
    """
    ref = ArtifactRef(repo=repo.name, relpath=relpath)
    candidates: list[tuple[Path, str]] = [(repo.path, "")]
    candidates += [(w, str(w)) for w in linked_worktrees(repo)]

    for tree, marker in candidates:
        path = tree / relpath
        if not path.is_file():
            continue
        try:
            sha, size = _hash(path)
        except OSError as exc:
            ref.error = f"unreadable: {exc}"
            ref.path = path
            return ref
        ref.path = path
        ref.sha256 = sha
        ref.bytes_ = size
        ref.worktree = marker
        ref.committed_at_head, ref.dirty, ref.branch, ref.git_sha = _git_standing(
            tree, relpath, sha
        )
        try:
            ref.document = _parse(path)
        except Exception as exc:  # noqa: BLE001 - any parse failure is the same finding
            ref.error = f"{type(exc).__name__}: {exc}"
        return ref

    searched = ", ".join(str(t) for t, _ in candidates)
    ref.error = (
        f"artifact not found at {relpath} in the checkout or any linked worktree "
        f"(searched {len(candidates)} tree(s): {searched})"
    )
    return ref


def _parse(path: Path) -> Any:
    """JSON, or a list of records for ``.jsonl``.

    JSONL is here because two repos record their test-arm ledger that way, and
    a ledger's value is entirely in its line count.
    """
    text = path.read_text(errors="strict")
    if path.suffix == ".jsonl":
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
