"""Paso 3. Calcula las métricas de monitoreo de cada periodo contra la referencia."""
import numpy as np
import pandas as pd

import metricas as m
from comun import SALIDA, SEMILLA, cargar_modelo, cargar_umbrales, particiones
from paso2_ventanas import ESCENARIOS, generar_ventanas


def metricas_periodo(modelo: dict, df: pd.DataFrame, cfg: dict, semilla: int = SEMILLA):
    """Regresa (resumen del periodo, tabla por variable, tabla por banda de PD)."""
    alfa = cfg["alfa_binomial"]
    ref = modelo["referencia"]
    y = df["incumple"].to_numpy()
    pd_pred = m.puntuar(modelo, df)
    n, k = len(df), int(y.sum())

    # Estabilidad de la puntuación y de cada variable.
    p_punt = m.proporciones(pd_pred, modelo["bordes_puntuacion"])
    psi_punt = m.psi_desde_proporciones(modelo["prop_puntuacion_ref"], p_punt)
    filas_var = []
    for v, info in modelo["variables_rangos"].items():
        p_act = m.proporciones(df[v], info["bordes"])
        filas_var.append({
            "variable": v,
            "psi": m.psi_desde_proporciones(info["prop_ref"], p_act),
            "csi": m.csi(info["prop_ref"], p_act, info["aporte_logit"]),
            "media_ref": float(modelo["media"][modelo["variables"].index(v)]),
            "media_periodo": float(df[v].mean()),
        })
    tabla_var = pd.DataFrame(filas_var)

    # Poder de ordenar riesgo.
    disc = m.discriminacion_con_intervalo(
        y, pd_pred, cfg["remuestras_bootstrap"], cfg["intervalo_bootstrap"], semilla)

    # Calibración global y por banda.
    pd_media = float(pd_pred.mean())
    p_global = m.prueba_binomial(k, n, pd_media)
    desv_bruta = abs(k / n / pd_media - 1)
    # Corrección de Bonferroni: con cinco bandas, alfa = 0.05 daría falsa alarma en 1 de cada 4 meses.
    bandas = m.calibracion_por_banda(y, pd_pred, modelo["bordes_bandas"], alfa / (len(modelo["bordes_bandas"]) + 1))

    # Las bandas que ya se rechazaban en la referencia son una debilidad conocida del modelo,
    # así que solo cuentan como alerta las que se rechazan ahora y antes no.
    bandas["rechaza_en_ref"] = bandas["banda"].isin(modelo["referencia"]["bandas_rechazadas_ref"])
    bandas["rechaza_nueva"] = bandas["rechaza"] & ~bandas["rechaza_en_ref"]

    # Estabilidad de rangos: cuánto cambia el peso de cada banda y si el orden de riesgo se conserva.
    peso_ref = np.array(modelo["prop_bandas_ref"])
    peso = m.proporciones(pd_pred, modelo["bordes_bandas"])
    bandas["peso_periodo"], bandas["peso_ref"] = peso, peso_ref
    tasas = bandas["tasa_observada"].to_numpy()
    lo, hi = m.wilson(k, n)
    resumen = {
        "clientes": n, "incumplen": k, "tasa_incumplimiento": k / n, "tasa_inf": lo, "tasa_sup": hi,
        "tasa_referencia": ref["tasa_incumplimiento"],
        "cambio_tasa_relativo": abs(k / n / ref["tasa_incumplimiento"] - 1),
        "pd_media": pd_media, "pd_media_ref": ref["pd_media"],
        "p_binomial_global": p_global, "desv_calibracion_bruta": desv_bruta,
        "desv_calibracion": desv_bruta if p_global < alfa else 0.0,
        "bandas_rechazadas_total": int(bandas["rechaza"].sum()),
        "bandas_rechazadas": int(bandas["rechaza_nueva"].sum()),
        "psi_puntuacion": psi_punt,
        "variables_psi_rojo": int((tabla_var["psi"] >= cfg["indicadores"]["psi_variable_max"]["rojo"]).sum()),
        "psi_variable_max": float(tabla_var["psi"].max()),
        "variable_psi_max": str(tabla_var.loc[tabla_var["psi"].idxmax(), "variable"]),
        "csi_abs_max": float(tabla_var["csi"].abs().max()),
        "desplazamiento_rangos_pp": float(np.abs(peso - peso_ref).max() * 100),
        "bandas_orden_invertido": int(np.sum(np.diff(tasas) < 0)),
        **disc,
        "auc_ref": ref["auc"], "gini_ref": ref["gini"], "ks_ref": ref["ks"],
        "caida_gini": ref["gini"] - disc["gini"], "caida_ks": ref["ks"] - disc["ks"],
    }
    return resumen, tabla_var, bandas


def main() -> None:
    cfg, modelo = cargar_umbrales(), cargar_modelo()
    ventanas = generar_ventanas(particiones()["reserva"])
    res, vars_, bandas = [], [], []
    for i, esc in enumerate(ESCENARIOS):
        r, tv, tb = metricas_periodo(modelo, ventanas[esc["periodo"]], cfg, SEMILLA + i)
        res.append({"periodo": esc["periodo"], "escenario": esc["nombre"], **r})
        vars_.append(tv.assign(periodo=esc["periodo"]))
        bandas.append(tb.assign(periodo=esc["periodo"]))
    pd.DataFrame(res).to_csv(SALIDA / "monitoreo_metricas.csv", index=False)
    pd.concat(vars_).to_csv(SALIDA / "monitoreo_variables.csv", index=False)
    pd.concat(bandas).to_csv(SALIDA / "monitoreo_bandas.csv", index=False)
    cols = ["periodo", "tasa_incumplimiento", "pd_media", "psi_puntuacion", "psi_variable_max",
            "csi_abs_max", "gini", "caida_gini", "desv_calibracion_bruta", "p_binomial_global",
            "bandas_rechazadas", "desplazamiento_rangos_pp"]
    print(pd.DataFrame(res)[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
