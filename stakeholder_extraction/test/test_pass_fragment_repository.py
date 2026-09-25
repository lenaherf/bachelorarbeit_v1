import os
from uuid import uuid4
import pytest
from neo4j import GraphDatabase

from stakeholder_extraction.models import StakeholderView, CandidateMessage, CandidateSubject
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view


@pytest.mark.integration
def test_saves_complete_pass_fragment():
    view_id = f"fragment-test-{uuid4()}"

    view = make_complaint_view()

    fragment = map_view_to_pass_fragment(view, view_id=view_id)

    saved_id = save_pass_model_fragment(fragment)

    assert saved_id == view_id

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })-[:CONTAINS]->(element:PassElement)
                RETURN count(element) AS element_count
                """,
                view_id=view_id,
            ).single()

            relationship_record = session.run(
                """
                   MATCH (fragment:PassModelFragment {
                       view_id: $view_id
                   })-[:CONTAINS]->(source:PassElement)
                   MATCH (source)-[relationship]->(target:PassElement)
                   MATCH (fragment)-[:CONTAINS]->(target)
                   RETURN count(relationship) AS relationship_count
                   """,
                view_id=view_id,
            ).single()

            assert record is not None
            assert record["element_count"] == 11

            assert relationship_record is not None
            assert relationship_record["relationship_count"] == 16
    finally:
        driver.close()

@pytest.mark.integration
def test_does_not_merge_matching_labels():
    # First StakeholderView
    first_view_id = f"first-fragment-{uuid4()}"
    first_view = make_complaint_view()
    first_fragment = map_view_to_pass_fragment(first_view, view_id=first_view_id)
    save_pass_model_fragment(first_fragment)
    first_customer = first_fragment.subjects[0]

    # Second StakeholderView
    second_view_id = f"second-fragment-{uuid4()}"
    second_view = make_complaint_view()
    second_fragment = map_view_to_pass_fragment(second_view, view_id=second_view_id)
    save_pass_model_fragment(second_fragment)
    second_customer = second_fragment.subjects[0]

    assert first_customer.label == second_customer.label
    assert first_customer.uri != second_customer.uri

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (subject:PassSubject {
                    label: "Customer"
                })
                WHERE subject.view_id IN [
                    $first_view_id,
                    $second_view_id
                ]
                RETURN
                    count(subject) AS subject_count,
                    count(DISTINCT subject.uri) AS uri_count
                """,
                first_view_id=first_view_id,
                second_view_id=second_view_id,
            ).single()

            assert record is not None
            assert record["subject_count"] == 2
            assert record["uri_count"] == 2
    finally:
        driver.close()

@pytest.mark.integration
def test_saves_mapping_issues():
    view_id = f"issue-fragment-{uuid4()}"

    view = StakeholderView(
        stakeholder="Customer Service",
        source_text="I send something to the customer.",
        corrected_text="I send something to the customer.",
        prepared_text="Customer Service sends something to the Customer.",
        candidate_subjects=[
            CandidateSubject(
                name="Customer Service",
                evidence="Customer Service",
            ),
            CandidateSubject(
                name="Customer",
                evidence="Customer",
            ),
        ],
        candidate_messages=[
            CandidateMessage(
                name=None,
                sender="Customer Service",
                receiver="Customer",
                evidence="sends something to the Customer",
            ),
        ],
        candidate_activities=[],
        candidate_states=[],
        candidate_transitions=[],
        open_questions=[],
    )

    fragment = map_view_to_pass_fragment(view, view_id=view_id)

    assert len(fragment.mapping_issues) == 1
    assert fragment.mapping_issues[0].code == "missing_message_name"

    save_pass_model_fragment(fragment)

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })-[:HAS_MAPPING_ISSUE]->
                    (issue:MappingIssue)
                RETURN
                    count(issue) AS issue_count,
                    collect(issue.code) AS issue_codes
                """,
                view_id=view_id,
            ).single()

            assert record is not None
            assert record["issue_count"] == 1
            assert record["issue_codes"] == ["missing_message_name"]
    finally:
        driver.close()

@pytest.mark.integration
def test_saving_same_fragment_twice_is_idempotent():
    view_id = f"same-fragment-{uuid4()}"
    view = make_complaint_view()
    fragment = map_view_to_pass_fragment(view, view_id=view_id)

    # Save same fragment twice.
    save_pass_model_fragment(fragment)
    save_pass_model_fragment(fragment)

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            fragment_record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })
                RETURN count(fragment) AS fragment_count
                """,
                view_id=view_id,
            ).single()

            element_record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })-[:CONTAINS]->(element:PassElement)
                RETURN count(element) AS element_count
                """,
                view_id=view_id,
            ).single()

            relationship_record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })-[:CONTAINS]->(source:PassElement)
                MATCH (source)-[relationship]->
                    (target:PassElement)
                MATCH (fragment)-[:CONTAINS]->(target)
                RETURN count(relationship)
                    AS relationship_count
                """,
                view_id=view_id,
            ).single()

            assert fragment_record is not None
            assert element_record is not None
            assert relationship_record is not None

            assert fragment_record["fragment_count"] == 1
            assert element_record["element_count"] == 11
            assert relationship_record["relationship_count"] == 16

    finally:
        driver.close()

@pytest.mark.integration
def test_preserves_formal_element_metadata():
    view_id = f"metadata-fragment-{uuid4()}"
    view = make_complaint_view()
    fragment = map_view_to_pass_fragment(view, view_id=view_id)
    save_pass_model_fragment(fragment)

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = session.run(
                """
                MATCH (fragment:PassModelFragment {
                    view_id: $view_id
                })-[:CONTAINS]->(element:PassElement)
                WITH collect(element) AS elements
                RETURN
                    size(elements) AS element_count,
                    all(element IN elements
                        WHERE element.view_id = $view_id
                    ) AS correct_view_id,
                    all(element IN elements
                        WHERE element.stakeholder
                            IS NOT NULL
                    ) AS has_stakeholder,
                    all(element IN elements
                        WHERE element.evidence
                            IS NOT NULL
                    ) AS has_evidence,
                    all(element IN elements
                        WHERE element.status
                            IS NOT NULL
                    ) AS has_status,
                    all(element IN elements
                        WHERE element.uri
                            STARTS WITH $base_uri
                    ) AS has_stable_uri
                """,
                view_id=view_id,
                base_uri=f"urn:pass:view:{view_id}:",
            ).single()

            assert record is not None
            assert record["element_count"] == 11
            assert record["correct_view_id"] is True
            assert record["has_stakeholder"] is True
            assert record["has_evidence"] is True
            assert record["has_status"] is True
            assert record["has_stable_uri"] is True
    finally:
        driver.close()