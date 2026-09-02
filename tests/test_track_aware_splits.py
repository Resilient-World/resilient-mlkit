"""TRACK-AWARE SPLITS: does the refusal fire, and does the old path stay still.

WHAT THIS IS FOR
----------------
``resilient-fray`` runs TWO holdout policies over ONE county-year panel, and
says so in its own source (``src/validation/yield_holdout.py``):
``county_label_splits`` measures generalisation to an unseen COUNTY,
``county_year_splits`` to an unseen future YEAR. Two partitions, two grouping
vocabularies — 0.5° spatial block ids, and crop years.

``.mlkit/repo.toml`` had ONE ``splits`` key with ONE return value, and D6 ties
a declaration's blocks to ``splits[arm]``. So a declaration taken on the
crop-year track, in a repo publishing the county-block partition, compared crop
years against block ids and landed on ``BLOCKS_CONTRADICT_SPLITS`` — for a
partition it was never taken under. The reverse was equally true. **There was
no wiring of `splits` under which both of fray's tracks could be judged**, and
the dependence-unit contract was therefore structurally unadoptable by the
repo whose row bootstrap motivated it.

THE PAIRING THAT CARRIES THE WEIGHT
-----------------------------------
* **The single-track path does not move.** A flat ``splits`` produces the same
  verdicts, the same reasons and the same evidence KEYS it produced before
  tracks existed — no ``track``, ``blocks_tied_to == "splits"``.
* **Every R3 clause is applied to every track**, and a two-track fixture FAILs
  if either track alone would.
* **A declaration cannot be judged against a partition it did not name.**
  ``TRACK_UNDECLARED`` refuses the case where mlkit could otherwise pick the
  track whose blocks happen to match.
* **The guard is not dead.** Six single-fact remutations of the SILENT
  two-track declaration each produce a different named verdict.

No figure from any real run appears here. The shapes are fixtures built in this
file; the fray drive that used the repo's real split membership is recorded in
``reports/TRACK_AWARE_SPLITS_RESULTS.md``.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

import resilient_mlkit.checks.readiness as readiness_module
import resilient_mlkit.core.served as served_module
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.decision import (
    DUPLICATE_TRACK_DECLARATION,
    RESAMPLING_BINDING,
    TRACK_FIELD,
    TRACK_NOT_IN_SPLITS,
    TRACK_UNDECLARED,
    d6_resampling_unit,
)
from resilient_mlkit.checks.readiness import (
    MIN_HOLDOUT_GROUPS,
    SINGLE_TRACK,
    TRACKS_ARE_THE_SAME_PARTITION,
    TRACKS_KEY,
    TRACKS_MALFORMED,
    TRACKS_MIXED_WITH_FLAT,
    SplitsUnreadable,
    normalise_splits,
    normalise_tracked_splits,
    r3_blocked_splits,
)
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status
from resilient_mlkit.core.served import (
    DEPENDENCE_UNIT_TOO_FINE,
    LOWER_IS_BETTER,
    RESAMPLING_ROWS_UNTIED,
    UNIT_IS_THE_BLOCK,
    UNIT_LABEL_CONTRADICTS_CONTENT,
    Comparison,
    ResamplingDeclaration,
    RowUnit,
    ServedContractError,
    challenger_decision,
    row_set_digest,
)

#: The recorded bar a challenger is decided against. A label, not a figure.
BAR = "persistence_t_minus_1"

# The binding assertion the loop's rules require of every driver. Without it a
# green run here says nothing about the tree under review.
_EXPECTED = Path(__file__).resolve().parent.parent / "src" / "resilient_mlkit"
for _mod in (served_module, readiness_module):
    assert Path(_mod.__file__).resolve().parent.parent == _EXPECTED, (
        f"{_mod.__name__} resolved to {_mod.__file__}, not to {_EXPECTED}"
    )

_SERIAL = iter(range(10_000))


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

#: Two tracks over one panel, in fray's shape and fray's two vocabularies. The
#: rows are the same rows; only the partition and the block key differ.
COUNTIES = [f"C{i:02d}" for i in range(18)]
YEARS = list(range(2010, 2022))

#: county_block track: whole blocks to one arm; a county's whole history
#: travels with it. Two blocks in each holdout arm, because ONE would be
#: refused by R3's holdout floor and by SINGLE_UNIT, and a fixture that trips
#: an unrelated clause cannot show which clause the test is about.
BLOCK_OF_COUNTY = {c: f"B{i // 3}" for i, c in enumerate(COUNTIES)}
COUNTY_TRACK_ARM = {"B0": "train", "B1": "train", "B2": "val", "B3": "val",
                    "B4": "test", "B5": "test"}

#: crop_year track: whole years to one arm; a county appears in all three.
YEAR_ARM = {y: ("train" if y < 2018 else "val" if y < 2020 else "test") for y in YEARS}


def _panel_rows(track: str, unit: str) -> list[dict]:
    """One mapping per panel row, for `track`, resampled by `unit`."""
    rows = []
    for county in COUNTIES:
        for year in YEARS:
            row_key = f"{county}@{year}"
            if track == "county_block":
                block = BLOCK_OF_COUNTY[county]
                arm = COUNTY_TRACK_ARM[block]
            else:
                block = str(year)
                arm = YEAR_ARM[year]
            unit_key = {
                "block": block, "row": row_key, "county": county,
            }[unit]
            rows.append(
                {"row_key": row_key, "arm": arm, "block_key": block, "unit_key": unit_key}
            )
    return rows


def _groups(track: str) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    for r in _panel_rows(track, "block"):
        out[r["arm"]].add(r["block_key"])
    return {k: sorted(v) for k, v in out.items()}


TRACKED_SPLITS = {TRACKS_KEY: {"county_block": _groups("county_block"),
                               "crop_year": _groups("crop_year")}}
FLAT_SPLITS = _groups("crop_year")


def _declaration(track: str, *, unit: str = "block", name: str | None = None,
                 blocking_unit: str | None = None, arm: str = "val",
                 draws: int = 4000) -> dict:
    labels = {"block": track, "row": "row", "county": "county"}
    d = {
        "procedure": "block bootstrap",
        "draws": draws,
        "policy": f"{track}_policy",
        "blocking_unit": blocking_unit or track,
        "unit": labels[unit],
        "arm": arm,
        "assignment": _panel_rows(track, unit),
    }
    if name is not None:
        d[TRACK_FIELD] = name
    return d


def _repo(tmp_path: Path, splits_value, declaration_value,
          *, declare_binding: bool = True) -> Repo:
    """A repo on disk whose bindings return these two values, resolved the real
    way — no monkeypatch, so the binding path itself is under test."""
    import json

    module = f"trk_bindings_{next(_SERIAL)}"
    payload = tmp_path / f"{module}.json"
    payload.write_text(json.dumps({"s": splits_value, "d": declaration_value}))
    (tmp_path / f"{module}.py").write_text(
        textwrap.dedent(
            f"""
            import json
            _P = json.loads(open({str(payload)!r}).read())
            def splits():
                return _P["s"]
            def resampling_declaration():
                return _P["d"]
            """
        )
    )
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = f'[repo]\nname = "trkfixture"\n\n[bindings]\nsplits = "{module}:splits"\n'
    if declare_binding:
        toml += f'{RESAMPLING_BINDING} = "{module}:resampling_declaration"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True,
                   capture_output=True)
    return Repo(name="trkfixture", path=tmp_path)


def _run(tmp_path: Path, splits_value, declaration_value, **kw):
    repo = _repo(tmp_path, splits_value, declaration_value, **kw)
    ctx = RunContext(nonce="t", root=tmp_path, offline=True, timeout=10.0)
    try:
        return r3_blocked_splits(repo, ctx), d6_resampling_unit(repo, ctx)
    finally:
        repo.release()


# ---------------------------------------------------------------------------
# the parser
# ---------------------------------------------------------------------------

def test_a_flat_splits_is_the_single_unnamed_track_and_parses_identically() -> None:
    """The old shape goes down the old parser and lands on one key."""
    tracked = normalise_tracked_splits(FLAT_SPLITS)
    assert list(tracked) == [SINGLE_TRACK]
    assert tracked[SINGLE_TRACK] == normalise_splits(FLAT_SPLITS)


def test_the_tracked_envelope_is_recognised_by_the_reserved_key() -> None:
    tracked = normalise_tracked_splits(TRACKED_SPLITS)
    assert sorted(tracked) == ["county_block", "crop_year"]
    assert tracked["crop_year"] == normalise_splits(FLAT_SPLITS)


def test_nesting_is_NOT_inferred_from_value_types(tmp_path: Path) -> None:
    """A flat splits whose group ids come from a dict's keys stays flat.

    This is why the envelope is a reserved key rather than "the values look
    like mappings": ``{"train": {"a": 1}}`` is a partition whose train group is
    ``a``, and a reader that guessed would silently reinterpret it as a track
    named ``train``.
    """
    raw = {"train": {"a": 1, "b": 2}, "val": {"c": 3}, "test": {"d": 4}}
    tracked = normalise_tracked_splits(raw)
    assert list(tracked) == [SINGLE_TRACK]
    assert tracked[SINGLE_TRACK]["train"] == {"a", "b"}


def test_tracks_mixed_with_flat_is_refused_not_resolved() -> None:
    with pytest.raises(SplitsUnreadable) as exc:
        normalise_tracked_splits({TRACKS_KEY: {"a": FLAT_SPLITS}, "train": ["x"]})
    assert TRACKS_MIXED_WITH_FLAT in exc.value.reason
    assert exc.value.evidence["tracks_mixed_with"] == ["train"]


@pytest.mark.parametrize(
    "raw, marker",
    [
        ({TRACKS_KEY: 7}, "tracks_type"),
        ({TRACKS_KEY: {}}, "n_tracks"),
        ({TRACKS_KEY: {"   ": FLAT_SPLITS}}, "blank_track_name"),
        ({TRACKS_KEY: {"a": 7}}, "malformed_track"),
    ],
)
def test_the_envelope_refuses_every_shape_it_cannot_read(raw, marker) -> None:
    with pytest.raises(SplitsUnreadable) as exc:
        normalise_tracked_splits(raw)
    assert TRACKS_MALFORMED in exc.value.reason
    assert marker in exc.value.evidence


def test_the_character_splitting_defect_is_refused_INSIDE_a_track() -> None:
    """`normalise_splits`' own refusal, reached through the track reader.

    A ``str`` is iterable, so ``set(map(str, v))`` accepts one and splits it
    into characters. That parser refuses it; this asserts the tracked path does
    not get its own second reading of the same question.
    """
    with pytest.raises(SplitsUnreadable) as exc:
        normalise_tracked_splits(
            {TRACKS_KEY: {"t": {"train": "abc", "val": ["d", "e"], "test": ["f", "g"]}}}
        )
    assert "one group per letter" in exc.value.reason
    assert exc.value.evidence["malformed_track"] == "t"


def test_two_tracks_with_one_written_name_are_refused() -> None:
    with pytest.raises(SplitsUnreadable) as exc:
        normalise_tracked_splits({TRACKS_KEY: {1: FLAT_SPLITS, "1": FLAT_SPLITS}})
    assert exc.value.evidence["duplicate_track_name"] == "1"


# ---------------------------------------------------------------------------
# R3
# ---------------------------------------------------------------------------

def test_r3_single_track_evidence_has_no_track_shaped_key(tmp_path: Path) -> None:
    """The byte-compatibility claim, at the level a test can assert it."""
    r3, _ = _run(tmp_path, FLAT_SPLITS, _declaration("crop_year"))
    assert r3.status is Status.PASS
    assert r3.evidence == {"n_train": 8, "n_val": 2, "n_test": 2}


def test_r3_judges_both_tracks_and_passes_only_when_both_clear(tmp_path: Path) -> None:
    r3, _ = _run(tmp_path, TRACKED_SPLITS, _declaration("crop_year", name="crop_year"))
    assert r3.status is Status.PASS
    assert r3.evidence["tracks"] == ["county_block", "crop_year"]
    assert r3.evidence["per_track"]["county_block"] == {"n_train": 2, "n_val": 2, "n_test": 2}
    assert r3.evidence["per_track"]["crop_year"] == {"n_train": 8, "n_val": 2, "n_test": 2}
    # recorded, interpreted nowhere: block ids and crop years are two
    # vocabularies and an equal string between them means nothing.
    assert r3.evidence["group_ids_shared_between_tracks"] == {"county_block&crop_year": 0}


def test_r3_FIRES_when_ONE_track_is_below_the_holdout_floor(tmp_path: Path) -> None:
    """B-3 firing half: the floor is applied per track, not to the union."""
    thin = {TRACKS_KEY: {
        "county_block": {"train": ["B0", "B1"], "val": ["B2"], "test": ["B3"]},
        "crop_year": _groups("crop_year"),
    }}
    r3, _ = _run(tmp_path, thin, _declaration("crop_year", name="crop_year"))
    assert r3.status is Status.FAIL
    assert "track 'county_block'" in r3.reason
    assert "holdout too thin" in r3.reason
    assert f">= {MIN_HOLDOUT_GROUPS}" in r3.reason
    # kept whole in the record, because the summary is bounded at MAX_REASON
    assert r3.evidence["failures"] == [r3.reason]
    assert "crop_year" not in r3.reason.split("track 'county_block'")[1][:80]


def test_r3_SILENT_when_the_same_track_clears_the_floor(tmp_path: Path) -> None:
    """B-3 silent half: one group added to val, nothing else changed."""
    ok = {TRACKS_KEY: {
        "county_block": {"train": ["B0"], "val": ["B1", "B2"], "test": ["B3", "B4"]},
        "crop_year": _groups("crop_year"),
    }}
    r3, _ = _run(tmp_path, ok, _declaration("crop_year", name="crop_year"))
    assert r3.status is Status.PASS


def test_r3_FIRES_when_one_track_overlaps(tmp_path: Path) -> None:
    leaky = {TRACKS_KEY: {
        "county_block": {"train": ["B0", "B2"], "val": ["B2", "B5"], "test": ["B3", "B4"]},
        "crop_year": _groups("crop_year"),
    }}
    r3, _ = _run(tmp_path, leaky, _declaration("crop_year", name="crop_year"))
    assert r3.status is Status.FAIL
    assert "track 'county_block'" in r3.reason
    assert "groups appear in more than one split" in r3.reason


def test_r3_FIRES_when_two_tracks_are_one_partition_twice(tmp_path: Path) -> None:
    """B-8: the cheap way to make a per-track verdict vacuous."""
    doubled = {TRACKS_KEY: {"a": _groups("crop_year"), "b": _groups("crop_year")}}
    r3, _ = _run(tmp_path, doubled, _declaration("crop_year", name="a"))
    assert r3.status is Status.FAIL
    assert TRACKS_ARE_THE_SAME_PARTITION in r3.reason
    assert "a&b" in r3.reason


def test_r3_SILENT_when_the_two_tracks_differ_by_one_group(tmp_path: Path) -> None:
    """B-8 silent half: one group moved, and the pair is no longer one
    partition under two names."""
    other = {k: list(v) for k, v in _groups("crop_year").items()}
    other["val"] = other["val"] + other["train"][-1:]
    other["train"] = other["train"][:-1]
    r3, _ = _run(tmp_path, {TRACKS_KEY: {"a": _groups("crop_year"), "b": other}},
                 _declaration("crop_year", name="a"))
    assert r3.status is Status.PASS


# ---------------------------------------------------------------------------
# the declaration
# ---------------------------------------------------------------------------

def _rows(track: str, unit: str) -> list[RowUnit]:
    return [RowUnit(**r) for r in _panel_rows(track, unit)]


def test_the_track_is_DECLARED_and_the_derived_facts_still_are_not() -> None:
    d = ResamplingDeclaration(
        procedure="p", draws=10, policy="pol", blocking_unit="crop_year",
        unit="crop_year", arm="val", assignment=_rows("crop_year", "block"),
        track="crop_year",
    )
    assert d.track == "crop_year"
    assert d.relation == UNIT_IS_THE_BLOCK
    for spelled in ("n_units_in_arm", "unit_digest", "relation", "refusal"):
        with pytest.raises(TypeError, match=spelled):
            ResamplingDeclaration(
                procedure="p", draws=10, policy="pol", blocking_unit="crop_year",
                unit="crop_year", arm="val", assignment=_rows("crop_year", "block"),
                track="crop_year", **{spelled: 1},
            )


def test_to_dict_carries_the_track_only_when_it_is_set() -> None:
    kw = {"procedure": "p", "draws": 10, "policy": "pol",
          "blocking_unit": "crop_year", "unit": "crop_year", "arm": "val"}
    without = ResamplingDeclaration(**kw, assignment=_rows("crop_year", "block")).to_dict()
    with_track = ResamplingDeclaration(
        **kw, assignment=_rows("crop_year", "block"), track="crop_year"
    ).to_dict()
    assert TRACK_FIELD not in without
    assert with_track[TRACK_FIELD] == "crop_year"
    assert {k: v for k, v in with_track.items() if k != TRACK_FIELD} == without


@pytest.mark.parametrize("bad, match", [(" ", "whitespace"), (7, "is a int"), (None, "NoneType")])
def test_a_track_that_cannot_point_at_a_name_is_refused(bad, match) -> None:
    with pytest.raises(ServedContractError, match=match):
        ResamplingDeclaration(
            procedure="p", draws=10, policy="pol", blocking_unit="crop_year",
            unit="crop_year", arm="val", assignment=_rows("crop_year", "block"),
            track=bad,
        )


# ---------------------------------------------------------------------------
# D6
# ---------------------------------------------------------------------------

def test_d6_single_track_pass_is_tied_to_splits_by_that_exact_word(tmp_path: Path) -> None:
    """The byte-compatibility claim on D6's side."""
    _, d6 = _run(tmp_path, FLAT_SPLITS, _declaration("crop_year"))
    assert d6.status is Status.PASS
    assert d6.evidence["blocks_tied_to"] == "splits"
    assert TRACK_FIELD not in d6.evidence
    assert "tracks_in_splits" not in d6.evidence


