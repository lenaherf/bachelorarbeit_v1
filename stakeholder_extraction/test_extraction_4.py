from extraction import extract_stakeholder_view

stakeholder = "Customer"

source_text = """
After filling out the form, I'll send it to customer service. Later, I'll receive a confirmation of receipt.
""".strip()

view = extract_stakeholder_view(
    stakeholder=stakeholder,
    source_text=source_text,
)

print(view.model_dump_json(indent=2))