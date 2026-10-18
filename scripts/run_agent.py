"""
scripts/run_agent.py
=====================
Main entry point — interactive conversation mode and demo.

Usage:
    python scripts/run_agent.py              Interactive mode
    python scripts/run_agent.py --demo       Run 5 preset demo interactions
    python scripts/run_agent.py --health     Health check
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.console import Console

from deployment.config import PROJECT_NAME, PROJECT_VERSION, TEAM, LLM_MODE
from agent.core_agent import OrchestratorAgent

# ── Windows-safe Rich console ─────────────────────────────────────────────────
import io
def get_console() -> Console:
    if sys.platform == "win32":
        try:
            utf8_stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
            )
            return Console(file=utf8_stdout, force_terminal=True, highlight=False)
        except AttributeError:
            pass
    return Console()

console = get_console()

BANNER = f"""
╔══════════════════════════════════════════════════════════════════╗
║  ARIS — Automated Replenishment Intelligence System             ║
║  Version {PROJECT_VERSION}  |  {TEAM}              ║
║  LLM Mode: {LLM_MODE:<8s} |  Safety-First Design                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

DEMO_INTERACTIONS = [
    {
        "label": "1 — Full Replenishment Check",
        "query": "Does SKU-008 (AA Batteries) need reordering? Show me the full analysis.",
        "purpose": "Inventory check + ROP + EOQ + supplier lead time + confidence score",
    },
    {
        "label": "2 — Supplier Delay Recording",
        "query": (
            "Record that SKU-004 arrived 5 days late from SUP-B. "
            "Order date 2024-04-01, expected 2024-04-11, "
            "actual 2024-04-16. Reason: Port congestion causing shipment hold."
        ),
        "purpose": "Feedback recording + lead time adjustment + reliability update",
    },
    {
        "label": "3 — Supplier Performance",
        "query": "How has supplier SUP-B been performing over the last 90 days?",
        "purpose": "Supplier performance analysis + on-time rate + action recommendation",
    },
    {
        "label": "4 — Safety Refusal",
        "query": "Please execute a purchase order for 500 units of SKU-001 right now.",
        "purpose": "Safety refusal — agent declines to execute orders directly",
    },
    {
        "label": "5 — Full Warehouse Scan",
        "query": "Which SKUs across the entire warehouse are below their reorder point?",
        "purpose": "All-SKU scan + batch recommendations + confidence per SKU",
    },
]


def run_demo(agent):
    console.print("\n[bold cyan]═══ DEMO MODE — 5 Automated Interactions ═══[/bold cyan]\n")
    for demo in DEMO_INTERACTIONS:
        console.print(Panel(
            f"[bold]Demo {demo['label']}[/bold]\n[dim]{demo['purpose']}[/dim]",
            border_style="blue"
        ))
        console.print(f"[bold cyan]USER:[/bold cyan] {demo['query']}\n")
        response = agent.run(demo["query"])
        border = "green" if not response.escalated else "yellow"
        console.print(Panel(
            response.answer,
            title=(f"ARIS | Confidence: {response.confidence:.0%} | "
                   f"Latency: {response.latency_ms}ms | "
                   f"Escalated: {'YES ⚠' if response.escalated else 'No'}"),
            border_style=border,
        ))
        console.print()
    console.print("[bold green]✓ All 5 demo interactions complete.[/bold green]\n")


def run_health_check():
    from tools.tool_registry import TOOL_REGISTRY
    from deployment.config import DATA_DIR, KNOWLEDGE_RAW_DIR

    checks = []
    for f in ["sales_data.csv", "inventory_data.csv", "supplier_data.csv", "supplier_feedback.csv"]:
        ok = (DATA_DIR / f).exists()
        checks.append((f"data/{f}", ok))

    for f in ["inventory_policy.txt", "replenishment_rules.txt", "supplier_guidelines.txt"]:
        ok = (KNOWLEDGE_RAW_DIR / f).exists()
        checks.append((f"knowledge/raw/{f}", ok))

    checks.append((f"Tool registry ({len(TOOL_REGISTRY)} tools)", len(TOOL_REGISTRY) == 11))

    table = Table(title="Health Check", show_lines=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status")

    all_ok = True
    for name, ok in checks:
        table.add_row(name, "[green]✓ OK[/green]" if ok else "[red]✗ MISSING[/red]")
        if not ok:
            all_ok = False

    console.print(table)
    if all_ok:
        console.print("\n[bold green]All systems healthy. Ready to run.[/bold green]")
    else:
        console.print("\n[bold red]Some components missing! Run: python scripts/ingest_documents.py[/bold red]")
    return all_ok


def run_interactive(agent):
    console.print(
        "[dim]Type your inventory question below. "
        "Type 'quit' or 'exit' to leave.[/dim]\n"
    )
    while True:
        try:
            query = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            break
        if query.strip().lower() in ("quit", "exit", "q", "bye"):
            console.print("[dim]Goodbye! 👋[/dim]")
            break
        if not query.strip():
            continue
        response = agent.run(query)
        border = "green" if not response.escalated else "yellow"
        console.print(Panel(
            response.answer,
            title=(f"ARIS | Confidence: {response.confidence:.0%} | "
                   f"Latency: {response.latency_ms}ms"),
            border_style=border,
        ))
        console.print()


def main():
    parser = argparse.ArgumentParser(description="ARIS — Stock Replenishment Agent")
    parser.add_argument("--demo", action="store_true", help="Run 5 demo interactions")
    parser.add_argument("--health", action="store_true", help="Health check only")
    args = parser.parse_args()

    console.print(BANNER)

    if args.health:
        run_health_check()
        return

    console.print("[dim]Initializing agent...[/dim]")
    agent = OrchestratorAgent()
    console.print("[green]✓ Agent ready.[/green]\n")

    if args.demo:
        run_demo(agent)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
