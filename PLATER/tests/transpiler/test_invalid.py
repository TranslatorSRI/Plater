"""Test invalid query graphs."""
import pytest

from PLATER.transpiler.cypher import get_query
from PLATER.transpiler.exceptions import InvalidPredicateError
from .transpiler_fixtures import fixture_database


def test_invalid_node():
    """Test that an invalid node property value throws an error."""
    qgraph = {
        "nodes": {
            "n0": {
                "categories": "biolink:BiologicalEntity",
                "dict": {"a": 1},
            },
        },
        "edges": dict(),
    }
    with pytest.raises(ValueError):
        get_query(qgraph)


def test_invalid_predicate():
    """Test that an invalid edge predicate throws an error."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": ["MONDO:0005148"],
            },
            "n1": {
                "categories": ["biolink:PhenotypicFeature"],
            },
        },
        "edges": {
            "e0": {
                "subject": "n0",
                "object": "n1",
                "predicates": ["biolink:invalid_predicate"],
            },
        },
    }
    with pytest.raises(InvalidPredicateError):
        query = get_query(qgraph)

    """Test that an invalid edge predicate throws an error, along with a valid predicate."""
    qgraph = {
        "nodes": {
            "n0": {
                "ids": ["MONDO:0005148"],
            },
            "n1": {
                "categories": ["biolink:PhenotypicFeature"],
            },
        },
        "edges": {
            "e0": {
                "subject": "n0",
                "object": "n1",
                "predicates": ["biolink:invalid_predicate", "biolink:associated_with"],
            },
        },
    }
    with pytest.raises(InvalidPredicateError):
        query = get_query(qgraph)
