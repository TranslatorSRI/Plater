"""FastAPI app."""
from typing import Any, Dict, List

from fastapi import Body, Depends, FastAPI
from fastapi.responses import RedirectResponse

from PLATER.models.models_trapi_1_0 import (
    Message, ReasonerRequest, CypherRequest, SimpleSpecResponse, SimpleSpecElement,
    GraphSummaryResponse, CypherResponse, PredicatesResponse
)
from PLATER.services.util.bl_helper import BLHelper
from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.metadata import GraphMetadata
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.api_utils import get_graph_interface, \
    get_bl_helper, get_example

APP_COMMON = FastAPI(openapi_url='/openapi.json', docs_url='/docs')

GRAPH_METADATA = GraphMetadata().get_metadata()


async def cypher(
        request: CypherRequest = Body(
            ...,
            example={"query": "MATCH (n) RETURN count(n)"},
        ),
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> CypherResponse:
    """Handle cypher."""
    request = request.dict()
    results = await graph_interface.run_cypher(
        request["query"],
        return_errors=True,
    )
    return results


APP_COMMON.add_api_route(
    "/cypher",
    cypher,
    methods=["POST"],
    response_model=CypherResponse,
    summary="Run cypher query",
    description=(
        "Runs cypher query against the Neo4j instance, and returns an "
        "equivalent response expected from a Neo4j HTTP endpoint "
        "(https://neo4j.com/docs/rest-docs/current/)."
    ),
)


async def overlay(
        request: ReasonerRequest = Body(
            ...,
            example={"message": get_example("overlay")},
        ),
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> Message:
    """Handle TRAPI request."""
    overlay_class = Overlay(graph_interface)
    return await overlay_class.overlay_support_edges(request.dict()["message"])


APP_COMMON.add_api_route(
    "/overlay",
    overlay,
    methods=["POST"],
    response_model=Message,
    description=(
        "Given a ReasonerAPI graph, add support edges for any nodes linked in "
        "result bindings."
    ),
    summary="Overlay results with available connections between each node.",
    tags=["translator"]
)


async def metadata() -> Any:
    """Handle /metadata."""
    return GRAPH_METADATA


APP_COMMON.add_api_route(
    "/metadata",
    metadata,
    methods=["GET"],
    response_model=Any,
    summary="Metadata about the knowledge graph.",
    description="Returns JSON with metadata about the data sources in this knowledge graph.",
)


async def one_hop(
        source_type: str,
        target_type: str,
        curie: str,
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> List[Dict]:
    """Handle one-hop."""
    return await graph_interface.get_single_hops(
        source_type,
        target_type,
        curie,
    )


APP_COMMON.add_api_route(
    "/{source_type}/{target_type}/{curie}",
    one_hop,
    methods=["GET"],
    response_model=List,
    summary=(
        "Get one hop results from source type to target type. "
        "Note: Please GET /predicates to determine what target goes "
        "with a source"
    ),
    description=(
        "Returns one hop paths from `source_node_type`  with `curie` "
        "to `target_node_type`."
    ),
)


async def node(
        node_type: str,
        curie: str,
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> List[List[Dict]]:
    """Handle node lookup."""
    return await graph_interface.get_node(
        node_type,
        curie,
    )


APP_COMMON.add_api_route(
    "/{node_type}/{curie}",
    node,
    methods=["GET"],
    response_model=List,
    summary="Find `node` by `curie`",
    description="Returns `node` matching `curie`.",
)


async def simple_spec(
        source: str = None,
        target: str = None,
        graph_interface: GraphInterface = Depends(get_graph_interface),
        bl_helper: BLHelper = Depends(get_bl_helper),
) -> SimpleSpecResponse:
    """Handle simple spec."""
    source_id = source
    target_id = target
    if source_id or target_id:
        minischema = []
        mini_schema_raw = await graph_interface.get_mini_schema(
            source_id,
            target_id,
        )
        for row in mini_schema_raw:
            source_labels = await bl_helper.get_most_specific_concept(
                row['source_label']
            )
            target_labels = await bl_helper.get_most_specific_concept(
                row['target_label']
            )
            for source_type in source_labels:
                for target_type in target_labels:
                    minischema.append((
                        source_type,
                        row['predicate'],
                        target_type,
                    ))
        minischema = list(set(minischema))  # remove dups
        return list(map(lambda x: SimpleSpecElement(**{
                'source_type': x[0],
                'target_type': x[2],
                'edge_type': x[1],
            }), minischema))
    else:
        schema = graph_interface.get_schema()
        reformatted_schema = []
        for source_type in schema:
            for target_type in schema[source_type]:
                for edge in schema[source_type][target_type]:
                    reformatted_schema.append(SimpleSpecElement(**{
                        'source_type': source_type,
                        'target_type': target_type,
                        'edge_type': edge
                    }))
        return reformatted_schema


APP_COMMON.add_api_route(
    "/simple_spec",
    simple_spec,
    methods=["GET"],
    response_model=SimpleSpecResponse,
    summary="Get one-hop connection schema",
    description=(
        "Returns a list of available predicates when choosing a single source "
        "or target curie. Calling this endpoint with no query parameters will "
        "return all possible hops for all types."
    ),
)


async def redirect_to_docs():
    return RedirectResponse(url="/docs")

APP_COMMON.add_api_route(
    "/",
    redirect_to_docs,
    include_in_schema=False,
    methods=["GET"]
)
