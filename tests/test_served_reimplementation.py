"""R12 controls: does the check fire on a re-implementation, and stay silent on an import.

Every test is one half of a matched pair, and the pairs are built the same way
R11's are: the POSITIVE fixture carries the defect, and the NEGATIVE fixture is
THE SAME FILE with one thing changed — here, an import line and the call that
uses it. The variable in the experiment is whether the file routes through
``resilient_mlkit.core.served``, never how it is spelled or where it lives.

The two module-level fixtures are reduced forms of the real thing. ``TORRENT``
is the shape of
``resilient-torrent/src/torrent/mlops/champion_challenger.py:30-40,118-141`` —
a promotion verdict held as a bare ``promote: bool``. ``SERVING`` is the shape
of the three serving modules' common core: a canonical-JSON self-hash, a
champion record that verifies it at load, and a serve-arm constant.
"""

from __future__ import annotations

import textwrap

from resilient_mlkit.core import served_reimplementation as sr

# The champion/challenger shape, minus the contract.
TORRENT = """
    from __future__ import annotations

    from dataclasses import dataclass


    @dataclass(frozen=True)
    class ChallengerResult:
        model_id: str
        aal_baseline: float
        aal_challenger: float
        promote: bool


    class ChampionChallenger:
        def __init__(self, aal_tolerance_pct: float = 5.0) -> None:
            self.aal_tolerance = aal_tolerance_pct / 100.0

        def evaluate(self, model_id, aal_baseline, aal_challenger) -> ChallengerResult:
            deviation = (
                abs(aal_challenger - aal_baseline) / aal_baseline
                if aal_baseline != 0
                else 0.0
            )
            return ChallengerResult(
                model_id=model_id,
                aal_baseline=aal_baseline,
                aal_challenger=aal_challenger,
                promote=deviation < self.aal_tolerance,
            )
"""

# The serving-module shape, minus the contract.
SERVING = """
    from __future__ import annotations

    import hashlib
    import json
    from pathlib import Path

    HASH_KEY = "artifact_sha256"
    RECORDED_BAR = "persistence_t_minus_1"
    SERVEABLE_ARMS = ("val", "train")


    def canonical_payload_sha256(payload):
        body = {k: v for k, v in payload.items() if k != HASH_KEY}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


    class CountyYieldChampion:
        def __init__(self, payload):
            self.payload = payload

        @classmethod
        def from_payload(cls, payload):
            recorded = payload.get(HASH_KEY)
            if recorded != canonical_payload_sha256(payload):
                raise RuntimeError("champion artifact hash mismatch")
            return cls(payload)

        def verify_checkpoint(self, path: Path) -> str:
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()


    def challenger_gate(reference_block):
        bar = reference_block.get(RECORDED_BAR)
        if bar is None:
            return {"status": "FAIL", "promotable": False, "reason": "not compared"}
        return {"status": "PASS", "promotable": bar > 0.0, "reason": "measured"}


    def serve(arm):
        if arm not in SERVEABLE_ARMS:
            raise SystemExit(f"refusing to serve the {arm!r} arm")
        return arm
"""

# The SAME two files, changed in one way: they import the contract and call it.
# The SAME two files, changed in one way: they import the contract and delegate
# to it. The class names, the constant names and the function names are held
# IDENTICAL to the positives on purpose — if the fixtures also dropped the
# shapes, their silence would be attributable to the missing shapes rather than
# to the import, and the pair would prove nothing. That property is not assumed:
# ``test_the_negative_controls_are_load_bearing`` strips the import line from
# each of these and asserts both fire.
TORRENT_ADOPTED = """
    from __future__ import annotations

    from resilient_mlkit.core.served import Comparison, challenger_decision


    class ChampionChallenger:
        def __init__(self, recorded_bar: str = "aal_baseline") -> None:
            self.recorded_bar = recorded_bar

        def evaluate_challenger(self, aal_baseline, aal_challenger, n_rows):
            return challenger_decision(
                [
                    Comparison(
                        self.recorded_bar, "aal", aal_challenger, aal_baseline, n_rows
                    )
                ],
                recorded_bar=self.recorded_bar,
                metrics=("aal",),
            )
"""

SERVING_ADOPTED = """
    from __future__ import annotations

    from pathlib import Path

    from resilient_mlkit.core.served import ServeArms, ServedModel

    RECORDED_BAR = "persistence_t_minus_1"
    SERVEABLE_ARMS = ServeArms(
        open={"val", "train"}, closed={"test": "closed at two reads"}
    )


    class CountyYieldChampion:
        @classmethod
        def from_payload(cls, payload, root: Path):
            return ServedModel.from_payload(payload, root=root)


    def challenger_gate(block):
        raise NotImplementedError("the contract decides; see ServedModel")


    def serve(arm):
        if arm not in SERVEABLE_ARMS.open:
            raise SystemExit(f"refusing to serve the {arm!r} arm")
        return SERVEABLE_ARMS.require(arm)
"""


def write_repo(root, files):
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# E-079: after the serve-arm exemption became the DECISION's, a fixture that
# routes its PROMOTION logic through the contract and still declares its arms
# as a bare tuple is no longer silent — it is the shape torrent measured. So
# the SILENT halves below have to say where the ARM comes from as well, and
# ``serving()`` is how they say it. Substituting one line keeps every other
# shape in the fixture identical, which is the property that makes the pair a
# pair.
# ---------------------------------------------------------------------------
SERVING_ARM_LINE = 'SERVEABLE_ARMS = ("val", "train")'

#: The arm policy taken FROM the contract, in the three import spellings.
ARMS_FROM_NAME = 'ServeArms(open={"val", "train"}, closed={"test": "held"})'
ARMS_FROM_CHAIN = (
    'resilient_mlkit.core.served.ServeArms(open={"val", "train"},'
    ' closed={"test": "held"})'
)
ARMS_FROM_ALIAS = 'served.ServeArms(open={"val", "train"}, closed={"test": "held"})'


def serving(arms=None):
    """``SERVING`` with its serve-arm policy replaced by ``arms``.

    ``None`` leaves the local tuple in place, which is the FIRES half.
    """
    source = textwrap.dedent(SERVING)
    assert SERVING_ARM_LINE in source, "the fixture's arm line has moved"
    if arms is None:
        return source
    return source.replace(SERVING_ARM_LINE, f"SERVEABLE_ARMS = {arms}")


def serve_arm_rows(findings):
    return [f for f in findings if f.clause == "SERVE_ARM"]


def non_serve_arm_rows(findings):
    return [f for f in findings if f.clause != "SERVE_ARM"]


