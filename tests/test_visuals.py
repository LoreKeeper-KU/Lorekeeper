# Authored By Saif Altamimi 31/10/2026
from multimodal.model import FactCheck, VisionCheckResult
from multimodal.visuals import build_visual_prompt, generate_visual, verify_visual
from shared.schemas import CanonFact, VisualAsset

SCENE = (
    "Captain Arin entered the royal palace in Eldoria. "
    "Queen Lyra greeted him warmly."
)
FACTS = [
    CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear"),
    CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria"),
]
ASSET = VisualAsset(image_path="outputs/fake_image.png", prompt="(any prompt)")


class FakeAIClient:
    """Pretends to be AIClient: no API calls, no cost."""

    def __init__(self, vision_result=None):
        self.prompts = []  # remembers every prompt it receives
        self.vision_result = vision_result  # what analyze_image should "see"

    def generate_image(self, prompt):
        self.prompts.append(prompt)
        return "outputs/fake_image.png"

    def analyze_image(self, image_path, prompt, schema=None):
        self.prompts.append(prompt)
        return self.vision_result


def vision(*checks):
    """Shortcut: build a fake vision answer from (fact_id, status, observed) tuples."""
    return VisionCheckResult(
        checks=[
            FactCheck(fact_id=fid, status=status, observed=observed, explanation="test")
            for fid, status, observed in checks
        ]
    )


# --- build_visual_prompt ------------------------------------------------------

def test_prompt_includes_scene_and_facts():
    prompt = build_visual_prompt(SCENE, FACTS)
    print(prompt)
    assert "Captain Arin entered the royal palace" in prompt
    assert "golden spear" in prompt
    assert "Queen Lyra" in prompt


def test_prompt_works_without_facts():
    prompt = build_visual_prompt(SCENE, [])
    assert "Scene:" in prompt


# --- generate_visual ----------------------------------------------------------

def test_generate_visual_returns_asset():
    # Arrange: make a fake AI client (no API calls, no cost)
    fake = FakeAIClient()

    # Act: run the function we're testing, using the fake
    asset = generate_visual(SCENE, FACTS, ai=fake)

    # Assert: check the result is right
    assert asset.image_path == "outputs/fake_image.png"  # used the path the client returned
    assert "golden spear" in asset.prompt  # canon facts made it into the prompt
    assert fake.prompts[0] == asset.prompt  # saved prompt = the one sent to the AI


# --- verify_visual ------------------------------------------------------------

def test_verify_visual_reports_mismatch():
    # Arrange: the "vision model" sees a blue staff instead of the golden spear
    fake = FakeAIClient(vision(
        ("fact-001", "mismatch", "blue staff"),
        ("fact-002", "unable_to_assess", None),
    ))

    # Act
    report = verify_visual(ASSET, FACTS, ai=fake)

    # Assert
    assert report.consistent is False
    assert report.evidence_fact_ids == ["fact-001"]
    assert "blue staff" in report.issues[0]


def test_verify_visual_all_match_is_consistent():
    fake = FakeAIClient(vision(
        ("fact-001", "match", "golden spear"),
        ("fact-002", "unable_to_assess", None),
    ))
    report = verify_visual(ASSET, FACTS, ai=fake)
    assert report.consistent is True
    assert report.issues == []
    assert report.evidence_fact_ids == []


def test_verify_visual_sends_fact_ids_to_vision_model():
    fake = FakeAIClient(vision(("fact-001", "match", "golden spear")))
    verify_visual(ASSET, FACTS, ai=fake)
    assert "fact-001" in fake.prompts[0]
    assert "golden spear" in fake.prompts[0]


def test_verify_visual_ignores_invented_fact_ids():
    # The model "mismatches" a fact we never sent -> must not become an issue
    fake = FakeAIClient(vision(("fact-999", "mismatch", "a dragon")))
    report = verify_visual(ASSET, FACTS, ai=fake)
    assert report.consistent is True
    assert report.evidence_fact_ids == []
