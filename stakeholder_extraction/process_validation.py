"""Check completeness of the prototype's selected process behaviours."""

from pydantic import BaseModel, ConfigDict, Field
from stakeholder_extraction.canonical_models import CanonicalProcessContents
from stakeholder_extraction.canonical_process import (
    validate_process_structure,
)
from typing import Literal


class ProcessValidationIssue(BaseModel):
    """One problem preventing the prototype's completeness checks passing."""

    model_config = ConfigDict(extra="forbid")

    code: str
    element_uri: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ProcessValidationReport(BaseModel):
    """Results of the prototype's structural and completeness checks."""

    model_config = ConfigDict(extra="forbid")

    model_uri: str
    issues: list[ProcessValidationIssue] = Field(default_factory=list)

    @property
    def passes_completeness_checks(self) -> bool:
        """Return whether the implemented checks found no errors."""
        return not any(
            issue.severity == "error"
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            issue.severity == "warning"
            for issue in self.issues
        )

def _reachable_from(
    starting_uris: set[str],
    adjacency: dict[str, set[str]],
) -> set[str]:
    """Find every state reachable through the supplied connections."""

    visited = set()
    pending = list(starting_uris)

    while pending:
        current = pending.pop()

        if current in visited:
            continue

        visited.add(current)
        pending.extend(adjacency.get(current, set()) - visited)

    return visited


def validate_process_completeness(
    contents: CanonicalProcessContents,
) -> ProcessValidationReport:
    """Report structural and completeness problems.

    These checks do not establish ontology conformance or freedom
    from communication deadlocks.
    """

    report = ProcessValidationReport(model_uri=contents.model.uri)

    def add_issue(
            code: str,
            uri: str,
            message: str,
            severity: Literal["error", "warning"] = "error",
    ) -> None:
        report.issues.append(
            ProcessValidationIssue(
                code=code,
                element_uri=uri,
                message=message,
                severity=severity,
            )
        )

    # First ensure references are usable for graph traversal.
    try:
        validate_process_structure(
            contents.model,
            subjects=contents.subjects,
            behavior_fragments=contents.behavior_fragments,
            messages=contents.messages,
            exchanges=contents.exchanges,
        )
    except ValueError as error:
        add_issue(
            "invalid_structure",
            contents.model.uri,
            str(error),
        )
        return report

    behavior_owners = {
        fragment.behavior.subject_uri
        for fragment in contents.behavior_fragments
    }

    for subject in sorted(contents.subjects, key=lambda item: item.uri):
        if (
            subject.pass_type == "FullySpecifiedSubject"
            and subject.uri not in behavior_owners
        ):
            add_issue(
                "missing_subject_behavior",
                subject.uri,
                "The fully specified subject has no selected behavior.",
            )

    for fragment in sorted(
        contents.behavior_fragments,
        key=lambda item: item.behavior.uri,
    ):
        behavior_uri = fragment.behavior.uri

        if not fragment.states:
            add_issue(
                "empty_behavior",
                behavior_uri,
                "The selected behavior contains no states.",
            )
            continue

        initial_uris = {
            state.uri for state in fragment.states if state.is_initial
        }
        end_uris = {
            state.uri for state in fragment.states if state.is_end
        }

        if len(initial_uris) != 1:
            add_issue(
                "invalid_initial_state_count",
                behavior_uri,
                "The prototype requires exactly one initial state "
                "per behavior.",
            )

        if not end_uris:
            add_issue(
                "missing_end_state",
                behavior_uri,
                "The behavior has no explicitly identified end state.",
            )

        outgoing = {state.uri: set() for state in fragment.states}
        incoming = {state.uri: set() for state in fragment.states}

        for transition in fragment.transitions:
            outgoing[transition.source_state_uri].add(
                transition.target_state_uri
            )
            incoming[transition.target_state_uri].add(
                transition.source_state_uri
            )

        for state in sorted(fragment.states, key=lambda item: item.uri):
            if state.is_end and outgoing[state.uri]:
                add_issue(
                    "end_state_has_outgoing_transition",
                    state.uri,
                    "An end state has an outgoing transition.",
                )

            if not state.is_end and not outgoing[state.uri]:
                add_issue(
                    "non_end_state_without_outgoing_transition",
                    state.uri,
                    "The state stops without being identified "
                    "as an end state.",
                )

        if len(initial_uris) == 1:
            reachable = _reachable_from(initial_uris, outgoing)

            for state in sorted(fragment.states, key=lambda item: item.uri):
                if state.uri not in reachable:
                    add_issue(
                        "unreachable_state",
                        state.uri,
                        "The state cannot be reached from the initial state.",
                    )

        if end_uris:
            # Follow transitions backwards from all end states.
            can_reach_end = _reachable_from(end_uris, incoming)

            for state in sorted(fragment.states, key=lambda item: item.uri):
                if state.uri not in can_reach_end:
                    add_issue(
                        "no_path_to_end",
                        state.uri,
                        "The state has no path to an end state.",
                    )

    # Identify communication represented in the selected behaviours.
    sending_references = set()
    receiving_references = set()

    for fragment in contents.behavior_fragments:
        owner_uri = fragment.behavior.subject_uri

        for transition in fragment.transitions:
            if transition.message_exchange_uri is None:
                continue

            reference = (
                owner_uri,
                transition.message_exchange_uri,
            )

            if transition.pass_type == "SendTransition":
                sending_references.add(reference)

            elif transition.pass_type == "ReceiveTransition":
                receiving_references.add(reference)

    for exchange in sorted(contents.exchanges, key=lambda item: item.uri):
        if len(exchange.source_exchange_uris) == 1:
            add_issue(
                "single_source_exchange",
                exchange.uri,
                "This exchange is supported by only one source view.",
                severity="warning",
            )

        if (exchange.sender_uri, exchange.uri) not in sending_references:
            add_issue(
                "missing_send_transition",
                exchange.uri,
                "The selected sender behavior has no send transition "
                "referencing this exchange.",
                severity="warning",
            )

        if (exchange.receiver_uri, exchange.uri) not in receiving_references:
            add_issue(
                "missing_receive_transition",
                exchange.uri,
                "The selected receiver behavior has no receive transition "
                "referencing this exchange.",
                severity="warning",
            )

    return report