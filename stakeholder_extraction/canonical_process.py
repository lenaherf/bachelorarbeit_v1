"""Create an explicit selection of elements for a canonical process."""

from urllib.parse import quote

from stakeholder_extraction.canonical_models import CanonicalProcessModel, CanonicalSubject, CanonicalSubjectBehavior, \
    CanonicalMessageExchange, CanonicalMessageSpecification, CanonicalBehaviorFragment


def _ordered_unique_uris(uris: list[str]) -> tuple[str, ...]:
    """Reject empty or repeated references and return a stable order."""

    if any(not uri.strip() for uri in uris):
        raise ValueError("URIs must not be empty")

    if len(set(uris)) != len(uris):
        raise ValueError("URIs must be unique")

    return tuple(sorted(uris))

def create_canonical_process_model(
        *,
        model_id: str,
        label: str,
        subject_uris: list[str],
        behavior_uris: list[str],
        message_specification_uris: list[str],
        message_exchange_uris: list[str],
) -> CanonicalProcessModel:
    """Create a process identity and its explicit membership."""

    if not model_id.strip():
        raise ValueError("model_id must not be empty")

    if not label.strip():
        raise ValueError("label must not be empty")

    if not subject_uris:
        raise ValueError("subject_uris must not be empty")

    encoded_id = quote(model_id.strip(), safe="")

    return CanonicalProcessModel(
        uri=f"urn:pass:canonical:process:{encoded_id}",
        model_component_id=f"canonical:process:{encoded_id}",
        label=label.strip(),
        subject_uris=_ordered_unique_uris(subject_uris),
        behavior_uris=_ordered_unique_uris(behavior_uris),
        message_specification_uris=_ordered_unique_uris(
            message_specification_uris
        ),
        message_exchange_uris=_ordered_unique_uris(
            message_exchange_uris
        ),
    )

def _check_selected_uris(
        selected: tuple[str, ...],
        supplied: list[str],
        *,
        element_type: str,
) -> None:
    """Require exactly one supplied object for every selected URI."""

    if len(set(selected)) != len(selected):
        raise ValueError(f"Duplicate selected {element_type} URIs.")

    if len(set(supplied)) != len(supplied):
        raise ValueError(f"Duplicate supplied {element_type} URIs.")

    if set(selected) != set(supplied):
        raise ValueError(f"Supplied {element_type} must exactly match the selection.")


def validate_process_membership(
        model: CanonicalProcessModel,
        *,
        subjects: list[CanonicalSubject],
        behaviors: list[CanonicalSubjectBehavior],
        messages: list[CanonicalMessageSpecification],
        exchanges: list[CanonicalMessageExchange],
) -> None:
    """Check selected elements and their immediate references."""

    _check_selected_uris(
        model.subject_uris,
        [item.uri for item in subjects],
        element_type="subjects",
    )

    _check_selected_uris(
        model.behavior_uris,
        [item.uri for item in behaviors],
        element_type="behaviors",
    )

    _check_selected_uris(
        model.message_specification_uris,
        [item.uri for item in messages],
        element_type="messages",
    )

    _check_selected_uris(
        model.message_exchange_uris,
        [item.uri for item in exchanges],
        element_type="exchanges",
    )

    subjects_by_uri = {subject.uri: subject for subject in subjects}
    message_uris = {message.uri for message in messages}

    behavior_owners = set()

    for behavior in behaviors:
        if behavior.subject_uri not in subjects_by_uri:
            raise ValueError("A selected behavior must belong to a selected subject.")

        owner = subjects_by_uri[behavior.subject_uri]

        if owner.pass_type != "FullySpecifiedSubject":
            raise ValueError("A behavior owner must be a FullySpecifiedSubject.")

        if behavior.source_subject_uri not in owner.source_subject_uris:
            raise ValueError("Behavior provenance must match its canonical subject.")

        #Prototype policy: select one behavior per subject
        if owner.uri in behavior_owners:
            raise ValueError("Select at most one behavior per subject.")

        behavior_owners.add(owner.uri)

    for exchange in exchanges:
        if (
                exchange.sender_uri not in subjects_by_uri
                or exchange.receiver_uri not in subjects_by_uri
        ):
            raise ValueError("Exchange participants must be selected subjects.")

        if exchange.message_specification_uri not in message_uris:
            raise ValueError("An exchange must reference a selected message.")

