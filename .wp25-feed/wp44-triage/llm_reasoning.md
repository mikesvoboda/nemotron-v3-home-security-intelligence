# WP4.4 Triage Dossier — backend/api/routes/llm_reasoning.py

- **Run state at analysis time:** 420/420 keys checked, **210 survived** (0 untested). The meta grew during analysis (133 -> 143 -> 210); this dossier is against the FINAL snapshot. All diffs pulled via `uv run mutmut show <key>`; raw dumps at `/tmp/wp25/wp44-triage/diffs-llm_reasoning.txt` + `diffs-llm_reasoning-new.txt`; final key list `/tmp/wp25/surv-final-keys.txt`.
- **Covering tests for every survivor function:** `backend/tests/unit/api/routes/test_llm_reasoning.py` (confirmed via `mutants/mutmut-stats.json` -> `tests_by_mangled_function_name`; all five survivor parser functions + the four newly-arrived ones list ONLY tests in this one file). Anchors: TestExtractThinkBlock :55, TestParseReasoningSteps :97, TestExtractKeyFactors :139, TestExtractConfidence :166, TestExtractKeyObservations :194, TestExtractRiskFactors :211, TestParseEnrichmentSources :246, TestParseTruncationInfo :285, TestParseHouseholdMatches :315, endpoint tests :355/:535.
- **Why this file is a survivor mine:** pure data-mapping code (dict -> pydantic schema). Existing tests construct the minimal happy shape, then assert `len(...)` / `"substring" in name` / one field. Every fallback key, default value, slice cap and label string is unasserted. `_parse_json_response` has NO direct test — its 2 "covering" tests are endpoint tests whose mocked `raw_response` (`"<think>...</think>"`) is not JSON, so the mutant (loads arg/result -> None) is indistinguishable there. A second trap: `_extract_key_observations`'s existing tests use content with NO periods, so the greedy `[^.]+` capture swallows everything into ONE observation — the dedup/length/cap guards (and the `[:10]` cap) are never exercised (this is why `_18` [:10]->[:11] survived a `len <= 10` assertion).
- One EQUIVALENT mutant found (C8); everything else is real unasserted behavior -> TEST-GAP. LOW-VALUE not used: the "cosmetic" strings here (display labels, keyword lists) are API payload values the UI renders, already asserted by substring today — exact assertions are cheap (see note on C6/C11).

## Cluster table (counts sum to 210)

