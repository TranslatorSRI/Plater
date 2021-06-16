from unittest.mock import patch
from PLATER.services.util.question import Question
import asyncio

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
    trapi_kg_response = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"original_attribute_name": "pub", "attribute_type_id": "CURIE:x"}]}}}}
    expected_trapi = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"attribute_type_id": "CURIE:x", "value_type_id": "biolink:Attribute", "original_attribute_name":"pub"}]}} }}
    q = Question(question_json={})
    # test if attribute_id if provided from neo4j response is preserved
    # test if value_type is added to default 'biolink:Attribute'
    assert q.transform_attributes(trapi_kg_response) == expected_trapi
    expected_trapi = {
        "knowledge_graph": {
            "nodes": {
                "CURIE:1": {
                    "attributes": [{"attribute_type_id": "EDAM:data_0006", "value": "x", "original_attribute_name": "pub", "value_type_id": "oo"}]
                }
            }
        }
    }
    trapi_kg_response = {
        "knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"original_attribute_name": "pub", "value": "x", "value_type_id": "oo"}]}}}
    }
    # test default attribute to be EDAM:data_0006
    # test if value_type is preserved if in response from neo4j
    assert q.transform_attributes(trapi_kg_response) == expected_trapi


class MOCK_GRAPH_ADAPTER():
    called = False

    async def run_cypher(self, cypher):
        assert cypher == "SOME CYPHER"
        self.called = True

    @staticmethod
    def convert_to_dict(item):
        return [{"trapi": {"compatible_ result"}}]


def test_answer():
    def compile_cypher_mock():
        return "SOME CYPHER"
    question = Question({"query_graph": {}})
    question.compile_cypher = compile_cypher_mock
    graph_interface = MOCK_GRAPH_ADAPTER()
    result = asyncio.run(question.answer(graph_interface=graph_interface))
    expected_result = graph_interface.convert_to_dict('')[0]
    expected_result.update({"query_graph": {}})
    assert result == expected_result
