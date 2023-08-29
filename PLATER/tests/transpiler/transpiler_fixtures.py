"""Initialize neo4j database helper function."""
import pytest
from PLATER.services.util.graph_adapter import Neo4jBoltDriver


@pytest.fixture(name="database", scope="module")
async def fixture_database():
    driver = Neo4jBoltDriver(host='localhost', port='7687', auth=('neo4j', 'plater_testing_pw'))
    yield driver
    await driver.close()
