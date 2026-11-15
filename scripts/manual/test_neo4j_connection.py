"""Manually verify the configured Neo4j connection.

Requires database credentials. Does not call OpenAI or create database records.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase


def main() -> None:
    load_dotenv()

    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        driver.verify_connectivity()
        print("Neo4j connection was successful")


if __name__ == "__main__":
    main()
