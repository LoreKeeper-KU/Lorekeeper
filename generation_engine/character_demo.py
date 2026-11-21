# Authored by Abdullah on 21/11/2026
# Runs character creation without needing existing canon.

import argparse
from pathlib import Path

from dotenv import load_dotenv

from .character_creator import create_character


def main():
    # Read the character description from the terminal command.
    parser = argparse.ArgumentParser(
        description="Create an unsaved LoreKeeper character draft."
    )
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    if not args.prompt.strip():
        parser.error("--prompt must describe a character")

    # Load the .env file from the Lorekeeper project folder.
    project_folder = Path(__file__).resolve().parents[1]
    load_dotenv(project_folder / ".env")

    # Import after loading the API configuration.
    from shared.ai_client import AIClient

    print("Creating character draft...", flush=True)

    # An empty list means there is no existing canon.
    draft = create_character(args.prompt, [], AIClient())

    # Display the profile and proposed facts.
    # This does not save or approve them.
    print(draft.model_dump_json(indent=2))


# Start the demo when this module is run.
if __name__ == "__main__":
    main()