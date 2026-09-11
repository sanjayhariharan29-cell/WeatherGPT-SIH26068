"""Structured Missing Information and Clarification Models for SkyZen.

Defines deterministic missing-information classifications and clarification payloads
to ensure SkyZen never guesses safety-critical information.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MissingInformationType(str, Enum):
    """Classifies the exact category of missing context required for safe decision making."""
    MISSING_LOCATION = "missing_location"
    MISSING_DATE = "missing_date"
    MISSING_TIME = "missing_time"
    MISSING_ACTIVITY = "missing_activity"
    MISSING_DESTINATION = "missing_destination"
    AMBIGUOUS_LOCATION = "ambiguous_location"
    INSUFFICIENT_MARINE_AREA = "insufficient_marine_area"
    INSUFFICIENT_SAFETY_CONTEXT = "insufficient_safety_context"


class MissingInformation(BaseModel):
    """Structured representation of missing context and its natural clarification prompt."""
    missing_type: MissingInformationType = Field(
        ...,
        description="Categorical type of missing information"
    )
    field: str = Field(
        ...,
        description="Specific field missing (e.g. location, date, time, destination, marine_area)"
    )
    severity: str = Field(
        default="safety_critical",
        description="'safety_critical' or 'standard'"
    )
    reason: str = Field(
        ...,
        description="Technical rationale why decision cannot be made safely"
    )
    prompt: str = Field(
        ...,
        description="Natural, concise, language-appropriate clarification question"
    )
    options: List[str] = Field(
        default_factory=list,
        description="Optional suggestions or candidates (e.g. for ambiguous locations)"
    )
    intent_to_resume: Optional[str] = Field(
        default=None,
        description="Original domain intent to resume once user provides clarification"
    )
    original_query: Optional[str] = Field(
        default=None,
        description="The original user query needing the missing context"
    )
    context_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of active dimensions captured at time of clarification"
    )
