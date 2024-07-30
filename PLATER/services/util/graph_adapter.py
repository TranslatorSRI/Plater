import base64
import traceback
import httpx
import time
import neo4j

from neo4j import unit_of_work
from opentelemetry import trace
from collections import defaultdict
from reasoner_transpiler.cypher import transform_result
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
        self.graph_db_uri = f'bolt://{host}:{port}'
        self.neo4j_driver = neo4j.AsyncGraphDatabase.driver(self.graph_db_uri, auth=auth)
        self.sync_neo4j_driver = neo4j.GraphDatabase.driver(self.graph_db_uri, auth=auth)
        self._supports_apoc = None
        logger.debug('PINGING NEO4J')
        self.ping()
        logger.debug('CHECKING IF NEO4J SUPPORTS APOC')
        self.check_apoc_support()
        logger.debug(f'SUPPORTS APOC : {self._supports_apoc}')

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

        if convert_to_trapi or convert_to_dict:
            consumed_results = []
            async for record in neo4j_result:
                consumed_results.append(record)
            if convert_to_trapi:
                return transform_result(consumed_results, qgraph, protocol='bolt')
            if convert_to_dict:
                results = []
                for record in consumed_results:
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
        async with self.neo4j_driver.session(database=self.database_name) as session:
            try:
                run_async_result = await session.execute_read(self._async_cypher_tx_function,
                                                              query,
                                                              query_parameters=query_parameters,
                                                              convert_to_dict=convert_to_dict,
                                                              convert_to_trapi=convert_to_trapi,
                                                              qgraph=qgraph)
            except neo4j.exceptions.ClientError as e:
                if return_errors:
                    return {"results": [],
                            "errors": [{"code": e.code,
                                        "message": e.message}]}
                raise e
            except (neo4j.exceptions.DriverError, neo4j.exceptions.ServiceUnavailable) as e:
                if return_errors:
                    return {"results": [],
                            "errors": [{"code": "",
                                        "message": f'A driver error occurred: {e}'}]}
                raise e
            return run_async_result

    def run_sync(self,
                 query,
                 query_parameters=None,
                 return_errors=False,
                 convert_to_dict=False):
        with self.sync_neo4j_driver.session(database=self.database_name) as session:
            try:
                run_sync_result = session.execute_read(self._sync_cypher_tx_function,
                                                       query,
                                                       query_parameters=query_parameters,
                                                       convert_to_dict=convert_to_dict)
            except neo4j.exceptions.ClientError as e:
                if return_errors:
                    return {"results": [],
                            "errors": [{"code": e.code,
                                        "message": e.message}]}
                raise e
            except (neo4j.exceptions.DriverError, neo4j.exceptions.ServiceUnavailable) as e:
                if return_errors:
                    return {"results": [],
                            "errors": [{"code": "",
                                        "message": f'A driver error occurred: {e}'}]}
                raise e
            return run_sync_result

    def ping(self, counter: int = 1, max_retries: int = 3):
        try:
            self.sync_neo4j_driver.verify_connectivity()
            return True
        except neo4j.exceptions.AuthError as e:
            raise e
        except Exception as e:
            if counter > max_retries:
                logger.error(f'Waited too long for Neo4j initialization... giving up..')
                raise RuntimeError('Connection to Neo4j could not be established.')
            logger.info(f'Pinging Neo4j failed, trying again... {repr(e)}')
            time.sleep(10)
            return self.ping(counter + 1)

    def check_apoc_support(self):
        apoc_version_query = 'call apoc.help("meta")'
        if self._supports_apoc is None:
            try:
                self.run_sync(apoc_version_query)
                self._supports_apoc = True
            except neo4j.exceptions.ClientError:
                self._supports_apoc = False
        return self._supports_apoc

    async def close(self):
        self.sync_neo4j_driver.close()
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


