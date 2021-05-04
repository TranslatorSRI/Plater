from typing import Dict, List, Union, Optional

from pydantic import BaseModel, constr, Field
from reasoner_pydantic import Message as Message_1_0, Response as Response_1_0, BiolinkEntity, BiolinkPredicate, CURIE


class MetaNode(BaseModel):
    id_prefixes: List[str]


class MetaEdge(BaseModel):
    subject: BiolinkEntity
    object: BiolinkEntity
    predicate: BiolinkPredicate


class MetaKnowledgeGraph(BaseModel):
    nodes: Dict[str, MetaNode]
    edges: List[MetaEdge]


class QNode(BaseModel):
    """
    Trapi version 1.1 Query Node
    """
    ids: Union[List[CURIE], None] = Field(
        None,
        title='ids',
        nullable=True,
    )
    categories: Union[List[BiolinkEntity], None] = Field(
        None,
        title='categories',
        nullable=True,
    )
    is_set: bool = False

    class Config:
        title = 'query-graph node'
        extra = 'allow'


class QEdge(BaseModel):
    """Query edge."""

    subject: str = Field(
        ...,
        title='subject node id',
    )
    object: str = Field(
        ...,
        title='object node id',
    )
    predicates: Union[List[BiolinkPredicate], None] = Field(
        None,
        title='predicates',
        nullable=True,
    )
    relation: Optional[str] = Field(None, nullable=True)

    class Config:
        title = 'query-graph edge'
        extra = 'allow'


class QueryGraph(BaseModel):
    """Query graph."""

    nodes: Dict[str, QNode] = Field(
        ...,
        title='dict of nodes',
    )
    edges: Dict[str, QEdge] = Field(
        ...,
        title='dict of edges',
    )

    class Config:
        title = 'simple query graph'
        extra = 'allow'


class Message(Message_1_0):
    """
    Overrides query graph of trapi 1.0
    """
    query_graph: Optional[QueryGraph] = Field(
        None,
        title='query graph',
        nullable=True
    )


class Response(Response_1_0):
    message: Message = Field(
        ...,
        title='message'
    )


class Query(BaseModel):
    message: Message = Field(..., title='message')

    class Config:
        title = 'query'
        extra = 'allow'
        schema_extra = {
            "x-body-name": "request_body"
        }