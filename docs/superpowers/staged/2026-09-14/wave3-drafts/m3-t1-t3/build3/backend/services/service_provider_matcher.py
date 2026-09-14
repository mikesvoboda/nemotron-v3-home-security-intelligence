"""Service Provider Matcher for OCR text matching.

This module provides fuzzy matching of OCR-extracted text against a curated
database of known service providers (delivery companies, utilities, etc.).

The matcher uses Levenshtein distance (via rapidfuzz for performance) to handle
common OCR errors like:
- Character substitutions: "AMAZ0N" -> "Amazon" (0/O confusion)
- Space insertions: "Fed Ex" -> "FedEx"
- Partial matches: "FedEx Ground" -> "FedEx"

Features:
- Exact match detection (confidence = 1.0)
- Fuzzy match with configurable threshold (default >= 0.85)
- Category-based risk modifiers for Nemotron context
- Case-insensitive matching
- ServiceCategory enum for type-safe category handling

Reference: docs/plans/2026-02-04-scene-ocr-design.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypedDict

from rapidfuzz import fuzz

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Fuzzy matching threshold (Levenshtein ratio)
# >= 0.85 is considered a match
DEFAULT_MATCH_THRESHOLD = 0.85


# =============================================================================
# ServiceCategory Enum
# =============================================================================


class ServiceCategory(str, Enum):
    """Categories of service providers for risk assessment.

    Each category represents a type of service that is typically low-risk
    when detected near a residence (uniforms, vehicles, packages).
    """

    DELIVERY = "delivery"
    UTILITY = "utility"
    TELECOM = "telecom"
    PLUMBING = "plumbing"
    HVAC = "hvac"
    ELECTRICAL = "electrical"
    LANDSCAPING = "landscaping"
    PEST_CONTROL = "pest_control"
    MEDICAL = "medical"
    SECURITY = "security"
    FOOD_DELIVERY = "food_delivery"
    HOME_SERVICES = "home_services"
    MOVING = "moving"
    WASTE = "waste"
    EMERGENCY = "emergency"


class ProviderEntry(TypedDict):
    """Type definition for a provider entry."""

    name: str
    aliases: list[str]
    category: str


class CategoryEntry(TypedDict):
    """Type definition for a category entry."""

    risk_modifier: str
    description: str


@dataclass(slots=True, frozen=True)
class ServiceMatch:
    """Result from service provider matching.

    Attributes:
        provider: Canonical provider name (e.g., "FedEx")
        category: Service category (e.g., "DELIVERY")
        confidence: Match confidence (0-1, 1.0 = exact match)
        risk_modifier: Risk modifier for Nemotron context (e.g., "low_risk_service")
        matched_alias: The alias that matched (for debugging)
    """

    provider: str
    category: str
    confidence: float
    risk_modifier: str
    matched_alias: str = ""

    def to_dict(self) -> dict[str, str | float]:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider": self.provider,
            "category": self.category,
            "confidence": self.confidence,
            "risk_modifier": self.risk_modifier,
        }


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculate Levenshtein similarity ratio between two strings.

    Uses rapidfuzz's fuzz.ratio which provides a ratio in the range [0, 100],
    converted to [0, 1] where 1.0 means identical strings.

    rapidfuzz is significantly faster than difflib.SequenceMatcher,
    especially for large-scale matching operations.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    if not s1 or not s2:
        return 0.0
    # rapidfuzz returns 0-100, convert to 0-1
    score: float = fuzz.ratio(s1, s2) / 100.0
    return score


# =============================================================================
# Service Providers Database (embedded)
# =============================================================================
# Curated list of ~100 known service providers with aliases and categories.
# This is embedded rather than loaded from JSON for simplicity and startup speed.

SERVICE_PROVIDERS: list[ProviderEntry] = [
    # Delivery Services
    {
        "name": "FedEx",
        "aliases": [
            "FEDEX",
            "FedEx Ground",
            "FedEx Express",
            "FedEx Home Delivery",
            "FedEx Freight",
        ],
        "category": "DELIVERY",
    },
    {
        "name": "UPS",
        "aliases": ["UPS", "United Parcel Service", "UPS Ground", "UPS Express"],
        "category": "DELIVERY",
    },
    {
        "name": "Amazon",
        "aliases": [
            "AMAZON",
            "Amazon Prime",
            "AMZ",
            "Amazon Logistics",
            "Amazon Fresh",
            "Whole Foods",
        ],
        "category": "DELIVERY",
    },
    {
        "name": "USPS",
        "aliases": [
            "USPS",
            "US Postal Service",
            "United States Postal",
            "Postal Service",
            "US Mail",
        ],
        "category": "DELIVERY",
    },
    {
        "name": "DHL",
        "aliases": ["DHL", "DHL Express", "DHL eCommerce"],
        "category": "DELIVERY",
    },
    {
        "name": "OnTrac",
        "aliases": ["ONTRAC", "OnTrac", "On Trac"],
        "category": "DELIVERY",
    },
    {
        "name": "LaserShip",
        "aliases": ["LASERSHIP", "LaserShip", "Laser Ship"],
        "category": "DELIVERY",
    },
    # Utility Services
    {
        "name": "PG&E",
        "aliases": [
            "PG&E",
            "Pacific Gas",
            "Pacific Gas and Electric",
            "Pacific Gas & Electric",
        ],
        "category": "UTILITY",
    },
    {
        "name": "ComEd",
        "aliases": ["COMED", "Commonwealth Edison", "Com Ed"],
        "category": "UTILITY",
    },
    {
        "name": "Con Edison",
        "aliases": ["CON EDISON", "ConEd", "Con Ed", "Consolidated Edison"],
        "category": "UTILITY",
    },
    {
        "name": "Duke Energy",
        "aliases": ["DUKE ENERGY", "Duke Power"],
        "category": "UTILITY",
    },
    {
        "name": "Southern California Edison",
        "aliases": ["SCE", "Southern California Edison", "SoCal Edison"],
        "category": "UTILITY",
    },
    {
        "name": "National Grid",
        "aliases": ["NATIONAL GRID", "National Grid USA"],
        "category": "UTILITY",
    },
    {
        "name": "Xcel Energy",
        "aliases": ["XCEL", "Xcel Energy"],
        "category": "UTILITY",
    },
    {
        "name": "SoCalGas",
        "aliases": ["SOCALGAS", "SoCalGas", "Southern California Gas"],
        "category": "UTILITY",
    },
    # Telecom Services
    {
        "name": "AT&T",
        "aliases": ["AT&T", "ATT", "AT and T", "AT&T Fiber", "AT&T Internet"],
        "category": "TELECOM",
    },
    {
        "name": "Comcast",
        "aliases": ["COMCAST", "Xfinity", "Comcast Xfinity"],
        "category": "TELECOM",
    },
    {
        "name": "Verizon",
        "aliases": ["VERIZON", "Verizon Fios", "Verizon Wireless", "VZW"],
        "category": "TELECOM",
    },
    {
        "name": "Spectrum",
        "aliases": ["SPECTRUM", "Charter Spectrum", "Charter Communications"],
        "category": "TELECOM",
    },
    {
        "name": "Cox",
        "aliases": ["COX", "Cox Communications"],
        "category": "TELECOM",
    },
    {
        "name": "CenturyLink",
        "aliases": ["CENTURYLINK", "CenturyLink", "Century Link", "Lumen"],
        "category": "TELECOM",
    },
    {
        "name": "T-Mobile",
        "aliases": ["T-MOBILE", "TMobile", "T Mobile"],
        "category": "TELECOM",
    },
    {
        "name": "Google Fiber",
        "aliases": ["GOOGLE FIBER", "Google Fiber"],
        "category": "TELECOM",
    },
    # Plumbing Services
    {
        "name": "Roto-Rooter",
        "aliases": ["ROTO-ROOTER", "Roto Rooter", "RotoRooter"],
        "category": "PLUMBING",
    },
    {
        "name": "Mr. Rooter",
        "aliases": ["MR. ROOTER", "Mr Rooter", "Mister Rooter"],
        "category": "PLUMBING",
    },
    {
        "name": "Benjamin Franklin Plumbing",
        "aliases": [
            "BENJAMIN FRANKLIN",
            "Benjamin Franklin Plumbing",
            "Ben Franklin Plumbing",
        ],
        "category": "PLUMBING",
    },
    # Home Services
    {
        "name": "ServiceMaster",
        "aliases": ["SERVICEMASTER", "Service Master", "ServiceMaster Restore"],
        "category": "HOME_SERVICES",
    },
    {
        "name": "Stanley Steemer",
        "aliases": ["STANLEY STEEMER", "Stanley Steemer"],
        "category": "HOME_SERVICES",
    },
    {
        "name": "Merry Maids",
        "aliases": ["MERRY MAIDS", "Merry Maids"],
        "category": "HOME_SERVICES",
    },
    {
        "name": "Molly Maid",
        "aliases": ["MOLLY MAID", "Molly Maid"],
        "category": "HOME_SERVICES",
    },
    {
        "name": "Servpro",
        "aliases": ["SERVPRO", "Servpro", "Serv Pro"],
        "category": "HOME_SERVICES",
    },
    # HVAC Services
    {
        "name": "Carrier",
        "aliases": ["CARRIER", "Carrier HVAC", "Carrier Heating"],
        "category": "HVAC",
    },
    {
        "name": "Trane",
        "aliases": ["TRANE", "Trane HVAC", "Trane Technologies"],
        "category": "HVAC",
    },
    {
        "name": "Lennox",
        "aliases": ["LENNOX", "Lennox HVAC", "Lennox Industries"],
        "category": "HVAC",
    },
    {
        "name": "One Hour Heating & Air",
        "aliases": [
            "ONE HOUR",
            "One Hour Heating",
            "One Hour Air",
            "One Hour Heating & Air Conditioning",
        ],
        "category": "HVAC",
    },
    {
        "name": "Aire Serv",
        "aliases": ["AIRE SERV", "Aire Serv", "AireServ"],
        "category": "HVAC",
    },
    # Electrical Services
    {
        "name": "Mr. Electric",
        "aliases": ["MR. ELECTRIC", "Mr Electric", "Mister Electric"],
        "category": "ELECTRICAL",
    },
    {
        "name": "Mister Sparky",
        "aliases": ["MISTER SPARKY", "Mr. Sparky", "Mr Sparky"],
        "category": "ELECTRICAL",
    },
    # Landscaping Services
    {
        "name": "TruGreen",
        "aliases": ["TRUGREEN", "TruGreen", "Tru Green"],
        "category": "LANDSCAPING",
    },
    {
        "name": "Lawn Doctor",
        "aliases": ["LAWN DOCTOR", "Lawn Doctor"],
        "category": "LANDSCAPING",
    },
    {
        "name": "BrightView",
        "aliases": ["BRIGHTVIEW", "BrightView", "Bright View"],
        "category": "LANDSCAPING",
    },
    # Pest Control Services
    {
        "name": "Terminix",
        "aliases": ["TERMINIX", "Terminix"],
        "category": "PEST_CONTROL",
    },
    {
        "name": "Orkin",
        "aliases": ["ORKIN", "Orkin Pest Control", "Orkin Man"],
        "category": "PEST_CONTROL",
    },
    {
        "name": "Rentokil",
        "aliases": ["RENTOKIL", "Rentokil", "Rentokil Pest Control"],
        "category": "PEST_CONTROL",
    },
    {
        "name": "Aptive",
        "aliases": ["APTIVE", "Aptive Environmental"],
        "category": "PEST_CONTROL",
    },
    # Security Services
    {
        "name": "ADT",
        "aliases": ["ADT", "ADT Security", "ADT Home Security"],
        "category": "SECURITY",
    },
    {
        "name": "Vivint",
        "aliases": ["VIVINT", "Vivint Smart Home", "Vivint Security"],
        "category": "SECURITY",
    },
    {
        "name": "SimpliSafe",
        "aliases": ["SIMPLISAFE", "SimpliSafe", "Simpli Safe"],
        "category": "SECURITY",
    },
    {
        "name": "Brinks",
        "aliases": ["BRINKS", "Brinks Home Security", "Brinks Home"],
        "category": "SECURITY",
    },
    # Medical / Healthcare
    {
        "name": "Visiting Angels",
        "aliases": ["VISITING ANGELS", "Visiting Angels"],
        "category": "MEDICAL",
    },
    {
        "name": "Home Instead",
        "aliases": ["HOME INSTEAD", "Home Instead Senior Care"],
        "category": "MEDICAL",
    },
    {
        "name": "Comfort Keepers",
        "aliases": ["COMFORT KEEPERS", "Comfort Keepers"],
        "category": "MEDICAL",
    },
    {
        "name": "BrightStar Care",
        "aliases": ["BRIGHTSTAR", "BrightStar Care", "Bright Star Care"],
        "category": "MEDICAL",
    },
    # Food Delivery
    {
        "name": "DoorDash",
        "aliases": ["DOORDASH", "DoorDash", "Door Dash"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Uber Eats",
        "aliases": ["UBER EATS", "UberEats", "Uber Eats"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Grubhub",
        "aliases": ["GRUBHUB", "GrubHub", "Grub Hub"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Instacart",
        "aliases": ["INSTACART", "Instacart", "Insta Cart"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Shipt",
        "aliases": ["SHIPT", "Shipt"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Dominos",
        "aliases": ["DOMINOS", "Domino's", "Dominos Pizza"],
        "category": "FOOD_DELIVERY",
    },
    {
        "name": "Pizza Hut",
        "aliases": ["PIZZA HUT", "PizzaHut"],
        "category": "FOOD_DELIVERY",
    },
    # Moving Services
    {
        "name": "U-Haul",
        "aliases": ["UHAUL", "U-Haul", "U Haul"],
        "category": "MOVING",
    },
    {
        "name": "Penske",
        "aliases": ["PENSKE", "Penske Truck Rental"],
        "category": "MOVING",
    },
    {
        "name": "Budget Truck",
        "aliases": ["BUDGET", "Budget Truck Rental", "Budget Moving"],
        "category": "MOVING",
    },
    {
        "name": "Two Men and a Truck",
        "aliases": ["TWO MEN AND A TRUCK", "Two Men and a Truck", "2 Men and a Truck"],
        "category": "MOVING",
    },
    {
        "name": "PODS",
        "aliases": ["PODS", "PODS Moving", "PODS Storage"],
        "category": "MOVING",
    },
    # Waste Management
    {
        "name": "Waste Management",
        "aliases": ["WASTE MANAGEMENT", "WM", "Waste Management Inc"],
        "category": "WASTE",
    },
    {
        "name": "Republic Services",
        "aliases": ["REPUBLIC", "Republic Services"],
        "category": "WASTE",
    },
    # Emergency Services
    {
        "name": "Police",
        "aliases": ["POLICE", "Police Department", "PD", "Police Dept"],
        "category": "EMERGENCY",
    },
    {
        "name": "Fire Department",
        "aliases": ["FIRE", "Fire Department", "Fire Dept", "FD"],
        "category": "EMERGENCY",
    },
    {
        "name": "Ambulance",
        "aliases": ["AMBULANCE", "EMS", "Emergency Medical Services", "Paramedic"],
        "category": "EMERGENCY",
    },
    {
        "name": "Sheriff",
        "aliases": ["SHERIFF", "Sheriff Department", "Sheriff's Office"],
        "category": "EMERGENCY",
    },
]

# Category definitions with risk modifiers
SERVICE_CATEGORIES: dict[str, CategoryEntry] = {
    "DELIVERY": {
        "risk_modifier": "low_risk_service",
        "description": "Package and mail delivery services",
    },
    "UTILITY": {
        "risk_modifier": "low_risk_service",
        "description": "Gas, electric, and water utility services",
    },
    "TELECOM": {
        "risk_modifier": "low_risk_service",
        "description": "Internet, phone, and cable services",
    },
    "PLUMBING": {
        "risk_modifier": "low_risk_service",
        "description": "Plumbing repair and maintenance services",
    },
    "HOME_SERVICES": {
        "risk_modifier": "low_risk_service",
        "description": "General home repair and cleaning services",
    },
    "HVAC": {
        "risk_modifier": "low_risk_service",
        "description": "Heating, ventilation, and air conditioning services",
    },
    "ELECTRICAL": {
        "risk_modifier": "low_risk_service",
        "description": "Electrical repair and installation services",
    },
    "LANDSCAPING": {
        "risk_modifier": "low_risk_service",
        "description": "Lawn care and landscaping services",
    },
    "PEST_CONTROL": {
        "risk_modifier": "low_risk_service",
        "description": "Pest control and extermination services",
    },
    "SECURITY": {
        "risk_modifier": "low_risk_service",
        "description": "Home security system services",
    },
    "MEDICAL": {
        "risk_modifier": "low_risk_service",
        "description": "Home healthcare and medical services",
    },
    "FOOD_DELIVERY": {
        "risk_modifier": "low_risk_service",
        "description": "Food delivery and grocery services",
    },
    "MOVING": {
        "risk_modifier": "low_risk_service",
        "description": "Moving and truck rental services",
    },
    "WASTE": {
        "risk_modifier": "low_risk_service",
        "description": "Trash collection and waste management services",
    },
    "EMERGENCY": {
        "risk_modifier": "authority",
        "description": "Emergency services (police, fire, EMS)",
    },
}


class ServiceProviderMatcher:
    """Fuzzy matcher for service provider text recognition.

    Matches OCR-extracted text against a curated database of known
    service providers using Levenshtein distance for error tolerance.

    Attributes:
        providers: List of provider entries with aliases
        categories: Category definitions with risk modifiers
        threshold: Minimum similarity ratio for fuzzy matches (default: 0.85)

    Example:
        >>> matcher = ServiceProviderMatcher()
        >>> result = matcher.match("FedE x")  # OCR error with space
        >>> result.provider
        'FedEx'
        >>> result.confidence
        0.86
    """

    def __init__(
        self,
        providers: list[ProviderEntry] | None = None,
        categories: dict[str, CategoryEntry] | None = None,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
    ) -> None:
        """Initialize the service provider matcher.

        Args:
            providers: Custom provider list (defaults to SERVICE_PROVIDERS)
            categories: Custom category definitions (defaults to SERVICE_CATEGORIES)
            threshold: Minimum similarity ratio for fuzzy matches (default: 0.85)
        """
        self.providers = providers or SERVICE_PROVIDERS
        self.categories = categories or SERVICE_CATEGORIES
        self.threshold = threshold

        # Build lookup index for faster exact matching
        self._exact_lookup: dict[str, tuple[str, str]] = {}
        for provider in self.providers:
            for alias in provider["aliases"]:
                normalized = alias.upper().strip()
                self._exact_lookup[normalized] = (provider["name"], provider["category"])

        logger.debug(
            f"ServiceProviderMatcher initialized with {len(self.providers)} providers, "
            f"{len(self._exact_lookup)} aliases"
        )

    def match(self, ocr_text: str) -> ServiceMatch | None:
        """Match OCR text against known service providers.

        First attempts exact match (case-insensitive), then falls back
        to fuzzy matching using Levenshtein distance.

        Args:
            ocr_text: Text extracted from OCR

        Returns:
            ServiceMatch if a match is found, None otherwise
        """
        if not ocr_text or not ocr_text.strip():
            return None

        normalized = ocr_text.upper().strip()

        # Try exact match first (O(1) lookup)
        if normalized in self._exact_lookup:
            provider_name, category = self._exact_lookup[normalized]
            category_entry = self.categories.get(category)
            risk_modifier = (
                category_entry.get("risk_modifier", "low_risk_service")
                if category_entry
                else "low_risk_service"
            )
            return ServiceMatch(
                provider=provider_name,
                category=category,
                confidence=1.0,
                risk_modifier=risk_modifier,
                matched_alias=normalized,
            )

        # Fall back to fuzzy matching
        return self._fuzzy_match(normalized)

    def _fuzzy_match(self, normalized_text: str) -> ServiceMatch | None:
        """Perform fuzzy matching against all provider aliases.

        Args:
            normalized_text: Uppercase, stripped OCR text

        Returns:
            ServiceMatch if a fuzzy match is found above threshold, None otherwise
        """
        best_match: tuple[str, str, str, float] | None = None
        best_score = 0.0

        for provider in self.providers:
            for alias in provider["aliases"]:
                alias_normalized = alias.upper()
                score = levenshtein_ratio(normalized_text, alias_normalized)

                if score >= self.threshold and score > best_score:
                    best_score = score
                    best_match = (
                        provider["name"],
                        provider["category"],
                        alias,
                        score,
                    )

        if best_match is None:
            return None

        provider_name, category, matched_alias, confidence = best_match
        category_entry = self.categories.get(category)
        risk_modifier = (
            category_entry.get("risk_modifier", "low_risk_service")
            if category_entry
            else "low_risk_service"
        )

        return ServiceMatch(
            provider=provider_name,
            category=category,
            confidence=round(confidence, 4),
            risk_modifier=risk_modifier,
            matched_alias=matched_alias,
        )

    def match_all(self, ocr_texts: list[str]) -> list[ServiceMatch]:
        """Match multiple OCR texts against known service providers.

        Args:
            ocr_texts: List of texts extracted from OCR

        Returns:
            List of ServiceMatch objects for texts that matched
        """
        matches = []
        for text in ocr_texts:
            match = self.match(text)
            if match:
                matches.append(match)
        return matches

    def get_category_info(self, category: str) -> CategoryEntry | None:
        """Get category information including risk modifier.

        Args:
            category: Category name (e.g., "DELIVERY")

        Returns:
            CategoryEntry with risk_modifier and description, or None
        """
        return self.categories.get(category)


# Module-level singleton for convenience
_service_provider_matcher: ServiceProviderMatcher | None = None


def get_service_provider_matcher() -> ServiceProviderMatcher:
    """Get or create the singleton ServiceProviderMatcher instance.

    Returns:
        ServiceProviderMatcher instance
    """
    global _service_provider_matcher  # noqa: PLW0603
    if _service_provider_matcher is None:
        _service_provider_matcher = ServiceProviderMatcher()
    return _service_provider_matcher


def reset_service_provider_matcher() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_provider_matcher  # noqa: PLW0603
    _service_provider_matcher = None
