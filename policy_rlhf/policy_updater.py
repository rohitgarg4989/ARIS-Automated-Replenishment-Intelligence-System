"""
policy_rlhf/policy_updater.py
===============================
Updates agent policies and parameters based on collected feedback.
Implements the RLHF feedback loop for adaptive behaviour.
"""

import json
from datetime import datetime
from pathlib import Path
from deployment.config import POLICY_DIR, STORE_DIR


class PolicyUpdater:
    """
    Updates agent policies based on feedback trends.
    Adjusts safety stock multipliers, service levels, and thresholds.
    """

    def __init__(self):
        self._adaptation_file = STORE_DIR / "adaptation_params.json"
        self._policy_file = POLICY_DIR / "policy.json"

    def update_from_feedback(self, feedback_summary: dict) -> dict:
        """
        Adjust agent parameters based on feedback trends.
        """
        total = feedback_summary.get("total", 0)
        helpful_pct = feedback_summary.get("helpful_pct", 100.0)
        changes = []

        if total < 5:
            return {"changes": [], "message": "Insufficient feedback for policy update."}

        # Load current adaptation params
        adaptation = self._load_adaptation()

        # Adjust safety stock multiplier
        if helpful_pct < 60:
            old_mult = adaptation.get("safety_stock_multiplier", 1.0)
            new_mult = min(1.5, old_mult + 0.05)
            adaptation["safety_stock_multiplier"] = new_mult
            changes.append(f"Safety stock multiplier: {old_mult:.2f} → {new_mult:.2f}")

        elif helpful_pct > 90:
            old_mult = adaptation.get("safety_stock_multiplier", 1.0)
            new_mult = max(1.0, old_mult - 0.02)
            adaptation["safety_stock_multiplier"] = new_mult
            changes.append(f"Safety stock multiplier: {old_mult:.2f} → {new_mult:.2f}")

        adaptation["last_updated"] = datetime.now().isoformat()
        self._save_adaptation(adaptation)

        return {
            "changes": changes,
            "new_multiplier": adaptation.get("safety_stock_multiplier", 1.0),
            "message": f"Policy updated based on {total} feedback entries.",
        }

    def _load_adaptation(self) -> dict:
        if self._adaptation_file.exists():
            with open(self._adaptation_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "safety_stock_multiplier": 1.0,
            "service_level_override": {},
            "feedback_history": [],
            "created_at": datetime.now().isoformat(),
        }

    def _save_adaptation(self, data: dict):
        with open(self._adaptation_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
