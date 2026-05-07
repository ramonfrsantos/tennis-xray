from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrackNetCandidate:
    x: float
    y: float
    radius: float
    confidence: float
    heatmap_score: float
    peak_z: float = 0.0
    peak_margin: float = 0.0
    background_mean: float = 0.0
    rank: int = 0


class TrackNetV1FallbackArchitecture:
    """Small FCN compatible with common TrackNet-style state dicts.

    TorchScript or full pickled modules are preferred because public TrackNet
    checkpoints vary in layer naming. This fallback covers checkpoints whose
    state dict was exported from a simple VGG-like 9-channel heatmap network.
    """

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


class TrackNetBallTracker:
    def __init__(self) -> None:
        self.enabled = os.getenv("TENNIS_XRAY_TRACKNET_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
        self.input_width = _int_env("TENNIS_XRAY_TRACKNET_WIDTH", 640)
        self.input_height = _int_env("TENNIS_XRAY_TRACKNET_HEIGHT", 360)
        self.min_confidence = _float_env("TENNIS_XRAY_TRACKNET_MIN_CONF", 0.16)
        self.min_peak_z = _float_env("TENNIS_XRAY_TRACKNET_MIN_PEAK_Z", 2.75)
        self.min_peak_margin = _float_env("TENNIS_XRAY_TRACKNET_MIN_PEAK_MARGIN", 0.018)
        self.max_candidates = max(1, _int_env("TENNIS_XRAY_TRACKNET_TOPK", 5))
        self.nms_radius = max(5, _int_env("TENNIS_XRAY_TRACKNET_TOPK_NMS_RADIUS", 0))
        self.weights_path = _resolve_weights_path()
        self._model: Any | None = None
        self._device: str | None = None
        self._load_attempted = False
        self._available = False

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._available

    def detect(
        self,
        frame_prev2: np.ndarray | None,
        frame_prev1: np.ndarray | None,
        frame_curr: np.ndarray,
    ) -> TrackNetCandidate | None:
        candidates = self.detect_many(frame_prev2, frame_prev1, frame_curr, max_candidates=1)
        return candidates[0] if candidates else None

    def detect_many(
        self,
        frame_prev2: np.ndarray | None,
        frame_prev1: np.ndarray | None,
        frame_curr: np.ndarray,
        max_candidates: int | None = None,
    ) -> list[TrackNetCandidate]:
        if not self.enabled:
            return []
        self._ensure_loaded()
        if not self._available or self._model is None or self._device is None:
            return []

        # Training samples are stored as prev/curr/next, with the label on the
        # middle frame. At runtime we do not always have lookahead, so duplicate
        # the current frame as the next slot instead of shifting curr into the
        # last slot. Feeding prev2/prev1/curr makes the heatmap one frame out of
        # phase on fast rallies and creates the visible tracking delay.
        prev_frame = frame_prev1 if frame_prev1 is not None else frame_prev2
        frames = [
            prev_frame if prev_frame is not None else frame_curr,
            frame_curr,
            frame_curr,
        ]
        if any(frame is None or frame.shape[:2] != frame_curr.shape[:2] for frame in frames):
            frames = [frame_curr, frame_curr, frame_curr]

        try:
            import torch

            tensor = self._preprocess(frames)
            tensor = tensor.to(self._device)
            with torch.no_grad():
                output = self._model(tensor)
            heatmap = self._extract_heatmap(output)
            if heatmap is None:
                return []

            heatmap = cv2.GaussianBlur(heatmap, (5, 5), 0).astype(np.float32)
            return self._heatmap_candidates(
                heatmap,
                frame_shape=frame_curr.shape,
                max_candidates=max_candidates or self.max_candidates,
            )
        except Exception as exc:
            logger.debug("TrackNet inference failed: %s", exc)
            return []

    def _heatmap_candidates(
        self,
        heatmap: np.ndarray,
        frame_shape: tuple[int, ...],
        max_candidates: int,
    ) -> list[TrackNetCandidate]:
        finite = np.nan_to_num(heatmap.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        search = finite.copy()
        candidates: list[TrackNetCandidate] = []
        attempts = max(1, int(max_candidates)) * 4
        suppress_radius = self.nms_radius
        if suppress_radius <= 0:
            suppress_radius = max(5, int(round(min(self.input_width, self.input_height) * 0.022)))

        for _attempt in range(attempts):
            if len(candidates) >= max_candidates:
                break
            _, max_val, _, max_loc = cv2.minMaxLoc(search)
            raw_confidence = float(max_val)
            if raw_confidence < self.min_confidence:
                break

            peak_z, peak_margin, background_mean = self._heatmap_peak_quality_from_maps(
                finite,
                search,
                max_loc,
                raw_confidence,
            )
            cv2.circle(search, (int(max_loc[0]), int(max_loc[1])), suppress_radius, 0.0, -1)

            # Newly trained or under-trained heatmap models often output a
            # nearly flat map around 0.5. A raw max from that map is not a real
            # detection; require the max to stand out from the background.
            if peak_z < self.min_peak_z:
                continue
            if peak_margin < self.min_peak_margin and raw_confidence < 0.78:
                continue
            if peak_margin < self.min_peak_margin * 0.45:
                continue

            x_model, y_model = max_loc
            h, w = frame_shape[:2]
            x = float(x_model) * (w / max(self.input_width, 1))
            y = float(y_model) * (h / max(self.input_height, 1))
            radius = max(2.0, min(w, h) * 0.0045)
            confidence = min(
                0.99,
                max(
                    0.0,
                    raw_confidence * 0.55
                    + min(peak_z / 8.0, 1.0) * 0.30
                    + min(peak_margin / 0.22, 1.0) * 0.15,
                ),
            )
            rank = len(candidates)
            if rank > 0:
                confidence *= max(0.68, 1.0 - rank * 0.10)
            candidates.append(
                TrackNetCandidate(
                    x=x,
                    y=y,
                    radius=radius,
                    confidence=confidence,
                    heatmap_score=raw_confidence,
                    peak_z=peak_z,
                    peak_margin=peak_margin,
                    background_mean=background_mean,
                    rank=rank,
                )
            )
        return candidates

    def _heatmap_peak_quality(
        self,
        heatmap: np.ndarray,
        max_loc: tuple[int, int],
        max_val: float,
    ) -> tuple[float, float, float]:
        finite = np.nan_to_num(heatmap.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        return self._heatmap_peak_quality_from_maps(finite, finite, max_loc, max_val)

    def _heatmap_peak_quality_from_maps(
        self,
        finite: np.ndarray,
        search: np.ndarray,
        max_loc: tuple[int, int],
        max_val: float,
    ) -> tuple[float, float, float]:
        mean = float(np.mean(finite))
        std = float(np.std(finite))
        peak_z = (float(max_val) - mean) / max(std, 1e-6)

        x, y = max_loc
        masked = search.copy()
        radius = max(5, int(round(min(self.input_width, self.input_height) * 0.018)))
        cv2.circle(masked, (int(x), int(y)), radius, 0.0, -1)
        secondary = float(np.max(masked)) if masked.size else 0.0
        peak_margin = max(0.0, float(max_val) - secondary)
        return peak_z, peak_margin, mean

    def _ensure_loaded(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        if not self.enabled:
            return
        if self.weights_path is None:
            logger.info("TrackNet disabled: no weights found. Set TENNIS_XRAY_TRACKNET_WEIGHTS.")
            return

        try:
            import torch

            self._device = "cuda" if torch.cuda.is_available() and os.getenv("TENNIS_XRAY_TRACKNET_DEVICE", "auto") != "cpu" else "cpu"
            path = str(self.weights_path)
            try:
                model = torch.jit.load(path, map_location=self._device)
            except Exception:
                payload = torch.load(path, map_location=self._device)
                if hasattr(payload, "eval"):
                    model = payload
                else:
                    state_dict = _extract_state_dict(payload)
                    model = TrackNetV1FallbackArchitecture()
                    model.load_state_dict(state_dict, strict=True)

            model.to(self._device)
            model.eval()
            self._model = model
            self._available = True
            logger.info("TrackNet ball tracker loaded from %s on %s", self.weights_path, self._device)
        except Exception as exc:
            logger.warning("TrackNet unavailable (%s). Falling back to OpenCV/YOLO ball tracking.", exc)
            self._model = None
            self._available = False

    def _preprocess(self, frames: list[np.ndarray]):
        import torch

        channels: list[np.ndarray] = []
        for frame in frames:
            resized = cv2.resize(frame, (self.input_width, self.input_height), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            channels.append(np.transpose(rgb, (2, 0, 1)))
        stacked = np.concatenate(channels, axis=0)
        return torch.from_numpy(stacked).unsqueeze(0).float()

    def _extract_heatmap(self, output: Any) -> np.ndarray | None:
        import torch

        if isinstance(output, (list, tuple)):
            output = output[0]
        if not torch.is_tensor(output):
            return None
        out = output.detach().float().cpu()
        if out.ndim == 4:
            out = out[0, 0]
        elif out.ndim == 3:
            out = out[0]
        elif out.ndim == 2:
            pass
        elif out.ndim == 1 and out.numel() == self.input_width * self.input_height:
            out = out.reshape(self.input_height, self.input_width)
        else:
            return None

        arr = out.numpy()
        if np.nanmax(arr) > 1.0 or np.nanmin(arr) < 0.0:
            arr = 1.0 / (1.0 + np.exp(-np.clip(arr, -30.0, 30.0)))
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        if arr.shape != (self.input_height, self.input_width):
            arr = cv2.resize(arr, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        return arr.astype(np.float32)


_TRACKER: TrackNetBallTracker | None = None


def get_tracknet_tracker() -> TrackNetBallTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = TrackNetBallTracker()
    return _TRACKER


def _resolve_weights_path() -> Path | None:
    raw = os.getenv("TENNIS_XRAY_TRACKNET_WEIGHTS")
    candidates = []
    if raw:
        candidates.append(Path(raw))
    root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            root / "weights" / "tracknet_tennis.pt",
            root / "weights" / "tracknet_tennis.pth",
            root / "tracknet_tennis.pt",
            root / "tracknet_tennis.pth",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _extract_state_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        state = payload.get("state_dict") or payload.get("model_state_dict") or payload.get("model") or payload
    else:
        state = payload
    if not isinstance(state, dict):
        raise ValueError("TrackNet checkpoint does not contain a state_dict.")
    cleaned = {}
    for key, value in state.items():
        if not hasattr(value, "shape"):
            continue
        name = str(key)
        for prefix in ("module.", "model."):
            if name.startswith(prefix):
                name = name[len(prefix) :]
        cleaned[name] = value
    if not cleaned:
        raise ValueError("TrackNet checkpoint state_dict is empty.")
    return cleaned


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
