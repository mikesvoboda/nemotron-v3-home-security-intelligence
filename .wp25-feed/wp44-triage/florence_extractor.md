# WP4.4 Triage Dossier — backend/services/florence_extractor.py

Generated 2026-09-17 from `mutants/backend/services/florence_extractor.py.meta`
(exit_code 0 = survived). Live mutation run still in progress: 128 survivors, 279 killed,
92 keys still unchecked at read time — survivor set may shift as verdicts land.

**Covering test file (all mutants, all functions):**
`backend/tests/unit/services/test_florence_extractor.py` (802 lines) — per
`mutants/mutmut-stats.json:tests_by_mangled_function_name`, every function in this module
is covered ONLY by this file.

Key line anchors in the covering file:

| Region                                                                                                                                                                     | Lines    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `TestVehicleAttributes` (to_dict :73, to_context_string :90/:106/:112)                                                                                                     | 41–116   |
| `TestPersonAttributes` (to_dict :150, to_context_string :168)                                                                                                              | 119–188  |
| `TestSceneAnalysis` (to_dict :219, to_context_string :250/:264)                                                                                                            | 191–268  |
| `TestEnvironmentContext` (to_dict :297, to_context_string :337)                                                                                                            | 271–349  |
| Helpers (`test_parse_list_response_with_items` :391, `test_parse_list_response_empty` :401, `test_extract_time_of_day` :440)                                               | 352–493  |
| Orchestrators (`test_extract_vehicle_attributes` :508, `test_extract_person_attributes` :544, `test_extract_environment_context` :604, `test_extract_handles_errors` :632) | 496–649+ |

Mutant key prefix omitted in tables: `backend.services.florence_extractor.xǁ` (ǁ = U+01C1).

## Why so many survive — the structural cause

The orchestrator tests (`:508–:629`) mock `_run_inference` with
`responses.get(prompt, "")`, which **swallows every argument** (model, image, prompt):
any call-site mutation that changes arguments to `None` still runs and still returns the
fixture's canned string, because tests assert only the _returned values_, never the _call
arguments_ and never `caption`. The helper tests feed only multi-keyword responses
("It is nighttime, very dark"), so single-keyword-list mutations are masked. The
dataclass tests assert with `in`/`==` per-key instead of exact-string / exact-dict
equality, so label, separator and key-name mutations slip through.

## Cluster table (counts sum to 128)

