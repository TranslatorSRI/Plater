from unittest.mock import patch

import pytest
import json
import os
import copy

from PLATER.services.util.question import Question


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


class MOCK_GRAPH_ADAPTER():
    called = False
    toolkit = None
    protocol = 'bolt'

    async def run_cypher(self,
                         cypher,
                         convert_to_dict=False,
                         convert_to_trapi=False,
                         qgraph=None):
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


"""
this was implemented in a version that stood up an actual neo4j for testing, it could be used if that happens again
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
"""