def test_d6_judges_EACH_track_against_ITS_OWN_partition(tmp_path: Path) -> None:
    """A-2's shape: two declarations, two partitions, two verdicts."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS,
                 [_declaration("county_block", name="county_block"),
                  _declaration("crop_year", name="crop_year")])
    assert d6.status is Status.PASS
    tied = {d["track"]: d["evidence"]["blocks_tied_to"] for d in d6.evidence["declarations"]}
    assert tied == {"county_block": f"splits.{TRACKS_KEY}.county_block",
                    "crop_year": f"splits.{TRACKS_KEY}.crop_year"}
    assert d6.evidence["tracks_without_declaration"] == []


def test_d6_the_SAME_declaration_against_the_WRONG_track_FAILS(tmp_path: Path) -> None:
    """The whole finding, in one assertion: the crop-year declaration judged
    against the county-block partition is BLOCKS_CONTRADICT_SPLITS, and judged
    against its own is PASS. One field differs."""
    _, wrong = _run(tmp_path, TRACKED_SPLITS,
                    [_declaration("crop_year", name="county_block")])
    assert wrong.status is Status.FAIL
    assert "BLOCKS_CONTRADICT_SPLITS" in wrong.reason
    _, right = _run(tmp_path, TRACKED_SPLITS,
                    [_declaration("crop_year", name="crop_year")])
    assert right.status is Status.PASS


def test_d6_FIRES_TRACK_UNDECLARED_rather_than_picking_the_track_that_matches(
    tmp_path: Path,
) -> None:
    """B-5 firing half. The crop-year declaration's blocks DO match the
    crop_year track exactly, so a reader that searched for a match would report
    PASS. That is a check selecting the operand of its own verdict."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS, _declaration("crop_year"))
    assert d6.status is Status.FAIL
    assert TRACK_UNDECLARED in d6.reason
    assert d6.evidence["tracks_in_splits"] == ["county_block", "crop_year"]


