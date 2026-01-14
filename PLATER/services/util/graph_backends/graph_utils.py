from neo4j import AsyncResult


# this is kind of hacky but in order to return the same pydantic model result for both drivers
# convert the raw bolt cypher response to something that's formatted like the http json response
async def convert_bolt_results_to_cypher_result(result: AsyncResult):
    cypher_result = {
        "results": [
            {
                "columns": result.keys(),
                "data": [{"row": [values for values in list(data.values())], "meta": []}
                         for data in await result.data()]
            }
        ],
        "errors": []
    }
    return cypher_result
