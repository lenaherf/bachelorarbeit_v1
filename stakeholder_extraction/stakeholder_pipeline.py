from stakeholder_extraction.extraction import extract_stakeholder_view
from stakeholder_extraction.models import StakeholderView
from stakeholder_extraction.stakeholdertext_processing import (
    prepare_stakeholder_text,
)
from stakeholder_extraction.test.test_text_preprocessing import corrected_text, prepared_text


def process_stakeholder_input(
        stakeholder: str,
        source_text: str,
) -> StakeholderView:
    corrected_text, prepared_text = prepare_stakeholder_text(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    extracted_view = extract_stakeholder_view(
        stakeholder=stakeholder,
        source_text=prepared_text,
    )

    return StakeholderView(
        stakeholder=stakeholder,
        source_text=source_text,
        corrected_text=corrected_text,
        prepared_text=prepared_text,
        candidate_subjects=extracted_view.candidate_subjects,
        candidate_messages=extracted_view.candidate_messages,
        candidate_activities=extracted_view.candidate_activities,
        open_questions=extracted_view.open_questions,
    )