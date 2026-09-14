"""Pydantic schemas for Household Matcher API endpoints.

Implements NEM-4934: Expose Household Matcher Endpoints.

These schemas provide request/response models for the HouseholdMatcher service,
enabling person and vehicle matching against known household members and vehicles.
"""

from pydantic import BaseModel, ConfigDict, Field


class PersonMatchRequest(BaseModel):
    """Schema for matching a person embedding against household members.

    The embedding should be a 512-dimensional OSNet person re-identification
    embedding vector.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embedding": [0.1, 0.2, 0.3, 0.0, 0.0],  # Truncated example of 512-dim vector
                "similarity_threshold": 0.85,
            }
        }
    )

    embedding: list[float] = Field(
        ...,
        min_length=1,
        description="Person re-identification embedding vector (512-dim OSNet)",
    )
    similarity_threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional custom similarity threshold (default: 0.85)",
    )


class VehicleMatchRequest(BaseModel):
    """Schema for matching a vehicle against registered vehicles.

    Supports both license plate matching (exact) and visual embedding matching.
    License plate matching takes priority if provided.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "license_plate": "ABC123",
                "embedding": None,
                "vehicle_type": "car",
                "color": "silver",
                "similarity_threshold": 0.85,
            }
        }
    )

    license_plate: str | None = Field(
        None,
        max_length=20,
        description="License plate text for exact matching (case-insensitive)",
    )
    embedding: list[float] | None = Field(
        None,
        description="Vehicle visual embedding vector (768-dim CLIP) for visual matching",
    )
    vehicle_type: str = Field(
        ...,
        description="Type of vehicle (car, truck, motorcycle, van, etc.)",
    )
    color: str | None = Field(
        None,
        max_length=50,
        description="Vehicle color for context (not used in matching currently)",
    )
    similarity_threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional custom similarity threshold for visual matching (default: 0.85)",
    )


class HouseholdMatchResponse(BaseModel):
    """Schema for household match result.

    Returned when a person or vehicle matches a known household member or vehicle.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matched": True,
                "member_id": 1,
                "member_name": "John Doe",
                "vehicle_id": None,
                "vehicle_description": None,
                "similarity": 0.92,
                "match_type": "person",
                "member_role": "resident",
                "schedule_status": True,
            }
        }
    )

    matched: bool = Field(..., description="Whether a match was found")
    member_id: int | None = Field(
        None, description="ID of the matched household member (for person matches)"
    )
    member_name: str | None = Field(None, description="Name of the matched household member")
    vehicle_id: int | None = Field(None, description="ID of the matched registered vehicle")
    vehicle_description: str | None = Field(None, description="Description of the matched vehicle")
    similarity: float = Field(
        0.0, ge=0.0, le=1.0, description="Similarity score (1.0 for exact plate match)"
    )
    match_type: str = Field(
        "",
        description="Type of match: 'person', 'license_plate', or 'vehicle_visual'",
    )
    member_role: str | None = Field(
        None,
        description="Role of the matched member (resident, family, service_worker, etc.)",
    )
    schedule_status: bool | None = Field(
        None,
        description="Whether member is within expected schedule (True/False/None if no schedule)",
    )


class BatchMatchRequest(BaseModel):
    """Schema for batch matching multiple detections.

    Allows matching multiple person and vehicle detections in a single request,
    using the enrichment_data structure that contains cached embeddings.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detections": [
                    {
                        "id": 1,
                        "object_type": "person",
                    },
                    {
                        "id": 2,
                        "object_type": "car",
                    },
                ],
                "enrichment_data": {
                    "1": {
                        "embeddings": {"person_reid": [0.1, 0.2, 0.3]},
                    },
                    "2": {
                        "embeddings": {"vehicle_visual": [0.4, 0.5, 0.6]},
                        "license_plates": [{"text": "ABC123"}],
                    },
                },
            }
        }
    )

    detections: list[dict] = Field(
        ...,
        min_length=1,
        description="List of detection objects with id and object_type",
    )
    enrichment_data: dict[str, dict] = Field(
        ...,
        description="Dict mapping detection_id to enrichment data containing embeddings",
    )


class BatchMatchResponse(BaseModel):
    """Schema for batch match results.

    Returns separate dictionaries for person and vehicle matches,
    keyed by detection ID.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "person_matches": {
                    "1": {
                        "matched": True,
                        "member_id": 1,
                        "member_name": "John Doe",
                        "similarity": 0.92,
                        "match_type": "person",
                    }
                },
                "vehicle_matches": {
                    "2": {
                        "matched": True,
                        "vehicle_id": 5,
                        "vehicle_description": "Silver Tesla Model 3",
                        "similarity": 1.0,
                        "match_type": "license_plate",
                    }
                },
                "total_detections": 2,
                "total_matches": 2,
            }
        }
    )

    person_matches: dict[str, HouseholdMatchResponse] = Field(
        default_factory=dict,
        description="Dict mapping detection_id to person match result",
    )
    vehicle_matches: dict[str, HouseholdMatchResponse] = Field(
        default_factory=dict,
        description="Dict mapping detection_id to vehicle match result",
    )
    total_detections: int = Field(..., description="Total number of detections processed")
    total_matches: int = Field(..., description="Total number of matches found")


class MatcherConfigResponse(BaseModel):
    """Schema for household matcher configuration response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "similarity_threshold": 0.85,
                "total_member_embeddings": 5,
                "total_registered_vehicles": 3,
            }
        }
    )

    similarity_threshold: float = Field(
        ..., description="Current similarity threshold for matching"
    )
    total_member_embeddings: int = Field(
        ..., description="Total number of person embeddings in database"
    )
    total_registered_vehicles: int = Field(..., description="Total number of registered vehicles")
