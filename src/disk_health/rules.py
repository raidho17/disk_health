from __future__ import annotations

from typing import List

from .models import HealthMetrics, RiskAssessment


def evaluate_risk(metrics: HealthMetrics) -> RiskAssessment:
    score = 0
    reasons: List[str] = []
    recommendations: List[str] = []

    if metrics.passed is False:
        score += 70
        reasons.append("SMART overall health check FAILED")

    def add_if(value, threshold, points, reason):
        nonlocal score
        if value is None:
            return
        if value >= threshold:
            score += points
            reasons.append(reason)

    add_if(metrics.reallocated_sectors, 1, 30, "Reallocated sectors detected")
    add_if(metrics.pending_sectors, 1, 40, "Pending sectors detected")
    add_if(metrics.uncorrectable_sectors, 1, 40, "Uncorrectable sectors detected")
    add_if(metrics.media_errors, 1, 40, "Media errors detected (NVMe)")
    add_if(metrics.error_log_entries, 1, 10, "Error log entries detected (NVMe)")
    add_if(metrics.critical_warning, 1, 50, "NVMe critical warning flag set")

    if metrics.temperature_c is not None:
        if metrics.temperature_c >= 60:
            score += 20
            reasons.append("High temperature (>= 60C)")
        elif metrics.temperature_c >= 55:
            score += 10
            reasons.append("Elevated temperature (>= 55C)")

    if metrics.temperature_max_c is not None and metrics.temperature_max_c >= 70:
        score += 15
        reasons.append("Temperature max high (>= 70C)")

    if metrics.start_stop_count is not None:
        if metrics.start_stop_count >= 65000:
            score += 25
            reasons.append("Start/Stop count saturated (>= 65535)")
        elif metrics.start_stop_count >= 50000:
            score += 15
            reasons.append("High Start/Stop count (>= 50000)")

    if metrics.load_cycle_count is not None:
        if metrics.load_cycle_count >= 300000:
            score += 20
            reasons.append("High Load/Unload count (>= 300000)")

    if metrics.write_latency_max_ms is not None and metrics.write_latency_max_ms >= 1000:
        score += 20
        reasons.append("High write latency max (>= 1000 ms)")

    if metrics.flush_latency_max_ms is not None and metrics.flush_latency_max_ms >= 1000:
        score += 20
        reasons.append("High flush latency max (>= 1000 ms)")

    if metrics.read_latency_max_ms is not None and metrics.read_latency_max_ms >= 1000:
        score += 15
        reasons.append("High read latency max (>= 1000 ms)")

    if score >= 100:
        score = 100

    if score >= 70:
        level = "CRITICAL"
        recommendations.append("Back up data immediately")
        recommendations.append("Plan drive replacement")
    elif score >= 40:
        level = "WARNING"
        recommendations.append("Back up important data soon")
        recommendations.append("Monitor SMART attributes")
    else:
        level = "OK"
        recommendations.append("No immediate action needed")

    if metrics.temperature_c is not None and metrics.temperature_c >= 55:
        recommendations.append("Improve cooling or airflow")

    return RiskAssessment(score=score, level=level, reasons=reasons, recommendations=recommendations)
