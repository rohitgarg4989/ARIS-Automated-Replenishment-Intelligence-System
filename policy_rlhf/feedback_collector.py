"""
policy_rlhf/feedback_collector.py
==================================
Collects and stores user feedback on agent recommendations.
Used for RLHF-style adaptive behaviour tuning.
"""

import json
from datetime import datetime
from pathlib import Path
from deployment.config import STORE_DIR


FEEDBACK_STORE_FILE = STORE_DIR / "feedback_store.json"


class FeedbackCollector:
    """
    Collects user feedback on agent recommendations for RLHF.
    """

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if FEEDBACK_STORE_FILE.exists():
            with open(FEEDBACK_STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"feedback_entries": [], "created_at": datetime.now().isoformat()}

    def _save(self):
        with open(FEEDBACK_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def collect(
        self,
        sku_id: str,
        recommendation_id: str,
        was_helpful: bool,
        rating: int = 0,
        comment: str = "",
    ) -> dict:
        """
        Record user feedback on a recommendation.
        """
        entry = {
            "sku_id": sku_id,
            "recommendation_id": recommendation_id,
            "was_helpful": was_helpful,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        }
        self._data.setdefault("feedback_entries", []).append(entry)
        self._save()
        return {"status": "recorded", "entry_id": len(self._data["feedback_entries"])}

    def get_summary(self) -> dict:
        """Get feedback summary statistics."""
        entries = self._data.get("feedback_entries", [])
        if not entries:
            return {"total": 0, "helpful_pct": 0.0, "avg_rating": 0.0}

        helpful = sum(1 for e in entries if e.get("was_helpful"))
        ratings = [e.get("rating", 0) for e in entries if e.get("rating", 0) > 0]

        return {
            "total": len(entries),
            "helpful_count": helpful,
            "helpful_pct": round(helpful / len(entries) * 100, 1),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        }

    def get_recent(self, n: int = 20) -> list[dict]:
        """Get the most recent feedback entries."""
        return self._data.get("feedback_entries", [])[-n:]
