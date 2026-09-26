"""
Stage 1 of the ANPR pipeline — Plate Bounding-Box Detection.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BBox:
    x: int
    y: int
    w: int
    h: int
    confidence: float


class PlateDetector:
    def __init__(self, model_path: str, conf_threshold: float) -> None:
        self._model_path = model_path
        self._conf_threshold = conf_threshold
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            logger.info("PlateDetector loaded — model=%s conf_threshold=%.2f", self._model_path, self._conf_threshold)
        except Exception as exc:
            logger.error("PlateDetector: failed to load model '%s': %s", self._model_path, exc)
            raise

    def detect(self, frame: np.ndarray) -> BBox | None:
        if frame is None or frame.size == 0:
            logger.error("PlateDetector: invalid or empty frame received")
            return None

        if self._model is None:
            logger.error("PlateDetector: model not loaded")
            return None

        try:
            results = self._model(frame, verbose=False)
        except Exception as exc:
            logger.error("PlateDetector: inference error: %s", exc)
            return None

        best: BBox | None = None
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < self._conf_threshold:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)

                candidate = BBox(
                    x=x1,
                    y=y1,
                    w=max(1, x2 - x1),
                    h=max(1, y2 - y1),
                    confidence=conf,
                )

                if best is None or conf > best.confidence:
                    best = candidate

        return best
