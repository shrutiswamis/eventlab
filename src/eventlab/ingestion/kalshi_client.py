from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class KalshiMarketSnapshot:
    market_id: str
    title: str
    yes_bid: float | None
    yes_ask: float | None
    mid_price: float | None
    volume: float | None
    liquidity: float | None


class KalshiClient:
    """Small public-data client with a deterministic interface for ETL jobs."""

    base_url = "https://trading-api.kalshi.com/trade-api/v2"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def list_markets(self, search: str, limit: int = 50) -> list[KalshiMarketSnapshot]:
        params = urlencode({"search": search, "limit": limit})
        payload = self._get_json(f"/markets?{params}")
        markets = payload.get("markets", [])
        return [self._parse_market(market) for market in markets]

    def _get_json(self, path: str) -> dict[str, Any]:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(f"{self.base_url}{path}", headers=headers)
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _parse_market(payload: dict[str, Any]) -> KalshiMarketSnapshot:
        yes_bid = _cents_to_probability(payload.get("yes_bid"))
        yes_ask = _cents_to_probability(payload.get("yes_ask"))
        mid_price = None if yes_bid is None or yes_ask is None else round((yes_bid + yes_ask) / 2.0, 4)
        return KalshiMarketSnapshot(
            market_id=str(payload.get("ticker", "")),
            title=str(payload.get("title", "")),
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            mid_price=mid_price,
            volume=_safe_float(payload.get("volume")),
            liquidity=_safe_float(payload.get("liquidity")),
        )


def _cents_to_probability(value: Any) -> float | None:
    numeric = _safe_float(value)
    return None if numeric is None else round(numeric / 100.0, 4)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)

