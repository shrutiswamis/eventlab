from __future__ import annotations

import unittest

from eventlab.models.calibration import brier_score, calibration_curve, log_loss


class CalibrationTest(unittest.TestCase):
    def test_metrics_are_computed(self) -> None:
        predictions = [0.1, 0.7, 0.8, 0.35]
        outcomes = [0, 1, 1, 0]

        self.assertAlmostEqual(brier_score(predictions, outcomes), 0.065625)
        self.assertGreater(log_loss(predictions, outcomes), 0.0)

    def test_calibration_curve_preserves_count(self) -> None:
        predictions = [0.1, 0.7, 0.8, 0.35]
        outcomes = [0, 1, 1, 0]

        curve = calibration_curve(predictions, outcomes, bins=4)

        self.assertEqual(sum(row.count for row in curve), len(predictions))


if __name__ == "__main__":
    unittest.main()
