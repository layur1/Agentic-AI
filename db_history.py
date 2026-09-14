import uuid
import mysql.connector

import config


def _get_connection():
    return mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


def init_db():
    """
    Creates the chat_history table if it doesn't already exist.
    Safe to call every time the server starts -- it will not touch or
    erase any existing rows.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX (session_id)
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


def new_session_id() -> str:
    """Generates a fresh, random conversation identifier."""
    return str(uuid.uuid4())


def get_history(session_id: str) -> list:
    """
    Returns this session's full conversation so far, oldest message
    first, already shaped the way brain.py's ask() expects:
        [{"role": "user", "content": "..."}, {"role": "assistant", ...}, ...]

    If session_id has no rows yet (new, or simply unknown), this
    returns an empty list rather than raising an error -- a fresh
    conversation just starts with no history, the same as before.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT role, content FROM chat_history WHERE session_id = %s ORDER BY id ASC",
        (session_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def append_turn(session_id: str, user_message: str, assistant_message: str):
    """Saves both halves of one exchange (the user's message and the
    assistant's reply) as two rows, permanently."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, role, content) VALUES (%s, %s, %s)",
        (session_id, "user", user_message),
    )
    cursor.execute(
        "INSERT INTO chat_history (session_id, role, content) VALUES (%s, %s, %s)",
        (session_id, "assistant", assistant_message),
    )
    conn.commit()
    cursor.close()
    conn.close()


def session_count() -> int:
    """Number of distinct conversations ever stored (for the admin endpoint)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_history")
    (count,) = cursor.fetchone()
    cursor.close()
    conn.close()
    return count