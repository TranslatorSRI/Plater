"""FastAPI app."""

from fastapi import Body, Depends, FastAPI
from PLATER.models.models_trapi_1_1 import (MetaKnowledgeGraph, Message, ReasonerRequest)
from PLATER.models.shared import SRITestData

from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.question import Question
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.api_utils import get_graph_interface, construct_open_api_schema, get_example

# Mount open api at /1.2/openapi.json
APP_TRAPI_1_3 = FastAPI(openapi_url="/openapi.json", docs_url="/docs", root_path='/1.3')


async def get_meta_knowledge_graph(
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> MetaKnowledgeGraph:
    """Handle /meta_knowledge_graph."""
    response = await graph_interface.get_meta_kg()
    return response


async def get_sri_testing_data(
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> SRITestData:
    """Handle /sri_testing_data."""
    response = await graph_interface.get_sri_testing_data()
    return response


async def reasoner_api(
        request: ReasonerRequest = Body(
            ...,
            # Works for now but in deployment would be replaced by a mount, specific to backend dataset
            example=get_example("reasoner-trapi-1.2"),
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
        response = await question.answer(graph_interface)
        request_json.update({'message': response, 'workflow': workflow})
    elif 'overlay_connect_knodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response = await overlay.connect_k_nodes(request_json['message'])
        request_json.update({'message': response, 'workflow': workflow})
    elif 'annotate_nodes' in workflows:
        overlay = Overlay(graph_interface=graph_interface)
        response = await overlay.annotate_node(request_json['message'])
        request_json.update({'message': response, 'workflow': workflow})
    return request_json


APP_TRAPI_1_3.add_api_route(
    "/meta_knowledge_graph",
    get_meta_knowledge_graph,
    methods=["GET"],
    response_model=MetaKnowledgeGraph,
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns meta knowledge graph representation of this TRAPI web service.",
    tags=["trapi"]
)

APP_TRAPI_1_3.add_api_route(
    "/sri_testing_data",
    get_sri_testing_data,
    methods=["GET"],
    response_model=SRITestData,
    response_model_exclude_none=True,
    summary="Test data for usage by the SRI Testing Harness.",
    description="Returns a list of edges that are representative examples of the knowledge graph.",
    tags=["trapi"]
)

APP_TRAPI_1_3.add_api_route(
    "/query",
    reasoner_api,
    methods=["POST"],
    response_model=ReasonerRequest,
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_3.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_3, trapi_version="1.3.0", prefix='/1.3')
