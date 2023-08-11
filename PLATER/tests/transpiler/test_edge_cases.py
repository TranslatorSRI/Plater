"""Test transpiler edge cases."""
from PLATER.transpiler.cypher import get_query
from .fixtures import fixture_database


def test_categories(database):
    """Test multiple categories."""
    qgraph = {
        "nodes": {"n0": {"categories": [
            "biolink:Disease",
            "biolink:Gene",
        ]}},
        "edges": dict(),
    }
    output = list(database.run(get_query(qgraph)))[0]
    assert len(output['results']) == 10


def test_empty(database):
    """Test empty qgraph."""
    qgraph = {
        "nodes": dict(),
        "edges": dict(),
    }
    output = list(database.run(get_query(qgraph)))[0]
    assert len(output["results"]) == 1
    assert output["results"][0]["node_bindings"] == dict()
    assert output["results"][0]["analyses"] == list([{"edge_bindings": {}}])
    assert output["knowledge_graph"]["nodes"] == []
    assert output["knowledge_graph"]["edges"] == []


def test_category_none(database):
    """Test node with type None."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": "MONDO:0014488",
                "categories": None,
            }
        },
        "edges": dict(),
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 1


def test_relation_none(database):
    """Test edge with relation None."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Disease",
            },
            "n1": {
                "categories": "biolink:Gene",
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "relation": None,
            }
        },
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 5


def test_qnode_addl_null(database):
    """Test qnode with null-valued additional property."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Disease",
            },
            "n1": {
                "categories": "biolink:Gene",
                "chromosome": None,
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
            }
        },
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 5


def test_predicate_none(database):
    """Test edge with predicate None."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:Disease",
            },
            "n1": {
                "categories": "biolink:Gene",
            },
        },
        "edges": {
            "e01": {
                "subject": "n0",
                "object": "n1",
                "predicates": None,
            }
        },
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 5


def test_fancy_key(database):
    """Test qnode/qedge keys with unusual characters."""
    qgraph = {
        "nodes": {
            "type-2 diabetes": {
                "categories": "biolink:Disease",
            },
            "n1": {
                "categories": "biolink:Gene",
            },
        },
        "edges": {
            "interacts with": {
                "subject": "type-2 diabetes",
                "object": "n1",
            }
        },
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 5


def test_backwards_predicate(database):
    """Test an extra backwards predicate."""
    qgraph = {
        "nodes": {
            "type-2 diabetes": {
                "id": "MONDO:0005148",
                "categories": "biolink:Disease",
            },
            "drug": {
                "categories": "biolink:ChemicalSubstance",
            },
        },
        "edges": {
            "related to": {
                "subject": "type-2 diabetes",
                "object": "drug",
                "predicates": ["biolink:related_to", "biolink:treats"]
            }
        },
    }
    cypher = get_query(qgraph)
    output = list(database.run(cypher))[0]
    assert len(output["results"]) == 3


def test_index_usage_single_labels():
    """
    Test when using single labels, checks if id index is with the node type is used
    """
    qgraph = {
        "nodes": {
            "n0": {
                "ids": ["MONDO:0005148"],
                "categories": "biolink:Disease",
            }
        },
        "edges": {}
    }
    cypher = get_query(qgraph, **{"use_hints": True})
    # superclass node_id is suffixed with _superclass
    assert "USING INDEX `n0_superclass`:`biolink:Disease`(id)" in cypher


def test_index_usage_multiple_labels():
    """
    When multiple labels are used `biolink:NamedThing` index to be used
    """
    qgraph = {
        "nodes": {
            "n0": {
                "ids": ["MONDO:0005148"],
                "categories": ["biolink:Disease", "biolink:PhenotypicFeature"],
            }
        },
        "edges": {}
    }
    cypher = get_query(qgraph, **{"use_hints": True})
    # superclass node_id is suffixed with _superclass
    assert "USING INDEX `n0_superclass`:`biolink:NamedThing`(id)" in cypher