def test_d6_SILENT_when_that_same_declaration_names_its_track(tmp_path: Path) -> None:
    """B-5 silent half: one key added, nothing else."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS, _declaration("crop_year", name="crop_year"))
    assert d6.status is Status.PASS


def test_d6_FIRES_when_the_named_track_is_not_in_a_FLAT_splits(tmp_path: Path) -> None:
    """B-6, the half that catches a half-finished adoption: the declaration was
    updated to name a track and `splits` was not."""
    _, d6 = _run(tmp_path, FLAT_SPLITS, _declaration("crop_year", name="crop_year"))
    assert d6.status is Status.FAIL
    assert TRACK_NOT_IN_SPLITS in d6.reason
    assert "declares no tracks at all" in d6.reason
    assert d6.evidence["tracks_in_splits"] == []


def test_d6_FIRES_when_the_named_track_is_absent_from_a_TRACKED_splits(
    tmp_path: Path,
) -> None:
    _, d6 = _run(tmp_path, TRACKED_SPLITS, _declaration("crop_year", name="nope"))
    assert d6.status is Status.FAIL
    assert TRACK_NOT_IN_SPLITS in d6.reason
    assert d6.evidence["tracks_in_splits"] == ["county_block", "crop_year"]


def test_d6_FIRES_on_two_declarations_naming_one_track(tmp_path: Path) -> None:
    """B-7 firing half, and it fires BEFORE either is judged: two intervals over
    one partition are two answers to one question."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS,
                 [_declaration("crop_year", name="crop_year"),
                  _declaration("crop_year", name="crop_year", unit="row")])
    assert d6.status is Status.FAIL
    assert DUPLICATE_TRACK_DECLARATION in d6.reason
    # the row declaration is NOT judged -- the duplicate is answered first
    assert DEPENDENCE_UNIT_TOO_FINE not in d6.reason


