import copy
import orjson
import time

from secrets import token_hex
from opentelemetry import trace
from PLATER.services.util.graph_adapter import GraphInterface
from reasoner_transpiler.cypher import get_query, set_custom_attribute_types, set_custom_attribute_value_types, \
    set_custom_attribute_skip_list
from PLATER.services.config import config, get_positive_int_from_config
from PLATER.services.util.attribute_mapping import SKIP_LIST, ATTRIBUTE_TYPES, VALUE_TYPES
from PLATER.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

# get these configurable options from the config or use the default
RESULTS_LIMIT = get_positive_int_from_config('RESULTS_LIMIT', None)
SUBCLASS_DEPTH = get_positive_int_from_config('SUBCLASS_DEPTH', 1)

# these are optional custom mappings that are applied in reasoner-transpiler
# if set they override default or biolink derived attribute type ids and value type ids for attributes in TRAPI results
if ATTRIBUTE_TYPES:
    set_custom_attribute_types(ATTRIBUTE_TYPES)
if VALUE_TYPES:
    set_custom_attribute_value_types(VALUE_TYPES)
# an optional list of attributes to skip/ignore when processing cypher results and formatting them into TRAPI
if SKIP_LIST:
    set_custom_attribute_skip_list(SKIP_LIST)


class Question:
    # SPEC VARS
    QUERY_GRAPH_KEY = 'query_graph'
    KG_ID_KEY = 'ids'
    QG_ID_KEY = 'ids'
    ANSWERS_KEY = 'results'
    KNOWLEDGE_GRAPH_KEY = 'knowledge_graph'
    NODES_LIST_KEY = 'nodes'
    EDGES_LIST_KEY = 'edges'
    NODE_TYPE_KEY = 'categories'
    EDGE_TYPE_KEY = 'predicate'
    SOURCE_KEY = 'subject'
    TARGET_KEY = 'object'
    NODE_BINDINGS_KEY = 'node_bindings'
    EDGE_BINDINGS_KEY = 'edge_bindings'
    CURIE_KEY = 'curie'

    def __init__(self, question_json):
        self._question_json = copy.deepcopy(question_json)
        self._transpiler_qgraph = question_json.get(Question.QUERY_GRAPH_KEY, {})

    def compile_cypher(self, **kwargs):
        return get_query(self._transpiler_qgraph, **kwargs)

    async def answer(self, graph_interface: GraphInterface):
        """
        Updates the query graph with answers from the neo4j backend
        :param graph_interface: interface for neo4j
        :return: None
        """
        # get a reference to the current opentelemetry span
        otel_span = trace.get_current_span()
        if not otel_span or not otel_span.is_recording():
            otel_span = None

        # compile a cypher query and return a string
        cypher = self.compile_cypher(**{"use_hints": True,
                                        "limit": RESULTS_LIMIT,
                                        "subclass_depth": SUBCLASS_DEPTH})

        # convert the incoming TRAPI query into a string for logging and tracing
        trapi_query = str(orjson.dumps(self._question_json), "utf-8")
        # create a probably-unique id to be associated with this query in the logs
        query_logging_id = token_hex(10)
        logger.info(f"querying neo4j for query {query_logging_id}, trapi: {trapi_query}")
        start_time = time.time()
        result_qgraph = await graph_interface.run_cypher(cypher,
                                                         convert_to_trapi=True,
                                                         qgraph=self._transpiler_qgraph)
        neo4j_duration = time.time() - start_time
        logger.info(f"returned results from neo4j for {query_logging_id}, neo4j_duration: {neo4j_duration}")
        if otel_span is not None:
            otel_span.set_attributes(
                {
                    "trapi": trapi_query,
                    "neo4j_duration": neo4j_duration,
                    "query_logging_id": query_logging_id
                }
            )
        self._question_json.update(result_qgraph)
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
