"""Manually convert a Turtle export to Visio-oriented RDF/XML and validate it.

Creates a local file. Does not call OpenAI or Neo4j. Adjust the input directory inside main() before running.
"""

from pathlib import Path

from rdflib import Graph

from stakeholder_extraction.pass_shacl import validate_pass_graph
from stakeholder_extraction.pass_visio import build_visio_graph

def main() -> None:
    # Adjust this to an existing export directory containing model.ttl.
    directory = Path("exports/order-demo-001")
    base_uri = "https://example.org/pass/order-demo-001"

    source = Graph().parse(
        directory / "model.ttl",
        format="turtle",
    )

    graph = build_visio_graph(
        source,
        base_uri=base_uri,
    )

    conforms, _, report = validate_pass_graph(graph)

    if not conforms:
        raise ValueError(report)

    target = directory / "model-visio-refactor.owl"

    with target.open("x", encoding="utf-8") as output:
        output.write(graph.serialize(format="xml", base=base_uri))

    print(f"Created: {target}")


if __name__ == "__main__":
    main()
