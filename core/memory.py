"""
memory/agent_memory.py
======================
Short-term (conversation) and long-term (persistent JSON) memory for agents.
"""

import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from config import STORE_DIR as MEMORY_DIR

# ── Paths ─────────────────────────────────────────────────────────────────────
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LT_MEMORY_FILE    = MEMORY_DIR / "long_term_memory.json"
FEEDBACK_LOG_FILE = MEMORY_DIR / "feedback_log.json"
ADAPTATION_FILE   = MEMORY_DIR / "adaptation_params.json"


# ════════════════════════════════════════════════════════════════════════════════
# Short-Term Memory (conversation window)
# ════════════════════════════════════════════════════════════════════════════════
class ShortTermMemory:
    """
    Rolling window of recent conversation turns.
    Resets when a new session starts or on explicit clear().
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._history: deque[dict] = deque(maxlen=max_turns)
        self.session_id = f"session_{int(time.time())}"

    def add(self, role: str, content: str, metadata: dict | None = None):
        """Add a turn to the conversation history."""
        self._history.append({
            "role"     : role,
            "content"  : content,
            "timestamp": datetime.now().isoformat(),
            "metadata" : metadata or {},
        })

    def get_history(self) -> list[dict]:
        return list(self._history)

    def get_langchain_messages(self) -> list[dict]:
        """Return history in LangChain message format."""
        return [{"role": t["role"], "content": t["content"]}
                for t in self._history]

    def clear(self):
        self._history.clear()
        self.session_id = f"session_{int(time.time())}"

    def __len__(self) -> int:
        return len(self._history)


# ════════════════════════════════════════════════════════════════════════════════
# Long-Term Memory (persistent JSON store)
# ════════════════════════════════════════════════════════════════════════════════
class LongTermMemory:
    """
    Persistent key-value store backed by a JSON file.
    Stores: user preferences, past decisions, SKU notes, adaptation params.
    """

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self):
        if LT_MEMORY_FILE.exists():
            with open(LT_MEMORY_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {
                "sku_notes"         : {},
                "past_recommendations": [],
                "user_preferences"  : {},
                "created_at"        : datetime.now().isoformat(),
            }
            self._save()

    def _save(self):
        with open(LT_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def add_recommendation(self, rec: dict):
        """Log a past recommendation (capped at 200 entries)."""
        recs = self._data.setdefault("past_recommendations", [])
        recs.append({**rec, "logged_at": datetime.now().isoformat()})
        if len(recs) > 200:
            recs.pop(0)
        self._save()

    def add_sku_note(self, sku_id: str, note: str):
        self._data.setdefault("sku_notes", {})[sku_id] = note
        self._save()

    def get_sku_note(self, sku_id: str) -> str | None:
        return self._data.get("sku_notes", {}).get(sku_id)


# ════════════════════════════════════════════════════════════════════════════════
# Adaptation Parameters (feedback-driven behavioural tuning)
# ════════════════════════════════════════════════════════════════════════════════
class AdaptationMemory:
    """
    Tracks user feedback on recommendations and adjusts agent behaviour.
    Phase 7: Adaptive Behaviour implementation.
    """

    _DEFAULTS = {
        "service_level_override" : {},   # sku_id → float
        "safety_stock_multiplier": 1.0,  # global multiplier
        "feedback_history"       : [],
        "created_at"             : None,
    }

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self):
        if ADAPTATION_FILE.exists():
            with open(ADAPTATION_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {**self._DEFAULTS,
                          "created_at": datetime.now().isoformat()}
            self._save()

    def _save(self):
        with open(ADAPTATION_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def record_feedback(self, sku_id: str, was_helpful: bool,
                        comment: str = "", recommendation_qty: int = 0):
        """Record user feedback on a recommendation."""
        entry = {
            "sku_id"           : sku_id,
            "was_helpful"      : was_helpful,
            "comment"          : comment,
            "recommendation_qty": recommendation_qty,
            "timestamp"        : datetime.now().isoformat(),
        }
        self._data.setdefault("feedback_history", []).append(entry)

        # ── Adapt safety stock multiplier based on feedback trend ─────────────
        recent = self._data["feedback_history"][-20:]  # last 20 feedbacks
        if len(recent) >= 5:
            negative_rate = sum(1 for r in recent if not r["was_helpful"]) / len(recent)
            if negative_rate > 0.40:
                # Users find recommendations too low → increase safety stock
                self._data["safety_stock_multiplier"] = min(
                    1.5, self._data["safety_stock_multiplier"] + 0.05
                )
            elif negative_rate < 0.10:
                # Users satisfied → gradually normalise
                self._data["safety_stock_multiplier"] = max(
                    1.0, self._data["safety_stock_multiplier"] - 0.02
                )

        self._save()

    def get_safety_stock_multiplier(self) -> float:
        return self._data.get("safety_stock_multiplier", 1.0)

    def get_service_level(self, sku_id: str, default: float = 0.95) -> float:
        return self._data.get("service_level_override", {}).get(sku_id, default)

    def set_service_level(self, sku_id: str, service_level: float):
        self._data.setdefault("service_level_override", {})[sku_id] = service_level
        self._save()

    def get_feedback_summary(self) -> dict:
        history = self._data.get("feedback_history", [])
        if not history:
            return {"total": 0, "helpful_pct": 0, "multiplier": 1.0}
        helpful = sum(1 for r in history if r["was_helpful"])
        return {
            "total"             : len(history),
            "helpful_count"     : helpful,
            "helpful_pct"       : round(helpful / len(history) * 100, 1),
            "safety_stock_mult" : self._data.get("safety_stock_multiplier", 1.0),
        }
