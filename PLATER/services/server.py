"""FastAPI app."""
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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(APP, host='0.0.0.0', port=8080)
