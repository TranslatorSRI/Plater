"""FastAPI app."""
from fastapi import Body, Depends, FastAPI, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from typing import Dict
from pydantic import ValidationError

from reasoner_transpiler.exceptions import InvalidPredicateError
from PLATER.models.shared import ReasonerRequest, MetaKnowledgeGraph, SRITestData
from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.metadata import GraphMetadata
from PLATER.services.util.question import Question
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.api_utils import get_graph_interface, construct_open_api_schema, get_example
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

# Mount open api at /1.4/openapi.json
APP_TRAPI_1_4 = FastAPI(openapi_url="/openapi.json", docs_url="/docs", root_path='/1.4')


def get_meta_kg_response(graph_metadata_reader: GraphMetadata):
    meta_kg_json = graph_metadata_reader.get_meta_kg()
    try:
        MetaKnowledgeGraph.parse_obj(meta_kg_json)
        logger.info('Successfully validated meta kg')
        return jsonable_encoder(meta_kg_json)
    except ValidationError as e:
        logger.error(f'Error validating meta kg: {e}')
        return None


graph_metadata_reader = GraphMetadata()
META_KG_RESPONSE = get_meta_kg_response(graph_metadata_reader)
SRI_TEST_DATA = graph_metadata_reader.get_sri_testing_data()
TRAPI_QUERY_EXAMPLE = graph_metadata_reader.get_example_qgraph()


async def get_meta_knowledge_graph() -> JSONResponse:
    """Handle /meta_knowledge_graph."""
    if META_KG_RESPONSE:
        # we are intentionally returning a JSONResponse directly,
        # we already validated with pydantic above and the content won't change
        return JSONResponse(status_code=200,
                            content=META_KG_RESPONSE,
                            media_type="application/json")
    else:
        return JSONResponse(status_code=500,
                            media_type="application/json",
                            content={"description": "MetaKnowledgeGraph failed validation - "
                                                    "please notify maintainers."})


async def get_sri_testing_data():
    """Handle /sri_testing_data."""
    return SRI_TEST_DATA


async def reasoner_api(
        response: Response,
        request: ReasonerRequest = Body(
            ...,
            example=TRAPI_QUERY_EXAMPLE,
        ),
        graph_interface: GraphInterface = Depends(get_graph_interface),
):
    """Handle TRAPI request."""
    request_json = request.dict(by_alias=True)
    # default workflow
    workflow = request_json.get('workflow') or [{"id": "lookup"}]
    workflows = {wkfl['id']: wkfl for wkfl in workflow}
    if 'lookup' in workflows:
        question = Question(request_json["message"])
        try:
            response_message = await question.answer(graph_interface)
            request_json.update({'message': response_message, 'workflow': workflow})
        except InvalidPredicateError as e:
            return JSONResponse(status_code=400, content={"description": str(e)})
    elif 'overlay_connect_knodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response_message = await overlay.connect_k_nodes(request_json['message'])
        request_json.update({'message': response_message, 'workflow': workflow})
    elif 'annotate_nodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response_message = await overlay.annotate_node(request_json['message'])
        request_json.update({'message': response_message, 'workflow': workflow})
    return request_json


APP_TRAPI_1_4.add_api_route(
    "/meta_knowledge_graph",
    get_meta_knowledge_graph,
    methods=["GET"],
    response_model=None,
    responses={200: {"model": MetaKnowledgeGraph}},
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns meta knowledge graph representation of this TRAPI web service.",
    tags=["trapi"]
)

APP_TRAPI_1_4.add_api_route(
    "/sri_testing_data",
    get_sri_testing_data,
    methods=["GET"],
    response_model=SRITestData,
    response_model_exclude_none=True,
    summary="Test data for usage by the SRI Testing Harness.",
    description="Returns a list of edges that are representative examples of the knowledge graph.",
    tags=["trapi"]
)

APP_TRAPI_1_4.add_api_route(
    "/query",
    reasoner_api,
    methods=["POST"],
    response_model=ReasonerRequest,
    responses={400: {"model": Dict}},
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_4.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_4, trapi_version="1.4.0", prefix='/1.4')
