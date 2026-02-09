from __future__ import annotations

import json
import platform
import subprocess
from typing import Any, Dict, List

from .models import DiskInfo, VolumeInfo


def _run_powershell_json(cmd: str) -> Any:
    ps_cmd = ["powershell", "-NoProfile", "-Command", cmd]
    proc = subprocess.run(ps_cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "PowerShell returned no output")
    return json.loads(proc.stdout)


def _windows_disks() -> List[DiskInfo]:
    disks = _run_powershell_json(
        "Get-Disk | Select-Object Number,FriendlyName,SerialNumber,Size | ConvertTo-Json -Depth 3"
    )
    parts = _run_powershell_json(
        "Get-Partition | Where-Object DriveLetter | Select-Object DiskNumber,DriveLetter | ConvertTo-Json -Depth 3"
    )
    vols = _run_powershell_json(
        "Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter,FileSystemLabel,Size,SizeRemaining | ConvertTo-Json -Depth 3"
    )
    try:
        rel = _run_powershell_json(
            "Get-PhysicalDisk | Get-StorageReliabilityCounter | "
            "Select-Object DeviceId,Temperature,TemperatureMax,PowerOnHours,"
            "LoadUnloadCycleCount,StartStopCycleCount,FlushLatencyMax,WriteLatencyMax,ReadLatencyMax | "
            "ConvertTo-Json -Depth 3"
        )
    except Exception:
        rel = []

    if isinstance(disks, dict):
        disks = [disks]
    if isinstance(parts, dict):
        parts = [parts]
    if isinstance(vols, dict):
        vols = [vols]
    if isinstance(rel, dict):
        rel = [rel]

    vol_map: Dict[str, VolumeInfo] = {}
    for v in vols:
        letter = v.get("DriveLetter")
        if not letter:
            continue
        mount = f"{letter}:\\"
        vol_map[letter] = VolumeInfo(
            mountpoint=mount,
            size_bytes=v.get("Size"),
            free_bytes=v.get("SizeRemaining"),
            label=v.get("FileSystemLabel"),
        )

    disk_to_letters: Dict[int, List[str]] = {}
    for p in parts:
        dn = p.get("DiskNumber")
        dl = p.get("DriveLetter")
        if dn is None or not dl:
            continue
        disk_to_letters.setdefault(int(dn), []).append(str(dl))

    rel_map: Dict[int, Dict[str, Any]] = {}
    for r in rel:
        if not isinstance(r, dict):
            continue
        did = r.get("DeviceId")
        if did is None:
            continue
        try:
            rel_map[int(did)] = r
        except (TypeError, ValueError):
            continue

    result: List[DiskInfo] = []
    for d in disks:
        num = d.get("Number")
        if num is None:
            continue
        device = f"//./PhysicalDrive{num}"
        volumes: List[VolumeInfo] = []
        for letter in disk_to_letters.get(int(num), []):
            vi = vol_map.get(letter)
            if vi:
                volumes.append(vi)
        r = rel_map.get(int(num), {})
        result.append(
            DiskInfo(
                device=device,
                model=d.get("FriendlyName"),
                serial=d.get("SerialNumber"),
                size_bytes=d.get("Size"),
                volumes=volumes,
                os_temperature_c=r.get("Temperature"),
                os_temperature_max_c=r.get("TemperatureMax"),
                os_power_on_hours=r.get("PowerOnHours"),
                os_load_cycle_count=r.get("LoadUnloadCycleCount"),
                os_start_stop_count=r.get("StartStopCycleCount"),
                os_flush_latency_max_ms=r.get("FlushLatencyMax"),
                os_write_latency_max_ms=r.get("WriteLatencyMax"),
                os_read_latency_max_ms=r.get("ReadLatencyMax"),
            )
        )

    return result


def _linux_disks() -> List[DiskInfo]:
    cmd = [
        "lsblk",
        "-J",
        "-b",
        "-o",
        "NAME,TYPE,SIZE,MOUNTPOINT,MODEL,SERIAL",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "lsblk returned no output")
    data = json.loads(proc.stdout)

    result: List[DiskInfo] = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        device = f"/dev/{dev.get('name')}"
        volumes: List[VolumeInfo] = []
        for child in dev.get("children", []) or []:
            if child.get("type") == "part":
                mp = child.get("mountpoint")
                if mp:
                    volumes.append(VolumeInfo(mountpoint=mp, size_bytes=child.get("size")))
        result.append(
            DiskInfo(
                device=device,
                model=dev.get("model"),
                serial=dev.get("serial"),
                size_bytes=dev.get("size"),
                volumes=volumes,
            )
        )

    return result


def get_disks() -> List[DiskInfo]:
    system = platform.system()
    if system == "Windows":
        return _windows_disks()
    if system == "Linux":
        return _linux_disks()
    raise RuntimeError(f"Unsupported OS: {system}")
