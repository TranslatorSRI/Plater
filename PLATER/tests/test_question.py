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
    # note that this test does not run through the reasoner code that does the attribute mapping.
    # so the values in the expected results must account for that

    trapi_kg_response = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [
        {"original_attribute_name": "pub", "attribute_type_id": "CURIE:x"},
        {"original_attribute_name": "biolink:original_knowledge_source", "value": "infores:kg_source"}]
    }}}}

    expected_trapi = {"knowledge_graph": {"nodes": {"CURIE:1": {"attributes": [
        {"original_attribute_name": "pub", "attribute_type_id": "CURIE:x", "value_type_id": "EDAM:data_0006"},
        {"original_attribute_name": "biolink:original_knowledge_source", "value": "infores:kg_source", "attribute_type_id": "biolink:Attribute", "value_type_id": "biolink:InformationResource"},
        {"attribute_type_id": "biolink:aggregator_knowledge_source", "value": "infores:automat.unknown", "value_type_id": "biolink:InformationResource", "original_attribute_name": "biolink:aggregator_knowledge_source"}]
    }}}}

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
        {"original_attribute_name": "equivalent_identifiers", "attribute_type_id": "biolink:same_as", "value": ["some_identifier"]},
        {"original_attribute_name": "biolink:original_knowledge_source", "value": "infores:kg_source"}]
    }}}}

    t2_expected_trapi = {'knowledge_graph': {'nodes': {'CURIE:1': {'attributes': [
        {'original_attribute_name': 'pub', 'value': 'x', 'value_type_id': 'EDAM:data_0006', 'attribute_type_id': 'preserved_attrib'},
        {'original_attribute_name': 'publications', 'value': 'x', 'value_type_id': 'publication', 'attribute_type_id': 'biolink:publications'},
        {'original_attribute_name': 'endogenous', 'value': 'false', 'value_type_id': 'xsd:boolean', 'attribute_type_id': 'biolink:Attribute'},
        {'original_attribute_name': 'p-value', 'value': '1.234', 'value_type_id': 'float', 'attribute_type_id': 'biolink:p_value'},
        {'original_attribute_name': 'chi-squared-statistic', 'value': '2.345', 'value_type_id': 'float', 'attribute_type_id': 'biolink:chi_squared_statistic'},
        {"original_attribute_name": "equivalent_identifiers", "attribute_type_id": "biolink:same_as", "value": ["some_identifier"], 'value_type_id': 'metatype:uriorcurie'},
        {"original_attribute_name": "biolink:original_knowledge_source", "value": "infores:kg_source", "attribute_type_id": "biolink:Attribute", "value_type_id": "biolink:InformationResource"},
        {'attribute_type_id': 'biolink:aggregator_knowledge_source', 'value': 'infores:automat.unknown', 'value_type_id': 'biolink:InformationResource', 'original_attribute_name': 'biolink:aggregator_knowledge_source'}]
    }}}}

    q = Question(question_json={})

    transformed = q.transform_attributes(t2_trapi_kg_response)

    # test default attribute to be EDAM:data_0006
    # test if value_type is preserved if in response from neo4j
    assert transformed == t2_expected_trapi


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
