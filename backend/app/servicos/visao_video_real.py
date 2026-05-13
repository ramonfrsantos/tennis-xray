from __future__ import annotations

import logging
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Callable, Iterable

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
from backend.app.servicos.tracknet_ball_tracker import get_tracknet_tracker

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
SERVE_SPEED_OVERLAY_DURATION_S = 2.5
# Recalibrado contra amostra real: 192,1 km/h estimados devem aproximar 204 km/h oficiais.
# 1.011 * (204 / 192.1) ~= 1.074. A estabilidade temporal vem da quantizacao por frame.
SERVE_RADAR_SPEED_FACTOR = 1.074

_YOLO_MODEL = None
_YOLO_LOAD_ATTEMPTED = False
_BALL_YOLO_MODEL = None
_BALL_YOLO_LOAD_ATTEMPTED = False
_BALL_YOLO_MODEL_SOURCE: str | None = None
_BALL_YOLO_MODEL_MTIME: float | None = None
_BALL_YOLO_MODEL_ERROR: str | None = None
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
    motion_score: float = 0.0
    yellow_ratio: float = 0.0


@dataclass
class BallAnchor:
    tempo_s: float
    x: float
    y: float
    source: str = "manual"
    role: str = "trajectory"


@dataclass
class BallPrior:
    x: float
    y: float
    gate_px: float
    confidence: float
    interval_s: float


