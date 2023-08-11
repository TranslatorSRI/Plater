import pytest

from PLATER.transpiler.cypher import get_query
from .fixtures import fixture_database


def test_single_qualifier(database):
    """Test edges satisfying all constraints are returned """
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:283871"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:affects",
                "qualifier_constraints": [
                    {
                        "qualifier_set": [
                            {
                                "qualifier_type_id": "qualified_predicate",
                                "qualifier_value": "biolink:causes"
                            }, {
                                "qualifier_type_id": "object_aspect",
                                "qualifier_value": "activity"
                            }
                        ]
                    }
                ]
            },
        },
    }
    query = get_query(qgraph)
    output = database.run(query)
    for record in output:
        assert len(record["results"]) == 1
        # make sure any edge s
        assert len(record["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 1


def test_multi_qualifier(database):
    """Test if edges satifying all constraints are returned"""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:283871"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:affects",
                "qualifier_constraints": [
                    {
                        "qualifier_set": [
                            {
                                "qualifier_type_id": "object_aspect",
                                "qualifier_value": "activity"
                            },
                        ]
                    },{
                        "qualifier_set": [
                            {
                                "qualifier_type_id": "qualified_predicate",
                                "qualifier_value": "biolink:causes"
                            }
                        ]
                    }
                ]
            },
        },
    }
    query = get_query(qgraph)
    output = database.run(query)
    for record in output:
        assert len(record["results"]) == 1
        # make sure any edge s
        assert len(record["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 2


# skipping this test for now will need to make them once qualifier heirarchy is supported
def test_qualifier_heirarchy(database):
    """Test if edges satifying all constraints are returned"""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:283871"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:affects",
                "qualifier_constraints": [
                    {
                        "qualifier_set": [
                            {
                                "qualifier_type_id": "object_aspect",
                                "qualifier_value": "activity_or_abundance"
                            },
                        ]
                    }
                ]
            },
        },
    }
    query = get_query(qgraph)
    output = database.run(query)
    for record in output:
        assert len(record["results"]) == 1
        # make sure any edge s
        assert len(record["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 1


def test_phony_qualifier_value(database):
    """Test if edges satifying all constraints are returned"""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:283871"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:affects",
                "qualifier_constraints": [
                    {
                        "qualifier_set": [
                            {
                                "qualifier_type_id": "object_aspect",
                                "qualifier_value": "some_non_existent"
                            },
                        ]
                    },
                ]
            },
        },
    }
    query = get_query(qgraph)
    output = database.run(query)
    for record in output:
        assert len(record["results"]) == 0

def test_empty_qualifier_set():
    """Test if edges satifying all constraints are returned"""
    qgraph = {
        "nodes": {
            "n0": {},
            "n1": {
                "ids": "NCBIGene:283871"
            },
        },
        "edges": {
            "e10a": {
                "subject": "n0",
                "object": "n1",
                "predicates": "biolink:affects",
                "qualifier_constraints": [
                    {
                        "qualifier_set": [
                        ]
                    },
                ]
            },
        },
    }
    query = get_query(qgraph)
    print(query)
    #for record in output:
    #    assert len(record["results"]) == 0
