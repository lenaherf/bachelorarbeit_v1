"""Persist canonical subject behavior."""

from neo4j import ManagedTransaction
from stakeholder_extraction.behavior_review_repository import _get_behavior_review_transaction
from stakeholder_extraction.canonical_behavior import assemble_reviewed_behavior
from stakeholder_extraction.canonical_models import CanonicalSubjectBehavior, CanonicalSubject, \
    CanonicalBehaviorFragment, CanonicalMessageSpecification, CanonicalMessageExchange, CanonicalState, \
    CanonicalTransition
from stakeholder_extraction.canonicalization import create_canonical_subject_behavior
from stakeholder_extraction.neo4j_connection import open_neo4j_session
from stakeholder_extraction.pass_fragment_repository import _get_fragment_transaction
from stakeholder_extraction.pass_models import PassSubject


def _create_behavior_container_transaction(
        transaction: ManagedTransaction,
        review_id: str
) -> CanonicalSubjectBehavior:
    """Create a behavior container from a saved confirmed review."""

    review = _get_behavior_review_transaction(transaction, review_id)

    if review.decision != "confirmed":
        raise ValueError("Only confirmed behavior reviews can create behavior.")

    record = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $view_id
        })-[:CONTAINS]->(source:PassSubject {
            uri: $source_uri
        })
        MATCH (subject:CanonicalSubject {
            uri: $subject_uri
        })-[:DERIVED_FROM]->(source)
        RETURN source, subject
        """,
        view_id=review.source_view_id,
        source_uri=review.source_subject_uri,
        subject_uri=review.canonical_subject_uri,
    ).single()

    if record is None:
        raise ValueError("The reviewed source and canonical subject could not be resolved.")

    source = PassSubject.model_validate(dict(record["source"]))
    subject = CanonicalSubject.model_validate(dict(record["subject"]))
    behavior = create_canonical_subject_behavior(source, subject=subject)

    saved = transaction.run(
        """
        MATCH (review:BehaviorReview {
            review_id: $review_id
        })
        MATCH (subject:CanonicalSubject {
            uri: $subject_uri
        })
        MATCH (source:PassSubject {
            uri: $source_uri
        })
        MERGE (behavior:CanonicalPassElement:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })
        SET behavior += $properties
        MERGE (subject)-[:HAS_BEHAVIOR]->(behavior)
        MERGE (review)-[:CREATED_CANONICAL]->(behavior)
        MERGE (behavior)-[:DERIVED_FROM]->(source)
        RETURN behavior.uri AS uri
        """,
        review_id=review_id,
        subject_uri=subject.uri,
        source_uri=source.uri,
        behavior_uri=behavior.uri,
        properties=behavior.model_dump(mode="json"),
    ).single()

    if saved is None:
        raise ValueError("The canonical behavior could not be saved.")

    return behavior

def create_confirmed_behavior_container(
        review_id: str,
) -> CanonicalSubjectBehavior:
    """Create or reuse the container for a confirmed source selection."""

    with open_neo4j_session() as session:
        return session.execute_write(
            _create_behavior_container_transaction,
            review_id,
        )

def _assemble_saved_behavior_transaction(
        transaction: ManagedTransaction,
        review_id: str,
) -> CanonicalBehaviorFragment:
    """Load saved inputs and assemble one confirmed behavior."""

    review = _get_behavior_review_transaction(transaction, review_id)

    if review.decision != "confirmed":
        raise ValueError("Only confirmed behavior reviews allow assembly.")

    fragment = _get_fragment_transaction(transaction, review.source_view_id)

    subject_record = transaction.run(
        """
        MATCH (subject:CanonicalSubject {
            uri: $subject_uri
        })-[:DERIVED_FROM]->(source:PassSubject {
            uri: $source_uri
        })
        RETURN subject
        """,
        subject_uri=review.canonical_subject_uri,
        source_uri=review.source_subject_uri,
    ).single()

    if subject_record is None:
        raise ValueError("The reviewed canonical subject could not be resolved.")

    subject = CanonicalSubject.model_validate(dict(subject_record["subject"]))

    message_records = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $view_id
        })-[:CONTAINS]->(source:PassMessageSpecification)
        MATCH (message:CanonicalMessageSpecification)
            -[:DERIVED_FROM]->(source)
        RETURN DISTINCT message
        ORDER BY message.uri
        """,
        view_id=fragment.view_id,
    )

    messages = [
        CanonicalMessageSpecification.model_validate(dict(message_record["message"]))
        for message_record in message_records
    ]

    exchange_records = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $view_id
        })-[:CONTAINS]->(source:PassMessageExchange)
        MATCH (exchange:CanonicalMessageExchange)
            -[:DERIVED_FROM]->(source)
        RETURN DISTINCT exchange
        ORDER BY exchange.uri
        """,
        view_id=fragment.view_id,
    )

    exchanges = [CanonicalMessageExchange.model_validate(dict(exchange_record["exchange"]))
        for exchange_record in exchange_records]

    return assemble_reviewed_behavior(
        fragment,
        review=review,
        subject=subject,
        messages=messages,
        exchanges=exchanges,
    )

def assemble_saved_behavior(
        review_id: str,
) -> CanonicalBehaviorFragment:
    """Assemble a reviewed behavior from Neo4j without saving it."""

    with open_neo4j_session() as session:
        return session.execute_read(
            _assemble_saved_behavior_transaction,
            review_id,
        )

def _save_canonical_state(
        transaction: ManagedTransaction,
        state: CanonicalState,
) -> None:
    """Save a state with its owner, message, and resource references."""

    record = transaction.run(
        """
        MATCH (behavior:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })
        MATCH (performer:CanonicalSubject {
            uri: $performer_uri
        })
        MATCH (source:PassState {
            uri: $source_state_uri
        })
        OPTIONAL MATCH (message:CanonicalMessageSpecification {
            uri: $message_uri
        })
        WITH behavior, performer, source, message
        WHERE $message_uri IS NULL OR message IS NOT NULL
        MERGE (state:CanonicalPassElement:CanonicalState {
            uri: $uri
        })
        SET state += $properties
        MERGE (behavior)-[:CONTAINS]->(state)
        MERGE (state)-[:PERFORMED_BY]->(performer)
        MERGE (state)-[:DERIVED_FROM]->(source)
        FOREACH (
            item IN CASE WHEN message IS NULL THEN [] ELSE [message] END |
            MERGE (state)-[:REFERENCES_MESSAGE]->(item)
        )
        RETURN state.uri AS uri
        """,
        uri=state.uri,
        behavior_uri=state.behavior_uri,
        performer_uri=state.performer_uri,
        source_state_uri=state.source_state_uri,
        message_uri=state.message_specification_uri,
        properties=state.model_dump(mode="json"),
    ).single()

    if record is None:
        raise ValueError(f"Cannot save state '{state.uri}': a required reference is still missing.")

def _save_canonical_transition(
        transaction: ManagedTransaction,
        transition: CanonicalTransition,
) -> None:
    """Save a transition with its endpoints, exchange, and provenance."""

    record = transaction.run(
        """
        MATCH (behavior:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })-[:CONTAINS]->(start:CanonicalState {
            uri: $start_uri
        })
        MATCH (behavior)-[:CONTAINS]->(end:CanonicalState {
            uri: $end_uri
        })
        MATCH (source:PassTransition {
            uri: $source_transition_uri
        })
        OPTIONAL MATCH (exchange:CanonicalMessageExchange {
            uri: $exchange_uri
        })
        WITH behavior, start, end, source, exchange
        WHERE $exchange_uri IS NULL OR exchange IS NOT NULL
        MERGE (transition:CanonicalPassElement:CanonicalTransition {
            uri: $uri
        })
        SET transition += $properties
        MERGE (behavior)-[:CONTAINS]->(transition)
        MERGE (transition)-[:FROM_STATE]->(start)
        MERGE (transition)-[:TO_STATE]->(end)
        MERGE (transition)-[:DERIVED_FROM]->(source)
        FOREACH (
            item IN CASE WHEN exchange IS NULL THEN [] ELSE [exchange] END |
            MERGE (transition)-[:REFERENCES_EXCHANGE]->(item)
        )
        RETURN transition.uri AS uri
        """,
        uri=transition.uri,
        behavior_uri=transition.behavior_uri,
        start_uri=transition.source_state_uri,
        end_uri=transition.target_state_uri,
        source_transition_uri=transition.source_transition_uri,
        exchange_uri=transition.message_exchange_uri,
        properties=transition.model_dump(mode="json"),
    ).single()

    if record is None:
        raise ValueError(f"Cannot save transition '{transition.uri}': a required reference is still missing.")

def _save_confirmed_behavior_transition(
        transaction: ManagedTransaction,
        review_id: str,
) -> CanonicalBehaviorFragment:
    """Assemble and persist a reviewed behavior atomically."""

    # Resolve and validate the complete structure before writing.
    result = _assemble_saved_behavior_transaction(transaction, review_id)

    behavior = _create_behavior_container_transaction(transaction, review_id)

    if behavior != result.behavior:
        raise ValueError("The saved container does not match the assembled behavior.")

    # States must exist before transitions can reference them.

    for state in result.states:
        _save_canonical_state(transaction, state)

    for transition in result.transitions:
        _save_canonical_transition(transaction, transition)

    return result

def save_confirmed_behavior(
        review_id: str,
) -> CanonicalBehaviorFragment:
    """Save a confirmed behavior, its states and its transitions."""

    with open_neo4j_session() as session:
        return session.execute_write(
            _save_confirmed_behavior_transition,
            review_id,
        )

def _get_canonical_behavior_transaction(
        transaction: ManagedTransaction,
        behavior_uri: str,
) -> CanonicalBehaviorFragment:
    """Load a persisted canonical behavior and its contained elements."""

    record = transaction.run(
        """
        MATCH (behavior:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })
        RETURN behavior
        """,
        behavior_uri=behavior_uri,
    ).single()

    if record is None:
        raise ValueError(f"No canonical behavior found with URI '{behavior_uri}'.")

    behavior = CanonicalSubjectBehavior.model_validate(dict(record["behavior"]))

    state_records = transaction.run(
        """
        MATCH (behavior:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })-[:CONTAINS]->(state:CanonicalState)
        RETURN state
        ORDER BY state.source_state_uri, state.uri
        """,
        behavior_uri=behavior_uri,
    )

    states = [
        CanonicalState.model_validate(dict(row["state"]))
        for row in state_records
    ]

    transition_records = transaction.run(
        """
        MATCH (behavior:CanonicalSubjectBehavior {
            uri: $behavior_uri
        })-[:CONTAINS]->(transition:CanonicalTransition)
        RETURN transition
        ORDER BY transition.source_transition_uri, transition.uri
        """,
        behavior_uri=behavior_uri,
    )

    transitions = [
        CanonicalTransition.model_validate(dict(row["transition"]))
        for row in transition_records
    ]

    return CanonicalBehaviorFragment(
        behavior=behavior,
        states=states,
        transitions=transitions,
    )

def get_canonical_behavior(
        behavior_uri: str,
) -> CanonicalBehaviorFragment:
    """Read a saved canonical behavior by its URI."""

    with open_neo4j_session() as session:
        return session.execute_read(
            _get_canonical_behavior_transaction,
            behavior_uri,
        )