"""Corre todos los pasos en orden. Con la misma semilla da los mismos resultados."""
import subprocess
import sys
from pathlib import Path

PASOS = [
    "paso1_modelo_desarrollo.py",
    "paso2_ventanas.py",
    "paso3_metricas.py",
    "paso4_alertas.py",
    "paso5_reporte.py",
]

if __name__ == "__main__":
    carpeta = Path(__file__).resolve().parent
    for paso in PASOS:
        print(f"\n=== {paso} ===")
        subprocess.run([sys.executable, str(carpeta / paso)], check=True, cwd=carpeta)
