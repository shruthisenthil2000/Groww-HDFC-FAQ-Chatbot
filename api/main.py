from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health as health_route
from api.routes import query as query_route

app = FastAPI(
    title="Simple MVP RAG Chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_route.router, prefix="/api", tags=["Chat"])
app.include_router(health_route.router, prefix="/api", tags=["Health"])


@app.get("/")
async def root() -> dict:
    return {"message": "Simple MVP RAG chatbot running"}
