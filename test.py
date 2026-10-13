import spacy
import networkx as nx
import matplotlib.pyplot as plt
import sqlite3
import os
from datetime import datetime

nlp = spacy.load("en_core_web_sm")

DB_PATH = "sentence_graph.db"

# Node types
ENTITY = "entity"
ATTRIBUTE = "attribute"

# Colors
COLOR_ENTITY = "#F18F01"   # orange
COLOR_ATTRIBUTE = "#2E86AB"  # blue
COLOR_DEFAULT = "#CCCCCC"


# ============================================================
# DATABASE
# ============================================================

def init_db(db_path: str = DB_PATH):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # --- Base tables (original) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            node_key TEXT PRIMARY KEY,
            label TEXT,
            pos TEXT,
            tag TEXT,
            lemma TEXT,
            first_seen TEXT,
            last_seen TEXT,
            mentions INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            source_key TEXT NOT NULL,
            target_key TEXT NOT NULL,
            label TEXT NOT NULL,
            relation TEXT,
            pos TEXT,
            strength INTEGER DEFAULT 1,
            first_seen TEXT,
            last_seen TEXT,
            PRIMARY KEY (source_key, target_key, label)
        )
    """)

    # --- Migrations: add columns if they're missing (old DB) ---
    existing_node_cols = {row[1] for row in cur.execute("PRAGMA table_info(nodes)")}
    for col, ddl in [
        ("kind",       "ALTER TABLE nodes ADD COLUMN kind TEXT"),
        ("tag",        "ALTER TABLE nodes ADD COLUMN tag TEXT"),
        ("lemma",      "ALTER TABLE nodes ADD COLUMN lemma TEXT"),
        ("first_seen", "ALTER TABLE nodes ADD COLUMN first_seen TEXT"),
        ("last_seen",  "ALTER TABLE nodes ADD COLUMN last_seen TEXT"),
        ("mentions",   "ALTER TABLE nodes ADD COLUMN mentions INTEGER DEFAULT 1"),
    ]:
        if col not in existing_node_cols:
            print(f"  [migrate] adding nodes.{col}")
            cur.execute(ddl)

    existing_edge_cols = {row[1] for row in cur.execute("PRAGMA table_info(edges)")}
    for col, ddl in [
        ("strength",   "ALTER TABLE edges ADD COLUMN strength INTEGER DEFAULT 1"),
        ("first_seen", "ALTER TABLE edges ADD COLUMN first_seen TEXT"),
        ("last_seen",  "ALTER TABLE edges ADD COLUMN last_seen TEXT"),
        ("pos",        "ALTER TABLE edges ADD COLUMN pos TEXT"),
    ]:
        if col not in existing_edge_cols:
            print(f"  [migrate] adding edges.{col}")
            cur.execute(ddl)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target_key)")

    con.commit()
    con.close()

def save_sentence(con, sentence: str) -> int:
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sentences (text, created_at) VALUES (?, ?)",
        (sentence, datetime.utcnow().isoformat())
    )
    con.commit()
    return cur.lastrowid


def upsert_node(con, key: str, label: str, pos: str, kind: str):
    """Insert if new, otherwise bump mention count."""
    now = datetime.utcnow().isoformat()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO nodes (node_key, label, pos, kind, first_seen, last_seen, mentions)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(node_key) DO UPDATE SET
            mentions = mentions + 1,
            last_seen = excluded.last_seen,
            label = excluded.label,
            pos = excluded.pos,
            kind = excluded.kind
    """, (key, label, pos, kind, now, now))
    con.commit()


