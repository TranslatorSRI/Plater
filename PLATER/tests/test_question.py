from unittest.mock import patch

import pytest
import json
import os
import copy

from PLATER.services.util.question import Question
from .plater_fixtures import bolt_graph_adapter

@pytest.fixture
def message():
    with open(os.path.join(os.path.dirname(__file__), 'data','trapi1.4.json')) as stream:
        message = json.load(stream)
    return message

def test_init():
    reasoner_dict = {
            "query_graph": {
                "nodes": {"n0": {}, "n1": {}},
                "edges": {"e0": {"subject": "n0", "object": "n1"}}
            }
    }
    question = Question(reasoner_dict)
    assert question._question_json == reasoner_dict
    assert question._question_json == reasoner_dict


def test_format_attribute():
    # note that this test does not run through the reasoner code that does the attribute mapping.
    # so the values in the expected results must account for that

    trapi_kg_response = {"knowledge_graph":
        {"nodes":
            {"CURIE:1":
                {"attributes": [{"original_attribute_name": "pub", "attribute_type_id": "CURIE:x"}]}
             },
         "edges":
             {"123123":
                  {
                      "attributes": [{"original_attribute_name": "some_attr", "value": "some_value"}],
                      "sources": [{"resource_role": "biolink:primary_knowledge_source", "resource_id":"infores:primary"}]
                  }
              }
         }
    }
    expected_trapi = {"knowledge_graph":
        {"nodes":
            {"CURIE:1":
                {"attributes": [{"original_attribute_name": "pub", "attribute_type_id": "CURIE:x", "value_type_id": "EDAM:data_0006"}]}
             },
         "edges":
             {"123123":
                  {"attributes": [{"original_attribute_name": "some_attr", "value": "some_value",
                                   "attribute_type_id": "biolink:Attribute",
                                   "value_type_id": "EDAM:data_0006"},
                                  ],

                   "sources": [
                       {"resource_role": "primary_knowledge_source",
                        "resource_id": "infores:primary",
                        "upstream_resource_ids": None},
                       {"resource_role": "aggregator_knowledge_source",
                        "resource_id": "infores:automat.notspecified",
                        "upstream_resource_ids": {"infores:primary"}},
                   ]}
              }
         }
    }
    q = Question(question_json={})
    transformed = q.transform_attributes(trapi_kg_response)

    # test attribute_id if provided from neo4j response is preserved
    # test if value_type is added to default 'biolink:Attribute'
    assert transformed == expected_trapi

    t2_trapi_kg_response = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [
        {"original_attribute_name": "pub", "value": "x", "value_type_id": "oo", "attribute_type_id": "preserved_attrib"},
        {"original_attribute_name": "publications", "value": "x"},
        {"original_attribute_name": "endogenous", "value": "false"},
        {"original_attribute_name": "p-value", "value": "1.234"},
        {"original_attribute_name": "chi-squared-statistic", "value": "2.345"},
        {"original_attribute_name": "equivalent_identifiers", "attribute_type_id": "biolink:same_as", "value": ["some_identifier"]}]
    }}}}

    t2_expected_trapi = {'knowledge_graph': {'nodes': {'CURIE:1': {'attributes': [
        {'original_attribute_name': 'pub', 'value': 'x', 'value_type_id': 'EDAM:data_0006', 'attribute_type_id': 'preserved_attrib'},
        {'original_attribute_name': 'publications', 'value': 'x', 'value_type_id': 'EDAM:data_0006', 'attribute_type_id': 'EDAM:data_0971'},
        {'original_attribute_name': 'endogenous', 'value': 'false', 'value_type_id': 'xsd:boolean', 'attribute_type_id': 'aragorn:endogenous'},
        {'original_attribute_name': 'p-value', 'value': '1.234', 'value_type_id': 'EDAM:data_0006', 'attribute_type_id': 'biolink:Attribute'},
        {'original_attribute_name': 'chi-squared-statistic', 'value': '2.345', 'value_type_id': 'EDAM:data_0006', 'attribute_type_id': 'biolink:Attribute'},
        {"original_attribute_name": "equivalent_identifiers", "attribute_type_id": "biolink:same_as", "value": ["some_identifier"], 'value_type_id': 'metatype:uriorcurie'}
    ]
    }}}}

    q = Question(question_json={})

    transformed = q.transform_attributes(t2_trapi_kg_response)

    # test default attribute to be EDAM:data_0006
    # test if value_type is preserved if in response from neo4j
    assert transformed == t2_expected_trapi

