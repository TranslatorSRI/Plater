import asyncio
import pytest
from PLATER.services.util.overlay import Overlay


@pytest.fixture()
def graph_interface_apoc_supported():
    class MockGI:
        def supports_apoc(self):
            return True

        async def run_apoc_cover(self, idlist):
            return [{
                'result': [
                    {
                        'subject': 'NODE:0',
                        'object': 'NODE:2',
                        'predicate': 'biolink:related_to',
                        'edge': {
                            'id': 'SUPPORT_EDGE_KG_ID_1',
                            'attr_1': [],
                            'attr_2': {}
                        }
                    }, {
                        'subject': 'NODE:00',
                        'object': 'NODE:22',
                        'predicate': 'biolink:related_to',
                        'edge': {
                            'type': 'biolink:related_to',
                            'id': 'SUPPORT_EDGE_KG_ID_2',
                            'attr_1': [],
                            'attr_2': {}
                        }
                    }, {  # Edge relating two nodes from different answers
                        # we should expect this NOT to be in response.
                        'subject': 'NODE:0',
                        'object': 'NODE:22',
                        'predicate': 'biolink:related_to',
                        'edge': {
                            'type': 'biolink:related_to',
                            'id': 'SUPPORT_EDGE_KG_ID_3'
                        }
                    }
                ]
            }]

    return MockGI()


@pytest.fixture()
def graph_interface_apoc_unsupported():
    class MockGI:
        def supports_apoc(self):
            return True

    return MockGI()


@pytest.fixture()
def reasoner_json():
    return {
        # Although this is not particularly useful in testing...
        'query_graph': {
            'nodes': {
                'n0': {'type': 'type'},
                'n1': {'type': 'type'},
                'n2': {'type': 'type'}
            },
            'edges':{
                'e0': {'subject': 'n0', 'object': 'n1'},
                'e1': {'subject': 'n1', 'object': 'n2'},
            }
        },
        # Knowledge_graph Here also we don't really care about what was in
        # kg
        'knowledge_graph':
            {
                'nodes': {},
                'edges': {}
            },
        'results': [
            {
                'node_bindings': {
                    'n0': [{'id': 'NODE:0'}],
                    'n1': [{'id': 'NODE:1'}],
                    'n2': [{'id': 'NODE:2'}],
                },
                'edge_bindings': {
                    'e0': [{'id': 'EDGE:0'}],
                    'e1': [{'id': 'EDGE:1'}],
                    'e2': [{'id': 'EDGE:2'}]
                }
            },
            {
                'node_bindings': {
                    'n0': [{'id': 'NODE:00'}],
                    'n1': [{'id': 'NODE:11'}],
                    'n2': [{'id': 'NODE:22'}],
                },
                'edge_bindings': {
                    'e0': [{'id': 'EDGE:00'}],
                    'e1': [{'id': 'EDGE:11'}],
                    'e2': [{'id': 'EDGE:22'}]
                }
            },
            {
                'node_bindings': {
                    'n0': [{'id': 'NODE:000'}],
                    'n1': [{'id': 'NODE:111'}],
                    'n2': [{'id': 'NODE:222'}],
                },
                'edge_bindings': {
                    'e0': [{'id': 'EDGE:000'}],
                    'e1': [{'id': 'EDGE:111'}],
                    'e2': [{'id': 'EDGE:222'}]
                },
            }
        ]
    }


def get_kg_ids(bindings):
    all_ids = []
    for key in bindings:
        items = bindings[key]
        for item in items:
            all_ids.append(item['id'])
    return all_ids


def test_overlay_adds_support_bindings(graph_interface_apoc_supported, reasoner_json):
    ov = Overlay(graph_interface=graph_interface_apoc_supported)
    event_loop = asyncio.get_event_loop()
    response = event_loop.run_until_complete(ov.overlay_support_edges(reasoner_json))
    edges = response['knowledge_graph']['edges']
    edge_ids = edges.keys()
    assert len(edge_ids) == 2
    assert 'SUPPORT_EDGE_KG_ID_1' in edge_ids
    assert 'SUPPORT_EDGE_KG_ID_2' in edge_ids
    checked = False
    for answer in response['results']:
        node_bindings = answer['node_bindings']
        all_node_ids = get_kg_ids(node_bindings)
        edge_bindings = answer['edge_bindings']
        all_edge_kg_ids = get_kg_ids(edge_bindings)
        if ('NODE:0' in all_node_ids and 'NODE:2' in all_node_ids) \
                or ('NODE:00' in all_node_ids and 'NODE:22' in all_node_ids):
            assert 'SUPPORT_EDGE_KG_ID_1' in all_edge_kg_ids or 'SUPPORT_EDGE_KG_ID_2' in all_edge_kg_ids
            checked = True
    assert checked
