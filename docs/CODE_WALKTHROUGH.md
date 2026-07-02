# Code Walkthrough

EventLab is organized as a small research platform rather than a notebook.

## Data Inputs

Bundled seed inputs live in `data/raw/`:

- `markets.csv` - contract metadata
- `events.csv` - event mapping and resolution dates
- `market_prices.csv` - YES bid/ask/mid snapshots
- `macro_observations.csv` - macro features for seed mode
- `historical_fomc_training.csv` - small backtest/calibration sample

Hybrid live mode is implemented in:

```text
src/eventlab/ingestion/public_live_data.py
```

It attempts:

- Polymarket public Gamma API for market prices
- BLS public API for unemployment and CPI
- fallback to bundled seed data if a source fails or no Fed-rate market is found

Each run writes `data/processed/data_sources.csv`, which is important because the dashboard should never hide whether a result came from live data or fallback data.

## Storage Layer

SQLite loading lives in:

```text
src/eventlab/db/load_data.py
```

The PostgreSQL-compatible schema lives in:

```text
src/eventlab/db/schema.sql
```

The main tables are:

- `markets`
- `market_prices`
- `events`
- `features`
- `model_predictions`

SQLite is used locally because it is zero-cost and easy to demo. PostgreSQL is available through `docker-compose.yml` for a stronger deployment story.

## Feature Engineering

Feature creation lives in:

```text
src/eventlab/features/build_features.py
```

Seed mode reads `macro_observations.csv`.

Hybrid live mode builds features from the database plus the latest macro snapshot:

- CPI surprise
- unemployment rate
- unemployment change
- Fed funds implied probability proxy
- FOMC tone score
- days to event

## Model

The pricer lives in:

```text
src/eventlab/models/bayesian_pricer.py
```

The contract is treated like a binary option:

```text
YES fair price ~= P(event happens)
```

The MVP model:

1. Starts with a prior probability.
2. Converts the prior to log-odds.
3. Adds evidence terms for macro and futures-style inputs.
4. Samples coefficient uncertainty.
5. Returns posterior mean, lower credible interval, upper credible interval, edge, and signal.

Signals:

- `BUY_YES` when model probability is at least 5 points above market
- `SELL_YES` when model probability is at least 5 points below market
- `NO_TRADE` otherwise

## Backtesting And Calibration

Backtest code lives in:

```text
src/eventlab/analysis/backtest.py
src/eventlab/models/calibration.py
```

It asks:

```text
When the model disagrees with the market by more than 5%, what happens?
```

Metrics:

- hit rate
- average edge
- Brier score
- log loss
- calibration curve
- hypothetical one-contract PnL after fees

## Pipeline

The main orchestration script is:

```text
src/eventlab/scripts/run_pipeline.py
```

Seed mode:

```sh
PYTHONPATH=src python -m eventlab.scripts.run_pipeline
```

Hybrid live mode:

```sh
PYTHONPATH=src python -m eventlab.scripts.run_pipeline --live
```

## Dashboard

The dashboard lives in:

```text
src/eventlab/dashboard/streamlit_app.py
```

Tabs:

- Live pricing
- Mispricing scanner
- Calibration
- Research notebook

The sidebar includes a `Refresh public data` button that reruns the live pipeline from the app.

