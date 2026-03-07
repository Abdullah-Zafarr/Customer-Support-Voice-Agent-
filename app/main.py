from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .logger import log_latency_middleware, logger
from .database import Base, engine
from .websocket import router as ws_router
from .rag import ingest_documents

import os

# Initialize database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Voice Agent API")

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_latency_middleware)

app.include_router(ws_router)

# Ensure the static directory exists before mounting, or create it if not
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
async def startup_event():
    """Auto-ingest knowledge documents on server startup."""
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    if os.path.isdir(knowledge_dir) and any(
        f.endswith(('.txt', '.md', '.pdf')) for f in os.listdir(knowledge_dir)
        if f != "README.md"
    ):
        logger.info("Knowledge folder detected — ingesting documents...")
        result = ingest_documents(knowledge_dir)
        logger.info(f"Ingestion result: {result['message']}")
    else:
        logger.info("No knowledge documents found. RAG will be inactive.")

@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

@app.post("/ingest")
async def ingest():
    """Re-index all documents in the knowledge/ folder."""
    result = ingest_documents()
    return result

