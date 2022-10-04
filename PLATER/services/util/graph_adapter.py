import base64
import traceback
import os
import httpx

from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from bmt import Toolkit
from PLATER.services.util.attribute_mapping import get_attribute_bl_info

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format')
                                  )


class Neo4jHTTPDriver:
    def __init__(self, host: str, port: int,  auth: tuple, scheme: str = 'http'):
        self._host = host
        self._neo4j_transaction_endpoint = "/db/data/transaction/commit"
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

    async def post_request_json(self, payload, timeout=600):
        async with httpx.AsyncClient(timeout=timeout) as session:
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
            import time
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

    async def run(self, query, return_errors=False, timeout=600):
        """
        Runs a neo4j query async.
        :param timeout: http timeout for queries sent to neo4j
        :param return_errors: returns errors as values instead of raising an exception
        :param query: Cypher query.
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

        response = await self.post_request_json(payload, timeout=timeout)
        errors = response.get('errors')
        if errors:
            logger.error(f'Neo4j returned `{errors}` for cypher {query}.')
            if return_errors:
                return response
            raise RuntimeWarning(f'Error running cypher {query}. {errors}')
        return response

    def run_sync(self, query):
        """
        Runs a neo4j query. Can cause the async loop to block.
        :param query:
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
            timeout=1500,
            json=payload).json()
        errors = response.get('errors')
        if errors:
            logger.error(f'Neo4j returned `{errors}` for cypher {query}.')
            raise RuntimeWarning(f'Error running cypher {query}.')
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
        def __init__(self, host, port, auth, query_timeout):
            self.driver = Neo4jHTTPDriver(host=host, port=port, auth=auth)
            self.schema = None
            self.summary = None
            self.meta_kg = None
            self.sri_testing_data = None
            self.query_timeout = query_timeout
            self.toolkit = Toolkit()

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
            if 'symmetric' in element and element.symmetric:
                return biolink_predicate
            # if neither symmetric nor an inverse is found
            if 'inverse' not in element or not element['inverse']:
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
            self.schema_raw_result = {}
            if self.schema is None:
                query = """
                           MATCH (a)-[x]->(b)
                           WHERE not a:Concept and not b:Concept                                                          
                           RETURN DISTINCT labels(a) as source_labels, type(x) as predicate, labels(b) as target_labels
                           """
                logger.info(f"starting query {query} on graph... this might take a few")
                result = self.driver.run_sync(query)
                logger.info(f"completed query, preparing initial schema")
                structured = self.convert_to_dict(result)
                self.schema_raw_result = structured
                schema_bag = {}
                # permute source labels and target labels array
                # replacement for unwind for previous cypher
                structured_expanded = []
                for triplet in structured:
                    # Since there are some nodes in data currently just one label ['biolink:NamedThing']
                    # This filter is to avoid that scenario.
                    # @TODO need to remove this filter when data build
                    #  avoids adding nodes with single ['biolink:NamedThing'] labels.
                    filter_named_thing = lambda x: list(filter(lambda y: y != 'biolink:NamedThing', x))
                    source_labels, predicate, target_labels =\
                        self.find_biolink_leaves(filter_named_thing(triplet['source_labels'])), triplet['predicate'], \
                        self.find_biolink_leaves(filter_named_thing(triplet['target_labels']))
                    for source_label in source_labels:
                        for target_label in target_labels:
                            structured_expanded.append(
                                {
                                    'source_label': source_label,
                                    'target_label': target_label,
                                    'predicate': predicate
                                }
                            )
                structured = structured_expanded
                for triplet in structured:
                    subject = triplet['source_label']
                    predicate = triplet['predicate']
                    objct = triplet['target_label']
                    if subject not in schema_bag:
                        schema_bag[subject] = {}
                    if objct not in schema_bag[subject]:
                        schema_bag[subject][objct] = []
                    if predicate not in schema_bag[subject][objct]:
                        schema_bag[subject][objct].append(predicate)

                    # If we invert the order of the nodes we also have to invert the predicate
                    inverse_predicate = self.invert_predicate(predicate)
                    if inverse_predicate is not None and \
                            inverse_predicate not in schema_bag.get(objct,{}).get(subject,[]):
                        # create the list if empty
                        if objct not in schema_bag:
                            schema_bag[objct] = {}
                        if subject not in schema_bag[objct]:
                            schema_bag[objct][subject] = []
                        schema_bag[objct][subject].append(inverse_predicate)
                self.schema = schema_bag
                logger.info("schema done.")
                if not self.summary:
                    query = """
                    MATCH (c) RETURN DISTINCT labels(c) as types, count(c) as count                
                    """
                    logger.info(f'generating graph summary: {query}')
                    raw = self.convert_to_dict(self.driver.run_sync(query))
                    summary = {}
                    for node in raw:
                        labels = node['types']
                        count = node['count']
                        query = f"""
                        MATCH (:{':'.join(labels)})-[e]->(b) WITH DISTINCT e , b 
                        RETURN 
                            type(e) as edge_types, 
                            count(e) as edge_counts,
                            labels(b) as target_labels 
                        """
                        raw = self.convert_to_dict(self.driver.run_sync(query))
                        summary_key = ':'.join(labels)
                        summary[summary_key] = {
                            'nodes_count': count,
                            'labels': labels
                        }
                        for row in raw:
                            target_key = ':'.join(row['target_labels'])
                            edge_name = row['edge_types']
                            edge_count = row['edge_counts']
                            summary[summary_key][target_key] = summary[summary_key].get(target_key, {})
                            summary[summary_key][target_key][edge_name] = edge_count
                    self.summary = summary
                    logger.info(f'generated summary for {len(summary)} node types.')
                    for nodes in summary:
                        leaf_type = self.find_biolink_leaves(summary[nodes]['labels'])
                        if len(leaf_type):
                            leaf_type = list(leaf_type)[0]
                            if leaf_type not in schema_bag:
                                self.schema[leaf_type] = {}
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
            response = await self.driver.run(query)
            response = self.convert_to_dict(response)
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
            response = await self.driver.run(query)

            data = response.get('results',[{}])[0].get('data', [])
            '''
            data looks like 
            [
            {'row': [{...node data..}], 'meta': [{...}]},
            {'row': [{...node data..}], 'meta': [{...}]},
            {'row': [{...node data..}], 'meta': [{...}]}
            ]            
            '''
            rows = []
            if len(data):
                from functools import reduce
                rows = reduce(lambda x, y: x + y.get('row', []), data, [])
            return rows

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
            response = await self.driver.run(query)
            rows = list(map(lambda data: data['row'], response['results'][0]['data']))
            query = f'MATCH (c:`{source_type}`{{id: \'{curie}\'}})<-[e]-(b:`{target_type}`) return distinct b , e, c'
            response = await self.driver.run(query)
            rows += list(map(lambda data: data['row'], response['results'][0]['data']))

            return rows

        async def run_cypher(self, cypher: str, **kwargs) -> list:
            """
            Runs cypher directly.
            :param cypher: cypher query.
            :type cypher: str
            :return: unprocessed neo4j response.
            :rtype: list
            """
            kwargs['timeout'] = self.query_timeout
            return await self.driver.run(cypher, **kwargs)

        async def get_sample(self, node_type):
            """
            Returns a few nodes.
            :param node_type: Type of nodes.
            :type node_type: str
            :return: Node dict values.
            :rtype: dict
            """
            query = f"MATCH (c:{node_type}) return c limit 5"
            response = await self.driver.run(query)
            rows = response['results'][0]['data'][0]['row']
            return rows

        def get_examples(self, subject_node_type, object_node_type=None, predicate=None, num_examples=1):
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
            if object_node_type and predicate:
                query = f"MATCH (subject:`{subject_node_type}`)-[edge:`{predicate}`]->(object:`{object_node_type}`) " \
                        f"return subject, edge, object limit {num_examples}"
                response = self.convert_to_dict(self.driver.run_sync(query))
                return response
            elif object_node_type:
                query = f"MATCH (subject:`{subject_node_type}`)-[edge]->(object:`{object_node_type}`) " \
                        f"return subject, edge, object limit {num_examples}"
                response = self.convert_to_dict(self.driver.run_sync(query))
                return response
            else:
                # this looks weird and I don't think it's used but leaving here just in case
                query = f"MATCH (`{subject_node_type}`:`{subject_node_type}`) " \
                        f"return `{subject_node_type}` limit {num_examples}"
                response = self.convert_to_dict(self.driver.run_sync(query))
                return response

        def get_curie_prefix_by_node_type(self, node_type):
            query = f"""
            MATCH (n:`{node_type}`) return collect(n.id) as ids , collect(keys(n)) as attributes
            """
            logger.info(f"starting query {query} on graph... this might take a few")
            result = self.driver.run_sync(query)
            logger.info(f"completed query, collecting node curie prefixes")
            result = self.convert_to_dict(result)
            curie_prefixes = set()
            for i in result[0]['ids']:
                curie_prefixes.add(i.split(':')[0])
            # sort according to bl model
            node_bl_def = self.toolkit.get_element(node_type)
            id_prefixes = node_bl_def.id_prefixes
            sorted_curie_prefixes = [i for i in id_prefixes if i in curie_prefixes] # gives presidence to what's in BL
            # add other ids even if not in BL next
            sorted_curie_prefixes += [i for i in curie_prefixes if i not in sorted_curie_prefixes]
            all_keys = set()
            for keys in result[0]['attributes']:
                for k in keys:
                    all_keys.add(k)

            attributes_as_bl_types = []
            for key in all_keys:
                attr_data = get_attribute_bl_info(key)
                if attr_data:
                    attr_data['original_attribute_names'] = [key]
                    attributes_as_bl_types.append(attr_data)
            return sorted_curie_prefixes, attributes_as_bl_types

        def generate_meta_kg_and_test_data(self):
            schema = self.get_schema()
            nodes = {}
            predicates = []
            test_edges = []
            for subject in schema:
                if subject not in nodes:
                    curies, attributes = self.get_curie_prefix_by_node_type(subject)
                    nodes[subject] = {'id_prefixes': curies, "attributes": attributes}
                for object in schema[subject]:
                    if object not in nodes:
                        curies, attributes = self.get_curie_prefix_by_node_type(object)
                        nodes[object] = {'id_prefixes': curies, "attributes": attributes}
                    for predicate in schema[subject][object]:
                        predicates.append({
                            'subject': subject,
                            'object': object,
                            'predicate': predicate
                        })
                        example_edges = self.get_examples(subject_node_type=subject,
                                                          object_node_type=object,
                                                          predicate=predicate,
                                                          num_examples=1)
                        if example_edges:
                            neo4j_edge = example_edges[0]
                            test_edge = {
                                "subject_category": subject,
                                "object_category": object,
                                "predicate": predicate,
                                "subject": neo4j_edge['subject']['id'],
                                "object": neo4j_edge['object']['id']
                            }
                            test_edges.append(test_edge)

            self.meta_kg = {
                'nodes': nodes,
                'edges': predicates
            }
            plater_url = os.environ['PUBLIC_URL']
            self.sri_testing_data = {
                'url': plater_url,
                'edges': test_edges
            }

        async def get_meta_kg(self):
            if not self.meta_kg:
                self.generate_meta_kg_and_test_data()
            return self.meta_kg

        async def get_sri_testing_data(self):
            if not self.sri_testing_data:
                self.generate_meta_kg_and_test_data()
            return self.sri_testing_data

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
            result = self.convert_to_dict(self.driver.run_sync(query))
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


        def convert_to_dict(self, result):
            return self.driver.convert_to_dict(result)

    instance = None

    def __init__(self, host, port, auth, query_timeout=600):
        # create a new instance if not already created.
        if not GraphInterface.instance:
            GraphInterface.instance = GraphInterface._GraphInterface(host=host,
                                                                     port=port,
                                                                     auth=auth,
                                                                     query_timeout=query_timeout)

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)
