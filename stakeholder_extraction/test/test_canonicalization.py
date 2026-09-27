import pytest

from stakeholder_extraction.canonicalization import create_canonical_subject
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