"""The prompt rules `python -m synthbench check` enforces (agent-driven design §3.1).

1. Every subject and prop is named with a term from its class's list (taxonomy `terms:`),
   matched as the P1 judge matched prop terms: whole words, any order, plural s/es allowed.
2. No blocklisted injury or real-person phrase (parent spec §3.8).
3. At most MAX_PROMPT_CHARS characters (plan ruling P3-R4).
4. No camera styling or overlay words: check appends CAMERA_SUFFIX, and the camera stage draws
   the real timestamp. This also bars clock times (H:MM, "<n> am/pm", "o'clock"): the camera
   stage draws the real one, and FLUX draws a stated one into the image as fake text.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import yaml

from synthbench.contract.clip import ClipSpec
from synthbench.contract.spec import Spec
from synthbench.taxonomy.model import Taxonomy

BLOCKLIST_FILE = Path(__file__).resolve().parent / "blocklist.yaml"
RULE_OF_CATEGORY = {"injury": 2, "real_people": 2, "styling": 4}

# Rule 4. It ends with the negatives because FLUX.2 draws a fake timestamp bar when asked for
# security-camera footage (design, measured 2026-09-28).
CAMERA_SUFFIX = (
    "Photorealistic still from a fixed, high-mounted security camera looking down at the scene "
    "through a wide-angle lens, ordinary everyday detail, no on-screen text, no timestamp, "
    "no watermark."
)
# Rule 3 (plan ruling P3-R4): FLUX.2 [dev] reads at most 512 tokens; the chat template takes
# 33, and English scene text measured 4.6-4.9 characters per token.
MAX_PROMPT_CHARS = 1200

# Rule 4, continued: a clock time gets drawn as fake text by FLUX (measured 2026-09-28, "at 4:40
# in the morning" -> a "4:40" reroll). H:MM/HH:MM (with an optional am/pm suffix folded in, so
# "12:30pm" is quoted whole rather than matching "30pm" as its own am/pm form), "<n>
# am/pm/a.m/a.m./p.m/p.m." (the final dot is optional: "9 a.m" is a clock time too), or
# "o'clock" (straight or curly apostrophe; chr(0x2019) avoids an ambiguous-unicode literal in
# source, RUF001).
_APOSTROPHES = "'" + chr(0x2019)
_AMPM = r"(?:a\.?m\.?|p\.?m\.?)"
_CLOCK_TIME = re.compile(
    rf"\b\d{{1,2}}:\d{{2}}(?:\s?{_AMPM})?(?!\w)"
    rf"|\b\d{{1,2}}\s?{_AMPM}(?!\w)"
    rf"|\bo[{_APOSTROPHES}]clock\b",
    re.IGNORECASE,
)


def words(text: str) -> list[str]:
    """Lowercase alphanumeric words: "ground-floor" -> ["ground", "floor"]."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _forms(word: str) -> set[str]:
    return {word, f"{word}s", f"{word}es"}


def mentions(text: str, terms: Sequence[str]) -> bool:
    """Rule 1: some term has all its words in the text, in any order, each a whole word."""
    field = set(words(text))
    return any(
        all(_forms(word) & field for word in term_words)
        for term_words in (words(term) for term in terms)
        if term_words
    )


def contains_phrase(text: str, phrase: str) -> bool:
    """Rules 2 and 4: the phrase's words appear together and in order (the last may be plural)."""
    target = words(phrase)
    if not target:
        return False
    tokens = words(text)
    size = len(target)
    return any(
        tokens[i : i + size - 1] == target[:-1] and tokens[i + size - 1] in _forms(target[-1])
        for i in range(len(tokens) - size + 1)
    )


def clock_times(text: str) -> list[str]:
    """Rule 4: every distinct clock-time-shaped match in the prompt, in first-seen order."""
    seen: list[str] = []
    for match in _CLOCK_TIME.finditer(text):
        found = match.group(0)
        if found not in seen:
            seen.append(found)
    return seen


@cache
def blocklist(path: Path = BLOCKLIST_FILE) -> dict[str, tuple[str, ...]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if set(data) != set(RULE_OF_CATEGORY):
        raise ValueError(
            f"{path}: categories must be {sorted(RULE_OF_CATEGORY)}, got {sorted(data)}"
        )
    return {category: tuple(str(p).lower() for p in phrases) for category, phrases in data.items()}


def render_text(spec: Spec) -> str:
    """Exactly what FLUX.2 receives: the frozen prompt, then the camera suffix."""
    if spec.prompt is None or spec.camera_suffix is None:
        raise ValueError(f"{spec.event_id} has no frozen prompt")
    return f"{spec.prompt} {spec.camera_suffix}"


def prompt_sha256(spec: Spec) -> str:
    return hashlib.sha256(render_text(spec).encode()).hexdigest()


def problems(spec: Spec | ClipSpec, prompt: str, tax: Taxonomy) -> list[str]:
    """Every rule the prompt breaks for this spec, one line each; empty when it passes."""
    if not prompt.strip():
        return ["rule 1: the prompt is empty"]
    found: list[str] = []
    for kind, items in (("subject", spec.subjects), ("prop", spec.props)):
        for item in items:
            terms = tax.terms[item.cls]
            if not mentions(prompt, terms):
                found.append(
                    f"rule 1: mention {kind} {item.id} ({item.cls}) with one of: {', '.join(terms)}"
                )
    for category, phrases in blocklist().items():
        for phrase in phrases:
            if contains_phrase(prompt, phrase):
                found.append(f"rule {RULE_OF_CATEGORY[category]}: remove '{phrase}' ({category})")
    for clock in clock_times(prompt):
        found.append(
            f'rule 4: no clock times ("{clock}"): describe the light instead (dawn, midday, '
            "late evening); the camera stage draws the time"
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        found.append(f"rule 3: {len(prompt)} characters; at most {MAX_PROMPT_CHARS}")
    return found
