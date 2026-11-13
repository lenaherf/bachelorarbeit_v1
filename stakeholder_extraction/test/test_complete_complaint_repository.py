from datetime import datetime, timezone
from uuid import uuid4
import pytest
import json
from stakeholder_extraction.behavior_review_models import BehaviorReview
from stakeholder_extraction.behavior_review_repository import (
    save_behavior_review,
)
from stakeholder_extraction.canonical_behavior_repository import (
    get_canonical_behavior,
    save_confirmed_behavior,
)
from stakeholder_extraction.canonical_process import (
    create_canonical_process_model,
)
from stakeholder_extraction.canonical_process_repository import (
    get_canonical_process_model,
    save_canonical_process_model, load_canonical_process_contents,
)
from stakeholder_extraction.canonical_repository import (
    canonicalize_confirmed_message_pair_proposal,
    canonicalize_confirmed_subject_proposal,
)
from stakeholder_extraction.examples.complaint import (
    make_complete_customer_complaint_view,
    make_complete_service_complaint_view,
)
from stakeholder_extraction.neo4j_connection import open_neo4j_session
from stakeholder_extraction.neo4j_repository import save_stakeholder_view
from stakeholder_extraction.pass_export import validate_export_request
from stakeholder_extraction.pass_export_files import write_pass_export
from stakeholder_extraction.pass_export_models import PassExportOptions
from stakeholder_extraction.pass_fragment_repository import (
    save_pass_model_fragment,
)
from stakeholder_extraction.pass_mapper import map_view_to_pass_fragment
from stakeholder_extraction.process_validation import validate_process_completeness
from stakeholder_extraction.reconciliation import compare_pass_fragments
from stakeholder_extraction.reconciliation_repository import (
    review_reconciliation_proposal,
    save_reconciliation_proposals,
)
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from rdflib.compare import isomorphic
from stakeholder_extraction.pass_rdf import PASS, build_pass_graph
from stakeholder_extraction.canonical_models import (
    CanonicalProcessContents,
)

@pytest.fixture
def canonical_complaint_contents() -> CanonicalProcessContents:
    """Prepare the canonical complaint scenario for integration tests."""
    # Save both original views and their formal fragments.
    views = [
        make_complete_customer_complaint_view(),
        make_complete_service_complaint_view(),
    ]

    fragments = []

    for view in views:
        view_id = save_stakeholder_view(view)
        fragment = map_view_to_pass_fragment(view, view_id=view_id)

        assert fragment.mapping_issues == []

        save_pass_model_fragment(fragment)
        fragments.append(fragment)

    proposals = compare_pass_fragments(
        fragments[0],
        fragments[1],
    )
    save_reconciliation_proposals(proposals)

    subject_proposals = [
        proposal
        for proposal in proposals
        if proposal.proposal_type == "equivalent_subject"
    ]
    message_proposals = [
        proposal
        for proposal in proposals
        if proposal.proposal_type == "message_pair"
    ]

    assert len(subject_proposals) == 2
    assert len(message_proposals) == 2
    assert len(proposals) == 4

    # These are explicit, predetermined decisions for this test scenario.
    canonical_subjects = {}

    for proposal in subject_proposals:
        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="demo-test",
        )

        subject = canonicalize_confirmed_subject_proposal(
            proposal.proposal_id
        )
        canonical_subjects[subject.label] = subject

    messages = []
    exchanges = []

    for proposal in message_proposals:
        review_reconciliation_proposal(
            proposal_id=proposal.proposal_id,
            decision="confirmed",
            reviewed_by="demo-test",
        )

        message, exchange = canonicalize_confirmed_message_pair_proposal(
            proposal.proposal_id
        )
        messages.append(message)
        exchanges.append(exchange)

    # Select each stakeholder's own behaviour.
    behaviors = []

    for fragment in fragments:
        owner = canonical_subjects[fragment.stakeholder]

        source_subject = next(
            subject
            for subject in fragment.subjects
            if subject.pass_type == "FullySpecifiedSubject"
        )

        review = BehaviorReview(
            source_view_id=fragment.view_id,
            source_subject_uri=source_subject.uri,
            canonical_subject_uri=owner.uri,
            decision="confirmed",
            reviewed_by="demo-test",
            reviewed_at=datetime.now(timezone.utc),
        )

        review_id = save_behavior_review(review)
        behavior = save_confirmed_behavior(review_id)

        assert get_canonical_behavior(behavior.behavior.uri) == behavior
        behaviors.append(behavior)

    # Both selected subjects must have their own behaviour.
    assert {
               item.behavior.subject_uri for item in behaviors
           } == {
               subject.uri for subject in canonical_subjects.values()
           }

    assert sum(len(item.states) for item in behaviors) == 7
    assert sum(len(item.transitions) for item in behaviors) == 5

    for item in behaviors:
        assert sum(state.is_initial for state in item.states) == 1
        assert sum(state.is_end for state in item.states) == 1

        end_uri = next(
            state.uri for state in item.states if state.is_end
        )
        assert not any(
            transition.source_state_uri == end_uri
            for transition in item.transitions
        )

    process = create_canonical_process_model(
        model_id=f"complete-complaint-{uuid4()}",
        label="Complete complaint handling example",
        subject_uris=[
            subject.uri for subject in canonical_subjects.values()
        ],
        behavior_uris=[
            item.behavior.uri for item in behaviors
        ],
        message_specification_uris=[
            message.uri for message in messages
        ],
        message_exchange_uris=[
            exchange.uri for exchange in exchanges
        ],
    )

    return CanonicalProcessContents(
        model=process,
        subjects=list(canonical_subjects.values()),
        behavior_fragments=behaviors,
        messages=messages,
        exchanges=exchanges,
    )

