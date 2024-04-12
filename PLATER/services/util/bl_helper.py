import asyncio
from functools import reduce
import httpx
from PLATER.services.config import config
from bmt import Toolkit

BIOLINK_MODEL_VERSION = config.get("BL_VERSION", None) or "4.1.6"
BIOLINK_MODEL_SCHEMA_URL = f"https://raw.githubusercontent.com/biolink/biolink-model/v{BIOLINK_MODEL_VERSION}/biolink-model.yaml"
PREDICATE_MAP_URL = f"https://raw.githubusercontent.com/biolink/biolink-model/v{BIOLINK_MODEL_VERSION}/predicate_mapping.yaml"

BIOLINK_MODEL_TOOLKIT = Toolkit(schema=BIOLINK_MODEL_SCHEMA_URL, predicate_map=PREDICATE_MAP_URL)


def get_biolink_model_toolkit():
    return BIOLINK_MODEL_TOOLKIT


# TODO - the following should be replaced with biolink model toolkit functions, no need to call bl-lookup
class BLHelper:
    def __init__(self, bl_url=config.get('bl_url')):
        self.bl_url = bl_url

    @staticmethod
    async def make_request(url):
        async with httpx.AsyncClient() as session:
            response = await session.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                return None

    async def get_most_specific_concept(self, concept_list: list) -> list:
        """
        Given a list of concepts find the most specific set of concepts.
        """
        tasks = []
        for concept in concept_list:
            parent_url = f"{self.bl_url}/bl/{concept}/ancestors"
            tasks.append(BLHelper.make_request(parent_url))
        response = await asyncio.gather(*tasks, return_exceptions=False)
        parents = list(reduce(lambda acc, value: acc + value, filter(lambda x: x, response), []))
        return list(filter(lambda x: x not in parents, concept_list))
