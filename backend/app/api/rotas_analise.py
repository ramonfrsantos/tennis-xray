from __future__ import annotations

import json
import re
import shutil
import traceback
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from uuid import uuid4

import cv2
from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from backend.app.modelos import RelatorioInteligente, RequisicaoAnaliseTexto, RespostaPainel
from backend.app.servicos.inteligencia_contextual import InteligenciaContextual
from backend.app.servicos.orquestrador import OrquestradorBiomecanico
from backend.app.servicos.visao_video_real import (
    VideoAnalysisCancelled,
    analisar_video_real,
    detectar_rastro_bola_calibracao,
    estimar_velocidade_saque_calibracao,
)

router = APIRouter(prefix="/api", tags=["Biomecanica"])

BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = UPLOAD_DIR / "processed"
CALIBRATION_DIR = UPLOAD_DIR / "calibration"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
CALIBRATION_DIR.mkdir(exist_ok=True)

orquestrador = OrquestradorBiomecanico()
inteligencia = InteligenciaContextual()
jobs_video: dict[str, dict] = {}
calibracoes_video: dict[str, dict] = {}
frame_calibracao_cache: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
frame_calibracao_cache_lock = Lock()
FRAME_CALIBRACAO_CACHE_MAX = 120
FRAME_CALIBRACAO_PREVIEW_WIDTH = 1280


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


@router.post("/videos/calibracao/preparar")
async def preparar_calibracao_video(arquivo: UploadFile = File(...)):
    nome_seguro = re.sub(r"[^a-zA-Z0-9._-]", "_", arquivo.filename or "captura.mp4")
    calibracao_id = uuid4().hex
    destino = CALIBRATION_DIR / f"{calibracao_id}_{nome_seguro}"
    tamanho_total = 0

    with destino.open("wb") as buffer:
        while True:
            bloco = await arquivo.read(1024 * 1024)
            if not bloco:
                break
            tamanho_total += len(bloco)
            buffer.write(bloco)

    metadata = _metadata_video(destino)
    calibracoes_video[calibracao_id] = {
        "id": calibracao_id,
        "path": destino,
        "nome_original": nome_seguro,
        "tamanho_bytes": tamanho_total,
        "metadata": metadata,
    }

    return {
        "calibracao_id": calibracao_id,
        "nome_original": nome_seguro,
        "tamanho_bytes": tamanho_total,
        **metadata,
    }


@router.get("/videos/calibracao/{calibracao_id}/frame")
def frame_calibracao_video(
    calibracao_id: str,
    tempo_s: float = Query(default=0.0, ge=0.0),
    max_width: int = Query(default=FRAME_CALIBRACAO_PREVIEW_WIDTH, ge=640, le=2560),
):
    item = _obter_calibracao_video(calibracao_id)
    frame_idx = _frame_idx_por_tempo(item.get("metadata", {}), tempo_s)
    cache_key = (calibracao_id, frame_idx, max_width)
    cached = _obter_frame_cache(cache_key)
    headers = {
        "Cache-Control": "public, max-age=600",
        "X-Frame-Index": str(frame_idx),
    }
    if cached is not None:
        return Response(content=cached, media_type="image/jpeg", headers=headers)

    frame = _extrair_frame_video(item["path"], frame_idx)
    frame = _redimensionar_frame_preview(frame, max_width)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        raise HTTPException(status_code=500, detail="Nao foi possivel codificar o frame do video.")
    payload = encoded.tobytes()
    _armazenar_frame_cache(cache_key, payload)
    return Response(
        content=payload,
        media_type="image/jpeg",
        headers=headers,
    )


@router.post("/videos/calibracao/velocidade-saque")
def calcular_velocidade_saque_calibrada(calibracao: dict = Body(...)):
    if not isinstance(calibracao, dict):
        raise HTTPException(status_code=400, detail="Calibracao deve ser um objeto JSON.")
    return estimar_velocidade_saque_calibracao(calibracao)


