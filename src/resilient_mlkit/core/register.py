"""S-5: the one-sided placebo register's CROSS-REPO invariant (E-080).

WHAT THIS IS FOR
----------------
``docs/one_sided_placebo_register.json`` is ONE document kept in three
repositories. ``canonical_body_sha256`` exists so that a drift between the
copies fails in whichever copy drifted. On 2026-09-05 there were **four live
bodies at once** — fray, chokepoint, torrent and a chokepoint PR head — and
E-080 recorded the part that matters:

    Every copy was internally consistent, so ``--mode check`` returned
    ``0 problem(s)`` in all three repos, and every repo's test suite was green
    on the constant it had pinned. The invariant is BETWEEN the repos. Nothing
    in any repo can see the other two, so nothing runs it.

Each repo had repaired its own site, ZEROED ITS OWN ENTRY in
``source_files_quoting_the_replaced_sentence``, and written in prose that the
other repo was still stale. Both statements were false, and no repo could ever
learn otherwise, because the only reader who could was a person holding all
three checkouts.

This module is that reader, as a command.

WHY IT IS LOCAL AND NOT A CI JOB
--------------------------------
E-080 named the closure and named why an agent may not build it the obvious
way: the repos are PRIVATE, so a cross-repo CI job needs a credential, and
CLAUDE.md rule 13 forbids an agent putting a credential anywhere near this.
Standing CI configuration is the signatory's under rule 12. So this runs on a
machine that already holds the checkouts. It fetches nothing, authenticates to
nothing, creates nothing, and writes nothing into any repo.

RULE 7: THE DIGEST IS NOT REDEFINED HERE
----------------------------------------
mlkit does not implement ``canonical_body_sha256``. It loads **each repo's own
committed** ``scripts/verify_one_sided_placebo_register.py`` from that repo's
``HEAD`` blob and calls that repo's function — and it applies every repo's
function to every repo's body, so the implementations are checked against each
other as well. Three implementations agreeing on one answer is a measurement;
one implementation asserting an answer is not. That is the shape the S-5 re-cut
of 2026-09-05 used, and it is the shape kept here.

TWO FAILURES, KEPT DISTINCT
---------------------------
``SELF_INCONSISTENT``
    a copy whose stored digest is not what its own function computes over its
    own body. Somebody edited the document and did not re-derive the digest.
    Each repo's own scanner already catches this.
``DIVERGENT``
    copies that are each internally consistent and do not agree. **This is
    E-080's actual failure**, the one no per-repo check can see, and the reason
    this module exists. The differing field is named by its dotted path to the
    depth at which the copies part company, and ``declarations`` is compared BY
    ID rather than positionally so that a narrowing live in one copy and absent
    from another is reported as the id that is missing.

WHAT A PASS HERE DOES NOT CLAIM
-------------------------------
That the register is CORRECT — only that the copies are one document. A field
that is wrong in the same way in all three copies passes here and should: this
check measures agreement, and agreement is not truth. It also says nothing
about copies that are not on this machine; the set it compares is the set it
found, and it prints that set so a reader can see what was and was not in
scope.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ARTIFACT_RELPATH",
    "ARTIFACT_SCHEMA",
    "DIVERGENT",
    "PROOF_FIELD",
    "REGISTER_RELPATH",
    "SELF_INCONSISTENT",
    "VERIFIER_RELPATH",
    "ArtifactRefused",
    "Copy",
    "FleetReport",
    "Problem",
    "RegisterUnreadable",
    "artifact_document",
    "check_fleet",
    "field_divergences",
    "load_artifact",
    "load_copy",
    "proof_sha256",
    "verify_artifact",
    "write_artifact",
]

#: The document, in every repo that carries it.
REGISTER_RELPATH = "docs/one_sided_placebo_register.json"

#: The repo's own committed digest function. Rule 7: mlkit calls this rather
#: than defining a second one.
VERIFIER_RELPATH = "scripts/verify_one_sided_placebo_register.py"

#: The field the digest covers everything except.
DIGEST_FIELD = "canonical_body_sha256"

#: The committable result of one ``--check-fleet`` run (E-M39). A consumer
#: commits it beside the register it describes and pins it with
#: :func:`verify_artifact`, so a register edit with no fresh fleet check is a
#: red test in that repo rather than a paragraph somebody was meant to read.
ARTIFACT_SCHEMA = "resilient-mlkit/s5-register-fleet-check/1"

#: Where a consumer is asked to keep it. A suggestion the verifier does not
#: depend on: :func:`verify_artifact` takes the path it is given.
ARTIFACT_RELPATH = "reports/s5_register_fleet_check.json"

#: The artifact's own seal: sha256 over its canonical body with this field
#: removed. It is NOT a second digest of the register (rule 7) -- the register's
#: digest stays the repos' own ``canonical_body_sha256``. It seals mlkit's
#: RESULT, so an artifact edited by hand to read PASS no longer verifies.
PROOF_FIELD = "proof_sha256"

#: Lists whose elements are matched by a stable key rather than by position,
#: so that an element present in one copy and absent from another is reported
#: as the missing id and not as "every element from here on differs". The value
#: is the key name to match on, tried in order.
_KEYED_LISTS: dict[str, tuple[str, ...]] = {
    "declarations": ("id", "declaration_id", "name")
}

#: A copy whose digest does not match its own body.
SELF_INCONSISTENT = "SELF_INCONSISTENT"

#: Copies that are each internally consistent and do not agree. E-080.
DIVERGENT = "DIVERGENT"

#: The three implementations of the digest disagree with each other. Not a
#: FAIL about the document: a REFUSAL about the instrument.
IMPLEMENTATIONS_DISAGREE = "IMPLEMENTATIONS_DISAGREE"


class RegisterUnreadable(RuntimeError):
    """A copy could not be read as the committed document it claims to be.

    Raised, never swallowed into "no problems found". A check that treats an
    unreadable copy as an absent one is a check that passes by looking away.
    """


# ---------------------------------------------------------------------------
# git — the committed blob, never the working tree
# ---------------------------------------------------------------------------
def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise RegisterUnreadable(
            f"{root.name}: git {' '.join(args)} failed: {out.stderr.strip()}"
        )
    return out.stdout


def _blob_id(root: Path, relpath: str) -> str:
    return _git(root, "rev-parse", f"HEAD:{relpath}").strip()


def _blob_text(root: Path, relpath: str) -> str:
    return _git(root, "show", f"HEAD:{relpath}")


# ---------------------------------------------------------------------------
# the repo's own digest function
# ---------------------------------------------------------------------------
def _load_digest_function(root: Path, into: Path) -> Callable[[dict], str]:
    """Import the repo's committed verifier and return ITS ``canonical_body_sha256``.

    The blob is materialised under ``<into>/scripts/`` with its own filename,
    because the verifier asserts on its ``__file__`` and derives a repo root
    from it. Nothing in this module calls anything that uses that root; the
    only symbol taken is the digest function.

    A module named after the repo, so importing three verifiers does not have
    them shadow one another in ``sys.modules``.
    """
    text = _blob_text(root, VERIFIER_RELPATH)
    scripts = into / root.name / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    path = scripts / Path(VERIFIER_RELPATH).name
    path.write_text(text, encoding="utf-8")

    module_name = f"_resilient_mlkit_s5_verifier__{root.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RegisterUnreadable(f"{root.name}: {VERIFIER_RELPATH} is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # reported, never swallowed into "no problems found"
        raise RegisterUnreadable(
            f"{root.name}: importing {VERIFIER_RELPATH} raised {type(exc).__name__}: {exc}"
        ) from exc
    fn = getattr(module, "canonical_body_sha256", None)
    if not callable(fn):
        raise RegisterUnreadable(
            f"{root.name}: {VERIFIER_RELPATH} defines no canonical_body_sha256, so this "
            "copy carries no definition of the digest that makes the three copies one "
            "document"
        )
    return fn


# ---------------------------------------------------------------------------
# copies
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Copy:
    """One repository's copy of the register, read from its ``HEAD``."""

    repo: str
    path: Path
    head: str
    blob: str
    body: dict[str, Any]
    stored_digest: str | None
    #: What every repo's own function computes over THIS body. One entry per
    #: repo whose verifier was loadable, keyed by that repo's name.
    computed: dict[str, str] = field(default_factory=dict)

    @property
    def agreed_digest(self) -> str | None:
        """The one value every implementation computed, or None if they differ."""
        values = set(self.computed.values())
        return values.pop() if len(values) == 1 else None


