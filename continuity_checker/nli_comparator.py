from collections.abc import Callable, Sequence

from continuity_checker.canon_verifier import Verdict, fact_to_premise
from continuity_checker.models import Claim
from shared.schemas import CanonFact

# (premise, hypothesis) -> one probability per label, in the order of the labels given
Scorer = Callable[[str, str], Sequence[float]]


class NLIComparator:
    """A Comparator backed by an NLI scorer. Holds no model itself."""

    def __init__(
        self,
        scorer: Scorer,
        labels: Sequence[str],
        contradiction_threshold: float = 0.5,
        entailment_threshold: float = 0.5,
    ):
        names = [label.lower() for label in labels]
        if sorted(names) != sorted(v.value for v in Verdict):
            raise ValueError(f"labels must be exactly entailment, neutral, contradiction: {labels}")
        self.scorer = scorer
        self.labels = names
        self.contradiction_threshold = contradiction_threshold
        self.entailment_threshold = entailment_threshold

    @classmethod
    def from_pretrained(cls, model_name: str, **thresholds) -> "NLIComparator":
        scorer, labels = load_hf_scorer(model_name)
        return cls(scorer, labels, **thresholds)

    def __call__(self, claim: Claim, fact: CanonFact) -> Verdict:
        probabilities = self.scorer(fact_to_premise(fact), claim.text)
        if len(probabilities) != len(self.labels):
            raise ValueError(
                f"Scorer returned {len(probabilities)} probabilities for {len(self.labels)} labels"
            )
        by_label = dict(zip(self.labels, probabilities))

        if by_label[Verdict.CONTRADICTION] >= self.contradiction_threshold:
            return Verdict.CONTRADICTION
        if by_label[Verdict.ENTAILMENT] >= self.entailment_threshold:
            return Verdict.ENTAILMENT
        return Verdict.NEUTRAL


def load_hf_scorer(model_name: str) -> tuple[Scorer, list[str]]:
    """Load a Hugging Face NLI model. torch is imported here so nothing else depends on it."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    labels = [model.config.id2label[i] for i in range(model.config.num_labels)]

    def scorer(premise: str, hypothesis: str) -> list[float]:
        inputs = tokenizer(premise, hypothesis, truncation=True, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
        return torch.softmax(logits, dim=-1)[0].tolist()

    return scorer, labels
