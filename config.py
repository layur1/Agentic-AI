import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# --- MySQL ---
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "products_db")

# --- Vectorstore / embeddings ---
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "vectorstore/chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# --- PDF source ---
PDF_PATH = os.getenv("PDF_PATH", "data/product_manuals.pdf")

# --- API access control ---
# NOTE: this is a single SHARED secret checked on every request -- it
# stops random unauthenticated callers from reaching the API at all, but
# it does NOT give individual users their own identity. Two different
# people both holding this same key can still each access any
# session_id, since the key doesn't distinguish WHO is calling, only
# THAT the caller is a known/trusted client. Real per-user session
# ownership would need an actual user-identity system (login, per-user
# tokens) -- out of scope for this fix, flagged here so it isn't
# forgotten.
APP_API_KEY = os.getenv("APP_API_KEY")

# --- Per-session rate limiting ---
MAX_REQUESTS_PER_SESSION_PER_MINUTE = int(
    os.getenv("MAX_REQUESTS_PER_SESSION_PER_MINUTE", "10")
)

# --- Request validation ---
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))


def require_openai_key():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://platform.openai.com/api-keys)."
        )


def require_app_api_key():
    if not APP_API_KEY:
        raise RuntimeError(
            "APP_API_KEY is not set in .env. Generate a random secret string "
            "and set it there before starting api_server.py."
        )