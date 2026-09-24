import pytest
from stakeholder_extraction.models import (
    CandidateMessage,
    CandidateSubject,
    CandidateActivity,
    StakeholderView, CandidateState, CandidateTransition, CandidateStateType,
)
from stakeholder_extraction.neo4j_repository import (
    get_stakeholder_view,
    save_stakeholder_view,
)

@pytest.mark.integration
def test_neo4j_roundtrip():
    original_view = StakeholderView(
        stakeholder="Customer Service",
        source_text="I receive and check a complaint.",
        corrected_text="I receive and check a complaint.",
        prepared_text=(
            "Customer Service receives a complaint. "
            "Customer Service checks the complaint."
        ),
        candidate_subjects=[
            CandidateSubject(
                name="Customer",
                evidence="complaint",
            ),
            CandidateSubject(
                name="Customer Service",
                evidence="I",
            ),
        ],
        candidate_messages=[
            CandidateMessage(
                name="Complaint",
                sender="Customer",
                receiver="Customer Service",
                evidence="receive and check a complaint",
            ),
        ],
        candidate_activities=[
            CandidateActivity(
                name="Check complaint",
                performed_by="Customer Service",
                evidence="check a complaint",
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
                evidence="receive a complaint",
            ),
            CandidateState(
                local_id="state-2",
                name="Check complaint",
                state_type=CandidateStateType.DO,
                performed_by="Customer Service",
                evidence="check a complaint",
            ),
        ],
        candidate_transitions=[
            CandidateTransition(
                source_state_id="state-1",
                target_state_id="state-2",
                sequence_evidence="receive and check a complaint"
            ),
        ],
    )

    view_id = save_stakeholder_view(original_view)
    loaded_view = get_stakeholder_view(view_id)

    assert loaded_view == original_view

@pytest.mark.integration
def test_rejects_ambiguous_subject_reference():
    ambiguous_view = StakeholderView(
        stakeholder="Customer Service",
        source_text="A customer sends a complaint.",
        corrected_text=(
            "A customer sends a complaint."
        ),
        prepared_text=(
            "A customer sends a complaint."
        ),
        candidate_subjects=[
            CandidateSubject(
                name="Customer",
                evidence="customer",
            ),
            CandidateSubject(
                name="Customer",
                evidence="customer",
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
                    "customer sends a complaint"
                ),
            ),
        ],
        candidate_activities=[],
        candidate_states=[],
        candidate_transitions=[],
        open_questions=[],
    )

    with pytest.raises(ValueError, match="matches multiple candidate_subjects",): save_stakeholder_view(ambiguous_view)