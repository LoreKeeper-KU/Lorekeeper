# Authored by Abdullah on 31/10/2026
# Temporary sample functions for the other team members' modules.
# These are placeholders so your workflow can run before their real code is ready.


def retrieve_canon():
    """
    Returns approved world facts.

    Abdulaziz will later replace this with the real canon database.
    """
    return {
        "character": "Princess Amina",
        "ability": "Amina has no magical ability.",
        "location": "Silverkeep Castle",
    }


def verify_scene(scene_text):
    """
    Checks the generated scene against the sample canon.

    Faris will later replace this with the real verification system.
    """

    # This is the contradiction we want to demonstrate.
    if "magical firestorm" in scene_text:
        return {
            "status": "conflict",
            "conflict": "Amina uses magic, but the canon says she has no magical ability.",
            "correction": "Replace the magical attack with a command to her archers.",
        }

    # If the contradiction is not present, the scene passes.
    return {
        "status": "consistent",
        "conflict": "",
        "correction": "",
    }


def generate_image(scene_text):
    """
    Placeholder for Saif's image-generation module.

    It returns a message instead of creating a real image.
    """
    return {
        "status": "not_implemented",
        "message": "Image generation will be connected later.",
        "scene_text": scene_text,
    }