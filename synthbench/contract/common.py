"""Shared contract types (spec §2): the base model, labels, boxes, times, bands and hashes."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict

Label = Literal["incident", "benign", "ambiguous"]
FactStatus = Literal["declared", "verified", "audited"]
Tier = Literal["A", "B"]
ScenarioGroup = Literal["benign", "hard_negative", "suspicious", "threat", "ambiguous"]

# Corpus versions and batch names: lowercase letters, digits and hyphens.
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ContractModel(BaseModel):
    """Base of every contract model: unknown keys are errors and instances are immutable.

    JSON keys are the aliases (`class`); Python code uses the field names (`cls`).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )

    def updated(self, **changes: Any) -> Self:
        """A validated copy with changes applied; model_copy(update=...) skips validators.

        Changes use field names, never an aliased field such as `cls`.
        """
        return self.model_validate({**self.model_dump(), **changes})


def _check_box(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = value
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError(f"box must be normalized [x0, y0, x1, y1], x0 < x1, y0 < y1: {value}")
    return value


def _check_hhmm(value: str) -> str:
    if not _HHMM.fullmatch(value):
        raise ValueError(f"time must be HH:MM between 00:00 and 23:59: {value!r}")
    return value


def _check_band(value: tuple[int, int]) -> tuple[int, int]:
    low, high = value
    if not 0 <= low <= high <= 100:
        raise ValueError(f"risk_band must be [low, high], 0 <= low <= high <= 100: {value}")
    return value


def _check_sha256(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"expected 64 lowercase hex characters: {value!r}")
    return value


Box = Annotated[tuple[float, float, float, float], AfterValidator(_check_box)]
HHMM = Annotated[str, AfterValidator(_check_hhmm)]
RiskBand = Annotated[tuple[int, int], AfterValidator(_check_band)]
Sha256 = Annotated[str, AfterValidator(_check_sha256)]
