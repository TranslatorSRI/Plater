import asyncio
from functools import reduce
import httpx
from PLATER.services.config import config


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
