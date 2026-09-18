# Product Data Quality Copilot

A LangGraph-based copilot for understanding, enhancing, quality-checking, and
running impact analysis on a product catalog (built against Tesco-style
product data: main attributes, source provenance, and weak/long-tail
attributes).

There is no external data feed - **this app is the system of record**.
Products are entered through the Streamlit UI (or `dataquality.storage`
directly) as the 3 JSON documents shown in the source data, stored in SQLite.

## Architecture

Four LangGraph subgraphs, one shared SQLite store, no shared mutable state
beyond the catalog itself:

| Subgraph | File | LLM needed? |
|---|---|---|
| Understanding (profiling) | `dataquality/graphs/understanding.py` | Only for miscategorization flagging; core profile is pure Python |
| Data Quality analysis | `dataquality/graphs/dq_analysis.py` | Only for the closing narrative; rule checks are pure Python |
| Enhancement (translate/rewrite) | `dataquality/graphs/enhancement.py` | Yes - generation + self-check |
| Impact analysis | `dataquality/graphs/impact_analysis.py` | Only for the closing narrative; the diff itself is pure Python |

`dataquality/graphs/supervisor.py` is a thin intent router for a future
free-text entrypoint; the Streamlit pages call each subgraph directly.

Everything that produces a number a PM might act on (counts, DQ scorecard,
impact diff) is deterministic Python. The LLM is only in the loop where
judgment or generation is actually required (translation, rewriting,
miscategorization judgment, narrative summaries) - and enhancement
suggestions always go through a human-approval gate before being written back.

### Data model

- **Doc 1 - `ProductMain`**: resolved/final attributes (descriptions,
  commercial hierarchy/category, per-country status, `rmsStatus`, `completeness`).
- **Doc 2 - `ProductSource`**: per-field provenance across source systems.
- **Doc 3 - `ProductAttributes`**: weak/long-tail attributes, grouped
  (`merchandising_details`, `global_identifiers`, `status.orderable/sellable`, ...).

The three are merged into one `ProductRecord` (`dataquality/catalog.py`) used
by every subgraph. Notably:

- **Active status** is `rmsStatus == "Approved"` AND at least one country is
  live (`authorised and not suspended and not deactivated`). When the two
  signals disagree, that's surfaced as its own DQ issue
  (`active_status_disagreement`) rather than silently resolved.
- **Images** are not modeled yet - none of the 3 source documents carry an
  image field, so that DQ check is deferred until a real field/feed exists.

### Impact analysis without arbitrary code execution

Letting a PM type a raw expression into a text box and `eval()` it against
the catalog is a code-injection risk. Instead, "derivation logic" is a
versioned Python module under `dataquality/derivation_rules/`, each exposing
`compute(record: ProductRecord) -> Any`. A logic change is a reviewed code
change (a new file), and the impact subgraph just imports and runs two named
versions across the catalog and diffs the results - by category and by
active status. See `active_status_v1_any_country.py` /
`active_status_v2_all_countries.py` for a worked example.

### Human-in-the-loop enhancement

`dataquality/graphs/enhancement.py` runs generation and a self-check
(back-translation + meaning-preservation scoring for translations) up to a
`langgraph.types.interrupt()`. A `SqliteSaver` checkpointer persists the
paused run under a `thread_id`, so the Streamlit review queue can approve,
edit, or reject it - potentially much later, in a separate process - by
resuming that thread. Only on approval is the product's document updated.

## Setup

```bash
uv venv
uv pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...   # optional - deterministic features work without it
```

## Run

```bash
streamlit run src/dataquality/ui/streamlit_app.py
```

Use "Add / Edit Product" -> "Fill with sample data" to load the example
Tesco-style product, then explore the other pages.

## Test

```bash
pytest
```

Tests cover catalog merging, DQ rules, and impact-analysis diffing - all
pure Python, no API key required.