# ---------------------------------------------------------------------------
# The pair the check exists for
# ---------------------------------------------------------------------------
def test_positive_control_a_repo_that_reimplements_is_named(tmp_path):
    """POSITIVE. The scanner names the file, not merely the repo."""
    root = write_repo(
        tmp_path,
        {
            "src/torrent/mlops/champion_challenger.py": TORRENT,
            "src/serve/county_yield.py": SERVING,
            "src/data/loader.py": "def load():\n    return []\n",
        },
    )
    findings, walked = sr.scan_repo(root)
    assert walked == 3
    named = {f.path for f in findings}
    assert "src/torrent/mlops/champion_challenger.py" in named
    assert "src/serve/county_yield.py" in named
    assert "src/data/loader.py" not in named


def test_negative_control_a_repo_that_imports_the_contract_is_silent(tmp_path):
    """NEGATIVE. The same two modules, routed through the contract."""
    root = write_repo(
        tmp_path,
        {
            "src/torrent/mlops/champion_challenger.py": TORRENT_ADOPTED,
            "src/serve/county_yield.py": SERVING_ADOPTED,
            "src/data/loader.py": "def load():\n    return []\n",
        },
    )
    findings, walked = sr.scan_repo(root)
    assert walked == 3
    assert findings == []


def test_the_negative_controls_are_load_bearing():
    """A control on the control: is the silence attributable to the import?

    A negative fixture that carries no detectable shape would be silent whatever
    the check did, and a pair built on one proves nothing. So each adopted
    fixture has its import line — and only its import line — removed, and both
    must then fire. Written after the first version of ``TORRENT_ADOPTED``
    failed exactly this: it was silent with the import stripped, because it had
    dropped the class names along with the local logic.
    """
    for name, source in (("SERVING", SERVING_ADOPTED), ("TORRENT", TORRENT_ADOPTED)):
        stripped = "\n".join(
            line
            for line in textwrap.dedent(source).splitlines()
            if "resilient_mlkit" not in line
        )
        findings = sr.scan_source(stripped, "src/x.py")
        assert findings, f"{name}_ADOPTED is silent without the import; it proves nothing"


# ---------------------------------------------------------------------------
# Each clause, fired and silenced on its own
# ---------------------------------------------------------------------------
def scan(source, display="src/serve/thing.py"):
    return sr.scan_source(textwrap.dedent(source), display)


def clauses(findings):
    return {f.clause for f in findings}


def test_self_hash_clause_fires_and_the_import_silences_it():
    positive = """
        import hashlib
        import json

        def canonical_payload_sha256(payload):
            body = {k: v for k, v in payload.items() if k != "artifact_sha256"}
            return hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
    """
    assert "SELF_HASH" in clauses(scan(positive))

    negative = """
        from resilient_mlkit.core.served import canonical_payload_sha256

        def artifact_digest(payload):
            return canonical_payload_sha256(payload)
    """
    assert scan(negative) == []


def test_self_hash_survives_being_split_across_two_statements():
    """The evasion is a newline, so the detector cannot be expression-shaped.

    Found by measurement, not by reading: the first version of this scanner
    required the ``json.dumps`` to sit inside the ``sha256`` call's own
    subtree, and assigning it to a local first defeated it.
    """
    findings = scan("""
        import hashlib
        import json

        HASH_KEY = "artifact_sha256"

        def digest(payload):
            body = {k: v for k, v in payload.items() if k != HASH_KEY}
            blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    """)
    assert "SELF_HASH" in clauses(findings)


def test_a_function_merely_named_like_a_self_hash_is_not_one():
    """NEGATIVE, from two more real files.

    ``resilient-torrent/src/torrent/api/routers/v4_avoided_loss.py:29``
    (``_canonical_hash``, a cache key over an API request) and
    ``resilient-blackout/resilient_blackout/mlops/checkpoint_sidecar.py:87``
    (``artifact_sha256``, a chunked hash of a file's bytes). Both were reported
    by a function-name list, and neither is an artifact self-hash. The list was
    removed rather than trimmed: it found nothing the shape rule missed.
    """
    assert scan("""
        import hashlib
        import json

        def _canonical_hash(request):
            payload = json.dumps(
                request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
            return hashlib.sha256(payload).hexdigest()
    """) == []
    assert scan("""
        import hashlib
        from pathlib import Path

        def artifact_sha256(path):
            digest = hashlib.sha256()
            with Path(path).open("rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
            return digest.hexdigest()
    """) == []


def test_a_run_fingerprint_is_not_a_self_hash():
    """NEGATIVE, and this one is a real file rather than an invented fixture.

    The shape below is ``resilient-surge/src/resilient_surge/mlops/
    reproducibility.py:34-36`` and ``governance/audit_trail.py:176-179``,
    reduced: a sha256 over canonical JSON, with nothing excluded. It fingerprints
    a run config and an audit record; neither is a served-model artifact digest,
    and a check that reported them would be a check nobody leaves switched on.

    The exclusion of the hash field is therefore the trigger, not the canonical
    serialisation — a digest stored inside the object it covers must omit
    itself, and nothing else needs to.
    """
    assert scan("""
        import hashlib
        import json

        def compute_hash(data):
            payload = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(payload.encode()).hexdigest()
    """) == []


def test_promotion_verdict_fires_on_a_bare_bool_field():
    """The torrent shape: a verdict with no status, so NA cannot exist."""
    findings = scan("""
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class ChallengerResult:
            model_id: str
            promote: bool
    """)
    assert "PROMOTION_VERDICT" in clauses(findings)
    assert any(f.symbol == "ChallengerResult.promote" for f in findings)


def test_promotion_verdict_fires_on_a_gate_the_name_list_never_heard_of():
    """The structural rule, from the case that exposed the need for it.

    ``resilient-arabica/src/registry/backbone_promotion.py:40`` decides whether
    a challenger backbone qualifies for promotion over the champion, and the
    function-name vocabulary was silent on it because nobody had listed
    ``evaluate_backbone_gate``. Chasing names loses; emitting PASS and FAIL from
    a function declared in a promotion context does not depend on the name.
    """
    findings = scan("""
        def evaluate_backbone_gate(champion_rmse, challenger_rmse):
            if challenger_rmse < champion_rmse:
                return {"result": "PASS"}
            return {"result": "FAIL"}
    """, display="src/registry/backbone_promotion.py")
    assert "PROMOTION_VERDICT" in clauses(findings)


def test_a_validation_script_that_merely_calls_a_gate_is_not_a_promotion():
    """NEGATIVE, from two real files.

    ``resilient-choco/src/validation/giews_drought_validation.py:156`` and
    ``resilient-fray/src/validation/belt_drought_barometer.py:42`` print PASS
    and FAIL and call a helper whose name contains "gate". Neither decides a
    promotion. An earlier version of the structural rule matched any identifier
    anywhere in the scope and reported both; the context is now the
    declaration — module path, class, function name — because where a function
    is declared is a claim about what it is, and what it happens to call is not.
    """
    assert scan("""
        def main(argv=None):
            ok = gate_drought_series(argv)
            print("PASS" if ok else "FAIL")
            return 0
    """, display="src/validation/giews_drought_validation.py") == []


