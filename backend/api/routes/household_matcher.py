"""API routes for Household Matcher service.

Implements NEM-4934: Expose Household Matcher Endpoints.

This module exposes the HouseholdMatcher service for person and vehicle
matching against known household members and registered vehicles.

Endpoints:
    POST /api/household-matcher/match-person    - RETIRED 410 (D-1, F11): a
        client-computed vector carries no model_id, so it cannot be compared
        in the gallery's space
    POST /api/household-matcher/match-vehicle   - Match vehicle by plate or embedding
    POST /api/household-matcher/match-batch     - Batch match multiple detections
    GET  /api/household-matcher/config          - Get matcher configuration
"""

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.household_matcher import (
    BatchMatchRequest,
    BatchMatchResponse,
    HouseholdMatchResponse,
    MatcherConfigResponse,
    PersonMatchRequest,
    VehicleMatchRequest,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.household import PersonEmbedding, RegisteredVehicle
from backend.services.household_matcher import (
    HouseholdMatch,
    HouseholdMatcher,
    get_household_matcher,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/household-matcher", tags=["household-matcher"])


def _match_to_response(
    match: HouseholdMatch | None,
) -> HouseholdMatchResponse:
    """Convert a HouseholdMatch to response schema.

    Args:
        match: HouseholdMatch instance or None

    Returns:
        HouseholdMatchResponse schema
    """
    if match is None:
        return HouseholdMatchResponse(matched=False)

    return HouseholdMatchResponse(
        matched=True,
        member_id=match.member_id,
        member_name=match.member_name,
        vehicle_id=match.vehicle_id,
        vehicle_description=match.vehicle_description,
        similarity=match.similarity,
        match_type=match.match_type,
        member_role=match.member_role,
        schedule_status=match.schedule_status,
    )


@router.post(
    "/match-person",
    response_model=HouseholdMatchResponse,
    deprecated=True,
    responses={
        status.HTTP_410_GONE: {
            "description": (
                "Always returned: POSTing a client-computed person embedding "
                "vector is retired (F11, re-ID full swap D-1). A matching "
                "request rides the enrichment pipeline, which computes the "
                "vector server-side and carries its model_id."
            )
        }
    },
)
async def match_person(
    request: PersonMatchRequest,  # noqa: ARG001 - never read: endpoint retired
    db: AsyncSession = Depends(get_db),  # noqa: ARG001 - no DB on a retired endpoint
) -> HouseholdMatchResponse:
    """Retired: POST a client-computed person embedding vector (D-1, F11).

    A vector the server did not compute cannot be trusted to live in the
    gallery's space: after the full swap every ``person_embeddings`` row
    names the weights that computed it (``model_id``), and a posted list
    of floats carries no such belt — comparing it would either score
    across embedding spaces or force trusting a client-claimed model id,
    which is no trust anchor. This is the person twin of the retired
    ``POST /face-recognition/known-persons/{id}/embeddings`` (F11 ruling 2).

    The sanctioned paths compute the vector server-side and store the
    model id beside it:

    - the enrichment pipeline (``person_reid`` leg, matched automatically)
    - ``POST /api/household/members/{member_id}/embeddings`` (member
      enrollment: extraction runs server-side from the event's detection)

    Returns:
        Never — the endpoint is retired.

    Raises:
        HTTPException: 410 Gone, always, naming the server-side paths.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Submitting a precomputed person embedding vector is retired: "
            "the server must compute every stored vector so its provenance "
            "(model_id) is known, and a client-claimed model id is no trust "
            "anchor. Person matching happens via the enrichment pipeline's "
            "person_reid leg, or enrollment via "
            "POST /api/household/members/{member_id}/embeddings."
        ),
    )


@router.post(
    "/match-vehicle",
    response_model=HouseholdMatchResponse,
    responses={
        400: {"description": "Invalid request - must provide plate or embedding"},
        500: {"description": "Internal server error"},
    },
)
async def match_vehicle(
    request: VehicleMatchRequest,
    db: AsyncSession = Depends(get_db),
) -> HouseholdMatchResponse:
    """Match a vehicle against registered vehicles.

    Matching priority:
    1. License plate match (exact, case-insensitive) - returns similarity 1.0
    2. Visual embedding match (if plate doesn't match or isn't provided)

    Args:
        request: VehicleMatchRequest with plate and/or embedding
        db: Database session

    Returns:
        HouseholdMatchResponse with match details if found

    Raises:
        HTTPException: 400 if neither plate nor embedding is provided
    """
    # Validate that at least one matching criterion is provided
    if request.license_plate is None and request.embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either license_plate or embedding for matching",
        )

    # Convert embedding to numpy array if provided
    embedding_array = None
    if request.embedding is not None:
        try:
            embedding_array = np.array(request.embedding, dtype=np.float32)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid embedding format: {e}",
            ) from e

    # Get matcher with optional custom threshold
    if request.similarity_threshold is not None:
        matcher = HouseholdMatcher(similarity_threshold=request.similarity_threshold)
    else:
        matcher = get_household_matcher()

    # Perform matching
    match = await matcher.match_vehicle(
        license_plate=request.license_plate,
        vehicle_embedding=embedding_array,
        vehicle_type=request.vehicle_type,
        color=request.color,
        session=db,
    )

    if match is None:
        logger.debug(
            "No vehicle match found (plate=%s, has_embedding=%s)",
            request.license_plate,
            request.embedding is not None,
        )
        return HouseholdMatchResponse(matched=False)

    logger.info(
        "Vehicle matched to '%s' (id=%d) via %s with similarity %.3f",
        match.vehicle_description,
        match.vehicle_id,
        match.match_type,
        match.similarity,
    )

    return _match_to_response(match)


@router.post(
    "/match-batch",
    response_model=BatchMatchResponse,
    responses={
        400: {"description": "Invalid request format"},
        500: {"description": "Internal server error"},
    },
)
async def match_batch(
    request: BatchMatchRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchMatchResponse:
    """Batch match multiple detections against household members and vehicles.

    This endpoint allows matching multiple person and vehicle detections in a
    single request, using the enrichment_data structure that contains cached
    embeddings.

    Args:
        request: BatchMatchRequest with detections and enrichment_data
        db: Database session

    Returns:
        BatchMatchResponse with person_matches and vehicle_matches dicts
    """

    # Convert detections to simple objects with id and object_type
    class SimpleDetection:
        """Simple detection class for batch matching."""

        def __init__(self, det_dict: dict) -> None:
            self.id = det_dict.get("id")
            self.object_type = det_dict.get("object_type", "")

    detections = [SimpleDetection(d) for d in request.detections]

    # Convert enrichment_data keys to int
    enrichment_data = {int(k): v for k, v in request.enrichment_data.items()}

    matcher = get_household_matcher()

    # Perform batch matching
    person_matches, vehicle_matches = await matcher.match_detections(
        detections=detections,
        enrichment_data=enrichment_data,
        session=db,
    )

    # Convert matches to response format
    person_responses = {
        str(det_id): _match_to_response(match) for det_id, match in person_matches.items()
    }
    vehicle_responses = {
        str(det_id): _match_to_response(match) for det_id, match in vehicle_matches.items()
    }

    total_matches = len(person_matches) + len(vehicle_matches)

    logger.info(
        "Batch matched %d detections: %d person matches, %d vehicle matches",
        len(detections),
        len(person_matches),
        len(vehicle_matches),
    )

    return BatchMatchResponse(
        person_matches=person_responses,
        vehicle_matches=vehicle_responses,
        total_detections=len(detections),
        total_matches=total_matches,
    )


@router.get(
    "/config",
    response_model=MatcherConfigResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_matcher_config(
    db: AsyncSession = Depends(get_db),
) -> MatcherConfigResponse:
    """Get the current household matcher configuration.

    Returns the similarity threshold and counts of stored embeddings/vehicles.

    Args:
        db: Database session

    Returns:
        MatcherConfigResponse with configuration details
    """
    matcher = get_household_matcher()

    # Count person embeddings
    embedding_count_result = await db.execute(select(func.count()).select_from(PersonEmbedding))
    total_embeddings = embedding_count_result.scalar() or 0

    # Count registered vehicles
    vehicle_count_result = await db.execute(select(func.count()).select_from(RegisteredVehicle))
    total_vehicles = vehicle_count_result.scalar() or 0

    return MatcherConfigResponse(
        similarity_threshold=matcher.similarity_threshold,
        total_member_embeddings=total_embeddings,
        total_registered_vehicles=total_vehicles,
    )
