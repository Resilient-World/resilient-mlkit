"""R13 — QUOTED RULE PARITY: no source file carries a copy of a hard-stop clause.

THE DEFECT (plan v3 §7 M-2; torrent E-069, 2026-09-04)
------------------------------------------------------
``src/torrent/mlops/hard_stops.py:48`` stored the D2 sentence from CLAUDE.md.
It was true on its branch. S-5 amended the sentence on ``main``; the branch
never received the amendment; on the merged tree the module went on emitting
the superseded clause into ``reports/hard_stops.{json,md}`` -- an artifact of
record asserting a standard the repo no longer held. "Invisible to single-PR
review by construction." Before that, E-056: four chokepoint artifacts said
"D2 and E1 remain NA" while both were armed and green, because the sentence
was typed in four places. The defect class is one thing: A HAND-WRITTEN
SENTENCE ABOUT A RULE, LIVING IN SOURCE, EMITTED INTO ARTIFACTS, GOING FALSE
WHEN THE RULE MOVES.

The S-5 register's scanner catches the superseded sentence -- in three repo
copies of one script, each exempting itself by a typed path, each scanning
for a typed phrase. Three copies of a check is rule 7's failure mode, and a
typed phrase catches exactly one amendment.

WHAT THIS CHECK READS, AND WHY NONE OF IT IS TYPED
--------------------------------------------------
* **Current clauses**: the bullets under ``## Hard stops`` in ``CLAUDE.md`` at
  HEAD, on the tree being measured.
* **Superseded clauses**: every distinct bullet under the same heading in every
  PRIOR committed version of ``CLAUDE.md`` on the tree's own history
  (``git log -- CLAUDE.md``), plus the S-5 register's ``the_rule_it_replaces``
  where a register exists, minus the current ones. The next amendment adds to
  this set by being committed, and nothing here needs editing.
* **Exemptions**: from the register at HEAD, in ITS vocabulary --
  ``source_files_quoting_the_replaced_sentence`` (sites the register discloses
  as stale; reported, counted, not failing) and ``how_this_is_enforced.scanner``
  (the enforcement may quote what it enforces).

THE DISCRIMINATOR, and why it is two window sizes
-------------------------------------------------
Tokens are lowercase alphanumeric runs, so ``10%`` is ``10``, ``[placebo]`` is
``placebo`` and a quotation reflowed across three lines or re-quoted is the
same token sequence: the clause digest is over tokens, so REGENERATE never
becomes RESTAMP.

* ``STALE_QUOTATION``: a file contains a window of :data:`W_STALE` = 4
  consecutive tokens of a superseded clause that occurs in no current clause.
  Four is the length of the register's own replaced phrase ("confidence
  interval excludes zero"); the windows a superseded clause SHARES with the
  current one ("a d2 placebo estimate …") are not evidence of staleness and
  are excluded by construction.
* ``SECOND_COPY``: a file contains a window of :data:`W_COPY` = 8 consecutive
  tokens of a CURRENT clause. Measured before this was written: torrent
  ``main``'s repaired ``hard_stops.py`` PARAPHRASES the current clause in its
  docstring with a longest shared run of five tokens ("the preregistered
  placebo declaration indicts"); a paraphrase that names the rule's subject is
  not a copy of the rule, and eight separates the two. This is torrent's
  "NO SECOND COPY" control generalised: storing today's sentence is the same
  defect waiting for the next amendment.

A scan that fires on every file containing "placebo" is the useless scanner
S-5.1 measured (18x / 25x / 2x on the committed trees) and rejected; the
conjunction of a verbatim run and a clause is the check.

TWO SURFACES, ONE VERDICT
-------------------------
The VERDICT surface is the repo's declared ``[source] trees`` plus the root
``mlkit_bindings.py``, read as committed blobs at HEAD: a quotation there is
repaired in code and a finding is FAIL. The DISCLOSURE surface is
``reports/``: an artifact quoting a clause is listed as ``tied`` (it carries
the current CLAUDE.md sha256), ``untied`` or ``stale``, and never fails --
an artifact cannot "match the current text" without being REGENERATED, and
chokepoint's run-of-record artifacts carry the superseded clause as a
labelled historical quote whose regeneration needs the pinned parquet.

This check imports nothing from the repo and reads only committed bytes, so
it measures correctly from any interpreter and is never guarded by the
environment probe.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.repo import Repo
from ..core.result import CheckResult
from . import RunContext, check

PHASE = "readiness"

#: The document of record for what a hard stop says, relative to the repo root.
CLAUDE_MD_RELPATH = "CLAUDE.md"

#: The heading whose bullet list enumerates them.
HARD_STOPS_HEADING = "## Hard stops"

#: The S-5 register, when the repo carries one. Read for its vocabulary only.
REGISTER_RELPATH = "docs/one_sided_placebo_register.json"

#: Window sizes. See the module docstring for how each was fixed.
W_STALE = 4
W_COPY = 8

#: Files on the verdict surface beyond the declared trees.
EXTRA_VERDICT_FILES = ("mlkit_bindings.py",)

#: The disclosure surface.
DISCLOSURE_TREES = ("reports",)

#: Trees walked when a repo declares none. The same default the S-5 scanner
#: reads from ``[source] trees``; declared here so a repo without a declaration
#: is still measured rather than silently exempt.
DEFAULT_TREES = ("src", "scripts")

FINDING_STALE = "STALE_QUOTATION"
FINDING_COPY = "SECOND_COPY"
SITE_REGISTERED = "REGISTERED"
SITE_ENFORCEMENT = "ENFORCEMENT"

#: Extensions never read as text.
_BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".parquet", ".pt", ".pkl", ".joblib",
    ".npy", ".npz", ".zip", ".gz", ".tar", ".whl", ".so", ".dylib", ".bin", ".nc",
}

_TOKEN = re.compile(r"[a-z0-9]+")
_MARKER = re.compile(r"\b([A-Z]\d+)\b")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def clause_digest(toks: list[str]) -> str:
    return hashlib.sha256(" ".join(toks).encode("utf-8")).hexdigest()


def _normalise_bullet(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("**", "").replace("`", "")
    return text.rstrip(";.").strip()


def hard_stop_bullets(document: str) -> list[str] | None:
    """The bullets under ``## Hard stops``; None when the heading is absent.

    A bullet continues over indented lines; the list ends at the next heading
    or at the first non-indented non-bullet line.
    """
    lines = document.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == HARD_STOPS_HEADING]
    if len(starts) != 1:
        return None
    bullets: list[str] = []
    for line in lines[starts[0] + 1:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            break
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
        elif bullets and stripped:
            if line[:1].isspace():
                bullets[-1] = f"{bullets[-1]} {stripped}"
            else:
                break
    return [b for b in (_normalise_bullet(b) for b in bullets) if b]


@dataclass(frozen=True)
class Clause:
    text: str
    marker: str
    tokens: tuple[str, ...]
    digest: str
    source: str
    current: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "text": self.text,
            "tokens": len(self.tokens),
            "clause_sha256": self.digest,
            "source": self.source,
        }


def _clause(text: str, source: str, current: bool) -> Clause:
    toks = tuple(tokens(text))
    marker = _MARKER.search(text)
    return Clause(text, marker.group(1) if marker else "", toks, clause_digest(list(toks)), source, current)


def _git(path: Path, *args: str) -> tuple[int, bytes]:
    out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=False)
    return out.returncode, out.stdout


def _blob(path: Path, relpath: str, rev: str = "HEAD") -> bytes | None:
    code, data = _git(path, "show", f"{rev}:{relpath}")
    return data if code == 0 else None


def _text(data: bytes | None) -> str | None:
    if data is None:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def current_clauses(repo: Repo) -> tuple[list[Clause] | None, str, str]:
    """``(clauses, claude_md_sha256, na_reason)``."""
    raw = _blob(repo.path, CLAUDE_MD_RELPATH)
    if raw is None:
        return None, "", f"{CLAUDE_MD_RELPATH} is not committed at HEAD; there is no hard-stop clause to hold source to"
    bullets = hard_stop_bullets(raw.decode("utf-8", errors="replace"))
    if bullets is None:
        return None, "", (
            f"{CLAUDE_MD_RELPATH} at HEAD has no single {HARD_STOPS_HEADING!r} section; "
            "the clauses this check holds source to could not be read"
        )
    if not bullets:
        return None, "", f"{CLAUDE_MD_RELPATH}'s {HARD_STOPS_HEADING!r} section carries no bullets"
    return [_clause(b, "HEAD", True) for b in bullets], hashlib.sha256(raw).hexdigest(), ""


def superseded_clauses(repo: Repo, current: list[Clause], register: dict[str, Any] | None) -> list[Clause]:
    """Every prior hard-stop bullet on this tree's history that is not current."""
    seen = {c.tokens for c in current}
    out: list[Clause] = []
    code, log = _git(repo.path, "log", "--format=%H", "HEAD", "--", CLAUDE_MD_RELPATH)
    shas = log.decode().split() if code == 0 else []
    for sha in shas:
        doc = _text(_blob(repo.path, CLAUDE_MD_RELPATH, sha))
        if doc is None:
            continue
        for bullet in hard_stop_bullets(doc) or []:
            c = _clause(bullet, sha, False)
            if c.tokens and c.tokens not in seen:
                seen.add(c.tokens)
                out.append(c)
    if register:
        replaced = register.get("the_rule_it_replaces")
        if isinstance(replaced, str) and replaced.strip():
            c = _clause(_normalise_bullet(replaced), REGISTER_RELPATH, False)
            if c.tokens and c.tokens not in seen:
                seen.add(c.tokens)
                out.append(c)
    return out


