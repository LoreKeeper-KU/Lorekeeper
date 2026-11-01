# Authored by Abdullah on 31/10/2026
# This file contains your story-generation and repair functions.
# The text is scripted for the demo. Later, you can replace it
# with a call to the shared ai_client.py.


from .models import DemoRequest, Scene, VerificationReport


def generate_story(request: DemoRequest) -> Scene:
    """
    Creates the first version of a scene.

    For this demo, the scene intentionally contains a contradiction:
    Amina uses magic even though the canon says she has no magic.
    """

    scene_text = (
        "Princess Amina stood on the walls of Silverkeep Castle. "
        "She summoned a magical firestorm to drive back the attackers."
    )

    return Scene(
        scene_id="scene_001",
        text=scene_text,
        revision=0,
    )


def repair_story(
    scene: Scene,
    report: VerificationReport,
) -> Scene:
    """
    Repairs the scene using the verifier's correction instruction.

    The function changes only the conflicting sentence and keeps
    the rest of the scene unchanged.
    """

    repaired_text = scene.text.replace(
        "She summoned a magical firestorm to drive back the attackers.",
        "She commanded her archers to fire flaming arrows at the attackers.",
    )

    return Scene(
        scene_id=scene.scene_id,
        text=repaired_text,
        revision=scene.revision + 1,
    )