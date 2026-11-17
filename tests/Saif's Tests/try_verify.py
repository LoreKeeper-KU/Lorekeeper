#Authored By Saif Altamimi 14/11/2026

from multimodal.visuals import verify_visual
from shared.schemas import CanonFact, VisualAsset

facts = [
    CanonFact(id="F001", subject="Princess Amina", predicate="hair_color", object="black"),
    CanonFact(id="F004", subject="Princess Amina", predicate="armor_color", object="silver"),
]

for path in ["outputs/example_amina.png", "outputs/example_amina_gold.png"]:
    report = verify_visual(VisualAsset(image_path=path, prompt="-"), facts)
    print(path)
    print("  consistent:", report.consistent)
    print("  issues:", report.issues)
    print("  broken facts:", report.evidence_fact_ids)