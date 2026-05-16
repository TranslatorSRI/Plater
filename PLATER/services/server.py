"""FastAPI app."""
from starlette.middleware.cors import CORSMiddleware
from PLATER.services.config import config
from PLATER.services.app_trapi import APP
from PLATER.services.util.api_utils import construct_open_api_schema
from PLATER.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)

PLATER_TITLE = config.get('PLATER_TITLE', 'Plater API')
logger.info(f"*** in server.py before setting openapi_schema, lifespan_context: {APP.router.lifespan_context} ***")
# Construct app /openapi.json
APP.openapi_schema = construct_open_api_schema(app=APP, trapi_version='1.5', plater_title=PLATER_TITLE)
logger.info(f"*** in server.py before calling add_middleware(), lifespan_context: {APP.router.lifespan_context} ***")
# CORS
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"*** in server.py after calling add_middleware(), lifespan_context: {APP.router.lifespan_context} ***")
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