| ID  | Concern (function)                                     | Pattern                                                                                                                                                                                                                               |   n | Example keys          | Class      | Killed by       |
| --- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --: | --------------------- | ---------- | --------------- |
| C1  | `_parse_json_response`                                 | `json.loads(raw)` result/arg -> None => always returns None (JSON dict inputs)                                                                                                                                                        |   2 | **1, **2              | TEST-GAP   | Extra A (below) |
| C2  | `_extract_key_observations`                            | regex flags `IGNORECASE\|MULTILINE` removed / bit-ANDed (=0) => case + line-anchor lost                                                                                                                                               |   2 | **9, **10             | TEST-GAP   | Draft 6         |
| C3  | `_extract_key_observations`                            | append-guard `and`s flipped (`and`->`or`, `obs or`), `len>5` -> `>=5`/`>6` (dedup + length filter broken)                                                                                                                             |   4 | **12, **13, \_\_14    | TEST-GAP   | Draft 6         |
| C4  | `_extract_key_observations`                            | return cap `[:10]` -> `[:11]`                                                                                                                                                                                                         |   1 | \_\_18                | TEST-GAP   | Draft 6         |
| C5  | `_extract_key_factors`                                 | same guard family: flags removed (`__9`), `and`->`or`, `factor or`, `>3`->`>=3`/`>4`                                                                                                                                                  |   5 | **9, **11, \_\_12     | TEST-GAP   | Draft 6         |
| C6  | `_extract_confidence`                                  | indicator keyword strings swapped to XX-padded/UPPERCASE (never match `content.lower()`) — 22 of 30 keywords untested; surviving set = exactly the keywords no test cites ("unclear","possibly","certain","clearly","definitely",...) |  22 | **4, **15, \_\_26     | TEST-GAP   | Draft 5         |
| C7  | `_extract_risk_factors`                                | dedup guard `and`->`or` (dup + keyword-when-absent), `append(factor)`->`append(None)`, cap `[:10]`->`[:11]`                                                                                                                           |   4 | **11, **13, \_\_17    | TEST-GAP   | Extra B         |
| C8  | `_extract_think_block`                                 | pattern `r"<THINK>.*</THINK>"` — searched with `re.IGNORECASE` => identical match set                                                                                                                                                 |   1 | \_\_3                 | EQUIVALENT | n/a             |
| C9  | `_parse_reasoning_steps`                               | `key_factors=`/`confidence_indicator=` kwargs removed or -> None in BOTH step builders (numbered + paragraph branches)                                                                                                                |   6 | **18, **21, \_\_37    | TEST-GAP   | Extra C         |
| C10 | `_parse_enrichment_sources`                            | `known_sources` LOOKUP keys mutated ("XXflorenceXX","FLORENCE") => real data hits the unknown-source branch: name becomes title-cased key, list-data sample_fields lost                                                               |  28 | **3, **8, \_\_63      | TEST-GAP   | Draft 3         |
| C11 | `_parse_enrichment_sources`                            | `known_sources` display-NAME values mutated (XX-padded/lower/UPPER) — API-visible label rot, unasserted beyond substring for 12 of 14 labels                                                                                          |  38 | **5, **11, \_\_70     | TEST-GAP   | Draft 3         |
| C12 | `_parse_enrichment_sources`                            | `field_count = 0` init -> `1` (both loops): scalar (non-dict/list) payload reports field_count 1                                                                                                                                      |   2 | **78, **103           | TEST-GAP   | Draft 4         |
| C13 | `_parse_enrichment_sources`                            | sample_fields slice `[:5]`->`[:6]` (dict + list paths), `data[0]`->`data[1]` (wrong item, IndexError on 1-element list)                                                                                                               |   3 | **83, **88, \_\_89    | TEST-GAP   | Draft 4         |
| C14 | `_parse_enrichment_sources`                            | EnrichmentSource kwargs dropped: `sample_fields=` (known+unknown loops), `field_count=` (unknown loop) => default []/0                                                                                                                |   3 | **98, **112, \_\_113  | TEST-GAP   | Draft 4         |
| C15 | `_parse_enrichment_sources`                            | unknown-loop condition inverted `not in` -> `in`: known keys duplicated, unknown keys dropped                                                                                                                                         |   1 | \_\_99                | TEST-GAP   | Draft 4         |
| C16 | `_parse_enrichment_sources`                            | unknown loop `populated = bool(data)` -> `bool(None)`: unknown sources always unpopulated                                                                                                                                             |   1 | \_\_101               | TEST-GAP   | Draft 4         |
| C17 | `_parse_enrichment_sources`                            | unknown-source name `key.replace("_", " ")` args mutated => "Mystery_X" / "Mysteryxx Xx"                                                                                                                                              |   2 | **118, **119          | TEST-GAP   | Draft 4         |
| C18 | `_parse_truncation_info`                               | `truncation_log.get("reason")` -> None / kwarg removed / key mutated => truncation_reason never surfaces                                                                                                                              |   5 | **8, **13, \_\_34     | TEST-GAP   | Extra D         |
| C19 | `_parse_truncation_info`                               | `was_truncated` default `False` -> None (pydantic ValidationError) / removed / -> True                                                                                                                                                |   3 | **15, **17, \_\_20    | TEST-GAP   | Extra D         |
| C20 | `_parse_household_matches` (list branch)               | `match_method` extraction -> None / kwarg dropped / key mutated                                                                                                                                                                       |   5 | **7, **11, \_\_34     | TEST-GAP   | Draft 2         |
| C21 | `_parse_household_matches` (list branch)               | `entity_type` default "unknown" -> None (ValidationError) / removed / "XXunknownXX" / "UNKNOWN"                                                                                                                                       |   4 | **13, **18, \_\_19    | TEST-GAP   | Draft 2         |
| C22 | `_parse_household_matches` (list branch)               | `entity_name` fallback key `"name"` -> None/XX/NAME (fallback lost)                                                                                                                                                                   |   3 | **24, **25, \_\_26    | TEST-GAP   | Draft 2         |
| C23 | `_parse_household_matches` (list branch)               | `similarity_score` default 0.0 -> None (ValidationError) / removed / 1.0                                                                                                                                                              |   3 | **28, **30, \_\_33    | TEST-GAP   | Draft 2         |
| C24 | `_parse_household_matches` (dict-list + dict branches) | whole `HouseholdMatch(...)` call -> `None`: `matches.append(None)` — len() unchanged, so `len == 2` tests pass; every element silently loses ALL data (worst real bug here)                                                           |   2 | **37, **73            | TEST-GAP   | Draft 1         |
| C25 | `_parse_household_matches` (dict-list branch)          | field extractors -> None / kwargs dropped / `or`->`and` for name & method                                                                                                                                                             |   6 | **39, **41, \_\_46    | TEST-GAP   | Draft 1         |
| C26 | `_parse_household_matches` (dict-list branch)          | `entity_name` fallback-chain key mutations (`"name"`, `"entity_name"` operands)                                                                                                                                                       |   6 | **47, **48, \_\_52    | TEST-GAP   | Draft 1         |
| C27 | `_parse_household_matches` (dict-list branch)          | similarity key-chain: `"similarity"` key / inner `"similarity_score"` key / inner default 0.0 mutations (None => ValidationError, 1.0)                                                                                                |  12 | **53, **59, \_\_65    | TEST-GAP   | Draft 1         |
| C28 | `_parse_household_matches` (dict-list branch)          | `match_method` fallback chain `"method"`/`"match_method"` key mutations                                                                                                                                                               |   6 | **67, **68, \_\_71    | TEST-GAP   | Draft 1         |
| C29 | `_parse_household_matches` (dict branch)               | `entity_name`/`match_method` -> None / kwargs dropped / `or`->`and`                                                                                                                                                                   |   5 | **75, **77, \_\_82    | TEST-GAP   | Draft 1         |
| C30 | `_parse_household_matches` (dict branch)               | `entity_name` fallback-chain key mutations                                                                                                                                                                                            |   6 | **83, **85, \_\_88    | TEST-GAP   | Draft 1         |
| C31 | `_parse_household_matches` (dict branch)               | similarity key-chain mutations                                                                                                                                                                                                        |  12 | **89, **95, \_\_101   | TEST-GAP   | Draft 1         |
| C32 | `_parse_household_matches` (dict branch)               | `match_method` fallback-chain key mutations                                                                                                                                                                                           |   7 | **102, **104, \_\_108 | TEST-GAP   | Draft 1         |

