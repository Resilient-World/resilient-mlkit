"""The licence allowlist, and the gate built on it.

Two rules shape everything in this module.

The first is that the allowlist is *signed by a human*. The agent proposes
additions in ``docs/ESCALATIONS.md``; it never edits the allowlist. So an
unsigned allowlist is not a failure to be worked around -- it is a signature
that has not happened yet, and the checks that depend on it report ESCALATED,
which routes the repo to AWAITING-SIGNOFF rather than to a false pass.

The second is that an entry without a resolvable licence URL and a retrieval
date is not an entry. Licences change; "it was open when I looked" is only a
defensible position if you recorded when you looked.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .repo import Repo

#: Relative to the repo root. Identical across all 8 repos.
ALLOWLIST_RELPATH = "docs/allowlist.yaml"

VALID_STATUSES = {"ALLOWED", "BLOCKED", "EVAL-ONLY"}


@dataclass
class Entry:
    """One data source or model checkpoint, with its licence determination."""

    id: str
    kind: str  # "data" | "weights"
    status: str  # ALLOWED | BLOCKED | EVAL-ONLY
    licence_url: str = ""
    retrieval_date: str = ""
    attribution: str = ""
    note: str = ""

    def defects(self) -> list[str]:
        """Structural problems that make this entry unusable as evidence."""
        problems: list[str] = []
        if self.status not in VALID_STATUSES:
            problems.append(
                f"status {self.status!r} is not one of {sorted(VALID_STATUSES)}"
            )
        if self.kind not in {"data", "weights"}:
            problems.append(f"kind {self.kind!r} is not 'data' or 'weights'")
        if not self.licence_url.startswith(("http://", "https://")):
            problems.append("licence_url is missing or not a resolvable URL")
        if not self.retrieval_date:
            problems.append("retrieval_date is missing")
        else:
            try:
                _dt.date.fromisoformat(self.retrieval_date)
            except ValueError:
                problems.append(
                    f"retrieval_date {self.retrieval_date!r} is not ISO-8601 (YYYY-MM-DD)"
                )
        return problems


@dataclass
class Allowlist:
    """The parsed, possibly-unsigned allowlist for one repo."""

    path: Path
    signed: bool = False
    #: What the FILE claims, before verification. Never read as a signature --
    #: it is the input to :func:`_verify_signature`, not its output.
    claims_signed: bool = False
    signed_by: str = ""
    signed_at: str = ""
    #: SHA-256 the signatory recorded over the entries. Mismatch voids signing.
    entries_sha256: str = ""
    #: `git log -1` on the allowlist. Provenance evidence, not proof of identity.
    last_commit: str = ""
    entries: dict[str, Entry] = field(default_factory=dict)
    parse_error: str = ""

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def verdict(self, source_id: str) -> str | None:
        """ALLOWED / BLOCKED / EVAL-ONLY, or None when the source is unlisted."""
        entry = self.entries.get(source_id)
        return entry.status if entry else None

    def defective_entries(self) -> dict[str, list[str]]:
        return {k: d for k, v in self.entries.items() if (d := v.defects())}

    def attributions(self) -> list[Entry]:
        """Entries carrying an attribution obligation, for NOTICE.md."""
        return [e for e in self.entries.values() if e.attribution.strip()]


def read(path: Path) -> Allowlist:
    """Parse an allowlist FILE. Never raises; malformed files become parse_error.

    Returns an allowlist with ``signed`` left False regardless of what the
    file claims: signature verification needs the repo's git history, which a
    path does not carry. :func:`load` is the entry point that verifies.

    Split out from :func:`load` so a caller that only needs the DETERMINATIONS
    -- which real products this repo's signatory has recorded -- can read them
    without constructing a Repo, and without a second parser growing beside
    this one. R11's value-side source adjudication is that caller.
    """
    allowlist = Allowlist(path=path)
    if not path.is_file():
        return allowlist

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        allowlist.parse_error = f"malformed YAML: {exc}"
        return allowlist
    if not isinstance(raw, dict):
        allowlist.parse_error = "top level of allowlist.yaml is not a mapping"
        return allowlist

    signature = raw.get("signature") or {}
    claimed = bool(signature.get("signed"))
    allowlist.signed_by = str(signature.get("signed_by") or "")
    allowlist.signed_at = str(signature.get("signed_at") or "")
    allowlist.entries_sha256 = str(signature.get("entries_sha256") or "")

    for item in raw.get("entries") or []:
        if not isinstance(item, dict) or "id" not in item:
            continue
        entry = Entry(
            id=str(item["id"]),
            kind=str(item.get("kind", "")),
            status=str(item.get("status", "")),
            licence_url=str(item.get("licence_url") or ""),
            retrieval_date=str(item.get("retrieval_date") or ""),
            attribution=str(item.get("attribution") or ""),
            note=str(item.get("note") or ""),
        )
        allowlist.entries[entry.id] = entry

    allowlist.claims_signed = claimed
    return allowlist


def load(repo: Repo) -> Allowlist:
    """Parse a repo's allowlist and verify its signature."""
    allowlist = read(repo.path / ALLOWLIST_RELPATH)
    # A boolean in a file an agent can write is not a signature. Treat the
    # claim as true only if it also survives an integrity check, so that
    # editing entries after signing revokes the signature automatically.
    allowlist.signed = _verify_signature(allowlist, allowlist.claims_signed, repo)
    return allowlist


