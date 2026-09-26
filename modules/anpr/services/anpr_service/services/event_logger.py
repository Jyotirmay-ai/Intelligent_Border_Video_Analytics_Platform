"""
Event logger — persists ANPREvent records into a local JSON lines log file.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.events import ANPREvent

logger = logging.getLogger(__name__)


class EventLogger:
    def __init__(self, log_path: str = "output_storage/anpr_events_log.json") -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: ANPREvent) -> str:
        try:
            record = event.model_dump(mode="json")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            logger.info("ANPREvent logged to file: %s", self._log_path)
            return str(self._log_path.resolve())
        except Exception as exc:
            logger.error("Failed to log ANPREvent to file: %s", exc)
            return ""
