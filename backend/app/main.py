from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.rotas_analise import router

BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
UPLOAD_DIR = BASE_DIR / "uploads"

app = FastAPI(
    title="Plataforma Biomecanica de Tenis",
    version="0.1.0",
    summary="Painel web visual para tracking e leitura biomecanica de movimentos.",
    description=(
        "Projeto novo em portugues-BR com pipeline em cinco camadas inspirado "
        "na referencia enviada e adaptado para biomecanica e tracking esportivo."
    ),
)

app.include_router(router)
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def raiz():
    return FileResponse(WEB_DIR / "index.html")
