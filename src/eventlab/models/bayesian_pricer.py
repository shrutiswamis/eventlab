from __future__ import annotations

import math
import random
from dataclasses import dataclass

from eventlab.utils import clamp


@dataclass(frozen=True)
class PricingEvidence:
    cpi_surprise: float
    unemployment_rate: float
    unemployment_change: float
    fed_funds_implied_prob: float
    fomc_tone_score: float
    days_to_event: int
    market_probability: float


@dataclass(frozen=True)
class PricingPrediction:
    model_probability: float
    lower_ci: float
    upper_ci: float
    market_probability: float
    edge: float
    signal: str


@dataclass(frozen=True)
class Coefficient:
    mean: float
    stddev: float


class BayesianFedCutPricer:
    """Transparent Bayesian-style pricer for Fed rate-cut prediction markets.

    The model treats each information source as evidence on the log-odds scale.
    Coefficient uncertainty is sampled directly, producing a posterior
    probability distribution and credible interval without requiring PyMC for
    the MVP pipeline.
    """

    coefficients = {
        "intercept": Coefficient(0.12, 0.08),
        "cpi_surprise": Coefficient(-0.55, 0.12),
        "unemployment_change": Coefficient(0.75, 0.12),
        "unemployment_rate_gap": Coefficient(0.18, 0.08),
        "fed_funds_logit": Coefficient(0.88, 0.04),
        "fomc_tone_score": Coefficient(-0.35, 0.08),
        "time_decay": Coefficient(-0.0012, 0.0008),
    }

    def __init__(self, prior_probability: float = 0.45, draws: int = 4000, seed: int = 7) -> None:
        self.prior_probability = clamp(prior_probability, 0.001, 0.999)
        self.draws = draws
        self.seed = seed

    def predict(self, evidence: PricingEvidence) -> PricingPrediction:
        samples = self.sample_posterior(evidence)
        mean_probability = sum(samples) / len(samples)
        lower_ci = percentile(samples, 0.05)
        upper_ci = percentile(samples, 0.95)
        edge = mean_probability - evidence.market_probability
        return PricingPrediction(
            model_probability=round(mean_probability, 4),
            lower_ci=round(lower_ci, 4),
            upper_ci=round(upper_ci, 4),
            market_probability=round(evidence.market_probability, 4),
            edge=round(edge, 4),
            signal=classify_edge(edge),
        )

    def sample_posterior(self, evidence: PricingEvidence) -> list[float]:
        rng = random.Random(self.seed)
        prior_log_odds = logit(self.prior_probability)
        futures_log_odds = logit(clamp(evidence.fed_funds_implied_prob, 0.01, 0.99))
        unemployment_rate_gap = evidence.unemployment_rate - 4.0
        samples: list[float] = []
        for _ in range(self.draws):
            beta = {
                name: rng.gauss(coef.mean, coef.stddev)
                for name, coef in self.coefficients.items()
            }
            z = (
                prior_log_odds
                + beta["intercept"]
                + beta["cpi_surprise"] * evidence.cpi_surprise
                + beta["unemployment_change"] * evidence.unemployment_change
                + beta["unemployment_rate_gap"] * unemployment_rate_gap
                + beta["fed_funds_logit"] * futures_log_odds
                + beta["fomc_tone_score"] * evidence.fomc_tone_score
                + beta["time_decay"] * max(evidence.days_to_event, 0)
            )
            samples.append(sigmoid(z))
        return samples


def classify_edge(edge: float, threshold: float = 0.05) -> str:
    if edge >= threshold:
        return "BUY_YES"
    if edge <= -threshold:
        return "SELL_YES"
    return "NO_TRADE"


def logit(probability: float) -> float:
    p = clamp(probability, 0.001, 0.999)
    return math.log(p / (1.0 - p))


def sigmoid(value: float) -> float:
    if value >= 0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * q
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return sorted_values[int(idx)]
    weight = idx - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
