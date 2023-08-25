"""Test predicate handling."""
import pytest

from PLATER.transpiler.cypher import get_query, transform_result
from .fixtures import fixture_database


def test_symmetric(database):
    """Test symmetric predicate."""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:836"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n1",
                "object": "n0",
                "predicates": "biolink:genetic_association",
            },
        },
    }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)
    assert len(output["results"]) == 2


def test_any(database):
    """Test any predicate."""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:836"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n1",
                "object": "n0",
            },
        },
    }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)
    assert len(output["results"]) == 4

def test_root_predicate(database):
    """Test root/related_to predicate."""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:836"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n1",
                "object": "n0",
                "predicates": "biolink:related_to"
            },
        },
    }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)
    assert len(output["results"]) == 4


def test_sub(database):
    """Test sub predicate."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": "MONDO:0004993",
            },
            "n1": {},
        },
        "edges": {
            "e10": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:genetic_association",
            },
        },
    }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)
    assert len(output["results"]) == 2


def test_inverse(database):
    """Test inverse predicate."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": "NCBIGene:672",
            },
            "n1": {},
        },
        "edges": {
            "e10": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:gene_associated_with_condition",
            },
        },
    }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)
    assert len(output["results"]) == 1
