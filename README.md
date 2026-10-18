# ARIS — Automated Replenishment Intelligence System

> AI-powered stock reordering agent that tells you what to reorder, how much, and when.

**Framework:** LangChain (Track A) | Python 3.11+

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure (optional — works without API key)
copy .env.example .env
# Edit .env if you have an OpenAI API key; otherwise MockLLM is used

# 3. Run the agent
python main.py            # Interactive mode
python main.py --demo     # 5 automated demo interactions
python main.py --health   # Verify all systems working
```

---

## What It Does

Ask plain-English questions about your warehouse inventory:

```
You: Does SKU-008 need reordering?
ARIS: ⚠ Reorder required for SKU-008 (AA Batteries).
      Current Stock: 295 | ROP: 319 | EOQ: 760
      Supplier: TechParts Global (10 days lead time)
      Confidence: 90%
```

### Capabilities
- Reorder point (ROP) calculation with dynamic demand analysis
- Economic Order Quantity (EOQ) optimization
- Safety stock computation with configurable service levels
- Supplier performance tracking and delay monitoring
- Demand spike detection
- Full warehouse scan across all 15 SKUs
- Safety refusals for dangerous requests (delete, execute, bypass)
- Human-in-the-loop escalation for high-value or low-confidence decisions

---

## Folder Structure

```
ARIS/
├── main.py              ← Single entry point
├── config.py            ← All settings
├── requirements.txt
├── .env.example
├── .gitignore
│
├── core/                ← Agent brain
│   ├── orchestrator.py  ← Perceive→Plan→Act→Validate→HITL loop
│   ├── llm_client.py   ← OpenAI + MockLLM interface
│   ├── memory.py        ← Short-term, Long-term, Adaptation memory
│   ├── retriever.py     ← RAG knowledge retrieval (TF-IDF)
│   └── console.py       ← Cross-platform terminal output
│
├── tools/               ← 11 self-defined tools
│   ├── schemas.py       ← JSON Schema definitions
│   ├── sales.py         ← Sales velocity, forecast, spike detection
│   ├── inventory.py     ← ROP, EOQ, safety stock, reorder recommendation
│   └── supplier.py      ← Lead time, feedback, performance
│
├── prompts/
│   └── system.py        ← System prompts (3 variants)
│
├── data/                ← CSV datasets + knowledge base
│   ├── generate_data.py ← One-time sample data generator
│   ├── sales_data.csv
│   ├── inventory_data.csv
│   ├── supplier_data.csv
│   ├── supplier_feedback.csv
│   └── knowledge_base/
│       ├── inventory_policy.txt
│       ├── replenishment_rules.txt
│       └── supplier_guidelines.txt
│
├── store/               ← Persistent memory (auto-created)
└── logs/                ← Structured logs (auto-created)
```

---

## Architecture

See [ARCHITECTURE.md](../ARCHITECTURE.md) for full details. In brief:

```
User Query → PERCEIVE (intent + entities + safety check)
           → PLAN (route to tools + retrieve KB context)
           → ACT (execute tools, compute formulas)
           → VALIDATE (confidence scoring + HITL check)
           → RESPOND (format answer + save to memory)
```

---

## Safety Features

| Feature | Description |
|---------|-------------|
| Unsafe query blocking | 12 regex patterns refuse delete/execute/bypass requests |
| Confidence scoring | 0-100% on every recommendation |
| HITL escalation | Auto-triggers for conf < 60%, orders > $50K, stockouts |
| PII masking | Emails appear as `***@***.com` in all outputs |
| Scope enforcement | Out-of-domain queries get polite refusal |
