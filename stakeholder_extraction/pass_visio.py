"""Adapt canonical PASS RDF for the Visio importer."""

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD
from stakeholder_extraction.pass_rdf import PASS


ALPS = Namespace("http://www.imi.kit.edu/abstract-pass-ont#")

def _add_visio_element(
    graph: Graph,
    *,
    model: URIRef,
    base_uri: str,
    local_id: str,
    element_type: URIRef,
    label: str,
) -> URIRef:
    """Add a diagram-support element and link it to the process."""

    node = URIRef(f"{base_uri}#{local_id}")

    graph.add((node, RDF.type, OWL.NamedIndividual))
    graph.add((node, RDF.type, element_type))
    graph.add((element_type, RDF.type, OWL.Class))

    graph.add((
        node,
        PASS.hasModelComponentID,
        Literal(local_id, datatype=XSD.string),
    ))

    graph.add((node, PASS.hasModelComponentLabel, Literal(label)))
    graph.add((node, RDFS.label, Literal(label)))
    graph.add((model, PASS.contains, node))

    return node

def _copy_with_visio_uris(
    source: Graph,
    base_uri: str,
) -> Graph:
    """Copy the source graph with Visio-compatible element URIs."""
    # Give every model element a URI containing "#".
    individuals = set(source.subjects(RDF.type, OWL.NamedIndividual))
    uri_mapping = {}

    for node in individuals:
        component_id = str(source.value(node, PASS.hasModelComponentID))
        local_id = component_id.replace(":", "_")
        uri_mapping[node] = URIRef(f"{base_uri}#{local_id}")

    assert len(set(uri_mapping.values())) == len(individuals)

    for node in source.subjects(RDF.type, OWL.Ontology):
        uri_mapping[node] = URIRef(base_uri)

    # Rewrite subjects and references together.
    graph = Graph()
    graph.bind("pass", PASS)
    graph.bind("alps", ALPS)
    graph.bind("owl", OWL)

    for subject, predicate, object_ in source:
        graph.add((
            uri_mapping.get(subject, subject),
            predicate,
            uri_mapping.get(object_, object_),
        ))

    # Keep component IDs consistent with the new URI fragments.
    for original in individuals:
        node = uri_mapping[original]
        local_id = str(node).split("#", 1)[1]
        graph.set((
            node,
            PASS.hasModelComponentID,
            Literal(local_id, datatype=XSD.string),
        ))

    return graph

def _add_sid_layer(
    graph: Graph,
    model: URIRef,
    base_uri: str,
) -> URIRef:
    """Create the SID layer containing the original process members."""

    members = set(graph.objects(model, PASS.contains))

    layer = _add_visio_element(
        graph,
        model=model,
        base_uri=base_uri,
        local_id="SID_1",
        element_type=ALPS.ModelLayer,
        label="Subject interaction",
    )

    graph.add((
        layer,
        PASS.hasPriorityNumber,
        Literal(1, datatype=XSD.positiveInteger),
    ))

    for member in members:
        graph.add((layer, PASS.contains, member))

    return layer

def _add_message_lists(
    graph: Graph,
    model: URIRef,
    layer: URIRef,
    base_uri: str,
) -> None:
    """Create one message list for each sender-receiver pair."""
    # Group message exchanges by sender and receiver for SID connectors.
    groups = {}

    for exchange in graph.subjects(RDF.type, PASS.MessageExchange):
        pair = (
            graph.value(exchange, PASS.hasSender),
            graph.value(exchange, PASS.hasReceiver),
        )
        groups.setdefault(pair, []).append(exchange)

    ordered_pairs = sorted(
        groups,
        key=lambda pair: tuple(map(str, pair)),
    )

    for index, pair in enumerate(ordered_pairs, start=1):
        connector = _add_visio_element(
            graph,
            model=model,
            base_uri=base_uri,
            local_id=f"MessageExchangeList_{index}",
            element_type=PASS.MessageExchangeList,
            label=f"Messages {index}",
        )
        graph.add((layer, PASS.contains, connector))

        for exchange in groups[pair]:
            graph.add((connector, PASS.contains, exchange))

def _apply_parser_compatibility(
    graph: Graph,
    model: URIRef,
) -> None:
    """Make literals, behavior types and membership explicit."""
    # Explicit string datatypes prevent the older parser
    # from interpreting plain text values as URIs.
    for subject, predicate, object_ in list(graph):
        if (
                isinstance(object_, Literal)
                and object_.datatype is None
                and not object_.language
        ):
            graph.remove((subject, predicate, object_))

            graph.add((
                subject,
                predicate,
                Literal(str(object_), datatype=XSD.string),
            ))

    # Also expose base behaviors as SubjectBehavior
    # so the Visio factory can select its drawing implementation.
    for behavior in list(
            graph.subjects(RDF.type, PASS.SubjectBaseBehavior)
    ):
        graph.add((behavior, RDF.type, PASS.SubjectBehavior))

    graph.add((PASS.SubjectBehavior, RDF.type, OWL.Class))

    # Explicitly list all model elements at process level
    # so the importer can prepare them before resolving references.
    for element in list(
            graph.subjects(RDF.type, OWL.NamedIndividual)
    ):
        if element != model:
            graph.add((model, PASS.contains, element))

def _add_communication_references(
    graph: Graph,
) -> None:
    """Populate communication partners and messages from exchanges."""
    # Make communication details explicit for the Visio importer.
    for condition_type, partner_property, message_property, exchange_role in [
        (
                PASS.SendTransitionCondition,
                PASS.requiresMessageSentTo,
                PASS.requiresSendingOfMessage,
                PASS.hasReceiver,
        ),
        (
                PASS.ReceiveTransitionCondition,
                PASS.requiresMessageSentFrom,
                PASS.requiresReceptionOfMessage,
                PASS.hasSender,
        ),
    ]:
        for condition in list(graph.subjects(RDF.type, condition_type)):
            exchange = graph.value(
                condition,
                PASS.requiresPerformedMessageExchange,
                any=False,
            )

            if not isinstance(exchange, URIRef):
                raise ValueError(f"Missing message exchange: {condition}")

            partner = graph.value(exchange, exchange_role, any=False)
            message = graph.value(
                exchange, PASS.hasMessageType, any=False
            )

            if (
                    not isinstance(partner, URIRef)
                    or not isinstance(message, URIRef)
            ):
                raise ValueError(
                    f"Incomplete message exchange: {exchange}"
                )

            graph.set((condition, partner_property, partner))
            graph.set((condition, message_property, message))

            graph.add((
                partner_property, RDF.type, OWL.ObjectProperty
            ))
            graph.add((
                message_property, RDF.type, OWL.ObjectProperty
            ))

def build_visio_graph(
    source: Graph,
    *,
    base_uri: str,
) -> Graph:
    """Create a Visio-compatible copy of a canonical PASS graph."""

    graph = _copy_with_visio_uris(source, base_uri)

    model = next(
        graph.subjects(RDF.type, PASS.PASSProcessModel)
    )

    layer = _add_sid_layer(graph, model, base_uri)

    _add_message_lists(graph, model, layer, base_uri)
    _apply_parser_compatibility(graph, model)
    _add_communication_references(graph)

    return graph
