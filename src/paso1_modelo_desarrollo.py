"""Paso 1. Entrena el modelo de PD con la muestra de desarrollo y fija la línea base.

Guarda en resultados/modelo_pd.json los coeficientes, los rangos de cada variable y
de la puntuación, y las métricas de la muestra de referencia (que el modelo no vio).
El monitoreo compara cada periodo contra esa referencia."""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import metricas as m
from comun import (N_BANDAS, SALIDA, SEMILLA, VARIABLES_PD, cargar_umbrales,
                   particiones, variables)


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    cfg = cargar_umbrales()
    part = particiones()
    des, ref = variables(part["desarrollo"]), variables(part["referencia"])

    escalador = StandardScaler().fit(des[VARIABLES_PD])
    lr = LogisticRegression(C=1.0, max_iter=1000, random_state=SEMILLA)
    lr.fit(escalador.transform(des[VARIABLES_PD]), des["incumple"])

    modelo = {
        "variables": VARIABLES_PD,
        "media": escalador.mean_.tolist(), "escala": escalador.scale_.tolist(),
        "intercepto": float(lr.intercept_[0]), "coeficientes": lr.coef_[0].tolist(),
    }
    pd_ref = m.puntuar(modelo, ref)
    pd_des = m.puntuar(modelo, des)

    # Rangos de la puntuación (deciles de la PD en referencia) y bandas de riesgo (quintiles).
    modelo["bordes_puntuacion"] = m.bordes(pd_ref, max_bins=10, max_categorias=0)
    modelo["bordes_bandas"] = [float(x) for x in
                               np.quantile(pd_ref, np.linspace(0, 1, N_BANDAS + 1)[1:-1])]
    modelo["prop_puntuacion_ref"] = m.proporciones(pd_ref, modelo["bordes_puntuacion"]).tolist()
    modelo["prop_bandas_ref"] = m.proporciones(pd_ref, modelo["bordes_bandas"]).tolist()

    # Rangos de cada variable, su distribución de referencia y lo que cada rango aporta al logit.
    modelo["variables_rangos"] = {}
    for j, v in enumerate(VARIABLES_PD):
        e = m.bordes(ref[v])
        rango = m.asignar(ref[v], e)
        aporte_obs = modelo["coeficientes"][j] * (ref[v].to_numpy() - modelo["media"][j]) / modelo["escala"][j]
        aporte = [float(aporte_obs[rango == b].mean()) if (rango == b).any() else 0.0
                  for b in range(len(e) + 1)]
        modelo["variables_rangos"][v] = {
            "bordes": e, "prop_ref": m.proporciones(ref[v], e).tolist(), "aporte_logit": aporte,
        }

    disc = m.discriminacion_con_intervalo(
        ref["incumple"], pd_ref, cfg["remuestras_bootstrap"], cfg["intervalo_bootstrap"], SEMILLA)
    n_bandas = len(modelo["bordes_bandas"]) + 1
    cal_ref = m.calibracion_por_banda(ref["incumple"], pd_ref, modelo["bordes_bandas"],
                                      cfg["alfa_binomial"] / n_bandas)
    modelo["n_desarrollo"] = int(len(des))
    modelo["referencia"] = {
        **disc, "bandas_rechazadas_ref": [int(b) for b in cal_ref.loc[cal_ref["rechaza"], "banda"]], "n": int(len(ref)), "tasa_incumplimiento": float(ref["incumple"].mean()),
        "pd_media": float(pd_ref.mean()),
    }
    (SALIDA / "modelo_pd.json").write_text(json.dumps(modelo, indent=2, ensure_ascii=False), encoding="utf-8")

    tabla = pd.DataFrame({
        "variable": VARIABLES_PD, "coeficiente_estandarizado": modelo["coeficientes"],
        "media_desarrollo": modelo["media"], "desv_desarrollo": modelo["escala"],
    })
    tabla.to_csv(SALIDA / "modelo_coeficientes.csv", index=False)

    r = modelo["referencia"]
    print(f"Desarrollo: {len(des):,} clientes, incumplimiento {des['incumple'].mean():.1%}, "
          f"AUC {m.auc(des['incumple'], pd_des):.3f}")
    print(f"Referencia: {r['n']:,} clientes, incumplimiento {r['tasa_incumplimiento']:.1%}, "
          f"PD media {r['pd_media']:.1%}")
    print(f"  Bandas de PD que ya se rechazan en la referencia: {r['bandas_rechazadas_ref'] or 'ninguna'}")
    print(f"  AUC {r['auc']:.3f} [{r['auc_inf']:.3f}, {r['auc_sup']:.3f}]  "
          f"Gini {r['gini']:.3f}  KS {r['ks']:.3f}")


if __name__ == "__main__":
    main()
