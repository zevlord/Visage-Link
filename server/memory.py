import os
import re
import json
import sqlite3
import asyncio
import urllib.request
import numpy as np

# ponytail: in-memory sqlite vector scan with numpy; upgrade to sqlite-vss/annoy when chunks > 50,000.

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")
KNOWLEDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "zerotwo_lore.md")
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"

use_memory = True

def get_embeddings(texts: list[str]) -> np.ndarray | None:
    """Fetches float32 embeddings from local Ollama instance."""
    if not texts:
        return None
    try:
        payload = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return np.array(data["embeddings"], dtype=np.float32)
    except Exception as e:
        print(f"[RAG] Embedding error: {e}")
        return None

def init_db():
    """Initializes tables and migrates schemas for vector storage."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                fact TEXT NOT NULL,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, fact)
            )
        """)
        # Ensure embedding column exists if table was previously created without it
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(user_facts)")
        cols = [col[1] for col in cursor.fetchall()]
        if "embedding" not in cols:
            conn.execute("ALTER TABLE user_facts ADD COLUMN embedding BLOB")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, title)
            )
        """)
        conn.commit()

    # Backfill missing embeddings for user facts
    backfill_user_fact_embeddings()
    # Sync knowledge base chunks
    sync_knowledge_base()

def backfill_user_fact_embeddings():
    """Computes embeddings for any legacy user facts missing vector data."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, fact FROM user_facts WHERE embedding IS NULL")
            rows = cursor.fetchall()
            if not rows:
                return
            ids = [r[0] for r in rows]
            facts = [f"search_document: {r[1]}" for r in rows]
            vecs = get_embeddings(facts)
            if vecs is not None:
                for row_id, vec in zip(ids, vecs):
                    cursor.execute(
                        "UPDATE user_facts SET embedding = ? WHERE id = ?",
                        (vec.tobytes(), row_id)
                    )
                conn.commit()
                print(f"[RAG] Backfilled {len(ids)} user fact embeddings.")
    except Exception as e:
        print(f"[RAG] Backfill error: {e}")

def sync_knowledge_base():
    """Parses zerotwo_lore.md chunks and indexes them into knowledge_chunks if missing or changed."""
    if not os.path.exists(KNOWLEDGE_PATH):
        return
    try:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            raw = f.read()

        raw_chunks = re.split(r"\n(?=### )", raw)
        parsed = []
        for c in raw_chunks:
            c = c.strip()
            if not c.startswith("###"):
                continue
            lines = c.splitlines()
            title = lines[0].replace("###", "").strip()
            content = "\n".join(lines[1:]).strip()
            if title and content:
                parsed.append((title, content))

        if not parsed:
            return

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM knowledge_chunks WHERE source = 'zerotwo_lore'")
            existing_titles = set(r[0] for r in cursor.fetchall())

            missing = [p for p in parsed if p[0] not in existing_titles]
            if not missing:
                return

            print(f"[RAG] Indexing {len(missing)} lore chunks into knowledge base...")
            embed_inputs = [f"search_document: {title}: {content}" for title, content in missing]
            vecs = get_embeddings(embed_inputs)
            if vecs is None:
                return

            for (title, content), vec in zip(missing, vecs):
                cursor.execute("""
                    INSERT OR REPLACE INTO knowledge_chunks (source, title, content, embedding)
                    VALUES ('zerotwo_lore', ?, ?, ?)
                """, (title, content, vec.tobytes()))
            conn.commit()
            print(f"[RAG] Successfully indexed {len(missing)} lore chunks.")
    except Exception as e:
        print(f"[RAG] Knowledge base sync error: {e}")