def read_register(repo: Repo) -> dict[str, Any] | None:
    raw = _blob(repo.path, REGISTER_RELPATH)
    if raw is None:
        return None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def exemptions(register: dict[str, Any] | None, repo_name: str) -> tuple[set[str], set[str]]:
    """``(registered_files, enforcement_files)`` from the register's own vocabulary."""
    if not register:
        return set(), set()
    identity = (register.get("repo_identity") or {}).get(repo_name) or f"resilient-{repo_name}"
    listed = (register.get("source_files_quoting_the_replaced_sentence") or {}).get(identity) or []
    registered = {str(p) for p in listed}
    scanner = str((register.get("how_this_is_enforced") or {}).get("scanner") or "").split()
    enforcement = {scanner[0]} if scanner else set()
    return registered, enforcement


def committed_files(repo: Repo, prefixes: list[str]) -> list[str]:
    out: list[str] = []
    for prefix in prefixes:
        code, listing = _git(repo.path, "ls-tree", "-r", "--name-only", "HEAD", "--", prefix)
        if code != 0:
            continue
        for rel in listing.decode("utf-8", errors="replace").splitlines():
            rel = rel.strip()
            if rel and Path(rel).suffix.lower() not in _BINARY_SUFFIXES and rel not in out:
                out.append(rel)
    return out


