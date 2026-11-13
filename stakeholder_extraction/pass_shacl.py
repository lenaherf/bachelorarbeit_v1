"""Validate exported RDF against the prototype's SHACL profile."""

from pathlib import Path

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import RDF, SH

from stakeholder_extraction.pass_rdf import PASS


SHAPES_PATH = (
    Path(__file__).resolve().parent.parent
    / "ontology/shapes/pass-prototype-shapes.ttl"
)

def validate_pass_graph(
    graph: Graph,
) -> tuple[bool, Graph, str]:
    """Check one exported process against the prototype shapes."""

    models = set(
        graph.subjects(RDF.type, PASS["PASSProcessModel"])
    )

    if len(models) != 1:
        raise ValueError(
            "SHACL validation expects exactly one exported process model."
        )

    shapes = Graph().parse(
        str(SHAPES_PATH),
        format="turtle",
    )

    if not any(shapes.subjects(RDF.type, SH.NodeShape)):
        raise ValueError("The SHACL file contains no node shapes.")

    conforms, results_graph, results_text = validate(
        data_graph=graph,
        shacl_graph=shapes,
        inference="none",
        meta_shacl=True,
    )

    if not isinstance(results_graph, Graph):
        raise ValueError(
            f"SHACL validation could not produce a report: {results_text}"
        )

    return bool(conforms), results_graph, str(results_text)