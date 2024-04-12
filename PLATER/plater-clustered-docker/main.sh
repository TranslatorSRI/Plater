#!/usr/bin/env bash
# set environment variables from .env
set -a
source .env
set +a

# Configure these for large graphs.
# When using gunicorn worker will time-out for long running operations.
NUM_WORKERS=${NUM_WORKERS:-4}
WORKER_TIMEOUT=${WORKER_TIMEOUT:-600}


function webServer {
    echo "Starting web server ... "
    if [ "$MODE" == "deploy" ]; then
        gunicorn PLATER.services.server:APP -b \
        ${WEB_HOST}:${WEB_PORT} \
        --workers ${NUM_WORKERS} \
        --timeout ${WORKER_TIMEOUT} \
        -k uvicorn.workers.UvicornWorker
    else
        uvicorn PLATER.services.server:APP --host ${WEB_HOST} --port ${WEB_PORT} --reload
    fi
}
function heartbeat {
    echo "starting heartbeat logic... "
    if [[ ! -z "${AUTOMAT_HOST}" ]]; then
        echo "Checking Plater status..."
        testEndpoint=${PLATER_SERVICE_ADDRESS}:${WEB_PORT}/meta_knowledge_graph
        response=$(curl --write-out %{http_code} --silent --output /dev/null ${testEndpoint})
        until [ $response = "200" ]; do
            response=$(curl --write-out %{http_code} --silent --output /dev/null ${testEndpoint})
            echo "Plater not ready sleeping... "
            sleep 1
        done
        echo "Plater ready starting heartbeat ..."
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