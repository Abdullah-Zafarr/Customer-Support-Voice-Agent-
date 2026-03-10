"""
RAG Engine — Retrieval-Augmented Generation for Voice Agent
Handles document ingestion, embedding, and retrieval using sentence-transformers + numpy.
Lightweight: no external vector DB required.
"""

import os
import re
import json
import numpy as np
from ..core.logger import logger

# ─── CONFIG ───
KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge")
INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "knowledge_index.json")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
TOP_K = 3

# ─── GLOBALS (lazy-init) ───
_model = None
_index = None  # {"chunks": [...], "embeddings": [[...], ...], "metadata": [...]}


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _model


def _load_index():
    """Load the pre-built index from disk if it exists."""
    global _index
    if _index is not None:
        return _index
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                _index = json.load(f)
            logger.info(f"Loaded knowledge index: {len(_index.get('chunks', []))} chunks.")
            return _index
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
    _index = {"chunks": [], "embeddings": [], "metadata": []}
    return _index


def _save_index():
    """Save the index to disk."""
    global _index
    if _index:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(_index, f)
        logger.info(f"Saved knowledge index: {len(_index['chunks'])} chunks.")


# ─── DOCUMENT LOADING ───
def _read_file(filepath: str) -> str:
    """Read text from .txt, .md, or .pdf files."""
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
    """Read all docs from knowledge/, chunk them, embed, and store in index."""
    global _index
    folder = folder_path or KNOWLEDGE_DIR

    if not os.path.isdir(folder):
        logger.warning(f"Knowledge directory not found: {folder}")
        return {"status": "error", "message": "Knowledge directory not found."}

    supported_ext = {".txt", ".md", ".pdf"}
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in supported_ext and f != "README.md"
    ]

    if not files:
        logger.info("No documents found in knowledge/ folder.")
        return {"status": "ok", "message": "No documents to ingest.", "chunks": 0}

    model = _get_model()

    all_chunks = []
    all_metadata = []

    for filepath in files:
        filename = os.path.basename(filepath)
        logger.info(f"Processing: {filename}")
        text = _read_file(filepath)
        if not text.strip():
            continue

        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({"source": filename, "chunk_index": i})

    if not all_chunks:
        return {"status": "ok", "message": "No text content found.", "chunks": 0}

    # Embed all chunks
    logger.info(f"Embedding {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=False)
    
    _index = {
        "chunks": all_chunks,
        "embeddings": embeddings.tolist(),
        "metadata": all_metadata,
    }
    _save_index()

    msg = f"Ingested {len(all_chunks)} chunks from {len(files)} file(s)."
    logger.info(msg)
    return {"status": "success", "files": len(files), "chunks": len(all_chunks), "message": msg}


# ─── RETRIEVAL ───
def query_knowledge(question: str, top_k: int = TOP_K) -> list:
    """Retrieve the most relevant document chunks for a given question."""
    index = _load_index()

    if not index or not index.get("chunks"):
        return []

    model = _get_model()

    # Embed the question
    q_embedding = model.encode([question])[0]
    doc_embeddings = np.array(index["embeddings"])

    # Cosine similarity
    q_norm = q_embedding / (np.linalg.norm(q_embedding) + 1e-10)
    doc_norms = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-10)
    similarities = doc_norms @ q_norm

    # Get top-K
    k = min(top_k, len(similarities))
    top_indices = np.argsort(similarities)[-k:][::-1]

    results = []
    for idx in top_indices:
        results.append({
            "text": index["chunks"][idx],
            "source": index["metadata"][idx].get("source", "unknown"),
            "score": float(similarities[idx]),
        })

    return results
