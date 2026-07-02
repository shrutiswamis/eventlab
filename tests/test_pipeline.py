from __future__ import annotations

import sqlite3
import unittest

from eventlab.db.load_data import initialize_sqlite, load_seed_data, reset_tables
from eventlab.features.build_features import build_feature_rows, persist_features
from eventlab.scripts.run_pipeline import generate_predictions


class PipelineTest(unittest.TestCase):
    def test_seed_pipeline_generates_predictions(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_sqlite(conn)
        reset_tables(conn)
        load_seed_data(conn)
        features = build_feature_rows()
        persist_features(conn, features)

        predictions = generate_predictions(conn)

        self.assertEqual(len(predictions), 3)
        self.assertTrue(all(0.0 <= row["model_probability"] <= 1.0 for row in predictions))
        self.assertTrue(all(row["signal"] in {"BUY_YES", "SELL_YES", "NO_TRADE"} for row in predictions))
        conn.close()


if __name__ == "__main__":
    unittest.main()

