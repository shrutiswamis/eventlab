from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from eventlab.config import RAW_DATA_DIR
from eventlab.db.load_data import connect_sqlite, initialize_sqlite
from eventlab.ingestion.public_live_data import MacroSnapshot, macro_to_fed_funds_implied_probability
from eventlab.utils import parse_date, parse_timestamp, read_csv, write_csv


@dataclass(frozen=True)
class FeatureRow:
    event_id: str
    timestamp: str
    cpi_surprise: float
    unemployment_rate: float
    unemployment_change: float
    fed_funds_implied_prob: float
    fomc_tone_score: float
    days_to_event: int

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "cpi_surprise": self.cpi_surprise,
            "unemployment_rate": self.unemployment_rate,
            "unemployment_change": self.unemployment_change,
            "fed_funds_implied_prob": self.fed_funds_implied_prob,
            "fomc_tone_score": self.fomc_tone_score,
            "days_to_event": self.days_to_event,
        }


def build_feature_rows(raw_dir=RAW_DATA_DIR) -> list[FeatureRow]:
    events = {row["event_id"]: row for row in read_csv(raw_dir / "events.csv")}
    rows: list[FeatureRow] = []
    for row in read_csv(raw_dir / "macro_observations.csv"):
        event = events[row["event_id"]]
        days_to_event = (parse_date(event["event_date"]) - parse_timestamp(row["timestamp"]).date()).days
        rows.append(
            FeatureRow(
                event_id=row["event_id"],
                timestamp=row["timestamp"],
                cpi_surprise=float(row["cpi_surprise"]),
                unemployment_rate=float(row["unemployment_rate"]),
                unemployment_change=float(row["unemployment_change"]),
                fed_funds_implied_prob=float(row["fed_funds_implied_prob"]),
                fomc_tone_score=float(row["fomc_tone_score"]),
                days_to_event=days_to_event,
            )
        )
    return rows


def build_feature_rows_from_database(conn: sqlite3.Connection, macro: MacroSnapshot) -> list[FeatureRow]:
    rows = conn.execute(
        """
        SELECT e.event_id, e.event_date, mp.timestamp, mp.mid_price
        FROM events e
        JOIN market_prices mp ON mp.market_id = e.market_id
        ORDER BY e.event_id
        """
    ).fetchall()
    features: list[FeatureRow] = []
    fed_funds_implied_prob = macro_to_fed_funds_implied_probability(macro)
    for row in rows:
        days_to_event = (parse_date(row["event_date"]) - parse_timestamp(row["timestamp"]).date()).days
        features.append(
            FeatureRow(
                event_id=row["event_id"],
                timestamp=row["timestamp"],
                cpi_surprise=macro.cpi_surprise,
                unemployment_rate=macro.unemployment_rate,
                unemployment_change=macro.unemployment_change,
                fed_funds_implied_prob=fed_funds_implied_prob,
                fomc_tone_score=macro.fomc_tone_score,
                days_to_event=days_to_event,
            )
        )
    return features


def persist_features(conn: sqlite3.Connection, rows: list[FeatureRow]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO features
        (event_id, timestamp, cpi_surprise, unemployment_rate, unemployment_change,
         fed_funds_implied_prob, fomc_tone_score, days_to_event)
        VALUES
        (:event_id, :timestamp, :cpi_surprise, :unemployment_rate, :unemployment_change,
         :fed_funds_implied_prob, :fomc_tone_score, :days_to_event)
        """,
        [row.as_dict() for row in rows],
    )
    conn.commit()


def main() -> None:
    rows = build_feature_rows()
    conn = connect_sqlite()
    initialize_sqlite(conn)
    persist_features(conn, rows)
    write_csv(
        RAW_DATA_DIR.parent / "processed" / "features.csv",
        [row.as_dict() for row in rows],
        list(rows[0].as_dict().keys()) if rows else [],
    )
    conn.close()


if __name__ == "__main__":
    main()