| #   | Cluster (pattern)                                                                                                                                                                                                                                    | n   | Class      | Example keys (≤3)                                                                                                                                                  | Covering test — what it misses                                                                                                                                                                                                                                                                                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `_extract_time_of_day`: keyword-list literals XX-clobbered or UPPERCASED — each mutant removes one keyword's match; single-token responses kill, multi-keyword fixtures mask it                                                                      | 22  | TEST-GAP   | `_extract_time_of_day__mutmut_5` (`"night"`→`"XXnightXX"`), `_…__mutmut_17` (`evening`), `_…__mutmut_35` (`day`)                                                   | test_florence_extractor.py:440–449 — every input contains ≥2 keywords from its branch, so keyword removal is invisible. No single-token cases, no "bright"/"sunset"/"sunrise"/"evening"-only cases.                                                                                                                                                                         |
| C2  | `_extract_time_of_day`: mutations on keywords dominated by a surviving shorter keyword (`nighttime`/`NIGHTTIME` while `night` stays; `daytime`/`DAYTIME` while `day` stays) — removed keyword is a superset string, can never be the sole signal     | 4   | EQUIVALENT | `_…__mutmut_9`, `_…__mutmut_10`, `_…__mutmut_37`                                                                                                                   | unreachable semantics — no test can kill; kill via mutmut equivalent-mutant suppression or leave.                                                                                                                                                                                                                                                                           |
| C3  | `_parse_list_response`: negation-keyword mutations in the early-return gate (`no ` / `none` / `nothing` / `not visible` XX-clobbered, UPPERCASED, whole-expr `.lower()`→`.upper()`) — gate stops catching the response whose signal was that keyword | 9   | TEST-GAP   | `_parse_list_response__mutmut_3` (`.upper()` flip), `_…__mutmut_4` (`"no "`), `_…__mutmut_10` (`"not visible"`)                                                    | :401–407 tests `"No tools visible"`/`"None detected"`/`"Nothing unusual"` — the _item filter_ still catches these so gate-only mutations survive; no `"not visible"` input (only keyword absent from the item filter), no mixed list like `"nothing, ladder"`. NOTE: analytically keys 4–11 SHOULD already be killed by `"No tools visible"`… they are not — see Anomalies. |
| C4  | `_parse_list_response`: mutations inside the **second** (per-item) filter — unreachable: the earlier gate's keyword list is a superset (gate has all filter keywords + `not visible`), so no item containing them ever reaches the filter            | 7   | EQUIVALENT | `_parse_list_response__mutmut_24` (`item.upper()`), `_…__mutmut_25`                                                                                                | dead code path; no test can kill.                                                                                                                                                                                                                                                                                                                                           |
| C5  | `extract_environment_context`: weather-guard keyword mutations (`cannot`/`unable`/`unclear`/`indoor` XX/UPPERD/`.upper()` on response) — only lowercase happy-path weather ("Clear skies") is ever fed                                               | 9   | TEST-GAP   | `_extract_environment_context__mutmut_40` (`.upper()`), `_…__mutmut_41` (`cannot`), `_…__mutmut_47` (`indoor`)                                                     | :604–629 — `weather="Clear skies"`, never a negative response; `weather=None` path never exercised.                                                                                                                                                                                                                                                                         |
| C6  | `extract_person_attributes`: clothing-guard keyword mutations (`cannot`/`unable`/`unclear`) — same shape                                                                                                                                             | 7   | TEST-GAP   | `_extract_person_attributes__mutmut_30`, `_…__mutmut_31`, `_…__mutmut_32`                                                                                          | :544–572 — clothing fixture "Blue jacket and jeans"; guard-branch (`clothing` stays None) never exercised.                                                                                                                                                                                                                                                                  |
| C7  | `extract_vehicle_attributes`: logo-guard keyword mutations (`no `/`none`/`not visible`) — commercial_text suppression never exercised negatively                                                                                                     | 7   | TEST-GAP   | `_extract_vehicle_attributes__mutmut_63` (`.upper()`), `_…__mutmut_64`, `_…__mutmut_68`                                                                            | :508–541 — logo fixture "FedEx logo visible" (positive only); `commercial_text is None` for negative logo never asserted.                                                                                                                                                                                                                                                   |
| C8  | `extract_*` orchestrators: `_run_inference(...)` call-site args replaced by `None` (model_tuple, image/crop, or prompt) — mock's `responses.get(prompt, "")` swallows the damage                                                                     | 29  | TEST-GAP   | `_extract_environment_context__mutmut_7` (model→None), `_extract_person_attributes__mutmut_11` (prompt→None), `_extract_vehicle_attributes__mutmut_53` (crop→None) | :508/:544/:604 — assertions only on returned attrs; call arguments never inspected, crop identity never checked.                                                                                                                                                                                                                                                            |
| C9  | `attrs.caption = caption_response.strip()` replaced by `None` (person :606, vehicle :540)                                                                                                                                                            | 2   | TEST-GAP   | `_extract_vehicle_attributes__mutmut_17`, `_extract_person_attributes__mutmut_17`                                                                                  | :508–:572 never assert `attrs.caption`.                                                                                                                                                                                                                                                                                                                                     |
| C10 | `*_crop = self._crop_bbox(image, bbox)` replaced by `None` (person :597, vehicle :531)                                                                                                                                                               | 2   | TEST-GAP   | `_extract_vehicle_attributes__mutmut_2`, `_extract_person_attributes__mutmut_2`                                                                                    | crop is passed into the (mocked) inference and forgotten — killed for free by C8's call-argument identity assertion.                                                                                                                                                                                                                                                        |
| C11 | logger call mutations: `logger.debug/warning(...)` argument → `None` or text clobbered, all three orchestrators (entry debug, success debug, failure warning)                                                                                        | 12  | LOW-VALUE  | `_extract_environment_context__mutmut_1`, `_…__mutmut_53`, `_extract_person_attributes__mutmut_72`                                                                 | logging text is diagnostic; asserting it via caplog is brittle noise. Deliberately leave surviving.                                                                                                                                                                                                                                                                         |
| C12 | `to_dict()` key-name literal mutations (`"caption"`→XX/`CAPTION` in Person+Vehicle; `"confidence"`→XX/`CONFIDENCE` in SceneAnalysis) — tests read every key EXCEPT the mutated one                                                                   | 6   | TEST-GAP   | `PersonAttributesǁto_dict__mutmut_9`, `SceneAnalysisǁto_dict__mutmut_9`, `VehicleAttributesǁto_dict__mutmut_10`                                                    | :73–88 (no `caption` assert), :150–166 (no `caption`), :219–232 (no `confidence`); no test does exact key-set/equality. These keys are a serialization contract consumed downstream.                                                                                                                                                                                        |
| C13 | `to_context_string()` literal label mutations (`"Commercial: Yes"`, `"Appears to be service worker"` + lowercased variant, `"Artificial light detected"`)                                                                                            | 4   | TEST-GAP   | `VehicleAttributesǁto_context_string__mutmut_5`, `PersonAttributesǁ…__mutmut_6`, `EnvironmentContextǁ…__mutmut_3`                                                  | :90/:168/:337 use `assert "X" in context` with case-insensitive-ish fragments (`"service worker"`), so `XX…XX`-wrapped or lowercased labels pass. This string is pasted verbatim into LLM prompts — `XX…XX` pollution is a real defect class.                                                                                                                               |
| C14 | `to_context_string()` separator/join mutations (`", "`→`"XX, XX"`, `"; "`→`"XX; XX"` at final join and at inner `', '.join(list)` renders)                                                                                                           | 6   | TEST-GAP   | `SceneAnalysisǁto_context_string__mutmut_7`, `_…__mutmut_16`, `PersonAttributesǁ…__mutmut_14`                                                                      | `in`-substring checks pass whenever a single item exists or the fragment avoids the joined region. Killed by exact-string asserts.                                                                                                                                                                                                                                          |
| C15 | `to_context_string()` caption/description-fallback guard flipped `not parts` → `parts` (Person :159, Scene :205) — caption is _suppressed_ exactly when parts exist and _added_ when it should be                                                    | 2   | TEST-GAP   | `PersonAttributesǁto_context_string__mutmut_10`, `SceneAnalysisǁ…__mutmut_12`                                                                                      | no test constructs populated attrs **plus** a caption; `test_to_context_string_caption_only` (:112) covers Vehicle only.                                                                                                                                                                                                                                                    |

