"""The merged tree, built without touching a branch; and ancestry, asked of git.

WHY THIS EXISTS (plan v3 M-3)
-----------------------------
Three defects this week existed ONLY in the combination of individually
correct changes, and a person found each one by constructing the merged tree
and driving it by hand:

* torrent E-069 -- ``src/torrent/mlops/hard_stops.py:48`` at ``cec1c48`` quoted
  a D2 clause that was TRUE on its own branch's CLAUDE.md. S-5 reached ``main``
  through #178 and never reached that branch. On the merged tree the sentence
  was stale. "No single-PR review could see it; only a merged-tree drive."
* chokepoint #122 -- editing ``.mlkit/repo.toml`` moved the sha256 the S-5
  register pinned; rc 0 on the branch, 1 on the merged tree.
* the stacked-merge trap, three times -- PRs based on a feature branch
  reported MERGED while ``main`` was unchanged. "MERGED is a status word, not a
  fact about main"; the fact is ``git merge-base --is-ancestor``.

WHAT IT DOES AND REFUSES
------------------------
:func:`build` asks git for the merge of HEAD with a base ref as a TREE
(``git merge-tree --write-tree``, git >= 2.38) and wraps it in a synthetic
commit with both parents (``git commit-tree``). No branch moves, no index is
touched, nothing is written into the working tree. A conflict is a
:class:`MergeConflict` naming the paths, and it is REFUSED: this module never
resolves one, with any strategy, because the standing rule this fleet paid for
is "never whole-file --ours/--theirs; resolve the HUNK and audit refusal counts
both ways", which is a person's job.

:func:`checkout` puts the synthetic commit in a detached temporary worktree so
a phase can be driven on it with the ordinary ``Repo``; :func:`remove` takes it
away. The worktree holds COMMITTED content only -- no gitignored staged panel
travels with it -- so a binding-dependent check on a merged tree renders
exactly what it renders on a clean clone (with M-1, UNMEASURABLE once the
binding raises ``InputUnavailable``).

:func:`contained` is ``git merge-base --is-ancestor``, one commit at a time,
with the resolved SHAs beside the answer so the record can quote them.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class MergeConflict(RuntimeError):
    """The merge of HEAD with the base ref does not apply cleanly. REFUSED."""

    def __init__(self, base_ref: str, base_sha: str, head_sha: str, paths: list[str], detail: str):
        self.base_ref = base_ref
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.paths = list(paths)
        self.detail = detail
        shown = ", ".join(paths[:8]) + (" …" if len(paths) > 8 else "")
        super().__init__(
            f"REFUSED: merging HEAD {head_sha[:12]} with {base_ref} ({base_sha[:12]}) "
            f"conflicts in {len(paths)} path(s): {shown}. mlkit does not resolve a "
            "conflict, with any strategy; resolve the HUNK yourself, audit both "
            "directions, and drive the merged tree again"
        )


class GitUnavailable(RuntimeError):
    """A ref did not resolve, or git could not answer. Nothing is asserted."""


@dataclass(frozen=True)
class MergedTree:
    """The merge of ``head_sha`` with ``base_ref`` as git computed it."""

    repo_path: Path
    head_sha: str
    head_tree: str
    base_ref: str
    base_sha: str
    merge_tree: str
    merge_commit: str

    @property
    def identical_to_head(self) -> bool:
        """True when merging changed nothing: the branch already contains the base.

        This is the SILENT case and it is a property, not a refusal: a drive on
        this tree must render exactly what a plain drive of HEAD renders.
        """
        return self.merge_tree == self.head_tree

    def stamp(self) -> dict[str, str | bool]:
        return {
            "head_sha": self.head_sha,
            "head_tree": self.head_tree,
            "base_ref": self.base_ref,
            "base_sha": self.base_sha,
            "merge_tree": self.merge_tree,
            "merge_commit": self.merge_commit,
            "identical_to_head": self.identical_to_head,
        }

    def header_lines(self) -> list[str]:
        same = (
            "  (merged tree == HEAD tree: the base is already contained; this drive "
            "must equal a plain drive of HEAD)"
            if self.identical_to_head
            else ""
        )
        return [
            f"MERGED-TREE DRIVE  head={self.head_sha[:12]}  base={self.base_ref}@{self.base_sha[:12]}",
            f"  merge tree {self.merge_tree}  synthetic commit {self.merge_commit[:12]} "
            "(parents: head, base; no branch moved; discarded after the drive)" + same,
        ]


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
    )


def resolve_ref(path: Path, ref: str) -> str:
    """The full SHA ``ref`` names in ``path``, or :class:`GitUnavailable`."""
    out = _git(path, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if out.returncode != 0 or not out.stdout.strip():
        raise GitUnavailable(
            f"{ref!r} does not resolve to a commit in {path} "
            f"({out.stderr.strip() or 'no such ref'}); nothing is asserted about it"
        )
    return out.stdout.strip()


def build(repo_path: Path, base_ref: str, head_ref: str = "HEAD") -> MergedTree:
    """The merge of ``head_ref`` with ``base_ref`` as a synthetic commit.

    Raises :class:`MergeConflict` (refused, never resolved) or
    :class:`GitUnavailable`.
    """
    path = Path(repo_path)
    head_sha = resolve_ref(path, head_ref)
    base_sha = resolve_ref(path, base_ref)
    head_tree = _git(path, "rev-parse", f"{head_sha}^{{tree}}").stdout.strip()

    merged = _git(path, "merge-tree", "--write-tree", "--name-only", base_sha, head_sha)
    if merged.returncode == 1:
        # `--write-tree --name-only` prints the (partial) tree oid, then one
        # conflicted path per line, then a BLANK line, then informational
        # messages ("Auto-merging …", "CONFLICT (content): …"). Only the block
        # before the blank line is paths.
        lines = merged.stdout.splitlines()
        paths: list[str] = []
        for ln in lines[1:]:
            if not ln.strip():
                break
            paths.append(ln.strip())
        messages = "\n".join(lines[len(paths) + 2:]).strip()
        raise MergeConflict(base_ref, base_sha, head_sha, paths, messages or merged.stderr.strip())
    if merged.returncode != 0:
        raise GitUnavailable(
            f"git merge-tree --write-tree failed in {path} (rc {merged.returncode}): "
            f"{merged.stderr.strip() or merged.stdout.strip()}; git >= 2.38 is required"
        )
    merge_tree = merged.stdout.splitlines()[0].strip()

    committed = subprocess.run(
        ["git", "-C", str(path), "commit-tree", merge_tree, "-p", head_sha, "-p", base_sha,
         "-m", f"mlkit --merged-with {base_ref}: synthetic merge of {head_sha[:12]} with "
               f"{base_sha[:12]}; not on any branch; discarded after the drive"],
        capture_output=True, text=True, check=False,
        env={
            # Deterministic identity so the same tree pair yields the same
            # commit id across drives; the TREE is the durable stamp anyway.
            "GIT_AUTHOR_NAME": "mlkit", "GIT_AUTHOR_EMAIL": "mlkit@resilient.world",
            "GIT_COMMITTER_NAME": "mlkit", "GIT_COMMITTER_EMAIL": "mlkit@resilient.world",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        },
    )
    if committed.returncode != 0:
        raise GitUnavailable(f"git commit-tree failed: {committed.stderr.strip()}")
    return MergedTree(
        repo_path=path,
        head_sha=head_sha,
        head_tree=head_tree,
        base_ref=base_ref,
        base_sha=base_sha,
        merge_tree=merge_tree,
        merge_commit=committed.stdout.strip(),
    )


def checkout(merged: MergedTree, parent: Path | None = None) -> Path:
    """A detached temporary worktree at the synthetic commit. Caller removes it."""
    base = Path(tempfile.mkdtemp(prefix="mlkit-merged-", dir=parent))
    target = base / merged.repo_path.name
    out = _git(merged.repo_path, "worktree", "add", "--detach", str(target), merged.merge_commit)
    if out.returncode != 0:
        raise GitUnavailable(f"git worktree add failed: {out.stderr.strip()}")
    return target


def remove(merged: MergedTree, worktree: Path) -> None:
    """Take the temporary worktree away and prune git's record of it."""
    _git(merged.repo_path, "worktree", "remove", "--force", str(worktree))
    _git(merged.repo_path, "worktree", "prune")
    parent = worktree.parent
    try:
        parent.rmdir()
    except OSError:
        pass