Sum check: C1-9 = 2+2+4+1+5+22+4+1+6 = 47; C10-17 = 78; C18-19 = 8; C20-32 = 15+2+6+6+12+6+5+6+12+7 = 77. Total = 47+78+8+77 = **210**.

Drafts 1-6 kill 182/210 (87%); Extras A-D cover the remaining 21 non-equivalent survivors.

## Notes per interesting cluster

- **C1**: original returns the dict for valid JSON input; both mutants return None for ALL inputs (arg->None raises TypeError which the except swallows). Tests never pass JSON `raw_response`, so the `parsed_response` field and the route's `reasoning`-fallback path (`raw_response` with no think block) are entirely unexercised.
- **C6**: killing one mutant per level already works today (mutating the _tested_ indicator "confident"/"uncertain"/"likely" was killed) — surviving 22 are the keywords no test cites. `content.lower()` makes UPPERCASE list items dead.
- **C10 vs C11**: C10 is not cosmetic — data routed through the unknown branch loses list-derived `sample_fields`; C11 alone is label-only (closest to LOW-VALUE) but shares the same one-table kill, so keep it under the same draft.
- **C24**: `matches.append(None)` keeps `len(matches) == 2` true. Only an element-type/field assertion catches it.
- **C21/C23/C19 (None-default variants)**: strict pydantic rejects None for `entity_type: str`, `similarity_score: float`, `was_truncated: bool` — these survive only because no test omits the key on a _non-empty_ input.

## Drafted tests (UNVERIFIED - not yet run red/green)

TDD procedure (one line): add the test, run the module's pytest file — the new assertion must FAIL against each mutant's one-line diff (red), then PASS against unmutated `backend/api/routes/llm_reasoning.py` (green); re-run `mutmut run` for these keys to confirm kill.

Add to the import block at the top of `backend/tests/unit/api/routes/test_llm_reasoning.py`:

```python
from backend.api.routes.llm_reasoning import (
    ...  # existing imports
    _parse_json_response,  # new (Extra A)
)
from backend.api.schemas.llm_reasoning import HouseholdMatch  # new (Draft 1/2)
```

