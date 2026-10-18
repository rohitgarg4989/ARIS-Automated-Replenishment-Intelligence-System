"""
evaluation/metrics.py
======================
Metrics computation for agent evaluation.
"""

from typing import Any


def compute_metrics(results: list[dict]) -> dict:
    """
    Compute aggregate metrics from evaluation results.
    """
    if not results:
        return {"total": 0, "pass_rate": 0.0}

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    avg_conf = sum(r.get("confidence", 0) for r in results) / total
    avg_lat = sum(r.get("latency_ms", 0) for r in results) / total
    avg_kw = sum(r.get("kw_score", 0) for r in results) / total

    # Category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r.get("passed"):
            categories[cat]["passed"] += 1

    for cat in categories:
        c = categories[cat]
        c["pass_rate"] = round(c["passed"] / c["total"] * 100, 1) if c["total"] else 0

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total * 100, 1),
        "avg_confidence": round(avg_conf, 3),
        "avg_latency_ms": round(avg_lat, 1),
        "avg_keyword_score": round(avg_kw, 3),
        "by_category": categories,
    }
