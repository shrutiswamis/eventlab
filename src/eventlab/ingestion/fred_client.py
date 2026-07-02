from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FredObservation:
    date: str
    value: float | None


class FredClient:
    """Minimal FRED adapter for macro time series used by Fed-rate features."""

    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def observations(self, series_id: str, limit: int = 12) -> list[FredObservation]:
        params = urlencode(
            {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
        )
        payload = self._get_json(f"/series/observations?{params}")
        rows = payload.get("observations", [])
        return [FredObservation(date=row["date"], value=_safe_float(row["value"])) for row in rows]

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(f"{self.base_url}{path}", headers={"accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


def _safe_float(value: Any) -> float | None:
    if value in (None, "."):
        return None
    return float(value)

