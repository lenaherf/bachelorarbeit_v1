"""Build PASS RDF from a selected canonical process."""

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD
from pathlib import Path
from stakeholder_extraction.canonical_models import (
    CanonicalBehaviorFragment,
    CanonicalProcessContents,
)
from stakeholder_extraction.pass_export import validate_export_request
from stakeholder_extraction.pass_export_models import PassExportOptions


PASS = Namespace("http://www.i2pm.net/standard-pass-ont#")


def _add_element(
    graph: Graph,
    *,
    uri: str,
    pass_type: str,
    component_id: str,
    label: str,
) -> URIRef:
    """Add an individual with its PASS type, identifier, and label."""

    node = URIRef(uri)

    graph.add((node, RDF.type, OWL.NamedIndividual))
    graph.add((node, RDF.type, PASS[pass_type]))
    graph.add((
        node,
        PASS["hasModelComponentID"],
        Literal(component_id, datatype=XSD.string),
    ))
    graph.add((
        node,
        PASS["hasModelComponentLabel"],
        Literal(label),
    ))

    graph.add((node, RDFS.label, Literal(label)))

    return node

def _declare_pass_vocabulary(graph: Graph) -> None:
    """Declare used PASS terms using their local ontology definitions."""

    ontology_path = (
        Path(__file__).resolve().parent.parent
        / "ontology/generated/standard_PASS_ont_dev.ttl"
    )

    schema = Graph().parse(
        str(ontology_path),
        format="turtle",
    )

    classes = {
        rdf_type
        for rdf_type in graph.objects(None, RDF.type)
        if str(rdf_type).startswith(str(PASS))
    }

    properties = {
        predicate
        for predicate in graph.predicates()
        if str(predicate).startswith(str(PASS))
    }

    for term in classes:
        if (term, RDF.type, OWL.Class) not in schema:
            raise ValueError(f"Undeclared PASS class: {term}")

        graph.add((term, RDF.type, OWL.Class))

    property_types = (
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
    )

    for term in properties:
        matches = [
            property_type
            for property_type in property_types
            if (term, RDF.type, property_type) in schema
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Cannot determine one property type for {term}"
            )

        graph.add((term, RDF.type, matches[0]))

def _add_containment(
    graph: Graph,
    container: URIRef,
    element: URIRef,
) -> None:
    """Write containment and its inverse explicitly."""

    graph.add((container, PASS["contains"], element))
    graph.add((element, PASS["belongsTo"], container))

def _add_interaction(
    graph: Graph,
    contents: CanonicalProcessContents,
    model_node: URIRef,
) -> None:
    """Add selected subjects, message specifications, and exchanges."""

    for subject in contents.subjects:
        node = _add_element(
            graph,
            uri=subject.uri,
            pass_type=subject.pass_type,
            component_id=subject.model_component_id,
            label=subject.label,
        )
        _add_containment(graph, model_node, node)

    for message in contents.messages:
        node = _add_element(
            graph,
            uri=message.uri,
            pass_type=message.pass_type,
            component_id=message.model_component_id,
            label=message.label,
        )
        _add_containment(graph, model_node, node)

    for exchange in contents.exchanges:
        node = _add_element(
            graph,
            uri=exchange.uri,
            pass_type=exchange.pass_type,
            component_id=exchange.model_component_id,
            label=exchange.label,
        )
        _add_containment(graph, model_node, node)

        sender = URIRef(exchange.sender_uri)
        receiver = URIRef(exchange.receiver_uri)
        message = URIRef(exchange.message_specification_uri)

        graph.add((node, PASS["hasSender"], sender))
        graph.add((node, PASS["hasReceiver"], receiver))
        graph.add((node, PASS["hasMessageType"], message))

        graph.add((
            sender,
            PASS["hasOutgoingMessageExchange"],
            node,
        ))
        graph.add((
            receiver,
            PASS["hasIncomingMessageExchange"],
            node,
        ))

