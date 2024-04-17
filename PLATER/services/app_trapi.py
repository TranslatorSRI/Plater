"""FastAPI app."""
from fastapi import Body, Depends, FastAPI, Response, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse, RedirectResponse
from typing import Any, Dict, List
from pydantic import ValidationError

from reasoner_transpiler.exceptions import (
    InvalidPredicateError, InvalidQualifierError, InvalidQualifierValueError, UnsupportedError
)
from PLATER.models.models_trapi_1_0 import (
    Message, ReasonerRequest, CypherRequest, SimpleSpecResponse, SimpleSpecElement, CypherResponse
)
from PLATER.models.shared import MetaKnowledgeGraph, SRITestData
from PLATER.services.util.api_utils import (
    get_graph_interface, get_example, CustomORJSONResponse
)
from PLATER.services.util.bl_helper import BLHelper, get_bl_helper
from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.metadata import GraphMetadata
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.question import Question
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil


APP = FastAPI(openapi_url='/openapi.json', docs_url='/docs')

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)


# read in and validate the meta kg json only once on startup,
# create an already-encoded object that is ready to be returned quickly
def get_meta_kg_response(graph_metadata_reader: GraphMetadata):
    meta_kg_json = graph_metadata_reader.get_meta_kg()
    try:
        MetaKnowledgeGraph.parse_obj(meta_kg_json)
        logger.info('Successfully validated meta kg')
        return jsonable_encoder(meta_kg_json)
    except ValidationError as e:
        logger.error(f'Error validating meta kg: {e}')
        return None


# process and store static objects ready to be returned by their respective endpoints
graph_metadata_reader = GraphMetadata()
GRAPH_METADATA = graph_metadata_reader.get_metadata()
META_KG_RESPONSE = get_meta_kg_response(graph_metadata_reader)
SRI_TEST_DATA = graph_metadata_reader.get_sri_testing_data()

# get an example query for the /query endpoint, to be included in the open api spec
TRAPI_QUERY_EXAMPLE = graph_metadata_reader.get_example_qgraph()


async def get_meta_knowledge_graph() -> ORJSONResponse:
    """Handle /meta_knowledge_graph."""
    if META_KG_RESPONSE:
        # we are intentionally returning a ORJSONResponse directly,
        # we already validated with pydantic above and the content won't change
        return ORJSONResponse(status_code=200,
                              content=META_KG_RESPONSE,
                              media_type="application/json")
    else:
        # if META_KG_RESPONSE is None it means the meta kg did not validate
        return ORJSONResponse(status_code=500,
                              media_type="application/json",
                              content={"description": "MetaKnowledgeGraph failed validation - "
                                                      "please notify maintainers."})

APP.add_api_route(
    "/meta_knowledge_graph",
    get_meta_knowledge_graph,
    methods=["GET"],
    response_model=None,
    responses={200: {"model": MetaKnowledgeGraph}},
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns a meta knowledge graph representation of this TRAPI web service. The meta knowledge graph is "
                "composed of the union of most specific categories and predicates for each node and edge.",
    tags=["trapi"]
)


async def get_sri_testing_data():
    """Handle /sri_testing_data."""
    return SRI_TEST_DATA

APP.add_api_route(
    "/sri_testing_data",
    get_sri_testing_data,
    methods=["GET"],
    response_model=SRITestData,
    response_model_exclude_none=True,
    summary="Test data for usage by the SRI Testing Harness.",
    description="Returns a list of edges that are representative examples of the knowledge graph.",
    tags=["trapi"]
)


async def reasoner_api(
        request: ReasonerRequest = Body(
            ...,
            example=TRAPI_QUERY_EXAMPLE,
        ),
        # it looks like the parameter profile is not used, but it is
        # it's here so that it's documented in the open api spec, and it's used by pyinstrument in profile_request
        profile: bool = False,
        validate: bool = False,
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> CustomORJSONResponse:

    """Handle /query TRAPI request."""
    request_json = request.dict(by_alias=True)
    # use lookup as the default workflow
    workflow = request_json.get('workflow') or [{"id": "lookup"}]
    workflows = {wkfl['id']: wkfl for wkfl in workflow}

    if 'lookup' in workflows:
        question = Question(request_json["message"])
        try:
            response_message = await question.answer(graph_interface)
            request_json.update({'message': response_message, 'workflow': workflow})
        except (InvalidPredicateError, InvalidQualifierError, InvalidQualifierValueError, UnsupportedError) as e:
            return CustomORJSONResponse(status_code=400, content={"description": str(e)}, media_type="application/json")
    elif 'overlay_connect_knodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response_message = await overlay.connect_k_nodes(request_json['message'])
        request_json.update({'message': response_message, 'workflow': workflow})
    elif 'annotate_nodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response_message = await overlay.annotate_node(request_json['message'])
        request_json.update({'message': response_message, 'workflow': workflow})

    if validate:
        try:
            # Attempt to parse the request_json using the pydantic model, if it fails it will throw a ValidationError.
            # Don't save the pydantic object created, we're returning a CustomORJSONResponse instead.
            ReasonerRequest.parse_obj(request_json)
        except ValidationError as e:
            json_response = CustomORJSONResponse(content={"description": f"Validation Errors Occurred: {e.errors()}"},
                                                 media_type="application/json",
                                                 status_code=500)
            return json_response

    # we are intentionally returning a CustomORJSONResponse and not a pydantic model for performance reasons
    json_response = CustomORJSONResponse(content=request_json, media_type="application/json")
    return json_response

APP.add_api_route(
    "/query",
    reasoner_api,
    methods=["POST"],
    response_model=None,
    responses={400: {"model": Dict}, 200: {"model": ReasonerRequest}},
    summary="Accepts TRAPI Queries.",
    description="Accepts a TRAPI Query and returns a TRAPI Response. (https://github.com/NCATSTranslator/ReasonerAPI/)",
    tags=["trapi"]
)


###########################################
# The following endpoints all come from the old app_common.py file, which was previously a different sub-application.
###########################################

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


APP.add_api_route(
    "/cypher",
    cypher,
    methods=["POST"],
    response_model=CypherResponse,
    summary="Run a Neo4j cypher query.",
    description=(
        "Runs a cypher query against the Neo4j instance, and returns an "
        "equivalent response expected from a Neo4j HTTP endpoint "
        "(https://neo4j.com/docs/rest-docs/current/)."
    ),
)


async def metadata() -> Any:
    """Handle /metadata."""
    return GRAPH_METADATA

APP.add_api_route(
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

APP.add_api_route(
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

APP.add_api_route(
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

APP.add_api_route(
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

APP.add_api_route(
    "/",
    redirect_to_docs,
    include_in_schema=False,
    methods=["GET"]
)

# config var PROFILER_ON=true can be used to turn on profiling for all http endpoints
# even with PROFILER_ON the query param "profile" is what makes an endpoint use profiling and return the results
if config.get('PROFILER_ON', False) and (config.get('PROFILER_ON') not in ("false", "False")):
    from pyinstrument import Profiler
    from pyinstrument.renderers import SpeedscopeRenderer
    from fastapi.responses import HTMLResponse

    @APP.middleware("http")
    async def profile_request(request: Request, call_next):
        profiling = request.query_params.get("profile", "false")
        if profiling and profiling != "false":
            profiler = Profiler(interval=.1, async_mode="enabled")
            profiler.start()
            await call_next(request)
            profiler.stop()
            return HTMLResponse(profiler.output(renderer=SpeedscopeRenderer()))
        else:
            return await call_next(request)
