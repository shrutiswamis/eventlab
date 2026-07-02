from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from eventlab.config import RAW_DATA_DIR
from eventlab.ingestion.polymarket_client import PolymarketClient, PolymarketSnapshot
from eventlab.utils import clamp, read_csv


FED_KEYWORDS = (
    "fed",
    "fomc",
    "federal reserve",
    "interest rate",
    "rate cut",
    "rate cuts",
    "rates",
)


@dataclass(frozen=True)
class SourceReport:
    source: str
    status: str
    rows: int
    detail: str
    fetched_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "rows": self.rows,
            "detail": self.detail,
            "fetched_at": self.fetched_at,
        }


@dataclass(frozen=True)
class MacroSnapshot:
    cpi_surprise: float
    unemployment_rate: float
    unemployment_change: float
    fed_funds_rate: float
    fomc_tone_score: float
    fetched_at: str
    source_detail: str


@dataclass(frozen=True)
class PublicLiveDataset:
    markets: list[dict[str, object]]
    events: list[dict[str, object]]
    market_prices: list[dict[str, object]]
    macro: MacroSnapshot
    reports: list[SourceReport]

    @property
    def has_live_markets(self) -> bool:
        return any(row["venue"] == "Polymarket" for row in self.markets)


def build_public_live_dataset(now: datetime | None = None, raw_dir: Path = RAW_DATA_DIR) -> PublicLiveDataset:
    now = now or datetime.now(UTC)
    reports: list[SourceReport] = []
    markets, events, market_prices, market_report = fetch_polymarket_fed_markets(now)
    reports.append(market_report)
    macro, macro_report = fetch_macro_snapshot(now, raw_dir)
    reports.append(macro_report)

    if not markets:
        reports.append(
            SourceReport(
                source="eventlab_seed_data",
                status="fallback",
                rows=3,
                detail="No matching public Fed-rate markets were found; using bundled contracts.",
                fetched_at=now.isoformat(timespec="seconds"),
            )
        )
        return _seed_dataset_with_macro(macro, reports, now, raw_dir)

    return PublicLiveDataset(markets, events, market_prices, macro, reports)


def fetch_polymarket_fed_markets(now: datetime, limit: int = 500) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], SourceReport]:
    fetched_at = now.isoformat(timespec="seconds")
    try:
        snapshots = PolymarketClient().list_active_markets(limit=limit)
    except Exception as exc:
        return [], [], [], SourceReport(
            source="polymarket_gamma",
            status="error",
            rows=0,
            detail=f"{type(exc).__name__}: {exc}",
            fetched_at=fetched_at,
        )

    matches = [snapshot for snapshot in snapshots if _is_fed_rate_market(snapshot)]
    markets: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    prices: list[dict[str, object]] = []
    for snapshot in matches[:12]:
        event_date = _event_date(snapshot, now.date())
        market_id = f"POLY-{snapshot.market_id}"
        event_id = f"POLY-FED-{snapshot.market_id}"
        mid_price = snapshot.mid_price if snapshot.mid_price is not None else 0.5
        markets.append(
            {
                "market_id": market_id,
                "venue": "Polymarket",
                "title": snapshot.title,
                "category": "fed_rates",
                "expiration_date": event_date.isoformat(),
                "resolution_date": event_date.isoformat(),
            }
        )
        events.append(
            {
                "event_id": event_id,
                "market_id": market_id,
                "event_name": snapshot.title,
                "event_date": event_date.isoformat(),
                "outcome": None,
            }
        )
        yes_bid = clamp(mid_price - 0.01)
        yes_ask = clamp(mid_price + 0.01)
        prices.append(
            {
                "market_id": market_id,
                "timestamp": fetched_at,
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "mid_price": clamp(mid_price),
                "volume": snapshot.volume or 0.0,
                "liquidity": snapshot.liquidity or 0.0,
            }
        )

    status = "live" if matches else "empty"
    detail = f"Scanned {len(snapshots)} active markets; matched {len(matches)} Fed/rate-related titles."
    return markets, events, prices, SourceReport("polymarket_gamma", status, len(matches), detail, fetched_at)


