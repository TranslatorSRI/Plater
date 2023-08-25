import pytest

from PLATER.transpiler.cypher import get_query, transform_result
from .fixtures import fixture_database



def test_primary_source(database):
    qgraph = {
            "nodes": {
                "n0": {
                    "categories": ["biolink:ChemicalSubstance"]
                },
                "n1": {
                    "categories": ["biolink:Disease"],
                    "ids": ["MONDO:0005148"]
                }

            },
            "edges": {
                "e0": {
                    "subject": "n0",
                    "object": "n1",
                    "predicate": "biolink:treats"
                }
            }
        }
    database_output = database.run(get_query(qgraph))
    output = transform_result(database_output, qgraph)

    assert len(output["results"]) == 3
    assert len(output["knowledge_graph"]["edges"]) == 3
    # sample edge
    """
    {
      "predicate": "biolink:treats",
      "sources": [
        {
          "resource": null,
          "resource_role": "biolink:aggregator_knowledge_source"
        },
        {
          "resource": null,
          "resource_role": "biolink:primary_knowledge_source"
        }
      ],
      "subject": "CHEBI:136043",
      "attributes": [
        {
          "attribute_type_id": "NA",
          "original_attribute_name": "fda_approved",
          "value": false
        }
      ],
      "object": "MONDO:0005148"
    } 
    """
    edge_sources = {
        e: {
            x["resource_role"]: x["resource_id"]
            for x in output["knowledge_graph"]["edges"][e]["sources"]
            } for e in
        output["knowledge_graph"]["edges"]
    }
    assert edge_sources["metformin_treats_t2d"] == {
        "biolink:aggregator_knowledge_source": ["ctd"],
        "biolink:primary_knowledge_source": "infores:test"
    }
    # if the attributes are not set return none. Further filtering would need to be applied.
    assert edge_sources["bezafibrate_treats_t2d"] == {
        "biolink:aggregator_knowledge_source": None,
        "biolink:primary_knowledge_source": None
    }
    assert edge_sources["anagliptin_treats_t2d"] == {
        "biolink:aggregator_knowledge_source": None,
        "biolink:primary_knowledge_source": None
    }