def validate_process_structure(
        model: CanonicalProcessModel,
        *,
        subjects: list[CanonicalSubject],
        behavior_fragments: list[CanonicalBehaviorFragment],
        messages: list[CanonicalMessageSpecification],
        exchanges: list[CanonicalMessageExchange],
) -> None:
    """Check process membership and references inside selected behaviors."""

    validate_process_membership(
        model,
        subjects=subjects,
        behaviors=[item.behavior for item in behavior_fragments],
        messages=messages,
        exchanges=exchanges,
    )

    message_uris = {message.uri for message in messages}
    exchanges_by_uri = {exchange.uri: exchange for exchange in exchanges}

    seen_element_uris = set()

    transition_types = {
        "ReceiveState": "ReceiveTransition",
        "DoState": "DoTransition",
        "SendState": "SendTransition",
    }

    for fragment in behavior_fragments:
        behavior = fragment.behavior

        # States and transitions must have distinct identities.
        for element in [*fragment.states, *fragment.transitions]:
            if element.uri in seen_element_uris:
                raise ValueError("State and transition URIs must be unique across selected behaviors.")
            seen_element_uris.add(element.uri)

            if element.behavior_uri != behavior.uri:
                raise ValueError("Every state and transition must reference its containing behavior.")

        states_by_uri = {state.uri: state for state in fragment.states}
        for state in fragment.states:
            if state.pass_type == "SendState":
                outgoing_count = sum(
                    transition.source_state_uri == state.uri
                    for transition in fragment.transitions
                )

                if outgoing_count > 1:
                    raise ValueError(
                        f"SendState '{state.label}' must not have "
                        "multiple outgoing transitions."
                    )

        for state in fragment.states:
            if state.performer_uri != behavior.subject_uri:
                raise ValueError("A state's performer must be its behavior owner.")

            if state.pass_type == "DoState":
                if state.message_specification_uri is not None:
                    raise ValueError("A DoState must not reference a message.")


            elif state.pass_type == "SendState":
                if state.message_specification_uri not in message_uris:
                    raise ValueError("A SendState must reference a selected message.")

            elif state.message_specification_uri is not None and state.message_specification_uri not in message_uris:
                raise ValueError("A ReceiveState's fixed message must be a selected message.")

        for transition in fragment.transitions:
            if (
                transition.source_state_uri not in states_by_uri
                or transition.target_state_uri not in states_by_uri
            ):
                raise ValueError("Transition endpoints must belong to the same selected behavior.")

            start = states_by_uri[transition.source_state_uri]

            if transition.pass_type != transition_types[start.pass_type]:
                raise ValueError("The transition type must match its starting state.")

            if transition.pass_type == "DoTransition":
                if transition.message_exchange_uri is not None:
                    raise ValueError("A DoTransition must not reference an exchange.")
                continue

            exchange = exchanges_by_uri.get(transition.message_exchange_uri)

            if exchange is None:
                raise ValueError("A communication transition must reference a selected exchange.")

            if (
                    start.message_specification_uri is not None
                    and exchange.message_specification_uri
                    != start.message_specification_uri
            ):
                raise ValueError("The transition exchange must match its starting state's message.")

            participant_uri = (
                exchange.sender_uri
                if transition.pass_type == "SendTransition"
                else exchange.receiver_uri
            )

            if participant_uri != behavior.subject_uri:
                raise ValueError("The exchange direction must match the behavior owner")
