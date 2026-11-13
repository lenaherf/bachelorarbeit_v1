import pytest

from stakeholder_extraction.examples.complaint import (
    make_complete_customer_complaint_view,
    make_complete_service_complaint_view,
)
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment


@pytest.mark.parametrize(
    ("factory", "state_count", "transition_count", "last_transition_type"),
    [
        (
            make_complete_customer_complaint_view,
            3,
            2,
            "ReceiveTransition",
        ),
        (
            make_complete_service_complaint_view,
            4,
            3,
            "SendTransition",
        ),
    ],
)
def test_maps_complete_complaint_behavior(
    factory,
    state_count,
    transition_count,
    last_transition_type,
):
    fragment = map_view_to_pass_fragment(
        factory(),
        view_id="complete-complaint-test",
    )

    assert fragment.mapping_issues == []
    assert len(fragment.states) == state_count
    assert len(fragment.transitions) == transition_count

    initial_states = [
        state for state in fragment.states if state.is_initial
    ]
    end_states = [
        state for state in fragment.states if state.is_end
    ]

    assert len(initial_states) == 1
    assert len(end_states) == 1
    assert end_states[0].pass_type == "DoState"

    # Verify the complete linear chain, including its final transition.
    for index, transition in enumerate(fragment.transitions):
        assert transition.source_state_uri == fragment.states[index].uri
        assert transition.target_state_uri == fragment.states[index + 1].uri

    assert fragment.transitions[-1].pass_type == last_transition_type
    assert (
        fragment.transitions[-1].target_state_uri
        == end_states[0].uri
    )