def iter_register_repos(root: Path) -> Iterator[Path]:
    """Every ``resilient-*`` directory under ``root`` carrying the register."""
    for child in sorted(Path(root).iterdir()):
        if (
            child.is_dir()
            and child.name.startswith("resilient-")
            and (child / REGISTER_RELPATH).is_file()
        ):
            yield child


def load_copy(root: Path) -> tuple[str, str, dict[str, Any]]:
    """``(head, blob_id, body)`` for one checkout, read from ``HEAD``."""
    head = _git(root, "rev-parse", "HEAD").strip()
    blob = _blob_id(root, REGISTER_RELPATH)
    try:
        body = json.loads(_blob_text(root, REGISTER_RELPATH))
    except json.JSONDecodeError as exc:
        raise RegisterUnreadable(
            f"{root.name}: {REGISTER_RELPATH} at HEAD is not JSON: {exc}"
        ) from exc
    if not isinstance(body, dict):
        raise RegisterUnreadable(
            f"{root.name}: {REGISTER_RELPATH} at HEAD is a {type(body).__name__}, "
            "not an object"
        )
    return head, blob, body


# ---------------------------------------------------------------------------
# the field-level comparison
# ---------------------------------------------------------------------------
def _keyed(values: list[Any], keys: tuple[str, ...]) -> dict[str, Any] | None:
    """``{id: element}`` when every element is a dict carrying one of ``keys``."""
    for key in keys:
        if values and all(isinstance(v, dict) and key in v for v in values):
            ids = [str(v[key]) for v in values]
            if len(set(ids)) == len(ids):
                return dict(zip(ids, values, strict=True))
    return None


