"""
config.py — Centralised configuration for ARIS
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)

# ── Project ───────────────────────────────────────────────────────────────────
PROJECT_NAME    = "ARIS — Automated Replenishment Intelligence System"
PROJECT_VERSION = "1.0.0"
TEAM            = "Team-20: Anandasekhar | Rohit | Raseeth"

# ── LLM ───────────────────────────────────────────────────────────────────────
LLM_MODE           = os.getenv("LLM_MODE", "mock")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
OPENAI_MAX_TOKENS  = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))

# ── Safety Thresholds ─────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
HITL_THRESHOLD       = float(os.getenv("HITL_ESCALATION_THRESHOLD", "0.60"))
MAX_REORDER_VALUE    = float(os.getenv("MAX_REORDER_VALUE", "50000"))

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR           = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
STORE_DIR          = BASE_DIR / "store"
LOG_DIR            = BASE_DIR / "logs"

# ── Inventory Defaults ────────────────────────────────────────────────────────
DEFAULT_SERVICE_LEVEL  = 0.95
WORKING_DAYS_PER_YEAR  = 250
HOLDING_COST_FRACTION  = 0.20

# ── Ensure directories ────────────────────────────────────────────────────────
for _d in [DATA_DIR, KNOWLEDGE_BASE_DIR, STORE_DIR, LOG_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


def is_openai_available() -> bool:
    return bool(OPENAI_API_KEY) and LLM_MODE == "openai"
