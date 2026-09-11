import os
import sqlite3
import asyncio

# Local SQLite database for persistent facts
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                fact TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, fact)
            )
        """)
        conn.commit()

init_db()

use_memory = True

def get_memory_context(user_id: str = "user_001") -> str:
    """Returns formatted memory facts about Darling to inject into the system prompt."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fact FROM user_facts WHERE user_id = ? ORDER BY id DESC LIMIT 15", (user_id,))
            rows = cursor.fetchall()
            if not rows:
                return ""
            facts = [f"- {row[0]}" for row in reversed(rows)]
            return "Facts I remember about Darling:\n" + "\n".join(facts) + "\n"
    except Exception as e:
        print(f"[MEMORY] Error reading memories: {e}")
        return ""

def save_fact(fact: str, user_id: str = "user_001"):
    """Inserts a single fact for a user."""
    clean_fact = fact.strip().lstrip("-*• ")
    if not clean_fact or len(clean_fact) < 3:
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO user_facts (user_id, fact) VALUES (?, ?)", (user_id, clean_fact))
            conn.commit()
            print(f"[MEMORY] Saved fact: {clean_fact}")
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
