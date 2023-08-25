#!/usr/bin/env python
"""Initialize neo4j database."""
import argparse
import logging
import time

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, DatabaseUnavailable

LOGGER = logging.getLogger(__name__)


def get_driver(url):
    """Get Neo4j driver.

    Wait up to ~512 seconds for Neo4j to be ready.
    """
    seconds = 1
    while True:
        try:
            driver = GraphDatabase.driver(url, auth=None)
            # make sure we can start and finish a session
            with driver.session() as session:
                session.run("SHOW PROCEDURES")
            return driver
        except (OSError, ServiceUnavailable, DatabaseUnavailable) as err:
            if seconds >= 256:
                raise err
            LOGGER.error(
                "Neo4j service unavailable. Trying again in %d seconds...",
                seconds
            )
            time.sleep(seconds)
            seconds *= 2


def main(hash: str = None):
    """Delete any existing data and initialize with dummy data."""
    url = "bolt://localhost:7687"
    driver = get_driver(url)
    LOGGER.info("Connected to Neo4j. Initializing...")
    if hash is not None:
        node_file = f"https://raw.githubusercontent.com/ranking-agent/reasoner/{hash}/tests/neo4j_csv/nodes.csv"
        edge_file = f"https://raw.githubusercontent.com/ranking-agent/reasoner/{hash}/tests/neo4j_csv/edges.csv"
    else:
        node_file = f"file:///nodes.csv"
        edge_file = f"file:///edges.csv"
    with driver.session() as session:
        session.run("MATCH (m) DETACH DELETE m")
        session.run(f"LOAD CSV WITH HEADERS FROM \"{node_file}\" "
                    "AS row "
                    "CALL apoc.create.node([row.category, 'biolink:NamedThing'], apoc.map.merge({"
                    "name: row.name, id: row.id"
                    "}, apoc.convert.fromJsonMap(row.props))) YIELD node "
                    "RETURN count(*)")
        session.run(f"LOAD CSV WITH HEADERS FROM \"{edge_file}\" "
                    "AS edge "
                    "MATCH (subject), (object) "
                    "WHERE subject.id = edge.subject AND object.id = edge.object "
                    "CALL apoc.create.relationship(subject, edge.predicate, "
                    "apoc.map.merge({predicate: edge.predicate, id: edge.id}, "
                    "apoc.convert.fromJsonMap(edge.props)), object) YIELD rel "
                    "RETURN count(*)")
    LOGGER.info("Done. Neo4j is ready for testing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Neo4j.")
    parser.add_argument(
        "commit_hash",
        type=str,
        help="a commit hash from github.com/ranking-agent/reasoner",
        nargs="?",
    )

    args = parser.parse_args()
    main(args.commit_hash)
