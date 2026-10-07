import pytest

from stakeholder_extraction.canonicalization import create_canonical_subject, create_canonical_message_specification, \
    create_canonical_message_exchange, create_single_source_canonical_message, create_single_source_canonical_exchange
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
