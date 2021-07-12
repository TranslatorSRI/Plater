"""FastAPI app."""
import os

from fastapi import  FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.app_trapi_1_0 import APP_TRAPI_1_0
from PLATER.services.app_trapi_1_1 import APP_TRAPI_1_1
from PLATER.services.util.api_utils import construct_open_api_schema

TITLE = config.get('PLATER_TITLE', 'Plater API')
VERSION = os.environ.get('PLATER_VERSION', '1.1.0')

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

APP = FastAPI()

# Mount 1.1 app at /1.1
APP.mount('/1.1',  APP_TRAPI_1_1, 'Trapi 1.1')
# Mount default  1.0 app at /
APP.mount('/', APP_TRAPI_1_0, 'Trapi 1.0')
# Add all routes of each app for open api generation at /openapi.json
# This will create an aggregate openapi spec.
APP.include_router(APP_TRAPI_1_1.router, prefix='/1.1')
APP.include_router(APP_TRAPI_1_0.router)
# Construct app /openapi.json
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='1.0')

# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
