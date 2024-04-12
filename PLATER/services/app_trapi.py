"""FastAPI app."""
from fastapi import Body, Depends, FastAPI, Response, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse
from typing import Dict
from pydantic import ValidationError


import orjson

from reasoner_transpiler.exceptions import InvalidPredicateError, InvalidQualifierError, InvalidQualifierValueError, UnsupportedError
from PLATER.models.shared import ReasonerRequest, MetaKnowledgeGraph, SRITestData
from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.util.metadata import GraphMetadata
from PLATER.services.util.question import Question
from PLATER.services.util.overlay import Overlay
from PLATER.services.util.api_utils import get_graph_interface, construct_open_api_schema
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


async def get_meta_knowledge_graph() -> ORJSONResponse:
    """Handle /meta_knowledge_graph."""
    if META_KG_RESPONSE:
        # we are intentionally returning a ORJSONResponse directly,
        # we already validated with pydantic above and the content won't change
        return ORJSONResponse(status_code=200,
                              content=META_KG_RESPONSE,
                              media_type="application/json")
    else:
        return ORJSONResponse(status_code=500,
                              media_type="application/json",
                              content={"description": "MetaKnowledgeGraph failed validation - "
                                                      "please notify maintainers."})


async def get_sri_testing_data():
    """Handle /sri_testing_data."""
    return SRI_TEST_DATA


def orjson_default(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError


class CustomORJSONResponse(Response):
    def render(self, content: dict) -> bytes:
        return orjson.dumps(content,
                            default=orjson_default)


async def reasoner_api(
        response: Response,
        request: ReasonerRequest = Body(
            ...,
            example=TRAPI_QUERY_EXAMPLE,
        ),
        profile: bool = False,
        validate: bool = False,
        graph_interface: GraphInterface = Depends(get_graph_interface),
) -> CustomORJSONResponse:

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
            return CustomORJSONResponse(status_code=400, content={"description": str(e)}, media_type="application/json")
        except InvalidQualifierError as e:
            return CustomORJSONResponse(status_code=400, content={"description": str(e)}, media_type="application/json")
        except InvalidQualifierValueError as e:
            return CustomORJSONResponse(status_code=400, content={"description": str(e)}, media_type="application/json")
        except UnsupportedError as e:
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
            ReasonerRequest.parse_obj(request_json)
        except ValidationError as e:
            json_response = CustomORJSONResponse(content={"description": f"Validation Errors Occurred: {e.errors()}"},
                                                 media_type="application/json",
                                                 status_code=500)
            return json_response

    # we are intentionally returning a CustomORJSONResponse and not a pydantic model for performance reasons
    json_response = CustomORJSONResponse(content=request_json, media_type="application/json")
    return json_response


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
    response_model=None,
    responses={400: {"model": Dict}, 200: {"model": ReasonerRequest}},
    summary="Query reasoner via one of several inputs.",
    description="",
    tags=["trapi"]
)

APP_TRAPI_1_4.openapi_schema = construct_open_api_schema(app=APP_TRAPI_1_4, trapi_version="1.4.0", prefix='/1.4')

# env var PROFILE_EVERYTHING=true could be used to turn on profiling / speedscope results for all http endpoints
if config.get('PROFILER_ON', False) and (config.get('PROFILER_ON') not in ("false", "False")):
    from pyinstrument import Profiler
    from pyinstrument.renderers import SpeedscopeRenderer
    from fastapi.responses import HTMLResponse

    @APP_TRAPI_1_4.middleware("http")
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
