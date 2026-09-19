import pytest
from stakeholder_extraction.models import (
    CandidateMessage,
    CandidateSubject,
    CandidateActivity,
    StakeholderView,
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
    )

    view_id = save_stakeholder_view(original_view)
    loaded_view = get_stakeholder_view(view_id)

    assert loaded_view == original_view