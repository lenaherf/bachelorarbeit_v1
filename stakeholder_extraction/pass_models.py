from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from stakeholder_extraction.models import ConfirmationStatus

class PassElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str

    view_id: str
    stakeholder: str
    evidence: str
    status: ConfirmationStatus

    source_kind: Literal[
        "subject",
        "message",
        "activity",
        "state",
        "transition",
    ]
    source_index: int

class PassSubject(PassElement):
    pass_type: Literal[
        "FullySpecifiedSubject",
        "InterfaceSubject",
    ]

class PassMessageSpecification(PassElement):
    pass_type: Literal["MessageSpecification"] = "MessageSpecification"

class PassMessageExchange(PassElement):
    pass_type: Literal["MessageExchange"] = "MessageExchange"
    sender_uri: str
    receiver_uri: str
    message_specification_uri: str

class PassState(PassElement):
    pass_type: Literal["ReceiveState", "DoState", "SendState",]

    local_id: str
    performer_uri: str | None = None
    message_specification_uri: str | None = None
    is_initial: bool = False
    is_end: bool = False

class PassTransition(PassElement):
    pass_type: Literal["ReceiveTransition", "DoTransition", "SendTransition"]

    source_state_uri: str
    target_state_uri: str
    message_exchange_uri: str | None = None

class MappingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    source_kind: Literal["message", "activity", "state", "transition"]
    source_index: int
    field: str
    detail: str

class PassModelFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_id: str
    stakeholder: str
    base_uri: str
    subjects: list[PassSubject]
    message_specifications: list[PassMessageSpecification]
    message_exchanges: list[PassMessageExchange]
    states: list[PassState] = Field(default_factory=list)
    transitions: list[PassTransition] = Field(default_factory=list)
    mapping_issues: list[MappingIssue]