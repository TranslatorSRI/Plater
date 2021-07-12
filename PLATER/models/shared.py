from pydantic import validator
from typing import Dict
from reasoner_pydantic import Query as ReasonerRequestBaseClass, Message, Response, BiolinkEntity, BiolinkPredicate, MetaNode, MetaEdge , MetaKnowledgeGraph, QNode, QEdge


class ReasonerRequest(ReasonerRequestBaseClass):

    @validator("message")
    def validate_unbound_nodes(cls, v):
        q_nodes: Dict[str, QNode] = v.query_graph.nodes
        has_bound_node = False
        for q_node_id in q_nodes:
            q_node = q_nodes[q_node_id]
            if q_node.ids:
                has_bound_node = True
                break
        assert has_bound_node, "Query graph should contain at least one bound node."
        return v

    @validator("message")
    def validate_broken_edge(cls, v):
        q_nodes: Dict[str, QNode] = v.query_graph.nodes
        q_edges: Dict[str, QEdge] = v.query_graph.edges
        for q_edge_id in q_edges:
            edge = q_edges[q_edge_id]
            if edge.subject == edge.object is None:
                continue
            assert edge.subject in q_nodes, f"Query graph edge {q_edge_id} references missing node key {edge.subject}" \
                                            f" in message.query_graph.nodes ."
            assert edge.object in q_nodes,  f"Query graph edge {q_edge_id} references missing node key {edge.object}" \
                                            f" in message.query_graph.nodes ."
        return v
