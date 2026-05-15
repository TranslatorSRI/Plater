"""FastAPI app."""
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.app_trapi import APP
from PLATER.services.util.api_utils import construct_open_api_schema

PLATER_TITLE = config.get('PLATER_TITLE', 'Plater API')

# Construct app /openapi.json
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='1.5', plater_title=PLATER_TITLE)

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _init_tracing():
    """
    Initialize OpenTelemetry tracing.

    Must be called inside each gunicorn worker AFTER fork to ensure
    BatchSpanProcessor background thread and gRPC channel are created
    in the correct worker process context.

    See: https://opentelemetry.io/docs/zero-code/python/troubleshooting/
    """
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    plater_service_name = PLATER_TITLE
    resource = Resource.create(attributes={
        SERVICE_NAME: config.get("OTEL_SERVICE_NAME", plater_service_name),
    })
    provider = TracerProvider(resource=resource)

    OTEL_USE_CONSOLE_EXPORTER = config.get("OTEL_USE_CONSOLE_EXPORTER", "False") not in ("false", "False")

    if OTEL_USE_CONSOLE_EXPORTER:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        processor = BatchSpanProcessor(ConsoleSpanExporter())
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_host = config.get("JAEGER_HOST", "http://localhost").rstrip('/')
        otlp_port = config.get("JAEGER_PORT", "4317")
        otlp_endpoint = f'{otlp_host}:{otlp_port}'
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(APP, tracer_provider=provider, excluded_urls="docs,openapi.json")

    return provider


@asynccontextmanager
async def lifespan(app):
    """
    FastAPI lifespan context manager.

    Code before yield runs on worker startup (post-fork) — safe for
    initializing BatchSpanProcessor and gRPC channels.
    Code after yield runs on worker shutdown — used to flush and
    shut down the tracer provider cleanly.

    See: https://fastapi.tiangolo.com/advanced/events/
    """
    provider = None
    if config.get("OTEL_ENABLED", "False") not in ("false", "False"):
        provider = _init_tracing()
    yield
    # Shutdown: flush remaining spans and clean up gRPC channel
    if provider:
        provider.shutdown()


# Attach lifespan to the existing APP
APP.router.lifespan_context = lifespan


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
