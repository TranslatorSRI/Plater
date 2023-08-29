import json

import neo4j.exceptions
import pytest
import os
from collections import defaultdict
from PLATER.services.util.graph_adapter import Neo4jBoltDriver, GraphInterface
from .plater_fixtures import bolt_graph_adapter, bolt_neo4j_driver


def test_bolt_graph_adapter_initialization(bolt_graph_adapter):
    assert bolt_graph_adapter is not None


@pytest.mark.asyncio
async def test_bolt_graph_adapter_auth_failure():
    driver = None
    try:
        driver = Neo4jBoltDriver('localhost', '7687', auth=('neo4j', 'invalid_password'))
        assert False
    except neo4j.exceptions.ClientError as e:
        assert e.code == "Neo.ClientError.Security.Unauthorized"
    finally:
        if driver:
            await driver.close()

@pytest.mark.asyncio
async def test_neo4j_bolt_driver_run_cypher(bolt_neo4j_driver):
    expected_response = [{"node_count": 17}]
    query = "MATCH (n) RETURN count(n) as node_count"

    response = await bolt_neo4j_driver.run(query, convert_to_dict=True)
    assert response == expected_response

    response = bolt_neo4j_driver.run_sync(query, convert_to_dict=True)
    assert response == expected_response


@pytest.mark.asyncio
async def test_neo4j_bolt_driver_run_cypher_fail(bolt_neo4j_driver):
    query = "BAD SYNTAX CYPHER QUERY"
    response = await bolt_neo4j_driver.run(query, return_errors=True)
    assert response["errors"][0]["code"] == 'Neo.ClientError.Statement.SyntaxError'

    with pytest.raises(neo4j.exceptions.ClientError) as client_error:
        response = bolt_neo4j_driver.run_sync(query, return_errors=False)
        assert str(client_error.code) == 'Neo.ClientError.Statement.SyntaxError'


@pytest.mark.asyncio
async def test_neo4j_http_driver_apoc(bolt_neo4j_driver):
    assert bolt_neo4j_driver.check_apoc_support()


@pytest.mark.asyncio
async def test_graph_interface_biolink_leaves(bolt_graph_adapter):
    list_1 = [
      "biolink:SmallMolecule",
      "biolink:MolecularEntity",
      "biolink:ChemicalEntity",
      "biolink:PhysicalEssence",
      "biolink:NamedThing",
      "biolink:Entity",
      "biolink:PhysicalEssenceOrOccurrent"
    ]
    assert bolt_graph_adapter.find_biolink_leaves(list_1) == set(["biolink:SmallMolecule"])
    include_mixins = ["biolink:SmallMolecule",
              "biolink:MolecularEntity",
              "biolink:ChemicalOrDrugOrTreatment"]
    assert bolt_graph_adapter.find_biolink_leaves(include_mixins) == set(["biolink:SmallMolecule"])

@pytest.mark.asyncio
async def test_graph_interface_predicate_inverse(bolt_graph_adapter):
    non_exist_predicate = "biolink:some_predicate"
    assert bolt_graph_adapter.invert_predicate(non_exist_predicate) is None
    symmetric_predicate = "biolink:related_to"
    assert bolt_graph_adapter.invert_predicate(symmetric_predicate) == symmetric_predicate
    predicate_with_inverse = "biolink:part_of"
    assert bolt_graph_adapter.invert_predicate(predicate_with_inverse) == "biolink:has_part"

@pytest.mark.asyncio
async def test_graph_interface_get_schema(bolt_graph_adapter):
    schema = bolt_graph_adapter.get_schema()
    expected = defaultdict(lambda: defaultdict(set))
    expected['biolink:Disease']['biolink:Disease'] = {'biolink:subclass_of', 'biolink:superclass_of'}
    expected['biolink:Disease']['biolink:PhenotypicFeature'] = {'biolink:has_phenotype', 'biolink:invalid_predicate'}
    expected['biolink:Disease']['biolink:Gene'] = {'biolink:genetic_association','biolink:condition_associated_with_gene'}
    expected['biolink:PhenotypicFeature']['biolink:PhenotypicFeature'] = {'biolink:subclass_of', 'biolink:superclass_of'}
    expected['biolink:PhenotypicFeature']['biolink:Disease'] = {'biolink:phenotype_of'}
    expected['biolink:Gene']['biolink:Gene'] = {'biolink:molecularly_interacts_with'}
    expected['biolink:Gene']['biolink:Disease'] = {'biolink:genetic_association', 'biolink:gene_associated_with_condition'}
    expected['biolink:Gene']['biolink:SmallMolecule'] = {'biolink:affected_by'}
    expected['biolink:SmallMolecule']['biolink:Gene'] = {'biolink:affects'}
    assert schema == expected

