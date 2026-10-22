"""Unit tests for backend.services.alerting.redact (B4.2, F13)."""

from __future__ import annotations

import pytest

from backend.services.alerting.redact import (
    escape_html,
    known_name_set,
    redact_names,
)


class TestLabelRedaction:
    def test_known_person_label_is_redacted(self) -> None:
        text = "known person Jane walks toward the door."
        assert redact_names(text, set(), include_names=False) == (
            "known person a known person walks toward the door."
        )

    def test_household_member_label_is_redacted(self) -> None:
        text = "matches household member Sam, holding a package"
        out = redact_names(text, set(), include_names=False)
        assert "Sam" not in out
        assert "household member a known person" in out

    def test_label_match_is_case_insensitive(self) -> None:
        text = "Known Person Jane at the gate"
        out = redact_names(text, set(), include_names=False)
        assert "Jane" not in out

    def test_include_names_passes_through(self) -> None:
        text = "known person Jane walks toward the door."
        assert redact_names(text, set(), include_names=True) == text


class TestBareNameRedaction:
    def test_known_gallery_name_redacted_without_label(self) -> None:
        names = known_name_set(known_people=["Jane"], household_members=["Sam"])
        text = "Jane and Sam are at the gate"
        out = redact_names(text, names, include_names=False)
        assert "Jane" not in out and "Sam" not in out
        assert out.count("a known person") == 2

    def test_name_redaction_is_whole_word(self) -> None:
        names = known_name_set(known_people=["Ann"])
        out = redact_names("Annual review at the gate", names, include_names=False)
        assert out == "Annual review at the gate"

    def test_name_redaction_is_case_insensitive(self) -> None:
        names = known_name_set(known_people=["jane"])
        out = redact_names("JANE at the door", names, include_names=False)
        assert "JANE" not in out


class TestEscape:
    def test_html_escapes_payload_fragments(self) -> None:
        assert (
            escape_html('<b>Person & "dog"</b>')
            == "&lt;b&gt;Person &amp; &quot;dog&quot;&lt;/b&gt;"
        )

    def test_redact_then_escape_composes(self) -> None:
        text = 'known person <Jane> & dog'
        out = escape_html(redact_names(text, set(), include_names=False))
        assert "<Jane>" not in out
        assert "&amp;" in out


class TestNameSet:
    def test_known_name_set_strips_and_skips_empty(self) -> None:
        names = known_name_set(
            known_people=[" Jane ", ""], household_members=[None, "Sam"]
        )
        assert names == {"Jane", "Sam"}


class TestRealSummaryShape:
    def test_specialist_summary_shape(self) -> None:
        """The exact shape the specialists write (vlm_specialists.py:236/:300)."""
        text = (
            "A known person Jane approaches the front door at night. "
            "matches household member Sam. Movement continues toward the garage."
        )
        names = known_name_set(known_people=["Jane"], household_members=["Sam"])
        out = redact_names(text, names, include_names=False)
        assert "Jane" not in out
        assert "Sam" not in out
        # The rest of the sentence survives.
        assert "approaches the front door at night" in out
        assert "Movement continues toward the garage" in out