### Draft 1 — kills C24, C25, C26, C27, C28, C29, C30, C31, C32 (55) — add to TestParseHouseholdMatches (:315)

```python
    def test_dict_format_preserves_all_fields_and_fallbacks(self):
        """Dict-shaped matches must map both key spellings, defaults, and never append None."""
        matches_data = {
            "person": [
                {"name": "Jane Doe", "similarity": 0.88, "method": "face_recognition"},
                {"name": "Bot", "similarity_score": 0.3, "match_method": "gait"},
                {"name": "Ghost"},
                {"entity_name": "Legacy", "similarity": 0.5},
            ],
            "vehicle": {"name": "Truck", "similarity": 0.75, "match_method": "plate_scan"},
            "pet": {"entity_name": "Rex", "similarity_score": 0.4},
            "other": {"entity_name": "Ghost2", "match_method": "manual"},
        }
        matches = _parse_household_matches(matches_data)
        assert len(matches) == 7
        assert all(isinstance(m, HouseholdMatch) for m in matches)  # kills append(None) (C24)
        person = [m for m in matches if m.entity_type == "person"]
        assert person[0].entity_name == "Jane Doe"
        assert person[0].similarity_score == 0.88
        assert person[0].match_method == "face_recognition"
        assert person[1].entity_name == "Bot"
        assert person[1].similarity_score == 0.3  # falls back to "similarity_score"
        assert person[1].match_method == "gait"  # falls back to "match_method"
        assert person[2].entity_name == "Ghost"
        assert person[2].similarity_score == 0.0  # default when neither score key present
        assert person[2].match_method is None
        assert person[3].entity_name == "Legacy"  # "entity_name" when "name" absent
        assert person[3].similarity_score == 0.5
        vehicle = [m for m in matches if m.entity_type == "vehicle"][0]
        assert vehicle.entity_name == "Truck"
        assert vehicle.similarity_score == 0.75
        assert vehicle.match_method == "plate_scan"
        pet = [m for m in matches if m.entity_type == "pet"][0]
        assert pet.entity_name == "Rex"  # dict branch falls back to "entity_name"
        assert pet.similarity_score == 0.4  # dict branch inner "similarity_score" key
        other = [m for m in matches if m.entity_type == "other"][0]
        assert other.match_method == "manual"
        assert other.similarity_score == 0.0
```

// UNVERIFIED - not yet run red/green. Kill logic: every fallback key mutation turns one asserted value into None/0.0 (or raises ValidationError on a None-defaulted required field); append(None) fails the isinstance sweep.

### Draft 2 — kills C20, C21, C22, C23 (15) — add to TestParseHouseholdMatches (:315)

```python
    def test_list_format_preserves_all_fields_and_fallbacks(self):
        """List-shaped entries must keep method/score fields and documented defaults."""
        matches_data = [
            {
                "entity_type": "person",
                "entity_name": "John Doe",
                "similarity_score": 0.92,
                "match_method": "face_recognition",
            },
            {"entity_type": "vehicle", "name": "Family Car"},
            {"entity_name": "Legacy Car", "similarity_score": 0.4},
        ]
        matches = _parse_household_matches(matches_data)
        assert len(matches) == 3
        assert all(isinstance(m, HouseholdMatch) for m in matches)
        assert matches[0].entity_type == "person"
        assert matches[0].entity_name == "John Doe"
        assert matches[0].similarity_score == 0.92
        assert matches[0].match_method == "face_recognition"  # kills C20
        assert matches[1].entity_name == "Family Car"  # "name" fallback (kills C22)
        assert matches[1].similarity_score == 0.0  # default (kills C23)
        assert matches[1].match_method is None
        assert matches[2].entity_type == "unknown"  # default (kills C21)
        assert matches[2].entity_name == "Legacy Car"
        assert matches[2].similarity_score == 0.4
```

// UNVERIFIED - not yet run red/green.

### Draft 3 — kills C10 + C11 (66) — module level in test_llm_reasoning.py

