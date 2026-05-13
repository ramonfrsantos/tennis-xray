from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2

from backend.app.servicos.visao_video_real import (
    BallDetection,
    DetectionBox,
    _detectar_jogadores,
    _expandir_trajetoria_global_para_indices_render,
    _load_yolo_model,
    _precalcular_trajetoria_bola_global,
    _reduzir_indices_trajetoria_global,
    _trajetoria_global_render_confiavel,
    _transcodificar_para_h264,
    _validar_video_saida,
)

ProgressCallback = Callable[[float, str], bool | None]


ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "9:20": (9, 20),
    "9:16": (9, 16),
    "4:5": (4, 5),
}


@dataclass
class PlayerFocusResult:
    video_path: Path
    metadata: dict


@dataclass
class FocusTrackState:
    x: float
    y: float
    width: float
    height: float
    confidence: float
    misses: int = 0


@dataclass
class FocusBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass
class FocusSegment:
    start_frame: int
    end_frame: int
    focus: str


@dataclass
class BallFocusCameraState:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    last_frame: int = 0
    misses: int = 0
    pending: list[tuple[int, float, float]] = field(default_factory=list)
    status: str = "confirmed"
    accepted: int = 0
    predicted: int = 0
    held: int = 0
    rejected_jump: int = 0
    rejected_bounds: int = 0
    reacquired: int = 0


