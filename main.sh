#!/usr/bin/env bash

# set environment variables from .env
set -a
source .env
set +a

if [ "$MODE" == "deploy" ]; then
    gunicorn PLATER.services.server:APP -b ${WEB_HOST}:${WEB_PORT} -w 4 -k uvicorn.workers.UvicornWorker
else
    uvicorn PLATER.services.server:APP --host ${WEB_HOST} --port ${WEB_PORT} --reload
fi

