from stakeholder_extraction.stakeholder_pipeline import process_stakeholder_input

stakeholder = "Customer Service"

source_text = """
I receive a complaint from the customer. I then review the complaint and send the customer a response.
""".strip()

view = process_stakeholder_input(
    stakeholder=stakeholder,
    source_text=source_text,
)

print(view.model_dump_json(indent=2))