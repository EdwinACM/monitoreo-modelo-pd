"""Paso 2. Arma los meses de monitoreo con deriva inducida y reproducible.

La base UCI es una foto de un solo corte, así que no existen meses posteriores al
desarrollo. Se simulan reordenando la reserva de clientes (los que no entraron ni al
desarrollo ni a la referencia) en seis ventanas de 2,000 clientes sin repetir a nadie.
Cada ventana tiene una receta fija y una semilla propia (42 + número de ventana). Las ventanas sin
cambio de mezcla se muestrean primero y las que sesgan la mezcla después, con los que sobran:

- mezcla: se muestrea con más probabilidad a clientes con uso alto de la línea y límite bajo.
- deterioro: a una fracción de los clientes que no incumplieron se les cambia la etiqueta
  a incumplimiento, con más probabilidad cuanto más meses de atraso tienen. Es sintético: la
  puntuación no cambia, la realidad sí.
- ruido: una fracción de las etiquetas se sustituye por un sorteo con la tasa base, lo que
  borra la relación entre las variables y el incumplimiento en esos clientes.
- ruptura: una fracción de los registros de mora_sep llega en cero, como si el sistema
  fuente hubiera dejado de reportar el atraso. Las variables derivadas se recalculan.

Los meses M01 y M02 no tienen deriva y sirven para ver el ruido normal del muestreo."""
import numpy as np
import pandas as pd

from comun import MORAS, N_VENTANA, SALIDA, SEMILLA, particiones, variables

# Columnas que calcula comun.variables y que se recalculan después de aplicar la deriva.
DERIVADAS = ["meses_con_atraso", "uso_sep", "razon_pago", "limite_log"]

ESCENARIOS = [
    {"periodo": "M01", "nombre": "Sin deriva", "mezcla": 0.0, "deterioro": 0.0, "ruptura": 0.0, "ruido": 0.0,
     "descripcion": "Muestra aleatoria de la reserva."},
    {"periodo": "M02", "nombre": "Sin deriva", "mezcla": 0.0, "deterioro": 0.0, "ruptura": 0.0, "ruido": 0.0,
     "descripcion": "Muestra aleatoria de la reserva."},
    {"periodo": "M03", "nombre": "Cambio de mezcla", "mezcla": 1.2, "deterioro": 0.0, "ruptura": 0.0, "ruido": 0.0,
     "descripcion": "Entran más clientes con uso alto de la línea y límite bajo."},
    {"periodo": "M04", "nombre": "Deterioro de mora", "mezcla": 0.0, "deterioro": 0.10, "ruptura": 0.0, "ruido": 0.0,
     "descripcion": "10% de los clientes que no incumplían pasan a incumplir (sintético)."},
    {"periodo": "M05", "nombre": "Ruptura de variable", "mezcla": 0.0, "deterioro": 0.0, "ruptura": 0.5, "ruido": 0.0,
     "descripcion": "La mitad de los registros de mora_sep llega en cero."},
    {"periodo": "M06", "nombre": "Pérdida de poder", "mezcla": 0.0, "deterioro": 0.0, "ruptura": 0.0, "ruido": 0.35,
     "descripcion": "35% de las etiquetas se sustituye por un sorteo con la tasa base."},
]


def _z(s: pd.Series) -> np.ndarray:
    return ((s - s.mean()) / s.std()).to_numpy()


def generar_ventanas(reserva: pd.DataFrame, escenarios=ESCENARIOS, n: int = N_VENTANA) -> dict[str, pd.DataFrame]:
    """Regresa {periodo: datos con variables calculadas}. Nadie aparece en dos ventanas."""
    pool = variables(reserva).reset_index(drop=True)
    z_uso, z_lim = _z(pool["uso_sep"]), _z(pool["limite_log"])
    libres = np.arange(len(pool))
    ventanas = {}
    # Primero salen las ventanas sin cambio de mezcla (muestras aleatorias, representativas) y al
    # final las que sesgan la mezcla, para que estas no vacíen de clientes de uso alto a las demás.
    orden = sorted(range(len(escenarios)), key=lambda k: (escenarios[k]["mezcla"] > 0, k))
    for i in orden:
        esc = escenarios[i]
        rng = np.random.default_rng(SEMILLA + i + 1)
        if esc["mezcla"] > 0:
            w = np.exp(esc["mezcla"] * (z_uso[libres] - 0.5 * z_lim[libres]))
            idx = rng.choice(libres, size=n, replace=False, p=w / w.sum())
        else:
            idx = rng.choice(libres, size=n, replace=False)
        libres = np.setdiff1d(libres, idx)
        v = pool.iloc[idx][[c for c in pool.columns if c not in DERIVADAS]].copy()
        v = v.reset_index(drop=True)
        if esc["deterioro"] > 0:
            peso = 1 + v[MORAS].ge(1).sum(axis=1)
            prob = (esc["deterioro"] * peso / peso.mean()).clip(upper=1)
            cambia = (v["incumple"] == 0) & (rng.random(len(v)) < prob)
            v.loc[cambia, "incumple"] = 1
        if esc["ruido"] > 0:
            sorteo = rng.random(len(v)) < esc["ruido"]
            tasa = v["incumple"].mean()
            v.loc[sorteo, "incumple"] = (rng.random(int(sorteo.sum())) < tasa).astype(int)
        if esc["ruptura"] > 0:
            rota = rng.random(len(v)) < esc["ruptura"]
            v.loc[rota, "mora_sep"] = 0
        ventanas[esc["periodo"]] = variables(v)
    return {e["periodo"]: ventanas[e["periodo"]] for e in escenarios}


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    ventanas = generar_ventanas(particiones()["reserva"])
    filas = []
    for esc in ESCENARIOS:
        v = ventanas[esc["periodo"]]
        filas.append({**esc, "clientes": len(v), "tasa_incumplimiento": v["incumple"].mean(),
                      "uso_sep_medio": v["uso_sep"].mean(), "limite_medio": v["limite"].mean(),
                      "pct_mora_sep_mayor_0": (v["mora_sep"] >= 1).mean()})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA / "ventanas_descripcion.csv", index=False)
    print(tabla[["periodo", "nombre", "clientes", "tasa_incumplimiento", "uso_sep_medio",
                 "pct_mora_sep_mayor_0"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
