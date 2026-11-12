"""Métricas de monitoreo. Son funciones puras: reciben arreglos y regresan números."""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

EPS = 1e-4  # piso de las proporciones para que el logaritmo del PSI exista


def bordes(ref, max_bins: int = 10, max_categorias: int = 12) -> list[float]:
    """Bordes internos de los rangos. Si la variable tiene pocos valores distintos,
    cada valor queda en su propio rango; si no, se usan cuantiles de la referencia."""
    ref = np.asarray(ref, dtype=float)
    valores = np.unique(ref)
    if len(valores) <= max_categorias:
        return [float(x) for x in (valores[:-1] + valores[1:]) / 2]
    cuantiles = np.quantile(ref, np.linspace(0, 1, max_bins + 1)[1:-1])
    return [float(x) for x in np.unique(cuantiles)]


def asignar(x, edges) -> np.ndarray:
    """Número de rango de cada observación. Los valores fuera del rango observado
    en la referencia caen en el primer o el último rango."""
    return np.searchsorted(np.asarray(edges, dtype=float), np.asarray(x, dtype=float), side="right")


def proporciones(x, edges) -> np.ndarray:
    k = len(edges) + 1
    conteo = np.bincount(asignar(x, edges), minlength=k)
    return conteo / conteo.sum()


def psi_desde_proporciones(p_ref, p_act) -> float:
    r = np.clip(np.asarray(p_ref, dtype=float), EPS, None)
    a = np.clip(np.asarray(p_act, dtype=float), EPS, None)
    return float(np.sum((a - r) * np.log(a / r)))


def psi(ref, act, edges=None) -> float:
    """Índice de estabilidad poblacional entre dos muestras."""
    edges = bordes(ref) if edges is None else edges
    return psi_desde_proporciones(proporciones(ref, edges), proporciones(act, edges))


def csi(p_ref, p_act, aporte_por_rango) -> float:
    """Índice de estabilidad de la característica: cada rango pesa su cambio de
    población por lo que aporta al logit del modelo (puntos del rango)."""
    d = np.asarray(p_act, dtype=float) - np.asarray(p_ref, dtype=float)
    return float(np.sum(d * np.asarray(aporte_por_rango, dtype=float)))


def ks(y, pd_pred) -> float:
    y = np.asarray(y)
    malos, buenos = np.asarray(pd_pred)[y == 1], np.asarray(pd_pred)[y == 0]
    if len(malos) == 0 or len(buenos) == 0:
        return float("nan")
    return float(stats.ks_2samp(malos, buenos).statistic)


def auc(y, pd_pred) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, pd_pred))


def gini(y, pd_pred) -> float:
    return 2 * auc(y, pd_pred) - 1


def discriminacion_con_intervalo(y, pd_pred, remuestras: int, nivel: float, semilla: int) -> dict:
    """AUC, Gini y KS con intervalo bootstrap percentil."""
    y, pd_pred = np.asarray(y), np.asarray(pd_pred)
    rng = np.random.default_rng(semilla)
    n = len(y)
    a, k = [], []
    for _ in range(remuestras):
        idx = rng.integers(0, n, n)
        a.append(auc(y[idx], pd_pred[idx]))
        k.append(ks(y[idx], pd_pred[idx]))
    q = [(1 - nivel) / 2 * 100, (1 + nivel) / 2 * 100]
    a_lo, a_hi = np.nanpercentile(a, q)
    k_lo, k_hi = np.nanpercentile(k, q)
    return {
        "auc": auc(y, pd_pred), "auc_inf": float(a_lo), "auc_sup": float(a_hi),
        "gini": gini(y, pd_pred), "gini_inf": float(2 * a_lo - 1), "gini_sup": float(2 * a_hi - 1),
        "ks": ks(y, pd_pred), "ks_inf": float(k_lo), "ks_sup": float(k_hi),
    }


def wilson(k: int, n: int, nivel: float = 0.95) -> tuple[float, float]:
    """Intervalo de Wilson para una proporción."""
    if n == 0:
        return float("nan"), float("nan")
    z = stats.norm.ppf((1 + nivel) / 2)
    p = k / n
    centro = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    mitad = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return float(centro - mitad), float(centro + mitad)


def prueba_binomial(k: int, n: int, p_esperada: float) -> float:
    """Valor p de dos colas: ¿los incumplimientos observados son compatibles con la PD predicha?"""
    if n == 0:
        return float("nan")
    p = min(max(p_esperada, 1e-9), 1 - 1e-9)
    return float(stats.binomtest(int(k), int(n), p).pvalue)


def calibracion_por_banda(y, pd_pred, band_edges, alfa: float) -> pd.DataFrame:
    """PD media predicha contra tasa observada en cada banda, con prueba binomial."""
    y, pd_pred = np.asarray(y), np.asarray(pd_pred, dtype=float)
    banda = asignar(pd_pred, band_edges)
    filas = []
    for b in range(len(band_edges) + 1):
        m = banda == b
        n = int(m.sum())
        k = int(y[m].sum())
        pred = float(pd_pred[m].mean()) if n else float("nan")
        p = prueba_binomial(k, n, pred) if n else float("nan")
        lo, hi = wilson(k, n)
        filas.append({
            "banda": b + 1, "clientes": n, "incumplen": k,
            "pd_predicha": pred, "tasa_observada": k / n if n else float("nan"),
            "obs_inf": lo, "obs_sup": hi, "valor_p": p,
            "rechaza": bool(p < alfa) if n else False,
        })
    return pd.DataFrame(filas)


def puntuar(modelo: dict, df: pd.DataFrame) -> np.ndarray:
    """PD del modelo de regresión logística guardado en JSON (sin pickle)."""
    x = df[modelo["variables"]].to_numpy(dtype=float)
    z = (x - np.array(modelo["media"])) / np.array(modelo["escala"])
    logit = modelo["intercepto"] + z @ np.array(modelo["coeficientes"])
    return 1.0 / (1.0 + np.exp(-logit))
