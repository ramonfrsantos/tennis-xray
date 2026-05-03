from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.servicos.visao_video_real import (  # noqa: E402
    BallDetection,
    _bola_renderizavel_no_escopo,
    _candidato_bola_em_borda_frame,
    _candidato_bola_no_corredor_quadra_central,
    _candidatos_bola_amplos,
    _expandir_trajetoria_global_para_indices_render,
    _metadata_modelo_tracknet,
    _metadata_modelo_yolo_bola,
    _poligono_quadra_video_px,
    _precalcular_trajetoria_bola_global,
    _reduzir_indices_trajetoria_global,
)


def main() -> int:
    args = _parse_args()

    original = Path(args.original).expanduser().resolve() if args.original else _selecionar_arquivo("Selecione o video ORIGINAL")
    if original is None or not original.exists():
        print("Video original nao encontrado ou nao selecionado.")
        return 1

    analisado = Path(args.analisado).expanduser().resolve() if args.analisado else None
    if analisado is not None and not analisado.exists():
        print(f"Video analisado nao encontrado: {analisado}")
        return 1

    saida_base = Path(args.saida).expanduser().resolve() if args.saida else _selecionar_pasta()
    if saida_base is None:
        print("Pasta de saida nao selecionada.")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saida = saida_base / f"diagnostico_rastro_{timestamp}"
    frames_dir = saida / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    calibracao = _carregar_calibracao(args.debug)
    if calibracao is None:
        print("")
        print("ATENCAO: diagnostico sem calibracao de quadra.")
        print("Sem calibracao, o filtro espacial nao consegue separar a quadra principal de bancos, logos, outras quadras e bordas.")
    meta_original = _metadata_video(original)
    if meta_original["total_frames"] <= 0:
        print("Nao foi possivel ler frames do video original.")
        return 1

    sample_indices = _indices_amostragem(
        total_frames=meta_original["total_frames"],
        fps=meta_original["fps"],
        inicio_s=args.inicio,
        fim_s=args.fim,
        step_s=args.step,
        max_frames=args.max_frames,
    )

    print("")
    print("=== Diagnostico do rastro da bolinha ===")
    print(f"Original: {original}")
    print(f"Analisado: {analisado or 'nao informado'}")
    print(f"Debug/calibracao: {args.debug or 'nao informado'}")
    print(f"Saida: {saida}")
    print(f"Frames amostrados: {len(sample_indices)}")

    trajetoria_global: dict[int, BallDetection] = {}
    if not args.sem_solver:
        trajetoria_global = _resolver_trajetoria_global_para_diagnostico(
            video=original,
            fps=meta_original["fps"],
            total_frames=meta_original["total_frames"],
            frame_shape=(meta_original["height"], meta_original["width"], 3),
            calibracao=calibracao,
            inicio_s=args.inicio,
            fim_s=args.fim,
        )
        print(f"Pontos de trajetoria global calculados: {len(trajetoria_global)}")

    cap_original = cv2.VideoCapture(str(original))
    cap_analisado = cv2.VideoCapture(str(analisado)) if analisado else None
    meta_analisado = _metadata_video(analisado) if analisado else None

    csv_path = saida / "relatorio_candidatos.csv"
    json_path = saida / "relatorio_diagnostico.json"
    rows: list[dict[str, Any]] = []
    resumo_frames: list[dict[str, Any]] = []

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = [
            "frame_idx",
            "tempo_s",
            "tipo",
            "rank",
            "x",
            "y",
            "source",
            "confidence",
            "motion_score",
            "yellow_ratio",
            "em_borda",
            "no_corredor_quadra",
            "renderizavel_no_escopo",
            "motivo_rejeicao",
            "distancia_px_para_escolhida",
            "dx_para_escolhida",
            "dy_para_escolhida",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for pos, frame_idx in enumerate(sample_indices, start=1):
            frame = _ler_frame(cap_original, frame_idx)
            if frame is None:
                continue
            frame_prev = _ler_frame_temporario(original, max(0, frame_idx - 1))
            frame_pre = _ler_frame_temporario(original, max(0, frame_idx - 2))
            tempo_s = frame_idx / max(meta_original["fps"], 1.0)

            candidatos = _candidatos_bola_amplos(
                frame=frame,
                frame_anterior=frame_prev,
                frame_pre_anterior=frame_pre,
                players=[],
                calibracao=calibracao,
            )
            selecionada = trajetoria_global.get(frame_idx)

            frame_analisado = None
            if cap_analisado is not None and meta_analisado is not None:
                frame_analisado_idx = int(round(tempo_s * max(meta_analisado["fps"], 1.0)))
                frame_analisado = _ler_frame(cap_analisado, min(frame_analisado_idx, meta_analisado["total_frames"] - 1))

            imagem_debug = _desenhar_debug_frame(
                frame=frame,
                frame_analisado=frame_analisado,
                frame_idx=frame_idx,
                tempo_s=tempo_s,
                candidatos=candidatos,
                selecionada=selecionada,
                calibracao=calibracao,
                max_width=args.image_width,
                top_candidates=args.top_candidates,
            )
            nome_frame = f"frame_{frame_idx:06d}_{tempo_s:07.3f}s.jpg"
            cv2.imwrite(str(frames_dir / nome_frame), imagem_debug, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            frame_summary = {
                "frame_idx": frame_idx,
                "tempo_s": round(tempo_s, 4),
                "screenshot": str((frames_dir / nome_frame).resolve()),
                "candidatos": len(candidatos),
                "selecionada": _ball_to_dict(selecionada, frame.shape, calibracao) if selecionada else None,
            }
            resumo_frames.append(frame_summary)

            if selecionada is not None:
                row = _row_bola("selecionada", 0, frame_idx, tempo_s, selecionada, frame.shape, calibracao, selecionada)
                writer.writerow(row)
                rows.append(row)

            for rank, candidato in enumerate(candidatos[: args.top_candidates], start=1):
                row = _row_bola("candidato", rank, frame_idx, tempo_s, candidato, frame.shape, calibracao, selecionada)
                writer.writerow(row)
                rows.append(row)

            print(f"[{pos:03d}/{len(sample_indices):03d}] frame {frame_idx} | candidatos={len(candidatos)} | selecionada={selecionada.source if selecionada else 'nenhuma'}")

    cap_original.release()
    if cap_analisado is not None:
        cap_analisado.release()

    payload = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "original": str(original),
        "analisado": str(analisado) if analisado else None,
        "debug": str(Path(args.debug).expanduser().resolve()) if args.debug else None,
        "saida": str(saida),
        "metadata_original": meta_original,
        "metadata_analisado": meta_analisado,
        "calibracao_presente": calibracao is not None,
        "frames": resumo_frames,
        "csv": str(csv_path.resolve()),
        "ambiente": _ambiente_relevante(),
        "modelos": {
            "tracknet": _metadata_modelo_tracknet(),
            "yolo_bola": _metadata_modelo_yolo_bola(),
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    grade_path = None
    if not args.sem_grade:
        grade_path = _gerar_grade_screenshots(frames_dir, saida / "grade_screenshots.jpg", args.image_width)

    print("")
    print("Diagnostico concluido.")
    print(f"Screenshots: {frames_dir}")
    if grade_path:
        print(f"Grade visual: {grade_path}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    if args.abrir_pasta and os.name == "nt":
        os.startfile(str(saida))  # type: ignore[attr-defined]
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera screenshots e logs tecnicos para diagnosticar por que o rastro da bolinha escolhe artefatos."
    )
    parser.add_argument("--original", help="Video original usado no teste.")
    parser.add_argument("--analisado", help="Video analisado/renderizado pela aplicacao, opcional.")
    parser.add_argument("--debug", help="JSON de calibracao ou .debug.json gerado pela aplicacao.")
    parser.add_argument("--saida", help="Pasta onde salvar screenshots e relatorios.")
    parser.add_argument("--inicio", type=float, default=0.0, help="Tempo inicial em segundos.")
    parser.add_argument("--fim", type=float, default=None, help="Tempo final em segundos.")
    parser.add_argument("--step", type=float, default=0.50, help="Intervalo entre screenshots em segundos.")
    parser.add_argument("--max-frames", type=int, default=80, help="Maximo de screenshots.")
    parser.add_argument("--top-candidates", type=int, default=12, help="Quantos candidatos registrar/desenhar por frame.")
    parser.add_argument("--image-width", type=int, default=1800, help="Largura maxima da imagem de diagnostico.")
    parser.add_argument("--sem-solver", action="store_true", help="Nao roda o solver global; mostra apenas candidatos por frame.")
    parser.add_argument("--sem-grade", action="store_true", help="Nao gera a grade unica com miniaturas dos screenshots.")
    parser.add_argument("--abrir-pasta", action="store_true", help="Abre a pasta de diagnostico ao finalizar no Windows.")
    return parser.parse_args()


def _resolver_trajetoria_global_para_diagnostico(
    video: Path,
    fps: float,
    total_frames: int,
    frame_shape: tuple[int, int, int],
    calibracao: dict | None,
    inicio_s: float,
    fim_s: float | None,
) -> dict[int, BallDetection]:
    inicio_frame = max(0, int(round(max(0.0, inicio_s) * max(fps, 1.0))))
    fim_frame = total_frames - 1 if fim_s is None else min(total_frames - 1, int(round(max(0.0, fim_s) * max(fps, 1.0))))
    if fim_frame <= inicio_frame:
        return {}
    stride = max(1, int(round(max(fps, 1.0) / min(max(fps, 1.0), 60.0))))
    indices_render = list(range(inicio_frame, fim_frame + 1, stride))
    indices_solver = _reduzir_indices_trajetoria_global(indices_render, fps)

    def progresso(valor: float, mensagem: str) -> bool:
        if int(valor * 10) % 10 == 0:
            print(f"  solver {valor:5.1f}% | {mensagem}")
        return True

    sparse = _precalcular_trajetoria_bola_global(
        caminho_video=video,
        indices=indices_solver,
        fps_original=fps,
        calibracao=calibracao,
        progress_callback=progresso,
        progress_start=0.0,
        progress_end=100.0,
    )
    return _expandir_trajetoria_global_para_indices_render(
        trajetoria_sparse=sparse,
        indices_render=indices_render,
        fps_original=fps,
        calibracao=calibracao,
        frame_shape=frame_shape,
    )


def _desenhar_debug_frame(
    frame: np.ndarray,
    frame_analisado: np.ndarray | None,
    frame_idx: int,
    tempo_s: float,
    candidatos: list[BallDetection],
    selecionada: BallDetection | None,
    calibracao: dict | None,
    max_width: int,
    top_candidates: int,
) -> np.ndarray:
    painel_original = frame.copy()
    _desenhar_poligono_quadra(painel_original, calibracao)

    for rank, candidato in enumerate(candidatos[:top_candidates], start=1):
        em_borda = _candidato_bola_em_borda_frame(candidato, frame.shape)
        no_corredor = _candidato_bola_no_corredor_quadra_central(candidato, calibracao, frame.shape)
        renderizavel = _bola_renderizavel_no_escopo(candidato, calibracao, frame.shape)
        if em_borda:
            cor = (0, 0, 255)
        elif not no_corredor or not renderizavel:
            cor = (0, 128, 255)
        else:
            cor = (80, 255, 120)
        center = (int(round(candidato.x)), int(round(candidato.y)))
        cv2.circle(painel_original, center, max(5, int(round(candidato.radius + 4))), cor, 2)
        cv2.putText(
            painel_original,
            f"{rank}:{candidato.source[:10]} {candidato.confidence:.2f}",
            (center[0] + 8, center[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            cor,
            2,
        )

    if selecionada is not None:
        center = (int(round(selecionada.x)), int(round(selecionada.y)))
        cv2.circle(painel_original, center, 13, (255, 0, 255), 3)
        cv2.putText(
            painel_original,
            f"ESCOLHIDA {selecionada.source} {selecionada.confidence:.2f}",
            (center[0] + 12, center[1] + 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
        )

    header = np.zeros((74, painel_original.shape[1], 3), dtype=np.uint8)
    cv2.putText(header, f"Original | frame {frame_idx} | {tempo_s:.2f}s | candidatos: {len(candidatos)}", (16, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (230, 255, 210), 2)
    painel_original = np.vstack([header, painel_original])

    if frame_analisado is not None:
        painel_analisado = _resize_to_height(frame_analisado, painel_original.shape[0])
        header_a = np.zeros((74, painel_analisado.shape[1], 3), dtype=np.uint8)
        cv2.putText(header_a, "Video analisado/renderizado", (16, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (230, 255, 210), 2)
        painel_analisado = np.vstack([header_a, painel_analisado])
        if painel_analisado.shape[0] != painel_original.shape[0]:
            painel_analisado = _resize_to_height(painel_analisado, painel_original.shape[0])
        combinado = np.hstack([painel_original, painel_analisado])
    else:
        combinado = painel_original

    if combinado.shape[1] > max_width:
        scale = max_width / combinado.shape[1]
        combinado = cv2.resize(combinado, (max_width, int(round(combinado.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    return combinado


def _row_bola(
    tipo: str,
    rank: int,
    frame_idx: int,
    tempo_s: float,
    bola: BallDetection,
    frame_shape: tuple[int, int, int],
    calibracao: dict | None,
    selecionada: BallDetection | None,
) -> dict[str, Any]:
    dx = dy = distancia = None
    if selecionada is not None:
        dx = float(bola.x) - float(selecionada.x)
        dy = float(bola.y) - float(selecionada.y)
        distancia = float((dx * dx + dy * dy) ** 0.5)
    return {
        "frame_idx": frame_idx,
        "tempo_s": round(tempo_s, 4),
        "tipo": tipo,
        "rank": rank,
        "x": round(float(bola.x), 2),
        "y": round(float(bola.y), 2),
        "source": bola.source,
        "confidence": round(float(bola.confidence), 4),
        "motion_score": round(float(bola.motion_score), 4),
        "yellow_ratio": round(float(bola.yellow_ratio), 4),
        "em_borda": _candidato_bola_em_borda_frame(bola, frame_shape),
        "no_corredor_quadra": _candidato_bola_no_corredor_quadra_central(bola, calibracao, frame_shape),
        "renderizavel_no_escopo": _bola_renderizavel_no_escopo(bola, calibracao, frame_shape),
        "motivo_rejeicao": _motivo_rejeicao_bola(bola, frame_shape, calibracao),
        "distancia_px_para_escolhida": round(distancia, 2) if distancia is not None else "",
        "dx_para_escolhida": round(dx, 2) if dx is not None else "",
        "dy_para_escolhida": round(dy, 2) if dy is not None else "",
    }


def _ball_to_dict(bola: BallDetection | None, frame_shape: tuple[int, int, int], calibracao: dict | None) -> dict[str, Any] | None:
    if bola is None:
        return None
    return _row_bola("selecionada", 0, -1, 0.0, bola, frame_shape, calibracao, bola)


def _motivo_rejeicao_bola(
    bola: BallDetection,
    frame_shape: tuple[int, int, int],
    calibracao: dict | None,
) -> str:
    motivos: list[str] = []
    if calibracao is None:
        motivos.append("sem_calibracao_escopo_indefinido")
    if _candidato_bola_em_borda_frame(bola, frame_shape):
        motivos.append("borda_frame")
    if not _candidato_bola_no_corredor_quadra_central(bola, calibracao, frame_shape):
        motivos.append("fora_corredor_quadra")
    if not _bola_renderizavel_no_escopo(bola, calibracao, frame_shape):
        motivos.append("fora_escopo_render")
    return "|".join(motivos) if motivos else "aceito"


def _desenhar_poligono_quadra(frame: np.ndarray, calibracao: dict | None) -> None:
    poligono = _poligono_quadra_video_px(calibracao, frame.shape)
    if poligono is not None:
        cv2.polylines(frame, [poligono.astype(np.int32)], True, (120, 255, 120), 2)


def _resize_to_height(frame: np.ndarray, height: int) -> np.ndarray:
    if frame.shape[0] == height:
        return frame
    scale = height / max(frame.shape[0], 1)
    return cv2.resize(frame, (int(round(frame.shape[1] * scale)), height), interpolation=cv2.INTER_AREA)


def _gerar_grade_screenshots(frames_dir: Path, saida: Path, max_width: int) -> Path | None:
    arquivos = sorted(frames_dir.glob("*.jpg"))
    if not arquivos:
        return None
    imagens: list[np.ndarray] = []
    limite = min(len(arquivos), 36)
    for arquivo in arquivos[:limite]:
        img = cv2.imread(str(arquivo))
        if img is None:
            continue
        thumb_w = 520
        scale = thumb_w / max(img.shape[1], 1)
        thumb = cv2.resize(img, (thumb_w, max(1, int(round(img.shape[0] * scale)))), interpolation=cv2.INTER_AREA)
        imagens.append(thumb)
    if not imagens:
        return None

    cols = 3 if len(imagens) >= 3 else len(imagens)
    rows = int(math.ceil(len(imagens) / cols))
    cell_w = max(img.shape[1] for img in imagens)
    cell_h = max(img.shape[0] for img in imagens)
    grade = np.full((rows * cell_h, cols * cell_w, 3), 18, dtype=np.uint8)
    for idx, img in enumerate(imagens):
        row = idx // cols
        col = idx % cols
        y0 = row * cell_h
        x0 = col * cell_w
        grade[y0 : y0 + img.shape[0], x0 : x0 + img.shape[1]] = img
    if grade.shape[1] > max_width:
        scale = max_width / grade.shape[1]
        grade = cv2.resize(grade, (max_width, int(round(grade.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(saida), grade, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return saida


def _indices_amostragem(total_frames: int, fps: float, inicio_s: float, fim_s: float | None, step_s: float, max_frames: int) -> list[int]:
    fps_ref = max(float(fps or 0.0), 1.0)
    inicio = max(0, int(round(max(0.0, inicio_s) * fps_ref)))
    fim = total_frames - 1 if fim_s is None else min(total_frames - 1, int(round(max(0.0, fim_s) * fps_ref)))
    step_frames = max(1, int(round(max(0.02, step_s) * fps_ref)))
    indices = list(range(inicio, fim + 1, step_frames))
    if len(indices) > max_frames:
        pos = np.linspace(0, len(indices) - 1, max_frames, dtype=int)
        indices = [indices[int(i)] for i in pos]
    return sorted(set(indices))


def _metadata_video(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"fps": 0.0, "total_frames": 0, "width": 0, "height": 0}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    return {"fps": fps, "total_frames": total, "width": width, "height": height, "duration_s": total / fps if fps > 0 else 0.0}


def _ler_frame(cap: cv2.VideoCapture, frame_idx: int) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
    ok, frame = cap.read()
    return frame if ok else None


def _ler_frame_temporario(video: Path, frame_idx: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video))
    try:
        return _ler_frame(cap, frame_idx)
    finally:
        cap.release()


def _carregar_calibracao(path_str: str | None) -> dict[str, Any] | None:
    if not path_str:
        return None
    path = Path(path_str).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "calibracao" in data:
            calibracao = data.get("calibracao")
            return calibracao if isinstance(calibracao, dict) else None
        if any(key in data for key in ("court_points", "court_missing", "ball_marks", "players", "serve_marks")):
            return data
        return None
    raise ValueError("JSON de debug/calibracao invalido.")


def _selecionar_arquivo(title: str) -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None
    root = Tk()
    root.withdraw()
    value = filedialog.askopenfilename(title=title, filetypes=[("Videos", "*.mp4 *.mov *.m4v *.avi *.mkv"), ("Todos", "*.*")])
    root.destroy()
    return Path(value).resolve() if value else None


def _selecionar_pasta() -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None
    root = Tk()
    root.withdraw()
    value = filedialog.askdirectory(title="Selecione a pasta para salvar o diagnostico")
    root.destroy()
    return Path(value).resolve() if value else None


def _ambiente_relevante() -> dict[str, str]:
    keys = [
        "TENNIS_XRAY_GLOBAL_BALL_TRACKING",
        "TENNIS_XRAY_GLOBAL_BALL_FPS",
        "TENNIS_XRAY_GLOBAL_BALL_MAX_FRAMES",
        "TENNIS_XRAY_GLOBAL_BALL_BEAM_WIDTH",
        "TENNIS_XRAY_GLOBAL_BALL_MAX_CANDIDATES",
        "TENNIS_XRAY_BALL_YOLO_PATH",
        "TENNIS_XRAY_TRACKNET_MODEL",
    ]
    return {key: value for key in keys if (value := os.getenv(key)) is not None}


if __name__ == "__main__":
    raise SystemExit(main())
