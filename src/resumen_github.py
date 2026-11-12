"""Escribe el semáforo de cada periodo en el resumen de la ejecución de GitHub Actions.

Si no corre dentro de Actions (no existe GITHUB_STEP_SUMMARY), lo imprime en pantalla."""
import os
from pathlib import Path

import pandas as pd

from comun import SALIDA


def main() -> None:
    p = pd.read_csv(SALIDA / "monitoreo_resumen.csv")
    lineas = ["## Monitoreo del modelo de PD", "",
              "| Periodo | Escenario | Semáforo | Acción |", "|---|---|---|---|"]
    lineas += [f"| {f.periodo} | {f.escenario} | {f.semaforo} | {f.accion} |" for f in p.itertuples()]
    texto = "\n".join(lineas) + "\n"
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with Path(destino).open("a", encoding="utf-8") as f:
            f.write(texto)
    else:
        print(texto)


if __name__ == "__main__":
    main()
