#Authored By Saif Altamimi 14/11/2026

from multimodal.visuals import repair_visual, verify_visual
from shared.schemas import CanonFact, VisualAsset

facts = [
    CanonFact(id="F001", subject="Princess Amina", predicate="hair_color", object="black"),
    CanonFact(id="F004", subject="Princess Amina", predicate="armor_color", object="silver"),
]

asset = VisualAsset(image_path="outputs/example_amina_gold.png", prompt="-")
report = verify_visual(asset, facts)
print("Before:", report.consistent, report.evidence_fact_ids)

result = repair_visual(asset, report, facts)
print("After: ", result.report.consistent, result.report.evidence_fact_ids)
print("Edits made:", result.attempts)
print("Final image:", result.asset.image_path)
print("Needs human review:", result.needs_human_review)