import asyncio
from httpx import AsyncClient
import pytest
import json
from functools import reduce
from PLATER.services.util.graph_adapter import GraphInterface
import os

from PLATER.services.app import APP, get_graph_interface


class MockGraphInterface(GraphInterface):
    def __init__(self, *args, **kwargs):
        pass

    def get_schema(self):
        graph_schema_file_path = os.path.join(os.path.dirname(__file__), 'data', 'graph_schema.json')
        with open(graph_schema_file_path) as j_file:
            return json.load(j_file)

    async def get_mini_schema(self, source_id, target_id):
        #this function is only used by simple_spec endpoint
        # we could assert that its being called appropriately
        if source_id:
            assert source_id == 'SOME:CURIE'
        if target_id:
            assert target_id == 'SOME:CURIE'

        schema = self.get_schema()
        # flatten the schema, to mimic
        # MATCH (a)-[e]->(b) return labels(a) as source_label, type(e) as predicate, labels(b) as target_label
        flat_schema = []
        for source_type in schema:
            for target_type in schema[source_type]:
                for edge_type in schema[source_type][target_type]:
                    flat_schema.append({
                        'source_label': [source_type],
                        'predicate': edge_type,
                        'target_label': [target_type]})
        return flat_schema

    async def get_node(self, node_type, curie):
        node_list_file_path = os.path.join(os.path.dirname(__file__), 'data', 'node_list.json')
        with open(node_list_file_path) as j_file:
            return json.load(j_file)

    async def get_single_hops(self, source_type, target_type, curie):
        single_hop_triplets_file_path = os.path.join(os.path.dirname(__file__), 'data', 'single_hop_triplets.json')
        with open(single_hop_triplets_file_path) as j_file:
            return json.load(j_file)

    async def run_cypher(self, cypher, return_errors=False):

        return {
            'results': [],
            "errors": []
        }

    async def get_examples(self, source, target=None):
        single_hop_triplets_file_path = os.path.join(os.path.dirname(__file__), 'data', 'single_hop_triplets.json')
        with open(single_hop_triplets_file_path) as j_file:
            triplets = json.load(j_file)
        return reduce(lambda x, y: x + [y[0]], triplets, [])


def _graph_interface():
    return MockGraphInterface('host', 'port', ('neo4j', 'pass'))


@pytest.fixture()
def graph_interface():
    return _graph_interface()


APP.dependency_overrides[get_graph_interface] = _graph_interface


@pytest.mark.asyncio
async def test_node_response(graph_interface):
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/chemical_substance/curie")
    assert response.status_code == 200
    graph_response = await graph_interface.get_node('chemical_substance', 'curie')
    assert response.json() == graph_response


@pytest.mark.asyncio
async def test_one_hop_response(graph_interface):
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/chemical_substance/gene/CHEBI:11492")
    assert response.status_code == 200
    graph_response = await graph_interface.get_single_hops('chemical_substance', 'gene', 'CHEBI:11492')
    assert response.json() == graph_response


@pytest.mark.asyncio
async def test_cypher_response(graph_interface):
    query = 'MATCH (n) return n limit 1'
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.post("/cypher", json={
            "query": query
        })
    assert response.status_code == 200
    graph_resp = await graph_interface.run_cypher(query)
    assert response.json() == graph_resp


@pytest.mark.asyncio
async def test_graph_schema_response(graph_interface):
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/graph/schema")
    assert response.status_code == 200
    assert response.json() == graph_interface.get_schema()


@pytest.mark.asyncio
async def test_simple_one_hop_spec_response(graph_interface):
    # with out parameters it should return all the questions based on that
    # send source parameter, target parameter
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/simple_spec")
    assert response.status_code == 200
    specs = response.json()
    schema = graph_interface.get_schema()
    source_types = set(schema.keys())
    target_types = set(reduce(lambda acc, source: acc + list(schema[source].keys()), schema, []))
    spec_len = 0
    for source in schema:
        for target in schema[source]:
            spec_len += len(schema[source][target])
    assert len(specs) == spec_len

    for item in specs:
        assert item['source_type'] in source_types
        assert item['target_type'] in target_types

    # test source param
    source_type = list(schema.keys())[0]
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/simple_spec?source=SOME:CURIE")
    # response = client.get(f'/simple_spec?source=SOME:CURIE')
    assert response.status_code == 200
    async with AsyncClient(app=APP, base_url="http://test") as ac:
        response = await ac.get("/simple_spec?source=SOME:CURIE")
    # response = client.get(f'/simple_spec?target=SOME:CURIE')
    assert response.status_code == 200
