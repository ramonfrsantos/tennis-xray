"""Treinador visual incremental para a bolinha de tenis.

Uso:
    python treinar_bolinha_visual.py

O script abre um video MP4, permite clicar na bolinha em frames selecionados,
gera labels YOLO e treina/faz fine-tuning de um modelo de deteccao de bolinha.
As amostras sao acumuladas em data/tennis_ball_visual_dataset e o peso treinado
e salvo em weights/tennis_ball_yolo_custom.pt.
"""

from __future__ import annotations

import argparse
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import cv2


ROOT_DIR = Path(__file__).resolve().parent
DATASET_DIR = ROOT_DIR / "data" / "tennis_ball_visual_dataset"
WEIGHTS_DIR = ROOT_DIR / "weights"
ACTIVE_MODEL = WEIGHTS_DIR / "tennis_ball_yolo.pt"
CUSTOM_MODEL = WEIGHTS_DIR / "tennis_ball_yolo_custom.pt"
FALLBACK_MODEL = ROOT_DIR / "yolov8n.pt"
RUNS_DIR = ROOT_DIR / "runs" / "tennis_ball_training"
DEFAULT_FRAME_STEP_S = 0.08
DEFAULT_START_S = 0.0
DEFAULT_MAX_FRAMES = 160
DEFAULT_BOX_SIZE_PX = 18


@dataclass
class AnnotationState:
    frame_index: int
    frame: object
    frame_count: int
    fps: float
    video_stem: str
    split: str
    box_size_px: int
    saved: int = 0
    positives: int = 0
    negatives: int = 0
    auto_next: bool = True
    clicked: bool = False
    click_xy: tuple[int, int] | None = None
    cursor_xy: tuple[int, int] | None = None
    zoom: float = 1.0
    view_center: tuple[float, float] | None = None
    message: str = ""


def ask_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if not value and default is not None:
        return default
    return value


def ask_int(prompt: str, default: int, min_value: int, max_value: int) -> int:
    while True:
        raw = ask_text(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Digite um numero inteiro.")
            continue
        return max(min_value, min(max_value, value))


def ask_float(prompt: str, default: float, min_value: float, max_value: float) -> float:
    while True:
        raw = ask_text(prompt, str(default))
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            print("Digite um numero.")
            continue
        return max(min_value, min(max_value, value))


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    default_text = "S" if default else "N"
    raw = ask_text(prompt, default_text).lower()
    return raw in {"s", "sim", "y", "yes"}


def choose_video_path(path_arg: str | None) -> Path:
    if path_arg:
        path = Path(path_arg).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Video nao encontrado: {path}")

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
            title="Selecione o video MP4 para treinar a bolinha",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv"), ("Todos", "*.*")],
        )
        root.destroy()
        if selected:
            return Path(selected)
    except Exception:
        pass

    raw = ask_text("Caminho do video MP4")
    return Path(raw.strip('"')).expanduser()


def destacar_janela_opencv(window_name: str) -> None:
    try:
        cv2.resizeWindow(window_name, 1280, 720)
        cv2.moveWindow(window_name, 60, 40)
    except Exception:
        pass
    try:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass


