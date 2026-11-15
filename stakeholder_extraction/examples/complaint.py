"""Deterministic stakeholder views for complaint examples."""

from stakeholder_extraction.models import (
    CandidateActivity,
    CandidateMessage,
    CandidateState,
    CandidateStateType,
    CandidateSubject,
    CandidateTransition,
    StakeholderView,
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
                sequence_evidence=(
                    "review the complaint  and send the customer a response"
                ),
                exit_condition="Complaint review completed",
                exit_condition_evidence=(
                    "review the complaint  and send the customer a response"
                ),
            )
        ]
    )

def make_customer_complaint_view():
    source_text = "I send a complaint to Customer Service. I then receive a response."

    return StakeholderView(
        stakeholder="Customer",
        source_text=source_text,
        corrected_text=source_text,
        prepared_text=source_text,
        candidate_subjects=[
            CandidateSubject(
                name="Customer",
                evidence="I",
            ),
            CandidateSubject(
                name="Customer Service",
                evidence="Customer Service",
            ),
        ],
        candidate_messages=[
            CandidateMessage(
                name="Complaint",
                sender="Customer",
                receiver="Customer Service",
                evidence=(
                    "send a complaint to "
                    "Customer Service"
                ),
            ),
            CandidateMessage(
                name="Response",
                sender="Customer Service",
                receiver="Customer",
                evidence="receive a response",
            ),
        ],
        candidate_activities=[],
        candidate_states=[
            CandidateState(
                local_id="state-1",
                name="Send complaint",
                state_type=CandidateStateType.SEND,
                performed_by="Customer",
                message_name="Complaint",
                is_initial=True,
                evidence="I send a complaint to Customer Service",
            ),
            CandidateState(
                local_id="state-2",
                name="Receive response",
                state_type=CandidateStateType.RECEIVE,
                performed_by="Customer",
                message_name="Response",
                evidence="I then receive a response",
            ),
        ],
        candidate_transitions=[
            CandidateTransition(
                source_state_id="state-1",
                target_state_id="state-2",
                sequence_evidence="I send a complaint to Customer Service. I then receive a response.",
            ),
        ],
        open_questions=[],
    )

def make_complete_customer_complaint_view() -> StakeholderView:
    """Describe the customer's behaviour with an explicit ending."""

    view = make_customer_complaint_view()

    ending = (
        " After receiving the response, I finish handling the complaint. "
        "This ends my part of the process."
    )

    view.source_text += ending
    view.corrected_text += ending
    view.prepared_text += (
        " After receiving the response, Customer finishes handling "
        "the complaint. This ends Customer's part of the process."
    )

    view.candidate_activities.append(
        CandidateActivity(
            name="Finish complaint handling",
            performed_by="Customer",
            evidence="I finish handling the complaint.",
        )
    )

    view.candidate_states.append(
        CandidateState(
            local_id="state-3",
            name="Finish complaint handling",
            state_type=CandidateStateType.DO,
            performed_by="Customer",
            is_end=True,
            evidence=(
                "I finish handling the complaint. "
                "This ends my part of the process."
            ),
        )
    )

    view.candidate_transitions.append(
        CandidateTransition(
            source_state_id="state-2",
            target_state_id="state-3",
            sequence_evidence=(
                "After receiving the response, "
                "I finish handling the complaint."
            ),
        )
    )

    return view


def make_complete_service_complaint_view() -> StakeholderView:
    """Describe service behavior with an explicit ending."""

    view = make_complaint_view()

    ending = (
        " After sending the response, I close the complaint. "
        "This ends my part of the process."
    )

    view.source_text += ending
    view.corrected_text += ending
    view.prepared_text += (
        " After sending the response, Customer Service closes "
        "the complaint. This ends Customer Service's part "
        "of the process."
    )

    view.candidate_activities.append(
        CandidateActivity(
            name="Close complaint",
            performed_by="Customer Service",
            evidence="I close the complaint.",
        )
    )

    view.candidate_states.append(
        CandidateState(
            local_id="state-4",
            name="Close complaint",
            state_type=CandidateStateType.DO,
            performed_by="Customer Service",
            is_end=True,
            evidence="I close the complaint. This ends my part of the process.",
        )
    )

    view.candidate_transitions.append(
        CandidateTransition(
            source_state_id="state-3",
            target_state_id="state-4",
            sequence_evidence="After sending the response, I close the complaint.",
        )
    )

    return view