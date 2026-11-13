from typing import Literal
from pydantic import BaseModel, ConfigDict

class CanonicalSubject(BaseModel):
    """A confirmed subject shared across stakeholder fragments."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["FullySpecifiedSubject","InterfaceSubject",]
    source_subject_uris: tuple[str, ...]
    status: Literal["confirmed"] = "confirmed"

class CanonicalMessageSpecification(BaseModel):
    """A confirmed message identity shared across stakeholder fragments."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["MessageSpecification"] = "MessageSpecification"
    source_message_uris: tuple[str, ...]
    status: Literal["confirmed"] = "confirmed"

class CanonicalMessageExchange(BaseModel):
    """A confirmed exchange between canonical subjects."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["MessageExchange"] = "MessageExchange"
    sender_uri: str
    receiver_uri: str
    message_specification_uri: str
    source_exchange_uris: tuple[str, ...]
    status: Literal["confirmed"] = "confirmed"

class CanonicalSubjectBehavior(BaseModel):
    """A subject's behavior selected from one stakeholder fragment."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["SubjectBehavior"] = "SubjectBehavior"
    subject_uri: str

    # Identify the fragment and local subject supplying the behavior.
    source_view_id: str
    source_subject_uri: str

    status: Literal["confirmed"] = "confirmed"

class CanonicalState(BaseModel):
    """A state belonging to a canonical subject behavior."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["ReceiveState", "DoState", "SendState"]
    behavior_uri: str
    performer_uri: str
    message_specification_uri: str | None = None
    is_initial: bool = False
    is_end: bool = False
    source_state_uri: str
    status: Literal["confirmed"] = "confirmed"

class CanonicalTransition(BaseModel):
    """A transition connecting states within a canonical behavior."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["ReceiveTransition", "DoTransition", "SendTransition"]
    behavior_uri: str
    source_state_uri: str
    target_state_uri: str
    message_exchange_uri: str | None = None
    source_transition_uri: str
    status: Literal["confirmed"] = "confirmed"

class CanonicalBehaviorFragment(BaseModel):
    """A canonical behavior together with its states and transitions."""

    model_config = ConfigDict(extra="forbid")
    behavior: CanonicalSubjectBehavior
    states: list[CanonicalState]
    transitions: list[CanonicalTransition]

class CanonicalProcessModel(BaseModel):
    """Identify the canonical elements selected for one process model."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    model_component_id: str
    label: str
    pass_type: Literal["PASSProcessModel"] = "PASSProcessModel"

    subject_uris: tuple[str, ...]
    behavior_uris: tuple[str, ...]
    message_specification_uris: tuple[str, ...]
    message_exchange_uris: tuple[str, ...]

class CanonicalProcessContents(BaseModel):
    """A process selection together with its resolved canonical elements."""

    model_config = ConfigDict(extra="forbid")

    model: CanonicalProcessModel
    subjects: list[CanonicalSubject]
    behavior_fragments: list[CanonicalBehaviorFragment]
    messages: list[CanonicalMessageSpecification]
    exchanges: list[CanonicalMessageExchange]