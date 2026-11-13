"""Export an existing canonical process from Neo4j."""

import argparse
from pathlib import Path

from stakeholder_extraction.canonical_models import CanonicalProcessContents
from stakeholder_extraction.canonical_process_repository import (
    load_canonical_process_contents,
)
from stakeholder_extraction.pass_export_files import write_pass_export
from stakeholder_extraction.pass_export_models import PassExportOptions


def select_start_subject(contents: CanonicalProcessContents) -> str:
    """Ask the user which selected subject starts the process."""

    if not contents.subjects:
        raise ValueError("The process has no subjects to select.")

    print("\nSelect the process start subject:")

    for number, subject in enumerate(contents.subjects, start=1):
        print(f"{number}. {subject.label}")
        print(f"   {subject.uri}")

    while True:
        answer = input("Start subject number: ").strip()

        try:
            number = int(answer)
        except ValueError:
            print("Enter one of the displayed numbers.")
            continue

        if 1 <= number <= len(contents.subjects):
            return contents.subjects[number - 1].uri

        print("Enter one of the displayed numbers.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export one saved canonical process as PASS Turtle."
    )

    parser.add_argument(
        "--process-uri",
        required=True,
        help="URI printed when the canonical process was saved.",
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="A new directory for model.ttl and validation.json.",
    )
    parser.add_argument(
        "--allow-draft-with-warnings",
        action="store_true",
        help="Explicitly allow draft export with unresolved warnings.",
    )

    args = parser.parse_args()

    try:
        contents = load_canonical_process_contents(args.process_uri)
        start_subject_uri = select_start_subject(contents)

        options = PassExportOptions(
            start_subject_uri=start_subject_uri,
            allow_draft_with_warnings=args.allow_draft_with_warnings,
        )

        turtle_path, report_path = write_pass_export(
            contents,
            options,
            args.output_directory,
        )

        print(f"\nTurtle: {turtle_path}")
        print(f"Visio OWL: {report_path.parent / 'model.owl'}")
        print(f"Validation report: {report_path}")
        print("The export conforms to the prototype SHACL profile.")
        print(
            "Full ontology conformance and consuming-tool compatibility "
            "are still pending."
        )
        return 0

    except FileExistsError:
        print(
            "\nThe output directory already exists. "
            "Choose a new directory."
        )
        return 1

    except (ValueError, OSError) as error:
        print(f"\nExport failed: {error}")
        return 1

    except (KeyboardInterrupt, EOFError):
        print("\nExport interrupted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())