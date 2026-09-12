from extraction import extract_stakeholder_view

stakeholder = "Customer Service"

source_text = """
I receive a complaint from the customer. I then review the complaint and send the customer a response.
""".strip()

view = extract_stakeholder_view(
    stakeholder=stakeholder,
    source_text=source_text,
)

print(view.model_dump_json(indent=2))