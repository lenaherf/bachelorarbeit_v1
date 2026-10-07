"""Create and extend canonical PASS elements deterministically."""
from hashlib import sha256

from stakeholder_extraction.canonical_models import CanonicalSubject, CanonicalMessageSpecification, \
    CanonicalMessageExchange
from stakeholder_extraction.pass_mapper import normalize_name
from stakeholder_extraction.pass_models import PassSubject, PassMessageExchange, PassMessageSpecification


def create_canonical_subject(
        left: PassSubject,
        right: PassSubject,
) -> CanonicalSubject:
    """Create a new canonical subject from two equivalent sources."""

    if left.uri == right.uri:
        raise ValueError("Canonicalization requires two different source subjects.")

    left_name = normalize_name(left.label)
    right_name = normalize_name(right.label)

    if left_name != right_name:
        raise ValueError("Canonical subjects must have equal normalized labels.")

    source_uris = tuple(sorted({left.uri, right.uri}))
    digest_source = "|".join(source_uris)
    digest = sha256(digest_source.encode("utf-8")).hexdigest()[:16]

    if left.pass_type == "FullySpecifiedSubject" or right.pass_type == "FullySpecifiedSubject":
        pass_type = "FullySpecifiedSubject"
    else:
        pass_type = "InterfaceSubject"

    subjects = sorted(
        [left, right],
        key=lambda subject:(
            subject.pass_type != "FullySpecifiedSubject",
            normalize_name(subject.label),
            subject.label,
            subject.uri,
        ),
    )

    label = subjects[0].label

    return CanonicalSubject(
        uri=f"urn:pass:canonical:subject:{digest}",
        model_component_id=f"canonical:subject:{digest}",
        label=label,
        pass_type=pass_type,
        source_subject_uris=source_uris,
    )

def extend_canonical_subject(
        existing: CanonicalSubject,
        left: PassSubject,
        right: PassSubject,
) -> CanonicalSubject:
    """Extend an existing canonical subject with new sources.

    The URI remains but provenance and PASS type are updated."""

    normalized_names = {
        normalize_name(existing.label),
        normalize_name(left.label),
        normalize_name(right.label),
    }

    if len(normalized_names) != 1:
        raise ValueError("Canonical subject sources must have equal normalized labels.")

    source_subject_uris = tuple(sorted(set(existing.source_subject_uris) | {left.uri, right.uri}))

    has_fully_specified_source = (
        existing.pass_type == "FullySpecifiedSubject"
        or left.pass_type == "FullySpecifiedSubject"
        or right.pass_type == "FullySpecifiedSubject"
    )

    pass_type = "FullySpecifiedSubject" if has_fully_specified_source else "InterfaceSubject"

    label = existing.label

    if existing.pass_type == "InterfaceSubject" and pass_type == "FullySpecifiedSubject":
        fully_specified_sources = [
            subject for subject in [left, right] if subject.pass_type == "FullySpecifiedSubject"
        ]
        label = sorted(fully_specified_sources, key=lambda subject:(
            normalize_name(subject.label),
            subject.label,
            subject.uri,
        ))[0].label

    return existing.model_copy(
        update= {
            "label": label,
            "pass_type": pass_type,
            "source_subject_uris": source_subject_uris,
        }
    )

def create_canonical_message_specification(
        left: PassMessageSpecification,
        right: PassMessageSpecification,
) -> CanonicalMessageSpecification:
    """Create one canonical message from two equivalent sources."""

    if left.uri == right.uri:
        raise ValueError("Canonicalization requires two different message specifications.")

    left_name = normalize_name(left.label)
    right_name = normalize_name(right.label)

    if left_name != right_name:
        raise ValueError("Canonical message specifications must have equal normalized labels.")

    source_message_uris = tuple(sorted({left.uri, right.uri}))

    digest = sha256("|".join(source_message_uris).encode("utf-8")).hexdigest()[:16]

    messages = sorted([left, right], key=lambda message:(
        normalize_name(message.label),
        message.label,
        message.uri,
    ))

    return CanonicalMessageSpecification(
        uri=f"urn:pass:canonical:message:{digest}",
        model_component_id=f"canonical:message:{digest}",
        label=messages[0].label,
        source_message_uris=source_message_uris,
    )

def create_canonical_message_exchange(
        left: PassMessageExchange,
        right: PassMessageExchange,
        *,
        message: CanonicalMessageSpecification,
        sender: CanonicalSubject,
        receiver: CanonicalSubject,
) -> CanonicalMessageExchange:
    """Create a canonical exchange using canonical references."""

    if left.uri == right.uri:
        raise ValueError("Canonicalization requires two different message exchanges.")

    source_message_uris = {left.message_specification_uri, right.message_specification_uri}

    if not source_message_uris.issubset(
        set(message.source_message_uris)
    ):
        raise ValueError(
            "The canonical message does not represent both exchange message specifications."
        )

    source_sender_uris = {left.sender_uri, right.sender_uri}

    if not source_sender_uris.issubset(
        set(sender.source_subject_uris)
    ):
        raise ValueError(
            "The canonical sender does not represent both exchange senders."
        )

    source_receiver_uris = {left.receiver_uri, right.receiver_uri}

    if not source_receiver_uris.issubset(
            set(receiver.source_subject_uris)
    ):
        raise ValueError(
            "The canonical receiver does not represent both exchange senders."
        )

    source_exchange_uris = tuple(sorted({left.uri, right.uri}))

    digest = sha256("|".join(source_exchange_uris).encode("utf-8")).hexdigest()[:16]

    return CanonicalMessageExchange(
        uri=f"urn:pass:canonical:message:{digest}",
        model_component_id=f"canonical:message:{digest}",
        label=f"{sender.label} sends {message.label} to {receiver.label}",
        sender_uri=sender.uri,
        receiver_uri=receiver.uri,
        message_specification_uri=message.uri,
        source_exchange_uris=source_exchange_uris
    )

def create_single_source_canonical_message(
        source: PassMessageSpecification
) -> CanonicalMessageSpecification:
    """Create a canonical message from one confirmed source."""

    digest = sha256(source.uri.encode("utf-8")).hexdigest()[:16]

    return CanonicalMessageSpecification(
        uri=f"urn:pass:canonical:message:{digest}",
        model_component_id=f"canonical:message:{digest}",
        label=source.label,
        source_message_uris=(source.uri,)
    )

def create_single_source_canonical_exchange(
        source: PassMessageExchange,
        *,
        message: CanonicalMessageSpecification,
        sender: CanonicalSubject,
        receiver: CanonicalSubject,
) -> CanonicalMessageExchange:
    """Create a canonical exchange from one confirmed source."""

    if source.message_specification_uri not in message.source_message_uris:
        raise ValueError("The canonical message does not represent the source exchange message.")

    if source.sender_uri not in sender.source_subject_uris:
        raise ValueError("The canonical sender does not represent the source exchange sender.")

    if source.receiver_uri not in receiver.source_subject_uris:
        raise ValueError("The canonical receiver does not represent the source exchange receiver.")

    digest = sha256(source.uri.encode("utf-8")).hexdigest()[:16]

    return CanonicalMessageExchange(
        uri=f"urn:pass:canonical:exchange:{digest}",
        model_component_id=f"canonical:exchange:{digest}",
        label=f"{sender.label} sends {message.label} to {receiver.label}",
        sender_uri=sender.uri,
        receiver_uri=receiver.uri,
        message_specification_uri=message.uri,
        source_exchange_uris=(source.uri,)
    )
