import argparse
from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.behavior_review_repository import save_behavior_review
from stakeholder_extraction.canonical_behavior_repository import save_confirmed_behavior
from stakeholder_extraction.canonical_process import create_canonical_process_model
from stakeholder_extraction.canonical_process_repository import save_canonical_process_model, load_canonical_process_contents
from stakeholder_extraction.canonical_repository import canonicalize_confirmed_message_pair_proposal, canonicalize_confirmed_subject_proposal, canonicalize_confirmed_one_sided_message
from stakeholder_extraction.examples.complaint import make_complete_customer_complaint_view, make_complete_service_complaint_view
from stakeholder_extraction.models import StakeholderView
from stakeholder_extraction.neo4j_repository import save_stakeholder_view
from stakeholder_extraction.pass_fragment_repository import save_pass_model_fragment
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.pass_models import PassModelFragment
from stakeholder_extraction.process_validation import validate_process_completeness
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_models import ReviewDecision
from stakeholder_extraction.reconciliation_repository import review_reconciliation_proposal, save_reconciliation_proposals
from uuid import uuid4
from datetime import timezone, datetime


class DemoStopped(Exception):
    """The reviewer stopped the example or rejected a required selection."""


def ask_decision(prompt: str) -> ReviewDecision:
    """Require an explicit confirmation or rejection."""

    while True:
        answer = input(
            f"{prompt} [c=confirm, r=reject, q=quit]: "
        ).strip().lower()

        if answer == "c":
            return "confirmed"

        if answer == "r":
            return "rejected"

        if answer == "q":
            raise DemoStopped("Stopped by the reviewer.")

        print("Please enter c, r, or q.")


def show_behavior(fragment: PassModelFragment) -> None:
    """Display the source behavior being considered for selection."""

    print(f"\nBehaviour from: {fragment.stakeholder}")
    print(f"Source view: {fragment.view_id}")

    states_by_uri = {
        state.uri: state for state in fragment.states
    }

    exchanges_by_uri = {
        exchange.uri: exchange
        for exchange in fragment.message_exchanges
    }
    messages_by_uri = {
        message.uri: message
        for message in fragment.message_specifications
    }

    for state in fragment.states:
        flags = []

        if state.is_initial:
            flags.append("initial")
        if state.is_end:
            flags.append("end")

        print(
            f"  {state.label} [{state.pass_type}] "
            f"{', '.join(flags)}"
        )
        print(f"    Evidence: {state.evidence}")

    print("Transitions:")

    for transition in fragment.transitions:
        start = states_by_uri[transition.source_state_uri]
        end = states_by_uri[transition.target_state_uri]

        print(
            f"  {start.label} → {end.label} "
            f"[{transition.pass_type}]"
        )
        print(f"    Sequence evidence: {transition.evidence}")

        if transition.pass_type == "ReceiveTransition":
            exchange_uri = transition.message_exchange_uri
            exchange = (
                exchanges_by_uri.get(exchange_uri)
                if exchange_uri is not None
                else None
            )
            message = (
                messages_by_uri.get(exchange.message_specification_uri)
                if exchange is not None
                else None
            )
            print(
                "    Received message: "
                f"{message.label if message is not None else 'unresolved'}"
            )

        if transition.pass_type == "DoTransition":
            condition = transition.exit_condition
            evidence = transition.exit_condition_evidence

            print(
                f"    Exit condition: "
                f"{condition if condition is not None else 'unresolved'}"
            )
            print(
                f"    Condition evidence: "
                f"{evidence if evidence is not None else 'unresolved'}"
            )

def prepare_demo_fragments(
    views: list[StakeholderView],
) -> list[PassModelFragment]:
    """Save supplied source views and formal fragments."""

    if len(views) != 2:
        raise ValueError(
            "This prototype runner currently requires two views."
        )

    fragments = []

    for view in views:
        print(f"\nDescription from {view.stakeholder}:")
        print(view.source_text)

        if view.open_questions:
            for question in view.open_questions:
                print(f"Open question: {question.question}")

            raise DemoStopped(
                "Resolve the source questions before continuing."
            )

        view_id = save_stakeholder_view(view)
        fragment = map_view_to_pass_fragment(view, view_id=view_id)

        if fragment.mapping_issues:
            for issue in fragment.mapping_issues:
                print(f"Mapping issue [{issue.code}]: {issue.detail}")

            raise DemoStopped(
                "Resolve the mapping issues before continuing."
            )

        save_pass_model_fragment(fragment)
        fragments.append(fragment)

        print(f"Saved source view: {view_id}")

    return fragments

