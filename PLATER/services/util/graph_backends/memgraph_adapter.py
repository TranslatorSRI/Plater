import asyncio
import neo4j

from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.util.graph_backends.base import GraphBackend
from PLATER.services.util.graph_backends.graph_utils import convert_bolt_results_to_cypher_result
from reasoner_transpiler.cypher import transform_result

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format'))

MEMGRAPH_QUERY_TIMEOUT = int(config.get('GRAPH_QUERY_TIMEOUT', 1600))


class MemgraphBackend(GraphBackend):
    """
    Memgraph backend using the Neo4j Bolt driver. APOC is not supported.
    """
    supports_element_id = False

    def __init__(self, host: str, port: str, auth: tuple | None = None):
        self.database_auth = auth
        self.graph_db_uri = f'bolt://{host}:{port}'
        self.driver = None
        self._supports_apoc = False

    async def connect(self, retries=0):
        if not self.driver:
            kwargs = {
                "telemetry_disabled": True,
                "max_connection_pool_size": 1000
            }
            if self.database_auth:
                kwargs["auth"] = self.database_auth

            self.driver = neo4j.AsyncGraphDatabase.driver(self.graph_db_uri,
                                                          **kwargs)
        try:
            await self.driver.verify_connectivity()
        except Exception as e:
            await self.driver.close()
            if retries <= 25:
                await asyncio.sleep(8)
                logger.error(f'Could not establish connection to memgraph, trying again... retry {retries + 1}')
                await self.connect(retries + 1)
            else:
                logger.error(f'Could not establish connection to memgraph, error: {e}')
                raise e

    @staticmethod
    async def _async_cypher_tx_function(tx,
                                        cypher,
                                        query_parameters=None,
                                        convert_to_dict=False,
                                        convert_to_trapi=False,
                                        qgraph=None):
        if not query_parameters:
            query_parameters = {}

        result: neo4j.AsyncResult = await tx.run(cypher, parameters=query_parameters)

        if convert_to_trapi:
            record = await result.single()
            return transform_result(record, qgraph)

        if convert_to_dict:
            rows = []
            async for record in result:
                rows.append({k: v for k, v in record.items()})
            return rows

        return await convert_bolt_results_to_cypher_result(result)

    async def run(self,
                  query,
                  query_parameters=None,
                  return_errors=False,
                  convert_to_dict=False,
                  convert_to_trapi=False,
                  qgraph=None):
        try:
            async with self.driver.session(default_access_mode=neo4j.READ_ACCESS) as session:
                task = asyncio.create_task(
                    session.execute_read(
                        self._async_cypher_tx_function,
                        query,
                        query_parameters=query_parameters,
                        convert_to_dict=convert_to_dict,
                        convert_to_trapi=convert_to_trapi,
                        qgraph=qgraph
                    )
                )

                try:
                    return await asyncio.wait_for(task, timeout=MEMGRAPH_QUERY_TIMEOUT)
                except asyncio.TimeoutError:
                    task.cancel()
                    logger.error(
                        f"Memgraph query timed out after {MEMGRAPH_QUERY_TIMEOUT}s"
                    )
                    raise TimeoutError(
                        f"Memgraph query exceeded timeout of {MEMGRAPH_QUERY_TIMEOUT} seconds"
                    )
        except neo4j.exceptions.ServiceUnavailable as e:
            logger.error(f'Session could not establish connection to Memgraph ({e}).. trying to connect again')
            await self.connect()
            return await self.run(query,
                                  query_parameters=query_parameters,
                                  return_errors=return_errors,
                                  convert_to_dict=convert_to_dict,
                                  convert_to_trapi=convert_to_trapi,
                                  qgraph=qgraph)
        except neo4j.exceptions.Neo4jError as e:
            logger.error(e)
            if return_errors:
                return {
                    "results": [],
                    "errors": [{"code": e.code, "message": e.message}]
                    }
            raise e
        except neo4j.exceptions.DriverError as e:
            logger.error(e)
            if return_errors:
                return {
                    "results": [],
                    "errors": [{"message": f'A driver error occurred: {e}'}]
                    }
            raise e

    def supports_apoc(self) -> bool:
        return False

    def check_apoc_support(self):
        return False

    async def close(self):
        if self.driver:
            await self.driver.close()
