import sqlite3
from pathlib import Path
from utils.paths import get_user_data_dir

def get_db_path() -> Path:
    return get_user_data_dir() / "chat_history.db"

def init_chat_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            provider TEXT,
            model TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def save_session(session_id: str, title: str, provider: str, model: str):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO sessions (id, title, provider, model, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (session_id, title, provider, model))
    conn.commit()
    conn.close()

def update_session_title(session_id: str, title: str):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (title, session_id))
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''
        INSERT INTO messages (session_id, role, content)
        VALUES (?, ?, ?)
    ''', (session_id, role, content))
    c.execute('UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()

def get_sessions() -> list[dict]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM sessions ORDER BY updated_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_messages(session_id: str) -> list[dict]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC', (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_session(session_id: str):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()