def _paths_where_they_differ(
    a: Any, b: Any, prefix: str, out: list[str], keyed_lists: Mapping[str, tuple[str, ...]]
) -> None:
    """Append the dotted path of every leaf at which ``a`` and ``b`` differ."""
    if type(a) is not type(b):
        out.append(prefix)
        return
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in a or key not in b:
                out.append(child)
                continue
            _paths_where_they_differ(a[key], b[key], child, out, keyed_lists)
        return
    if isinstance(a, list):
        name = prefix.rsplit(".", 1)[-1]
        keys = keyed_lists.get(name)
        if keys:
            ka, kb = _keyed(a, keys), _keyed(b, keys)
            if ka is not None and kb is not None:
                for ident in sorted(set(ka) | set(kb)):
                    child = f"{prefix}[{ident}]"
                    if ident not in ka or ident not in kb:
                        out.append(child)
                        continue
                    _paths_where_they_differ(ka[ident], kb[ident], child, out, keyed_lists)
                return
        if len(a) != len(b):
            # The list itself, not `<path>[len]`: a reader repairing this needs
            # to see WHICH element is missing, and a length is not that. The
            # values are abbreviated where they are reported, not here.
            out.append(prefix)
            return
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _paths_where_they_differ(x, y, f"{prefix}[{i}]", out, keyed_lists)
        return
    if a != b:
        out.append(prefix)


def _at(body: Any, path: str) -> Any:
    """The value at a dotted path produced by :func:`_paths_where_they_differ`.

    Returns the sentinel string ``"<absent>"`` when the path does not resolve,
    which is the honest answer for the case the path exists to report.
    """
    node: Any = body
    token = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            node = _step(node, token)
            token = ""
        elif ch == "[":
            node = _step(node, token)
            token = ""
            close = path.find("]", i)
            if close == -1:
                return ABSENT
            node = _step(node, path[i + 1 : close])
            i = close
        else:
            token += ch
        i += 1
    return _step(node, token) if token else node


#: What a field is when the copy does not carry it at all.
ABSENT = "<absent>"

#: How much of a differing value goes in the message. A divergence is repaired
#: by opening the two files, so the report exists to say WHICH field and WHO
#: holds what — not to reproduce the document. Long values are cut with an
#: ellipsis that says so.
_ABBREVIATE_TO = 160


def _abbreviate(value: str) -> str:
    if len(value) <= _ABBREVIATE_TO:
        return value
    return value[:_ABBREVIATE_TO] + f"… ({len(value)} chars)"