def test_format_edge_qualifiers():
    # note that this test does not run through the reasoner code that does the attribute mapping.
    # so the values in the expected results must account for that

    trapi_kg_response ={ "knowledge_graph": {
       "edges":{
          "some_id":{
              "object": "NCBIGene:283871",
              "predicate": "biolink:affects",
              "subject": "PUBCHEM.COMPOUND:5311062",
              "attributes": [
                {
                   "attribute_type_id":"NA",
                   "original_attribute_name":"qualified_predicate",
                   "value":"biolink:causes"
                },
                {
                   "attribute_type_id":"NA",
                   "original_attribute_name":"object_aspect_qualifier",
                   "value":"activity"
                },
                {
                   "attribute_type_id":"NA",
                   "original_attribute_name":"object_direction_qualifier",
                   "value":"decreased"
                }],
          }
       }
    }}
    expected_trapi = {"knowledge_graph": {"edges": {'some_id': {
        'object': 'NCBIGene:283871',
        'predicate': 'biolink:affects',
        'subject': 'PUBCHEM.COMPOUND:5311062',
        'attributes': [],
        'sources': [{'resource_id': 'infores:automat.notspecified',
                     'resource_role': 'aggregator_knowledge_source',
                     'upstream_resource_ids': None
                     }],
        "qualifiers": [
            {
                "qualifier_type_id": "biolink:qualified_predicate",
                "qualifier_value": "biolink:causes"
            },
            {
                "qualifier_type_id": "biolink:object_aspect_qualifier",
                "qualifier_value": "activity"
            },
            {
                "qualifier_type_id": "biolink:object_direction_qualifier",
                "qualifier_value": "decreased"
            },
        ],
        }}
    }}

    q = Question(question_json={})
    transformed = q.transform_attributes(trapi_kg_response)

    # test attribute_id if provided from neo4j response is preserved
    # test if value_type is added to default "biolink:Attribute"
    assert transformed == expected_trapi

class MOCK_GRAPH_ADAPTER():
    called = False
    toolkit = None
    protocol = 'bolt'

    async def run_cypher(self, cypher, convert_to_dict=False, convert_to_trapi_message=False, qgraph=None):
        assert cypher == "SOME CYPHER"
        self.called = True
        return {'query_graph': {'nodes': {}, 'edges': {}},
                       'results': [],
                       'knowledge_graph': {'nodes': {}, 'edges': {}}}


@pytest.mark.asyncio
async def test_mock_answer():
    def compile_cypher_mock(**kwargs):
        return "SOME CYPHER"
    question = Question({"query_graph": {"nodes": {}, "edges": {}}})
    question.compile_cypher = compile_cypher_mock
    graph_interface = MOCK_GRAPH_ADAPTER()
    result = await question.answer(graph_interface=graph_interface)
    expected_result = {'query_graph': {'nodes': {}, 'edges': {}},
                       'results': [],
                       'knowledge_graph': {'nodes': {}, 'edges': {}}}
    assert result == expected_result


