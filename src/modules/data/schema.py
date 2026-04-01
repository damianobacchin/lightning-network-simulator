from pydantic import BaseModel


class Node(BaseModel):
    id: str
    alias: str


class EdgeNode(BaseModel):
    id: str
    fee_base: int
    fee_rate: int


class Edge(BaseModel):
    nodes: list[EdgeNode]
    capacity: int


class LightningNetworkData(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
