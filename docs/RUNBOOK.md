# EventLab Runbook

This runbook explains how to run EventLab locally, refresh public data, inspect outputs, and launch the dashboard.

## 1. Start From The Project Folder

```sh
cd /Users/shrutiswami/Documents/Playground/eventlab
```

## 2. Use The Local Virtual Environment

If `.venv` already exists:

```sh
source .venv/bin/activate
```

If you need to recreate it:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 3. Run Deterministic Seed Mode

Seed mode uses the bundled sample market and macro CSV files. It is best for demos when you need stable output.

```sh
PYTHONPATH=src python -m eventlab.scripts.run_pipeline
```

## 4. Run Hybrid Live Mode

Hybrid live mode attempts public data ingestion:

- Polymarket Gamma API for active market prices
- BLS public API for unemployment and CPI
- bundled fallback data when public data is unavailable or no Fed-rate markets are found

```sh
PYTHONPATH=src python -m eventlab.scripts.run_pipeline --live
```

## 5. Inspect Generated Outputs

```sh
ls data/processed
```

Important files:

```text
data_sources.csv
features.csv
model_predictions.csv
mispricing_scanner.csv
backtest_summary.csv
backtest_trades.csv
calibration_curve.csv
eventlab.sqlite
```

View the latest source status:

```sh
cat data/processed/data_sources.csv
```

View the latest model predictions:

```sh
cat data/processed/model_predictions.csv
```

## 6. Launch The Dashboard

```sh
PYTHONPATH=src streamlit run src/eventlab/dashboard/streamlit_app.py
```

If Streamlit is not on your shell path, use the venv executable directly:

```sh
env PYTHONPATH=src .venv/bin/streamlit run src/eventlab/dashboard/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

## 7. Run Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests
```

Expected result:

```text
Ran 5 tests
OK
```

