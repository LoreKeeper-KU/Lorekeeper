# Authored By Saif Altamimi 31/10/2026
from multimodal.visuals import build_visual_prompt, generate_visual
from shared.schemas import CanonFact

SCENE = (
    "Captain Arin entered the royal palace in Eldoria. "
    "Queen Lyra greeted him warmly."
)
FACTS = [
    CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear"),
    CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria"),
]


class FakeAIClient:
    """Pretends to be AIClient: no API calls, no cost."""

    def __init__(self):
        self.prompts = []  # remembers every prompt it receives

    def generate_image(self, prompt):
        self.prompts.append(prompt)
        return "outputs/fake_image.png"


def test_prompt_includes_scene_and_facts():
    prompt = build_visual_prompt(SCENE, FACTS)
    print(prompt)
    assert "Captain Arin entered the royal palace" in prompt
    assert "golden spear" in prompt
    assert "Queen Lyra" in prompt


def test_prompt_works_without_facts():
    prompt = build_visual_prompt(SCENE, [])
    assert "Scene:" in prompt


def test_generate_visual_returns_asset():
    # Arrange: make a fake AI client (no API calls, no cost)
    fake = FakeAIClient()

    # Act: run the function we're testing, using the fake
    asset = generate_visual(SCENE, FACTS, ai=fake)

    # Assert: check the result is right
    assert asset.image_path == "outputs/fake_image.png"  # used the path the client returned
    assert "golden spear" in asset.prompt  # canon facts made it into the prompt
    assert fake.prompts[0] == asset.prompt  # saved prompt = the one sent to the AI