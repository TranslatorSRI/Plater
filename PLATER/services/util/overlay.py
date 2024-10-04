from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.question import Question
from reasoner_transpiler.attributes import ATTRIBUTE_TYPES
from reasoner_transpiler.cypher import transform_attributes
import reasoner_transpiler.cypher_expression as cypher_expression


class Overlay:
    def __init__(self, graph_interface: GraphInterface):
        self.graph_interface = graph_interface

    async def connect_k_nodes(self, reasoner_graph):
        """
        This is the text from the workflow runner describing what overlay_connect_knodes should do:
        Given a TRAPI message, create new kedges between existing knodes. These may be created using arbitrary methods
        or data sources, though provenance should be attached to the new kedges. Each new kedge is also added to all
        results containing node bindings to both the subject and object knodes. This may be independent of any qedge
        connections, i.e. kedges can be created between any nodes in the kgraph.
        :param reasoner_graph:
        :return:
        """
        if not self.graph_interface.supports_apoc():
            raise RuntimeError(f'Error - the neo4j database does not support APOC, '
                               f'overlay_connect_knodes cannot be performed.')

        final_response = {}
        overlay_edges = dict()
        overlayed_answers = list()
        chunk_size = 1000
        chunked_results = [reasoner_graph[Question.RESULTS_KEY][start: start + chunk_size]
                           for start in range(0, len(reasoner_graph[Question.RESULTS_KEY]), chunk_size)]
        for results in chunked_results:
            all_kg_nodes = []
            for result in results:
                result_nodes = result[Question.NODE_BINDINGS_KEY]
                for qid in result_nodes:
                    nodes = result_nodes[qid]
                    for n in nodes:
                        all_kg_nodes.append(n['id'])
            all_kg_nodes = list(all_kg_nodes)
            # find all the edges between the nodes in this chunk of results
            apoc_cover_trapi_edges = (await self.graph_interface.run_apoc_cover(all_kg_nodes))
            apoc_cover_graph = self.structure_apoc_cover_for_easy_lookup(apoc_cover_trapi_edges)
            # now go back to the results and add the edges
            for result in results:
                support_id_suffix = 0
                node_bindings = result[Question.NODE_BINDINGS_KEY]
                ans_all_node_ids = set()
                for qid in node_bindings:
                    nodes = node_bindings[qid]
                    for n in nodes:
                        ans_all_node_ids.add(n['id'])
                for node_id in ans_all_node_ids:
                    other_nodes = ans_all_node_ids.difference({node_id})
                    # lookup current node in apoc_result
                    current_node_relations = apoc_cover_graph.get(node_id, {})
                    for other_node_id in other_nodes:
                        # lookup for relations in apoc_result graph
                        support_edges = current_node_relations.get(other_node_id, [])
                        for support_edge in support_edges:
                            q_graph_id = f'overlay_{support_id_suffix}'
                            support_id_suffix += 1
                            k_graph_id = support_edge['id']
                            result['analyses'][0]['edge_bindings'][q_graph_id] = [{"id": k_graph_id, "attributes": []}]
                            if k_graph_id not in overlay_edges:
                                overlay_edges[k_graph_id] = support_edge
                overlayed_answers.append(result)

        # we'd like to do this, but in reality it's unlikely the edges match perfectly due to null values added
        # by pydantic and/or optional attributes
        # new_edges = {edge_id: edge for edge_id, edge in overlay_edges.items()
        #              if edge not in reasoner_graph[Question.KNOWLEDGE_GRAPH_KEY][Question.EDGES_LIST_KEY].values()}
        for edge in overlay_edges.values():
            del edge['id']

        final_response[Question.QUERY_GRAPH_KEY] = reasoner_graph[Question.QUERY_GRAPH_KEY]
        final_response[Question.RESULTS_KEY] = overlayed_answers
        final_response[Question.KNOWLEDGE_GRAPH_KEY] = reasoner_graph[Question.KNOWLEDGE_GRAPH_KEY]
        final_response[Question.KNOWLEDGE_GRAPH_KEY][Question.EDGES_LIST_KEY].update(overlay_edges)
        return final_response

    @staticmethod
    def structure_apoc_cover_for_easy_lookup(apoc_cover_edges):
        """
        Converts apoc edges in TRAPI format into a mini graph
        :param apoc_cover_edges: this is a map of {edge_id: trapi_edge}
        :return:
        """
        result = {}
        for edge_id, edge in apoc_cover_edges.items():
            # Normally the edge id wouldn't be inside the trapi edge dict but in this case we want it so we can add it
            # to the TRAPI knowledge graph, we'll remove it before returning the TRAPI.
            edge['id'] = edge_id
            source_id = edge['subject']
            target_id = edge['object']
            m = result.get(source_id, {})
            n = m.get(target_id, list())
            n.append(edge)
            m[target_id] = n
            result[source_id] = m
        return result

    async def annotate_node(self, message):
        node_ids = list(message['knowledge_graph'].get('nodes').keys())
        node_ids = cypher_expression.dumps(node_ids)
        # skip RESERVED_NODE_PROPS from being returned in attributes array
        # core_properties = cypher_expression.dumps(RESERVED_NODE_PROPS)
        # mapping for attributes
        attribute_types = cypher_expression.dumps(ATTRIBUTE_TYPES)
        response = await self.graph_interface.get_nodes(node_ids,
                                                        [],
                                                        attribute_types,
                                                        convert_to_dict=True)[0]
        response = {
            node_id: transform_attributes(node) for node_id, node in response.items()
        }
        # overides based on original attribute names
        for n_id in message['knowledge_graph']['nodes']:
            current_node = message['knowledge_graph']['nodes'][n_id]
            # get node from db
            from_db = response.get(n_id, {})
            # skip if node is empty
            if not from_db:
                continue
            result = self.merge_attributes(
                attributes_msg=current_node.get('attributes') or [],
                attributes_neo=from_db.get('attributes') or [])
            # override categories and name if they exist from db else preserve original
            current_node['categories'] = from_db.get('categories') or current_node.get('categories')
            current_node['name'] = from_db.get('name') or current_node.get('name')
            # set attributes of new node to merged attributes
            current_node['attributes'] = result
            message['knowledge_graph']['nodes'][n_id] = current_node
        return message


    def merge_attributes(self, attributes_msg, attributes_neo):
        """
        :param attrs_1: Original attributes from message
        :param attrs_2: attributes from neo4j
        :param skip_list: attributes to skip from neo4j
        :return:
        """
        reformatted_1 = {x['original_attribute_name']: x for x in attributes_msg}
        reformatted_2 = {x['original_attribute_name']: x for x in attributes_neo}
        reformatted_1.update(reformatted_2)
        return [reformatted_1[x] for x in reformatted_1]
