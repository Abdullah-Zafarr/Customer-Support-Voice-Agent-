from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .logger import log_latency_middleware, logger
from .database import Base, engine
from .websocket import router as ws_router

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
import os
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("app/static/index.html")
