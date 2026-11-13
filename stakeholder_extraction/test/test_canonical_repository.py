import uuid
from uuid import uuid4
from datetime import datetime, timezone
import pytest

from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.behavior_review_repository import save_behavior_review, get_behavior_review
from stakeholder_extraction.canonical_behavior_repository import create_confirmed_behavior_container, \
    assemble_saved_behavior, save_confirmed_behavior, get_canonical_behavior
from stakeholder_extraction.canonical_process import create_canonical_process_model
from stakeholder_extraction.canonical_process_repository import get_canonical_process_model, save_canonical_process_model
from stakeholder_extraction.canonical_repository import canonicalize_confirmed_subject_proposal, \
    canonicalize_confirmed_message_pair_proposal, canonicalize_confirmed_one_sided_message
from stakeholder_extraction.models import CandidateMessage
from stakeholder_extraction.neo4j_connection import open_neo4j_session
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_models import ReviewDecision
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

    with open_neo4j_session() as session:
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

@pytest.mark.integration
def test_canonicalizes_confirmed_message_pair():
    test_id = str(uuid4())

    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id=f"customer-message-{test_id}")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"service-message-{test_id}")

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    save_reconciliation_proposals(proposals)

    subject_proposals = [
        proposal for proposal in proposals
        if proposal.proposal_type == "equivalent_subject"
    ]

    assert len(subject_proposals) == 2

    for proposal in subject_proposals:
        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="admin-test"
        )

        canonicalize_confirmed_subject_proposal(
            proposal.proposal_id
        )

    complaint_proposal = next(
        proposal for proposal in proposals
        if (proposal.proposal_type == "message_pair"
            and proposal.left_element_uri == customer_fragment.message_exchanges[0].uri
            and proposal.right_element_uri == service_fragment.message_exchanges[0].uri
        )
    )

    review_reconciliation_proposal(
        proposal_id=complaint_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    canonical_message, canonical_exchange = (
        canonicalize_confirmed_message_pair_proposal(complaint_proposal.proposal_id)
    )

    second_message, second_exchange = (
        canonicalize_confirmed_message_pair_proposal(complaint_proposal.proposal_id)
    )

    assert canonical_message.label == "Complaint"
    assert canonical_message.status == "confirmed"
    assert canonical_exchange.label == "Customer sends Complaint to Customer Service"
    assert canonical_exchange.status == "confirmed"

    assert second_message == canonical_message
    assert second_exchange == canonical_exchange

    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (
                proposal:ReconciliationProposal {
                    proposal_id: $proposal_id
                }
            )-[:CREATED_CANONICAL]->
                (exchange:CanonicalMessageExchange)
            MATCH (exchange)-[:HAS_SENDER]->
                (sender:CanonicalSubject)
            MATCH (exchange)-[:HAS_RECEIVER]->
                (receiver:CanonicalSubject)
            MATCH (exchange)-[
                :HAS_MESSAGE_SPECIFICATION
            ]->(message:CanonicalMessageSpecification)
            OPTIONAL MATCH
                (exchange)-[:DERIVED_FROM]->
                    (source_exchange:PassMessageExchange)
            OPTIONAL MATCH
                (message)-[:DERIVED_FROM]->
                    (source_message:PassMessageSpecification)
            RETURN
                exchange.uri AS exchange_uri,
                message.uri AS message_uri,
                sender.label AS sender_label,
                receiver.label AS receiver_label,
                count(DISTINCT source_exchange)
                    AS exchange_source_count,
                count(DISTINCT source_message)
                    AS message_source_count
            """,
            proposal_id=complaint_proposal.proposal_id,
        ).single()

        assert record is not None
        assert record["exchange_uri"] == canonical_exchange.uri
        assert record["message_uri"] == canonical_message.uri
        assert record["sender_label"] == "Customer"
        assert record["receiver_label"] == "Customer Service"
        assert record["exchange_source_count"] == 2
        assert record["message_source_count"] == 2

@pytest.mark.integration
def test_rejects_unconfirmed_message_pair():
    test_id = str(uuid4())

    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id=f"customer_unconfirmed_{test_id}")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"service_unconfirmed_{test_id}")

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    save_reconciliation_proposals(proposals)

    message_proposal = next(
        proposal for proposal in proposals
        if proposal.proposal_type == "message_pair"
    )

    with pytest.raises(
        ValueError,
        match="Only confirmed proposals"
    ):
        canonicalize_confirmed_message_pair_proposal(message_proposal.proposal_id)

@pytest.mark.integration
def test_requires_canonical_subjects_for_message_pair():
    test_id = str(uuid4())

    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id=f"customer-dependency-{test_id}")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id=f"service-dependency-{test_id}")

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    save_reconciliation_proposals(proposals)

    message_proposal = next(
        proposal for proposal in proposals
        if proposal.proposal_type == "message_pair"
    )

    review_reconciliation_proposal(
        proposal_id=message_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    # Subject proposals have not been canonicalized.

    with pytest.raises(
        ValueError,
        match="canonical sender must be created"
    ):
        canonicalize_confirmed_message_pair_proposal(message_proposal.proposal_id)

@pytest.mark.integration
def test_canonicalizes_confirmed_one_sided_message():
    test_id = str(uuid4())
    customer_view = make_customer_complaint_view()
    service_view = make_complaint_view()

    # This message occurs only in the Customer Service view
    service_view.candidate_messages.append(
        CandidateMessage(
            name="Acknowledgement",
            sender="Customer Service",
            receiver="Customer",
            evidence="send the customer an acknowledgement",
        )
    )

    customer_fragment = map_view_to_pass_fragment(
        customer_view,
        view_id=f"customer-one-sided-{test_id}",
    )

    service_fragment = map_view_to_pass_fragment(
        service_view,
        view_id=f"service-one-sided-{test_id}",
    )

    save_pass_model_fragment(customer_fragment)
    save_pass_model_fragment(service_fragment)

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    save_reconciliation_proposals(proposals)

    # Canonical sender and receiver must exist before the exchange can be canonicalized
    subject_proposals = [
        proposal for proposal in proposals
        if proposal.proposal_type == "equivalent_subject"
    ]

    assert len(subject_proposals) == 2

    canonical_subjects = {}

    for proposal in subject_proposals:
        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="admin-test"
        )

        canonical_subject = (canonicalize_confirmed_subject_proposal(proposal.proposal_id))

        canonical_subjects[canonical_subject.label] = canonical_subject

    one_sided_proposals = [
        proposal for proposal in proposals
        if proposal.proposal_type == "one_sided_message"
    ]

    assert len(one_sided_proposals) == 1

    one_sided_proposal = one_sided_proposals[0]

    #The additional mesage exists only in the service fragment.
    assert one_sided_proposal.left_element_uri is None
    assert one_sided_proposal.right_element_uri == service_fragment.message_exchanges[2].uri

    review_reconciliation_proposal(
        proposal_id=one_sided_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    canonical_message, canonical_exchange = (
        canonicalize_confirmed_one_sided_message(
            one_sided_proposal.proposal_id,
        )
    )

    # Run second time to verify idempotence.
    second_message, second_exchange = (
        canonicalize_confirmed_one_sided_message(one_sided_proposal.proposal_id)
    )

    source_message = (service_fragment.message_specifications[2])
    source_exchange = service_fragment.message_exchanges[2]

    assert canonical_message.label == "Acknowledgement"
    assert canonical_message.status == "confirmed"
    assert canonical_message.source_message_uris == (source_message.uri, )
    assert canonical_exchange.label == "Customer Service sends Acknowledgement to Customer"
    assert canonical_exchange.status == "confirmed"
    assert canonical_exchange.source_exchange_uris == (source_exchange.uri, )
    assert canonical_exchange.sender_uri == canonical_subjects["Customer Service"].uri
    assert canonical_exchange.receiver_uri == canonical_subjects["Customer"].uri
    assert canonical_exchange.message_specification_uri == canonical_message.uri
    assert second_message == canonical_message
    assert second_exchange == canonical_exchange

    # verify the Neo4j structure
    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (
                proposal:ReconciliationProposal {
                    proposal_id: $proposal_id
                }
            )-[:CREATED_CANONICAL]->
                (exchange:CanonicalMessageExchange)
            MATCH (proposal)-[:CREATED_CANONICAL]->
                (message:CanonicalMessageSpecification)
            MATCH (exchange)-[:HAS_SENDER]->
                (sender:CanonicalSubject)
            MATCH (exchange)-[:HAS_RECEIVER]->
                (receiver:CanonicalSubject)
            MATCH (exchange)-[
                :HAS_MESSAGE_SPECIFICATION
            ]->(message)
            OPTIONAL MATCH
                (exchange)-[:DERIVED_FROM]->
                    (source_exchange:PassMessageExchange)
            OPTIONAL MATCH
                (message)-[:DERIVED_FROM]->
                    (source_message:PassMessageSpecification)
            RETURN
                exchange.uri AS exchange_uri,
                message.uri AS message_uri,
                sender.label AS sender_label,
                receiver.label AS receiver_label,
                count(DISTINCT source_exchange)
                    AS exchange_source_count,
                count(DISTINCT source_message)
                    AS message_source_count
            """,
            proposal_id=one_sided_proposal.proposal_id,
        ).single()

        assert record is not None
        assert record["exchange_uri"] == canonical_exchange.uri
        assert record["message_uri"] == canonical_message.uri
        assert record["sender_label"] == "Customer Service"
        assert record["receiver_label"] == "Customer"
        assert record["exchange_source_count"] == 1
        assert record["message_source_count"] == 1

