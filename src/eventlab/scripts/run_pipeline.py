from __future__ import annotations

import argparse

from eventlab.analysis.backtest import run_backtest
from eventlab.analysis.mispricing import scan_mispricings
from eventlab.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from eventlab.db.load_data import (
    connect_sqlite,
    initialize_sqlite,
    load_event_records,
    load_market_price_records,
    load_market_records,
    load_seed_data,
    reset_tables,
)
from eventlab.features.build_features import build_feature_rows, build_feature_rows_from_database, persist_features
from eventlab.ingestion.public_live_data import build_public_live_dataset
from eventlab.models.bayesian_pricer import BayesianFedCutPricer, PricingEvidence
from eventlab.utils import write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EventLab pricing pipeline.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt public Polymarket/FRED ingestion; fall back to bundled seed data when unavailable.",
    )
    args = parser.parse_args()

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_sqlite()
    initialize_sqlite(conn)
    reset_tables(conn)
    source_rows: list[dict[str, object]] = []

    if args.live:
        dataset = build_public_live_dataset()
        load_market_records(conn, dataset.markets)
        load_event_records(conn, dataset.events)
        load_market_price_records(conn, dataset.market_prices)
        conn.commit()
        feature_rows = build_feature_rows_from_database(conn, dataset.macro)
        source_rows = [report.as_dict() for report in dataset.reports]
    else:
        load_seed_data(conn)
        feature_rows = build_feature_rows()
        source_rows = [
            {
                "source": "eventlab_seed_data",
                "status": "seed",
                "rows": len(feature_rows),
                "detail": "Bundled CSV data; deterministic demo mode.",
                "fetched_at": "",
            }
        ]

    persist_features(conn, feature_rows)
    write_csv(
        PROCESSED_DATA_DIR / "features.csv",
        [row.as_dict() for row in feature_rows],
        [
            "event_id",
            "timestamp",
            "cpi_surprise",
            "unemployment_rate",
            "unemployment_change",
            "fed_funds_implied_prob",
            "fomc_tone_score",
            "days_to_event",
        ],
    )
    write_csv(PROCESSED_DATA_DIR / "data_sources.csv", source_rows, ["source", "status", "rows", "detail", "fetched_at"])

    prediction_rows = generate_predictions(conn)
    write_csv(
        PROCESSED_DATA_DIR / "model_predictions.csv",
        prediction_rows,
        [
            "event_id",
            "timestamp",
            "model_probability",
            "lower_ci",
            "upper_ci",
            "market_probability",
            "edge",
            "signal",
        ],
    )

    mispricings = [row.as_dict() for row in scan_mispricings(conn)]
    write_csv(
        PROCESSED_DATA_DIR / "mispricing_scanner.csv",
        mispricings,
        ["event_id", "event_name", "model_probability", "market_probability", "edge", "signal"],
    )

    summary, trades, curve = run_backtest(RAW_DATA_DIR / "historical_fomc_training.csv")
    write_csv(PROCESSED_DATA_DIR / "backtest_summary.csv", [summary.as_dict()], list(summary.as_dict().keys()))
    write_csv(
        PROCESSED_DATA_DIR / "backtest_trades.csv",
        trades,
        ["event_id", "model_probability", "market_probability", "edge", "signal", "outcome", "pnl", "hit"],
    )
    write_csv(PROCESSED_DATA_DIR / "calibration_curve.csv", curve, ["lower", "upper", "count", "mean_prediction", "empirical_rate"])

    print("EventLab pipeline complete")
    print(f"Mode: {'hybrid live' if args.live else 'seed'}")
    print(f"SQLite database: {PROCESSED_DATA_DIR / 'eventlab.sqlite'}")
    print(f"Predictions: {PROCESSED_DATA_DIR / 'model_predictions.csv'}")
    print(f"Data sources: {PROCESSED_DATA_DIR / 'data_sources.csv'}")
    print(f"Backtest summary: {summary.as_dict()}")
    conn.close()


def generate_predictions(conn) -> list[dict[str, object]]:
    pricer = BayesianFedCutPricer()
    rows = conn.execute(
        """
        SELECT f.event_id, f.timestamp, f.cpi_surprise, f.unemployment_rate, f.unemployment_change,
               f.fed_funds_implied_prob, f.fomc_tone_score, f.days_to_event, mp.mid_price
        FROM features f
        JOIN events e ON e.event_id = f.event_id
        JOIN market_prices mp ON mp.market_id = e.market_id AND mp.timestamp = f.timestamp
        ORDER BY f.event_id
        """
    ).fetchall()

    output: list[dict[str, object]] = []
    for row in rows:
        evidence = PricingEvidence(
            cpi_surprise=float(row["cpi_surprise"]),
            unemployment_rate=float(row["unemployment_rate"]),
            unemployment_change=float(row["unemployment_change"]),
            fed_funds_implied_prob=float(row["fed_funds_implied_prob"]),
            fomc_tone_score=float(row["fomc_tone_score"]),
            days_to_event=int(row["days_to_event"]),
            market_probability=float(row["mid_price"]),
        )
        prediction = pricer.predict(evidence)
        prediction_row = {
            "event_id": row["event_id"],
            "timestamp": row["timestamp"],
            "model_probability": prediction.model_probability,
            "lower_ci": prediction.lower_ci,
            "upper_ci": prediction.upper_ci,
            "market_probability": prediction.market_probability,
            "edge": prediction.edge,
            "signal": prediction.signal,
        }
        output.append(prediction_row)
        conn.execute(
            """
            INSERT OR REPLACE INTO model_predictions
            (event_id, timestamp, model_probability, lower_ci, upper_ci, market_probability, edge, signal)
            VALUES
            (:event_id, :timestamp, :model_probability, :lower_ci, :upper_ci, :market_probability, :edge, :signal)
            """,
            prediction_row,
        )
    conn.commit()
    return output


if __name__ == "__main__":
    main()