def fetch_macro_snapshot(now: datetime, raw_dir: Path = RAW_DATA_DIR) -> tuple[MacroSnapshot, SourceReport]:
    fetched_at = now.isoformat(timespec="seconds")
    try:
        unrate = fetch_bls_series("LNS14000000", now.year - 2, now.year, timeout=12)
        cpi = fetch_bls_series("CUUR0000SA0", now.year - 2, now.year, timeout=12)
        if len(unrate) < 2 or len(cpi) < 7:
            raise ValueError("BLS returned too few observations for feature construction")
        unemployment_rate = unrate[-1][1]
        unemployment_change = unemployment_rate - unrate[-2][1]
        cpi_monthly = [cpi[i][1] / cpi[i - 1][1] - 1.0 for i in range(1, len(cpi))]
        latest_cpi_move = cpi_monthly[-1]
        trailing_cpi_move = sum(cpi_monthly[-7:-1]) / 6.0
        cpi_surprise = (latest_cpi_move - trailing_cpi_move) * 100.0
        fallback = _fallback_macro(raw_dir, fetched_at)
        macro = MacroSnapshot(
            cpi_surprise=round(cpi_surprise, 4),
            unemployment_rate=round(unemployment_rate, 4),
            unemployment_change=round(unemployment_change, 4),
            fed_funds_rate=fallback.fed_funds_rate,
            fomc_tone_score=0.0,
            fetched_at=fetched_at,
            source_detail="BLS public API: unemployment and CPI; bundled Fed funds proxy.",
        )
        return macro, SourceReport("bls_public_api", "live", 2, macro.source_detail, fetched_at)
    except Exception as exc:
        fallback = _fallback_macro(raw_dir, fetched_at)
        return fallback, SourceReport(
            "bls_public_api",
            "fallback",
            0,
            f"{type(exc).__name__}: {exc}; using bundled macro snapshot.",
            fetched_at,
        )


def fetch_fred_csv_series(series_id: str, timeout: int = 8) -> list[tuple[date, float]]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    request = Request(url, headers={"user-agent": "eventlab-research/0.1"})
    with urlopen(request, timeout=timeout) as response:
        content = response.read().decode("utf-8")
    rows = []
    for row in csv.DictReader(StringIO(content)):
        value = row.get(series_id)
        observation_date = row.get("observation_date")
        if not observation_date or value in (None, "", "."):
            continue
        rows.append((datetime.strptime(observation_date, "%Y-%m-%d").date(), float(value)))
    return rows


def fetch_bls_series(series_id: str, start_year: int, end_year: int, timeout: int = 12) -> list[tuple[date, float]]:
    url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}?startyear={start_year}&endyear={end_year}"
    request = Request(url, headers={"accept": "application/json", "user-agent": "eventlab-research/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: {payload.get('message')}")
    series = payload.get("Results", {}).get("series", [])
    if not series:
        return []
    rows = []
    for row in series[0].get("data", []):
        period = row.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue
        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            continue
        rows.append((_bls_period_to_date(row), value))
    return sorted(rows, key=lambda item: item[0])


def _bls_period_to_date(row: dict[str, Any]) -> date:
    year = int(row["year"])
    month = int(row["period"][1:])
    return date(year, month, 1)


def macro_to_fed_funds_implied_probability(macro: MacroSnapshot) -> float:
    probability = (
        0.48
        + 0.04 * max(macro.fed_funds_rate - 4.0, 0.0)
        + 0.35 * macro.unemployment_change
        - 0.20 * macro.cpi_surprise
    )
    return round(clamp(probability, 0.05, 0.95), 4)


def _seed_dataset_with_macro(macro: MacroSnapshot, reports: list[SourceReport], now: datetime, raw_dir: Path) -> PublicLiveDataset:
    markets = read_csv(raw_dir / "markets.csv")
    events = read_csv(raw_dir / "events.csv")
    price_rows = []
    source_timestamp = now.isoformat(timespec="seconds")
    for row in read_csv(raw_dir / "market_prices.csv"):
        price_rows.append({**row, "timestamp": source_timestamp})
    return PublicLiveDataset(markets, events, price_rows, macro, reports)


def _fallback_macro(raw_dir: Path, fetched_at: str) -> MacroSnapshot:
    rows = read_csv(raw_dir / "macro_observations.csv")
    latest = rows[-1]
    return MacroSnapshot(
        cpi_surprise=float(latest["cpi_surprise"]),
        unemployment_rate=float(latest["unemployment_rate"]),
        unemployment_change=float(latest["unemployment_change"]),
        fed_funds_rate=5.0,
        fomc_tone_score=float(latest["fomc_tone_score"]),
        fetched_at=fetched_at,
        source_detail="Bundled macro_observations.csv fallback",
    )


def _is_fed_rate_market(snapshot: PolymarketSnapshot) -> bool:
    title = snapshot.title.lower()
    has_keyword = any(keyword in title for keyword in FED_KEYWORDS)
    has_binary_price = snapshot.mid_price is not None and 0.0 <= snapshot.mid_price <= 1.0
    return has_keyword and has_binary_price


def _event_date(snapshot: PolymarketSnapshot, today: date) -> date:
    if snapshot.end_date:
        normalized = snapshot.end_date.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            pass
    return today + timedelta(days=90)
