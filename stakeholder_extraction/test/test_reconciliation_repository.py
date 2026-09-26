import os
from uuid import uuid4
import pytest
from neo4j import GraphDatabase

from stakeholder_extraction.models import CandidateMessage
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_repository import save_reconciliation_proposals
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view
from stakeholder_extraction.test.test_reconciliation import make_customer_complaint_view


@pytest.mark.integration
def test_saves_reconciliation_proposals():
    test_id = str(uuid4())
    customer_view_id = f"customer-{test_id}"
    service_view_id = f"service-{test_id}"
    customer_view = make_customer_complaint_view()
    service_view = make_complaint_view()

    service_view.candidate_messages.append(
        CandidateMessage(
            name="Acknowledgement",
            sender="Customer Service",
            receiver="Customer",
            evidence=(
                "send the customer an acknowledgement"
            ),
        )
    )

    customer_fragment = map_view_to_pass_fragment(
        customer_view,
        view_id=customer_view_id,
    )

    service_fragment = map_view_to_pass_fragment(
        service_view,
        view_id=service_view_id,
    )

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    assert len(proposals) == 5

    saved_ids = save_reconciliation_proposals(proposals)

    assert saved_ids == [proposal.proposal_id for proposal in proposals]

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (
                    proposal:ReconciliationProposal
                )
                WHERE proposal.left_view_id
                    = $customer_view_id
                  AND proposal.right_view_id
                    = $service_view_id
                OPTIONAL MATCH
                    (proposal)-[
                        element_relationship:
                        LEFT_ELEMENT|RIGHT_ELEMENT
                    ]->(:PassElement)
                RETURN
                    count(DISTINCT proposal)
                        AS proposal_count,
                    count(element_relationship)
                        AS element_relationship_count,
                    collect(DISTINCT proposal.status)
                        AS statuses
                """,
                customer_view_id=customer_view_id,
                service_view_id=service_view_id,
            ).single()

            assert record is not None
            assert record["proposal_count"] == 5
            assert record["element_relationship_count"] == 9
            assert record["statuses"] == ["proposed"]

    finally:
        driver.close()
