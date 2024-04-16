import yaml
import json
import os
import orjson

from fastapi import Response
from fastapi.openapi.utils import get_openapi

from PLATER.services.util.graph_adapter import GraphInterface
from PLATER.services.config import config


def get_graph_interface():
    """Get graph interface."""
    return GraphInterface(
        host=config.get('NEO4J_HOST'),
        port=config.get('NEO4J_HTTP_PORT'),
        auth=(
            config.get('NEO4J_USERNAME'),
            config.get('NEO4J_PASSWORD')
        ),
        query_timeout=int(config.get('NEO4J_QUERY_TIMEOUT')),
        bl_version=config.get('BL_VERSION')
    )


def construct_open_api_schema(app, trapi_version, prefix="", plater_title='Plater API'):
    plater_version = os.environ.get('PLATER_VERSION', 'v1.6.1')
    server_url = os.environ.get('PUBLIC_URL', '')
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
        open_api_schema["info"]["x-translator"]["biolink-version"] = config.get("BL_VERSION", "2.1.0")
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
            if prefix and 'url' in cnf:
                cnf['url'] = cnf['url'] + prefix
                cnf['x-maturity'] = os.environ.get("MATURITY_VALUE", "maturity")
                cnf['x-location'] = os.environ.get("LOCATION_VALUE", "location")
                cnf['x-trapi'] = trapi_version
                cnf['x-translator'] = {}
                cnf['x-translator']['biolink-version'] = config.get("BL_VERSION", "2.1.0")
                cnf['x-translator']['test-data-location'] = server_url.strip('/') + "/sri_testing_data"
        open_api_schema["servers"] = servers_conf

    open_api_schema["info"]["x-trapi"] = x_trapi_extension
    if server_url:
        open_api_schema["info"]["x-trapi"]["test_data_location"] = {
            os.environ.get("MATURITY_VALUE", "maturity"): {
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
