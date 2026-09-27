from hashlib import sha256

from stakeholder_extraction.canonical_models import CanonicalSubject
from stakeholder_extraction.pass_mapper import normalize_name
from stakeholder_extraction.pass_models import PassSubject


def create_canonical_subject(
        left: PassSubject,
        right: PassSubject,
) -> CanonicalSubject:
    """Create one deterministic subject from two equivalent subjects."""

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
    """Extend an existing canonical subject with new sources."""

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