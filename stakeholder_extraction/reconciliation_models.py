from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator
from stakeholder_extraction.models import ConfirmationStatus

ReconciliationProposalType = Literal[
    "equivalent_subject",
    "message_pair",
    "one_sided_message",
]

class ReconciliationProposal(BaseModel):
    """A reviewable correspondence or discrepancy between two fragments."""
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    proposal_type: ReconciliationProposalType
    left_view_id: str
    right_view_id: str
    left_element_uri: str | None = None
    right_element_uri: str | None = None
    explanation: str
    status: ConfirmationStatus = (ConfirmationStatus.PROPOSED)

    @model_validator(mode="after")
    def validate_element_references(self,) -> "ReconciliationProposal":
        """Ensure the element references match the selected proposal type."""
        if self.left_view_id == self.right_view_id:
            raise ValueError("A reconciliation proposal must compare two different views.")

        if self.proposal_type == "one_sided_message":
            has_left = self.left_element_uri is not None
            has_right = self.right_element_uri is not None

            if has_left == has_right:
                raise ValueError("A one sided message proposal must reference exactly one element.")

        elif (
            self.left_element_uri is None or self.right_element_uri is None
        ):
            raise ValueError(f"A {self.proposal_type} proposal must reference an element from both views.")

        return self

# Defining the allowed decisions after review.
ReviewDecision = Literal[
    "confirmed",
    "rejected",
]

