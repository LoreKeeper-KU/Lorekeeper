# Authored By Saif Altamimi 31/10/2026
"""Shared settings for every LoreKeeper module.

Everything is read from the .env file, so the team can switch provider or
model without editing code. The API key lives ONLY in .env, never in code.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # reads the .env file

# Which AI provider to talk to (any "OpenAI-compatible" API works)
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")

# Models (override any of them in .env)
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.4-mini")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-5.4-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")

# Network behaviour
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "180"))  # seconds; images are slow
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))  # extra tries on temporary errors

# Where generated images are saved
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
