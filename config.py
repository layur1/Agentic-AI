"""
Centralized configuration. Loads everything from .env so no secrets
or environment-specific paths are hardcoded elsewhere in the codebase.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# --- MySQL ---
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Layuri@1128")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "product_assistant_db")

# --- Vectorstore / embeddings ---
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "vectorstore/chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# --- PDF source ---
PDF_PATH = os.getenv("PDF_PATH", "data/product_manuals.pdf")


def require_groq_key():
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://console.groq.com/keys)."
        )