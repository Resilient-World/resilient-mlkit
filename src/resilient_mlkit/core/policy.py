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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

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
    signed_by: str = ""
    signed_at: str = ""
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


def load(repo: Repo) -> Allowlist:
    """Parse a repo's allowlist. Never raises; malformed files become parse_error."""
    path = repo.path / ALLOWLIST_RELPATH
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
    allowlist.signed = bool(signature.get("signed"))
    allowlist.signed_by = str(signature.get("signed_by") or "")
    allowlist.signed_at = str(signature.get("signed_at") or "")

    # A signature block that claims signed:true without naming a signatory is
    # not a signature. Treat it as unsigned rather than trusting the flag.
    if allowlist.signed and not allowlist.signed_by:
        allowlist.signed = False
        allowlist.parse_error = "signature.signed is true but signature.signed_by is empty"

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
    return allowlist


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
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            return [], f"manifest {declared} is malformed YAML: {exc}"
        sources = data.get("sources") or data.get("data_sources") or []
        ids: list[str] = []
        for item in sources:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict) and "id" in item:
                ids.append(str(item["id"]))
        return ids, ""

    return [], "no 'manifest' binding and no [manifest] path declared in .mlkit/repo.toml"


def render_notice(repo: Repo, allowlist: Allowlist) -> str:
    """Generate NOTICE.md content from attribution obligations.

    Copernicus requires an attribution notice on distribution, and for a company
    selling to banks and insurers this file is a due-diligence deliverable
    rather than housekeeping. It is generated, never hand-edited, so that it
    cannot drift away from the allowlist it is supposed to reflect.
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
