from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2

from backend.app.servicos.visao_video_real import (
    DetectionBox,
    _detectar_jogadores,
    _load_yolo_model,
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


def gerar_video_player_focus(
    caminho_video: Path,
    pasta_saida: Path,
    config: dict,
    progress_callback: ProgressCallback | None = None,
) -> PlayerFocusResult:
    """Renderiza um recorte vertical limpo mantendo o jogador escolhido no centro."""

    aspect = str(config.get("aspect_ratio") or "9:16")
    if aspect not in ASPECT_RATIOS:
        raise ValueError("Proporcao invalida. Use 9:20, 9:16 ou 4:5.")

    focus_player = str(config.get("focus_player") or "p1").lower()
    players = config.get("players")
    if not isinstance(players, dict):
        raise ValueError("Informe os pontos dos jogadores.")
    focus_anchor = _anchor_player_px(players.get(focus_player), None)
    if focus_anchor is None:
        raise ValueError("Marque o jogador que deve ficar em foco.")

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

    focus_anchor = _anchor_player_px(players.get(focus_player), (width, height))
    if focus_anchor is None:
        cap.release()
        raise ValueError("Ponto do jogador em foco invalido.")

    zoom_factor = max(1.0, min(2.5, float(config.get("zoom_factor") or 1.35)))
    crop_w, crop_h = _crop_size(width, height, aspect, zoom_factor)
    output_size = _output_size(aspect, crop_w, crop_h)
    if output_size[0] <= 0 or output_size[1] <= 0:
        cap.release()
        raise RuntimeError("Nao foi possivel calcular o recorte vertical.")

    pasta_saida.mkdir(parents=True, exist_ok=True)
    stem = caminho_video.stem[:70]
    video_temporario = pasta_saida / f"{stem}_player_focus_raw.mp4"
    zoom_label = str(round(zoom_factor, 2)).replace(".", "p")
    video_saida = pasta_saida / f"{stem}_player_focus_{aspect.replace(':', 'x')}_{zoom_label}x.mp4"
    writer = cv2.VideoWriter(
        str(video_temporario),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        output_size,
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Nao foi possivel iniciar a renderizacao do Player Focus.")

    modelo_yolo = _load_yolo_model()
    detect_every = max(1, _int_env("TENNIS_XRAY_PLAYER_FOCUS_DETECT_EVERY", 2))
    smoothing = max(0.02, min(0.85, _float_env("TENNIS_XRAY_PLAYER_FOCUS_SMOOTHING", 0.14)))
    deadzone_px = max(2.0, min(crop_w, crop_h) * max(0.0, _float_env("TENNIS_XRAY_PLAYER_FOCUS_DEADZONE", 0.035)))
    max_step_px = max(
        4.0,
        math.hypot(crop_w, crop_h)
        * max(0.1, _float_env("TENNIS_XRAY_PLAYER_FOCUS_MAX_SPEED", 1.15))
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
    estado: FocusTrackState | None = None
    ultimo_detectado: DetectionBox | None = None
    total = max(total_frames, 1)

    try:
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_idx == 0 or frame_idx % detect_every == 0 or estado is None:
                detections = _detectar_jogadores(frame, modelo_yolo)
                escolhido = _selecionar_box_foco(detections, estado, focus_anchor, (width, height))
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
                    estado = FocusTrackState(
                        x=center[0],
                        y=center[1],
                        width=escolhido.width,
                        height=escolhido.height,
                        confidence=escolhido.confidence,
                        misses=0,
                    )
                    ultimo_detectado = escolhido
                elif estado is not None:
                    estado.misses += 1
                    target_center_x, target_center_y = _limitar_centro_crop(
                        estado.x,
                        estado.y,
                        width,
                        height,
                        crop_w,
                        crop_h,
                    )
                elif ultimo_detectado is not None:
                    target_center_x, target_center_y = _limitar_centro_crop(
                        ultimo_detectado.center[0],
                        ultimo_detectado.center[1],
                        width,
                        height,
                        crop_w,
                        crop_h,
                    )

            smooth_x, smooth_y = _suavizar_centro_crop(
                smooth_x,
                smooth_y,
                target_center_x,
                target_center_y,
                smoothing,
                deadzone_px,
                max_step_px,
            )
            crop = _recortar_frame(frame, smooth_x, smooth_y, crop_w, crop_h)
            writer.write(_preparar_frame_saida(crop, output_size))

            if frame_idx % 12 == 0:
                progresso = 100.0 * frame_idx / total
                if _notify(progress_callback, progresso, f"Centralizando jogador em foco ({frame_idx + 1}/{total})") is False:
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
            "player_detector": "yolo_person" if modelo_yolo is not None else "opencv_fallback",
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


def _preparar_frame_saida(frame, output_size: tuple[int, int]):
    output_w, output_h = output_size
    if frame.shape[1] != output_w or frame.shape[0] != output_h:
        frame = cv2.resize(frame, (output_w, output_h), interpolation=cv2.INTER_LANCZOS4)

    if _int_env("TENNIS_XRAY_PLAYER_FOCUS_POSTPROCESS", 1) <= 0:
        return frame

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(
        clipLimit=max(1.0, min(3.0, _float_env("TENNIS_XRAY_PLAYER_FOCUS_CLAHE_CLIP", 1.35))),
        tileGridSize=(8, 8),
    )
    l_channel = clahe.apply(l_channel)
    frame = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

    blur = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.15)
    amount = max(0.0, min(1.2, _float_env("TENNIS_XRAY_PLAYER_FOCUS_SHARPEN", 0.42)))
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