```python
KNOWN_ENRICHMENT_LABELS = [
    ("florence", "Florence-2 Vision Analysis"),
    ("clip", "CLIP Embeddings"),
    ("weather", "Weather Analysis"),
    ("violence", "Violence Detection"),
    ("clothing", "Clothing Analysis"),
    ("vehicle", "Vehicle Classification"),
    ("pet", "Pet Detection"),
    ("pose", "Pose Estimation"),
    ("demographics", "Demographics Analysis"),
    ("image_quality", "Image Quality Assessment"),
    ("zones", "Zone Analysis"),
    ("baseline", "Baseline Comparison"),
    ("cross_camera", "Cross-Camera Correlation"),
    ("detections", "Object Detections"),
]


@pytest.mark.parametrize("key,display_name", KNOWN_ENRICHMENT_LABELS)
def test_known_enrichment_source_exact_display_name(key, display_name):
    """Each known snapshot key must surface exactly once under its exact display label."""
    sources = _parse_enrichment_sources({key: {"a": 1}})
    assert len(sources) == 1
    assert sources[0].name == display_name
```

// UNVERIFIED - not yet run red/green. Key mutation => title-cased unknown-branch name != label; value mutation => label string changed. One table kills all 66.

### Draft 4 — kills C12, C13, C14, C15, C16, C17 (12) — add to TestParseEnrichmentSources (:246)

```python
    def test_sample_fields_scalar_and_unknown_source_handling(self):
        """Sample-field caps read the first item; scalars report field_count 0; unknowns keep data."""
        snapshot = {
            "florence": {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6},
            "detections": [
                {"type": "person", "conf": 0.9, "x": 1, "y": 2, "z": 3, "w": 4},
                {"kind": "car", "speed": 2},
            ],
            "pose": [{"p": 1}],
            "baseline": "raw string",
            "mystery_x": {"alpha": 1, "beta": 2},
            "weird": 3,
        }
        sources = _parse_enrichment_sources(snapshot)
        assert len(sources) == 6  # no known-key duplicates, no dropped unknowns (kills C15)
        by_name = {s.name: s for s in sources}
        flo = by_name["Florence-2 Vision Analysis"]
        assert flo.field_count == 6
        assert flo.sample_fields == ["a", "b", "c", "d", "e"]  # cap 5, from kwargs (kills C13/C14)
        det = by_name["Object Detections"]
        assert det.field_count == 2
        assert det.sample_fields == ["type", "conf", "x", "y", "z"]  # FIRST item, cap 5 (kills C13)
        pose = by_name["Pose Estimation"]
        assert pose.populated is True
        assert pose.field_count == 1
        assert pose.sample_fields == ["p"]  # single-element list must not index [1] (kills C13)
        base = by_name["Baseline Comparison"]
        assert base.populated is True
        assert base.field_count == 0  # scalar payload (kills C12 known loop)
        mx = by_name["Mystery X"]  # exact underscore->space title (kills C17)
        assert mx.populated is True  # kills C16
        assert mx.field_count == 2
        assert mx.sample_fields == ["alpha", "beta"]  # kills C14 unknown loop
        weird = by_name["Weird"]
        assert weird.populated is True and weird.field_count == 0  # kills C12 unknown loop
```

// UNVERIFIED - not yet run red/green.

### Draft 5 — kills C6 (22) — module level in test_llm_reasoning.py

```python
CONFIDENCE_INDICATORS = [
    ("low", ["low confidence", "uncertain", "unclear", "possibly", "might be"]),
    ("high", ["high confidence", "confident", "certain", "clearly", "definitely"]),
    ("medium", ["moderate confidence", "likely", "probably", "suggests"]),
]


@pytest.mark.parametrize("level,indicators", CONFIDENCE_INDICATORS)
def test_every_confidence_indicator_is_detected(level, indicators):
    """Each documented keyword in every tier must classify content at that tier."""
    for indicator in indicators:
        content = f"the assessment said {indicator} about the visitor."
        assert _extract_confidence(content) == level, f"missed {indicator!r}"
```

// UNVERIFIED - not yet run red/green. (Content phrasing is chosen so no other tier's keyword appears as a substring; "confidence" does not contain "confident".)

### Draft 6 — kills C2, C3, C4, C5 (12) — add to TestExtractKeyObservations (:194) and TestExtractKeyFactors (:139)

