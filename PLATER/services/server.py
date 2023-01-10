"""FastAPI app."""
import os

from fastapi import  FastAPI
from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.app_common import APP_COMMON
from PLATER.services.app_trapi_1_3 import APP_TRAPI_1_3
from PLATER.services.util.api_utils import construct_open_api_schema

TITLE = config.get('PLATER_TITLE', 'Plater API')

VERSION = os.environ.get('PLATER_VERSION', '1.3.0-9')


logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

APP = FastAPI()

# Mount 1.2 app at /1.2
APP.mount('/1.3', APP_TRAPI_1_3, 'Trapi 1.3')
# Mount default app at /
APP.mount('/', APP_COMMON, '')
# Add all routes of each app for open api generation at /openapi.json
# This will create an aggregate openapi spec.
APP.include_router(APP_TRAPI_1_3.router, prefix='/1.3')
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

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