def windows(toks: tuple[str, ...] | list[str], w: int) -> set[tuple[str, ...]]:
    if len(toks) < w:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i:i + w]) for i in range(len(toks) - w + 1)}


@dataclass
class Vocabulary:
    """The windows a file is scanned for, built once per repo."""

    stale: dict[tuple[str, ...], Clause] = field(default_factory=dict)
    copy: dict[tuple[str, ...], Clause] = field(default_factory=dict)

    @classmethod
    def build(cls, current: list[Clause], superseded: list[Clause]) -> Vocabulary:
        v = cls()
        current_stale_windows: set[tuple[str, ...]] = set()
        superseded_copy_windows: set[tuple[str, ...]] = set()
        for c in current:
            current_stale_windows |= windows(c.tokens, W_STALE)
        for c in superseded:
            superseded_copy_windows |= windows(c.tokens, W_COPY)
            for win in windows(c.tokens, W_STALE) - current_stale_windows:
                v.stale.setdefault(win, c)
        # A copy window the current clause SHARES with a superseded one ("a d2
        # placebo estimate whose confidence interval excludes …") cannot say
        # which of the two was copied, so it is not evidence of a second copy
        # of the current clause; a copy of the superseded clause is caught by
        # its distinctive STALE windows instead. E1, never amended, keeps
        # every window.
        for c in current:
            for win in windows(c.tokens, W_COPY) - superseded_copy_windows:
                v.copy.setdefault(win, c)
        return v


@dataclass(frozen=True)
class Finding:
    relpath: str
    line: int
    kind: str
    clause_marker: str
    clause_source: str
    clause_sha256: str
    window: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.relpath, "line": self.line, "kind": self.kind,
            "clause": self.clause_marker, "clause_source": self.clause_source,
            "clause_sha256": self.clause_sha256, "window": self.window,
        }


