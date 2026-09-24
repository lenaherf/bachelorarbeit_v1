import pytest
from stakeholder_extraction.models import (
    CandidateActivity,
    CandidateMessage,
    CandidateSubject,
    StakeholderView, CandidateState, CandidateStateType, CandidateTransition,
)
from stakeholder_extraction.pass_mapper import (
    map_view_to_pass_fragment,
)

def make_complaint_view() -> StakeholderView:
    source_text = (
        "I receive a complaint from the customer. I then review the complaint "
        " and send the customer a response."
    )

    return StakeholderView(
        stakeholder="Customer Service",
        source_text=source_text,
        corrected_text=source_text,
        prepared_text=source_text,
        candidate_subjects=[
            CandidateSubject(
                name="Customer",
                evidence="the customer"
            ),
            CandidateSubject(
                name="Customer Service",
                evidence="I"
            ),
        ],
        candidate_messages=[
            CandidateMessage(
                name="Complaint",
                sender="Customer",
                receiver="Customer Service",
                evidence="receive a complaint from the customer",
            ),
            CandidateMessage(
                name="Response",
                sender="Customer Service",
                receiver="Customer",
                evidence="send the customer a response",
            ),
        ],
        candidate_activities=[
            CandidateActivity(
                name="Review complaint",
                performed_by="Customer Service",
                evidence="review the complaint",
            ),
        ],
        open_questions=[],
        candidate_states=[
            CandidateState(
                local_id="state-1",
                name="Receive complaint",
                state_type=CandidateStateType.RECEIVE,
                performed_by="Customer Service",
                message_name="Complaint",
                is_initial=True,
                evidence="I receive a complaint from the customer"
            ),
            CandidateState(
                local_id="state-2",
                name="Review complaint",
                state_type=CandidateStateType.DO,
                performed_by="Customer Service",
                evidence="I then review the complaint",
            ),
            CandidateState(
                local_id="state-3",
                name="Send response",
                state_type=CandidateStateType.SEND,
                performed_by="Customer Service",
                message_name="Response",
                evidence="send the customer a response"
            )
        ],
        candidate_transitions=[
            CandidateTransition(
                source_state_id="state-1",
                target_state_id="state-2",
                sequence_evidence="I receive a complaint from the customer. I then review the complaint"
            ),
            CandidateTransition(
                source_state_id="state-2",
                target_state_id="state-3",
                sequence_evidence="review the complaint and send the customer a response"
            )
        ]
    )

def test_maps_complaint_view():
    view = make_complaint_view()
    fragment = map_view_to_pass_fragment(view, view_id="view-001")

    assert len(fragment.subjects) == 2
    assert len(fragment.message_specifications) == 2
    assert len(fragment.message_exchanges) == 2
    assert fragment.mapping_issues == []

    customer = fragment.subjects[0]
    customer_service = fragment.subjects[1]

    assert customer.pass_type == "InterfaceSubject"
    assert customer_service.pass_type == "FullySpecifiedSubject"

    assert customer.uri == "urn:pass:view:view-001:subject:000"
    assert customer_service.uri == "urn:pass:view:view-001:subject:001"

    complaint_exchange = fragment.message_exchanges[0]

    assert complaint_exchange.sender_uri == customer.uri
    assert complaint_exchange.receiver_uri == customer_service.uri

    assert len(fragment.states) == 3
    assert len(fragment.transitions) == 2

    receive_state = fragment.states[0]
    review_state = fragment.states[1]
    send_state = fragment.states[2]

    assert receive_state.pass_type == "ReceiveState"
    assert receive_state.is_initial is True
    assert review_state.pass_type == "DoState"
    assert send_state.pass_type == "SendState"

    receive_transition = fragment.transitions[0]
    do_transition = fragment.transitions[1]

    assert receive_transition.pass_type == "ReceiveTransition"
    assert receive_transition.source_state_uri == receive_state.uri
    assert receive_transition.target_state_uri == review_state.uri
    assert receive_transition.message_exchange_uri == fragment.message_exchanges[0].uri
    assert do_transition.pass_type == "DoTransition"
    assert do_transition.source_state_uri == review_state.uri
    assert do_transition.target_state_uri == send_state.uri
    assert do_transition.message_exchange_uri is None


def test_mapping_is_deterministic():
    view = make_complaint_view()

    first = map_view_to_pass_fragment(view, view_id="view-001")

    second = map_view_to_pass_fragment(view, view_id="view-001")

    assert first == second

def test_does_not_invent_missing_messages():
    view = make_complaint_view()

    view.candidate_messages = [
        CandidateMessage(
            name=None,
            sender="Customer Service",
            receiver=None,
            evidence="I notify someone",
        )
    ]

    fragment = map_view_to_pass_fragment(view, view_id="view-002")

    assert fragment.message_specifications == []
    assert fragment.message_exchanges == []

    issue_codes = {issue.code for issue in fragment.mapping_issues}

    assert "missing_message_name" in issue_codes
    assert "missing_receiver" in issue_codes

def test_duplicate_subject_names_are_not_merged():
    view = make_complaint_view()

    view.candidate_subjects = [
        CandidateSubject(
            name="Customer",
            evidence="first customer",
        ),
        CandidateSubject(
            name="Customer",
            evidence="second customer",
        ),
        CandidateSubject(
            name="Customer Service",
            evidence="I",
        ),
    ]

    fragment = map_view_to_pass_fragment(view, view_id="view-003")

    assert len(fragment.subjects) == 3

    assert fragment.subjects[0].uri != fragment.subjects[1].uri

    assert fragment.message_exchanges == []

    assert any(
        issue.code == "ambiguous_subject" and issue.field == "sender"
        for issue in fragment.mapping_issues
    )

def test_rejects_empty_view_id():
    view = make_complaint_view()

    with pytest.raises(ValueError, match="view_id must not be empty"):
        map_view_to_pass_fragment(view, view_id="",)

def test_does_not_create_send_end_state():
    view = make_complaint_view()

    view.candidate_states[2].is_end = True
    fragment = map_view_to_pass_fragment(view, view_id="view-send-end",)
    send_state = fragment.states[2]

    assert send_state.pass_type == "SendState"
    assert send_state.is_end is False

    assert any (issue.code == "invalid_send_end_state" for issue in fragment.mapping_issues)

def test_preserves_valid_do_end_state():
    view = make_complaint_view()

    view.candidate_states[1].is_end = True

    view.candidate_transitions = view.candidate_transitions[:1]

    fragment = map_view_to_pass_fragment(view, view_id="view-do-end")

    end_state = fragment.states[1]

    assert end_state.pass_type == "DoState"
    assert end_state.is_end is True
    assert not any(issue.code == "invalid_send_end_state" for issue in fragment.mapping_issues)