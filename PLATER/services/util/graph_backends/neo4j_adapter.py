import asyncio
import neo4j

import neo4j.exceptions
from neo4j import unit_of_work

from PLATER.services.config import config
from PLATER.services.util.logutil import LoggingUtil
from PLATER.services.util.graph_backends.base import GraphBackend
from PLATER.services.util.graph_backends.graph_utils import convert_bolt_results_to_cypher_result
from reasoner_transpiler.cypher import transform_result

logger = LoggingUtil.init_logging(__name__,
                                  config.get('logging_level'),
                                  config.get('logging_format'))

NEO4J_QUERY_TIMEOUT = int(config.get('GRAPH_QUERY_TIMEOUT', 1600))


class Neo4jBackend(GraphBackend):
    supports_element_id = True

    def __init__(self, host: str, port: str, auth: tuple, database_name='neo4j'):
        self.database_name = database_name
        self.database_auth = auth
        self.graph_db_uri = f'bolt://{host}:{port}'
        self.neo4j_driver = None
        self.sync_neo4j_driver = None
        self._supports_apoc = None

    async def connect(self, retries=0):
        if not self.neo4j_driver:
            self.neo4j_driver = neo4j.AsyncGraphDatabase.driver(self.graph_db_uri,
                                                                auth=self.database_auth,
                                                                **{'telemetry_disabled': True,
                                                                   'max_connection_pool_size': 1000})
        try:
            await self.neo4j_driver.verify_connectivity()
        except Exception as e:  # currently the driver says it raises Exception, not something more specific
            await self.neo4j_driver.close()
            if retries <= 25:
                await asyncio.sleep(8)
                logger.error(f'Could not establish connection to neo4j, trying again... retry {retries + 1}')
                await self.connect(retries + 1)
            else:
                logger.error(f'Could not establish connection to neo4j, error: {e}')
                raise e

    @staticmethod
    @unit_of_work(timeout=NEO4J_QUERY_TIMEOUT)
    async def _async_cypher_tx_function(tx,
                                        cypher,
                                        query_parameters=None,
                                        convert_to_dict=False,
                                        convert_to_trapi=False,
                                        qgraph=None):
        if not query_parameters:
            query_parameters = {}

        neo4j_result: neo4j.AsyncResult = await tx.run(cypher, parameters=query_parameters)

        if convert_to_trapi:
            record = await neo4j_result.single()
            return transform_result(record, qgraph)

        if convert_to_dict:
            results = []
            async for record in neo4j_result:
                results.append({k: v for k, v in record.items()})
            return results

        return await convert_bolt_results_to_cypher_result(neo4j_result)

    @staticmethod
    def _sync_cypher_tx_function(tx,
                                 cypher,
                                 query_parameters=None,
                                 convert_to_dict=False):
        if not query_parameters:
            query_parameters = {}
        neo4j_result: neo4j.Result = tx.run(cypher, parameters=query_parameters)
        if convert_to_dict:
            results = []
            for record in neo4j_result:
                results.append({key: value for key, value in record.items()})
            return results
        else:
            return neo4j_result

    async def run(self,
                  query,
                  query_parameters=None,
                  return_errors=False,
                  convert_to_dict=False,
                  convert_to_trapi=False,
                  qgraph=None):
        try:
            async with self.neo4j_driver.session(database=self.database_name,
                                                 default_access_mode=neo4j.READ_ACCESS) as session:
                return await session.execute_read(self._async_cypher_tx_function,
                                                  query,
                                                  query_parameters=query_parameters,
                                                  convert_to_dict=convert_to_dict,
                                                  convert_to_trapi=convert_to_trapi,
                                                  qgraph=qgraph)
        except neo4j.exceptions.ServiceUnavailable as e:
            logger.error(f'Session could not establish connection to neo4j ({e}).. trying to connect again')
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
                return {"results": [],
                        "errors": [{"code": e.code,
                                    "message": e.message}]}
            raise e
        except neo4j.exceptions.DriverError as e:
            logger.error(e)
            if return_errors:
                return {"results": [],
                        "errors": [{"message": f'A driver error occurred: {e}'}]}
            raise e

    def run_sync(self,
                 query,
                 query_parameters=None,
                 return_errors=False,
                 convert_to_dict=False):
        if not self.sync_neo4j_driver:
            self.sync_neo4j_driver = neo4j.GraphDatabase.driver(self.graph_db_uri, auth=self.database_auth)
        try:
            with self.sync_neo4j_driver.session(database=self.database_name, default_access_mode=neo4j.READ_ACCESS) as session:

                run_sync_result = session.execute_read(self._sync_cypher_tx_function,
                                                       query,
                                                       query_parameters=query_parameters,
                                                       convert_to_dict=convert_to_dict)
                return run_sync_result

        except neo4j.exceptions.Neo4jError as e:
            if return_errors:
                logger.error(e)
                return {"results": [],
                        "errors": [{"code": e.code,
                                    "message": e.message}]}
            raise e
        except (neo4j.exceptions.DriverError, neo4j.exceptions.ServiceUnavailable) as e:
            if return_errors:
                logger.error(e)
                return {"results": [],
                        "errors": [{"code": "",
                                    "message": f'A driver error occurred: {e}'}]}
            raise e
        finally:
            if self.sync_neo4j_driver:
                self.sync_neo4j_driver.close()
            self.sync_neo4j_driver = None

    def check_apoc_support(self):
        apoc_version_query = 'call apoc.version()'
        if self._supports_apoc is None:
            try:
                self.run_sync(apoc_version_query)
                self._supports_apoc = True
            except neo4j.exceptions.ClientError:
                self._supports_apoc = False
        return self._supports_apoc

    def supports_apoc(self) -> bool:
        if self._supports_apoc is None:
            try:
                self.run_sync("CALL apoc.version()")
                self._supports_apoc = True
            except neo4j.exceptions.ClientError:
                self._supports_apoc = False
        return self._supports_apoc

    async def close(self):
        if self.neo4j_driver:
            await self.neo4j_driver.close()


def convert_http_response_to_dict(response: dict) -> list:
    """
    Converts a neo4j result to a structured result.
    :param response: neo4j http raw result.
    :type response: dict
    :return: reformatted dict
    :rtype: dict
    """
    results = response.get('results')
    array = []
    if results:
        for result in results:
            cols = result.get('columns')
            if cols:
                data_items = result.get('data')
                for item in data_items:
                    new_row = {}
                    row = item.get('row')
                    for col_name, col_value in zip(cols, row):
                        new_row[col_name] = col_value
                    array.append(new_row)
    return array