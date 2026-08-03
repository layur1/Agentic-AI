"""
One-time (or re-run-on-update) ingestion script.

Loads the PDF(s) in data/, splits them into chunks, embeds them locally
using a HuggingFace sentence-transformer, and saves a Chroma vectorstore
to disk.

Run this whenever you add/replace a PDF:
    python ingest_pdf.py
"""
import os
import glob
import shutil

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config


def load_all_pdfs(data_dir: str = "data"):
    pdf_paths = glob.glob(os.path.join(data_dir, "*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found in '{data_dir}/'.")

    all_pages = []
    for path in pdf_paths:
        print(f"Loading: {path}")
        loader = PyPDFLoader(path)
        pages = loader.load()
        for p in pages:
            p.metadata["source_file"] = os.path.basename(path)
        all_pages.extend(pages)
    return all_pages


def build_vectorstore():
    pages = load_all_pdfs()
    print(f"Loaded {len(pages)} page(s) total.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)
    print(f"Split into {len(chunks)} chunk(s).")

    print(f"Loading embedding model: {config.EMBEDDING_MODEL} (first run downloads the model)")
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)

    # Wipe any existing index so re-running this script doesn't duplicate chunks
    if os.path.exists(config.VECTORSTORE_PATH):
        shutil.rmtree(config.VECTORSTORE_PATH)
    os.makedirs(config.VECTORSTORE_PATH, exist_ok=True)

    print("Building Chroma index...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=config.VECTORSTORE_PATH,
    )
    print(f"Vectorstore saved to: {config.VECTORSTORE_PATH}")


if __name__ == "__main__":
    build_vectorstore()