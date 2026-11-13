from types import SimpleNamespace

import pytest

from stakeholder_extraction import complaint_demo
from stakeholder_extraction.examples.complaint import (
    make_complete_customer_complaint_view,
    make_complete_service_complaint_view,
)
from stakeholder_extraction.models import CandidateMessage
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment


@pytest.mark.parametrize("source_side", ["customer", "service"])
def test_cli_reviews_one_sided_message(
    monkeypatch,
    capsys,
    source_side,
):
    customer_view = make_complete_customer_complaint_view()
    service_view = make_complete_service_complaint_view()

    source_view = (
        customer_view
        if source_side == "customer"
        else service_view
    )

    source_view.candidate_messages.append(
        CandidateMessage(
            name="Acknowledgement",
            sender="Customer Service",
            receiver="Customer",
            evidence="Customer Service sends an acknowledgement.",
        )
    )

    fragments = [
        map_view_to_pass_fragment(
            customer_view,
            view_id="cli-customer",
        ),
        map_view_to_pass_fragment(
            service_view,
            view_id="cli-service",
        ),
    ]

    saved_decisions = []
    one_sided_calls = []

    # Keep the real comparison logic, but replace database operations.
    monkeypatch.setattr(
        complaint_demo,
        "save_reconciliation_proposals",
        lambda proposals: None,
    )
    monkeypatch.setattr(
        complaint_demo,
        "ask_decision",
        lambda prompt: "confirmed",
    )
    monkeypatch.setattr(
        complaint_demo,
        "review_reconciliation_proposal",
        lambda **kwargs: saved_decisions.append(kwargs),
    )
    monkeypatch.setattr(
        complaint_demo,
        "canonicalize_confirmed_subject_proposal",
        lambda proposal_id: object(),
    )
    monkeypatch.setattr(
        complaint_demo,
        "canonicalize_confirmed_message_pair_proposal",
        lambda proposal_id: (object(), object()),
    )

    def canonicalize_one_sided(proposal_id):
        one_sided_calls.append(proposal_id)

        return (
            SimpleNamespace(label="Acknowledgement"),
            SimpleNamespace(label="Acknowledgement exchange"),
        )

    monkeypatch.setattr(
        complaint_demo,
        "canonicalize_confirmed_one_sided_message",
        canonicalize_one_sided,
    )

    subjects, messages, exchanges = (
        complaint_demo.reconcile_demo_fragments(
            fragments,
            reviewed_by="test-reviewer",
        )
    )

    assert len(subjects) == 2
    assert len(messages) == 3
    assert len(exchanges) == 3
    assert len(one_sided_calls) == 1
    assert len(saved_decisions) == 5

    assert all(
        decision["decision"] == "confirmed"
        for decision in saved_decisions
    )

    output = capsys.readouterr().out

    assert "No matching message mentioned in this view." in output
    assert "Only one view supplies evidence" in output