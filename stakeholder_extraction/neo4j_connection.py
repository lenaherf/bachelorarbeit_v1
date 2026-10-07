"""Provide consistently configured Neo4j sessions."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dotenv import load_dotenv
from neo4j import GraphDatabase, Session

load_dotenv()

@contextmanager
def open_neo4j_session() -> Iterator[Session]:
    """Open and safely close a Neo4j session."""
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            yield session
    finally:
        driver.close()