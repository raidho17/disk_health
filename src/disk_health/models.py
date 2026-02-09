from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VolumeInfo:
    mountpoint: str
    size_bytes: Optional[int] = None
    free_bytes: Optional[int] = None
    label: Optional[str] = None


@dataclass
class DiskInfo:
    device: str
    model: Optional[str]
    serial: Optional[str]
    size_bytes: Optional[int]
    volumes: List[VolumeInfo] = field(default_factory=list)
    os_temperature_c: Optional[int] = None
    os_temperature_max_c: Optional[int] = None
    os_power_on_hours: Optional[int] = None
    os_load_cycle_count: Optional[int] = None
    os_start_stop_count: Optional[int] = None
    os_flush_latency_max_ms: Optional[int] = None
    os_write_latency_max_ms: Optional[int] = None
    os_read_latency_max_ms: Optional[int] = None


@dataclass
class HealthMetrics:
    passed: Optional[bool]
    temperature_c: Optional[int]
    temperature_max_c: Optional[int]
    power_on_hours: Optional[int]
    load_cycle_count: Optional[int]
    start_stop_count: Optional[int]
    power_cycle_count: Optional[int]
    reallocated_sectors: Optional[int]
    pending_sectors: Optional[int]
    uncorrectable_sectors: Optional[int]
    media_errors: Optional[int]
    error_log_entries: Optional[int]
    critical_warning: Optional[int]
    flush_latency_max_ms: Optional[int]
    write_latency_max_ms: Optional[int]
    read_latency_max_ms: Optional[int]


@dataclass
class RiskAssessment:
    score: int
    level: str
    reasons: List[str]
    recommendations: List[str]
