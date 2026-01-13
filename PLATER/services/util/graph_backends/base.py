import time
from abc import ABC, abstractmethod
from collections import defaultdict
from functools import cache
from opentelemetry import trace

from reasoner_transpiler.cypher import transform_edges_list
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.util.bl_helper import get_biolink_model_toolkit

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format'))

class GraphBackend(ABC):
    """
    Abstract graph backend interface to support concrete implementations
    such as Neo4jBackend and MemgraphBackend.
    """

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def run(self, *args, **kwargs):
        pass

    @abstractmethod
    def run_sync(self, *args, **kwargs):
        pass

    @abstractmethod
    def supports_apoc(self) -> bool:
        pass


class GraphInterface:
    """
    Singleton class for graph interfacing and access via its GraphBackend instance.
    """

    class _GraphInterface:
        def __init__(self, backend: GraphBackend):
            self.backend = backend
            self.schema = None
            self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            self.toolkit = get_biolink_model_toolkit()
            self.bl_version = config.get('BL_VERSION', '4.2.1')

        async def connect(self):
            await self.backend.connect()

        @cache
        def find_biolink_leaves(self, biolink_concepts: frozenset):
            """
            Given a list of biolink concepts, returns the leaves removing any parent concepts.
            :param biolink_concepts: list of biolink concepts
            :return: leave concepts.
            """
            ancestry_set = set()
            # Keep track of things like "MacromolecularMachine" in current datasets.
            unknown_elements = set()

            for x in biolink_concepts:
                current_element = self.toolkit.get_element(x)
                if not current_element:
                    unknown_elements.add(x)
                ancestors = set(self.toolkit.get_ancestors(x, mixin=True, reflexive=False, formatted=True))
                ancestry_set = ancestry_set.union(ancestors)
            leaf_set = biolink_concepts - ancestry_set - unknown_elements
            return leaf_set

        def invert_predicate(self, biolink_predicate):
            """Given a biolink predicate, find its inverse"""
            element = self.toolkit.get_element(biolink_predicate)
            if element is None:
                return None
            if element.symmetric:
                return biolink_predicate
            if not element.inverse:
                # if neither symmetric nor an inverse is found
                return None
            return self.toolkit.get_element(element['inverse']).slot_uri

        def get_schema(self):
            """
            Gets the schema of the graph. To be used by. Also generates graph summary
            :return: Dict of structure source label as outer most keys, target labels as inner keys and list of predicates
            as value.
            :rtype: dict
            """
            if self.schema is None:
                query = """ 
                MATCH (a)-[x]->(b)
                RETURN DISTINCT labels(a) as source_labels, type(x) as predicate, labels(b) as target_labels
                """
                logger.info(f"Starting schema query {query} on graph... this might take a few.")
                before_time = time.time()
                schema_query_results = self.backend.run_sync(query, convert_to_dict=True)
                after_time = time.time()
                logger.info(f"Completed schema query ({after_time - before_time} seconds). Preparing initial schema.")
                # iterate through results (multiple sets of source label, predicate, target label arrays)
                # and convert them to a schema dictionary of subject->object->predicates
                self.schema = defaultdict(lambda: defaultdict(set))
                for schema_result in schema_query_results:
                    # Since there are some nodes in data currently just one label ['biolink:NamedThing']
                    # This filter is to avoid that scenario.
                    # @TODO need to remove this filter when data build
                    #  avoids adding nodes with single ['biolink:NamedThing'] labels.
                    filter_named_thing = lambda x: list(filter(lambda y: y != 'biolink:NamedThing', x))
                    source_labels, predicate, target_labels = \
                        self.find_biolink_leaves(frozenset(filter_named_thing(schema_result['source_labels']))), \
                            schema_result['predicate'], \
                            self.find_biolink_leaves(frozenset(filter_named_thing(schema_result['target_labels'])))
                    for source_label in source_labels:
                        for target_label in target_labels:
                            self.schema[source_label][target_label].add(predicate)

                # find and add the inverse for each predicate if there is one,
                # keep track of inverted predicates we added so we don't query the graph for them
                for source_label in list(self.schema.keys()):
                    for target_label in list(self.schema[source_label].keys()):
                        inverted_predicates = set()
                        for predicate in self.schema[source_label][target_label]:
                            inverse_predicate = self.invert_predicate(predicate)
                            if inverse_predicate is not None and \
                                    inverse_predicate not in self.schema[target_label][source_label]:
                                inverted_predicates.add(inverse_predicate)
                                self.inverted_predicates[target_label][source_label].add(inverse_predicate)
                        self.schema[target_label][source_label].update(inverted_predicates)

                logger.info("schema done.")
            return self.schema

        async def get_mini_schema(self, source_id, target_id):
            """
            Given either id of source and/or target returns predicates that relate them. And their
            possible labels.
            :param source_id:
            :param target_id:
            :return:
            """
            source_id_syntaxed = f"{{id: \"{source_id}\"}}" if source_id else ''
            target_id_syntaxed = f"{{id: \"{target_id}\"}}" if target_id else ''
            query = f"""
                            MATCH (a{source_id_syntaxed})-[x]->(b{target_id_syntaxed}) WITH
                                [la in labels(a) where la <> 'Concept'] as source_label,
                                [lb in labels(b) where lb <> 'Concept'] as target_label,
                                type(x) as predicate
                            RETURN DISTINCT source_label, predicate, target_label
                        """
            response = await self.backend.run(query, convert_to_dict=True)
            return response

        async def get_node(self, curie: str) -> dict:
            """
            Returns a node that matches curie as its ID.
            :param curie: Curie.
            :type curie: str
            :return: value of the node in neo4j.
            :rtype: list
            """
            query = f"MATCH (n:`biolink:NamedThing`{{id: $node_id}}) return n"
            response = await self.backend.run(query, convert_to_dict=True, query_parameters={'node_id': curie})
            if response and 'n' in response[0]:
                node_object = response[0]['n']
                node_properties = dict(node_object.items())
                return {
                    'id': node_properties.pop('id'),
                    'name': node_properties.pop('name'),
                    'category': self.find_biolink_leaves(node_object.labels),
                    'properties': node_properties
                }
            else:
                return {}

        async def get_single_hop_summary(self,
                                         curie: str) -> dict:
            """
            Returns edges from the node with the curie id to other nodes, optionally filtered by node category or
            predicates.
            :param curie: Curie of source node.
            :type curie: str
            :return: list a list of kinds of edges connected to the curie node and counts of how many there are
            :rtype: list
            """
            query = f'MATCH (n:`biolink:NamedThing`{{id: $node_id}})-[r]-(m) ' \
                    f'RETURN type(r) as predicate, labels(m) as node_labels, count(r) as edge_count'
            response = await self.backend.run(query, convert_to_dict=True, query_parameters={'node_id': curie})

            summary_edges = defaultdict(dict)
            for record in response:
                predicate = record["predicate"]
                edge_count = record["edge_count"]
                leaf_categories = self.find_biolink_leaves(frozenset(record['node_labels']))
                for category in leaf_categories:
                    if category not in summary_edges[predicate]:
                        summary_edges[predicate][category] = {
                            "predicate": predicate,
                            "category": category,
                            "count": edge_count
                        }
                    else:
                        summary_edges[predicate][category]["count"] += edge_count
            summary = {
                "query_curie": curie,
                # flatten the summary_edges dictionary of dictionaries into a list of the most nested values
                "edge_types": [summary_edge for predicate_summary in summary_edges.values()
                               for summary_edge in predicate_summary.values()]
            }
            return summary

        async def get_single_hops(self,
                                  curie: str,
                                  category: str = None,
                                  predicate: str = None,
                                  limit: int = None,
                                  offset: int = None,
                                  count_only: bool = False) -> dict:
            """
            Returns edges from the node with the curie id to other nodes, optionally filtered by node category or
            predicates.
            :param curie: Curie of source node.
            :type curie: str
            :param category: Type of target node.
            :type category: str
            :param category: Predicate.
            :type category: str
            :return: list of edges and nodes where each item contains information about the edge and the other node
            it's connected to
            :rtype: list
            """
            query = f'MATCH (n:`biolink:NamedThing`{{id: $node_id}})'
            query += f'-[r:`{predicate}`]-' if predicate else '-[r]-'
            query += f'(m:`{category}`)' if category else '(m) '

            if count_only:
                query += 'return count(r) as edge_count'
            else:
                query += 'return distinct type(r) as predicate, properties(r) as edge_properties, ' \
                         'CASE WHEN elementId(m) = elementId(startNode(r)) THEN "<" ELSE ">" END AS edge_direction, ' \
                         'm.id as m_id, m.name as m_name, labels(m) as m_labels ORDER BY m_id'

                if offset is not None:
                    query += f' OFFSET {offset}'
                    # query += f' SKIP {offset}'
                if limit is not None:
                    query += f' LIMIT {limit}'

            response = await self.backend.run(query, convert_to_dict=True, query_parameters={'node_id': curie,
                                                                                            'predicate': predicate})

            if count_only:
                edges_response = {
                    "query_curie": curie,
                    "edges": None,
                    "pagination": {
                        "count": response[0]['edge_count'],
                        "offset": None,
                        "limit": None
                    }
                }
                return edges_response

            rows = [{'edge': {'predicate': record['predicate'],
                              'direction': record['edge_direction'],
                              'properties': record['edge_properties']},
                     'adj_node': {'id': record['m_id'],
                                  'name': record['m_name'],
                                  'category': self.find_biolink_leaves(frozenset(record['m_labels']))}
                     }
                    for record in response]
            edges_response = {
                "query_curie": curie,
                "edges": rows,
                "pagination": {
                    "count": len(rows),
                    "offset": offset,
                    "limit": limit
                }
            }
            return edges_response

        async def run_cypher(self,
                             cypher: str,
                             convert_to_dict: bool = False,
                             return_errors: bool = False,
                             convert_to_trapi: bool = False,
                             qgraph: dict = None
                             ) -> list:
            """
            Runs cypher directly.
            :param cypher: cypher query.
            :type cypher: str
            :param convert_to_dict: cypher query.
            :param return_errors: cypher query.
            :param convert_to_trapi: cypher query.
            :param qgraph: cypher query.

            :return: unprocessed neo4j response.
            :rtype: list
            """
            otel_span = trace.get_current_span()
            if not otel_span or not otel_span.is_recording():
                otel_span = None
            else:
                otel_span.add_event("neo4j_query_start",
                                    attributes={
                                        'cypher_query': cypher
                                    })

            cypher_results = await self.backend.run(cypher,
                                                   convert_to_dict=convert_to_dict,
                                                   convert_to_trapi=convert_to_trapi,
                                                   qgraph=qgraph,
                                                   return_errors=return_errors)
            if otel_span is not None:
                otel_span.add_event("neo4j_query_end")
            return cypher_results

        def get_examples(self,
                         subject_node_type,
                         object_node_type=None,
                         predicate=None,
                         num_examples=1,
                         use_qualifiers=False):
            """
            Returns an example for source node only if target is not specified, if target is specified a sample one hop
            is returned.
            :param subject_node_type: Node type of the source node.
            :type subject_node_type: str
            :param object_node_type: Node type of the target node.
            :type object_node_type: str
            :param predicate: Predicate curie for the edge.
            :type predicate: str
            :param num_examples: The maximum number of examples returned.
            :type num_examples: int
            :return: A single source node value if target is not provided. If target is provided too, a triplet.
            :rtype:
            """
            qualifiers_check = " WHERE edge.qualified_predicate IS NOT NULL " if use_qualifiers else ""
            if object_node_type and predicate:
                query = f"MATCH (subject:`{subject_node_type}`)-[edge:`{predicate}`]->(object:`{object_node_type}`) " \
                        f"{qualifiers_check} return subject, edge, object limit {num_examples}"
                response = self.backend.run_sync(query, convert_to_dict=True)
                return response
            elif object_node_type:
                query = f"MATCH (subject:`{subject_node_type}`)-[edge]->(object:`{object_node_type}`) " \
                        f"{qualifiers_check} return subject, edge, object limit {num_examples}"
                response = self.backend.run_sync(query, convert_to_dict=True)
                return response
            else:
                query = f"MATCH (subject:`{subject_node_type}`) " \
                        f"return subject limit {num_examples}"
                response = self.backend.run_sync(query, convert_to_dict=True)
                return response

        def supports_apoc(self) -> bool:
            """
            Returns true if apoc is supported by backend database.
            :return: bool true if neo4j supports apoc.
            """
            return self.backend.supports_apoc()

        async def run_apoc_cover(self, ids: list):
            """
            Runs apoc.algo.cover on list of ids
            :param ids:
            :return: dictionary of edges and source and target nodes ids
            """
            query = f"""
                    MATCH (node:`biolink:NamedThing`)
                    USING INDEX node:`biolink:NamedThing`(id)
                    WHERE node.id in {ids}
                    WITH collect(node) as nodes
                    CALL apoc.algo.cover(nodes) yield rel
                    WITH [elementId(rel), startNode(rel).id, type(rel), endNode(rel).id, properties(rel)] as row
                    return collect(row) as apoc_cover_edges
                    """
            result = await self.backend.run(query, convert_to_dict=True)
            result_edges = result[0]['apoc_cover_edges']
            # utilize the transpiler function to transform the list of edges into a map TRAPI edges
            # apoc_cover_kg_edges is a dict like {edge_id: trapi_edge}
            # element_id_to_edge_id is a mapping of neo4j element_id to edge_id but in this case we won't use it
            apoc_cover_kg_edges, element_id_to_edge_id = transform_edges_list(result_edges)
            return apoc_cover_kg_edges

        async def get_nodes(self, node_ids, core_attributes, attr_types, **kwargs):
            query = f"""
            UNWIND {node_ids} as id
            match (n:`biolink:NamedThing`{{id: id}})
            return apoc.map.fromLists(
                [n IN collect(DISTINCT n) | n.id], 
                [
                    n IN collect(DISTINCT n)| {{
                            categories: labels(n),
                            name: n.name,
                            attributes: [
                                key in apoc.coll.subtract(keys(n), {core_attributes})
                                | 
                                {{
                                    original_attribute_name: key, 
                                    value: n[key],
                                    attribute_type_id: COALESCE({attr_types}[key], "NA")                                    
                                }}                                
                                ]
                            }}
                ]) as result
            """
            return await self.backend.run(query, **kwargs)

        async def close(self):
            await self.backend.close()

    instance = None

    def __init__(self, backend: GraphBackend):
        # create a new instance if not already created.
        if not GraphInterface.instance:
            GraphInterface.instance = GraphInterface._GraphInterface(backend)

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)

    @staticmethod
    async def connect():
        await GraphInterface.instance.connect()
