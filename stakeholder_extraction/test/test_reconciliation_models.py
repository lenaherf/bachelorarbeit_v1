import pytest
from pydantic import ValidationError
from stakeholder_extraction.models import CandidateMessage
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_models import ReconciliationProposal
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view
from stakeholder_extraction.test.test_reconciliation import make_customer_complaint_view


def test_creates_equivalent_subject_proposal():
    proposal = ReconciliationProposal(
        proposal_id="proposal-001",
        proposal_type="equivalent_subject",
        left_view_id="customer-view",
        right_view_id="service-view",
        left_element_uri="urn:pass:view:customer-view:subject:000",
        right_element_uri="urn:pass:view:service-view:subject:001",
        explanation="Both subjects have the normalized name 'customer'.",
    )

    assert proposal.proposal_type == "equivalent_subject"
    assert proposal.status.value == "proposed"
    assert proposal.left_element_uri is not None
    assert proposal.right_element_uri is not None

def test_creates_one_sided_message_proposal():
    proposal = ReconciliationProposal(
        proposal_id="proposal-002",
        proposal_type="one_sided_message",
        left_view_id="customer-view",
        right_view_id="service-view",
        left_element_uri=(
            "urn:pass:view:customer-view:exchange:000"
        ),
        right_element_uri=None,
        explanation=(
            "The message occurs only in the customer "
            "fragment."
        ),
    )

    assert proposal.left_element_uri is not None
    assert proposal.right_element_uri is None

def test_rejects_incomplete_equivalent_proposal():
    with pytest.raises(ValidationError, match="must reference an element from both views."):
        ReconciliationProposal(
            proposal_id="proposal-003",
            proposal_type="equivalent_subject",
            left_view_id="customer-view",
            right_view_id="service-view",
            left_element_uri=(
                "urn:pass:view:customer-view:subject:000"
            ),
            right_element_uri=None,
            explanation="Missing right subject.",
        )

def test_rejects_two_sided_one_sided_message():
    with pytest.raises(ValidationError, match="must reference exactly one element."):
        ReconciliationProposal(
            proposal_id="proposal-004",
            proposal_type="one_sided_message",
            left_view_id="customer-view",
            right_view_id="service-view",
            left_element_uri=(
                "urn:pass:view:customer-view:exchange:000"
            ),
            right_element_uri=(
                "urn:pass:view:service-view:exchange:000"
            ),
            explanation="Both sides were provided.",
        )

