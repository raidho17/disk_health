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


English

Disk Health MVP is a minimal PySide6 desktop app that scans physical disks, lists their logical volumes, and evaluates disk risk using SMART data. It pulls disk/volume info via OS tools (PowerShell on Windows or lsblk on Linux), enriches metrics with smartctl from smartmontools, and applies a rule‑based scoring model to label each disk as OK, WARNING, or CRITICAL. Results are displayed in a tree view and can be exported to JSON or CSV. It runs on Windows or Linux with Python 3.10+ and works best when SMART access is available (admin/root often required).

Русский

Disk Health MVP — минималистичное настольное приложение на PySide6, которое сканирует физические диски, показывает их логические тома и оценивает риск на основе SMART‑данных. Информация о дисках/томах берётся из системных инструментов (PowerShell на Windows или lsblk на Linux), затем дополняется данными smartctl из smartmontools, после чего применяется правило‑базированная модель для уровня риска: OK, WARNING или CRITICAL. Результаты отображаются в дереве и могут быть экспортированы в JSON или CSV. Работает на Windows и Linux с Python 3.10+ и даёт лучшие результаты при наличии доступа к SMART (часто нужен админ/root).