def _step(node: Any, token: str) -> Any:
    if token == "" or node is ABSENT:
        return node
    if token == "len":
        return len(node) if isinstance(node, (list, dict, str)) else ABSENT
    if isinstance(node, dict):
        return node.get(token, ABSENT)
    if isinstance(node, list):
        if token.lstrip("-").isdigit():
            index = int(token)
            return node[index] if -len(node) <= index < len(node) else ABSENT
        for element in node:
            if isinstance(element, dict):
                for key in ("id", "declaration_id", "name"):
                    if str(element.get(key)) == token:
                        return element
        return ABSENT
    return ABSENT


def field_divergences(copies: Iterable[Copy]) -> dict[str, dict[str, list[str]]]:
    """``{dotted field: {value as canonical JSON: [repos holding it]}}``.

    The value is the grouping key rather than a repo, because a divergence has
    **no innocent party** until a person says which copy the document is. E-080
    is the proof: each of the four bodies was internally consistent and each
    repo believed the other two were the stale ones. Reporting "these two
    differ from that one" would have reproduced that framing; reporting "here
    are the two values and here is who holds each" does not.
    """
    copies = sorted(copies, key=lambda c: c.repo)
    if len(copies) < 2:
        return {}
    reference = copies[0]
    paths: set[str] = set()
    for other in copies[1:]:
        found: list[str] = []
        _paths_where_they_differ(
            {k: v for k, v in reference.body.items() if k != DIGEST_FIELD},
            {k: v for k, v in other.body.items() if k != DIGEST_FIELD},
            "",
            found,
            _KEYED_LISTS,
        )
        paths |= {p or "<document>" for p in found}

    out: dict[str, dict[str, list[str]]] = {}
    for path in sorted(paths):
        groups: dict[str, list[str]] = {}
        for copy in copies:
            value = _at({k: v for k, v in copy.body.items() if k != DIGEST_FIELD}, path)
            groups.setdefault(
                json.dumps(value, sort_keys=True, ensure_ascii=False), []
            ).append(copy.repo)
        out[path] = dict(sorted(groups.items()))
    return out


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Problem:
    kind: str
    repo: str
    detail: str
    field_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "repo": self.repo,
            "field": self.field_path,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class FleetReport:
    root: str
    copies: tuple[Copy, ...]
    problems: tuple[Problem, ...]
    refusal: str | None = None

    @property
    def ok(self) -> bool:
        return self.refusal is None and not self.problems

    @property
    def one_blob(self) -> str | None:
        blobs = {c.blob for c in self.copies}
        return blobs.pop() if len(blobs) == 1 else None

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_schema": "resilient-mlkit/s5-register-fleet-check/1",
            "root": self.root,
            "refusal": self.refusal,
            "copies": [
                {
                    "repo": c.repo,
                    "head": c.head,
                    "blob": c.blob,
                    "stored_digest": c.stored_digest,
                    "computed_by": dict(sorted(c.computed.items())),
                    "agreed_digest": c.agreed_digest,
                }
                for c in self.copies
            ],
            "identical_blob": self.one_blob,
            "problems": [p.to_dict() for p in self.problems],
            "ok": self.ok,
        }


