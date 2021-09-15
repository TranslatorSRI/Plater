import copy
from functools import reduce
from PLATER.services.util.graph_adapter import GraphInterface
import time
import reasoner_transpiler as reasoner
import json
from reasoner_transpiler.cypher import get_query
import os
from bmt import Toolkit
from PLATER.services.config import config

# load the attrib and value mapping file
map_data = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "attr_val_map.json")))

# attribute skip list
skip_list = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "skip_attr.json")))

# set the transpiler attribute mappings
reasoner.cypher.ATTRIBUTE_TYPES = map_data['attribute_type_map']

# set the value type mappings
VALUE_TYPES = map_data['value_type_map']


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

        # self.toolkit = toolkit
        self.provenance = config.get('PROVENANCE_TAG', 'infores:automat.notspecified')

    def compile_cypher(self):
        return get_query(self._question_json[Question.QUERY_GRAPH_KEY])

    # @staticmethod
    def format_attribute_trapi_1_1(self, kg_items, graph_interface: GraphInterface):
        for identifier in kg_items:
            # get the properties for the record
            props = kg_items[identifier]

            # save the transpiler attribs
            attributes = props.get('attributes', [])

            # create a new list that doesnt have the core properties
            new_attribs = [attrib for attrib in attributes
                           if attrib['original_attribute_name'] not in props and attrib['original_attribute_name']
                           not in skip_list
                           ]

            # for the non-core properties
            for attr in new_attribs:
                # make sure the original_attribute_name has somthig other than none
                attr['original_attribute_name'] = attr['original_attribute_name'] or ''

                # map the attribute type to the list above, otherwise generic default
                attr["value_type_id"] = VALUE_TYPES.get(attr["original_attribute_name"], "EDAM:data_0006")

                # uses generic data as attribute type id if not defined
                if not ('attribute_type_id' in attr and attr['attribute_type_id'] != 'NA'):
                    attr['attribute_type_id'] = 'biolink:Attribute'

                    # lookup the biolink info
                    bl_info = graph_interface.toolkit.get_element(attr['original_attribute_name'])

                    # did we get something
                    if bl_info is not None:
                        # if there are exact mappings use the first on
                        if 'slot_uri' in bl_info:
                            attr['attribute_type_id'] = bl_info['slot_uri']

                            # was there a range value
                            if 'range' in bl_info and bl_info['range'] is not None:
                                # try to get the type of data
                                new_type = graph_interface.toolkit.get_element(bl_info['range'])
                                # check if new_type is not None. For eg. bl_info['range'] = 'uriorcurie' for things
                                # for `relation` .
                                if new_type:
                                    if 'uri' in new_type and new_type['uri'] is not None:
                                        # get the real data type
                                        attr["value_type_id"] = new_type['uri']
                        elif 'class_uri' in bl_info:
                            attr['attribute_type_id'] = bl_info['class_uri']

            # create a provenance attribute for plater
            provenance_attrib = {
                "attribute_type_id": "biolink:aggregator_knowledge_source",
                "value": self.provenance,
                "value_type_id": "biolink:InformationResource",
                "original_attribute_name": "biolink:aggregator_knowledge_source"
            }

            # add plater provenance to the list
            new_attribs.append(provenance_attrib)

            # assign these attribs back to the original attrib list without the core properties
            props['attributes'] = new_attribs

        return kg_items

    def transform_attributes(self, trapi_message, graph_interface: GraphInterface):
        self.format_attribute_trapi_1_1(trapi_message.get('knowledge_graph', {}).get('nodes', {}), graph_interface)
        self.format_attribute_trapi_1_1(trapi_message.get('knowledge_graph', {}).get('edges', {}), graph_interface)
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
        self._question_json.update(self.transform_attributes(results_dict[0], graph_interface))
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