def scan_text(relpath: str, text: str, vocab: Vocabulary) -> list[Finding]:
    """One finding per (kind, clause) per file, at the first line it appears."""
    toks: list[str] = []
    line_of: list[int] = []
    for n, line in enumerate(text.splitlines(), start=1):
        for t in _TOKEN.findall(line.lower()):
            toks.append(t)
            line_of.append(n)
    found: dict[tuple[str, str], Finding] = {}
    for w, table, kind in ((W_STALE, vocab.stale, FINDING_STALE), (W_COPY, vocab.copy, FINDING_COPY)):
        if not table:
            continue
        for i in range(0, max(0, len(toks) - w + 1)):
            win = tuple(toks[i:i + w])
            clause = table.get(win)
            if clause is None:
                continue
            key = (kind, clause.digest)
            if key not in found:
                found[key] = Finding(
                    relpath, line_of[i], kind, clause.marker, clause.source,
                    clause.digest, " ".join(win),
                )
    return sorted(found.values(), key=lambda f: (f.line, f.kind))


@check("R13", PHASE, "QUOTED_RULE_PARITY — no source file carries a copy of a hard-stop clause")
def r13_quoted_rule_parity(repo: Repo, ctx: RunContext) -> CheckResult:
    current, claude_sha, na_reason = current_clauses(repo)
    if current is None:
        return CheckResult.na("R13", PHASE, na_reason)

    register = read_register(repo)
    superseded = superseded_clauses(repo, current, register)
    vocab = Vocabulary.build(current, superseded)
    registered_files, enforcement_files = exemptions(register, repo.name)

    source = repo.config().get("source") or {}
    trees = [str(t).strip() for t in (source.get("trees") or []) if str(t).strip()] or list(DEFAULT_TREES)
    verdict_files = committed_files(repo, trees)
    for extra in EXTRA_VERDICT_FILES:
        if _blob(repo.path, extra) is not None and extra not in verdict_files:
            verdict_files.append(extra)

    problems: list[Finding] = []
    registered_sites: list[dict[str, Any]] = []
    enforcement_sites: list[dict[str, Any]] = []
    scanned = 0
    for rel in verdict_files:
        text = _text(_blob(repo.path, rel))
        if text is None:
            continue
        scanned += 1
        for f in scan_text(rel, text, vocab):
            if rel in registered_files:
                registered_sites.append({**f.to_dict(), "site": SITE_REGISTERED})
            elif rel in enforcement_files:
                enforcement_sites.append({**f.to_dict(), "site": SITE_ENFORCEMENT})
            else:
                problems.append(f)

    artifacts: list[dict[str, Any]] = []
    for rel in committed_files(repo, list(DISCLOSURE_TREES)):
        text = _text(_blob(repo.path, rel))
        if text is None:
            continue
        for f in scan_text(rel, text, vocab):
            standing = (
                "stale" if f.kind == FINDING_STALE
                else "tied" if claude_sha and claude_sha in text
                else "untied"
            )
            artifacts.append({**f.to_dict(), "standing": standing})

    evidence: dict[str, Any] = {
        "claude_md_sha256": claude_sha,
        "clauses": [c.to_dict() for c in current],
        "superseded_clauses": [c.to_dict() for c in superseded],
        "register_at_head": register is not None,
        "verdict_trees": trees + [e for e in EXTRA_VERDICT_FILES if e in verdict_files],
        "files_scanned": scanned,
        "window_tokens": {"stale": W_STALE, "second_copy": W_COPY},
        "findings": [f.to_dict() for f in problems],
        "registered_sites": registered_sites,
        "enforcement_sites": enforcement_sites,
        "artifacts": artifacts,
        "artifact_counts": {
            k: sum(1 for a in artifacts if a["standing"] == k) for k in ("tied", "untied", "stale")
        },
    }
    if problems:
        head = problems[0]
        return CheckResult.failed(
            "R13", PHASE,
            f"{len(problems)} quotation(s) of a hard-stop clause in committed source that the "
            f"register does not list: {head.relpath}:{head.line} {head.kind} of the "
            f"{head.clause_marker or 'hard-stop'} clause ({head.clause_source[:12]}) — "
            f"\"{head.window}\""
            + (f" (+{len(problems) - 1} more)" if len(problems) > 1 else "")
            + ". A sentence about a rule, living in source and emitted into artifacts, goes "
            "stale the moment the rule moves (E-056, E-069). Read the document at run time; "
            "do not store the sentence",
            evidence,
        )
    return CheckResult.passed("R13", PHASE, evidence)
