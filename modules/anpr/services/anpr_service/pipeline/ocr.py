"""
Stage 2 of the ANPR pipeline — Optical Character Recognition.
"""
from __future__ import annotations

import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

UNREADABLE = "unreadable"


class PlateOCR:
    def __init__(
        self,
        conf_threshold: float,
        languages: list[str],
        model_storage_path: str | None = None,
        user_network_path: str | None = None,
    ) -> None:
        self._conf_threshold = conf_threshold
        self._reader = None
        self._load_reader(languages, model_storage_path, user_network_path)

    def _load_reader(
        self,
        languages: list[str],
        model_storage_path: str | None,
        user_network_path: str | None,
    ) -> None:
        try:
            import easyocr
            reader_options = {"gpu": False, "verbose": False}
            if model_storage_path:
                Path(model_storage_path).mkdir(parents=True, exist_ok=True)
                reader_options["model_storage_directory"] = model_storage_path
            if user_network_path:
                Path(user_network_path).mkdir(parents=True, exist_ok=True)
                reader_options["user_network_directory"] = user_network_path
            self._reader = easyocr.Reader(languages, **reader_options)
            logger.info("PlateOCR loaded — languages=%s conf_threshold=%.2f", languages, self._conf_threshold)
        except Exception as exc:
            logger.error("PlateOCR: failed to initialise reader: %s", exc)
            raise

    def read(self, crop: np.ndarray) -> tuple[str, float]:
        if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
            return UNREADABLE, 0.0

        if self._reader is None:
            return UNREADABLE, 0.0

        try:
            results = self._reader.readtext(crop)
        except Exception as exc:
            logger.error("PlateOCR: readtext error: %s", exc)
            return UNREADABLE, 0.0

        if not results:
            return UNREADABLE, 0.0

        texts: list[str] = []
        total_conf = 0.0

        for (_, text, conf) in results:
            cleaned = text.strip().upper()
            if cleaned:
                texts.append(cleaned)
            total_conf += conf

        avg_conf = total_conf / len(results)
        combined = "".join(texts)

        if avg_conf < self._conf_threshold:
            logger.info("PlateOCR: confidence %.3f below threshold %.3f → UNREADABLE", avg_conf, self._conf_threshold)
            return UNREADABLE, round(avg_conf, 4)

        return combined, round(avg_conf, 4)