def test_promotion_verdict_fires_on_a_verdict_dict():
    findings = scan("""
        def decide(skill):
            return {"status": "PASS", "promotable": skill > 0, "reason": "measured"}
    """)
    assert "PROMOTION_VERDICT" in clauses(findings)


def test_a_configuration_dict_with_a_promote_key_is_not_a_verdict():
    """NEGATIVE. A settings blob is not a gate, and the check knows the difference."""
    findings = scan("""
        DEFAULTS = {"promote": False, "traffic_fraction": 0.1, "seed": 42}
    """)
    assert findings == []


def test_serve_arm_clause_fires_on_a_local_policy_and_on_an_inline_refusal():
    constant = scan("""
        SERVEABLE_ARMS = ("val", "train")
    """)
    assert "SERVE_ARM" in clauses(constant)

    inline = scan("""
        def serve(arm):
            if arm == "test":
                raise SystemExit("refusing to serve the test arm")
            return arm
    """)
    assert "SERVE_ARM" in clauses(inline)


def test_serve_arm_does_not_fire_on_the_letters_a_r_m_inside_another_word():
    """NEGATIVE, from real files: ``farm_size_col`` and ``_IPCC_WARMING``.

    The first version of the arm detector matched ``"arm" in name.lower()`` and
    reported four files across choco, arabica and blackout — all of them on the
    words *farm* and *warming*. The shapes below are
    ``resilient-choco/src/analysis/did_impact.py:404``,
    ``resilient-choco/src/api/config.py:347`` and
    ``resilient-blackout/resilient_blackout/climate/storyline.py:103``, reduced.
    """
    assert scan("""
        def att(matched_df, farm_size_col):
            if farm_size_col not in matched_df.columns:
                raise ValueError("column not found")
    """) == []
    assert scan("""
        _IPCC_WARMING = {"ssp126": 1.5}

        def build(climate_scenario):
            if climate_scenario not in _IPCC_WARMING:
                raise ValueError("unknown scenario")
    """) == []


def test_serve_arm_does_not_fire_on_an_ensembles_arm_set():
    """NEGATIVE. A different sense of the word, from a real file.

    ``resilient-chokepoint/src/resilient_chokepoint/forecasting/
    corridor_pooling.py:525`` asserts that an ensemble's arms are in their
    declared order. It genuinely says "arm", and it is not a serving decision:
    it names no train/val/test arm and no declared serve-arm policy.
    """
    assert scan("""
        ARM_NAMES = ("ridge", "gru", "persistence")

        def ordered(arms):
            if [arm.name for arm in arms] != list(ARM_NAMES):
                raise RuntimeError("arm set does not match the declared ARM_NAMES")
            return arms
    """) == []


def test_provenance_clause_fires_on_a_local_verifier():
    findings = scan("""
        import hashlib

        def verify_recorded_checkpoint(path, expected):
            actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            if actual != expected:
                raise RuntimeError("not the measured model")
            return path
    """)
    assert "PROVENANCE" in clauses(findings)


def test_shadow_router_is_reported_at_the_lower_severity():
    findings = scan("""
        class ShadowRouter:
            def __init__(self, champion, challenger):
                self.champion = champion
                self.challenger = challenger
    """)
    assert [f.severity for f in findings] == [sr.SERVING_ADJACENT]
    assert clauses(findings) == {"SHADOW_ROUTER"}


def test_a_champion_named_class_without_record_behaviour_is_not_a_finding():
    """NEGATIVE. The word in a name is not the contract."""
    assert scan("""
        class ChampionshipRegion:
            def area(self):
                return 0.0
    """) == []


def test_a_champion_record_with_load_behaviour_is_a_finding():
    findings = scan("""
        class WeeklyMortalityChampion:
            @classmethod
            def from_payload(cls, payload):
                return cls()
    """)
    assert clauses(findings) == {"CHAMPION_RECORD"}
    assert findings[0].severity == sr.SERVING_ADJACENT


# ---------------------------------------------------------------------------
# The exemption, and its limits
# ---------------------------------------------------------------------------
def test_one_level_of_indirection_through_a_repo_adapter_is_exempt(tmp_path):
    """A repo may put the contract behind one thin adapter of its own.

    SILENT for the promotion clause, and — since E-079 — silent for the arm
    only when the ARM comes through the adapter too. Both halves are asserted
    here rather than in two tests, because the variable between them is one
    expression in one file and separating them would hide that.
    """
    adapter = """
        from resilient_mlkit.core.served import (
            ServeArms,
            ServedModel,
            challenger_decision,
        )

        __all__ = ["ServeArms", "ServedModel", "challenger_decision"]
    """
    root = write_repo(
        tmp_path,
        {
            "src/serve/contract.py": adapter,
            "src/serve/county_yield.py": """
                from serve.contract import ServeArms, ServedModel, challenger_decision

                SERVEABLE_ARMS = ServeArms(open={"val", "train"})

                def challenger_gate(block):
                    return challenger_decision(block, recorded_bar="p", metrics=("mae",))
            """,
        },
    )
    findings, _ = sr.scan_repo(root)
    assert findings == []

    # FIRES. The same adapter, the same use of it, and a LOCAL arm tuple: the
    # promotion clause stays exempt and the arm is reported. This is E-079's
    # third row, one level of indirection out.
    root = write_repo(
        tmp_path / "local_arm",
        {
            "src/serve/contract.py": adapter,
            "src/serve/county_yield.py": """
                from serve.contract import ServeArms, ServedModel, challenger_decision

                SERVEABLE_ARMS = ("val", "train")

                def challenger_gate(block):
                    return challenger_decision(block, recorded_bar="p", metrics=("mae",))
            """,
        },
    )
    findings, _ = sr.scan_repo(root)
    assert [(f.path, f.clause, f.symbol) for f in findings] == [
        ("src/serve/county_yield.py", "SERVE_ARM", "SERVEABLE_ARMS")
    ]


def test_two_levels_of_indirection_are_not_exempt(tmp_path):
    """Stated, not hidden: the exemption is one level, matching R11's precedent."""
    root = write_repo(
        tmp_path,
        {
            "src/a.py": "from resilient_mlkit.core.served import ServedModel\n",
            "src/b.py": "from a import ServedModel\n",
            "src/c.py": """
                from b import ServedModel

                SERVEABLE_ARMS = ("val", "train")
            """,
        },
    )
    findings, _ = sr.scan_repo(root)
    assert {f.path for f in findings} == {"src/c.py"}


