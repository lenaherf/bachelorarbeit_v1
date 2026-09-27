import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, ManagedTransaction, Transaction

from stakeholder_extraction.canonical_models import CanonicalSubject
from stakeholder_extraction.canonicalization import create_canonical_subject, extend_canonical_subject
from stakeholder_extraction.pass_models import PassSubject

load_dotenv()

def _canonicalize_subject_transaction(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> CanonicalSubject:
    """Canonicalize one confirmed equivalent subject proposal."""

    left, right = _load_confirmed_subjects(transaction, proposal_id)

    existing = _find_existing_canonical_subject(transaction, left_uri=left.uri, right_uri=right.uri)

    if existing is None:
        canonical = create_canonical_subject(left, right)
    else:
        canonical = extend_canonical_subject(existing, left, right)

    _save_canonical_subject(transaction, proposal_id=proposal_id, canonical=canonical, left=left, right=right)

    return canonical

def canonicalize_confirmed_subject_proposal(
        proposal_id: str,
) -> CanonicalSubject:
    """Canonicalize one confirmed subject proposal in Neo4j."""
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            return session.execute_write(_canonicalize_subject_transaction,proposal_id,)
    finally:
        driver.close()

def _load_confirmed_subjects(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[PassSubject, PassSubject]:
    """Load the two subjects from a confirmed equivalent subject proposal."""
    record = transaction.run(
        """
        MATCH (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
    
        OPTIONAL MATCH
            (proposal)-[:LEFT_ELEMENT]->
                (left:PassSubject)
    
        OPTIONAL MATCH
            (proposal)-[:RIGHT_ELEMENT]->
                (right:PassSubject)
    
        RETURN
            proposal.proposal_type AS proposal_type,
            proposal.status AS status,
            left,
            right
        """,
        proposal_id=proposal_id,
    ).single()

    if record is None:
        raise ValueError(f"No reconciliation found for proposal {proposal_id}.")
    if record["proposal_type"] != "equivalent_subject":
        raise ValueError("Only equivalent subject proposals can create canonical subjects.")
    if record["status"] != "confirmed":
        raise ValueError("Only confirmed proposals can create canonical subjects.")
    if record["left"] is None or record["right"] is None:
        raise ValueError("The proposal does not reference two saved PASS subjects.")

    left = PassSubject.model_validate(dict(record["left"]))
    right = PassSubject.model_validate(dict(record["right"]))

    return left, right

def _find_existing_canonical_subject(
        transaction: ManagedTransaction,
        *,
        left_uri: str,
        right_uri: str,
) -> CanonicalSubject | None:
    """Find the canonical identity of either source subject."""
    records = list(transaction.run(
        """
        MATCH (
            canonical:CanonicalSubject
        )-[:DERIVED_FROM]->
            (source:PassSubject)
    
        WHERE source.uri IN [
            $left_uri,
            $right_uri
        ]
    
        RETURN DISTINCT canonical
        """,
        left_uri=left_uri,
        right_uri=right_uri,
    ))

    if len(records) > 1:
        raise ValueError("The proposal connects subjects that already belong to different canonical subjects")
    if not records:
        return None

    return CanonicalSubject.model_validate(dict(records[0]["canonical"]))

def _save_canonical_subject(
        transaction: ManagedTransaction,
        *,
        proposal_id: str,
        canonical: CanonicalSubject,
        left: PassSubject,
        right: PassSubject,
) -> None:
    """Save a canonical subject and its decision and provenance links."""
    record = transaction.run(
        """
        MATCH (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
        MATCH (left:PassSubject {
            uri: $left_uri
        })
        MATCH (right:PassSubject {
            uri: $right_uri
        })
        MERGE (
            canonical:
            CanonicalPassElement:
            CanonicalSubject {
                uri: $canonical_uri
            }
        )
        SET canonical.model_component_id =
                $model_component_id,
            canonical.label = $label,
            canonical.pass_type = $pass_type,
            canonical.status = $status,
            canonical.source_subject_uris =
                $source_subject_uris
        MERGE (canonical)-[:DERIVED_FROM]->(left)
        MERGE (canonical)-[:DERIVED_FROM]->(right)
        MERGE (proposal)-[:CREATED_CANONICAL]->
            (canonical)
        RETURN canonical.uri AS uri
        """,
        proposal_id=proposal_id,
        left_uri=left.uri,
        right_uri=right.uri,
        canonical_uri=canonical.uri,
        model_component_id=(canonical.model_component_id),
        label=canonical.label,
        pass_type=canonical.pass_type,
        status=canonical.status,
        source_subject_uris=list(canonical.source_subject_uris),
    ).single()

    if record is None:
        raise ValueError("Canonical subject could not be saved.")