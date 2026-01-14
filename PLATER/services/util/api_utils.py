import yaml
import json
import os
import orjson

from fastapi import Response
from fastapi.openapi.utils import get_openapi

from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.util.graph_backends.base import GraphInterface
from PLATER.services.util.graph_backends.neo4j_adapter import Neo4jBackend
from PLATER.services.util.graph_backends.memgraph_adapter import MemgraphBackend
from PLATER.services.config import config

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format'))

async def get_graph_interface():
    """Get graph interface."""
    graph_db = config.get('GRAPH_DB', 'neo4j')
    if graph_db == 'memgraph':
        mg_username = config.get('MEMGRAPH_USERNAME', None)
        mg_password = config.get('MEMGRAPH_PASSWORD', None)
        if mg_username and mg_password:
            auth = (mg_username, mg_password)
        else:
            auth = None
        graph_backend = MemgraphBackend(
            host=config.get('MEMGRAPH_HOST', 'localhost'),
            port=config.get('MEMGRAPH_BOLT_PORT', '7687'),
            auth=auth)
    else:
        graph_backend = Neo4jBackend(
            host=config.get('NEO4J_HOST', 'localhost'),
            port=config.get('NEO4J_BOLT_PORT', '7687'),
            auth=(
                config.get('NEO4J_USERNAME'),
                config.get('NEO4J_PASSWORD')
            ))
    graph_interface = GraphInterface(graph_backend)

    await graph_interface.connect()
    return graph_interface


def construct_open_api_schema(app, trapi_version, prefix="", plater_title='Plater API'):
    plater_version = config.get('PLATER_VERSION', 'v2.1.4')
    server_url = config.get('PUBLIC_URL', '')
    if app.openapi_schema:
        return app.openapi_schema
    open_api_schema = get_openapi(
        title=plater_title,
        version=plater_version,
        description='',
        routes=app.routes,
    )
    open_api_extended_file_path = config.get_resource_path(f'../openapi-config.yaml')
    with open(open_api_extended_file_path) as open_api_file:
        open_api_extended_spec = yaml.load(open_api_file, Loader=yaml.SafeLoader)

    x_translator_extension = open_api_extended_spec.get("x-translator")
    contact_config = open_api_extended_spec.get("contact")
    terms_of_service = open_api_extended_spec.get("termsOfService")
    servers_conf = open_api_extended_spec.get("servers")
    tags = open_api_extended_spec.get("tags")
    title_override = (open_api_extended_spec.get("title") or plater_title)
    description = open_api_extended_spec.get("description")
    x_trapi_extension = open_api_extended_spec.get("x-trapi", {"version": trapi_version, "operations": ["lookup"]})
    if tags:
        open_api_schema['tags'] = tags

    if x_translator_extension:
        # if x_translator_team is defined amends schema with x_translator extension
        open_api_schema["info"]["x-translator"] = x_translator_extension
        open_api_schema["info"]["x-translator"]["biolink-version"] = config.get("BL_VERSION", "4.1.6")
        open_api_schema["info"]["x-translator"]["infores"] = config.get('PROVENANCE_TAG', 'infores:automat.notspecified')

    if contact_config:
        open_api_schema["info"]["contact"] = contact_config

    if terms_of_service:
        open_api_schema["info"]["termsOfService"] = terms_of_service

    if description:
        open_api_schema["info"]["description"] = description

    if title_override:
        open_api_schema["info"]["title"] = title_override

    if servers_conf:
        for cnf in servers_conf:
            if 'url' in cnf:
                cnf['url'] = cnf['url'] + prefix
                cnf['x-maturity'] = config.get("MATURITY_VALUE", "maturity")
                cnf['x-location'] = config.get("LOCATION_VALUE", "location")
                cnf['x-trapi'] = trapi_version
                cnf['x-translator'] = {}
                cnf['x-translator']['biolink-version'] = config.get("BL_VERSION", "4.1.6")
                cnf['x-translator']['test-data-location'] = server_url.strip('/') + "/sri_testing_data"
        open_api_schema["servers"] = servers_conf

    open_api_schema["info"]["x-trapi"] = x_trapi_extension
    if server_url:
        open_api_schema["info"]["x-trapi"]["test_data_location"] = {
            config.get("MATURITY_VALUE", "maturity"): {
                'url': server_url.strip('/') + "/sri_testing_data"
            }
        }
    return open_api_schema


# note: for the trapi /query endpoint an example is retrieved from the sri test data and now and not through this
def get_example(operation: str):
    """Get example for operation."""
    with open(os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "examples",
        f"{operation}.json",
    )) as stream:
        return json.load(stream)


def orjson_default(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError


class CustomORJSONResponse(Response):
    def render(self, content: dict) -> bytes:
        return orjson.dumps(content,
                            default=orjson_default)