@pytest.fixture
def broken_complaint_contents(
    canonical_complaint_contents,
) -> CanonicalProcessContents:
    """Return a copy with one behavior's final transition removed."""

    contents = canonical_complaint_contents
    original_behavior = contents.behavior_fragments[0]

    broken_behavior = original_behavior.model_copy(
        update={
            "transitions": original_behavior.transitions[:-1],
        }
    )

    return contents.model_copy(
        update={
            "behavior_fragments": [
                broken_behavior,
                *contents.behavior_fragments[1:],
            ],
        }
    )


@pytest.fixture
def single_source_complaint_contents(
    canonical_complaint_contents,
) -> CanonicalProcessContents:
    """Return a copy with one exchange supported by one source."""

    contents = canonical_complaint_contents
    original_exchange = contents.exchanges[0]

    single_source_exchange = original_exchange.model_copy(
        update={
            "source_exchange_uris": (
                original_exchange.source_exchange_uris[0],
            ),
        }
    )

    return contents.model_copy(
        update={
            "exchanges": [
                single_source_exchange,
                *contents.exchanges[1:],
            ],
        }
    )

@pytest.mark.integration
def test_persists_complete_two_subject_complaint_process(canonical_complaint_contents):
    process = canonical_complaint_contents.model

    first_uri = save_canonical_process_model(process)
    second_uri = save_canonical_process_model(process)

    assert first_uri == process.uri
    assert second_uri == first_uri
    assert get_canonical_process_model(process.uri) == process

    expected_members = {
        *process.subject_uris,
        *process.behavior_uris,
        *process.message_specification_uris,
        *process.message_exchange_uris,
    }

    with open_neo4j_session() as session:
        record = session.run(
            """
            MATCH (model:CanonicalProcessModel {
                uri: $uri
            })-[membership:CONTAINS]->(element)
            RETURN
                collect(element.uri) AS member_uris,
                count(membership) AS relationship_count
            """,
            uri=process.uri,
        ).single()

    assert record is not None
    assert set(record["member_uris"]) == expected_members
    assert record["relationship_count"] == 8

    contents = load_canonical_process_contents(process.uri)

    assert contents.model == process
    assert len(contents.subjects) == 2
    assert len(contents.behavior_fragments) == 2
    assert len(contents.messages) == 2
    assert len(contents.exchanges) == 2

    report = validate_process_completeness(contents)

    assert report.passes_completeness_checks, report.model_dump_json(indent=2)
    assert report.issues == []
    assert not report.has_warnings

