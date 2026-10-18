"""
monitoring/langsmith_tracer.py
===============================
LangSmith integration for tracing agent interactions.
Provides observability into the agent's reasoning chain.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from deployment.config import LOG_DIR

logger = logging.getLogger("LangSmithTracer")


class LangSmithTracer:
    """
    Traces agent interactions for debugging and observability.
    Logs to local files; can be extended with LangSmith API integration.
    """

    def __init__(self):
        self._log_file = LOG_DIR / "interactions.log"
        self._events: list[dict] = []
        logger.info("LangSmith tracer initialised (local mode)")

    def trace_start(self, query: str, session_id: str = "") -> str:
        """Start tracing a new interaction."""
        trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        event = {
            "trace_id": trace_id,
            "session_id": session_id,
            "query": query,
            "start_time": datetime.now().isoformat(),
            "steps": [],
        }
        self._events.append(event)
        return trace_id

    def trace_step(self, trace_id: str, step_name: str, data: dict):
        """Log a step within a trace."""
        for event in self._events:
            if event["trace_id"] == trace_id:
                event["steps"].append({
                    "step": step_name,
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                })
                break

    def trace_end(self, trace_id: str, response: str, confidence: float):
        """End a trace and persist it."""
        for event in self._events:
            if event["trace_id"] == trace_id:
                event["end_time"] = datetime.now().isoformat()
                event["response_length"] = len(response)
                event["confidence"] = confidence
                self._persist(event)
                break

    def _persist(self, event: dict):
        """Append trace to log file."""
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
