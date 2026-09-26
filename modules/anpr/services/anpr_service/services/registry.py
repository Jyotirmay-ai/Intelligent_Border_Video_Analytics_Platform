"""
Registry client — cross-checks a read plate against the registered-vehicle list.
"""
from __future__ import annotations

import logging
from typing import Literal
import httpx

logger = logging.getLogger(__name__)
RegistrationStatus = Literal["registered", "unregistered", "unknown"]


class RegistryClient:
    def __init__(
        self,
        api_url: str,
        timeout_sec: float,
        mock_enabled: bool,
        mock_plates: list[str],
    ) -> None:
        self._api_url = api_url
        self._timeout = timeout_sec
        self._mock_enabled = mock_enabled
        self._mock_plates: frozenset[str] = frozenset(p.upper() for p in mock_plates)

    def check(self, plate_text: str) -> RegistrationStatus:
        if plate_text == "unreadable":
            return "unknown"

        normalised = plate_text.upper()
        if self._mock_enabled:
            return "registered" if normalised in self._mock_plates else "unregistered"
        
        try:
            resp = httpx.get(self._api_url, params={"plate": normalised}, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            raw_status = data.get("status", "")
            return raw_status if raw_status in ("registered", "unregistered") else "unknown"
        except Exception as exc:
            logger.error("RegistryClient: network/API error: %s", exc)
            return "unknown"
