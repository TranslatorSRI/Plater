"""Test entity subclassing."""
import copy
import pytest
from PLATER.transpiler.cypher import get_query
from .transpiler_fixtures import fixture_database

def get_node_binding_ids_from_database_output(output):
    return [binding["id"] for result in output["results"]
            for binding_list in result["node_bindings"].values()
            for binding in binding_list]


@pytest.mark.asyncio
async def test_node_subclass(database):
    """Test node-only subclass query."""
    qgraph = {
        "nodes": {"n0": {"ids": ["MONDO:0000001"]}},
        "edges": dict(),
    }
    original_qgraph = copy.deepcopy(qgraph)
    query = get_query(qgraph)
    assert qgraph != original_qgraph  # subclass queries should change the qgraph and add qnodes etc
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 3
    node_binding_ids = get_node_binding_ids_from_database_output(output)
    assert 'MONDO:0015967' in node_binding_ids
    assert any(
        result["node_bindings"]["n0"] == [{"id": "MONDO:0005148", "query_id": "MONDO:0000001"}]
        for result in output["results"]
    )


@pytest.mark.asyncio
async def test_onehop_subclass(database):
    """Test one-hop subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["MONDO:0000001"]},
            "n1": {},
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 12


@pytest.mark.asyncio
async def test_onehop_subclass_categories():
    """Test one-hop subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["HP:0011015"], "categories": ["biolink:PhenotypicFeature"]},
            "n1": {},
        },
        "edges": {
            "e01": {
                "subject": "n1",
                "object": "n0",
                "predicates": ["biolink:treats"]
            },
        },
    }
    query = get_query(qgraph)
    #make sure that the class (PhenotypicFeature) has been removed from n0
    clause = query.split('RETURN')[0]
    elements = clause.split('-')
    checked = False
    for element in elements:
        if '`n0`' in element:
            checked = True
            assert 'PhenotypicFeature' not in element
    assert checked


@pytest.mark.asyncio
async def test_backward_subclass(database):
    """Test pinned-object one-hop subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["MONDO:0000001"]},
            "n1": {},
        },
        "edges": {
            "e01": {
                "subject": "n1",
                "object": "n0",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 12


@pytest.mark.asyncio
async def test_pinned_subclass(database):
    """Test both-pinned subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["MONDO:0000001"]},
            "n1": {"ids": ["HP:0000118"]},
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    # assert len(output['results']) == 1
    assert output["results"][0]["node_bindings"] == {
        "n0": [{"id": "MONDO:0005148", "query_id": "MONDO:0000001"}],
        "n1": [{"id": "HP:0012592", "query_id": "HP:0000118"}],
    }


@pytest.mark.asyncio
async def test_same_pinned_subclass(database):
    """Test both-pinned subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["MONDO:0000001"]},
            "n1": {"ids": ["MONDO:0000001"]},
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 4


@pytest.mark.asyncio
async def test_multihop_subclass(database):
    """Test multi-hop subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": ["MONDO:0000001"]},
            "n1": {},
            "n2": {},
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
            "e12": {
                "subject": "n1",
                "object": "n2",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert output['results']


@pytest.mark.asyncio
async def test_dont_subclass(database):
    """Test disallowing subclassing."""
    qgraph = {
        "nodes": {"n0": {"ids": ["MONDO:0000001"]}},
        "edges": dict(),
    }
    output = await database.run(get_query(qgraph, subclass=False), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 1
    assert output["results"][0]["node_bindings"] == {
        "n0": [{"id": "MONDO:0000001"}],
    }


@pytest.mark.asyncio
async def test_batch_subclass(database):
    """Test batched subclass query."""
    qgraph = {
        "nodes": {
            "n0": {"ids": [
                "MONDO:0000001",
                "HP:0000118",
            ]},
            "n1": {},
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 15
    for result in output["results"]:
        for binding in result["node_bindings"]["n0"]:
            assert "query_id" in binding
            assert (binding["query_id"] == "HP:0000118") if binding["id"].startswith("HP") else (binding["query_id"] == "MONDO:0000001")


@pytest.mark.asyncio
async def test_hierarchy_inference_on_superclass_queries(database):
    """ Test that subclass edges should not be added to explicit subclass/superclass predicate queries  """
    qgraph = {
        "nodes": {"n0": {"ids": ["MONDO:0000001"]},
                  "n1": {}},
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "predicates": ['biolink:superclass_of']
            },
        }
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 2
    node_binding_ids = get_node_binding_ids_from_database_output(output)
    assert "MONDO:0000001" in node_binding_ids
    assert "MONDO:0005148" in node_binding_ids
    assert "MONDO:0015967" in node_binding_ids
    # note that for graphs where redundant subclass edges are added results would show MONDO:0000001 as a superclass
    # of MONDO:0014488, but because that explicit edge is not included in the test data MONDO:0014488 is excluded from
    # the results, as it's a subclass of a subclass of MONDO:0000001
    assert "MONDO:0014488" not in node_binding_ids


@pytest.mark.asyncio
async def test_hierarchy_inference_on_subclass_queries(database):
    qgraph = {
        "nodes": {"n0": {"ids": ["MONDO:0005148"]},
                  "n1": {}},
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "predicates": ['biolink:subclass_of']
            },
        }
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output['results']) == 1
    node_binding_ids = [binding["id"] for binding_list in output["results"][0]["node_bindings"].values() for binding in
                        binding_list]
    assert "MONDO:0000001" in node_binding_ids
    assert "MONDO:0005148" in node_binding_ids
    assert "MONDO:0014488" not in node_binding_ids
