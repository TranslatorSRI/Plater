import time
import neo4j
import asyncio

import neo4j.exceptions
from functools import cache
from neo4j import unit_of_work
from opentelemetry import trace
from collections import defaultdict
from reasoner_transpiler.cypher import transform_result, transform_edges_list
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.util.bl_helper import get_biolink_model_toolkit

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format'))

NEO4J_QUERY_TIMEOUT = int(config.get('NEO4J_QUERY_TIMEOUT', 1600))


class Neo4jBoltDriver:

    def __init__(self,
                 host: str,
                 port: str,
                 auth: tuple,
                 database_name: str = 'neo4j'):
        self.database_name = database_name
        self.database_auth = auth
        self.graph_db_uri = f'bolt://{host}:{port}'
        self.neo4j_driver = None
        self.sync_neo4j_driver = None
        self._supports_apoc = None

    async def connect_to_neo4j(self, retries=0):
        if not self.neo4j_driver:
            self.neo4j_driver = neo4j.AsyncGraphDatabase.driver(self.graph_db_uri,
                                                                auth=self.database_auth,
                                                                **{'telemetry_disabled': True,
                                                                   'max_connection_pool_size': 1000})
        try:
            await self.neo4j_driver.verify_connectivity()
        except Exception as e:  # currently the driver says it raises Exception, not something more specific
            await self.neo4j_driver.close()
            if retries <= 25:
                await asyncio.sleep(8)
                logger.error(f'Could not establish connection to neo4j, trying again... retry {retries + 1}')
                await self.connect_to_neo4j(retries + 1)
            else:
                logger.error(f'Could not establish connection to neo4j, error: {e}')
                raise e

    @staticmethod
    @unit_of_work(timeout=NEO4J_QUERY_TIMEOUT)
    async def _async_cypher_tx_function(tx,
                                        cypher,
                                        query_parameters=None,
                                        convert_to_dict=False,
                                        convert_to_trapi=False,
                                        qgraph=None):
        if not query_parameters:
            query_parameters = {}

        neo4j_result: neo4j.AsyncResult = await tx.run(cypher, parameters=query_parameters)
        if convert_to_trapi:
            neo4j_record = await neo4j_result.single()
            return transform_result(neo4j_record, qgraph)
        elif convert_to_dict:
            results = []
            async for record in neo4j_result:
                results.append({key: value for key, value in record.items()})
            return results
        return await convert_bolt_results_to_cypher_result(neo4j_result)

    @staticmethod
    def _sync_cypher_tx_function(tx,
                                 cypher,
                                 query_parameters=None,
                                 convert_to_dict=False):
        if not query_parameters:
            query_parameters = {}
        neo4j_result: neo4j.Result = tx.run(cypher, parameters=query_parameters)
        if convert_to_dict:
            results = []
            for record in neo4j_result:
                results.append({key: value for key, value in record.items()})
            return results
        else:
            return neo4j_result

    async def run(self,
                  query,
                  query_parameters=None,
                  return_errors=False,
                  convert_to_dict=False,
                  convert_to_trapi=False,
                  qgraph=None):
        try:
            async with self.neo4j_driver.session(database=self.database_name,
                                                 default_access_mode=neo4j.READ_ACCESS) as session:
                run_async_result = await session.execute_read(self._async_cypher_tx_function,
                                                              query,
                                                              query_parameters=query_parameters,
                                                              convert_to_dict=convert_to_dict,
                                                              convert_to_trapi=convert_to_trapi,
                                                              qgraph=qgraph)
        except neo4j.exceptions.ServiceUnavailable as e:
            logger.error(f'Session could not establish connection to neo4j ({e}).. trying to connect again')
            await self.connect_to_neo4j()
            return await self.run(query,
                                  query_parameters=query_parameters,
                                  return_errors=return_errors,
                                  convert_to_dict=convert_to_dict,
                                  convert_to_trapi=convert_to_trapi,
                                  qgraph=qgraph)
        except neo4j.exceptions.Neo4jError as e:
            logger.error(e)
            if return_errors:
                return {"results": [],
                        "errors": [{"code": e.code,
                                    "message": e.message}]}
            raise e
        except neo4j.exceptions.DriverError as e:
            logger.error(e)
            if return_errors:
                return {"results": [],
                        "errors": [{"message": f'A driver error occurred: {e}'}]}
            raise e
        return run_async_result

    def run_sync(self,
                 query,
                 query_parameters=None,
                 return_errors=False,
                 convert_to_dict=False):
        if not self.sync_neo4j_driver:
            self.sync_neo4j_driver = neo4j.GraphDatabase.driver(self.graph_db_uri, auth=self.database_auth)
        try:
            with self.sync_neo4j_driver.session(database=self.database_name, default_access_mode=neo4j.READ_ACCESS) as session:

                run_sync_result = session.execute_read(self._sync_cypher_tx_function,
                                                       query,
                                                       query_parameters=query_parameters,
                                                       convert_to_dict=convert_to_dict)
                return run_sync_result

        except neo4j.exceptions.Neo4jError as e:
            if return_errors:
                logger.error(e)
                return {"results": [],
                        "errors": [{"code": e.code,
                                    "message": e.message}]}
            raise e
        except (neo4j.exceptions.DriverError, neo4j.exceptions.ServiceUnavailable) as e:
            if return_errors:
                logger.error(e)
                return {"results": [],
                        "errors": [{"code": "",
                                    "message": f'A driver error occurred: {e}'}]}
            raise e
        finally:
            if self.sync_neo4j_driver:
                self.sync_neo4j_driver.close()
            self.sync_neo4j_driver = None

    def check_apoc_support(self):
        apoc_version_query = 'call apoc.version()'
        if self._supports_apoc is None:
            try:
                self.run_sync(apoc_version_query)
                self._supports_apoc = True
            except neo4j.exceptions.ClientError:
                self._supports_apoc = False
        return self._supports_apoc

    async def close(self):
        await self.neo4j_driver.close()


