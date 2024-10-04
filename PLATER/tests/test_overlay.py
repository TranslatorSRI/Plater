import asyncio
import pytest
from PLATER.services.util.overlay import Overlay


@pytest.fixture()
def graph_interface_apoc_supported():
    class MockGI:
        def supports_apoc(self):
            return True

        async def run_apoc_cover(self, idlist):
            return {
                "SUPPORT_EDGE_KG_ID_1": {
                    "subject": "NODE:0",
                    "predicate": "biolink:related_to",
                    "object": "NODE:2",
                    "attributes": [
                        {"original_attribute_name": "attr_1",
                         "value": [],
                         "attribute_type_id": "biolink:Attribute",
                         "value_type_id": "EDAM:data_0006"},
                        {"original_attribute_name": "attr_2",
                         "value": 1,
                         "attribute_type_id": "biolink:Attribute",
                         "value_type_id": "EDAM:data_0006"}]
                },
                "SUPPORT_EDGE_KG_ID_2": {
                    "subject": "NODE:00",
                    "predicate": "biolink:related_to",
                    "object": "NODE:22",
                    "attributes": [
                        {"original_attribute_name": "attr_1",
                         "value": [],
                         "attribute_type_id": "biolink:Attribute",
                         "value_type_id": "EDAM:data_0006"},
                        {"original_attribute_name": "attr_2",
                         "value": 1,
                         "attribute_type_id": "biolink:Attribute",
                         "value_type_id": "EDAM:data_0006"}]
                },
                "SUPPORT_EDGE_KG_ID_3": {
                    "subject": "NODE:0",
                    "predicate": "biolink:related_to",
                    "object": "NODE:22",
                    "attributes": []
                },

            }

    return MockGI()


@pytest.fixture()
def graph_interface_apoc_unsupported():
    class MockGI:
        def supports_apoc(self):
            return True

    return MockGI()


@pytest.fixture()
def reasoner_json():
    return \
    {"query_graph":{"nodes":{"n0":{"type":"type"},"n1":{"type":"type"},"n2":{"type":"type"}},
                   "edges":{"e0":{"subject":"n0","object":"n1"},"e1":{"subject":"n1","object":"n2"}}},
    "knowledge_graph":{"nodes":{},"edges":{}},
    "results":[
        {"analyses":[{"edge_bindings":{"e0":[{"id":"EDGE:0"}],"e1":[{"id":"EDGE:1"}],"e2":[{"id":"EDGE:2"}]}}],
         "node_bindings":{"n0":[{"id":"NODE:0"}],"n1":[{"id":"NODE:1"}],"n2":[{"id":"NODE:2"}]}},
        {"analyses":[{"edge_bindings":{"e0":[{"id":"EDGE:00"}],"e1":[{"id":"EDGE:11"}],"e2":[{"id":"EDGE:22"}]}}],
         "node_bindings":{"n0":[{"id":"NODE:00"}],"n1":[{"id":"NODE:11"}],"n2":[{"id":"NODE:22"}]}},
        {"analyses":[{"edge_bindings":{"e0":[{"id":"EDGE:000"}],"e1":[{"id":"EDGE:111"}],"e2":[{"id":"EDGE:222"}]}}],
         "node_bindings":{"n0":[{"id":"NODE:000"}],"n1":[{"id":"NODE:111"}],"n2":[{"id":"NODE:222"}]}}]}


def get_kg_ids(bindings):
    all_ids = []
    for key in bindings:
        items = bindings[key]
        for item in items:
            all_ids.append(item['id'])
    return all_ids


def test_overlay_adds_support_bindings(graph_interface_apoc_supported, reasoner_json):
    ov = Overlay(graph_interface=graph_interface_apoc_supported)
    response = asyncio.run(ov.connect_k_nodes(reasoner_json))
    edges = response['knowledge_graph']['edges']
    edge_ids = edges.keys()
    assert len(edge_ids) == 2
    assert 'SUPPORT_EDGE_KG_ID_1' in edge_ids
    assert 'SUPPORT_EDGE_KG_ID_2' in edge_ids
    checked = False
    for answer in response['results']:
        node_bindings = answer['node_bindings']
        all_node_ids = get_kg_ids(node_bindings)
        edge_bindings = answer['analyses'][0]['edge_bindings']
        all_edge_kg_ids = get_kg_ids(edge_bindings)
        if ('NODE:0' in all_node_ids and 'NODE:2' in all_node_ids) \
                or ('NODE:00' in all_node_ids and 'NODE:22' in all_node_ids):
            assert 'SUPPORT_EDGE_KG_ID_1' in all_edge_kg_ids or 'SUPPORT_EDGE_KG_ID_2' in all_edge_kg_ids
            checked = True
    assert checked
