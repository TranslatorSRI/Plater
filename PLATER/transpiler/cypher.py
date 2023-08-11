"""Tools for compiling QGraph into Cypher query."""
import copy
from functools import reduce
import json
from operator import and_
from pathlib import Path

from PLATER.transpiler import cypher_expression
from PLATER.transpiler.matching import match_query

DIR_PATH = Path(__file__).parent
with open(DIR_PATH / "attribute_types.json", "r") as stream:
    ATTRIBUTE_TYPES = json.load(stream)

RESERVED_NODE_PROPS = [
    "id",
    "category",
]
RESERVED_EDGE_PROPS = [
    "id",
    "predicate",
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


def transpile_compound(qgraph, **kwargs):
    """Transpile compound qgraph."""
    if isinstance(qgraph, dict):
        return match_query(
            qgraph,
            **kwargs,
        )
    if qgraph[0] == "OR":
        qgraph = nest_op(*qgraph)

    args = [
        transpile_compound(arg, **kwargs)
        for arg in qgraph[1:]
    ]
    if qgraph[0] == "AND":
        return reduce(and_, args)
    elif qgraph[0] == "OR":
        return args[0] | args[1]
    elif qgraph[0] == "XOR":
        if len(args) != 2:
            raise ValueError("XOR must have exactly two operands")
        return args[0] ^ args[1]
    elif qgraph[0] == "NOT":
        if len(args) != 1:
            raise ValueError("NOT must have exactly one operand")
        return ~args[0]
    raise ValueError(f"Unrecognized operator \"{qgraph[0]}\"")


def assemble_results(qnodes, qedges, **kwargs):
    """Assemble results into Reasoner format."""
    clauses = []

    # assemble result (bindings) and associated (result) kgraph
    node_bindings = [
        (
            "`{0}`: [ni IN collect(DISTINCT `{0}`.id) "
            "WHERE ni IS NOT null "
            "| {{id: ni}}]"
        ).format(
            qnode_id,
        ) if qnode.get("is_set", False) else
        (
            "`{0}`: (CASE "
            "WHEN `{0}` IS NOT NULL THEN [{{id: `{0}`.id{1}}}] "
            "ELSE [] "
            "END)"
        ).format(
            qnode_id,
            f", qnode_id: `{qnode_id}_superclass`.id" if f"{qnode_id}_superclass" in qnodes else "",
        )
        for qnode_id, qnode in qnodes.items()
        if qnode.get("_return", True)
    ]
    edge_bindings = [
        (
            "`{0}`: [ei IN collect(DISTINCT toString(id(`{0}`))) "
            "WHERE ei IS NOT null "
            "| {{id: ei}}]"
        ).format(
            qedge_id,
        ) if kwargs.get("relationship_id", "property") == "internal" else
        (
            "`{0}`: [ei IN collect(DISTINCT `{0}`.id) "
            "WHERE ei IS NOT null "
            "| {{id: ei}}]"
        ).format(
            qedge_id,
        )
        for qedge_id, qedge in qedges.items()
        if qedge.get("_return", True)
    ]
    knodes = [
        "collect(DISTINCT `{0}`)".format(qnode_id)
        for qnode_id, qnode in qnodes.items()
        if qnode.get("_return", True)
    ]
    kedges = [
        "collect(DISTINCT `{0}`)".format(qedge_id)
        for qedge_id, qedge in qedges.items()
        if qedge.get("_return", True)
    ]
    assemble_clause = (
        "WITH {{node_bindings: {{{0}}}, analyses: [{{edge_bindings: {{{1}}}}}]}} AS result, "
        "{{nodes: {2}, edges: {3}}} AS knowledge_graph"
    ).format(
        ", ".join(node_bindings) or "",
        ", ".join(edge_bindings) or "",
        " + ".join(knodes) or "[]",
        " + ".join(kedges) or "[]",
    )
    clauses.append(assemble_clause)

    # add SKIP and LIMIT sub-clauses
    clauses.extend(pagination(**kwargs))

    # collect results and aggregate kgraphs
    # also fetch extra knode/kedge properties
    if knodes:
        clauses.append("UNWIND knowledge_graph.nodes AS knode")
    if kedges:
        clauses.append("UNWIND knowledge_graph.edges AS kedge")
    aggregate_clause = "WITH collect(DISTINCT result) AS results, {"
    aggregate_clause += (
        (
            "nodes: apoc.map.fromLists("
            "[n IN collect(DISTINCT knode) | n.id], "
            "[n IN collect(DISTINCT knode) | {"
            "categories: labels(n), name: n.name, "
            "attributes: [key in apoc.coll.subtract(keys(n), "
            + cypher_expression.dumps(RESERVED_NODE_PROPS) +
            ") | {original_attribute_name: key, attribute_type_id: COALESCE("
            + cypher_expression.dumps(ATTRIBUTE_TYPES) +
            "[key], \"NA\"), value: n[key]}]}]), "
        )
        if qnodes else
        "nodes: [], "
    )
    aggregate_clause += (
        (
            "edges: apoc.map.fromLists(" + (
            "[e IN collect(DISTINCT kedge) | toString(ID(e)) ], " if kwargs.get("relationship_id", "property") == "internal" else
            "[e IN collect(DISTINCT kedge) | e.id], "
            ) +
            "[e IN collect(DISTINCT kedge) | {"
            "predicate: type(e), subject: startNode(e).id, object: endNode(e).id, "
            "attributes: [key in apoc.coll.subtract(keys(e), "
            + cypher_expression.dumps(RESERVED_EDGE_PROPS + EDGE_SOURCE_PROPS) +
            ") | {original_attribute_name: key, attribute_type_id: COALESCE("
            + cypher_expression.dumps(ATTRIBUTE_TYPES) +
            "[key], \"NA\"), value: e[key]}]," +
            "sources: [key IN " + cypher_expression.dumps(EDGE_SOURCE_PROPS) +" | "
            " {resource_id: e[key] , resource_role: key }]"
            "}])"
        )
        if kedges else
        "edges: []"
    )
    aggregate_clause += "} AS knowledge_graph"
    clauses.append(aggregate_clause)

    # return results and knowledge graph
    return_clause = "RETURN results, knowledge_graph"
    clauses.append(return_clause)
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
    qgraph = copy.deepcopy(qgraph)
    clauses = []
    query = transpile_compound(qgraph, **kwargs)
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

    return " ".join(clauses)
