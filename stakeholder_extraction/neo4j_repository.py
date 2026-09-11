import os
from uuid import uuid4

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j import ManagedTransaction

from models import StakeholderView


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
            source_text: $source_text
            })
        CREATE (stakeholder)-[:SUBMITTED]->(view)
        """,
        stakeholder_name=view.stakeholder,
        view_id=view_id,
        source_text=view.source_text,
    )

    # Connect subject names from the LLM output to the Neo4j candidate IDs.
    subject_ids: dict[str, str] = {}

    # Store the candidate subjects.
    for position, subject in enumerate(view.candidate_subjects):
        subject_id = str(uuid4())
        subject_ids[subject.name] = subject_id

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

    # Store the candidate messages.
    for position, message in enumerate(view.candidate_messages):
        message_id=str(uuid4())

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
            sender_id = subject_ids.get(message.sender)

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
            receiver_id = subject_ids.get(message.receiver)

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
            performer_id = subject_ids.get(activity.performed_by)

            if performer_id is None:
                raise ValueError(
                    f"Activity performer '{activity.performed_by}' is not present in candidate_subjects."
                )

            transaction.run(
                """
                MATCH (activity:CandidateActivity {id: $activity_id})
                MATCH (performer:CandidateSubject {id: $performer_id})
                CREATE (activity)-[:PERFORMED_BY]->(performer)
                """,
                activity_id=activity_id,
                performer_id=performer_id,
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