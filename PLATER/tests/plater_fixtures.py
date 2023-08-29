"""Fixtures to be used by pytests."""
import pytest_asyncio
from PLATER.services.util.graph_adapter import GraphInterface, Neo4jBoltDriver


@pytest_asyncio.fixture(name="bolt_graph_adapter", scope="module")
async def bolt_graph_adapter():
    gi = GraphInterface('localhost', '7687', auth=('neo4j', 'plater_testing_pw'), protocol='bolt')
    yield gi
    await gi.close()
    GraphInterface.instance = None


@pytest_asyncio.fixture(name="bolt_neo4j_driver", scope="module")
async def bolt_neo4j_driver():
    driver = Neo4jBoltDriver(host='localhost', port='7687', auth=('neo4j', 'plater_testing_pw'))
    yield driver
    await driver.close()

