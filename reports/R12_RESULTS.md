# R12 results, against the pre-registration

Read `reports/R12_PREREGISTRATION.md` first; this file answers it hypothesis by
hypothesis. Every figure here was produced by running code in this branch and
is reproducible from the two committed artifacts named below.

- mlkit `0.5.0`, git `14b2e6c`, python `3.14.6`, measured 2026-08-29
- authorization: A-1 — local CPU, no cloud, no GPU, no spend. **Nothing was
  fitted.** The only executions were focused pytest files and two `ast` walks.
- artifacts: `reports/served_hash_parity.json`,
  `reports/served_contract_fleet.json`

## The reproduction that the prime directive demands

The refactor may not change any served number. For a served model the number
that must not change is its **identity**: every committed champion artifact
carries an `artifact_sha256` produced by its own repo's local function. If
mlkit's contract computed that digest differently, adopting it would make every
artifact fail its own load-time check, and the fix would look like *update the
recorded hash*.

`scripts/verify_served_hash_parity.py` recomputes each digest with
`resilient_mlkit.core.served.canonical_payload_sha256` and compares:

| repo | artifact | result |
|---|---|---|
| fray | `models/county_yield/champion_forecast_available.json` | MATCH |
| fray | `models/county_yield/champion_spatial_infill.json` | MATCH |
| chokepoint | `models/daily_flow/champion.json` | MATCH |
| chokepoint | `models/episode_response/champion.json` | MATCH |
| triage | `models/weekly_mortality/champion.json` | MATCH |

**5 compared, 5 matched, 0 differed.** choco, arabica, torrent, surge and
blackout pin no hashed artifact under `models/` and are reported `NA` with that
reason, not counted as passes.

## Hypotheses

**H1 — the contract fires. CONFIRMED.** A payload with one edited field fails
the self-hash; an unhashed payload is refused outright; a data file with one
changed byte, and an absent one, both fail provenance; an unmeasurable
comparison returns `NA`; a closed arm and an undeclared arm both raise.

**H2 — the contract stays silent. CONFIRMED.** The same sealed payload loads;
the same file verifies; measured positive skill returns `PASS` and measured
non-positive skill returns `FAIL`; open arms are returned. 41 assertions in
`tests/test_served_contract.py`, all matched pairs.

**H3 — R12 fires. CONFIRMED**, and on the right files. Both
`champion_challenger.py` files are named, as is every `promotion_gate.py` and
all three per-product serving modules.

**H4 — R12 stays silent on an importer. CONFIRMED**, and the silence is
attributable. `test_the_negative_controls_are_load_bearing` strips the import
line — and only the import line — from each adopted fixture and asserts both
then fire. Written because the first version of `TORRENT_ADOPTED` passed for
the wrong reason: it was silent with the import stripped, having dropped the
class names along with the local logic.

**H5 — the predicted fleet result. CONFIRMED for seven repos, one exception,
adjudicated.**

| repo | verdict | findings | files named | files walked |
|---|---|---|---|---|
| choco | FAIL | 2 | 1 | 398 |
| arabica | FAIL | 4 | 1 | 375 |
| fray | FAIL | 22 | 4 | 217 |
| torrent | FAIL | 7 | 2 | 533 |
| chokepoint | FAIL | 30 | 7 | 272 |
| **surge** | **PASS** | 0 | 0 | 328 |
| triage | FAIL | 14 | 7 | 416 |
| blackout | FAIL | 2 | 2 | 241 |

The pre-registration said a PASS would be evidence of a blind scanner rather
than of a clean repo, and would be reported as such. Two PASSes appeared in the
first run and both were investigated:

* **arabica was blindness, and it is fixed.** `src/registry/
  backbone_promotion.py:40` decides *"whether challenger backbone model
  qualifies for promotion over champion"*, and the function-name vocabulary was
  silent because nobody had listed `evaluate_backbone_gate`. Replaced with a
  structural rule; arabica now FAILs.
* **surge's PASS stands.** `grep -rl` for `champion|challenger|promotable` over
  its `src/` and `scripts/` returns nothing. `mlops/model_registry.py:109`
  `promote()` is a registry *stage transition* — it moves a version to
  production and decides nothing, with no bar, no comparison and no verdict.
  surge passes because it has no served-model contract to converge, which is a
  different fact from having adopted one. **Its first serving path will need to
  import the contract**, and R12 will say so then.

## What the falsification criteria caught

The pre-registration listed R12 firing on an adopted file as disqualifying. It
did not do that. But four *other* defects were found by running the scanner
across the fleet and reading what it named — none by reviewing it:

1. `SERVE_ARM` matched `arm` as a substring and reported four files on the words
   *farm* and *warming*.
2. `SELF_HASH` was defeated by moving `json.dumps` to its own statement.
3. `SELF_HASH` reported two honest run fingerprints in surge until it required
   the payload's own hash field to be excluded.
4. The `SELF_HASH` function-name list produced two false positives on names
   alone and found nothing the shape rule missed; it was deleted.

Each is recorded in the module, in `CHANGELOG.md`, and in a negative-control
test built from the real file that exposed it.

## Standing caveat

A green R12 does not claim a serving path is correct. It is an `ast` walk: it
sees that a file routes through the contract, never that it routes through it
correctly. A file that imports `core.served` and ignores the decision it
returns is silent here and is a defect. Closing that needs the adopter's own
served-report reproduction, which is the adopter's verifier and not this check.

## Not done here, on purpose

No adopter repo was edited. `resilient-triage` was read-only throughout —
`scripts/scan_served_contract.py` exists so the fleet can be measured without
the phase runner writing finding lists into the repos it measures. No tag was
cut. The adopters pin a tag after their own verifiers pass, and the session
lead cuts it.
