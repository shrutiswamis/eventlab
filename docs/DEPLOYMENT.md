# Free Deployment Guide

The simplest free deployment target is Streamlit Community Cloud.

## Prepare The Repository

For easiest deployment, publish `eventlab/` as its own GitHub repository with these files at the repository root:

```text
README.md
requirements.txt
pyproject.toml
src/
data/
docs/
```

`requirements.txt` includes `-e .`, so the platform installs the local `eventlab` package before running the Streamlit app.

## Streamlit Community Cloud

1. Push the EventLab repo to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app from the GitHub repo.
4. Set the main file path:

```text
src/eventlab/dashboard/streamlit_app.py
```

5. Deploy.

## Data Refresh Options

Free/simple:

- The dashboard reads committed seed/processed data.
- Users click `Refresh public data` in the sidebar.

Stronger:

- Add a scheduled GitHub Action that runs:

```sh
PYTHONPATH=src python -m eventlab.scripts.run_pipeline --live
```

- Commit refreshed CSV artifacts or upload them to a free database/storage layer.

## Important Limitation

Free public data is not guaranteed to be complete at every moment.

This project handles that by writing `data/processed/data_sources.csv`, which reports:

- source name
- live/fallback/error status
- rows found
- fetch timestamp
- detail message

That source transparency is part of the project design.

