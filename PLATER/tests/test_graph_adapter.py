import json
from collections import defaultdict
from PLATER.services.util.graph_adapter import Neo4jHTTPDriver, GraphInterface
from pytest_httpx import HTTPXMock
import pytest
import os


def test_neo4j_http_driver_ping_success(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))


def test_neo4j_http_driver_ping_fail(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=500)
    try:
        driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
        assert False
    except:
        assert True


@pytest.mark.asyncio
async def test_neo4j_http_driver_run_cypher(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
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
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
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
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    httpx_mock.add_response(url="http://localhost:7474/db/data/transaction/commit", method="POST", status_code=200,
                            match_content=json.dumps({
                                "statements": [
                                    {
                                        "statement": f"{query}"
                                    }
                                ]
                            }).encode('utf-8'), json={}
                            )
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
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
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
    assert driver.check_apoc_support() is False

@pytest.mark.asyncio
async def test_driver_convert_to_dict(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    driver = Neo4jHTTPDriver(host='localhost', port=7474, auth=('neo4j', 'somepass'))
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
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
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
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
    gi = GraphInterface('localhost', '7474', auth=('neo4j', ''))
    non_exist_predicate = "biolink:some_predicate"
    assert gi.invert_predicate(non_exist_predicate) is None
    symmetric_predicate = "biolink:related_to"
    assert gi.invert_predicate(symmetric_predicate) == symmetric_predicate
    predicate_with_inverse = "biolink:part_of"
    assert gi.invert_predicate(predicate_with_inverse) == "biolink:has_part"
    predicate_no_inverse_and_not_symmetric = "biolink:has_part"
    assert gi.invert_predicate(predicate_no_inverse_and_not_symmetric) is None
    GraphInterface.instance = None

@pytest.mark.asyncio
async  def test_graph_interface_get_schema(httpx_mock: HTTPXMock):
    query_schema = """ 
                MATCH (a)-[x]->(b)
                RETURN DISTINCT labels(a) as source_labels, type(x) as predicate, labels(b) as target_labels
                """
    httpx_mock.add_response(url="http://localhost:7474/", method="GET", status_code=200)
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
    # gi.instance.summary = True
    schema = gi.get_schema()
    expected = defaultdict(lambda: defaultdict(set))
    expected['biolink:Disease']['biolink:Disease'] = {'biolink:has_phenotype'}
    expected['biolink:PhenotypicFeature']['biolink:Disease'] = set()
    expected['biolink:Disease']['biolink:PhenotypicFeature'] = {'biolink:has_phenotype'}

    assert schema == expected
    GraphInterface.instance = None
