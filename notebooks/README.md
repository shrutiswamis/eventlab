# Research Notebooks

Use this folder for exploratory analysis after the production pipeline is in place.

Suggested notebook sequence:

1. `01_fomc_feature_audit.ipynb` - inspect CPI, unemployment, futures probabilities, and missingness.
2. `02_model_comparison.ipynb` - compare the transparent MVP pricer with PyMC logistic and hierarchical variants.
3. `03_trading_rule_backtest.ipynb` - stress-test edge thresholds, fees, and position sizing.

The production code path lives in `src/eventlab/` so the project remains more than a notebook.

