"""
Compare separate PASS fragments and produce reviewable proposals.

This module never merges or modifies the input fragments.
It only identifies possible correspondences and inconsistencies between them.
"""

from hashlib import sha256

from stakeholder_extraction.pass_mapper import normalize_name
from stakeholder_extraction.pass_models import PassModelFragment, PassMessageExchange
from stakeholder_extraction.reconciliation_models import ReconciliationProposal, ReconciliationProposalType

"""
Create a stable URI for one reconciliation proposal.
The identifier is derived from the proposal type, view ids, and referenced element URIs.
Sorting the two sides makes the identifier independent of the order in which the fragments are compared.
"""
def make_proposal_id(
    *,
    proposal_type: ReconciliationProposalType,
    left_view_id: str,
    right_view_id: str,
    left_element_uri: str | None,
    right_element_uri: str | None,
) -> str:
    # Swapping left and right does not produce a second identifier.
    sides = sorted(
        [
            (left_view_id, left_element_uri or "",),
            (right_view_id, right_element_uri or "",),
        ]
    )

    source = "|".join(
        [proposal_type, sides[0][0], sides[0][1], sides[1][0], sides[1][1],]
    )

    # Hash the long comparison description into a compact ID.
    digest = sha256(source.encode("utf-8")).hexdigest()[:16]

    return f"urn:pass:reconciliation:proposal:{digest}"

"""
Propose equivalence for subjects with equal normalized labels.
Even for duplicate subject names, this function does not automatically choose one.
"""
def _compare_equivalent_subjects(
        left: PassModelFragment,
        right: PassModelFragment,
) -> list[ReconciliationProposal]:
    proposals: list[ReconciliationProposal] = []

    for left_subject in left.subjects:
        left_name = normalize_name(left_subject.label)

        if not left_name:
            continue

        for right_subject in right.subjects:
            right_name = normalize_name(right_subject.label)

            if left_name != right_name:
                continue

            proposal_id = make_proposal_id(
                proposal_type="equivalent_subject",
                left_view_id=left.view_id,
                right_view_id=right.view_id,
                left_element_uri=left_subject.uri,
                right_element_uri=right_subject.uri,
            )

            proposals.append(
                ReconciliationProposal(
                    proposal_id=proposal_id,
                    proposal_type="equivalent_subject",
                    left_view_id=left.view_id,
                    right_view_id=right.view_id,
                    left_element_uri=left_subject.uri,
                    right_element_uri=right_subject.uri,
                    explanation=(f"Both subjects have the normalized name '{left_name}'."
                    ),
                )
            )

    return proposals

"""
Return the normalized identity of a message exchange.
The key consists of the message name, sender name and receiver name.
"""
def _exchange_key(
        fragment: PassModelFragment,
        exchange: PassMessageExchange,
) -> tuple[str, str, str] | None:
    subjects_by_uri = {subject.uri: subject for subject in fragment.subjects}
    messages_by_uri = {message.uri: message for message in fragment.message_specifications}
    sender = subjects_by_uri.get(exchange.sender_uri)
    receiver = subjects_by_uri.get(exchange.receiver_uri)
    message = messages_by_uri.get(exchange.message_specification_uri)

    if (
        sender is None or receiver is None or message is None
    ):
        return None

    return (
        normalize_name(message.label),
        normalize_name(sender.label),
        normalize_name(receiver.label),
    )

"""
Return the PASS state types that reference an exchange's message.
"""
def _communication_state_types(
        fragment: PassModelFragment,
        exchange: PassMessageExchange,
) -> set[str]:
    return {
        state.pass_type for state in fragment.states
        if state.message_specification_uri == exchange.message_specification_uri
    }

"""Return whether one fragment sends what the other receives."""
def _has_opposite_communication_perspectives(
        left_types: set[str],
        right_types: set[str],
) -> bool:
    return (
        "SendState" in left_types and "ReceiveState" in right_types
    ) or (
        "ReceiveState" in left_types and "SendState" in right_types
    )

