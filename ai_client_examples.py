# Authored By Saif Altamimi 31/10/2026
"""Examples of every AIClient method.

Run from the main Lorekeeper folder:  python ai_client_examples.py
Makes real API calls (a few cents in total, mostly the images).
"""
from pydantic import BaseModel

from shared.ai_client import AIClient

ai = AIClient()

# 1. generate_text (Abdullah)
print("1. generate_text")
print(ai.generate_text("You are a fantasy storyteller.", "Describe a castle in one sentence."))

# 2. generate_structured (Faris)
class Character(BaseModel):
    name: str
    hair_color: str

print("\n2. generate_structured")
character = ai.generate_structured(
    "Extract the character described.", "Princess Amina has long black hair.", Character
)
print(character)

# 3. embed_text (Abdulaziz)
print("\n3. embed_text")
vector = ai.embed_text("Amina defends the northern castle.")
print(f"{len(vector)} numbers, first three: {vector[:3]}")

# 4. generate_image (Saif)
print("\n4. generate_image (can take up to a minute)")
path = ai.generate_image(
    "A cinematic fantasy illustration of Princess Amina, a black-haired ruler "
    "wearing silver armor, on stone castle walls.",
    output_path="outputs/example_amina.png",
)
print("Saved to:", path)

# 5. analyze_image (Saif)
print("\n5. analyze_image")
print(ai.analyze_image(path, "What colour is her hair, and what colour is her armor?"))

# 6. edit_image (Saif)
print("\n6. edit_image (can take up to a minute)")
edited = ai.edit_image(
    path,
    "Change the armor to gold. Keep everything else the same.",
    output_path="outputs/example_amina_gold.png",
)
print("Saved to:", edited)