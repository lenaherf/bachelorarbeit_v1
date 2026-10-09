from neo4j import ManagedTransaction
from stakeholder_extraction.neo4j_connection import open_neo4j_session
from stakeholder_extraction.pass_models import (PassElement, PassModelFragment)

def _enum_value(value):
    return value.value if hasattr(value, "value") else value

def _save_element(
        transaction: ManagedTransaction,
        *,
        fragment: PassModelFragment,
        element: PassElement,
        neo4j_label: str,
        extra_properties: dict | None = None,
) -> None:
    properties = {
        "model_component_id": element.model_component_id,
        "label": element.label,
        "view_id": element.view_id,
        "stakeholder": element.stakeholder,
        "evidence": element.evidence,
        "status": _enum_value(element.status),
        "source_kind": element.source_kind,
        "source_index": element.source_index,
        "pass_type": element.pass_type,
    }

    if extra_properties: properties.update(extra_properties)

    transaction.run(
        f"""
        MATCH (fragment:PassModelFragment {{
            view_id: $view_id
        }})
        MERGE (element:PassElement:{neo4j_label} {{
            uri: $uri
        }})
        SET element += $properties
        MERGE (fragment)-[:CONTAINS]->(element)
        """,
        view_id=fragment.view_id,
        uri=element.uri,
        properties=properties,
    )

def _save_fragment_transaction(
        transaction: ManagedTransaction,
        fragment: PassModelFragment,
) -> None:
    transaction.run(
        """
        MERGE (fragment:PassModelFragment {
            view_id: $view_id
        })
        SET fragment.stakeholder = $stakeholder,
            fragment.base_uri = $base_uri
        """,
        view_id=fragment.view_id,
        stakeholder=fragment.stakeholder,
        base_uri=fragment.base_uri,
    )

    for subject in fragment.subjects:
        _save_element(
            transaction,
            fragment=fragment,
            element=subject,
            neo4j_label="PassSubject",
        )

    for message in fragment.message_specifications:
        _save_element(
            transaction,
            fragment=fragment,
            element=message,
            neo4j_label="PassMessageSpecification",
        )

    for exchange in fragment.message_exchanges:
        _save_element(
            transaction,
            fragment=fragment,
            element=exchange,
            neo4j_label="PassMessageExchange",
            extra_properties={
                "sender_uri": exchange.sender_uri,
                "receiver_uri": exchange.receiver_uri,
                "message_specification_uri": exchange.message_specification_uri,
            },
        )

    for states in fragment.states:
        _save_element(
            transaction,
            fragment=fragment,
            element=states,
            neo4j_label="PassState",
            extra_properties={
                "local_id": states.local_id,
                "performer_uri": states.performer_uri,
                "message_specification_uri": states.message_specification_uri,
                "is_initial": states.is_initial,
                "is_end": states.is_end,
            },
        )

    for transition in fragment.transitions:
        _save_element(
            transaction,
            fragment=fragment,
            element=transition,
            neo4j_label="PassTransition",
            extra_properties={
                "source_state_uri": transition.source_state_uri,
                "target_state_uri": transition.target_state_uri,
                "message_exchange_uri": transition.message_exchange_uri,
            },
        )

    for exchange in fragment.message_exchanges:
        _connect_elements(
            transaction,
            source_uri=exchange.uri,
            relationship_type="HAS_SENDER",
            target_uri=exchange.sender_uri,
        )

        _connect_elements(
            transaction,
            source_uri=exchange.uri,
            relationship_type="HAS_RECEIVER",
            target_uri=exchange.receiver_uri,
        )

        _connect_elements(
            transaction,
            source_uri=exchange.uri,
            relationship_type="HAS_MESSAGE_SPECIFICATION",
            target_uri=exchange.message_specification_uri,
        )

    for state in fragment.states:
        if state.performer_uri is not None:
            _connect_elements(
                transaction,
                source_uri=state.uri,
                relationship_type="PERFORMED_BY",
                target_uri=state.performer_uri,
            )

        if state.message_specification_uri is not None:
            _connect_elements(
                transaction,
                source_uri=state.uri,
                relationship_type="REFERENCES_MESSAGE",
                target_uri=state.message_specification_uri,
            )

    for transition in fragment.transitions:
        _connect_elements(
            transaction,
            source_uri=transition.uri,
            relationship_type="FROM_STATE",
            target_uri=transition.source_state_uri,
        )

        _connect_elements(
            transaction,
            source_uri=transition.uri,
            relationship_type="TO_STATE",
            target_uri=transition.target_state_uri,
        )

        if transition.message_exchange_uri is not None:
            _connect_elements(
                transaction,
                source_uri=transition.uri,
                relationship_type="REFERENCES_EXCHANGE",
                target_uri=transition.message_exchange_uri,
            )

    for index, issue in enumerate(fragment.mapping_issues):
        issue_id = (f"{fragment.view_id}: mapping-issue:{index:03d}")

        transaction.run(
            """
            MATCH (fragment:PassModelFragment {
                view_id: $view_id
            })
            MERGE (issue:MappingIssue {
                issue_id: $issue_id
            })
            SET issue.view_id = $view_id,
                issue.position = $position,
                issue.code = $code,
                issue.source_kind = $source_kind,
                issue.source_index = $source_index,
                issue.field = $field,
                issue.detail = $detail
            MERGE (fragment)-[:HAS_MAPPING_ISSUE]->(issue)
            """,
            issue_id=issue_id,
            view_id=fragment.view_id,
            position=index,
            code=issue.code,
            source_kind=issue.source_kind,
            source_index=issue.source_index,
            field=issue.field,
            detail=issue.detail,
        )

