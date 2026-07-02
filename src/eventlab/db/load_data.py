from __future__ import annotations

import sqlite3
from pathlib import Path

from eventlab.config import DEFAULT_SQLITE_PATH, RAW_DATA_DIR
from eventlab.utils import read_csv


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    market_id TEXT PRIMARY KEY,
    venue TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    expiration_date TEXT NOT NULL,
    resolution_date TEXT
);

CREATE TABLE IF NOT EXISTS market_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    yes_bid REAL,
    yes_ask REAL,
    mid_price REAL NOT NULL,
    volume REAL,
    liquidity REAL,
    UNIQUE (market_id, timestamp)
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    outcome INTEGER
);

CREATE TABLE IF NOT EXISTS features (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    cpi_surprise REAL,
    unemployment_rate REAL,
    unemployment_change REAL,
    fed_funds_implied_prob REAL,
    fomc_tone_score REAL,
    days_to_event INTEGER NOT NULL,
    UNIQUE (event_id, timestamp)
);

CREATE TABLE IF NOT EXISTS model_predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    model_probability REAL NOT NULL,
    lower_ci REAL NOT NULL,
    upper_ci REAL NOT NULL,
    market_probability REAL NOT NULL,
    edge REAL NOT NULL,
    signal TEXT NOT NULL,
    UNIQUE (event_id, timestamp)
);
"""


def connect_sqlite(path: Path = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_sqlite(conn: sqlite3.Connection) -> None:
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()


def reset_tables(conn: sqlite3.Connection) -> None:
    for table in ["model_predictions", "features", "market_prices", "events", "markets"]:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def load_seed_data(conn: sqlite3.Connection, raw_dir: Path = RAW_DATA_DIR) -> None:
    load_markets(conn, raw_dir / "markets.csv")
    load_events(conn, raw_dir / "events.csv")
    load_market_prices(conn, raw_dir / "market_prices.csv")
    conn.commit()


def load_market_records(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO markets
        (market_id, venue, title, category, expiration_date, resolution_date)
        VALUES (:market_id, :venue, :title, :category, :expiration_date, :resolution_date)
        """,
        rows,
    )


def load_event_records(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO events
        (event_id, market_id, event_name, event_date, outcome)
        VALUES (:event_id, :market_id, :event_name, :event_date, :outcome)
        """,
        rows,
    )


def load_market_price_records(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO market_prices
        (market_id, timestamp, yes_bid, yes_ask, mid_price, volume, liquidity)
        VALUES (:market_id, :timestamp, :yes_bid, :yes_ask, :mid_price, :volume, :liquidity)
        """,
        rows,
    )


def load_markets(conn: sqlite3.Connection, path: Path) -> None:
    rows = read_csv(path)
    conn.executemany(
        """
        INSERT OR REPLACE INTO markets
        (market_id, venue, title, category, expiration_date, resolution_date)
        VALUES (:market_id, :venue, :title, :category, :expiration_date, :resolution_date)
        """,
        rows,
    )


def load_events(conn: sqlite3.Connection, path: Path) -> None:
    rows = []
    for row in read_csv(path):
        row["outcome"] = None if row["outcome"] == "" else int(row["outcome"])
        rows.append(row)
    conn.executemany(
        """
        INSERT OR REPLACE INTO events
        (event_id, market_id, event_name, event_date, outcome)
        VALUES (:event_id, :market_id, :event_name, :event_date, :outcome)
        """,
        rows,
    )


def load_market_prices(conn: sqlite3.Connection, path: Path) -> None:
    rows = []
    for row in read_csv(path):
        rows.append(
            {
                **row,
                "yes_bid": float(row["yes_bid"]),
                "yes_ask": float(row["yes_ask"]),
                "mid_price": float(row["mid_price"]),
                "volume": float(row["volume"]),
                "liquidity": float(row["liquidity"]),
            }
        )
    conn.executemany(
        """
        INSERT OR REPLACE INTO market_prices
        (market_id, timestamp, yes_bid, yes_ask, mid_price, volume, liquidity)
        VALUES (:market_id, :timestamp, :yes_bid, :yes_ask, :mid_price, :volume, :liquidity)
        """,
        rows,
    )


def main() -> None:
    conn = connect_sqlite()
    initialize_sqlite(conn)
    reset_tables(conn)
    load_seed_data(conn)
    conn.close()


if __name__ == "__main__":
    main()
