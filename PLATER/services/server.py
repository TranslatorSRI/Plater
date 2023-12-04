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

if os.environ.get("OTEL_ENABLED", False):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    OTEL_USE_CONSOLE_EXPORTER = os.environ.get("OTEL_USE_CONSOLE_EXPORTER", False)
    if OTEL_USE_CONSOLE_EXPORTER:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    plater_service_name = os.environ.get('PLATER_TITLE', 'PLATER')
    assert plater_service_name and isinstance(plater_service_name, str)
    resource = Resource(attributes={
        SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", plater_service_name),
    })
    provider = TracerProvider(resource=resource)
    if OTEL_USE_CONSOLE_EXPORTER:
        processor = BatchSpanProcessor(ConsoleSpanExporter())
    else:
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost").rstrip('/')
        otlp_exporter = OTLPSpanExporter(endpoint=f'{otlp_endpoint}/v1/traces')
        processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(APP, tracer_provider=provider, excluded_urls=
                                       "docs,openapi.json")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
