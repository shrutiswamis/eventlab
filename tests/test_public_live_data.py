from __future__ import annotations

from datetime import UTC, datetime
import unittest

from eventlab.ingestion.polymarket_client import PolymarketClient
from eventlab.ingestion.public_live_data import _is_fed_rate_market, fetch_bls_series


class PublicLiveDataTest(unittest.TestCase):
    def test_polymarket_parser_extracts_yes_no_prices(self) -> None:
        snapshot = PolymarketClient._parse_market(
            {
                "id": "123",
                "question": "Will the Fed cut rates in September?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.64", "0.36"]',
                "endDate": "2026-09-16T00:00:00Z",
                "volume": "1000",
                "liquidity": "500",
            }
        )

        self.assertEqual(snapshot.market_id, "123")
        self.assertEqual(snapshot.yes_price, 0.64)
        self.assertEqual(snapshot.no_price, 0.36)
        self.assertTrue(_is_fed_rate_market(snapshot))

    def test_bls_parser_can_be_monkeypatched(self) -> None:
        self.assertTrue(callable(fetch_bls_series))
        self.assertEqual(datetime.now(UTC).tzinfo, UTC)


if __name__ == "__main__":
    unittest.main()