def reconcile_demo_fragments(fragments, reviewed_by):
    """Review subject correspondences and communication discrepancies."""

    proposals = compare_pass_fragments(
        fragments[0],
        fragments[1],
    )
    save_reconciliation_proposals(proposals)

    supported_types = {
        "equivalent_subject",
        "message_pair",
        "one_sided_message",
    }

    unsupported = [
        proposal
        for proposal in proposals
        if proposal.proposal_type not in supported_types
    ]

    if unsupported:
        raise DemoStopped(
            "The runner encountered an unsupported proposal type."
        )

    elements_by_uri = {}

    for fragment in fragments:
        for element in [
            *fragment.subjects,
            *fragment.message_exchanges,
        ]:
            elements_by_uri[element.uri] = element

    fragments_by_id = {
        fragment.view_id: fragment
        for fragment in fragments
    }

    subjects = []
    messages = []
    exchanges = []

    # Resolve subjects before creating communication references.
    proposal_order = (
        "equivalent_subject",
        "message_pair",
        "one_sided_message",
    )

    for proposal_type in proposal_order:
        for proposal in proposals:
            if proposal.proposal_type != proposal_type:
                continue

            print(f"\nProposal: {proposal.proposal_type}")
            print(proposal.explanation)

            for view_id, element_uri in (
                (proposal.left_view_id, proposal.left_element_uri),
                (proposal.right_view_id, proposal.right_element_uri),
            ):
                stakeholder = fragments_by_id[view_id].stakeholder

                print(f"Perspective: {stakeholder}")

                if element_uri is None:
                    print("  No matching message mentioned in this view.")
                    continue

                element = elements_by_uri[element_uri]

                print(f"  Element: {element.label}")
                print(f"  Evidence: {element.evidence}")

            if proposal_type == "one_sided_message":
                print(
                    "Only one view supplies evidence for this message. "
                    "Including it will not add states to the other view."
                )
                prompt = "Include this message using its single source?"
            else:
                prompt = "Accept this correspondence?"

            decision = ask_decision(prompt)

            review_reconciliation_proposal(
                proposal_id=proposal.proposal_id,
                decision=decision,
                reviewed_by=reviewed_by,
            )

            if decision == "rejected":
                raise DemoStopped(
                    "Rejection saved. Resolve or revise the affected "
                    "source description before building this process."
                )

            if proposal_type == "equivalent_subject":
                subject = canonicalize_confirmed_subject_proposal(
                    proposal.proposal_id
                )
                subjects.append(subject)
                continue

            if proposal_type == "message_pair":
                message, exchange = (
                    canonicalize_confirmed_message_pair_proposal(
                        proposal.proposal_id
                    )
                )
            else:
                message, exchange = (
                    canonicalize_confirmed_one_sided_message(
                        proposal.proposal_id
                    )
                )

            messages.append(message)
            exchanges.append(exchange)

    return subjects, messages, exchanges

def save_demo_behaviors(fragments, subjects, reviewed_by):
    """Review and save each stakeholder's own source behavior."""

    behaviors = []

    for fragment in fragments:
        source_subject = next(
            subject
            for subject in fragment.subjects
            if subject.pass_type == "FullySpecifiedSubject"
        )

        matches = [
            subject
            for subject in subjects
            if source_subject.uri in subject.source_subject_uris
        ]

        if len(matches) != 1:
            raise ValueError(
                "The source must resolve to one canonical subject."
            )

        owner = matches[0]

        show_behavior(fragment)
        print(f"Canonical owner: {owner.label}")

        decision = ask_decision("Use this source behaviour?")

        review = BehaviorReview(
            source_view_id=fragment.view_id,
            source_subject_uri=source_subject.uri,
            canonical_subject_uri=owner.uri,
            decision=decision,
            reviewed_by=reviewed_by,
            reviewed_at=datetime.now(timezone.utc),
        )

        review_id = save_behavior_review(review)

        if decision == "rejected":
            raise DemoStopped(
                "Behaviour rejection saved. No complete process "
                "was created for this run."
            )

        behaviors.append(save_confirmed_behavior(review_id))

    return behaviors


