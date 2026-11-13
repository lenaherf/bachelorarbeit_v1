import pytest

from stakeholder_extraction.examples.complaint import make_customer_complaint_view
from stakeholder_extraction.models import StakeholderView, CandidateTransition, CandidateStateType, CandidateState, \
    CandidateMessage, CandidateSubject
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view


def test_proposes_equivalent_subject_names():
    left = map_view_to_pass_fragment(make_complaint_view(), view_id="left-view")
    right = map_view_to_pass_fragment(make_complaint_view(), view_id="right-view")
    proposals = compare_pass_fragments(left, right)

    assert len(proposals) == 2
    assert all(proposal.proposal_type == "equivalent_subject" for proposal in proposals)

    paired_uris = {(proposal.left_element_uri, proposal.right_element_uri) for proposal in proposals}

    assert paired_uris == {
        (
            "urn:pass:view:left-view:subject:000",
            "urn:pass:view:right-view:subject:000",
        ),
        (
            "urn:pass:view:left-view:subject:001",
            "urn:pass:view:right-view:subject:001",
        ),
    }

def test_subject_comparison_is_deterministic():
    left = map_view_to_pass_fragment(make_complaint_view(), view_id="left-view")
    right = map_view_to_pass_fragment(make_complaint_view(), view_id="right-view")

    first = compare_pass_fragments(left, right)
    second = compare_pass_fragments(left, right)

    assert first == second

def test_rejects_comparison_with_same_view_id():
    left = map_view_to_pass_fragment(
        make_complaint_view(),
        view_id="same-view",
    )

    right = map_view_to_pass_fragment(
        make_complaint_view(),
        view_id="same-view",
    )

    with pytest.raises(
        ValueError,
        match="Cannot compare a fragment with itself",
    ):
        compare_pass_fragments(left, right)

def test_pairs_send_receive_messages():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    proposals = compare_pass_fragments(customer_fragment, service_fragment)
    message_pairs = [proposal for proposal in proposals
                     if proposal.proposal_type == "message_pair"]

    assert len(message_pairs) == 2

    paired_uris = {
        (
            proposal.left_element_uri,
            proposal.right_element_uri,
        )
        for proposal in message_pairs
    }

    assert paired_uris == {
        (
            "urn:pass:view:customer-view:exchange:000",
            "urn:pass:view:service-view:exchange:000",
        ),
        (
            "urn:pass:view:customer-view:exchange:001",
            "urn:pass:view:service-view:exchange:001",
        ),
    }

def test_proposes_message_mentioned_by_one_side():
    customer_view = make_customer_complaint_view()
    service_view = make_complaint_view()

    service_view.candidate_messages.append(
        CandidateMessage(
            name="Acknowledgement",
            sender="Customer Service",
            receiver="Customer",
            evidence="send the customer an acknowledgement",
        )
    )

    customer_fragment = map_view_to_pass_fragment(customer_view, view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(service_view, view_id="service-view")
    proposals = compare_pass_fragments(customer_fragment, service_fragment)
    one_sided = [proposal for proposal in proposals if proposal.proposal_type == "one_sided_message"]
    assert len(one_sided) == 1
    proposal = one_sided[0]
    assert proposal.left_element_uri is None
    assert proposal.right_element_uri == "urn:pass:view:service-view:exchange:002"
    assert proposal.status.value == "proposed"