from __future__ import annotations

from dataclasses import dataclass

from eventlab.models.bayesian_pricer import BayesianFedCutPricer, PricingEvidence
from eventlab.models.calibration import brier_score, calibration_curve, log_loss
from eventlab.utils import read_csv


@dataclass(frozen=True)
class BacktestSummary:
    n_events: int
    n_trades: int
    hit_rate: float
    average_edge: float
    brier_score: float
    log_loss: float
    hypothetical_pnl: float

    def as_dict(self) -> dict[str, object]:
        return {
            "n_events": self.n_events,
            "n_trades": self.n_trades,
            "hit_rate": round(self.hit_rate, 4),
            "average_edge": round(self.average_edge, 4),
            "brier_score": round(self.brier_score, 4),
            "log_loss": round(self.log_loss, 4),
            "hypothetical_pnl": round(self.hypothetical_pnl, 4),
        }


def run_backtest(training_csv, edge_threshold: float = 0.05, fee_per_contract: float = 0.01) -> tuple[BacktestSummary, list[dict[str, object]], list[dict[str, object]]]:
    rows = read_csv(training_csv)
    pricer = BayesianFedCutPricer(draws=1500, seed=19)
    predictions: list[float] = []
    outcomes: list[int] = []
    trades: list[dict[str, object]] = []

    for row in rows:
        market_probability = float(row["market_probability"])
        evidence = PricingEvidence(
            cpi_surprise=float(row["cpi_surprise"]),
            unemployment_rate=float(row["unemployment_rate"]),
            unemployment_change=float(row["unemployment_change"]),
            fed_funds_implied_prob=float(row["fed_funds_implied_prob"]),
            fomc_tone_score=float(row["fomc_tone_score"]),
            days_to_event=int(row["days_to_event"]),
            market_probability=market_probability,
        )
        prediction = pricer.predict(evidence)
        outcome = int(row["outcome"])
        predictions.append(prediction.model_probability)
        outcomes.append(outcome)

        if abs(prediction.edge) >= edge_threshold:
            pnl = trade_pnl(prediction.edge, market_probability, outcome, fee_per_contract)
            trades.append(
                {
                    "event_id": row["event_id"],
                    "model_probability": prediction.model_probability,
                    "market_probability": market_probability,
                    "edge": prediction.edge,
                    "signal": prediction.signal,
                    "outcome": outcome,
                    "pnl": round(pnl, 4),
                    "hit": int(pnl > 0),
                }
            )

    hit_rate = sum(int(trade["hit"]) for trade in trades) / len(trades) if trades else 0.0
    average_edge = sum(float(trade["edge"]) for trade in trades) / len(trades) if trades else 0.0
    summary = BacktestSummary(
        n_events=len(rows),
        n_trades=len(trades),
        hit_rate=hit_rate,
        average_edge=average_edge,
        brier_score=brier_score(predictions, outcomes),
        log_loss=log_loss(predictions, outcomes),
        hypothetical_pnl=sum(float(trade["pnl"]) for trade in trades),
    )
    curve = [row.as_dict() for row in calibration_curve(predictions, outcomes, bins=5)]
    return summary, trades, curve


def trade_pnl(edge: float, market_probability: float, outcome: int, fee: float) -> float:
    """One-contract PnL for buying YES on positive edge or selling/shorting YES on negative edge."""
    if edge > 0:
        return (outcome - market_probability) - fee
    return (market_probability - outcome) - fee

