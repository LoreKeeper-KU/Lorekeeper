# Written by Abdulaziz Albastaki in October 2026
import networkx as nx

from shared.schemas import CanonFact
class KnowledgeGraph:
    def __init__(self, facts: list[CanonFact]):
        self.graph = nx.MultiDiGraph()
        self.facts = {}

        for fact in facts:
            self.add_fact(fact)

    def add_fact(self, fact: CanonFact):
        """Add a canon fact to the graph."""

        self.facts[fact.id] = fact

        self.graph.add_edge(
            fact.subject,
            fact.object,
            key=fact.id,
            predicate=fact.predicate
        )

    def get_related_facts(self, entity: str) -> list[CanonFact]:
        """Get facts where entity is subject or object."""

        if entity not in self.graph:
            return []

        fact_ids = set()

        # Facts where entity is the subject
        for _, _, fact_id in self.graph.out_edges(
            entity, keys=True
        ):
            fact_ids.add(fact_id)

        # Facts where entity is the object
        for _, _, fact_id in self.graph.in_edges(
            entity, keys=True
        ):
            fact_ids.add(fact_id)

        return [
            self.facts[fact_id]
            for fact_id in sorted(fact_ids)
        ]
