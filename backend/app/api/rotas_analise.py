from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile

from backend.app.modelos import RelatorioInteligente, RequisicaoAnaliseTexto, RespostaPainel
from backend.app.servicos.inteligencia_contextual import InteligenciaContextual
from backend.app.servicos.orquestrador import OrquestradorBiomecanico

router = APIRouter(prefix="/api", tags=["Biomecanica"])

BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

orquestrador = OrquestradorBiomecanico()
inteligencia = InteligenciaContextual()


@router.get("/saude")
def saude():
    return {
        "status": "ok",
        "projeto": "Plataforma Biomecanica de Tenis",
        "modo": "demo-visual",
    }


@router.get("/arquitetura")
def arquitetura():
    return {
        "camadas": [
            {
                "nome": "Camada 1 - Visao e Tracking",
                "descricao": "Detecta atletas, bola, quadra e marcadores corporais em cada quadro.",
            },
            {
                "nome": "Camada 2 - Motor Bayesiano",
                "descricao": "Atualiza a confianca biomecanica com posterior e intervalos de incerteza.",
            },
            {
                "nome": "Camada 3 - Ponte de Sessao",
                "descricao": "Enriquece a captura com contexto operacional e fase atual do movimento.",
            },
            {
                "nome": "Camada 4 - Inteligencia Contextual",
                "descricao": "Converte anotacoes humanas em sinais estruturados e prioridade clinica.",
            },
            {
                "nome": "Camada 5 - Motor de Diagnostico",
                "descricao": "Combina tracking, confianca e contexto para gerar alertas acionaveis.",
            },
        ]
    }


@router.get("/painel/demo", response_model=RespostaPainel)
def painel_demo(
    quadros: int = Query(90, ge=30, le=240),
    anotacao: str | None = Query(default=None),
):
    return orquestrador.executar_demo(total_quadros=quadros, anotacao=anotacao)


@router.post("/inteligencia/analisar-anotacao", response_model=RelatorioInteligente)
def analisar_anotacao(payload: RequisicaoAnaliseTexto):
    resposta = orquestrador.executar_demo(total_quadros=90, anotacao=payload.anotacao)
    return resposta.relatorio


@router.post("/videos/upload")
async def upload_video(arquivo: UploadFile = File(...)):
    nome_seguro = re.sub(r"[^a-zA-Z0-9._-]", "_", arquivo.filename or "captura.mp4")
    destino = UPLOAD_DIR / nome_seguro
    tamanho_total = 0

    with destino.open("wb") as buffer:
        while True:
            bloco = await arquivo.read(1024 * 1024)
            if not bloco:
                break
            tamanho_total += len(bloco)
            buffer.write(bloco)

    return {
        "mensagem": "Arquivo recebido com sucesso.",
        "arquivo": nome_seguro,
        "tamanho_bytes": tamanho_total,
        "proximo_passo": (
            "Conectar este upload ao pipeline real de inferencia com YOLO e pose "
            "para substituir a demonstracao sintetica."
        ),
    }