@pytest.mark.integration
@pytest.mark.parametrize("decision", ["confirmed", "rejected"])
def test_saves_behavior_review(decision: ReviewDecision):
    customer_fragment, _, subject_proposal = ( _create_saved_subject_reconciliation())

    # First establish the shared subject identity.
    review_reconciliation_proposal(
        proposal_id=subject_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    customer = canonicalize_confirmed_subject_proposal(subject_proposal.proposal_id)

    # Separately record the decision about its source behavior.
    review = BehaviorReview(
        source_view_id=customer_fragment.view_id,
        source_subject_uri=customer_fragment.subjects[0].uri,
        canonical_subject_uri=customer.uri,
        decision=decision,
        reviewed_by="admin-test",
        reviewed_at=datetime.now(timezone.utc),
    )

    review_id = save_behavior_review(review)

    loaded_review = get_behavior_review(review_id)

    assert loaded_review == review

    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (review:BehaviorReview {
                review_id: $review_id
            })-[:REVIEWS_FRAGMENT]->(fragment:PassModelFragment)

            MATCH (review)-[:SELECTS_SOURCE]->(source:PassSubject)
            MATCH (fragment)-[:CONTAINS]->(source)

            MATCH (review)-[:FOR_SUBJECT]->(canonical:CanonicalSubject)
            MATCH (canonical)-[:DERIVED_FROM]->(source)

            RETURN
                review.decision AS decision,
                review.reviewed_by AS reviewed_by,
                review.reviewed_at AS reviewed_at,
                fragment.view_id AS view_id,
                source.uri AS source_uri,
                canonical.uri AS canonical_uri
            """,
            review_id=review_id,
        ).single()

        assert record is not None
        assert record["decision"] == decision
        assert record["reviewed_by"] == "admin-test"
        assert record["reviewed_at"].to_native() == review.reviewed_at
        assert record["view_id"] == customer_fragment.view_id
        assert record["source_uri"] == review.source_subject_uri
        assert record["canonical_uri"] == customer.uri

        # An unrelated canonical subject must not receive the review.
        invalid_review = BehaviorReview(
            **{
                **review.model_dump(),
                "canonical_subject_uri": (
                    "urn:pass:canonical:subject:missing"
                ),
            }
        )

        with pytest.raises(
            ValueError,
            match="matching canonical subject",
        ):
            save_behavior_review(invalid_review)

@pytest.mark.integration
def test_get_behavior_review_rejects_missing_id():
    missing_id = str(uuid4())

    with pytest.raises(
        ValueError,
        match="No behavior review found"
    ):
        get_behavior_review(missing_id)

@pytest.mark.integration
@pytest.mark.parametrize("decision", ["confirmed", "rejected"])
def test_creates_only_confirmed_behavior_container(
        decision: ReviewDecision,
):
    customer_fragment, _, subject_proposal = (_create_saved_subject_reconciliation())

    review_reconciliation_proposal(
        proposal_id=subject_proposal.proposal_id,
        decision="confirmed",
        reviewed_by="admin-test"
    )

    customer = canonicalize_confirmed_subject_proposal(subject_proposal.proposal_id)

    review = BehaviorReview(
        source_view_id=customer_fragment.view_id,
        source_subject_uri=customer_fragment.subjects[0].uri,
        canonical_subject_uri=customer.uri,
        decision=decision,
        reviewed_by="admin-test",
        reviewed_at=datetime.now(timezone.utc),
    )

    review_id = save_behavior_review(review)

    if decision == "rejected":
        with pytest.raises(
            ValueError,
            match="Only confirmed behavior reviews",
        ):
            create_confirmed_behavior_container(review_id)

        with open_neo4j_session() as session:
            record = session.run(
                """
                MATCH (subject:CanonicalSubject {uri: $uri})
                OPTIONAL MATCH (subject)-[:HAS_BEHAVIOR]->(behavior)
                RETURN count(behavior) AS behavior_count
                """,
                uri=customer.uri,
            ).single()

        assert record["behavior_count"] == 0
        return

    behavior = create_confirmed_behavior_container(review_id)
    second_behavior = create_confirmed_behavior_container(review_id)

    assert second_behavior == behavior
    assert behavior.subject_uri == customer.uri
    assert behavior.source_subject_uri == review.source_subject_uri

    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (review:BehaviorReview {
                review_id: $review_id
            })-[:CREATED_CANONICAL]->
                (behavior:CanonicalSubjectBehavior)
            MATCH (subject:CanonicalSubject {
                uri: $subject_uri
            })-[:HAS_BEHAVIOR]->(behavior)
            MATCH (behavior)-[:DERIVED_FROM]->
                (source:PassSubject {uri: $source_uri})
            RETURN
                collect(DISTINCT behavior.uri) AS behavior_uris,
                count(*) AS path_count
            """,
            review_id=review_id,
            subject_uri=customer.uri,
            source_uri=review.source_subject_uri,
        ).single()

    assert record["behavior_uris"] == [behavior.uri]
    assert record["path_count"] == 1

@pytest.mark.integration
def test_assembles_behavior_from_saved_review():
    customer_fragment, service_fragment, _ = (_create_saved_subject_reconciliation())

    proposals = compare_pass_fragments(customer_fragment, service_fragment)

    canonical_subjects = {}

    for proposal in proposals:
        if proposal.proposal_type != "equivalent_subject":
            continue

        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="admin-test",
        )

        subject = canonicalize_confirmed_subject_proposal(proposal.proposal_id)

        canonical_subjects[subject.label] = subject

    service = canonical_subjects["Customer Service"]

    review = BehaviorReview(
        source_view_id=service_fragment.view_id,
        source_subject_uri=service_fragment.subjects[1].uri,
        canonical_subject_uri=service.uri,
        decision="confirmed",
        reviewed_by="admin-test",
        reviewed_at=datetime.now(timezone.utc),
    )

    review_id = save_behavior_review(review)

    # Communication has not been canonicalized yet.
    with pytest.raises(
        ValueError,
        match="exactly one canonical message",
    ):
        assemble_saved_behavior(review_id)

    canonical_messages = []
    canonical_exchanges = []

    for proposal in proposals:
        if proposal.proposal_type != "message_pair":
            continue

        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="admin-test",
        )

        message, exchange = canonicalize_confirmed_message_pair_proposal(proposal.proposal_id)
        canonical_messages.append(message)
        canonical_exchanges.append(exchange)

    result = assemble_saved_behavior(review_id)

    assert result.behavior.subject_uri == service.uri
    assert result.behavior.source_view_id == service_fragment.view_id
    assert len(result.states) == 3
    assert len(result.transitions) == 2

    state_uris = {state.uri for state in result.states}

    assert all(
        transition.source_state_uri in state_uris
        and transition.target_state_uri in state_uris
        for transition in result.transitions
    )

    assert assemble_saved_behavior(review_id) == result

    saved = save_confirmed_behavior(review_id)
    second_saved = save_confirmed_behavior(review_id)

    assert saved == result
    assert second_saved == saved

    process = create_canonical_process_model(
        model_id=f"complaint-process-{uuid4()}",
        label="Complaint handling",
        subject_uris=[subject.uri for subject in canonical_subjects.values()],
        behavior_uris=[saved.behavior.uri],
        message_specification_uris=[message.uri for message in canonical_messages],
        message_exchange_uris=[exchange.uri for exchange in canonical_exchanges],
    )

    assert save_canonical_process_model(process) == process.uri
    assert save_canonical_process_model(process) == process.uri
    assert get_canonical_process_model(process.uri) == process

    expected_members = {
        *process.subject_uris,
        *process.behavior_uris,
        *process.message_specification_uris,
        *process.message_exchange_uris,
    }

    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (model:CanonicalProcessModel {
                uri: $uri
            })-[membership:CONTAINS]->(element)
            RETURN
                collect(element.uri) AS member_uris,
                count(membership) AS relationship_count
            """,
            uri=process.uri,
        ).single()

    assert set(record["member_uris"]) == expected_members
    assert record["relationship_count"] == len(expected_members)

    # Missing selected elements must prevent the process from being saved.
    invalid_process = process.model_copy(
        update={
            "uri": f"urn:pass:canonical:process:invalid-{uuid4()}",
            "subject_uris": (
                *process.subject_uris,
                "urn:pass:canonical:subject:missing",
            ),
        }
    )

    with pytest.raises(
            ValueError,
            match="Could not resolve exactly the selected CanonicalSubject",
    ):
        save_canonical_process_model(invalid_process)

    with pytest.raises(ValueError, match="No canonical process found"):
        get_canonical_process_model(invalid_process.uri)

    loaded = get_canonical_behavior(saved.behavior.uri)
    assert loaded == result

    with open_neo4j_session() as session:
        state_records = list(
            session.run(
                """
                MATCH (behavior:CanonicalSubjectBehavior {
                    uri: $behavior_uri
                })-[:CONTAINS]->(state:CanonicalState)
                MATCH (state)-[:PERFORMED_BY]->
                    (performer:CanonicalSubject)
                MATCH (state)-[:DERIVED_FROM]->(source:PassState)
                OPTIONAL MATCH (state)-[:REFERENCES_MESSAGE]->
                    (message:CanonicalMessageSpecification)
                RETURN
                    state.uri AS uri,
                    performer.uri AS performer_uri,
                    source.uri AS source_uri,
                    message.uri AS message_uri
                """,
                behavior_uri=saved.behavior.uri,
            )
        )

        transition_records = list(
            session.run(
                """
                MATCH (behavior:CanonicalSubjectBehavior {
                    uri: $behavior_uri
                })-[:CONTAINS]->(transition:CanonicalTransition)
                MATCH (transition)-[:FROM_STATE]->(start:CanonicalState)
                MATCH (transition)-[:TO_STATE]->(end:CanonicalState)
                MATCH (transition)-[:DERIVED_FROM]->(source:PassTransition)
                OPTIONAL MATCH (transition)-[:REFERENCES_EXCHANGE]->
                    (exchange:CanonicalMessageExchange)
                RETURN
                    transition.uri AS uri,
                    start.uri AS start_uri,
                    end.uri AS end_uri,
                    source.uri AS source_uri,
                    exchange.uri AS exchange_uri
                """,
                behavior_uri=saved.behavior.uri,
            )
        )

    # Check the persisted links.
    assert len(state_records) == 3
    assert {
        (
            row["uri"],
            row["performer_uri"],
            row["source_uri"],
            row["message_uri"],
        )
        for row in state_records
    } == {
        (
            state.uri,
            state.performer_uri,
            state.source_state_uri,
            state.message_specification_uri,
        )
        for state in saved.states
    }

    assert len(transition_records) == 2
    assert {
        (
            row["uri"],
            row["start_uri"],
            row["end_uri"],
            row["source_uri"],
            row["exchange_uri"],
        )
        for row in transition_records
    } == {
        (
            transition.uri,
            transition.source_state_uri,
            transition.target_state_uri,
            transition.source_transition_uri,
            transition.message_exchange_uri,
        )
        for transition in saved.transitions
    }

    rejected_review = BehaviorReview(
        **{
            **review.model_dump(),
            "decision": "rejected",
        }
    )
    rejected_review_id = save_behavior_review(rejected_review)

    with pytest.raises(
        ValueError,
        match="Only confirmed behavior reviews",
    ):
        assemble_saved_behavior(rejected_review_id)

@pytest.mark.integration
def test_rejects_missing_canonical_behavior():
    missing_uri = f"urn:pass:canonical:behavior:{uuid4()}"

    with pytest.raises(
        ValueError,
        match="No canonical behavior found",
    ):
        get_canonical_behavior(missing_uri)

