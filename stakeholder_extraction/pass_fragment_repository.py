import os
from neo4j import GraphDatabase, ManagedTransaction
from stakeholder_extraction.pass_models import (PassElement, PassModelFragment)
from dotenv import load_dotenv

load_dotenv()

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
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            session.execute_write(_save_fragment_transaction, fragment)
    finally:
        driver.close()

    return fragment.view_id