@dataclass
class BallBeamState:
    x: float
    y: float
    vx: float
    vy: float
    cost: float
    misses: int
    detected: int
    path: list[dict]


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
    tempo_voo_bruto_s: float
    fps_calculo: float
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
    desenhar_predicoes_bola = _bool_env("TENNIS_XRAY_DRAW_PREDICTED_BALL", True)
    hard_reset_bola_s = _float_env("TENNIS_XRAY_BALL_HARD_RESET_GAP_S", 0.85)
    transformacao_video_para_quadra = _transformacao_video_para_quadra(calibracao)
    velocidade_saque = _velocidade_saque_travada(calibracao) or _calcular_velocidade_saque(
        calibracao,
        transformacao_video_para_quadra,
        fps_original,
    )

    # Ball tracking suffers a lot when we skip frames. Keep the uploaded FPS
    # by default (capped at 60) so close/fast balls do not disappear between
    # sampled frames. Env vars can still lower this on slow machines.
    target_fps = (
        _float_env("TENNIS_XRAY_SERVE_DOWNLOAD_FPS", min(fps_original, 60.0))
        if modo_download_saque
        else _float_env("TENNIS_XRAY_ANALYSIS_FPS", min(fps_original, 60.0))
    )
    max_frames = (
        _int_env("TENNIS_XRAY_SERVE_DOWNLOAD_MAX_FRAMES", 720)
        if modo_download_saque
        else _int_env("TENNIS_XRAY_MAX_ANALYSIS_FRAMES", 3600 if tem_calibracao_bola else 2400)
    )
    # 0 means "keep the uploaded video's original width". The previous 960px
    # default made the annotated video visibly softer and harder to audit.
    output_width = _int_env("TENNIS_XRAY_ANALYSIS_WIDTH", 0)
    min_output_width = _int_env("TENNIS_XRAY_MIN_ANALYSIS_WIDTH", 0)
    process_full_env = os.getenv("TENNIS_XRAY_PROCESS_FULL_VIDEO")
    process_full = (process_full_env == "1") if process_full_env is not None else duracao_s <= 60.0

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
    trajetoria_bola_global: dict[int, BallDetection] = {}
    tentou_trajetoria_global = False
    if not ocultar_bola_render and _bool_env("TENNIS_XRAY_GLOBAL_BALL_TRACKING", True):
        tentou_trajetoria_global = True
        indices_trajetoria = _reduzir_indices_trajetoria_global(indices, fps_original)
        _notify(progress_callback, 4.2, f"Resolvendo trajetoria global da bolinha (0/{len(indices_trajetoria)})")
        trajetoria_bola_sparse = _precalcular_trajetoria_bola_global(
            caminho_video=caminho_video,
            indices=indices_trajetoria,
            fps_original=fps_original,
            calibracao=calibracao,
            progress_callback=progress_callback,
            progress_start=4.2,
            progress_end=8.8,
        )
        trajetoria_bola_global = _expandir_trajetoria_global_para_indices_render(
            trajetoria_bola_sparse,
            indices,
            fps_original,
            calibracao=calibracao,
            frame_shape=(altura_original, largura_original, 3),
        )
        if not _trajetoria_global_render_confiavel(trajetoria_bola_sparse, trajetoria_bola_global):
            trajetoria_bola_global = {}
        if trajetoria_bola_global:
            detector_usado = f"{detector_usado}+global_ball_path"
        _notify(progress_callback, 8.9, f"Trajetoria global pronta ({len(trajetoria_bola_global)} pontos)")

    stem = caminho_video.stem[:80]
    video_temporario = pasta_saida / f"{stem}_analisado_raw.mp4"
    video_saida = pasta_saida / f"{stem}_analisado.mp4"
    writer = None
    output_size = None
    quadros: list[QuadroAnalise] = []
    ball_samples: list[tuple[int, float, float]] = []
    player_tracks = {"P1": [], "P2": []}
    ball_track: list[tuple[int, int]] = []
    ball_detection_track: list[tuple[int, int]] = []
    ultimo_players: list[DetectionBox] = []
    ultimo_bola: BallDetection | None = None
    ultimo_bola_frame_idx: int | None = None
    pending_bola_inicio: tuple[int, BallDetection] | None = None
    falhas_bola_consecutivas = 0
    frame_anterior: np.ndarray | None = None
    frame_pre_anterior: np.ndarray | None = None
    anchors_bola: list[BallAnchor] | None = None
    tolerancia_anchor_bola_s = max(0.055, 0.72 / max(target_fps, 1.0))
    janela_saque_saida = _janela_overlay_saque_saida(velocidade_saque, indices, fps_original, target_fps)

    for posicao_saida, frame_idx in enumerate(indices):
        _notify(
            progress_callback,
            (9.0 if tentou_trajetoria_global else 4.0)
            + (posicao_saida / max(len(indices), 1)) * (85.0 if tentou_trajetoria_global else 90.0),
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
        ultimo_players = _atualizar_ultimo_players_por_slot(players, ultimo_players, frame.shape)

        tempo_s = (frame_idx / fps_original) if fps_original > 0 else posicao_saida / target_fps
        tempo_saida_s = posicao_saida / max(target_fps, 1.0)
        bola = None
        bola_vem_de_trajetoria_global = False
        if ocultar_bola_render:
            ultimo_bola = None
            ultimo_bola_frame_idx = None
            pending_bola_inicio = None
            falhas_bola_consecutivas = 0
            ball_track.clear()
            ball_detection_track.clear()
        else:
            prior_bola = _prior_bola_calibracao(anchors_bola or [], tempo_s, frame.shape)
            bola_global = trajetoria_bola_global.get(int(frame_idx))
            if bola_global is not None:
                bola = bola_global
                bola_vem_de_trajetoria_global = True
                if bola_global.source == "trajectory_prediction":
                    bola_local = _detectar_bola(
                        frame,
                        ultimo_bola,
                        frame_anterior,
                        players_validos,
                        ball_detection_track,
                        prior_bola,
                        calibracao,
                        frame_pre_anterior,
                        falhas_bola_consecutivas=falhas_bola_consecutivas,
                    )
                    if _candidato_substitui_predicao_global(bola_local, bola_global, frame.shape, players_validos, calibracao):
                        bola = bola_local
                        bola_vem_de_trajetoria_global = False
            elif (
                prior_bola is None
                and falhas_bola_consecutivas >= _int_env("TENNIS_XRAY_BALL_STALE_RESET_AFTER", 72)
            ):
                # Depois de uma lacuna longa, a ultima previsao deixa de ser
                # uma boa ancora fisica. Reiniciamos o segmento para permitir
                # reacquisicao forte sem arrastar uma trajetoria morta.
                ultimo_bola = None
                ultimo_bola_frame_idx = None
                pending_bola_inicio = None
                ball_track.clear()
                ball_detection_track.clear()
                falhas_bola_consecutivas = 0
            if bola is None and bola_global is None and ultimo_bola_frame_idx is not None:
                gap_frames = abs(int(frame_idx) - ultimo_bola_frame_idx)
                if gap_frames > _hard_reset_frames_bola(fps_original, hard_reset_bola_s, ultimo_bola):
                    ultimo_bola = None
                    pending_bola_inicio = None
                    ball_track.clear()
                    ball_detection_track.clear()
            if bola is None and bola_global is None:
                bola = _bola_anchor_exata(anchors_bola or [], tempo_s, frame.shape, tolerancia_anchor_bola_s)
            if bola is None and bola_global is None:
                if anchors_bola and prior_bola is None and not ball_detection_track and ultimo_bola is None:
                    bola = None
                else:
                    bola = _detectar_bola(
                        frame,
                        ultimo_bola,
                        frame_anterior,
                        players_validos,
                        ball_detection_track,
                        prior_bola,
                        calibracao,
                        frame_pre_anterior,
                        falhas_bola_consecutivas=falhas_bola_consecutivas,
                    )
                if bola is None and prior_bola is not None and _prior_preenchivel(prior_bola):
                    bola = _bola_estimativa_prior(prior_bola, frame.shape)
            if bola is not None and not _validar_bola_temporal(bola, ball_detection_track, frame.shape, prior_bola):
                bola = _bola_estimativa_prior(prior_bola, frame.shape) if prior_bola is not None and _prior_preenchivel(prior_bola) else None
            if bola is not None:
                bola = _suavizar_bola_com_prior(bola, prior_bola)
            if bola is None and bola_global is None:
                gap_frames_pred = abs(int(frame_idx) - int(ultimo_bola_frame_idx)) if ultimo_bola_frame_idx is not None else 0
                gap_steps_pred = max(1.0, gap_frames_pred / max(1.0, fps_original / max(target_fps, 1.0))) if gap_frames_pred else 1.0
                max_predicoes_render = _max_predicoes_render_bola(ultimo_bola)
                if desenhar_predicoes_bola and falhas_bola_consecutivas < max_predicoes_render:
                    bola = _bola_predita_por_rastro(
                        ball_track=ball_detection_track,
                        ultima_bola=ultimo_bola,
                        frame_shape=frame.shape,
                        gap_steps=gap_steps_pred,
                        falhas_consecutivas=falhas_bola_consecutivas,
                        calibracao=calibracao,
                    )
            if bola:
                eh_predicao = bola.source == "trajectory_prediction"
                if eh_predicao and not desenhar_predicoes_bola:
                    # A predicao ajuda a abrir a janela de busca, mas nao deve
                    # virar evidencia visual. Isso evita rastros imaginarios
                    # quando a bola real some ou o detector pega um artefato.
                    bola = None
                    falhas_bola_consecutivas += 1
                elif (
                    bola_global is None
                    and
                    prior_bola is None
                    and not ball_detection_track
                    and bola.source not in {"manual_anchor", "calibrated_fill"}
                ):
                    if _candidato_inicio_imediato_rastro_bola(bola):
                        confirmado = (int(frame_idx), bola)
                    else:
                        confirmado = _confirmar_inicio_rastro_bola(
                            pending_bola_inicio,
                            int(frame_idx),
                            bola,
                            frame.shape,
                            fps_original,
                        )
                    if confirmado is None:
                        pending_bola_inicio = (int(frame_idx), bola)
                        bola = None
                        falhas_bola_consecutivas += 1
                    else:
                        primeiro_idx, primeira_bola = confirmado
                        pending_bola_inicio = None
                        ultimo_bola = bola
                        ultimo_bola_frame_idx = int(frame_idx)
                        ball_samples.append((int(primeiro_idx), primeira_bola.x, primeira_bola.y))
                        ball_samples.append((int(frame_idx), bola.x, bola.y))
                        ball_detection_track.extend(
                            [
                                (int(primeira_bola.x), int(primeira_bola.y)),
                                (int(bola.x), int(bola.y)),
                            ]
                        )
                        ball_track.extend(
                            [
                                (int(primeira_bola.x), int(primeira_bola.y)),
                                (int(bola.x), int(bola.y)),
                            ]
                        )
                        max_detection_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_DETECTION_POINTS", 96))
                        max_track_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_RENDER_POINTS", 90))
                        ball_detection_track = ball_detection_track[-max_detection_points:]
                        ball_track = ball_track[-max_track_points:]
                        falhas_bola_consecutivas = 0
                else:
                    pending_bola_inicio = None
                    if ultimo_bola_frame_idx is not None and not eh_predicao:
                        gap_frames = abs(int(frame_idx) - ultimo_bola_frame_idx)
                        if gap_frames > _hard_reset_frames_bola(fps_original, hard_reset_bola_s, ultimo_bola):
                            ball_track.clear()
                            ball_detection_track.clear()
                    if not eh_predicao:
                        ultimo_bola = bola
                        ultimo_bola_frame_idx = int(frame_idx)
                        ball_samples.append((int(frame_idx), bola.x, bola.y))
                        if _bola_alimenta_tracking_local(bola, bola_vem_de_trajetoria_global):
                            ball_detection_track.append((int(bola.x), int(bola.y)))
                            max_detection_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_DETECTION_POINTS", 96))
                            ball_detection_track = ball_detection_track[-max_detection_points:]
                    ball_track.append((int(bola.x), int(bola.y)))
                    max_track_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_RENDER_POINTS", 90))
                    ball_track = ball_track[-max_track_points:]
                    falhas_bola_consecutivas = falhas_bola_consecutivas + 1 if eh_predicao else 0
            else:
                falhas_bola_consecutivas += 1

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

        ball_track_visual = _rastro_visual_bola_para_frame(
            trajetoria_bola_global,
            int(frame_idx),
            bola,
            fps_original,
        )
        if not ball_track_visual:
            ball_track_visual = ball_track[-_max_pontos_rastro_visual(fps_original):]

        anotado = _desenhar_frame(
            frame=frame,
            players=players,
            bola=bola,
            player_tracks=player_tracks,
            ball_track=ball_track_visual,
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
        frame_pre_anterior = frame_anterior
        frame_anterior = frame

    cap.release()
    if writer is not None:
        writer.release()

    if not quadros:
        raise RuntimeError("Nenhum frame valido foi lido do video enviado.")
    _validar_video_saida(video_temporario, "video temporario anotado")

    codec_saida = _transcodificar_para_h264(video_temporario, video_saida)
    _validar_video_saida(video_saida, "video analisado final")

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
            "desenha_predicoes_bola": desenhar_predicoes_bola,
            "gap_reset_bola_s": hard_reset_bola_s,
            "trajetoria_global_bola": bool(trajetoria_bola_global),
            "trajetoria_global_bola_pontos": len(trajetoria_bola_global),
            "modelo_bola_yolo": _metadata_modelo_yolo_bola(),
            "modelo_bola_tracknet": _metadata_modelo_tracknet(),
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


def _calibracao_para_rastro_bola(calibracao: dict | None) -> dict | None:
    if not isinstance(calibracao, dict):
        return None

    filtrada = dict(calibracao)
    marks = calibracao.get("ball_marks")
    if not isinstance(marks, list):
        return filtrada

    filtrada["ball_marks"] = [
        mark
        for mark in marks
        if isinstance(mark, dict)
        and str(mark.get("role") or mark.get("event") or mark.get("type") or "") != "serve_contact_ground"
    ]
    return filtrada


def detectar_rastro_bola_calibracao(
    caminho_video: Path,
    calibracao: dict | None = None,
    seed: dict | None = None,
    step_s: float = 0.02,
    min_confidence: float = 0.40,
    max_points: int = 360,
) -> dict:
    """Suggest tennis-ball trajectory marks directly from the calibration video.

    This reuses the same detector used by the real analysis pipeline, but skips
    video rendering. Manual ball anchors already present in the calibration are
    used only as priors; the frontend decides how to merge the suggestions.
    """

    caminho_video = Path(caminho_video)
    calibracao = calibracao if isinstance(calibracao, dict) else None
    calibracao_rastro = _calibracao_para_rastro_bola(calibracao)
    step_s = max(0.02, min(0.18, float(step_s or 0.02)))
    min_confidence = max(0.18, min(0.92, float(min_confidence or 0.48)))
    max_points = max(12, min(900, int(max_points or 360)))

    cap = cv2.VideoCapture(str(caminho_video))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {caminho_video}")

    fps_original = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        cap.release()
        raise RuntimeError("Nao foi possivel ler a quantidade de frames do video.")

    target_fps = min(max(fps_original, 1.0), 1.0 / step_s)
    if isinstance(seed, dict):
        try:
            return _detectar_rastro_bola_com_seed(
                cap=cap,
                total_frames=total_frames,
                fps_original=fps_original,
                calibracao=calibracao,
                seed=seed,
                step_s=step_s,
                min_confidence=min_confidence,
                max_points=max_points,
                target_fps=target_fps,
            )
        finally:
            cap.release()

    max_frames = _int_env("TENNIS_XRAY_AUTO_BALL_MAX_FRAMES", min(720, max(max_points * 2, 180)))
    indices = _selecionar_indices_intervalo_bola(total_frames, fps_original, target_fps, max_frames, calibracao_rastro)
    if not indices:
        indices = _selecionar_indices(total_frames, fps_original, target_fps, max_frames, False)

    modelo_yolo = _load_yolo_model()
    detector_usado = "yolo_person+opencv_ball_auto" if modelo_yolo is not None else "opencv_auto"
    frame_anterior: np.ndarray | None = None
    anchors_bola: list[BallAnchor] | None = None
    ultimo_players: list[DetectionBox] = []
    ultimo_bola: BallDetection | None = None
    ultimo_bola_frame_idx: int | None = None
    ball_track: list[tuple[int, int]] = []
    frame_pre_anterior: np.ndarray | None = None
    marcas: list[dict] = []
    frames_processados = 0
    deteccoes_brutas = 0
    falhas_consecutivas = 0
    tolerancia_anchor_bola_s = max(0.055, 0.72 / max(target_fps, 1.0))

    for frame_idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            continue

        frames_processados += 1
        if anchors_bola is None:
            anchors_bola = _anchors_bola_calibracao(calibracao_rastro, frame.shape)

        players_detectados = _detectar_jogadores(frame, modelo_yolo)
        players_escopo = _filtrar_jogadores_escopo_quadra(players_detectados, calibracao, frame.shape)
        if _tem_anchors_jogadores(calibracao):
            players = _ordenar_jogadores_por_calibracao(players_escopo, calibracao, frame.shape, ultimo_players)
        else:
            players = _normalizar_dois_jogadores(players_escopo, ultimo_players, frame.shape)
        players_validos = [box for box in players if _box_desenhavel(box)]
        ultimo_players = _atualizar_ultimo_players_por_slot(players, ultimo_players, frame.shape)

        tempo_s = (frame_idx / fps_original) if fps_original > 0 else 0.0
        prior_bola = _prior_bola_calibracao(anchors_bola or [], tempo_s, frame.shape)
        if ultimo_bola_frame_idx is not None:
            gap_frames = abs(int(frame_idx) - ultimo_bola_frame_idx)
            if gap_frames > max(4, int(round(fps_original * 0.35))):
                ultimo_bola = None
                ball_track.clear()

        bola = _bola_anchor_exata(anchors_bola or [], tempo_s, frame.shape, tolerancia_anchor_bola_s)
        if bola is None:
            if anchors_bola and prior_bola is None and not ball_track and ultimo_bola is None:
                bola = None
            else:
                bola = _detectar_bola(
                    frame,
                    ultimo_bola,
                    frame_anterior,
                    players_validos,
                    ball_track,
                    prior_bola,
                    calibracao,
                    frame_pre_anterior,
                    falhas_bola_consecutivas=falhas_bola_consecutivas,
                )
            if bola is None and prior_bola is not None and _prior_preenchivel(prior_bola):
                bola = _bola_estimativa_prior(prior_bola, frame.shape)

        if bola is not None and not _validar_bola_temporal(bola, ball_track, frame.shape, prior_bola):
            bola = _bola_estimativa_prior(prior_bola, frame.shape) if prior_bola is not None and _prior_preenchivel(prior_bola) else None
        if bola is not None:
            bola = _suavizar_bola_com_prior(bola, prior_bola)
        if bola is None:
            gap_frames_pred = abs(int(frame_idx) - int(ultimo_bola_frame_idx)) if ultimo_bola_frame_idx is not None else 0
            gap_steps_pred = max(1.0, gap_frames_pred / max(1.0, fps_original / max(target_fps, 1.0))) if gap_frames_pred else 1.0
            max_predicoes_render = _int_env("TENNIS_XRAY_BALL_RENDER_PREDICT_MAX_GAPS", 8)
            if falhas_consecutivas < max_predicoes_render:
                bola = _bola_predita_por_rastro(
                    ball_track=ball_track,
                    ultima_bola=ultimo_bola,
                    frame_shape=frame.shape,
                    gap_steps=gap_steps_pred,
                    falhas_consecutivas=falhas_consecutivas,
                    calibracao=calibracao,
                )

        if bola is not None:
            eh_predicao = bola.source == "trajectory_prediction"
            if not eh_predicao:
                deteccoes_brutas += 1
            limiar_gravacao = max(0.22, min_confidence * 0.62) if eh_predicao else min_confidence
            if bola.confidence >= limiar_gravacao:
                h, w = frame.shape[:2]
                marcas.append(
                    {
                        "x": round(max(0.0, min(1.0, bola.x / max(w, 1))), 5),
                        "y": round(max(0.0, min(1.0, bola.y / max(h, 1))), 5),
                        "time_s": round(float(tempo_s), 3),
                        "frame_index": int(frame_idx),
                        "role": "trajectory",
                        "label": "Rastro estimado da bolinha" if eh_predicao else "Rastro automatico da bolinha",
                        "source": "auto_prediction" if eh_predicao else "auto_track",
                        "confidence": round(float(bola.confidence), 3),
                        "radius_px": round(float(bola.radius), 2),
                        "detector_source": bola.source or detector_usado,
                    }
                )
            if not eh_predicao:
                ultimo_bola = bola
                ultimo_bola_frame_idx = int(frame_idx)
                ball_track.append((int(bola.x), int(bola.y)))
                max_track_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_RENDER_POINTS", 90))
                ball_track = ball_track[-max_track_points:]
            falhas_consecutivas = falhas_consecutivas + 1 if eh_predicao else 0
        else:
            falhas_consecutivas += 1

        frame_pre_anterior = frame_anterior
        frame_anterior = frame

    cap.release()
    marcas = _filtrar_marcas_auto_bola(marcas)
    if len(marcas) > max_points:
        indices_marcados = sorted(set(np.linspace(0, len(marcas) - 1, max_points, dtype=int).tolist()))
        marcas = [marcas[i] for i in indices_marcados]

    confiancas = [float(marca.get("confidence", 0.0)) for marca in marcas]
    return {
        "marks": marcas,
        "quality": {
            "metodo": detector_usado,
            "step_s": round(step_s, 3),
            "fps_video": round(fps_original, 3),
            "target_fps": round(target_fps, 3),
            "duracao_s": round(total_frames / max(fps_original, 1.0), 3),
            "frames_analisados": frames_processados,
            "deteccoes_brutas": deteccoes_brutas,
            "pontos_aceitos": len(marcas),
            "confianca_media": round(float(fmean(confiancas)), 3) if confiancas else 0.0,
            "min_confidence": round(min_confidence, 3),
        },
    }


def _detectar_rastro_bola_com_seed(
    cap,
    total_frames: int,
    fps_original: float,
    calibracao: dict | None,
    seed: dict,
    step_s: float,
    min_confidence: float,
    max_points: int,
    target_fps: float,
) -> dict:
    try:
        resultado_beam = _detectar_rastro_bola_com_seed_beam(
            cap=cap,
            total_frames=total_frames,
            fps_original=fps_original,
            calibracao=calibracao,
            seed=seed,
            step_s=step_s,
            min_confidence=min_confidence,
            max_points=max_points,
            target_fps=target_fps,
        )
        if len(resultado_beam.get("marks") or []) >= max(6, min(max_points, 18)):
            return resultado_beam
    except Exception as exc:
        logger.warning("Beam tracker da bolinha falhou; usando fallback local: %s", exc)

    try:
        seed_time_s = max(0.0, float(seed.get("time_s", 0.0)))
        seed_x_norm = float(seed.get("x"))
        seed_y_norm = float(seed.get("y"))
    except (TypeError, ValueError):
        raise ValueError("Seed inicial da bolinha invalida.") from None

    if not math.isfinite(seed_x_norm) or not math.isfinite(seed_y_norm) or not 0 <= seed_x_norm <= 1 or not 0 <= seed_y_norm <= 1:
        raise ValueError("Seed inicial da bolinha deve ter coordenadas normalizadas entre 0 e 1.")

    fps_ref = max(fps_original, 1.0)
    seed_frame_idx = max(0, min(total_frames - 1, int(round(seed_time_s * fps_ref))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(seed_frame_idx))
    ok, seed_frame = cap.read()
    if not ok:
        raise ValueError("Nao foi possivel ler o frame da marcacao inicial da bolinha.")

    h_seed, w_seed = seed_frame.shape[:2]
    seed_px = (seed_x_norm * w_seed, seed_y_norm * h_seed)
    radius = max(3.0, min(w_seed, h_seed) * 0.005)
    ultima_bola = BallDetection(seed_px[0], seed_px[1], radius, 0.99, "manual_seed")
    ultimo_bola_frame_idx = seed_frame_idx
    frame_anterior: np.ndarray | None = seed_frame
    frame_pre_anterior: np.ndarray | None = seed_frame
    template_bola = _extrair_template_bola(seed_frame, ultima_bola)
    ball_track: list[tuple[int, int]] = [(int(seed_px[0]), int(seed_px[1]))]
    ultimo_players: list[DetectionBox] = []
    marcas: list[dict] = []
    frames_processados = 0
    deteccoes_brutas = 0
    falhas_consecutivas = 0
    stride_frames = max(1, int(round(step_s * fps_ref)))
    max_frames = _int_env("TENNIS_XRAY_AUTO_BALL_SEEDED_MAX_FRAMES", min(900, max(max_points * 3, 180)))
    indices = list(range(seed_frame_idx + stride_frames, total_frames, stride_frames))[:max_frames]
    modelo_yolo = _load_yolo_model()
    detector_usado = "seeded_yolo_person+opencv_ball" if modelo_yolo is not None else "seeded_opencv_ball"

    for frame_idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            continue

        frames_processados += 1
        players_detectados = _detectar_jogadores(frame, modelo_yolo)
        players_escopo = _filtrar_jogadores_escopo_quadra(players_detectados, calibracao, frame.shape)
        if _tem_anchors_jogadores(calibracao):
            players = _ordenar_jogadores_por_calibracao(players_escopo, calibracao, frame.shape, ultimo_players)
        else:
            players = _normalizar_dois_jogadores(players_escopo, ultimo_players, frame.shape)
        players_validos = [box for box in players if _box_desenhavel(box)]
        ultimo_players = _atualizar_ultimo_players_por_slot(players, ultimo_players, frame.shape)

        gap_frames = max(1, int(frame_idx) - int(ultimo_bola_frame_idx))
        gap_steps = max(1.0, gap_frames / max(stride_frames, 1))
        h, w = frame.shape[:2]
        min_dim = float(min(w, h))
        gate_px = max(18.0, min_dim * (0.034 + min(gap_steps, 5.0) * 0.012))
        gate_px = min(gate_px, min_dim * 0.14)
        if falhas_consecutivas > 0:
            gate_px *= min(1.85, 1.0 + falhas_consecutivas * 0.22)
        if len(ball_track) >= 3 and falhas_consecutivas == 0:
            gate_px *= 0.82
        pred_x, pred_y, pred_conf = _predizer_bola_cinematica(ball_track, ultima_bola, gap_steps, frame.shape)
        last_x, last_y = map(float, ball_track[-1])
        if len(ball_track) < 4:
            peso_predicao = 0.0
        elif falhas_consecutivas == 0:
            peso_predicao = 0.28
        else:
            peso_predicao = 0.16
        prior_x = last_x * (1.0 - peso_predicao) + pred_x * peso_predicao
        prior_y = last_y * (1.0 - peso_predicao) + pred_y * peso_predicao
        prior_bola = BallPrior(
            x=prior_x,
            y=prior_y,
            gate_px=gate_px,
            confidence=max(0.46, min(0.84, pred_conf - min(gap_steps, 8.0) * 0.038)),
            interval_s=max(step_s, gap_frames / fps_ref),
        )

        bola = _detectar_bola(
            frame,
            ultima_bola,
            frame_anterior,
            players_validos,
            ball_track,
            prior_bola,
            calibracao,
            frame_pre_anterior,
            falhas_bola_consecutivas=falhas_consecutivas,
        )
        bola_template = _candidato_bola_template(
            frame=frame,
            template=template_bola,
            prior_bola=prior_bola,
            players=players_validos,
            ball_track=ball_track,
            calibracao=calibracao,
        )
        if bola_template is not None and (bola is None or bola_template.confidence > bola.confidence + 0.04):
            bola = bola_template
        if bola is not None and not _validar_bola_temporal(bola, ball_track, frame.shape, prior_bola):
            bola = None
        if bola is not None:
            bola = _suavizar_bola_com_prior(bola, prior_bola)

        if bola is None or bola.confidence < min_confidence:
            bola_predita = None
            max_predicoes_render = _int_env("TENNIS_XRAY_BALL_RENDER_PREDICT_MAX_GAPS", 8)
            if falhas_consecutivas < max_predicoes_render:
                bola_predita = _bola_predita_por_rastro(
                    ball_track=ball_track,
                    ultima_bola=ultima_bola,
                    frame_shape=frame.shape,
                    gap_steps=gap_steps,
                    falhas_consecutivas=falhas_consecutivas,
                    calibracao=calibracao,
                )
            limiar_predicao = max(0.24, min_confidence * 0.70)
            if bola_predita is None or bola_predita.confidence < limiar_predicao:
                falhas_consecutivas += 1
                frame_pre_anterior = frame_anterior
                frame_anterior = frame
                continue
            bola = bola_predita

        deteccoes_brutas += 1
        eh_predicao = bola.source == "trajectory_prediction"
        if eh_predicao:
            deteccoes_brutas -= 1
        tempo_s = (frame_idx / fps_ref) if fps_ref > 0 else 0.0
        marcas.append(
            {
                "x": round(max(0.0, min(1.0, bola.x / max(w, 1))), 5),
                "y": round(max(0.0, min(1.0, bola.y / max(h, 1))), 5),
                "time_s": round(float(tempo_s), 3),
                "frame_index": int(frame_idx),
                "role": "trajectory",
                "label": "Rastro estimado da bolinha" if eh_predicao else "Rastro automatico da bolinha",
                "source": "auto_prediction" if eh_predicao else "auto_track",
                "confidence": round(float(bola.confidence), 3),
                "radius_px": round(float(bola.radius), 2),
                "detector_source": bola.source or detector_usado,
            }
        )
        falhas_consecutivas = falhas_consecutivas + 1 if eh_predicao else 0
        if not eh_predicao:
            ultima_bola = bola
            ultimo_bola_frame_idx = int(frame_idx)
            ball_track.append((int(bola.x), int(bola.y)))
            max_track_points = max(18, _int_env("TENNIS_XRAY_BALL_TRACK_RENDER_POINTS", 90))
            ball_track = ball_track[-max_track_points:]
        if not eh_predicao and bola.confidence >= 0.44:
            novo_template = _extrair_template_bola(frame, bola)
            if novo_template is not None:
                template_bola = novo_template
        frame_pre_anterior = frame_anterior
        frame_anterior = frame
        if len(marcas) >= max_points:
            break

    marcas = _filtrar_marcas_auto_bola(marcas)
    confiancas = [float(marca.get("confidence", 0.0)) for marca in marcas]
    return {
        "marks": marcas,
        "quality": {
            "metodo": detector_usado,
            "modo": "seed_manual_local",
            "step_s": round(step_s, 3),
            "fps_video": round(fps_original, 3),
            "target_fps": round(target_fps, 3),
            "seed_time_s": round(seed_frame_idx / fps_ref, 3),
            "seed_frame_index": int(seed_frame_idx),
            "duracao_s": round(total_frames / fps_ref, 3),
            "frames_analisados": frames_processados,
            "deteccoes_brutas": deteccoes_brutas,
            "pontos_aceitos": len(marcas),
            "falhas_consecutivas_finais": falhas_consecutivas,
            "confianca_media": round(float(fmean(confiancas)), 3) if confiancas else 0.0,
            "min_confidence": round(min_confidence, 3),
        },
    }


def _reduzir_indices_trajetoria_global(indices: list[int], fps_original: float) -> list[int]:
    """Amostra frames para o solver global sem travar a renderizacao.

    A renderizacao pode estar em 60fps, mas o solver global nao precisa rodar
    inferencia pesada em cada frame. Ele resolve a rota em baixa amostragem e a
    etapa seguinte interpola os frames intermediarios.
    """

    if not indices:
        return []
    fps_ref = max(float(fps_original or 0.0), 1.0)
    target_fps = max(3.0, min(fps_ref, _float_env("TENNIS_XRAY_GLOBAL_BALL_FPS", min(12.0, fps_ref))))
    stride_frames = max(1, int(round(fps_ref / target_fps)))
    selecionados: list[int] = []
    ultimo = -10**9
    for indice in sorted(set(int(item) for item in indices)):
        if not selecionados or indice - ultimo >= stride_frames:
            selecionados.append(indice)
            ultimo = indice
    if selecionados[-1] != int(indices[-1]):
        selecionados.append(int(indices[-1]))

    max_frames = _int_env("TENNIS_XRAY_GLOBAL_BALL_MAX_FRAMES", 220)
    if len(selecionados) > max_frames:
        posicoes = np.linspace(0, len(selecionados) - 1, max_frames, dtype=int)
        selecionados = [selecionados[int(pos)] for pos in posicoes]
    return sorted(set(selecionados))


def _expandir_trajetoria_global_para_indices_render(
    trajetoria_sparse: dict[int, BallDetection],
    indices_render: list[int],
    fps_original: float,
    calibracao: dict | None = None,
    frame_shape: tuple[int, int, int] | None = None,
) -> dict[int, BallDetection]:
    if not trajetoria_sparse or not indices_render:
        return {}

    pontos = sorted((int(frame_idx), bola) for frame_idx, bola in trajetoria_sparse.items())
    if not pontos:
        return {}

    fps_ref = max(float(fps_original or 0.0), 1.0)
    max_gap_frames = max(2, int(round(fps_ref * _float_env("TENNIS_XRAY_GLOBAL_BALL_INTERP_MAX_GAP_S", 0.80))))
    shape_valido = frame_shape if frame_shape and frame_shape[0] > 0 and frame_shape[1] > 0 else None
    resultado: dict[int, BallDetection] = {}
    cursor = 0

    for frame_idx in sorted(set(int(item) for item in indices_render)):
        while cursor + 1 < len(pontos) and pontos[cursor + 1][0] < frame_idx:
            cursor += 1

        frame_a, bola_a = pontos[cursor]
        if frame_idx < frame_a:
            continue
        if frame_idx == frame_a:
            if _bola_renderizavel_no_escopo(bola_a, calibracao, shape_valido):
                resultado[frame_idx] = bola_a
            continue

        if cursor + 1 >= len(pontos):
            continue
        frame_b, bola_b = pontos[cursor + 1]
        if frame_idx > frame_b:
            continue
        if frame_idx == frame_b:
            if _bola_renderizavel_no_escopo(bola_b, calibracao, shape_valido):
                resultado[frame_idx] = bola_b
            continue

        gap = frame_b - frame_a
        if gap <= 0 or gap > max_gap_frames:
            continue
        t = (frame_idx - frame_a) / gap
        x = bola_a.x + (bola_b.x - bola_a.x) * t
        y = bola_a.y + (bola_b.y - bola_a.y) * t
        radius = bola_a.radius + (bola_b.radius - bola_a.radius) * t
        confidence = max(0.16, min(bola_a.confidence, bola_b.confidence) * 0.82)
        bola_interpolada = BallDetection(
            x=float(x),
            y=float(y),
            radius=float(max(2.0, radius)),
            confidence=float(min(0.56, confidence)),
            source="trajectory_prediction",
            motion_score=0.08,
            yellow_ratio=0.08,
        )
        if _bola_renderizavel_no_escopo(bola_interpolada, calibracao, shape_valido):
            resultado[frame_idx] = bola_interpolada

    return resultado


def _trajetoria_global_render_confiavel(
    trajetoria_sparse: dict[int, BallDetection],
    trajetoria_render: dict[int, BallDetection],
) -> bool:
    if not trajetoria_sparse or not trajetoria_render:
        return False

    reais = [
        bola
        for bola in trajetoria_sparse.values()
        if bola.source != "trajectory_prediction"
        and _fonte_bola_global_confiavel(bola.source)
    ]
    if len(reais) < _int_env("TENNIS_XRAY_GLOBAL_BALL_RENDER_MIN_REAL", 4):
        return False

    predicoes = sum(1 for bola in trajetoria_render.values() if bola.source == "trajectory_prediction")
    taxa_predicao = predicoes / max(len(trajetoria_render), 1)
    limite_padrao = _float_env("TENNIS_XRAY_GLOBAL_BALL_RENDER_MAX_PRED_RATE", 0.78)
    if taxa_predicao <= limite_padrao:
        return True

    # Quando o modelo entrega ancoras fortes mas esparsas, a trilha correta tem
    # necessariamente muitos pontos interpolados. Nesse modo aceitamos uma taxa
    # maior de predicao, desde que haja varias ancoras reais confiaveis para
    # sustentar os segmentos renderizados.
    min_ancoras_segmentadas = _int_env("TENNIS_XRAY_GLOBAL_BALL_SEGMENT_MIN_ANCHORS", 8)
    limite_segmentado = _float_env("TENNIS_XRAY_GLOBAL_BALL_SEGMENT_MAX_PRED_RATE", 0.95)
    if len(reais) < min_ancoras_segmentadas or taxa_predicao > limite_segmentado:
        return False
    return True


def _rastro_visual_bola_para_frame(
    trajetoria_global: dict[int, BallDetection],
    frame_idx: int,
    bola_atual: BallDetection | None,
    fps_original: float,
) -> list[tuple[int, int]]:
    pontos: list[tuple[int, float, float]] = []
    fps_ref = max(float(fps_original or 0.0), 1.0)
    max_pontos = _max_pontos_rastro_visual(fps_ref)
    max_gap = max(2, int(round(fps_ref * _float_env("TENNIS_XRAY_BALL_VISUAL_TRAIL_MAX_GAP_S", 0.75))))
    max_idade = max(max_pontos, max_gap) if bola_atual is not None else max_pontos
    corte_idade = int(frame_idx) - max_idade

    for idx, bola in sorted(trajetoria_global.items()):
        idx_int = int(idx)
        if idx_int > frame_idx:
            break
        if idx_int < corte_idade:
            continue
        pontos.append((idx_int, float(bola.x), float(bola.y)))

    if bola_atual is not None:
        if not pontos or pontos[-1][0] != int(frame_idx):
            pontos.append((int(frame_idx), float(bola_atual.x), float(bola_atual.y)))
        else:
            pontos[-1] = (int(frame_idx), float(bola_atual.x), float(bola_atual.y))

    if len(pontos) < 2:
        return [(int(x), int(y)) for _idx, x, y in pontos]

    inicio = len(pontos) - 1
    while inicio > 0:
        if pontos[inicio][0] - pontos[inicio - 1][0] > max_gap:
            break
        inicio -= 1

    segmento = pontos[inicio:][-max_pontos:]
    return [(int(round(x)), int(round(y))) for _idx, x, y in segmento]


def _max_pontos_rastro_visual(fps_original: float) -> int:
    fps_ref = max(float(fps_original or 0.0), 1.0)
    duracao_s = _float_env("TENNIS_XRAY_BALL_VISUAL_TRAIL_S", 0.45)
    return max(8, int(round(fps_ref * max(0.12, min(1.20, duracao_s)))))


def _calibracao_quadra_basica_disponivel(calibracao: dict | None) -> bool:
    pontos = _pontos_calibracao_normalizados(calibracao)
    return all(nome in pontos for nome in ("sup_esquerda", "sup_direita", "inf_direita", "inf_esquerda"))


def _fonte_bola_normalizada(source: str) -> str:
    fonte = str(source or "")
    if fonte.startswith("global_"):
        fonte = fonte[len("global_") :]
    if fonte.endswith("_reacquired"):
        fonte = fonte[: -len("_reacquired")]
    return fonte


def _fonte_bola_global_confiavel(source: str) -> bool:
    return _fonte_bola_normalizada(source) in {"manual_anchor", "calibrated_fill", "manual_seed", "tracknet", "ball_yolo", "beam_contact"}


def _candidato_global_sem_calibracao_valido(candidato: BallDetection, frame_shape: tuple[int, int, int]) -> bool:
    """Evita que testes sem quadra calibrada sejam dominados por artefatos.

    Sem homografia/corredor de quadra, candidatos puramente visuais aparecem em
    logos, mochilas, bancos, outras quadras e cantos do frame. Nessa condição a
    trilha global deve usar fontes mais fortes (TrackNet/YOLO/manual) ou um
    candidato OpenCV com evidência local muito forte.
    """

    if _candidato_bola_em_borda_frame(candidato, frame_shape, margem_px=max(24.0, min(frame_shape[:2]) * 0.035)):
        return False
    if _fonte_bola_global_confiavel(candidato.source):
        return True
    return (
        candidato.confidence >= 0.62
        and candidato.motion_score >= 0.080
        and candidato.yellow_ratio >= 0.180
    )


def _precalcular_trajetoria_bola_global(
    caminho_video: Path,
    indices: list[int],
    fps_original: float,
    calibracao: dict | None,
    progress_callback: ProgressCallback | None = None,
    progress_start: float = 4.2,
    progress_end: float = 8.8,
) -> dict[int, BallDetection]:
    """Resolve uma trilha unica e coerente da bolinha antes da renderizacao."""

    if not indices:
        return {}

    cap = cv2.VideoCapture(str(caminho_video))
    if not cap.isOpened():
        return {}

    fps_ref = max(float(fps_original or 0.0), 1.0)
    beam_width = _int_env("TENNIS_XRAY_GLOBAL_BALL_BEAM_WIDTH", 10)
    tem_calibracao_quadra = _calibracao_quadra_basica_disponivel(calibracao)
    max_misses_padrao = 54 if tem_calibracao_quadra else 8
    max_misses = _int_env("TENNIS_XRAY_GLOBAL_BALL_MAX_MISSES", max_misses_padrao)
    min_detected = _int_env("TENNIS_XRAY_GLOBAL_BALL_MIN_DETECTED", 4)
    max_candidates = _int_env("TENNIS_XRAY_GLOBAL_BALL_MAX_CANDIDATES", 16)
    min_real_rate = _float_env("TENNIS_XRAY_GLOBAL_BALL_MIN_REAL_RATE", 0.22 if tem_calibracao_quadra else 0.28)
    min_reliable = _int_env("TENNIS_XRAY_GLOBAL_BALL_MIN_RELIABLE", 3 if tem_calibracao_quadra else 4)

    frame_anterior: np.ndarray | None = None
    frame_pre_anterior: np.ndarray | None = None
    anchors_bola: list[BallAnchor] | None = None
    ancoras_confiaveis: list[tuple[int, float, BallDetection]] = []
    resgates_contato: list[tuple[int, float, BallDetection]] = []
    estados: list[BallBeamState] = []
    melhor_estado: BallBeamState | None = None
    modelo_pessoas = _load_yolo_model() if _bool_env("TENNIS_XRAY_GLOBAL_BALL_PLAYER_CONTEXT", False) else None
    ultimo_players_global: list[DetectionBox] = []
    total_indices = max(len(indices), 1)
    ultimo_progresso_emitido = -1

    try:
        for posicao_global, frame_idx in enumerate(indices):
            bucket_progresso = int((posicao_global / total_indices) * 100)
            if bucket_progresso != ultimo_progresso_emitido and (posicao_global == 0 or posicao_global % 4 == 0):
                ultimo_progresso_emitido = bucket_progresso
                progresso = progress_start + (posicao_global / total_indices) * max(0.0, progress_end - progress_start)
                _notify(
                    progress_callback,
                    progresso,
                    f"Resolvendo trajetoria global da bolinha ({posicao_global + 1}/{len(indices)})",
                )
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
            ok, frame = cap.read()
            if not ok:
                continue

            h, w = frame.shape[:2]
            min_dim = float(min(w, h))
            tempo_s = int(frame_idx) / fps_ref
            if anchors_bola is None:
                anchors_bola = _anchors_bola_calibracao(calibracao, frame.shape)

            players_global: list[DetectionBox] = []
            if modelo_pessoas is not None:
                players_detectados = _detectar_jogadores(frame, modelo_pessoas)
                players_escopo = _filtrar_jogadores_escopo_quadra(players_detectados, calibracao, frame.shape)
                if _tem_anchors_jogadores(calibracao):
                    players_ordenados = _ordenar_jogadores_por_calibracao(
                        players_escopo,
                        calibracao,
                        frame.shape,
                        ultimo_players_global,
                    )
                else:
                    players_ordenados = _normalizar_dois_jogadores(players_escopo, ultimo_players_global, frame.shape)
                players_global = [box for box in players_ordenados if _box_desenhavel(box)]
                ultimo_players_global = _atualizar_ultimo_players_por_slot(
                    players_ordenados,
                    ultimo_players_global,
                    frame.shape,
                )

            candidatos = _candidatos_bola_amplos(
                frame=frame,
                frame_anterior=frame_anterior,
                frame_pre_anterior=frame_pre_anterior,
                players=players_global,
                calibracao=calibracao,
            )
            anchor = _bola_anchor_exata(anchors_bola or [], tempo_s, frame.shape, max(0.045, 0.70 / fps_ref))
            if anchor is not None:
                candidatos.insert(0, anchor)
            candidatos = _deduplicar_candidatos_bola_global(candidatos)[:max_candidates]
            contatos_frame: list[BallDetection] = []
            for candidato in candidatos:
                if _candidato_beam_resgate_contato(candidato, players_global, frame.shape, calibracao):
                    contato = BallDetection(
                        candidato.x,
                        candidato.y,
                        candidato.radius,
                        min(0.76, max(0.50, candidato.confidence)),
                        "beam_contact",
                        candidato.motion_score,
                        candidato.yellow_ratio,
                    )
                    resgates_contato.append(
                        (
                            int(frame_idx),
                            tempo_s,
                            contato,
                        )
                    )
                    contatos_frame.append(contato)
            if contatos_frame and _bool_env("TENNIS_XRAY_GLOBAL_BALL_CONTACT_CANDIDATES", False):
                candidatos = _deduplicar_candidatos_bola_global([*contatos_frame, *candidatos])[:max_candidates]
            candidatos = [
                candidato
                for candidato in candidatos
                if _candidato_global_tem_evidencia_minima(candidato)
                and (tem_calibracao_quadra or _candidato_global_sem_calibracao_valido(candidato, frame.shape))
                and not _candidato_bola_em_borda_frame(candidato, frame.shape, margem_px=max(18.0, min_dim * 0.022))
                and (
                    _ancora_bola_global_forte_isolada(candidato)
                    or _candidato_bola_no_corredor_quadra_central(
                        candidato,
                        calibracao,
                        frame.shape,
                        margem_px=max(24.0, min_dim * 0.035),
                        margem_ar_px=max(64.0, min_dim * 0.095),
                    )
                )
            ]
            melhor_ancora_confiavel = _melhor_ancora_bola_global_confiavel(candidatos)
            if melhor_ancora_confiavel is not None:
                ancoras_confiaveis.append((int(frame_idx), tempo_s, melhor_ancora_confiavel))

            proximos: list[BallBeamState] = []

            for candidato in candidatos:
                if not _candidato_inicio_global_valido(candidato):
                    continue
                if not tem_calibracao_quadra and not _fonte_bola_global_confiavel(candidato.source):
                    continue
                if (
                    candidato.source not in {"manual_anchor", "calibrated_fill"}
                    and _candidato_em_zona_jogador(candidato, players_global, frame.shape)
                    and not (
                        candidato.source in {"tracknet", "ball_yolo"}
                        and candidato.confidence >= 0.74
                        and candidato.motion_score >= 0.14
                        and candidato.yellow_ratio >= 0.12
                    )
                ):
                    continue
                proximos.append(
                    BallBeamState(
                        x=candidato.x,
                        y=candidato.y,
                        vx=0.0,
                        vy=0.0,
                        cost=_custo_deteccao_global(candidato, source_start=True),
                        misses=0,
                        detected=1,
                        path=[_ponto_trajetoria_global_dict(candidato, int(frame_idx), tempo_s)],
                    )
                )

            for estado in estados:
                pred_x = max(0.0, min(float(w - 1), estado.x + estado.vx))
                pred_y = max(0.0, min(float(h - 1), estado.y + estado.vy))
                velocidade = math.hypot(estado.vx, estado.vy)
                try:
                    frame_anterior_estado = int(estado.path[-1]["frame_index"])
                except (IndexError, KeyError, TypeError, ValueError):
                    frame_anterior_estado = int(frame_idx)
                intervalo_frames_estado = max(1, int(frame_idx) - frame_anterior_estado)
                intervalo_norm = max(1.0, intervalo_frames_estado / max(1.0, fps_ref / 60.0))
                gate = max(42.0, min_dim * 0.048, velocidade * 2.35 + 24.0 + estado.misses * 9.0)
                if estado.detected <= 2:
                    gate = max(gate, min_dim * 0.105)
                salto_absoluto_max = max(
                    76.0,
                    min_dim * (0.070 + 0.030 * min(intervalo_norm, 4.0))
                    + min(velocidade * 0.38, min_dim * 0.105)
                    + estado.misses * 16.0,
                )
                teto_fisico = max(
                    96.0,
                    min_dim * (0.084 + 0.019 * min(intervalo_norm, 4.0))
                    + min(estado.misses, 6) * 6.0,
                )
                if estado.detected <= 2:
                    teto_fisico *= 1.18
                salto_absoluto_max = min(salto_absoluto_max, teto_fisico)

                for candidato in candidatos:
                    dist = math.hypot(candidato.x - pred_x, candidato.y - pred_y)
                    evidencia_local_forte = (
                        candidato.source in {"manual_anchor", "calibrated_fill"}
                        or candidato.motion_score >= 0.060
                        or candidato.yellow_ratio >= 0.155
                    )
                    gate_candidato = gate * (1.22 if candidato.confidence >= 0.82 and evidencia_local_forte else 1.0)
                    if candidato.source in {"tracknet", "ball_yolo"} and not evidencia_local_forte and dist > gate * 0.46:
                        continue
                    if candidato.source not in {"manual_anchor", "calibrated_fill", "tracknet", "ball_yolo"}:
                        if dist > gate * 0.72 and candidato.motion_score < 0.065 and candidato.yellow_ratio < 0.16:
                            continue
                    em_zona_jogador = (
                        candidato.source not in {"manual_anchor", "calibrated_fill"}
                        and _candidato_em_zona_jogador(candidato, players_global, frame.shape)
                    )
                    if em_zona_jogador and dist > gate * 0.42:
                        continue
                    path_reaquisicao: list[dict] | None = None
                    vx_reaquisicao = 0.0
                    vy_reaquisicao = 0.0
                    custo_reaquisicao = 0.0
                    precisa_reaquisicao = estado.misses >= 3 and dist > max(72.0, min_dim * 0.075)
                    if precisa_reaquisicao or dist > gate_candidato or dist > salto_absoluto_max:
                        tentativa = _tentar_reaquisicao_global_bola(
                            estado=estado,
                            candidato=candidato,
                            frame_idx=int(frame_idx),
                            tempo_s=tempo_s,
                            fps_ref=fps_ref,
                            min_dim=min_dim,
                        )
                        if tentativa is None:
                            continue
                        path_reaquisicao, vx_reaquisicao, vy_reaquisicao, custo_reaquisicao = tentativa

                    if path_reaquisicao is not None:
                        vx = vx_reaquisicao
                        vy = vy_reaquisicao
                    else:
                        vx = candidato.x - estado.x
                        vy = candidato.y - estado.y
                    accel = math.hypot(vx - estado.vx, vy - estado.vy)
                    deslocamento = math.hypot(vx, vy)
                    custo = (
                        estado.cost
                        + (dist / max(gate_candidato, 1.0)) * 0.72
                        + (accel / max(gate * 1.75, 1.0)) * 0.34
                        + _custo_deteccao_global(candidato)
                        + custo_reaquisicao
                    )
                    if path_reaquisicao is not None:
                        custo -= 0.18
                    if deslocamento < max(2.8, min_dim * 0.0028) and candidato.source not in {"manual_anchor", "calibrated_fill"}:
                        custo += 0.48
                    if candidato.motion_score < 0.030 and candidato.yellow_ratio < 0.11 and dist > gate * 0.35:
                        custo += 0.42
                    if candidato.source in {"tracknet", "ball_yolo"} and not evidencia_local_forte and dist > gate * 0.30:
                        custo += 0.46
                    if em_zona_jogador:
                        custo += 0.44
                        if candidato.source == "beam_candidate":
                            custo += 0.38
                    if candidato.source not in {"manual_anchor", "calibrated_fill", "tracknet", "ball_yolo"} and candidato.motion_score < 0.026 and candidato.yellow_ratio < 0.12:
                        custo += 1.20
                    if estado.misses >= 3 and dist > gate * 0.52 and candidato.confidence < 0.72:
                        custo += 0.36

                    proximos.append(
                        BallBeamState(
                            x=candidato.x,
                            y=candidato.y,
                            vx=vx * 0.78 + estado.vx * 0.22,
                            vy=vy * 0.78 + estado.vy * 0.22,
                            cost=custo,
                            misses=0,
                            detected=estado.detected + 1,
                            path=path_reaquisicao
                            if path_reaquisicao is not None
                            else [*estado.path, _ponto_trajetoria_global_dict(candidato, int(frame_idx), tempo_s)],
                        )
                    )

                if estado.misses < max_misses and estado.detected >= 1:
                    deteccoes_confiaveis_estado = _estado_bola_global_contar_confiaveis(estado)
                    if deteccoes_confiaveis_estado <= 0 and estado.detected < 2:
                        continue
                    pred = BallDetection(
                        pred_x,
                        pred_y,
                        max(2.2, min(9.0, min_dim * 0.0045)),
                        max(0.16, 0.48 - estado.misses * 0.014),
                        "trajectory_prediction",
                        0.08,
                        0.08,
                    )
                    predicao_permitida = (
                        estado.misses < min(max_misses, 4)
                        or (tem_calibracao_quadra and deteccoes_confiaveis_estado >= 1 and estado.misses < max_misses)
                    )
                    if (
                        predicao_permitida
                        and not _candidato_bola_em_borda_frame(pred, frame.shape, margem_px=max(18.0, min_dim * 0.022))
                        and _candidato_bola_no_corredor_quadra_central(
                            pred,
                            calibracao,
                            frame.shape,
                            margem_px=max(24.0, min_dim * 0.035),
                            margem_ar_px=max(64.0, min_dim * 0.095),
                        )
                        and _candidato_bola_em_escopo_de_tracking(pred, calibracao, frame.shape, [(int(estado.x), int(estado.y))], None)
                    ):
                        proximos.append(
                            BallBeamState(
                                x=pred.x,
                                y=pred.y,
                                vx=estado.vx * 0.94,
                                vy=estado.vy * 0.94,
                                cost=estado.cost + 0.34 + min(estado.misses, 24) * 0.026,
                                misses=estado.misses + 1,
                                detected=estado.detected,
                                path=[*estado.path, _ponto_trajetoria_global_dict(pred, int(frame_idx), tempo_s)],
                            )
                        )

            if proximos:
                estados = _selecionar_estados_bola_global(proximos, beam_width)
                candidato_melhor = estados[0]
                candidato_cobertura = min(estados, key=_chave_estado_bola_global_final)
                if melhor_estado is None or _chave_estado_bola_global_final(candidato_cobertura) < _chave_estado_bola_global_final(melhor_estado):
                    melhor_estado = candidato_cobertura

            frame_pre_anterior = frame_anterior
            frame_anterior = frame
    finally:
        cap.release()

    _notify(progress_callback, progress_end, f"Trajetoria global analisada ({len(indices)} frames)")

    candidatos_finais = [
        estado
        for estado in estados
        if estado.detected >= min_detected
        and _estado_bola_global_tem_cobertura_real(estado, min_real_rate, min_reliable, tem_calibracao_quadra)
    ]
    if (
        not candidatos_finais
        and melhor_estado is not None
        and melhor_estado.detected >= min_detected
        and _estado_bola_global_tem_cobertura_real(melhor_estado, min_real_rate, min_reliable, tem_calibracao_quadra)
    ):
        candidatos_finais = [melhor_estado]
    if not candidatos_finais:
        return _trajetoria_global_por_ancoras_confiaveis(
            ancoras=ancoras_confiaveis,
            indices=indices,
            fps_ref=fps_ref,
            frame_shape=(h, w, 3) if "h" in locals() and "w" in locals() else None,
            calibracao=calibracao,
        )

    melhor = min(candidatos_finais, key=_chave_estado_bola_global_final)
    pontos: dict[int, BallDetection] = {}
    for item in melhor.path:
        try:
            frame_idx = int(item["frame_index"])
            source = str(item.get("detector_source") or "global")
            x = float(item["x_px"])
            y = float(item["y_px"])
            radius = float(item.get("radius_px", 4.0))
            confidence = float(item.get("confidence", 0.35))
        except (TypeError, ValueError, KeyError):
            continue
        if source == "trajectory_prediction":
            final_source = "trajectory_prediction"
        elif source in {"manual_anchor", "calibrated_fill"}:
            final_source = source
        else:
            final_source = f"global_{source}"
        motion_score = float(item.get("motion_score", 0.0) or 0.0)
        yellow_ratio = float(item.get("yellow_ratio", 0.0) or 0.0)
        pontos[frame_idx] = BallDetection(x, y, radius, confidence, final_source, motion_score, yellow_ratio)

    pontos = _mesclar_ancoras_confiaveis_na_trajetoria(pontos, ancoras_confiaveis)
    pontos = _mesclar_resgates_contato_na_trajetoria(
        pontos,
        resgates_contato,
        fps_ref,
        (h, w, 3) if "h" in locals() and "w" in locals() else None,
        calibracao,
    )
    resgates_contato_validos = [
        (frame_idx, tempo_s, pontos[frame_idx])
        for frame_idx, tempo_s, _bola in resgates_contato
        if frame_idx in pontos and pontos[frame_idx].source == "beam_contact"
    ]
    frame_shape_global = (h, w, 3) if "h" in locals() and "w" in locals() else None
    pontos = _podar_predicoes_global_sem_ancoras(pontos, fps_ref, frame_shape_global)
    pontos_ancoras = _trajetoria_global_por_ancoras_confiaveis(
        ancoras=sorted([*ancoras_confiaveis, *resgates_contato_validos], key=lambda item: item[0]),
        indices=indices,
        fps_ref=fps_ref,
        frame_shape=frame_shape_global,
        calibracao=calibracao,
    )
    pontos_ancoras = _podar_predicoes_global_sem_ancoras(pontos_ancoras, fps_ref, frame_shape_global)
    pontos_mesclados = _mesclar_trajetorias_global_bola(pontos, pontos_ancoras, fps_ref, frame_shape_global)
    pontos_mesclados = _preencher_lacunas_globais_estendidas_seguras(
        pontos_mesclados,
        indices,
        fps_ref,
        frame_shape_global,
        calibracao,
    )
    melhor_base = max((pontos, pontos_ancoras), key=_pontuacao_trajetoria_global_segmentada)
    if _trajetoria_mesclada_preserva_cobertura_real(pontos_mesclados, melhor_base):
        return pontos_mesclados
    return melhor_base


def _estado_bola_global_tem_cobertura_real(
    estado: BallBeamState,
    min_real_rate: float,
    min_reliable: int,
    tem_calibracao_quadra: bool,
) -> bool:
    tamanho = max(len(estado.path), 1)
    reais = 0
    confiaveis = 0
    for item in estado.path:
        source = str(item.get("detector_source") or "")
        if source == "trajectory_prediction":
            continue
        reais += 1
        if _fonte_bola_global_confiavel(source):
            confiaveis += 1

    if confiaveis >= min_reliable:
        return True
    taxa_real = reais / tamanho
    if reais < 3 or taxa_real < min_real_rate:
        return False
    return False


def _mesclar_ancoras_confiaveis_na_trajetoria(
    pontos: dict[int, BallDetection],
    ancoras: list[tuple[int, float, BallDetection]],
) -> dict[int, BallDetection]:
    if not ancoras:
        return pontos

    resultado = dict(pontos)
    melhores: dict[int, BallDetection] = {}
    for frame_idx, _tempo_s, bola in ancoras:
        atual = melhores.get(int(frame_idx))
        if atual is None or _score_ancora_confiavel(bola) > _score_ancora_confiavel(atual):
            melhores[int(frame_idx)] = bola

    for frame_idx, ancora in melhores.items():
        existente = resultado.get(frame_idx)
        if existente is None or existente.source == "trajectory_prediction":
            resultado[frame_idx] = ancora
            continue
        fonte_existente = _fonte_bola_normalizada(existente.source)
        if not _fonte_bola_global_confiavel(fonte_existente):
            resultado[frame_idx] = ancora
            continue
        if _score_ancora_confiavel(ancora) > _score_ancora_confiavel(existente) + 0.08:
            resultado[frame_idx] = ancora
    return resultado


def _podar_predicoes_global_sem_ancoras(
    pontos: dict[int, BallDetection],
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None = None,
) -> dict[int, BallDetection]:
    if not pontos:
        return pontos

    max_gap_s = _float_env("TENNIS_XRAY_GLOBAL_BALL_ANCHOR_INTERP_MAX_GAP_S", 0.55)
    max_gap_s_forte = max(max_gap_s, _float_env("TENNIS_XRAY_GLOBAL_BALL_STRONG_ANCHOR_INTERP_MAX_GAP_S", 0.75))
    min_pred_conf = _float_env("TENNIS_XRAY_GLOBAL_BALL_MIN_PRED_CONF", 0.40)
    max_gap_frames = max(2, int(round(max(fps_ref, 1.0) * max_gap_s)))
    max_gap_frames_forte = max(max_gap_frames, int(round(max(fps_ref, 1.0) * max_gap_s_forte)))
    frames_reais = sorted(
        frame_idx
        for frame_idx, bola in pontos.items()
        if bola.source != "trajectory_prediction"
    )
    if len(frames_reais) < 2:
        return {frame_idx: bola for frame_idx, bola in pontos.items() if bola.source != "trajectory_prediction"}

    resultado: dict[int, BallDetection] = {}
    reais_set = set(frames_reais)
    for frame_idx, bola in sorted(pontos.items()):
        if bola.source != "trajectory_prediction":
            resultado[frame_idx] = bola
            continue
        if bola.confidence < min_pred_conf:
            continue

        anterior = None
        posterior = None
        for real_idx in frames_reais:
            if real_idx < frame_idx:
                anterior = real_idx
                continue
            if real_idx > frame_idx:
                posterior = real_idx
                break
        if anterior is None or posterior is None:
            continue
        limite_gap = max_gap_frames
        if _ancora_segmento_global_forte(pontos[anterior]) and _ancora_segmento_global_forte(pontos[posterior]):
            limite_gap = max_gap_frames_forte
        if posterior - anterior > limite_gap:
            if not _segmento_interpolacao_global_estendido_seguro(
                pontos[anterior],
                pontos[posterior],
                posterior - anterior,
                fps_ref,
                frame_shape,
            ):
                continue
        if anterior not in reais_set or posterior not in reais_set:
            continue
        resultado[frame_idx] = bola
    return resultado


def _mesclar_trajetorias_global_bola(
    primaria: dict[int, BallDetection],
    secundaria: dict[int, BallDetection],
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None = None,
) -> dict[int, BallDetection]:
    """Combina a trilha do beam com a trilha por ancoras sem trocar segmentos bons."""

    if not primaria:
        return dict(secundaria)
    if not secundaria:
        return dict(primaria)

    resultado = dict(primaria)
    for frame_idx, candidato in secundaria.items():
        existente = resultado.get(frame_idx)
        if existente is None or _preferir_ponto_trajetoria_global(candidato, existente):
            resultado[int(frame_idx)] = candidato

    return _podar_predicoes_global_sem_ancoras(resultado, fps_ref, frame_shape)


def _preferir_ponto_trajetoria_global(novo: BallDetection, atual: BallDetection) -> bool:
    if atual.source == "trajectory_prediction":
        if novo.source != "trajectory_prediction":
            return True
        return novo.confidence > atual.confidence + 0.03
    if novo.source == "trajectory_prediction":
        return False

    novo_forte = _candidato_modelo_bola_forte(novo)
    atual_forte = _candidato_modelo_bola_forte(atual)
    if novo_forte != atual_forte:
        return novo_forte

    novo_confiavel = _fonte_bola_global_confiavel(novo.source)
    atual_confiavel = _fonte_bola_global_confiavel(atual.source)
    if novo_confiavel != atual_confiavel:
        return novo_confiavel

    return _score_ancora_confiavel(novo) > _score_ancora_confiavel(atual) + 0.05


def _ancora_segmento_global_forte(bola: BallDetection) -> bool:
    source = _fonte_bola_normalizada(bola.source)
    if source in {"manual_anchor", "calibrated_fill", "manual_seed"}:
        return True
    return _candidato_modelo_bola_forte(bola)


def _segmento_interpolacao_global_estendido_seguro(
    bola_a: BallDetection,
    bola_b: BallDetection,
    gap_frames: int,
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None,
) -> bool:
    if frame_shape is None or gap_frames <= 0:
        return False
    if not (_ancora_segmento_global_forte(bola_a) and _ancora_segmento_global_forte(bola_b)):
        return False

    gap_s = gap_frames / max(fps_ref, 1.0)
    max_gap_s = _float_env("TENNIS_XRAY_GLOBAL_BALL_STEEP_INTERP_MAX_GAP_S", 1.55)
    if gap_s > max_gap_s:
        return False

    min_dim = float(min(frame_shape[:2]))
    dx = float(bola_b.x - bola_a.x)
    dy = float(bola_b.y - bola_a.y)
    dist = math.hypot(dx, dy)
    if dist > max(260.0, min_dim * 0.34):
        return False
    if (
        gap_s <= _float_env("TENNIS_XRAY_GLOBAL_BALL_SHORT_ARC_INTERP_MAX_GAP_S", 0.95)
        and dist <= max(92.0, min_dim * 0.105)
        and abs(dy) <= max(48.0, min_dim * 0.050)
    ):
        return True
    if abs(dy) < max(58.0, min_dim * 0.052):
        return False
    if abs(dx) > max(82.0, min_dim * 0.115) and abs(dx) / max(abs(dy), 1.0) > 0.42:
        return False
    return True


def _preencher_lacunas_globais_estendidas_seguras(
    pontos: dict[int, BallDetection],
    indices: list[int],
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None,
    calibracao: dict | None,
) -> dict[int, BallDetection]:
    if not pontos or frame_shape is None:
        return pontos

    reais = sorted(
        (int(frame_idx), bola)
        for frame_idx, bola in pontos.items()
        if bola.source != "trajectory_prediction"
    )
    if len(reais) < 2:
        return pontos

    resultado = dict(pontos)
    indices_ordenados = sorted(set(int(item) for item in indices))
    for (frame_a, bola_a), (frame_b, bola_b) in zip(reais, reais[1:]):
        gap_frames = frame_b - frame_a
        if not _segmento_interpolacao_global_estendido_seguro(bola_a, bola_b, gap_frames, fps_ref, frame_shape):
            continue
        for frame_idx in indices_ordenados:
            if frame_idx <= frame_a or frame_idx >= frame_b:
                continue
            existente = resultado.get(frame_idx)
            if existente is not None and existente.source != "trajectory_prediction":
                continue
            t = (frame_idx - frame_a) / max(gap_frames, 1)
            t = max(0.0, min(1.0, float(t)))
            t_y = _t_interpolacao_y_segmento_estendido(bola_a, bola_b, t, frame_shape)
            candidato = BallDetection(
                x=bola_a.x + (bola_b.x - bola_a.x) * t,
                y=bola_a.y + (bola_b.y - bola_a.y) * t_y,
                radius=max(2.2, min(9.0, (bola_a.radius + bola_b.radius) * 0.5)),
                confidence=max(0.32, min(bola_a.confidence, bola_b.confidence) * (0.68 - abs(t - 0.5) * 0.16)),
                source="trajectory_prediction",
                motion_score=0.08,
                yellow_ratio=0.08,
            )
            if _bola_renderizavel_no_escopo(candidato, calibracao, frame_shape):
                resultado[int(frame_idx)] = candidato

    return _podar_predicoes_global_sem_ancoras(resultado, fps_ref, frame_shape)


def _t_interpolacao_y_segmento_estendido(
    bola_a: BallDetection,
    bola_b: BallDetection,
    t: float,
    frame_shape: tuple[int, int, int],
) -> float:
    min_dim = float(min(frame_shape[:2]))
    dx = float(bola_b.x - bola_a.x)
    dy = float(bola_b.y - bola_a.y)
    if abs(dy) <= max(abs(dx) * 1.8, min_dim * 0.080):
        return t

    expoente = max(1.0, _float_env("TENNIS_XRAY_GLOBAL_BALL_STEEP_INTERP_Y_EXP", 1.45))
    if dy > 0:
        return t**expoente
    return 1.0 - ((1.0 - t) ** expoente)


def _trajetoria_mesclada_preserva_cobertura_real(
    mesclada: dict[int, BallDetection],
    base: dict[int, BallDetection],
) -> bool:
    if len(mesclada) <= len(base):
        return False

    reais_base = [
        frame_idx
        for frame_idx, bola in base.items()
        if bola.source != "trajectory_prediction" and _fonte_bola_global_confiavel(bola.source)
    ]
    reais_mesclada = [
        frame_idx
        for frame_idx, bola in mesclada.items()
        if bola.source != "trajectory_prediction" and _fonte_bola_global_confiavel(bola.source)
    ]
    if len(reais_mesclada) < len(reais_base):
        return False
    if not reais_base:
        return bool(reais_mesclada)
    return min(reais_mesclada) <= min(reais_base) and max(reais_mesclada) >= max(reais_base)


def _mesclar_resgates_contato_na_trajetoria(
    pontos: dict[int, BallDetection],
    resgates: list[tuple[int, float, BallDetection]],
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None,
    calibracao: dict | None,
) -> dict[int, BallDetection]:
    if not _bool_env("TENNIS_XRAY_GLOBAL_BALL_CONTACT_RESCUE", False):
        return pontos
    if not pontos or not resgates or frame_shape is None:
        return pontos

    resultado = dict(pontos)
    frames_fortes = sorted(
        frame_idx
        for frame_idx, bola in resultado.items()
        if bola.source != "trajectory_prediction" and _candidato_modelo_bola_forte(bola)
    )
    if len(frames_fortes) < 2:
        return resultado

    max_gap = int(round(max(fps_ref, 1.0) * _float_env("TENNIS_XRAY_BALL_CONTACT_RESCUE_BRACKET_GAP_S", 1.55)))
    melhores: dict[int, BallDetection] = {}
    for frame_idx, _tempo_s, candidato in resgates:
        if not _candidato_em_metade_inferior_quadra(candidato, calibracao, frame_shape):
            continue
        anterior = max((idx for idx in frames_fortes if idx < frame_idx), default=None)
        posterior = min((idx for idx in frames_fortes if idx > frame_idx), default=None)
        if anterior is None or posterior is None:
            continue
        if frame_idx - anterior > max_gap or posterior - frame_idx > max_gap:
            continue
        if posterior - anterior > max_gap * 2:
            continue

        bola_anterior = resultado[anterior]
        bola_posterior = resultado[posterior]
        dist_anterior = math.hypot(candidato.x - bola_anterior.x, candidato.y - bola_anterior.y)
        dist_posterior = math.hypot(candidato.x - bola_posterior.x, candidato.y - bola_posterior.y)
        min_dim = float(min(frame_shape[:2]))
        alcance = max(170.0, min_dim * 0.36)
        if min(dist_anterior, dist_posterior) > alcance:
            continue

        atual = melhores.get(frame_idx)
        if atual is None or _score_ancora_confiavel(candidato) > _score_ancora_confiavel(atual):
            melhores[frame_idx] = candidato

    for frame_idx, candidato in melhores.items():
        existente = resultado.get(frame_idx)
        if existente is None or existente.source == "trajectory_prediction":
            resultado[frame_idx] = candidato

    return resultado


def _score_ancora_confiavel(bola: BallDetection) -> float:
    source = _fonte_bola_normalizada(bola.source)
    bonus = 0.16 if source == "tracknet" else 0.12 if source == "ball_yolo" else 0.04 if source == "beam_contact" else 0.0
    return (
        float(bola.confidence)
        + min(float(bola.motion_score), 0.45) * 0.42
        + min(float(bola.yellow_ratio), 0.85) * 0.18
        + bonus
    )


def _pontuacao_trajetoria_global_segmentada(pontos: dict[int, BallDetection]) -> float:
    if not pontos:
        return -1.0

    reais = [
        frame_idx
        for frame_idx, bola in pontos.items()
        if bola.source != "trajectory_prediction"
        and _fonte_bola_global_confiavel(bola.source)
    ]
    if not reais:
        return -1.0

    frames = sorted(pontos)
    span_total = max(frames) - min(frames) if len(frames) >= 2 else 0
    span_real = max(reais) - min(reais) if len(reais) >= 2 else 0
    predicoes = sum(1 for bola in pontos.values() if bola.source == "trajectory_prediction")
    primeiro_real = min(reais)
    return len(reais) * 210.0 + span_real * 1.25 + span_total * 0.25 - predicoes * 0.018 - primeiro_real * 0.18


def _estado_bola_global_contar_confiaveis(estado: BallBeamState) -> int:
    total = 0
    for item in estado.path:
        if _fonte_bola_global_confiavel(str(item.get("detector_source") or "")):
            total += 1
    return total


def _melhor_ancora_bola_global_confiavel(candidatos: list[BallDetection]) -> BallDetection | None:
    manuais = [
        candidato
        for candidato in candidatos
        if candidato.source in {"manual_anchor", "calibrated_fill"}
    ]
    if manuais:
        return max(manuais, key=lambda item: item.confidence)

    confiaveis = [
        candidato
        for candidato in candidatos
        if _ancora_bola_global_forte(candidato)
    ]
    if len(confiaveis) == 1:
        return confiaveis[0] if _ancora_bola_global_forte_isolada(confiaveis[0]) else None
    if len(confiaveis) < 2:
        return None

    consenso: list[BallDetection] = []
    for candidato in confiaveis:
        if any(
            outro is not candidato
            and outro.source != candidato.source
            and math.hypot(outro.x - candidato.x, outro.y - candidato.y) <= max(26.0, candidato.radius + outro.radius + 16.0)
            for outro in confiaveis
        ):
            consenso.append(candidato)
    if not consenso:
        candidato_unico = max(
            confiaveis,
            key=lambda item: (
                _fonte_bola_normalizada(item.source) in {"tracknet", "ball_yolo"},
                item.confidence + min(item.motion_score, 0.35) * 0.45 + min(item.yellow_ratio, 0.85) * 0.18,
            ),
        )
        if _ancora_bola_global_forte_isolada(candidato_unico):
            return candidato_unico
        return None

    return max(
        consenso,
        key=lambda item: (
            _fonte_bola_normalizada(item.source) in {"tracknet", "ball_yolo"},
            item.confidence + min(item.motion_score, 0.35) * 0.45 + min(item.yellow_ratio, 0.85) * 0.18,
        ),
    )


def _ancora_bola_global_forte(candidato: BallDetection) -> bool:
    source = _fonte_bola_normalizada(candidato.source)
    if source in {"manual_anchor", "calibrated_fill"}:
        return True
    if source == "tracknet":
        return (
            candidato.confidence >= 0.72
            and candidato.motion_score >= 0.050
            and candidato.yellow_ratio >= 0.050
        )
    if source == "ball_yolo":
        return (
            candidato.confidence >= 0.60
            and candidato.motion_score >= 0.080
            and candidato.yellow_ratio >= 0.200
        )
    return False


def _ancora_bola_global_forte_isolada(candidato: BallDetection) -> bool:
    source = _fonte_bola_normalizada(candidato.source)
    if source == "tracknet":
        return (
            candidato.confidence >= 0.76
            and candidato.motion_score >= 0.050
            and candidato.yellow_ratio >= 0.045
        )
    if source == "ball_yolo":
        return (
            candidato.confidence >= 0.62
            and candidato.motion_score >= 0.075
            and candidato.yellow_ratio >= 0.120
        )
    return source in {"manual_anchor", "calibrated_fill"}


def _trajetoria_global_por_ancoras_confiaveis(
    ancoras: list[tuple[int, float, BallDetection]],
    indices: list[int],
    fps_ref: float,
    frame_shape: tuple[int, int, int] | None,
    calibracao: dict | None,
) -> dict[int, BallDetection]:
    if len(ancoras) < 2 or frame_shape is None:
        return {}

    min_dim = float(min(frame_shape[:2]))
    max_gap_s = _float_env("TENNIS_XRAY_GLOBAL_BALL_ANCHOR_INTERP_MAX_GAP_S", 0.55)
    max_gap_s_forte = max(max_gap_s, _float_env("TENNIS_XRAY_GLOBAL_BALL_STRONG_ANCHOR_INTERP_MAX_GAP_S", 0.75))
    resultado: dict[int, BallDetection] = {}
    indices_ordenados = sorted(set(indices))

    for (frame_a, tempo_a, bola_a), (frame_b, tempo_b, bola_b) in zip(ancoras, ancoras[1:]):
        if frame_b <= frame_a:
            continue
        gap_s = max(0.0, (frame_b - frame_a) / max(fps_ref, 1.0))
        limite_gap_s = max_gap_s_forte if _ancora_segmento_global_forte(bola_a) and _ancora_segmento_global_forte(bola_b) else max_gap_s
        if gap_s > limite_gap_s and not _segmento_interpolacao_global_estendido_seguro(
            bola_a,
            bola_b,
            frame_b - frame_a,
            fps_ref,
            frame_shape,
        ):
            continue
        distancia = math.hypot(bola_b.x - bola_a.x, bola_b.y - bola_a.y)
        alcance = max(115.0, min_dim * (0.12 + 0.65 * min(gap_s, 1.55)))
        if distancia > alcance:
            continue
        for frame_idx in indices_ordenados:
            if frame_idx < frame_a or frame_idx > frame_b:
                continue
            t = (frame_idx - frame_a) / max(frame_b - frame_a, 1)
            t = max(0.0, min(1.0, float(t)))
            x = bola_a.x + (bola_b.x - bola_a.x) * t
            y = bola_a.y + (bola_b.y - bola_a.y) * t
            if frame_idx == frame_a:
                candidato = bola_a
            elif frame_idx == frame_b:
                candidato = bola_b
            else:
                candidato = BallDetection(
                    x=x,
                    y=y,
                    radius=max(2.2, min(9.0, (bola_a.radius + bola_b.radius) * 0.5)),
                    confidence=max(0.24, min(bola_a.confidence, bola_b.confidence) * (0.72 - abs(t - 0.5) * 0.18)),
                    source="trajectory_prediction",
                    motion_score=0.08,
                    yellow_ratio=0.08,
                )
            if _bola_renderizavel_no_escopo(candidato, calibracao, frame_shape):
                resultado[int(frame_idx)] = candidato

    return resultado


def _ponto_trajetoria_global_dict(bola: BallDetection, frame_idx: int, tempo_s: float) -> dict:
    return {
        "frame_index": int(frame_idx),
        "time_s": round(float(tempo_s), 4),
        "x_px": float(bola.x),
        "y_px": float(bola.y),
        "radius_px": float(bola.radius),
        "confidence": round(float(bola.confidence), 4),
        "detector_source": bola.source,
        "motion_score": round(float(bola.motion_score), 4),
        "yellow_ratio": round(float(bola.yellow_ratio), 4),
    }


def _deduplicar_candidatos_bola_global(candidatos: list[BallDetection]) -> list[BallDetection]:
    ordenados = sorted(candidatos, key=lambda item: item.confidence, reverse=True)
    resultado: list[BallDetection] = []
    for candidato in ordenados:
        if any(math.hypot(candidato.x - outro.x, candidato.y - outro.y) < max(5.0, candidato.radius + outro.radius) for outro in resultado):
            continue
        resultado.append(candidato)
    return resultado


def _candidato_inicio_global_valido(candidato: BallDetection) -> bool:
    if candidato.source in {"manual_anchor", "calibrated_fill"}:
        return True
    if candidato.source == "beam_candidate":
        return (
            candidato.confidence >= 0.62
            and candidato.motion_score >= 0.080
            and candidato.yellow_ratio >= 0.120
        )
    if candidato.motion_score >= 0.040 and candidato.confidence >= 0.38:
        return True
    if candidato.motion_score >= 0.024 and candidato.yellow_ratio >= 0.16 and candidato.confidence >= 0.56:
        return True
    if _fonte_bola_normalizada(candidato.source) in {"tracknet", "ball_yolo"} and candidato.confidence >= 0.84 and candidato.motion_score >= 0.020:
        return True
    return False


def _tentar_reaquisicao_global_bola(
    estado: BallBeamState,
    candidato: BallDetection,
    frame_idx: int,
    tempo_s: float,
    fps_ref: float,
    min_dim: float,
) -> tuple[list[dict], float, float, float] | None:
    """Reconecta a trilha apos uma lacuna usando interpolacao fisica.

    O rastro de uma troca nao e uma reta de velocidade constante: batidas e
    quiques mudam a direcao. Quando a bolinha some por alguns frames e reaparece
    com boa evidencia visual, esta rotina substitui as predicoes antigas por uma
    ponte interpolada entre a ultima deteccao real e a nova deteccao.
    """

    reaquisicao_forte = _candidato_global_reaquisicao_forte(candidato)
    reaquisicao_moderada = (
        estado.misses >= _int_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_MODERATE_MIN_MISSES", 5)
        and _candidato_global_reaquisicao_moderada(candidato)
    )
    if estado.misses < 3 or not (reaquisicao_forte or reaquisicao_moderada):
        return None

    indice_detectado = None
    ultimo_detectado = None
    for indice in range(len(estado.path) - 1, -1, -1):
        item = estado.path[indice]
        if str(item.get("detector_source")) != "trajectory_prediction":
            indice_detectado = indice
            ultimo_detectado = item
            break
    if indice_detectado is None or ultimo_detectado is None:
        return None

    try:
        frame_detectado = int(ultimo_detectado["frame_index"])
        x_detectado = float(ultimo_detectado["x_px"])
        y_detectado = float(ultimo_detectado["y_px"])
    except (KeyError, TypeError, ValueError):
        return None

    gap_frames = max(1, frame_idx - frame_detectado)
    tempo_gap = gap_frames / max(fps_ref, 1.0)
    dist_detectado = math.hypot(candidato.x - x_detectado, candidato.y - y_detectado)
    alcance = max(150.0, min_dim * (0.135 + 0.305 * min(tempo_gap, 2.0)))
    if dist_detectado > alcance:
        return None

    caminho = list(estado.path[: indice_detectado + 1])
    for item in estado.path[indice_detectado + 1 :]:
        try:
            frame_inter = int(item["frame_index"])
            tempo_inter = float(item.get("time_s", frame_inter / max(fps_ref, 1.0)))
        except (KeyError, TypeError, ValueError):
            continue
        t = (frame_inter - frame_detectado) / max(frame_idx - frame_detectado, 1)
        t = max(0.0, min(1.0, float(t)))
        x_inter = x_detectado + (candidato.x - x_detectado) * t
        y_inter = y_detectado + (candidato.y - y_detectado) * t
        caminho.append(
            {
                "frame_index": frame_inter,
                "time_s": round(tempo_inter, 4),
                "x_px": float(x_inter),
                "y_px": float(y_inter),
                "radius_px": float(item.get("radius_px", candidato.radius)),
                "confidence": max(0.18, min(0.42, float(item.get("confidence", 0.24)))),
                "detector_source": "trajectory_prediction",
                "motion_score": 0.08,
                "yellow_ratio": 0.08,
            }
        )

    ponto_atual = _ponto_trajetoria_global_dict(candidato, frame_idx, tempo_s)
    caminho.append(ponto_atual)
    anterior = caminho[-2] if len(caminho) >= 2 else ultimo_detectado
    try:
        vx = float(ponto_atual["x_px"]) - float(anterior["x_px"])
        vy = float(ponto_atual["y_px"]) - float(anterior["y_px"])
    except (KeyError, TypeError, ValueError):
        vx = candidato.x - estado.x
        vy = candidato.y - estado.y

    custo_extra = 0.42 + min(dist_detectado / max(alcance, 1.0), 1.35) * 0.42 + min(estado.misses, 24) * 0.010
    return caminho, vx, vy, custo_extra


def _candidato_global_reaquisicao_forte(candidato: BallDetection) -> bool:
    source = _fonte_bola_normalizada(candidato.source)
    if source in {"manual_anchor", "calibrated_fill", "manual_seed"}:
        return True
    if source in {"tracknet", "ball_yolo"}:
        return (
            candidato.confidence >= 0.62
            and (
                candidato.motion_score >= 0.045
                or candidato.yellow_ratio >= 0.115
                or (candidato.confidence >= 0.90 and candidato.motion_score >= 0.020)
            )
        )
    return candidato.confidence >= 0.68 and candidato.motion_score >= 0.140 and candidato.yellow_ratio >= 0.120


def _candidato_global_reaquisicao_moderada(candidato: BallDetection) -> bool:
    source = _fonte_bola_normalizada(candidato.source)
    if source == "tracknet":
        return (
            candidato.confidence >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_TRACKNET_MIN_CONF", 0.46)
            and candidato.motion_score >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_TRACKNET_MIN_MOTION", 0.075)
            and candidato.yellow_ratio >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_TRACKNET_MIN_YELLOW", 0.18)
        )
    if source == "ball_yolo":
        return (
            candidato.confidence >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_YOLO_MIN_CONF", 0.52)
            and candidato.motion_score >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_YOLO_MIN_MOTION", 0.075)
            and candidato.yellow_ratio >= _float_env("TENNIS_XRAY_GLOBAL_BALL_REACQUIRE_YOLO_MIN_YELLOW", 0.38)
        )
    return False


def _candidato_global_tem_evidencia_minima(candidato: BallDetection) -> bool:
    """Evita que o caminho global seja alimentado por artefatos estaticos.

    YOLO/TrackNet continuam entrando, mas deixam de ser aceitos apenas por
    confianca numerica quando a regiao nao tem movimento nem assinatura visual
    de bolinha. Isso reduz saltos para fita da rede, logos e highlights.
    """

    source = _fonte_bola_normalizada(candidato.source)
    if source in {"manual_anchor", "calibrated_fill"}:
        return True
    if source == "tracknet":
        return (
            candidato.confidence >= 0.42
            and (
                candidato.motion_score >= 0.016
                or candidato.yellow_ratio >= 0.040
                or candidato.confidence >= 0.90
            )
        )
    if source == "ball_yolo":
        return (
            candidato.confidence >= 0.40
            and (
                candidato.motion_score >= 0.020
                or candidato.yellow_ratio >= 0.070
                or (candidato.confidence >= 0.93 and candidato.motion_score >= 0.010)
            )
        )
    if source == "beam_contact":
        return (
            candidato.confidence >= 0.50
            and (
                candidato.motion_score >= 0.42
                or (candidato.motion_score >= 0.24 and candidato.yellow_ratio >= 0.050)
            )
        )
    if source == "beam_candidate":
        return (
            candidato.confidence >= 0.52
            and candidato.motion_score >= 0.065
            and candidato.yellow_ratio >= 0.090
        )
    return candidato.motion_score >= 0.075 and candidato.yellow_ratio >= 0.110


def _candidato_beam_movimento_compacto_forte(candidato: BallDetection) -> bool:
    if _fonte_bola_normalizada(candidato.source) != "beam_candidate":
        return False
    if candidato.confidence >= 0.60 and candidato.motion_score >= 0.48:
        return True
    return candidato.confidence >= 0.56 and candidato.motion_score >= 0.24 and candidato.yellow_ratio >= 0.150


def _candidato_beam_resgate_contato(
    candidato: BallDetection,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    calibracao: dict | None,
) -> bool:
    if not _candidato_beam_movimento_compacto_forte(candidato):
        return False
    if players and not _candidato_em_zona_jogador(candidato, players, frame_shape):
        return False
    if not _candidato_em_metade_inferior_quadra(candidato, calibracao, frame_shape):
        return False
    if _candidato_bola_em_borda_frame(candidato, frame_shape, margem_px=max(18.0, min(frame_shape[:2]) * 0.022)):
        return False
    return _candidato_bola_no_corredor_quadra_central(
        candidato,
        calibracao,
        frame_shape,
        margem_px=max(24.0, min(frame_shape[:2]) * 0.035),
        margem_ar_px=max(64.0, min(frame_shape[:2]) * 0.095),
    )


def _candidato_em_metade_inferior_quadra(
    candidato: BallDetection,
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
) -> bool:
    h, _w = frame_shape[:2]
    pontos = _pontos_calibracao_normalizados(calibracao)
    ids = ("sup_esquerda", "sup_direita", "inf_direita", "inf_esquerda")
    if not all(nome in pontos for nome in ids):
        return candidato.y >= h * 0.52

    topo_y = min(pontos["sup_esquerda"][1], pontos["sup_direita"][1]) * h
    base_y = max(pontos["inf_esquerda"][1], pontos["inf_direita"][1]) * h
    if base_y <= topo_y:
        return candidato.y >= h * 0.52
    limite = topo_y + (base_y - topo_y) * 0.46
    return candidato.y >= limite


def _custo_deteccao_global(candidato: BallDetection, source_start: bool = False) -> float:
    source = _fonte_bola_normalizada(candidato.source)
    custo = (1.0 - max(0.0, min(0.99, candidato.confidence))) * 0.82
    custo -= min(candidato.motion_score * 1.8, 0.24)
    custo -= min(candidato.yellow_ratio * 0.7, 0.14)
    if source == "tracknet":
        custo -= 0.16
    elif source == "ball_yolo":
        custo -= 0.12
        if candidato.motion_score < 0.030 and candidato.yellow_ratio < 0.10:
            custo += 0.18
    elif source == "beam_contact":
        custo -= 0.04
        if candidato.motion_score < 0.50 and candidato.yellow_ratio < 0.045:
            custo += 0.16
    elif source == "beam_candidate":
        custo += 0.46
    elif source == "manual_anchor":
        custo -= 0.55
    elif source == "trajectory_prediction":
        custo += 0.18
    if source_start and candidato.motion_score < 0.035 and source != "manual_anchor":
        custo += 0.38
    return max(-0.55, custo)


def _chave_estado_bola_global(estado: BallBeamState) -> float:
    tamanho = max(len(estado.path), 1)
    return (estado.cost / tamanho) - min(estado.detected, 80) * 0.025 + estado.misses * 0.020 - tamanho * 0.006


def _selecionar_estados_bola_global(estados: list[BallBeamState], beam_width: int) -> list[BallBeamState]:
    """Mantem hipoteses boas localmente e hipoteses com boa cobertura temporal."""

    largura = max(4, beam_width)
    selecionados: list[BallBeamState] = []
    vistos: set[tuple[int, int, int, int]] = set()

    def adicionar(estado: BallBeamState) -> None:
        if len(selecionados) >= largura:
            return
        try:
            frame_idx = int(estado.path[-1]["frame_index"])
        except (IndexError, KeyError, TypeError, ValueError):
            frame_idx = -1
        chave = (
            frame_idx,
            int(round(estado.x / 12.0)),
            int(round(estado.y / 12.0)),
            max(0, len(estado.path) // 12),
        )
        if chave in vistos:
            return
        vistos.add(chave)
        selecionados.append(estado)

    for estado in sorted(estados, key=_chave_estado_bola_global)[:largura]:
        adicionar(estado)
    for estado in sorted(estados, key=_chave_estado_bola_global_final)[: max(3, largura // 2)]:
        adicionar(estado)
    if not selecionados:
        return sorted(estados, key=_chave_estado_bola_global)[:largura]
    return selecionados


def _chave_estado_bola_global_final(estado: BallBeamState) -> float:
    tamanho = max(len(estado.path), 1)
    deteccoes = max(estado.detected, 0)
    predicoes = max(tamanho - deteccoes, 0)
    taxa_deteccao = deteccoes / tamanho
    return (
        (estado.cost / tamanho)
        - min(tamanho, 240) * 0.018
        - min(deteccoes, 80) * 0.020
        + estado.misses * 0.010
        + predicoes * 0.002
        + max(0.0, 0.14 - taxa_deteccao) * 0.42
    )


def _detectar_rastro_bola_com_seed_beam(
    cap,
    total_frames: int,
    fps_original: float,
    calibracao: dict | None,
    seed: dict,
    step_s: float,
    min_confidence: float,
    max_points: int,
    target_fps: float,
) -> dict:
    try:
        seed_time_s = max(0.0, float(seed.get("time_s", 0.0)))
        seed_x_norm = float(seed.get("x"))
        seed_y_norm = float(seed.get("y"))
    except (TypeError, ValueError):
        return {"marks": [], "quality": {"metodo": "beam_seed", "erro": "seed_invalida"}}

    if not math.isfinite(seed_x_norm) or not math.isfinite(seed_y_norm) or not 0 <= seed_x_norm <= 1 or not 0 <= seed_y_norm <= 1:
        return {"marks": [], "quality": {"metodo": "beam_seed", "erro": "seed_fora_do_frame"}}

    fps_ref = max(fps_original, 1.0)
    seed_frame_idx = max(0, min(total_frames - 1, int(round(seed_time_s * fps_ref))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(seed_frame_idx))
    ok, seed_frame = cap.read()
    if not ok:
        return {"marks": [], "quality": {"metodo": "beam_seed", "erro": "frame_seed_indisponivel"}}

    h_seed, w_seed = seed_frame.shape[:2]
    seed_px = (seed_x_norm * w_seed, seed_y_norm * h_seed)
    seed_ball = BallDetection(seed_px[0], seed_px[1], max(3.0, min(w_seed, h_seed) * 0.005), 0.99, "manual_seed")
    template_bola = _extrair_template_bola(seed_frame, seed_ball)
    stride_frames = max(1, int(round(step_s * fps_ref)))
    max_frames = _int_env("TENNIS_XRAY_AUTO_BALL_SEEDED_MAX_FRAMES", min(900, max(max_points * 3, 180)))
    indices = list(range(seed_frame_idx + stride_frames, total_frames, stride_frames))[:max_frames]
    if not indices:
        return {"marks": [], "quality": {"metodo": "beam_seed", "erro": "sem_frames_apos_seed"}}

    modelo_yolo = _load_yolo_model()
    frame_anterior: np.ndarray | None = seed_frame
    frame_pre_anterior: np.ndarray | None = seed_frame
    ultimo_players: list[DetectionBox] = []
    min_dim_seed = float(min(w_seed, h_seed))
    beam_width = _int_env("TENNIS_XRAY_BALL_BEAM_WIDTH", 9)
    max_misses = _int_env("TENNIS_XRAY_BALL_BEAM_MAX_MISSES", 10)
    estados: list[BallBeamState] = [
        BallBeamState(
            x=float(seed_px[0]),
            y=float(seed_px[1]),
            vx=0.0,
            vy=0.0,
            cost=0.0,
            misses=0,
            detected=1,
            path=[
                _marca_bola_auto_dict(
                    seed_ball,
                    seed_frame_idx,
                    seed_frame_idx / fps_ref,
                    w_seed,
                    h_seed,
                    source="manual_auto_seed",
                    label="Inicio manual do auto-rastro",
                )
            ],
        )
    ]
    frames_processados = 0
    candidatos_total = 0

    for frame_idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame = cap.read()
        if not ok:
            continue
        frames_processados += 1
        h, w = frame.shape[:2]
        min_dim = float(min(w, h))
        tempo_s = frame_idx / fps_ref

        players_detectados = _detectar_jogadores(frame, modelo_yolo)
        players_escopo = _filtrar_jogadores_escopo_quadra(players_detectados, calibracao, frame.shape)
        if _tem_anchors_jogadores(calibracao):
            players = _ordenar_jogadores_por_calibracao(players_escopo, calibracao, frame.shape, ultimo_players)
        else:
            players = _normalizar_dois_jogadores(players_escopo, ultimo_players, frame.shape)
        players_validos = [box for box in players if _box_desenhavel(box)]
        ultimo_players = _atualizar_ultimo_players_por_slot(players, ultimo_players, frame.shape)

        candidatos = _candidatos_bola_amplos(
            frame=frame,
            frame_anterior=frame_anterior,
            frame_pre_anterior=frame_pre_anterior,
            players=players_validos,
            calibracao=calibracao,
        )
        candidatos_total += len(candidatos)

        proximos: list[BallBeamState] = []
        for estado_beam in estados:
            pred_x = max(0.0, min(float(w - 1), estado_beam.x + estado_beam.vx))
            pred_y = max(0.0, min(float(h - 1), estado_beam.y + estado_beam.vy))
            velocidade = math.hypot(estado_beam.vx, estado_beam.vy)
            gate = max(44.0, min_dim * 0.055, velocidade * 2.15 + 22.0 + estado_beam.misses * 14.0)
            if estado_beam.detected <= 2:
                gate = max(gate, min_dim * 0.115)

            prior_bola = BallPrior(pred_x, pred_y, gate, max(0.34, 0.72 - estado_beam.misses * 0.05), step_s)
            candidato_template = _candidato_bola_template(
                frame=frame,
                template=template_bola,
                prior_bola=prior_bola,
                players=players_validos,
                ball_track=[(int(item["x"] * w), int(item["y"] * h)) for item in estado_beam.path[-8:]],
                calibracao=calibracao,
            )
            candidatos_estado = list(candidatos)
            if candidato_template is not None:
                candidatos_estado.append(candidato_template)

            for candidato in candidatos_estado:
                dist_pred = math.hypot(candidato.x - pred_x, candidato.y - pred_y)
                gate_candidato = gate * (1.45 if candidato.confidence >= 0.72 else 1.0)
                if dist_pred > gate_candidato:
                    continue
                vx = candidato.x - estado_beam.x
                vy = candidato.y - estado_beam.y
                accel = math.hypot(vx - estado_beam.vx, vy - estado_beam.vy)
                accel_norm = accel / max(gate * 1.6, 1.0)
                dist_norm = dist_pred / max(gate_candidato, 1.0)
                custo = estado_beam.cost + dist_norm * 0.82 + accel_norm * 0.36 + (1.0 - candidato.confidence) * 0.92
                if candidato.source in {"ball_yolo", "beam_candidate", "hough"}:
                    if candidato.motion_score < 0.045 and dist_pred > gate * 0.38:
                        custo += 0.58
                    if candidato.motion_score < 0.025 and candidato.yellow_ratio < 0.14:
                        custo += 0.42
                if _candidato_em_zona_jogador(candidato, players_validos, frame.shape):
                    custo += 0.40
                marca = _marca_bola_auto_dict(candidato, frame_idx, tempo_s, w, h)
                proximos.append(
                    BallBeamState(
                        x=candidato.x,
                        y=candidato.y,
                        vx=vx * 0.76 + estado_beam.vx * 0.24,
                        vy=vy * 0.76 + estado_beam.vy * 0.24,
                        cost=custo,
                        misses=0,
                        detected=estado_beam.detected + 1,
                        path=[*estado_beam.path, marca],
                    )
                )

            if estado_beam.misses < max_misses and estado_beam.detected >= 2:
                pred = BallDetection(
                    pred_x,
                    pred_y,
                    max(2.2, min(9.0, min_dim * 0.004)),
                    max(0.18, 0.46 - estado_beam.misses * 0.035),
                    "trajectory_prediction",
                    0.08,
                    0.08,
                )
                if _candidato_bola_em_escopo_de_tracking(pred, calibracao, frame.shape, [(int(estado_beam.x), int(estado_beam.y))], None):
                    marca = _marca_bola_auto_dict(pred, frame_idx, tempo_s, w, h)
                    proximos.append(
                        BallBeamState(
                            x=pred.x,
                            y=pred.y,
                            vx=estado_beam.vx * 0.96,
                            vy=estado_beam.vy * 0.96,
                            cost=estado_beam.cost + 1.06 + estado_beam.misses * 0.18,
                            misses=estado_beam.misses + 1,
                            detected=estado_beam.detected,
                            path=[*estado_beam.path, marca],
                        )
                    )

        if not proximos:
            frame_pre_anterior = frame_anterior
            frame_anterior = frame
            continue

        def chave_estado(item: BallBeamState) -> float:
            return item.cost - item.detected * 0.34 + item.misses * 0.08

        proximos.sort(key=chave_estado)
        estados = proximos[:beam_width]
        melhor = estados[0]
        if melhor.path and melhor.path[-1].get("source") not in {"auto_prediction", "manual_auto_seed"}:
            ultimo = BallDetection(
                melhor.x,
                melhor.y,
                max(2.4, min_dim * 0.0045),
                0.55,
                "beam_update",
            )
            novo_template = _extrair_template_bola(frame, ultimo)
            if novo_template is not None:
                template_bola = novo_template
        frame_pre_anterior = frame_anterior
        frame_anterior = frame
        if len(melhor.path) >= max_points:
            break

    if not estados:
        return {"marks": [], "quality": {"metodo": "beam_seed", "frames_analisados": frames_processados}}

    melhor = min(estados, key=lambda item: item.cost / max(len(item.path), 1) - item.detected * 0.022)
    marcas = _filtrar_marcas_auto_bola(melhor.path)
    if marcas and marcas[0].get("source") == "manual_auto_seed":
        marcas = marcas[1:]
    marcas = marcas[:max_points]
    confiancas = [float(marca.get("confidence", 0.0)) for marca in marcas]
    return {
        "marks": marcas,
        "quality": {
            "metodo": "beam_global+opencv_template",
            "modo": "seed_manual_global",
            "step_s": round(step_s, 3),
            "fps_video": round(fps_original, 3),
            "target_fps": round(target_fps, 3),
            "seed_time_s": round(seed_frame_idx / fps_ref, 3),
            "seed_frame_index": int(seed_frame_idx),
            "frames_analisados": frames_processados,
            "candidatos_total": candidatos_total,
            "pontos_aceitos": len(marcas),
            "confianca_media": round(fmean(confiancas), 3) if confiancas else 0.0,
            "confianca_min": round(min(confiancas), 3) if confiancas else 0.0,
            "beam_width": beam_width,
        },
    }


def _marca_bola_auto_dict(
    bola: BallDetection,
    frame_idx: int,
    tempo_s: float,
    w: int,
    h: int,
    source: str | None = None,
    label: str | None = None,
) -> dict:
    origem = source or ("auto_prediction" if bola.source == "trajectory_prediction" else "auto_track")
    return {
        "x": round(max(0.0, min(1.0, bola.x / max(w, 1))), 5),
        "y": round(max(0.0, min(1.0, bola.y / max(h, 1))), 5),
        "time_s": round(float(tempo_s), 3),
        "frame_index": int(frame_idx),
        "role": "trajectory",
        "label": label or ("Rastro estimado da bolinha" if origem == "auto_prediction" else "Rastro automatico da bolinha"),
        "source": origem,
        "confidence": round(float(bola.confidence), 3),
        "radius_px": round(float(bola.radius), 2),
        "detector_source": bola.source,
    }


def _filtrar_marcas_auto_bola(marcas: list[dict]) -> list[dict]:
    if len(marcas) < 3:
        return marcas

    ordenadas = sorted(marcas, key=lambda item: float(item.get("time_s", 0.0)))
    filtradas: list[dict] = []
    for marca in ordenadas:
        try:
            x = float(marca.get("x", 0.0))
            y = float(marca.get("y", 0.0))
            confidence = float(marca.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue

        if not filtradas:
            filtradas.append(marca)
            continue

        last = filtradas[-1]
        lx = float(last.get("x", 0.0))
        ly = float(last.get("y", 0.0))
        step = math.hypot(x - lx, y - ly)
        if step > 0.24 and confidence < 0.76:
            continue

        if len(filtradas) >= 2:
            prev = filtradas[-2]
            px = float(prev.get("x", 0.0))
            py = float(prev.get("y", 0.0))
            v1 = (lx - px, ly - py)
            v2 = (x - lx, y - ly)
            n1 = math.hypot(v1[0], v1[1])
            n2 = math.hypot(v2[0], v2[1])
            if n1 > 0.012 and n2 > 0.012:
                cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / max(n1 * n2, 1e-6)
                zigzag_curto = cos_angle < -0.68 and min(n1, n2) < 0.055
                reversao_longa = cos_angle < -0.25 and n2 > max(0.035, n1 * 1.20)
                reversao_vertical_brusca = (
                    v1[1] * v2[1] < 0
                    and abs(v2[1]) > max(0.035, abs(v1[1]) * 1.35)
                    and n2 > n1 * 1.10
                )
                salto_lateral = abs(v2[0]) > max(0.06, abs(v2[1]) * 2.4)
                if confidence < 0.82 and (zigzag_curto or salto_lateral):
                    continue
                if reversao_longa or reversao_vertical_brusca:
                    continue

        filtradas.append(marca)

    for indice, marca in enumerate(filtradas, start=1):
        marca["label"] = f"Rastro automatico {indice}"
        marca["sequence_id"] = f"auto_ball_{indice:03d}"
    return filtradas


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
        "tempo_voo_bruto_s": round(velocidade_saque.tempo_voo_bruto_s, 3),
        "fps_calculo": round(velocidade_saque.fps_calculo, 3),
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


def _load_ball_yolo_model():
    global _BALL_YOLO_LOAD_ATTEMPTED, _BALL_YOLO_MODEL
    global _BALL_YOLO_MODEL_ERROR, _BALL_YOLO_MODEL_MTIME, _BALL_YOLO_MODEL_SOURCE
    if os.getenv("TENNIS_XRAY_USE_BALL_YOLO", "1") != "1":
        return None

    model_source = _resolver_fonte_yolo_bola()
    source_str, source_mtime = _assinatura_fonte_yolo_bola(model_source)
    fonte_inalterada = (
        _BALL_YOLO_LOAD_ATTEMPTED
        and source_str == _BALL_YOLO_MODEL_SOURCE
        and source_mtime == _BALL_YOLO_MODEL_MTIME
    )
    if fonte_inalterada:
        return _BALL_YOLO_MODEL

    _BALL_YOLO_LOAD_ATTEMPTED = True
    _BALL_YOLO_MODEL_SOURCE = source_str
    _BALL_YOLO_MODEL_MTIME = source_mtime
    _BALL_YOLO_MODEL_ERROR = None
    if model_source is None:
        _BALL_YOLO_MODEL = None
        return None

    try:
        from ultralytics import YOLO

        _BALL_YOLO_MODEL = YOLO(str(model_source))
        logger.info(
            "YOLO da bolinha carregado/recarregado de %s (mtime=%s)",
            model_source,
            f"{source_mtime:.3f}" if source_mtime is not None else "n/a",
        )
        return _BALL_YOLO_MODEL
    except Exception as exc:
        logger.warning("YOLO da bolinha indisponivel, usando TrackNet/OpenCV/beam: %s", exc)
        _BALL_YOLO_MODEL = None
        _BALL_YOLO_MODEL_ERROR = str(exc)
        return None


def _assinatura_fonte_yolo_bola(model_source: str | Path | None) -> tuple[str | None, float | None]:
    if model_source is None:
        return None, None
    source_str = str(model_source)
    try:
        caminho = Path(model_source)
        if caminho.exists():
            return source_str, float(caminho.stat().st_mtime)
    except (OSError, TypeError, ValueError):
        pass
    return source_str, None


def _metadata_modelo_yolo_bola() -> dict:
    return {
        "habilitado": os.getenv("TENNIS_XRAY_USE_BALL_YOLO", "1") == "1",
        "tentou_carregar": _BALL_YOLO_LOAD_ATTEMPTED,
        "carregado": _BALL_YOLO_MODEL is not None,
        "fonte": _BALL_YOLO_MODEL_SOURCE,
        "mtime": round(_BALL_YOLO_MODEL_MTIME, 3) if _BALL_YOLO_MODEL_MTIME is not None else None,
        "erro": _BALL_YOLO_MODEL_ERROR,
    }


def _metadata_modelo_tracknet() -> dict:
    tracker = get_tracknet_tracker()
    tentou_carregar = bool(getattr(tracker, "_load_attempted", False))
    try:
        disponivel = bool(tracker.available) if tentou_carregar else False
    except Exception:
        disponivel = False
    weights_path = getattr(tracker, "weights_path", None)
    mtime = None
    try:
        if weights_path is not None and Path(weights_path).exists():
            mtime = Path(weights_path).stat().st_mtime
    except OSError:
        mtime = None
    return {
        "habilitado": bool(getattr(tracker, "enabled", False)),
        "tentou_carregar": tentou_carregar,
        "carregado": disponivel,
        "fonte": str(weights_path) if weights_path else None,
        "mtime": round(float(mtime), 3) if mtime is not None else None,
        "input_width": int(getattr(tracker, "input_width", 0) or 0),
        "input_height": int(getattr(tracker, "input_height", 0) or 0),
        "min_confidence": float(getattr(tracker, "min_confidence", 0.0) or 0.0),
        "min_peak_z": float(getattr(tracker, "min_peak_z", 0.0) or 0.0),
        "min_peak_margin": float(getattr(tracker, "min_peak_margin", 0.0) or 0.0),
        "topk": int(getattr(tracker, "max_candidates", 1) or 1),
        "topk_nms_radius": int(getattr(tracker, "nms_radius", 0) or 0),
    }


def _resolver_fonte_yolo_bola() -> str | Path | None:
    fonte_env = os.getenv("TENNIS_XRAY_YOLO_BALL_MODEL")
    candidatos_locais = [
        fonte_env,
        "weights/tennis_ball_yolo_custom.pt",
        "weights/tennis_ball_yolo.pt",
        "weights/yolo5_last.pt",
        "models/yolo5_last.pt",
    ]
    for fonte in candidatos_locais:
        if not fonte:
            continue
        caminho = Path(fonte)
        if caminho.exists():
            return caminho

    if os.getenv("TENNIS_XRAY_YOLO_BALL_HF_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        logger.info("YOLO da bolinha remoto desativado. Defina TENNIS_XRAY_YOLO_BALL_HF_ENABLED=1 ou coloque pesos locais.")
        return None

    repo_id = (
        fonte_env
        if fonte_env and "/" in fonte_env and not fonte_env.lower().endswith((".pt", ".pth", ".onnx"))
        else os.getenv("TENNIS_XRAY_YOLO_BALL_HF_REPO", "RJTPP/tennis-ball-detection")
    )
    filename = os.getenv("TENNIS_XRAY_YOLO_BALL_HF_FILENAME", "best.pt")
    try:
        from huggingface_hub import hf_hub_download
    except Exception as exc:
        logger.info(
            "YOLO da bolinha remoto indisponivel: instale huggingface_hub para carregar %s/%s direto do Hugging Face (%s).",
            repo_id,
            filename,
            exc,
        )
        return None

    try:
        caminho_cache = hf_hub_download(repo_id=repo_id, filename=filename)
        return Path(caminho_cache)
    except Exception as exc:
        logger.warning("Falha ao baixar/carregar YOLO da bolinha de %s/%s: %s", repo_id, filename, exc)
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


def _validar_video_saida(path: Path, descricao: str = "video") -> None:
    if not path.exists():
        raise RuntimeError(f"Nao foi possivel gerar o {descricao}. Arquivo nao encontrado: {path.name}.")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"Nao foi possivel gerar o {descricao}. Arquivo vazio: {path.name}.")


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
            logger.exception("Falha ao mover MP4 bruto para o destino final.")
    _validar_video_saida(video_destino, "video analisado final")
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
        conf = _float_env("TENNIS_XRAY_YOLO_PLAYER_CONF", 0.025)
        imgsz = _int_env("TENNIS_XRAY_YOLO_PLAYER_IMGSZ", 1536)
        results = modelo_yolo.predict(frame, classes=[0], conf=conf, imgsz=imgsz, verbose=False)
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
        if area_ratio < _float_env("TENNIS_XRAY_YOLO_PLAYER_MIN_AREA_RATIO", 0.000015):
            continue
        boxes.append(DetectionBox(x1, y1, x2, y2, conf, "yolo"))

    boxes.sort(key=lambda b: b.confidence * b.width * b.height, reverse=True)
    return _filtrar_boxes_distintos(boxes, frame.shape)[:10]


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
        if area < w * h * 0.00032 or area > w * h * 0.18:
            continue
        aspect = bh / max(bw, 1)
        if aspect < 0.65 or aspect > 6.2:
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
            if not _box_plausivel_jogador_anchor(box, anchor, frame_shape):
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

        gate = max(70.0, min(w, h) * (0.30 if chave == "p2" else 0.24))
        if melhor_idx is not None and melhor_dist <= gate:
            usados.add(melhor_idx)
            ordenados.append(players[melhor_idx])
        else:
            idx_slot = 0 if chave == "p1" else 1
            hold = _tracking_hold_calibrado(ultimo_players or [], idx_slot, anchor, frame_shape, gate * (1.35 if chave == "p2" else 1.15))
            ordenados.append(hold if hold is not None else _placeholder_jogador(frame_shape, idx_slot))

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


def _limites_box_jogador_por_anchor(
    anchor: tuple[float, float],
    frame_shape: tuple[int, int, int],
) -> tuple[float, float, float]:
    h, w = frame_shape[:2]
    _, ay = anchor
    y_norm = max(0.0, min(1.0, ay / max(h, 1)))
    min_h = max(18.0, h * (0.034 + y_norm * 0.050))
    max_h = max(min_h * 1.8, h * (0.145 + y_norm * 0.300))
    max_w = max(w * 0.030, max_h * 0.82)
    return min_h, max_h, max_w


def _box_plausivel_jogador_anchor(
    box: DetectionBox,
    anchor: tuple[float, float],
    frame_shape: tuple[int, int, int],
) -> bool:
    min_h, max_h, max_w = _limites_box_jogador_por_anchor(anchor, frame_shape)
    if box.height < min_h * 0.55:
        return False
    if box.height > max_h or box.width > max_w:
        return False
    aspect = box.height / max(box.width, 1.0)
    if aspect < 0.90 or aspect > 7.2:
        return False
    return True


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
    if box.source == "tracking_hold" and box.confidence < _confianca_minima_jogador(box.source):
        return None
    if not _box_plausivel_jogador_anchor(box, anchor, frame_shape):
        return None
    if not _box_desenhavel(box) or _distancia_anchor_box(anchor, box) > gate:
        return None
    confidence = min(0.76, box.confidence * (0.78 if box.source != "tracking_hold" else 0.94))
    if confidence < _confianca_minima_jogador("tracking_hold"):
        return None
    return DetectionBox(box.x1, box.y1, box.x2, box.y2, confidence, "tracking_hold")


def _placeholder_jogador_anchor(
    frame_shape: tuple[int, int, int],
    idx: int,
    anchor: tuple[float, float],
) -> DetectionBox:
    h, w = frame_shape[:2]
    ax, ay = anchor
    min_h, max_h, max_w = _limites_box_jogador_por_anchor(anchor, frame_shape)
    bh = max(min_h, min(max_h * 0.72, h * (0.075 + (ay / max(h, 1)) * 0.18)))
    bw = min(max_w, max(w * 0.026, bh * 0.34))
    return DetectionBox(ax - bw / 2, ay - bh * 0.52, ax + bw / 2, ay + bh * 0.48, 0.08, "calibrated_anchor")


def _placeholder_jogador(frame_shape: tuple[int, int, int], idx: int) -> DetectionBox:
    h, w = frame_shape[:2]
    cx = w * (0.50 + (idx - 0.5) * 0.08)
    cy = h * (0.72 if idx == 0 else 0.32)
    bw = w * 0.08
    bh = h * 0.22
    return DetectionBox(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, 0.0, "missing")


def _atualizar_ultimo_players_por_slot(
    players: list[DetectionBox],
    ultimo_players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> list[DetectionBox]:
    slots: list[DetectionBox] = []
    for idx in range(2):
        if idx < len(ultimo_players):
            anterior = ultimo_players[idx]
            slots.append(anterior if _box_desenhavel(anterior) else _placeholder_jogador(frame_shape, idx))
        else:
            slots.append(_placeholder_jogador(frame_shape, idx))

    for idx, box in enumerate(players[:2]):
        if _box_desenhavel(box):
            slots[idx] = box

    return slots[:2]


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
            if not _box_desenhavel(box):
                continue
            confidence = min(0.76, box.confidence * (0.78 if box.source != "tracking_hold" else 0.94))
            if confidence < _confianca_minima_jogador("tracking_hold"):
                continue
            escolhidos.append(
                DetectionBox(
                    box.x1,
                    box.y1,
                    box.x2,
                    box.y2,
                    confidence,
                    "tracking_hold",
                )
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


def _confianca_minima_jogador(source: str) -> float:
    thresholds = {
        "yolo": _float_env("TENNIS_XRAY_PLAYER_DRAW_CONF_YOLO", 0.035),
        "opencv": _float_env("TENNIS_XRAY_PLAYER_DRAW_CONF_OPENCV", 0.22),
        "hog": _float_env("TENNIS_XRAY_PLAYER_DRAW_CONF_HOG", 0.24),
        "tracking_hold": _float_env("TENNIS_XRAY_PLAYER_DRAW_CONF_HOLD", 0.035),
    }
    return thresholds.get(source, _float_env("TENNIS_XRAY_PLAYER_DRAW_CONF_DEFAULT", 0.14))


def _box_desenhavel(box: DetectionBox) -> bool:
    if box.source in {"missing", "placeholder", "calibrated_anchor"}:
        return False
    return box.confidence >= _confianca_minima_jogador(box.source)


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
        role = str(mark.get("role") or mark.get("event") or mark.get("type") or "trajectory")
        source = str(mark.get("source") or "manual")
        if role == "serve_contact_ground":
            continue
        ponto = _ponto_calibracao_px(mark, frame_shape)
        if ponto is None:
            continue
        try:
            tempo_s = float(mark.get("time_s", 0.0))
        except (TypeError, ValueError):
            tempo_s = 0.0
        anchors.append(BallAnchor(max(0.0, tempo_s), ponto[0], ponto[1], source=source, role=role))

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
    anchors_exatos = [anchor for anchor in anchors if not anchor.source.startswith("auto_")]
    if not anchors_exatos:
        return None
    mais_proximo = min(anchors_exatos, key=lambda item: abs(item.tempo_s - tempo_s))
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
            if anterior.source.startswith("auto_") or atual.source.startswith("auto_"):
                confianca = max(0.30, confianca * 0.72)
                gate = max(20.0, gate * 0.86)
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
    calibracao: dict | None = None,
    frame_pre_anterior: np.ndarray | None = None,
    falhas_bola_consecutivas: int = 0,
) -> BallDetection | None:
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    modo_reaquisicao = (
        prior_bola is None
        and bool(ball_track)
        and falhas_bola_consecutivas >= _int_env("TENNIS_XRAY_BALL_REACQUIRE_AFTER", 3)
    )

    if prior_bola is not None:
        yellow = cv2.inRange(hsv, np.array([14, 24, 58]), np.array([76, 255, 255]))
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

    mask = cv2.GaussianBlur(mask, (3, 3), 0) if prior_bola is not None else cv2.medianBlur(mask, 5)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_radius = max(0.95 if prior_bola is not None else 3.0, min(w, h) * (0.0009 if prior_bola is not None else 0.0026))
    min_area = max(math.pi * (min_radius * 0.42) ** 2, w * h * (0.00000035 if prior_bola is not None else 0.000003))
    # Close balls often look larger and motion-blurred. The previous cap was
    # tuned for deep-court dots and could reject the easiest near-camera ball.
    max_area = max(120.0, w * h * (0.00042 if prior_bola is not None else 0.00030))
    candidates: list[tuple[float, BallDetection]] = []
    tracknet_candidate = _candidato_bola_tracknet(
        frame=frame,
        frame_anterior=frame_anterior,
        frame_pre_anterior=frame_pre_anterior,
        players=players or [],
        frame_shape=frame.shape,
        ball_track=ball_track or [],
        prior_bola=prior_bola,
        calibracao=calibracao,
        modo_reaquisicao=modo_reaquisicao,
        falhas_bola_consecutivas=falhas_bola_consecutivas,
    )
    if tracknet_candidate is not None:
        candidates.append(tracknet_candidate)
    if modo_reaquisicao:
        for score, candidato in _candidatos_bola_yolo(
            frame=frame,
            players=players or [],
            frame_shape=frame.shape,
            ball_track=[],
            prior_bola=None,
            calibracao=calibracao,
            motion_mask=motion_mask,
            max_candidates=5,
            modo_reaquisicao=True,
        ):
            if _candidato_reaquisicao_bola_valido(candidato, hsv, players or [], frame.shape):
                candidates.append(
                    (
                        min(0.99, score + 0.26),
                        BallDetection(
                            candidato.x,
                            candidato.y,
                            candidato.radius,
                            candidato.confidence,
                            f"{candidato.source}_reacquired",
                            candidato.motion_score,
                            candidato.yellow_ratio,
                        ),
                    )
                )
    candidates.extend(
        _candidatos_bola_yolo(
            frame=frame,
            players=players or [],
            frame_shape=frame.shape,
            ball_track=ball_track or [],
            prior_bola=prior_bola,
            calibracao=calibracao,
            motion_mask=motion_mask,
            max_candidates=4,
        )
    )
    usar_bright_motion = (
        prior_bola is not None
        or os.getenv("TENNIS_XRAY_ENABLE_BRIGHT_MOTION", "0").strip().lower() in {"1", "true", "yes"}
    )
    if usar_bright_motion:
        candidates.extend(
            _candidatos_bola_bright_motion(
                frame=frame,
                hsv=hsv,
                motion_mask=motion_mask,
                players=players or [],
                frame_shape=frame.shape,
                ball_track=ball_track or [],
                prior_bola=prior_bola,
                calibracao=calibracao,
                falhas_bola_consecutivas=falhas_bola_consecutivas,
                max_candidates=5,
            )
        )
    candidates.extend(
        _candidatos_bola_hough(
            frame=frame,
            hsv=hsv,
            motion_mask=motion_mask,
            players=players or [],
            frame_shape=frame.shape,
            min_radius=min_radius,
            max_radius=max(12.0, min(w, h) * (0.026 if prior_bola is not None else 0.024)),
            prior_bola=prior_bola,
            ball_track=ball_track or [],
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
        if circularity < (0.18 if prior_bola is not None else 0.24):
            continue
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        if radius < min_radius or radius > max(14, min(w, h) * (0.026 if prior_bola is not None else 0.024)):
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
        if sat_media < (28 if prior_bola is not None else 65) or val_media < (58 if prior_bola is not None else 105):
            continue
        core_sat, core_val = _metricas_core_bola(hsv, x, y, radius)
        if core_sat < (30 if prior_bola is not None else 92) or core_val < (62 if prior_bola is not None else 120):
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
            if prior_bola is None and dist < max(4.0, radius * 1.2) and motion_score < 0.22:
                continue

        score = (
            circularity * 0.34
            + min(area / max_area, 1.0) * 0.14
            + min(sat_media / 180.0, 1.0) * 0.18
            + min(motion_score * 2.2, 1.0) * 0.22
            + continuity * 0.12
        )
        local_yellow = cv2.inRange(roi_hsv, np.array([14, 24, 58]), np.array([76, 255, 255]))
        yellow_ratio = float(np.count_nonzero(local_yellow)) / max(local_yellow.size, 1)
        candidate = BallDetection(float(x), float(y), float(radius), min(0.98, score), "visual", motion_score, yellow_ratio)
        if prior_bola is not None and _candidato_sobre_linha_branca(hsv, candidate, motion_score, 0.0):
            continue
        if _candidato_em_zona_jogador(candidate, players or [], frame.shape) and not _prior_confirma_candidato(candidate, prior_bola):
            continue
        if prior_bola is not None and _distancia_prior(candidate, prior_bola) > prior_bola.gate_px * 2.0:
            continue
        score = _score_bola_contextual(score, candidate, players or [], ball_track or [], frame.shape, prior_bola)
        if score >= 0.34:
            candidates.append((score, BallDetection(candidate.x, candidate.y, candidate.radius, min(0.98, score), candidate.source, candidate.motion_score, candidate.yellow_ratio)))

    if prior_bola is not None:
        candidates.extend(
            _candidatos_bola_pequena_prior(
                hsv=hsv,
                motion_mask=motion_mask,
                players=players or [],
                frame_shape=frame.shape,
                prior_bola=prior_bola,
                ball_track=ball_track or [],
            )
        )

    if not candidates:
        return None
    if calibracao is not None:
        candidates = [
            (score, candidate)
            for score, candidate in candidates
            if _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame.shape, ball_track or [], prior_bola)
            or (
                _candidato_modelo_bola_forte(candidate)
                and _bola_renderizavel_no_escopo(candidate, calibracao, frame.shape)
            )
        ]
        if not candidates:
            return None
    if ball_track:
        if modo_reaquisicao:
            candidates = [
                (score, candidate)
                for score, candidate in candidates
                if (
                    _movimento_bola_cinematico_valido(candidate, ball_track, frame.shape, prior_bola)
                    or (
                        _candidato_reaquisicao_bola_valido(candidate, hsv, players or [], frame.shape)
                        and _candidato_reaquisicao_em_janela(
                            candidate,
                            ball_track,
                            frame.shape,
                            falhas_bola_consecutivas,
                        )
                    )
                )
            ]
        else:
            candidates = [
                (score, candidate)
                for score, candidate in candidates
                if _movimento_bola_cinematico_valido(candidate, ball_track, frame.shape, prior_bola)
            ]
        if not candidates:
            return None
    if ball_track:
        last_x, last_y = ball_track[-1]

        def selection_score(item: tuple[float, BallDetection]) -> float:
            score, candidate = item
            dist_last = math.hypot(candidate.x - float(last_x), candidate.y - float(last_y))
            gate = max(18.0, min(w, h) * 0.040)
            if prior_bola is not None:
                gate = max(gate, prior_bola.gate_px * 0.92)
            fonte_bonus = 0.10 if _fonte_bola_normalizada(candidate.source) in {"tracknet", "ball_yolo"} else 0.0
            return score + fonte_bonus + max(0.0, 1.0 - dist_last / max(gate, 1.0)) * 0.22

        rankeados = [(selection_score(item), item[0], item[1]) for item in candidates]
        melhor_rank, best_score, best_candidate = max(rankeados, key=lambda item: item[0])
        yolo_rankeados = [item for item in rankeados if _fonte_bola_normalizada(item[2].source) == "ball_yolo"]
        if yolo_rankeados:
            yolo_rank, yolo_score, yolo_candidate = max(yolo_rankeados, key=lambda item: item[0])
            if yolo_rank >= melhor_rank - 0.10 and yolo_score >= best_score - 0.16:
                best_score, best_candidate = yolo_score, yolo_candidate
    else:
        best_score, best_candidate = max(candidates, key=lambda item: item[0])
        yolo_candidates = [item for item in candidates if _fonte_bola_normalizada(item[1].source) == "ball_yolo"]
        if yolo_candidates:
            yolo_score, yolo_candidate = max(yolo_candidates, key=lambda item: item[0])
            if yolo_score >= best_score - 0.08:
                best_score, best_candidate = yolo_score, yolo_candidate
    min_score = 0.40 if prior_bola is not None else 0.58
    if best_score < min_score:
        return None
    return best_candidate


def _candidato_bola_tracknet(
    frame: np.ndarray,
    frame_anterior: np.ndarray | None,
    frame_pre_anterior: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    ball_track: list[tuple[int, int]],
    prior_bola: BallPrior | None,
    calibracao: dict | None,
    modo_reaquisicao: bool = False,
    falhas_bola_consecutivas: int = 0,
) -> tuple[float, BallDetection] | None:
    candidatos = _candidatos_bola_tracknet(
        frame=frame,
        frame_anterior=frame_anterior,
        frame_pre_anterior=frame_pre_anterior,
        players=players,
        frame_shape=frame_shape,
        ball_track=ball_track,
        prior_bola=prior_bola,
        calibracao=calibracao,
        modo_reaquisicao=modo_reaquisicao,
        falhas_bola_consecutivas=falhas_bola_consecutivas,
        max_candidates=1,
    )
    return candidatos[0] if candidatos else None


def _candidatos_bola_tracknet(
    frame: np.ndarray,
    frame_anterior: np.ndarray | None,
    frame_pre_anterior: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    ball_track: list[tuple[int, int]],
    prior_bola: BallPrior | None,
    calibracao: dict | None,
    modo_reaquisicao: bool = False,
    falhas_bola_consecutivas: int = 0,
    max_candidates: int | None = None,
) -> list[tuple[float, BallDetection]]:
    tracker = get_tracknet_tracker()
    if not tracker.available:
        return []

    limite = max(1, int(max_candidates or _int_env("TENNIS_XRAY_TRACKNET_GLOBAL_TOPK", 5)))
    results = tracker.detect_many(frame_pre_anterior, frame_anterior, frame, max_candidates=limite)
    if not results:
        return []

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    motion_mask = _mask_movimento(frame, frame_anterior)
    candidatos: list[tuple[float, BallDetection]] = []
    for result in results:
        rank = int(getattr(result, "rank", len(candidatos)) or 0)
        candidate = BallDetection(
            x=result.x,
            y=result.y,
            radius=result.radius,
            confidence=min(0.99, max(0.0, result.confidence)),
            source="tracknet",
            motion_score=0.0,
            yellow_ratio=0.0,
        )
        motion_score, yellow_ratio, core_sat, core_val = _metricas_locais_candidato_tracknet(
            hsv=hsv,
            motion_mask=motion_mask,
            candidate=candidate,
        )
        candidate.motion_score = motion_score
        candidate.yellow_ratio = yellow_ratio

        peak_z = float(getattr(result, "peak_z", 0.0) or 0.0)
        peak_margin = float(getattr(result, "peak_margin", 0.0) or 0.0)
        heatmap_score = float(getattr(result, "heatmap_score", result.confidence) or 0.0)
        pico_forte = peak_z >= 3.75 or peak_margin >= 0.035 or (peak_z >= 3.1 and heatmap_score >= 0.70)
        if rank > 0:
            pico_forte = pico_forte or (peak_z >= 3.35 and heatmap_score >= 0.68 and peak_margin >= 0.010)
        evidencia_visual = yellow_ratio >= 0.052 or (yellow_ratio >= 0.022 and core_sat >= 52 and core_val >= 122)
        evidencia_movimento = motion_score >= _float_env("TENNIS_XRAY_TRACKNET_LOCAL_MOTION_MIN", 0.045)
        inicio_exige_movimento = _bool_env("TENNIS_XRAY_TRACKNET_START_REQUIRES_MOTION", True)
        reacquisicao_modelo_forte = (
            modo_reaquisicao
            and falhas_bola_consecutivas >= _int_env("TENNIS_XRAY_TRACKNET_REACQUIRE_MIN_GAPS", 12)
            and _candidato_modelo_bola_forte(candidate)
        )

        if _candidato_sobre_linha_branca(hsv, candidate, motion_score, yellow_ratio):
            continue
        if prior_bola is None and not ball_track:
            # TrackNet sozinho nao pode iniciar um rastro a partir de um pico sem
            # movimento/cor local. Isso evita "bolinhas fantasmas" presas em regioes
            # vazias quando o heatmap ainda esta pouco treinado.
            if not pico_forte:
                continue
            if inicio_exige_movimento and not evidencia_movimento:
                continue
            if not (evidencia_movimento or evidencia_visual):
                continue
        else:
            if not (evidencia_movimento or evidencia_visual):
                perto_prior = prior_bola is not None and _prior_confirma_candidato(candidate, prior_bola)
                perto_ultimo = False
                if ball_track:
                    last_x, last_y = ball_track[-1]
                    gate = max(18.0, min(frame_shape[:2]) * 0.030)
                    if prior_bola is not None:
                        gate = max(gate, prior_bola.gate_px * 0.56)
                    perto_ultimo = math.hypot(candidate.x - float(last_x), candidate.y - float(last_y)) <= gate
                if not (pico_forte and (perto_prior or perto_ultimo) and heatmap_score >= 0.72):
                    continue

        if _candidato_em_zona_jogador(candidate, players, frame_shape) and not _prior_confirma_candidato(candidate, prior_bola):
            # TrackNet can still light up rackets/clothes. Keep contact points only
            # when they agree with an existing temporal prior.
            if not ball_track:
                contato_forte = candidate.confidence >= 0.82 and motion_score >= 0.18 and yellow_ratio >= 0.045
                if not contato_forte:
                    continue
            elif math.hypot(candidate.x - float(ball_track[-1][0]), candidate.y - float(ball_track[-1][1])) > max(22.0, min(frame_shape[:2]) * 0.040):
                continue

        if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame_shape, ball_track, prior_bola):
            if not (reacquisicao_modelo_forte and _bola_renderizavel_no_escopo(candidate, calibracao, frame_shape)):
                continue
            candidate.source = "tracknet_reacquired"
        if ball_track and not _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, prior_bola):
            if not (reacquisicao_modelo_forte and _bola_renderizavel_no_escopo(candidate, calibracao, frame_shape)):
                continue
            candidate.source = "tracknet_reacquired"

        score = (
            0.34
            + candidate.confidence * 0.38
            + min(motion_score * 2.6, 1.0) * 0.16
            + min(yellow_ratio * 2.4, 1.0) * 0.08
            + min(peak_z / 8.0, 1.0) * 0.08
            + min(peak_margin / 0.16, 1.0) * 0.06
        )
        score = _score_bola_contextual(score, candidate, players, ball_track, frame_shape, prior_bola)
        if rank > 0:
            score -= min(0.20, 0.055 * rank)
        if candidate.source == "tracknet_reacquired":
            score = max(score, 0.74)
        if score >= (0.46 if prior_bola is not None else 0.52):
            candidatos.append((score, candidate))
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos


def _metricas_locais_candidato_tracknet(
    hsv: np.ndarray,
    motion_mask: np.ndarray | None,
    candidate: BallDetection,
) -> tuple[float, float, float, float]:
    h, w = hsv.shape[:2]
    cx = int(round(candidate.x))
    cy = int(round(candidate.y))
    raio = int(round(max(7.0, candidate.radius * 4.4)))
    x0 = max(0, cx - raio)
    y0 = max(0, cy - raio)
    x1 = min(w, cx + raio + 1)
    y1 = min(h, cy + raio + 1)
    roi_hsv = hsv[y0:y1, x0:x1]
    if roi_hsv.size == 0:
        return 0.0, 0.0, 0.0, 0.0

    # Use compact yellow evidence instead of a broad yellow/green mask. Tennis
    # courts, walls and banners often share the ball hue; the ball should be a
    # compact local highlight, not a uniform patch where center and ring look
    # the same.
    strict_yellow = cv2.inRange(roi_hsv, np.array([18, 62, 105]), np.array([58, 255, 255]))
    yy, xx = np.ogrid[: roi_hsv.shape[0], : roi_hsv.shape[1]]
    local_cx = float(cx - x0)
    local_cy = float(cy - y0)
    core_r = max(2.0, candidate.radius * 1.45)
    core_mask = ((xx - local_cx) ** 2 + (yy - local_cy) ** 2) <= core_r * core_r
    ring_mask = ~core_mask
    core_size = int(np.count_nonzero(core_mask))
    ring_size = int(np.count_nonzero(ring_mask))
    core_yellow = float(np.count_nonzero(strict_yellow[core_mask])) / max(core_size, 1)
    ring_yellow = float(np.count_nonzero(strict_yellow[ring_mask])) / max(ring_size, 1)
    compact_yellow = max(0.0, core_yellow - ring_yellow * 0.72)

    core_sat, core_val = _metricas_core_bola(hsv, candidate.x, candidate.y, max(candidate.radius, 2.0))
    if ring_size > 0:
        ring_pixels = roi_hsv[ring_mask]
        ring_sat = float(np.mean(ring_pixels[:, 1])) if ring_pixels.size else 0.0
        ring_val = float(np.mean(ring_pixels[:, 2])) if ring_pixels.size else 0.0
        compact_yellow += max(0.0, core_sat - ring_sat - 18.0) / 220.0
        compact_yellow += max(0.0, core_val - ring_val - 18.0) / 260.0
    yellow_ratio = min(1.0, compact_yellow)
    motion_score = 0.0
    if motion_mask is not None:
        motion_roi = motion_mask[y0:y1, x0:x1]
        motion_score = float(np.count_nonzero(motion_roi)) / max(motion_roi.size, 1)
    return motion_score, yellow_ratio, core_sat, core_val


def _candidato_reaquisicao_bola_valido(
    candidate: BallDetection,
    hsv: np.ndarray,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
) -> bool:
    source = _fonte_bola_normalizada(candidate.source)
    if source == "tracknet":
        if candidate.confidence < 0.68:
            return False
        if candidate.motion_score < 0.065 and candidate.yellow_ratio < 0.045:
            return False
    elif source == "ball_yolo":
        if candidate.confidence < 0.43:
            return False
        if candidate.motion_score < 0.020 and candidate.yellow_ratio < 0.12 and candidate.confidence < 0.66:
            return False
    elif source == "bright_motion":
        if candidate.confidence < 0.42:
            return False
        if candidate.motion_score < 0.050 or candidate.yellow_ratio < 0.030:
            return False
    else:
        if candidate.confidence < 0.52 or (candidate.motion_score < 0.08 and candidate.yellow_ratio < 0.14):
            return False

    if _candidato_sobre_linha_branca(hsv, candidate, candidate.motion_score, candidate.yellow_ratio):
        return False
    if _candidato_em_zona_jogador(candidate, players, frame_shape):
        return source in {"ball_yolo", "bright_motion"} and candidate.confidence >= 0.68 and candidate.motion_score >= 0.12
    return True


def _candidato_reaquisicao_em_janela(
    candidate: BallDetection,
    ball_track: list[tuple[int, int]],
    frame_shape: tuple[int, int, int],
    falhas_bola_consecutivas: int,
) -> bool:
    if not ball_track:
        return True

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    gap_steps = max(1.0, min(12.0, float(falhas_bola_consecutivas + 1)))
    pred_x, pred_y, pred_conf = _predizer_bola_cinematica(ball_track, None, gap_steps, frame_shape)
    dist_pred = math.hypot(candidate.x - pred_x, candidate.y - pred_y)

    velocidade_recente = 0.0
    if len(ball_track) >= 2:
        janela = ball_track[-min(len(ball_track), 5) :]
        passos = [
            math.hypot(float(janela[i][0] - janela[i - 1][0]), float(janela[i][1] - janela[i - 1][1]))
            for i in range(1, len(janela))
        ]
        if passos:
            velocidade_recente = float(np.median(passos))

    gate = max(
        34.0,
        min_dim * (0.038 + min(gap_steps, 8.0) * 0.006),
        velocidade_recente * (1.85 + min(gap_steps, 8.0) * 0.18) + 20.0 + gap_steps * 5.0,
    )
    if candidate.confidence >= 0.80 and candidate.motion_score >= 0.16:
        gate *= 1.18
    if _candidato_modelo_bola_forte(candidate):
        gate *= 1.20
    if pred_conf < 0.46:
        gate *= 1.08
    return dist_pred <= gate


def _candidatos_bola_yolo(
    frame: np.ndarray,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    ball_track: list[tuple[int, int]],
    prior_bola: BallPrior | None,
    calibracao: dict | None,
    motion_mask: np.ndarray | None = None,
    max_candidates: int = 6,
    modo_reaquisicao: bool = False,
) -> list[tuple[float, BallDetection]]:
    modelo = _load_ball_yolo_model()
    if modelo is None:
        return []

    try:
        conf = _float_env("TENNIS_XRAY_YOLO_BALL_CONF", 0.06)
        imgsz = _int_env("TENNIS_XRAY_YOLO_BALL_IMGSZ", 1536)
        results = modelo.predict(frame, conf=conf, imgsz=imgsz, verbose=False)
    except Exception as exc:
        logger.debug("YOLO da bolinha falhou no frame: %s", exc)
        return []

    if not results or results[0].boxes is None:
        return []

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    candidatos: list[tuple[float, BallDetection]] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].cpu().numpy()]
        conf_box = float(box.conf[0].cpu().numpy())
        bw = max(1.0, x2 - x1)
        bh = max(1.0, y2 - y1)
        area_ratio = (bw * bh) / max(w * h, 1)
        if area_ratio > 0.0022:
            continue
        if bw > min_dim * 0.085 or bh > min_dim * 0.085:
            continue

        x = (x1 + x2) / 2.0
        y = (y1 + y2) / 2.0
        radius = max(1.7, min(10.0, max(bw, bh) / 2.15))

        roi_pad = int(round(max(4.0, radius * 1.9)))
        rx0 = max(0, int(round(x - roi_pad)))
        ry0 = max(0, int(round(y - roi_pad)))
        rx1 = min(w, int(round(x + roi_pad + 1)))
        ry1 = min(h, int(round(y + roi_pad + 1)))

        motion_score = 0.0
        if motion_mask is not None and rx1 > rx0 and ry1 > ry0:
            motion_roi = motion_mask[ry0:ry1, rx0:rx1]
            motion_score = float(np.count_nonzero(motion_roi)) / max(motion_roi.size, 1)

        yellow_ratio = 0.0
        if rx1 > rx0 and ry1 > ry0:
            roi_hsv = hsv[ry0:ry1, rx0:rx1]
            local_yellow = cv2.inRange(roi_hsv, np.array([13, 24, 58]), np.array([82, 255, 255]))
            yellow_ratio = float(np.count_nonzero(local_yellow)) / max(local_yellow.size, 1)

        candidate_conf = (
            0.38
            + conf_box * 0.42
            + min(motion_score * 3.2, 1.0) * 0.16
            + min(yellow_ratio * 2.2, 1.0) * 0.04
        )
        candidate = BallDetection(x, y, radius, min(0.97, candidate_conf), "ball_yolo", motion_score, yellow_ratio)

        dist_prior = _distancia_prior(candidate, prior_bola) if prior_bola is not None else 0.0
        perto_do_prior = prior_bola is not None and dist_prior <= prior_bola.gate_px * 0.62
        if prior_bola is not None and dist_prior > prior_bola.gate_px * 1.75:
            continue
        if prior_bola is None and not ball_track and motion_mask is None:
            # Sem frame anterior nao existe prova de movimento. Nao deixe um
            # detector iniciar o rastro no primeiro frame em logo/rede/linha.
            continue
        if motion_mask is not None:
            # O YOLO de bola tende a ativar em placas, fita da rede e reflexos. Sem
            # movimento local real, esses pontos estaticos nao devem iniciar nem
            # desviar o rastro, exceto quando ja estao colados na previsao temporal.
            if prior_bola is None and not ball_track:
                if modo_reaquisicao:
                    if motion_score < 0.030 and conf_box < 0.68 and yellow_ratio < 0.18:
                        continue
                elif motion_score < _float_env("TENNIS_XRAY_YOLO_BALL_START_MOTION_MIN", 0.085):
                    continue
                if not modo_reaquisicao and motion_score < 0.16 and conf_box < 0.84 and yellow_ratio < 0.24:
                    continue
            elif motion_score < 0.030 and not perto_do_prior and conf_box < 0.88:
                continue
        if _candidato_sobre_linha_branca(hsv, candidate, motion_score, yellow_ratio):
            continue
        if _candidato_em_zona_jogador(candidate, players, frame_shape) and not _prior_confirma_candidato(candidate, prior_bola):
            contato_plausivel = (
                bool(ball_track)
                and motion_score >= 0.13
                and (yellow_ratio >= 0.10 or conf_box >= 0.72)
                and _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, prior_bola)
            )
            if not contato_plausivel:
                continue
        if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame_shape, ball_track, prior_bola):
            continue
        if ball_track and not _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, prior_bola):
            continue

        score = (
            0.40
            + conf_box * 0.36
            + min(motion_score * 3.0, 1.0) * 0.18
            + min(yellow_ratio * 2.2, 1.0) * 0.06
        )
        if motion_mask is not None and motion_score < 0.055:
            score -= 0.08 if perto_do_prior else 0.32
        score = _score_bola_contextual(score, candidate, players, ball_track, frame_shape, prior_bola)
        candidatos.append((min(0.99, score), BallDetection(candidate.x, candidate.y, candidate.radius, min(0.99, score), candidate.source, candidate.motion_score, candidate.yellow_ratio)))

    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[:max_candidates]


def _candidatos_bola_bright_motion(
    frame: np.ndarray,
    hsv: np.ndarray,
    motion_mask: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    ball_track: list[tuple[int, int]],
    prior_bola: BallPrior | None,
    calibracao: dict | None,
    falhas_bola_consecutivas: int = 0,
    max_candidates: int = 5,
) -> list[tuple[float, BallDetection]]:
    """Detecta bolinhas claras em movimento que o filtro amarelo/YOLO perde.

    Muitos videos de transmissao comprimem a bola para um ponto quase branco.
    Esta etapa so atua em ROI temporal/cinematica, usa movimento local e
    contraste compacto para evitar que linhas da quadra virem bola.
    """

    if motion_mask is None:
        return []

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    roi: tuple[int, int, int, int] | None = None
    pred_ref: tuple[float, float, float] | None = None

    if prior_bola is not None:
        roi = _roi_bola_prior(prior_bola, frame_shape)
        pred_ref = (prior_bola.x, prior_bola.y, max(18.0, prior_bola.gate_px))
    elif ball_track:
        gap_steps = max(1.0, min(10.0, float(falhas_bola_consecutivas + 1)))
        pred_x, pred_y, _ = _predizer_bola_cinematica(ball_track, None, gap_steps, frame_shape)
        velocidade_recente = 0.0
        if len(ball_track) >= 2:
            janela = ball_track[-min(len(ball_track), 5) :]
            passos = [
                math.hypot(float(janela[i][0] - janela[i - 1][0]), float(janela[i][1] - janela[i - 1][1]))
                for i in range(1, len(janela))
            ]
            if passos:
                velocidade_recente = float(np.median(passos))
        gate = max(
            44.0,
            min_dim * (0.050 + min(gap_steps, 8.0) * 0.007),
            velocidade_recente * (2.1 + min(gap_steps, 8.0) * 0.22) + 26.0 + gap_steps * 7.0,
        )
        x0 = max(0, int(round(pred_x - gate)))
        y0 = max(0, int(round(pred_y - gate)))
        x1 = min(w, int(round(pred_x + gate)) + 1)
        y1 = min(h, int(round(pred_y + gate)) + 1)
        roi = (x0, y0, x1, y1)
        pred_ref = (pred_x, pred_y, gate)
    elif calibracao:
        # Sem rastro ainda, limitamos ao poligono expandido da quadra. O score
        # exigido sera mais alto porque nao ha ancora temporal.
        roi = (0, 0, w, h)

    if roi is None:
        return []

    x0, y0, x1, y1 = roi
    if x1 <= x0 or y1 <= y0:
        return []

    crop_hsv = hsv[y0:y1, x0:x1]
    crop_motion = motion_mask[y0:y1, x0:x1]
    if crop_hsv.size == 0 or crop_motion.size == 0:
        return []

    yellow = cv2.inRange(crop_hsv, np.array([10, 18, 45]), np.array([86, 255, 255]))
    bright = cv2.inRange(crop_hsv, np.array([0, 0, 142]), np.array([179, 158, 255]))
    motion_dilatado = cv2.dilate(crop_motion, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
    mask = cv2.bitwise_and(cv2.bitwise_or(yellow, bright), motion_dilatado)
    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    _, mask = cv2.threshold(mask, 18, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = max(1.0, w * h * 0.00000010)
    max_area = max(95.0, w * h * 0.00011)
    candidatos: list[tuple[float, BallDetection]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(1, min(bw, bh))
        if aspect > 3.15:
            continue
        perimeter = cv2.arcLength(cnt, True)
        circularity = 0.0 if perimeter <= 0 else 4 * math.pi * area / (perimeter * perimeter)
        if circularity < 0.075:
            continue

        (lx, ly), radius = cv2.minEnclosingCircle(cnt)
        x = float(x0 + lx)
        y = float(y0 + ly)
        radius = float(radius)
        if radius < 0.55 or radius > max(9.0, min_dim * 0.0105):
            continue

        pad = max(3.0, radius * 2.4)
        rx0 = max(0, int(round(x - pad)))
        ry0 = max(0, int(round(y - pad)))
        rx1 = min(w, int(round(x + pad)) + 1)
        ry1 = min(h, int(round(y + pad)) + 1)
        local_hsv = hsv[ry0:ry1, rx0:rx1]
        local_motion = motion_mask[ry0:ry1, rx0:rx1]
        if local_hsv.size == 0 or local_motion.size == 0:
            continue

        local_yellow = cv2.inRange(local_hsv, np.array([10, 18, 45]), np.array([86, 255, 255]))
        local_bright = cv2.inRange(local_hsv, np.array([0, 0, 142]), np.array([179, 158, 255]))
        yellow_ratio = float(np.count_nonzero(local_yellow)) / max(local_yellow.size, 1)
        bright_ratio = float(np.count_nonzero(local_bright)) / max(local_bright.size, 1)
        motion_score = float(np.count_nonzero(local_motion)) / max(local_motion.size, 1)
        core_sat, core_val = _metricas_core_bola(hsv, x, y, max(radius, 1.4))
        ring_sat = float(np.mean(local_hsv[:, :, 1]))
        ring_val = float(np.mean(local_hsv[:, :, 2]))
        contrast_val = max(0.0, core_val - ring_val)
        contrast_sat = max(0.0, core_sat - ring_sat)
        evidence = max(yellow_ratio, bright_ratio * 0.72, contrast_val / 170.0, contrast_sat / 190.0)

        if motion_score < (0.055 if ball_track or prior_bola is not None else 0.12):
            continue
        if evidence < (0.026 if ball_track or prior_bola is not None else 0.070):
            continue
        if core_val < 88 and evidence < 0.10:
            continue

        candidate = BallDetection(x, y, radius, 0.0, "bright_motion", motion_score, evidence)
        if _candidato_sobre_linha_branca(hsv, candidate, motion_score, evidence):
            continue
        if _candidato_em_zona_jogador(candidate, players, frame_shape):
            contato_plausivel = (
                bool(ball_track)
                and motion_score >= 0.15
                and evidence >= 0.07
                and _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, prior_bola)
            )
            if not contato_plausivel:
                continue
        if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame_shape, ball_track, prior_bola):
            continue
        if ball_track and not _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, prior_bola):
            continue

        dist_score = 0.0
        if pred_ref is not None:
            px, py, gate = pred_ref
            dist_score = max(0.0, 1.0 - math.hypot(x - px, y - py) / max(gate, 1.0))
        score = (
            0.24
            + min(motion_score * 2.5, 1.0) * 0.24
            + min(evidence * 2.4, 1.0) * 0.18
            + min(circularity, 1.0) * 0.12
            + min(contrast_val / 90.0, 1.0) * 0.08
            + dist_score * 0.26
        )
        if not ball_track and prior_bola is None:
            score -= 0.10
        score = _score_bola_contextual(score, candidate, players, ball_track, frame_shape, prior_bola)
        if score >= (0.36 if ball_track or prior_bola is not None else 0.54):
            candidatos.append((min(0.96, score), BallDetection(x, y, radius, min(0.96, score), "bright_motion", motion_score, evidence)))

    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[:max_candidates]


def _extrair_template_bola(frame: np.ndarray, bola: BallDetection | None) -> np.ndarray | None:
    if bola is None:
        return None
    h, w = frame.shape[:2]
    raio = int(round(max(5.0, min(15.0, bola.radius * 2.6))))
    cx = int(round(bola.x))
    cy = int(round(bola.y))
    x0 = max(0, cx - raio)
    y0 = max(0, cy - raio)
    x1 = min(w, cx + raio + 1)
    y1 = min(h, cy + raio + 1)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    yellow = cv2.inRange(hsv, np.array([10, 20, 45]), np.array([84, 255, 255]))
    if float(np.count_nonzero(yellow)) / max(yellow.size, 1) < 0.025 and bola.source == "manual_seed":
        # A primeira marcacao pode ter sido levemente fora do centro; ainda
        # assim mantemos o template, mas com contraste normalizado.
        pass
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)
    return gray


def _candidato_bola_template(
    frame: np.ndarray,
    template: np.ndarray | None,
    prior_bola: BallPrior | None,
    players: list[DetectionBox],
    ball_track: list[tuple[int, int]],
    calibracao: dict | None,
) -> BallDetection | None:
    if template is None or prior_bola is None or template.size == 0:
        return None

    h, w = frame.shape[:2]
    x0, y0, x1, y1 = _roi_bola_prior(prior_bola, frame.shape) or (0, 0, w, h)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)
    escalas = (0.55, 0.72, 0.90, 1.12, 1.35)
    melhor: tuple[float, float, float, float] | None = None
    for escala in escalas:
        tw = max(7, int(round(template.shape[1] * escala)))
        th = max(7, int(round(template.shape[0] * escala)))
        if tw >= gray.shape[1] or th >= gray.shape[0]:
            continue
        tmpl = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA if escala < 1.0 else cv2.INTER_CUBIC)
        try:
            resposta = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        except cv2.error:
            continue
        _, max_val, _, max_loc = cv2.minMaxLoc(resposta)
        score = float(max_val)
        cx = float(x0 + max_loc[0] + tw / 2)
        cy = float(y0 + max_loc[1] + th / 2)
        dist = math.hypot(cx - prior_bola.x, cy - prior_bola.y)
        dist_score = max(0.0, 1.0 - dist / max(prior_bola.gate_px * 1.55, 1.0))
        combinado = score * 0.72 + dist_score * 0.28
        if melhor is None or combinado > melhor[0]:
            melhor = (combinado, cx, cy, max(tw, th) / 4.6)

    if melhor is None:
        return None

    combinado, x, y, radius = melhor
    if combinado < 0.43:
        return None

    candidate = BallDetection(
        x=float(x),
        y=float(y),
        radius=max(1.8, min(10.0, float(radius))),
        confidence=max(0.24, min(0.74, combinado)),
        source="template_prior",
        motion_score=0.18,
        yellow_ratio=0.10,
    )
    if _candidato_em_zona_jogador(candidate, players, frame.shape) and not _prior_confirma_candidato(candidate, prior_bola):
        return None
    if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame.shape, ball_track, prior_bola):
        return None
    if not _movimento_bola_cinematico_valido(candidate, ball_track, frame.shape, prior_bola):
        return None
    return candidate


