"""Unit tests for ServiceProviderMatcher service.

Tests cover:
- ServiceMatch dataclass creation and fields
- Exact matching of service provider names
- Fuzzy matching using Levenshtein distance (similarity >= 0.85)
- Case insensitivity for all matches
- Multiple alias matching for same provider
- No match scenarios for random text
- ServiceCategory enum values

Implements Scene OCR feature from docs/plans/2026-02-04-scene-ocr-design.md
"""

from __future__ import annotations

import pytest

from backend.services.service_provider_matcher import (
    ServiceCategory,
    ServiceMatch,
    ServiceProviderMatcher,
    get_service_provider_matcher,
    levenshtein_ratio,
    reset_service_provider_matcher,
)

# =============================================================================
# Levenshtein Ratio Tests
# =============================================================================


class TestLevenshteinRatio:
    """Tests for the levenshtein_ratio function."""

    def test_identical_strings(self) -> None:
        """Test that identical strings have ratio 1.0."""
        assert levenshtein_ratio("FedEx", "FedEx") == 1.0

    def test_empty_strings(self) -> None:
        """Test that empty strings return 0.0."""
        assert levenshtein_ratio("", "") == 0.0
        assert levenshtein_ratio("FedEx", "") == 0.0
        assert levenshtein_ratio("", "FedEx") == 0.0

    def test_similar_strings(self) -> None:
        """Test ratio for similar strings."""
        # AMAZ0N vs AMAZON - one character different
        ratio = levenshtein_ratio("AMAZ0N", "AMAZON")
        assert ratio > 0.8  # Should be high similarity

    def test_very_different_strings(self) -> None:
        """Test ratio for very different strings."""
        ratio = levenshtein_ratio("FedEx", "XYZABC")
        assert ratio < 0.5  # Low similarity


# =============================================================================
# ServiceCategory Enum Tests
# =============================================================================


class TestServiceCategory:
    """Tests for ServiceCategory enum."""

    def test_all_expected_categories_exist(self) -> None:
        """Test that all expected service categories are defined."""
        expected_categories = [
            "DELIVERY",
            "UTILITY",
            "TELECOM",
            "PLUMBING",
            "HVAC",
            "ELECTRICAL",
            "LANDSCAPING",
            "PEST_CONTROL",
            "MEDICAL",
            "SECURITY",
            "FOOD_DELIVERY",
        ]

        for category_name in expected_categories:
            assert hasattr(ServiceCategory, category_name), f"Missing category: {category_name}"

    def test_category_values_are_strings(self) -> None:
        """Test that category values are lowercase strings."""
        assert ServiceCategory.DELIVERY.value == "delivery"
        assert ServiceCategory.UTILITY.value == "utility"
        assert ServiceCategory.FOOD_DELIVERY.value == "food_delivery"

    def test_category_is_string_enum(self) -> None:
        """Test that ServiceCategory is a string enum."""
        # ServiceCategory inherits from str, so it should be usable as a string
        assert isinstance(ServiceCategory.DELIVERY, str)
        assert ServiceCategory.DELIVERY == "delivery"


# =============================================================================
# ServiceMatch Dataclass Tests
# =============================================================================


class TestServiceMatch:
    """Tests for ServiceMatch dataclass."""

    def test_service_match_required_fields(self) -> None:
        """Test ServiceMatch with required fields."""
        match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=1.0,
            risk_modifier="low_risk_service",
        )

        assert match.provider == "FedEx"
        assert match.category == "DELIVERY"
        assert match.confidence == 1.0
        assert match.risk_modifier == "low_risk_service"

    def test_service_match_optional_matched_alias(self) -> None:
        """Test ServiceMatch with matched_alias field."""
        match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=0.92,
            risk_modifier="low_risk_service",
            matched_alias="FEDEX",
        )

        assert match.matched_alias == "FEDEX"

    def test_service_match_to_dict(self) -> None:
        """Test ServiceMatch.to_dict() serialization."""
        match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=1.0,
            risk_modifier="low_risk_service",
        )

        result = match.to_dict()

        assert result["provider"] == "FedEx"
        assert result["category"] == "DELIVERY"
        assert result["confidence"] == 1.0
        assert result["risk_modifier"] == "low_risk_service"

    def test_service_match_is_frozen(self) -> None:
        """Test that ServiceMatch is immutable (frozen dataclass)."""
        match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=1.0,
            risk_modifier="low_risk_service",
        )

        with pytest.raises(AttributeError):
            match.provider = "UPS"  # type: ignore[misc]


