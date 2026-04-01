import matplotlib
import matplotlib.pyplot as plt
import networkx as nx

from modules.data.schema import Edge, Node

matplotlib.use("Qt5Agg")


class LightningNetwork:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, node: Node):
        self.graph.add_node(node.id, alias=node.alias)

    def add_edge(self, edge: Edge):
        src, dst = edge.nodes[0], edge.nodes[1]
        balance = edge.capacity // 2

        self.graph.add_edge(
            src.id,
            dst.id,
            capacity=balance,
            fee_base=src.fee_base,
            fee_rate=src.fee_rate,
        )
        self.graph.add_edge(
            dst.id,
            src.id,
            capacity=balance,
            fee_base=dst.fee_base,
            fee_rate=dst.fee_rate,
        )

    def plot(self):
        pos = nx.nx_agraph.graphviz_layout(self.graph, prog="sfdp")
        labels = nx.get_node_attributes(self.graph, "alias")
        nx.draw(self.graph, pos, labels=labels, with_labels=True, node_color="skyblue")
        plt.show()
