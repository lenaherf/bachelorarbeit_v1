from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from stakeholder_extraction.behavior_review_models import BehaviorReview


def _review_data():
    """Return a valid example review payload."""
    return {
        "source_view_id": "service-view",
        "source_subject_uri": (
            "urn:pass:view:service-view:subject:001"
        ),
        "canonical_subject_uri": (
            "urn:pass:canonical:subject:service"
        ),
        "decision": "confirmed",
        "reviewed_by": "admin-test",
        "reviewed_at": datetime.now(timezone.utc),
    }

@pytest.mark.parametrize("decision", ["confirmed", "rejected"])
def test_accepts_behavior_review_decision(decision):
    data = _review_data()
    data["decision"] = decision
    review = BehaviorReview(**data)

    assert review.decision == decision
    assert review.source_view_id == "service-view"
    assert review.reviewed_by == "admin-test"
    assert review.reviewed_at.tzinfo is not None

def test_rejects_blank_reviewer():
    data = _review_data()
    data["reviewed_by"] = "  "
    with pytest.raises(ValidationError):
        BehaviorReview(**data)

def test_rejects_invalid_decision():
    data = _review_data()
    data["decision"] = "proposed"
    with pytest.raises(ValidationError):
        BehaviorReview(**data)

def test_requires_timezone_for_review_timestamp():
    data = _review_data()
    data["reviewed_at"] = datetime(2026, 10, 7, 12, 0)

    with pytest.raises(ValidationError):
        BehaviorReview(**data)