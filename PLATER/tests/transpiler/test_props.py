"""Test querying with properties."""
import pytest
from PLATER.transpiler.cypher import get_query
from .transpiler_fixtures import fixture_database

@pytest.mark.asyncio
async def test_numeric(database):
    """Test querying with numeric property."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Gene",
                "length": 277,
            },
        },
        "edges": {},
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    results = sorted(
        output["knowledge_graph"]["nodes"].values(),
        key=lambda node: node["name"],
    )
    expected_nodes = [
        "CASP3",
    ]
    for ind, result in enumerate(results):
        assert result["name"] == expected_nodes[ind]


@pytest.mark.asyncio
async def test_string(database):
    """Test querying with string property."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Gene",
                "chromosome": "17",
            },
        },
        "edges": {},
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    results = sorted(
        output["knowledge_graph"]["nodes"].values(),
        key=lambda node: node["name"],
    )
    expected_nodes = [
        "BRCA1",
    ]
    for ind, result in enumerate(results):
        assert result["name"] == expected_nodes[ind]


@pytest.mark.asyncio
async def test_bool(database):
    """Test querying with boolean property."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:ChemicalSubstance",
            },
            "n1": {
                "categories": "biolink:Disease",
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:treats",
                "fda_approved": True,
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    results = sorted(
        output["knowledge_graph"]["nodes"].values(),
        key=lambda node: node["name"],
    )
    expected_nodes = [
        "metformin", "type 2 diabetes mellitus",
    ]
    for ind, result in enumerate(results):
        assert result["name"] == expected_nodes[ind]


@pytest.mark.asyncio
async def test_publications(database):
    """Test publications."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": "NCBIGene:836",
            },
            "n1": {
                "ids": "NCBIGene:841",
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    edges = output["knowledge_graph"]["edges"]
    assert len(edges) == 1
    attributes = list(edges.values())[0]["attributes"]
    assert len(attributes) == 1
    assert attributes[0] == {
        "original_attribute_name": "publications",
        "attribute_type_id": "EDAM:data_0971",
        "value": ["xxx"],
    }


@pytest.mark.asyncio
async def test_constraints(database):
    """Test querying with 'constraints' property."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Gene",
                "constraints": [],
            },
            "n1": {
                "constraints": [],
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "attribute_constraints": [],
            },
        },
    }
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 10