@pytest.mark.integration
def test_builds_complete_pass_graph(canonical_complaint_contents):
    """Check RDF structure, serialization and PASS vocabulary."""

    contents = canonical_complaint_contents
    process = contents.model

    customer = next(
        subject
        for subject in contents.subjects
        if subject.label == "Customer"
    )

    options = PassExportOptions(
        start_subject_uri=customer.uri,
    )

    graph = build_pass_graph(contents, options)

    assert (
               URIRef(process.uri),
               RDF.type,
               PASS["PASSProcessModel"],
           ) in graph

    assert (
               URIRef(process.uri),
               PASS["hasStartSubject"],
               URIRef(options.start_subject_uri),
           ) in graph

    assert len(set(
        graph.subjects(RDF.type, PASS["SubjectBaseBehavior"])
    )) == 2

    assert len(set(
        graph.subjects(RDF.type, PASS["InitialStateOfBehavior"])
    )) == 2

    assert len(set(
        graph.subjects(RDF.type, PASS["EndState"])
    )) == 2

    for fragment in contents.behavior_fragments:
        for transition in fragment.transitions:
            condition_uri = URIRef(f"{transition.uri}:condition")

            assert (
                       URIRef(transition.uri),
                       PASS["hasTransitionCondition"],
                       condition_uri,
                   ) in graph

            if transition.message_exchange_uri is not None:
                assert (
                           condition_uri,
                           PASS["requiresPerformedMessageExchange"],
                           URIRef(transition.message_exchange_uri),
                       ) in graph

    # Export must not pull source-fragment URIs into the RDF graph.
    assert not any(
        isinstance(term, URIRef)
        and str(term).startswith("urn:pass:view:")
        for triple in graph
        for term in triple
    )

    # Turtle serialization must preserve the graph.
    turtle = graph.serialize(format="turtle")
    parsed = Graph().parse(data=turtle, format="turtle")

    assert isomorphic(graph, parsed)

    # Check every used PASS term against the downloaded ontology.
    ontology_path = (
            Path(__file__).resolve().parents[2]
            / "ontology/generated/standard_PASS_ont_dev.ttl"
    )

    schema = Graph().parse(
        str(ontology_path),
        format="turtle",
    )

    declared_terms = set(schema.subjects())

    used_pass_terms = {
        predicate
        for _, predicate, _ in graph
        if str(predicate).startswith(str(PASS))
    }

    used_pass_terms.update(
        rdf_type
        for rdf_type in graph.objects(None, RDF.type)
        if str(rdf_type).startswith(str(PASS))
    )

    assert used_pass_terms <= declared_terms

@pytest.mark.integration
def test_writes_complete_export_without_overwriting(
    canonical_complaint_contents,
    tmp_path,
):
    """Write valid export files and protect existing output."""

    contents = canonical_complaint_contents
    process = contents.model

    customer = next(
        subject
        for subject in contents.subjects
        if subject.label == "Customer"
    )

    options = PassExportOptions(
        start_subject_uri=customer.uri,
    )

    graph = build_pass_graph(contents, options)

    output_directory = tmp_path / "complete-export"

    turtle_path, report_path = write_pass_export(
        contents,
        options,
        output_directory,
    )

    assert turtle_path.is_file()
    assert report_path.is_file()

    owl_path = output_directory / "model.owl"
    assert owl_path.is_file()

    visio_file_graph = Graph().parse(
        str(owl_path),
        format="xml",
    )

    assert len(set(
        visio_file_graph.subjects(
            RDF.type, PASS["PASSProcessModel"]
        )
    )) == 1

    assert len(set(
        visio_file_graph.subjects(
            RDF.type, PASS["SubjectBehavior"]
        )
    )) == 2

    file_graph = Graph().parse(
        str(turtle_path),
        format="turtle",
    )

    assert isomorphic(graph, file_graph)

    report_data = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert report_data["model_uri"] == process.uri
    assert report_data["start_subject_uri"] == options.start_subject_uri
    assert report_data["passes_completeness_checks"] is True
    assert report_data["has_warnings"] is False
    assert report_data["export_status"] == "passes_prototype_checks"
    assert report_data["ontology_validation"] == "not_run"
    assert report_data["triple_count"] == len(graph)
    assert report_data["visio_export"]["file"] == "model.owl"
    assert report_data["visio_export"]["shacl_validation"]["conforms"] is True

    # Reusing an export directory must not overwrite its contents.
    original_turtle = turtle_path.read_bytes()
    original_report = report_path.read_bytes()

    with pytest.raises(FileExistsError):
        write_pass_export(contents, options, output_directory)

    assert turtle_path.read_bytes() == original_turtle
    assert report_path.read_bytes() == original_report

@pytest.mark.integration
def test_reports_missing_subject_behavior(
    canonical_complaint_contents,
):
    """Report a subject whose behavior was not selected."""

    contents = canonical_complaint_contents

    # Select only one of the two behaviours, retaining both subjects.
    remaining_behavior = contents.behavior_fragments[0]

    partial_model = contents.model.model_copy(
        update={
            "behavior_uris": (remaining_behavior.behavior.uri,),
        }
    )

    partial_contents = contents.model_copy(
        update={
            "model": partial_model,
            "behavior_fragments": [remaining_behavior],
        }
    )

    partial_report = validate_process_completeness(partial_contents)

    assert any(
        issue.code == "missing_subject_behavior"
        for issue in partial_report.issues
    )

