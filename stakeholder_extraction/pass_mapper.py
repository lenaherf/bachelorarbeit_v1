from collections import defaultdict

from stakeholder_extraction.models import StakeholderView, CandidateStateType
from stakeholder_extraction.pass_models import PassModelFragment, PassSubject, PassMessageSpecification, \
    PassMessageExchange, MappingIssue, PassState, PassTransition


# Normalize a name only for reference lookup.
def normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()

# Build a stable URI for an element inside of one StakeholderView.
def make_uri(
        view_id: str,
        element_kind: str,
        source_index: int,
) -> str:
    return (
        f"urn:pass:view:{view_id}:"
        f"{element_kind}:{source_index:03d}"
    )

def make_component_id(
        view_id: str,
        element_kind: str,
        source_index: int,
) -> str:
    return (
        f"{view_id}:"
        f"{element_kind}:"
        f"{source_index:03d}"
    )


# Deterministically map one StakeholderView to a draft model fragment.
def map_view_to_pass_fragment(
        view: StakeholderView,
        *,
        view_id: str,
) -> PassModelFragment:
    if not view_id.strip():
        raise ValueError("view_id must not be empty")

    subjects: list[PassSubject] = []
    message_specifications: list[PassMessageSpecification] = []
    message_exchanges: list[PassMessageExchange] = []
    states: list[PassState] = []
    transitions: list[PassTransition] = []
    mapping_issues: list[MappingIssue] = []

    stakeholder_name = normalize_name(view.stakeholder)

    subjects_by_name: dict[str, list[PassSubject]] = defaultdict(list)

    for index, candidate in enumerate (view.candidate_subjects):
        candidate_name = normalize_name(candidate.name)

        if candidate_name == stakeholder_name:
            pass_type = "FullySpecifiedSubject"
        else:
            pass_type = "InterfaceSubject"

        subject = PassSubject(
            uri=make_uri(view_id, "subject", index),
            model_component_id=make_component_id(view_id, "subject", index),
            label=candidate.name,
            view_id=view_id,
            stakeholder=view.stakeholder,
            evidence=candidate.evidence,
            status=candidate.status,
            source_kind="subject",
            source_index=index,
            pass_type=pass_type,
        )

        subjects.append(subject)

        subjects_by_name[candidate_name].append(subject)

    def resolve_subject(
        name: str | None,
        *,
        source_kind: str,
        source_index: int,
        field: str,
    ) -> PassSubject | None:
        if name is None:
            mapping_issues.append(MappingIssue(
                code=f"missing_{field}",
                source_kind=source_kind,
                source_index=source_index,
                field=field,
                detail=f"No {field} was extracted",
                )
            )
            return None

        normalized = normalize_name(name)
        matches = subjects_by_name.get(normalized, [],)

        if len(matches) == 0:
            mapping_issues.append(MappingIssue(
                code="unknown_subject",
                source_kind=source_kind,
                source_index=source_index,
                field=field,
                detail=f"{field.title()} '{name}' has no matching candidate subject.",
                )
            )
            return None

        if len(matches) > 1:
            mapping_issues.append(
                MappingIssue(
                    code="ambiguous_subject",
                    source_kind=source_kind,
                    source_index=source_index,
                    field=field,
                    detail=f"{field.title()} '{name}' matches {len(matches)} candidate subjects. No candidate was selected automatically.",
                )
            )
            return None

        return matches[0]

    message_specifications_by_name: dict[str, list[PassMessageSpecification]] = defaultdict(list)
    exchanges_by_message_uri: dict[str, list[PassMessageExchange]] = defaultdict(list)

    for index, candidate in enumerate(view.candidate_messages):
        message_specification = None

        if candidate.name is None:
            mapping_issues.append(MappingIssue(
                code="missing_message_name",
                source_kind="message",
                source_index=index,
                field="name",
                detail="No MessageSpecification was created because the message name is missing.",
            ))
        else:
            message_specification = (
                PassMessageSpecification(
                    uri=make_uri(view_id, "message", index),
                    model_component_id=make_component_id(view_id, "message", index),
                    label=candidate.name,
                    view_id=view_id,
                    stakeholder=view.stakeholder,
                    evidence=candidate.evidence,
                    status=candidate.status,
                    source_kind="message",
                    source_index=index,
                )
            )

            message_specifications.append(message_specification)
            message_specifications_by_name[normalize_name(candidate.name)].append(message_specification)

        sender = resolve_subject(
            candidate.sender,
            source_kind="message",
            source_index=index,
            field="sender",
        )

        receiver = resolve_subject(
            candidate.receiver,
            source_kind="message",
            source_index=index,
            field="receiver",
        )

        if (
            message_specification is not None
            and sender is not None
            and receiver is not None
        ):
            exchange = PassMessageExchange(
                uri=make_uri(view_id, "exchange", index),
                model_component_id=make_component_id(view_id, "exchange", index),
                label=f"{sender.label} sends {message_specification.label} to {receiver.label}",
                view_id=view_id,
                stakeholder=view.stakeholder,
                evidence=candidate.evidence,
                status=candidate.status,
                source_kind="message",
                source_index=index,
                sender_uri=sender.uri,
                receiver_uri=receiver.uri,
                message_specification_uri=message_specification.uri
            )

            message_exchanges.append(exchange)
            exchanges_by_message_uri[message_specification.uri].append(exchange)

    state_type_mapping = {
        CandidateStateType.RECEIVE: "ReceiveState",
        CandidateStateType.DO: "DoState",
        CandidateStateType.SEND: "SendState",
    }

    states_by_local_id: dict[str, list[PassState]] = defaultdict(list)

    for index, candidate in enumerate(view.candidate_states):
        performer = resolve_subject(
            candidate.performed_by,
            source_kind="state",
            source_index=index,
            field="performer",
        )

        message_specification = None

        if candidate.message_name is not None:
            message_matches = (
                message_specifications_by_name.get(normalize_name(candidate.message_name), [])
            )

            if len(message_matches) == 0:
                mapping_issues.append(MappingIssue(
                    code="unknown_state_message",
                    source_kind="state",
                    source_index=index,
                    field="message_name",
                    detail=(
                        "State message "
                        f"'{candidate.message_name}' "
                        "has no matching message "
                        "specification."
                    ),
                ))
            elif len(message_matches) > 1:
                mapping_issues.append(MappingIssue(
                    code="ambiguous_state_message",
                    source_kind="state",
                    source_index=index,
                    field="message_name",
                    detail=(
                        "State message "
                        f"'{candidate.message_name}' "
                        f"matches {len(message_matches)} "
                        "message specifications."
                    ),
                ))
            else:
                message_specification = message_matches[0]

        if candidate.state_type in {CandidateStateType.RECEIVE, CandidateStateType.SEND} and candidate.message_name is None:
            mapping_issues.append(MappingIssue(
                code="missing_state_message",
                source_kind="state",
                source_index=index,
                field="message_name",
                detail=(
                    f"{candidate.state_type.value} "
                    "state has no message reference."
                ),
            ))

        if candidate.state_type == CandidateStateType.DO and candidate.message_name is not None:
            mapping_issues.append(MappingIssue(
                code="unexpected_do_state_message",
                source_kind="state",
                source_index=index,
                field="message_name",
                detail=(
                    "A do state must not reference "
                    "a message specification."
                ),
            ))
            message_specification = None

        formal_is_end = candidate.is_end

        if (candidate.state_type == CandidateStateType.SEND and candidate.is_end):
            mapping_issues.append(MappingIssue(
                code="invalid_send_end_state",
                source_kind="state",
                source_index=index,
                field="is_end",
                detail=(
                    "A SendState cannot be an "
                    "EndState in PASS."
                ),
            ))

            formal_is_end = False

        state = PassState(
            uri=make_uri(view_id, "state", index),
            model_component_id=make_component_id(view_id, "state", index),
            label=candidate.name,
            view_id=view_id,
            stakeholder=view.stakeholder,
            evidence=candidate.evidence,
            status=candidate.status,
            source_kind="state",
            source_index=index,
            pass_type=state_type_mapping[candidate.state_type],
            local_id=candidate.local_id,
            performer_uri=performer.uri if performer else None,
            message_specification_uri=message_specification.uri if message_specification else None,
            is_initial=candidate.is_initial,
            is_end=formal_is_end,
        )

        states.append(state)
        states_by_local_id[candidate.local_id].append(state)

        if len(states_by_local_id[candidate.local_id]) > 1:
            mapping_issues.append(MappingIssue(
                code="duplicate_state_local_id",
                source_kind="state",
                source_index=index,
                field="local_id",
                detail=(
                    "Multiple candidate states use "
                    f"local_id '{candidate.local_id}'."
                ),
            ))

    transition_type_mapping = {
        "ReceiveState": "ReceiveTransition",
        "DoState": "DoTransition",
        "SendState": "SendTransition",
    }

    for index, candidate in enumerate(view.candidate_transitions):
        source_matches = states_by_local_id.get(candidate.source_state_id, [])
        target_matches = states_by_local_id.get(candidate.target_state_id, [])

        if len(source_matches) != 1:
            mapping_issues.append(MappingIssue(
                code=(
                    "unknown_transition_source"
                    if len(source_matches) == 0
                    else "ambiguous_transition_source"
                ),
                source_kind="transition",
                source_index=index,
                field="source_state_id",
                detail=(
                    "Transition source "
                    f"'{candidate.source_state_id}' "
                    f"has {len(source_matches)} "
                    "matching states."
                ),
            ))

        if len(target_matches) != 1:
            mapping_issues.append(MappingIssue(
                code=(
                    "unknown_transition_target"
                    if len(target_matches) == 0
                    else "ambiguous_transition_target"
                ),
                source_kind="transition",
                source_index=index,
                field="target_state_id",
                detail=(
                    "Transition target "
                    f"'{candidate.target_state_id}' "
                    f"has {len(target_matches)} "
                    "matching states."
                ),
            ))

        if len(source_matches) != 1 or len(target_matches) != 1:
            continue

        source = source_matches[0]
        target = target_matches[0]

        message_exchange = None

        if source.pass_type in {"ReceiveState", "SendState"} and source.message_specification_uri is not None:
            exchange_matches = exchanges_by_message_uri.get(source.message_specification_uri, [])

            if len(exchange_matches) == 1:
                message_exchange = exchange_matches[0]
            elif len(exchange_matches) == 0:
                mapping_issues.append(MappingIssue(
                    code=(
                        "missing_transition_exchange"
                    ),
                    source_kind="transition",
                    source_index=index,
                    field="message_exchange",
                    detail=(
                        "Communication transition "
                        "has no matching message "
                        "exchange."
                    ),
                ))
            else:
                mapping_issues.append(MappingIssue(
                    code=(
                        "ambiguous_transition_exchange"
                    ),
                    source_kind="transition",
                    source_index=index,
                    field="message_exchange",
                    detail=(
                        "Communication transition "
                        "matches multiple message "
                        "exchanges."
                    ),
                ))

        transition = PassTransition(
            uri=make_uri(view_id, "transition", index),
            model_component_id=make_component_id(view_id, "transition", index),
            label= f"{source.label} to {target.label}",
            view_id=view_id,
            stakeholder=view.stakeholder,
            evidence=candidate.sequence_evidence,
            status=candidate.status,
            source_kind="transition",
            source_index=index,
            pass_type=transition_type_mapping[source.pass_type],
            source_state_uri=source.uri,
            target_state_uri=target.uri,
            message_exchange_uri=message_exchange.uri if message_exchange else None,
        )

        transitions.append(transition)

    return PassModelFragment(
        view_id=view_id,
        stakeholder=view.stakeholder,
        base_uri=f"urn:pass:view:{view_id}",
        subjects=subjects,
        message_specifications=message_specifications,
        message_exchanges=message_exchanges,
        states=states,
        transitions=transitions,
        mapping_issues=mapping_issues,
    )
