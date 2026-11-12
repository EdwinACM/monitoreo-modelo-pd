"""Pruebas del sistema de monitoreo. Se corren con: python -m pytest"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from sklearn.metrics import roc_auc_score

import metricas as m
import paso1_modelo_desarrollo as paso1
import paso5_reporte
from comun import VARIABLES_PD, cargar, cargar_umbrales, particiones
from paso2_ventanas import ESCENARIOS, generar_ventanas
from paso3_metricas import metricas_periodo
from paso4_alertas import semaforos
from semaforos import AMBAR, ROJO, VERDE, evaluar, nivel, recomendar

CFG = cargar_umbrales()


@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    """Entrena el modelo y mide los seis periodos, sin tocar la carpeta resultados."""
    carpeta = tmp_path_factory.mktemp("resultados")
    mp = pytest.MonkeyPatch()
    mp.setattr(paso1, "SALIDA", carpeta)
    paso1.main()
    mp.undo()
    modelo = json.loads((carpeta / "modelo_pd.json").read_text(encoding="utf-8"))
    ventanas = generar_ventanas(particiones()["reserva"])
    res, vars_, bandas = [], [], []
    for i, esc in enumerate(ESCENARIOS):
        r, tv, tb = metricas_periodo(modelo, ventanas[esc["periodo"]], CFG, 42 + i)
        res.append({"periodo": esc["periodo"], "escenario": esc["nombre"], **r})
        vars_.append(tv.assign(periodo=esc["periodo"]))
        bandas.append(tb.assign(periodo=esc["periodo"]))
    resumen = pd.DataFrame(res)
    todos, por_periodo = semaforos(resumen, CFG)
    return {"modelo": modelo, "ventanas": ventanas, "resumen": resumen, "vars": pd.concat(vars_),
            "bandas": pd.concat(bandas), "todos": todos, "periodos": por_periodo}


def accion(corrida, periodo):
    return corrida["periodos"].set_index("periodo").loc[periodo]


# ---------- PSI ----------

def test_psi_cero_con_datos_identicos():
    rng = np.random.default_rng(1)
    x = rng.normal(size=5000)
    assert m.psi(x, x.copy()) == 0.0
    d = particiones()["referencia"]
    for v in ["limite", "mora_sep", "saldo_sep"]:
        assert m.psi(d[v], d[v].copy()) == 0.0


def test_psi_cero_en_el_pipeline_si_el_periodo_es_la_referencia(corrida):
    from comun import variables
    ref = variables(particiones()["referencia"])
    r, tv, tb = metricas_periodo(corrida["modelo"], ref, CFG)
    assert r["psi_puntuacion"] == pytest.approx(0.0, abs=1e-12)
    assert (tv["psi"].abs() < 1e-12).all()
    assert r["desplazamiento_rangos_pp"] == pytest.approx(0.0, abs=1e-9)
    assert r["cambio_tasa_relativo"] == pytest.approx(0.0, abs=1e-9)


def test_psi_detecta_desplazamiento_y_no_se_asusta_con_ruido():
    rng = np.random.default_rng(2)
    ref = rng.normal(size=20000)
    assert m.psi(ref, rng.normal(size=20000)) < 0.02           # mismo proceso, solo ruido
    assert m.psi(ref, rng.normal(loc=0.5, size=20000)) > 0.10  # medio sigma de corrimiento
    assert m.psi(ref, rng.normal(loc=1.5, size=20000)) > 0.25


def test_psi_finito_con_rangos_vacios_y_valores_fuera_de_rango():
    ref = np.arange(1000.0)
    act = np.full(1000, 5000.0)  # todo fuera del rango de referencia
    valor = m.psi(ref, act)
    assert np.isfinite(valor) and valor > 0.25


def test_psi_coincide_con_la_formula_a_mano():
    p_ref, p_act = np.array([0.5, 0.5]), np.array([0.3, 0.7])
    esperado = (0.3 - 0.5) * np.log(0.3 / 0.5) + (0.7 - 0.5) * np.log(0.7 / 0.5)
    assert m.psi_desde_proporciones(p_ref, p_act) == pytest.approx(esperado)


# ---------- Métricas ----------

def test_auc_y_ks_coinciden_con_las_librerias():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 3000)
    s = rng.random(3000) + 0.4 * y
    assert m.auc(y, s) == pytest.approx(roc_auc_score(y, s))
    assert m.gini(y, s) == pytest.approx(2 * roc_auc_score(y, s) - 1)
    assert m.ks(y, s) == pytest.approx(stats.ks_2samp(s[y == 1], s[y == 0]).statistic)


def test_intervalo_bootstrap_contiene_la_estimacion_y_es_reproducible():
    rng = np.random.default_rng(4)
    y = rng.integers(0, 2, 2000)
    s = rng.random(2000) + 0.3 * y
    a = m.discriminacion_con_intervalo(y, s, 200, 0.95, 42)
    b = m.discriminacion_con_intervalo(y, s, 200, 0.95, 42)
    assert a == b
    assert a["gini_inf"] <= a["gini"] <= a["gini_sup"]
    assert a["ks_inf"] <= a["ks"] <= a["ks_sup"]


def test_binomial_acepta_lo_compatible_y_rechaza_lo_lejano():
    assert m.prueba_binomial(200, 1000, 0.20) > 0.9
    assert m.prueba_binomial(300, 1000, 0.20) < 1e-6


def test_wilson_contiene_la_proporcion():
    lo, hi = m.wilson(220, 1000)
    assert lo < 0.22 < hi


# ---------- Umbrales y semáforos ----------

@pytest.mark.parametrize("valor,esperado", [
    (0.0, VERDE), (0.0999, VERDE), (0.10, AMBAR), (0.2499, AMBAR), (0.25, ROJO), (3.0, ROJO),
])
def test_umbrales_de_psi_disparan_el_semaforo_correcto(valor, esperado):
    u = CFG["indicadores"]["psi_puntuacion"]
    assert (u["ambar"], u["rojo"]) == (0.10, 0.25)
    assert nivel(valor, u["ambar"], u["rojo"]) == esperado


def test_nan_se_trata_como_rojo():
    assert nivel(float("nan"), 0.1, 0.25) == ROJO


def base_verde():
    """Resumen con todos los indicadores en cero (verde)."""
    return {k: 0.0 for k in CFG["indicadores"]}


def test_cada_indicador_dispara_ambar_y_rojo_en_sus_umbrales():
    for nombre, u in CFG["indicadores"].items():
        for valor, esperado in [(u["ambar"] * 0.5, VERDE), (u["ambar"], AMBAR), (u["rojo"], ROJO)]:
            r = base_verde()
            r[nombre] = valor
            niveles = {f["indicador"]: f["nivel"] for f in evaluar(r, CFG)}
            assert niveles[nombre] == esperado, nombre
            assert all(v == VERDE for k, v in niveles.items() if k != nombre)


def test_umbrales_configurables():
    cfg = copy.deepcopy(CFG)
    cfg["indicadores"]["psi_puntuacion"].update(ambar=0.02, rojo=0.04)
    r = base_verde()
    r["psi_puntuacion"] = 0.03
    assert {f["indicador"]: f["nivel"] for f in evaluar(r, cfg)}["psi_puntuacion"] == AMBAR
    assert {f["indicador"]: f["nivel"] for f in evaluar(r, CFG)}["psi_puntuacion"] == VERDE


def test_umbrales_mal_ordenados_se_rechazan(tmp_path):
    malo = tmp_path / "u.yaml"
    malo.write_text("indicadores:\n  psi_puntuacion: {ambar: 0.3, rojo: 0.1, descripcion: x}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_umbrales(malo)


def acc(**cambios):
    r = base_verde()
    r.update(cambios)
    return recomendar(evaluar(r, CFG))[0]


def test_acciones_recomendadas():
    assert acc() == "Sin acción"
    assert acc(psi_puntuacion=0.12) == "Vigilar"
    assert acc(caida_gini=0.12) == "Redesarrollar"
    assert acc(desv_calibracion=0.3) == "Recalibrar"
    assert acc(bandas_rechazadas=3) == "Recalibrar"
    assert acc(psi_puntuacion=0.4) == "Vigilar de cerca"
    ev = evaluar({**base_verde(), "psi_variable_max": 0.5}, CFG)
    assert recomendar(ev, variables_en_rojo=1)[0] == "Revisar datos"
    assert recomendar(ev, variables_en_rojo=4)[0] == "Vigilar de cerca"


# ---------- Deriva inyectada, de punta a punta ----------

def test_periodos_sin_deriva_quedan_en_verde(corrida):
    for p in ["M01", "M02"]:
        assert accion(corrida, p)["semaforo"] == VERDE
        assert accion(corrida, p)["accion"] == "Sin acción"


def test_detecta_el_cambio_de_mezcla(corrida):
    r = corrida["resumen"].set_index("periodo").loc["M03"]
    assert r["psi_puntuacion"] >= 0.25 and r["psi_variable_max"] >= 0.25
    assert r["variable_psi_max"] == "uso_sep"
    assert accion(corrida, "M03")["accion"] == "Vigilar de cerca"


def test_detecta_el_deterioro_de_mora_como_problema_de_calibracion(corrida):
    r = corrida["resumen"].set_index("periodo").loc["M04"]
    assert r["psi_puntuacion"] < 0.10            # la población no cambió
    assert r["tasa_incumplimiento"] > r["pd_media"]
    assert r["desv_calibracion"] >= 0.20 and r["p_binomial_global"] < 0.001
    assert accion(corrida, "M04")["accion"] == "Recalibrar"


def test_detecta_la_ruptura_de_variable(corrida):
    tv = corrida["vars"].query("periodo == 'M05'").set_index("variable")
    assert tv.loc["mora_sep", "psi"] >= 0.25
    assert tv.drop(index=["mora_sep", "meses_con_atraso"])["psi"].max() < 0.10
    assert accion(corrida, "M05")["accion"] == "Revisar datos"


def test_detecta_la_perdida_de_poder(corrida):
    r = corrida["resumen"].set_index("periodo").loc["M06"]
    assert r["caida_gini"] >= 0.10
    assert accion(corrida, "M06")["accion"] == "Redesarrollar"


def test_la_deriva_se_nota_mas_que_el_ruido(corrida):
    r = corrida["resumen"].set_index("periodo")
    ruido = max(r.loc[["M01", "M02"], "psi_puntuacion"].max(), r.loc[["M01", "M02"], "psi_variable_max"].max())
    assert ruido < 0.05
    assert r.loc["M03", "psi_puntuacion"] > 5 * ruido


# ---------- Ventanas y datos ----------

def test_ventanas_reproducibles_y_sin_clientes_repetidos():
    reserva = particiones()["reserva"]
    a, b = generar_ventanas(reserva), generar_ventanas(reserva)
    ids = []
    for p in a:
        pd.testing.assert_frame_equal(a[p], b[p])
        assert len(a[p]) == 2000
        ids += list(a[p]["ID"])
    assert len(ids) == len(set(ids))


def test_particiones_disjuntas_y_base_completa():
    assert len(cargar()) == 30000
    part = particiones()
    ids = [set(df["ID"]) for df in part.values()]
    assert not (ids[0] & ids[1]) and not (ids[0] & ids[2]) and not (ids[1] & ids[2])
    assert sum(len(i) for i in ids) == 30000


def test_modelo_sin_variables_sensibles(corrida):
    assert corrida["modelo"]["variables"] == VARIABLES_PD
    for prohibida in ["sexo", "estado_civil", "educacion", "edad"]:
        assert prohibida not in VARIABLES_PD


def test_la_ruptura_recalcula_las_variables_derivadas():
    v = generar_ventanas(particiones()["reserva"])["M05"]
    moras = v[[c for c in v.columns if c.startswith("mora_")]]
    assert ((moras >= 1).sum(axis=1) == v["meses_con_atraso"]).all()


# ---------- Reporte HTML y alertas ----------

def pagina(corrida, periodo="M05", **cambios):
    periodos = corrida["periodos"].copy()
    for k, val in cambios.items():
        periodos[k] = val
    return paso5_reporte.generar_html(
        corrida["resumen"], corrida["todos"], periodos, corrida["vars"], corrida["bandas"],
        corrida["modelo"], CFG, periodo)


def test_reporte_autocontenido_con_csp_y_sin_js(corrida):
    h = pagina(corrida)
    bajo = h.lower()
    assert 'http-equiv="content-security-policy"' in bajo
    assert "default-src &#x27;none&#x27;" in bajo
    for prohibido in ["<script", "javascript:", "http://", "https://", "<link", "<iframe", " onclick=", " onerror=", "<img"]:
        assert prohibido not in bajo, prohibido
    assert "Revisar datos" in h


def test_reporte_escapa_texto_de_los_datos(corrida):
    ataque = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    h = pagina(corrida, escenario=ataque, motivo=ataque, accion=ataque)
    assert "<script>alert(1)" not in h
    assert "<img" not in h.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in h


def test_reporte_de_cada_periodo_se_genera(corrida):
    for p in corrida["resumen"]["periodo"]:
        assert f"Monitoreo del modelo de PD: {p}" in pagina(corrida, p)


def test_alertas_solo_traen_lo_que_no_esta_en_verde(corrida):
    alertas = corrida["todos"][corrida["todos"]["nivel"] != VERDE]
    assert len(alertas) > 0
    assert set(alertas["nivel"]) <= {AMBAR, ROJO}
    assert "M01" not in set(alertas["periodo"]) and "M02" not in set(alertas["periodo"])
