"""Persist canonical PASS elements and their provenance in Neo4j."""
from neo4j import ManagedTransaction
from stakeholder_extraction.canonical_models import CanonicalSubject, CanonicalMessageSpecification, \
    CanonicalMessageExchange
from stakeholder_extraction.canonicalization import create_canonical_subject, extend_canonical_subject, \
    create_canonical_message_exchange, create_canonical_message_specification, create_single_source_canonical_message, \
    create_single_source_canonical_exchange
from stakeholder_extraction.neo4j_connection import open_neo4j_session
from stakeholder_extraction.pass_models import PassSubject, PassMessageExchange, PassMessageSpecification

def _canonicalize_subject_transaction(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> CanonicalSubject:
    """Canonicalize one confirmed equivalent subject proposal."""

    left, right = _load_confirmed_subjects(transaction, proposal_id)

    existing = _find_existing_canonical_subject(transaction, left_uri=left.uri, right_uri=right.uri)

    if existing is None:
        canonical = create_canonical_subject(left, right)
    else:
        canonical = extend_canonical_subject(existing, left, right)

    _save_canonical_subject(transaction, proposal_id=proposal_id, canonical=canonical, left=left, right=right)

    return canonical

def canonicalize_confirmed_subject_proposal(
        proposal_id: str,
) -> CanonicalSubject:
    """Canonicalize one confirmed subject proposal in Neo4j."""
    with open_neo4j_session() as session:
        return session.execute_write(
            _canonicalize_subject_transaction,
            proposal_id,
        )

def _load_confirmed_subjects(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[PassSubject, PassSubject]:
    """Load the two subjects from a confirmed equivalent subject proposal."""
    record = transaction.run(
        """
        MATCH (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
    
        OPTIONAL MATCH
            (proposal)-[:LEFT_ELEMENT]->
                (left:PassSubject)
    
        OPTIONAL MATCH
            (proposal)-[:RIGHT_ELEMENT]->
                (right:PassSubject)
    
        RETURN
            proposal.proposal_type AS proposal_type,
            proposal.status AS status,
            left,
            right
        """,
        proposal_id=proposal_id,
    ).single()

    if record is None:
        raise ValueError(f"No reconciliation found for proposal {proposal_id}.")
    if record["proposal_type"] != "equivalent_subject":
        raise ValueError("Only equivalent subject proposals can create canonical subjects.")
    if record["status"] != "confirmed":
        raise ValueError("Only confirmed proposals can create canonical subjects.")
    if record["left"] is None or record["right"] is None:
        raise ValueError("The proposal does not reference two saved PASS subjects.")

    left = PassSubject.model_validate(dict(record["left"]))
    right = PassSubject.model_validate(dict(record["right"]))

    return left, right

def _find_existing_canonical_subject(
        transaction: ManagedTransaction,
        *,
        left_uri: str,
        right_uri: str,
) -> CanonicalSubject | None:
    """Find the canonical identity of either source subject."""
    records = list(transaction.run(
        """
        MATCH (
            canonical:CanonicalSubject
        )-[:DERIVED_FROM]->
            (source:PassSubject)
    
        WHERE source.uri IN [
            $left_uri,
            $right_uri
        ]
    
        RETURN DISTINCT canonical
        """,
        left_uri=left_uri,
        right_uri=right_uri,
    ))

    if len(records) > 1:
        raise ValueError("The proposal connects subjects that already belong to different canonical subjects")
    if not records:
        return None

    return CanonicalSubject.model_validate(dict(records[0]["canonical"]))

def _save_canonical_subject(
        transaction: ManagedTransaction,
        *,
        proposal_id: str,
        canonical: CanonicalSubject,
        left: PassSubject,
        right: PassSubject,
) -> None:
    """Save a canonical subject and its decision and provenance links."""
    record = transaction.run(
        """
        MATCH (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
        MATCH (left:PassSubject {
            uri: $left_uri
        })
        MATCH (right:PassSubject {
            uri: $right_uri
        })
        MERGE (
            canonical:
            CanonicalPassElement:
            CanonicalSubject {
                uri: $canonical_uri
            }
        )
        SET canonical.model_component_id =
                $model_component_id,
            canonical.label = $label,
            canonical.pass_type = $pass_type,
            canonical.status = $status,
            canonical.source_subject_uris =
                $source_subject_uris
        MERGE (canonical)-[:DERIVED_FROM]->(left)
        MERGE (canonical)-[:DERIVED_FROM]->(right)
        MERGE (proposal)-[:CREATED_CANONICAL]->
            (canonical)
        RETURN canonical.uri AS uri
        """,
        proposal_id=proposal_id,
        left_uri=left.uri,
        right_uri=right.uri,
        canonical_uri=canonical.uri,
        model_component_id=(canonical.model_component_id),
        label=canonical.label,
        pass_type=canonical.pass_type,
        status=canonical.status,
        source_subject_uris=list(canonical.source_subject_uris),
    ).single()

    if record is None:
        raise ValueError("Canonical subject could not be saved.")

def _load_confirmed_message_pair(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[
    PassMessageExchange,
    PassMessageExchange,
    PassMessageSpecification,
    PassMessageSpecification,
]:
    """Load both exchanges and messages from a confirmed pair."""
    record = transaction.run(
        """
         MATCH (proposal:ReconciliationProposal {
             proposal_id: $proposal_id
         })
         OPTIONAL MATCH
             (proposal)-[:LEFT_ELEMENT]->
                 (left_exchange:PassMessageExchange)
         OPTIONAL MATCH
             (proposal)-[:RIGHT_ELEMENT]->
                 (right_exchange:PassMessageExchange)
         OPTIONAL MATCH
             (left_exchange)-[
                 :HAS_MESSAGE_SPECIFICATION
             ]->(left_message:PassMessageSpecification)
         OPTIONAL MATCH
             (right_exchange)-[
                 :HAS_MESSAGE_SPECIFICATION
             ]->(right_message:PassMessageSpecification)
         RETURN
             proposal.proposal_type AS proposal_type,
             proposal.status AS status,
             left_exchange,
             right_exchange,
             left_message,
             right_message
         """,
        proposal_id=proposal_id,
    ).single()

    if record is None:
        raise ValueError(f"No reconciliation proposal found with ID '{proposal_id}'.")
    if record["proposal_type"] != "message_pair":
        raise ValueError("Only message_pair proposals can create canonical message exchanges.")
    if record["status"] != "confirmed":
        raise ValueError("Only confirmed proposals can create canonical message exchanges.")

    required_values = [
        "left_exchange",
        "right_exchange",
        "left_message",
        "right_message",
    ]

    if any(record[name] is None for name in required_values):
        raise ValueError("The proposal does not reference two complete saved message exchanges.")

    left_exchange = PassMessageExchange.model_validate(dict(record["left_exchange"]))
    right_exchange = PassMessageExchange.model_validate(dict(record["right_exchange"]))
    left_message = PassMessageSpecification.model_validate(dict(record["left_message"]))
    right_message = PassMessageSpecification.model_validate(dict(record["right_message"]))

    return left_exchange, right_exchange, left_message, right_message

def _find_canonical_subject_for_sources(
        transaction: ManagedTransaction,
        *,
        source_uris: set[str],
        role: str,
) -> CanonicalSubject:
    """Find one canonical subject covering all given source URIs."""

    records = list(transaction.run(
        """
        MATCH (
            canonical:CanonicalSubject
        )-[:DERIVED_FROM]->
            (source:PassSubject)

        WHERE source.uri IN $source_uris

        WITH
            canonical,
            count(DISTINCT source.uri)
                AS matched_sources

        WHERE matched_sources = $source_count

        RETURN canonical
        """,
        source_uris=sorted(source_uris),
        source_count=len(source_uris),
    ))

    if not records:
        raise ValueError(f"The canonical {role} must be created before canonicalizing the message pair.")
    if len(records) > 1:
        raise ValueError(f"The message pair matches multiple canonical {role} subjects.")
    return CanonicalSubject.model_validate(dict(records[0]["canonical"]))

def _save_canonical_message_specification(
        transaction: ManagedTransaction,
        *,
        message: CanonicalMessageSpecification,
        sources: tuple[PassMessageSpecification, ...],
) -> None:
    """Save a canonical message and all source links."""

    if not sources:
        raise ValueError(f"A canonical message specification must have at least one source message.")

    source_uris = [source.uri for source in sources]

    record = transaction.run(
        """
        MERGE (
            message:
            CanonicalPassElement:
            CanonicalMessageSpecification {
                uri: $uri
            }
        )
        SET message.model_component_id =
                $model_component_id,
            message.label = $label,
            message.pass_type = $pass_type,
            message.status = $status,
            message.source_message_uris =
                $source_uris
        WITH message
        UNWIND $source_uris AS source_uri
        MATCH (source:PassMessageSpecification {
            uri: source_uri
        })
        MERGE (message)-[:DERIVED_FROM]->(source)
        RETURN count(DISTINCT source) AS source_count
        """,
        uri=message.uri,
        model_component_id=message.model_component_id,
        label=message.label,
        pass_type=message.pass_type,
        status=message.status,
        source_uris=source_uris,
    ).single()

    if record is None or record["source_count"] != len(source_uris):
        raise ValueError("Not all source message specifications were found.")

def _save_canonical_exchange(
        transaction: ManagedTransaction,
        *,
        proposal_id: str,
        exchange: CanonicalMessageExchange,
        message: CanonicalMessageSpecification,
        sources: tuple[PassMessageExchange, ...],
) -> None:
    """Save a canonical exchange and its references and provenance."""

    if not sources:
        raise ValueError(f"A canonical exchange must have at least one source exchange.")

    source_uris = [source.uri for source in sources]

    record = transaction.run(
        """
                MATCH (proposal:ReconciliationProposal {
                    proposal_id: $proposal_id
                })
    
                MATCH (sender:CanonicalSubject {
                    uri: $sender_uri
                })
    
                MATCH (receiver:CanonicalSubject {
                    uri: $receiver_uri
                })
    
                MATCH (message:CanonicalMessageSpecification {
                    uri: $message_uri
                })
    
                MERGE (
                    exchange:
                    CanonicalPassElement:
                    CanonicalMessageExchange {
                        uri: $exchange_uri
                    }
                )
    
                SET exchange.model_component_id =
                        $model_component_id,
                    exchange.label = $label,
                    exchange.pass_type = $pass_type,
                    exchange.status = $status,
                    exchange.sender_uri = $sender_uri,
                    exchange.receiver_uri = $receiver_uri,
                    exchange.message_specification_uri =
                        $message_uri,
                    exchange.source_exchange_uris =
                        $source_uris
    
                MERGE (exchange)-[:HAS_SENDER]->(sender)
                MERGE (exchange)-[:HAS_RECEIVER]->(receiver)
                MERGE (exchange)-[:HAS_MESSAGE_SPECIFICATION]->
                    (message)
    
                MERGE (proposal)-[:CREATED_CANONICAL]->
                    (message)
                MERGE (proposal)-[:CREATED_CANONICAL]->
                    (exchange)
    
                WITH exchange
    
                UNWIND $source_uris AS source_uri
    
                MATCH (source:PassMessageExchange {
                    uri: source_uri
                })
    
                MERGE (exchange)-[:DERIVED_FROM]->(source)
    
                RETURN count(DISTINCT source) AS source_count
                """,
        proposal_id=proposal_id,
        sender_uri=exchange.sender_uri,
        receiver_uri=exchange.receiver_uri,
        message_uri=message.uri,
        exchange_uri=exchange.uri,
        model_component_id=exchange.model_component_id,
        label=exchange.label,
        pass_type=exchange.pass_type,
        status=exchange.status,
        source_uris=source_uris,
    ).single()

    if record is None or record["source_count"] != len(source_uris):
        raise ValueError("Not all source message exchanges were found.")

def _save_canonical_communication(
        transaction: ManagedTransaction,
        *,
        proposal_id: str,
        message: CanonicalMessageSpecification,
        exchange: CanonicalMessageExchange,
        source_messages: tuple[PassMessageSpecification, ...],
        source_exchanges: tuple[PassMessageExchange, ...],
) -> None:
    """Save canonical communication elements atomically."""

    _save_canonical_message_specification(
        transaction=transaction,
        message=message,
        sources=source_messages,
    )

    _save_canonical_exchange(
        transaction=transaction,
        proposal_id=proposal_id,
        exchange=exchange,
        message=message,
        sources=source_exchanges,
    )

def _canonicalize_message_pair_transaction(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[CanonicalMessageSpecification, CanonicalMessageExchange]:
    """Canonicalize one confirmed message pair proposal."""
    (left_exchange, right_exchange, left_message, right_message) = _load_confirmed_message_pair(transaction, proposal_id)

    sender = _find_canonical_subject_for_sources(transaction, source_uris={left_exchange.sender_uri, right_exchange.sender_uri}, role="sender")
    receiver = _find_canonical_subject_for_sources(transaction, source_uris={right_exchange.receiver_uri, left_exchange.receiver_uri}, role="receiver")
    message = create_canonical_message_specification(left_message, right_message)
    exchange = create_canonical_message_exchange(left_exchange, right_exchange, message=message, sender=sender, receiver=receiver)
    _save_canonical_communication(
        transaction,
        proposal_id=proposal_id,
        message=message,
        exchange=exchange,
        source_messages=(left_message, right_message),
        source_exchanges=(left_exchange, right_exchange),
    )

    return message, exchange

def canonicalize_confirmed_message_pair_proposal(
        proposal_id: str,
) -> tuple[CanonicalMessageSpecification, CanonicalMessageExchange]:
    """Canonicalize one confirmed message pair proposal in Neo4j."""

    with open_neo4j_session() as session:
        return session.execute_write(
            _canonicalize_message_pair_transaction,
            proposal_id,
        )

def _load_confirmed_one_sided_message(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[PassMessageExchange, PassMessageSpecification]:
    """Load the one existing exchange from a confirmed discrepancy."""

    record = transaction.run(
        """
        MATCH (proposal:ReconciliationProposal {
            proposal_id: $proposal_id
        })
        OPTIONAL MATCH
            (proposal)-[:LEFT_ELEMENT]->
                (left_exchange:PassMessageExchange)
        OPTIONAL MATCH
            (proposal)-[:RIGHT_ELEMENT]->
                (right_exchange:PassMessageExchange)
        OPTIONAL MATCH
            (left_exchange)-[
                :HAS_MESSAGE_SPECIFICATION
            ]->(left_message:PassMessageSpecification)
        OPTIONAL MATCH
            (right_exchange)-[
                :HAS_MESSAGE_SPECIFICATION
            ]->(right_message:PassMessageSpecification)
        RETURN
            proposal.proposal_type AS proposal_type,
            proposal.status AS status,
            left_exchange,
            right_exchange,
            left_message,
            right_message
        """,
        proposal_id=proposal_id,
    ).single()

    if record is None:
        raise ValueError(f"No reconciliation proposal found with ID {proposal_id}")
    if record["proposal_type"] != "one_sided_message":
        raise ValueError("Only confirmed proposals can create single source canonical messages.")
    if record["status"] != "confirmed":
        raise ValueError("Only confirmed proposals can create single source canonical messages.")

    has_left = record["left_exchange"] is not None
    has_right = record["right_exchange"] is not None

    if has_left == has_right:
        raise ValueError("A one sided proposal must reference exactly one saved message exchange.")

    if has_left:
        exchange_node = record["left_exchange"]
        message_node = record["left_message"]
    else:
        exchange_node = record["right_exchange"]
        message_node = record["right_message"]

    if message_node is None:
        raise ValueError("The one sided exchange has no saved message specification.")

    exchange = PassMessageExchange.model_validate(dict(exchange_node))

    message = PassMessageSpecification.model_validate(dict(message_node))

    return exchange, message

def _canonicalize_one_sided_message_transaction(
        transaction: ManagedTransaction,
        proposal_id: str,
) -> tuple[CanonicalMessageSpecification, CanonicalMessageExchange]:
    """Canonicalize one confirmed one-sided message."""

    source_exchange, source_message = (_load_confirmed_one_sided_message(transaction, proposal_id))

    sender = _find_canonical_subject_for_sources(transaction, source_uris={source_exchange.sender_uri}, role="sender")
    receiver = _find_canonical_subject_for_sources(transaction, source_uris={source_exchange.receiver_uri}, role="receiver")

    message = create_single_source_canonical_message(source_message)

    exchange = create_single_source_canonical_exchange(
        source_exchange,
        message=message,
        sender=sender,
        receiver=receiver
    )

    _save_canonical_communication(
        transaction,
        proposal_id=proposal_id,
        message=message,
        exchange=exchange,
        source_messages=(source_message,),
        source_exchanges=(source_exchange,),
    )

    return message, exchange

def canonicalize_confirmed_one_sided_message(
        proposal_id: str,
) -> tuple[CanonicalMessageSpecification, CanonicalMessageExchange]:
    """Canonicalize one confirmed one_sided message in Neo4j."""

    with open_neo4j_session() as session:
        return session.execute_write(
            _canonicalize_one_sided_message_transaction,
            proposal_id,
        )

