from typing import Dict, List

from pydantic import BaseModel
from reasoner_pydantic import Query as ReasonerRequest, Message, Response, BiolinkEntity, BiolinkPredicate


class MetaNode(BaseModel):
    id_prefixes: List[str]


class MetaEdge(BaseModel):
    subject: BiolinkEntity
    object: BiolinkEntity
    predicate: BiolinkPredicate


class MetaKnowledgeGraph(BaseModel):
    nodes: Dict[str, MetaNode]
    edges: List[MetaEdge]