def check_fleet(root: Path) -> FleetReport:
    """Compare every register copy under ``root``. See the module docstring."""
    root = Path(root)
    roots = list(iter_register_repos(root))
    if len(roots) < 2:
        found = ", ".join(p.name for p in roots) or "none"
        return FleetReport(
            root=str(root),
            copies=(),
            problems=(),
            # No path in the sentence: this refusal is carried verbatim into the
            # committable artifact, and a machine path there is M-5's defect.
            # The CLI prints --root on its own line beside it.
            refusal=(
                f"REFUSED: {len(roots)} copy/copies of {REGISTER_RELPATH} found under "
                f"--root ({found}). The invariant this checks lives BETWEEN the repos, "
                "so a run over fewer than two copies measures nothing — and reporting "
                "it green would be the strongest possible version of the defect it "
                "exists to catch (E-080)"
            ),
        )

    with tempfile.TemporaryDirectory(prefix="mlkit-s5-verifiers-") as tmp:
        into = Path(tmp)
        functions: dict[str, Callable[[dict], str]] = {}
        for repo_root in roots:
            functions[repo_root.name] = _load_digest_function(repo_root, into)

        copies: list[Copy] = []
        for repo_root in roots:
            head, blob, body = load_copy(repo_root)
            computed = {
                name: fn({k: v for k, v in body.items()})
                for name, fn in functions.items()
            }
            stored = body.get(DIGEST_FIELD)
            copies.append(
                Copy(
                    repo=repo_root.name,
                    path=repo_root,
                    head=head,
                    blob=blob,
                    body=body,
                    stored_digest=stored if isinstance(stored, str) else None,
                    computed=computed,
                )
            )

    problems: list[Problem] = []

    # (0) the instrument first. If the three implementations disagree, no
    # verdict taken with any of them is worth reading, so this is reported
    # before anything about the document.
    for copy in copies:
        if copy.agreed_digest is None:
            problems.append(
                Problem(
                    kind=IMPLEMENTATIONS_DISAGREE,
                    repo=copy.repo,
                    field_path=DIGEST_FIELD,
                    detail=(
                        "the repos' own canonical_body_sha256 implementations do not "
                        f"agree on this body: {dict(sorted(copy.computed.items()))}. "
                        "The fleet has two definitions of the digest; settle that "
                        "before reading any digest verdict"
                    ),
                )
            )

    # (1) each copy against its own function. Every repo's own scanner already
    # catches this; it is here so that a divergence report cannot be blamed on
    # a stale digest that nobody had re-derived.
    for copy in copies:
        agreed = copy.agreed_digest
        if agreed is None:
            continue
        if copy.stored_digest != agreed:
            problems.append(
                Problem(
                    kind=SELF_INCONSISTENT,
                    repo=copy.repo,
                    field_path=DIGEST_FIELD,
                    detail=(
                        f"stored {copy.stored_digest!r}, but this copy's body hashes to "
                        f"{agreed!r} under its own function. The register was edited "
                        "without re-deriving its own digest"
                    ),
                )
            )

    # (2) THE ONE NO PER-REPO CHECK CAN SEE. Copies that are each internally
    # consistent and do not agree (E-080).
    for path, groups in field_divergences(copies).items():
        held = "; ".join(
            f"{', '.join(repos)} = {_abbreviate(value)}" for value, repos in groups.items()
        )
        problems.append(
            Problem(
                kind=DIVERGENT,
                repo=", ".join(sorted({r for repos in groups.values() for r in repos})),
                field_path=path,
                detail=(
                    f"{path} holds {len(groups)} distinct values across the copies: "
                    f"{held}. These copies are ONE document; a field that differs means "
                    "they are not, and no copy is the innocent party until a person "
                    "says which one the document is"
                ),
            )
        )

    return FleetReport(
        root=str(root), copies=tuple(copies), problems=tuple(problems), refusal=None
    )


# ---------------------------------------------------------------------------
# the committable artifact, and the consumer-side pin (E-M39)
# ---------------------------------------------------------------------------
class ArtifactRefused(RuntimeError):
    """The artifact would carry something a committed file may not (a machine path)."""


def proof_sha256(doc: Mapping[str, Any]) -> str:
    """The seal over an artifact body: sha256 of its canonical JSON, seal excluded."""
    body = {k: v for k, v in doc.items() if k != PROOF_FIELD}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def artifact_document(
    report: FleetReport, *, mlkit_version: str, mlkit_build: str
) -> dict[str, Any]:
    """The committable form of one fleet-check run.

    Differs from :meth:`FleetReport.to_dict` in exactly the ways a committed
    file needs: no ``root`` and no ``path`` (machine paths), a one-word
    ``verdict`` beside the boolean, the mlkit that measured it, and the seal.
    Everything a reader needs to re-derive the verdict is inside it: each
    copy's HEAD, its register blob, what every repo's function computed over
    its body, and every problem by field.
    """
    verdict = "REFUSED" if report.refusal else ("FAIL" if report.problems else "PASS")
    doc: dict[str, Any] = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "verdict": verdict,
        "ok": report.ok,
        "mlkit": {"version": mlkit_version, "build": mlkit_build},
        "copies": [
            {
                "repo": c.repo,
                "head": c.head,
                "blob": c.blob,
                "stored_digest": c.stored_digest,
                "computed_by": dict(sorted(c.computed.items())),
                "agreed_digest": c.agreed_digest,
            }
            for c in report.copies
        ],
        "identical_blob": report.one_blob,
        "problems": [p.to_dict() for p in report.problems],
        "refusal": report.refusal,
    }
    doc[PROOF_FIELD] = proof_sha256(doc)
    return doc


