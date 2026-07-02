from __future__ import annotations

import unittest

from eventlab.models.bayesian_pricer import BayesianFedCutPricer, PricingEvidence, classify_edge


class BayesianPricerTest(unittest.TestCase):
    def test_prediction_has_valid_probability_interval_and_edge(self) -> None:
        pricer = BayesianFedCutPricer(draws=500, seed=11)
        prediction = pricer.predict(
            PricingEvidence(
                cpi_surprise=0.18,
                unemployment_rate=4.1,
                unemployment_change=0.2,
                fed_funds_implied_prob=0.68,
                fomc_tone_score=-0.05,
                days_to_event=81,
                market_probability=0.72,
            )
        )

        self.assertGreaterEqual(prediction.model_probability, 0.0)
        self.assertLessEqual(prediction.model_probability, 1.0)
        self.assertLessEqual(prediction.lower_ci, prediction.model_probability)
        self.assertGreaterEqual(prediction.upper_ci, prediction.model_probability)
        self.assertAlmostEqual(
            prediction.edge,
            round(prediction.model_probability - prediction.market_probability, 4),
        )

    def test_edge_classification(self) -> None:
        self.assertEqual(classify_edge(0.06), "BUY_YES")
        self.assertEqual(classify_edge(-0.06), "SELL_YES")
        self.assertEqual(classify_edge(0.01), "NO_TRADE")


if __name__ == "__main__":
    unittest.main()

