"""Visual TrackNet/heatmap trainer for Tennis X-Ray.

Usage:
    python train_tracknet_heatmap.py
    python train_tracknet_heatmap.py --video "C:\\path\\to\\video.mp4"
    python train_tracknet_heatmap.py --train-only --epochs 12

This script trains a TrackNet-style heatmap model, not a YOLO box detector.
Each positive click marks the ball center in the current frame. The script
saves a 3-frame temporal sample and trains a model that receives 9 channels
(RGB prev + RGB current + RGB next) and predicts a 1-channel ball heatmap.

Outputs:
    data/tracknet_heatmap_dataset/manifest.jsonl
    weights/tracknet_tennis.pth  - resume checkpoint
    weights/tracknet_tennis.pt   - TorchScript model used by the app
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parent
DATASET_DIR = ROOT_DIR / "data" / "tracknet_heatmap_dataset"
SAMPLES_DIR = DATASET_DIR / "samples"
MANIFEST_PATH = DATASET_DIR / "manifest.jsonl"
WEIGHTS_DIR = ROOT_DIR / "weights"
CHECKPOINT_PATH = WEIGHTS_DIR / "tracknet_tennis.pth"
TORCHSCRIPT_PATH = WEIGHTS_DIR / "tracknet_tennis.pt"

DEFAULT_INPUT_WIDTH = 640
DEFAULT_INPUT_HEIGHT = 360
DEFAULT_FRAME_STEP_S = 0.05
DEFAULT_TEMPORAL_GAP = 1
DEFAULT_SIGMA = 3.0
DEFAULT_EPOCHS = 8
DEFAULT_BATCH_SIZE = 4
DEFAULT_MAX_ANNOTATIONS = 220


@dataclass
class AnnotationState:
    cap: Any
    video_path: Path
    frame_index: int
    frame_count: int
    fps: float
    frame_step: int
    temporal_gap: int
    max_annotations: int
    frame: np.ndarray | None = None
    saved: int = 0
    positives: int = 0
    negatives: int = 0
    cursor_xy: tuple[int, int] | None = None
    zoom: float = 1.0
    view_center: tuple[float, float] | None = None
    dragging: bool = False
    drag_start_display: tuple[int, int] | None = None
    drag_start_center: tuple[float, float] | None = None
    auto_next: bool = True
    message: str = ""
    last_sample_id: str | None = None


def main() -> None:
    args = parse_args()
    ensure_dirs()

    if not args.train_only:
        video_path = choose_video_path(args.video)
        annotate_video(
            video_path=video_path,
            frame_step_s=args.frame_step_s,
            start_s=args.start_s,
            temporal_gap=args.temporal_gap,
            max_annotations=args.max_annotations,
            input_width=args.input_width,
            input_height=args.input_height,
            sigma=args.sigma,
        )

    if not args.no_train:
        train_model(
            epochs=args.epochs,
            batch_size=args.batch_size,
            input_width=args.input_width,
            input_height=args.input_height,
            sigma=args.sigma,
            lr=args.lr,
            device_arg=args.device,
            fresh=args.fresh,
            model_size=args.model_size,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treina um modelo TrackNet/heatmap para detectar a bolinha."
    )
    parser.add_argument("--video", default=None, help="Caminho do video para anotacao.")
    parser.add_argument("--train-only", action="store_true", help="Treina usando o dataset existente.")
    parser.add_argument("--no-train", action="store_true", help="Apenas anota, sem treinar no final.")
    parser.add_argument("--fresh", action="store_true", help="Ignora checkpoint anterior e treina do zero.")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--input-width", type=int, default=DEFAULT_INPUT_WIDTH)
    parser.add_argument("--input-height", type=int, default=DEFAULT_INPUT_HEIGHT)
    parser.add_argument(
        "--model-size",
        default="lite",
        choices=["lite", "full"],
        help="lite e mais rapido em CPU; full replica a arquitetura fallback do app.",
    )
    parser.add_argument("--sigma", type=float, default=DEFAULT_SIGMA, help="Raio visual do heatmap em px.")
    parser.add_argument("--frame-step-s", type=float, default=DEFAULT_FRAME_STEP_S)
    parser.add_argument("--start-s", type=float, default=0.0)
    parser.add_argument("--temporal-gap", type=int, default=DEFAULT_TEMPORAL_GAP)
    parser.add_argument("--max-annotations", type=int, default=DEFAULT_MAX_ANNOTATIONS)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return parser.parse_args()


def ensure_dirs() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)


def choose_video_path(path_arg: str | None) -> Path:
    if path_arg:
        path = Path(path_arg.strip('"')).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Video nao encontrado: {path}")
        return path

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.title("Tennis X-Ray - selecionar video")
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askopenfilename(
            parent=root,
            title="Selecione o video para treinar TrackNet/heatmap",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv"), ("Todos", "*.*")],
        )
        root.destroy()
        if selected:
            return Path(selected)
    except Exception:
        pass

    raw = input("Caminho do video: ").strip()
    return Path(raw.strip('"')).expanduser()


def annotate_video(
    video_path: Path,
    frame_step_s: float,
    start_s: float,
    temporal_gap: int,
    max_annotations: int,
    input_width: int,
    input_height: int,
    sigma: float,
) -> None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_step = max(1, int(round(max(frame_step_s, 0.001) * fps)))
    start_index = max(0, min(frame_count - 1, int(round(start_s * fps)))) if frame_count else 0

    state = AnnotationState(
        cap=cap,
        video_path=video_path,
        frame_index=start_index,
        frame_count=frame_count,
        fps=fps,
        frame_step=frame_step,
        temporal_gap=max(1, temporal_gap),
        max_annotations=max_annotations,
    )
    read_current_frame(state)

    window = "Tennis X-Ray - TrackNet heatmap trainer"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    try:
        cv2.resizeWindow(window, 1280, 840)
        cv2.moveWindow(window, 50, 30)
        cv2.setWindowProperty(window, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    cv2.setMouseCallback(
        window,
        lambda event, x, y, flags, _param: on_mouse(
            state, event, x, y, flags, input_width=input_width, input_height=input_height, sigma=sigma
        ),
    )

    print("")
    print("=== TrackNet heatmap trainer ===")
    print("Clique ESQUERDO: salva centro da bolinha (positivo)")
    print("N ou clique DIREITO: salva frame negativo/sem bolinha")
    print("Setas/A-D/Espaco: navega frames | Ctrl+Scroll ou +/-: zoom")
    print("Botao do meio + arrastar ou W/A/S/D com zoom: reposiciona")
    print("U: desfaz ultima amostra | R: reseta zoom | Q/Esc: finaliza")
    print("")

    while True:
        if state.frame is None:
            break
        display = draw_annotation_view(state, input_width=input_width, input_height=input_height, sigma=sigma)
        cv2.imshow(window, display)
        key = cv2.waitKeyEx(20)
        if key in (-1, 255):
            continue
        if handle_key(state, key):
            break
        if state.saved >= state.max_annotations:
            state.message = f"Limite de {state.max_annotations} anotacoes atingido."
            break

    cv2.destroyWindow(window)
    cap.release()
    print(f"Anotacao finalizada. Positivos: {state.positives}, negativos: {state.negatives}.")


def on_mouse(
    state: AnnotationState,
    event: int,
    x: int,
    y: int,
    flags: int,
    input_width: int,
    input_height: int,
    sigma: float,
) -> None:
    if state.frame is None:
        return

    state.cursor_xy = display_to_frame_xy(state, x, y)

    if event == cv2.EVENT_MOUSEWHEEL:
        if flags & cv2.EVENT_FLAG_CTRLKEY:
            delta = mouse_wheel_delta(flags)
            zoom_at_cursor(state, factor=1.18 if delta > 0 else 1 / 1.18, display_xy=(x, y))
        return

    if event == cv2.EVENT_MBUTTONDOWN:
        state.dragging = True
        state.drag_start_display = (x, y)
        state.drag_start_center = state.view_center
        return

    if event == cv2.EVENT_MOUSEMOVE and state.dragging:
        pan_from_drag(state, x, y)
        return

    if event == cv2.EVENT_MBUTTONUP:
        state.dragging = False
        state.drag_start_display = None
        state.drag_start_center = None
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        point = display_to_frame_xy(state, x, y)
        save_sample(
            state,
            positive=True,
            center_xy=point,
            input_width=input_width,
            input_height=input_height,
            sigma=sigma,
        )
        if state.auto_next:
            advance_frame(state, state.frame_step)
        return

    if event == cv2.EVENT_RBUTTONDOWN:
        save_sample(
            state,
            positive=False,
            center_xy=None,
            input_width=input_width,
            input_height=input_height,
            sigma=sigma,
        )
        if state.auto_next:
            advance_frame(state, state.frame_step)


def handle_key(state: AnnotationState, key: int) -> bool:
    # OpenCV key codes vary by OS. Keep both ASCII and common extended codes.
    if key in (27, ord("q"), ord("Q")):
        return True
    if key in (ord("n"), ord("N")):
        save_sample(state, positive=False, center_xy=None)
        if state.auto_next:
            advance_frame(state, state.frame_step)
    elif key in (ord("u"), ord("U")):
        undo_last_sample(state)
    elif key in (ord("r"), ord("R")):
        state.zoom = 1.0
        state.view_center = None
    elif key in (ord("+"), ord("=")):
        zoom_at_cursor(state, factor=1.18)
    elif key in (ord("-"), ord("_")):
        zoom_at_cursor(state, factor=1 / 1.18)
    elif key in (ord(" "), ord("d"), ord("D"), 83, 2555904):
        advance_frame(state, state.frame_step)
    elif key in (ord("a"), ord("A"), 81, 2424832):
        advance_frame(state, -state.frame_step)
    elif key in (ord("w"), ord("W")):
        pan_by_pixels(state, 0, -80)
    elif key in (ord("s"), ord("S")):
        pan_by_pixels(state, 0, 80)
    elif key in (ord("j"), ord("J")):
        advance_frame(state, -1)
    elif key in (ord("l"), ord("L")):
        advance_frame(state, 1)
    return False


def read_current_frame(state: AnnotationState) -> bool:
    if state.frame_count:
        state.frame_index = max(0, min(state.frame_count - 1, state.frame_index))
    state.cap.set(cv2.CAP_PROP_POS_FRAMES, state.frame_index)
    ok, frame = state.cap.read()
    if not ok or frame is None:
        state.frame = None
        state.message = "Frame nao carregado."
        return False
    state.frame = frame
    if state.view_center is None:
        h, w = frame.shape[:2]
        state.view_center = (w / 2.0, h / 2.0)
    return True


def read_frame_at(cap: Any, index: int, fallback: np.ndarray) -> np.ndarray:
    index = max(0, int(index))
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    if not ok or frame is None:
        return fallback.copy()
    return frame


def advance_frame(state: AnnotationState, delta: int) -> None:
    if state.frame_count:
        state.frame_index = max(0, min(state.frame_count - 1, state.frame_index + delta))
    else:
        state.frame_index = max(0, state.frame_index + delta)
    read_current_frame(state)


def save_sample(
    state: AnnotationState,
    positive: bool,
    center_xy: tuple[int, int] | None,
    input_width: int = DEFAULT_INPUT_WIDTH,
    input_height: int = DEFAULT_INPUT_HEIGHT,
    sigma: float = DEFAULT_SIGMA,
) -> None:
    if state.frame is None:
        return
    if positive and center_xy is None:
        return

    split = split_for_next_sample(count_manifest_entries())
    sample_id = f"{state.video_path.stem}_f{state.frame_index:07d}_{int(time.time() * 1000)}"
    sample_dir = SAMPLES_DIR / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    prev_frame = read_frame_at(state.cap, state.frame_index - state.temporal_gap, state.frame)
    curr_frame = state.frame.copy()
    next_frame = read_frame_at(state.cap, state.frame_index + state.temporal_gap, state.frame)
    for name, frame in (("prev", prev_frame), ("curr", curr_frame), ("next", next_frame)):
        cv2.imwrite(str(sample_dir / f"{name}.jpg"), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 96])

    h, w = curr_frame.shape[:2]
    center_norm = None
    if positive and center_xy is not None:
        x, y = center_xy
        center_norm = {
            "x": clamp(float(x) / max(w - 1, 1), 0.0, 1.0),
            "y": clamp(float(y) / max(h - 1, 1), 0.0, 1.0),
        }

    entry = {
        "id": sample_id,
        "split": split,
        "positive": bool(positive),
        "center_norm": center_norm,
        "video": str(state.video_path),
        "frame_index": int(state.frame_index),
        "fps": float(state.fps),
        "input_width": int(input_width),
        "input_height": int(input_height),
        "sigma": float(sigma),
        "created_at": time.time(),
    }
    with MANIFEST_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    state.saved += 1
    state.last_sample_id = sample_id
    if positive:
        state.positives += 1
        state.message = f"Positivo salvo: {sample_id}"
    else:
        state.negatives += 1
        state.message = f"Negativo salvo: {sample_id}"


def undo_last_sample(state: AnnotationState) -> None:
    entries = load_manifest()
    if not entries:
        state.message = "Nada para desfazer."
        return
    last = entries[-1]
    sample_id = str(last.get("id", ""))
    sample_dir = SAMPLES_DIR / sample_id
    if sample_dir.exists():
        for child in sample_dir.glob("*"):
            child.unlink(missing_ok=True)
        sample_dir.rmdir()
    rewrite_manifest(entries[:-1])
    state.saved = max(0, state.saved - 1)
    if last.get("positive"):
        state.positives = max(0, state.positives - 1)
    else:
        state.negatives = max(0, state.negatives - 1)
    state.message = f"Desfeito: {sample_id}"


def split_for_next_sample(sample_number: int) -> str:
    return "val" if sample_number % 5 == 0 else "train"


def count_manifest_entries() -> int:
    if not MANIFEST_PATH.exists():
        return 0
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    entries: list[dict[str, Any]] = []
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def rewrite_manifest(entries: list[dict[str, Any]]) -> None:
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def viewport_params(state: AnnotationState) -> tuple[float, float, float, float, float, int, int]:
    if state.frame is None:
        return 0, 0, 1, 1, 1, 1, 1
    h, w = state.frame.shape[:2]
    zoom = clamp(float(state.zoom or 1.0), 1.0, 16.0)
    state.zoom = zoom
    crop_w = max(1.0, w / zoom)
    crop_h = max(1.0, h / zoom)
    if state.view_center is None:
        cx, cy = w / 2.0, h / 2.0
    else:
        cx, cy = state.view_center
    cx = clamp(cx, crop_w / 2.0, w - crop_w / 2.0)
    cy = clamp(cy, crop_h / 2.0, h - crop_h / 2.0)
    state.view_center = (cx, cy)
    x0 = clamp(cx - crop_w / 2.0, 0.0, max(0.0, w - crop_w))
    y0 = clamp(cy - crop_h / 2.0, 0.0, max(0.0, h - crop_h))
    scale = min(1280.0 / crop_w, 820.0 / crop_h)
    scale = clamp(scale, 0.10, 12.0)
    display_w = max(1, int(round(crop_w * scale)))
    display_h = max(1, int(round(crop_h * scale)))
    return x0, y0, crop_w, crop_h, scale, display_w, display_h


def display_to_frame_xy(state: AnnotationState, x: int, y: int) -> tuple[int, int]:
    x0, y0, _cw, _ch, scale, display_w, display_h = viewport_params(state)
    if state.frame is None:
        return 0, 0
    h, w = state.frame.shape[:2]
    dx = clamp(float(x), 0.0, float(display_w - 1))
    dy = clamp(float(y), 0.0, float(display_h - 1))
    px = int(round(clamp(x0 + dx / max(scale, 1e-6), 0.0, float(w - 1))))
    py = int(round(clamp(y0 + dy / max(scale, 1e-6), 0.0, float(h - 1))))
    return px, py


def frame_to_display_xy(state: AnnotationState, point: tuple[int, int]) -> tuple[int, int] | None:
    x0, y0, cw, ch, scale, display_w, display_h = viewport_params(state)
    px, py = point
    if px < x0 or px > x0 + cw or py < y0 or py > y0 + ch:
        return None
    dx = int(round((px - x0) * scale))
    dy = int(round((py - y0) * scale))
    if dx < -24 or dy < -24 or dx > display_w + 24 or dy > display_h + 24:
        return None
    return dx, dy


def draw_annotation_view(
    state: AnnotationState,
    input_width: int,
    input_height: int,
    sigma: float,
) -> np.ndarray:
    assert state.frame is not None
    x0, y0, cw, ch, scale, display_w, display_h = viewport_params(state)
    x1 = int(round(x0 + cw))
    y1 = int(round(y0 + ch))
    crop = state.frame[int(round(y0)) : y1, int(round(x0)) : x1]
    display = cv2.resize(crop, (display_w, display_h), interpolation=cv2.INTER_LINEAR)

    if state.cursor_xy is not None:
        cursor = frame_to_display_xy(state, state.cursor_xy)
        if cursor is not None:
            guide_radius = max(5, int(round(sigma * scale * (state.frame.shape[1] / max(input_width, 1)))))
            cv2.circle(display, cursor, guide_radius, (60, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(display, cursor, 2, (0, 240, 255), -1, cv2.LINE_AA)

    frame_time = state.frame_index / max(state.fps, 1e-6)
    text_lines = [
        "TrackNet heatmap trainer",
        f"Frame {state.frame_index}/{max(state.frame_count - 1, 0)} | {frame_time:.2f}s | zoom {state.zoom:.1f}x",
        f"Dataset: +{state.positives} positivos, {state.negatives} negativos nesta sessao",
        "Clique: positivo | N/direito: negativo | setas: frame | Ctrl+scroll: zoom | U: desfaz | Q: sair",
    ]
    draw_text_panel(display, text_lines, origin=(16, 18))
    if state.message:
        draw_status(display, state.message)
    return display


def draw_text_panel(img: np.ndarray, lines: list[str], origin: tuple[int, int]) -> None:
    x, y = origin
    width = min(img.shape[1] - 20, 980)
    height = 24 + len(lines) * 24
    overlay = img.copy()
    cv2.rectangle(overlay, (x - 8, y - 18), (x + width, y - 18 + height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.58, img, 0.42, 0, img)
    for i, line in enumerate(lines):
        color = (190, 255, 210) if i == 0 else (235, 235, 235)
        cv2.putText(img, line, (x, y + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 1, cv2.LINE_AA)


def draw_status(img: np.ndarray, text: str) -> None:
    x, y = 18, img.shape[0] - 26
    cv2.putText(img, text[:150], (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (50, 255, 210), 2, cv2.LINE_AA)


def zoom_at_cursor(
    state: AnnotationState,
    factor: float,
    display_xy: tuple[int, int] | None = None,
) -> None:
    if state.frame is None:
        return
    if display_xy is None:
        if state.cursor_xy is None:
            frame_point = state.view_center
        else:
            frame_point = state.cursor_xy
    else:
        frame_point = display_to_frame_xy(state, display_xy[0], display_xy[1])
    old_zoom = state.zoom
    state.zoom = clamp(state.zoom * factor, 1.0, 16.0)
    if state.zoom != old_zoom and frame_point is not None:
        state.view_center = (float(frame_point[0]), float(frame_point[1]))


def pan_from_drag(state: AnnotationState, x: int, y: int) -> None:
    if state.frame is None or state.drag_start_display is None or state.drag_start_center is None:
        return
    _x0, _y0, _cw, _ch, scale, _dw, _dh = viewport_params(state)
    dx = (x - state.drag_start_display[0]) / max(scale, 1e-6)
    dy = (y - state.drag_start_display[1]) / max(scale, 1e-6)
    state.view_center = (state.drag_start_center[0] - dx, state.drag_start_center[1] - dy)
    viewport_params(state)


def pan_by_pixels(state: AnnotationState, dx: int, dy: int) -> None:
    if state.frame is None:
        return
    _x0, _y0, _cw, _ch, scale, _dw, _dh = viewport_params(state)
    cx, cy = state.view_center or (state.frame.shape[1] / 2.0, state.frame.shape[0] / 2.0)
    state.view_center = (cx + dx / max(scale, 1e-6), cy + dy / max(scale, 1e-6))
    viewport_params(state)


def mouse_wheel_delta(flags: int) -> int:
    try:
        return int(cv2.getMouseWheelDelta(flags))
    except Exception:
        # Fallback: OpenCV stores wheel delta in the high word on Windows.
        return 1 if flags > 0 else -1


def train_model(
    epochs: int,
    batch_size: int,
    input_width: int,
    input_height: int,
    sigma: float,
    lr: float,
    device_arg: str,
    fresh: bool,
    model_size: str,
) -> None:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader

    entries = [entry for entry in load_manifest() if sample_files_exist(entry)]
    positives = sum(1 for e in entries if e.get("positive"))
    if positives < 8:
        print("")
        print("Poucos positivos para treinar TrackNet com seguranca.")
        print(f"Positivos atuais: {positives}. Recomendo pelo menos 30-60 cliques variados.")
        if positives == 0:
            return

    train_entries = [e for e in entries if e.get("split") == "train"]
    val_entries = [e for e in entries if e.get("split") == "val"] or train_entries[: max(1, len(train_entries) // 5)]
    if not train_entries:
        print("Dataset de treino vazio.")
        return

    device = resolve_device(device_arg)
    model = build_tracknet_model(model_size)
    if not fresh:
        load_checkpoint(model, model_size)
    model.to(device)

    train_loader = DataLoader(
        TrackNetHeatmapDataset(train_entries, input_width, input_height, sigma),
        batch_size=max(1, batch_size),
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        TrackNetHeatmapDataset(val_entries, input_width, input_height, sigma),
        batch_size=max(1, batch_size),
        shuffle=False,
        num_workers=0,
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    positive_weight = 16.0
    print("")
    print(f"Treinando TrackNet {model_size} em {device} | train={len(train_entries)} val={len(val_entries)}")
    print(f"Saida: {TORCHSCRIPT_PATH}")

    for epoch in range(1, max(1, epochs) + 1):
        model.train()
        train_losses: list[float] = []
        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            if logits.shape[-2:] != y.shape[-2:]:
                logits = F.interpolate(logits, size=y.shape[-2:], mode="bilinear", align_corners=False)
            loss_map = F.binary_cross_entropy_with_logits(logits, y, reduction="none")
            weights = 1.0 + y * positive_weight
            loss = (loss_map * weights).mean()
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))

        val_loss = evaluate_model(model, val_loader, device)
        train_loss = float(np.mean(train_losses)) if train_losses else 0.0
        print(f"Epoch {epoch:02d}/{epochs}: train_loss={train_loss:.5f} val_loss={val_loss:.5f}")

    save_checkpoint_and_export(model, input_width, input_height, sigma, entries, model_size)


class TrackNetHeatmapDataset:
    def __init__(self, entries: list[dict[str, Any]], input_width: int, input_height: int, sigma: float) -> None:
        self.entries = entries
        self.input_width = int(input_width)
        self.input_height = int(input_height)
        self.sigma = float(sigma)

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int):
        import torch

        entry = self.entries[idx]
        sample_dir = SAMPLES_DIR / str(entry["id"])
        channels: list[np.ndarray] = []
        for name in ("prev", "curr", "next"):
            frame = cv2.imread(str(sample_dir / f"{name}.jpg"), cv2.IMREAD_COLOR)
            if frame is None:
                frame = np.zeros((self.input_height, self.input_width, 3), dtype=np.uint8)
            frame = cv2.resize(frame, (self.input_width, self.input_height), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            channels.append(np.transpose(rgb, (2, 0, 1)))
        x = np.concatenate(channels, axis=0)

        heatmap = np.zeros((self.input_height, self.input_width), dtype=np.float32)
        if entry.get("positive") and entry.get("center_norm"):
            center = entry["center_norm"]
            cx = float(center["x"]) * (self.input_width - 1)
            cy = float(center["y"]) * (self.input_height - 1)
            heatmap = gaussian_heatmap(self.input_width, self.input_height, cx, cy, self.sigma)
        y = heatmap[None, :, :]
        return torch.from_numpy(x).float(), torch.from_numpy(y).float()


def gaussian_heatmap(width: int, height: int, cx: float, cy: float, sigma: float) -> np.ndarray:
    xs = np.arange(width, dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    sigma = max(0.8, float(sigma))
    heatmap = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma))
    return heatmap.astype(np.float32)


def evaluate_model(model: Any, loader: Any, device: str) -> float:
    import torch
    import torch.nn.functional as F

    model.eval()
    losses: list[float] = []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            if logits.shape[-2:] != y.shape[-2:]:
                logits = F.interpolate(logits, size=y.shape[-2:], mode="bilinear", align_corners=False)
            loss = F.binary_cross_entropy_with_logits(logits, y)
            losses.append(float(loss.detach().cpu()))
    return float(np.mean(losses)) if losses else 0.0


def build_tracknet_model(model_size: str) -> Any:
    if model_size == "lite":
        return TrackNetLiteArchitecture()
    try:
        from backend.app.servicos.tracknet_ball_tracker import TrackNetV1FallbackArchitecture

        return TrackNetV1FallbackArchitecture()
    except Exception:
        return LocalTrackNetV1FallbackArchitecture()


class TrackNetLiteArchitecture:
    """Small heatmap FCN exported as TorchScript for fast CPU iteration."""

    def __new__(cls):
        from torch import nn

        class _Model(nn.Module):
            def __init__(self) -> None:
                super().__init__()

                def block(in_ch: int, out_ch: int) -> nn.Sequential:
                    return nn.Sequential(
                        nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
                        nn.BatchNorm2d(out_ch),
                        nn.ReLU(inplace=True),
                        nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
                        nn.BatchNorm2d(out_ch),
                        nn.ReLU(inplace=True),
                    )

                self.encoder1 = block(9, 32)
                self.pool1 = nn.MaxPool2d(2, 2)
                self.encoder2 = block(32, 64)
                self.pool2 = nn.MaxPool2d(2, 2)
                self.encoder3 = block(64, 128)
                self.up2 = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)
                self.decoder2 = block(128 + 64, 64)
                self.up1 = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)
                self.decoder1 = block(64 + 32, 32)
                self.out = nn.Conv2d(32, 1, kernel_size=1)

            def forward(self, x):  # type: ignore[no-untyped-def]
                import torch
                import torch.nn.functional as F

                e1 = self.encoder1(x)
                e2 = self.encoder2(self.pool1(e1))
                e3 = self.encoder3(self.pool2(e2))
                d2 = self.up2(e3)
                if d2.shape[-2:] != e2.shape[-2:]:
                    d2 = F.interpolate(d2, size=e2.shape[-2:], mode="bilinear", align_corners=False)
                d2 = self.decoder2(torch.cat([d2, e2], dim=1))
                d1 = self.up1(d2)
                if d1.shape[-2:] != e1.shape[-2:]:
                    d1 = F.interpolate(d1, size=e1.shape[-2:], mode="bilinear", align_corners=False)
                d1 = self.decoder1(torch.cat([d1, e1], dim=1))
                return self.out(d1)

        return _Model()


class LocalTrackNetV1FallbackArchitecture:
    def __new__(cls):
        import torch
        from torch import nn

        class _Model(nn.Module):
            def __init__(self) -> None:
                super().__init__()

                def conv(in_ch: int, out_ch: int) -> nn.Sequential:
                    return nn.Sequential(
                        nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
                        nn.ReLU(inplace=True),
                        nn.BatchNorm2d(out_ch),
                    )

                self.net = nn.Sequential(
                    conv(9, 64),
                    conv(64, 64),
                    nn.MaxPool2d(2, 2),
                    conv(64, 128),
                    conv(128, 128),
                    nn.MaxPool2d(2, 2),
                    conv(128, 256),
                    conv(256, 256),
                    conv(256, 256),
                    nn.MaxPool2d(2, 2),
                    conv(256, 512),
                    conv(512, 512),
                    conv(512, 512),
                    nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False),
                    conv(512, 256),
                    conv(256, 256),
                    conv(256, 256),
                    nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False),
                    conv(256, 128),
                    conv(128, 128),
                    nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False),
                    conv(128, 64),
                    conv(64, 64),
                    nn.Conv2d(64, 1, kernel_size=1),
                )

            def forward(self, x):  # type: ignore[no-untyped-def]
                return self.net(x)

        return _Model()


def load_checkpoint(model: Any, model_size: str) -> None:
    if not CHECKPOINT_PATH.exists():
        return
    try:
        import torch

        payload = torch.load(str(CHECKPOINT_PATH), map_location="cpu")
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        previous_size = metadata.get("model_size")
        if previous_size not in (None, model_size):
            print(
                f"Checkpoint anterior e '{previous_size}', mas o treino atual e "
                f"'{model_size}'. Ignorando checkpoint."
            )
            return
        state = payload.get("state_dict") if isinstance(payload, dict) else payload
        if isinstance(state, dict):
            model.load_state_dict(state, strict=True)
            print(f"Checkpoint carregado: {CHECKPOINT_PATH}")
    except Exception as exc:
        print(f"Nao foi possivel carregar checkpoint anterior: {exc}")


def save_checkpoint_and_export(
    model: Any,
    input_width: int,
    input_height: int,
    sigma: float,
    entries: list[dict[str, Any]],
    model_size: str,
) -> None:
    import torch

    model_cpu = model.to("cpu").eval()
    metadata = {
        "architecture": "TrackNetLiteArchitecture" if model_size == "lite" else "TrackNetV1FallbackArchitecture",
        "model_size": model_size,
        "input_width": int(input_width),
        "input_height": int(input_height),
        "sigma": float(sigma),
        "samples": len(entries),
        "positives": sum(1 for e in entries if e.get("positive")),
        "negatives": sum(1 for e in entries if not e.get("positive")),
        "saved_at": time.time(),
    }
    torch.save({"state_dict": model_cpu.state_dict(), "metadata": metadata}, str(CHECKPOINT_PATH))

    example = torch.zeros(1, 9, int(input_height), int(input_width), dtype=torch.float32)
    scripted = torch.jit.trace(model_cpu, example)
    scripted.save(str(TORCHSCRIPT_PATH))
    print("")
    print(f"Checkpoint salvo: {CHECKPOINT_PATH}")
    print(f"Modelo TrackNet usado pelo app salvo: {TORCHSCRIPT_PATH}")
    print("Para comparar com YOLO/OpenCV, rode a app com TENNIS_XRAY_TRACKNET_ENABLED=0.")


def resolve_device(device_arg: str) -> str:
    import torch

    if device_arg == "cpu":
        return "cpu"
    if device_arg == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def sample_files_exist(entry: dict[str, Any]) -> bool:
    sample_dir = SAMPLES_DIR / str(entry.get("id", ""))
    return all((sample_dir / f"{name}.jpg").exists() for name in ("prev", "curr", "next"))


def clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return max(low, min(high, value))


if __name__ == "__main__":
    main()
