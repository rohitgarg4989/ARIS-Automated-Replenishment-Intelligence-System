"""
monitoring/langfuse_logger.py
==============================
Langfuse integration for logging agent events and metrics.
Provides structured logging for analysis and debugging.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from deployment.config import LOG_DIR

logger = logging.getLogger("LangfuseLogger")


class LangfuseLogger:
    """
    Structured event logger for ARIS agent operations.
    Logs to local files; can be extended with Langfuse API integration.
    """

    def __init__(self):
        self._mcp_log = LOG_DIR / "mcp_events.log"
        self._policy_log = LOG_DIR / "policy_change.log"
        self._error_log = LOG_DIR / "errors.log"
        logger.info("Langfuse logger initialised (local mode)")

    def log_event(self, event_type: str, data: dict):
        """Log a structured event."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        if event_type == "mcp":
            self._write(self._mcp_log, event)
        elif event_type == "policy_change":
            self._write(self._policy_log, event)
        elif event_type == "error":
            self._write(self._error_log, event)
        else:
            self._write(self._mcp_log, event)

    def log_error(self, error: str, context: dict = None):
        """Log an error event."""
        self.log_event("error", {
            "error": error,
            "context": context or {},
        })

    def log_tool_call(self, tool_name: str, args: dict, result: dict):
        """Log a tool execution event."""
        self.log_event("tool_call", {
            "tool": tool_name,
            "arguments": args,
            "status": result.get("status", "unknown"),
        })

    def _write(self, path: Path, event: dict):
        """Write event to log file."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
