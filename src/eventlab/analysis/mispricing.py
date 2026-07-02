from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from eventlab.db.load_data import connect_sqlite


@dataclass(frozen=True)
class Mispricing:
    event_id: str
    event_name: str
    model_probability: float
    market_probability: float
    edge: float
    signal: str

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "model_probability": self.model_probability,
            "market_probability": self.market_probability,
            "edge": self.edge,
            "signal": self.signal,
        }


def scan_mispricings(conn: sqlite3.Connection, min_abs_edge: float = 0.0) -> list[Mispricing]:
    rows = conn.execute(
        """
        SELECT e.event_id, e.event_name, p.model_probability, p.market_probability, p.edge, p.signal
        FROM model_predictions p
        JOIN events e ON e.event_id = p.event_id
        WHERE ABS(p.edge) >= ?
        ORDER BY ABS(p.edge) DESC
        """,
        (min_abs_edge,),
    ).fetchall()
    return [
        Mispricing(
            event_id=row["event_id"],
            event_name=row["event_name"],
            model_probability=float(row["model_probability"]),
            market_probability=float(row["market_probability"]),
            edge=float(row["edge"]),
            signal=row["signal"],
        )
        for row in rows
    ]


def main() -> None:
    conn = connect_sqlite()
    for row in scan_mispricings(conn, min_abs_edge=0.05):
        print(row)
    conn.close()


if __name__ == "__main__":
    main()

