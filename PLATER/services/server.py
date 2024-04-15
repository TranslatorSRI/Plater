"""FastAPI app."""
import os

from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.app_trapi import APP_COMMON  # yes, this is right, read the comment below
from PLATER.services.util.api_utils import construct_open_api_schema

TITLE = config.get('PLATER_TITLE', 'Plater API')

VERSION = os.environ.get('PLATER_VERSION', 'v1.6.1')

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

# This is pretty gross but in order to preserve the history of the codebase, until we verify combining the routes is ok,
# we are using the same FastAPI() object which is created in app_common.py and then added to in app_trapi.py.
# Previously, we created a new FastAPI here and mounted both of the others to it, but that's not needed now.
APP = APP_COMMON

# Construct app /openapi.json
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='1.5')

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.environ.get("OTEL_ENABLED", "False") not in ("false", "False"):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    OTEL_USE_CONSOLE_EXPORTER = os.environ.get("OTEL_USE_CONSOLE_EXPORTER", "False") not in ("false", "False")
    if OTEL_USE_CONSOLE_EXPORTER:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    else:
        # from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

    plater_service_name = os.environ.get('PLATER_TITLE', 'PLATER')
    assert plater_service_name and isinstance(plater_service_name, str)
    resource = Resource(attributes={
        SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", plater_service_name),
    })
    provider = TracerProvider(resource=resource)
    if OTEL_USE_CONSOLE_EXPORTER:
        processor = BatchSpanProcessor(ConsoleSpanExporter())
    else:
        # otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost").rstrip('/')
        # otlp_exporter = OTLPSpanExporter(endpoint=f'{otlp_endpoint}/v1/traces')
        # processor = BatchSpanProcessor(otlp_exporter)
        jaeger_exporter = JaegerExporter(
            agent_host_name=os.environ.get("JAEGER_HOST", "localhost"),
            agent_port=int(os.environ.get("JAEGER_PORT", "6831")),
        )
        processor = BatchSpanProcessor(jaeger_exporter)

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(APP, tracer_provider=provider, excluded_urls=
                                       "docs,openapi.json")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
