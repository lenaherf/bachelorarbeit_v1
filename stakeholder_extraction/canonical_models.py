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