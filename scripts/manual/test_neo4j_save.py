"""Manually extract a view using OpenAI and save it to Neo4j.

Requires API and database credentials. Makes paid API calls and creates database records.
"""

from stakeholder_extraction.extraction import extract_stakeholder_view
from stakeholder_extraction.neo4j_repository import save_stakeholder_view


def main() -> None:
    view = extract_stakeholder_view(
        stakeholder="Customer Service",
        source_text=(
            "After reviewing the complaint, I will notify the responsible authority."
        ),
    )

    print("Extracted view:")
    print(view.model_dump_json(indent=2))

    view_id = save_stakeholder_view(view)

    print(f"\nSaved StakeholderView with ID: {view_id}")
    print("Repository:", save_stakeholder_view.__module__)
    print("Subjects:", len(view.candidate_subjects))
    print("Messages:", len(view.candidate_messages))
    print("Activities:", len(view.candidate_activities))
    print("Questions:", len(view.open_questions))


if __name__ == "__main__":
    main()
