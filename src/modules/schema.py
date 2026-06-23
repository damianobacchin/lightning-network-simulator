from pydantic import BaseModel


class Node(BaseModel):
    id: str


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


class LightningPaymentData(BaseModel):
    src: str
    dst: str
    amount: int


class SimulationResult(BaseModel):
    total_payments: int
    successful_payments: int
    failed_payments: int
    total_fees: int
