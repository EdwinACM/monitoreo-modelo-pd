"""Paso 4. Aplica los umbrales, asigna semáforo y acción, y escribe el CSV de alertas."""
import pandas as pd

from comun import SALIDA, cargar_umbrales
from semaforos import AMBAR, ORDEN, ROJO, evaluar, peor, recomendar


def semaforos(resumen: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Regresa (todos los indicadores por periodo, resumen por periodo con acción)."""
    todos, por_periodo = [], []
    for _, fila in resumen.iterrows():
        ev = evaluar(fila.to_dict(), cfg)
        accion, motivo = recomendar(
            ev, int(fila["variables_psi_rojo"]), cfg["max_variables_ruptura"])
        for f in ev:
            todos.append({"periodo": fila["periodo"], **f})
        por_periodo.append({
            "periodo": fila["periodo"], "escenario": fila["escenario"],
            "semaforo": peor([f["nivel"] for f in ev]), "accion": accion, "motivo": motivo,
            "indicadores_rojos": sum(f["nivel"] == ROJO for f in ev),
            "indicadores_ambar": sum(f["nivel"] == AMBAR for f in ev),
        })
    return pd.DataFrame(todos), pd.DataFrame(por_periodo)


def main() -> None:
    cfg = cargar_umbrales()
    resumen = pd.read_csv(SALIDA / "monitoreo_metricas.csv")
    todos, por_periodo = semaforos(resumen, cfg)
    todos.to_csv(SALIDA / "monitoreo_semaforos.csv", index=False)
    por_periodo.to_csv(SALIDA / "monitoreo_resumen.csv", index=False)
    # El CSV de alertas solo trae lo que no está en verde, con la acción del periodo.
    alertas = todos[todos["nivel"] != "verde"].merge(
        por_periodo[["periodo", "semaforo", "accion"]], on="periodo", suffixes=("", "_periodo"))
    alertas = alertas.sort_values(
        ["periodo", "nivel"], key=lambda s: s.map(ORDEN).fillna(0) * -1 if s.name == "nivel" else s)
    alertas.to_csv(SALIDA / "alertas.csv", index=False)
    print(por_periodo[["periodo", "escenario", "semaforo", "accion",
                       "indicadores_rojos", "indicadores_ambar"]].to_string(index=False))
    print(f"\n{len(alertas)} alertas escritas en resultados/alertas.csv")


if __name__ == "__main__":
    main()
