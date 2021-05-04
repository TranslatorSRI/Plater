"""FastAPI app."""

from fastapi import Depends, FastAPI
from PLATER.models.models_trapi_1_1 import (MetaKnowledgeGraph, Response, Query)

from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.question import Question
from PLATER.services.util.api_utils import get_graph_interface, construct_open_api_schema


APP_TRAPI_1_1 = FastAPI(openapi_url="/1.1/openapi.json" ,docs_url="/1.1/docs")


async def get_meta_knowledge_graph(
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> MetaKnowledgeGraph:
    """Handle /meta_knowledge_graph."""
    response = await graph_interface.get_meta_kg()
    return response


async def reasoner_api(
        request: Query,
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> Response:
    """Handle TRAPI request."""
    request_json = request.dict()
    question = Question(request_json["message"], trapi_version='1.1')
    response = await question.answer(graph_interface)
    request_json.update({'message': response})
    return request_json


APP_TRAPI_1_1.add_api_route(
    "/1.1/meta_knowledge_graph",
    get_meta_knowledge_graph,
    methods=["GET"],
    response_model=MetaKnowledgeGraph,
    summary="Meta knowledge graph representation of this TRAPI web service.",
    description="Returns meta knowledge graph representation of this TRAPI web service.",
    tags=["trapi"]
)

APP_TRAPI_1_1.add_api_route(
    "/1.1/query",
    reasoner_api,
    methods=["POST"],
    response_model=Response,
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_1.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_1, trapi_version="1.1")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP_TRAPI_1_1, host='0.0.0.0', port=8080)