**Totals: TEST-GAP 105 · EQUIVALENT 11 · LOW-VALUE 12 = 128.**

## Anomalies worth flagging to WP4.4 owners

1. **PLR gate mutants 4–11 (C3)**: with the current test file, `test_parse_list_response_empty`'s
   `"No tools visible"` case analytically kills the `"no "`-keyword mutants (gate misses → the
   surviving `"No tools visible"` item is returned non-empty, breaking `== []`). Verdict says
   survived. Either the verdict predates these assertions, or mutmut's per-line test selection
   skipped it. Re-check these keys once the live run settles before spending effort on them.
2. **Env entry-debug text mutants (2,3,4) survived but vehicle/person entry-debug survived only
   as `None`-arg variants** — consistent with C11 being genuinely unkillable-by-design, not a
   test bug.
3. `_parse_list_response`'s per-item filter (lines 419–423) is dead code (C4) — a `# noqa`
   suppression or a refactor note is cheaper than 7 future survivor rows.

## Drafted tests (6 tests killing 105 survivors — clusters C1, C3, C5, C6, C7, C8, C9, C10, C12, C13, C14, C15)

All UNVERIFIED — not yet run red/green. TDD procedure per test: add the test, run it against
the mutant copy / patched mutant line — the named assert must FAIL on the mutant diff — then
run against unmutated `backend/services/florence_extractor.py` and it must PASS.

