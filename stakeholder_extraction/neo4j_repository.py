import os
from uuid import uuid4

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j import ManagedTransaction

from stakeholder_extraction.models import (
    CandidateActivity,
    CandidateMessage,
    CandidateSubject,
    CandidateState,
    CandidateTransition,
    OpenQuestion,
    StakeholderView,
)


load_dotenv()

def _enum_value(value):
    """Convert an Enum into its string value if necessary."""
    return value.value if hasattr(value, 'value') else value

def _save_view_transaction(
        transaction: ManagedTransaction,
        view: StakeholderView,
        view_id: str,
) -> None:
    # Create or find the stakeholder submitting a StakeholderView
    transaction.run(
        """
        MERGE (stakeholder:Stakeholder {name: $stakeholder_name})
        CREATE (view:StakeholderView {
            view_id: $view_id,
            stakeholder: $stakeholder_name,
            source_text: $source_text,
            corrected_text: $corrected_text,
            prepared_text: $prepared_text
            })
        CREATE (stakeholder)-[:SUBMITTED]->(view)
        """,
        stakeholder_name=view.stakeholder,
        view_id=view_id,
        source_text=view.source_text,
        corrected_text=view.corrected_text,
        prepared_text=view.prepared_text,
    )

    # Connect subject names from the LLM output to the Neo4j candidate IDs.
    subject_ids_by_name: dict[str, list[str]] = {}

    # Store the candidate subjects.
    for position, subject in enumerate(view.candidate_subjects):
        subject_id = str(uuid4())
        subject_ids_by_name.setdefault(subject.name, []).append(subject_id)

        transaction.run(
            """
            MATCH (view:StakeholderView {view_id: $view_id})
            CREATE (subject:CandidateSubject {
                id: $subject_id,
                position: $position,
                name: $name,
                evidence: $evidence,
                status: $status
            })
            CREATE (view)-[:CONTAINS]->(subject)
            """,
            view_id=view_id,
            subject_id=subject_id,
            position=position,
            name=subject.name,
            evidence=subject.evidence,
            status=_enum_value(subject.status),
        )

    def resolve_subject_id(
            subject_name: str,
            *,
            reference_description,
    ) -> str:
        matching_ids = subject_ids_by_name.get(subject_name, [])

        if len(matching_ids) == 0:
            raise ValueError(f"{reference_description} '{subject_name}' is not present in candidate_subjects.")

        if len(matching_ids) > 1:
            raise ValueError(f"{reference_description} '{subject_name}' matches multiple candidate_subjects.")

        return matching_ids[0]

    # Store the candidate messages.
    message_ids_by_name: dict[str, list[str]] = {}

    for position, message in enumerate(view.candidate_messages):
        message_id=str(uuid4())

        if message.name is not None:
            message_ids_by_name.setdefault(message.name, []).append(message_id)

        transaction.run(
            """
            MATCH (view:StakeholderView {view_id: $view_id})
            CREATE (message:CandidateMessage {
                id: $message_id,
                position: $position,
                name: $name,
                sender_name: $sender_name,
                receiver_name: $receiver_name,
                evidence: $evidence,
                status: $status
            })
            CREATE (view)-[:CONTAINS]->(message)
            """,
            view_id=view_id,
            message_id=message_id,
            position=position,
            name=message.name,
            sender_name=message.sender,
            receiver_name=message.receiver,
            evidence=message.evidence,
            status=_enum_value(message.status),
        )

        #Connect message to its local sender candidate.
        if message.sender is not None:
            sender_id = resolve_subject_id(message.sender, reference_description="Message sender")

            if sender_id is None:
                raise ValueError(
                    f"Message sender '{message.sender}' is not present in candidate subjects."
                )

            transaction.run(
                """
                MATCH (message:CandidateMessage {id: $message_id})
                MATCH (sender:CandidateSubject {id: $sender_id})
                CREATE (message)-[:SENT_BY]->(sender)
                """,
                message_id=message_id,
                sender_id=sender_id,
            )

        #Connect the message to its local receiver candidate.
        if message.receiver is not None:
            receiver_id = resolve_subject_id(message.receiver, reference_description="Message receiver")

            if receiver_id is None:
                raise ValueError(
                    f"Message receiver '{message.receiver}' is not present in candidate_subjects."
                )

            transaction.run(
                """
                MATCH (message:CandidateMessage {id: $message_id})
                MATCH (receiver:CandidateSubject {id: $receiver_id})
                CREATE (message)-[:RECEIVED_BY]->(receiver)
                """,
                message_id=message_id,
                receiver_id=receiver_id,
            )

    # Store the candidate activities.
    for position, activity in enumerate(view.candidate_activities):
        activity_id = str(uuid4())

        transaction.run(
            """
            MATCH (view:StakeholderView {view_id: $view_id})
            CREATE (activity:CandidateActivity {
                id: $activity_id,
                position: $position,
                name: $name,
                performed_by_name: $performed_by_name,
                evidence: $evidence,
                status: $status
            })
            CREATE (view)-[:CONTAINS]->(activity)
            """,
            view_id=view_id,
            activity_id=activity_id,
            position=position,
            name=activity.name,
            performed_by_name=activity.performed_by,
            evidence=activity.evidence,
            status=_enum_value(activity.status),
        )

        if activity.performed_by is not None:
            performer_id = resolve_subject_id(activity.performed_by, reference_description="Activity performer")

            if performer_id is None:
                raise ValueError(f"Activity performer '{activity.performed_by}' is not present in candidate_subjects.")

            transaction.run(
                """
                MATCH (activity:CandidateActivity {id: $activity_id})
                MATCH (performer:CandidateSubject {id: $performer_id})
                CREATE (activity)-[:PERFORMED_BY]->(performer)
                """,
                activity_id=activity_id,
                performer_id=performer_id,
            )

    # Store Candidate Behavior states.
    state_ids: dict[str, str] = {}

    for position, state in enumerate(view.candidate_states):

        if state.local_id in state_ids:
            raise ValueError(f"Duplicate candidate state local_id '{state.local_id}'.")

        state_id = str(uuid4())
        state_ids[state.local_id] = state_id

        transaction.run(
            """
            MATCH (view:StakeholderView {
                view_id: $view_id
            })
            CREATE (state:CandidateState {
                id: $state_id,
                position: $position,
                local_id: $local_id,
                name: $name,
                state_type: $state_type,
                performed_by_name: $performed_by_name,
                message_name: $message_name,
                is_initial: $is_initial,
                is_end: $is_end,
                evidence: $evidence,
                status: $status
            })
            CREATE (view)-[:CONTAINS]->(state)
            """,
            view_id=view_id,
            state_id=state_id,
            position=position,
            local_id=state.local_id,
            name=state.name,
            state_type=_enum_value(
                state.state_type
            ),
            performed_by_name=state.performed_by,
            message_name=state.message_name,
            is_initial=state.is_initial,
            is_end=state.is_end,
            evidence=state.evidence,
            status=_enum_value(state.status),
        )

        if state.performed_by is not None:
            performer_id = resolve_subject_id(state.performed_by, reference_description="State performer")

            if performer_id is None:
                raise ValueError(f"State performer '{state.performed_by}' is not present in candidate_subjects.")

            transaction.run(
                """
                MATCH (state:CandidateState {
                    id: $state_id
                })
                MATCH (performer:CandidateSubject {
                    id: $performer_id
                })
                CREATE (state)-[:PERFORMED_BY]->
                    (performer)
                """,
                state_id=state_id,
                performer_id=performer_id,
            )

        if state.message_name is not None:
            matching_message_ids = message_ids_by_name.get(state.message_name, [])

            if len(matching_message_ids) == 0:
                raise ValueError(f"State message '{state.message_name}' is not present in candidate_messages.")

            if len(matching_message_ids) > 1:
                raise ValueError(f"State message '{state.message_name}' matches multiple candidate_messages.")

            transaction.run(
                """
                MATCH (state:CandidateState {
                    id: $state_id
                })
                MATCH (message:CandidateMessage {
                    id: $message_id
                })
                CREATE (state)-[:REFERENCES_MESSAGE]->
                    (message)
                """,
                state_id=state_id,
                message_id=matching_message_ids[0],
            )

    # Store candidate behavior transitions.
    for position, transition in enumerate(view.candidate_transitions):
        source_id = state_ids.get(transition.source_state_id)
        target_id = state_ids.get(transition.target_state_id)

        if source_id is None:
            raise ValueError(f"Transition source state '{transition.source_state_id}' does not exist.")

        if target_id is None:
            raise ValueError(f"Transition target state '{transition.target_state_id}' does not exist.")

        transition_id = str(uuid4())

        transaction.run(
            """
            MATCH (view:StakeholderView {
                view_id: $view_id
            })
            MATCH (source:CandidateState {
                id: $source_id
            })
            MATCH (target:CandidateState {
                id: $target_id
            })
            CREATE (transition:CandidateTransition {
                id: $transition_id,
                position: $position,
                source_state_id: $source_state_local_id,
                target_state_id: $target_state_local_id,
                sequence_evidence: $sequence_evidence,
                status: $status
            })
            CREATE (view)-[:CONTAINS]->(transition)
            CREATE (transition)-[:FROM_STATE]->(source)
            CREATE (transition)-[:TO_STATE]->(target)
            """,
            view_id=view_id,
            transition_id=transition_id,
            position=position,
            source_id=source_id,
            target_id=target_id,
            source_state_local_id=(
                transition.source_state_id
            ),
            target_state_local_id=(
                transition.target_state_id
            ),
            sequence_evidence=(
                transition.sequence_evidence
            ),
            status=_enum_value(transition.status),
        )

    # 5. Store clarification questions.
    for position, question in enumerate(view.open_questions):
        question_id = str(uuid4())

        transaction.run(
            """
            MATCH (view:StakeholderView {view_id: $view_id})
            CREATE (question:OpenQuestion {
                id: $question_id,
                position: $position,
                related_element_type: $related_element_type,
                related_field: $related_field,
                reason: $reason,
                question: $question
            })
            CREATE (view)-[:HAS_QUESTION]->(question)
            """,
            view_id=view_id,
            question_id=question_id,
            position=position,
            related_element_type=_enum_value(
                question.related_element_type
            ),
            related_field=question.related_field,
            reason=_enum_value(question.reason),
            question=question.question,
        )

