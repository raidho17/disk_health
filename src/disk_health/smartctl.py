from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

from .models import HealthMetrics


SMARTCTL_OK_CODES = {0, 2, 4, 8, 16, 32, 64, 128}

_SMARTCTL_PATH: Optional[str] = None


def has_smartctl() -> bool:
    return _find_smartctl() is not None


def _find_smartctl() -> Optional[str]:
    global _SMARTCTL_PATH
    if _SMARTCTL_PATH:
        return _SMARTCTL_PATH
    from shutil import which

    path = which("smartctl")
    if path:
        _SMARTCTL_PATH = path
        return path
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\smartmontools\bin\smartctl.exe",
            r"C:\Program Files\smartmontools\smartctl.exe",
            r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe",
            r"C:\Program Files (x86)\smartmontools\smartctl.exe",
        ]
        for c in candidates:
            if Path(c).is_file():
                _SMARTCTL_PATH = c
                return c
    return None


def _run_smartctl(device: str, dev_type: Optional[str] = None) -> Dict[str, Any]:
    exe = _find_smartctl()
    if not exe:
        raise RuntimeError("smartctl not found in PATH")
    cmd = [exe, "-a", "-j"]
    if dev_type:
        cmd.extend(["-d", dev_type])
    cmd.append(device)
    # smartctl return codes are a bitmask; non-zero can still include valid JSON
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout.strip():
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"smartctl returned non-JSON output for {device}")
    raise RuntimeError(proc.stderr.strip() or f"smartctl failed for {device}")


def _run_smartctl_info(device: str, dev_type: Optional[str]) -> Dict[str, Any]:
    exe = _find_smartctl()
    if not exe:
        raise RuntimeError("smartctl not found in PATH")
    cmd = [exe, "-i", "-j"]
    if dev_type:
        cmd.extend(["-d", dev_type])
    cmd.append(device)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout.strip():
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"smartctl returned non-JSON output for {device}")
    raise RuntimeError(proc.stderr.strip() or f"smartctl failed for {device}")


def _scan_open_devices() -> List[Tuple[str, str]]:
    exe = _find_smartctl()
    if not exe:
        return []
    cmd = [exe, "--scan-open"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        return []
    result: List[Tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "-d":
            result.append((parts[0], parts[2]))
    return result


def _extract_id(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    model = data.get("model_name") or data.get("model_number")
    serial = data.get("serial_number")
    capacity = None
    if isinstance(data.get("user_capacity"), dict):
        capacity = data["user_capacity"].get("bytes")
    return (
        str(model) if model is not None else None,
        str(serial) if serial is not None else None,
        int(capacity) if capacity is not None else None,
    )


def _has_smart_fields(data: Dict[str, Any]) -> bool:
    if "ata_smart_attributes" in data:
        return True
    if "nvme_smart_health_information_log" in data:
        return True
    if "smart_status" in data or "temperature" in data:
        return True
    return False


def _get_attr_value(attr: Dict[str, Any]) -> Optional[int]:
    raw = attr.get("raw", {})
    if isinstance(raw, dict):
        val = raw.get("value")
    else:
        val = raw
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def get_smart_health(
    device: str,
    model: Optional[str] = None,
    serial: Optional[str] = None,
    size_bytes: Optional[int] = None,
) -> HealthMetrics:
    data = _run_smartctl(device)
    if (
        platform.system() == "Windows"
        and device.startswith("//./PhysicalDrive")
        and not _has_smart_fields(data)
    ):
        candidates = _scan_open_devices()
        if candidates:
            best = None
            best_score = -1
            for dev_path, dev_type in candidates:
                try:
                    info = _run_smartctl_info(dev_path, dev_type)
                except Exception:
                    continue
                cand_model, cand_serial, cand_size = _extract_id(info)
                score = 0
                if serial and cand_serial and serial.strip().lower() == cand_serial.strip().lower():
                    score += 3
                if model and cand_model and model.strip().lower() == cand_model.strip().lower():
                    score += 2
                if size_bytes and cand_size:
                    delta = abs(size_bytes - cand_size)
                    if delta <= max(1024 * 1024 * 10, int(size_bytes * 0.01)):
                        score += 1
                if score > best_score:
                    best_score = score
                    best = (dev_path, dev_type)
            if best is None and len(candidates) == 1:
                best = candidates[0]
            if best is not None:
                data = _run_smartctl(best[0], best[1])

    passed = None
    if isinstance(data.get("smart_status"), dict):
        passed = data["smart_status"].get("passed")

    temperature = None
    if "temperature" in data and isinstance(data["temperature"], dict):
        temperature = data["temperature"].get("current")
    if temperature is None and "ata_smart_attributes" in data:
        table = data["ata_smart_attributes"].get("table", [])
        for attr in table:
            if attr.get("id") in (190, 194):
                temperature = _get_attr_value(attr)
                if temperature is not None:
                    break

    reallocated = None
    pending = None
    uncorrectable = None
    power_on_hours = None
    load_cycle_count = None
    start_stop_count = None
    power_cycle_count = None
    if "ata_smart_attributes" in data:
        table = data["ata_smart_attributes"].get("table", [])
        for attr in table:
            if attr.get("id") == 5:
                reallocated = _get_attr_value(attr)
            elif attr.get("id") == 9:
                power_on_hours = _get_attr_value(attr)
            elif attr.get("id") == 193:
                load_cycle_count = _get_attr_value(attr)
            elif attr.get("id") == 4:
                start_stop_count = _get_attr_value(attr)
            elif attr.get("id") == 12:
                power_cycle_count = _get_attr_value(attr)
            elif attr.get("id") == 197:
                pending = _get_attr_value(attr)
            elif attr.get("id") == 198:
                uncorrectable = _get_attr_value(attr)

    media_errors = None
    error_log_entries = None
    critical_warning = None
    if "nvme_smart_health_information_log" in data:
        nvme = data["nvme_smart_health_information_log"]
        media_errors = nvme.get("media_errors")
        error_log_entries = nvme.get("num_err_log_entries")
        critical_warning = nvme.get("critical_warning")
        if temperature is None:
            temperature = nvme.get("temperature")
        if power_on_hours is None:
            poh = nvme.get("power_on_hours")
            if isinstance(poh, dict):
                power_on_hours = poh.get("hours")
            else:
                power_on_hours = poh

    return HealthMetrics(
        passed=passed,
        temperature_c=temperature,
        temperature_max_c=None,
        power_on_hours=power_on_hours,
        load_cycle_count=load_cycle_count,
        start_stop_count=start_stop_count,
        power_cycle_count=power_cycle_count,
        reallocated_sectors=reallocated,
        pending_sectors=pending,
        uncorrectable_sectors=uncorrectable,
        media_errors=media_errors,
        error_log_entries=error_log_entries,
        critical_warning=critical_warning,
        flush_latency_max_ms=None,
        write_latency_max_ms=None,
        read_latency_max_ms=None,
    )
