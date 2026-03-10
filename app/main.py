from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from typing import List
from .core.logger import log_latency_middleware, logger
from .db.database import Base, engine
from .routers.websocket import router as ws_router
from .services.rag import ingest_documents

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
        result = await run_in_threadpool(ingest_documents, knowledge_dir)
        logger.info(f"Ingestion result: {result['message']}")
    else:
        logger.info("No knowledge documents found. RAG will be inactive.")

@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

@app.post("/ingest")
async def ingest():
    """Re-index all documents in the knowledge/ folder."""
    result = await run_in_threadpool(ingest_documents)
    return result

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload documents to the knowledge/ folder and trigger ingestion."""
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    
    uploaded_files = []
    for file in files:
        file_path = os.path.join(knowledge_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        uploaded_files.append(file.filename)
        logger.info(f"Uploaded: {file.filename}")
    
    # Trigger re-index
    result = await run_in_threadpool(ingest_documents, knowledge_dir)
    return {
        "status": "success",
        "files": uploaded_files,
        "message": f"Successfully uploaded and indexed {len(uploaded_files)} file(s)."
    }