class Neo4jHTTPDriver:
    def __init__(self, host: str, port: str,  auth: tuple, scheme: str = 'http'):
        self._host = host
        #  NOTE - here "neo4j" refers to the database name, for the community edition there's only one "neo4j"
        self._neo4j_transaction_endpoint = "/db/neo4j/tx/commit"
        self._scheme = scheme
        self._full_transaction_path = f"{self._scheme}://{self._host}:{port}{self._neo4j_transaction_endpoint}"
        self._port = port
        self._supports_apoc = None
        self._header = {
                'Accept': 'application/json; charset=UTF-8',
                'Content-Type': 'application/json',
                'Authorization': 'Basic %s' % base64.b64encode(f"{auth[0]}:{auth[1]}".encode('utf-8')).decode('utf-8')
            }
        # ping and raise error if neo4j doesn't respond.
        logger.debug('PINGING NEO4J')
        self.ping()
        logger.debug('CHECKING IF NEO4J SUPPORTS APOC')
        self.check_apoc_support()
        logger.debug(f'SUPPORTS APOC : {self._supports_apoc}')

    async def post_request_json(self, payload):
        async with httpx.AsyncClient(timeout=NEO4J_QUERY_TIMEOUT) as session:
            response = await session.post(self._full_transaction_path, json=payload, headers=self._header)
            if response.status_code != 200:
                logger.error(f"[x] Problem contacting Neo4j server {self._host}:{self._port} -- {response.status_code}")
                txt = response.text
                logger.debug(f"[x] Server responded with {txt}")
                try:
                    return response.json()
                except:
                    return txt
            else:
                return response.json()

    def ping(self):
        """
        Pings the neo4j backend.
        :return:
        """
        neo4j_test_connection_endpoint = ""
        ping_url = f"{self._scheme}://{self._host}:{self._port}/{neo4j_test_connection_endpoint}"
        # if we can't contact neo4j, we should exit.
        try:
            now = time.time()
            response = httpx.get(ping_url, headers=self._header)
            later = time.time()
            time_taken = later - now
            logger.debug(f'Contacting neo4j took {time_taken} seconds.')
            if time_taken > 5:  # greater than 5 seconds it's not healthy
                logger.warn(f"Contacting neo4j took more than 5 seconds ({time_taken}). Neo4j might be stressed.")
            if response.status_code != 200:
                raise Exception(f'server returned {response.status_code}')
        except Exception as e:
            logger.error(f"Error contacting Neo4j @ {ping_url} -- Exception raised -- {e}")
            logger.debug(traceback.print_exc())
            raise RuntimeError('Connection to Neo4j could not be established.')

    async def run(self,
                  query,
                  return_errors=False,
                  convert_to_dict=False,
                  convert_to_trapi=False,
                  qgraph=None):
        """
        Runs a neo4j query async.
        :param return_errors: returns errors as values instead of raising an exception
        :param query: Cypher query.
        :param convert_to_dict: whether to convert the neo4j results into a dict
        :param convert_to_trapi: whether to convert the neo4j results into a TRAPI dict
        :param qgraph: the TRAPI qgraph
        :return: result of query.
        :rtype: dict
        """
        # make the statement dictionary
        payload = {
            "statements": [
                {
                    "statement": f"{query}"
                }
            ]
        }

        response = await self.post_request_json(payload)
        errors = response.get('errors')
        if errors:
            logger.error(f'Neo4j returned `{errors}` for cypher {query}.')
            if return_errors:
                return response
            raise RuntimeWarning(f'Error running cypher {query}. {errors}')
        if convert_to_trapi:
            response = transform_result(response, qgraph, protocol='http')
        if convert_to_dict:
            response = convert_http_response_to_dict(response)
        return response

    def run_sync(self, query, convert_to_dict=False):
        """
        Runs a neo4j query. Can cause the async loop to block.
        :param query:
        :param convert_to_dict:
        :return:
        """
        payload = {
            "statements": [
                {
                    "statement": f"{query}"
                }
            ]
        }
        response = httpx.post(
            self._full_transaction_path,
            headers=self._header,
            timeout=NEO4J_QUERY_TIMEOUT,
            json=payload).json()
        errors = response.get('errors')
        if errors:
            logger.error(f'Neo4j returned `{errors}` for cypher {query}.')
            raise RuntimeWarning(f'Error running cypher {query}.')
        if convert_to_dict:
            response = convert_http_response_to_dict(response)
        return response

    def convert_to_dict(self, response: dict) -> list:
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

    def check_apoc_support(self):
        apoc_version_query = 'call apoc.help("meta")'
        if self._supports_apoc is None:
            try:
                self.run_sync(apoc_version_query)
                self._supports_apoc = True
            except:
                self._supports_apoc = False
        return self._supports_apoc


