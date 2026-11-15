"""Persist explicitly selected canonical process models."""

from neo4j import ManagedTransaction
from stakeholder_extraction.canonical_behavior_repository import _get_canonical_behavior_transaction
from stakeholder_extraction.canonical_models import CanonicalProcessModel, CanonicalSubject, \
    CanonicalMessageSpecification, CanonicalMessageExchange, CanonicalProcessContents
from stakeholder_extraction.canonical_process import validate_process_structure
from stakeholder_extraction.neo4j_connection import open_neo4j_session


def _load_selected_nodes(
        transaction: ManagedTransaction,
        *,
        label: str,
        uris: tuple[str, ...],
) -> list[dict]:
    """Load exactly the selected nodes of one supported type."""

    allowed_labels = {
        "CanonicalSubject",
        "CanonicalMessageSpecification",
        "CanonicalMessageExchange",
    }

    if label not in allowed_labels:
        raise ValueError("Unsupported canonical element label.")

    records = list(
        transaction.run(
            f"""
            MATCH (element:CanonicalPassElement:{label})
            WHERE element.uri IN $uris
            RETURN element
            ORDER BY element.uri
            """,
            uris=list(uris),
        )
    )

    properties = [dict(row["element"]) for row in records]
    found_uris = [item["uri"] for item in properties]

    if (len(found_uris) != len(uris) or set(found_uris) != set(uris)):
        raise ValueError(f"Could not resolve exactly the selected {label} nodes.")

    return properties

def _load_process_members(
    transaction: ManagedTransaction,
    model: CanonicalProcessModel,
) -> CanonicalProcessContents:
    """Resolve the selected process members in the current transaction."""
    subjects = [
        CanonicalSubject.model_validate(properties)
        for properties in _load_selected_nodes(
            transaction,
            label="CanonicalSubject",
            uris=model.subject_uris,
        )
    ]

    messages = [
        CanonicalMessageSpecification.model_validate(properties)
        for properties in _load_selected_nodes(
            transaction,
            label="CanonicalMessageSpecification",
            uris=model.message_specification_uris,
        )
    ]

    exchanges = [
        CanonicalMessageExchange.model_validate(properties)
        for properties in _load_selected_nodes(
            transaction,
            label="CanonicalMessageExchange",
            uris=model.message_exchange_uris,
        )
    ]

    behavior_fragments = [
        _get_canonical_behavior_transaction(transaction, behavior_uri)
        for behavior_uri in model.behavior_uris
    ]

    return CanonicalProcessContents(
        model=model,
        subjects=subjects,
        behavior_fragments=behavior_fragments,
        messages=messages,
        exchanges=exchanges,
    )

def _save_process_transaction(
        transaction: ManagedTransaction,
        model: CanonicalProcessModel,
) -> str:
    """Validate saved members and persist the process selection."""

    if not model.subject_uris:
        raise ValueError("Select at least one subject.")

    contents = _load_process_members(transaction, model)

    validate_process_structure(
        model,
        subjects=contents.subjects,
        behavior_fragments=contents.behavior_fragments,
        messages=contents.messages,
        exchanges=contents.exchanges,
    )

    # Repeated saves are allowed but replacing a selection is not.
    existing = transaction.run(
        """
        MATCH (model:CanonicalProcessModel {uri: $uri})
        RETURN model
        """,
        uri=model.uri,
    ).single()

    if existing is not None:
        existing_model = CanonicalProcessModel.model_validate(dict(existing["model"]))

        if existing_model != model:
            raise ValueError("This process model already exists with different data. Use a new model ID.")

    member_uris = [
        *model.subject_uris,
        *model.behavior_uris,
        *model.message_specification_uris,
        *model.message_exchange_uris,
    ]

    if len(set(member_uris)) != len(member_uris):
        raise ValueError("Different process members must have distinct URIs.")

    record = transaction.run(
        """
        MERGE (model:CanonicalProcessModel {uri: $uri})
        SET model += $properties
        WITH model
        UNWIND $member_uris AS member_uri
        MATCH (element:CanonicalPassElement {uri: member_uri})
        MERGE (model)-[:CONTAINS]->(element)
        RETURN count(element) AS member_count
        """,
        uri=model.uri,
        properties=model.model_dump(mode="json"),
        member_uris=member_uris,
    ).single()

    if record is None or record["member_count"] != len(member_uris):
        raise ValueError("Not all process members could be linked.")

    return model.uri

def save_canonical_process_model(
        model: CanonicalProcessModel,
) -> str:
    """Validate and save one canonical process selection."""

    with open_neo4j_session() as session:
        return session.execute_write(_save_process_transaction, model)

def _get_process_transaction(
        transaction: ManagedTransaction,
        uri: str,
) -> CanonicalProcessModel:
    """Load a proces identity and its stored membership lists."""

    record = transaction.run(
        """
        MATCH (model:CanonicalProcessModel {uri: $uri})
        RETURN model
        """,
        uri=uri,
    ).single()

    if record is None:
        raise ValueError(f"No canonical process found with URI '{uri}'.")

    return CanonicalProcessModel.model_validate(dict(record["model"]))

def get_canonical_process_model(uri: str) -> CanonicalProcessModel:
    """Retrieve a saved process model by URI."""

    with open_neo4j_session() as session:
        return session.execute_read(_get_process_transaction, uri)

def _load_process_contents_transaction(
    transaction: ManagedTransaction,
    uri: str,
) -> CanonicalProcessContents:
    """Load exactly the elements selected by one saved process."""

    model = _get_process_transaction(transaction, uri)

    return _load_process_members(transaction, model)

def load_canonical_process_contents(
    uri: str,
) -> CanonicalProcessContents:
    """Load a process and its selected contents in one read transaction."""

    with open_neo4j_session() as session:
        return session.execute_read(
            _load_process_contents_transaction,
            uri,
        )