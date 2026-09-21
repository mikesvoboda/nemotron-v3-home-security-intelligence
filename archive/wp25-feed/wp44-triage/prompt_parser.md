# WP4.4 Triage Dossier — backend/services/prompt_parser.py

**Census:** 211 mutants total — 186 killed, **25 survived** (0 unchecked). All survivor diffs pulled via
`uv run mutmut show <key>` (all succeeded; no manual fallback needed).

**Covering test file (single file for all four functions):**
`backend/tests/unit/services/test_prompt_parser.py` (890 lines; unit + Hypothesis property classes).

**Module shape note (drives most verdicts):** in `generate_insertion_text` the `"curly"` branch is
textually identical to the `else` fallback (`var = f"{{{proposed_variable}}}"` on both sides), and the
label branch is `if label_style == "equals": ... else: <colon>`. Any mutation of the string constants
"curly"/"colon" — as `.get(key, DEFAULT)` defaults or as the comparison literal — is absorbed by the
identical fallback path and produces byte-identical output for every input. This is the model_zoo-style
"dead default" absorption pattern from the queue index.

## Cluster table (sums to 25)

| # | Cluster | Count | Class | Example keys |
|---|---------|-------|-------|--------------|
| C1 | `find_insertion_point` fallback `logger.warning` — message-string and %-arg surgery | 5 | EQUIVALENT | `x_find_insertion_point__mutmut_24`, `_26`, `_29` |
| C2 | `find_insertion_point` fallback `logger.warning` — structured `extra=` payload removal/renames | 6 | LOW-VALUE | `x_find_insertion_point__mutmut_25`, `_33`, `_35` |
| C3 | `generate_insertion_text` — "curly" format default & comparison constants absorbed by identical else-fallback | 6 | EQUIVALENT | `x_generate_insertion_text__mutmut_11`, `_17`, `_28` |
| C4 | `generate_insertion_text` — label_style default constants absorbed by colon `else` branch | 4 | EQUIVALENT | `x_generate_insertion_text__mutmut_20`, `_25`, `_26` |
| C5 | `detect_variable_style` — label regexes lose the `[A-Z]` anchor (`[A-Z][a-z]+` → `[a-z][a-z]+`) | 2 | **TEST-GAP** | `x_detect_variable_style__mutmut_51`, `_63` |
| C6 | `validate_prompt_syntax` — duplicate-variable join separator `", "` mutated to `"XX, XX"` | 1 | **TEST-GAP** | `x_validate_prompt_syntax__mutmut_24` |
| C7 | `validate_prompt_syntax` — angle close-count literal `">"` → `"XX>XX"` (warning counts wrong) | 1 | **TEST-GAP** | `x_validate_prompt_syntax__mutmut_31` |

**Totals: TEST-GAP 4 / EQUIVALENT 15 / LOW-VALUE 6.**

## Cluster notes