def upsert_edge(con, src: str, tgt: str, label: str, relation: str, pos: str):
    """Insert if new, otherwise increment strength."""
    now = datetime.utcnow().isoformat()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO edges (source_key, target_key, label, relation, pos,
                           strength, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(source_key, target_key, label) DO UPDATE SET
            strength = strength + 1,
            last_seen = excluded.last_seen
    """, (src, tgt, label, relation, pos, now, now))
    con.commit()


def load_graph(con) -> nx.DiGraph:
    G = nx.DiGraph()
    cur = con.cursor()

    for key, label, pos, kind, mentions in cur.execute(
        "SELECT node_key, label, pos, kind, mentions FROM nodes"
    ):
        G.add_node(key, label=label, pos=pos, kind=kind, mentions=mentions)

    for src, tgt, label, relation, pos, strength in cur.execute(
        "SELECT source_key, target_key, label, relation, pos, strength FROM edges"
    ):
        G.add_edge(src, tgt, label=label, relation=relation, pos=pos, strength=strength)

    return G


def list_sentences(con):
    cur = con.cursor()
    return cur.execute(
        "SELECT id, text, created_at FROM sentences ORDER BY id"
    ).fetchall()


def clear_db(db_path: str = DB_PATH):
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    print(f"Cleared {db_path}")


# ============================================================
# NLP → GRAPH
# ============================================================

def node_key(text: str, pos: str) -> str:
    """Canonical key: lemma lowercased + kind marker to avoid collision."""
    lemma = nlp(text)[0].lemma_.lower()
    return f"{lemma}::{pos}"


def sentence_to_graph(sentence: str) -> nx.DiGraph:
    """Build a per-sentence graph using lemma-only keys."""
    doc = nlp(sentence)
    G = nx.DiGraph()

    # --- 1. Entity nodes (orange) ---
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN", "PRON"):
            key = f"{token.lemma_.lower()}::ENT"
            G.add_node(key, label=token.text, pos=token.pos_,
                       kind=ENTITY, lemma=token.lemma_)

    # --- 2. Attribute sub-nodes (blue) ---
    # adjectives, determiners, numbers, possessive pronouns
    for token in doc:
        # Adjectives
        if token.pos_ == "ADJ":
            head = token.head
            if head.pos_ in ("NOUN", "PROPN", "PRON"):
                h_key = f"{head.lemma_.lower()}::ENT"
                a_key = f"{token.lemma_.lower()}::ADJ"
                G.add_node(a_key, label=token.text, pos="ADJ",
                           kind=ATTRIBUTE, lemma=token.lemma_)
                if h_key in G:
                    G.add_edge(h_key, a_key,
                               label="is", relation="attribute", pos="ADJ")

        # Determiners (the, a, this)
        if token.pos_ == "DET" and token.dep_ == "det":
            head = token.head
            if head.pos_ in ("NOUN", "PROPN", "PRON"):
                h_key = f"{head.lemma_.lower()}::ENT"
                d_key = f"{token.lemma_.lower()}::DET"
                G.add_node(d_key, label=token.text, pos="DET",
                           kind=ATTRIBUTE, lemma=token.lemma_)
                if h_key in G:
                    G.add_edge(h_key, d_key,
                               label="det", relation="attribute", pos="DET")

        # Numerals
        if token.pos_ == "NUM" and token.dep_ == "nummod":
            head = token.head
            if head.pos_ in ("NOUN", "PROPN"):
                h_key = f"{head.lemma_.lower()}::ENT"
                n_key = f"{token.lemma_.lower()}::NUM"
                G.add_node(n_key, label=token.text, pos="NUM",
                           kind=ATTRIBUTE, lemma=token.lemma_)
                if h_key in G:
                    G.add_edge(h_key, n_key,
                               label="num", relation="attribute", pos="NUM")

    # --- 3. Verb relations between entities ---
    for token in doc:
        if token.pos_ in ("VERB", "AUX") and token.dep_ in (
            "ROOT", "relcl", "advcl", "acl", "conj"
        ):
            subjects = [c for c in token.children if c.dep_ in ("nsubj", "nsubjpass")]
            objects  = [c for c in token.children if c.dep_ in ("dobj", "obj", "attr", "pobj")]
            for s in subjects:
                for o in objects:
                    s_key = f"{s.lemma_.lower()}::ENT"
                    o_key = f"{o.lemma_.lower()}::ENT"
                    if s_key in G and o_key in G:
                        G.add_edge(s_key, o_key,
                                   label=token.lemma_, relation="verb",
                                   pos="VERB")

    # --- 4. Prepositional relations ---
    for token in doc:
        if token.pos_ == "ADP":
            head = token.head
            for child in token.children:
                if child.dep_ == "pobj":
                    h_key = f"{head.lemma_.lower()}::ENT"
                    c_key = f"{child.lemma_.lower()}::ENT"
                    if h_key in G and c_key in G:
                        G.add_edge(h_key, c_key,
                                   label=token.text, relation="prep", pos="ADP")

    return G


# ============================================================
# DRAWING
# ============================================================

def draw_graph(G: nx.DiGraph, title: str = "Accumulated Sentence Graph"):
    if not G.nodes:
        print("Graph is empty.")
        return

    plt.figure(figsize=(14, 9))
    pos = nx.spring_layout(G, seed=42, k=1.8, iterations=100)

    node_colors = []
    node_sizes = []
    for n in G.nodes:
        kind = G.nodes[n].get("kind", ENTITY)
        node_colors.append(COLOR_ENTITY if kind == ENTITY else COLOR_ATTRIBUTE)
        mentions = G.nodes[n].get("mentions", 1)
        node_sizes.append(1500 + 300 * mentions)

    labels = {n: (G.nodes[n].get("label") or n) for n in G.nodes}

    # Nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=node_sizes, alpha=0.9)

    # Node labels (contrast text)
    nx.draw_networkx_labels(G, pos, labels, font_size=10,
                            font_color="white", font_weight="bold")

    # Edges — width proportional to strength
    strengths = [G[u][v].get("strength", 1) for u, v in G.edges]
    max_s = max(strengths) if strengths else 1
    widths = [1.0 + 2.5 * (s / max_s) for s in strengths]

    nx.draw_networkx_edges(
        G, pos, arrows=True, arrowsize=18,
        edge_color="#555555",
        width=widths,
        connectionstyle="arc3,rad=0.1",
    )

    # Edge labels: relation + strength
    edge_labels = {
        (u, v): f"{G[u][v].get('label','')} ({G[u][v].get('strength',1)})"
        for u, v in G.edges
    }
    nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=8,
                                 font_color="#B22222", rotate=False)

    # Legend
    import matplotlib.patches as mpatches
    legend = [
        mpatches.Patch(color=COLOR_ENTITY, label="Entity (noun / pronoun)"),
        mpatches.Patch(color=COLOR_ATTRIBUTE, label="Attribute (adj / det / num)"),
    ]
    plt.legend(handles=legend, loc="upper left", fontsize=9)

    plt.title(title, fontsize=12)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    init_db()
    con = sqlite3.connect(DB_PATH)

    print("Sentence Graph — persistent, merged, weighted")
    print("Commands: 'show' | 'draw' | 'clear' | 'quit'\n")

    while True:
        sentence = input("Enter a sentence (or command): ").strip()

        if not sentence:
            continue
        if sentence.lower() in ("quit", "exit", "q"):
            break
        if sentence.lower() == "show":
            for sid, text, ts in list_sentences(con):
                print(f"  [{sid}] {ts}  {text}")
            continue
        if sentence.lower() == "draw":
            G = load_graph(con)
            draw_graph(G, title="Accumulated Sentence Graph")
            continue
        if sentence.lower() == "clear":
            con.close()
            clear_db()
            con = sqlite3.connect(DB_PATH)
            continue

        # --- Process a new sentence ---
        sid = save_sentence(con, sentence)
        G_new = sentence_to_graph(sentence)

        # Upsert nodes (no repeats)
        for n, data in G_new.nodes(data=True):
            upsert_node(con, n, data.get("label"), data.get("pos"), data.get("kind", ENTITY))

        # Upsert edges (strength++ on repeat)
        for u, v, data in G_new.edges(data=True):
            upsert_edge(con, u, v, data.get("label", ""),
                        data.get("relation", ""), data.get("pos", ""))

        # Report
        n_count = con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e_count = con.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        s_count = con.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]

        print(f"  Saved sentence #{sid}  |  "
              f"{len(G_new.nodes)} nodes, {len(G_new.edges)} edges in this sentence")
        print(f"  Totals: {s_count} sentences, {n_count} nodes, {e_count} edges")

        # Reload & redraw
        G_full = load_graph(con)
        draw_graph(G_full, title=f"Accumulated Graph ({s_count} sentences)")

    con.close()
    print("Goodbye.")
#The scrawny dog  that had been abandoned quietly ate the fish that the fisherman had discarded.