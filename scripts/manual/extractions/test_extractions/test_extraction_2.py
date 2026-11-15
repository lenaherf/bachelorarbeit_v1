"""Manually extract a stakeholder view using OpenAI and print the result.

Requires an API key and makes paid API calls. Does not save to Neo4j.
"""

from stakeholder_extraction.extraction import extract_stakeholder_view

def main() -> None:
    stakeholder = "Customer Service"
    source_text = (
        "After reviewing the complaint, I will notify the responsible authority."
    )

    view = extract_stakeholder_view(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    print(view.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
