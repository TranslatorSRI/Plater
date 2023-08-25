"""Initialize neo4j database helper function."""
import pytest
from neo4j import GraphDatabase


@pytest.fixture(name="database", scope="module")
def fixture_database():
    """Pytest fixture for Neo4j database connection."""
    url = "bolt://localhost:7687"
    driver = GraphDatabase.driver(url, auth=None)
    with driver.session() as session:
        yield session
    driver.close()