def cosine_similarity(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    """Computes cosine similarity between a 1D query vector and a 2D matrix of document vectors."""
    dot = doc_vecs @ query_vec
    q_norm = np.linalg.norm(query_vec)
    d_norms = np.linalg.norm(doc_vecs, axis=1)
    denom = d_norms * q_norm
    denom[denom == 0] = 1e-8
    return dot / denom

def get_rag_context(query: str, user_id: str = "user_001") -> str:
    """Dual-source RAG: embeds the query once, searches lore and user memories, and formats context."""
    if not query or len(query.strip()) < 3:
        return get_memory_context(user_id)

    q_vecs = get_embeddings([f"search_query: {query.strip()}"])
    if q_vecs is None:
        return get_memory_context(user_id)
    q_vec = q_vecs[0]

    lore_sections = []
    user_fact_sections = []

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 1. Query external knowledge base (Zero Two lore)
            cursor.execute("SELECT title, content, embedding FROM knowledge_chunks WHERE source = 'zerotwo_lore'")
            lore_rows = cursor.fetchall()
            if lore_rows:
                titles = [r[0] for r in lore_rows]
                contents = [r[1] for r in lore_rows]
                lore_matrix = np.array([np.frombuffer(r[2], dtype=np.float32) for r in lore_rows])
                lore_sims = cosine_similarity(q_vec, lore_matrix)

                # Keep top 1 or 2 chunks exceeding similarity threshold
                top_indices = np.argsort(lore_sims)[::-1]
                for idx in top_indices[:2]:
                    if lore_sims[idx] >= 0.45:
                        lore_sections.append(f"- {titles[idx]}: {contents[idx]}")

            # 2. Query user facts (semantic recall with recency fallback)
            cursor.execute("SELECT id, fact, embedding FROM user_facts WHERE user_id = ? ORDER BY id DESC", (user_id,))
            user_rows = cursor.fetchall()
            if user_rows:
                facts = [r[1] for r in user_rows]
                valid_pairs = [(r[1], np.frombuffer(r[2], dtype=np.float32)) for r in user_rows if r[2] is not None]

                matched_facts = []
                if valid_pairs:
                    fact_texts = [p[0] for p in valid_pairs]
                    fact_matrix = np.array([p[1] for p in valid_pairs])
                    fact_sims = cosine_similarity(q_vec, fact_matrix)

                    top_fact_indices = np.argsort(fact_sims)[::-1]
                    for idx in top_fact_indices[:3]:
                        if fact_sims[idx] >= 0.38:
                            matched_facts.append(fact_texts[idx])

                # If fewer than 2 relevant semantic matches, supplement with most recent facts
                for f in facts:
                    if f not in matched_facts and len(matched_facts) < 3:
                        matched_facts.append(f)

                user_fact_sections = [f"- {f}" for f in matched_facts]

    except Exception as e:
        print(f"[RAG] Context retrieval error: {e}")
        return get_memory_context(user_id)

    parts = []
    if lore_sections:
        parts.append("ZERO TWO CANON LORE CONTEXT (integrate naturally if relevant):\n" + "\n".join(lore_sections))
    if user_fact_sections:
        parts.append("FACTS I REMEMBER ABOUT DARLING:\n" + "\n".join(user_fact_sections))

    return "\n\n".join(parts) + ("\n" if parts else "")

def get_memory_context(user_id: str = "user_001") -> str:
    """Fallback recency retrieval: returns the latest 10 facts about Darling."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fact FROM user_facts WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
            rows = cursor.fetchall()
            if not rows:
                return ""
            facts = [f"- {row[0]}" for row in reversed(rows)]
            return "FACTS I REMEMBER ABOUT DARLING:\n" + "\n".join(facts) + "\n"
    except Exception as e:
        print(f"[MEMORY] Error reading memories: {e}")
        return ""

def save_fact(fact: str, user_id: str = "user_001"):
    """Inserts a single fact and its vector embedding for a user."""
    clean_fact = fact.strip().lstrip("-*• ")
    if not clean_fact or len(clean_fact) < 3:
        return
    try:
        vec = get_embeddings([f"search_document: {clean_fact}"])
        blob = vec[0].tobytes() if vec is not None else None

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO user_facts (user_id, fact, embedding) VALUES (?, ?, ?)",
                (user_id, clean_fact, blob)
            )
            conn.commit()
            print(f"[MEMORY] Saved fact with vector: {clean_fact}")
    except Exception as e:
        print(f"[MEMORY] Error saving fact: {e}")

async def extract_and_store_facts(user_message: str, user_id: str = "user_001"):
    """Extracts personal user facts in the background using the local LLM."""
    if len(user_message.strip()) < 8:
        return
    try:
        import models
        prompt = (
            f"User message: \"{user_message}\"\n\n"
            "Task: Does the user explicitly state a personal fact, habit, preference, name, or detail about themselves? "
            "If YES, state the concise fact in English (e.g. 'Likes eating ramen', 'Works as a software developer'). "
            "If NO personal fact is revealed, reply strictly with 'NONE'. Do not include markdown or reasoning."
        )
        response = await models.llm.ainvoke([{"role": "user", "content": prompt}])
        reply = response.content.strip()
        if reply and "NONE" not in reply.upper() and not reply.startswith("{"):
            for line in reply.splitlines():
                line = line.strip()
                if line and not line.upper().startswith("NONE"):
                    save_fact(line, user_id)
    except Exception as e:
        print(f"[MEMORY] Background extraction error: {e}")

init_db()
