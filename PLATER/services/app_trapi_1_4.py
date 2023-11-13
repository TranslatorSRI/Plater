"""FastAPI app."""
from fastapi import Body, Depends, FastAPI, Response, status
from fastapi.responses import JSONResponse
from reasoner_transpiler.exceptions import InvalidPredicateError
from PLATER.models.models_trapi_1_1 import (MetaKnowledgeGraph, Message, ReasonerRequest)
from PLATER.models.shared import SRITestData

from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.metadata import GraphMetadata
from PLATER.services.util.question import Question
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.api_utils import get_graph_interface, get_graph_metadata, construct_open_api_schema, get_example

# Mount open api at /1.4/openapi.json
APP_TRAPI_1_4 = FastAPI(openapi_url="/openapi.json", docs_url="/docs", root_path='/1.4')


async def get_meta_knowledge_graph(
        graph_metadata: GraphMetadata = Depends(get_graph_metadata),
) -> JSONResponse:
    """Handle /meta_knowledge_graph."""
    # NOTE - we are intentionally returning a JSONResponse directly and skipping pydantic validation for speed
    meta_kg = await graph_metadata.get_meta_kg()
    return JSONResponse(content=meta_kg, media_type="application/json")


async def get_meta_knowledge_graph_pydantic(
        graph_metadata: GraphMetadata = Depends(get_graph_metadata),
):
    """Handle /meta_knowledge_graph."""
    meta_kg = await graph_metadata.get_meta_kg()
    return meta_kg


async def get_sri_testing_data(
        graph_metadata: GraphMetadata = Depends(get_graph_metadata),
):
    """Handle /sri_testing_data."""
    sri_test_data = await graph_metadata.get_sri_testing_data()
    return sri_test_data


async def reasoner_api(
        response: Response,
        request: ReasonerRequest = Body(
            ...,
            # Works for now but in deployment would be replaced by a mount, specific to backend dataset
            example=get_example("reasoner-trapi-1.3"),
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
            response.status_code = status.HTTP_400_BAD_REQUEST
            request_json["description"] = str(e)
            return request_json
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
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns meta knowledge graph representation of this TRAPI web service.",
    tags=["trapi"]
)

APP_TRAPI_1_4.add_api_route(
    "/meta_knowledge_graph_pydantic",
    get_meta_knowledge_graph_pydantic,
    methods=["GET"],
    response_model=MetaKnowledgeGraph,
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
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_4.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_4, trapi_version="1.4.0", prefix='/1.4')
