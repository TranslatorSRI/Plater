from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.question import Question, cypher_expression, RESERVED_NODE_PROPS, skip_list
import os
import json

map_data = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "attr_val_map.json")))

ATTRIBUTE_TYPES = map_data['attribute_type_map']


class Overlay:
    def __init__(self, graph_interface: GraphInterface):
        self.graph_interface = graph_interface

    async def connect_k_nodes(self, reasoner_graph):
        """
        Grabs a set of answers and queries for connection among set of nodes
        :param reasoner_graph:
        :return:
        """
        final_response = {}
        edges_to_add = dict()
        overlayed_answers = list()
        chunk_size = 1000
        chunked_answers = [reasoner_graph[Question.ANSWERS_KEY][start: start + chunk_size]
                           for start in range(0, len(reasoner_graph[Question.ANSWERS_KEY]), chunk_size)]
        for answer in chunked_answers:
            # 3. filter out kg ids
            all_kg_nodes = []
            for ans in answer:
                ans_nodes = ans[Question.NODE_BINDINGS_KEY]
                for qid in ans_nodes:
                    nodes = ans_nodes[qid]
                    for n in nodes:
                        all_kg_nodes.append(n['id'])

            if self.graph_interface.supports_apoc():
                all_kg_nodes = list(all_kg_nodes)
                apoc_result = (await self.graph_interface.run_apoc_cover(all_kg_nodes))[0]['result']
                apoc_result = self.structure_for_easy_lookup(apoc_result)
                # now go back to the answers and add the edges
                for ans in answer:
                    support_id_suffix = 0
                    node_bindings = ans[Question.NODE_BINDINGS_KEY]
                    ans_all_node_ids = set()
                    for qid in node_bindings:
                        nodes = node_bindings[qid]
                        for n in nodes:
                            ans_all_node_ids.add(n['id'])
                    for node_id in ans_all_node_ids:
                        other_nodes = ans_all_node_ids.difference({node_id})
                        # lookup current node in apoc_result
                        current_node_relations = apoc_result.get(node_id, {})
                        for other_node_id in other_nodes:
                            # lookup for relations in apoc_result graph
                            support_edges = current_node_relations.get(other_node_id, [])
                            for support_edge in support_edges:
                                q_graph_id = f's_{support_id_suffix}'
                                support_id_suffix += 1
                                k_graph_id = support_edge['id']
                                del support_edge['id']
                                ans['edge_bindings'][q_graph_id] = [{"id": k_graph_id}]
                                if k_graph_id not in edges_to_add:
                                    edges_to_add[k_graph_id] = support_edge
                    overlayed_answers.append(ans)
                    # @TODO raise exception if apoc is not supported

        final_response[Question.QUERY_GRAPH_KEY] = reasoner_graph[Question.QUERY_GRAPH_KEY]
        final_response[Question.ANSWERS_KEY] = overlayed_answers
        final_response[Question.KNOWLEDGE_GRAPH_KEY] = reasoner_graph[Question.KNOWLEDGE_GRAPH_KEY]
        final_response[Question.KNOWLEDGE_GRAPH_KEY][Question.EDGES_LIST_KEY].update(edges_to_add)
        return final_response

    def structure_for_easy_lookup(self, result_set):
        """
        Converts apoc result into a mini graph
        :param result_set:
        :return:
        """
        result = {}
        for r in result_set:
            edge = r['edge']
            core_attributes = ['subject', 'object', 'predicate', 'id']
            attributes = []
            new_edge = {attr: r['edge'][attr] for attr in core_attributes}
            for attribute in edge:
                if attribute not in core_attributes:
                    attributes.append({
                        'original_attribute_name': attribute,
                        'value': edge[attribute]
                    })
            new_edge['attributes'] = attributes

            edge = Question({}).format_attribute_trapi({'edge': new_edge}, self.graph_interface)['edge']
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
        # skip name , id , categories from being returned in attributes array
        core_properties = cypher_expression.dumps(RESERVED_NODE_PROPS + ['name'])
        # mapping for attributes
        attribute_types = cypher_expression.dumps(ATTRIBUTE_TYPES)
        response = self.graph_interface.convert_to_dict(
            await self.graph_interface.get_nodes(node_ids, core_properties, attribute_types)
        )[0]['result']
        response = Question({}).format_attribute_trapi(response, self.graph_interface)
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
                attributes_neo=from_db.get('attributes') or [],
                skip_list=skip_list)
            # override categories and name if they exist from db else preserve original
            current_node['categories'] = from_db.get('categories') or current_node['categories']
            current_node['name'] = from_db.get('name') or current_node['name']
            # set attributes of new node to merged attributes
            current_node['attributes'] = result
            message['knowledge_graph']['nodes'][n_id] = current_node
        return message

    def merge_attributes(self, attributes_msg, attributes_neo, skip_list=[]):
        """
        :param attrs_1: Original attributes from message
        :param attrs_2: attributes from neo4j
        :param skip_list: attributes to skip from neo4j
        :return:
        """
        reformatted_1 = {x['original_attribute_name']: x for x in attributes_msg}
        reformatted_2 = {x['original_attribute_name']: x for x in attributes_neo if x not in skip_list}
        reformatted_1.update(reformatted_2)
        return [reformatted_1[x] for x in reformatted_1]