def test_d6_FIRES_on_two_declarations_that_both_name_nothing(tmp_path: Path) -> None:
    """The same refusal reaches the empty name, which is the one a careless
    sequence gets by default."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS,
                 [_declaration("crop_year"), _declaration("county_block")])
    assert d6.status is Status.FAIL
    assert DUPLICATE_TRACK_DECLARATION in d6.reason


def test_d6_records_a_track_nobody_declared_rather_than_refusing_it(
    tmp_path: Path,
) -> None:
    """RECORDED, NOT REFUSED, and the pre-registration says so in advance:
    mlkit cannot know whether a track produced an interval at all."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS, [_declaration("crop_year", name="crop_year")])
    assert d6.status is Status.PASS
    assert d6.evidence["tracks_without_declaration"] == ["county_block"]


def test_d6_the_worst_of_the_per_track_verdicts_is_the_verdict(tmp_path: Path) -> None:
    _, d6 = _run(tmp_path, TRACKED_SPLITS,
                 [_declaration("county_block", name="county_block"),
                  _declaration("crop_year", name="crop_year", unit="row")])
    assert d6.status is Status.FAIL
    assert "track 'crop_year'" in d6.reason
    assert DEPENDENCE_UNIT_TOO_FINE in d6.reason
    statuses = {d["track"]: d["status"] for d in d6.evidence["declarations"]}
    assert statuses == {"county_block": "PASS", "crop_year": "FAIL"}
    # the full detail survives the 400-character reason cap, in the record
    detail = next(d for d in d6.evidence["declarations"] if d["track"] == "crop_year")
    assert "manufactured more evidence out of the arm" in detail["evidence"]["detail"]