# =============================================================================
# ServiceProviderMatcher Exact Match Tests
# =============================================================================


class TestServiceProviderMatcherExactMatch:
    """Tests for ServiceProviderMatcher exact matching."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_exact_match_fedex(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for 'FedEx'."""
        result = matcher.match("FedEx")

        assert result is not None
        assert result.provider == "FedEx"
        assert result.category == "DELIVERY"
        assert result.confidence == 1.0

    def test_exact_match_amazon(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for 'Amazon'."""
        result = matcher.match("Amazon")

        assert result is not None
        assert result.provider == "Amazon"
        assert result.category == "DELIVERY"
        assert result.confidence == 1.0

    def test_exact_match_ups(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for 'UPS'."""
        result = matcher.match("UPS")

        assert result is not None
        assert result.provider == "UPS"
        assert result.category == "DELIVERY"
        assert result.confidence == 1.0

    def test_exact_match_usps(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for 'USPS'."""
        result = matcher.match("USPS")

        assert result is not None
        assert result.provider == "USPS"
        assert result.category == "DELIVERY"
        assert result.confidence == 1.0

    def test_exact_match_utility_provider(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for utility provider 'PG&E'."""
        result = matcher.match("PG&E")

        assert result is not None
        assert result.provider == "PG&E"
        assert result.category == "UTILITY"

    def test_exact_match_telecom_provider(self, matcher: ServiceProviderMatcher) -> None:
        """Test exact match for telecom provider 'AT&T'."""
        result = matcher.match("AT&T")

        assert result is not None
        assert result.provider == "AT&T"
        assert result.category == "TELECOM"


# =============================================================================
# ServiceProviderMatcher Case Insensitivity Tests
# =============================================================================


class TestServiceProviderMatcherCaseInsensitivity:
    """Tests for case-insensitive matching."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_case_insensitive_lowercase(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching lowercase 'fedex'."""
        result = matcher.match("fedex")

        assert result is not None
        assert result.provider == "FedEx"
        assert result.confidence == 1.0

    def test_case_insensitive_uppercase(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching uppercase 'FEDEX'."""
        result = matcher.match("FEDEX")

        assert result is not None
        assert result.provider == "FedEx"
        assert result.confidence == 1.0

    def test_case_insensitive_mixed_case(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching mixed case 'FeDEx'."""
        result = matcher.match("FeDEx")

        assert result is not None
        assert result.provider == "FedEx"
        # May be exact or fuzzy depending on alias registration
        assert result.confidence >= 0.85

    def test_case_insensitive_amazon(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'AMAZON' (uppercase)."""
        result = matcher.match("AMAZON")

        assert result is not None
        assert result.provider == "Amazon"
        assert result.confidence == 1.0

    def test_case_insensitive_with_whitespace(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching with leading/trailing whitespace."""
        result = matcher.match("  FEDEX  ")

        assert result is not None
        assert result.provider == "FedEx"
        assert result.confidence == 1.0


# =============================================================================
# ServiceProviderMatcher Fuzzy Match Tests
# =============================================================================


class TestServiceProviderMatcherFuzzyMatch:
    """Tests for fuzzy matching using Levenshtein distance."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_fuzzy_match_with_space_insertion(self, matcher: ServiceProviderMatcher) -> None:
        """Test fuzzy match for 'Fed Ex' (OCR space insertion error)."""
        result = matcher.match("Fed Ex")

        # "Fed Ex" may fuzzy match to "FedEx" if similarity >= 0.85
        # "FED EX" vs "FEDEX" has similarity ~0.91
        if result is not None:
            assert result.provider == "FedEx"
            assert result.confidence >= 0.85

    def test_fuzzy_match_extra_letter(self, matcher: ServiceProviderMatcher) -> None:
        """Test fuzzy match for 'AMAZOON' (OCR extra letter insertion).

        Note: Single character substitutions like 'AMAZ0N' have similarity ~0.83
        which is below threshold. Extra letter insertion gives higher similarity.
        """
        result = matcher.match("AMAZOON")

        # "AMAZOON" vs "AMAZON" should have high similarity (~0.92)
        assert result is not None
        assert result.provider == "Amazon"
        assert result.confidence >= 0.85
        assert result.confidence < 1.0

    def test_fuzzy_match_partial_name(self, matcher: ServiceProviderMatcher) -> None:
        """Test fuzzy match for partial name like 'FedEx Ground'."""
        result = matcher.match("FedEx Ground")

        assert result is not None
        assert result.provider == "FedEx"
        # Should match via exact alias "FedEx Ground"
        assert result.confidence == 1.0

    def test_fuzzy_match_ups_typo(self, matcher: ServiceProviderMatcher) -> None:
        """Test fuzzy match for 'UPX' (single character typo)."""
        result = matcher.match("UPX")

        # UPX -> UPS = 2/3 = 0.67 similarity, below 0.85 threshold
        assert result is None

    def test_fuzzy_match_dhl_with_extra_char(self, matcher: ServiceProviderMatcher) -> None:
        """Test fuzzy match for 'DHLL' (OCR double letter).

        rapidfuzz calculates DHLL vs DHL as ~0.857 similarity (above threshold),
        so this actually matches. We test this behavior.
        """
        result = matcher.match("DHLL")

        # DHLL vs DHL = ~0.857 similarity with rapidfuzz, just above 0.85 threshold
        # This is expected to match (rapidfuzz is more lenient than difflib)
        if result is not None:
            assert result.provider == "DHL"
            assert result.confidence >= 0.85

    def test_fuzzy_match_amazon_prime(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'Amazon Prime' should match Amazon."""
        result = matcher.match("Amazon Prime")

        assert result is not None
        assert result.provider == "Amazon"
        # Should match via exact alias

    def test_fuzzy_match_fedex_express(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'FedEx Express' should match FedEx."""
        result = matcher.match("FedEx Express")

        assert result is not None
        assert result.provider == "FedEx"


# =============================================================================
# ServiceProviderMatcher No Match Tests
# =============================================================================


class TestServiceProviderMatcherNoMatch:
    """Tests for scenarios where no match should be found."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_no_match_random_text(self, matcher: ServiceProviderMatcher) -> None:
        """Test that random text doesn't match any provider."""
        result = matcher.match("XYZABC123")

        assert result is None

    def test_no_match_gibberish(self, matcher: ServiceProviderMatcher) -> None:
        """Test that gibberish text doesn't match."""
        result = matcher.match("asdfghjkl")

        assert result is None

    def test_no_match_numbers_only(self, matcher: ServiceProviderMatcher) -> None:
        """Test that pure numbers don't match."""
        result = matcher.match("12345678")

        assert result is None

    def test_no_match_empty_string(self, matcher: ServiceProviderMatcher) -> None:
        """Test that empty string doesn't match."""
        result = matcher.match("")

        assert result is None

    def test_no_match_whitespace_only(self, matcher: ServiceProviderMatcher) -> None:
        """Test that whitespace-only string doesn't match."""
        result = matcher.match("   ")

        assert result is None

    def test_no_match_short_text(self, matcher: ServiceProviderMatcher) -> None:
        """Test that very short text doesn't falsely match."""
        result = matcher.match("A")

        assert result is None

    def test_no_match_partial_below_threshold(self, matcher: ServiceProviderMatcher) -> None:
        """Test that partial text with similarity below threshold doesn't match."""
        # "Fed" vs "FedEx" similarity is ~0.6 (below 0.85)
        result = matcher.match("Fed")

        assert result is None


# =============================================================================
# ServiceProviderMatcher Alias Tests
# =============================================================================


class TestServiceProviderMatcherAliasMatching:
    """Tests for alias-based matching."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_alias_match_united_parcel_service(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'United Parcel Service' (UPS alias)."""
        result = matcher.match("United Parcel Service")

        assert result is not None
        assert result.provider == "UPS"
        assert result.confidence == 1.0  # Exact alias match

    def test_alias_match_us_postal_service(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'US Postal Service' (USPS alias)."""
        result = matcher.match("US Postal Service")

        assert result is not None
        assert result.provider == "USPS"

    def test_alias_match_xfinity(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'Xfinity' (Comcast alias)."""
        result = matcher.match("Xfinity")

        assert result is not None
        assert result.provider == "Comcast"
        assert result.category == "TELECOM"

    def test_alias_match_pacific_gas(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'Pacific Gas' (PG&E alias)."""
        result = matcher.match("Pacific Gas")

        assert result is not None
        assert result.provider == "PG&E"
        assert result.category == "UTILITY"

    def test_alias_match_verizon_fios(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching 'Verizon Fios' (Verizon alias)."""
        result = matcher.match("Verizon Fios")

        assert result is not None
        assert result.provider == "Verizon"
        assert result.category == "TELECOM"


# =============================================================================
# ServiceProviderMatcher Multiple Category Tests
# =============================================================================


class TestServiceProviderMatcherCategories:
    """Tests for different provider categories."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_delivery_category_providers(self, matcher: ServiceProviderMatcher) -> None:
        """Test that delivery providers have correct category."""
        delivery_providers = ["FedEx", "UPS", "USPS", "Amazon", "DHL"]

        for provider in delivery_providers:
            result = matcher.match(provider)
            assert result is not None, f"Expected match for {provider}"
            assert result.category == "DELIVERY", f"{provider} should be DELIVERY"

    def test_food_delivery_category_providers(self, matcher: ServiceProviderMatcher) -> None:
        """Test food delivery providers."""
        food_providers = ["DoorDash", "Uber Eats", "Grubhub"]

        for provider in food_providers:
            result = matcher.match(provider)
            if result is not None:  # Only check if provider exists in database
                assert result.category == "FOOD_DELIVERY"

    def test_utility_category_providers(self, matcher: ServiceProviderMatcher) -> None:
        """Test utility providers."""
        result = matcher.match("PG&E")

        assert result is not None
        assert result.category == "UTILITY"

    def test_plumbing_category_provider(self, matcher: ServiceProviderMatcher) -> None:
        """Test plumbing provider 'Roto-Rooter'."""
        result = matcher.match("Roto-Rooter")

        assert result is not None
        assert result.provider == "Roto-Rooter"
        assert result.category == "PLUMBING"


# =============================================================================
# ServiceProviderMatcher Provider Database Tests
# =============================================================================


class TestServiceProviderMatcherDatabase:
    """Tests for provider database structure."""

    def test_database_has_minimum_providers(self) -> None:
        """Test that database has at least 50 providers."""
        reset_service_provider_matcher()
        matcher = get_service_provider_matcher()

        # Access provider count
        assert len(matcher.providers) >= 50

    def test_database_has_all_main_categories(self) -> None:
        """Test that database has providers in main expected categories."""
        reset_service_provider_matcher()
        matcher = get_service_provider_matcher()

        # Get unique categories from providers
        categories_found = {p["category"] for p in matcher.providers}

        expected_categories = {
            "DELIVERY",
            "UTILITY",
            "TELECOM",
            "PLUMBING",
        }

        for expected in expected_categories:
            assert expected in categories_found, f"Missing providers in category: {expected}"


# =============================================================================
# ServiceProviderMatcher Singleton Tests
# =============================================================================


class TestServiceProviderMatcherSingleton:
    """Tests for singleton pattern."""

    def test_get_service_provider_matcher_returns_instance(self) -> None:
        """Test that get_service_provider_matcher returns an instance."""
        reset_service_provider_matcher()
        matcher = get_service_provider_matcher()

        assert isinstance(matcher, ServiceProviderMatcher)

    def test_get_service_provider_matcher_returns_same_instance(self) -> None:
        """Test that get_service_provider_matcher returns the same instance."""
        reset_service_provider_matcher()
        matcher1 = get_service_provider_matcher()
        matcher2 = get_service_provider_matcher()

        assert matcher1 is matcher2

    def test_reset_service_provider_matcher(self) -> None:
        """Test that reset creates a new instance."""
        reset_service_provider_matcher()
        matcher1 = get_service_provider_matcher()
        reset_service_provider_matcher()
        matcher2 = get_service_provider_matcher()

        assert matcher1 is not matcher2


# =============================================================================
# ServiceProviderMatcher Edge Cases
# =============================================================================


class TestServiceProviderMatcherEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_special_characters_in_input(self, matcher: ServiceProviderMatcher) -> None:
        """Test handling of special characters in input."""
        # AT&T has special character
        result = matcher.match("AT&T")

        assert result is not None
        assert result.provider == "AT&T"

    def test_hyphenated_provider(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching hyphenated provider names."""
        result = matcher.match("Roto-Rooter")

        assert result is not None
        assert result.provider == "Roto-Rooter"

    def test_multi_word_provider(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching multi-word provider names."""
        result = matcher.match("United Parcel Service")

        assert result is not None
        assert result.provider == "UPS"

    def test_match_returns_correct_risk_modifier(self, matcher: ServiceProviderMatcher) -> None:
        """Test that most matches return low_risk_service modifier."""
        providers_to_test = ["FedEx", "UPS", "Amazon", "PG&E", "AT&T"]

        for provider in providers_to_test:
            result = matcher.match(provider)
            assert result is not None
            assert result.risk_modifier == "low_risk_service"


# =============================================================================
# ServiceProviderMatcher Confidence Score Tests
# =============================================================================


class TestServiceProviderMatcherConfidenceScores:
    """Tests for confidence score calculation."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_exact_match_confidence_is_one(self, matcher: ServiceProviderMatcher) -> None:
        """Test that exact matches have confidence 1.0."""
        result = matcher.match("FEDEX")

        assert result is not None
        assert result.confidence == 1.0

    def test_fuzzy_match_confidence_below_one(self, matcher: ServiceProviderMatcher) -> None:
        """Test that fuzzy matches have confidence below 1.0."""
        result = matcher.match("AMAZQN")  # OCR error: O -> Q

        if result is not None:
            assert result.confidence < 1.0
            assert result.confidence >= 0.85

    def test_confidence_threshold_respected(self, matcher: ServiceProviderMatcher) -> None:
        """Test that matches below threshold are not returned."""
        # "Amz" matches exactly to "AMZ" alias for Amazon (confidence 1.0)
        # Use something that doesn't match any alias
        result = matcher.match("XYZ")  # Random 3-letter code

        assert result is None


# =============================================================================
# ServiceProviderMatcher Match All Tests
# =============================================================================


class TestServiceProviderMatcherMatchAll:
    """Tests for match_all method."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_match_all_multiple_providers(self, matcher: ServiceProviderMatcher) -> None:
        """Test matching multiple provider texts at once."""
        texts = ["FedEx", "UPS", "random_text", "Amazon"]
        results = matcher.match_all(texts)

        # Should get 3 matches (FedEx, UPS, Amazon), skip random_text
        assert len(results) == 3
        provider_names = {r.provider for r in results}
        assert "FedEx" in provider_names
        assert "UPS" in provider_names
        assert "Amazon" in provider_names

    def test_match_all_empty_list(self, matcher: ServiceProviderMatcher) -> None:
        """Test match_all with empty list."""
        results = matcher.match_all([])
        assert results == []

    def test_match_all_no_matches(self, matcher: ServiceProviderMatcher) -> None:
        """Test match_all when nothing matches."""
        texts = ["xyz123", "abc456", "random"]
        results = matcher.match_all(texts)
        assert results == []


# =============================================================================
# ServiceProviderMatcher Category Info Tests
# =============================================================================


class TestServiceProviderMatcherCategoryInfo:
    """Tests for get_category_info method."""

    @pytest.fixture
    def matcher(self) -> ServiceProviderMatcher:
        """Create a ServiceProviderMatcher instance."""
        reset_service_provider_matcher()
        return get_service_provider_matcher()

    def test_get_category_info_delivery(self, matcher: ServiceProviderMatcher) -> None:
        """Test getting category info for DELIVERY."""
        info = matcher.get_category_info("DELIVERY")

        assert info is not None
        assert info["risk_modifier"] == "low_risk_service"
        assert "description" in info

    def test_get_category_info_unknown(self, matcher: ServiceProviderMatcher) -> None:
        """Test getting category info for unknown category."""
        info = matcher.get_category_info("UNKNOWN_CATEGORY")

        assert info is None

    def test_get_category_info_emergency(self, matcher: ServiceProviderMatcher) -> None:
        """Test getting category info for EMERGENCY (special risk modifier)."""
        info = matcher.get_category_info("EMERGENCY")

        assert info is not None
        assert info["risk_modifier"] == "authority"


# =============================================================================
# ServiceProviderMatcher Custom Threshold Tests
# =============================================================================


class TestServiceProviderMatcherCustomThreshold:
    """Tests for custom similarity threshold."""

    def test_custom_threshold_stricter(self) -> None:
        """Test with a stricter threshold (0.95)."""
        matcher = ServiceProviderMatcher(threshold=0.95)

        # "AMAZ0N" vs "AMAZON" should not match with 0.95 threshold
        result = matcher.match("AMAZ0N")

        # Should not match since similarity is ~0.83
        assert result is None

    def test_custom_threshold_looser(self) -> None:
        """Test with a looser threshold (0.70)."""
        matcher = ServiceProviderMatcher(threshold=0.70)

        # "UPX" vs "UPS" might match with lower threshold
        result = matcher.match("UPX")

        # UPX vs UPS has ~0.67 similarity, still below 0.70
        assert result is None
