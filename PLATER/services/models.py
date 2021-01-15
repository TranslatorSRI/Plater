"""Pydantic models."""
from typing import Dict, List, Union

from pydantic import BaseModel, constr
from reasoner_pydantic import Message , Query as ReasonerRequest


class CypherRequest(BaseModel):
    query: str


class SimpleSpecElement(BaseModel):
    source_type: str
    target_type: str
    edge_type: str


SimpleSpecResponse = List[SimpleSpecElement]

TypeSet = constr(regex=r"\w+(:\w+)*")


class TypeSummary(BaseModel):
    nodes_count: int

    class Config:
        schema_extra = {
            "patternProperties": {
                r"\w+(:\w+)*": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "integer"
                    }
                }
            }
        }


# class GraphSummaryResponse(BaseModel):
#     __root__: Dict[TypeSet, TypeSummary]


# print(GraphSummaryResponse.schema_json(indent=4))

GraphSummaryResponse = Dict[TypeSet, TypeSummary]


class CypherDatum(BaseModel):
    row: List
    meta: List


class CypherResult(BaseModel):
    columns: List[str]
    data: List[CypherDatum]


class CypherError(BaseModel):
    code: str
    message: str


class CypherResponse(BaseModel):
    results: List[CypherResult]
    errors: List[CypherError]


PredicatesResponse = Dict[str, Dict[str, List[str]]]