### C1 — EQUIVALENT (5) — fallback warning message prose/args
Keys: `__mutmut_24` (arg `target_section`→`None`), `_26` (format string deleted, section name becomes
the msg), `_27` (positional arg deleted → raw `%s` + logging-module stderr noise), `_29` (`XX…XX`
wrappers), `_30` (lowercase first letter). Return value `(len(prompt), "fallback")` unchanged in all
five; observable delta is confined to the rendered log message. Per the WP4.3 convention ("pure
log/message text" ⇒ EQUIVALENT) and the fact that `test_fallback_when_section_not_found`
(test_prompt_parser.py:96) and `test_empty_prompt_returns_fallback` (:126) assert only the return
tuple with zero `caplog` usage in the entire file. `_27` additionally emits a `--- Logging error ---`
trace to stderr; still diagnostic-only. Optional kill-all draft at the end of this dossier if the
closeout wants belt-and-braces coverage of the silent-degradation path.

### C2 — LOW-VALUE (6) — fallback warning `extra=` payload
Keys: `_25` and `_28` (whole `extra={...}` dropped — record loses the attributes), `_32`/`_34`
(`"XXtarget_sectionXX"`/`"XXprompt_lengthXX"`), `_33`/`_35` (key casing `TARGET_SECTION`/`PROMPT_LENGTH`).
Real change to the JSON-structured log payload (`CustomJsonFormatter` dumps extra attrs generically),
but grep found **no in-repo consumer parsing these keys** — this is the Prometheus-label-casing
precedent from the queue index (class "label CASING → LOW-VALUE"). The function's return contract is
untouched. Same optional caplog draft kills these if wanted.

### C3 — EQUIVALENT (6) — "curly" constant absorption
Keys: `_11` (format default→`None`), `_13` (default deleted), `_16` (`"XXcurlyXX"` default),
`_17` (`"CURLY"` default), `_28`/`_29` (`if var_format == "XXcurlyXX"`/`"CURLY"` comparison).
Absorption proof: `curly` branch and `else` branch both evaluate to `f"{{{proposed_variable}}}"`, so
any mutation of the "curly" string (default or comparison) routes execution into the else branch with
identical output — for **every** input, including a hypothetical caller literally passing `"XXcurlyXX"`.
`test_handles_missing_keys_with_defaults` (:254) and `test_defaults_to_curly_when_format_none` (:240)
execute these lines and get byte-identical text. Unkillable; do not draft.

### C4 — EQUIVALENT (4) — label_style default absorption
Keys: `_20` (default→`None`), `_22` (default deleted), `_25` (`"XXcolonXX"`), `_26` (`"COLON"`).
The default is only ever compared against `"equals"`; none of the mutants equal it, so the colon
`else` fires — the same branch the original `"colon"` default takes. Byte-identical output for every
style dict; `test_defaults_to_colon_when_label_style_none` (:247) executes them. Unkillable; do not
draft.

### C5 — TEST-GAP (2) — label regexes lose the uppercase anchor
Keys: `x_detect_variable_style__mutmut_51` (colon regex `[A-Z][a-z]+:\s*` → `[a-z][a-z]+:\s*`),
`_63` (equals regex `[A-Z][a-z]+=` → `[a-z][a-z]+=`).
Real behavior change: a prompt whose only labeled lines are lowercase (`camera: {x}`) currently
reports `label_style == "none"`; the mutants report `"colon"`/`"equals"`, which then flows through
`apply_suggestion_to_prompt` and changes the generated line's separator. **Coverage gap:**
`test_detects_colon_label_style` (test_prompt_parser.py:163) and `test_detects_equals_label_style`
(:169) feed only uppercase-labeled samples (`SAMPLE_PROMPT_CURLY`, `SAMPLE_PROMPT_EQUALS`), and
`test_variable_with_uppercase_ignored` (:469) pins the *variable* regex's case-sensitivity but never
touches `label_style`. No test anywhere feeds a lowercase-labeled prompt. Property tests
(:546-:604) only assert the value is in the legal set — `"colon"` is legal, so no trip.
Drafts: T1a + T1b below.

### C6 — TEST-GAP (1) — duplicate-list separator unasserted
Key: `x_validate_prompt_syntax__mutmut_24` (`"', '.join(...)"` → `"XX, XX'.join(...)"` — warning
becomes `"Duplicate variables: var_aXX, XXvar_b"`).
`test_detects_multiple_duplicate_variables` (test_prompt_parser.py:300) asserts membership only
(`"var_a" in warnings[0]`) — a token-substring test the separator mutant slips through. The curly
test (:271) shows the file's own style *does* pin message content; the duplicate test just doesn't.
Draft: T2.

### C7 — TEST-GAP (1) — angle-bracket warning counts unasserted
Key: `x_validate_prompt_syntax__mutmut_31` (`prompt.count(">")` → `prompt.count("XX>XX")` — a prompt
with real `>` characters now counts 0 closers, warning prints a wrong close count; the warning still
fires whenever open>0 so count-only blindness survives).
`test_detects_unclosed_angle_brackets` (test_prompt_parser.py:310) asserts only
`"Unbalanced angle brackets" in warnings[0]`, while its curly twin `test_detects_unclosed_curly_brace`
(:271) asserts `"2 open"` and `"0 close"`. Direct asymmetry = classic weak-assert TEST-GAP. Draft: T3.

## Drafted kill tests (UNVERIFIED — not yet run red/green)

All appended to `backend/tests/unit/services/test_prompt_parser.py` inside the matching existing
classes; imports already present at the top of the file (no new imports needed for T1–T3).
TDD procedure for each: expect FAILED on the mutant (assertion names above), PASSED on pristine —
run only in the serial WP4.4 pytest/kill-probe lane (per the stale-mutants-tree protocol, sync the
touched test into the in-tree copy before probing).

### T1a — kills C5/`x_detect_variable_style__mutmut_51` (in `TestDetectVariableStyle`, after line 173)

```python
    def test_label_style_none_for_lowercase_colon_labels(self) -> None:
        """Label regex is anchored on an uppercase first letter — 'camera: {var}' is not colon style."""
        style = detect_variable_style("camera: {camera_name}\ntimestamp: {timestamp}\n")

        assert style["format"] == "curly"
        assert style["label_style"] == "none"
```

Red/green: mutant 51's `[a-z][a-z]+:\s*[\{\<\$]` matches `camera: {` → `"colon"` → assert red;
original requires `[A-Z]` start, none present → `"none"` → green.

### T1b — kills C5/`x_detect_variable_style__mutmut_63` (same class)

```python
    def test_label_style_none_for_lowercase_equals_labels(self) -> None:
        """The [A-Z] anchor applies to the equals-label regex too — 'camera={var}' stays 'none'."""
        style = detect_variable_style("camera={camera_name}\ntimestamp={timestamp}\n")

        assert style["label_style"] == "none"
```

Red/green: mutant 63 matches `camera={` → `"equals"` → red; original → `"none"` → green.
(T1a does not kill 63 — no colon in its prompt — hence the pair.)

### T2 — kills C6/`x_validate_prompt_syntax__mutmut_24` (in `TestValidatePromptSyntax`, after line 308)

```python
    def test_duplicate_variables_warning_exact_message(self) -> None:
        """Duplicate list is ', '-joined in sorted order — pin the exact warning string."""
        prompt_with_duplicates = "A: {var_a}\nB: {var_a}\nC: {var_b}\nD: {var_b}\n"
        warnings = validate_prompt_syntax(prompt_with_duplicates)

        assert warnings == ["Duplicate variables: var_a, var_b"]
```

Red/green: mutant joins with `"XX, XX"` → `"Duplicate variables: var_aXX, XXvar_b"` ≠ → red;
original → exact match → green. (Curly braces balanced 4/4, no angle chars → exactly one warning.)

### T3 — kills C7/`x_validate_prompt_syntax__mutmut_31` (in `TestValidatePromptSyntax`, after line 316)

```python
    def test_angle_bracket_warning_reports_counts(self) -> None:
        """Angle warning carries open/close counts, mirroring the curly-brace warning style."""
        prompt_with_unclosed = "Camera: <camera_name\nTime: <timestamp>"
        warnings = validate_prompt_syntax(prompt_with_unclosed)

        assert len(warnings) == 1
        assert "2 open" in warnings[0]
        assert "1 close" in warnings[0]
```

Red/green: mutant counts `close_angles = count("XX>XX") = 0` → `"2 open, 0 close"` → `"1 close"`
assert red; original `"2 open, 1 close"` → green.

### T4 (optional — targets LOW-VALUE C2 and most of C1) — one caplog test kills all 11
`find_insertion_point` fallback survivors. Adds `import logging` at module top. Marked optional:
C1/C2 are classified non-TEST-GAP, so this is belt-and-braces for the silent-degradation path, not a
required kill.

```python
    def test_fallback_logs_warning_with_target_and_length(self, caplog) -> None:
        """Fallback path warns with the missing section name and structured extra payload."""
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.services.prompt_parser"):
            find_insertion_point(SAMPLE_PROMPT_CURLY, "Nonexistent Section", "append")

        messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(messages) == 1
        record = messages[0]
        assert record.getMessage() == (
            "Section 'Nonexistent Section' not found in prompt, falling back to end insertion"
        )
        assert record.target_section == "Nonexistent Section"
        assert record.prompt_length == len(SAMPLE_PROMPT_CURLY)
```

// UNVERIFIED - not yet run red/green (all drafts above)

## No-deletion receipts
- 15 EQUIVALENT (C1, C3, C4): proven by branch-identity argument (C3/C4) and log-prose-only scope (C1).
- 6 LOW-VALUE (C2): structured-log payload key casing/dropping; zero in-repo consumers (grep over
  `backend/` excluding tests/mutants shows `prompt_parser` symbols referenced only by its own test file).
