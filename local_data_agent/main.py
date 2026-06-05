from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import ChatMessage, LocalDataAgent
from .config import ConfigStore, LocalConnection
from .connectors import create_sqlite_demo
from .exports import ExportFormat

app = FastAPI(title="Local Data Agent", version="0.1.0")
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
store = ConfigStore()
agent = LocalDataAgent(store=store)


class ConnectionRequest(BaseModel):
    type: str = Field(pattern="^(database|folder)$")
    name: str = Field(min_length=1, max_length=80)
    database_uri: str | None = None
    folder_path: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    export_format: ExportFormat | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    connection = store.load_connection()
    return {"configured": connection is not None, "connection": connection.public_dict() if connection else None}


@app.post("/api/connect")
def connect(payload: ConnectionRequest) -> dict[str, Any]:
    connection = LocalConnection(
        type=payload.type,  # type: ignore[arg-type]
        name=payload.name,
        database_uri=payload.database_uri,
        folder_path=payload.folder_path,
    )
    if connection.type == "database" and not connection.database_uri:
        raise HTTPException(status_code=400, detail="Ingresá la URI de la base de datos.")
    if connection.type == "folder" and not connection.folder_path:
        raise HTTPException(status_code=400, detail="Ingresá o seleccioná una carpeta.")
    store.save_connection(connection)
    return {"ok": True, "connection": connection.public_dict()}


@app.delete("/api/connect")
def disconnect() -> dict[str, bool]:
    store.clear()
    return {"ok": True}


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    response = agent.answer(payload.message, payload.history, payload.export_format)
    return {"message": response.message, "downloads": response.downloads, "context": response.context}


@app.post("/api/demo")
def demo() -> dict[str, Any]:
    demo_path = store.root / "demo_invoices.sqlite"
    create_sqlite_demo(demo_path)
    connection = LocalConnection(type="database", name="Facturas demo", database_uri=f"sqlite:///{demo_path}")
    store.save_connection(connection)
    return {"ok": True, "connection": connection.public_dict()}


@app.get("/api/downloads/{filename}")
def download(filename: str) -> FileResponse:
    path = (store.exports_dir / filename).resolve()
    if store.exports_dir.resolve() not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(path, filename=filename)