def test_importing_the_package_but_not_the_contract_does_not_exempt():
    """One unrelated import must not be able to silence the check."""
    findings = scan("""
        import resilient_mlkit

        SERVEABLE_ARMS = ("val", "train")
    """)
    assert "SERVE_ARM" in clauses(findings)


def test_from_package_import_module_spelling_is_recognised():
    assert scan("""
        from resilient_mlkit.core import served

        SERVEABLE_ARMS = served.ServeArms(open={"val"})
    """) == []


def test_aliased_import_spelling_is_recognised():
    assert scan("""
        import resilient_mlkit.core.served as contract

        SERVEABLE_ARMS = contract.ServeArms(open={"val"})
    """) == []


def test_the_contract_itself_is_never_reported(tmp_path):
    """mlkit's own module implements the contract; that is not re-implementing it."""
    root = write_repo(
        tmp_path,
        {
            "src/resilient_mlkit/core/served.py": SERVING,
            "src/serve/county_yield.py": SERVING,
        },
    )
    findings, walked = sr.scan_repo(root)
    assert walked == 1
    assert {f.path for f in findings} == {"src/serve/county_yield.py"}


def test_tests_and_vendored_directories_are_not_walked(tmp_path):
    root = write_repo(
        tmp_path,
        {
            "tests/test_serving.py": SERVING,
            ".venv/lib/site-packages/vendored.py": SERVING,
            "src/ok.py": "def f():\n    return 1\n",
        },
    )
    findings, walked = sr.scan_repo(root)
    assert walked == 1
    assert findings == []


def test_an_unparseable_file_is_skipped_rather_than_crashing(tmp_path):
    root = write_repo(
        tmp_path,
        {
            "src/broken.py": "def f(:\n",
            "src/serve.py": SERVING,
        },
    )
    findings, _ = sr.scan_repo(root)
    assert {f.path for f in findings} == {"src/serve.py"}


# ---------------------------------------------------------------------------
# The check itself
# ---------------------------------------------------------------------------
def test_the_check_fails_and_names_the_file(tmp_path):
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(tmp_path, {"src/serve/county_yield.py": SERVING})
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.FAIL
    assert "src/serve/county_yield.py" in result.reason
    assert result.evidence["contract_reimplemented"] > 0
    assert (tmp_path / "reports" / "served_contract.md").is_file()


def test_the_check_passes_on_a_repo_that_imports(tmp_path):
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(tmp_path, {"src/serve/county_yield.py": SERVING_ADOPTED})
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.PASS
    assert result.evidence["findings"] == 0
    assert result.evidence["files_walked"] == 1