def run_demo(
    reviewed_by: str,
    *,
    views: list[StakeholderView] | None = None,
) -> int:
    """Build, persist, and validate two reviewed stakeholder views."""

    if views is None:
        views = [
            make_complete_customer_complaint_view(),
            make_complete_service_complaint_view(),
        ]

    fragments = prepare_demo_fragments(views)

    subjects, messages, exchanges = reconcile_demo_fragments(
        fragments,
        reviewed_by,
    )

    behaviors = save_demo_behaviors(
        fragments,
        subjects,
        reviewed_by,
    )

    process = create_canonical_process_model(
        model_id=f"complaint-demo-{uuid4()}",
        label="Reviewed complaint handling example",
        subject_uris=[subject.uri for subject in subjects],
        behavior_uris=[item.behavior.uri for item in behaviors],
        message_specification_uris=[
            message.uri for message in messages
        ],
        message_exchange_uris=[
            exchange.uri for exchange in exchanges
        ],
    )

    save_canonical_process_model(process)

    print(f"\nSaved process: {process.uri}")

    contents = load_canonical_process_contents(process.uri)
    report = validate_process_completeness(contents)

    for issue in report.issues:
        print(
            f"- {issue.severity.upper()} [{issue.code}]: "
            f"{issue.message}"
        )
        print(f"  Element: {issue.element_uri}")

    if not report.passes_completeness_checks:
        print("\nThe process was saved but has blocking validation issues.")
        return 1

    if report.has_warnings:
        print(
            "\nNo errors were found by the prototype checks, "
            "but the warnings above remain unresolved."
        )
    else:
        print("\nThe process passes the prototype completeness checks.")

    print("Ontology and export-tool validation are still pending.")
    return 0

def read_description() -> str:
    """Read a multiline description ending with a single dot."""

    print("Enter the description.")
    print("Finish with a line containing only a dot: .")

    lines = []

    while True:
        line = input()

        if line.strip() == ".":
            break

        lines.append(line)

    description = "\n".join(lines).strip()

    if not description:
        raise ValueError("The description must not be empty.")

    return description


def collect_live_views() -> list[StakeholderView]:
    """Extract and inspect two stakeholder descriptions."""

    # Delay loading the LLM pipeline until live mode is requested.
    from stakeholder_extraction.stakeholder_pipeline import (
        process_stakeholder_input,
    )

    views = []

    for position in range(1, 3):
        print(f"\nStakeholder {position}")

        stakeholder = input("Role name: ").strip()

        if not stakeholder:
            raise ValueError("The stakeholder name must not be empty.")

        if any(
            view.stakeholder.casefold() == stakeholder.casefold()
            for view in views
        ):
            raise ValueError(
                "Use two different stakeholder role names."
            )

        source_text = read_description()

        print("\nPreparing and extracting the description...")

        view = process_stakeholder_input(
            stakeholder=stakeholder,
            source_text=source_text,
        )

        print("\nExtracted view:")
        print(view.model_dump_json(indent=2))

        decision = ask_decision(
            "Continue with this extraction?"
        )

        if decision == "rejected":
            raise DemoStopped(
                "Extraction rejected. Correct the description "
                "and start a new run."
            )

        views.append(view)

    return views

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic complaint process "
            "with interactive administrator review."
        )
    )
    parser.add_argument(
        "--reviewer",
        required=True,
        help="Name recorded with administrator decisions.",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Extract two entered descriptions using the LLM pipeline.",
    )

    args = parser.parse_args()
    reviewed_by = args.reviewer.strip()

    if not reviewed_by:
        parser.error("--reviewer must not be blank")

    try:
        views = collect_live_views() if args.live else None

        return run_demo(
            reviewed_by,
            views=views,
        )
    except DemoStopped as error:
        print(f"\n{error}")
        print("Previously saved views and decisions remain in Neo4j.")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nReview interrupted.")
        print("Previously saved records remain in Neo4j.")
        return 1
    except ValueError as error:
        print(f"\nThe demo could not continue: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
