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
    assert question.trapi_version == "1.0.0"
    assert question._question_json == reasoner_dict
    question = Question(reasoner_dict, trapi_version='1.0.1')
    assert question.trapi_version == '1.0.1'
    assert question._question_json == reasoner_dict


def test_format_attribute():
    trapi_kg_response = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"name": "pub", "type": "CURIE:x", "value": "x"}]}}}}
    q = Question(question_json={}, trapi_version="1.0.0")
    assert trapi_kg_response["knowledge_graph"] == q.transform_attributes(trapi_kg_response["knowledge_graph"])
    expected_trapi_1_1 = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"attribute_type_id": "CURIE:x", "value": "x", "original_attribute_name":"pub"}]}} }}
    q = Question(question_json={}, trapi_version="1.1.0")
    assert q.transform_attributes(trapi_kg_response) == expected_trapi_1_1
    expected_trapi_1_1 = {
        "knowledge_graph": {
            "nodes": {
                "CURIE:1": {
                    "attributes": [{"attribute_type_id": "EDAM:data_0006", "value": "x", "original_attribute_name": "pub"}]
                }
            }
        }
    }
    trapi_kg_response = {
        "knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [{"name": "pub", "value": "x"}]}}}
    }
    # test default attribute to be EDAM:data_0006
    assert q.transform_attributes(trapi_kg_response) == expected_trapi_1_1


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