def test_a_repo_with_no_python_is_na_not_a_pass(tmp_path):
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    (tmp_path / "README.md").write_text("nothing here")
    result = r12_served_contract(
        Repo(name="empty", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.NA
    assert "unmeasured, not established" in result.reason


def test_r12_is_registered_in_the_readiness_phase_and_before_r8():
    from resilient_mlkit.checks import PHASE_ORDER, get, load_all

    load_all()
    spec = get("R12")
    assert spec.phase == "readiness"
    order = PHASE_ORDER["readiness"]
    assert order.index("R12") < order.index("R8")
    assert order[-1] == "R8"


def test_r12_did_not_disturb_the_existing_readiness_order():
    """Additive, asserted rather than promised.

    R13 (M-2, 2026-09-04) joined the same way, directly after R12; with both
    additive ids removed the original order stands, and with only R13 removed
    R12's own placement (after R11, before R1) stands too.
    """
    from resilient_mlkit.checks import PHASE_ORDER

    without = [c for c in PHASE_ORDER["readiness"] if c not in ("R12", "R13")]
    assert without == [
        "R9", "R10", "R11", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    ]
    without_r13 = [c for c in PHASE_ORDER["readiness"] if c != "R13"]
    assert without_r13 == [
        "R9", "R10", "R11", "R12", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    ]
    order = PHASE_ORDER["readiness"]
    assert order.index("R13") == order.index("R12") + 1


# ---------------------------------------------------------------------------
# E-035: an import is not a use
# ---------------------------------------------------------------------------
# The exemption used to be satisfied by the import statement alone, and
# resilient-fray proved by measurement what that bought: ONE unused line added
# to src/registry/promotion_gate.py took its findings from 4 to 0. fray refused
# to take R12 green that way and recorded it as E-035. These are that mutation,
# reduced to the two module fixtures above so they run without fray present.
#
# Both halves are required. The FIRES half alone would pass a check that fired
# on everything; the SILENT half alone would pass the check that shipped.

EVASION = "from resilient_mlkit.core.served import challenger_decision  # noqa: F401\n"


def test_an_unused_import_does_not_exempt_a_reimplementation():
    """FIRES. The E-035 mutation, on both fixtures.

    The assertion is equality with the un-evaded count, not merely "non-empty":
    a repair that silenced SOME findings would still be a repair a dead import
    can pay for, and this is the property that says it pays for nothing.
    """
    for name, source in (("SERVING", SERVING), ("TORRENT", TORRENT)):
        bare = textwrap.dedent(source)
        before = sr.scan_source(bare, "src/serve/thing.py")
        after = sr.scan_source(EVASION + bare, "src/serve/thing.py")
        assert before, f"{name} must carry a clause for this control to mean anything"
        assert len(after) == len(before), (
            f"{name}: one unused contract import took findings "
            f"{len(before)} -> {len(after)}; an import is not a use (E-035)"
        )


def test_an_unused_import_does_not_exempt_at_repo_scope(tmp_path):
    """FIRES, through scan_repo rather than scan_source.

    scan_tree applies the exemption on its own path (the two-pass walk), so the
    single-module entry point passing is not evidence that the repo scan does.
    """
    root = write_repo(
        tmp_path,
        {"src/serve/county_yield.py": EVASION + textwrap.dedent(SERVING)},
    )
    findings, walked = sr.scan_repo(root)
    assert walked == 1
    assert {f.path for f in findings} == {"src/serve/county_yield.py"}


def test_an_unused_import_does_not_exempt_through_the_check(tmp_path):
    """FIRES, at the check the portfolio actually runs."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(
        tmp_path,
        {"src/serve/county_yield.py": EVASION + textwrap.dedent(SERVING)},
    )
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.FAIL
    assert result.evidence["contract_reimplemented"] > 0


#: The contract import both halves below share, plus the call that uses it.
CONTRACT_IMPORT = (
    "from resilient_mlkit.core.served import ServeArms, challenger_decision\n"
)
DECIDE = (
    "\n\ndef decide(comparisons):\n"
    "    return challenger_decision(\n"
    '        comparisons, recorded_bar=RECORDED_BAR, metrics=("mae",)\n'
    "    )\n"
)


def test_a_used_import_still_exempts():
    """SILENT. Add the SAME import to the SAME fixture and then CALL it.

    The variable between this and the FIRES half is one call expression. If
    this went red the repair would have bought its firing by breaking adoption,
    which is the trade the module docstring says must not be made.

    Since E-079 "the same fixture" has to include the ARM: a file whose
    promotion logic is the contract's and whose arm policy is a local tuple is
    exempt for the first and reported for the second, and the second half of
    this test is that row.
    """
    used = CONTRACT_IMPORT + serving(ARMS_FROM_NAME) + DECIDE
    assert sr.scan_source(used, "src/serve/thing.py") == []

    # FIRES. The identical file with the arm policy left local.
    local_arm = CONTRACT_IMPORT + serving() + DECIDE
    findings = sr.scan_source(local_arm, "src/serve/thing.py")
    assert non_serve_arm_rows(findings) == [], (
        "the used import must still exempt the promotion and self-hash clauses; "
        "E-079 scoped the SERVE_ARM clause and nothing else"
    )
    assert {f.symbol for f in serve_arm_rows(findings)} == {
        "SERVEABLE_ARMS",
        "if <arm> ... raise",
    }


def test_an_unused_repo_local_route_does_not_exempt_either(tmp_path):
    """FIRES. The evasion one level of indirection out.

    The adapter is real and the import of it is real; what is missing is any
    reference to what was taken from it. Held separately from the direct case
    because the two go through different predicates.
    """
    root = write_repo(
        tmp_path,
        {
            "src/serve/contract.py": """
                from resilient_mlkit.core.served import ServedModel, challenger_decision

                __all__ = ["ServedModel", "challenger_decision"]
            """,
            "src/serve/county_yield.py": (
                "from serve.contract import challenger_decision  # noqa: F401\n"
                + textwrap.dedent(SERVING)
            ),
        },
    )
    findings, _ = sr.scan_repo(root)
    assert {f.path for f in findings} == {"src/serve/county_yield.py"}


def test_a_rebind_of_the_imported_name_is_not_a_use():
    """FIRES. Shadowing the contract's name is the opposite of using it.

    ``challenger_decision = _my_gate`` reads as a reference to a name-matching
    scanner and is a local definition wearing the contract's name.
    """
    source = (
        EVASION
        + "\n\ndef _my_gate(block):\n"
        '    return {"status": "PASS", "promotable": True, "reason": "local"}\n'
        "\n\nchallenger_decision = _my_gate\n"
    )
    findings = sr.scan_source(source, "src/serve/thing.py")
    assert "PROMOTION_VERDICT" in {f.clause for f in findings}


# ---------------------------------------------------------------------------
# E-035-VERIFY. The repair above closed the exemption for the
# ``from X import f`` spelling and left it open for two others, both of which
# were forced against the REAL resilient-fray file before these were written:
#
#   * ``import X.Y.Z`` binds the ROOT name, so any unrelated read of that root
#     paid for the import. fray's promotion gate, given a benign
#     ``import resilient_mlkit.core.result`` and a use of it, went 4 findings
#     -> 0 on ONE added ``import resilient_mlkit.core.served`` line. That is
#     E-035's own mutation, unrepaired, at check level (R12 FAIL -> PASS).
#   * SHADOW-AND-CALL. ``_referenced_names`` skips ``Store`` nodes, but a file
#     that rebinds the contract's name AND THEN CALLS the rebinding still has a
#     ``Load`` of it, so it earned the exemption. The control above
#     (``test_a_rebind_of_the_imported_name_is_not_a_use``) never called the
#     rebinding, so it did not see this.
#
# Each is a FIRES/SILENT pair: the SILENT half is the same import spelling with
# a real use, because a repair that fired on those would break adoption.

DOTTED_EVASION = "import resilient_mlkit.core.served\n"

#: A file that already touches ``resilient_mlkit`` for an unrelated reason,
#: which is what made the dotted evasion cost one line rather than two.
UNRELATED_USE = (
    "import resilient_mlkit.core.result\n"
    "\n"
    "def _ok(cid):\n"
    "    return resilient_mlkit.core.result.CheckResult.passed(cid, 'x', {})\n"
    "\n"
)


def test_a_dotted_import_is_not_paid_for_by_an_unrelated_use_of_its_root():
    """FIRES. ``import pkg.a.b`` must be used as ``pkg.a.b.…``, not as ``pkg``."""
    for name, source in (("SERVING", SERVING), ("TORRENT", TORRENT)):
        bare = UNRELATED_USE + textwrap.dedent(source)
        before = sr.scan_source(bare, "src/serve/thing.py")
        after = sr.scan_source(DOTTED_EVASION + bare, "src/serve/thing.py")
        assert before, f"{name} must carry a clause for this control to mean anything"
        assert len(after) == len(before), (
            f"{name}: one unused `import {sr.CONTRACT_MODULE}` took findings "
            f"{len(before)} -> {len(after)} because an unrelated read of the "
            "root package paid for it (E-035, dotted spelling)"
        )


def test_a_dotted_import_used_as_a_full_chain_still_exempts():
    """SILENT. The same import line; the variable is the chain that reads it."""
    used = (
        DOTTED_EVASION
        + serving(ARMS_FROM_CHAIN)
        + "\n\ndef decide(comparisons):\n"
        "    return resilient_mlkit.core.served.challenger_decision(\n"
        '        comparisons, recorded_bar=RECORDED_BAR, metrics=("mae",)\n'
        "    )\n"
    )
    assert sr.scan_source(used, "src/serve/thing.py") == []

    # FIRES. The same dotted chain, the same use, a local arm tuple (E-079).
    local_arm = (
        DOTTED_EVASION
        + serving()
        + "\n\ndef decide(comparisons):\n"
        "    return resilient_mlkit.core.served.challenger_decision(\n"
        '        comparisons, recorded_bar=RECORDED_BAR, metrics=("mae",)\n'
        "    )\n"
    )
    findings = sr.scan_source(local_arm, "src/serve/thing.py")
    assert non_serve_arm_rows(findings) == []
    assert serve_arm_rows(findings)


def test_a_dotted_import_bound_with_as_still_exempts():
    """SILENT. ``import X.Y.Z as s`` binds a bare name, and ``s.f(...)`` uses it."""
    used = (
        "import resilient_mlkit.core.served as served\n"
        + serving(ARMS_FROM_ALIAS)
        + "\n\ndef decide(comparisons):\n"
        "    return served.challenger_decision(\n"
        '        comparisons, recorded_bar=RECORDED_BAR, metrics=("mae",)\n'
        "    )\n"
    )
    assert sr.scan_source(used, "src/serve/thing.py") == []

    # FIRES. The same alias, the same use, a local arm tuple (E-079).
    local_arm = (
        "import resilient_mlkit.core.served as served\n"
        + serving()
        + "\n\ndef decide(comparisons):\n"
        "    return served.challenger_decision(\n"
        '        comparisons, recorded_bar=RECORDED_BAR, metrics=("mae",)\n'
        "    )\n"
    )
    findings = sr.scan_source(local_arm, "src/serve/thing.py")
    assert non_serve_arm_rows(findings) == []
    assert serve_arm_rows(findings)


def test_shadowing_the_contract_name_and_then_calling_it_is_not_a_use():
    """FIRES. The rebind control above, plus the one line that defeated it.

    ``challenger_decision = _my_gate`` followed by ``challenger_decision(b)``
    is a local implementation wearing the contract's name and being called;
    the ``Load`` it produces resolves to the local thing, not to the import.
    """
    source = (
        "from resilient_mlkit.core.served import challenger_decision\n"
        "\n\ndef _my_gate(block):\n"
        '    return {"status": "PASS", "promotable": True, "reason": "local"}\n'
        "\n\nchallenger_decision = _my_gate\n"
        "\n\ndef go(block):\n    return challenger_decision(block)\n"
    )
    findings = sr.scan_source(source, "src/serve/thing.py")
    assert "PROMOTION_VERDICT" in {f.clause for f in findings}


def test_shadowing_control_fires_at_repo_scope_and_through_the_check(tmp_path):
    """FIRES, at the check the portfolio runs, for both evasions at once."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(
        tmp_path,
        {
            "src/serve/dotted.py": (
                DOTTED_EVASION + UNRELATED_USE + textwrap.dedent(SERVING)
            ),
            "src/serve/shadow.py": (
                "from resilient_mlkit.core.served import challenger_decision\n"
                "\n\ndef _my_gate(block):\n"
                '    return {"status": "PASS", "promotable": True}\n'
                "\n\nchallenger_decision = _my_gate\n"
                "\n\ndef go(block):\n    return challenger_decision(block)\n"
                + textwrap.dedent(TORRENT)
            ),
        },
    )
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.FAIL
    findings, _ = sr.scan_repo(tmp_path)
    assert {f.path for f in findings} == {"src/serve/dotted.py", "src/serve/shadow.py"}


def test_a_repo_local_route_taken_by_the_dotted_spelling_still_exempts(tmp_path):
    """SILENT, one level of indirection out, via ``import serve.contract``.

    The indirection exemption has to survive the dotted-prefix rule too, or the
    repair would have closed the evasion by breaking the adoption path.
    """
    root = write_repo(
        tmp_path,
        {
            "src/serve/contract.py": """
                from resilient_mlkit.core.served import ServedModel, challenger_decision

                __all__ = ["ServedModel", "challenger_decision"]
            """,
            "src/serve/county_yield.py": (
                "import serve.contract\n"
                + serving("serve.contract.ServeArms(open={\"val\"})")
                + "\n\ndef decide(c):\n"
                "    return serve.contract.challenger_decision(c)\n"
            ),
        },
    )
    findings, _ = sr.scan_repo(root)
    assert findings == []

    # FIRES. The same dotted route, used, with the arm policy left local.
    root = write_repo(
        tmp_path / "local_arm",
        {
            "src/serve/contract.py": """
                from resilient_mlkit.core.served import ServedModel, challenger_decision

                __all__ = ["ServedModel", "challenger_decision"]
            """,
            "src/serve/county_yield.py": (
                "import serve.contract\n"
                + serving()
                + "\n\ndef decide(c):\n"
                "    return serve.contract.challenger_decision(c)\n"
            ),
        },
    )
    findings, _ = sr.scan_repo(root)
    assert non_serve_arm_rows(findings) == []
    assert {f.path for f in serve_arm_rows(findings)} == {"src/serve/county_yield.py"}


# ---------------------------------------------------------------------------
# E-079: the serve-arm exemption is the DECISION's, not the file's
# ---------------------------------------------------------------------------
# resilient-torrent drove its own `mlkit_bindings.py` three ways and the third
# result is why these exist (E-079, 2026-09-05):
#
#     PR #190 as authored (local constant, no ServeArms)      1 finding
#     the repair (arm obtained via ServeArms.require)         0
#     the repair PLUS the constant restored and USED,
#         with the helper left dead                           0   <-- the defect
#
# The fixtures below are that file reduced to its serve-arm decision. Every
# pair holds ONE variable: where the value `d6_deciding_arm()` returns comes
# from. Nothing else in the file moves between the halves.

TORRENT_D6_HELPER = '''
    from resilient_mlkit.core.served import ServeArms


    def _d6_serve_arms():
        return ServeArms(
            open={"val"},
            closed={"test": "a ledgered holdout", "train": "the fitted arm"},
        )
'''

TORRENT_D6_REPAIR = TORRENT_D6_HELPER + '''

    def d6_deciding_arm():
        return _d6_serve_arms().require("val")
'''

TORRENT_D6_CONSTANT_USED_HELPER_DEAD = TORRENT_D6_HELPER + '''

    D6_DECIDING_ARM = "val"


    def d6_deciding_arm():
        return D6_DECIDING_ARM
'''

TORRENT_D6_AS_AUTHORED = '''
    D6_DECIDING_ARM = "val"


    def d6_deciding_arm():
        return D6_DECIDING_ARM
'''


def test_e079_a_conforming_helper_does_not_exempt_the_arm_the_file_actually_uses():
    """FIRES. E-079's third row, which the file-scoped exemption read as clean.

    `ServeArms` is imported and referenced, so the FILE routes through the
    contract; the value served is a module-level constant that never consults
    it. The exemption belongs to the decision, and this decision did not earn
    it.
    """
    findings = scan(TORRENT_D6_CONSTANT_USED_HELPER_DEAD, "mlkit_bindings.py")
    assert [(f.clause, f.symbol) for f in findings] == [
        ("SERVE_ARM", "D6_DECIDING_ARM")
    ]


def test_e079_the_repair_that_takes_the_arm_from_the_contract_is_silent():
    """SILENT. The same file; the variable is what `d6_deciding_arm` returns.

    Two statements, not one: the value comes from a module-local helper whose
    own value comes from the contract. A rule that demanded the contract's name
    appear IN the returned expression would report torrent's real repair, which
    is the trade the module docstring forbids.
    """
    assert scan(TORRENT_D6_REPAIR, "mlkit_bindings.py") == []


def test_e079_the_defect_as_authored_is_still_reported():
    """FIRES. E-079's first row, unmoved: no contract name in the file at all."""
    findings = scan(TORRENT_D6_AS_AUTHORED, "mlkit_bindings.py")
    assert [(f.clause, f.symbol) for f in findings] == [
        ("SERVE_ARM", "D6_DECIDING_ARM")
    ]


def test_e079_the_three_shapes_are_the_control_pair_they_claim_to_be():
    """A control on the controls: the three fixtures differ only where they say.

    If the SILENT fixture had also dropped the constant's NAME, its silence
    would be attributable to the missing shape rather than to the derivation,
    and the pair would prove nothing. So the helper block is asserted
    byte-identical across the two shapes that carry it.
    """
    assert TORRENT_D6_HELPER in TORRENT_D6_REPAIR
    assert TORRENT_D6_HELPER in TORRENT_D6_CONSTANT_USED_HELPER_DEAD
    assert "ServeArms" not in TORRENT_D6_AS_AUTHORED
    assert 'D6_DECIDING_ARM = "val"' in TORRENT_D6_CONSTANT_USED_HELPER_DEAD
    assert 'D6_DECIDING_ARM = "val"' in TORRENT_D6_AS_AUTHORED
    assert 'D6_DECIDING_ARM = "val"' not in TORRENT_D6_REPAIR


def test_e079_one_level_of_local_indirection_is_honoured_but_is_not_free():
    """SILENT / FIRES on the same shape: `ARMS = _arms()`.

    The fixpoint in `_serve_arm_derivation` is what makes the first half
    silent. The second half is the same two statements with the helper
    returning a tuple of its own, and it must fire — otherwise the fixpoint
    would exempt any value reachable through any helper, which is the
    file-scoped rule wearing a longer name.
    """
    silent = """
        from resilient_mlkit.core.served import ServeArms

        def _arms():
            return ServeArms(open={"val"}, closed={"test": "held"})

        SERVE_ARMS = _arms()
    """
    assert scan(silent) == []

    fires = """
        from resilient_mlkit.core.served import ServeArms

        def _arms():
            return ("val", "train")

        def unrelated():
            return ServeArms(open={"val"})

        SERVE_ARMS = _arms()
    """
    findings = scan(fires)
    assert [(f.clause, f.symbol) for f in findings] == [("SERVE_ARM", "SERVE_ARMS")]


def test_e079_only_the_serve_arm_clause_is_decision_scoped():
    """The five other clauses keep the FILE-scoped exemption, unchanged.

    Stated as a test because "we changed one clause" is exactly the kind of
    claim that goes stale. The fixture carries a promotion verdict AND a local
    arm constant and uses the contract; only the arm is reported.
    """
    source = (
        "from resilient_mlkit.core.served import challenger_decision\n"
        + serving()
        + DECIDE
    )
    findings = sr.scan_source(source, "src/serve/thing.py")
    assert {f.clause for f in findings} == {"SERVE_ARM"}
    bare = serving()
    assert {f.clause for f in sr.scan_source(bare, "src/serve/thing.py")} > {
        "SERVE_ARM"
    }, "the fixture must carry other clauses or this control proves nothing"


def test_e079_fires_at_repo_scope_and_through_the_check(tmp_path):
    """FIRES at the check the portfolio actually runs, not only in the scanner."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(
        tmp_path,
        {"mlkit_bindings.py": TORRENT_D6_CONSTANT_USED_HELPER_DEAD},
    )
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.FAIL
    assert result.evidence["contract_reimplemented"] == 1
    findings, _ = sr.scan_repo(tmp_path)
    assert [(f.path, f.clause, f.symbol) for f in findings] == [
        ("mlkit_bindings.py", "SERVE_ARM", "D6_DECIDING_ARM")
    ]


def test_e079_is_silent_at_repo_scope_on_the_repair(tmp_path):
    """SILENT at the same scope, through the same check."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import r12_served_contract
    from resilient_mlkit.core.repo import Repo
    from resilient_mlkit.core.result import Status

    write_repo(tmp_path, {"mlkit_bindings.py": TORRENT_D6_REPAIR})
    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path),
        RunContext(nonce="test-nonce", root=tmp_path),
    )
    assert result.status is Status.PASS
    assert sr.scan_repo(tmp_path)[0] == []


