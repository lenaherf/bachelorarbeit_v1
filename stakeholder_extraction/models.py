# Defining the schema for the StakeholderView

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

class ConfirmationStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

class QuestionReason(str, Enum):
    MISSING_INFORMATION = "missing_information"
    AMBIGUOUS_INFORMATION = "ambiguous_information"

class ElementType(str, Enum):
    SUBJECT = "subject"
    MESSAGE = "message"
    ACTIVITY = "activity"

class CandidateSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    evidence: str
    status: ConfirmationStatus = ConfirmationStatus.PROPOSED

class CandidateMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    sender: str | None = None
    receiver: str | None = None
    evidence: str
    status: ConfirmationStatus = ConfirmationStatus.PROPOSED

class CandidateActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    performed_by: str | None = None
    evidence: str
    status: ConfirmationStatus = ConfirmationStatus.PROPOSED

class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    related_element_type: ElementType
    related_field: str
    reason: QuestionReason
    question: str

class StakeholderView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stakeholder: str
    source_text: str
    candidate_subjects: list[CandidateSubject]
    candidate_messages: list[CandidateMessage]
    candidate_activities: list[CandidateActivity]
    open_questions: list[OpenQuestion]