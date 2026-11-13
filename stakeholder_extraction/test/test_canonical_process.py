import pytest

from stakeholder_extraction.canonical_process import create_canonical_process_model


def _model_arguments():
    """Return a small process membership example."""

    return {
        "model_id": "complaint-demo-001",
        "label": "Complaint handling",
        "subject_uris": [
            "urn:pass:canonical:subject:service",
            "urn:pass:canonical:subject:customer",
        ],
        "behavior_uris": [
            "urn:pass:canonical:behavior:service",
            "urn:pass:canonical:behavior:customer",
        ],
        "message_specification_uris": [
            "urn:pass:canonical:message:complaint",
            "urn:pass:canonical:message:response",
        ],
        "message_exchange_uris": [
            "urn:pass:canonical:exchange:complaint",
            "urn:pass:canonical:exchange:response",
        ],
    }

def test_creates_canonical_process_model():
    model = create_canonical_process_model(**_model_arguments())

    assert model.pass_type == "PASSProcessModel"
    assert model.uri == "urn:pass:canonical:process:complaint-demo-001"
    assert model.label == "Complaint handling"
    assert len(model.subject_uris) == 2
    assert len(model.behavior_uris) == 2

def test_process_membership_is_order_independent():
    arguments = _model_arguments()
    first = create_canonical_process_model(**arguments)

    for field in (
        "subject_uris",
        "behavior_uris",
        "message_specification_uris",
        "message_exchange_uris",
    ):
        arguments[field] = list(reversed(arguments[field]))

    second = create_canonical_process_model(**arguments)

    assert first == second

def test_rejects_duplicate_process_members():
    arguments = _model_arguments()
    arguments["subject_uris"].append(arguments["subject_uris"][0])

    with pytest.raises(ValueError, match="must be unique"):
        create_canonical_process_model(**arguments)

def test_requires_process_subject():
    arguments = _model_arguments()
    arguments["subject_uris"] = []

    with pytest.raises(ValueError, match="must not be empty"):
        create_canonical_process_model(**arguments)