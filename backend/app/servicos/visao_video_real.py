from __future__ import annotations

import logging
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Callable

import cv2
import numpy as np

from backend.app.modelos import (
    AlertaDiagnostico,
    AmostraLinhaTempo,
    AtletaQuadro,
    BolaQuadro,
    CaixaDelimitadora,
    Coordenada,
    DiagnosticoSessao,
    EstadoSessao,
    EstimativaBayesiana,
    MarcadorCorporal,
    MetricasBiomecanicas,
    PontoQuadra,
    QuadroAnalise,
    RelatorioInteligente,
    RespostaPainel,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], bool | None]

COURT_WIDTH_M = 10.97
COURT_SINGLES_WIDTH_M = 8.23
COURT_BASE_TO_T_M = 5.485
COURT_T_TO_NET_M = 6.4
COURT_T_TO_INNER_LINE_M = 4.115
COURT_NET_Y_M = COURT_BASE_TO_T_M + COURT_T_TO_NET_M
COURT_LENGTH_M = COURT_NET_Y_M * 2
COURT_CENTER_X_M = COURT_WIDTH_M / 2
COURT_SINGLES_LEFT_X_M = COURT_CENTER_X_M - COURT_T_TO_INNER_LINE_M
COURT_SINGLES_RIGHT_X_M = COURT_CENTER_X_M + COURT_T_TO_INNER_LINE_M
COURT_SERVICE_TOP_Y_M = COURT_BASE_TO_T_M
COURT_SERVICE_BOTTOM_Y_M = COURT_LENGTH_M - COURT_BASE_TO_T_M
NET_HEIGHT_CENTER_M = 0.914
NET_HEIGHT_SIDE_M = 1.07
TENNIS_BALL_RADIUS_M = 0.0335
SERVE_SPEED_OVERLAY_DURATION_S = 0.7
SERVE_RADAR_SPEED_FACTOR = 1.30

_YOLO_MODEL = None
_YOLO_LOAD_ATTEMPTED = False
_HOG = None


class VideoAnalysisCancelled(RuntimeError):
    """Raised when the user requests cancellation of a video analysis job."""


