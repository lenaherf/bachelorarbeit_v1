"""Validate export requests and, later, produce PASS RDF."""

from stakeholder_extraction.canonical_models import CanonicalProcessContents
from stakeholder_extraction.pass_export_models import PassExportOptions
from stakeholder_extraction.process_validation import (
    ProcessValidationReport,
    validate_process_completeness,
)


def validate_export_request(
    contents: CanonicalProcessContents,
    options: PassExportOptions,
) -> ProcessValidationReport:
    """Check the selected start subject and export warning policy."""

    if options.start_subject_uri not in contents.model.subject_uris:
        raise ValueError("The export start subject must belong to the selected process.")

    report = validate_process_completeness(contents)

    errors = [
        issue for issue in report.issues
        if issue.severity == "error"
    ]

    if errors:
        codes = ", ".join(sorted({issue.code for issue in errors}))

        raise ValueError(f"Export blocked by validation errors: {codes}")

    if report.has_warnings and not options.allow_draft_with_warnings:
        raise ValueError("The process has unresolved warnings. Resolve them or explicitly request a draft export.")

    return report