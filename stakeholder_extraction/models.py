# Defining the schema for the StakeholderView

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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
    STATE = "state"
    TRANSITION = "transition"

class CandidateStateType(str, Enum):
    RECEIVE = "receive"
    DO = "do"
    SEND = "send"

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

class CandidateState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_id: str
    name: str
    state_type: CandidateStateType
    performed_by: str | None = None
    message_name: str | None = None
    is_initial: bool = False
    is_end: bool = False
    evidence: str
    status: ConfirmationStatus = ConfirmationStatus.PROPOSED

class CandidateTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_state_id: str
    target_state_id: str
    sequence_evidence: str
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
    corrected_text: str
    prepared_text: str

    candidate_subjects: list[CandidateSubject]
    candidate_messages: list[CandidateMessage]
    candidate_activities: list[CandidateActivity]
    open_questions: list[OpenQuestion]

    candidate_states: list[CandidateState] = Field(default_factory=list)
    candidate_transitions: list[CandidateTransition] = Field(default_factory=list)