@dataclass
class DetectionBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    source: str

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def width(self) -> float:
        return max(1.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(1.0, self.y2 - self.y1)


@dataclass
class BallDetection:
    x: float
    y: float
    radius: float
    confidence: float
    source: str = "visual"


@dataclass
class BallAnchor:
    tempo_s: float
    x: float
    y: float


@dataclass
class BallPrior:
    x: float
    y: float
    gate_px: float
    confidence: float
    interval_s: float


@dataclass
class ServeSpeedEvent:
    contato_s: float
    primeiro_toque_s: float
    velocidade_ms: float
    velocidade_kmh: float
    velocidade_media_voo_ms: float
    velocidade_media_voo_kmh: float
    fator_radar: float
    distancia_m: float
    distancia_planta_m: float
    distancia_reta_3d_m: float
    distancia_segmentada_m: float
    altura_contato_m: float
    altura_primeiro_toque_m: float
    tempo_voo_s: float
    amostras_usadas: int
    metodo: str
    confianca: float


@dataclass
class ServeOverlayWindow:
    inicio_saida_s: float
    fim_saida_s: float
    contato_saida_s: float
    primeiro_toque_saida_s: float
    inicio_frame_saida: int
    fim_frame_saida: int
    frame_saida_contato: int


@dataclass
class RealVideoAnalysisResult:
    analise: RespostaPainel
    video_analisado_path: Path
    metadata: dict


def analisar_video_real(
    caminho_video: Path,
    pasta_saida: Path,
    progress_callback: ProgressCallback | None = None,
    calibracao: dict | None = None,
) -> RealVideoAnalysisResult:
    """Analyze an uploaded tennis video and write an annotated video.

    This is intentionally a real-video pipeline, not the old synthetic demo. It
    uses YOLO for people when available and OpenCV heuristics for tennis-ball
    candidates. If YOLO cannot load, it falls back to OpenCV person heuristics.
    """

    caminho_video = Path(caminho_video)
    calibracao = calibracao if isinstance(calibracao, dict) else None
    pasta_saida.mkdir(parents=True, exist_ok=True)
    _notify(progress_callback, 1, "Abrindo video enviado")

    cap = cv2.VideoCapture(str(caminho_video))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {caminho_video}")

    fps_original = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    largura_original = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    altura_original = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duracao_s = total_frames / fps_original if total_frames > 0 else 0.0
    tem_calibracao_bola = _tem_calibracao_bola(calibracao)
    modo_download_saque = _modo_download_saque(calibracao)
    ocultar_bola_render = _ocultar_bola_no_render(calibracao)
    transformacao_video_para_quadra = _transformacao_video_para_quadra(calibracao)
    velocidade_saque = _calcular_velocidade_saque(calibracao, transformacao_video_para_quadra)

    target_fps = (
        _float_env("TENNIS_XRAY_SERVE_DOWNLOAD_FPS", min(fps_original, 24.0))
        if modo_download_saque
        else _float_env("TENNIS_XRAY_ANALYSIS_FPS", min(fps_original, 30.0) if tem_calibracao_bola else 24.0)
    )
    max_frames = (
        _int_env("TENNIS_XRAY_SERVE_DOWNLOAD_MAX_FRAMES", 180)
        if modo_download_saque
        else _int_env("TENNIS_XRAY_MAX_ANALYSIS_FRAMES", 1800 if tem_calibracao_bola else 720)
    )
    # 0 means "keep the uploaded video's original width". The previous 960px
    # default made the annotated video visibly softer and harder to audit.
    output_width = _int_env("TENNIS_XRAY_ANALYSIS_WIDTH", 0)
    min_output_width = _int_env("TENNIS_XRAY_MIN_ANALYSIS_WIDTH", 0)
    process_full = os.getenv("TENNIS_XRAY_PROCESS_FULL_VIDEO", "0") == "1"

    if modo_download_saque and velocidade_saque is not None:
        indices = _selecionar_indices_download_saque(total_frames, fps_original, target_fps, max_frames, velocidade_saque)
    elif tem_calibracao_bola and not process_full:
        indices = _selecionar_indices_intervalo_bola(total_frames, fps_original, target_fps, max_frames, calibracao)
    else:
        indices = _selecionar_indices(total_frames, fps_original, target_fps, max_frames, process_full)
    if not indices:
        indices = list(range(max_frames))

    modelo_yolo = _load_yolo_model()
    detector_usado = "yolo_person+opencv_ball" if modelo_yolo is not None else "opencv_fallback"
    _notify(progress_callback, 4, f"Detector ativo: {detector_usado}")

    stem = caminho_video.stem[:80]
    video_temporario = pasta_saida / f"{stem}_analisado_raw.mp4"
    video_saida = pasta_saida / f"{stem}_analisado.mp4"
    writer = None
    output_size = None
    quadros: list[QuadroAnalise] = []
    ball_samples: list[tuple[int, float, float]] = []
    player_tracks = {"P1": [], "P2": []}
    ball_track: list[tuple[int, int]] = []
    ultimo_players: list[DetectionBox] = []
    ultimo_bola: BallDetection | None = None
    ultimo_bola_frame_idx: int | None = None
    frame_anterior: np.ndarray | None = None
    anchors_bola: list[BallAnchor] | None = None
    tolerancia_anchor_bola_s = max(0.055, 0.72 / max(target_fps, 1.0))
    janela_saque_saida = _janela_overlay_saque_saida(velocidade_saque, indices, fps_original, target_fps)

    for posicao_saida, frame_idx in enumerate(indices):
        _notify(
            progress_callback,
            4 + (posicao_saida / max(len(indices), 1)) * 90,
            f"Processando frame {posicao_saida + 1}/{len(indices)}",
        )

        if total_frames > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            if total_frames <= 0:
                break
            continue

        if output_size is None:
            output_size = _calcular_tamanho_saida(frame, output_width, min_output_width)
            writer = _abrir_writer(video_temporario, target_fps, output_size)
            anchors_bola = [] if ocultar_bola_render else _anchors_bola_calibracao(calibracao, frame.shape)

        players_detectados = _detectar_jogadores(frame, modelo_yolo)
        players_escopo = _filtrar_jogadores_escopo_quadra(players_detectados, calibracao, frame.shape)
        if _tem_anchors_jogadores(calibracao):
            players = _ordenar_jogadores_por_calibracao(players_escopo, calibracao, frame.shape, ultimo_players)
        else:
            players = _normalizar_dois_jogadores(players_escopo, ultimo_players, frame.shape)
        players_validos = [box for box in players if _box_desenhavel(box)]
        if players_validos:
            ultimo_players = players_validos

        tempo_s = (frame_idx / fps_original) if fps_original > 0 else posicao_saida / target_fps
        tempo_saida_s = posicao_saida / max(target_fps, 1.0)
        bola = None
        if ocultar_bola_render:
            ultimo_bola = None
            ball_track.clear()
        else:
            prior_bola = _prior_bola_calibracao(anchors_bola or [], tempo_s, frame.shape)
            if ultimo_bola_frame_idx is not None:
                gap_frames = abs(int(frame_idx) - ultimo_bola_frame_idx)
                if gap_frames > max(4, int(round(fps_original * 0.35))):
                    ultimo_bola = None
                    ball_track.clear()
            bola = _bola_anchor_exata(anchors_bola or [], tempo_s, frame.shape, tolerancia_anchor_bola_s)
            if bola is None:
                if anchors_bola and prior_bola is None:
                    bola = None
                else:
                    bola = _detectar_bola(frame, ultimo_bola, frame_anterior, players_validos, ball_track, prior_bola)
                if bola is None and prior_bola is not None and _prior_preenchivel(prior_bola):
                    bola = _bola_estimativa_prior(prior_bola, frame.shape)
            if bola is not None and not _validar_bola_temporal(bola, ball_track, frame.shape, prior_bola):
                bola = _bola_estimativa_prior(prior_bola, frame.shape) if prior_bola is not None and _prior_preenchivel(prior_bola) else None
            if bola is not None:
                bola = _suavizar_bola_com_prior(bola, prior_bola)
            if bola:
                if ultimo_bola_frame_idx is not None:
                    gap_frames = abs(int(frame_idx) - ultimo_bola_frame_idx)
                    if gap_frames > max(4, int(round(fps_original * 0.35))):
                        ball_track.clear()
                ultimo_bola = bola
                ultimo_bola_frame_idx = int(frame_idx)
                ball_samples.append((int(frame_idx), bola.x, bola.y))
                ball_track.append((int(bola.x), int(bola.y)))
                ball_track = ball_track[-18:]

        quadro = _montar_quadro(
            frame_idx=int(frame_idx),
            tempo_s=tempo_s,
            players=players,
            bola=bola,
            frame_shape=frame.shape,
            quadros=quadros,
            calibracao=calibracao,
            transformacao_video_para_quadra=transformacao_video_para_quadra,
        )
        quadros.append(quadro)

        for atleta in quadro.atletas:
            if atleta.confianca_tracking < 0.08 or "(missing)" in atleta.rotulo:
                continue
            ponto = (
                int(atleta.centro_video.x * frame.shape[1]),
                int(atleta.centro_video.y * frame.shape[0]),
            )
            player_tracks[atleta.id_atleta].append(ponto)
            player_tracks[atleta.id_atleta] = player_tracks[atleta.id_atleta][-22:]

        anotado = _desenhar_frame(
            frame=frame,
            players=players,
            bola=bola,
            player_tracks=player_tracks,
            ball_track=ball_track,
            frame_idx=int(frame_idx),
            tempo_s=tempo_s,
            detector=detector_usado,
            output_size=output_size,
            velocidade_saque=velocidade_saque,
            frame_saida_idx=posicao_saida,
            tempo_saida_s=tempo_saida_s,
            janela_saque_saida=janela_saque_saida,
        )
        writer.write(anotado)
        frame_anterior = frame

    cap.release()
    if writer is not None:
        writer.release()

    if not quadros:
        raise RuntimeError("Nenhum frame valido foi lido do video enviado.")

    codec_saida = _transcodificar_para_h264(video_temporario, video_saida)

    metricas = _computar_metricas(quadros, ball_samples, fps_original, largura_original or output_size[0])
    estimativa = _estimativa_basica(metricas, quadros)
    relatorio = _relatorio_real(metricas, detector_usado)
    diagnostico = _diagnostico_real(metricas, detector_usado)
    estado = EstadoSessao(
        id_sessao=f"video-real-{abs(hash(caminho_video.name))}",
        titulo=f"Analise real do upload: {caminho_video.name}",
        superficie="desconhecida",
        camera="video enviado",
        fps=round(target_fps, 2),
        total_quadros=len(quadros),
        duracao_s=round(duracao_s or (len(quadros) / target_fps), 2),
        fase_atual="video real processado",
        qualidade_calibracao=metricas.qualidade_tracking,
        marcadores_monitorados=["jogadores", "bola", "trilhas", "boxes"],
        observacao=(
            "Analise feita diretamente sobre frames do video enviado. "
            + (
                (
                    "Com calibracao manual de quadra e bola fornecida pelo usuario. "
                    "As medidas em metros usam a planta real da quadra e interpolam pontos invisiveis quando necessario."
                )
                if calibracao
                else "Sem homografia calibrada, as medidas em metros sao aproximadas por escala visual."
            )
        ),
    )

    analise = RespostaPainel(
        estado_sessao=estado,
        quadros=quadros,
        metricas=metricas,
        estimativa=estimativa,
        relatorio=relatorio,
        diagnostico=diagnostico,
        linha_tempo=_montar_linha_tempo(quadros),
    )
    _notify(progress_callback, 100, "Video analisado gerado")

    return RealVideoAnalysisResult(
        analise=analise,
        video_analisado_path=video_saida,
        metadata={
            "detector": detector_usado,
            "fps_original": round(fps_original, 2),
            "frames_video": total_frames,
            "frames_processados": len(quadros),
            "duracao_s": round(duracao_s, 2),
            "duracao_saida_s": round(len(quadros) / max(target_fps, 1.0), 2),
            "largura_original": largura_original,
            "altura_original": altura_original,
            "largura_saida": output_size[0] if output_size else largura_original,
            "altura_saida": output_size[1] if output_size else altura_original,
            "qualidade_h264_crf": _int_env("TENNIS_XRAY_H264_CRF", 18),
            "amostragem": "trecho_saque_download" if modo_download_saque else ("trecho_calibrado_bola" if tem_calibracao_bola and not process_full else ("completa" if process_full else "scan_distribuido")),
            "codec_saida": codec_saida,
            "calibracao_usuario": bool(calibracao),
            "pontos_quadra_calibrados": len((calibracao or {}).get("court_points", {}) or {}),
            "pontos_quadra_pulados": len((calibracao or {}).get("court_missing", {}) or {}),
            "marcacoes_bola_calibradas": len((calibracao or {}).get("ball_marks", []) or []),
            "bola_oculta_render": ocultar_bola_render,
            "velocidade_saque_status": _status_velocidade_saque(calibracao, velocidade_saque, janela_saque_saida),
            "velocidade_saque": _serializar_velocidade_saque(velocidade_saque, janela_saque_saida),
            "medidas_quadra_m": {
                "largura_total": COURT_WIDTH_M,
                "largura_interna": COURT_SINGLES_WIDTH_M,
                "base_ate_t": COURT_BASE_TO_T_M,
                "t_ate_rede": COURT_T_TO_NET_M,
                "t_ate_linha_vertical_interna": COURT_T_TO_INNER_LINE_M,
                "rede_centro": NET_HEIGHT_CENTER_M,
                "rede_extremidades": NET_HEIGHT_SIDE_M,
            },
        },
    )


def estimar_velocidade_saque_calibracao(calibracao: dict | None) -> dict:
    """Calculate serve speed from manual calibration without rendering video."""
    transformacao_video_para_quadra = _transformacao_video_para_quadra(calibracao)
    velocidade_saque = _calcular_velocidade_saque(calibracao, transformacao_video_para_quadra)
    return {
        "velocidade_saque_status": _status_velocidade_saque(calibracao, velocidade_saque, None),
        "velocidade_saque": _serializar_velocidade_saque(velocidade_saque, None),
        "transformacao_quadra": transformacao_video_para_quadra[0] if transformacao_video_para_quadra else None,
        "medidas_quadra_m": {
            "largura_total": COURT_WIDTH_M,
            "largura_interna": COURT_SINGLES_WIDTH_M,
            "base_ate_t": COURT_BASE_TO_T_M,
            "t_ate_rede": COURT_T_TO_NET_M,
            "t_ate_linha_vertical_interna": COURT_T_TO_INNER_LINE_M,
            "rede_centro": NET_HEIGHT_CENTER_M,
            "rede_extremidades": NET_HEIGHT_SIDE_M,
        },
    }


def _serializar_velocidade_saque(
    velocidade_saque: ServeSpeedEvent | None,
    janela_saque_saida: ServeOverlayWindow | None = None,
) -> dict | None:
    if velocidade_saque is None:
        return None
    return {
        "velocidade_ms": round(velocidade_saque.velocidade_ms, 2),
        "velocidade_kmh": round(velocidade_saque.velocidade_kmh, 1),
        "velocidade_media_voo_ms": round(velocidade_saque.velocidade_media_voo_ms, 2),
        "velocidade_media_voo_kmh": round(velocidade_saque.velocidade_media_voo_kmh, 1),
        "fator_radar": round(velocidade_saque.fator_radar, 3),
        "distancia_m": round(velocidade_saque.distancia_m, 2),
        "distancia_planta_m": round(velocidade_saque.distancia_planta_m, 2),
        "distancia_reta_3d_m": round(velocidade_saque.distancia_reta_3d_m, 2),
        "distancia_segmentada_m": round(velocidade_saque.distancia_segmentada_m, 2),
        "altura_contato_m": round(velocidade_saque.altura_contato_m, 2),
        "altura_primeiro_toque_m": round(velocidade_saque.altura_primeiro_toque_m, 2),
        "tempo_voo_s": round(velocidade_saque.tempo_voo_s, 3),
        "amostras_usadas": velocidade_saque.amostras_usadas,
        "metodo": velocidade_saque.metodo,
        "altura_modo": "auto_por_projecao_e_escala_local",
        "confianca": round(velocidade_saque.confianca, 2),
        "contato_s": round(velocidade_saque.contato_s, 3),
        "primeiro_toque_s": round(velocidade_saque.primeiro_toque_s, 3),
        "overlay_inicio_saida_s": round(janela_saque_saida.inicio_saida_s, 3) if janela_saque_saida else None,
        "overlay_fim_saida_s": round(janela_saque_saida.fim_saida_s, 3) if janela_saque_saida else None,
        "overlay_duracao_s": SERVE_SPEED_OVERLAY_DURATION_S,
        "contato_saida_s": round(janela_saque_saida.contato_saida_s, 3) if janela_saque_saida else None,
        "overlay_inicio_frame_saida": janela_saque_saida.inicio_frame_saida if janela_saque_saida else None,
        "overlay_fim_frame_saida": janela_saque_saida.fim_frame_saida if janela_saque_saida else None,
        "frame_saida_contato": janela_saque_saida.frame_saida_contato if janela_saque_saida else None,
    }


def _notify(callback: ProgressCallback | None, progress: float, message: str) -> None:
    if callback is None:
        return
    keep_running = callback(round(float(progress), 2), message)
    if keep_running is False:
        raise VideoAnalysisCancelled("Processamento cancelado pelo usuario.")


def _load_yolo_model():
    global _YOLO_LOAD_ATTEMPTED, _YOLO_MODEL
    if os.getenv("TENNIS_XRAY_USE_YOLO", "1") != "1":
        return None
    if _YOLO_LOAD_ATTEMPTED:
        return _YOLO_MODEL
    _YOLO_LOAD_ATTEMPTED = True

    try:
        from ultralytics import YOLO

        model_path = os.getenv("TENNIS_XRAY_YOLO_PLAYER_MODEL", "yolov8n.pt")
        _YOLO_MODEL = YOLO(model_path)
        return _YOLO_MODEL
    except Exception as exc:  # pragma: no cover - depends on local weights/runtime
        logger.warning("YOLO indisponivel, usando fallback OpenCV: %s", exc)
        _YOLO_MODEL = None
        return None


def _selecionar_indices(
    total_frames: int,
    fps_original: float,
    target_fps: float,
    max_frames: int,
    process_full: bool,
) -> list[int]:
    if total_frames <= 0:
        return []

    stride_fps = max(1, int(round(fps_original / max(target_fps, 1))))
    if process_full:
        return list(range(0, total_frames, stride_fps))

    if total_frames <= max_frames * stride_fps:
        return list(range(0, total_frames, stride_fps))

    return sorted(set(np.linspace(0, total_frames - 1, max_frames, dtype=int).tolist()))


def _selecionar_indices_intervalo_bola(
    total_frames: int,
    fps_original: float,
    target_fps: float,
    max_frames: int,
    calibracao: dict | None,
) -> list[int]:
    if total_frames <= 0:
        return []

    marks = calibracao.get("ball_marks") if isinstance(calibracao, dict) else None
    tempos: list[float] = []
    if isinstance(marks, list):
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            try:
                tempos.append(max(0.0, float(mark.get("time_s", 0.0))))
            except (TypeError, ValueError):
                continue

    if len(tempos) < 2:
        return _selecionar_indices(total_frames, fps_original, target_fps, max_frames, False)

    margem_s = _float_env("TENNIS_XRAY_BALL_INTERVAL_MARGIN_S", 0.75)
    inicio_s = max(0.0, min(tempos) - margem_s)
    fim_s = max(inicio_s, max(tempos) + margem_s)
    inicio = max(0, int(round(inicio_s * max(fps_original, 1.0))))
    fim = min(total_frames - 1, int(round(fim_s * max(fps_original, 1.0))))
    stride_fps = max(1, int(round(fps_original / max(target_fps, 1))))
    indices = list(range(inicio, fim + 1, stride_fps))
    if len(indices) > max_frames:
        indices = sorted(set(np.linspace(inicio, fim, max_frames, dtype=int).tolist()))
    return indices


def _selecionar_indices_download_saque(
    total_frames: int,
    fps_original: float,
    target_fps: float,
    max_frames: int,
    velocidade_saque: ServeSpeedEvent,
) -> list[int]:
    if total_frames <= 0:
        return []

    pre_s = _float_env("TENNIS_XRAY_SERVE_DOWNLOAD_PRE_S", 0.55)
    post_s = _float_env("TENNIS_XRAY_SERVE_DOWNLOAD_POST_S", 0.65)
    inicio_s = max(0.0, velocidade_saque.contato_s - pre_s)
    fim_s = max(
        inicio_s + SERVE_SPEED_OVERLAY_DURATION_S + 0.25,
        velocidade_saque.primeiro_toque_s + post_s,
        velocidade_saque.contato_s + 1.05,
    )
    fps_ref = max(fps_original, 1.0)
    inicio = max(0, int(round(inicio_s * fps_ref)))
    fim = min(total_frames - 1, int(round(fim_s * fps_ref)))
    stride_fps = max(1, int(round(fps_ref / max(target_fps, 1.0))))
    indices = list(range(inicio, fim + 1, stride_fps))
    if len(indices) > max_frames:
        indices = sorted(set(np.linspace(inicio, fim, max_frames, dtype=int).tolist()))
    return indices


def _janela_overlay_saque_saida(
    velocidade_saque: ServeSpeedEvent | None,
    indices: list[int],
    fps_original: float,
    target_fps: float,
) -> ServeOverlayWindow | None:
    if velocidade_saque is None or not indices:
        return None

    fps_ref = max(fps_original, 1.0)
    fps_saida = max(target_fps, 1.0)
    contato_frame_original = int(round(velocidade_saque.contato_s * fps_ref))
    primeiro_toque_frame_original = int(round(velocidade_saque.primeiro_toque_s * fps_ref))

    def _posicao_saida_mais_proxima(frame_original: int) -> int:
        return min(range(len(indices)), key=lambda pos: abs(int(indices[pos]) - frame_original))

    frame_saida_contato = _posicao_saida_mais_proxima(contato_frame_original)
    frame_saida_toque = _posicao_saida_mais_proxima(primeiro_toque_frame_original)
    contato_saida_s = frame_saida_contato / fps_saida
    primeiro_toque_saida_s = frame_saida_toque / fps_saida
    total_frames_saida = len(indices)
    frames_overlay = max(1, int(round(SERVE_SPEED_OVERLAY_DURATION_S * fps_saida)))
    antecipacao_frames = max(0, int(round(0.12 * fps_saida)))
    inicio_frame_saida = max(0, frame_saida_contato - antecipacao_frames)
    fim_frame_saida = min(total_frames_saida - 1, inicio_frame_saida + frames_overlay - 1)
    if fim_frame_saida - inicio_frame_saida + 1 < frames_overlay:
        inicio_frame_saida = max(0, fim_frame_saida - frames_overlay + 1)

    inicio_saida_s = inicio_frame_saida / fps_saida
    fim_saida_s = min(total_frames_saida / fps_saida, (fim_frame_saida + 1) / fps_saida)

    return ServeOverlayWindow(
        inicio_saida_s=inicio_saida_s,
        fim_saida_s=max(fim_saida_s, inicio_saida_s + 1 / fps_saida),
        contato_saida_s=contato_saida_s,
        primeiro_toque_saida_s=primeiro_toque_saida_s,
        inicio_frame_saida=inicio_frame_saida,
        fim_frame_saida=fim_frame_saida,
        frame_saida_contato=frame_saida_contato,
    )


def _calcular_tamanho_saida(frame: np.ndarray, output_width: int, min_output_width: int = 0) -> tuple[int, int]:
    h, w = frame.shape[:2]
    if output_width > 0:
        largura = min(output_width, w)
    else:
        largura = w
    if min_output_width > 0 and largura < min_output_width:
        largura = min_output_width
    altura = int(round(h * (largura / max(w, 1))))
    if largura % 2:
        largura -= 1
    if altura % 2:
        altura -= 1
    return max(2, largura), max(2, altura)


def _abrir_writer(path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    for codec in ("mp4v", "avc1", "H264"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError("Nao foi possivel criar o video anotado com OpenCV.")


def _transcodificar_para_h264(video_origem: Path, video_destino: Path) -> str:
    """Convert OpenCV's raw MP4 to a browser-friendly H.264/yuv420p MP4."""

    try:
        import imageio_ffmpeg

        crf = str(max(0, min(51, _int_env("TENNIS_XRAY_H264_CRF", 18))))
        preset = os.getenv("TENNIS_XRAY_H264_PRESET", "medium")
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        comando = [
            ffmpeg,
            "-y",
            "-i",
            str(video_origem),
            "-an",
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-preset",
            preset,
            "-crf",
            crf,
            str(video_destino),
        ]
        subprocess.run(comando, check=True, capture_output=True, text=True)
        if video_destino.exists() and video_destino.stat().st_size > 0:
            try:
                video_origem.unlink()
            except OSError:
                pass
            return "h264"
    except Exception as exc:  # pragma: no cover - depends on local ffmpeg binary
        logger.warning("Falha ao transcodificar para H.264, usando MP4 bruto: %s", exc)

    if video_destino != video_origem:
        try:
            if video_destino.exists():
                video_destino.unlink()
            video_origem.replace(video_destino)
        except OSError:
            pass
    return "mp4v_fallback"


def _detectar_jogadores(frame: np.ndarray, modelo_yolo) -> list[DetectionBox]:
    if modelo_yolo is not None:
        players = _detectar_jogadores_yolo(frame, modelo_yolo)
        if players:
            return players

    players = _detectar_jogadores_hog(frame)
    if players:
        return players
    return _detectar_jogadores_contorno(frame)


def _detectar_jogadores_yolo(frame: np.ndarray, modelo_yolo) -> list[DetectionBox]:
    try:
        results = modelo_yolo.predict(frame, classes=[0], conf=0.32, imgsz=640, verbose=False)
    except Exception as exc:
        logger.debug("YOLO falhou no frame: %s", exc)
        return []

    boxes = []
    if not results or results[0].boxes is None:
        return boxes

    h, w = frame.shape[:2]
    for box in results[0].boxes:
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].cpu().numpy()]
        conf = float(box.conf[0].cpu().numpy())
        area_ratio = ((x2 - x1) * (y2 - y1)) / max(w * h, 1)
        if area_ratio < 0.001:
            continue
        boxes.append(DetectionBox(x1, y1, x2, y2, conf, "yolo"))

    boxes.sort(key=lambda b: b.confidence * b.width * b.height, reverse=True)
    return _filtrar_boxes_distintos(boxes, frame.shape)[:4]


def _detectar_jogadores_hog(frame: np.ndarray) -> list[DetectionBox]:
    global _HOG
    if os.getenv("TENNIS_XRAY_USE_HOG_FALLBACK", "0") != "1":
        return []
    if _HOG is None:
        _HOG = cv2.HOGDescriptor()
        _HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    h, w = frame.shape[:2]
    scale = min(1.0, 720 / max(w, 1))
    small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame
    rects, weights = _HOG.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)

    boxes = []
    inv = 1 / scale
    for (x, y, bw, bh), weight in zip(rects, weights):
        boxes.append(
            DetectionBox(
                x * inv,
                y * inv,
                (x + bw) * inv,
                (y + bh) * inv,
                float(weight),
                "hog",
            )
        )
    boxes.sort(key=lambda b: b.confidence * b.width * b.height, reverse=True)
    return _filtrar_boxes_distintos(boxes, frame.shape)[:4]