"""Propose pairs for matching exchanges with opposite perspectives."""
def _compare_message_pairs(
        left: PassModelFragment,
        right: PassModelFragment,
) -> list[ReconciliationProposal]:
    proposals: list[ReconciliationProposal] = []

    for left_exchange in left.message_exchanges:
        left_key = _exchange_key(left, left_exchange)

        if left_key is None:
            continue

        left_state_types = _communication_state_types(left, left_exchange)

        for right_exchange in right.message_exchanges:
            right_key = _exchange_key(right, right_exchange)

            if left_key != right_key:
                continue

            right_state_types = _communication_state_types(right, right_exchange)

            if not _has_opposite_communication_perspectives(left_state_types, right_state_types):
                continue

            proposal_id = make_proposal_id(
                proposal_type="message_pair",
                left_view_id=left.view_id,
                right_view_id=right.view_id,
                left_element_uri=left_exchange.uri,
                right_element_uri=right_exchange.uri,
            )

            proposals.append(
                ReconciliationProposal(
                    proposal_id=proposal_id,
                    proposal_type="message_pair",
                    left_view_id=left.view_id,
                    right_view_id=right.view_id,
                    left_element_uri=left_exchange.uri,
                    right_element_uri=right_exchange.uri,
                    explanation=(
                        "Both fragments describe message "
                        f"'{left_key[0]}' from "
                        f"'{left_key[1]}' to "
                        f"'{left_key[2]}' with opposite "
                        "send and receive perspectives."
                    ),
                )
            )

    return proposals

"""Find message exchanges whose comaprison key exists on one side only."""
def _compare_one_sided_messages(
        left: PassModelFragment,
        right: PassModelFragment,
) -> list[ReconciliationProposal]:
    proposals: list[ReconciliationProposal] = []
    left_exchanges_with_keys = [
        (exchange, _exchange_key(left, exchange),) for exchange in left.message_exchanges
    ]
    right_exchanges_with_keys = [
        (exchange, _exchange_key(right, exchange),) for exchange in right.message_exchanges
    ]
    left_keys = {key for _, key in left_exchanges_with_keys if key is not None}
    right_keys = {key for _, key in right_exchanges_with_keys if key is not None}

    for exchange, key in left_exchanges_with_keys:
        if key is None or key in right_keys:
            continue

        proposal_id = make_proposal_id(
            proposal_type="one_sided_message",
            left_view_id=left.view_id,
            right_view_id=right.view_id,
            left_element_uri=exchange.uri,
            right_element_uri=None,
        )
        proposals.append(
            ReconciliationProposal(proposal_id=proposal_id,
                proposal_type="one_sided_message",
                left_view_id=left.view_id,
                right_view_id=right.view_id,
                left_element_uri=exchange.uri,
                right_element_uri=None,
                explanation=(
                    f"The left fragment mentions message '{key[0]}' from '{key[1]}' to "
                    f"'{key[2]}', but the right fragment has no matching message exchange."
                ),
            )
        )

    for exchange, key in right_exchanges_with_keys:
        if key is None or key in left_keys:
            continue

        proposal_id = make_proposal_id(
            proposal_type="one_sided_message",
            left_view_id=left.view_id,
            right_view_id=right.view_id,
            left_element_uri=None,
            right_element_uri=exchange.uri,
        )

        proposals.append(
            ReconciliationProposal(
                proposal_id=proposal_id,
                proposal_type="one_sided_message",
                left_view_id=left.view_id,
                right_view_id=right.view_id,
                left_element_uri=None,
                right_element_uri=exchange.uri,
                explanation=(
                    f"The right fragment mentions message '{key[0]}' from '{key[1]}' to "
                    f"'{key[2]}', but the left fragment has no matching message exchange."
                ),
            )
        )

    return proposals

"""
Compare two PASS fragments without modifying either fragment.
"""
def compare_pass_fragments(
        left: PassModelFragment,
        right: PassModelFragment,
) -> list[ReconciliationProposal]:
    if left.view_id == right.view_id:
        raise ValueError("Cannot compare a fragment with itself.")

    proposals = _compare_equivalent_subjects(left, right,)
    proposals.extend(_compare_message_pairs(left, right,))
    proposals.extend(_compare_one_sided_messages(left, right,))

    return sorted(proposals, key=lambda proposal: proposal.proposal_id,)