```python
# UNVERIFIED - not yet run red/green. Append to backend/tests/unit/services/test_florence_extractor.py

class TestFlorenceExtractorParsingGranularity:
    """WP4.4: kill keyword-list mutants by feeding single-signal responses."""

    def setup_method(self) -> None:
        reset_florence_extractor()

    def teardown_method(self) -> None:
        reset_florence_extractor()

    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ("night", "night"),          # kills mutmut_5/6 (night keyword clobbered)
            ("nighttime", "night"),      # kills _9? no (dominated) but guards branch order
            ("dark", "night"),           # kills mutmut_7/8
            ("dusk", "dusk"),
            ("evening", "dusk"),         # kills mutmut_17/18
            ("sunset", "dusk"),          # kills mutmut_19/20
            ("dawn", "dawn"),            # kills mutmut_25/26
            ("sunrise", "dawn"),         # kills mutmut_27/28
            ("morning", "dawn"),         # kills mutmut_29/30
            ("day", "day"),              # kills mutmut_35/36
            ("afternoon", "day"),        # kills mutmut_39/40
            ("midday", "day"),           # kills mutmut_41/42
            ("bright", "day"),           # kills mutmut_43/44
            ("unable to determine", "unknown"),
        ],
    )
    def test_extract_time_of_day_single_keyword(self, response: str, expected: str) -> None:
        """Each keyword must resolve the time of day on its own (kills C1: 22 mutants)."""
        extractor = FlorenceExtractor()
        assert extractor._extract_time_of_day(response) == expected

    @pytest.mark.parametrize(
        "response",
        [
            "not visible",            # only gate keyword absent from the item filter: kills mutmut_3 (.upper flip)
            "NO TOOLS VISIBLE",       # uppercase response: kills mutmut_3 via .upper() flip
            "no tools, ladder",       # gate-only suppression; item filter would spare "ladder": kills mutmut_4/5
            "none, ladder",           # kills mutmut_6/7
            "nothing, ladder",        # kills mutmut_8/9
            "not visible, ladder",    # kills mutmut_10/11
        ],
    )
    def test_parse_list_response_gate_negatives(self, response: str) -> None:
        """Gate must catch every negation keyword standalone and in mixed lists (kills C3: 9)."""
        extractor = FlorenceExtractor()
        assert extractor._parse_list_response(response) == []


class TestFlorenceExtractorNegativeResponses:
    """WP4.4: negative model responses exercise the suppression guards (kills C5/C6/C7: 23)."""

    def setup_method(self) -> None:
        reset_florence_extractor()

    def teardown_method(self) -> None:
        reset_florence_extractor()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "weather_response",
        ["cannot determine", "UNABLE TO SEE", "UNCLEAR", "Unclear from this angle", "indoor scene"],
    )
    async def test_environment_weather_negative_suppressed(self, weather_response: str) -> None:
        """Weather guard must fire on lowercase, uppercase, and mixed-case refusals."""
        from PIL import Image

        extractor = FlorenceExtractor()
        responses = {
            ENVIRONMENT_QUERIES["time_of_day"]: "day",
            ENVIRONMENT_QUERIES["artificial_light"]: "No",
            ENVIRONMENT_QUERIES["weather"]: weather_response,
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference, autospec=True):
            image = Image.new("RGB", (640, 480), color="white")
            context = await extractor.extract_environment_context((MagicMock(), MagicMock()), image)
            assert context.weather is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "clothing_response",
        ["cannot determine clothing", "UNABLE TO DESCRIBE", "UNCLEAR", "Unclear from this angle"],
    )
    async def test_person_clothing_negative_suppressed(self, clothing_response: str) -> None:
        """Clothing guard must fire regardless of keyword casing (kills person mutmut_30-36)."""
        from PIL import Image

        extractor = FlorenceExtractor()
        responses = {
            PERSON_QUERIES["caption"]: "A person",
            PERSON_QUERIES["clothing"]: clothing_response,
            PERSON_QUERIES["carrying"]: "No",
            PERSON_QUERIES["service_worker"]: "No",
            PERSON_QUERIES["action"]: "Standing",
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference, autospec=True):
            image = Image.new("RGB", (640, 480), color="gray")
            attrs = await extractor.extract_person_attributes(
                (MagicMock(), MagicMock()), image, (10, 10, 100, 200)
            )
            assert attrs.clothing is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("logo_response", ["no logo visible", "none", "None visible", "Not visible"])
    async def test_vehicle_commercial_text_negative_logo_suppressed(self, logo_response: str) -> None:
        """Commercial text must stay None when the logo answer is negative (kills vehicle mutmut_63-69)."""
        from PIL import Image

        extractor = FlorenceExtractor()
        responses = {
            VEHICLE_QUERIES["caption"]: "A van",
            VEHICLE_QUERIES["color"]: "White",
            VEHICLE_QUERIES["type"]: "Van",
            VEHICLE_QUERIES["commercial"]: "Yes",
            VEHICLE_QUERIES["logo"]: logo_response,
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference, autospec=True):
            image = Image.new("RGB", (640, 480), color="white")
            attrs = await extractor.extract_vehicle_attributes(
                (MagicMock(), MagicMock()), image, (0, 0, 100, 100)
            )
            assert attrs.is_commercial is True
            assert attrs.commercial_text is None


class TestFlorenceExtractorCallContract:
    """WP4.4: inference call arguments are behavior (kills C8+C9+C10: 33)."""

    def setup_method(self) -> None:
        reset_florence_extractor()

    def teardown_method(self) -> None:
        reset_florence_extractor()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("query_map", "extract_name"),
        [(VEHICLE_QUERIES, "extract_vehicle_attributes"), (PERSON_QUERIES, "extract_person_attributes")],
    )
    async def test_inference_receives_real_model_crop_and_prompt(
        self, query_map: dict[str, str], extract_name: str
    ) -> None:
        """Every inference call gets the real model tuple, a fresh padded crop, and a real prompt."""
        from PIL import Image

        extractor = FlorenceExtractor()
        model_tuple = (MagicMock(name="model"), MagicMock(name="processor"))
        calls: list[tuple[object, object, str]] = []

        async def capture(model, image, prompt):
            calls.append((model, image, prompt))
            return query_map.get(next(k for k, v in query_map.items() if v == prompt), "answer")

        with patch.object(extractor, "_run_inference", side_effect=capture, autospec=True):
            image = Image.new("RGB", (640, 480), color="white")
            bbox = (100, 100, 300, 250)
            attrs = await getattr(extractor, extract_name)(model_tuple, image, bbox)

            assert calls, "no inference calls recorded"
            for model, crop, prompt in calls:
                assert model is model_tuple          # kills model_tuple→None mutants
                assert crop is not None              # kills crop→None mutants
                assert crop is not image             # a real crop, not the original passed through
                assert isinstance(crop.size, tuple) and crop.size == (220, 170)  # bbox+padding=10 each side
                assert prompt in query_map.values()  # kills prompt→None mutants
            assert attrs.caption == "answer"         # kills caption = None mutants (vehicle_17, person_17)


class TestDataclassSerializationContract:
    """WP4.4: exact dict keys and exact context strings (kills C12-C15: 18)."""

    def test_to_dict_exact_key_contract(self) -> None:
        """to_dict output is a wire contract — pin the full key set and values."""
        vehicle = VehicleAttributes(
            color="red", vehicle_type="SUV", is_commercial=True,
            commercial_text="FedEx", caption="a van", confidence=0.9,
        )
        assert vehicle.to_dict() == {
            "color": "red",
            "vehicle_type": "SUV",
            "is_commercial": True,
            "commercial_text": "FedEx",
            "caption": "a van",          # kills vehicle/Person to_dict caption-key mutants
            "confidence": 0.9,
        }

        person = PersonAttributes(
            clothing="uniform", carrying="package", is_service_worker=True,
            action="standing", caption="a person", confidence=0.8,
        )
        assert person.to_dict() == {
            "clothing": "uniform",
            "carrying": "package",
            "is_service_worker": True,
            "action": "standing",
            "caption": "a person",
            "confidence": 0.8,
        }

        scene = SceneAnalysis(
            unusual_objects=["ladder"], tools_detected=["crowbar"],
            abandoned_items=["bag"], scene_description="A garage", confidence=0.7,
        )
        assert scene.to_dict() == {
            "unusual_objects": ["ladder"],
            "tools_detected": ["crowbar"],
            "abandoned_items": ["bag"],
            "scene_description": "A garage",
            "confidence": 0.7,           # kills SceneAnalysis confidence-key mutants
        }

    def test_to_context_string_exact_contract(self) -> None:
        """Context strings go into LLM prompts — pin labels, separators, and fallback behavior."""
        vehicle = VehicleAttributes(
            color="blue", vehicle_type="van", is_commercial=True,
            commercial_text="Amazon", caption="fallback caption",
        )
        assert vehicle.to_context_string() == "Color: blue, Type: van, Commercial: Yes, Company: Amazon"

        person = PersonAttributes(
            clothing="red shirt", carrying="briefcase", action="running",
            is_service_worker=True, caption="a runner",
        )
        assert person.to_context_string() == (
            "Wearing: red shirt, Carrying: briefcase, Action: running, Appears to be service worker"
        )  # kills label mutants _6/_7, separator _14, and not-parts flip _10 (caption must NOT appear)

        scene = SceneAnalysis(
            tools_detected=["ladder", "crowbar"], unusual_objects=["broken window"],
            abandoned_items=["bag"], scene_description="backyard",
        )
        assert scene.to_context_string() == (
            "Tools: ladder, crowbar; Unusual: broken window; Abandoned: bag"
        )  # kills inner-join _7/_10, final sep _16, not-parts flip _12

        env = EnvironmentContext(time_of_day="night", artificial_light=True, weather="foggy")
        assert env.to_context_string() == "Time: night, Artificial light detected, Weather: foggy"
        # kills EnvironmentContext label _3 and separator _8
```

**Kill accounting:** D(TOD single-keyword)=C1(22) · D(PLR gate negatives)=C3(9) ·
D(negative weather/clothing/logo)=C5+C6+C7(23) · D(call contract)=C8+C9+C10(33) ·
D(to_dict exact)=C12(6) · D(context exact)=C13+C14+C15(12). Total covered: **105/105 TEST-GAP survivors**.
EQUIVALENT (11) and LOW-VALUE (12) deliberately unkilled — record them in the WP4.4
equivalent/low-value suppression list rather than writing tests for them.