def test_e079_a_dead_route_does_not_derive_an_arm(tmp_path):
    """FIRES. The E-035 evasion, aimed at the arm instead of at the gate.

    A repo-local adapter that imports the contract makes the route real, and a
    file that takes a name from that adapter and USES it is exempt for the five
    shape clauses. It is not exempt for an arm the adapter never touched.
    """
    root = write_repo(
        tmp_path,
        {
            "src/serve/contract.py": """
                from resilient_mlkit.core.served import ServeArms, challenger_decision

                __all__ = ["ServeArms", "challenger_decision"]
            """,
            "src/serve/arms.py": """
                from serve.contract import ServeArms, challenger_decision

                DECIDING_ARM = "val"

                def gate(block):
                    return challenger_decision(block, recorded_bar="p", metrics=("mae",))

                def declared():
                    return ServeArms(open={"val"})
            """,
        },
    )
    findings, _ = sr.scan_repo(root)
    assert [(f.path, f.clause, f.symbol) for f in findings] == [
        ("src/serve/arms.py", "SERVE_ARM", "DECIDING_ARM")
    ]


def test_e079_derivation_does_not_change_a_file_that_never_binds_the_contract():
    """The narrowing is one-directional: it can only ADD findings.

    Every fixture in this module that carries a serve-arm shape and no contract
    binding must report exactly what it reported before, because there is
    nothing for a derivation to exempt.
    """
    findings = scan(serving())
    assert {f.symbol for f in serve_arm_rows(findings)} == {
        "SERVEABLE_ARMS",
        "if <arm> ... raise",
    }


