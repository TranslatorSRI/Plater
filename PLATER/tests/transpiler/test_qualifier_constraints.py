import pytest

from PLATER.transpiler.cypher import get_query
from .transpiler_fixtures import fixture_database

@pytest.mark.asyncio
async def test_single_qualifier(database):
    """Test edge satisfying one set of qualifier constraints is returned """
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
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    # make sure any edge s
    assert len(output["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 1

@pytest.mark.asyncio
async def test_multi_qualifier(database):
    """Test if edges satisfying constraints are returned with multiple qualifier sets"""
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
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    assert len(output["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 2

@pytest.mark.asyncio
async def test_qualifier_heirarchy(database):
    """Test if edges satisfying constraints are returned when a qualifier has a value
    that is an ancestor of the value expected in the test data edge"""
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
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
    assert len(output["results"][0]["analyses"][0]["edge_bindings"]["e10a"]) == 1

@pytest.mark.asyncio
async def test_phony_qualifier_value(database):
    """ test that no edges are returned with a qualifier value that isn't valid"""
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
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 0

@pytest.mark.asyncio
async def test_empty_qualifier_set(database):
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
    output = await database.run(get_query(qgraph), convert_to_trapi_message=True, qgraph=qgraph)
    assert len(output["results"]) == 1
