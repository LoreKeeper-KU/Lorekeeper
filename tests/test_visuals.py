# Authored By Saif Altamimi 31/10/2026
from shared.schemas import CanonFact
from multimodal.visuals import build_visual_prompt

SCENE = (
    "Captain Arin entered the royal palace in Eldoria. "
    "Queen Lyra greeted him warmly."
)
FACTS = [
    CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear"),
    CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria"),
]


def test_prompt_includes_scene_and_facts():
    prompt = build_visual_prompt(SCENE, FACTS)
    print(prompt)
    assert "Captain Arin entered the royal palace" in prompt
    assert "golden spear" in prompt
    assert "Queen Lyra" in prompt


def test_prompt_works_without_facts():
    prompt = build_visual_prompt(SCENE, [])
    assert "Scene:" in prompt