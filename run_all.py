"""Запускает все шаги проекта по порядку: данные, очистка, анализ, карта и графики."""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent / "scripts"
STEPS = ["01_download_data.py", "02_clean.py", "03_analysis.py", "04_map_and_plots.py"]

for step in STEPS:
    print(f"\n===== {step} =====", flush=True)
    # sys.executable — тот же Python, которым запущен этот файл (из .venv)
    subprocess.run([sys.executable, str(SCRIPTS / step)], check=True)
