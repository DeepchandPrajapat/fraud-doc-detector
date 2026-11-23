"""Stage 6: risk fusion. V1 placeholder: hard rules + noisy-OR over signal weights.
Weights and thresholds are tuned once modules produce signals on the test set."""
from __future__ import annotations

from fdd.schemas import Severity, Signal, Verdict

SEVERITY_WEIGHT = {
    Severity.POSITIVE: 0.0, Severity.INFO: 0.0, Severity.LOW: 0.15,
    Severity.MEDIUM: 0.35, Severity.HIGH: 0.65, Severity.CRITICAL: 0.95,
}
REVIEW_AT = 0.30
REJECT_AT = 0.85


def score_signals(signals: list[Signal]) -> tuple[float, Verdict]:
    # noisy-OR: independent signals reinforce each other without exceeding 1
    p_clean = 1.0
    for s in signals:
        p_clean *= 1 - SEVERITY_WEIGHT[s.severity] * s.confidence
    score = round(1 - p_clean, 3)

    if any(s.severity == Severity.CRITICAL for s in signals):
        return max(score, REJECT_AT), Verdict.REJECT   # suggested; HR confirms
    if score >= REJECT_AT:
        return score, Verdict.REJECT
    if score >= REVIEW_AT:
        return score, Verdict.REVIEW
    return score, Verdict.PASS
