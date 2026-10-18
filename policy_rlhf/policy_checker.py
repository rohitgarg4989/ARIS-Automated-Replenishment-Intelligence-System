"""
policy_rlhf/policy_checker.py
==============================
Policy compliance checker for agent recommendations.
Ensures all outputs conform to business rules and safety policies.
"""

import json
from pathlib import Path
from deployment.config import POLICY_DIR


class PolicyChecker:
    """
    Validates agent recommendations against defined business policies.
    """

    def __init__(self):
        self._policies = self._load_policies()

    def _load_policies(self) -> dict:
        """Load policy definitions from JSON file."""
        policy_file = POLICY_DIR / "policy.json"
        if policy_file.exists():
            with open(policy_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._default_policies()

    def _default_policies(self) -> dict:
        """Return default policy configuration."""
        return {
            "max_auto_approve_value": 5000,
            "max_manager_approve_value": 50000,
            "min_confidence_threshold": 0.60,
            "min_reliability_score": 0.75,
            "max_safety_stock_multiplier": 1.5,
            "escalation_triggers": [
                "order_value_exceeds_limit",
                "low_confidence",
                "stockout_detected",
                "high_demand_uncertainty",
            ],
        }

    def check_recommendation(self, recommendation: dict) -> dict:
        """
        Validate a recommendation against policies.
        Returns compliance status and any violations.
        """
        violations = []

        order_value = recommendation.get("order_value_usd", 0)
        confidence = recommendation.get("confidence_score", 1.0)
        health = recommendation.get("health_status", "")

        if confidence < self._policies.get("min_confidence_threshold", 0.60):
            violations.append({
                "rule": "min_confidence",
                "message": f"Confidence {confidence:.0%} below threshold",
                "severity": "high",
            })

        if order_value > self._policies.get("max_manager_approve_value", 50000):
            violations.append({
                "rule": "max_order_value",
                "message": f"Order value ${order_value:,.2f} requires CFO approval",
                "severity": "high",
            })

        if health == "STOCKOUT":
            violations.append({
                "rule": "stockout_escalation",
                "message": "Stockout detected — immediate human review required",
                "severity": "critical",
            })

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "approval_level": self._get_approval_level(order_value),
        }

    def _get_approval_level(self, order_value: float) -> str:
        if order_value < self._policies.get("max_auto_approve_value", 5000):
            return "auto_approved"
        elif order_value <= self._policies.get("max_manager_approve_value", 50000):
            return "inventory_manager"
        else:
            return "cfo_sign_off"