@dataclass(frozen=True)
class Ancestry:
    """One answer to "is this commit in that ref", with the SHAs it rests on."""

    commit: str
    commit_sha: str
    base_ref: str
    base_sha: str
    contained: bool
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "commit_sha": self.commit_sha,
            "base_ref": self.base_ref,
            "base_sha": self.base_sha,
            "contained": self.contained,
            "verdict": "CONTAINED" if self.contained else "NOT CONTAINED",
            "detail": self.detail,
        }


def contained(repo_path: Path, base_ref: str, commit: str) -> Ancestry:
    """``git merge-base --is-ancestor <commit> <base_ref>``, with both SHAs.

    Raises :class:`GitUnavailable` when either side does not resolve; a
    missing ref is not "not contained", it is a question that was not asked.
    """
    path = Path(repo_path)
    commit_sha = resolve_ref(path, commit)
    base_sha = resolve_ref(path, base_ref)
    out = _git(path, "merge-base", "--is-ancestor", commit_sha, base_sha)
    if out.returncode not in (0, 1):
        raise GitUnavailable(f"git merge-base --is-ancestor failed: {out.stderr.strip()}")
    return Ancestry(
        commit=commit,
        commit_sha=commit_sha,
        base_ref=base_ref,
        base_sha=base_sha,
        contained=(out.returncode == 0),
        detail=(
            f"{commit_sha[:12]} is an ancestor of {base_ref} ({base_sha[:12]})"
            if out.returncode == 0
            else f"{commit_sha[:12]} is NOT an ancestor of {base_ref} ({base_sha[:12]}); "
            "whatever a PR status page says, this commit is not in that ref"
        ),
    )


#: A field per PR after any merge, as the plan asks: what a caller quotes.
def containment_fields(repo_path: Path, base_ref: str, commits: list[str]) -> list[dict[str, object]]:
    return [contained(repo_path, base_ref, c).to_dict() for c in commits]