@pytest.mark.parametrize(
    "value, marker",
    [
        (7, "returned a int"),
        ("nope", "returned a str"),
        ([], "empty sequence"),
        ([7], "[0] is a int"),
    ],
)
def test_d6_refuses_a_shape_it_cannot_read_by_type(tmp_path: Path, value, marker) -> None:
    """A bare sequence is refused rather than reassembled: ``dict()`` accepts a
    list of pairs, and a declaration built out of whatever pairs happened to
    land would carry fields nobody wrote."""
    _, d6 = _run(tmp_path, TRACKED_SPLITS, value)
    assert d6.status is Status.FAIL
    assert marker in d6.reason


def test_d6_a_sequence_still_reaches_the_untied_operand_NA(tmp_path: Path) -> None:
    """`splits` unreadable is NA on every track, from ONE read of the binding."""
    _, d6 = _run(tmp_path, {TRACKS_KEY: {"a": {"train": "abc", "val": ["d"], "test": ["e"]}}},
                 [_declaration("crop_year", name="crop_year")])
    assert d6.status is Status.NA
    assert "BLOCKS_UNTIED" in d6.reason


# ---------------------------------------------------------------------------
# the hole a second track could have opened one layer up
# ---------------------------------------------------------------------------

def test_a_declaration_from_the_WRONG_TRACK_is_caught_by_CONTENT_at_the_gate() -> None:
    """The gap a per-track declaration could have opened, driven rather than
    argued.

    ``Comparison`` ties its interval to its declaration by ARM
    (``declaration.arm != self.arm`` raises), and both of fray's tracks have an
    arm called ``val``. So the name-level tie cannot separate them, and adding
    a ``track`` field to ``Comparison`` would be one more name to compare.

    It does not have to: ``challenger_decision`` ties them by CONTENT, through
    ``row_set_digest`` — the interval's row digest against the figure's. The
    two tracks' val arms are different rows, so a declaration borrowed from the
    other track is ``RESAMPLING_ROWS_UNTIED`` on the digests alone. Asserted
    here so the claim is measured, and so a future change that drops the digest
    tie fails this test rather than passing quietly.
    """
    def val_rows(track: str) -> list[str]:
        return [r["row_key"] for r in _panel_rows(track, "block") if r["arm"] == "val"]

    def declare(track: str) -> ResamplingDeclaration:
        return ResamplingDeclaration(
            procedure="block bootstrap", draws=4000, policy=f"{track}_policy",
            blocking_unit=track, unit=track, arm="val",
            assignment=_rows(track, "block"), track=track,
        )

    own, other = declare("crop_year"), declare("county_block")
    assert own.row_digest == row_set_digest(val_rows("crop_year"))
    assert own.row_digest != other.row_digest

    def compare(declaration: ResamplingDeclaration) -> Comparison:
        return Comparison(
            reference=BAR, metric="mae", candidate_value=1.0, reference_value=2.0,
            n_rows=len(val_rows("crop_year")), arm="val", polarity=LOWER_IS_BETTER,
            candidate_row_digest=row_set_digest(val_rows("crop_year")),
            reference_row_digest=row_set_digest(val_rows("crop_year")),
            skill_interval_low=0.1, skill_interval_high=0.9,
            resampling=declaration,
        )

    borrowed = challenger_decision([compare(other)], recorded_bar=BAR, metrics=["mae"])
    assert borrowed.refusal_class == RESAMPLING_ROWS_UNTIED
    assert borrowed.status is Status.NA

    matched = challenger_decision([compare(own)], recorded_bar=BAR, metrics=["mae"])
    assert matched.refusal_class != RESAMPLING_ROWS_UNTIED


