"""
RAG Engine — Retrieval-Augmented Generation for Voice Agent
Handles document ingestion and retrieval using ChromaDB.
Automatic persistence and retrieval.
"""

import os
import re
import json
import chromadb
from .config import logger

# ─── CONFIG ───
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma")
KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

_chroma_client = None

def _get_client():
    """Lazy-load ChromaDB Client and create collection with defaults."""
    global _chroma_client
    if _chroma_client is None:
        # chroma uses persistent storage
        _chroma_client = chromadb.PersistentClient(path=DB_PATH)
    return _chroma_client

def _get_collection():
    client = _get_client()
    # Uses default sentence-transformers model automatically
    return client.get_or_create_collection("knowledge")

# ─── DOCUMENT LOADING ───
def _read_file(filepath: str) -> str:
    """Read text from .txt, .md, .pdf, or .json files."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".txt", ".md"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            logger.warning("PyMuPDF not installed. Skipping PDF: " + filepath)
            return ""
    elif ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return json.dumps(data, indent=2)
        except Exception as e:
            logger.error(f"Failed to read JSON file {filepath}: {e}")
            return ""
    else:
        return ""

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ─── INGESTION ───
def ingest_documents(folder_path: str = None) -> dict:
    folder = folder_path or KNOWLEDGE_DIR

    if not os.path.isdir(folder):
        logger.warning(f"Knowledge directory not found: {folder}")
        return {"status": "error", "message": "Knowledge directory not found."}

    supported_ext = {".txt", ".md", ".pdf", ".json"}
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in supported_ext and f != "README.md"
    ]

    if not files:
        logger.info("No documents found in knowledge/ folder.")
        return {"status": "ok", "message": "No documents to ingest.", "chunks": 0}

    collection = _get_collection()

    all_chunks = []
    all_metadata = []
    ids = []

    for filepath in files:
        filename = os.path.basename(filepath)
        text = _read_file(filepath)
        if not text.strip():
            continue

        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({"source": filename, "chunk_index": i})
            # Generate a unique ID for each chunk insertion
            ids.append(f"{filename}_{i}")

    if not all_chunks:
        return {"status": "ok", "message": "No text content found.", "chunks": 0}

    # Add to ChromaDB
    logger.info(f"Adding {len(all_chunks)} chunks to ChromaDB collection...")
    # automatically embeds using Chroma default all-MiniLM-L6-v2 without setup
    collection.add(
        documents=all_chunks,
        metadatas=all_metadata,
        ids=ids
    )

    msg = f"Ingested {len(all_chunks)} chunks from {len(files)} file(s)."
    logger.info(msg)
    return {"status": "success", "files": len(files), "chunks": len(all_chunks), "message": msg}


# ─── RETRIEVAL ───
def query_knowledge(question: str, top_k: int = 3) -> list:
    collection = _get_collection()

    try:
        results = collection.query(
            query_texts=[question],
            n_results=top_k
        )
    except Exception as e:
        logger.warning(f"ChromaDB query failed: {e}")
        return []

    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    documents = []
    # iterate query indices (single question batch index 0)
    for idx, doc in enumerate(results["documents"][0]):
        documents.append({
            "text": doc,
            "source": results["metadatas"][0][idx].get("source", "unknown"),
            # Distance in chroma is standard L2, but gives similarity context
            "score": results["distances"][0][idx] if "distances" in results else 0.0,
        })

    return documents
