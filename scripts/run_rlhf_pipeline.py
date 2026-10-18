"""
scripts/run_rlhf_pipeline.py
==============================
Run the RLHF feedback pipeline — collect, analyse, and update policies.

Usage: python scripts/run_rlhf_pipeline.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policy_rlhf.feedback_collector import FeedbackCollector
from policy_rlhf.policy_updater import PolicyUpdater


def main():
    print("\n🔄 RLHF Pipeline — Feedback Analysis & Policy Update\n")

    collector = FeedbackCollector()
    updater = PolicyUpdater()

    # Get feedback summary
    summary = collector.get_summary()
    print(f"  Total feedback entries : {summary['total']}")
    print(f"  Helpful percentage     : {summary['helpful_pct']}%")
    print(f"  Avg rating            : {summary['avg_rating']}")

    if summary["total"] == 0:
        print("\n  No feedback collected yet. Run the agent and provide feedback first.")
        print("  Use agent.provide_feedback(sku_id, was_helpful, comment) to record feedback.")
        return

    # Update policies based on feedback
    result = updater.update_from_feedback(summary)
    print(f"\n  {result['message']}")

    if result.get("changes"):
        print("  Changes applied:")
        for change in result["changes"]:
            print(f"    • {change}")
    else:
        print("  No policy changes needed.")

    print(f"  Current multiplier: {result.get('new_multiplier', 1.0):.2f}×")
    print(f"\n✅ RLHF pipeline complete.\n")


if __name__ == "__main__":
    main()
