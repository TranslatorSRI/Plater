#!/usr/bin/env bash

# set environment variables from .env
set -a
source .env
set +a

if [ "$MODE" == "deploy" ]; then
    gunicorn PLATER.services.app:APP -b 0.0.0.0:2304 -w 4 -k uvicorn.workers.UvicornWorker
else
    uvicorn PLATER.services.app:APP --host 0.0.0.0 --port 9747 --reload
fi
