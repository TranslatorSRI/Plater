"""FastAPI app."""
import logging, warnings, os, json

from fastapi import  FastAPI
from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.app_common import APP_COMMON
from PLATER.services.app_trapi_1_4 import APP_TRAPI_1_4
from PLATER.services.util.api_utils import construct_open_api_schema

TITLE = config.get('PLATER_TITLE', 'Plater API')

VERSION = os.environ.get('PLATER_VERSION', '1.4.0-2')


logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

APP = FastAPI()

# Mount 1.4 app at /1.4
APP.mount('/1.4', APP_TRAPI_1_4, 'Trapi 1.4')
# Mount default app at /
APP.mount('/', APP_COMMON, '')
# Add all routes of each app for open api generation at /openapi.json
# This will create an aggregate openapi spec.
APP.include_router(APP_TRAPI_1_4.router, prefix='/1.4')
APP.include_router(APP_COMMON.router)
# Construct app /openapi.json # Note this is not to be registered on smart api . Instead /1.1/openapi.json
# or /1.2/openapi.json should be used.
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='N/A')

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.environ.get("OTEL_ENABLED"):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    # from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    # httpx connections need to be open a little longer by the otel decorators
    # but some libs display warnings of resource being unclosed.
    # these supresses such warnings.
    logging.captureWarnings(capture=True)
    warnings.filterwarnings("ignore", category=ResourceWarning)
    plater_service_name = os.environ.get('PLATER_TITLE', 'PLATER')
    assert plater_service_name and isinstance(plater_service_name, str)

    jaeger_exporter = JaegerExporter(
        agent_host_name=os.environ.get("JAEGER_HOST", "localhost"),
        agent_port=int(os.environ.get("JAEGER_PORT", "6831")),
    )

    resource = Resource(attributes={
        SERVICE_NAME: plater_service_name
    })
    provider = TracerProvider(resource=resource)
    # processor = BatchSpanProcessor(ConsoleSpanExporter())
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(APP, tracer_provider=provider, excluded_urls=
                                       "docs,openapi.json")

    async def request_hook(span, request):
        # logs cypher queries set to neo4j
        # check url
        if span.attributes.get('http.url').endswith('/db/data/transaction/commit'):
            # if url matches try to json load the query
            try:
                neo4j_query = json.loads(
                    request.stream._stream.decode('utf-8')
                )['statements'][0]['statement']
                span.set_attribute('cypher', neo4j_query)
            except Exception as ex:
                logger.error(f"error logging neo4j query when sending to OTEL: {ex}")
    HTTPXClientInstrumentor().instrument(request_hook=request_hook)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