# ---------------------------------------------------------------------------
# the guard is not dead
# ---------------------------------------------------------------------------

def test_the_two_track_silence_is_the_code_deciding(tmp_path: Path) -> None:
    """Six single-fact remutations of the SILENT two-track declaration, each
    producing a DIFFERENT named verdict. Silence that survives every mutation
    is a check that is not looking."""
    base_decls = [_declaration("county_block", name="county_block"),
                  _declaration("crop_year", name="crop_year")]
    _, silent = _run(tmp_path, TRACKED_SPLITS, base_decls)
    assert silent.status is Status.PASS

    def mutate(fn, splits_value=TRACKED_SPLITS):
        import copy
        d = copy.deepcopy(base_decls)
        fn(d)
        return _run(tmp_path, splits_value, d)[1]

    seen: dict[str, str] = {}

    # 1. the crop-year track resampled by row
    r = mutate(lambda d: d[1].update(unit="row", assignment=_panel_rows("crop_year", "row")))
    assert r.status is Status.FAIL and DEPENDENCE_UNIT_TOO_FINE in r.reason
    seen["row_unit"] = r.reason

    # 2. the crop-year declaration points at the other track. The county-block
    #    declaration is dropped in the same breath, because leaving it in would
    #    make the pair DUPLICATE_TRACK_DECLARATION -- which is itself the
    #    correct answer, and is asserted on its own above.
    def _point_at_the_other_track(d):
        d.pop(0)
        d[0].update(track="county_block")

    r = mutate(_point_at_the_other_track)
    assert r.status is Status.FAIL and "BLOCKS_CONTRADICT_SPLITS" in r.reason
    seen["wrong_track"] = r.reason

    # 3. the crop-year declaration points at nothing
    r = mutate(lambda d: d[1].pop(TRACK_FIELD))
    assert r.status is Status.FAIL and TRACK_UNDECLARED in r.reason
    seen["no_track"] = r.reason

    # 4. the crop-year declaration points at a track that does not exist
    r = mutate(lambda d: d[1].update(track="unseen_year"))
    assert r.status is Status.FAIL and TRACK_NOT_IN_SPLITS in r.reason
    seen["absent_track"] = r.reason

    # 5. the crop-year declaration keeps its LABEL and changes its content
    r = mutate(lambda d: d[1].update(assignment=_panel_rows("crop_year", "county")))
    assert r.status is Status.FAIL and UNIT_LABEL_CONTRADICTS_CONTENT in r.reason
    seen["label_contradicts_content"] = r.reason

    # 6. `splits` drops one crop year from val
    thinned = {TRACKS_KEY: {
        "county_block": _groups("county_block"),
        "crop_year": {**_groups("crop_year"), "val": _groups("crop_year")["val"][:1]},
    }}
    r = mutate(lambda d: None, splits_value=thinned)
    assert r.status is Status.FAIL and "BLOCKS_CONTRADICT_SPLITS" in r.reason
    seen["splits_moved"] = r.reason

    assert len(set(seen.values())) == len(seen), "two mutations produced one message"