def gerar_video_player_focus(
    caminho_video: Path,
    pasta_saida: Path,
    config: dict,
    progress_callback: ProgressCallback | None = None,
) -> PlayerFocusResult:
    """Renderiza um recorte vertical limpo mantendo o alvo escolhido no centro."""

    aspect = str(config.get("aspect_ratio") or "9:16")
    if aspect not in ASPECT_RATIOS:
        raise ValueError("Proporcao invalida. Use 9:20, 9:16 ou 4:5.")

    focus_player = _normalizar_foco(config.get("focus_player"))
    players = config.get("players") if isinstance(config.get("players"), dict) else {}

    cap = cv2.VideoCapture(str(caminho_video))
    if not cap.isOpened():
        raise RuntimeError("Nao foi possivel abrir o video original.")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Video sem dimensoes validas.")

    focus_segments = _normalizar_segmentos_foco(config.get("focus_segments"), focus_player, total_frames)
    usa_bolinha = any(segmento.focus == "ball" for segmento in focus_segments)
    usa_jogadores = any(segmento.focus in {"p1", "p2"} for segmento in focus_segments)
    focus_anchors = {
        chave: _anchor_player_px(players.get(chave), (width, height))
        for chave in ("p1", "p2")
    }
    if usa_jogadores:
        focos_necessarios = {segmento.focus for segmento in focus_segments if segmento.focus in {"p1", "p2"}}
        for foco in sorted(focos_necessarios):
            if focus_anchors.get(foco) is None:
                cap.release()
                raise ValueError(f"Marque o {foco.upper()} para usar esse foco na timeline.")
    focus_anchor = focus_anchors.get(focus_segments[0].focus) or (width / 2, height / 2)

    zoom_factor = max(1.0, min(2.5, float(config.get("zoom_factor") or 1.35)))
    crop_w, crop_h = _crop_size(width, height, aspect, zoom_factor)
    output_size = _output_size(aspect, crop_w, crop_h)
    if output_size[0] <= 0 or output_size[1] <= 0:
        cap.release()
        raise RuntimeError("Nao foi possivel calcular o recorte vertical.")
    manual_targets = _normalizar_alvos_manuais(config.get("manual_targets"), width, height)
    image_adjustments = _normalizar_ajustes_imagem(config.get("image_adjustments"))

    pasta_saida.mkdir(parents=True, exist_ok=True)
    stem = caminho_video.stem[:70]
    focos_timeline = {segmento.focus for segmento in focus_segments}
    focus_label = "mixed_focus" if len(focos_timeline) > 1 or manual_targets else ("ball_focus" if "ball" in focos_timeline else "player_focus")
    video_temporario = pasta_saida / f"{stem}_{focus_label}_raw.mp4"
    zoom_label = str(round(zoom_factor, 2)).replace(".", "p")
    video_saida = pasta_saida / f"{stem}_{focus_label}_{aspect.replace(':', 'x')}_{zoom_label}x.mp4"
    writer = cv2.VideoWriter(
        str(video_temporario),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        output_size,
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Nao foi possivel iniciar a renderizacao do Player Focus.")

    modelo_yolo = _load_yolo_model() if usa_jogadores else None
    trajetoria_bolinha: dict[int, BallDetection] = {}
    ball_focus_bounds: FocusBounds | None = None
    ball_focus_state: BallFocusCameraState | None = None
    calibracao_bolinha = config.get("calibracao") if usa_bolinha and isinstance(config.get("calibracao"), dict) else None
    if usa_bolinha:
        try:
            trajetoria_bolinha = _resolver_trajetoria_bolinha_focus(
                caminho_video=caminho_video,
                total_frames=total_frames,
                fps=fps,
                calibracao=calibracao_bolinha,
                frame_shape=(height, width, 3),
                progress_callback=progress_callback,
            )
        except Exception:
            cap.release()
            writer.release()
            raise
        if not trajetoria_bolinha:
            cap.release()
            writer.release()
            raise RuntimeError("Nao foi possivel localizar a bolinha para centralizar o video vertical.")
        ball_focus_bounds = _bounds_foco_bolinha(calibracao_bolinha, width, height)
        primeiro_frame = min(trajetoria_bolinha)
        primeira_bola = trajetoria_bolinha[primeiro_frame]
        primeiro_x, primeiro_y = _limitar_alvo_foco_bolinha(
            primeira_bola.x,
            primeira_bola.y,
            ball_focus_bounds,
        )
        focus_anchor = (primeiro_x, primeiro_y)
        ball_focus_state = BallFocusCameraState(
            x=primeiro_x,
            y=primeiro_y,
            last_frame=int(primeiro_frame),
            accepted=1,
        )

    detect_every = max(1, _int_env("TENNIS_XRAY_PLAYER_FOCUS_DETECT_EVERY", 2))
    smoothing_padrao = 0.22 if usa_bolinha else 0.14
    deadzone_padrao = 0.014 if usa_bolinha else 0.035
    velocidade_padrao = 2.65 if usa_bolinha else 1.15
    smoothing = max(0.02, min(0.85, _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_SMOOTHING" if usa_bolinha else "TENNIS_XRAY_PLAYER_FOCUS_SMOOTHING", smoothing_padrao)))
    deadzone_px = max(1.0, min(crop_w, crop_h) * max(0.0, _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_DEADZONE" if usa_bolinha else "TENNIS_XRAY_PLAYER_FOCUS_DEADZONE", deadzone_padrao)))
    max_step_px = max(
        4.0,
        math.hypot(crop_w, crop_h)
        * max(0.1, _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_MAX_SPEED" if usa_bolinha else "TENNIS_XRAY_PLAYER_FOCUS_MAX_SPEED", velocidade_padrao))
        / max(fps, 1.0),
    )
    target_center_x, target_center_y = focus_anchor
    target_center_x, target_center_y = _limitar_centro_crop(
        target_center_x,
        target_center_y,
        width,
        height,
        crop_w,
        crop_h,
    )
    smooth_x, smooth_y = target_center_x, target_center_y
    estados_jogadores: dict[str, FocusTrackState] = {}
    ultimos_detectados: dict[str, DetectionBox] = {}
    total = max(total_frames, 1)

    try:
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            foco_frame = _foco_para_frame(frame_idx, focus_segments, focus_player)
            alvo_manual = _alvo_manual_para_frame(manual_targets, frame_idx)
            alvo_manual_ativo = alvo_manual is not None
            if alvo_manual_ativo:
                target_center_x, target_center_y = _limitar_centro_crop(
                    alvo_manual[0],
                    alvo_manual[1],
                    width,
                    height,
                    crop_w,
                    crop_h,
                )
            elif foco_frame == "ball":
                bola_frame = trajetoria_bolinha.get(int(frame_idx))
                if ball_focus_state is not None:
                    target_center_x, target_center_y = _atualizar_alvo_foco_bolinha(
                        estado=ball_focus_state,
                        bola=bola_frame,
                        frame_idx=int(frame_idx),
                        fps=fps,
                        frame_w=width,
                        frame_h=height,
                        bounds=ball_focus_bounds,
                    )
                    target_center_x, target_center_y = _limitar_centro_crop(
                        target_center_x,
                        target_center_y,
                        width,
                        height,
                        crop_w,
                        crop_h,
                    )
            elif foco_frame in {"p1", "p2"}:
                estado_jogador = estados_jogadores.get(foco_frame)
                ultimo_jogador = ultimos_detectados.get(foco_frame)
                if frame_idx == 0 or frame_idx % detect_every == 0 or estado_jogador is None:
                    detections = _detectar_jogadores(frame, modelo_yolo)
                    anchor_jogador = focus_anchors.get(foco_frame) or focus_anchor
                    escolhido = _selecionar_box_foco(detections, estado_jogador, anchor_jogador, (width, height))
                    if escolhido is not None:
                        center = escolhido.center
                        target_center_x, target_center_y = _limitar_centro_crop(
                            center[0],
                            center[1],
                            width,
                            height,
                            crop_w,
                            crop_h,
                        )
                        estados_jogadores[foco_frame] = FocusTrackState(
                            x=center[0],
                            y=center[1],
                            width=escolhido.width,
                            height=escolhido.height,
                            confidence=escolhido.confidence,
                            misses=0,
                        )
                        ultimos_detectados[foco_frame] = escolhido
                    elif estado_jogador is not None:
                        estado_jogador.misses += 1
                        target_center_x, target_center_y = _limitar_centro_crop(
                            estado_jogador.x,
                            estado_jogador.y,
                            width,
                            height,
                            crop_w,
                            crop_h,
                        )
                    elif ultimo_jogador is not None:
                        target_center_x, target_center_y = _limitar_centro_crop(
                            ultimo_jogador.center[0],
                            ultimo_jogador.center[1],
                            width,
                            height,
                            crop_w,
                            crop_h,
                        )

            smoothing_frame = (
                _smoothing_foco_bolinha(smoothing, ball_focus_state.status)
                if foco_frame == "ball" and ball_focus_state is not None and not alvo_manual_ativo
                else smoothing
            )
            smooth_x, smooth_y = _suavizar_centro_crop(
                smooth_x,
                smooth_y,
                target_center_x,
                target_center_y,
                smoothing_frame,
                deadzone_px,
                max_step_px,
            )
            crop = _recortar_frame(frame, smooth_x, smooth_y, crop_w, crop_h)
            writer.write(_preparar_frame_saida(crop, output_size, image_adjustments))

            if frame_idx % 12 == 0:
                if usa_bolinha:
                    progresso = 35.0 + 65.0 * frame_idx / total
                    mensagem = f"Centralizando timeline vertical ({frame_idx + 1}/{total})"
                else:
                    progresso = 100.0 * frame_idx / total
                    mensagem = f"Centralizando timeline vertical ({frame_idx + 1}/{total})"
                if _notify(progress_callback, progresso, mensagem) is False:
                    raise RuntimeError("Renderizacao Player Focus cancelada.")
            frame_idx += 1
    finally:
        cap.release()
        writer.release()

    _validar_video_saida(video_temporario, "video temporario Player Focus")
    codec_saida = _transcodificar_player_focus_para_h264(video_temporario, video_saida)
    _validar_video_saida(video_saida, "video Player Focus")

    try:
        video_temporario.unlink(missing_ok=True)
    except OSError:
        pass

    _notify(progress_callback, 100.0, "Player Focus pronto para download.")
    return PlayerFocusResult(
        video_path=video_saida,
        metadata={
            "aspect_ratio": aspect,
            "focus_player": focus_player,
            "zoom_factor": round(zoom_factor, 3),
            "fps": round(fps, 3),
            "frames_video": total_frames,
            "source_width": width,
            "source_height": height,
            "crop_width": crop_w,
            "crop_height": crop_h,
            "output_width": output_size[0],
            "output_height": output_size[1],
            "codec_saida": codec_saida,
            "player_detector": "yolo_person" if modelo_yolo is not None else ("nao_usado" if not usa_jogadores else "opencv_fallback"),
            "ball_focus_points": len(trajetoria_bolinha),
            "ball_focus_filter": _metadata_filtro_bolinha(ball_focus_state),
            "focus_segments": [segmento.__dict__ for segmento in focus_segments],
            "manual_targets": len(manual_targets),
            "image_adjustments": image_adjustments,
            "quality_profile": {
                "resize": "lanczos4_virtual_upscale",
                "contrast": "clahe_luma",
                "sharpen": "unsharp_mask",
                "target_height": _int_env("TENNIS_XRAY_PLAYER_FOCUS_OUTPUT_HEIGHT", 1920),
                "h264_crf": _int_env("TENNIS_XRAY_PLAYER_FOCUS_H264_CRF", 14),
            },
            "stabilization": {
                "smoothing": round(smoothing, 4),
                "deadzone_px": round(deadzone_px, 2),
                "max_step_px": round(max_step_px, 2),
            },
        },
    )


def _normalizar_foco(valor: object) -> str:
    foco = str(valor or "p1").strip().lower()
    if foco in {"bola", "bolinha", "ball", "tennis_ball"}:
        return "ball"
    if foco in {"p2", "j2", "jogador2", "jogador_2"}:
        return "p2"
    return "p1"


def _normalizar_segmentos_foco(raw: object, fallback: str, total_frames: int) -> list[FocusSegment]:
    total = max(1, int(total_frames or 1))
    segmentos: list[FocusSegment] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            foco = _normalizar_foco(item.get("focus") or item.get("focus_player") or fallback)
            try:
                start = int(round(float(item.get("start_frame", 0))))
                end_raw = item.get("end_frame", total - 1)
                end = total - 1 if end_raw is None or end_raw == "" else int(round(float(end_raw)))
            except (TypeError, ValueError):
                continue
            start = max(0, min(total - 1, start))
            end = max(0, min(total - 1, end))
            if end < start:
                start, end = end, start
            segmentos.append(FocusSegment(start, end, foco))
    if not segmentos:
        return [FocusSegment(0, total - 1, fallback)]
    segmentos.sort(key=lambda item: (item.start_frame, item.end_frame))
    return segmentos


def _foco_para_frame(frame_idx: int, segmentos: list[FocusSegment], fallback: str) -> str:
    escolhido = fallback
    for segmento in segmentos:
        if segmento.start_frame <= frame_idx <= segmento.end_frame:
            escolhido = segmento.focus
    return escolhido


def _normalizar_alvos_manuais(raw: object, frame_w: int, frame_h: int) -> dict[int, tuple[float, float]]:
    alvos: dict[int, tuple[float, float]] = {}
    itens = raw.values() if isinstance(raw, dict) else raw
    if not isinstance(itens, list) and not hasattr(itens, "__iter__"):
        return alvos
    for item in itens:
        if not isinstance(item, dict):
            continue
        try:
            frame_idx = int(round(float(item.get("frame_index", item.get("frame", 0)))))
            x = float(item.get("x"))
            y = float(item.get("y"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(x) or not math.isfinite(y) or frame_idx < 0:
            continue
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            x *= frame_w
            y *= frame_h
        alvos[frame_idx] = (
            max(0.0, min(float(frame_w), x)),
            max(0.0, min(float(frame_h), y)),
        )
    return alvos


def _alvo_manual_para_frame(alvos: dict[int, tuple[float, float]], frame_idx: int) -> tuple[float, float] | None:
    if not alvos:
        return None
    frame_idx = int(frame_idx)
    if frame_idx in alvos:
        return alvos[frame_idx]
    max_gap = _int_env("TENNIS_XRAY_PLAYER_FOCUS_MANUAL_INTERP_MAX_GAP", 90)
    anteriores = [frame for frame in alvos if frame < frame_idx]
    posteriores = [frame for frame in alvos if frame > frame_idx]
    if not anteriores or not posteriores:
        return None
    frame_a = max(anteriores)
    frame_b = min(posteriores)
    if frame_b - frame_a > max_gap:
        return None
    ax, ay = alvos[frame_a]
    bx, by = alvos[frame_b]
    t = (frame_idx - frame_a) / max(frame_b - frame_a, 1)
    return ax + (bx - ax) * t, ay + (by - ay) * t


def _normalizar_ajustes_imagem(raw: object) -> dict[str, float]:
    dados = raw if isinstance(raw, dict) else {}

    def valor(nome: str, padrao: float, minimo: float, maximo: float) -> float:
        try:
            numero = float(dados.get(nome, padrao))
        except (TypeError, ValueError):
            numero = padrao
        return max(minimo, min(maximo, numero))

    return {
        "sharpness": valor("sharpness", _float_env("TENNIS_XRAY_PLAYER_FOCUS_SHARPEN", 0.42), 0.0, 1.2),
        "definition": valor("definition", _float_env("TENNIS_XRAY_PLAYER_FOCUS_CLAHE_CLIP", 1.35), 0.0, 3.0),
        "brightness": valor("brightness", 0.0, -60.0, 60.0),
        "saturation": valor("saturation", 1.0, 0.0, 2.0),
    }


def _resolver_trajetoria_bolinha_focus(
    caminho_video: Path,
    total_frames: int,
    fps: float,
    calibracao: dict | None,
    frame_shape: tuple[int, int, int],
    progress_callback: ProgressCallback | None = None,
) -> dict[int, BallDetection]:
    if total_frames <= 0:
        return {}

    indices_render = list(range(total_frames))
    indices_trajetoria = _reduzir_indices_trajetoria_global(indices_render, fps)
    _notify(progress_callback, 1.0, f"Localizando trajetoria da bolinha (0/{len(indices_trajetoria)})")
    trajetoria_sparse = _precalcular_trajetoria_bola_global(
        caminho_video=caminho_video,
        indices=indices_trajetoria,
        fps_original=fps,
        calibracao=calibracao,
        progress_callback=progress_callback,
        progress_start=1.0,
        progress_end=32.0,
    )
    trajetoria_render = _expandir_trajetoria_global_para_indices_render(
        trajetoria_sparse,
        indices_render,
        fps,
        calibracao=calibracao,
        frame_shape=frame_shape,
    )
    if not _trajetoria_global_render_confiavel(trajetoria_sparse, trajetoria_render):
        return {}
    _notify(progress_callback, 34.0, f"Trajetoria da bolinha pronta ({len(trajetoria_render)} pontos)")
    return trajetoria_render


def _atualizar_alvo_foco_bolinha(
    estado: BallFocusCameraState,
    bola: BallDetection | None,
    frame_idx: int,
    fps: float,
    frame_w: int,
    frame_h: int,
    bounds: FocusBounds | None,
) -> tuple[float, float]:
    if bola is None:
        return _prever_ou_segurar_foco_bolinha(estado, frame_idx, fps, bounds, "predicted")

    try:
        candidato_x = float(bola.x)
        candidato_y = float(bola.y)
    except (TypeError, ValueError):
        return _prever_ou_segurar_foco_bolinha(estado, frame_idx, fps, bounds, "predicted")
    if not math.isfinite(candidato_x) or not math.isfinite(candidato_y):
        return _prever_ou_segurar_foco_bolinha(estado, frame_idx, fps, bounds, "predicted")

    if bounds is not None and not _ponto_dentro_bounds_foco_bolinha(candidato_x, candidato_y, bounds):
        estado.rejected_bounds += 1
        estado.pending.clear()
        return _prever_ou_segurar_foco_bolinha(estado, frame_idx, fps, bounds, "held")

    candidato_x, candidato_y = _limitar_alvo_foco_bolinha(candidato_x, candidato_y, bounds)
    dt_frames = max(1, int(frame_idx) - int(estado.last_frame))
    dist = math.hypot(candidato_x - estado.x, candidato_y - estado.y)
    gate_salto = _gate_salto_foco_bolinha(frame_w, frame_h, fps, dt_frames)
    gate_reaquisicao = gate_salto * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_REACQUIRE_GATE_FACTOR", 0.58)
    precisa_confirmar = (
        dist > gate_salto
        or (
            estado.misses >= _int_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_CONFIRM_AFTER_MISSES", 5)
            and dist > gate_reaquisicao
        )
    )

    if precisa_confirmar:
        estado.rejected_jump += 1
        confirmado = _registrar_reaquisicao_pendente_bolinha(
            estado,
            frame_idx,
            candidato_x,
            candidato_y,
            frame_w,
            frame_h,
            fps,
        )
        if not confirmado:
            return _prever_ou_segurar_foco_bolinha(estado, frame_idx, fps, bounds, "pending")
        return _aceitar_alvo_foco_bolinha(
            estado,
            candidato_x,
            candidato_y,
            frame_idx,
            fps,
            bounds,
            status="reacquired",
        )

    return _aceitar_alvo_foco_bolinha(
        estado,
        candidato_x,
        candidato_y,
        frame_idx,
        fps,
        bounds,
        status="confirmed",
    )


def _aceitar_alvo_foco_bolinha(
    estado: BallFocusCameraState,
    x: float,
    y: float,
    frame_idx: int,
    fps: float,
    bounds: FocusBounds | None,
    status: str,
) -> tuple[float, float]:
    dt_frames = max(1, int(frame_idx) - int(estado.last_frame))
    novo_vx = (x - estado.x) / dt_frames
    novo_vy = (y - estado.y) / dt_frames
    novo_vx, novo_vy = _limitar_velocidade_predicao_bolinha(novo_vx, novo_vy, fps)
    estado.vx = estado.vx * 0.35 + novo_vx * 0.65
    estado.vy = estado.vy * 0.35 + novo_vy * 0.65
    estado.x, estado.y = _limitar_alvo_foco_bolinha(x, y, bounds)
    estado.last_frame = int(frame_idx)
    estado.misses = 0
    estado.pending.clear()
    estado.status = status
    estado.accepted += 1
    if status == "reacquired":
        estado.reacquired += 1
    return estado.x, estado.y


def _prever_ou_segurar_foco_bolinha(
    estado: BallFocusCameraState,
    frame_idx: int,
    fps: float,
    bounds: FocusBounds | None,
    status: str,
) -> tuple[float, float]:
    estado.misses += 1
    if status == "held":
        estado.held += 1
        estado.status = "held"
        estado.last_frame = int(frame_idx)
        return estado.x, estado.y
    max_pred = max(1, int(round(max(fps, 1.0) * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_PREDICT_S", 0.45))))
    if estado.misses <= max_pred:
        dt_frames = max(1, int(frame_idx) - int(estado.last_frame))
        vx, vy = _limitar_velocidade_predicao_bolinha(estado.vx, estado.vy, fps)
        estado.x, estado.y = _limitar_alvo_foco_bolinha(
            estado.x + vx * dt_frames,
            estado.y + vy * dt_frames,
            bounds,
        )
        estado.vx, estado.vy = vx * 0.94, vy * 0.94
        estado.predicted += 1
        estado.status = status if status == "pending" else "predicted"
    else:
        estado.held += 1
        estado.status = "held"
    estado.last_frame = int(frame_idx)
    return estado.x, estado.y


def _registrar_reaquisicao_pendente_bolinha(
    estado: BallFocusCameraState,
    frame_idx: int,
    x: float,
    y: float,
    frame_w: int,
    frame_h: int,
    fps: float,
) -> bool:
    max_intervalo = max(1, _int_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_PENDING_MAX_INTERVAL", 8))
    if estado.pending:
        ultimo_frame, ultimo_x, ultimo_y = estado.pending[-1]
        dt = max(1, int(frame_idx) - int(ultimo_frame))
        gate = _gate_salto_foco_bolinha(frame_w, frame_h, fps, dt) * 0.85
        if int(frame_idx) - int(ultimo_frame) > max_intervalo or math.hypot(x - ultimo_x, y - ultimo_y) > gate:
            estado.pending.clear()
    estado.pending.append((int(frame_idx), float(x), float(y)))
    max_pendentes = max(2, _int_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_REACQUIRE_CONFIRM_FRAMES", 3))
    estado.pending = estado.pending[-max_pendentes:]
    return len(estado.pending) >= max_pendentes


def _gate_salto_foco_bolinha(frame_w: int, frame_h: int, fps: float, dt_frames: int) -> float:
    min_dim = max(1.0, float(min(frame_w, frame_h)))
    dt_s = max(1.0 / max(fps, 1.0), float(dt_frames) / max(fps, 1.0))
    base = min_dim * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_JUMP_BASE", 0.045)
    por_segundo = min_dim * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_JUMP_PER_S", 1.10) * dt_s
    return max(34.0, base + por_segundo)


def _limitar_velocidade_predicao_bolinha(vx: float, vy: float, fps: float) -> tuple[float, float]:
    limite_por_frame = max(6.0, _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_PREDICT_MAX_PX_S", 1250.0) / max(fps, 1.0))
    velocidade = math.hypot(vx, vy)
    if velocidade <= limite_por_frame:
        return vx, vy
    escala = limite_por_frame / max(velocidade, 1e-6)
    return vx * escala, vy * escala


def _smoothing_foco_bolinha(base: float, status: str) -> float:
    if status == "confirmed":
        return base
    if status == "predicted":
        return max(0.02, base * 0.62)
    if status == "reacquired":
        return max(0.02, base * 0.48)
    if status == "pending":
        return max(0.02, base * 0.36)
    return max(0.02, base * 0.30)


def _bounds_foco_bolinha(calibracao: dict | None, frame_w: int, frame_h: int) -> FocusBounds | None:
    pontos: list[tuple[float, float]] = []
    court_points = calibracao.get("court_points") if isinstance(calibracao, dict) else None
    if isinstance(court_points, dict):
        for raw in court_points.values():
            ponto = _ponto_calibracao_px(raw, frame_w, frame_h)
            if ponto is not None:
                pontos.append(ponto)
    if len(pontos) < 3:
        return None
    xs = [ponto[0] for ponto in pontos]
    ys = [ponto[1] for ponto in pontos]
    margem_x = float(frame_w) * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_COURT_MARGIN_X", 0.13)
    margem_y = float(frame_h) * _float_env("TENNIS_XRAY_PLAYER_FOCUS_BALL_COURT_MARGIN_Y", 0.16)
    return FocusBounds(
        min_x=max(0.0, min(xs) - margem_x),
        max_x=min(float(frame_w), max(xs) + margem_x),
        min_y=max(0.0, min(ys) - margem_y),
        max_y=min(float(frame_h), max(ys) + margem_y),
    )


def _ponto_calibracao_px(raw: object, frame_w: int, frame_h: int) -> tuple[float, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x"))
        y = float(raw.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
        return x * frame_w, y * frame_h
    return x, y


def _ponto_dentro_bounds_foco_bolinha(x: float, y: float, bounds: FocusBounds) -> bool:
    return bounds.min_x <= x <= bounds.max_x and bounds.min_y <= y <= bounds.max_y


def _limitar_alvo_foco_bolinha(x: float, y: float, bounds: FocusBounds | None) -> tuple[float, float]:
    if bounds is None:
        return x, y
    return (
        max(bounds.min_x, min(bounds.max_x, x)),
        max(bounds.min_y, min(bounds.max_y, y)),
    )


def _metadata_filtro_bolinha(estado: BallFocusCameraState | None) -> dict | None:
    if estado is None:
        return None
    return {
        "accepted": estado.accepted,
        "predicted": estado.predicted,
        "held": estado.held,
        "rejected_jump": estado.rejected_jump,
        "rejected_bounds": estado.rejected_bounds,
        "reacquired": estado.reacquired,
    }


def _anchor_player_px(raw: object, frame_size: tuple[int, int] | None) -> tuple[float, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x"))
        y = float(raw.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    if frame_size is None:
        return (x, y)
    width, height = frame_size
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
        return (x * width, y * height)
    return (x, y)


def _crop_size(width: int, height: int, aspect: str, zoom_factor: float = 1.0) -> tuple[int, int]:
    rw, rh = ASPECT_RATIOS[aspect]
    ratio = rw / rh
    crop_h = height
    crop_w = int(round(crop_h * ratio))
    if crop_w > width:
        crop_w = width
        crop_h = int(round(crop_w / ratio))
    zoom = max(1.0, min(2.5, float(zoom_factor or 1.0)))
    crop_w = int(round(crop_w / zoom))
    crop_h = int(round(crop_h / zoom))
    return max(2, min(width, crop_w)), max(2, min(height, crop_h))


def _output_size(aspect: str, crop_w: int, crop_h: int) -> tuple[int, int]:
    rw, rh = ASPECT_RATIOS[aspect]
    target_h = max(720, min(3840, _int_env("TENNIS_XRAY_PLAYER_FOCUS_OUTPUT_HEIGHT", 1920)))
    target_w = int(round(target_h * rw / rh))
    if aspect == "4:5":
        target_w = max(target_w, _int_env("TENNIS_XRAY_PLAYER_FOCUS_OUTPUT_WIDTH_4_5", 1536))
        target_h = int(round(target_w * rh / rw))
    return (_even(max(crop_w, target_w)), _even(max(crop_h, target_h)))


def _recortar_frame(frame, center_x: float, center_y: float, crop_w: int, crop_h: int):
    h, w = frame.shape[:2]
    crop_w = min(max(2, crop_w), w)
    crop_h = min(max(2, crop_h), h)
    x1 = int(round(center_x - crop_w / 2))
    y1 = int(round(center_y - crop_h / 2))
    x1 = max(0, min(w - crop_w, x1))
    y1 = max(0, min(h - crop_h, y1))
    crop = frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
    if crop.shape[1] != crop_w or crop.shape[0] != crop_h:
        crop = cv2.resize(crop, (crop_w, crop_h), interpolation=cv2.INTER_AREA)
    return crop.copy()


def _preparar_frame_saida(frame, output_size: tuple[int, int], ajustes: dict[str, float] | None = None):
    output_w, output_h = output_size
    if frame.shape[1] != output_w or frame.shape[0] != output_h:
        frame = cv2.resize(frame, (output_w, output_h), interpolation=cv2.INTER_LANCZOS4)

    if _int_env("TENNIS_XRAY_PLAYER_FOCUS_POSTPROCESS", 1) <= 0:
        return frame

    ajustes = ajustes or _normalizar_ajustes_imagem(None)
    brilho = float(ajustes.get("brightness", 0.0))
    saturacao = float(ajustes.get("saturation", 1.0))
    if abs(brilho) > 0.01:
        frame = cv2.convertScaleAbs(frame, alpha=1.0, beta=brilho)
    if abs(saturacao - 1.0) > 0.01:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)
        s_channel = cv2.convertScaleAbs(s_channel, alpha=max(0.0, saturacao), beta=0)
        frame = cv2.cvtColor(cv2.merge((h_channel, s_channel, v_channel)), cv2.COLOR_HSV2BGR)

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    definition = max(0.0, min(3.0, float(ajustes.get("definition", 1.35))))
    if definition > 0.01:
        clahe = cv2.createCLAHE(
            clipLimit=max(1.0, definition),
            tileGridSize=(8, 8),
        )
        l_channel = clahe.apply(l_channel)
    frame = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

    blur = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.15)
    amount = max(0.0, min(1.2, float(ajustes.get("sharpness", 0.42))))
    return cv2.addWeighted(frame, 1.0 + amount, blur, -amount, 0)


def _transcodificar_player_focus_para_h264(video_origem: Path, video_destino: Path) -> str:
    crf_anterior = os.environ.get("TENNIS_XRAY_H264_CRF")
    preset_anterior = os.environ.get("TENNIS_XRAY_H264_PRESET")
    os.environ["TENNIS_XRAY_H264_CRF"] = str(
        max(0, min(51, _int_env("TENNIS_XRAY_PLAYER_FOCUS_H264_CRF", 14)))
    )
    os.environ["TENNIS_XRAY_H264_PRESET"] = os.getenv("TENNIS_XRAY_PLAYER_FOCUS_H264_PRESET", "slow")
    try:
        return _transcodificar_para_h264(video_origem, video_destino)
    finally:
        if crf_anterior is None:
            os.environ.pop("TENNIS_XRAY_H264_CRF", None)
        else:
            os.environ["TENNIS_XRAY_H264_CRF"] = crf_anterior
        if preset_anterior is None:
            os.environ.pop("TENNIS_XRAY_H264_PRESET", None)
        else:
            os.environ["TENNIS_XRAY_H264_PRESET"] = preset_anterior


def _limitar_centro_crop(
    center_x: float,
    center_y: float,
    frame_w: int,
    frame_h: int,
    crop_w: int,
    crop_h: int,
) -> tuple[float, float]:
    min_x = crop_w / 2
    max_x = max(min_x, frame_w - crop_w / 2)
    min_y = crop_h / 2
    max_y = max(min_y, frame_h - crop_h / 2)
    return (
        max(min_x, min(max_x, float(center_x))),
        max(min_y, min(max_y, float(center_y))),
    )


def _suavizar_centro_crop(
    smooth_x: float,
    smooth_y: float,
    target_x: float,
    target_y: float,
    smoothing: float,
    deadzone_px: float,
    max_step_px: float,
) -> tuple[float, float]:
    delta_x = target_x - smooth_x
    delta_y = target_y - smooth_y
    distancia = math.hypot(delta_x, delta_y)
    if distancia <= deadzone_px:
        return smooth_x, smooth_y

    fator_zona_morta = (distancia - deadzone_px) / max(distancia, 1e-6)
    passo_x = delta_x * fator_zona_morta * smoothing
    passo_y = delta_y * fator_zona_morta * smoothing
    passo_distancia = math.hypot(passo_x, passo_y)
    if passo_distancia > max_step_px:
        escala = max_step_px / max(passo_distancia, 1e-6)
        passo_x *= escala
        passo_y *= escala
    return smooth_x + passo_x, smooth_y + passo_y


def _selecionar_box_foco(
    boxes: list[DetectionBox],
    estado: FocusTrackState | None,
    anchor: tuple[float, float],
    frame_size: tuple[int, int],
) -> DetectionBox | None:
    if not boxes:
        return None

    width, height = frame_size
    diag = math.hypot(width, height)
    referencia = (estado.x, estado.y) if estado is not None else anchor

    def custo(box: DetectionBox) -> float:
        cx, cy = box.center
        dist_ref = math.hypot(cx - referencia[0], cy - referencia[1]) / max(diag, 1.0)
        dist_anchor = math.hypot(cx - anchor[0], cy - anchor[1]) / max(diag, 1.0)
        area = (box.width * box.height) / max(width * height, 1)
        area_penalty = 0.18 if area < 0.00004 else 0.0
        return (
            dist_ref * 1.40
            + dist_anchor * (0.36 if estado is not None else 0.95)
            + (1.0 - max(0.0, min(1.0, box.confidence))) * 0.18
            + area_penalty
        )

    return min(boxes, key=custo)


def _even(value: int) -> int:
    value = int(max(2, value))
    return value if value % 2 == 0 else value - 1


def _notify(callback: ProgressCallback | None, valor: float, mensagem: str) -> bool | None:
    if callback is None:
        return None
    return callback(round(float(valor), 2), mensagem)


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
