"""Write canonical PASS RDF and its validation reports."""

import json
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph
from stakeholder_extraction.pass_visio import build_visio_graph
from stakeholder_extraction.canonical_models import CanonicalProcessContents
from stakeholder_extraction.pass_export import validate_export_request
from stakeholder_extraction.pass_export_models import PassExportOptions
from stakeholder_extraction.pass_rdf import build_pass_graph
from stakeholder_extraction.pass_shacl import validate_pass_graph

def _validate_graph_for_export(
    graph: Graph,
    *,
    label: str,
) -> bool:
    """Run the SHACL validation and reject graphs with violations."""

    conforms, _, report_text = validate_pass_graph(graph)

    if not conforms:
        raise ValueError(f"{label} is not a valid SHACL graph and blocked by violations:\n{report_text}")

    return conforms

def write_pass_export(
    contents: CanonicalProcessContents,
    options: PassExportOptions,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Validate and write an export into a new directory."""

    report = validate_export_request(contents, options)
    graph = build_pass_graph(contents, options)

    conforms = _validate_graph_for_export(graph, label="Export")

    # Derive a distinct export namespace from the saved process URI.
    visio_base_uri = (
            "https://example.org/pass/models/"
            + quote(contents.model.uri, safe="")
    )

    visio_graph = build_visio_graph(
        graph,
        base_uri=visio_base_uri,
    )

    visio_conforms = _validate_graph_for_export(visio_graph, label="Visio export")

    # Prepare all output before creating the directory.
    turtle = graph.serialize(format="turtle")

    visio_xml = visio_graph.serialize(
        format="xml",
        base=visio_base_uri,
    )

    report_data = {
        **report.model_dump(mode="json"),
        "start_subject_uri": options.start_subject_uri,
        "passes_completeness_checks": (
            report.passes_completeness_checks
        ),
        "has_warnings": report.has_warnings,
        "export_status": (
            "draft_with_warnings"
            if report.has_warnings
            else "passes_prototype_checks"
        ),
        "shacl_validation": {
            "profile": "ontology/shapes/pass-prototype-shapes.ttl",
            "conforms": conforms,
            "inference": "none",
        },
        "ontology_validation": "not_run",
        "consuming_tool_validation": "not_run",
        "triple_count": len(graph),
        "visio_export": {
            "file": "model.owl",
            "base_uri": visio_base_uri,
            "triple_count": len(visio_graph),
            "shacl_validation": {
                "conforms": visio_conforms,
                "profile": "ontology/shapes/pass-prototype-shapes.ttl",
                "inference": "none",
            },
        },
    }

    report_json = json.dumps(
        report_data,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

    files = {
        "model.ttl": turtle,
        "model.owl": visio_xml,
        "validation.json": report_json + "\n",
    }

    output_directory = Path(output_directory).expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=False)

    for filename, content in files.items():
        path = output_directory / filename

        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)

    return (
        output_directory / "model.ttl",
        output_directory / "validation.json",
    )