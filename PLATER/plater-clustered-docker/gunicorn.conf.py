# gunicorn.conf.py
import os

def post_fork(server, worker):
    """
    Called in each worker after forking from master.
    Initialize OpenTelemetry here so BatchSpanProcessor background thread
    and gRPC channel are created in the correct worker process context.
    Refer to https://oneuptime.com/blog/post/2026-02-06-troubleshoot-fastapi-uvicorn-reload/view
    """
    from PLATER.services.config import config

    if config.get("OTEL_ENABLED", "False") not in ("false", "False"):

        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        PLATER_TITLE = config.get('PLATER_TITLE', 'Plater API')
        resource = Resource.create(attributes={
            SERVICE_NAME: config.get("OTEL_SERVICE_NAME", PLATER_TITLE),
            "worker.pid": worker.pid,
        })
        provider = TracerProvider(resource=resource)

        OTEL_USE_CONSOLE_EXPORTER = config.get(
            "OTEL_USE_CONSOLE_EXPORTER", "False"
        ) not in ("false", "False")

        if OTEL_USE_CONSOLE_EXPORTER:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            processor = BatchSpanProcessor(ConsoleSpanExporter())
        else:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_host = config.get("JAEGER_HOST", "http://localhost").rstrip('/')
            otlp_port = config.get("JAEGER_PORT", "4317")
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=f'{otlp_host}:{otlp_port}'))

        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        from PLATER.services.app_trapi import APP
        FastAPIInstrumentor.instrument_app(APP, excluded_urls="docs,openapi.json")