# this is kind of hacky but in order to return the same pydantic model result for both drivers
# convert the raw bolt cypher response to something that's formatted like the http json response
async def convert_bolt_results_to_cypher_result(result: neo4j.AsyncResult):
    cypher_result = {
        "results": [
            {
                "columns": result.keys(),
                "data": [{"row": [values for values in list(data.values())], "meta": []}
                         for data in await result.data()]
            }
        ],
        "errors": []
    }
    return cypher_result


def convert_http_response_to_dict(response: dict) -> list:
    """
    Converts a neo4j result to a structured result.
    :param response: neo4j http raw result.
    :type response: dict
    :return: reformatted dict
    :rtype: dict
    """
    results = response.get('results')
    array = []
    if results:
        for result in results:
            cols = result.get('columns')
            if cols:
                data_items = result.get('data')
                for item in data_items:
                    new_row = {}
                    row = item.get('row')
                    for col_name, col_value in zip(cols, row):
                        new_row[col_name] = col_value
                    array.append(new_row)
    return array


class GraphInterface:
    """
    Singleton class for interfacing with the graph.
    """

    class _GraphInterface:
        def __init__(self, host, port, auth, protocol='bolt'):
            self.protocol = protocol
            if protocol == 'bolt':
                self.driver = Neo4jBoltDriver(host=host, port=port, auth=auth)
            else:
                raise Exception(f'Unsupported graph interface protocol: {protocol}')
            self.schema = None
            # used to keep track of derived inverted predicates
            self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            # self.summary = None
            self.toolkit = get_biolink_model_toolkit()
            self.bl_version = config.get('BL_VERSION', '4.2.1')

        async def connect_to_neo4j(self):
            await self.driver.connect_to_neo4j()

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
            # If its symmetric
            if element.symmetric:
                return biolink_predicate
            # if neither symmetric nor an inverse is found
            if not element.inverse:
                return None
            # if an inverse is found
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
                schema_query_results = self.driver.run_sync(query, convert_to_dict=True)
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
            response = await self.driver.run(query, convert_to_dict=True)
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
            response = await self.driver.run(query, convert_to_dict=True, query_parameters={'node_id': curie})
            if response and 'n' in response[0]:
                node_object: neo4j.graph.Node = response[0]['n']
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
            response = await self.driver.run(query, convert_to_dict=True, query_parameters={'node_id': curie})
            summary = defaultdict(list)
            for record in response:
                summary[record['predicate']].append([self.find_biolink_leaves(frozenset(record['node_labels'])), record['edge_count']])
            return dict(summary)

        async def get_single_hops(self,
                                  curie: str,
                                  category: str = None,
                                  predicate: str = None,
                                  limit: int = None,
                                  offset: int = None) -> list:
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
            query += f'(m:`{category}`)' if category else '(m)'
            query += ' return distinct type(r) as predicate, properties(r) as edge_properties, ' \
                     'CASE WHEN elementId(m) = elementId(startNode(r)) THEN "<" ELSE ">" END AS edge_direction, ' \
                     'm.id as m_id, m.name as m_name, labels(m) as m_labels ORDER BY m_id'

            if offset is not None:
                query += f' OFFSET {offset}'
                # query += f' SKIP {offset}'
            if limit is not None:
                query += f' LIMIT {limit}'

            response = await self.driver.run(query, convert_to_dict=True, query_parameters={'node_id': curie,
                                                                                            'predicate': predicate})
            rows = [{'edge': {'predicate': record['predicate'],
                              'direction': record['edge_direction'],
                              'properties': record['edge_properties']},
                     'adj_node': {'id': record['m_id'],
                                  'name': record['m_name'],
                                  'category': self.find_biolink_leaves(frozenset(record['m_labels']))}
                     }
                    for record in response]
            return rows

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
            # get a reference to the current opentelemetry span
            otel_span = trace.get_current_span()
            if not otel_span or not otel_span.is_recording():
                otel_span = None
            else:
                otel_span.add_event("neo4j_query_start",
                                    attributes={
                                        'cypher_query': cypher
                                    })
            cypher_results = await self.driver.run(cypher,
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
                response = self.driver.run_sync(query, convert_to_dict=True)
                return response
            elif object_node_type:
                query = f"MATCH (subject:`{subject_node_type}`)-[edge]->(object:`{object_node_type}`) " \
                        f"{qualifiers_check} return subject, edge, object limit {num_examples}"
                response = self.driver.run_sync(query, convert_to_dict=True)
                return response
            else:
                query = f"MATCH (subject:`{subject_node_type}`) " \
                        f"return subject limit {num_examples}"
                response = self.driver.run_sync(query, convert_to_dict=True)
                return response

        def supports_apoc(self):
            """
            Returns true if apoc is supported by backend database.
            :return: bool true if neo4j supports apoc.
            """
            return self.driver.check_apoc_support()

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
            result = await self.driver.run(query, convert_to_dict=True)
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
            return await self.driver.run(query, **kwargs)

        async def close(self):
            await self.driver.close()

    instance = None

    def __init__(self, host, port, auth, protocol='bolt'):
        # create a new instance if not already created.
        if not GraphInterface.instance:
            GraphInterface.instance = GraphInterface._GraphInterface(host=host,
                                                                     port=port,
                                                                     auth=auth,
                                                                     protocol=protocol)

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)

    @staticmethod
    async def connect_to_neo4j():
        await GraphInterface.instance.connect_to_neo4j()