def _connect_elements(
        transaction: ManagedTransaction,
        *,
        source_uri: str,
        relationship_type: str,
        target_uri: str,
) -> None:
    transaction.run(
        f"""
          MATCH (source:PassElement {{
              uri: $source_uri
          }})
          MATCH (target:PassElement {{
              uri: $target_uri
          }})
          MERGE (source)-[:{relationship_type}]->(target)
          """,
        source_uri=source_uri,
        target_uri=target_uri,
    )

def save_pass_model_fragment(
        fragment: PassModelFragment,
) -> str:
    with open_neo4j_session() as session:
        session.execute_write(_save_fragment_transaction, fragment)

    return fragment.view_id

def _get_fragment_transaction(
        transaction: ManagedTransaction,
        view_id: str,
) -> PassModelFragment:
    """Reconstruct a saved fragment and its mapping issues."""

    record = transaction.run(
        """
        MATCH (fragment:PassModelFragment {view_id: $view_id})
        RETURN fragment
        """,
        view_id=view_id,
    ).single()

    if record is None:
        raise ValueError(f"No PASS fragment found with ID '{view_id}'.")

    properties = dict(record["fragment"])

    elements = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $view_id
        })-[:CONTAINS]->(element:PassElement)
        RETURN labels(element) AS labels, element
        ORDER BY element.uri
        """,
        view_id=view_id,
    )

    collections = {
        "subjects": [],
        "message_specifications": [],
        "message_exchanges": [],
        "states": [],
        "transitions": [],
    }

    label_to_collection = {
        "PassSubject": "subjects",
        "PassMessageSpecification": "message_specifications",
        "PassMessageExchange": "message_exchanges",
        "PassState": "states",
        "PassTransition": "transitions",
    }

    for row in elements:
        matching_labels = [
            label for label in label_to_collection
            if label in row["labels"]
        ]

        if len(matching_labels) != 1:
            raise ValueError("Each fragment element must have exactly one supported element type label.")

        collection_name = label_to_collection[matching_labels[0]]
        collections[collection_name].append(dict(row["element"]))

    issue_records = transaction.run(
        """
        MATCH (fragment:PassModelFragment {
            view_id: $view_id
        })-[:HAS_MAPPING_ISSUE]->(issue:MappingIssue)
        RETURN issue {
            .code,
            .source_kind,
            .source_index,
            .field,
            .detail
        } AS issue
        ORDER BY issue.position
        """,
        view_id=view_id,
    )

    return PassModelFragment.model_validate(
        {
            "view_id": properties["view_id"],
            "stakeholder": properties["stakeholder"],
            "base_uri": properties["base_uri"],
            **collections,
            "mapping_issues": [row["issue"] for row in issue_records],
        }
    )

def get_pass_model_fragment(view_id: str) -> PassModelFragment:
    """Load PASS fragment by its saved view identifier."""

    with open_neo4j_session() as session:
        return session.execute_read(
            _get_fragment_transaction,
            view_id,
        )