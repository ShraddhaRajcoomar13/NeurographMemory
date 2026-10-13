
# Neurograph

> A persistent, weighted knowledge graph that serves as **long-term memory for AI agents**.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![spaCy](https://img.shields.io/badge/spaCy-3.8-09A3D5)](https://spacy.io/)
[![NetworkX](https://img.shields.io/badge/networkx-3.7-orange)](https://networkx.org/)
[![SQLite](https://img.shields.io/badge/sqlite-3-003B57)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![For AI Agents](https://img.shields.io/badge/for-AI%20agents-purple)](https://github.com/)
[![Local-first](https://img.shields.io/badge/local--first-yes-success)](https://github.com/)

**Neurograph** gives agents a memory that behaves like human recall:
facts reinforce with repetition, concepts consolidate across sessions,
and a weighted graph lets the agent ask *"what do I know, and how strongly?"*

Feed it sentences. It extracts entities and relations, merges them into a
persistent graph, and scores every edge by how often it's been observed.

---

## Table of Contents

- [Why Agent Memory Needs This](#why-agent-memory-needs-this)
- [What It Does](#what-it-does)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Using Neurograph as Agent Memory](#using-neurograph-as-agent-memory)
- [How It Works](#how-it-works)
- [Database Schema](#database-schema)
- [Visual Encoding](#visual-encoding)
- [Inspecting the Database](#inspecting-the-database)
- [Example Graph](#example-graph)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Dependencies](#dependencies)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Why Agent Memory Needs This

Most LLM memory systems are one of these:

| Approach | Limitation |
|----------|------------|
| **Chat log / RAG** | Flat, no structure, no reinforcement |
| **Vector store** | Similarity ≠ structure; can't traverse relations |
| **Key-value store** | No relationships, no weighting |
| **Graph DB (Neo4j)** | Heavy, needs ops, overkill for local agents |

**Neurograph is a lightweight, structured, weighted, local-first alternative.**

- **Structured** — entities and relations, not raw text
- **Weighted** — repetition strengthens memory (like Hebbian learning)
- **Consolidating** — "cat", "cats", "the cat" become one memory node
- **Traversable** — ask "what connects to *cat*?" in one hop
- **Local** — a single SQLite file; no server, no cloud, no latency
- **Embeddable** — drop it into any Python agent as a memory module

---

## What It Does

Given a sentence like:

> *The scrawny cat ate the fish that the fisherman had discarded.*

The script produces a directed graph where:

- 🟠 **Orange nodes** = entities (nouns, proper nouns, pronouns)
- 🔵 **Blue nodes** = attributes (adjectives, determiners, numerals)
- ➡️ **Edges** = relations (verbs, prepositions, attribute links)
- **Edge labels** show the relation word and its **strength** score
- **Node size** scales with how often the entity appears
- **Edge width** scales with how often the relation repeats

Every sentence you type is stored in SQLite and appended to the graph.
Run the script again tomorrow — your graph is still there.

---

## Features

| Feature | Description |
|---------|-------------|
| **Persistent storage** | Sentences, nodes, and edges are saved to `sentence_graph.db` |
| **Merged nodes** | "cat", "cats", "the cat" collapse into a single node |
| **Mention counter** | Each node tracks how many times it's been seen |
| **Strength score** | Each edge tracks how many times the relation appeared |
| **Attribute sub-nodes** | Adjectives, determiners, and numerals become child nodes |
| **Auto-migration** | Old database schemas are detected and rebuilt |
| **Interactive loop** | Type sentences one at a time; graph redraws after each |
| **Command interface** | `show`, `draw`, `clear`, `quit` |

---

## Installation

### 1. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# or
source .venv/bin/activate          # macOS / Linux
```

### 2. Install dependencies

```bash
pip install spacy networkx matplotlib
python -m spacy download en_core_web_sm
```

### 3. Run

```bash
python test.py
```

---

## Usage

```
Sentence Graph — persistent, merged, weighted
Commands: 'show' | 'draw' | 'clear' | 'quit'

Enter a sentence (or command): The scrawny cat ate the fish.
  Saved sentence #1  |  2 nodes, 3 edges in this sentence
  Totals: 1 sentences, 4 nodes, 4 edges
  [graph window opens]

Enter a sentence (or command): The cat ate the fish.
  Saved sentence #2  |  2 nodes, 2 edges in this sentence
  Totals: 2 sentences, 4 nodes, 4 edges
  [graph updates: cat→fish strength now 2]

Enter a sentence (or command): show
  [1] 2026-10-13T10:22:01+00:00  The scrawny cat ate the fish.
  [2] 2026-10-13T10:22:15+00:00  The cat ate the fish.

Enter a sentence (or command): draw
  [redraws the accumulated graph without adding data]

Enter a sentence (or command): clear
  Cleared sentence_graph.db

Enter a sentence (or command): quit
Goodbye.
```

---

## Commands

| Command | Action |
|---------|--------|
| *(any text)* | Parse as a sentence and append to the graph |
| `show` | List all stored sentences with IDs and timestamps |
| `draw` | Redraw the accumulated graph |
| `clear` | Delete the database and start fresh |
| `quit` / `exit` / `q` | Exit the program |

---

## Using Neurograph as Agent Memory

### 1. Write memories

Every sentence the agent observes becomes a memory:

```python
from neurograph import MemoryGraph

mem = MemoryGraph("agent_memory.db")

mem.remember("The user's name is Shraddha.")
mem.remember("Shraddha is building a project called Neurograph.")
mem.remember("Neurograph uses spaCy for parsing.")
mem.remember("Neurograph stores data in SQLite.")
```

### 2. Recall by entity

```python
mem.recall("Shraddha")
# [
#   ("name", "is", 1),
#   ("building", "Neurograph", 1),
# ]

mem.recall("Neurograph")
# [
#   ("uses", "spaCy", 1),
#   ("stores", "SQLite", 1),
# ]
```

### 3. Reinforcement

Repeat a fact and the edge gets stronger:

```python
mem.remember("The user's name is Shraddha.")
mem.remember("The user's name is Shraddha.")

mem.strength("user", "name", "Shraddha")  # → 3
```

Low-strength edges can be pruned; high-strength edges become "core facts."

### 4. Inject into an LLM prompt

```python
context = mem.summarize("Shraddha", depth=1, top_k=5)
prompt = f"""
You are an assistant with the following memories about the user:

{context}

User: What am I working on?
Assistant:
"""
```

The graph becomes a **structured, compressed context** — far more
token-efficient than dumping raw chat history.

### 5. Fits into an agent loop

```
   ┌──────────────────────────────────────────────┐
   │                  LLM Agent                   │
   │                                              │
   │   User turn ──► LLM ──► Response             │
   │       │                     ▲                │
   │       │ extract facts       │ inject context │
   │       ▼                     │                │
   │  ┌──────────────────────────────────────┐    │
   │  │          Neurograph                  │    │
   │  │  ┌────────┐    ┌────────┐            │    │
   │  │  │ nodes  │◄──►│ edges  │  SQLite    │    │
   │  │  └────────┘    └────────┘            │    │
   │  │   entities      relations            │    │
   │  │   attributes    strengths            │    │
   │  └──────────────────────────────────────┘    │
   └──────────────────────────────────────────────┘
```

---

## How It Works

### Pipeline

```
input sentence
    │
    ▼
spaCy NLP  ──► tokens, POS tags, dependencies
    │
    ▼
Entity extraction     (NOUN, PROPN, PRON)
Attribute extraction  (ADJ, DET, NUM)
Relation extraction   (VERB, ADP, amod)
    │
    ▼
Graph construction (networkx)
    │
    ▼
SQLite upsert  ──► nodes (mentions++)
                └► edges (strength++)
    │
    ▼
Reload full graph
    │
    ▼
matplotlib render
```

### Node Keys

Nodes are keyed by **lemma + type**, so duplicates merge automatically:

| Surface form | Node key |
|--------------|----------|
| cat, cats, the cat | `cat::ENT` |
| scrawny | `scrawny::ADJ` |
| the | `the::DET` |
| fisherman | `fisherman::ENT` |

### Edge Keys

Edges are keyed by `(source_key, target_key, label)`. If the same relation
appears in a new sentence, the `strength` column increments:

```
Run 1:  cat --eat--> fish         strength = 1
Run 2:  cat --eat--> fish         strength = 2
Run 3:  cat --eat--> fish         strength = 3
```

---

## Database Schema

### `sentences`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| text | TEXT | Raw sentence |
| created_at | TEXT | ISO 8601 UTC timestamp |

### `nodes`

| Column | Type | Notes |
|--------|------|-------|
| node_key | TEXT | Primary key, e.g. `cat::ENT` |
| label | TEXT | Surface form, e.g. `cat` |
| pos | TEXT | spaCy POS (NOUN, ADJ, DET…) |
| kind | TEXT | `entity` or `attribute` |
| first_seen | TEXT | ISO 8601 UTC |
| last_seen | TEXT | ISO 8601 UTC |
| mentions | INTEGER | Incremented on each sighting |

### `edges`

| Column | Type | Notes |
|--------|------|-------|
| source_key | TEXT | FK to nodes.node_key |
| target_key | TEXT | FK to nodes.node_key |
| label | TEXT | Relation word, e.g. `eat` |
| relation | TEXT | `verb`, `prep`, `attribute` |
| pos | TEXT | POS of the relation word |
| strength | INTEGER | Incremented on each repeat |
| first_seen | TEXT | ISO 8601 UTC |
| last_seen | TEXT | ISO 8601 UTC |

Composite primary key: `(source_key, target_key, label)`

---

## Visual Encoding

| Visual | Meaning |
|--------|---------|
| 🟠 Orange node | Entity (noun / pronoun) |
| 🔵 Blue node | Attribute (adj / det / num) |
| Node size | Number of mentions |
| Edge width | Relation strength |
| Edge label | `relation (strength)` |

---

## Inspecting the Database

### Via sqlite3 CLI

```bash
sqlite3 sentence_graph.db
sqlite> .tables
sqlite> SELECT * FROM sentences;
sqlite> SELECT * FROM nodes ORDER BY mentions DESC;
sqlite> SELECT * FROM edges ORDER BY strength DESC;
sqlite> .quit
```

### Via Python

```python
import sqlite3, pandas as pd
con = sqlite3.connect("sentence_graph.db")
print(pd.read_sql("SELECT * FROM edges ORDER BY strength DESC", con))
```

### Top relations

```sql
SELECT source_key, label, target_key, strength
FROM edges
ORDER BY strength DESC
LIMIT 10;
```

---

## Example Graph

Input:

```
The scrawny cat that had been abandoned quietly ate the fish that the fisherman had discarded.
```

Produces:

```
        scrawny              abandoned
           ▲                    ▲
           │ is                 │ relcl
           │                    │
 the ───► cat ─── eat ───► fish ◄─── the
                       ▲
                       │ discard
                       │
                   fisherman
```

Then feeding:

```
The cat ate another fish.
```

Boosts `cat --eat--> fish` from strength 1 → 2 and adds `another` as a
new blue attribute node.

---

## Project Structure

```
Neurograph/
├── test.py               # main script
├── sentence_graph.db     # SQLite database (auto-created)
├── README.md             # this file
├── requirements.txt      # dependencies (optional)
└── .venv/                # virtual environment (optional)
```

---

## Troubleshooting

### `sqlite3.OperationalError: table nodes has no column named kind`

Your DB was created with an older script version. Either:

- Delete the DB:
  ```powershell
  Remove-Item sentence_graph.db
  ```
- Or use the migration-aware `init_db` that drops and rebuilds
  incompatible tables automatically.

### `ON CONFLICT clause does not match any PRIMARY KEY`

Same cause — the old `nodes` table had a `UNIQUE(node_key, sentence_id)`
constraint instead of `node_key PRIMARY KEY`. Delete the DB and rerun.

### `DeprecationWarning: datetime.datetime.utcnow()`

Use `datetime.now(timezone.utc)` instead:

```python
from datetime import datetime, timezone
datetime.now(timezone.utc).isoformat()
```

### `Can't find model 'en_core_web_sm'`

```bash
python -m spacy download en_core_web_sm
```

### Graph window doesn't appear

`matplotlib` uses a GUI backend. On headless servers, add before importing pyplot:

```python
import matplotlib
matplotlib.use("Agg")   # renders to file instead of screen
```

Then save instead of show:

```python
plt.savefig("graph.png", dpi=150, bbox_inches="tight")
```

---

## Known Limitations

- **No coreference resolution** — "it" and "the fish" are different nodes
- **Pronouns create their own nodes** — "I", "you", "he" are treated as entities
- **Wh-words filtered separately** — `that`, `which`, `who` used as relative
  pronouns are excluded from entity nodes
- **English only** — model is `en_core_web_sm`
- **Directional edges only** — passive voice reverses arrow direction but
  isn't marked as passive
- **No cross-sentence entity linking beyond lemma** — "the fisherman" and
  "a fisherman" merge, but "he" does not
- **No decay or forgetting** — edges only grow; they don't fade over time
- **No temporal reasoning** — the graph has no notion of "when" a fact was true

---

## Roadmap

- [ ] Coreference resolution (spaCy `coreferee` or `fastcoref`)
- [ ] Interactive HTML graph via `pyvis`
- [ ] Per-sentence subgraph filter (`draw 3`)
- [ ] Attribute type refinement (separate colors for DET, NUM, POSS)
- [ ] Sentence similarity search (embed & query)
- [ ] Export to GraphML / JSON / Cypher
- [ ] Web UI (FastAPI + D3.js)
- [ ] Batch mode: `python test.py --file sentences.txt`
- [ ] `MemoryGraph` class with `remember()` / `recall()` / `summarize()` / `forget()`
- [ ] Edge decay / forgetting mechanism for pruning stale memories
- [ ] Multi-hop traversal queries (2-hop, 3-hop recall)
- [ ] LangChain / LlamaIndex memory adapter
- [ ] Incremental embedding for semantic node linking

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `spacy` + `en_core_web_sm` | Tokenization, POS tagging, dependency parsing |
| `networkx` | In-memory directed graph |
| `matplotlib` | Graph rendering |
| `sqlite3` | Persistent storage (Python stdlib) |

---

## License

MIT — do whatever you want.

---

## Acknowledgements

Built on top of spaCy's `en_core_web_sm` pipeline. Graph layout by
NetworkX spring layout. Inspired by classic SVO extraction, Hebbian
learning, and knowledge-graph construction patterns for agent memory.

---

*Neurograph is not a chatbot, not a vector database, and not a
knowledge-graph platform. It is a small, embeddable memory primitive
for agents — the hippocampus that stores structured, weighted,
persistent facts about the world the agent has encountered.*
```
