from types import SimpleNamespace
from stakeholder_extraction import stakeholder_pipeline
from stakeholder_extraction.models import (
    CandidateActivity,
    CandidateSubject,
    CandidateMessage,
)

def test_process_stakeholder_input(monkeypatch):

    # Mocking the prepared stakeholder text and the StakeholderView result to reduce the OpenAI API calls.
    def mock_prepare_stakeholder_text(
        stakeholder: str,
        source_text: str,
    ) -> tuple[str, str]:
        assert stakeholder == "Customer Service"
        assert source_text == "I recieved a complain."

        return (
            "I received a complaint.",
            "Customer Service receives a complaint.",
        )

    mocked_extraction_result = SimpleNamespace(
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
                evidence="receives a complaint.",
            ),
        ],
        candidate_activities=[
            CandidateActivity(
                name="Check complaint",
                performed_by="Customer Service",
                evidence="checks the complaint",
            ),
        ],
        open_questions=[],
    )

    def mock_extract_stakeholder_view(
            stakeholder: str,
            source_text: str,
    ):
        assert stakeholder == "Customer Service"
        assert source_text == "Customer Service receives a complaint."

        return mocked_extraction_result

    # Making sure to return the mocked results when the functions are called.
    monkeypatch.setattr(stakeholder_pipeline, "prepare_stakeholder_text", mock_prepare_stakeholder_text,)
    monkeypatch.setattr(stakeholder_pipeline, "extract_stakeholder_view", mock_extract_stakeholder_view,)

    # Tested function.
    result = stakeholder_pipeline.process_stakeholder_input(
        stakeholder="Customer Service",
        source_text="I recieved a complain.",
    )

    # Assertions.
    assert result.stakeholder == "Customer Service"
    assert result.source_text == "I recieved a complain."
    assert result.corrected_text == "I received a complaint."
    assert result.prepared_text == "Customer Service receives a complaint."

    assert len(result.candidate_subjects) == 2
    assert len(result.candidate_messages) == 1
    assert len(result.candidate_activities) == 1

    assert result.candidate_messages[0].name == "Complaint"
    assert result.candidate_messages[0].sender == "Customer"
    assert result.candidate_messages[0].receiver == "Customer Service"