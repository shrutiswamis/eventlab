from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

try:
    import altair as alt
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as exc:
    raise SystemExit("Install dashboard dependencies with: python3 -m pip install -r requirements.txt") from exc

from eventlab.config import DEFAULT_SQLITE_PATH, PROCESSED_DATA_DIR


st.set_page_config(page_title="EventLab", page_icon="EL", layout="wide")


SIGNAL_COLORS = {
    "BUY_YES": "#14b86a",
    "SELL_YES": "#ff5f6d",
    "NO_TRADE": "#9aa4b2",
}

STATUS_COLORS = {
    "live": "#14b86a",
    "seed": "#61a5ff",
    "fallback": "#f4b740",
    "empty": "#9aa4b2",
    "error": "#ff5f6d",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --eventlab-bg: #0b1018;
            --eventlab-panel: #111827;
            --eventlab-panel-2: #151e2d;
            --eventlab-border: rgba(148, 163, 184, 0.22);
            --eventlab-text: #f8fafc;
            --eventlab-muted: #94a3b8;
            --eventlab-green: #14b86a;
            --eventlab-red: #ff5f6d;
            --eventlab-blue: #61a5ff;
            --eventlab-amber: #f4b740;
        }

        .block-container {
            padding-top: 2.1rem;
            padding-bottom: 3rem;
            max-width: 1440px;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 15% 0%, rgba(97, 165, 255, 0.12), transparent 26rem),
                linear-gradient(180deg, #0b1018 0%, #0d1320 100%);
        }

        h1, h2, h3 {
            letter-spacing: 0;
        }

        .hero {
            border: 1px solid var(--eventlab-border);
            background: linear-gradient(135deg, rgba(17, 24, 39, 0.96), rgba(21, 30, 45, 0.96));
            padding: 1.35rem 1.45rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .hero h1 {
            margin: 0 0 0.35rem 0;
            font-size: 2.25rem;
            line-height: 1.05;
        }

        .hero p {
            margin: 0;
            color: var(--eventlab-muted);
            font-size: 1rem;
        }

        .metric-card, .contract-card, .source-card, .method-panel {
            border: 1px solid var(--eventlab-border);
            background: rgba(17, 24, 39, 0.88);
            border-radius: 8px;
            padding: 1rem;
        }

        .metric-label {
            color: var(--eventlab-muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.45rem;
        }

        .metric-value {
            color: var(--eventlab-text);
            font-size: 1.55rem;
            font-weight: 720;
            line-height: 1.1;
        }

        .contract-title {
            color: var(--eventlab-text);
            font-size: 1rem;
            font-weight: 680;
            min-height: 3rem;
            line-height: 1.25;
        }

        .probability {
            color: var(--eventlab-text);
            font-size: 3rem;
            font-weight: 740;
            margin-top: 0.6rem;
            line-height: 1;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.28rem 0.62rem;
            font-weight: 700;
            font-size: 0.82rem;
            margin-top: 0.8rem;
            margin-bottom: 0.8rem;
        }

        .contract-detail {
            color: var(--eventlab-muted);
            font-size: 0.92rem;
            line-height: 1.75;
        }

        .source-name {
            color: var(--eventlab-text);
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 0.35rem;
        }

        .source-detail {
            color: var(--eventlab-muted);
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .method-panel h3 {
            margin-top: 0;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(17, 24, 39, 0.72);
            border: 1px solid var(--eventlab-border);
            border-radius: 8px;
            padding: 0.6rem 0.9rem;
        }

        .stTabs [aria-selected="true"] {
            background: rgba(97, 165, 255, 0.16);
        }

        [data-testid="stSidebar"] {
            background: #0a0f17;
            border-right: 1px solid var(--eventlab-border);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def read_sql(query: str, db_path: Path = DEFAULT_SQLITE_PATH) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


def load_predictions() -> pd.DataFrame:
    return read_sql(
        """
        SELECT e.event_name, m.venue, m.title, p.timestamp, p.model_probability,
               p.lower_ci, p.upper_ci, p.market_probability, p.edge, p.signal
        FROM model_predictions p
        JOIN events e ON e.event_id = p.event_id
        JOIN markets m ON m.market_id = e.market_id
        ORDER BY ABS(p.edge) DESC
        """
    )


def load_sources() -> pd.DataFrame:
    path = PROCESSED_DATA_DIR / "data_sources.csv"
    if not path.exists():
        return pd.DataFrame(columns=["source", "status", "rows", "detail", "fetched_at"])
    return pd.read_csv(path)


def load_csv(name: str) -> pd.DataFrame:
    path = PROCESSED_DATA_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def run_live_refresh() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "eventlab.scripts.run_pipeline", "--live"],
        cwd=PROCESSED_DATA_DIR.parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )


def format_pct(value: float) -> str:
    return f"{value:.1%}"


def format_pp(value: float) -> str:
    return f"{value * 100:+.1f} pp"


def signal_color(signal: str) -> str:
    return SIGNAL_COLORS.get(signal, SIGNAL_COLORS["NO_TRADE"])


def status_color(status: str) -> str:
    return STATUS_COLORS.get(str(status).lower(), "#9aa4b2")


def header(predictions: pd.DataFrame, sources: pd.DataFrame) -> None:
    refreshed = "Not generated"
    if not predictions.empty and "timestamp" in predictions:
        refreshed = str(predictions["timestamp"].max())
    live_count = 0 if sources.empty else int((sources["status"].astype(str).str.lower() == "live").sum())
    fallback_count = 0 if sources.empty else int((sources["status"].astype(str).str.lower().isin(["fallback", "empty", "error"])).sum())
    st.markdown(
        f"""
        <div class="hero">
            <h1>EventLab</h1>
            <p>Bayesian prediction-market pricing for Fed-rate contracts. Last refreshed: <b>{refreshed}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    summary = [
        ("Contracts", len(predictions)),
        ("Live Sources", live_count),
        ("Fallback Sources", fallback_count),
        ("Avg Abs Edge", format_pct(predictions["edge"].abs().mean()) if not predictions.empty else "0.0%"),
    ]
    for col, (label, value) in zip(cols, summary):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def sidebar(predictions: pd.DataFrame) -> tuple[list[str], float]:
    with st.sidebar:
        st.header("Controls")
        st.caption("Refresh public data or filter the current pricing view.")
        if st.button("Refresh public data", type="primary", use_container_width=True):
            with st.spinner("Refreshing public data..."):
                result = run_live_refresh()
            if result.returncode == 0:
                st.success("Public data refresh complete.")
                st.code(result.stdout)
            else:
                st.error("Refresh failed.")
                st.code(result.stderr or result.stdout)

        signals = sorted(predictions["signal"].unique()) if not predictions.empty else []
        selected = st.multiselect("Signals", signals, default=signals)
        min_edge = st.slider("Minimum absolute edge", 0.0, 0.50, 0.0, 0.01, format="%.2f")
        st.divider()
        st.caption("Open source report")
        st.code("data/processed/data_sources.csv")
        return selected, min_edge


def source_status_panel(sources: pd.DataFrame) -> None:
    st.subheader("Data Status")
    if sources.empty:
        st.info("No source report found. Run the pipeline to generate data_sources.csv.")
        return

    cols = st.columns(min(len(sources), 3))
    for idx, row in sources.iterrows():
        color = status_color(row["status"])
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="source-card">
                    <div class="source-name">{row["source"]}</div>
                    <span class="pill" style="background:{color}24;color:{color};border:1px solid {color}55;">
                        {str(row["status"]).upper()}
                    </span>
                    <div class="source-detail">{row["detail"]}</div>
                    <div class="source-detail">Rows: {row["rows"]} | Fetched: {row["fetched_at"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def pricing_cards(predictions: pd.DataFrame) -> None:
    st.subheader("Model vs Market")
    if predictions.empty:
        st.warning("No predictions available.")
        return

    cols = st.columns(3)
    for idx, row in predictions.iterrows():
        color = signal_color(row["signal"])
        with cols[idx % 3]:
            st.markdown(
                f"""
                <div class="contract-card">
                    <div class="contract-title">{row["event_name"]}</div>
                    <div class="probability">{format_pct(row["model_probability"])}</div>
                    <span class="pill" style="background:{color}24;color:{color};border:1px solid {color}55;">
                        {format_pp(row["edge"])} edge
                    </span>
                    <div class="contract-detail">
                        Market: <b>{format_pct(row["market_probability"])}</b><br>
                        Credible interval: <b>{format_pct(row["lower_ci"])} - {format_pct(row["upper_ci"])}</b><br>
                        Signal: <b style="color:{color};">{row["signal"]}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def model_vs_market_chart(predictions: pd.DataFrame) -> None:
    if predictions.empty:
        return
    chart_data = predictions[["event_name", "model_probability", "market_probability"]].melt(
        id_vars="event_name",
        var_name="series",
        value_name="probability",
    )
    chart_data["series"] = chart_data["series"].replace(
        {"model_probability": "Model", "market_probability": "Market"}
    )
    chart = (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("event_name:N", title=None, sort="-y", axis=alt.Axis(labelLimit=220)),
            y=alt.Y("probability:Q", title="Probability", axis=alt.Axis(format="%")),
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(domain=["Model", "Market"], range=["#61a5ff", "#f4b740"]),
            ),
            xOffset="series:N",
            tooltip=["event_name:N", "series:N", alt.Tooltip("probability:Q", format=".1%")],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)


def edge_chart(predictions: pd.DataFrame) -> None:
    if predictions.empty:
        return
    chart = (
        alt.Chart(predictions)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y("event_name:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)),
            x=alt.X("edge:Q", title="Model edge", axis=alt.Axis(format="%")),
            color=alt.Color(
                "signal:N",
                title=None,
                scale=alt.Scale(
                    domain=["BUY_YES", "SELL_YES", "NO_TRADE"],
                    range=[SIGNAL_COLORS["BUY_YES"], SIGNAL_COLORS["SELL_YES"], SIGNAL_COLORS["NO_TRADE"]],
                ),
            ),
            tooltip=[
                "event_name:N",
                "signal:N",
                alt.Tooltip("edge:Q", format=".1%"),
                alt.Tooltip("model_probability:Q", format=".1%"),
                alt.Tooltip("market_probability:Q", format=".1%"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def scanner_table(predictions: pd.DataFrame) -> None:
    display = predictions.copy()
    display["abs_edge"] = display["edge"].abs()
    display = display.sort_values("abs_edge", ascending=False)
    for column in ["model_probability", "lower_ci", "upper_ci", "market_probability", "edge", "abs_edge"]:
        display[column] = display[column].map(format_pct)
    st.dataframe(
        display[
            [
                "event_name",
                "venue",
                "model_probability",
                "market_probability",
                "edge",
                "lower_ci",
                "upper_ci",
                "signal",
                "timestamp",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def calibration_view() -> None:
    summary = load_csv("backtest_summary.csv")
    curve = load_csv("calibration_curve.csv")
    trades = load_csv("backtest_trades.csv")

    st.subheader("Backtest Metrics")
    if not summary.empty:
        metric_cols = st.columns(len(summary.columns))
        for col, metric in zip(metric_cols, summary.columns):
            value = summary.loc[0, metric]
            if metric in {"hit_rate", "average_edge", "brier_score", "log_loss", "hypothetical_pnl"}:
                value = f"{value:.4f}" if isinstance(value, float) else value
            col.metric(metric.replace("_", " ").title(), value)

    chart_cols = st.columns([1.1, 1])
    with chart_cols[0]:
        st.subheader("Calibration Curve")
        if not curve.empty:
            calibration = (
                alt.Chart(curve)
                .mark_line(point=True)
                .encode(
                    x=alt.X("mean_prediction:Q", title="Mean predicted probability", axis=alt.Axis(format="%")),
                    y=alt.Y("empirical_rate:Q", title="Empirical event rate", axis=alt.Axis(format="%")),
                    tooltip=[
                        alt.Tooltip("mean_prediction:Q", format=".1%"),
                        alt.Tooltip("empirical_rate:Q", format=".1%"),
                        "count:Q",
                    ],
                )
                .properties(height=310)
            )
            reference = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(
                strokeDash=[5, 5], color="#94a3b8"
            ).encode(x="x:Q", y="y:Q")
            st.altair_chart(calibration + reference, use_container_width=True)
        else:
            st.info("No calibration output found.")

    with chart_cols[1]:
        st.subheader("Backtest Trades")
        if not trades.empty:
            pnl_chart = (
                alt.Chart(trades)
                .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("event_id:N", title=None, axis=alt.Axis(labelAngle=-35)),
                    y=alt.Y("pnl:Q", title="Hypothetical PnL"),
                    color=alt.condition(alt.datum.pnl >= 0, alt.value("#14b86a"), alt.value("#ff5f6d")),
                    tooltip=["event_id:N", "signal:N", "pnl:Q", "hit:Q"],
                )
                .properties(height=310)
            )
            st.altair_chart(pnl_chart, use_container_width=True)
            st.dataframe(trades, use_container_width=True, hide_index=True)
        else:
            st.info("No trade output found.")


def research_view() -> None:
    st.subheader("Research Notebook")
    cols = st.columns(2)
    panels = [
        (
            "Problem",
            "Prediction-market YES contracts pay $1 if an event happens and $0 otherwise, so fair value is approximately the probability of the event.",
        ),
        (
            "Data",
            "The pipeline combines contract prices, CPI surprise, unemployment changes, a Fed funds probability proxy, event timing, and source-status metadata.",
        ),
        (
            "Model",
            "The MVP converts a prior into log-odds, adds interpretable evidence terms, samples coefficient uncertainty, and reports a posterior probability interval.",
        ),
        (
            "Validation",
            "The backtest tracks Brier score, log loss, calibration, edge hit rate, and simplified one-contract hypothetical PnL after fees.",
        ),
        (
            "Limitations",
            "Hybrid live mode can fall back to bundled contracts when public market APIs return no relevant Fed-rate markets. PnL is not an execution-grade trading simulation.",
        ),
        (
            "Future Work",
            "Add authenticated Kalshi ingestion, stronger Polymarket market discovery, liquidity filters, bid/ask execution, and a hierarchical PyMC model.",
        ),
    ]
    for idx, (title, body) in enumerate(panels):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="method-panel">
                    <h3>{title}</h3>
                    <p>{body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def main() -> None:
    inject_css()

    if not DEFAULT_SQLITE_PATH.exists():
        st.error("Run `PYTHONPATH=src python3 -m eventlab.scripts.run_pipeline` before opening the dashboard.")
        return

    predictions = load_predictions()
    sources = load_sources()
    selected_signals, min_edge = sidebar(predictions)
    if selected_signals:
        predictions = predictions[predictions["signal"].isin(selected_signals)]
    predictions = predictions[predictions["edge"].abs() >= min_edge]

    header(predictions, sources)

    live_tab, scanner_tab, calibration_tab, research_tab = st.tabs(
        ["Live Pricing", "Mispricing Scanner", "Calibration", "Research Notebook"]
    )

    with live_tab:
        source_status_panel(sources)
        st.divider()
        pricing_cards(predictions)
        st.divider()
        chart_cols = st.columns([1.1, 1])
        with chart_cols[0]:
            st.subheader("Model vs Market Probability")
            model_vs_market_chart(predictions)
        with chart_cols[1]:
            st.subheader("Edge by Contract")
            edge_chart(predictions)

    with scanner_tab:
        st.subheader("Contracts Ranked by Absolute Edge")
        edge_chart(predictions)
        scanner_table(predictions)

    with calibration_tab:
        calibration_view()

    with research_tab:
        research_view()


if __name__ == "__main__":
    main()
