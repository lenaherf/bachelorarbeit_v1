import os
import uuid
from uuid import uuid4
import pytest
from neo4j import GraphDatabase

from stakeholder_extraction.canonical_repository import canonicalize_confirmed_subject_proposal
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_repository import save_reconciliation_proposals, \
    review_reconciliation_proposal
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view
from stakeholder_extraction.test.test_reconciliation import make_customer_complaint_view

def _create_saved_subject_reconciliation():
    """Create and persist a two fragment test scenario."""
    test_id = str(uuid4())
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id=f"customer-{test_id}")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"service-{test_id}")

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    save_reconciliation_proposals(proposals)

    customer_subject_proposal = next(
        proposal for proposal in proposals if (
                proposal.proposal_type == "equivalent_subject"
                and proposal.left_element_uri == customer_fragment.subjects[0].uri
                and proposal.right_element_uri == service_fragment.subjects[0].uri
        )
    )

    return (
        customer_fragment,
        service_fragment,
        customer_subject_proposal,
    )


@pytest.mark.integration
def test_canonicalizes_confirmed_subject_proposal():
    (customer_fragment, service_fragment, customer_subject_proposal) = _create_saved_subject_reconciliation()
    review_reconciliation_proposal(
        proposal_id=customer_subject_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    canonical = (canonicalize_confirmed_subject_proposal(customer_subject_proposal.proposal_id))
    second_canonical = (canonicalize_confirmed_subject_proposal(customer_subject_proposal.proposal_id))

    assert canonical.label == "Customer"
    assert canonical.pass_type == "FullySpecifiedSubject"
    assert canonical.status == "confirmed"

    assert second_canonical == canonical

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])
    )
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (
                    proposal:ReconciliationProposal {
                        proposal_id: $proposal_id
                    }
                )-[:CREATED_CANONICAL]->
                    (canonical:CanonicalSubject)
                OPTIONAL MATCH
                    (canonical)-[
                        provenance:DERIVED_FROM
                    ]->(source:PassSubject)
                RETURN
                    canonical.uri AS uri,
                    canonical.label AS label,
                    canonical.pass_type AS pass_type,
                    canonical.status AS status,
                    count(provenance)
                        AS provenance_count,
                    count(DISTINCT source)
                        AS source_count
                """,
                proposal_id=(
                    customer_subject_proposal.proposal_id
                ),
            ).single()

            assert record is not None
            assert record["uri"] == canonical.uri
            assert record["label"] == "Customer"
            assert record["pass_type"] == "FullySpecifiedSubject"
            assert record["status"] == "confirmed"
            assert record["provenance_count"] == 2
            assert record["source_count"] == 2

    finally:
        driver.close()

@pytest.mark.integration
def test_rejects_unconfirmed_subject_proposal():
    (_, _, customer_subject_proposal) = _create_saved_subject_reconciliation()

    with pytest.raises(ValueError, match="Only confirmed proposals",):
        canonicalize_confirmed_subject_proposal(customer_subject_proposal.proposal_id)

@pytest.mark.integration
def test_rejects_rejected_subject_proposal():
    (_, _, customer_subject_proposal) = _create_saved_subject_reconciliation()

    review_reconciliation_proposal(
        proposal_id=customer_subject_proposal.proposal_id,
        decision="rejected",
        reviewed_by="admin-test"
    )

    with pytest.raises(ValueError, match="Only confirmed proposals",):
        canonicalize_confirmed_subject_proposal(customer_subject_proposal.proposal_id)

@pytest.mark.integration
def test_reuses_canonical_subject_across_three_views():
    test_id = str(uuid.uuid4())
    first_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id=f"first-{test_id}")
    second_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"second-{test_id}")
    third_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"third-{test_id}")

    for fragment in [first_fragment, second_fragment, third_fragment]:
        save_pass_model_fragment(fragment)

    first_comparison = compare_pass_fragments(first_fragment, second_fragment)
    second_comparison = compare_pass_fragments(second_fragment, third_fragment)

    save_reconciliation_proposals(first_comparison + second_comparison)

    first_proposal = next(
        proposal for proposal in first_comparison
        if (
            proposal.proposal_type == "equivalent_subject"
            and proposal.left_element_uri == first_fragment.subjects[0].uri
            and proposal.right_element_uri == second_fragment.subjects[0].uri
        )
    )

    second_proposal = next(
        proposal for proposal in second_comparison
        if (
            proposal.proposal_type == "equivalent_subject"
            and proposal.left_element_uri == second_fragment.subjects[0].uri
            and proposal.right_element_uri == third_fragment.subjects[0].uri
        )
    )

    for proposal in [first_proposal, second_proposal]:
        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="admin-test"
        )

    first_canonical = (canonicalize_confirmed_subject_proposal(first_proposal.proposal_id))
    second_canonical = (canonicalize_confirmed_subject_proposal(second_proposal.proposal_id))

    assert second_canonical.uri == first_canonical.uri
    assert len(second_canonical.source_subject_uris) == 3