from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PolymarketSnapshot:
    market_id: str
    title: str
    end_date: str | None
    yes_price: float | None
    no_price: float | None
    mid_price: float | None
    volume: float | None
    liquidity: float | None


class PolymarketClient:
    """Read-only Gamma API adapter for market discovery."""

    base_url = "https://gamma-api.polymarket.com"

    def list_markets(self, query: str, limit: int = 50) -> list[PolymarketSnapshot]:
        params = urlencode({"q": query, "limit": limit})
        payload = self._get_json(f"/markets?{params}")
        return self._parse_market_list(payload)

    def list_active_markets(self, limit: int = 500) -> list[PolymarketSnapshot]:
        params = urlencode({"active": "true", "closed": "false", "limit": limit})
        payload = self._get_json(f"/markets?{params}")
        return self._parse_market_list(payload)

    @staticmethod
    def _parse_market_list(payload: Any) -> list[PolymarketSnapshot]:
        if isinstance(payload, dict):
            markets = payload.get("data", [])
        else:
            markets = payload
        return [PolymarketClient._parse_market(market) for market in markets]

    def _get_json(self, path: str) -> Any:
        request = Request(
            f"{self.base_url}{path}",
            headers={"accept": "application/json", "user-agent": "eventlab-research/0.1"},
        )
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _parse_market(payload: dict[str, Any]) -> PolymarketSnapshot:
        yes_price, no_price = _parse_yes_no_prices(payload)
        return PolymarketSnapshot(
            market_id=str(payload.get("id", "")),
            title=str(payload.get("question", payload.get("title", ""))),
            end_date=payload.get("endDate") or payload.get("endDateIso") or payload.get("end_date_iso"),
            yes_price=yes_price,
            no_price=no_price,
            mid_price=yes_price or _safe_float(payload.get("lastTradePrice")),
            volume=_safe_float(payload.get("volume")),
            liquidity=_safe_float(payload.get("liquidity")),
        )


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_yes_no_prices(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    outcomes = _jsonish_list(payload.get("outcomes"))
    prices = _jsonish_list(payload.get("outcomePrices"))
    if not outcomes or not prices or len(outcomes) != len(prices):
        last_trade = _safe_float(payload.get("lastTradePrice"))
        return last_trade, None

    normalized = [str(outcome).strip().lower() for outcome in outcomes]
    yes_price = None
    no_price = None
    for outcome, price in zip(normalized, prices):
        if outcome == "yes":
            yes_price = _safe_float(price)
        elif outcome == "no":
            no_price = _safe_float(price)
    return yes_price, no_price


def _jsonish_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []
