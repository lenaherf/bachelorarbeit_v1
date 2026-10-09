import pytest

from datetime import datetime, timezone
from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.canonical_behavior import assemble_canonical_behavior, assemble_reviewed_behavior
from stakeholder_extraction.canonicalization import create_canonical_subject, create_canonical_message_specification, \
    create_canonical_message_exchange, create_single_source_canonical_message, create_single_source_canonical_exchange, \
    create_canonical_state, create_canonical_transition, create_canonical_subject_behavior
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.test.test_pass_mapper import make_complaint_view
from stakeholder_extraction.test.test_reconciliation import make_customer_complaint_view


def test_creates_canonical_subject():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    customer_from_customer_view = customer_fragment.subjects[0]
    customer_from_service_view = service_fragment.subjects[0]
    canonical = create_canonical_subject(customer_from_customer_view, customer_from_service_view)

    assert canonical.label == "Customer"
    assert canonical.pass_type == "FullySpecifiedSubject"
    assert canonical.status == "confirmed"
    assert canonical.source_subject_uris == tuple(sorted(
        [customer_from_customer_view.uri, customer_from_service_view.uri]
    ))

def test_canonical_subject_is_order_independent():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    left = customer_fragment.subjects[0]
    right = service_fragment.subjects[0]
    first = create_canonical_subject(left, right)
    second = create_canonical_subject(right, left)

    assert first == second

def test_rejects_unequal_subject_names():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    customer = customer_fragment.subjects[0]
    customer_service = customer_fragment.subjects[1]

    with pytest.raises(ValueError, match="equal normalized labels",):
        create_canonical_subject(customer, customer_service)

def test_creates_canonical_message_exchange():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")

    canonical_customer = create_canonical_subject(customer_fragment.subjects[0], service_fragment.subjects[0])
    canonical_service = create_canonical_subject(customer_fragment.subjects[1], service_fragment.subjects[1])

    canonical_message = create_canonical_message_specification(
        customer_fragment.message_specifications[0],
        service_fragment.message_specifications[0]
    )
    canonical_exchange = create_canonical_message_exchange(
        customer_fragment.message_exchanges[0],
        service_fragment.message_exchanges[0],
        message=canonical_message,
        sender=canonical_customer,
        receiver=canonical_service
    )

    assert canonical_message.label == "Complaint"
    assert canonical_message.pass_type == "MessageSpecification"

    assert canonical_exchange.label == "Customer sends Complaint to Customer Service"
    assert canonical_exchange.sender_uri == canonical_customer.uri
    assert canonical_exchange.receiver_uri == canonical_service.uri
    assert canonical_exchange.message_specification_uri == canonical_message.uri
    assert len(canonical_message.source_message_uris) == 2
    assert len(canonical_exchange.source_exchange_uris) == 2

def test_creates_single_source_canonical_message():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    canonical_customer = create_canonical_subject(customer_fragment.subjects[0], service_fragment.subjects[0])
    canonical_service = create_canonical_subject(customer_fragment.subjects[1], service_fragment.subjects[1])

    source_message = service_fragment.message_specifications[1]
    source_exchange = service_fragment.message_exchanges[1]
    canonical_message = create_single_source_canonical_message(source_message)
    canonical_exchange = create_single_source_canonical_exchange(
        source_exchange,
        message=canonical_message,
        sender=canonical_service,
        receiver=canonical_customer)
    assert canonical_message.label == "Response"
    assert canonical_message.source_message_uris == (source_message.uri, )
    assert canonical_exchange.label == "Customer Service sends Response to Customer"
    assert canonical_exchange.source_exchange_uris == (source_exchange.uri, )
    assert canonical_exchange.sender_uri == canonical_service.uri
    assert canonical_exchange.receiver_uri == canonical_customer.uri
    assert canonical_message.uri.startswith("urn:pass:canonical:message:")
    assert canonical_exchange.uri.startswith("urn:pass:canonical:exchange:")

def test_creates_canonical_receive_state():
    customer_fragment, service_fragment, service, behavior = _make_service_behavior_context()
    complaint = create_canonical_message_specification(customer_fragment.message_specifications[0], service_fragment.message_specifications[0])

    source = service_fragment.states[0]

    canonical = create_canonical_state(
        source,
        behavior=behavior,
        performer=service,
        message=complaint,
    )

    assert canonical.pass_type == "ReceiveState"
    assert canonical.label == source.label
    assert canonical.behavior_uri == behavior.uri
    assert canonical.performer_uri == service.uri
    assert canonical.message_specification_uri == complaint.uri
    assert canonical.source_state_uri == source.uri
    assert canonical.is_initial == source.is_initial
    assert canonical.is_end == source.is_end
    assert canonical.uri != source.uri

    #Identical inputs must produce the same canonical state.
    assert canonical == create_canonical_state(
        source,
        behavior=behavior,
        performer=service,
        message=complaint,
    )

    # A response message cannot replace the complaint reference.
    response = create_canonical_message_specification(
        customer_fragment.message_specifications[1],
        service_fragment.message_specifications[1]
    )

    with pytest.raises(ValueError, match="must include the source message",):
        create_canonical_state(
            source,
            behavior=behavior,
            performer=service,
            message=response,
        )

def _make_service_behavior_context():
    """Create source fragments and a canonical service behavior."""

    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    service = create_canonical_subject(customer_fragment.subjects[1], service_fragment.subjects[1])

    behavior = create_canonical_subject_behavior(service_fragment.subjects[1], subject=service)

    return customer_fragment, service_fragment, service, behavior

def test_creates_canonical_do_state():
    _, service_fragment, service, behavior = _make_service_behavior_context()
    source = service_fragment.states[1]
    canonical = create_canonical_state(
        source,
        behavior=behavior,
        performer=service,
    )

    assert canonical.pass_type == "DoState"
    assert canonical.label == "Review complaint"
    assert canonical.behavior_uri == behavior.uri
    assert canonical.performer_uri == service.uri
    assert canonical.message_specification_uri is None
    assert canonical.source_state_uri == source.uri

def test_creates_canonical_send_state():
    customer_fragment, service_fragment, service, behavior = _make_service_behavior_context()

    response = create_canonical_message_specification(
        customer_fragment.message_specifications[1],
        service_fragment.message_specifications[1]
    )

    source = service_fragment.states[2]

    canonical = create_canonical_state(
        source,
        behavior=behavior,
        performer=service,
        message=response,
    )

    assert canonical.pass_type == "SendState"
    assert canonical.label == "Send response"
    assert canonical.behavior_uri == behavior.uri
    assert canonical.performer_uri == service.uri
    assert canonical.message_specification_uri == response.uri
    assert canonical.source_state_uri == source.uri
    assert canonical.is_end == source.is_end

    # Communication state cannot be mapped without its message
    with pytest.raises(ValueError, match="requires a canonical message",):
        create_canonical_state(
            source,
            behavior=behavior,
            performer=service,
        )

def test_rejects_message_for_canonical_do_state():
    customer_fragment, service_fragment, service, behavior = _make_service_behavior_context()
    complaint = create_canonical_message_specification(
        customer_fragment.message_specifications[0],
        service_fragment.message_specifications[0]
    )

    with pytest.raises(ValueError, match="A DoState must not reference a message",):
        create_canonical_state(
            service_fragment.states[1],
            behavior=behavior,
            performer=service,
            message=complaint,
        )

def test_creates_canonical_do_transition():
    customer_fragment, service_fragment, service, behavior = _make_service_behavior_context()

    response = create_canonical_message_specification(
        customer_fragment.message_specifications[1],
        service_fragment.message_specifications[1],
    )

    review = create_canonical_state(
        service_fragment.states[1],
        behavior=behavior,
        performer=service,
    )

    send = create_canonical_state(
        service_fragment.states[2],
        behavior=behavior,
        performer=service,
        message=response,
    )

    source = service_fragment.transitions[1]

    canonical = create_canonical_transition(
        source,
        behavior=behavior,
        start=review,
        end=send,
    )

    assert canonical.pass_type == "DoTransition"
    assert canonical.behavior_uri == behavior.uri
    assert canonical.source_state_uri == review.uri
    assert canonical.target_state_uri == send.uri
    assert canonical.message_exchange_uri is None
    assert canonical.source_transition_uri == source.uri
    assert canonical.uri != source.uri

    # Repeating the conversion must preserve identity and content.
    assert canonical == create_canonical_transition(
        source,
        behavior=behavior,
        start=review,
        end=send,
    )

    # Reversing the endpoints must be rejected.
    with pytest.raises(
            ValueError,
            match="starting state must represent the source endpoint",
    ):
        create_canonical_transition(
            source,
            behavior=behavior,
            start=send,
            end=review,
        )

    # A target from another behaviour must also be rejected.
    other_behavior_state = send.model_copy(
        update={"behavior_uri": "urn:pass:canonical:behavior:other"}
    )

    with pytest.raises(
            ValueError,
            match="Both states must belong to the selected behaviour",
    ):
        create_canonical_transition(
            source,
            behavior=behavior,
            start=review,
            end=other_behavior_state,
        )

