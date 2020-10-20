#!/bin/bash

# set environment variables from .env
set -a
source .env
set +a

function webServer {
    echo "Starting web server ... "
    if [ "$MODE" == "deploy" ]; then
        gunicorn PLATER.services.app:APP -b ${WEB_HOST}:${WEB_PORT} -w 4 -k uvicorn.workers.UvicornWorker
    else
        uvicorn PLATER.services.app:APP --host ${WEB_HOST} --port ${WEB_PORT} --reload
    fi
}

function heartbeat {
    if [[ ! -z "${AUTOMAT_HOST}" ]]; then
        testEndpoint=${PLATER_SERVICE_ADDRESS}:${WEB_PORT}/predicates
        response=$(curl --write-out %{http_code} --silent --output /dev/null ${testEndpoint})
        until [ $response = "200" ]; do
            response=$(curl --write-out %{http_code} --silent --output /dev/null ${testEndpoint})
            sleep 1
        done
        python PLATER/services/heartbeat.py -a ${AUTOMAT_HOST}
    fi
    $*
}

# Run the web server in the background
webServer &
webServerPID=$!
# Run heartbeat sender in background, only runs if AUTOMAT_SERVER env is provided
heartbeat &
heartbeatPID=$!
# add wait so killing this script would kill the bg processes.
wait $webServerPID $heartbeatPID