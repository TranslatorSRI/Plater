# gunicorn.conf.py
# Thin shim: real OTEL setup lives in PLATER/services/otel.py.
# It must run in post_fork so OTEL background threads/channels are created
# in the worker process, not the master.


def post_fork(server, worker):
    from PLATER.services.otel import setup_otel
    setup_otel(worker_pid=worker.pid)