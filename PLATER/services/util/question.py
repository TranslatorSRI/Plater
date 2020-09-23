import copy
from functools import reduce
from PLATER.services.util.graph_adapter import GraphInterface
import time
from reasoner.cypher import get_query

class Question:

    #SPEC VARS
    QUERY_GRAPH_KEY='query_graph'
    KG_ID_KEY='kg_id'
    QG_ID_KEY='qg_id'
    ANSWERS_KEY='results'
    KNOWLEDGE_GRAPH_KEY='knowledge_graph'
    NODES_LIST_KEY='nodes'
    EDGES_LIST_KEY='edges'
    TYPE_KEY='type'
    SOURCE_KEY='source_id'
    TARGET_KEY='target_id'
    NODE_BINDINGS_KEY='node_bindings'
    EDGE_BINDINGS_KEY='edge_bindings'
    CURIE_KEY = 'curie'

    def __init__(self, question_json):
        self._question_json = copy.deepcopy(question_json)

    def compile_cypher(self):
        return get_query(self._question_json[Question.QUERY_GRAPH_KEY])

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
        self._question_json.update(results_dict[0])
        return self._question_json

    def __validate(self):
        assert Question.QUERY_GRAPH_KEY in self._question_json, "No question graph in json."
        question_graph = self._question_json[Question.QUERY_GRAPH_KEY]
        assert Question.NODES_LIST_KEY in question_graph, "No nodes in query graph"
        assert isinstance(question_graph[Question.NODES_LIST_KEY], list), "Expected nodes to be list"
        assert Question.EDGES_LIST_KEY in question_graph, "No edges in query graph"
        assert isinstance(question_graph[Question.EDGES_LIST_KEY], list), "Expected edges to be list"
        for node in question_graph[Question.NODES_LIST_KEY]:
            assert Question.TYPE_KEY in node , f"Expected {Question.TYPE_KEY} in {node}"
            assert 'id' in node, f"Expected `id` in {node}"
        for edge in question_graph[Question.EDGES_LIST_KEY]:
            assert 'id' in edge, f"Expected `id` in {edge}"
            assert Question.SOURCE_KEY in edge, f"Expected {Question.SOURCE_KEY} in {edge}"
            assert Question.TARGET_KEY in edge, f"Expected {Question.TARGET_KEY} in {edge}"
        # make sure everything mentioned in edges is actually refering something in the node list.
        node_ids = list(map(lambda node: node['id'], question_graph[Question.NODES_LIST_KEY]))
        mentions = reduce(lambda accu, value: accu + value,
                          list(map(lambda edge: [
                              edge[Question.SOURCE_KEY],
                              edge[Question.TARGET_KEY]
                          ], question_graph[Question.EDGES_LIST_KEY])), [])
        assert reduce(lambda x, y: x and (y in node_ids), mentions, True), "Some edge mentions don't have matching " \
                                                                           "nodes. Please check question graph."

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
                "nodes" : [
                    {
                        "qg_id": "n1",
                        "type": "Type 1",
                        "kg_id": "{{curie}}"
                    },
                    {
                        "qg_id" : "n2",
                        "type": "Type 2",
                        "kg_id": "{{curie}}"
                    }
                ],
                "edges":[
                    {
                        "qg_id": "e1",
                        "type": "edge 1",
                        "source_id": "n1",
                        "target_id": "n2"
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
                    Question.NODES_LIST_KEY: [
                        {
                            'id': "n1",
                            Question.TYPE_KEY: source_type,
                        },
                        {
                            'id': "n2",
                            Question.TYPE_KEY: target_type,
                        }
                    ],
                    Question.EDGES_LIST_KEY: []
                }
                edge_set = target_set[target_type]
                for index, edge_type in enumerate(set(edge_set)):
                    edge_dict = {
                        'id': f"e{index}",
                        Question.SOURCE_KEY: "n1",
                        Question.TARGET_KEY: "n2",
                        Question.TYPE_KEY: edge_type
                    }
                    question_graph[Question.EDGES_LIST_KEY].append(edge_dict)
            question_templates.append({Question.QUERY_GRAPH_KEY: question_graph})
        return question_templates


if __name__ == '__main__':
    schema  = {
      "gene": {
        "biological_process_or_activity": [
          "actively_involved_in"
        ],
        "named_thing": [
          "similar_to"
        ]
      },
      "named_thing": {
        "chemical_substance": [
          "similar_to"
        ],
        "named_thing": [
          "similar_to"
        ]
      }
    }
    import json
    questions = Question.transform_schema_to_question_template(schema)
    print(questions)
    question = Question(questions[0])
    # questions[0]['query_graph']['nodes'][1]['curie'] = ''
    questions[0]['query_graph']['nodes'][1]['type'] = 'disease'
    del questions[0]['query_graph']['edges'][0]['type']
    questions[0]['query_graph']['nodes'][0]['type'] = 'information_content_entity'
    q2 = Question(questions[0])
    ans = q2.answer(graph_interface=GraphInterface('localhost','7474', ('neo4j', 'neo4jkp')))
    import asyncio
    event_loop = asyncio.get_event_loop()
    result = event_loop.run_until_complete(ans)
    print(json.dumps(result, indent=2))
