"""Manually extract a customer perspective using OpenAI and print the result.

Requires an API key and makes paid API calls. Does not save to Neo4j.
"""

from stakeholder_extraction.extraction import extract_stakeholder_view

def main() -> None:
    stakeholder = "Customer"
    source_text = (
        "After filling out the form, I'll send it to customer service. "
        "Later, I'll receive a confirmation of receipt."
    )

    view = extract_stakeholder_view(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    print(view.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
