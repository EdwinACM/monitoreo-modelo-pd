"""Carga, variables y constantes compartidas por todos los pasos del proyecto."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[1]
# La base se puede cambiar con la variable MONITOREO_DATOS (ruta a un CSV con el mismo formato).
DATOS = Path(os.environ.get("MONITOREO_DATOS", RAIZ / "datos" / "credito_tarjetas.csv"))
SALIDA = RAIZ / "resultados"
CONFIG = RAIZ / "config" / "umbrales.yaml"
SEMILLA = 42

# Del mes más reciente al más antiguo. En la base original PAY_0 es septiembre
# y PAY_2 a PAY_6 son agosto a abril (no existe PAY_1).
MESES = ["sep", "ago", "jul", "jun", "may", "abr"]
MORAS = [f"mora_{m}" for m in MESES]

# Las mismas cinco variables de comportamiento del proyecto de políticas.
# Sexo, estado civil, educación y edad no entran al modelo.
VARIABLES_PD = ["limite_log", "mora_sep", "meses_con_atraso", "uso_sep", "razon_pago"]

# Reparto de la base. Desarrollo entrena el modelo, referencia fija los rangos y
# la línea base de las métricas, y el resto alimenta las ventanas de monitoreo.
N_DESARROLLO = 10000
N_REFERENCIA = 5000
N_VENTANA = 2000
N_BANDAS = 5


def cargar(ruta: Path | None = None) -> pd.DataFrame:
    """Lee la base, renombra columnas y corrige categorías sin significado."""
    df = pd.read_csv(ruta or DATOS)
    nombres = {
        "default": "incumple", "LIMIT_BAL": "limite", "AGE": "edad",
        "SEX": "sexo", "EDUCATION": "educacion", "MARRIAGE": "estado_civil",
    }
    for original, mes in zip(["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"], MESES):
        nombres[original] = f"mora_{mes}"
    for i, mes in enumerate(MESES, start=1):
        nombres[f"BILL_AMT{i}"] = f"saldo_{mes}"
        nombres[f"PAY_AMT{i}"] = f"pago_{mes}"
    df = df.rename(columns=nombres)
    df["educacion"] = df["educacion"].replace({0: 4, 5: 4, 6: 4})
    df["estado_civil"] = df["estado_civil"].replace({0: 3})
    return df


def variables(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula las variables de comportamiento a partir de las columnas crudas."""
    d = df.copy()
    d["meses_con_atraso"] = (d[MORAS] >= 1).sum(axis=1)
    d["uso_sep"] = (d["saldo_sep"] / d["limite"]).clip(-0.5, 2)
    # Lo pagado en un mes liquida el saldo del mes anterior.
    facturado = sum(d[f"saldo_{m}"].clip(lower=0) for m in MESES[1:])
    pagado = sum(d[f"pago_{m}"] for m in MESES[:-1])
    d["razon_pago"] = (pagado / facturado.where(facturado > 0)).clip(0, 2).fillna(1.0)
    d["limite_log"] = np.log(d["limite"])
    return d


def particiones(ruta: Path | None = None) -> dict[str, pd.DataFrame]:
    """Reparto reproducible: desarrollo, referencia y reserva para las ventanas."""
    df = cargar(ruta).sample(frac=1.0, random_state=SEMILLA).reset_index(drop=True)
    return {
        "desarrollo": df.iloc[:N_DESARROLLO].copy(),
        "referencia": df.iloc[N_DESARROLLO:N_DESARROLLO + N_REFERENCIA].copy(),
        "reserva": df.iloc[N_DESARROLLO + N_REFERENCIA:].copy(),
    }


def cargar_umbrales(ruta: Path | None = None) -> dict:
    """Lee y valida el archivo de umbrales."""
    with open(ruta or CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for nombre, u in cfg["indicadores"].items():
        if not (u["ambar"] < u["rojo"]):
            raise ValueError(f"En '{nombre}' el umbral ámbar debe ser menor que el rojo.")
    return cfg


def cargar_modelo() -> dict:
    ruta = SALIDA / "modelo_pd.json"
    if not ruta.exists():
        raise SystemExit("Falta resultados/modelo_pd.json. Corre primero paso1_modelo_desarrollo.py.")
    return json.loads(ruta.read_text(encoding="utf-8"))
