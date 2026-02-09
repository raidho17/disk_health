from __future__ import annotations

import sys
import json
from typing import List

from PySide6 import QtCore, QtWidgets

from .models import DiskInfo, RiskAssessment, HealthMetrics
from .platform import get_disks
from .rules import evaluate_risk
from .smartctl import get_smart_health, has_smartctl


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Disk Health MVP")
        self.resize(960, 540)

        self.status_label = QtWidgets.QLabel("")
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan)
        self.export_json_button = QtWidgets.QPushButton("Export JSON")
        self.export_json_button.clicked.connect(self.export_json)
        self.export_csv_button = QtWidgets.QPushButton("Export CSV")
        self.export_csv_button.clicked.connect(self.export_csv)
        self._last_report = None

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.scan_button)
        header.addWidget(self.export_json_button)
        header.addWidget(self.export_csv_button)
        header.addStretch(1)
        header.addWidget(self.status_label)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(14)
        self.tree.setHeaderLabels(
            [
                "Disk/Volume",
                "Model",
                "Serial",
                "Size",
                "Temp (C)",
                "Temp Max (C)",
                "Power-On Hours",
                "Power-On Years",
                "Load/Unload",
                "Start/Stop",
                "Write Lat Max (ms)",
                "Flush Lat Max (ms)",
                "Risk",
                "Notes",
            ]
        )
        self.tree.setAlternatingRowColors(True)

        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.addLayout(header)
        layout.addWidget(self.tree)
        self.setCentralWidget(root)

        self._set_status("Ready")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def scan(self) -> None:
        self.tree.clear()
        if not has_smartctl():
            self._set_status("smartctl not found in PATH")
        else:
            self._set_status("Scanning...")

        try:
            disks = get_disks()
        except Exception as exc:
            self._set_status(f"Disk scan failed: {exc}")
            return

        report = []
        for disk in disks:
            risk, notes, metrics = self._risk_for_disk(disk)
            item = QtWidgets.QTreeWidgetItem(
                [
                    disk.device,
                    disk.model or "",
                    disk.serial or "",
                    _fmt_bytes(disk.size_bytes),
                    _fmt_temp(metrics.temperature_c) if metrics else "",
                    _fmt_int(metrics.temperature_max_c) if metrics else "",
                    _fmt_int(metrics.power_on_hours) if metrics else "",
                    _fmt_years(metrics.power_on_hours) if metrics else "",
                    _fmt_int(metrics.load_cycle_count) if metrics else "",
                    _fmt_int(metrics.start_stop_count) if metrics else "",
                    _fmt_int(metrics.write_latency_max_ms) if metrics else "",
                    _fmt_int(metrics.flush_latency_max_ms) if metrics else "",
                    risk.level,
                    notes,
                ]
            )
            _apply_risk_color(item, risk.level)
            self.tree.addTopLevelItem(item)

            for vol in disk.volumes:
                vitem = QtWidgets.QTreeWidgetItem(
                    [
                        vol.mountpoint,
                        vol.label or "",
                        "",
                        _fmt_bytes(vol.size_bytes),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                item.addChild(vitem)

            report.append(self._disk_report(disk, risk, notes, metrics))

        self.tree.expandAll()
        self._last_report = report
        self._set_status("Done")

    def _risk_for_disk(
        self, disk: DiskInfo
    ) -> tuple[RiskAssessment, str, "HealthMetrics | None"]:
        metrics = None
        smart_error = None
        if has_smartctl():
            try:
                metrics = get_smart_health(
                    disk.device,
                    model=disk.model,
                    serial=disk.serial,
                    size_bytes=disk.size_bytes,
                )
            except Exception as exc:
                smart_error = str(exc)
        else:
            smart_error = "SMART unavailable"

        os_metrics = _metrics_from_os(disk)
        metrics = _merge_metrics(metrics, os_metrics)

        if metrics is None:
            return RiskAssessment(0, "UNKNOWN", [], []), smart_error or "No data", None

        risk = evaluate_risk(metrics)
        notes = "; ".join(risk.reasons) if risk.reasons else "No issues"
        if smart_error and not risk.reasons:
            notes = smart_error
        return risk, notes, metrics

    def _disk_report(
        self,
        disk: DiskInfo,
        risk: RiskAssessment,
        notes: str,
        metrics: "HealthMetrics | None",
    ) -> dict:
        return {
            "device": disk.device,
            "model": disk.model,
            "serial": disk.serial,
            "size_bytes": disk.size_bytes,
            "smart": {
                "temperature_c": metrics.temperature_c if metrics else None,
                "temperature_max_c": metrics.temperature_max_c if metrics else None,
                "power_on_hours": metrics.power_on_hours if metrics else None,
                "power_on_years": _years(metrics.power_on_hours) if metrics else None,
                "load_cycle_count": metrics.load_cycle_count if metrics else None,
                "start_stop_count": metrics.start_stop_count if metrics else None,
                "power_cycle_count": metrics.power_cycle_count if metrics else None,
                "flush_latency_max_ms": metrics.flush_latency_max_ms if metrics else None,
                "write_latency_max_ms": metrics.write_latency_max_ms if metrics else None,
                "read_latency_max_ms": metrics.read_latency_max_ms if metrics else None,
            },
            "os": {
                "temperature_c": disk.os_temperature_c,
                "temperature_max_c": disk.os_temperature_max_c,
                "power_on_hours": disk.os_power_on_hours,
                "load_cycle_count": disk.os_load_cycle_count,
                "start_stop_count": disk.os_start_stop_count,
                "flush_latency_max_ms": disk.os_flush_latency_max_ms,
                "write_latency_max_ms": disk.os_write_latency_max_ms,
                "read_latency_max_ms": disk.os_read_latency_max_ms,
            },
            "risk": {
                "level": risk.level,
                "score": risk.score,
                "reasons": risk.reasons,
                "recommendations": risk.recommendations,
                "notes": notes,
            },
            "volumes": [
                {
                    "mountpoint": v.mountpoint,
                    "label": v.label,
                    "size_bytes": v.size_bytes,
                    "free_bytes": v.free_bytes,
                }
                for v in disk.volumes
            ],
        }

    def export_json(self) -> None:
        if not self._last_report:
            self._set_status("Nothing to export. Run Scan first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export JSON", "disk_health_report.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._last_report, f, ensure_ascii=False, indent=2)
            self._set_status(f"Exported: {path}")
        except Exception as exc:
            self._set_status(f"Export failed: {exc}")

    def export_csv(self) -> None:
        if not self._last_report:
            self._set_status("Nothing to export. Run Scan first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export CSV", "disk_health_report.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "device",
                        "model",
                        "serial",
                        "size_bytes",
                        "temperature_c",
                        "temperature_max_c",
                        "power_on_hours",
                        "power_on_years",
                        "load_cycle_count",
                        "start_stop_count",
                        "write_latency_max_ms",
                        "flush_latency_max_ms",
                        "risk_level",
                        "risk_score",
                        "notes",
                        "volume_mountpoint",
                        "volume_label",
                        "volume_size_bytes",
                        "volume_free_bytes",
                    ]
                )
                for d in self._last_report:
                    vols = d.get("volumes") or [None]
                    for v in vols:
                        writer.writerow(
                            [
                                d.get("device"),
                                d.get("model"),
                                d.get("serial"),
                                d.get("size_bytes"),
                                d.get("smart", {}).get("temperature_c"),
                                d.get("smart", {}).get("temperature_max_c"),
                                d.get("smart", {}).get("power_on_hours"),
                                d.get("smart", {}).get("power_on_years"),
                                d.get("smart", {}).get("load_cycle_count"),
                                d.get("smart", {}).get("start_stop_count"),
                                d.get("smart", {}).get("write_latency_max_ms"),
                                d.get("smart", {}).get("flush_latency_max_ms"),
                                d.get("risk", {}).get("level"),
                                d.get("risk", {}).get("score"),
                                d.get("risk", {}).get("notes"),
                                (v or {}).get("mountpoint"),
                                (v or {}).get("label"),
                                (v or {}).get("size_bytes"),
                                (v or {}).get("free_bytes"),
                            ]
                        )
            self._set_status(f"Exported: {path}")
        except Exception as exc:
            self._set_status(f"Export failed: {exc}")


def _apply_risk_color(item: QtWidgets.QTreeWidgetItem, level: str) -> None:
    if level == "CRITICAL":
        color = QtCore.Qt.GlobalColor.red
    elif level == "WARNING":
        color = QtCore.Qt.GlobalColor.darkYellow
    elif level == "OK":
        color = QtCore.Qt.GlobalColor.darkGreen
    else:
        color = QtCore.Qt.GlobalColor.gray

    for i in range(item.columnCount()):
        item.setForeground(i, color)


def _fmt_bytes(value: int | None) -> str:
    if not value:
        return ""
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _fmt_temp(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value}"


def _fmt_int(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value}"


def _years(hours: int | None) -> float | None:
    if hours is None:
        return None
    return round(hours / 24 / 365, 2)


def _fmt_years(hours: int | None) -> str:
    value = _years(hours)
    if value is None:
        return ""
    return f"{value}"


def _metrics_from_os(disk: DiskInfo) -> "HealthMetrics | None":
    if (
        disk.os_temperature_c is None
        and disk.os_temperature_max_c is None
        and disk.os_power_on_hours is None
        and disk.os_load_cycle_count is None
        and disk.os_start_stop_count is None
        and disk.os_flush_latency_max_ms is None
        and disk.os_write_latency_max_ms is None
        and disk.os_read_latency_max_ms is None
    ):
        return None
    return HealthMetrics(
        passed=None,
        temperature_c=disk.os_temperature_c,
        temperature_max_c=disk.os_temperature_max_c,
        power_on_hours=disk.os_power_on_hours,
        load_cycle_count=disk.os_load_cycle_count,
        start_stop_count=disk.os_start_stop_count,
        power_cycle_count=None,
        reallocated_sectors=None,
        pending_sectors=None,
        uncorrectable_sectors=None,
        media_errors=None,
        error_log_entries=None,
        critical_warning=None,
        flush_latency_max_ms=disk.os_flush_latency_max_ms,
        write_latency_max_ms=disk.os_write_latency_max_ms,
        read_latency_max_ms=disk.os_read_latency_max_ms,
    )


def _merge_metrics(
    smart: "HealthMetrics | None", os_metrics: "HealthMetrics | None"
) -> "HealthMetrics | None":
    if smart is None:
        return os_metrics
    if os_metrics is None:
        return smart
    def pick(a, b):
        return a if a is not None else b

    return HealthMetrics(
        passed=smart.passed,
        temperature_c=pick(smart.temperature_c, os_metrics.temperature_c),
        temperature_max_c=pick(smart.temperature_max_c, os_metrics.temperature_max_c),
        power_on_hours=pick(smart.power_on_hours, os_metrics.power_on_hours),
        load_cycle_count=pick(smart.load_cycle_count, os_metrics.load_cycle_count),
        start_stop_count=pick(smart.start_stop_count, os_metrics.start_stop_count),
        power_cycle_count=pick(smart.power_cycle_count, os_metrics.power_cycle_count),
        reallocated_sectors=smart.reallocated_sectors,
        pending_sectors=smart.pending_sectors,
        uncorrectable_sectors=smart.uncorrectable_sectors,
        media_errors=smart.media_errors,
        error_log_entries=smart.error_log_entries,
        critical_warning=smart.critical_warning,
        flush_latency_max_ms=pick(smart.flush_latency_max_ms, os_metrics.flush_latency_max_ms),
        write_latency_max_ms=pick(smart.write_latency_max_ms, os_metrics.write_latency_max_ms),
        read_latency_max_ms=pick(smart.read_latency_max_ms, os_metrics.read_latency_max_ms),
    )


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