def _detectar_jogadores_contorno(frame: np.ndarray) -> list[DetectionBox]:
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 150)

    # Players usually differ from the blue/green court by local edges and value.
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    mask = ((edges > 0) & (val > 45) & (sat < 210)).astype(np.uint8) * 255
    mask[: int(h * 0.08), :] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area < w * h * 0.001 or area > w * h * 0.18:
            continue
        aspect = bh / max(bw, 1)
        if aspect < 0.8 or aspect > 5.5:
            continue
        boxes.append(DetectionBox(x, y, x + bw, y + bh, 0.35, "opencv"))

    boxes.sort(key=lambda b: b.width * b.height, reverse=True)
    return _filtrar_boxes_distintos(boxes, frame.shape)[:4]


def _filtrar_boxes_distintos(
    boxes: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> list[DetectionBox]:
    h, w = frame_shape[:2]
    distintos: list[DetectionBox] = []
    distancia_minima = max(36.0, min(w, h) * 0.045)

    for box in boxes:
        cx, cy = box.center
        if box.x1 < 0 or box.y1 < 0 or box.x2 > w or box.y2 > h:
            box = DetectionBox(
                max(0, box.x1),
                max(0, box.y1),
                min(w - 1, box.x2),
                min(h - 1, box.y2),
                box.confidence,
                box.source,
            )

        duplicado = False
        for escolhido in distintos:
            dist = math.hypot(cx - escolhido.center[0], cy - escolhido.center[1])
            if _iou(box, escolhido) > 0.32 or dist < distancia_minima:
                duplicado = True
                break
        if not duplicado:
            distintos.append(box)

    return distintos


def _filtrar_jogadores_escopo_quadra(
    players: list[DetectionBox],
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
) -> list[DetectionBox]:
    if not players or not calibracao:
        return players

    transformacao = _transformacao_video_para_quadra(calibracao)
    poligono = _poligono_quadra_video_px(calibracao, frame_shape)
    filtrados = [
        box
        for box in players
        if _box_dentro_escopo_quadra(box, frame_shape, transformacao, poligono)
    ]
    return filtrados if filtrados else players


def _box_dentro_escopo_quadra(
    box: DetectionBox,
    frame_shape: tuple[int, int, int],
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None,
    poligono_quadra_px: np.ndarray | None,
) -> bool:
    h, w = frame_shape[:2]
    cx, cy = box.center
    pontos_px = [
        (cx, box.y2),
        (cx, cy),
        (box.x1 + box.width * 0.35, box.y2),
        (box.x1 + box.width * 0.65, box.y2),
    ]

    if transformacao_video_para_quadra is not None:
        margem_x_m = 1.35
        margem_y_m = 3.2
        for px, py in pontos_px:
            convertido = _aplicar_transformacao(transformacao_video_para_quadra, px / max(w, 1), py / max(h, 1))
            if convertido is None:
                continue
            x_m, y_m = convertido
            if -margem_x_m <= x_m <= COURT_WIDTH_M + margem_x_m and -margem_y_m <= y_m <= COURT_LENGTH_M + margem_y_m:
                return True
        return False

    if poligono_quadra_px is not None:
        margem_px = max(42.0, min(w, h) * 0.055)
        for px, py in pontos_px:
            if cv2.pointPolygonTest(poligono_quadra_px, (float(px), float(py)), True) >= -margem_px:
                return True
        return False

    return True


def _poligono_quadra_video_px(calibracao: dict | None, frame_shape: tuple[int, int, int]) -> np.ndarray | None:
    pontos = _pontos_calibracao_normalizados(calibracao)
    ids = ("sup_esquerda", "sup_direita", "inf_direita", "inf_esquerda")
    if not all(nome in pontos for nome in ids):
        return None
    h, w = frame_shape[:2]
    return np.asarray(
        [[pontos[nome][0] * w, pontos[nome][1] * h] for nome in ids],
        dtype=np.float32,
    )


def _tem_anchors_jogadores(calibracao: dict | None) -> bool:
    if not calibracao:
        return False
    dados_players = calibracao.get("players") if isinstance(calibracao.get("players"), dict) else {}
    return _ponto_normalizado_calibracao(dados_players.get("p1")) is not None or _ponto_normalizado_calibracao(dados_players.get("p2")) is not None


def _ordenar_jogadores_por_calibracao(
    players: list[DetectionBox],
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
    ultimo_players: list[DetectionBox] | None = None,
) -> list[DetectionBox]:
    if not calibracao:
        return players

    dados_players = calibracao.get("players") if isinstance(calibracao.get("players"), dict) else {}
    try:
        quantidade = int(dados_players.get("player_count") or 2)
    except (TypeError, ValueError):
        quantidade = 2
    quantidade = 1 if quantidade == 1 else 2
    anchors = {
        "p1": _ponto_calibracao_px(dados_players.get("p1"), frame_shape),
        "p2": _ponto_calibracao_px(dados_players.get("p2"), frame_shape),
    }
    if anchors["p1"] is None and anchors["p2"] is None:
        return players

    h, w = frame_shape[:2]
    usados: set[int] = set()
    ordenados: list[DetectionBox] = []
    for chave in ("p1", "p2"):
        if chave == "p2" and quantidade < 2:
            ordenados.append(_placeholder_jogador(frame_shape, 1))
            continue

        anchor = anchors[chave]
        if anchor is None:
            continue

        anterior_slot = (ultimo_players or [])[len(ordenados)] if len(ultimo_players or []) > len(ordenados) else None
        melhor_idx = None
        melhor_dist = float("inf")
        for idx, box in enumerate(players):
            if idx in usados:
                continue
            dist_anchor = _distancia_anchor_box(anchor, box)
            dist = dist_anchor
            if anterior_slot is not None and _box_desenhavel(anterior_slot):
                dist_anterior = math.hypot(box.center[0] - anterior_slot.center[0], box.center[1] - anterior_slot.center[1])
                if dist_anterior <= max(80.0, min(w, h) * 0.18):
                    dist = min(dist, dist_anterior * 0.72)
            if dist < melhor_dist:
                melhor_idx = idx
                melhor_dist = dist

        gate = max(70.0, min(w, h) * (0.18 if chave == "p2" else 0.22))
        if melhor_idx is not None and melhor_dist <= gate:
            usados.add(melhor_idx)
            ordenados.append(players[melhor_idx])
        else:
            idx_slot = 0 if chave == "p1" else 1
            hold = _tracking_hold_calibrado(ultimo_players or [], idx_slot, anchor, frame_shape, gate * 1.15)
            ordenados.append(hold if hold is not None else _placeholder_jogador_anchor(frame_shape, idx_slot, anchor))

    while len(ordenados) < 2:
        ordenados.append(_placeholder_jogador(frame_shape, len(ordenados)))

    return ordenados[:2]


def _distancia_anchor_box(anchor: tuple[float, float], box: DetectionBox) -> float:
    ax, ay = anchor
    pontos = [
        box.center,
        ((box.x1 + box.x2) / 2, box.y2),
        ((box.x1 + box.x2) / 2, box.y1 + box.height * 0.72),
    ]
    dentro_x = box.x1 <= ax <= box.x2
    dentro_y = box.y1 <= ay <= box.y2
    if dentro_x and dentro_y:
        return 0.0
    return min(math.hypot(px - ax, py - ay) for px, py in pontos)


def _tracking_hold_calibrado(
    ultimo_players: list[DetectionBox],
    idx_slot: int,
    anchor: tuple[float, float],
    frame_shape: tuple[int, int, int],
    gate: float,
) -> DetectionBox | None:
    if idx_slot >= len(ultimo_players):
        return None
    box = ultimo_players[idx_slot]
    if not _box_desenhavel(box) or _distancia_anchor_box(anchor, box) > gate:
        return None
    return DetectionBox(box.x1, box.y1, box.x2, box.y2, box.confidence * 0.58, "tracking_hold")


def _placeholder_jogador_anchor(
    frame_shape: tuple[int, int, int],
    idx: int,
    anchor: tuple[float, float],
) -> DetectionBox:
    h, w = frame_shape[:2]
    ax, ay = anchor
    escala_y = max(0.12, min(0.30, 0.16 + (ay / max(h, 1)) * 0.12))
    bh = h * escala_y
    bw = max(w * 0.035, bh * 0.32)
    return DetectionBox(ax - bw / 2, ay - bh * 0.52, ax + bw / 2, ay + bh * 0.48, 0.0, "missing")


def _placeholder_jogador(frame_shape: tuple[int, int, int], idx: int) -> DetectionBox:
    h, w = frame_shape[:2]
    cx = w * (0.50 + (idx - 0.5) * 0.08)
    cy = h * (0.72 if idx == 0 else 0.32)
    bw = w * 0.08
    bh = h * 0.22
    return DetectionBox(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 0.0, "missing")


def _normalizar_dois_jogadores(
    players: list[DetectionBox],
    ultimo_players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> list[DetectionBox]:
    h, w = frame_shape[:2]
    players = sorted(_filtrar_boxes_distintos(players[:4], frame_shape), key=lambda b: b.center[1], reverse=True)
    escolhidos = players[:2]

    if len(escolhidos) < 2 and ultimo_players:
        for box in ultimo_players:
            if len(escolhidos) >= 2:
                break
            if any(_boxes_sobrepostas(box, escolhido, frame_shape) for escolhido in escolhidos):
                continue
            escolhidos.append(
                DetectionBox(box.x1, box.y1, box.x2, box.y2, box.confidence * 0.65, "tracking_hold")
            )

    while len(escolhidos) < 2:
        idx = len(escolhidos)
        cx = w * (0.50 + (idx - 0.5) * 0.08)
        cy = h * (0.72 if idx == 0 else 0.32)
        bw = w * 0.08
        bh = h * 0.22
        escolhidos.append(
            DetectionBox(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 0.0, "missing")
        )

    return sorted(escolhidos[:2], key=lambda b: b.center[1], reverse=True)


def _boxes_sobrepostas(
    box_a: DetectionBox,
    box_b: DetectionBox,
    frame_shape: tuple[int, int, int],
) -> bool:
    h, w = frame_shape[:2]
    dist = math.hypot(box_a.center[0] - box_b.center[0], box_a.center[1] - box_b.center[1])
    return _iou(box_a, box_b) > 0.18 or dist < max(42.0, min(w, h) * 0.055)


def _iou(box_a: DetectionBox, box_b: DetectionBox) -> float:
    x1 = max(box_a.x1, box_b.x1)
    y1 = max(box_a.y1, box_b.y1)
    x2 = min(box_a.x2, box_b.x2)
    y2 = min(box_a.y2, box_b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = box_a.width * box_a.height
    area_b = box_b.width * box_b.height
    return inter / max(area_a + area_b - inter, 1.0)


def _box_desenhavel(box: DetectionBox) -> bool:
    return box.source not in {"missing", "placeholder"} and box.confidence >= 0.08


def _tem_calibracao_bola(calibracao: dict | None) -> bool:
    if not calibracao:
        return False
    marks = calibracao.get("ball_marks")
    return isinstance(marks, list) and len(marks) >= 2


def _modo_download_saque(calibracao: dict | None) -> bool:
    render_options = calibracao.get("render_options") if isinstance(calibracao, dict) else None
    return isinstance(render_options, dict) and str(render_options.get("modo") or "") == "download_saque"


def _ocultar_bola_no_render(calibracao: dict | None) -> bool:
    if not isinstance(calibracao, dict):
        return False
    render_options = calibracao.get("render_options")
    if not isinstance(render_options, dict) or not render_options.get("ocultar_bola_se_apenas_saque"):
        return False
    return not _tem_marcacao_trajetoria_bola(calibracao)


def _tem_marcacao_trajetoria_bola(calibracao: dict | None) -> bool:
    marks = calibracao.get("ball_marks") if isinstance(calibracao, dict) else None
    if not isinstance(marks, list):
        return False
    roles_saque = {"serve_contact", "serve_contact_ground", "serve_court_bounce"}
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        role = str(mark.get("role") or mark.get("event") or mark.get("type") or "")
        if role not in roles_saque:
            return True
    return False


def _anchors_bola_calibracao(
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
) -> list[BallAnchor]:
    if not calibracao:
        return []

    marks = calibracao.get("ball_marks")
    if not isinstance(marks, list):
        return []

    anchors: list[BallAnchor] = []
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        ponto = _ponto_calibracao_px(mark, frame_shape)
        if ponto is None:
            continue
        try:
            tempo_s = float(mark.get("time_s", 0.0))
        except (TypeError, ValueError):
            tempo_s = 0.0
        anchors.append(BallAnchor(max(0.0, tempo_s), ponto[0], ponto[1]))

    anchors.sort(key=lambda item: item.tempo_s)
    return anchors


def _bola_anchor_exata(
    anchors: list[BallAnchor],
    tempo_s: float,
    frame_shape: tuple[int, int, int],
    tolerancia_s: float,
) -> BallDetection | None:
    if not anchors:
        return None

    h, w = frame_shape[:2]
    radius = max(4.0, min(w, h) * 0.006)
    mais_proximo = min(anchors, key=lambda item: abs(item.tempo_s - tempo_s))
    if abs(mais_proximo.tempo_s - tempo_s) <= tolerancia_s:
        return BallDetection(mais_proximo.x, mais_proximo.y, radius, 0.99, "manual_anchor")

    return None


def _prior_bola_calibracao(
    anchors: list[BallAnchor],
    tempo_s: float,
    frame_shape: tuple[int, int, int],
) -> BallPrior | None:
    if len(anchors) < 2:
        return None

    h, w = frame_shape[:2]
    for anterior, atual in zip(anchors, anchors[1:]):
        if atual.tempo_s <= anterior.tempo_s:
            continue
        if anterior.tempo_s <= tempo_s <= atual.tempo_s:
            intervalo_s = atual.tempo_s - anterior.tempo_s
            alpha = (tempo_s - anterior.tempo_s) / intervalo_s
            x = anterior.x + (atual.x - anterior.x) * alpha
            y = anterior.y + (atual.y - anterior.y) * alpha
            distancia_segmento = math.hypot(atual.x - anterior.x, atual.y - anterior.y)
            folga_movimento = min(w, h) * 0.035 + distancia_segmento * 0.12
            folga_tempo = min(w, h) * min(0.12, intervalo_s * 0.035)
            gate = max(24.0, min(w, h) * 0.025, min(folga_movimento + folga_tempo, min(w, h) * 0.105))
            confianca = max(0.35, min(0.88, 1.0 - min(intervalo_s / 2.8, 0.65)))
            return BallPrior(x=x, y=y, gate_px=gate, confidence=confianca, interval_s=intervalo_s)

    return None


def _prior_preenchivel(prior_bola: BallPrior) -> bool:
    return prior_bola.interval_s <= 0.7 and prior_bola.confidence >= 0.48


def _bola_estimativa_prior(prior_bola: BallPrior, frame_shape: tuple[int, int, int]) -> BallDetection:
    h, w = frame_shape[:2]
    radius = max(3.0, min(w, h) * 0.0045)
    confidence = max(0.22, min(0.54, prior_bola.confidence * 0.58))
    return BallDetection(prior_bola.x, prior_bola.y, radius, confidence, "calibrated_fill")


def _ponto_calibracao_px(
    ponto: object,
    frame_shape: tuple[int, int, int],
) -> tuple[float, float] | None:
    if not isinstance(ponto, dict):
        return None
    try:
        x = float(ponto.get("x"))
        y = float(ponto.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y) or x < 0 or x > 1 or y < 0 or y > 1:
        return None
    h, w = frame_shape[:2]
    return x * w, y * h


def _detectar_bola(
    frame: np.ndarray,
    ultima_bola: BallDetection | None,
    frame_anterior: np.ndarray | None = None,
    players: list[DetectionBox] | None = None,
    ball_track: list[tuple[int, int]] | None = None,
    prior_bola: BallPrior | None = None,
) -> BallDetection | None:
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    if prior_bola is not None:
        yellow = cv2.inRange(hsv, np.array([15, 34, 72]), np.array([72, 255, 255]))
    else:
        yellow = cv2.inRange(hsv, np.array([18, 58, 95]), np.array([62, 255, 255]))
    glare = cv2.inRange(hsv, np.array([0, 0, 220]), np.array([179, 95, 255]))
    glare = cv2.dilate(glare, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35)), iterations=1)

    mask = yellow
    motion_mask = _mask_movimento(frame, frame_anterior)
    if prior_bola is not None:
        mask = cv2.bitwise_and(mask, _mascara_roi_bola_prior(prior_bola, frame.shape, fator=2.35))
    elif motion_mask is not None:
        mask = cv2.bitwise_and(mask, motion_mask)

    mask = cv2.medianBlur(mask, 5)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_radius = max(1.6 if prior_bola is not None else 3.0, min(w, h) * (0.0015 if prior_bola is not None else 0.0026))
    min_area = max(math.pi * (min_radius * 0.58) ** 2, w * h * (0.0000012 if prior_bola is not None else 0.000003))
    max_area = max(40.0, w * h * (0.00012 if prior_bola is not None else 0.000085))
    candidates: list[tuple[float, BallDetection]] = []
    candidates.extend(
        _candidatos_bola_hough(
            frame=frame,
            hsv=hsv,
            motion_mask=motion_mask,
            players=players or [],
            frame_shape=frame.shape,
            min_radius=min_radius,
            max_radius=max(9.0, min(w, h) * 0.014),
            prior_bola=prior_bola,
        )
    )

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter <= 0:
            continue
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        if circularity < 0.34:
            continue
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        if radius < min_radius or radius > max(9, min(w, h) * 0.014):
            continue
        x0 = max(0, int(x - radius * 1.8))
        y0 = max(0, int(y - radius * 1.8))
        x1 = min(w, int(x + radius * 1.8) + 1)
        y1 = min(h, int(y + radius * 1.8) + 1)
        roi_hsv = hsv[y0:y1, x0:x1]
        if roi_hsv.size == 0:
            continue
        sat_media = float(np.mean(roi_hsv[:, :, 1]))
        val_media = float(np.mean(roi_hsv[:, :, 2]))
        if sat_media < (42 if prior_bola is not None else 65) or val_media < (78 if prior_bola is not None else 105):
            continue
        core_sat, core_val = _metricas_core_bola(hsv, x, y, radius)
        if core_sat < (50 if prior_bola is not None else 92) or core_val < (82 if prior_bola is not None else 120):
            continue
        glare_roi = glare[y0:y1, x0:x1]
        glare_ratio = float(np.count_nonzero(glare_roi)) / max(glare_roi.size, 1)
        if glare_ratio > 0.68 and sat_media < 82:
            continue

        motion_score = 0.0
        if motion_mask is not None:
            motion_roi = motion_mask[y0:y1, x0:x1]
            motion_score = float(np.count_nonzero(motion_roi)) / max(motion_roi.size, 1)
            if prior_bola is None and motion_score < 0.08:
                continue

        continuity = 0.0
        if ultima_bola is not None:
            dist = math.hypot(x - ultima_bola.x, y - ultima_bola.y)
            continuidade_maxima = max(120.0, min(w, h) * 0.22)
            continuity = max(0.0, 1.0 - dist / continuidade_maxima)
            if dist < max(4.0, radius * 1.2) and motion_score < 0.22:
                continue

        score = (
            circularity * 0.34
            + min(area / max_area, 1.0) * 0.14
            + min(sat_media / 180.0, 1.0) * 0.18
            + min(motion_score * 2.2, 1.0) * 0.22
            + continuity * 0.12
        )
        candidate = BallDetection(float(x), float(y), float(radius), min(0.98, score))
        if _candidato_em_zona_jogador(candidate, players or [], frame.shape) and not _prior_confirma_candidato(candidate, prior_bola):
            continue
        if prior_bola is not None and _distancia_prior(candidate, prior_bola) > prior_bola.gate_px * 2.0:
            continue
        score = _score_bola_contextual(score, candidate, players or [], ball_track or [], frame.shape, prior_bola)
        if score >= 0.34:
            candidates.append((score, BallDetection(candidate.x, candidate.y, candidate.radius, min(0.98, score))))

    if not candidates:
        return None
    best_score, best_candidate = max(candidates, key=lambda item: item[0])
    min_score = 0.50 if prior_bola is not None else 0.58
    if best_score < min_score:
        return None
    return best_candidate


def _candidatos_bola_hough(
    frame: np.ndarray,
    hsv: np.ndarray,
    motion_mask: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    min_radius: float,
    max_radius: float,
    prior_bola: BallPrior | None = None,
) -> list[tuple[float, BallDetection]]:
    h, w = frame_shape[:2]
    roi = _roi_bola_prior(prior_bola, frame_shape) if prior_bola is not None else _roi_saque(players, frame_shape)
    if roi is None:
        return []

    x0, y0, x1, y1 = roi
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return []

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(14, int(min_radius * 4)),
        param1=82,
        param2=24 if prior_bola is not None else 34,
        minRadius=max(2, int(min_radius)),
        maxRadius=max(4, int(max_radius)),
    )
    if circles is None:
        return []

    candidates: list[tuple[float, BallDetection]] = []
    for x_local, y_local, radius in np.round(circles[0, :24], 2):
        x = float(x0 + x_local)
        y = float(y0 + y_local)
        radius = float(radius)
        cx0 = max(0, int(x - radius * 1.35))
        cy0 = max(0, int(y - radius * 1.35))
        cx1 = min(w, int(x + radius * 1.35) + 1)
        cy1 = min(h, int(y + radius * 1.35) + 1)
        roi_hsv = hsv[cy0:cy1, cx0:cx1]
        if roi_hsv.size == 0:
            continue

        yellow_mask = cv2.inRange(roi_hsv, np.array([18, 45, 85]), np.array([66, 255, 255]))
        yellow_ratio = float(np.count_nonzero(yellow_mask)) / max(yellow_mask.size, 1)
        sat_mean = float(np.mean(roi_hsv[:, :, 1]))
        val_mean = float(np.mean(roi_hsv[:, :, 2]))
        if yellow_ratio < (0.08 if prior_bola is not None else 0.18) or sat_mean < (38 if prior_bola is not None else 62) or val_mean < (58 if prior_bola is not None else 78):
            continue
        core_sat, core_val = _metricas_core_bola(hsv, x, y, radius)
        if core_sat < (48 if prior_bola is not None else 96) or core_val < (76 if prior_bola is not None else 122):
            continue

        motion_score = 0.0
        if motion_mask is not None:
            motion_roi = motion_mask[cy0:cy1, cx0:cx1]
            motion_score = float(np.count_nonzero(motion_roi)) / max(motion_roi.size, 1)
            if prior_bola is None and motion_score < 0.05:
                continue

        candidate = BallDetection(x=x, y=y, radius=radius, confidence=0.0)
        if _candidato_em_zona_jogador(candidate, players, frame_shape) and not _prior_confirma_candidato(candidate, prior_bola):
            continue
        if prior_bola is not None and _distancia_prior(candidate, prior_bola) > prior_bola.gate_px * 2.0:
            continue
        score = (
            0.42
            + min(yellow_ratio * 1.8, 1.0) * 0.20
            + min(sat_mean / 150.0, 1.0) * 0.15
            + min(motion_score * 1.8, 1.0) * 0.13
        )
        score = _score_bola_contextual(score, candidate, players, [], frame_shape, prior_bola)
        if score >= (0.38 if prior_bola is not None else 0.46):
            candidates.append((score, BallDetection(x, y, radius, min(0.98, score))))

    return candidates


