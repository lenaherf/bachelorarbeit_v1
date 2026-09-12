from extraction import extract_stakeholder_view

stakeholder = "Customer Service"

source_text = """
After reviewing the complaint, I will notify the responsible authority.
""".strip()

view = extract_stakeholder_view(
    stakeholder=stakeholder,
    source_text=source_text,
)

print(view.model_dump_json(indent=2))