class GraphInterface:
    """
    Singleton class for interfacing with the graph.
    """

    class _GraphInterface:
        def __init__(self, host, port, auth, protocol='bolt'):
            self.protocol = protocol
            if protocol == 'http':
                self.driver = Neo4jHTTPDriver(host=host, port=port, auth=auth)
            elif protocol == 'bolt':
                self.driver = Neo4jBoltDriver(host=host, port=port, auth=auth)
            else:
                raise Exception(f'Unsupported graph interface protocol: {protocol}')
            self.schema = None
            # used to keep track of derived inverted predicates
            self.inverted_predicates = defaultdict(lambda: defaultdict(set))
            # self.summary = None
            self.toolkit = get_biolink_model_toolkit()
            self.bl_version = config.get('BL_VERSION', '4.2.1')

        def find_biolink_leaves(self, biolink_concepts: list):
            """
            Given a list of biolink concepts, returns the leaves removing any parent concepts.
            :param biolink_concepts: list of biolink concepts
            :return: leave concepts.
            """
            ancestry_set = set()
            all_concepts = set(biolink_concepts)
            # Keep track of things like "MacromolecularMachine" in current datasets.
            unknown_elements = set()

            for x in all_concepts:
                current_element = self.toolkit.get_element(x)
                if not current_element:
                    unknown_elements.add(x)
                ancestors = set(self.toolkit.get_ancestors(x, mixin=True, reflexive=False, formatted=True))
                ancestry_set = ancestry_set.union(ancestors)
            leaf_set = all_concepts - ancestry_set - unknown_elements
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
                        self.find_biolink_leaves(filter_named_thing(schema_result['source_labels'])), \
                        schema_result['predicate'], \
                        self.find_biolink_leaves(filter_named_thing(schema_result['target_labels']))
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

        async def get_node(self, node_type: str, curie: str) -> list:
            """
            Returns a node that matches curie as its ID.
            :param node_type: Type of the node.
            :type node_type:str
            :param curie: Curie.
            :type curie: str
            :return: value of the node in neo4j.
            :rtype: list
            """
            query = f"MATCH (c:`{node_type}`{{id: '{curie}'}}) return c"
            response = await self.driver.run(query, convert_to_dict=True)
            return [response[0]['c']]

        async def get_single_hops(self, source_type: str, target_type: str, curie: str) -> list:
            """
            Returns a triplets of source to target where source id is curie.
            :param source_type: Type of the source node.
            :type source_type: str
            :param target_type: Type of target node.
            :type target_type: str
            :param curie: Curie of source node.
            :type curie: str
            :return: list of triplets where each item contains source node, edge, target.
            :rtype: list
            """

            query = f'MATCH (c:`{source_type}`{{id: \'{curie}\'}})-[e]->(b:`{target_type}`) return distinct c , e, b'
            response = await self.driver.run(query, convert_to_dict=True)
            rows = [[{key: value for key, value in record['c'].items()},
                     {key: value for key, value in record['e'].items()},
                     {key: value for key, value in record['b'].items()}] for record in response]
            query = f'MATCH (c:`{source_type}`{{id: \'{curie}\'}})<-[e]-(b:`{target_type}`) return distinct b , e, c'
            response = await self.driver.run(query, convert_to_dict=True)
            rows += [[{key: value for key, value in record['b'].items()},
                     {key: value for key, value in record['e'].items()},
                     {key: value for key, value in record['c'].items()}] for record in response]
            return rows

        async def run_cypher(self,
                             cypher: str,
                             convert_to_dict: bool = False,
                             return_errors: bool = True,
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
                        WITH {{subject: startNode(rel).id ,
                               object: endNode(rel).id,
                               predicate: type(rel),
                               edge: rel }} as row
                        return collect(row) as result                                        
                        """
            result = self.driver.run_sync(query, convert_to_dict=True)
            return result

        async def get_nodes(self, node_ids, core_attributes, attr_types, **kwargs):
            query = f"""
            UNWIND  {node_ids} as id
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
