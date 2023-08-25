"""Tools for compiling QGraph into Cypher query."""
import copy
from functools import reduce
import json
from pathlib import Path


from PLATER.transpiler import cypher_expression
from PLATER.transpiler.matching import match_query

DIR_PATH = Path(__file__).parent
with open(DIR_PATH / "attribute_types.json", "r") as stream:
    ATTRIBUTE_TYPES = json.load(stream)

RESERVED_NODE_PROPS = [
    "id",
    "name"
]
RESERVED_EDGE_PROPS = [
    "id",
    "predicate"
]

EDGE_SOURCE_PROPS = [
    "biolink:aggregator_knowledge_source",
    "biolink:primary_knowledge_source"
]


def nest_op(operator, *args):
    """Generate a nested set of operations from a flat expression."""
    if len(args) > 2:
        return [operator, args[0], nest_op(operator, *args[1:])]
    else:
        return [operator, *args]


def assemble_results(qnodes, qedges, **kwargs):
    """Assemble results into Reasoner format."""
    clauses = []
    nodes = [
        f"`{qnode_id}`" for qnode_id in qnodes
    ]
    edges = [
        f"`{qedge_id}`" for qedge_id in qedges
    ]
    return_clause = 'RETURN '
    if nodes:
        return_clause += ', '.join(nodes)
        if edges:
            return_clause += ', '
    if edges:
        return_clause += ', '.join(edges)
    if not (nodes or edges):
        return_clause += '1'
    clauses.append(return_clause)
    # add SKIP and LIMIT sub-clauses
    clauses.extend(pagination(**kwargs))
    return clauses


def pagination(skip=None, limit=None, **kwargs):
    """Get pagination clauses."""
    clauses = []
    if skip is not None:
        clauses.append(f"SKIP {skip}")
    if limit is not None:
        clauses.append(f"LIMIT {limit}")
    return clauses


def get_query(qgraph, **kwargs):
    """Generate a Cypher query to extract the answer maps for a question.

    Returns the query as a string.
    """
    # commented this out because now we rely on the altering the qgraph to transform results into TRAPI,
    # leaving as a reminder in case that breaks something
    # qgraph = copy.deepcopy(qgraph)
    clauses = []
    query = match_query(qgraph, **kwargs)
    clauses.extend(query.compile())
    where_clause = query.where_clause()
    if where_clause:
        if not clauses[-1].startswith("WITH"):
            clauses.append(query.with_clause())
        clauses.append(where_clause)

    if not kwargs.pop("reasoner", True):
        clauses.append(query.return_clause())
        # add SKIP and LIMIT sub-clauses
        clauses.extend(pagination(**kwargs))
    else:
        clauses.extend(assemble_results(
            query.qgraph["nodes"],
            query.qgraph["edges"],
            **kwargs,
        ))

    cypher_query = " ".join(clauses)
    return cypher_query


def transform_result(cypher_result,  # type neo4j.Result
                     qgraph: dict):
    kg_nodes = {}
    kg_edges = {}
    all_qnode_ids = []
    qnode_ids_to_return = []
    qnodes_that_are_sets = set()
    for qnode_id, qnode in qgraph["nodes"].items():
        all_qnode_ids.append(qnode_id)
        if qnode.get('_return', True):
            qnode_ids_to_return.append(qnode_id)
            if qnode.get('is_set', False):
                qnodes_that_are_sets.add(qnode_id)

    results = {}  # results are grouped by unique sets of result node ids
    for cypher_record in cypher_result:
        node_bindings = {}
        result_node_ids_key = ''
        for qnode_id in qnode_ids_to_return:
            if not cypher_record[qnode_id]:
                node_bindings[qnode_id] = []
                continue

            result_node_id = cypher_record[qnode_id].get('id')
            result_node_ids_key += result_node_id
            if qnode_id in qnodes_that_are_sets:
                # if qnode has is_set there won't be any superclass bindings
                node_bindings[qnode_id] = [{'id': result_node_id}]
            else:
                # otherwise create a list of the id mappings including superclass qnode ids if they exist
                node_bindings[qnode_id] = \
                    [{'id': result_node_id, 'query_id': cypher_record[f'{qnode_id}_superclass'].get('id')}
                     if f'{qnode_id}_superclass' in all_qnode_ids else
                     {'id': result_node_id}]

            if result_node_id not in kg_nodes:
                result_node = cypher_record[qnode_id]
                kg_nodes[result_node_id] = {
                    'name': result_node.get('name'),
                    'categories': list(cypher_record[qnode_id].labels),
                    'attributes': [
                        {'original_attribute_name': key,
                         'value': value,
                         'attribute_type_id': ATTRIBUTE_TYPES.get(key, 'NA')}
                        for key, value in result_node.items()
                        if key not in RESERVED_NODE_PROPS
                    ]
                }

        edge_bindings = {}
        for qedge_id, qedge in qgraph['edges'].items():
            result_edge = cypher_record[qedge_id]
            if qedge.get('_return', True) and result_edge:
                graph_edge_id = result_edge.get('id', result_edge.element_id)
                edge_bindings[qedge_id] = [{'id': graph_edge_id}]
                if graph_edge_id not in kg_edges:
                    kg_edges[graph_edge_id] = {
                        'subject': result_edge.start_node.get('id'),
                        'predicate': result_edge.type,
                        'object': result_edge.end_node.get('id'),
                        'sources': [
                            {'resource_role': edge_source_prop,
                             'resource_id': result_edge.get(edge_source_prop)}
                            for edge_source_prop in EDGE_SOURCE_PROPS
                        ],
                        'attributes': [
                            {'original_attribute_name': key,
                             'value': value,
                             'attribute_type_id': ATTRIBUTE_TYPES.get(key, 'NA')}
                            for key, value in result_edge.items()
                            if key not in EDGE_SOURCE_PROPS + RESERVED_EDGE_PROPS
                        ]
                    }

        # if we haven't encountered this specific group of result nodes before, create a new result
        if result_node_ids_key not in results:
            results[result_node_ids_key] = {'analyses': [{'edge_bindings': edge_bindings}],
                                            'node_bindings': node_bindings}
        else:
            # otherwise append new edge bindings to the existing result
            for qedge_id, edge_binding_list in edge_bindings.items():
                results[result_node_ids_key]['analyses'][0]['edge_bindings'][qedge_id].extend(
                    [new_edge_bind for new_edge_bind in edge_binding_list if new_edge_bind['id'] not in
                     [existing_edge_bind['id'] for existing_edge_bind in results[result_node_ids_key]['analyses'][0]['edge_bindings'][qedge_id]]]
                )

    knowledge_graph = {
            'nodes': kg_nodes,
            'edges': kg_edges
        }
    transformed_results = {
        'results': list(results.values()),  # convert the results dictionary to a flattened list
        'knowledge_graph': knowledge_graph
    }
    return transformed_results