@router.post("/videos/calibracao/{calibracao_id}/auto-rastro-bola")
def detectar_rastro_bola_automatico(calibracao_id: str, payload: dict | None = Body(default=None)):
    item = _obter_calibracao_video(calibracao_id)
    dados = payload if isinstance(payload, dict) else {}
    calibracao = dados.get("calibracao")
    if calibracao is not None and not isinstance(calibracao, dict):
        raise HTTPException(status_code=400, detail="Calibracao deve ser um objeto JSON.")

    try:
        return detectar_rastro_bola_calibracao(
            Path(item["path"]),
            calibracao=calibracao,
            seed=dados.get("seed"),
            step_s=float(dados.get("step_s", 0.02)),
            min_confidence=float(dados.get("min_confidence", 0.36)),
            max_points=int(dados.get("max_points", 360)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/videos/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile | None = File(default=None),
    calibracao: str | None = Form(default=None),
    calibracao_id: str | None = Form(default=None),
):
    destino, nome_seguro, tamanho_total = await _resolver_video_upload(arquivo, calibracao_id)

    dados_calibracao = _parse_calibracao_upload(calibracao)
    job_id = uuid4().hex
    jobs_video[job_id] = {
        "id": job_id,
        "status": "pendente",
        "progresso": 0,
        "mensagem": "Arquivo recebido. Aguardando processamento real do video.",
        "arquivo": destino.name,
        "nome_original": nome_seguro,
        "url_video_original": f"/uploads/{destino.name}",
        "tamanho_bytes": tamanho_total,
        "calibracao": dados_calibracao,
        "cancelar": False,
    }
    background_tasks.add_task(_processar_job_video, job_id, destino, dados_calibracao)

    return {
        "mensagem": "Arquivo recebido. Processamento real iniciado.",
        "job_id": job_id,
        "status": "pendente",
        "arquivo": destino.name,
        "nome_original": nome_seguro,
        "url_video_original": f"/uploads/{destino.name}",
        "tamanho_bytes": tamanho_total,
    }


@router.get("/videos/jobs/{job_id}")
def consultar_job_video(job_id: str, resumo: bool = Query(default=False)):
    job = jobs_video.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de video nao encontrado.")
    return _serializar_job_video(job, incluir_resultado=not resumo)


@router.post("/videos/jobs/{job_id}/finalizar")
def finalizar_job_video(job_id: str):
    job = jobs_video.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de video nao encontrado.")
    if job["status"] in {"concluido", "falhou", "cancelado"}:
        return _serializar_job_video(job, incluir_resultado=False)
    job["cancelar"] = True
    job["status"] = "cancelando"
    job["mensagem"] = "Finalizacao solicitada. Encerrando o processamento com seguranca."
    return _serializar_job_video(job, incluir_resultado=False)


def _serializar_job_video(job: dict, incluir_resultado: bool = True) -> dict:
    payload = {chave: valor for chave, valor in job.items() if chave != "cancelar"}
    if not incluir_resultado:
        payload.pop("analise", None)
        payload.pop("traceback", None)
        payload.pop("calibracao", None)
    return payload


def _processar_job_video(job_id: str, caminho_video: Path, calibracao: dict | None = None) -> None:
    job = jobs_video[job_id]
    job["status"] = "processando"
    job["mensagem"] = "Lendo frames reais do video enviado."

    def progresso(valor: float, mensagem: str):
        job["progresso"] = valor
        job["mensagem"] = mensagem
        return not job.get("cancelar", False)

    try:
        resultado = analisar_video_real(caminho_video, PROCESSED_DIR, progresso, calibracao=calibracao)
        nome_saida = resultado.video_analisado_path.name
        debug_path = resultado.video_analisado_path.with_suffix(".debug.json")
        try:
            debug_path.write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "video_origem": str(caminho_video),
                        "video_saida": str(resultado.video_analisado_path),
                        "metadata": resultado.metadata,
                        "calibracao": calibracao,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        except OSError:
            debug_path = None
        job.update(
            {
                "status": "concluido",
                "progresso": 100,
                "mensagem": "Video analisado carregado.",
                "url_video_analisado": f"/uploads/processed/{nome_saida}",
                "analise": resultado.analise.model_dump(mode="json"),
                "metadata": resultado.metadata,
                "debug_url": f"/uploads/processed/{debug_path.name}" if debug_path else None,
            }
        )
    except VideoAnalysisCancelled:
        job.update(
            {
                "status": "cancelado",
                "progresso": job.get("progresso", 0),
                "mensagem": "Processamento finalizado pelo usuario.",
            }
        )
    except Exception as exc:
        erro_texto = str(exc) or exc.__class__.__name__
        job.update(
            {
                "status": "falhou",
                "mensagem": f"Falha ao analisar o video real: {erro_texto}",
                "erro": erro_texto,
                "traceback": traceback.format_exc(),
            }
        )


def _parse_calibracao_upload(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Calibracao invalida: {exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Calibracao deve ser um objeto JSON.")

    return data


async def _resolver_video_upload(
    arquivo: UploadFile | None,
    calibracao_id: str | None,
) -> tuple[Path, str, int]:
    if calibracao_id:
        item = _obter_calibracao_video(calibracao_id)
        origem = Path(item["path"])
        nome_seguro = str(item["nome_original"])
        destino = UPLOAD_DIR / f"{uuid4().hex[:10]}_{nome_seguro}"
        shutil.copy2(origem, destino)
        return destino, nome_seguro, destino.stat().st_size

    if arquivo is None:
        raise HTTPException(status_code=400, detail="Envie um arquivo de video ou uma calibracao preparada.")

    nome_seguro = re.sub(r"[^a-zA-Z0-9._-]", "_", arquivo.filename or "captura.mp4")
    destino = UPLOAD_DIR / f"{uuid4().hex[:10]}_{nome_seguro}"
    tamanho_total = 0

    with destino.open("wb") as buffer:
        while True:
            bloco = await arquivo.read(1024 * 1024)
            if not bloco:
                break
            tamanho_total += len(bloco)
            buffer.write(bloco)

    return destino, nome_seguro, tamanho_total


def _obter_calibracao_video(calibracao_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", calibracao_id or ""):
        raise HTTPException(status_code=404, detail="Calibracao de video nao encontrada.")
    item = calibracoes_video.get(calibracao_id)
    if not item or not Path(item["path"]).exists():
        raise HTTPException(status_code=404, detail="Calibracao de video nao encontrada.")
    return item


def _metadata_video(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Nao foi possivel abrir este video para calibracao.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    largura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    altura = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    return {
        "fps": round(fps, 3),
        "frames_video": total_frames,
        "duracao_s": round(total_frames / fps, 3) if fps > 0 and total_frames > 0 else 0.0,
        "largura": largura,
        "altura": altura,
    }


def _frame_idx_por_tempo(metadata: dict, tempo_s: float) -> int:
    try:
        fps = float(metadata.get("fps") or 30.0)
    except (TypeError, ValueError):
        fps = 30.0
    try:
        total_frames = int(metadata.get("frames_video") or 0)
    except (TypeError, ValueError):
        total_frames = 0

    frame_idx = int(round(max(0.0, tempo_s) * max(fps, 1.0)))
    if total_frames > 0:
        frame_idx = min(max(0, frame_idx), total_frames - 1)
    return max(0, frame_idx)


def _obter_frame_cache(cache_key: tuple[str, int, int]) -> bytes | None:
    with frame_calibracao_cache_lock:
        payload = frame_calibracao_cache.get(cache_key)
        if payload is not None:
            frame_calibracao_cache.move_to_end(cache_key)
        return payload


def _armazenar_frame_cache(cache_key: tuple[str, int, int], payload: bytes) -> None:
    with frame_calibracao_cache_lock:
        frame_calibracao_cache[cache_key] = payload
        frame_calibracao_cache.move_to_end(cache_key)
        while len(frame_calibracao_cache) > FRAME_CALIBRACAO_CACHE_MAX:
            frame_calibracao_cache.popitem(last=False)


def _redimensionar_frame_preview(frame, max_width: int):
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0 or w <= max_width:
        return frame
    escala = max_width / w
    altura = max(2, int(round(h * escala)))
    return cv2.resize(frame, (max_width, altura), interpolation=cv2.INTER_AREA)


def _extrair_frame_video(path: Path, frame_idx: int):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Nao foi possivel abrir este video.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames > 0:
        frame_idx = min(max(0, frame_idx), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    else:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_idx))

    ok, frame = cap.read()
    if not ok and frame_idx > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel extrair frame deste video.")
    return frame

