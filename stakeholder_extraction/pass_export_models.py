"""Options explicitly selected for PASS RDF export."""

from pydantic import BaseModel, ConfigDict, Field


class PassExportOptions(BaseModel):
    """Define the start subject and warning policy for an export."""

    model_config = ConfigDict(extra="forbid")
    start_subject_uri: str = Field(min_length=1)
    allow_draft_with_warnings: bool = False