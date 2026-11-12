"""Semáforos verde, ámbar y rojo, y la recomendación de acción de cada periodo."""

VERDE, AMBAR, ROJO = "verde", "ámbar", "rojo"
ORDEN = {VERDE: 0, AMBAR: 1, ROJO: 2}


def nivel(valor: float, ambar: float, rojo: float) -> str:
    """Un valor más alto es peor. El umbral cuenta como alcanzado cuando valor >= umbral."""
    if valor != valor:  # NaN: no se puede evaluar, se trata como alerta
        return ROJO
    if valor >= rojo:
        return ROJO
    if valor >= ambar:
        return AMBAR
    return VERDE


def peor(niveles) -> str:
    return max(niveles, key=lambda n: ORDEN[n], default=VERDE)


def evaluar(resumen: dict, cfg: dict) -> list[dict]:
    """Un renglón por indicador: valor, umbrales y nivel."""
    filas = []
    for nombre, u in cfg["indicadores"].items():
        valor = float(resumen[nombre])
        filas.append({
            "indicador": nombre, "descripcion": u["descripcion"], "valor": valor,
            "umbral_ambar": u["ambar"], "umbral_rojo": u["rojo"],
            "nivel": nivel(valor, u["ambar"], u["rojo"]),
        })
    return filas


def recomendar(evaluacion: list[dict], variables_en_rojo: int = 0, max_ruptura: int = 2) -> tuple[str, str]:
    """Acción sugerida y su motivo. Se aplica la primera regla que se cumpla:

    1. Una o dos variables cambiaron de forma abrupta (PSI o CSI en rojo, con no más de
       `max_ruptura` variables en rojo) mientras las demás siguen igual: patrón de un problema
       en la fuente de datos, así que se revisa antes de tocar el modelo.
    2. Gini o KS en rojo: redesarrollar el modelo.
    3. Calibración en rojo (desviación o bandas): recalibrar.
    4. Cambio de población en rojo sin pérdida de desempeño: vigilar de cerca.
    5. Cualquier ámbar: vigilar.
    6. Todo verde: sin acción."""
    n = {f["indicador"]: f["nivel"] for f in evaluacion}
    discr = peor([n["caida_gini"], n["caida_ks"]])
    estab_var = peor([n["psi_variable_max"], n["csi_abs_max"]])
    calib = peor([n["desv_calibracion"], n["bandas_rechazadas"]])
    estab = peor([n["psi_puntuacion"], n["psi_variable_max"], n["csi_abs_max"], n["desplazamiento_rangos_pp"]])

    if estab_var == ROJO and 0 < variables_en_rojo <= max_ruptura:
        return ("Revisar datos",
                "Pocas variables cambiaron de forma abrupta mientras las demás siguen estables, "
                "un patrón típico de un problema en la fuente. Confirma que el dato llega bien. "
                "Si es correcto y el desempeño sigue bajando, evalúa redesarrollar.")
    if discr == ROJO:
        return ("Redesarrollar",
                "El modelo perdió poder para ordenar riesgo (Gini o KS en rojo) sin una falla clara de datos.")
    if calib == ROJO:
        return ("Recalibrar",
                "El modelo todavía ordena el riesgo, pero la PD predicha ya no coincide con lo observado.")
    if estab == ROJO:
        return ("Vigilar de cerca",
                "La población cambió de forma importante, aunque el desempeño sigue estable. "
                "Revisa el segmento nuevo y repite la medición el mes siguiente.")
    if any(f["nivel"] == AMBAR for f in evaluacion) or ORDEN[discr] or ORDEN[calib] or ORDEN[estab]:
        return ("Vigilar", "Hay indicadores en ámbar. Se revisan de nuevo el mes siguiente.")
    return ("Sin acción", "Todos los indicadores están en verde.")
