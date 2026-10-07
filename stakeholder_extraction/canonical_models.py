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
