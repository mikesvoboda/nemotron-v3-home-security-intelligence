"""Payload redaction for outbound alert deliveries (B4.2, F13).

The VLM summary can carry gallery names ("known person Jane", "matches household
member Sam") because the specialists put names into the prompt. Nothing leaves
the house with those names unless the channel's ``include_names`` switch is on:
every gallery name becomes "a known person". Email bodies are HTML-escaped on
top of this (the email adapter does the escaping — see F9/F13).
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence

_REDACTED = "a known person"

# The specialists write "known person <name>" and "matches household member <name>"
# (backend/services/vlm_specialists.py:236/:300). Gallery names are proper nouns:
# 1-3 capitalised words (Mary Jane Watson), letters/hyphens/apostrophes only —
# so a lowercase verb after the name terminates the match. The label match is
# case-insensitive; the name group is scoped case-SENSITIVE (?-i:) so a whole
# pattern IGNORECASE does not let lowercase verbs join the name.
_NAME = r"(?-i:[A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,2})"
_NAME_PATTERN = re.compile(
    rf"(?P<label>\bknown person|\bmatches household member|\bhousehold member)"
    rf"\s+(?P<name>{_NAME})",
    re.IGNORECASE,
)


def redact_names(text: str, known_names: set[str], include_names: bool) -> str:
    """Redact gallery names from a payload text.

    Two passes, because names reach the summary two ways:

    1. The specialists' fixed labels ("known person X", "matches household
       member X") — the label names the gallery, so everything after it is a
       name.
    2. Any bare occurrence of a known gallery name (known people, household
       members, vehicle owners) — the summary might mention a name outside the
       label pattern.

    With ``include_names`` on the text passes through unchanged (ISS-048: the
    channel opted in). ``known_names`` comes from the recognisers' person-name
    tables (KnownPerson.name, HouseholdMember.name) resolved per alert.
    """
    if include_names or not text:
        return text
    redacted = _NAME_PATTERN.sub(lambda m: f"{m.group('label')} {_REDACTED}", text)
    if known_names:
        for name in known_names:
            if not name:
                continue
            pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
            redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def escape_html(text: str) -> str:
    """HTML-escape a payload fragment for an email body (F13)."""
    return html.escape(text, quote=True)


def known_name_set(
    known_people: Sequence[str] | None = None,
    household_members: Sequence[str] | None = None,
    vehicle_owners: Sequence[str] | None = None,
) -> set[str]:
    """Build the gallery-name set from the recognisers' name sources."""
    names: set[str] = set()
    for source in (known_people, household_members, vehicle_owners):
        for name in source or ():
            if name and name.strip():
                names.add(name.strip())
    return names


__all__ = ["escape_html", "known_name_set", "redact_names"]
