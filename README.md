# Disk Health MVP (Python + PySide6)

Minimal GUI that scans physical disks, shows logical volumes, and evaluates risk using SMART data.

## Requirements
- Windows or Linux
- Python 3.10+
- `smartctl` from smartmontools
  - Windows: install smartmontools and ensure `smartctl.exe` is in PATH
  - Linux: `sudo apt install smartmontools` or equivalent

## Install
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run
```powershell
python src/app.py
```

## Notes
- Some SMART data requires Admin (Windows) or root (Linux). If SMART is unavailable, the app will still show disks and volumes but risk evaluation will be limited.
- Rule-based risk is a starting point. Treat warnings/critical as a prompt to back up data and consider drive replacement.
