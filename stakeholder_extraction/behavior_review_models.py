"""Represent administrator decisions about source behavior selection."""

from pydantic import (BaseModel, AwareDatetime,ConfigDict, Field)
from stakeholder_extraction.reconciliation_models import ReviewDecision


class BehaviorReview(BaseModel):
    """A recorded decision about using a subject's source behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    source_view_id: str = Field(min_length=1)
    source_subject_uri: str = Field(min_length=1)
    canonical_subject_uri: str = Field(min_length=1)

    decision: ReviewDecision
    reviewed_by: str = Field(min_length=1)
    reviewed_at: AwareDatetime
