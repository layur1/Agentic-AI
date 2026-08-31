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


def require_openai_key():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "(https://platform.openai.com/api-keys)."
        )