def _add_behavior(
    graph: Graph,
    fragment: CanonicalBehaviorFragment,
    model_node: URIRef,
) -> None:
    """Export the selected behaviour as the subject's base behaviour."""

    behavior = fragment.behavior
    owner = URIRef(behavior.subject_uri)

    behavior_node = _add_element(
        graph,
        uri=behavior.uri,
        pass_type="SubjectBaseBehavior",
        component_id=behavior.model_component_id,
        label=behavior.label,
    )

    _add_containment(graph, model_node, behavior_node)

    graph.add((
        owner,
        PASS["containsBehavior"],
        behavior_node,
    ))
    graph.add((
        owner,
        PASS["containsBaseBehavior"],
        behavior_node,
    ))
    graph.add((
        behavior_node,
        PASS["isBaseBehaviorOf"],
        owner,
    ))
    graph.add((
        behavior_node,
        PASS["hasPriorityNumber"],
        Literal(1, datatype=XSD.positiveInteger),
    ))

    for state in fragment.states:
        state_node = _add_element(
            graph,
            uri=state.uri,
            pass_type=state.pass_type,
            component_id=state.model_component_id,
            label=state.label,
        )

        _add_containment(graph, behavior_node, state_node)

        if state.is_initial:
            graph.add((
                state_node,
                RDF.type,
                PASS["InitialStateOfBehavior"],
            ))
            graph.add((
                behavior_node,
                PASS["hasInitialState"],
                state_node,
            ))

        if state.is_end:
            graph.add((
                state_node,
                RDF.type,
                PASS["EndState"],
            ))
            graph.add((
                behavior_node,
                PASS["hasEndState"],
                state_node,
            ))

    _add_transitions(graph, fragment, behavior_node)

def _add_transitions(
    graph: Graph,
    fragment: CanonicalBehaviorFragment,
    behavior_node: URIRef,
) -> None:
    """Export transitions and deterministic transition-condition nodes."""

    condition_types = {
        "SendTransition": "SendTransitionCondition",
        "ReceiveTransition": "ReceiveTransitionCondition",
        "DoTransition": "DoTransitionCondition",
    }

    for transition in fragment.transitions:
        transition_node = _add_element(
            graph,
            uri=transition.uri,
            pass_type=transition.pass_type,
            component_id=transition.model_component_id,
            label=transition.label,
        )

        _add_containment(
            graph,
            behavior_node,
            transition_node,
        )

        start = URIRef(transition.source_state_uri)
        end = URIRef(transition.target_state_uri)

        graph.add((
            transition_node,
            PASS["hasSourceState"],
            start,
        ))
        graph.add((
            transition_node,
            PASS["hasTargetState"],
            end,
        ))
        graph.add((
            start,
            PASS["hasOutgoingTransition"],
            transition_node,
        ))
        graph.add((
            end,
            PASS["hasIncomingTransition"],
            transition_node,
        ))

        condition_node = _add_element(
            graph,
            uri=f"{transition.uri}:condition",
            pass_type=condition_types[transition.pass_type],
            component_id=(
                f"{transition.model_component_id}:condition"
            ),
            label=f"{transition.label} condition",
        )

        _add_containment(
            graph,
            behavior_node,
            condition_node,
        )

        graph.add((
            transition_node,
            PASS["hasTransitionCondition"],
            condition_node,
        ))

        if transition.message_exchange_uri is not None:
            graph.add((
                condition_node,
                PASS["requiresPerformedMessageExchange"],
                URIRef(transition.message_exchange_uri),
            ))

def build_pass_graph(
    contents: CanonicalProcessContents,
    options: PassExportOptions,
) -> Graph:
    """Build PASS instance RDF after checking export preconditions."""

    report = validate_export_request(contents, options)

    graph = Graph()
    graph.bind("pass", PASS)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    ontology_node = URIRef(f"{contents.model.uri}:ontology")
    graph.add((ontology_node, RDF.type, OWL.Ontology))
    graph.add((
        ontology_node,
        RDFS.comment,
        Literal(
            "Prototype PASS instance export. Ontology conformance "
            "and consuming-tool compatibility require separate validation."
        ),
    ))

    # Keep accepted warnings visible in a draft RDF export.
    for issue in report.issues:
        graph.add((
            ontology_node,
            RDFS.comment,
            Literal(
                f"{issue.severity.upper()} [{issue.code}] "
                f"{issue.element_uri}: {issue.message}"
            ),
        ))

    model = contents.model

    model_node = _add_element(
        graph,
        uri=model.uri,
        pass_type=model.pass_type,
        component_id=model.model_component_id,
        label=model.label,
    )

    start_subject = URIRef(options.start_subject_uri)

    graph.add((
        model_node,
        PASS["hasStartSubject"],
        start_subject,
    ))
    graph.add((
        start_subject,
        RDF.type,
        PASS["StartSubject"],
    ))

    _add_interaction(graph, contents, model_node)

    for fragment in contents.behavior_fragments:
        _add_behavior(graph, fragment, model_node)

    _declare_pass_vocabulary(graph)
    return graph