def _candidatos_bola_amplos(
    frame: np.ndarray,
    frame_anterior: np.ndarray | None,
    frame_pre_anterior: np.ndarray | None,
    players: list[DetectionBox],
    calibracao: dict | None,
) -> list[BallDetection]:
    """Gera candidatos de bolinha em todo o frame para o beam tracker.

    Diferente do detector local, esta etapa nao escolhe um unico ponto. Ela
    coleta candidatos plausiveis para que a selecao global decida a rota mais
    coerente ao longo do tempo.
    """

    h, w = frame.shape[:2]
    min_dim = float(min(w, h))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    motion_mask = _mask_movimento(frame, frame_anterior)
    candidatos: list[BallDetection] = []

    tracknets = _candidatos_bola_tracknet(
        frame=frame,
        frame_anterior=frame_anterior,
        frame_pre_anterior=frame_pre_anterior,
        players=players,
        frame_shape=frame.shape,
        ball_track=[],
        prior_bola=None,
        calibracao=calibracao,
        max_candidates=_int_env("TENNIS_XRAY_TRACKNET_GLOBAL_TOPK", 5),
    )
    candidatos.extend([candidato for _, candidato in tracknets])
    candidatos.extend([
        candidato
        for _, candidato in _candidatos_bola_yolo(
            frame=frame,
            players=players,
            frame_shape=frame.shape,
            ball_track=[],
            prior_bola=None,
            calibracao=calibracao,
            motion_mask=motion_mask,
            max_candidates=10,
        )
    ])

    yellow = cv2.inRange(hsv, np.array([10, 22, 50]), np.array([86, 255, 255]))
    bright = cv2.inRange(hsv, np.array([0, 0, 148]), np.array([179, 138, 255]))
    mask = cv2.bitwise_or(yellow, bright)
    if motion_mask is not None:
        motion_dilatado = cv2.dilate(motion_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        mask = cv2.bitwise_or(cv2.bitwise_and(mask, motion_dilatado), yellow)

    if calibracao:
        poligono = _poligono_quadra_video_px(calibracao, frame.shape)
        if poligono is not None:
            court_mask = np.zeros((h, w), dtype=np.uint8)
            margem = int(max(28.0, min_dim * 0.040))
            poligono_expandido = poligono.astype(np.int32)
            cv2.fillPoly(court_mask, [poligono_expandido], 255)
            court_mask = cv2.dilate(court_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margem | 1, margem | 1)), iterations=1)
            mask = cv2.bitwise_and(mask, court_mask)

    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    _, mask = cv2.threshold(mask, 18, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = max(1.0, w * h * 0.00000012)
    max_area = max(96.0, w * h * 0.00013)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(1, min(bw, bh))
        if aspect > 2.85:
            continue
        perimeter = cv2.arcLength(cnt, True)
        circularity = 0.0 if perimeter <= 0 else 4 * math.pi * area / (perimeter * perimeter)
        if circularity < 0.10:
            continue

        (x, y), radius = cv2.minEnclosingCircle(cnt)
        radius = float(radius)
        if radius < 0.55 or radius > max(10.0, min_dim * 0.012):
            continue

        rx0 = max(0, int(x - max(2.0, radius * 2.0)))
        ry0 = max(0, int(y - max(2.0, radius * 2.0)))
        rx1 = min(w, int(x + max(2.0, radius * 2.0)) + 1)
        ry1 = min(h, int(y + max(2.0, radius * 2.0)) + 1)
        local_hsv = hsv[ry0:ry1, rx0:rx1]
        if local_hsv.size == 0:
            continue

        local_yellow = cv2.inRange(local_hsv, np.array([10, 22, 50]), np.array([86, 255, 255]))
        yellow_ratio = float(np.count_nonzero(local_yellow)) / max(local_yellow.size, 1)
        sat_mean = float(np.mean(local_hsv[:, :, 1]))
        val_mean = float(np.mean(local_hsv[:, :, 2]))
        motion_score = 0.0
        if motion_mask is not None:
            local_motion = motion_mask[ry0:ry1, rx0:rx1]
            motion_score = float(np.count_nonzero(local_motion)) / max(local_motion.size, 1)

        candidate = BallDetection(float(x), float(y), radius, 0.0, "beam_candidate", motion_score, yellow_ratio)
        if _candidato_sobre_linha_branca(hsv, candidate, motion_score, yellow_ratio):
            continue
        if _candidato_em_zona_jogador(candidate, players, frame.shape) and motion_score < 0.20 and yellow_ratio < 0.16:
            continue
        if _candidato_bola_em_borda_frame(candidate, frame.shape, margem_px=max(18.0, min_dim * 0.022)):
            continue
        if not _candidato_bola_no_corredor_quadra_central(
            candidate,
            calibracao,
            frame.shape,
            margem_px=max(24.0, min_dim * 0.035),
            margem_ar_px=max(64.0, min_dim * 0.095),
        ):
            continue
        if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame.shape, [], None):
            continue

        score = (
            0.22
            + min(yellow_ratio * 2.6, 1.0) * 0.24
            + min(max(sat_mean, 18.0) / 165.0, 1.0) * 0.14
            + min(val_mean / 220.0, 1.0) * 0.10
            + min(motion_score * 1.8, 1.0) * 0.16
            + min(circularity, 1.0) * 0.14
        )
        if score < 0.32:
            continue
        candidatos.append(BallDetection(float(x), float(y), radius, min(0.86, score), "beam_candidate", motion_score, yellow_ratio))

    candidatos.sort(key=lambda item: item.confidence, reverse=True)
    return candidatos[:36]


