from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.servicos.visao_video_real import analisar_video_real  # noqa: E402


VIDEO_EXTENSIONS = ("*.mp4", "*.mov", "*.m4v", "*.avi", "*.mkv")


def main() -> int:
    args = _parse_args()

    video_path = Path(args.video).expanduser().resolve() if args.video else _selecionar_video_interativo()
    if video_path is None:
        print("Nenhum video selecionado.")
        return 1
    if not video_path.exists():
        print(f"Video nao encontrado: {video_path}")
        return 1

    output_dir = Path(args.saida).expanduser().resolve() if args.saida else _selecionar_pasta_saida_interativo()
    if output_dir is None:
        print("Nenhuma pasta de saida selecionada.")
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)

    _aplicar_ambiente_teste(args)
    calibracao = _carregar_calibracao(args.calibracao)
    if calibracao is None:
        print("")
        print("ATENCAO: teste sem calibracao de quadra.")
        print("Para diagnosticar a bolinha com fidelidade, use --calibracao apontando para um .debug.json gerado pela aplicacao ou para o JSON de calibracao.")
        print("Sem isso, o rastreador nao consegue limitar artefatos de bancos, logos, outras quadras e cantos do frame.")

    print("")
    print("=== Tennis X-Ray | teste isolado do rastro da bolinha ===")
    print(f"Video: {video_path}")
    print(f"Saida: {output_dir}")
    print(f"Calibracao: {args.calibracao or 'nao informada'}")
    print("")

    ultimo_progresso = {"valor": -1.0}

    def progresso(valor: float, mensagem: str) -> bool:
        if valor - ultimo_progresso["valor"] >= 0.4 or valor >= 99:
            ultimo_progresso["valor"] = valor
            print(f"[{valor:6.2f}%] {mensagem}", flush=True)
        return True

    try:
        resultado = analisar_video_real(
            caminho_video=video_path,
            pasta_saida=output_dir,
            progress_callback=progresso,
            calibracao=calibracao,
        )
    except Exception as exc:
        print("")
        print(f"Falha ao renderizar o teste do rastro: {type(exc).__name__}: {exc}")
        return 1

    debug_path = resultado.video_analisado_path.with_suffix(".debug.json")
    debug_payload = {
        "script": Path(__file__).name,
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "video_origem": str(video_path),
        "video_saida": str(resultado.video_analisado_path),
        "metadata": resultado.metadata,
        "calibracao": calibracao,
        "ambiente_teste": _ambiente_teste_snapshot(),
    }
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("")
    print("Renderizacao concluida.")
    print(f"Video renderizado: {resultado.video_analisado_path}")
    print(f"Debug JSON: {debug_path}")

    if args.abrir_pasta and os.name == "nt":
        os.startfile(str(output_dir))  # type: ignore[attr-defined]

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Renderiza um video com os overlays reais da aplicacao para testar "
            "rapidamente o rastro da bolinha, sem abrir o frontend."
        )
    )
    parser.add_argument("--video", help="Caminho do video original MP4/MOV/etc.")
    parser.add_argument("--saida", help="Pasta onde o video analisado sera salvo.")
    parser.add_argument(
        "--calibracao",
        help=(
            "JSON opcional de calibracao. Aceita tanto o objeto de calibracao "
            "direto quanto um .debug.json gerado pela aplicacao."
        ),
    )
    parser.add_argument(
        "--global-fps",
        type=float,
        help="FPS usado somente no pre-processamento global da bolinha. Padrao atual da aplicacao: 12.",
    )
    parser.add_argument(
        "--global-max-frames",
        type=int,
        help="Limite de frames no solver global da bolinha. Padrao atual da aplicacao: 220.",
    )
    parser.add_argument(
        "--analysis-fps",
        type=float,
        help="FPS de renderizacao/anotacao. Se omitido, usa a configuracao da aplicacao.",
    )
    parser.add_argument(
        "--sem-global",
        action="store_true",
        help="Desliga apenas o solver global para comparar com o tracker frame a frame da aplicacao.",
    )
    parser.add_argument(
        "--abrir-pasta",
        action="store_true",
        help="Abre a pasta de saida ao finalizar no Windows.",
    )
    return parser.parse_args()


def _selecionar_video_interativo() -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None

    root = Tk()
    root.withdraw()
    tipos = [
        ("Videos", " ".join(VIDEO_EXTENSIONS)),
        ("Todos os arquivos", "*.*"),
    ]
    selecionado = filedialog.askopenfilename(
        title="Selecione o video original para testar o rastro da bolinha",
        filetypes=tipos,
    )
    root.destroy()
    return Path(selecionado).resolve() if selecionado else None


def _selecionar_pasta_saida_interativo() -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None

    root = Tk()
    root.withdraw()
    selecionado = filedialog.askdirectory(title="Selecione a pasta para salvar o video renderizado")
    root.destroy()
    return Path(selecionado).resolve() if selecionado else None


def _carregar_calibracao(caminho: str | None) -> dict[str, Any] | None:
    if not caminho:
        return None

    path = Path(caminho).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"JSON de calibracao nao encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("O JSON de calibracao precisa ser um objeto.")

    if "calibracao" in data:
        calibracao = data.get("calibracao")
    else:
        calibracao = data if any(key in data for key in ("court_points", "court_missing", "ball_marks", "players", "serve_marks")) else None
    if calibracao is None:
        return None
    if not isinstance(calibracao, dict):
        raise ValueError("Nao foi possivel extrair um objeto de calibracao do JSON informado.")
    return calibracao


def _aplicar_ambiente_teste(args: argparse.Namespace) -> None:
    if args.global_fps is not None:
        os.environ["TENNIS_XRAY_GLOBAL_BALL_FPS"] = str(args.global_fps)
    if args.global_max_frames is not None:
        os.environ["TENNIS_XRAY_GLOBAL_BALL_MAX_FRAMES"] = str(args.global_max_frames)
    if args.analysis_fps is not None:
        os.environ["TENNIS_XRAY_ANALYSIS_FPS"] = str(args.analysis_fps)
    if args.sem_global:
        os.environ["TENNIS_XRAY_GLOBAL_BALL_TRACKING"] = "0"


def _ambiente_teste_snapshot() -> dict[str, str]:
    chaves = [
        "TENNIS_XRAY_GLOBAL_BALL_TRACKING",
        "TENNIS_XRAY_GLOBAL_BALL_FPS",
        "TENNIS_XRAY_GLOBAL_BALL_MAX_FRAMES",
        "TENNIS_XRAY_GLOBAL_BALL_BEAM_WIDTH",
        "TENNIS_XRAY_GLOBAL_BALL_MAX_CANDIDATES",
        "TENNIS_XRAY_ANALYSIS_FPS",
        "TENNIS_XRAY_MAX_ANALYSIS_FRAMES",
        "TENNIS_XRAY_USE_BALL_YOLO",
        "TENNIS_XRAY_BALL_YOLO_PATH",
        "TENNIS_XRAY_TRACKNET_MODEL",
    ]
    return {chave: valor for chave in chaves if (valor := os.getenv(chave)) is not None}


if __name__ == "__main__":
    raise SystemExit(main())
