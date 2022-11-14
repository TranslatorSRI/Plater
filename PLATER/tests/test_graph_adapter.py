import httpx
import json

from PLATER.services.util.graph_adapter import Neo4jHTTPDriver, GraphInterface
from pytest_httpx import HTTPXMock
import pytest
from unittest.mock import patch
import os


def test_neo4j_http_driver_ping_success(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))


def test_neo4j_http_driver_ping_fail(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=500)
    try:
        driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
        assert False
    except:
        assert True


@pytest.mark.asyncio
async def test_neo4j_http_driver_run_cypher(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
    test_response = {"some": "response"}
    query = "some test cypher"

    httpx_mock.add_response(url=driver._full_transaction_path, method='POST', json=test_response, match_content = json.dumps({
            "statements": [
                {
                    "statement": f"{query}"
                }
            ]
        }).encode('utf-8'))
    response = await driver.run(query)
    assert response == test_response
    # test sync runner
    response = driver.run_sync(query)
    assert response == test_response


@pytest.mark.asyncio
async def test_neo4j_http_driver_run_cypher_fail(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
    test_response = {"errors": "some_error"}
    query = "some test cypher"

    httpx_mock.add_response(url=driver._full_transaction_path, method='POST', json=test_response, match_content = json.dumps({
            "statements": [
                {
                    "statement": f"{query}"
                }
            ]
        }).encode('utf-8'), status_code= 500)
    try:
        response = await driver.run(query)
    except:
        assert True
    response = await  driver.run(query, return_errors=True)
    assert response == test_response
    # test sync runner
    try:
        response = driver.run_sync(query)
    except:
        assert True

@pytest.mark.asyncio
async def test_neo4j_http_driver_apoc(httpx_mock: HTTPXMock):
    query = 'call apoc.help("meta")'
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    httpx_mock.add_response(url="http://localhost:7474/db/data/transaction/commit", method="POST", status_code=200,
                            match_content=json.dumps({
                                "statements": [
                                    {
                                        "statement": f"{query}"
                                    }
                                ]
                            }).encode('utf-8'), json={}
                            )
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
    assert driver.check_apoc_support() == True
    httpx_mock.add_response(url="http://localhost:7474/db/data/transaction/commit", method="POST", status_code=500,
                            match_content=json.dumps({
                                "statements": [
                                    {
                                        "statement": f"{query}"
                                    }
                                ]
                            }).encode('utf-8'), json={"errors": "apoc not supported"}
                            )
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
    assert driver.check_apoc_support() == False

@pytest.mark.asyncio
async def test_driver_convert_to_dict(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port='7474', auth=('neo4j', 'somepass'))
    sample_resp = {
          "results": [
            {
              "columns": [
                "count(n)"
              ],
              "data": [
                {
                  "row": [
                    82513
                  ],
                  "meta": []
                }
              ]
            }
          ],
          "errors": []
    }
    expected = [{"count(n)": 82513}]
    assert driver.convert_to_dict(sample_resp) == expected


@pytest.mark.asyncio
async def test_graph_interface_biolink_leaves(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    gi = GraphInterface('localhost','7474', auth=('neo4j', ''))
    list_1 = [
      "biolink:SmallMolecule",
      "biolink:MolecularEntity",
      "biolink:ChemicalEntity",
      "biolink:PhysicalEssence",
      "biolink:NamedThing",
      "biolink:Entity",
      "biolink:PhysicalEssenceOrOccurrent"
    ]
    assert gi.find_biolink_leaves(list_1) == set(["biolink:SmallMolecule"])
    include_mixins = ["biolink:SmallMolecule",
              "biolink:MolecularEntity",
              "biolink:ChemicalOrDrugOrTreatment"]
    assert gi.find_biolink_leaves(include_mixins) == set(["biolink:SmallMolecule"])
    GraphInterface.instance = None

@pytest.mark.asyncio
async def test_graph_interface_predicate_inverse(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    gi = GraphInterface('localhost', '7474', auth=('neo4j', ''))
    non_exist_predicate = "biolink:some_predicate"
    assert gi.invert_predicate(non_exist_predicate) == None
    symmetric_predicate = "biolink:related_to"
    assert gi.invert_predicate(symmetric_predicate) == symmetric_predicate
    predicate_with_inverse = "biolink:part_of"
    assert gi.invert_predicate(predicate_with_inverse) == "biolink:has_part"
    # biolink 3.1.0 seems to be pretty good on inverses.
    # predicate_no_inverse_and_not_symmetric = "biolink:associated_with_increased_likelihood_of"
    # assert gi.invert_predicate(predicate_no_inverse_and_not_symmetric) == None
    GraphInterface.instance = None

@pytest.mark.asyncio
async  def test_graph_interface_get_schema(httpx_mock: HTTPXMock):
    query_schema = """\n                           MATCH (a)-[x]->(b)\n                           WHERE not a:Concept and not b:Concept                                                          \n                           RETURN DISTINCT labels(a) as source_labels, type(x) as predicate, labels(b) as target_labels\n                           """

    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    gi = GraphInterface('localhost', '7474', auth=('neo4j', ''))
    with open( os.path.join(os.path.dirname(__file__), 'data', 'schema_cypher_response.json'))as f:
        get_schema_response_json = json.load(f)
    httpx_mock.add_response(url="http://localhost:7474/db/data/transaction/commit", method="POST", status_code=200,
                            match_content=json.dumps({
                                "statements": [
                                    {
                                        "statement": f"{query_schema}"
                                    }
                                ]
                            }).encode('utf-8'), json=get_schema_response_json
                            )

    # lets pretend we already have summary
    gi.instance.summary = True
    schema = gi.get_schema()
    expected = {
        'biolink:Disease': {
            'biolink:Disease': ['biolink:has_phenotype',
                                'biolink:phenotype_of'],
            'biolink:PhenotypicFeature': ['biolink:has_phenotype']},
        'biolink:PhenotypicFeature': {
            'biolink:Disease': ['biolink:phenotype_of']
        }
    }
    assert schema == expected
    GraphInterface.instance = None

@pytest.mark.asyncio
async def test_get_meta_kg(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474", method="GET", status_code=200)
    gi = GraphInterface('localhost', '7474', auth=('neo4j', ''))
    gi.instance.schema = {
      "biolink:Disease": {
        "biolink:PhenotypicFeature": [
          "biolink:has_phenotype"
        ],
        "biolink:Disease": [
          "biolink:has_phenotype"
        ]
      }
    }
    node_attributes = [{"attribute_type_id": "biolink:same_as"}]
    def patch_get_node_curies(node_type):
        # mimic db return ids then filter curie prefixes
        if node_type == "biolink:Disease":
            return ['MONDO'] , node_attributes
        if node_type == "biolink:PhenotypicFeature":
            return ['HP'], node_attributes
    gi.instance.get_curie_prefix_by_node_type = patch_get_node_curies

    def patch_get_examples(subject_node_type, object_node_type=None, predicate=None, num_examples=1):
        examples = []
        for i in range(num_examples):
            mock_edge = {
                'subject': {'id': f'HP:{i+1}999'},
                'edge': {'id': 'abc123'},
                'object': {'id': f'MONDO:{i+1}999'}
            }
            examples.append(mock_edge)
        return examples
    gi.instance.get_examples = patch_get_examples

    assert await gi.get_meta_kg() == {
        "nodes": {
            "biolink:Disease": { "id_prefixes": ['MONDO'], "attributes": node_attributes},
            "biolink:PhenotypicFeature":{ "id_prefixes": ['HP'], "attributes": node_attributes}
        }, "edges": [
            { "subject": "biolink:Disease", "object": "biolink:PhenotypicFeature", "predicate": "biolink:has_phenotype"},
            { "object": "biolink:Disease", "subject": "biolink:Disease", "predicate": "biolink:has_phenotype"},
        ]
    }

    sri_testing_data = await gi.get_sri_testing_data()
    if 'PUBLIC_URL' in os.environ and os.environ['PUBLIC_URL']:
        sri_testing_data['url'] == os.environ['PUBLIC_URL']
    else:
        assert sri_testing_data['url'] == 'http://-fake-default-url-/plater'
    assert sri_testing_data['edges'] == [
        {'subject_category': 'biolink:Disease',
         'object_category': 'biolink:PhenotypicFeature',
         'predicate': 'biolink:has_phenotype',
         'subject': 'HP:1999',
         'object': 'MONDO:1999'},
        {'subject_category': 'biolink:Disease',
         'object_category': 'biolink:Disease',
         'predicate': 'biolink:has_phenotype',
         'subject': 'HP:1999',
         'object': 'MONDO:1999'}]