def write_artifact(
    report: FleetReport, path: Path, *, mlkit_version: str, mlkit_build: str
) -> dict[str, Any]:
    """Write :func:`artifact_document` to ``path``; refuse a machine path in it."""
    from . import artifact as artifact_mod

    doc = artifact_document(report, mlkit_version=mlkit_version, mlkit_build=mlkit_build)
    offending = artifact_mod.machine_paths(doc)
    if offending:
        raise ArtifactRefused(
            "the fleet-check artifact would carry a machine path and is not written: "
            + "; ".join(f"{pointer} = {value!r}" for pointer, value in offending)
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def load_artifact(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegisterUnreadable(f"fleet-check artifact {Path(path).name}: {exc}") from exc
    if not isinstance(doc, dict):
        raise RegisterUnreadable(
            f"fleet-check artifact {Path(path).name} is a {type(doc).__name__}, not an object"
        )
    return doc


def verify_artifact(doc_or_path: Mapping[str, Any] | Path | str, repo_root: Path) -> list[str]:
    """Every reason a committed fleet-check artifact does not license the
    register this repository carries at ``HEAD``. Empty is the pin holding.

    This is the consumer-side half of E-M39: a test in each register-carrying
    repo asserts this returns ``[]``. Then a register edit with no fresh
    ``--check-fleet`` run is a red test in that repo -- the blob at ``HEAD``
    is not among the blobs the artifact compared -- and so is an artifact from
    a FAIL or REFUSED run, or one edited by hand to say PASS.

    It reads ``HEAD``, like the check it pins: an uncommitted register edit
    does not move this, and the same edit committed does.
    """
    problems: list[str] = []
    if isinstance(doc_or_path, (str, Path)):
        try:
            doc: Mapping[str, Any] = load_artifact(Path(doc_or_path))
        except RegisterUnreadable as exc:
            return [str(exc)]
    else:
        doc = doc_or_path

    if doc.get("artifact_schema") != ARTIFACT_SCHEMA:
        problems.append(
            f"artifact_schema is {doc.get('artifact_schema')!r}, not {ARTIFACT_SCHEMA!r}: "
            "this is not a fleet-check artifact mlkit wrote"
        )
        return problems
    stored = doc.get(PROOF_FIELD)
    computed = proof_sha256(doc)
    if stored != computed:
        problems.append(
            f"{PROOF_FIELD} is {str(stored)[:16]!r} but the body seals to {computed[:16]!r}: "
            "the artifact was edited after it was written, or was not written by "
            "`mlkit register --check-fleet --out`"
        )
    verdict = doc.get("verdict")
    if verdict != "PASS" or doc.get("ok") is not True:
        problems.append(
            f"verdict is {verdict!r}: a register change lands on a PASS, never on a "
            "FAIL or on a run that measured nothing"
            + (f" ({doc['refusal']})" if doc.get("refusal") else "")
        )
    copies = doc.get("copies") or []
    if len(copies) < 2:
        problems.append(
            f"{len(copies)} copy/copies compared: the invariant lives BETWEEN the repos "
            "and fewer than two is not a fleet check"
        )
    try:
        head_blob = _blob_id(Path(repo_root), REGISTER_RELPATH)
    except RegisterUnreadable as exc:
        problems.append(f"this repository's register at HEAD could not be read: {exc}")
        return problems
    compared = {c.get("blob") for c in copies if isinstance(c, Mapping)}
    if head_blob not in compared:
        shown = ", ".join(sorted(str(b)[:12] for b in compared)) or "none"
        problems.append(
            f"this repository's {REGISTER_RELPATH} at HEAD is blob {head_blob[:12]}, which "
            f"the artifact never compared (it compared: {shown}). The fleet check ran "
            "before this edit, or on another tree. Re-run `mlkit register --check-fleet "
            f"--root <checkouts> --out {ARTIFACT_RELPATH}` on this tree beside the "
            "other repositories and commit its output"
        )
    return problems