# ---------------------------------------------------------------------------
# E-M38: a SERVE_ARM row names its own repair
# ---------------------------------------------------------------------------
# The nine rows E-M38 enumerates each told the owning repo WHY the site was a
# finding and nothing about WHAT to write. A consumer fixing one had to read
# this module to learn what "derived from a bound core.served name" means.
# Every SERVE_ARM finding now carries `repair`, and the control that matters is
# executable: the line the message names, written into the fixture, is the
# line that clears the row.

TORRENT_CANDIDATE_PROMOTION_SHAPE = '''
    from resilient_mlkit.core.served import ServeArms

    SERVE_ARMS = ServeArms(
        open=frozenset({"val"}),
        closed={"test": "the holdout ledger is held"},
    )
    DECIDING_ARM = "val"


    def decide():
        return DECIDING_ARM
'''

FRAY_BINDINGS_SHAPE = '''
    from resilient_mlkit.core.served import row_set_digest

    D6_DECIDING_ARM = "val"


    def digest(rows):
        return row_set_digest(rows)


    def decide():
        return D6_DECIDING_ARM
'''

INLINE_REFUSAL_SHAPE = '''
    from resilient_mlkit.core.served import ServeArms


    def serve(arm):
        if arm == "test":
            raise RuntimeError("closed")
        return arm
'''


