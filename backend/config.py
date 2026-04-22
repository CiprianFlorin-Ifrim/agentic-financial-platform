# backend/config.py
# Centralised configuration loader.
# Import this module before any os.getenv() call that reads from .env.
# Because Python caches module imports, load_dotenv() runs exactly once
# regardless of how many agents import this file.

import os
from dotenv import load_dotenv

load_dotenv()

# -- Models -------------------------------------------------------------------
# Two tiers: orchestrators use the standard model for deeper reasoning,
# leaf agents use the lite model for fast single-tool-call execution.

STD_MODEL: str = os.getenv("STD_MODEL", "gemini-3-flash-preview")
LITE_MODEL: str = os.getenv("LITE_MODEL", "gemini-3.1-flash-lite-preview")
