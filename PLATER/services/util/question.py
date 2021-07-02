import copy
from functools import reduce
from PLATER.services.util.graph_adapter import GraphInterface
import time
import reasoner
from reasoner.cypher import get_query


reasoner.cypher.ATTRIBUTE_TYPES = {
    "publications": "EDAM:data_0971",
    "`biolink:orignal_knowledge_source`": "biolink:original_knowledge_source"
}

class Question:

    #SPEC VARS
    QUERY_GRAPH_KEY='query_graph'
    KG_ID_KEY='id'
    QG_ID_KEY='id'
    ANSWERS_KEY='results'
    KNOWLEDGE_GRAPH_KEY='knowledge_graph'
    NODES_LIST_KEY='nodes'
    EDGES_LIST_KEY='edges'
    NODE_TYPE_KEY='category'
    EDGE_TYPE_KEY='predicate'
    SOURCE_KEY='subject'
    TARGET_KEY='object'
    NODE_BINDINGS_KEY='node_bindings'
    EDGE_BINDINGS_KEY='edge_bindings'
    CURIE_KEY = 'curie'

    def __init__(self, question_json):
        self._question_json = copy.deepcopy(question_json)

    def compile_cypher(self):
        return get_query(self._question_json[Question.QUERY_GRAPH_KEY])

    @staticmethod
    def format_attribute_trapi_1_1 (kg_items):
        for identifier in kg_items:
            item = kg_items[identifier]
            attributes = item.get('attributes', {})
            for attr in attributes:
                attr['original_attribute_name'] = attr['original_attribute_name'] or ''
                # uses Data as attribute type id if not defined
                if not('attribute_type_id' in attr and attr['attribute_type_id'] != 'NA'):
                    attr['attribute_type_id'] = 'EDAM:data_0006'
                if not('value_type_id' in attr and attr['value_type_id'] != 'NA'):
                    # fix for issue https://github.com/RENCI-AUTOMAT/Automat-server/issues/15
                    attr['value_type_id'] = 'biolink:Attribute'
                if attr['attribute_type_id'] == "biolink:original_knowledge_source":
                    attr['value_type_id'] = 'biolink:InformationResource'

        return kg_items

    def transform_attributes(self, trapi_message):
        self.format_attribute_trapi_1_1(trapi_message.get('knowledge_graph', {}).get('nodes', {}))
        self.format_attribute_trapi_1_1(trapi_message.get('knowledge_graph', {}).get('edges', {}))
        return trapi_message

    async def answer(self, graph_interface: GraphInterface):
        """
        Updates the query graph with answers from the neo4j backend
        :param graph_interface: interface for neo4j
        :return: None
        """
        cypher = self.compile_cypher()
        print(cypher)
        s = time.time()
        results = await graph_interface.run_cypher(cypher)
        end = time.time()
        print(f'grabbing results took {end - s}')
        results_dict = graph_interface.convert_to_dict(results)
        self._question_json.update(self.transform_attributes(results_dict[0]))
        return self._question_json

    @staticmethod
    def transform_schema_to_question_template(graph_schema):
        """
        Returns array of Templates given a graph schema
        Eg: if schema looks like
           {
            "Type 1" : {
                "Type 2": [
                    "edge 1"
                ]
            }
           }
           We would get
           {
            "question_graph": {
                "nodes" : {
                    "n1": {
                        "id": "{{ curie }}",
                        "category": "Type 1"
                    },
                    "n2": {
                        "id" : "{{ curie }}",
                        "category": "Type 2"
                    }
                },
                "edges":{
                    "e1": {
                        "predicate": "edge 1",
                        "subject": "n1",
                        "object": "n2"
                    }
                ]
            }
           }
        :param graph_schema:
        :return:
        """
        question_templates = []
        for source_type in graph_schema:
            target_set = graph_schema[source_type]
            for target_type in target_set:
                question_graph = {
                    Question.NODES_LIST_KEY: {
                        "n1": {
                            'id': None,
                            Question.NODE_TYPE_KEY: source_type,
                        },
                        "n2": {
                            'id': None,
                            Question.NODE_TYPE_KEY: target_type,
                        }
                    },
                    Question.EDGES_LIST_KEY: []
                }
                edge_set = target_set[target_type]
                question_graph[Question.EDGES_LIST_KEY] = {}
                for index, edge_type in enumerate(set(edge_set)):
                    edge_dict = {
                        Question.SOURCE_KEY: "n1",
                        Question.TARGET_KEY: "n2",
                        Question.EDGE_TYPE_KEY: edge_type
                    }
                    question_graph[Question.EDGES_LIST_KEY][f"e{index}"] = edge_dict
            question_templates.append({Question.QUERY_GRAPH_KEY: question_graph})
        return question_templates