def _only_serve_arm(source, display="mlkit_bindings.py"):
    findings = scan(source, display)
    assert [f.clause for f in findings] == ["SERVE_ARM"], findings
    return findings[0]


def test_em38_the_repair_names_the_policy_the_file_already_takes_from_the_contract():
    """torrent candidate_promotion.py:124, reduced: a live SERVE_ARMS eleven
    lines above a bare literal. The repair names THAT binding, not a generic
    ServeArms, and spells the arm the file actually serves."""
    f = _only_serve_arm(TORRENT_CANDIDATE_PROMOTION_SHAPE)
    assert f.symbol == "DECIDING_ARM"
    assert f.repair.startswith("REPAIR: derive DECIDING_ARM from SERVE_ARMS")
    assert 'DECIDING_ARM = SERVE_ARMS.require("val")' in f.repair
    assert "E-079" in f.repair


def test_em38_the_repair_the_message_names_is_the_repair_that_clears_the_row():
    """The executable control. Take the message's own line, write it into the
    fixture in place of the literal, rescan: silence. If the message ever
    names a line the scanner would still report, this fails."""
    f = _only_serve_arm(TORRENT_CANDIDATE_PROMOTION_SHAPE)
    named = 'DECIDING_ARM = SERVE_ARMS.require("val")'
    assert named in f.repair
    repaired = TORRENT_CANDIDATE_PROMOTION_SHAPE.replace('DECIDING_ARM = "val"', named)
    assert repaired != TORRENT_CANDIDATE_PROMOTION_SHAPE
    assert scan(repaired, "mlkit_bindings.py") == []


def test_em38_a_helper_returning_the_policy_is_named_as_a_call():
    """E-079's third row: the policy lives behind a dead helper. The repair
    names the helper, spelled as the call it is, and that line clears the row."""
    f = _only_serve_arm(TORRENT_D6_CONSTANT_USED_HELPER_DEAD)
    named = 'D6_DECIDING_ARM = _d6_serve_arms().require("val")'
    assert named in f.repair, f.repair
    repaired = TORRENT_D6_CONSTANT_USED_HELPER_DEAD.replace('D6_DECIDING_ARM = "val"', named)
    assert scan(repaired, "mlkit_bindings.py") == []


def test_em38_a_file_that_binds_the_contract_but_no_policy_is_told_to_declare_one():
    """fray mlkit_bindings.py:848, reduced: row_set_digest is bound and used,
    no ServeArms anywhere. The repair names what IS bound, the import that is
    missing, the declaration, and the derivation -- in that order."""
    f = _only_serve_arm(FRAY_BINDINGS_SHAPE)
    r = f.repair
    assert "this file binds row_set_digest from core.served" in r
    assert "from resilient_mlkit.core.served import ServeArms" in r
    assert 'SERVE_ARMS = ServeArms(open=frozenset({"val"})' in r
    assert 'D6_DECIDING_ARM = SERVE_ARMS.require("val")' in r
    assert r.index("import ServeArms") < r.index("SERVE_ARMS = ServeArms(") < r.index(
        "D6_DECIDING_ARM = SERVE_ARMS.require"
    )


def test_em38_a_file_that_binds_nothing_is_told_the_import_first():
    f = _only_serve_arm(TORRENT_D6_AS_AUTHORED)
    assert "this file binds no core.served name" in f.repair
    assert "from resilient_mlkit.core.served import ServeArms" in f.repair
    assert 'D6_DECIDING_ARM = SERVE_ARMS.require("val")' in f.repair


def test_em38_an_inline_refusal_is_told_to_use_the_contracts_guard():
    f = _only_serve_arm(INLINE_REFUSAL_SHAPE, "src/serve/thing.py")
    assert f.symbol == "if <arm> ... raise"
    assert "SERVE_ARMS.require(<the arm being tested>)" in f.repair
    assert "UNDECLARED" in f.repair
    assert "declare the policy with the ServeArms this file already binds" in f.repair


def test_em38_the_other_honest_exit_is_named_with_the_pattern_to_leave():
    """E-M38 leaves two exits: adopt, or say the word is another sense. The
    second is only usable if the message says which names the pattern owns."""
    f = _only_serve_arm(TORRENT_D6_AS_AUTHORED)
    assert "rename it out of R12's arm-constant pattern" in f.repair
    assert "DECIDING" in f.repair and "SERVE_ARMS" in f.repair
    assert "mlkit keeps no exemption list" in f.repair


def test_em38_only_serve_arm_rows_carry_a_repair_and_to_dict_carries_it():
    """The other five clauses are repaired by the file-level adoption the
    module docstring describes; their rows say so by carrying no repair."""
    hashing = scan(
        textwrap.dedent(
            '''
            import hashlib, json

            def artifact_hash(payload):
                body = {k: v for k, v in payload.items() if k != "artifact_hash"}
                return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            '''
        ),
        "src/serve/thing.py",
    )
    assert hashing, "the control needs a non-SERVE_ARM finding to look at"
    assert all(f.repair == "" for f in hashing)
    assert all("repair" in f.to_dict() for f in hashing)
    arm = _only_serve_arm(TORRENT_D6_AS_AUTHORED)
    assert arm.to_dict()["repair"] == arm.repair != ""


def test_em38_the_repair_survives_the_repo_scope_walk_and_reaches_the_report(tmp_path):
    """scan() rebuilds every finding to attach corroboration; the first cut of
    this field was dropped there and the nine real rows read `repair: ''`.
    Held at repo scope AND in the R12 report the consumer actually reads."""
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import R12_REPORT_RELPATH, r12_served_contract
    from resilient_mlkit.core.repo import Repo

    write_repo(tmp_path, {"mlkit_bindings.py": TORRENT_CANDIDATE_PROMOTION_SHAPE})
    findings, _ = sr.scan_repo(tmp_path)
    assert [f.symbol for f in findings] == ["DECIDING_ARM"]
    assert 'DECIDING_ARM = SERVE_ARMS.require("val")' in findings[0].repair

    result = r12_served_contract(
        Repo(name="fixture", path=tmp_path), RunContext(nonce="test-nonce", root=tmp_path)
    )
    assert result.evidence["top"][0]["repair"] == findings[0].repair
    report = (tmp_path / R12_REPORT_RELPATH).read_text(encoding="utf-8")
    assert "| repair |" in report
    assert 'DECIDING_ARM = SERVE_ARMS.require("val")' in report
