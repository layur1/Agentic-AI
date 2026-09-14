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
    #Creates the chat_history table if it doesn't already exist.
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
    #Generates a fresh, random conversation identifier.
    return str(uuid.uuid4())


def get_history(session_id: str) -> list:
        # Retrieves a session's full chat history from the database in chronological order and formats it for the AI agent.
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
        # Saves both the user's message and the assistant's reply into the database as a single conversation turn.
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

    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_history")
    (count,) = cursor.fetchone()
    cursor.close()
    conn.close()
    return count