@pytest.mark.parametrize(
    ("perspective", "expected_type"),
    [
        ("customer", "SendTransition"),
        ("service", "ReceiveTransition"),
    ],
)
def test_creates_canonical_communication_transition(
    perspective,
    expected_type,
):
    customer_fragment, service_fragment, service, service_behavior = _make_service_behavior_context()
    customer = create_canonical_subject(
        customer_fragment.subjects[0],
        service_fragment.subjects[0],
    )
    complaint = create_canonical_message_specification(
        customer_fragment.message_specifications[0],
        service_fragment.message_specifications[0],)

    complaint_exchange = create_canonical_message_exchange(
        customer_fragment.message_exchanges[0],
        service_fragment.message_exchanges[0],
        message=complaint,
        sender=customer,
        receiver=service,
    )

    if perspective == "customer":
        fragment = customer_fragment
        performer = customer

        behavior = create_canonical_subject_behavior(
            customer_fragment.subjects[0],
            subject=customer,
        )

        # The customer's next state receives the Response.
        end_message = create_canonical_message_specification(
            customer_fragment.message_specifications[1],
            service_fragment.message_specifications[1],
        )
    else:
        fragment = service_fragment
        performer = service
        behavior = service_behavior

        # The service's next state reviews the complaint.
        end_message = None

    start = create_canonical_state(
        fragment.states[0],
        behavior=behavior,
        performer=performer,
        message=complaint,
    )

    end = create_canonical_state(
        fragment.states[1],
        behavior=behavior,
        performer=performer,
        message=end_message,
    )

    source = fragment.transitions[0]

    canonical = create_canonical_transition(
        source,
        behavior=behavior,
        start=start,
        end=end,
        exchange=complaint_exchange,
    )

    assert canonical.pass_type == expected_type
    assert canonical.behavior_uri == behavior.uri
    assert canonical.source_state_uri == start.uri
    assert canonical.target_state_uri == end.uri
    assert canonical.message_exchange_uri == complaint_exchange.uri
    assert canonical.source_transition_uri == source.uri

    # Repeating the conversion must produce the same result.
    assert canonical == create_canonical_transition(
        source,
        behavior=behavior,
        start=start,
        end=end,
        exchange=complaint_exchange,
    )

    # Communication transitions must not silently lose their exchange.
    with pytest.raises(
            ValueError,
            match="requires a canonical exchange",
    ):
        create_canonical_transition(
            source,
            behavior=behavior,
            start=start,
            end=end,
        )

    # Deliberately reverse the exchange to test direction validation.
    reversed_exchange = complaint_exchange.model_copy(
        update={
            "sender_uri": complaint_exchange.receiver_uri,
            "receiver_uri": complaint_exchange.sender_uri,
        }
    )

    with pytest.raises(
            ValueError,
            match="exchange direction must match",
    ):
        create_canonical_transition(
            source,
            behavior=behavior,
            start=start,
            end=end,
            exchange=reversed_exchange,
        )

def test_creates_canonical_subject_behavior():
    customer_fragment = map_view_to_pass_fragment(make_customer_complaint_view(), view_id="customer-view")
    service_fragment = map_view_to_pass_fragment(make_complaint_view(), view_id="service-view")
    service = create_canonical_subject(
        customer_fragment.subjects[1],
        service_fragment.subjects[1],
    )
    source = service_fragment.subjects[1]

    behavior = create_canonical_subject_behavior(source, subject=service)

    assert behavior.pass_type == "SubjectBehavior"
    assert behavior.label == "Customer Service behaviour"
    assert behavior.subject_uri == service.uri
    assert behavior.source_view_id == service_fragment.view_id
    assert behavior.source_subject_uri == source.uri
    assert behavior.uri.startswith("urn:pass:canonical:behavior:")

    assert behavior == create_canonical_subject_behavior(source, subject=service,)

    # The customer's view only describes service as an interface.
    with pytest.raises(
        ValueError,
        match="source must be a FullySpecifiedSubject",
    ):
        create_canonical_subject_behavior(
            customer_fragment.subjects[1],
            subject=service,
        )

    customer = create_canonical_subject(
        customer_fragment.subjects[0],
        service_fragment.subjects[0],
    )

    #Service behavior cannot be assigned to the canonical customer.
    with pytest.raises(
        ValueError,
        match="must include the source subject",
    ):
        create_canonical_subject_behavior(
            source,
            subject=customer,
        )