def _metricas_core_bola(hsv: np.ndarray, x: float, y: float, radius: float) -> tuple[float, float]:
    h, w = hsv.shape[:2]
    r = max(2, int(round(radius * 0.55)))
    cx = int(round(x))
    cy = int(round(y))
    x0 = max(0, cx - r)
    y0 = max(0, cy - r)
    x1 = min(w, cx + r + 1)
    y1 = min(h, cy + r + 1)
    core = hsv[y0:y1, x0:x1]
    if core.size == 0:
        return 0.0, 0.0
    return float(np.mean(core[:, :, 1])), float(np.mean(core[:, :, 2]))


def _roi_saque(
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> tuple[int, int, int, int] | None:
    valid_players = [box for box in players if _box_desenhavel(box)]
    if not valid_players:
        return None

    h, w = frame_shape[:2]
    player = max(valid_players, key=lambda box: box.center[1])
    x0 = int(max(0, player.x1 - player.width * 0.9))
    x1 = int(min(w, player.x2 + player.width * 1.7))
    y0 = int(max(0, player.y1 - player.height * 0.78))
    y1 = int(min(h, player.y1 + player.height * 0.34))
    if x1 - x0 < 32 or y1 - y0 < 32:
        return None
    return x0, y0, x1, y1


def _roi_bola_prior(
    prior_bola: BallPrior | None,
    frame_shape: tuple[int, int, int],
) -> tuple[int, int, int, int] | None:
    if prior_bola is None:
        return None
    h, w = frame_shape[:2]
    raio = max(42.0, prior_bola.gate_px * 2.25)
    x0 = int(max(0, prior_bola.x - raio))
    x1 = int(min(w, prior_bola.x + raio))
    y0 = int(max(0, prior_bola.y - raio))
    y1 = int(min(h, prior_bola.y + raio))
    if x1 - x0 < 24 or y1 - y0 < 24:
        return None
    return x0, y0, x1, y1


def _mascara_roi_bola_prior(
    prior_bola: BallPrior,
    frame_shape: tuple[int, int, int],
    fator: float,
) -> np.ndarray:
    h, w = frame_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    raio = max(34.0, prior_bola.gate_px * fator)
    centro = (int(round(prior_bola.x)), int(round(prior_bola.y)))
    eixos = (int(round(raio)), int(round(raio)))
    cv2.ellipse(mask, centro, eixos, 0, 0, 360, 255, -1)
    return mask


def _distancia_prior(candidate: BallDetection, prior_bola: BallPrior) -> float:
    return math.hypot(candidate.x - prior_bola.x, candidate.y - prior_bola.y)


def _prior_confirma_candidato(candidate: BallDetection, prior_bola: BallPrior | None) -> bool:
    if prior_bola is None:
        return False
    return _distancia_prior(candidate, prior_bola) <= max(18.0, prior_bola.gate_px * 0.34)


def _validar_bola_temporal(
    bola: BallDetection,
    ball_track: list[tuple[int, int]],
    frame_shape: tuple[int, int, int],
    prior_bola: BallPrior | None,
) -> bool:
    if bola.source in {"manual_anchor", "calibrated_fill"}:
        return True

    h, w = frame_shape[:2]
    if prior_bola is not None:
        dist_prior = _distancia_prior(bola, prior_bola)
        if dist_prior > max(20.0, prior_bola.gate_px * 0.92):
            return False

    if not ball_track:
        return True

    last_x, last_y = ball_track[-1]
    step = math.hypot(bola.x - last_x, bola.y - last_y)
    max_step = max(32.0, min(w, h) * 0.045)
    if prior_bola is not None:
        max_step = max(max_step, prior_bola.gate_px * 0.95)
    else:
        max_step = max(80.0, min(w, h) * 0.12)
    if step > max_step:
        return False

    if len(ball_track) >= 2:
        prev_x, prev_y = ball_track[-2]
        v1 = (last_x - prev_x, last_y - prev_y)
        v2 = (bola.x - last_x, bola.y - last_y)
        n1 = math.hypot(v1[0], v1[1])
        n2 = math.hypot(v2[0], v2[1])
        if n1 > 8 and n2 > 8:
            cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / max(n1 * n2, 1e-6)
            if cos_angle < -0.35 and not _prior_confirma_candidato(bola, prior_bola):
                return False

            lateral_jump = abs(v2[0]) > max(26.0, abs(v2[1]) * 1.8, min(w, h) * 0.04)
            if lateral_jump and not _prior_confirma_candidato(bola, prior_bola):
                return False

    return True


def _suavizar_bola_com_prior(bola: BallDetection, prior_bola: BallPrior | None) -> BallDetection:
    if prior_bola is None or bola.source in {"manual_anchor", "calibrated_fill"}:
        return bola
    dist_prior = _distancia_prior(bola, prior_bola)
    if dist_prior > max(18.0, prior_bola.gate_px * 0.9):
        return bola
    peso_prior = min(0.42, max(0.18, prior_bola.confidence * 0.34))
    x = bola.x * (1 - peso_prior) + prior_bola.x * peso_prior
    y = bola.y * (1 - peso_prior) + prior_bola.y * peso_prior
    return BallDetection(x, y, bola.radius, min(0.98, max(bola.confidence, prior_bola.confidence * 0.72)), "visual_smoothed")


def _candidato_em_zona_jogador(
    candidate: BallDetection,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> bool:
    h, w = frame_shape[:2]
    for box in players:
        if not _box_desenhavel(box):
            continue
        margem_x = max(10.0, box.width * 0.10)
        margem_top = max(12.0, box.height * 0.16)
        margem_bottom = max(6.0, box.height * 0.05)
        dentro_x = box.x1 - margem_x <= candidate.x <= box.x2 + margem_x
        dentro_y = box.y1 - margem_top <= candidate.y <= box.y2 + margem_bottom
        if dentro_x and dentro_y:
            return True

        # Racket/hand false positives usually sit just above the upper body.
        near_upper_body_x = box.x1 - box.width * 0.35 <= candidate.x <= box.x2 + box.width * 0.35
        near_upper_body_y = box.y1 - box.height * 0.26 <= candidate.y <= box.y1 + box.height * 0.18
        if near_upper_body_x and near_upper_body_y:
            return True

    return False


def _score_bola_contextual(
    base_score: float,
    candidate: BallDetection,
    players: list[DetectionBox],
    ball_track: list[tuple[int, int]],
    frame_shape: tuple[int, int, int],
    prior_bola: BallPrior | None = None,
) -> float:
    h, w = frame_shape[:2]
    score = base_score

    if prior_bola is not None:
        dist_prior = _distancia_prior(candidate, prior_bola)
        score += max(0.0, 1.0 - dist_prior / max(prior_bola.gate_px, 1.0)) * (0.62 * prior_bola.confidence)
        if dist_prior > prior_bola.gate_px * 1.35:
            score -= 0.48
        if dist_prior > prior_bola.gate_px * 2.0:
            score -= 1.0

    if len(ball_track) >= 2:
        prev_x, prev_y = ball_track[-2]
        last_x, last_y = ball_track[-1]
        pred_x = last_x + (last_x - prev_x)
        pred_y = last_y + (last_y - prev_y)
        dist_pred = math.hypot(candidate.x - pred_x, candidate.y - pred_y)
        gate = max(90.0, min(w, h) * 0.16)
        score += max(0.0, 1.0 - dist_pred / gate) * 0.42
        if dist_pred > gate * 1.85:
            score -= 0.32

    valid_players = [box for box in players if _box_desenhavel(box)]
    if valid_players:
        jogador_proximo = max(valid_players, key=lambda box: box.center[1])
        score += _score_contexto_saque(candidate, jogador_proximo, frame_shape)

    if candidate.y < h * 0.08 or candidate.y > h * 0.92:
        score -= 0.24

    return score


def _score_contexto_saque(
    candidate: BallDetection,
    player: DetectionBox,
    frame_shape: tuple[int, int, int],
) -> float:
    h, w = frame_shape[:2]
    zone_x1 = max(0.0, player.x1 - player.width * 0.55)
    zone_x2 = min(float(w), player.x2 + player.width * 1.15)
    zone_y1 = max(0.0, player.y1 - player.height * 0.55)
    zone_y2 = min(float(h), player.y1 + player.height * 0.28)

    dx = 0.0
    if candidate.x < zone_x1:
        dx = zone_x1 - candidate.x
    elif candidate.x > zone_x2:
        dx = candidate.x - zone_x2

    dy = 0.0
    if candidate.y < zone_y1:
        dy = zone_y1 - candidate.y
    elif candidate.y > zone_y2:
        dy = candidate.y - zone_y2

    dist_zone = math.hypot(dx, dy)
    gate = max(80.0, min(w, h) * 0.12)
    contextual = max(0.0, 1.0 - dist_zone / gate) * 0.34

    hand_proxy_x = player.center[0] + player.width * 0.32
    hand_proxy_y = player.y1 - player.height * 0.12
    dist_hand = math.hypot(candidate.x - hand_proxy_x, candidate.y - hand_proxy_y)
    hand_gate = max(140.0, player.height * 0.42)
    contextual += max(0.0, 1.0 - dist_hand / hand_gate) * 0.32

    if candidate.y < player.y1 - player.height * 0.72:
        contextual -= 0.28
    if candidate.x < player.x1 - player.width * 0.85 or candidate.x > player.x2 + player.width * 1.45:
        contextual -= 0.18

    return contextual


def _mask_movimento(frame: np.ndarray, frame_anterior: np.ndarray | None) -> np.ndarray | None:
    if frame_anterior is None or frame_anterior.shape != frame.shape:
        return None
    atual = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    anterior = cv2.cvtColor(frame_anterior, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(atual, anterior)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)
    _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
    return mask


def _montar_quadro(
    frame_idx: int,
    tempo_s: float,
    players: list[DetectionBox],
    bola: BallDetection | None,
    frame_shape: tuple[int, int, int],
    quadros: list[QuadroAnalise],
    calibracao: dict | None = None,
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None = None,
) -> QuadroAnalise:
    h, w = frame_shape[:2]
    atletas = []
    for idx, box in enumerate(players[:2]):
        atleta_id = "P1" if idx == 0 else "P2"
        rotulo = "Jogador 1" if idx == 0 else "Jogador 2"
        atletas.append(_box_para_atleta(atleta_id, rotulo, box, w, h, quadros, transformacao_video_para_quadra))

    bola_model = None
    if bola is not None:
        pos_quadra = _video_norm_para_quadra_m(bola.x / max(w, 1), bola.y / max(h, 1), transformacao_video_para_quadra)
        velocidade = _velocidade_bola_aproximada(pos_quadra, tempo_s, quadros)
        bola_model = BolaQuadro(
            posicao_video=Coordenada(x=round(bola.x / max(w, 1), 4), y=round(bola.y / max(h, 1), 4)),
            posicao_quadra_m=pos_quadra,
            velocidade_ms=round(velocidade, 2),
            confianca_tracking=round(bola.confidence, 2),
        )

    return QuadroAnalise(
        indice=len(quadros),
        tempo_s=round(tempo_s, 3),
        atletas=atletas,
        bola=bola_model,
        pontos_quadra=_pontos_quadra_calibrados(calibracao),
    )


def _box_para_atleta(
    atleta_id: str,
    rotulo: str,
    box: DetectionBox,
    w: int,
    h: int,
    quadros: list[QuadroAnalise],
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None = None,
) -> AtletaQuadro:
    cx, cy = box.center
    centro_quadra = _video_norm_para_quadra_m(cx / max(w, 1), cy / max(h, 1), transformacao_video_para_quadra)
    velocidade = _velocidade_atleta_aproximada(atleta_id, centro_quadra, quadros)
    largura_base = round((box.width / max(w, 1)) * COURT_WIDTH_M, 2)
    confianca = max(0.01, min(box.confidence, 0.99))
    marcadores = _marcadores_estimados(cx / max(w, 1), cy / max(h, 1), box.width / max(w, 1), box.height / max(h, 1), confianca)

    return AtletaQuadro(
        id_atleta=atleta_id,
        rotulo=f"{rotulo} ({box.source})",
        caixa=CaixaDelimitadora(
            x=round(max(0, box.x1 / max(w, 1)), 4),
            y=round(max(0, box.y1 / max(h, 1)), 4),
            largura=round(min(1, box.width / max(w, 1)), 4),
            altura=round(min(1, box.height / max(h, 1)), 4),
        ),
        centro_video=Coordenada(x=round(cx / max(w, 1), 4), y=round(cy / max(h, 1), 4)),
        centro_quadra_m=centro_quadra,
        velocidade_ms=round(velocidade, 2),
        angulo_tronco_graus=0.0,
        flexao_joelho_graus=135.0,
        largura_base_apoio_m=largura_base,
        indice_estabilidade=round(0.45 + confianca * 0.5, 2),
        indice_simetria=round(0.55 + confianca * 0.35, 2),
        cobertura_lateral_m=0.0,
        marcadores=marcadores,
        confianca_tracking=round(confianca, 2),
    )


def _marcadores_estimados(cx: float, cy: float, bw: float, bh: float, conf: float) -> list[MarcadorCorporal]:
    pontos = {
        "cabeca": (cx, cy - bh * 0.40),
        "ombro_esquerdo": (cx - bw * 0.22, cy - bh * 0.24),
        "ombro_direito": (cx + bw * 0.22, cy - bh * 0.24),
        "quadril_esquerdo": (cx - bw * 0.17, cy + bh * 0.04),
        "quadril_direito": (cx + bw * 0.17, cy + bh * 0.04),
        "joelho_esquerdo": (cx - bw * 0.14, cy + bh * 0.27),
        "joelho_direito": (cx + bw * 0.14, cy + bh * 0.27),
        "tornozelo_esquerdo": (cx - bw * 0.18, cy + bh * 0.48),
        "tornozelo_direito": (cx + bw * 0.18, cy + bh * 0.48),
    }
    return [
        MarcadorCorporal(
            nome=nome,
            posicao=Coordenada(x=round(max(0, min(1, x)), 4), y=round(max(0, min(1, y)), 4)),
            confianca=round(conf * 0.82, 2),
        )
        for nome, (x, y) in pontos.items()
    ]


def _video_norm_para_quadra_m(
    x_norm: float,
    y_norm: float,
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None = None,
) -> Coordenada:
    if transformacao_video_para_quadra is not None:
        convertido = _aplicar_transformacao(transformacao_video_para_quadra, x_norm, y_norm)
        if convertido is not None:
            return Coordenada(
                x=round(max(0.0, min(COURT_WIDTH_M, convertido[0])), 2),
                y=round(max(0.0, min(COURT_LENGTH_M, convertido[1])), 2),
            )
    return Coordenada(
        x=round(max(0.0, min(1.0, x_norm)) * COURT_WIDTH_M, 2),
        y=round(max(0.0, min(1.0, y_norm)) * COURT_LENGTH_M, 2),
    )


def _velocidade_atleta_aproximada(
    atleta_id: str,
    centro_quadra: Coordenada,
    quadros: list[QuadroAnalise],
) -> float:
    if not quadros:
        return 0.0
    anterior = next((a for a in quadros[-1].atletas if a.id_atleta == atleta_id), None)
    if anterior is None:
        return 0.0
    dt = max(quadros[-1].tempo_s - (quadros[-2].tempo_s if len(quadros) > 1 else 0), 1 / 30)
    dist = math.hypot(centro_quadra.x - anterior.centro_quadra_m.x, centro_quadra.y - anterior.centro_quadra_m.y)
    return dist / dt


def _velocidade_bola_aproximada(pos_quadra: Coordenada, tempo_s: float, quadros: list[QuadroAnalise]) -> float:
    ultimo_com_bola = next((q for q in reversed(quadros) if q.bola is not None), None)
    if ultimo_com_bola is None:
        return 0.0
    dist_m = math.hypot(
        pos_quadra.x - ultimo_com_bola.bola.posicao_quadra_m.x,
        pos_quadra.y - ultimo_com_bola.bola.posicao_quadra_m.y,
    )
    dt = max(1 / 30, abs(tempo_s - ultimo_com_bola.tempo_s))
    return dist_m / dt


def _calcular_velocidade_saque(
    calibracao: dict | None,
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None,
) -> ServeSpeedEvent | None:
    marks = calibracao.get("ball_marks") if isinstance(calibracao, dict) else None
    if not isinstance(marks, list):
        return None

    contato = _marca_bola_por_role(marks, "serve_contact")
    projecao_contato = _marca_bola_por_role(marks, "serve_contact_ground")
    primeiro_toque = _marca_bola_por_role(marks, "serve_court_bounce")
    if contato is None or primeiro_toque is None:
        return None

    try:
        contato_s = float(contato.get("time_s"))
        primeiro_toque_s = float(primeiro_toque.get("time_s"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(contato_s) or not math.isfinite(primeiro_toque_s) or primeiro_toque_s <= contato_s:
        return None

    contato_xy = _ponto_normalizado_calibracao(projecao_contato) or _ponto_normalizado_calibracao(contato)
    toque_xy = _ponto_normalizado_calibracao(primeiro_toque)
    if contato_xy is None or toque_xy is None:
        return None

    transformacao_real_para_video = _transformacao_real_para_video(calibracao)
    curva = _fator_curva_saque(calibracao)
    ponto_contato_chao = _video_norm_para_quadra_m(contato_xy[0], contato_xy[1], transformacao_video_para_quadra)
    ponto_toque = _video_norm_para_quadra_m(toque_xy[0], toque_xy[1], transformacao_video_para_quadra)
    altura_contato = _altura_por_projecao_imagem(
        _ponto_normalizado_calibracao(contato),
        contato_xy,
        ponto_contato_chao,
        transformacao_real_para_video,
    )
    altura_toque = TENNIS_BALL_RADIUS_M if _ponto_normalizado_calibracao(primeiro_toque) is not None else 0.0

    pontos_trajetoria: list[tuple[float, Coordenada, float, str]] = [
        (contato_s, ponto_contato_chao, altura_contato, "contato"),
    ]
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        try:
            tempo = float(mark.get("time_s"))
        except (TypeError, ValueError):
            continue
        if tempo < contato_s or tempo > primeiro_toque_s:
            continue
        ponto = _ponto_normalizado_calibracao(mark)
        if ponto is None:
            continue
        role = str(mark.get("role") or "")
        if role in {"serve_contact", "serve_contact_ground", "serve_court_bounce"}:
            continue
        alpha = (tempo - contato_s) / max(primeiro_toque_s - contato_s, 1e-6)
        alpha_clamped = max(0.0, min(1.0, alpha))
        ground_estimado = Coordenada(
            x=ponto_contato_chao.x + (ponto_toque.x - ponto_contato_chao.x) * alpha_clamped,
            y=ponto_contato_chao.y + (ponto_toque.y - ponto_contato_chao.y) * alpha_clamped,
        )
        altura_estimada = _altura_por_projecao_imagem(ponto, None, ground_estimado, transformacao_real_para_video)
        altura_linear = altura_contato + (altura_toque - altura_contato) * alpha_clamped
        altura = altura_estimada if altura_estimada > TENNIS_BALL_RADIUS_M else max(TENNIS_BALL_RADIUS_M, altura_linear)
        pontos_trajetoria.append((tempo, ground_estimado, altura, "trajetoria"))
    pontos_trajetoria.append((primeiro_toque_s, ponto_toque, altura_toque, "primeiro_toque"))

    pontos_trajetoria.sort(key=lambda item: item[0])
    pontos_filtrados: list[tuple[float, Coordenada, float, str]] = []
    for tempo, ponto, altura, origem in pontos_trajetoria:
        if pontos_filtrados and abs(tempo - pontos_filtrados[-1][0]) < 1e-4:
            pontos_filtrados[-1] = (tempo, ponto, altura, origem)
        else:
            pontos_filtrados.append((tempo, ponto, altura, origem))
    if len(pontos_filtrados) < 2:
        return None

    dt = primeiro_toque_s - contato_s
    distancia_planta = math.hypot(ponto_toque.x - ponto_contato_chao.x, ponto_toque.y - ponto_contato_chao.y)
    distancia_reta_3d = math.sqrt(distancia_planta**2 + (altura_contato - altura_toque) ** 2)
    distancia_segmentada = 0.0
    for (_, anterior, altura_anterior, _), (_, atual, altura_atual, _) in zip(pontos_filtrados, pontos_filtrados[1:]):
        distancia_segmentada += math.sqrt(
            (atual.x - anterior.x) ** 2
            + (atual.y - anterior.y) ** 2
            + (altura_atual - altura_anterior) ** 2
        )

    limite_segmentado = distancia_reta_3d * 1.18
    altura_automatica_ok = projecao_contato is not None and altura_contato > TENNIS_BALL_RADIUS_M * 2
    if len(pontos_filtrados) >= 4 and altura_automatica_ok:
        distancia = max(distancia_reta_3d, min(distancia_segmentada, limite_segmentado))
        metodo = "trajetoria_3d_segmentada_com_altura"
    elif altura_automatica_ok:
        distancia = distancia_reta_3d * curva
        metodo = "triangulo_3d_altura_por_projecao"
    elif len(pontos_filtrados) >= 4:
        distancia = max(distancia_planta, min(distancia_segmentada, limite_segmentado))
        metodo = "trajetoria_2d_sem_projecao_altura"
    else:
        distancia = distancia_planta
        metodo = "planta_2d_sem_projecao_altura"

    if distancia <= 0.05 or dt <= 0.03:
        return None
    velocidade_media_voo_ms = distancia / dt
    fator_radar = _fator_radar_saque(calibracao, distancia, dt, len(pontos_filtrados), altura_automatica_ok)
    velocidade_ms = velocidade_media_voo_ms * fator_radar
    confianca = 0.55
    if altura_automatica_ok:
        confianca += 0.2
    if len(pontos_filtrados) >= 4:
        confianca += 0.15
    if transformacao_video_para_quadra is not None:
        confianca += 0.1
    return ServeSpeedEvent(
        contato_s=contato_s,
        primeiro_toque_s=primeiro_toque_s,
        velocidade_ms=velocidade_ms,
        velocidade_kmh=velocidade_ms * 3.6,
        velocidade_media_voo_ms=velocidade_media_voo_ms,
        velocidade_media_voo_kmh=velocidade_media_voo_ms * 3.6,
        fator_radar=fator_radar,
        distancia_m=distancia,
        distancia_planta_m=distancia_planta,
        distancia_reta_3d_m=distancia_reta_3d,
        distancia_segmentada_m=distancia_segmentada,
        altura_contato_m=altura_contato,
        altura_primeiro_toque_m=altura_toque,
        tempo_voo_s=dt,
        amostras_usadas=len(pontos_filtrados),
        metodo=metodo,
        confianca=min(0.98, confianca),
    )


def _marca_bola_por_role(marks: list, role: str) -> dict | None:
    fallback: dict | None = None
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        if str(mark.get("role") or mark.get("event") or mark.get("type") or "") == role:
            return mark
        label = str(mark.get("label") or "").lower()
        if role == "serve_contact" and "contato" in label and ("raquete" in label or "saida" in label):
            fallback = mark
        elif role == "serve_court_bounce" and (("primeiro" in label and "toque" in label) or "quique" in label):
            fallback = mark
        elif role == "serve_contact_ground" and "projecao" in label and "contato" in label:
            fallback = mark
    return fallback


def _status_velocidade_saque(
    calibracao: dict | None,
    velocidade_saque: ServeSpeedEvent | None,
    janela_saque_saida: ServeOverlayWindow | None,
) -> dict:
    marks = calibracao.get("ball_marks") if isinstance(calibracao, dict) else None
    if not isinstance(marks, list):
        return {
            "status": "sem_marcacoes",
            "mensagem": "Nenhuma marcacao de bola foi enviada para calcular o saque.",
            "faltando": ["contato_raquete", "primeiro_toque_quadra"],
            "roles_presentes": [],
        }

    roles_presentes = sorted({str(mark.get("role") or mark.get("event") or mark.get("type") or "") for mark in marks if isinstance(mark, dict)})
    requisitos = {
        "serve_contact": "contato_raquete",
        "serve_contact_ground": "projecao_chao_contato",
        "serve_court_bounce": "primeiro_toque_quadra",
    }
    faltando = [rotulo for role, rotulo in requisitos.items() if _marca_bola_por_role(marks, role) is None]

    if velocidade_saque is None:
        return {
            "status": "nao_calculada",
            "mensagem": "Velocidade do saque nao foi calculada com as marcacoes atuais.",
            "faltando": faltando,
            "roles_presentes": roles_presentes,
        }

    return {
        "status": "calculada",
        "mensagem": "Velocidade do saque calculada e mapeada para o video analisado.",
        "faltando": faltando,
        "roles_presentes": roles_presentes,
        "overlay_mapeado": janela_saque_saida is not None,
    }


def _altura_por_projecao_imagem(
    ponto_bola_norm: tuple[float, float] | None,
    ponto_chao_norm: tuple[float, float] | None,
    ponto_chao_m: Coordenada,
    transformacao_real_para_video: tuple[str, np.ndarray] | None,
) -> float:
    if ponto_bola_norm is None:
        return 0.0

    chao_norm = ponto_chao_norm
    if chao_norm is None and transformacao_real_para_video is not None:
        chao_norm = _aplicar_transformacao(transformacao_real_para_video, ponto_chao_m.x, ponto_chao_m.y)
    if chao_norm is None:
        return 0.0

    escala = _escala_local_imagem_por_metro(ponto_chao_m, transformacao_real_para_video)
    if escala <= 1e-6:
        return 0.0

    distancia_imagem = math.hypot(ponto_bola_norm[0] - chao_norm[0], ponto_bola_norm[1] - chao_norm[1])
    altura = distancia_imagem / escala
    return max(0.0, min(4.5, altura))


def _escala_local_imagem_por_metro(
    ponto_chao_m: Coordenada,
    transformacao_real_para_video: tuple[str, np.ndarray] | None,
) -> float:
    if transformacao_real_para_video is None:
        return 0.0

    base = _aplicar_transformacao(transformacao_real_para_video, ponto_chao_m.x, ponto_chao_m.y)
    if base is None:
        return 0.0

    amostras: list[float] = []
    candidatos = [
        (min(COURT_WIDTH_M, ponto_chao_m.x + 1.0), ponto_chao_m.y),
        (max(0.0, ponto_chao_m.x - 1.0), ponto_chao_m.y),
        (ponto_chao_m.x, min(COURT_LENGTH_M, ponto_chao_m.y + 1.0)),
        (ponto_chao_m.x, max(0.0, ponto_chao_m.y - 1.0)),
    ]
    for x, y in candidatos:
        dist_m = math.hypot(x - ponto_chao_m.x, y - ponto_chao_m.y)
        if dist_m < 0.2:
            continue
        projetado = _aplicar_transformacao(transformacao_real_para_video, x, y)
        if projetado is None:
            continue
        dist_img = math.hypot(projetado[0] - base[0], projetado[1] - base[1])
        if math.isfinite(dist_img) and dist_img > 0:
            amostras.append(dist_img / dist_m)
    if not amostras:
        return 0.0
    return median(amostras)


def _fator_curva_saque(calibracao: dict | None) -> float:
    raw = (calibracao or {}).get("serve_metrics", {}).get("curve_factor") if isinstance((calibracao or {}).get("serve_metrics"), dict) else None
    try:
        fator = float(raw)
    except (TypeError, ValueError):
        fator = 1.03
    return max(1.0, min(1.12, fator))


def _fator_radar_saque(
    calibracao: dict | None,
    distancia_m: float,
    tempo_voo_s: float,
    amostras: int,
    altura_automatica_ok: bool,
) -> float:
    _ = (distancia_m, tempo_voo_s, amostras, altura_automatica_ok)
    serve_metrics = (calibracao or {}).get("serve_metrics", {}) if isinstance((calibracao or {}).get("serve_metrics"), dict) else {}
    raw = serve_metrics.get("radar_factor")
    try:
        fator = float(raw)
    except (TypeError, ValueError):
        fator = SERVE_RADAR_SPEED_FACTOR
    if fator < SERVE_RADAR_SPEED_FACTOR:
        fator = SERVE_RADAR_SPEED_FACTOR

    # A medicao oficial de TV costuma ser a velocidade inicial/radar logo apos
    # a raquete. O trecho contato->primeiro quique mede velocidade media de voo,
    # que ja perdeu energia por arrasto; aplicamos uma correcao conservadora.
    return max(1.12, min(1.38, fator))


def _desenhar_frame(
    frame: np.ndarray,
    players: list[DetectionBox],
    bola: BallDetection | None,
    player_tracks: dict[str, list[tuple[int, int]]],
    ball_track: list[tuple[int, int]],
    frame_idx: int,
    tempo_s: float,
    detector: str,
    output_size: tuple[int, int],
    velocidade_saque: ServeSpeedEvent | None = None,
    frame_saida_idx: int | None = None,
    tempo_saida_s: float | None = None,
    janela_saque_saida: ServeOverlayWindow | None = None,
) -> np.ndarray:
    if output_size == (frame.shape[1], frame.shape[0]):
        canvas = frame.copy()
    else:
        interpolation = cv2.INTER_CUBIC if output_size[0] > frame.shape[1] else cv2.INTER_AREA
        canvas = cv2.resize(frame, output_size, interpolation=interpolation)
    sx = output_size[0] / frame.shape[1]
    sy = output_size[1] / frame.shape[0]

    cv2.rectangle(canvas, (0, 0), (output_size[0], 82), (6, 15, 24), -1)
    cv2.putText(canvas, "Tennis X-Ray | video real analisado", (22, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (118, 245, 203), 2)
    cv2.putText(canvas, f"Frame {frame_idx} | {tempo_s:0.2f}s | detector: {detector}", (22, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 246, 255), 1)
    _desenhar_velocidade_saque(canvas, output_size, tempo_s, velocidade_saque, frame_saida_idx, tempo_saida_s, janela_saque_saida)

    colors = [(89, 245, 194), (255, 113, 159)]
    for idx, box in enumerate(players[:2]):
        if not _box_desenhavel(box):
            continue
        color = colors[idx]
        x1, y1 = int(box.x1 * sx), int(box.y1 * sy)
        x2, y2 = int(box.x2 * sx), int(box.y2 * sy)
        label = f"Jogador {idx + 1} {box.confidence:.2f}"
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        cv2.rectangle(canvas, (x1, max(0, y1 - 26)), (x1 + 170, y1), (5, 14, 22), -1)
        cv2.putText(canvas, label, (x1 + 8, max(17, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2)
        _desenhar_esqueleto_estimado(canvas, (x1, y1, x2, y2), color)

    if len(ball_track) > 1:
        pts = [(int(x * sx), int(y * sy)) for x, y in ball_track]
        max_segmento = max(42.0, min(output_size) * 0.13)
        for p1, p2 in zip(pts, pts[1:]):
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > max_segmento:
                continue
            cv2.line(canvas, p1, p2, (66, 246, 255), 2)

    if bola is not None:
        center = (int(bola.x * sx), int(bola.y * sy))
        radius = max(5, int(bola.radius * (sx + sy) / 2))
        cor_bola = (74, 244, 255)
        if bola.source == "manual_anchor":
            cor_bola = (97, 255, 116)
        elif bola.source == "calibrated_fill":
            cor_bola = (0, 190, 255)
        cv2.circle(canvas, center, radius + 5, (0, 0, 0), 2)
        cv2.circle(canvas, center, radius, cor_bola, -1)
        rotulo_bola = "bola" if bola.source != "calibrated_fill" else "bola estimada"
        cv2.putText(canvas, f"{rotulo_bola} {bola.confidence:.2f}", (center[0] + 12, center[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_bola, 2)

    return canvas


def _desenhar_velocidade_saque(
    canvas: np.ndarray,
    output_size: tuple[int, int],
    tempo_s: float,
    velocidade_saque: ServeSpeedEvent | None,
    frame_saida_idx: int | None = None,
    tempo_saida_s: float | None = None,
    janela_saque_saida: ServeOverlayWindow | None = None,
) -> None:
    if velocidade_saque is None:
        return
    if janela_saque_saida is not None and frame_saida_idx is not None:
        if frame_saida_idx < janela_saque_saida.inicio_frame_saida or frame_saida_idx > janela_saque_saida.fim_frame_saida:
            return
    elif janela_saque_saida is not None and tempo_saida_s is not None:
        if tempo_saida_s < janela_saque_saida.inicio_saida_s or tempo_saida_s >= janela_saque_saida.fim_saida_s:
            return
    else:
        inicio_overlay = max(0.0, velocidade_saque.contato_s - 0.15)
        if tempo_s < inicio_overlay or tempo_s >= inicio_overlay + SERVE_SPEED_OVERLAY_DURATION_S:
            return

    largura, _ = output_size
    box_w = min(520, max(260, largura - 44))
    x0 = max(22, largura - box_w - 22)
    y0 = 11
    x1 = min(largura - 18, x0 + box_w)
    y1 = 72
    cv2.rectangle(canvas, (x0, y0), (x1, y1), (14, 29, 38), -1)
    cv2.rectangle(canvas, (x0, y0), (x1, y1), (93, 245, 194), 2)
    cv2.putText(canvas, f"Velocidade do saque 3D | conf {velocidade_saque.confianca:0.0%}", (x0 + 14, y0 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (178, 214, 232), 1)
    cv2.putText(
        canvas,
        f"{velocidade_saque.velocidade_kmh:0.1f} km/h",
        (x0 + 14, y0 + 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.64,
        (93, 245, 194),
        2,
    )


def _desenhar_esqueleto_estimado(frame: np.ndarray, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = box
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    cx = x1 + bw * 0.5
    pts = {
        "head": (int(cx), int(y1 + bh * 0.12)),
        "ls": (int(x1 + bw * 0.35), int(y1 + bh * 0.30)),
        "rs": (int(x1 + bw * 0.65), int(y1 + bh * 0.30)),
        "lh": (int(x1 + bw * 0.40), int(y1 + bh * 0.55)),
        "rh": (int(x1 + bw * 0.60), int(y1 + bh * 0.55)),
        "lk": (int(x1 + bw * 0.38), int(y1 + bh * 0.75)),
        "rk": (int(x1 + bw * 0.62), int(y1 + bh * 0.75)),
        "la": (int(x1 + bw * 0.32), int(y1 + bh * 0.95)),
        "ra": (int(x1 + bw * 0.68), int(y1 + bh * 0.95)),
    }
    links = [("head", "ls"), ("head", "rs"), ("ls", "rs"), ("ls", "lh"), ("rs", "rh"), ("lh", "rh"), ("lh", "lk"), ("rh", "rk"), ("lk", "la"), ("rk", "ra")]
    for a, b in links:
        cv2.line(frame, pts[a], pts[b], color, 2)
    for p in pts.values():
        cv2.circle(frame, p, 3, color, -1)


def _computar_metricas(
    quadros: list[QuadroAnalise],
    ball_samples: list[tuple[int, float, float]],
    fps_original: float,
    frame_width: int,
) -> MetricasBiomecanicas:
    p1 = [next(a for a in q.atletas if a.id_atleta == "P1") for q in quadros]
    p2 = [next(a for a in q.atletas if a.id_atleta == "P2") for q in quadros]
    net_y = COURT_LENGTH_M / 2
    p1_depth = fmean(abs(a.centro_quadra_m.y - net_y) for a in p1)
    p2_depth = fmean(abs(a.centro_quadra_m.y - net_y) for a in p2)
    p1_cov = max(a.centro_quadra_m.x for a in p1) - min(a.centro_quadra_m.x for a in p1)
    p2_cov = max(a.centro_quadra_m.x for a in p2) - min(a.centro_quadra_m.x for a in p2)
    speeds = []
    quadros_com_bola = [q for q in quadros if q.bola is not None]
    for anterior, atual in zip(quadros_com_bola, quadros_com_bola[1:]):
        dt = max(1 / max(fps_original, 1), atual.tempo_s - anterior.tempo_s)
        dist = math.hypot(
            atual.bola.posicao_quadra_m.x - anterior.bola.posicao_quadra_m.x,
            atual.bola.posicao_quadra_m.y - anterior.bola.posicao_quadra_m.y,
        )
        speeds.append(dist / dt)
    if not speeds:
        for anterior, atual in zip(ball_samples, ball_samples[1:]):
            frame_delta = max(1, atual[0] - anterior[0])
            dt = frame_delta / max(fps_original, 1)
            px_dist = math.hypot(atual[1] - anterior[1], atual[2] - anterior[2])
            speeds.append(px_dist / dt * (COURT_WIDTH_M / max(frame_width, 1)))
    avg_ball_speed = median(speeds) if speeds else 0.0
    confiancas = [a.confianca_tracking for a in p1 + p2]
    confiancas.extend(q.bola.confianca_tracking for q in quadros if q.bola)

    return MetricasBiomecanicas(
        profundidade_media_p1_m=round(p1_depth, 2),
        profundidade_media_p2_m=round(p2_depth, 2),
        diferenca_agressividade=round(p2_depth - p1_depth, 2),
        cobertura_lateral_p1_m=round(p1_cov, 2),
        cobertura_lateral_p2_m=round(p2_cov, 2),
        razao_cobertura=round(p1_cov / (p2_cov + 1e-6), 2),
        velocidade_media_bola_ms=round(avg_ball_speed, 2),
        estabilidade_tronco_p1=round(fmean(a.indice_estabilidade for a in p1), 2),
        estabilidade_tronco_p2=round(fmean(a.indice_estabilidade for a in p2), 2),
        simetria_apoio_p1=round(fmean(a.indice_simetria for a in p1), 2),
        simetria_apoio_p2=round(fmean(a.indice_simetria for a in p2), 2),
        amplitude_tronco_max_graus=0.0,
        qualidade_tracking=round(fmean(confiancas), 2) if confiancas else 0.0,
        quadros_utilizados=len(quadros),
    )


def _estimativa_basica(metricas: MetricasBiomecanicas, quadros: list[QuadroAnalise]) -> EstimativaBayesiana:
    qualidade = max(0.05, min(metricas.qualidade_tracking, 0.98))
    spread = max(0.04, 0.22 * (1 - qualidade))
    return EstimativaBayesiana(
        qualidade_movimento_p1=qualidade,
        qualidade_movimento_p2=max(0.05, min(0.98, qualidade - abs(metricas.razao_cobertura - 1) * 0.05)),
        intervalo_p1_inferior=max(0.0, qualidade - spread),
        intervalo_p1_superior=min(1.0, qualidade + spread),
        intervalo_p2_inferior=max(0.0, qualidade - spread),
        intervalo_p2_superior=min(1.0, qualidade + spread),
        risco_assimetria_p1=max(0.0, min(1.0, abs(metricas.razao_cobertura - 1) / 2)),
        risco_assimetria_p2=max(0.0, min(1.0, abs(1 - metricas.razao_cobertura) / 2)),
        ajuste_momento=max(-0.08, min(0.08, metricas.diferenca_agressividade / 100)),
        observacoes_processadas=len(quadros),
        incerteza_media=round(1 - qualidade, 2),
    )


def _relatorio_real(metricas: MetricasBiomecanicas, detector: str) -> RelatorioInteligente:
    achados = [
        f"Pipeline real aplicado ao video enviado com detector {detector}.",
        f"{metricas.quadros_utilizados} frames analisados para trajetorias e metricas.",
        "A bola so e desenhada quando ha candidato visual; sem candidato, o overlay nao inventa posicao.",
    ]
    return RelatorioInteligente(
        ajuste_confianca=metricas.qualidade_tracking,
        prioridade_clinica=max(0.1, 1 - metricas.qualidade_tracking),
        resumo=(
            "O upload foi processado diretamente por visao computacional. "
            "As leituras ainda sao aproximadas quando nao ha homografia/pose calibradas, mas nao usam mais animacao sintetica."
        ),
        achados_principais=achados,
        anotacao_processada="Analise automatica do video enviado.",
    )


def _diagnostico_real(metricas: MetricasBiomecanicas, detector: str) -> DiagnosticoSessao:
    alertas = []
    if metricas.qualidade_tracking < 0.45:
        alertas.append(
            AlertaDiagnostico(
                tipo="tracking_baixa_confianca",
                atleta="sessao",
                severidade="media",
                mensagem="A confianca visual ficou baixa; recomenda-se melhorar angulo, iluminacao ou usar pesos especializados.",
                confianca=round(1 - metricas.qualidade_tracking, 2),
            )
        )
    return DiagnosticoSessao(
        sinal_principal="video_real_processado",
        nivel_risco="baixo" if metricas.qualidade_tracking >= 0.55 else "moderado",
        confianca=metricas.qualidade_tracking,
        resumo_execucao=f"Video anotado gerado com {detector}.",
        recomendacoes=[
            "Usar pesos treinados para bola de tenis para reduzir falsos positivos.",
            "Adicionar homografia da quadra para converter pixels em metros com precisao.",
            "Adicionar pose estimation dedicada para substituir o esqueleto estimado por landmarks reais.",
        ],
        alertas=alertas,
    )


def _montar_linha_tempo(quadros: list[QuadroAnalise]) -> list[AmostraLinhaTempo]:
    serie = []
    for quadro in quadros:
        p1 = next(a for a in quadro.atletas if a.id_atleta == "P1")
        p2 = next(a for a in quadro.atletas if a.id_atleta == "P2")
        serie.append(
            AmostraLinhaTempo(
                tempo_s=quadro.tempo_s,
                qualidade_p1=p1.indice_estabilidade,
                qualidade_p2=p2.indice_estabilidade,
                simetria_p1=p1.indice_simetria,
                simetria_p2=p2.indice_simetria,
                velocidade_bola_ms=quadro.bola.velocidade_ms if quadro.bola else 0.0,
                agressividade_instante=round(p2.centro_quadra_m.y - p1.centro_quadra_m.y, 2),
            )
        )
    return serie


def _pontos_quadra_padrao() -> list[PontoQuadra]:
    pontos = [
        ("sup_esquerda", 0.28, 0.33),
        ("sup_direita", 0.72, 0.33),
        ("inf_esquerda", 0.18, 0.86),
        ("inf_direita", 0.82, 0.86),
        ("servico_sup_esquerda", 0.35, 0.47),
        ("servico_sup_direita", 0.65, 0.47),
        ("servico_inf_esquerda", 0.28, 0.67),
        ("servico_inf_direita", 0.72, 0.67),
        ("centro_sup", 0.50, 0.47),
        ("centro_inf", 0.50, 0.67),
        ("rede_esquerda", 0.22, 0.56),
        ("rede_direita", 0.78, 0.56),
    ]
    return [PontoQuadra(nome=nome, posicao_video=Coordenada(x=x, y=y)) for nome, x, y in pontos]


def _pontos_quadra_reais_m() -> dict[str, tuple[float, float]]:
    return {
        "sup_esquerda": (0.0, 0.0),
        "sup_direita": (COURT_WIDTH_M, 0.0),
        "inf_esquerda": (0.0, COURT_LENGTH_M),
        "inf_direita": (COURT_WIDTH_M, COURT_LENGTH_M),
        "rede_esquerda": (0.0, COURT_NET_Y_M),
        "rede_direita": (COURT_WIDTH_M, COURT_NET_Y_M),
        "servico_sup_esquerda": (COURT_SINGLES_LEFT_X_M, COURT_SERVICE_TOP_Y_M),
        "servico_sup_direita": (COURT_SINGLES_RIGHT_X_M, COURT_SERVICE_TOP_Y_M),
        "servico_inf_esquerda": (COURT_SINGLES_LEFT_X_M, COURT_SERVICE_BOTTOM_Y_M),
        "servico_inf_direita": (COURT_SINGLES_RIGHT_X_M, COURT_SERVICE_BOTTOM_Y_M),
        "centro_sup": (COURT_CENTER_X_M, COURT_SERVICE_TOP_Y_M),
        "centro_inf": (COURT_CENTER_X_M, COURT_SERVICE_BOTTOM_Y_M),
    }


def _pontos_quadra_calibrados(calibracao: dict | None) -> list[PontoQuadra]:
    pontos = {ponto.nome: ponto for ponto in _pontos_quadra_padrao()}
    if not calibracao:
        return list(pontos.values())

    pontos_marcados = _pontos_calibracao_normalizados(calibracao)
    for nome, (x, y) in pontos_marcados.items():
        pontos[str(nome)] = PontoQuadra(nome=str(nome), posicao_video=Coordenada(x=round(x, 4), y=round(y, 4)))

    faltantes = calibracao.get("court_missing")
    transformacao_real_para_video = _transformacao_real_para_video(calibracao)
    reais = _pontos_quadra_reais_m()
    if isinstance(faltantes, dict) and transformacao_real_para_video is not None:
        for nome in faltantes:
            nome = str(nome)
            if nome in pontos_marcados or nome not in reais:
                continue
            estimado = _aplicar_transformacao(transformacao_real_para_video, *reais[nome])
            if estimado is None:
                continue
            x, y = estimado
            pontos[nome] = PontoQuadra(
                nome=nome,
                posicao_video=Coordenada(
                    x=round(max(-0.2, min(1.2, x)), 4),
                    y=round(max(-0.2, min(1.2, y)), 4),
                ),
            )

    return list(pontos.values())


def _pontos_calibracao_normalizados(calibracao: dict | None) -> dict[str, tuple[float, float]]:
    if not calibracao:
        return {}
    court_points = calibracao.get("court_points")
    if not isinstance(court_points, dict):
        return {}

    pontos: dict[str, tuple[float, float]] = {}
    for nome, raw in court_points.items():
        ponto = _ponto_normalizado_calibracao(raw)
        if ponto is not None:
            pontos[str(nome)] = ponto
    return pontos


def _ponto_normalizado_calibracao(raw: object) -> tuple[float, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x"))
        y = float(raw.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y) or x < 0 or x > 1 or y < 0 or y > 1:
        return None
    return x, y


def _transformacao_real_para_video(calibracao: dict | None) -> tuple[str, np.ndarray] | None:
    return _transformacao_quadra(calibracao, real_para_video=True)


def _transformacao_video_para_quadra(calibracao: dict | None) -> tuple[str, np.ndarray] | None:
    return _transformacao_quadra(calibracao, real_para_video=False)


def _transformacao_quadra(calibracao: dict | None, real_para_video: bool) -> tuple[str, np.ndarray] | None:
    pontos_video = _pontos_calibracao_normalizados(calibracao)
    if len(pontos_video) < 3:
        return None

    pontos_reais = _pontos_quadra_reais_m()
    origem: list[tuple[float, float]] = []
    destino: list[tuple[float, float]] = []
    for nome, ponto_video in pontos_video.items():
        ponto_real = pontos_reais.get(nome)
        if ponto_real is None:
            continue
        if real_para_video:
            origem.append(ponto_real)
            destino.append(ponto_video)
        else:
            origem.append(ponto_video)
            destino.append(ponto_real)

    return _estimar_transformacao_pontos(origem, destino)


def _estimar_transformacao_pontos(
    origem: list[tuple[float, float]],
    destino: list[tuple[float, float]],
) -> tuple[str, np.ndarray] | None:
    if len(origem) != len(destino) or len(origem) < 3:
        return None

    src = np.asarray(origem, dtype=np.float32)
    dst = np.asarray(destino, dtype=np.float32)
    if len(origem) >= 4:
        homografia, status = cv2.findHomography(src, dst, method=0)
        if homografia is not None and _matriz_finita(homografia):
            if status is None or int(status.sum()) >= 4:
                return "homography", homografia.astype(np.float64)

    if len(origem) == 3:
        affine = cv2.getAffineTransform(src[:3], dst[:3])
    else:
        affine, _ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
    if affine is not None and _matriz_finita(affine):
        return "affine", affine.astype(np.float64)
    return None


def _matriz_finita(matriz: np.ndarray) -> bool:
    return bool(np.all(np.isfinite(matriz)))


def _aplicar_transformacao(transformacao: tuple[str, np.ndarray], x: float, y: float) -> tuple[float, float] | None:
    tipo, matriz = transformacao
    if tipo == "homography":
        ponto = np.asarray([[[x, y]]], dtype=np.float32)
        convertido = cv2.perspectiveTransform(ponto, matriz.astype(np.float32))[0][0]
    else:
        convertido = np.asarray([x, y, 1.0], dtype=np.float64) @ matriz.T
    if convertido.shape[0] < 2 or not np.all(np.isfinite(convertido[:2])):
        return None
    return float(convertido[0]), float(convertido[1])


def _int_env(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao


def _float_env(nome: str, padrao: float) -> float:
    try:
        return float(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao
