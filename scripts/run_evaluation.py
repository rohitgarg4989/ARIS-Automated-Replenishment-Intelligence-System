"""
scripts/run_evaluation.py
==========================
Run the evaluation harness against the ARIS agent.

Usage: python scripts/run_evaluation.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.core_agent import OrchestratorAgent
from evaluation.test_harness import TestHarness
from evaluation.metrics import compute_metrics


def main():
    print("\n📋 ARIS Evaluation Harness\n")

    print("Initializing agent...")
    agent = OrchestratorAgent()

    harness = TestHarness(agent=agent)
    print("Running test cases...\n")

    results = harness.run()
    out_path = harness.save_results()

    metrics = compute_metrics(results)

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Tests  : {metrics['total']}")
    print(f"  Passed       : {metrics['passed']}/{metrics['total']} ({metrics['pass_rate']}%)")
    print(f"  Avg Confidence: {metrics['avg_confidence']:.0%}")
    print(f"  Avg Latency  : {metrics['avg_latency_ms']:.0f}ms")
    print(f"  Avg KW Score : {metrics['avg_keyword_score']:.0%}")

    print(f"\nBy Category:")
    for cat, data in metrics.get("by_category", {}).items():
        print(f"  {cat}: {data['passed']}/{data['total']} ({data['pass_rate']}%)")

    print(f"\nDetailed results: {out_path}")

    # Print individual results
    print(f"\n{'ID':<8} {'Category':<18} {'Pass':<6} {'KW%':<6} {'Conf':<6} {'Latency'}")
    print("-" * 60)
    for r in results:
        status = "✓" if r["passed"] else "✗"
        print(f"{r['id']:<8} {r['category']:<18} {status:<6} "
              f"{r['kw_score']:.0%}{'':>2} {r['confidence']:.0%}{'':>2} {r['latency_ms']}ms")

    print(f"\n✅ Evaluation complete.\n")


if __name__ == "__main__":
    main()