def save_stakeholder_view(view: StakeholderView) -> str:
    """
    Save a complete StakeholderView in Neo4j.

    Returns the ID of the newly created StakeholderView.
    """
    view_id = str(uuid4())

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(
            os.environ["NEO4J_USERNAME"],
            os.environ["NEO4J_PASSWORD"],
        ),
    )

    try:
        with driver.session(
            database=os.getenv("NEO4J_DATABASE", "neo4j")
        ) as session:
            session.execute_write(
                _save_view_transaction,
                view,
                view_id,
            )
    finally:
        driver.close()

    return view_id

def _get_view_transaction(
        transaction: ManagedTransaction,
        view_id: str,
) -> StakeholderView | None:
    view_record = transaction.run(
        """
        MATCH (view:StakeholderView {view_id: $view_id})
        RETURN
            view.stakeholder AS stakeholder,
            view.source_text AS source_text,
            view.corrected_text AS corrected_text,
            view.prepared_text AS prepared_text
        """,
        view_id=view_id,
    ).single()

    if view_record is None:
        return None

    subject_records = transaction.run(
        """
        MATCH (view:StakeholderView {view_id: $view_id})
            -[:CONTAINS]->(subject:CandidateSubject)
        RETURN 
            subject.name AS name,
            subject.evidence AS evidence,
            subject.status AS status
        ORDER BY subject.position
        """,
        view_id=view_id,
    )

    subjects = [
        CandidateSubject(
            name=record["name"],
            evidence=record["evidence"],
            status=record["status"],
        )
        for record in subject_records
    ]

    message_records = transaction.run(
        """
        MATCH (view:StakeholderView {view_id: $view_id})
            -[:CONTAINS]->(message:CandidateMessage)
        RETURN
            message.name AS name,
            message.sender_name AS sender,
            message.receiver_name AS receiver,
            message.evidence AS evidence,
            message.status AS status
        ORDER BY message.position
        """,
        view_id=view_id,
    )

    messages = [
        CandidateMessage(
            name=record["name"],
            sender=record["sender"],
            receiver=record["receiver"],
            evidence=record["evidence"],
            status=record["status"],
        )
        for record in message_records
    ]

    activity_records = transaction.run(
        """
        MATCH (view:StakeholderView {view_id: $view_id})
            -[:CONTAINS]->(activity:CandidateActivity)
        RETURN
            activity.name AS name,
            activity.performed_by_name AS performed_by,
            activity.evidence AS evidence,
            activity.status AS status
        ORDER BY activity.position
        """,
        view_id=view_id,
    )

    activities = [
        CandidateActivity(
            name=record["name"],
            performed_by=record["performed_by"],
            evidence=record["evidence"],
            status=record["status"],
        )
        for record in activity_records
    ]

    state_records = transaction.run(
        """
        MATCH (view:StakeholderView {
            view_id: $view_id
        })-[:CONTAINS]->(state:CandidateState)
        RETURN
            state.local_id AS local_id,
            state.name AS name,
            state.state_type AS state_type,
            state.performed_by_name AS performed_by,
            state.message_name AS message_name,
            state.is_initial AS is_initial,
            state.is_end AS is_end,
            state.evidence AS evidence,
            state.status AS status
        ORDER BY state.position
        """,
        view_id=view_id,
    )

    states = [
        CandidateState(
            local_id=record["local_id"],
            name=record["name"],
            state_type=record["state_type"],
            performed_by=record["performed_by"],
            message_name=record["message_name"],
            is_initial=record["is_initial"],
            is_end=record["is_end"],
            evidence=record["evidence"],
            status=record["status"],
        )
        for record in state_records
    ]

    transition_records = transaction.run(
    """
        MATCH (view:StakeholderView {
            view_id: $view_id
        })-[:CONTAINS]->
            (transition:CandidateTransition)
        RETURN
            transition.source_state_id
                AS source_state_id,
            transition.target_state_id
                AS target_state_id,
            transition.sequence_evidence
                AS sequence_evidence,
            transition.status AS status
        ORDER BY transition.position
        """,
        view_id=view_id,
    )

    transitions = [
        CandidateTransition(
            source_state_id=record["source_state_id"],
            target_state_id=record["target_state_id"],
            sequence_evidence=record["sequence_evidence"],
            status=record["status"],
        )
        for record in transition_records
    ]

    question_records = transaction.run(
"""
       MATCH (view:StakeholderView {view_id: $view_id})
           -[:HAS_QUESTION]->(open_question:OpenQuestion)
       RETURN
           open_question.related_element_type AS related_element_type,
           open_question.related_field AS related_field,
           open_question.reason AS reason,
           open_question.question AS question
       ORDER BY open_question.position
       """,
       view_id=view_id,
    )

    questions = [
        OpenQuestion(
            related_element_type=record["related_element_type"],
            related_field=record["related_field"],
            reason=record["reason"],
            question=record["question"],
        )
        for record in question_records
    ]

    return StakeholderView(
        stakeholder=view_record["stakeholder"],
        source_text=view_record["source_text"],
        corrected_text=view_record["corrected_text"],
        prepared_text=view_record["prepared_text"],
        candidate_subjects=subjects,
        candidate_messages=messages,
        candidate_activities=activities,
        open_questions=questions,
        candidate_states=states,
        candidate_transitions=transitions,
    )

def get_stakeholder_view(view_id: str) -> StakeholderView:
    """
    Load a StakeholderView from Neo4j.

    Raises ValueError if the requested view does not exist.
    """
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(
            os.environ["NEO4J_USERNAME"],
            os.environ["NEO4J_PASSWORD"],
        ),
    )

    try:
        with driver.session(
            database=os.getenv("NEO4J_DATABASE", "neo4j")
        ) as session:
            view = session.execute_read(
                _get_view_transaction,
                view_id,
            )
    finally:
        driver.close()

    if view is None:
        raise ValueError(f"No StakeholderView found with view_id '{view_id}'.")
    return view