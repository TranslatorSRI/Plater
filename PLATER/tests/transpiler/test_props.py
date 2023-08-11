"""Test querying with properties."""
from PLATER.transpiler.cypher import get_query
from .fixtures import fixture_database


def test_numeric(database):
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
    output = database.run(get_query(qgraph))
    for record in output:
        assert len(record["results"]) == 1
        results = sorted(
            record["knowledge_graph"]["nodes"].values(),
            key=lambda node: node["name"],
        )
        expected_nodes = [
            "CASP3",
        ]
        for ind, result in enumerate(results):
            assert result["name"] == expected_nodes[ind]


def test_string(database):
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
    output = database.run(get_query(qgraph))
    for record in output:
        assert len(record["results"]) == 1
        results = sorted(
            record["knowledge_graph"]["nodes"].values(),
            key=lambda node: node["name"],
        )
        expected_nodes = [
            "BRCA1",
        ]
        for ind, result in enumerate(results):
            assert result["name"] == expected_nodes[ind]


def test_bool(database):
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
    output = database.run(get_query(qgraph))
    for record in output:
        assert len(record["results"]) == 1
        results = sorted(
            record["knowledge_graph"]["nodes"].values(),
            key=lambda node: node["name"],
        )
        expected_nodes = [
            "metformin", "type 2 diabetes mellitus",
        ]
        for ind, result in enumerate(results):
            assert result["name"] == expected_nodes[ind]


def test_publications(database):
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
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    edges = output["knowledge_graph"]["edges"]
    assert len(edges) == 1
    attributes = list(edges.values())[0]["attributes"]
    assert len(attributes) == 1
    assert attributes[0] == {
        "original_attribute_name": "publications",
        "attribute_type_id": "EDAM:data_0971",
        "value": ["xxx"],
    }


def test_constraints(database):
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
    output = list(database.run(get_query(qgraph)))[0]
    assert len(output["results"]) == 10
