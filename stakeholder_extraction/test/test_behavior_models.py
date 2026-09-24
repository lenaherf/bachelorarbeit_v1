from stakeholder_extraction.models import CandidateState, CandidateStateType, CandidateTransition
from stakeholder_extraction.pass_models import PassState, PassTransition


def test_creates_candidate_behavior_structure():
    receive_state = CandidateState(
        local_id="state-1",
        name="Receive complaint",
        state_type=CandidateStateType.RECEIVE,
        performed_by="Customer Service",
        message_name="Complaint",
        is_initial=True,
        evidence=(
            "I receive a complaint from the customer"
        ),
    )

    review_state = CandidateState(
        local_id="state-2",
        name="Review complaint",
        state_type=CandidateStateType.DO,
        performed_by="Customer Service",
        evidence="I then review the complaint",
    )

    transition = CandidateTransition(
        source_state_id="state-1",
        target_state_id="state-2",
        sequence_evidence=(
            "I receive a complaint from the customer. "
            "I then review the complaint"
        ),
    )

    assert receive_state.state_type == CandidateStateType.RECEIVE
    assert receive_state.is_initial is True
    assert review_state.state_type == CandidateStateType.DO
    assert review_state.message_name is None
    assert transition.source_state_id == "state-1"
    assert transition.target_state_id == "state-2"

def test_creates_formal_pass_state_and_transition():
    receive_state = PassState(
        uri="urn:pass:view:test:state:000",
        model_component_id="test:state:000",
        label="Receive complaint",
        view_id="test",
        stakeholder="Customer Service",
        evidence="Customer Service receives a complaint.",
        status="proposed",
        source_kind="state",
        source_index=0,
        pass_type="ReceiveState",
        local_id="state-1",
        performer_uri=(
            "urn:pass:view:test:subject:000"
        ),
        message_specification_uri=(
            "urn:pass:view:test:message:000"
        ),
        is_initial=True,
        is_end=False,
    )

    transition = PassTransition(
        uri="urn:pass:view:test:transition:000",
        model_component_id=(
            "test:transition:000"
        ),
        label=(
            "Receive complaint to Review complaint"
        ),
        view_id="test",
        stakeholder="Customer Service",
        evidence=(
            "Customer Service receives a complaint. "
            "Customer Service reviews the complaint."
        ),
        status="proposed",
        source_kind="transition",
        source_index=0,
        pass_type="ReceiveTransition",
        source_state_uri=receive_state.uri,
        target_state_uri=(
            "urn:pass:view:test:state:001"
        ),
        message_exchange_uri=(
            "urn:pass:view:test:exchange:000"
        ),
    )

    assert receive_state.pass_type == "ReceiveState"
    assert receive_state.is_initial is True
    assert transition.pass_type == "ReceiveTransition"
    assert transition.source_state_uri == receive_state.uri