def entries_digest(entries: dict[str, Entry]) -> str:
    """Stable SHA-256 over the determinations, independent of YAML formatting."""
    canonical = json.dumps(
        [
            [e.id, e.kind, e.status, e.licence_url, e.retrieval_date, e.attribution]
            for e in sorted(entries.values(), key=lambda x: x.id)
        ],
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _verify_signature(allowlist: Allowlist, claimed: bool, repo: Repo) -> bool:
    """Decide whether a claimed signature holds up.

    What this can prove: that the entries are byte-for-byte the ones the
    signatory hashed, and who last committed the file. What it cannot prove
    without a key: that the signatory personally authored that commit. The
    honest position is to verify integrity, record provenance as evidence, and
    never silently upgrade a bare boolean into a determination.
    """
    if not claimed:
        return False
    if not allowlist.signed_by:
        allowlist.parse_error = "signature.signed is true but signature.signed_by is empty"
        return False
    if not allowlist.entries_sha256:
        allowlist.parse_error = (
            "signature.signed is true but signature.entries_sha256 is absent; "
            "a signature that does not cover the entries protects nothing"
        )
        return False

    actual = entries_digest(allowlist.entries)
    if actual != allowlist.entries_sha256:
        allowlist.parse_error = (
            f"signature.entries_sha256 does not match the entries it covers "
            f"(recorded {allowlist.entries_sha256[:12]}…, computed {actual[:12]}…). "
            "The entries changed after signing; the signature is void."
        )
        return False

    # Provenance, as evidence rather than as proof.
    allowlist.last_commit = repo._git(
        "log", "-1", "--format=%h %an <%ae> %G?", "--", ALLOWLIST_RELPATH
    )
    if repo._git("status", "--porcelain", "--", ALLOWLIST_RELPATH):
        allowlist.parse_error = (
            "allowlist has uncommitted changes; a signature is only meaningful "
            "against a committed file"
        )
        return False
    return True


def manifest_sources(repo: Repo) -> tuple[list[str], str]:
    """Return (source ids currently in this repo's pipeline, error).

    Resolution order is the ``manifest`` binding first, then a declared
    ``[manifest] path``. There is no fallback that scans the repo and guesses:
    a licence gate that guesses its own input is not a gate.
    """
    from .repo import BindingError

    if repo.binding("manifest"):
        try:
            fn = repo.resolve("manifest")
        except BindingError as exc:
            return [], str(exc)
        try:
            value = fn()
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            return [], f"manifest binding raised {type(exc).__name__}: {exc}"
        return [str(v) for v in value], ""

    declared = (repo.config().get("manifest") or {}).get("path")
    if declared:
        path = repo.path / declared
        if not path.is_file():
            return [], f"declared manifest {declared} does not exist"
        # YAML is a superset of JSON, so one parser covers both the .yaml
        # manifests and the config/commercial_sources.json catalogues that
        # four of the repos already keep as their source of record.
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            return [], f"manifest {declared} is malformed: {exc}"
        if not isinstance(data, dict):
            return [], f"manifest {declared} top level is not a mapping"
        sources = data.get("sources") or data.get("data_sources") or []
        ids: list[str] = []
        for item in sources:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict):
                key = item.get("source_id") or item.get("id")
                if key:
                    ids.append(str(key))
        if not ids and sources:
            return [], (
                f"manifest {declared} lists {len(sources)} source(s) but none carries "
                "a 'source_id' or 'id'"
            )
        return ids, ""

    return [], "no 'manifest' binding and no [manifest] path declared in .mlkit/repo.toml"


def render_notice(repo: Repo, allowlist: Allowlist) -> str:
    """Generate NOTICE.md content from attribution obligations.

    Content comes solely from the ``attribution`` field of signed allowlist
    entries -- this function asserts nothing about any licence itself. It is
    generated rather than hand-edited so that it cannot drift away from the
    allowlist it is supposed to reflect, which is what R9 checks.
    """
    lines = [
        f"# NOTICE — resilient-{repo.name}",
        "",
        "<!-- GENERATED BY `mlkit notice`. Do not edit by hand; edits are overwritten.",
        f"     Source of truth: {ALLOWLIST_RELPATH} -->",
        "",
    ]
    obligations = sorted(allowlist.attributions(), key=lambda e: e.id)
    if not obligations:
        lines += [
            "No source or checkpoint in this repo's signed allowlist carries an",
            "attribution obligation.",
            "",
        ]
    else:
        lines += [
            "This product incorporates the following third-party sources, each of",
            "which carries an attribution obligation under its licence.",
            "",
        ]
        for entry in obligations:
            lines += [
                f"## {entry.id}",
                "",
                f"> {entry.attribution}",
                "",
                f"- Licence: {entry.licence_url}",
                f"- Retrieved: {entry.retrieval_date}",
                f"- Kind: {entry.kind}",
                "",
            ]
    if not allowlist.signed:
        lines += [
            "---",
            "",
            "**This notice is provisional.** The allowlist it was generated from is",
            "unsigned, so the determinations above have not been ratified.",
            "",
        ]
    return "\n".join(lines)
