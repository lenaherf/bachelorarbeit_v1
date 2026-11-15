"""Persist administrator decisions about source behavior."""

from uuid import uuid4
from neo4j import ManagedTransaction

from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.neo4j_connection import open_neo4j_session


def _save_behavior_review_transaction(
        transaction: ManagedTransaction,
        review_id: str,
        review: BehaviorReview,
) -> str:
    """Save a review only when its source and canonical references match."""

    record = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $source_view_id
        })-[:CONTAINS]->(source:PassSubject {
            uri: $source_subject_uri
        })        MATCH (canonical:CanonicalSubject {
            uri: $canonical_subject_uri
        })-[:DERIVED_FROM]->(source)        WHERE source.pass_type = "FullySpecifiedSubject"
          AND canonical.pass_type = "FullySpecifiedSubject"        CREATE (review:BehaviorReview {
            review_id: $review_id,
            source_view_id: $source_view_id,
            source_subject_uri: $source_subject_uri,
            canonical_subject_uri: $canonical_subject_uri,
            decision: $decision,
            reviewed_by: $reviewed_by,
            reviewed_at: datetime($reviewed_at)
        })        CREATE (review)-[:REVIEWS_FRAGMENT]->(fragment)
        CREATE (review)-[:SELECTS_SOURCE]->(source)
        CREATE (review)-[:FOR_SUBJECT]->(canonical)        RETURN review.review_id AS review_id
        """,
        review_id=review_id,
        source_view_id=review.source_view_id,
        source_subject_uri=review.source_subject_uri,
        canonical_subject_uri=review.canonical_subject_uri,
        decision=review.decision,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at.isoformat(),
    ).single()

    if record is None:
        raise ValueError(
            "The review requires a saved source subject in the selected fragment and a "
            "matching canonical subject. Both subjects must be FullySpecifiedSubject."
        )

    return record["review_id"]

def save_behavior_review(review: BehaviorReview) -> str:
    """Save one review decision and return its identifier."""

    review_id = str(uuid4())

    with open_neo4j_session() as session:
        return session.execute_write(
            _save_behavior_review_transaction,
            review_id,
            review,
        )

def _get_behavior_review_transaction(
        transaction: ManagedTransaction,
        review_id: str,
) -> BehaviorReview:
    """Load one saved behavior review."""

    records = list(
        transaction.run(
            """
            MATCH (review:BehaviorReview {
                review_id: $review_id
            })
            RETURN review
            """,
            review_id=review_id,
        )
    )

    if not records:
        raise ValueError(f"No behavior review found with ID '{review_id}'.")

    if len(records) != 1:
        raise ValueError(f"Multiple behavior reviews found with ID '{review_id}'.")

    properties = dict(records[0]["review"])

    properties.pop("review_id") # Not field of BehaviorReview

    properties["reviewed_at"] = properties["reviewed_at"].to_native()

    return BehaviorReview.model_validate(properties)

def get_behavior_review(review_id: str) -> BehaviorReview:
    """Retrieve a behavior review by its saved identifier."""

    with open_neo4j_session() as session:
        return session.execute_read(
            _get_behavior_review_transaction,
            review_id,
        )