```python
    def test_observations_flags_dedup_length_and_cap(self):
        """Matching is case-insensitive; dedup, length filter and [:10] cap hold."""
        content = (
            "I OBSERVE that the door is open. "
            "I OBSERVE that the door is open. "  # exact duplicate -> kept once
            "I NOTICE that ab. "  # too short
            "I NOTICE that abcde. "  # 5 chars: excluded by len > 5
            "I SEE that abcdef."  # 6 chars: kept
        )
        observations = _extract_key_observations(content)
        stripped = [obs.strip() for obs in observations]
        assert any("the door is open" in obs for obs in stripped)  # IGNORECASE (kills C2)
        assert sum(1 for obs in stripped if "the door is open" in obs) == 1  # dedup (kills C3)
        assert "abcde" not in stripped  # kills C3/C5 family on observations
        assert "abcdef" in stripped
        many = " ".join(f"I note that observation number {i} stops here." for i in range(12))
        assert len(_extract_key_observations(many)) == 10  # kills C4 ([:11] -> 11)
```

```python
    def test_key_factors_flags_dedup_and_length_boundaries(self):
        """Factor extraction is case-insensitive; dedup and len > 3 boundary hold."""
        assert _extract_key_factors("Due to the late hour.") != []  # capitalized-only match (kills C5 flags)
        content = "due to late hour, due to late hour, due to ab, due to abc, due to abcd."
        factors = _extract_key_factors(content)
        assert sum(1 for f in factors if f == "late hour") == 1  # dedup
        assert "abc" not in factors  # 3-char factor excluded (len > 3)
        assert "abcd" in factors  # 4-char factor kept
```

// UNVERIFIED - not yet run red/green.

## Extras A-D — kill the remaining 21 non-equivalent survivors

### Extra A — kills C1 (2) — module level (needs `_parse_json_response` import)

```python
def test_parse_json_response_accepts_json_objects_only():
    assert _parse_json_response('{"reasoning": "because of rain"}') == {
        "reasoning": "because of rain"
    }
    assert _parse_json_response("not json at all") is None
    assert _parse_json_response("[1, 2]") is None
```

// UNVERIFIED - not yet run red/green.

### Extra B — kills C7 (4) — add to TestExtractRiskFactors (:211)

```python
    def test_risk_factors_dedup_types_keywords_and_cap(self):
        content = "Risk factor: unknown person. Risk factor: unknown person. The person is loitering."
        factors = _extract_risk_factors(content)
        assert all(isinstance(f, str) for f in factors)  # append(None) (kills __13)
        assert sum(1 for f in factors if f == "unknown person") == 1  # dedup (kills __11)
        assert _extract_risk_factors("Nothing notable here at all.") == []  # keywords only when present (kills __17)
        many = "".join(f"risk factor: factor number {i}. " for i in range(12))
        assert len(_extract_risk_factors(many)) == 10  # cap (kills __21)
```

// UNVERIFIED - not yet run red/green.

### Extra C — kills C9 (6) — add to TestParseReasoningSteps (:97)

```python
    def test_steps_carry_key_factors_and_confidence(self):
        numbered = _parse_reasoning_steps("1. The risk is elevated due to the late hour, I am confident.")
        assert numbered[0].key_factors  # kwargs must survive (kills __21/__40)
        assert numbered[0].confidence_indicator == "high"  # kills __18/__22
        paragraph = _parse_reasoning_steps("The risk is elevated due to the late hour, I am confident.")
        assert paragraph[0].key_factors
        assert paragraph[0].confidence_indicator == "high"  # kills __37/__41
```

// UNVERIFIED - not yet run red/green.

### Extra D — kills C18 + C19 (8) — add to TestParseTruncationInfo (:285)

```python
    def test_truncation_reason_surfaces_and_missing_flag_defaults_false(self):
        info = _parse_truncation_info(
            {
                "was_truncated": True,
                "original_length": 8000,
                "truncated_length": 4096,
                "dropped_sections": ["historical_data"],
                "reason": "Token limit exceeded",
            }
        )
        assert info.truncation_reason == "Token limit exceeded"  # kills C18
        sparse = _parse_truncation_info({"reason": "short context"})
        assert sparse.was_truncated is False  # kills C19 (None -> ValidationError; True -> True)
```

// UNVERIFIED - not yet run red/green.

## Verdict for WP4.4

TEST-GAP cluster mass concentrates in `_parse_household_matches` (77) and `_parse_enrichment_sources` (78): the test file asserts existence and shape but never field values for 12 of 14 label paths and never the fallback/default chain. Six drafted tests (182 kills) + four extras (21 kills) close the entire gap; C8 (1 key) is EQUIVALENT and can be annotated/ignored. All new tests are pure-function (no DB/mocks), fast, and follow the existing file's class placement; the `datetime.now`-relative flake trap does not apply here (no time usage).
