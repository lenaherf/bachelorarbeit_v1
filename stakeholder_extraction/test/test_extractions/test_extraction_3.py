from extraction import extract_stakeholder_view

stakeholder = "Complaint Management"

source_text = """
I review the complaint, assess its urgency, and document the result.
""".strip()

view = extract_stakeholder_view(
    stakeholder=stakeholder,
    source_text=source_text,
)

print(view.model_dump_json(indent=2))