def test_assembles_service_behavior():
    customer_fragment, service_fragment, service, _ = _make_service_behavior_context()

    customer = create_canonical_subject(
        customer_fragment.subjects[0],
        service_fragment.subjects[0],
    )

    complaint = create_canonical_message_specification(
        customer_fragment.message_specifications[0],
        service_fragment.message_specifications[0],
    )

    response = create_canonical_message_specification(
        customer_fragment.message_specifications[1],
        service_fragment.message_specifications[1],
    )

    complaint_exchange = create_canonical_message_exchange(
        customer_fragment.message_exchanges[0],
        service_fragment.message_exchanges[0],
        message=complaint,
        sender=customer,
        receiver=service,
    )

    result = assemble_canonical_behavior(
        service_fragment,
        source_subject_uri=service_fragment.subjects[1].uri,
        subject=service,
        messages=[complaint, response],
        exchanges=[complaint_exchange],
    )

    assert result.behavior.subject_uri == service.uri
    assert len(result.states) == 3
    assert len(result.transitions) == 2

    states_by_source = {
        state.source_state_uri: state
        for state in result.states
    }

    for transition, original in zip(
        result.transitions,
        service_fragment.transitions,
        strict=True,
    ):
        assert transition.source_transition_uri == original.uri
        assert transition.source_state_uri == states_by_source[original.source_state_uri].uri
        assert transition.target_state_uri == states_by_source[original.target_state_uri].uri

    assert all(
        state.behavior_uri == result.behavior.uri
        for state in result.states
    )
    assert all(
        transition.behavior_uri == result.behavior.uri
        for transition in result.transitions
    )

    # Missing canonical communication must block assembly.
    with pytest.raises(
        ValueError,
        match="exactly one canonical message",
    ):
        assemble_canonical_behavior(
            service_fragment,
            source_subject_uri=service_fragment.subjects[1].uri,
            subject=service,
            messages=[complaint],  # Response is missing.
            exchanges=[complaint_exchange],
        )

    # Input list order must not change the assembled result.
    reordered_fragment = service_fragment.model_copy(
        update={
            "states": list(reversed(service_fragment.states)),
            "transitions": list(reversed(service_fragment.transitions)),
        }
    )

    second_result = assemble_canonical_behavior(
        reordered_fragment,
        source_subject_uri=service_fragment.subjects[1].uri,
        subject=service,
        messages=[response, complaint],
        exchanges=[complaint_exchange],
    )

    assert second_result == result

    # Simulate two canonical identities claiming the same source message.
    duplicate_complaint = complaint.model_copy(
        update={
            "uri": "urn:pass:canonical:message:duplicate",
            "model_component_id": "canonical:message:duplicate",
        }
    )

    with pytest.raises(
            ValueError,
            match="exactly one canonical message",
    ):
        assemble_canonical_behavior(
            service_fragment,
            source_subject_uri=service_fragment.subjects[1].uri,
            subject=service,
            messages=[complaint, duplicate_complaint, response],
            exchanges=[complaint_exchange],
        )

    # A transition must not point to a state outside this behaviour.
    broken_transition = service_fragment.transitions[0].model_copy(
        update={
            "target_state_uri": "urn:pass:view:other:state:000",
        }
    )

    broken_fragment = service_fragment.model_copy(
        update={
            "transitions": [
                broken_transition,
                *service_fragment.transitions[1:],
            ],
        }
    )

    with pytest.raises(
            ValueError,
            match="Both transition endpoints must belong",
    ):
        assemble_canonical_behavior(
            broken_fragment,
            source_subject_uri=service_fragment.subjects[1].uri,
            subject=service,
            messages=[complaint, response],
            exchanges=[complaint_exchange],
        )

    review = BehaviorReview(
        source_view_id=service_fragment.view_id,
        source_subject_uri=service_fragment.subjects[1].uri,
        canonical_subject_uri=service.uri,
        decision="confirmed",
        reviewed_by="admin-test",
        reviewed_at=datetime.now(timezone.utc),
    )

    reviewed_result = assemble_reviewed_behavior(
        service_fragment,
        review=review,
        subject=service,
        messages=[complaint, response],
        exchanges=[complaint_exchange],
    )

    assert reviewed_result == result

    # A rejected review must block assembly.
    rejected_review = BehaviorReview(
        **{
            **review.model_dump(),
            "decision": "rejected",
        }
    )

    with pytest.raises(
            ValueError,
            match="Only confirmed behavior reviews",
    ):
        assemble_reviewed_behavior(
            service_fragment,
            review=rejected_review,
            subject=service,
            messages=[complaint, response],
            exchanges=[complaint_exchange],
        )

    # A confirmation must not apply to another view, owner, or source subject.
    invalid_reviews = [
        (
            {"source_view_id": "another-view"},
            "supplied source view",
        ),
        (
            {"canonical_subject_uri": customer.uri},
            "supplied canonical subject",
        ),
        (
            {"source_subject_uri": "urn:pass:view:missing:subject:000"},
            "Select exactly one source",
        ),
    ]

    for changes, expected_error in invalid_reviews:
        invalid_review = BehaviorReview(
            **{
                **review.model_dump(),
                **changes,
            }
        )

        with pytest.raises(ValueError, match=expected_error):
            assemble_reviewed_behavior(
                service_fragment,
                review=invalid_review,
                subject=service,
                messages=[complaint, response],
                exchanges=[complaint_exchange],
            )