def _candidatos_bola_hough(
    frame: np.ndarray,
    hsv: np.ndarray,
    motion_mask: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    min_radius: float,
    max_radius: float,
    prior_bola: BallPrior | None = None,
    ball_track: list[tuple[int, int]] | None = None,
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
        param2=15 if prior_bola is not None else 34,
        minRadius=max(1 if prior_bola is not None else 2, int(min_radius)),
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

        yellow_mask = cv2.inRange(roi_hsv, np.array([14, 24, 58]), np.array([76, 255, 255]))
        yellow_ratio = float(np.count_nonzero(yellow_mask)) / max(yellow_mask.size, 1)
        sat_mean = float(np.mean(roi_hsv[:, :, 1]))
        val_mean = float(np.mean(roi_hsv[:, :, 2]))
        if yellow_ratio < (0.035 if prior_bola is not None else 0.18) or sat_mean < (24 if prior_bola is not None else 62) or val_mean < (46 if prior_bola is not None else 78):
            continue
        core_sat, core_val = _metricas_core_bola(hsv, x, y, radius)
        if core_sat < (28 if prior_bola is not None else 96) or core_val < (54 if prior_bola is not None else 122):
            continue

        motion_score = 0.0
        if motion_mask is not None:
            motion_roi = motion_mask[cy0:cy1, cx0:cx1]
            motion_score = float(np.count_nonzero(motion_roi)) / max(motion_roi.size, 1)
            if prior_bola is None and motion_score < 0.05:
                continue

        candidate = BallDetection(x=x, y=y, radius=radius, confidence=0.0, motion_score=motion_score, yellow_ratio=yellow_ratio)
        if prior_bola is not None and _candidato_sobre_linha_branca(hsv, candidate, motion_score, yellow_ratio):
            continue
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
        score = _score_bola_contextual(score, candidate, players, ball_track or [], frame_shape, prior_bola)
        if score >= (0.38 if prior_bola is not None else 0.46):
            candidates.append((score, BallDetection(x, y, radius, min(0.98, score), "hough", motion_score, yellow_ratio)))

    return candidates


def _candidatos_bola_pequena_prior(
    hsv: np.ndarray,
    motion_mask: np.ndarray | None,
    players: list[DetectionBox],
    frame_shape: tuple[int, int, int],
    prior_bola: BallPrior,
    ball_track: list[tuple[int, int]] | None = None,
) -> list[tuple[float, BallDetection]]:
    h, w = frame_shape[:2]
    roi = _roi_bola_prior(prior_bola, frame_shape)
    if roi is None:
        return []

    x0, y0, x1, y1 = roi
    crop_hsv = hsv[y0:y1, x0:x1]
    if crop_hsv.size == 0:
        return []

    yellow = cv2.inRange(crop_hsv, np.array([12, 18, 48]), np.array([82, 255, 255]))
    bright = cv2.inRange(crop_hsv, np.array([0, 0, 132]), np.array([179, 145, 255]))
    mask = cv2.bitwise_or(yellow, bright)
    if motion_mask is not None:
        motion_crop = motion_mask[y0:y1, x0:x1]
        motion_crop = cv2.dilate(motion_crop, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        mask = cv2.bitwise_or(cv2.bitwise_and(mask, motion_crop), yellow)

    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    _, mask = cv2.threshold(mask, 24, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = max(1.2, w * h * 0.00000018)
    max_area = max(52.0, w * h * 0.000075)
    candidates: list[tuple[float, BallDetection]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(1, min(bw, bh))
        if aspect > 2.35:
            continue
        perimeter = cv2.arcLength(cnt, True)
        circularity = 0.0 if perimeter <= 0 else 4 * math.pi * area / (perimeter * perimeter)
        if circularity < 0.12:
            continue

        (x_local, y_local), radius = cv2.minEnclosingCircle(cnt)
        x = float(x0 + x_local)
        y = float(y0 + y_local)
        radius = float(radius)
        if radius < 0.65 or radius > max(7.0, min(w, h) * 0.011):
            continue

        dist_prior = math.hypot(x - prior_bola.x, y - prior_bola.y)
        if dist_prior > prior_bola.gate_px * 1.45:
            continue

        rx0 = max(0, int(x - max(2.0, radius * 1.9)))
        ry0 = max(0, int(y - max(2.0, radius * 1.9)))
        rx1 = min(w, int(x + max(2.0, radius * 1.9)) + 1)
        ry1 = min(h, int(y + max(2.0, radius * 1.9)) + 1)
        local_hsv = hsv[ry0:ry1, rx0:rx1]
        if local_hsv.size == 0:
            continue

        local_yellow = cv2.inRange(local_hsv, np.array([12, 18, 48]), np.array([82, 255, 255]))
        yellow_ratio = float(np.count_nonzero(local_yellow)) / max(local_yellow.size, 1)
        sat_mean = float(np.mean(local_hsv[:, :, 1]))
        val_mean = float(np.mean(local_hsv[:, :, 2]))

        motion_score = 0.0
        if motion_mask is not None:
            local_motion = motion_mask[ry0:ry1, rx0:rx1]
            motion_score = float(np.count_nonzero(local_motion)) / max(local_motion.size, 1)

        candidate = BallDetection(x=x, y=y, radius=radius, confidence=0.0, source="small_prior")
        if _candidato_sobre_linha_branca(hsv, candidate, motion_score, yellow_ratio):
            continue
        if yellow_ratio < 0.035 and (motion_score < 0.18 or sat_mean < 34 or val_mean < 118):
            continue
        if _candidato_em_zona_jogador(candidate, players, frame_shape) and dist_prior > prior_bola.gate_px * 0.72:
            continue

        dist_score = max(0.0, 1.0 - dist_prior / max(prior_bola.gate_px * 1.45, 1.0))
        score = (
            0.22
            + dist_score * 0.42
            + min(yellow_ratio * 2.8, 1.0) * 0.14
            + min(max(sat_mean, 20.0) / 150.0, 1.0) * 0.08
            + min(val_mean / 210.0, 1.0) * 0.08
            + min(motion_score * 1.7, 1.0) * 0.06
            + min(circularity, 1.0) * 0.06
        )
        score = _score_bola_contextual(score, candidate, players, ball_track or [], frame_shape, prior_bola)
        if score >= 0.36:
            candidates.append((score, BallDetection(x, y, radius, min(0.92, score), "small_prior", motion_score, yellow_ratio)))

    return candidates


def _candidato_sobre_linha_branca(
    hsv: np.ndarray,
    candidate: BallDetection,
    motion_score: float,
    yellow_ratio: float,
) -> bool:
    """Reject white court/net-line fragments that look like tiny balls.

    The ball can become very small in depth, but it should not be accepted when
    the local neighborhood is dominated by a long white horizontal/vertical
    structure, such as the net tape or a painted court line.
    """

    if yellow_ratio >= 0.075:
        return False

    h, w = hsv.shape[:2]
    raio = int(round(max(8.0, candidate.radius * 5.5)))
    cx = int(round(candidate.x))
    cy = int(round(candidate.y))
    x0 = max(0, cx - raio)
    y0 = max(0, cy - raio)
    x1 = min(w, cx + raio + 1)
    y1 = min(h, cy + raio + 1)
    local = hsv[y0:y1, x0:x1]
    if local.size == 0:
        return False

    white = cv2.inRange(local, np.array([0, 0, 132]), np.array([179, 72, 255]))
    if white.size == 0:
        return False

    centro_y = min(max(cy - y0, 0), white.shape[0] - 1)
    centro_x = min(max(cx - x0, 0), white.shape[1] - 1)
    faixa_h = white[max(0, centro_y - 1) : min(white.shape[0], centro_y + 2), :]
    faixa_v = white[:, max(0, centro_x - 1) : min(white.shape[1], centro_x + 2)]
    horizontal = float(np.count_nonzero(faixa_h)) / max(faixa_h.size, 1)
    vertical = float(np.count_nonzero(faixa_v)) / max(faixa_v.size, 1)
    white_total = float(np.count_nonzero(white)) / max(white.size, 1)
    line_score = max(horizontal, vertical)

    if line_score >= 0.48 and white_total >= 0.10 and motion_score < 0.30:
        return True
    if line_score >= 0.64 and white_total >= 0.06:
        return True
    return False


def _candidato_bola_em_escopo_de_tracking(
    candidate: BallDetection,
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
    ball_track: list[tuple[int, int]],
    prior_bola: BallPrior | None,
) -> bool:
    if not calibracao:
        return True

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    if candidate.source not in {"manual_anchor", "calibrated_fill"} and _candidato_bola_em_borda_frame(
        candidate,
        frame_shape,
        margem_px=max(18.0, min_dim * 0.022),
    ):
        return False
    if not ball_track and candidate.source not in {"manual_anchor", "calibrated_fill"}:
        if not _candidato_bola_no_corredor_quadra_central(
            candidate,
            calibracao,
            frame_shape,
            margem_px=max(26.0, min_dim * 0.040),
            margem_ar_px=max(70.0, min_dim * 0.105),
        ):
            return False

    fora = False
    transformacao = _transformacao_video_para_quadra(calibracao)
    if transformacao is not None:
        convertido = _aplicar_transformacao(transformacao, candidate.x / max(w, 1), candidate.y / max(h, 1))
        if convertido is not None:
            x_m, y_m = convertido
            margem_x_m = 2.8
            margem_y_m = 5.2
            fora = not (-margem_x_m <= x_m <= COURT_WIDTH_M + margem_x_m and -margem_y_m <= y_m <= COURT_LENGTH_M + margem_y_m)

    if not fora:
        poligono = _poligono_quadra_video_px(calibracao, frame_shape)
        if poligono is not None:
            margem_px = max(58.0, min_dim * 0.070)
            fora = cv2.pointPolygonTest(poligono, (float(candidate.x), float(candidate.y)), True) < -margem_px

    if not fora:
        return True

    if not ball_track:
        return candidate.confidence >= 0.84 and candidate.motion_score >= 0.20

    last_x, last_y = ball_track[-1]
    dist_last = math.hypot(candidate.x - float(last_x), candidate.y - float(last_y))
    gate_continuidade = max(20.0, min_dim * 0.034)
    if prior_bola is not None:
        gate_continuidade = max(gate_continuidade, prior_bola.gate_px * 0.62)

    # Fora da quadra so e aceito quando segue colado no rastro. Artefatos em
    # placa, banco, fundo ou lateral costumam estar fora do escopo e longe do
    # ultimo ponto real.
    if dist_last <= gate_continuidade and candidate.motion_score >= 0.10:
        return True
    if dist_last <= gate_continuidade * 0.72 and candidate.yellow_ratio >= 0.16:
        return True
    return False


def _candidato_bola_no_corredor_quadra_central(
    candidate: BallDetection,
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
    margem_px: float | None = None,
    margem_ar_px: float | None = None,
) -> bool:
    """Valida se a bolinha esta no corredor visual da quadra principal.

    O detector pode acertar "bolinhas" em outras quadras, mochilas, bancos e
    logos. Para o rastro automatico, essas regioes nao devem competir com a
    bola da quadra calibrada. A margem extra acima da baseline permite bola no
    ar, mas ainda dentro das laterais extrapoladas da quadra central.
    """

    if not calibracao or candidate.source in {"manual_anchor", "calibrated_fill"}:
        return True

    pontos = _pontos_calibracao_normalizados(calibracao)
    ids = ("sup_esquerda", "sup_direita", "inf_direita", "inf_esquerda")
    if not all(nome in pontos for nome in ids):
        return True

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    margem = float(margem_px if margem_px is not None else max(30.0, min_dim * 0.045))
    margem_ar = float(margem_ar_px if margem_ar_px is not None else max(72.0, min_dim * 0.110))
    sup_esq = (pontos["sup_esquerda"][0] * w, pontos["sup_esquerda"][1] * h)
    sup_dir = (pontos["sup_direita"][0] * w, pontos["sup_direita"][1] * h)
    inf_dir = (pontos["inf_direita"][0] * w, pontos["inf_direita"][1] * h)
    inf_esq = (pontos["inf_esquerda"][0] * w, pontos["inf_esquerda"][1] * h)
    poligono = np.asarray([sup_esq, sup_dir, inf_dir, inf_esq], dtype=np.float32)

    px = float(candidate.x)
    py = float(candidate.y)
    distancia_poligono = cv2.pointPolygonTest(poligono, (px, py), True)
    if distancia_poligono >= -margem:
        return True

    topo_y = min(sup_esq[1], sup_dir[1])
    base_y = max(inf_esq[1], inf_dir[1])
    if py < topo_y:
        if py < topo_y - margem_ar:
            return False
        x_esq = _x_linha_em_y(sup_esq, inf_esq, py)
        x_dir = _x_linha_em_y(sup_dir, inf_dir, py)
        if x_esq is None or x_dir is None:
            return False
        x_min = min(x_esq, x_dir) - max(margem, min_dim * 0.035)
        x_max = max(x_esq, x_dir) + max(margem, min_dim * 0.035)
        return x_min <= px <= x_max

    if py > base_y + max(margem, min_dim * 0.045):
        return False

    return False


def _bola_renderizavel_no_escopo(
    bola: BallDetection,
    calibracao: dict | None,
    frame_shape: tuple[int, int, int] | None,
) -> bool:
    if frame_shape is None:
        return True
    h, w = frame_shape[:2]
    if h <= 0 or w <= 0:
        return True
    min_dim = float(min(w, h))
    if bola.source not in {"manual_anchor", "calibrated_fill"} and _candidato_bola_em_borda_frame(
        bola,
        frame_shape,
        margem_px=max(18.0, min_dim * 0.022),
    ):
        return False
    return _candidato_bola_no_corredor_quadra_central(
        bola,
        calibracao,
        frame_shape,
        margem_px=max(24.0, min_dim * 0.035),
        margem_ar_px=max(64.0, min_dim * 0.095),
    )


def _candidato_bola_em_borda_frame(
    candidate: BallDetection,
    frame_shape: tuple[int, int, int],
    margem_px: float | None = None,
) -> bool:
    h, w = frame_shape[:2]
    if h <= 0 or w <= 0:
        return False
    margem = float(margem_px if margem_px is not None else max(18.0, min(w, h) * 0.022))
    return (
        candidate.x <= margem
        or candidate.x >= float(w) - margem
        or candidate.y <= margem
        or candidate.y >= float(h) - margem
    )


def _x_linha_em_y(p1: tuple[float, float], p2: tuple[float, float], y: float) -> float | None:
    y1 = float(p1[1])
    y2 = float(p2[1])
    if abs(y2 - y1) < 1e-6:
        return None
    t = (float(y) - y1) / (y2 - y1)
    return float(p1[0]) + (float(p2[0]) - float(p1[0])) * t


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
    return _distancia_prior(candidate, prior_bola) <= max(18.0, prior_bola.gate_px * 0.62)


def _tendencia_vertical_bola(ball_track: list[tuple[int, int]], amostras: int = 4) -> float:
    if len(ball_track) < 2:
        return 0.0

    inicio = max(1, len(ball_track) - amostras)
    deslocamentos = [
        float(ball_track[i][1] - ball_track[i - 1][1])
        for i in range(inicio, len(ball_track))
    ]
    if not deslocamentos:
        return 0.0
    tendencia_local = float(median(deslocamentos))
    janela = ball_track[-min(len(ball_track), max(3, amostras + 1)) :]
    if len(janela) >= 3:
        tendencia_total = (float(janela[-1][1]) - float(janela[0][1])) / max(len(janela) - 1, 1)
        if abs(tendencia_total) > abs(tendencia_local):
            return tendencia_total
    return tendencia_local


def _predizer_bola_cinematica(
    ball_track: list[tuple[int, int]],
    ultima_bola: BallDetection | None,
    gap_steps: float,
    frame_shape: tuple[int, int, int],
) -> tuple[float, float, float]:
    h, w = frame_shape[:2]
    min_dim = float(min(w, h))

    if not ball_track:
        if ultima_bola is None:
            return w / 2.0, h / 2.0, 0.0
        return ultima_bola.x, ultima_bola.y, 0.48

    last_x, last_y = map(float, ball_track[-1])
    if len(ball_track) < 2:
        return last_x, last_y, 0.56

    inicio = max(1, len(ball_track) - 4)
    dxs = [float(ball_track[i][0] - ball_track[i - 1][0]) for i in range(inicio, len(ball_track))]
    dys = [float(ball_track[i][1] - ball_track[i - 1][1]) for i in range(inicio, len(ball_track))]
    vx = float(median(dxs)) if dxs else 0.0
    vy = float(median(dys)) if dys else 0.0

    ax = 0.0
    ay = 0.0
    if len(ball_track) >= 3:
        prev_x, prev_y = map(float, ball_track[-2])
        prev_prev_x, prev_prev_y = map(float, ball_track[-3])
        vprev_x = prev_x - prev_prev_x
        vprev_y = prev_y - prev_prev_y
        ax = max(-min_dim * 0.020, min(min_dim * 0.020, vx - vprev_x))
        ay = max(-min_dim * 0.024, min(min_dim * 0.032, vy - vprev_y))

    gap = max(1.0, min(float(gap_steps), 8.0))
    dx = vx * gap + 0.18 * ax * gap * (gap + 1.0)
    dy = vy * gap + 0.18 * ay * gap * (gap + 1.0)

    deslocamento_max = min_dim * (0.040 + 0.045 * min(gap, 4.0))
    norma = math.hypot(dx, dy)
    if norma > deslocamento_max:
        escala = deslocamento_max / max(norma, 1e-6)
        dx *= escala
        dy *= escala

    pred_x = max(0.0, min(float(w - 1), last_x + dx))
    pred_y = max(0.0, min(float(h - 1), last_y + dy))
    confianca = 0.68 if len(ball_track) >= 4 else 0.58
    return pred_x, pred_y, confianca


def _bola_predita_por_rastro(
    ball_track: list[tuple[int, int]],
    ultima_bola: BallDetection | None,
    frame_shape: tuple[int, int, int],
    gap_steps: float,
    falhas_consecutivas: int,
    calibracao: dict | None,
) -> BallDetection | None:
    if ultima_bola is None or len(ball_track) < 3:
        return None

    max_falhas = _int_env("TENNIS_XRAY_BALL_PREDICT_MAX_GAPS", 36)
    if _candidato_modelo_bola_forte(ultima_bola):
        max_falhas = max(max_falhas, _int_env("TENNIS_XRAY_BALL_PREDICT_STRONG_MAX_GAPS", 96))
    if falhas_consecutivas >= max_falhas:
        return None

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    pred_x, pred_y, pred_conf = _predizer_bola_cinematica(ball_track, ultima_bola, gap_steps, frame_shape)
    last_x, last_y = map(float, ball_track[-1])
    step = math.hypot(pred_x - last_x, pred_y - last_y)
    max_step = max(24.0, min_dim * (0.038 + 0.018 * min(max(gap_steps, 1.0), 4.0)))
    if step > max_step:
        return None

    confidence = max(0.16, min(0.48, pred_conf * 0.62 - falhas_consecutivas * 0.018))
    candidate = BallDetection(
        x=pred_x,
        y=pred_y,
        radius=max(2.5, min(12.0, ultima_bola.radius)),
        confidence=confidence,
        source="trajectory_prediction",
        motion_score=0.12,
        yellow_ratio=0.18,
    )
    if not _candidato_bola_em_escopo_de_tracking(candidate, calibracao, frame_shape, ball_track, None):
        return None
    if not _movimento_bola_cinematico_valido(candidate, ball_track, frame_shape, None):
        return None
    return candidate


def _movimento_bola_cinematico_valido(
    candidate: BallDetection,
    ball_track: list[tuple[int, int]],
    frame_shape: tuple[int, int, int],
    prior_bola: BallPrior | None,
) -> bool:
    if len(ball_track) < 3 or candidate.source in {"manual_anchor", "calibrated_fill"}:
        return True

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    last_x, last_y = map(float, ball_track[-1])
    tendencia_y = _tendencia_vertical_bola(ball_track)
    dy = candidate.y - last_y
    gap_steps = 1.0
    if prior_bola is not None and prior_bola.interval_s > 0:
        gap_steps = max(1.0, min(8.0, prior_bola.interval_s / 0.02))
    pred_x, pred_y, _ = _predizer_bola_cinematica(ball_track, None, gap_steps, frame_shape)
    dist_pred = math.hypot(candidate.x - pred_x, candidate.y - pred_y)
    gate_pred = max(18.0, min_dim * 0.042)
    if prior_bola is not None:
        gate_pred = max(gate_pred, prior_bola.gate_px * 0.58)
    if candidate.source == "trajectory_prediction":
        return dist_pred <= gate_pred * 1.35

    # Quando a bola ja esta descendo, artefatos acima da rota costumam roubar
    # o tracking. A reversao so e aceita se ela tambem estiver coerente com a
    # previsao cinetica curta.
    descendo = tendencia_y > max(3.5, min_dim * 0.0055)
    subiu_demais = dy < -max(7.0, min_dim * 0.010)
    if descendo and subiu_demais and dist_pred > gate_pred * 0.72:
        return False

    if len(ball_track) >= 4:
        janela = ball_track[-4:]
        ref_vx = (float(janela[-1][0]) - float(janela[0][0])) / max(len(janela) - 1, 1)
        ref_vy = (float(janela[-1][1]) - float(janela[0][1])) / max(len(janela) - 1, 1)
        cand_vx = candidate.x - last_x
        cand_vy = candidate.y - last_y
        ref_norm = math.hypot(ref_vx, ref_vy)
        cand_norm = math.hypot(cand_vx, cand_vy)
        if ref_norm > max(4.0, min_dim * 0.006) and cand_norm > max(5.0, min_dim * 0.007):
            cos_angle = (ref_vx * cand_vx + ref_vy * cand_vy) / max(ref_norm * cand_norm, 1e-6)
            accel = math.hypot(cand_vx - ref_vx, cand_vy - ref_vy)
            pouco_movimento_visual = candidate.motion_score < 0.10 and candidate.yellow_ratio < 0.12
            curva_brusca = cos_angle < -0.05 and accel > max(14.0, ref_norm * 1.65, min_dim * 0.020)
            if curva_brusca and (dist_pred > gate_pred * 0.55 or pouco_movimento_visual):
                return False

    # Rejeita saltos verticais de alta confianca visual, mas fisicamente
    # distantes da previsao. Isso evita linhas quase retas para cima quando a
    # bola real esta caindo.
    if dist_pred > gate_pred * 1.45:
        if _fonte_bola_normalizada(candidate.source) in {"small_prior", "visual_smoothed"}:
            return False
        if abs(dy) > max(12.0, min_dim * 0.018) and not _prior_confirma_candidato(candidate, prior_bola):
            return False

    return True


def _validar_bola_temporal(
    bola: BallDetection,
    ball_track: list[tuple[int, int]],
    frame_shape: tuple[int, int, int],
    prior_bola: BallPrior | None,
) -> bool:
    source = _fonte_bola_normalizada(bola.source)
    if source in {"manual_anchor", "calibrated_fill", "manual_seed"}:
        return True

    h, w = frame_shape[:2]
    if prior_bola is not None:
        dist_prior = _distancia_prior(bola, prior_bola)
        if dist_prior > max(20.0, prior_bola.gate_px * 0.92):
            return False

    if not ball_track:
        return True

    if str(bola.source).endswith("_reacquired"):
        return bola.confidence >= 0.50 and (bola.motion_score >= 0.030 or bola.yellow_ratio >= 0.14)

    last_x, last_y = ball_track[-1]
    step = math.hypot(bola.x - last_x, bola.y - last_y)
    max_step = max(32.0, min(w, h) * 0.045)
    if prior_bola is not None:
        max_step = max(max_step, prior_bola.gate_px * 0.95)
    else:
        max_step = max(80.0, min(w, h) * 0.12)
    if step > max_step:
        return False
    if len(ball_track) < 4 and step > max(24.0, min(w, h) * 0.038) and bola.confidence < 0.86:
        return False

    if not _movimento_bola_cinematico_valido(bola, ball_track, frame_shape, prior_bola):
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


def _confirmar_inicio_rastro_bola(
    pendente: tuple[int, BallDetection] | None,
    frame_idx: int,
    bola: BallDetection,
    frame_shape: tuple[int, int, int],
    fps_original: float,
) -> tuple[int, BallDetection] | None:
    """Require two plausible detections before starting an automatic trail.

    Single-frame tennis-ball detections are noisy: logos, net tape and static
    court marks can receive high model confidence. This confirmation gate makes
    the automatic trail start only after the point moves like a ball.
    """

    if pendente is None:
        return None

    primeiro_idx, primeira_bola = pendente
    delta_frames = max(1, int(frame_idx) - int(primeiro_idx))
    max_gap_frames = max(2, int(round(max(fps_original, 1.0) * 0.30)))
    if delta_frames > max_gap_frames:
        return None

    h, w = frame_shape[:2]
    min_dim = float(min(w, h))
    dist = math.hypot(bola.x - primeira_bola.x, bola.y - primeira_bola.y)
    dt_s = delta_frames / max(fps_original, 1.0)
    deslocamento_min = max(3.5, min_dim * 0.0035)
    deslocamento_max = max(38.0, min_dim * (0.030 + min(dt_s, 0.30) * 0.36))

    evidencias = [
        bola.motion_score >= 0.040,
        primeira_bola.motion_score >= 0.040,
        bola.yellow_ratio >= 0.11,
        primeira_bola.yellow_ratio >= 0.11,
        bola.confidence >= 0.86 and primeira_bola.confidence >= 0.78,
    ]
    if sum(1 for ok in evidencias if ok) < 2:
        return None
    if dist < deslocamento_min or dist > deslocamento_max:
        return None

    return primeiro_idx, primeira_bola


def _max_predicoes_render_bola(ultima_bola: BallDetection | None) -> int:
    base = _int_env("TENNIS_XRAY_BALL_RENDER_PREDICT_MAX_GAPS", 8)
    if ultima_bola is not None and _candidato_modelo_bola_forte(ultima_bola):
        return max(base, _int_env("TENNIS_XRAY_BALL_RENDER_PREDICT_STRONG_MAX_GAPS", 96))
    return base


def _hard_reset_frames_bola(fps_original: float, hard_reset_bola_s: float, ultima_bola: BallDetection | None) -> int:
    base = max(4, int(round(max(fps_original, 1.0) * hard_reset_bola_s)))
    if ultima_bola is not None and _candidato_modelo_bola_forte(ultima_bola):
        forte_s = _float_env("TENNIS_XRAY_BALL_STRONG_HARD_RESET_GAP_S", 2.75)
        return max(base, int(round(max(fps_original, 1.0) * forte_s)))
    return base


def _bola_alimenta_tracking_local(bola: BallDetection, vem_de_trajetoria_global: bool) -> bool:
    if bola.source == "trajectory_prediction":
        return False
    if not vem_de_trajetoria_global:
        return True
    fonte = _fonte_bola_normalizada(bola.source)
    if fonte in {"manual_anchor", "calibrated_fill", "manual_seed"}:
        return True
    return _candidato_modelo_bola_forte(bola)


def _candidato_inicio_imediato_rastro_bola(bola: BallDetection) -> bool:
    if bola.source in {"manual_anchor", "calibrated_fill"}:
        return True
    source = _fonte_bola_normalizada(bola.source)
    if source == "tracknet":
        return bola.confidence >= 0.78 and bola.motion_score >= 0.070 and bola.yellow_ratio >= 0.045
    if source == "ball_yolo":
        return bola.confidence >= 0.62 and bola.motion_score >= 0.075 and bola.yellow_ratio >= 0.180
    return False


def _candidato_modelo_bola_forte(bola: BallDetection) -> bool:
    source = _fonte_bola_normalizada(bola.source)
    if source == "tracknet":
        return bola.confidence >= 0.76 and (
            bola.motion_score >= 0.070
            or bola.yellow_ratio >= 0.100
            or (bola.confidence >= 0.86 and bola.yellow_ratio >= 0.055)
        )
    if source == "ball_yolo":
        return bola.confidence >= 0.62 and (
            bola.motion_score >= 0.100
            or bola.yellow_ratio >= 0.350
            or bola.confidence >= 0.72
        )
    return False


def _candidato_substitui_predicao_global(
    candidato: BallDetection | None,
    predicao_global: BallDetection,
    frame_shape: tuple[int, int, int],
    players: list[DetectionBox],
    calibracao: dict | None,
) -> bool:
    if candidato is None or predicao_global.source != "trajectory_prediction":
        return False
    if not _candidato_modelo_bola_forte(candidato):
        return False
    if _candidato_bola_em_borda_frame(candidato, frame_shape):
        return False
    if not _candidato_bola_no_corredor_quadra_central(candidato, calibracao, frame_shape):
        return False
    if not _bola_renderizavel_no_escopo(candidato, calibracao, frame_shape):
        return False

    dist_predicao = math.hypot(candidato.x - predicao_global.x, candidato.y - predicao_global.y)
    if dist_predicao < max(18.0, min(frame_shape[:2]) * 0.020):
        return candidato.confidence >= predicao_global.confidence + 0.02

    if _candidato_em_zona_jogador(candidato, players, frame_shape):
        source = _fonte_bola_normalizada(candidato.source)
        if source == "tracknet":
            return candidato.confidence >= 0.84 and candidato.motion_score >= 0.14 and candidato.yellow_ratio >= 0.045
        if source == "ball_yolo":
            return candidato.confidence >= 0.68 and candidato.motion_score >= 0.12 and candidato.yellow_ratio >= 0.18
        return False

    return True


def _suavizar_bola_com_prior(bola: BallDetection, prior_bola: BallPrior | None) -> BallDetection:
    if prior_bola is None or bola.source in {"manual_anchor", "calibrated_fill"}:
        return bola
    if _fonte_bola_normalizada(bola.source) in {"tracknet", "ball_yolo"}:
        return bola
    dist_prior = _distancia_prior(bola, prior_bola)
    if dist_prior > max(18.0, prior_bola.gate_px * 0.9):
        return bola
    peso_prior = min(0.42, max(0.18, prior_bola.confidence * 0.34))
    x = bola.x * (1 - peso_prior) + prior_bola.x * peso_prior
    y = bola.y * (1 - peso_prior) + prior_bola.y * peso_prior
    return BallDetection(
        x,
        y,
        bola.radius,
        min(0.98, max(bola.confidence, prior_bola.confidence * 0.72)),
        "visual_smoothed",
        bola.motion_score,
        bola.yellow_ratio,
    )


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
        score += max(0.0, 1.0 - dist_prior / max(prior_bola.gate_px, 1.0)) * (0.42 * prior_bola.confidence)
        if dist_prior > prior_bola.gate_px * 1.15:
            score -= 0.54
        if dist_prior > prior_bola.gate_px * 1.65:
            score -= 1.0

    if ball_track:
        last_x, last_y = ball_track[-1]
        dist_last = math.hypot(candidate.x - float(last_x), candidate.y - float(last_y))
        gate_last = max(16.0, min(w, h) * 0.035)
        if prior_bola is not None:
            gate_last = max(18.0, min(gate_last * 1.45, prior_bola.gate_px * 0.86))
        score += max(0.0, 1.0 - dist_last / max(gate_last, 1.0)) * 0.72
        if len(ball_track) < 4 and dist_last > gate_last * 1.25:
            score -= 0.90
        elif dist_last > gate_last * 1.95:
            score -= 0.58

    if len(ball_track) >= 2:
        last_x, last_y = ball_track[-1]
        pred_x, pred_y, pred_conf = _predizer_bola_cinematica(ball_track, None, 1.0, frame_shape)
        dist_pred = math.hypot(candidate.x - pred_x, candidate.y - pred_y)
        gate = max(90.0, min(w, h) * 0.16)
        if prior_bola is not None:
            gate = max(24.0, min(gate, prior_bola.gate_px * 1.05))
        score += max(0.0, 1.0 - dist_pred / gate) * (0.24 * max(0.50, pred_conf))
        if dist_pred > gate * 1.85:
            score -= 0.32
        tendencia_y = _tendencia_vertical_bola(ball_track)
        dy = candidate.y - float(last_y)
        if tendencia_y > max(3.5, min(w, h) * 0.0055) and dy < -max(7.0, min(w, h) * 0.010):
            score -= 0.58

    valid_players = [box for box in players if _box_desenhavel(box)]
    if valid_players and len(ball_track) <= 1:
        jogador_proximo = max(valid_players, key=lambda box: box.center[1])
        score += _score_contexto_saque(candidate, jogador_proximo, frame_shape) * 0.38

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
        if not _box_desenhavel(box):
            continue
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


def _fps_para_calculo_saque(calibracao: dict | None, fps_original: float | None = None) -> float:
    candidatos = [fps_original]
    video = (calibracao or {}).get("video", {}) if isinstance((calibracao or {}).get("video"), dict) else {}
    candidatos.extend([video.get("fps"), (calibracao or {}).get("fps")])
    for candidato in candidatos:
        try:
            fps = float(candidato)
        except (TypeError, ValueError):
            continue
        if math.isfinite(fps) and fps >= 1.0:
            return max(1.0, min(240.0, fps))
    return 30.0


def _quantizar_tempo_frame(tempo_s: float, fps: float) -> float:
    fps_ref = max(1.0, min(240.0, float(fps or 30.0)))
    return max(0.0, round(max(0.0, tempo_s) * fps_ref) / fps_ref)


def _float_dict(data: dict, chave: str, padrao: float = 0.0) -> float:
    try:
        valor = float(data.get(chave, padrao))
    except (TypeError, ValueError):
        return padrao
    return valor if math.isfinite(valor) else padrao


def _int_dict(data: dict, chave: str, padrao: int = 0) -> int:
    try:
        valor = int(float(data.get(chave, padrao)))
    except (TypeError, ValueError):
        return padrao
    return valor


def _velocidade_saque_travada(calibracao: dict | None) -> ServeSpeedEvent | None:
    if not isinstance(calibracao, dict):
        return None
    raw = calibracao.get("serve_speed_locked")
    if not isinstance(raw, dict):
        serve_metrics = calibracao.get("serve_metrics")
        raw = serve_metrics.get("locked_speed") if isinstance(serve_metrics, dict) else None
    if not isinstance(raw, dict):
        return None

    velocidade_kmh = _float_dict(raw, "velocidade_kmh")
    if velocidade_kmh <= 0:
        return None
    velocidade_ms = _float_dict(raw, "velocidade_ms", velocidade_kmh / 3.6)
    velocidade_media_voo_kmh = _float_dict(raw, "velocidade_media_voo_kmh", velocidade_kmh)
    velocidade_media_voo_ms = _float_dict(raw, "velocidade_media_voo_ms", velocidade_media_voo_kmh / 3.6)
    contato_s = _float_dict(raw, "contato_s")
    primeiro_toque_s = _float_dict(raw, "primeiro_toque_s", contato_s + _float_dict(raw, "tempo_voo_s"))
    tempo_voo_s = _float_dict(raw, "tempo_voo_s", max(0.0, primeiro_toque_s - contato_s))

    return ServeSpeedEvent(
        contato_s=contato_s,
        primeiro_toque_s=primeiro_toque_s,
        velocidade_ms=velocidade_ms,
        velocidade_kmh=velocidade_kmh,
        velocidade_media_voo_ms=velocidade_media_voo_ms,
        velocidade_media_voo_kmh=velocidade_media_voo_kmh,
        fator_radar=_float_dict(raw, "fator_radar", SERVE_RADAR_SPEED_FACTOR),
        distancia_m=_float_dict(raw, "distancia_m"),
        distancia_planta_m=_float_dict(raw, "distancia_planta_m"),
        distancia_reta_3d_m=_float_dict(raw, "distancia_reta_3d_m"),
        distancia_segmentada_m=_float_dict(raw, "distancia_segmentada_m"),
        altura_contato_m=_float_dict(raw, "altura_contato_m"),
        altura_primeiro_toque_m=_float_dict(raw, "altura_primeiro_toque_m", TENNIS_BALL_RADIUS_M),
        tempo_voo_s=tempo_voo_s,
        tempo_voo_bruto_s=_float_dict(raw, "tempo_voo_bruto_s", tempo_voo_s),
        fps_calculo=_float_dict(raw, "fps_calculo", _fps_para_calculo_saque(calibracao)),
        amostras_usadas=_int_dict(raw, "amostras_usadas", 2),
        metodo=str(raw.get("metodo") or "preview_travado"),
        confianca=max(0.0, min(1.0, _float_dict(raw, "confianca", 0.9))),
    )


def _calcular_velocidade_saque(
    calibracao: dict | None,
    transformacao_video_para_quadra: tuple[str, np.ndarray] | None,
    fps_original: float | None = None,
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
        contato_s_bruto = float(contato.get("time_s"))
        primeiro_toque_s_bruto = float(primeiro_toque.get("time_s"))
    except (TypeError, ValueError):
        return None
    if (
        not math.isfinite(contato_s_bruto)
        or not math.isfinite(primeiro_toque_s_bruto)
        or primeiro_toque_s_bruto <= contato_s_bruto
    ):
        return None

    fps_calculo = _fps_para_calculo_saque(calibracao, fps_original)
    contato_s = _quantizar_tempo_frame(contato_s_bruto, fps_calculo)
    primeiro_toque_s = _quantizar_tempo_frame(primeiro_toque_s_bruto, fps_calculo)
    if primeiro_toque_s <= contato_s:
        frames_voo = max(1, int(round((primeiro_toque_s_bruto - contato_s_bruto) * fps_calculo)))
        primeiro_toque_s = contato_s + frames_voo / fps_calculo
    margem_frame_s = 0.51 / max(fps_calculo, 1.0)

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
            tempo = _quantizar_tempo_frame(float(mark.get("time_s")), fps_calculo)
        except (TypeError, ValueError):
            continue
        if tempo < contato_s - margem_frame_s or tempo > primeiro_toque_s + margem_frame_s:
            continue
        tempo = max(contato_s, min(primeiro_toque_s, tempo))
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
    dt_bruto = primeiro_toque_s_bruto - contato_s_bruto
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
        tempo_voo_bruto_s=dt_bruto,
        fps_calculo=fps_calculo,
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
    if fator > 1.30:
        # Compatibilidade com calibracoes corrompidas/acima do teto esperado.
        fator = SERVE_RADAR_SPEED_FACTOR
    if fator < SERVE_RADAR_SPEED_FACTOR:
        fator = SERVE_RADAR_SPEED_FACTOR

    # A medicao oficial de TV costuma ser a velocidade inicial/radar logo apos
    # a raquete. Este fator e mantido como calibracao empirica, mas sem piso
    # alto para nao superestimar saques ja medidos com pontos precisos.
    return max(1.0, min(1.30, fator))


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

    if bola is not None:
        center = (int(bola.x * sx), int(bola.y * sy))
        raio_base = max(5, int(bola.radius * (sx + sy) / 2))
    elif ball_track:
        ultimo_x, ultimo_y = ball_track[-1]
        center = (int(ultimo_x * sx), int(ultimo_y * sy))
        raio_base = max(5, int(min(output_size) * 0.006))
    else:
        center = None

    if center is not None:
        raio_marcacao = max(8, raio_base + 4)
        cv2.circle(canvas, center, raio_marcacao + 1, (0, 0, 0), 1)
        cv2.circle(canvas, center, raio_marcacao, (0, 255, 255), 2)

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
    p1 = [a for q in quadros for a in q.atletas if a.id_atleta == "P1"]
    p2 = [a for q in quadros for a in q.atletas if a.id_atleta == "P2"]
    net_y = COURT_LENGTH_M / 2
    p1_depth = _media_segura(abs(a.centro_quadra_m.y - net_y) for a in p1)
    p2_depth = _media_segura(abs(a.centro_quadra_m.y - net_y) for a in p2)
    p1_cov = _amplitude_segura(a.centro_quadra_m.x for a in p1)
    p2_cov = _amplitude_segura(a.centro_quadra_m.x for a in p2)
    if p1 and not p2:
        p2_depth = p1_depth
        p2_cov = p1_cov
    elif p2 and not p1:
        p1_depth = p2_depth
        p1_cov = p2_cov
    coverage_ratio = (p1_cov / p2_cov) if p1_cov > 0 and p2_cov > 0 else 1.0
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
        razao_cobertura=round(coverage_ratio, 2),
        velocidade_media_bola_ms=round(avg_ball_speed, 2),
        estabilidade_tronco_p1=round(_media_segura(a.indice_estabilidade for a in p1), 2),
        estabilidade_tronco_p2=round(_media_segura(a.indice_estabilidade for a in p2), 2),
        simetria_apoio_p1=round(_media_segura(a.indice_simetria for a in p1), 2),
        simetria_apoio_p2=round(_media_segura(a.indice_simetria for a in p2), 2),
        amplitude_tronco_max_graus=0.0,
        qualidade_tracking=round(fmean(confiancas), 2) if confiancas else 0.0,
        quadros_utilizados=len(quadros),
    )


def _media_segura(valores: Iterable[float], default: float = 0.0) -> float:
    validos: list[float] = []
    for valor in valores:
        try:
            convertido = float(valor)
        except (TypeError, ValueError):
            continue
        if math.isfinite(convertido):
            validos.append(convertido)
    return fmean(validos) if validos else default


def _amplitude_segura(valores: Iterable[float]) -> float:
    validos: list[float] = []
    for valor in valores:
        try:
            convertido = float(valor)
        except (TypeError, ValueError):
            continue
        if math.isfinite(convertido):
            validos.append(convertido)
    if len(validos) < 2:
        return 0.0
    return max(validos) - min(validos)


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
    ultimo_p1: AtletaQuadro | None = None
    ultimo_p2: AtletaQuadro | None = None
    for quadro in quadros:
        p1 = next((a for a in quadro.atletas if a.id_atleta == "P1"), None)
        p2 = next((a for a in quadro.atletas if a.id_atleta == "P2"), None)
        if p1 is not None:
            ultimo_p1 = p1
        if p2 is not None:
            ultimo_p2 = p2
        p1 = p1 or ultimo_p1
        p2 = p2 or ultimo_p2
        if p1 is None or p2 is None:
            continue
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
    auto_projetado = bool(raw.get("auto_projected")) or str(raw.get("source") or "") == "projection_baseline_center"
    limite_min = -0.25 if auto_projetado else 0.0
    limite_max = 1.25 if auto_projetado else 1.0
    if (
        not math.isfinite(x)
        or not math.isfinite(y)
        or x < limite_min
        or x > limite_max
        or y < limite_min
        or y > limite_max
    ):
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


def _bool_env(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}
