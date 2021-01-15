from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.question import Question
from functools import reduce


class Overlay:
    def __init__(self, graph_interface: GraphInterface):
        self.graph_interface = graph_interface

    async def overlay_support_edges(self, reasoner_graph):
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

            # all_kg_nodes = set(
            #     reduce(lambda a, b: a + b,
            #            map(lambda node_binding: node_binding[Question.KG_ID_KEY]
            #            if isinstance(node_binding[Question.KG_ID_KEY], list)
            #            # 3. convert every thing to array and reduce
            #            else [node_binding[Question.KG_ID_KEY]],
            #                # 2. merge them into single array
            #                reduce(lambda a, b: a + b,
            #                       # 1. get node bindings from all answers
            #                       map(lambda ans: ans[Question.NODE_BINDINGS_KEY], answer), [])), []))
            # fun part summon APOC
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
                        other_nodes = ans_all_node_ids.difference(set([node_id]))
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
            source_id = r['subject']
            target_id = r['object']
            edge = {}
            edge['subject'] = source_id
            edge['object'] = target_id
            edge['predicate'] = r['predicate']
            edge['id'] = r['edge']['id']
            edge['attributes'] = [{
                "type": "WIKIDATA:Q80585",
                "value": r['edge']
            }]
            m = result.get(source_id, {})
            n = m.get(target_id, list())
            n.append(edge)
            m[target_id] = n
            result[source_id] = m
        return result

