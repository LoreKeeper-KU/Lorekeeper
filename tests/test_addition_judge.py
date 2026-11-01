"""LLMAdditionJudge: decides whether a neutral claim is a safe candidate new addition.

No real API calls: a fake client stands in for the shared AIClient.
"""

import pytest

from continuity_checker.addition_judge import (
    ADDITION_SYSTEM_PROMPT,
    AdditionDecision,
    AdditionVerdict,
    LLMAdditionJudge,
)
from continuity_checker.canon_verifier import ClaimComparison, Verdict
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import CanonFact, Claim, ClaimClassification, SourceSpan
from shared.ai_client import AIClientError

CLAIM = Claim(
    claim_id="C001",
    text="Queen Lyra greeted Arin warmly.",
    source_span=SourceSpan(start=0, end=31),
)
FACTS = [
    CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear"),
    CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria"),
]


class FakeSharedClient:
    """Stands in for AIClient: only generate_structured, no network."""

    def __init__(self, verdict=None, error=None):
        self.calls = []
        self._verdict = verdict
        self._error = error

    def generate_structured(self, instructions, prompt, schema):
        self.calls.append((instructions, prompt, schema))
        if self._error:
            raise self._error
        return AdditionDecision(reasoning="because", verdict=self._verdict)


def judge_with(verdict):
    return LLMAdditionJudge(FakeSharedClient(verdict=verdict))


def test_a_clear_valid_addition_is_approved():
    assert judge_with(AdditionVerdict.VALID_NEW_ADDITION)(CLAIM, FACTS) is True


def test_a_claim_that_conflicts_or_is_in_tension_is_not_approved():
    assert judge_with(AdditionVerdict.CONFLICTS_OR_TENSION)(CLAIM, FACTS) is False


def test_insufficient_context_is_not_approved():
    assert judge_with(AdditionVerdict.INSUFFICIENT_CONTEXT)(CLAIM, FACTS) is False


def test_without_canon_facts_it_declines_and_never_calls_the_model():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)

    assert LLMAdditionJudge(client)(CLAIM, []) is False
    assert client.calls == []


def test_model_sees_the_claim_and_every_fact_with_its_id():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)

    LLMAdditionJudge(client)(CLAIM, FACTS)

    ((instructions, prompt, schema),) = client.calls
    assert instructions == ADDITION_SYSTEM_PROMPT
    assert schema is AdditionDecision
    assert "Queen Lyra greeted Arin warmly." in prompt
    assert "fact-001: Captain Arin weapon: golden spear" in prompt
    assert "fact-002: Queen Lyra rules: Eldoria" in prompt


def test_prompt_names_every_verdict_the_model_may_choose():
    for verdict in AdditionVerdict:
        assert verdict.value in ADDITION_SYSTEM_PROMPT


def test_prompt_says_missing_evidence_alone_is_not_validity():
    assert "absence" in ADDITION_SYSTEM_PROMPT.lower()


def test_a_failing_model_call_is_raised_not_turned_into_a_decision():
    judge = LLMAdditionJudge(FakeSharedClient(error=AIClientError("Could not reach the API")))

    with pytest.raises(AIClientError, match="Could not reach"):
        judge(CLAIM, FACTS)


# --- inside the policy layer -------------------------------------------------------------


def neutral():
    return ClaimComparison(
        claim_id="C001", verdict=Verdict.NEUTRAL, supporting_fact_ids=[], conflicting_fact_ids=[]
    )


def test_policy_makes_a_neutral_claim_a_valid_new_addition_when_the_judge_approves():
    classifier = ContradictionClassifier(judge_with(AdditionVerdict.VALID_NEW_ADDITION))

    result = classifier.classify(CLAIM, neutral(), FACTS)

    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert result.evidence_ids == []
    assert "approval" in result.explanation


@pytest.mark.parametrize(
    "verdict", [AdditionVerdict.CONFLICTS_OR_TENSION, AdditionVerdict.INSUFFICIENT_CONTEXT]
)
def test_policy_keeps_a_neutral_claim_uncertain_when_the_judge_declines(verdict):
    result = ContradictionClassifier(judge_with(verdict)).classify(CLAIM, neutral(), FACTS)

    assert result.classification == ClaimClassification.UNCERTAIN


def test_policy_does_not_ask_the_judge_when_there_is_no_canon_evidence():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)

    result = ContradictionClassifier(LLMAdditionJudge(client)).classify(CLAIM, neutral(), [])

    assert result.classification == ClaimClassification.UNCERTAIN
    assert client.calls == []


def test_policy_does_not_ask_the_judge_about_supported_claims():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)
    supported = ClaimComparison(
        claim_id="C001",
        verdict=Verdict.ENTAILMENT,
        supporting_fact_ids=["fact-002"],
        conflicting_fact_ids=[],
    )

    result = ContradictionClassifier(LLMAdditionJudge(client)).classify(CLAIM, supported, FACTS)

    assert result.classification == ClaimClassification.SUPPORTED
    assert client.calls == []


def test_policy_does_not_ask_the_judge_about_exclusive_contradictions():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)
    status = CanonFact(id="fact-003", subject="Arin's father", predicate="status", object="alive")
    conflict = ClaimComparison(
        claim_id="C001",
        verdict=Verdict.CONTRADICTION,
        supporting_fact_ids=[],
        conflicting_fact_ids=["fact-003"],
    )

    result = ContradictionClassifier(LLMAdditionJudge(client)).classify(CLAIM, conflict, [status])

    assert result.classification == ClaimClassification.CONTRADICTION
    assert client.calls == []


def test_policy_does_not_ask_the_judge_about_an_unaccepted_conflict():
    client = FakeSharedClient(verdict=AdditionVerdict.VALID_NEW_ADDITION)
    conflict = ClaimComparison(
        claim_id="C001",
        verdict=Verdict.CONTRADICTION,
        supporting_fact_ids=[],
        conflicting_fact_ids=["fact-001"],
    )

    result = ContradictionClassifier(LLMAdditionJudge(client)).classify(CLAIM, conflict, FACTS)

    assert result.classification == ClaimClassification.UNCERTAIN
    assert client.calls == []


# --- with the real shared AIClient against a local fake server ---------------------------


def test_real_shared_client_round_trip_approves_a_valid_addition(fake_chat_api):
    fake_chat_api.reply_text = AdditionDecision(
        reasoning="A greeting conflicts with nothing shown.",
        verdict=AdditionVerdict.VALID_NEW_ADDITION,
    ).model_dump_json()

    assert LLMAdditionJudge(fake_chat_api.client)(CLAIM, FACTS) is True
    (request,) = fake_chat_api.requests_seen
    assert ADDITION_SYSTEM_PROMPT in [m["content"] for m in request["messages"]]


def test_real_shared_client_round_trip_declines_on_insufficient_context(fake_chat_api):
    fake_chat_api.reply_text = AdditionDecision(
        reasoning="Canon says too little.", verdict=AdditionVerdict.INSUFFICIENT_CONTEXT
    ).model_dump_json()

    assert LLMAdditionJudge(fake_chat_api.client)(CLAIM, FACTS) is False
