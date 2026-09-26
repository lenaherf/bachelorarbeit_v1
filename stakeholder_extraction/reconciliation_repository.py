import os
from itertools import starmap

from dotenv import load_dotenv
from neo4j import GraphDatabase, ManagedTransaction

from stakeholder_extraction.reconciliation_models import ReconciliationProposal

load_dotenv()

def _enum_value(value):
    return value.value if hasattr(value, "value") else value

def _save_proposal_transaction(
    transaction: ManagedTransaction,
    proposal: ReconciliationProposal,
) -> None:
    record = transaction.run(
        """
        MATCH (left:PassModelFragment {
            view_id: $left_view_id
        })
        MATCH (right:PassModelFragment {
            view_id: $right_view_id
        })

        MERGE (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
        SET proposal.proposal_type = $proposal_type,
            proposal.explanation = $explanation,
            proposal.status = $status,
            proposal.left_view_id = $left_view_id,
            proposal.right_view_id = $right_view_id

        MERGE (proposal)-[:LEFT_FRAGMENT]->(left)
        MERGE (proposal)-[:RIGHT_FRAGMENT]->(right)

        RETURN proposal.proposal_id AS proposal_id
        """,
        proposal_id=proposal.proposal_id,
        proposal_type=proposal.proposal_type,
        explanation=proposal.explanation,
        status=_enum_value(proposal.status),
        left_view_id=proposal.left_view_id,
        right_view_id=proposal.right_view_id,
    ).single()

    if record is None:
        raise ValueError(
            "Both referenced PASS fragments must be saved before saving reconciliation proposals."
        )

    if proposal.left_element_uri is not None:
        _connect_proposal_element(
            transaction,
            proposal_id=proposal.proposal_id,
            element_uri=proposal.left_element_uri,
            relationship_type="LEFT_ELEMENT",
        )

    if proposal.right_element_uri is not None:
        _connect_proposal_element(
            transaction,
            proposal_id=proposal.proposal_id,
            element_uri=proposal.right_element_uri,
            relationship_type="RIGHT_ELEMENT",
        )

def _connect_proposal_element(
        transaction: ManagedTransaction,
        *,
        proposal_id: str,
        element_uri: str,
        relationship_type:str,
) -> None:
    allowed_relationships = {"LEFT_ELEMENT", "RIGHT_ELEMENT"}

    if relationship_type not in allowed_relationships:
        raise ValueError(f"Unsupported relationship type {relationship_type}")

    record = transaction.run(
        f"""
            MATCH (proposal:ReconciliationProposal {{
                proposal_id: $proposal_id
            }})
            MATCH (element:PassElement {{
                uri: $element_uri
            }})
            MERGE (proposal)-[:{relationship_type}]->
                (element)
            RETURN element.uri AS element_uri
            """,
        proposal_id=proposal_id,
        element_uri=element_uri,
    ).single()

    if record is None:
        raise ValueError(f"Referenced PASS element '{element_uri}' has not been saved.")

def _save_proposals_transaction(
        transaction: ManagedTransaction,
        proposals: list[ReconciliationProposal],
    ) -> None:
    for proposal in proposals:
        _save_proposal_transaction(
            transaction,
            proposal,
        )

def save_reconciliation_proposals(
        proposals: list[ReconciliationProposal],
) -> list[str]:
    if not proposals:
        return []

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            session.execute_write(
                _save_proposals_transaction,
                proposals,
            )
    finally:
        driver.close()

    return [
        proposal.proposal_id for proposal in proposals
    ]