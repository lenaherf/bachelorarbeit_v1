"""Assemble canonical behavior from a selected stakeholder fragment."""
from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.canonical_models import CanonicalState, CanonicalSubject, CanonicalMessageSpecification, \
    CanonicalMessageExchange, CanonicalBehaviorFragment
from stakeholder_extraction.canonicalization import create_canonical_subject_behavior, create_canonical_transition, \
    create_canonical_state
from stakeholder_extraction.pass_models import PassModelFragment


def assemble_canonical_behavior(
        fragment: PassModelFragment,
        *,
        source_subject_uri: str,
        subject: CanonicalSubject,
        messages: list[CanonicalMessageSpecification],
        exchanges: list[CanonicalMessageExchange]
) -> CanonicalBehaviorFragment:
    """Assemble behavior using existing canonical communication."""

    sources = [candidate for candidate in fragment.subjects
               if candidate.uri == source_subject_uri]

    if len(sources) != 1:
        raise ValueError("Select exactly one source.")

    source_subject = sources[0]

    if source_subject.view_id != fragment.view_id:
        raise ValueError("Source subject must belong to the fragment.")

    if fragment.mapping_issues:
        raise ValueError("Mapping issues must be resolved first.")

    behavior = create_canonical_subject_behavior(source_subject, subject=subject)
    source_states = [state for state in fragment.states
                     if state.performer_uri == source_subject_uri]

    if not source_states:
        raise ValueError("The selected subject has no states.")

    source_state_uris = {state.uri for state in source_states}

    if len(source_state_uris) != len(source_states):
        raise ValueError("Source state uris must be unique.")

    states_by_source = {}

    for source_state in sorted(source_states, key=lambda item: item.uri):
        message = None

        if source_state.message_specification_uri is not None:
            matches = [
                candidate for candidate in messages
                if source_state.message_specification_uri in candidate.source_message_uris
            ]
            if len(matches) != 1:
                raise ValueError("Each states message must resolve to exactly one canonical message.")

            message = matches[0]

        states_by_source[source_state.uri] = create_canonical_state(
            source_state,
            behavior=behavior,
            performer=subject,
            message=message,
        )

    source_transitions = [
        transition for transition in fragment.transitions
        if (
            transition.source_state_uri in source_state_uris
            or transition.target_state_uri in source_state_uris
        )
    ]

    if len({item.uri for item in source_transitions}) != len(source_transitions):
        raise ValueError("Source transition URIs must be unique..")

    transitions = []

    for source_transition in sorted(source_transitions, key=lambda item: item.uri):
        if(
            source_transition.source_state_uri not in states_by_source
            or source_transition.target_state_uri not in states_by_source
        ):
            raise ValueError("Both transition endpoints must belong to the selected subject's states.")

        exchange = None

        if source_transition.message_exchange_uri is not None:
            matches = [
                candidate for candidate in exchanges
                if source_transition.message_exchange_uri in candidate.source_exchange_uris
            ]

            if len(matches) != 1:
                raise ValueError("Each transition exchange message must resolve to exactly one canonical exchange.")

            exchange = matches[0]

        transitions.append(
            create_canonical_transition(
                source_transition,
                behavior=behavior,
                start=states_by_source[source_transition.source_state_uri],
                end=states_by_source[source_transition.target_state_uri],
                exchange=exchange,
            )
        )

    return CanonicalBehaviorFragment(
        behavior=behavior,
        states=list(states_by_source.values()),
        transitions=transitions,
    )

def assemble_reviewed_behavior(
        fragment: PassModelFragment,
        *,
        review: BehaviorReview,
        subject: CanonicalSubject,
        messages: list[CanonicalMessageSpecification],
        exchanges: list[CanonicalMessageExchange],
) -> CanonicalBehaviorFragment:
    """Check a behavior review before assembling its selected source."""

    if review.decision != "confirmed":
        raise ValueError("Only confirmed behavior reviews allow assembly.")

    if review.source_view_id != fragment.view_id:
        raise ValueError("The review must reference the supplied source view.")

    if review.canonical_subject_uri != subject.uri:
        raise ValueError("The review must reference the supplied canonical subject.")

    #Assembler checks that this source subject exists in the fragment and belongs to the supplied canonical subject

    return assemble_canonical_behavior(
        fragment,
        source_subject_uri=review.source_subject_uri,
        subject=subject,
        messages=messages,
        exchanges=exchanges,
    )