@pytest.mark.integration
def test_warns_about_missing_receive_transition(
    canonical_complaint_contents,
):
    """Report communication without a corresponding receive transition."""

    contents = canonical_complaint_contents
    original_exchange = contents.exchanges[0]

    # Remove the receiving transition for this exchange in a copy.
    changed_behaviors = []

    for fragment in contents.behavior_fragments:
        changed_behaviors.append(
            fragment.model_copy(
                update={
                    "transitions": [
                        transition
                        for transition in fragment.transitions
                        if not (
                                transition.pass_type == "ReceiveTransition"
                                and transition.message_exchange_uri
                                == original_exchange.uri
                        )
                    ]
                }
            )
        )

    missing_receive_contents = contents.model_copy(
        update={"behavior_fragments": changed_behaviors}
    )

    missing_receive_report = validate_process_completeness(
        missing_receive_contents
    )

    assert any(
        issue.code == "missing_receive_transition"
        and issue.severity == "warning"
        and issue.element_uri == original_exchange.uri
        for issue in missing_receive_report.issues
    )

    # Removing the transition also breaks local reachability/completeness.
    assert not missing_receive_report.passes_completeness_checks

@pytest.mark.integration
def test_validates_modified_complaint_processes(
    broken_complaint_contents,
    single_source_complaint_contents,
):
    """Check completeness errors and single-source warnings."""
    broken_contents = broken_complaint_contents

    broken_report = validate_process_completeness(broken_contents)
    codes = {issue.code for issue in broken_report.issues}

    assert not broken_report.passes_completeness_checks
    assert "unreachable_state" in codes
    assert "non_end_state_without_outgoing_transition" in codes
    assert "no_path_to_end" in codes

    single_source_contents = single_source_complaint_contents
    original_exchange = single_source_contents.exchanges[0]

    single_source_report = validate_process_completeness(
        single_source_contents
    )

    assert single_source_report.passes_completeness_checks
    assert single_source_report.has_warnings
    assert any(
        issue.code == "single_source_exchange"
        and issue.severity == "warning"
        and issue.element_uri == original_exchange.uri
        for issue in single_source_report.issues
    )

@pytest.mark.integration
def test_validates_export_request_policy(
    canonical_complaint_contents,
    broken_complaint_contents,
    single_source_complaint_contents,
):
    """Check start-subject selection and draft-export policy."""

    contents = canonical_complaint_contents
    broken_contents = broken_complaint_contents
    single_source_contents = single_source_complaint_contents

    canonical_subjects = {
        subject.label: subject
        for subject in contents.subjects
    }

    options = PassExportOptions(
        start_subject_uri=canonical_subjects["Customer"].uri,
    )

    # The complete agreement example satisfies the export preconditions.
    export_report = validate_export_request(contents, options)

    assert export_report.passes_completeness_checks
    assert not export_report.has_warnings

    # A subject outside the model cannot be selected as its start subject.
    outside_options = PassExportOptions(
        start_subject_uri="urn:pass:canonical:subject:outside",
    )

    with pytest.raises(
            ValueError,
            match="start subject must belong",
    ):
        validate_export_request(contents, outside_options)

    # Warnings require an explicit draft request.
    with pytest.raises(
            ValueError,
            match="unresolved warnings",
    ):
        validate_export_request(single_source_contents, options)

    draft_options = PassExportOptions(
        start_subject_uri=canonical_subjects["Customer"].uri,
        allow_draft_with_warnings=True,
    )

    draft_report = validate_export_request(
        single_source_contents,
        draft_options,
    )

    assert draft_report.has_warnings

    # Draft export still cannot bypass structural/completeness errors.
    with pytest.raises(
            ValueError,
            match="Export blocked by validation errors",
    ):
        validate_export_request(broken_contents, draft_options)

@pytest.mark.integration
def test_exports_drafts_but_blocks_invalid_processes(
    broken_complaint_contents,
    single_source_complaint_contents,
    tmp_path,
):
    """Block invalid exports and preserve accepted draft warnings."""

    broken_contents = broken_complaint_contents
    single_source_contents = single_source_complaint_contents

    customer_uri = next(
        subject.uri
        for subject in single_source_contents.subjects
        if subject.label == "Customer"
    )

    draft_options = PassExportOptions(
        start_subject_uri=customer_uri,
        allow_draft_with_warnings=True,
    )

    # Invalid models must fail before creating an output directory.
    invalid_directory = tmp_path / "invalid-export"

    with pytest.raises(
            ValueError,
            match="Export blocked by validation errors",
    ):
        write_pass_export(
            broken_contents,
            draft_options,
            invalid_directory,
        )

    assert not invalid_directory.exists()

    # Explicit draft export must preserve its warnings in the report.
    _, draft_report_path = write_pass_export(
        single_source_contents,
        draft_options,
        tmp_path / "draft-export",
    )

    draft_report_data = json.loads(
        draft_report_path.read_text(encoding="utf-8")
    )

    assert draft_report_data["export_status"] == "draft_with_warnings"
    assert draft_report_data["has_warnings"] is True
    assert any(
        issue["code"] == "single_source_exchange"
        for issue in draft_report_data["issues"]
    )