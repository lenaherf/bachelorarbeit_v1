"""Manually prepare and extract a description, then save its view and fragment.

Requires OpenAI and Neo4j credentials. Makes paid API calls and creates database records.
"""

from stakeholder_extraction.neo4j_repository import save_stakeholder_view
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment

def main() -> None:
    # The pipeline initializes its API client, so load it only when running.
    from stakeholder_extraction.stakeholder_pipeline import process_stakeholder_input

    stakeholder = "Customer Service"
    source_text = (
        "I receive a complaint from the customer. "
        "I then review the complaint and send the customer a response."
    )

    view = process_stakeholder_input(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    # Save extracted candidate view.
    view_id = save_stakeholder_view(view)

    # Convert the extracted view into formal PASS elements.
    fragment = map_view_to_pass_fragment(view, view_id=view_id)

    # Save formal fragment.
    saved_fragment_id = save_pass_model_fragment(fragment)

    print(f"Stakeholderview saved with id: {view_id}")
    print(f"Pass fragment saved with id: {saved_fragment_id}")
    print(f"Formal subjects: {len(fragment.subjects)}")
    print(f"Formal messages: {len(fragment.message_specifications)}")
    print(f"Formal states: {len(fragment.states)}")
    print(f"Formal transitions: {len(fragment.transitions)}")
    print(f"Mapping issues: {len(fragment.mapping_issues)}")
    print(view.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