def ensure_dataset() -> Path:
    for split in ("train", "val"):
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    data_yaml = DATASET_DIR / "data.yaml"
    # Ultralytics aceita caminho absoluto no campo path. Isso evita depender do
    # diretorio de execucao quando o treino for chamado pelo script.
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {DATASET_DIR.as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: tennis-ball",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return data_yaml


def count_existing_images() -> int:
    total = 0
    for split in ("train", "val"):
        total += len(list((DATASET_DIR / "images" / split).glob("*.jpg")))
    return total


def split_for_next_sample(sample_number: int) -> str:
    # Mantem um pequeno conjunto de validacao mesmo em datasets pequenos.
    return "val" if sample_number % 5 == 0 else "train"


def yolo_label_from_click(x: int, y: int, width: int, height: int, box_size_px: int) -> str:
    box_w = max(4, min(width, box_size_px))
    box_h = max(4, min(height, box_size_px))
    xc = max(0.0, min(1.0, x / max(width, 1)))
    yc = max(0.0, min(1.0, y / max(height, 1)))
    wn = max(0.001, min(1.0, box_w / max(width, 1)))
    hn = max(0.001, min(1.0, box_h / max(height, 1)))
    return f"0 {xc:.8f} {yc:.8f} {wn:.8f} {hn:.8f}\n"


def save_sample(state: AnnotationState, positive: bool) -> None:
    image_dir = DATASET_DIR / "images" / state.split
    label_dir = DATASET_DIR / "labels" / state.split
    timestamp = int(time.time() * 1000)
    sample_name = f"{state.video_stem}_f{state.frame_index:07d}_{timestamp}"
    image_path = image_dir / f"{sample_name}.jpg"
    label_path = label_dir / f"{sample_name}.txt"

    cv2.imwrite(str(image_path), state.frame, [int(cv2.IMWRITE_JPEG_QUALITY), 96])

    if positive:
        if state.click_xy is None:
            return
        h, w = state.frame.shape[:2]
        label_path.write_text(
            yolo_label_from_click(state.click_xy[0], state.click_xy[1], w, h, state.box_size_px),
            encoding="utf-8",
        )
        state.positives += 1
        state.message = f"Positivo salvo: {image_path.name}"
    else:
        # Label vazio = frame negativo. Isso ajuda o YOLO a aprender que linhas,
        # placas, rede e reflexos nao sao bolinhas.
        label_path.write_text("", encoding="utf-8")
        state.negatives += 1
        state.message = f"Negativo salvo: {image_path.name}"

    state.saved += 1


def viewport_params(state: AnnotationState) -> tuple[float, float, float, float, float, int, int]:
    h, w = state.frame.shape[:2]
    zoom = max(1.0, min(12.0, float(state.zoom or 1.0)))
    state.zoom = zoom
    crop_w = max(1.0, w / zoom)
    crop_h = max(1.0, h / zoom)

    if state.view_center is None:
        cx, cy = w / 2.0, h / 2.0
    else:
        cx, cy = state.view_center
    cx = max(crop_w / 2.0, min(w - crop_w / 2.0, cx))
    cy = max(crop_h / 2.0, min(h - crop_h / 2.0, cy))
    state.view_center = (cx, cy)

    x0 = max(0.0, min(w - crop_w, cx - crop_w / 2.0))
    y0 = max(0.0, min(h - crop_h, cy - crop_h / 2.0))
    scale = min(1280.0 / crop_w, 900.0 / crop_h)
    scale = max(0.10, min(8.0, scale))
    display_w = max(1, int(round(crop_w * scale)))
    display_h = max(1, int(round(crop_h * scale)))
    return x0, y0, crop_w, crop_h, scale, display_w, display_h


def display_to_frame_xy(state: AnnotationState, x: int, y: int) -> tuple[int, int]:
    x0, y0, _crop_w, _crop_h, scale, display_w, display_h = viewport_params(state)
    h, w = state.frame.shape[:2]
    dx = max(0, min(display_w - 1, int(x)))
    dy = max(0, min(display_h - 1, int(y)))
    px = int(max(0, min(w - 1, round(x0 + dx / max(scale, 1e-6)))))
    py = int(max(0, min(h - 1, round(y0 + dy / max(scale, 1e-6)))))
    return px, py


def frame_to_display_xy(state: AnnotationState, point: tuple[int, int]) -> tuple[int, int] | None:
    x0, y0, crop_w, crop_h, scale, display_w, display_h = viewport_params(state)
    px, py = point
    if px < x0 or py < y0 or px > x0 + crop_w or py > y0 + crop_h:
        return None
    dx = int(round((px - x0) * scale))
    dy = int(round((py - y0) * scale))
    if dx < -32 or dy < -32 or dx > display_w + 32 or dy > display_h + 32:
        return None
    return dx, dy


def draw_overlay(state: AnnotationState) -> object:
    x0, y0, crop_w, crop_h, scale, display_w, display_h = viewport_params(state)
    x1 = int(round(x0 + crop_w))
    y1 = int(round(y0 + crop_h))
    x0i = int(round(x0))
    y0i = int(round(y0))
    crop = state.frame[y0i:y1, x0i:x1]
    interpolation = cv2.INTER_LINEAR if state.zoom > 1.0 else cv2.INTER_AREA
    display = cv2.resize(crop, (display_w, display_h), interpolation=interpolation)
    dh, dw = display.shape[:2]

    if state.cursor_xy is not None:
        cursor = frame_to_display_xy(state, state.cursor_xy)
        if cursor is not None:
            cx, cy = cursor
            half = max(3, int(round((state.box_size_px / 2.0) * scale)))
            cv2.rectangle(display, (cx - half, cy - half), (cx + half, cy + half), (50, 255, 210), 1, cv2.LINE_AA)
            cv2.circle(display, (cx, cy), max(3, half), (50, 255, 210), 1, cv2.LINE_AA)
            cv2.drawMarker(display, (cx, cy), (20, 20, 20), cv2.MARKER_CROSS, max(10, half * 2), 3)
            cv2.drawMarker(display, (cx, cy), (50, 255, 210), cv2.MARKER_CROSS, max(10, half * 2), 1)
            label = f"{state.box_size_px}px"
            cv2.putText(display, label, (min(dw - 80, cx + half + 8), max(18, cy - half - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display, label, (min(dw - 80, cx + half + 8), max(18, cy - half - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 255, 210), 1, cv2.LINE_AA)

    if state.click_xy is not None:
        clicked = frame_to_display_xy(state, state.click_xy)
        if clicked is not None:
            cx, cy = clicked
            radius = max(5, int(state.box_size_px * scale / 2))
            cv2.circle(display, (cx, cy), radius, (0, 255, 255), 2)
            cv2.drawMarker(display, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, max(10, radius * 2), 2)

    info_lines = [
        f"Frame {state.frame_index}/{state.frame_count - 1} | {state.frame_index / max(state.fps, 1.0):.2f}s",
        f"Box {state.box_size_px}px | zoom {state.zoom:.1f}x | salvos {state.saved} (+{state.positives}/-{state.negatives}) | split {state.split}",
        "Clique=bolinha | e=negativo | Ctrl+scroll=zoom | 0=reset | +/- box | s/espaco=pular | q sair",
    ]
    if state.message:
        info_lines.append(state.message)

    y = 28
    for line in info_lines:
        cv2.putText(display, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.63, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(display, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.63, (235, 255, 235), 1, cv2.LINE_AA)
        y += 28

    # Pequeno alvo central ajuda quando o frame e muito grande.
    cv2.rectangle(display, (0, 0), (dw - 1, dh - 1), (24, 64, 56), 2)
    return display


def on_mouse(event: int, x: int, y: int, flags: int, param: AnnotationState) -> None:
    if event == cv2.EVENT_MOUSEMOVE:
        param.cursor_xy = display_to_frame_xy(param, x, y)
        return

    if event == cv2.EVENT_MOUSEWHEEL:
        if flags & cv2.EVENT_FLAG_CTRLKEY:
            try:
                delta = cv2.getMouseWheelDelta(flags)
            except Exception:
                delta = 1 if flags > 0 else -1
            anchor = display_to_frame_xy(param, x, y)
            fator = 1.22 if delta > 0 else 1 / 1.22
            param.zoom = max(1.0, min(12.0, param.zoom * fator))
            param.view_center = (float(anchor[0]), float(anchor[1]))
            param.cursor_xy = anchor
            param.message = f"Zoom {param.zoom:.1f}x"
        return

    if event != cv2.EVENT_LBUTTONDOWN:
        return
    px, py = display_to_frame_xy(param, x, y)
    param.click_xy = (px, py)
    param.cursor_xy = (px, py)
    param.clicked = True
    save_sample(param, positive=True)


def annotate_video(video_path: Path, frame_step_s: float, start_s: float, max_frames: int, box_size_px: int) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        cap.release()
        raise RuntimeError("Nao foi possivel ler frames do video.")

    step_frames = max(1, int(round(frame_step_s * fps)))
    frame_index = max(0, min(frame_count - 1, int(round(start_s * fps))))
    existing = count_existing_images()
    processed = 0

    window_name = "Tennis X-Ray - treino visual da bolinha"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    destacar_janela_opencv(window_name)

    state: AnnotationState | None = None
    try:
        while frame_index < frame_count and processed < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                break

            split = split_for_next_sample(existing + processed + 1)
            state = AnnotationState(
                frame_index=frame_index,
                frame=frame,
                frame_count=frame_count,
                fps=fps,
                video_stem=safe_stem(video_path),
                split=split,
                box_size_px=box_size_px,
                saved=0 if state is None else state.saved,
                positives=0 if state is None else state.positives,
                negatives=0 if state is None else state.negatives,
                auto_next=True if state is None else state.auto_next,
                cursor_xy=None if state is None else state.cursor_xy,
                zoom=1.0 if state is None else state.zoom,
                view_center=None if state is None else state.view_center,
                message="" if state is None else state.message,
            )
            cv2.setMouseCallback(window_name, on_mouse, state)

            while True:
                cv2.imshow(window_name, draw_overlay(state))
                key = cv2.waitKey(20) & 0xFF

                if state.clicked and state.auto_next:
                    frame_index += step_frames
                    processed += 1
                    break
                state.clicked = False

                if key in (ord("q"), 27):
                    cap.release()
                    cv2.destroyWindow(window_name)
                    return state.saved
                if key in (ord(" "), ord("s"), ord("n")):
                    frame_index += step_frames
                    processed += 1
                    break
                if key == ord("e"):
                    save_sample(state, positive=False)
                    frame_index += step_frames
                    processed += 1
                    break
                if key in (ord("+"), ord("=")):
                    state.box_size_px = min(96, state.box_size_px + 2)
                    box_size_px = state.box_size_px
                if key in (ord("-"), ord("_")):
                    state.box_size_px = max(4, state.box_size_px - 2)
                    box_size_px = state.box_size_px
                if key == ord("0"):
                    state.zoom = 1.0
                    state.view_center = None
                    state.message = "Zoom resetado"
                if key == ord("a"):
                    state.auto_next = not state.auto_next
                    state.message = f"Auto-next: {'ligado' if state.auto_next else 'desligado'}"
                if key == ord("b"):
                    frame_index = max(0, frame_index - step_frames)
                    processed = max(0, processed - 1)
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0 if state is None else state.saved


def safe_stem(path: Path) -> str:
    raw = path.stem.lower()
    keep = []
    for ch in raw:
        keep.append(ch if ch.isalnum() else "_")
    stem = "".join(keep).strip("_")
    return stem or "video"


def dataset_stats() -> tuple[int, int, int]:
    positives = 0
    negatives = 0
    for split in ("train", "val"):
        for label_path in (DATASET_DIR / "labels" / split).glob("*.txt"):
            text = label_path.read_text(encoding="utf-8").strip()
            if text:
                positives += 1
            else:
                negatives += 1
    return positives + negatives, positives, negatives


def choose_base_model() -> Path:
    if CUSTOM_MODEL.exists():
        return CUSTOM_MODEL
    if ACTIVE_MODEL.exists():
        return ACTIVE_MODEL
    if FALLBACK_MODEL.exists():
        return FALLBACK_MODEL
    raise FileNotFoundError(
        "Nenhum peso base encontrado. Esperado: weights/tennis_ball_yolo_custom.pt, "
        "weights/tennis_ball_yolo.pt ou yolov8n.pt."
    )


def train_model(data_yaml: Path, epochs: int, imgsz: int, batch: int, device: str, publish_active: bool) -> Path:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "Ultralytics nao esta instalado. Instale com: pip install -r requirements-visao.txt"
        ) from exc

    base_model = choose_base_model()
    print(f"\nTreinando a partir de: {base_model}")
    model = YOLO(str(base_model))

    train_kwargs = {
        "data": str(data_yaml),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "project": str(RUNS_DIR),
        "name": time.strftime("visual_%Y%m%d_%H%M%S"),
        "exist_ok": False,
        "patience": max(6, min(epochs, 15)),
        "workers": 0,
    }
    if device.strip():
        train_kwargs["device"] = device.strip()

    results = model.train(**train_kwargs)
    save_dir = Path(getattr(results, "save_dir", ""))
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise RuntimeError(f"Treino finalizou, mas best.pt nao foi encontrado em: {best}")

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, CUSTOM_MODEL)
    print(f"Modelo customizado salvo em: {CUSTOM_MODEL}")

    if publish_active:
        publish_custom_model()

    return CUSTOM_MODEL


def publish_custom_model() -> None:
    if not CUSTOM_MODEL.exists():
        raise FileNotFoundError(f"Modelo customizado nao encontrado: {CUSTOM_MODEL}")
    backup_dir = WEIGHTS_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if ACTIVE_MODEL.exists():
        backup = backup_dir / f"tennis_ball_yolo_{time.strftime('%Y%m%d_%H%M%S')}.pt"
        shutil.copy2(ACTIVE_MODEL, backup)
        print(f"Backup do modelo ativo salvo em: {backup}")
    shutil.copy2(CUSTOM_MODEL, ACTIVE_MODEL)
    print(f"Modelo ativo atualizado em: {ACTIVE_MODEL}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Treino visual incremental da bolinha de tenis.")
    parser.add_argument("--video", help="Caminho do video MP4.")
    parser.add_argument("--sem-treino", action="store_true", help="Apenas anotar dataset, sem treinar.")
    parser.add_argument("--publicar", action="store_true", help="Publicar o modelo customizado como weights/tennis_ball_yolo.pt.")
    parser.add_argument("--epochs", type=int, default=None, help="Epocas de treino.")
    parser.add_argument("--imgsz", type=int, default=None, help="Tamanho de imagem do YOLO.")
    parser.add_argument("--batch", type=int, default=None, help="Batch do YOLO. Use -1 para auto.")
    parser.add_argument("--device", default="", help="Device Ultralytics, ex: 0, cpu, cuda.")
    parser.add_argument("--configurar", action="store_true", help="Perguntar parametros de anotacao antes de abrir a janela.")
    parser.add_argument("--step-s", type=float, default=DEFAULT_FRAME_STEP_S, help="Intervalo entre frames revisados.")
    parser.add_argument("--start-s", type=float, default=DEFAULT_START_S, help="Tempo inicial do video.")
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES, help="Maximo de frames revisados.")
    parser.add_argument("--box-size", type=int, default=DEFAULT_BOX_SIZE_PX, help="Tamanho inicial da caixa da bolinha em pixels.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("=== Tennis X-Ray | Treino visual da bolinha ===")
    print("Dica: salve positivos clicando na bolinha e negativos com 'e' em frames onde o modelo costuma confundir rede/placa/linha.")

    data_yaml = ensure_dataset()
    video_path = choose_video_path(args.video)
    if not video_path.exists():
        print(f"Video nao encontrado: {video_path}")
        return 1

    if args.configurar:
        frame_step_s = ask_float("Intervalo entre frames para anotacao em segundos", DEFAULT_FRAME_STEP_S, 0.01, 2.0)
        start_s = ask_float("Tempo inicial do video em segundos", DEFAULT_START_S, 0.0, 999999.0)
        max_frames = ask_int("Maximo de frames para revisar nesta rodada", DEFAULT_MAX_FRAMES, 1, 5000)
        box_size_px = ask_int("Tamanho inicial da caixa da bolinha em pixels", DEFAULT_BOX_SIZE_PX, 4, 96)
    else:
        frame_step_s = max(0.01, min(2.0, float(args.step_s)))
        start_s = max(0.0, float(args.start_s))
        max_frames = max(1, min(5000, int(args.max_frames)))
        box_size_px = max(4, min(96, int(args.box_size)))

    print("\nJanela de anotacao:")
    print(f"Video: {video_path}")
    print(f"Parametros: step={frame_step_s:.3f}s, inicio={start_s:.2f}s, max_frames={max_frames}, box={box_size_px}px")
    print("- Clique esquerdo: salva a bolinha no frame atual")
    print("- e: salva frame negativo/sem bolinha")
    print("- espaco/s/n: pula frame")
    print("- +/-: muda tamanho da caixa")
    print("- a: liga/desliga avancar automatico apos clique")
    print("- b: volta um passo")
    print("- q ou Esc: encerra anotacao")

    saved_now = annotate_video(video_path, frame_step_s, start_s, max_frames, box_size_px)
    total, positives, negatives = dataset_stats()
    print(f"\nAmostras novas nesta rodada: {saved_now}")
    print(f"Dataset acumulado: {total} imagens | positivos: {positives} | negativos: {negatives}")
    print(f"Dataset YAML: {data_yaml}")

    if args.sem_treino:
        print("Treino pulado por --sem-treino.")
        return 0

    if positives < 5:
        print("Poucos positivos para treinar com seguranca. Anote pelo menos 5 frames com bolinha.")
        return 0

    if not ask_yes_no("Treinar/fazer fine-tuning agora?", True):
        print("Anotacoes salvas. Rode o script novamente para continuar alimentando o dataset.")
        return 0

    epochs = args.epochs if args.epochs is not None else ask_int("Epocas", 30, 1, 500)
    imgsz = args.imgsz if args.imgsz is not None else ask_int("imgsz YOLO", 1280, 320, 2048)
    batch = args.batch if args.batch is not None else ask_int("Batch (-1 = automatico)", -1, -1, 128)
    publish_active = args.publicar or ask_yes_no("Publicar como modelo ativo weights/tennis_ball_yolo.pt?", False)

    trained_path = train_model(data_yaml, epochs=epochs, imgsz=imgsz, batch=batch, device=args.device, publish_active=publish_active)
    print(f"\nPronto. Peso treinado: {trained_path}")
    print("A cada nova execucao, novas anotacoes serao somadas ao mesmo dataset e o treino partira do peso customizado anterior.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        raise SystemExit(130)