@pytest.mark.asyncio
async def test_real_answer(bolt_graph_adapter):
    question = Question({
        "query_graph": {
          "nodes": {
            "n0": {
              "categories": [
                "biolink:ChemicalSubstance"
              ],
              "ids": [
                "CHEBI:136043"
              ]
            },
            "n1": {
              "categories": [
                "biolink:Disease"
              ],
              "ids": [
                "MONDO:0005148"
              ]
            }
          },
          "edges": {
            "e01": {
              "subject": "n0",
              "object": "n1",
              "predicates": [
                "biolink:treats"
              ]
            }
          }
        }
    })
    trapi_message = await question.answer(graph_interface=bolt_graph_adapter)
    assert len(trapi_message['results']) == 1
    assert 'CHEBI:136043' in trapi_message['knowledge_graph']['nodes']
    assert 'MONDO:0005148' in trapi_message['knowledge_graph']['nodes']


def test_attribute_constraint_basic(message):
    node_constraints = [{"id": "biolink:same_as" , "name": "eq_id_filter", "value": ["DRUGBANK:DB04572"], "operator": "=="}]
    message['query_graph']['nodes']['n1']['constraints'] = node_constraints
    expected = copy.deepcopy(message)
    result = Question.apply_attribute_constraints(message)
    assert result == expected

def test_attribute_constraint_filter_node(message):
    # this node doesnt exist, and is the main node, so everything should vanish
    node_constraints = [
        {"id": "biolink:same_as", "name": "eq_id_filter", "value": ["DRUGBANK:DB0450"], "operator": "=="}
    ]
    message['query_graph']['nodes']['n1']['constraints'] = node_constraints
    result = Question.apply_attribute_constraints(message)
    assert result['query_graph'] == message['query_graph']
    # other node should remain
    assert len(result['knowledge_graph']['nodes']) == 2 # two disease in the graph remain
    assert len(result['knowledge_graph']['edges']) == 0 # no edges
    assert len(result['results']) == 0  # no bindings
    # swapping constraint we should have single node no bindings
    message['query_graph']['nodes']['n0']['constraints'] = node_constraints
    message['query_graph']['nodes']['n1']['constraints'] = []
    result = Question.apply_attribute_constraints(message)
    assert len(result['knowledge_graph']['nodes']) == 1  # two disease in the graph remain
    assert len(result['knowledge_graph']['edges']) == 0  # no edges
    assert len(result['results']) == 0  # no bindings

def test_attribute_constraint_filter_edge(message):
    edge_constraints = [
        {"id": "biolink:relation", "name": "eq_id_filter", "value": "CTD:marker_mechanism", "operator": "=="}
    ]
    message['query_graph']['edges']['e0']['attribute_constraints'] = edge_constraints
    #"57de50b7d36a7b952a12376ae39c1f92": {
    #    "subject": "PUBCHEM.COMPOUND:5453",
    #    "object": "MONDO:0001609",
    # one match and one binding out of three edges is expected
    m_copy = copy.deepcopy(message)
    result = Question.apply_attribute_constraints(m_copy)

    assert result['query_graph'] == message['query_graph']
    assert len(result['knowledge_graph']['nodes']) == 3
    assert len(result['knowledge_graph']['edges']) == 1
    assert message['knowledge_graph']['edges']['57de50b7d36a7b952a12376ae39c1f92'] == \
           result['knowledge_graph']['edges']['57de50b7d36a7b952a12376ae39c1f92']
    assert len(result['results']) == 1
    edge_constraints = [
        {"id": "biolink:relation", "name": "eq_id_filter", "value": 'CTD:marker_mechanism', "operator": "=="}
    ]
    message['query_graph']['edges']['e0']['attribute_constraints'] = edge_constraints
    m_copy_2 = copy.deepcopy(message)
    result = Question.apply_attribute_constraints(m_copy_2)
    # mondo:0001609 -> pubchem.compund:5453 has two edges with same type
    # hence result binding contains "e0" len 2. filter should return one binding
    # with exactly one edge `304ef8f54494931d8eccb50e1b68be04`
    assert len(result['knowledge_graph']['nodes']) == 3
    assert len(result['knowledge_graph']['edges']) == 1
    assert len(result['results']) == 1
    assert len(result['results'][0]['analyses'][0]['edge_bindings']['e0']) == 1