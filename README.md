# Monitoreo de un modelo de PD con datos públicos

Sistema que vigila mes a mes un modelo de probabilidad de incumplimiento (PD). Revisa si la población cambió, si el modelo sigue ordenando el riesgo y si la PD predicha se parece a lo observado. Cada periodo recibe un semáforo y una acción sugerida: recalibrar, redesarrollar, revisar datos o vigilar. Genera un reporte HTML, un CSV de alertas y una acción de GitHub que lo corre cada mes con los datos de ejemplo.

Es un ejercicio académico con datos públicos. No usa información de ningún banco ni de sus clientes.

## Los datos y cómo se simulan los meses

Uso la base "Default of Credit Card Clients" de UCI (Yeh y Lien, 2009): 30,000 clientes de tarjeta de Taiwán con un solo corte en septiembre de 2005. Como no hay meses posteriores, los de monitoreo se simulan:

- 10,000 clientes entrenan el modelo, 5,000 forman la referencia (línea base) y 15,000 quedan en reserva.
- De la reserva salen seis ventanas de 2,000 clientes, sin repetir a nadie, con recetas fijas y semilla 42.

| Periodo | Receta | Qué se inyecta |
|---|---|---|
| M01, M02 | Sin deriva | Muestra aleatoria, que da una idea del ruido normal. |
| M03 | Cambio de mezcla | Entran más clientes con uso alto de la línea y límite bajo. |
| M04 | Deterioro de mora | 10% de los que no incumplían pasa a incumplir, con más probabilidad si ya tenían atrasos. |
| M05 | Ruptura de variable | La mitad de los registros de `mora_sep` llega en cero. |
| M06 | Pérdida de poder | 35% de las etiquetas se sustituye por un sorteo con la tasa base. |

La deriva es sintética. Sirve para comprobar que el sistema detecta lo que se le inyecta.

## Qué mide

Para cada periodo calcula el PSI de la puntuación y de cada variable, el CSI, y el AUC, el Gini y el KS con intervalo bootstrap. Compara la PD predicha con la tasa observada, con prueba binomial global y por banda, revisa la estabilidad de las cinco bandas de riesgo y estima la tasa de incumplimiento con intervalo de Wilson. Los umbrales de cada semáforo están en `config/umbrales.yaml`.

## Resultados

Con los umbrales del archivo, el sistema clasifica así los seis periodos:

| Periodo | Semáforo | Acción | Lo que lo dispara |
|---|---|---|---|
| M01 | verde | Sin acción | Todo dentro de lo normal. |
| M02 | verde | Sin acción | Todo dentro de lo normal. |
| M03 | rojo | Vigilar de cerca | PSI de la puntuación 0.302 y de `uso_sep` 0.674. El Gini no baja (0.519) y la calibración se sostiene. |
| M04 | rojo | Recalibrar | Tasa observada 29.0% contra 21.4% predicho. Prueba binomial global con valor p menor a 0.001. Los PSI quedan en 0.01. |
| M05 | rojo | Revisar datos | PSI de `mora_sep` en 0.271, único PSI de variable en rojo. El Gini apenas se mueve (0.478). |
| M06 | rojo | Redesarrollar | Gini de 0.336 contra 0.518 de la referencia. Los PSI quedan en 0.01. |

M01 y M02, que no tienen deriva, dan PSI de la puntuación de 0.005 y 0.006. Las cuatro derivas se distinguen del ruido y cada una activa indicadores distintos: el PSI detecta el cambio de mezcla y la ruptura, la calibración detecta el deterioro y el Gini detecta la pérdida de poder.

La ruptura de `mora_sep` es el caso más difícil. El Gini cae solo 0.039 (verde) porque `meses_con_atraso` conserva buena parte de la información, así que sin el PSI de variables no se habría notado. El CSI de esa variable es 0.005 y tampoco la detecta.

En la muestra de referencia el modelo base tiene AUC de 0.759, Gini de 0.518 y KS de 0.427. Sobrestima la banda 2 de PD (12.4% predicho contra 9.3% observado) y subestima la banda 5 (51.3% contra 55.6%). Esas dos bandas ya se rechazan en la referencia, así que el indicador de bandas cuenta solo las que se rechazan de nuevo.

## Límites

- Los meses son una simulación sobre una foto de 2005. No hay estacionalidad, ni cambios de política, ni rezago real entre puntuar y observar el incumplimiento.
- Cada ventana tiene 2,000 clientes. El intervalo del Gini mide entre 0.09 y 0.14 de ancho según el periodo, así que caídas de 0.05 se confunden con ruido. M01 cae 0.042 contra la referencia sin que haya deriva, en parte porque la referencia salió algo mejor que el promedio: su Gini es 0.518 y el de la muestra de desarrollo, convertido desde su AUC de 0.742, es 0.484.
- Los umbrales de PSI (0.10 y 0.25) son el criterio habitual. Los demás los fijé yo y no son estándares; habría que recalibrarlos con el tamaño de ventana real.
- Para separar una ruptura de datos de un cambio de población cuento las variables en rojo. La regla es simple y puede fallar: una ruptura que toque tres variables se leería como cambio de mezcla.
- Hay una sola ventana por receta. No medí con qué frecuencia acierta el sistema ni cuánto tarda en detectar una deriva gradual.
- La acción de GitHub corre con los datos de ejemplo. Para usarlo con una cartera real habría que reemplazar la base, definir qué es un periodo y revisar los umbrales.

## Cómo correrlo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/ejecutar_todo.py
python -m pytest
```

Pasos: `paso1_modelo_desarrollo.py` entrena y fija la línea base, `paso2_ventanas.py` arma los meses con deriva, `paso3_metricas.py` calcula las métricas, `paso4_alertas.py` aplica los umbrales y `paso5_reporte.py` escribe el HTML. Para el reporte de otro periodo: `python src/paso5_reporte.py --periodo M04`. Con la variable `MONITOREO_DATOS` se puede apuntar a otra base con el mismo formato.

Las salidas quedan en `resultados/`: `reporte_mensual.html`, `alertas.csv`, `monitoreo_metricas.csv`, `monitoreo_variables.csv`, `monitoreo_bandas.csv`, `monitoreo_semaforos.csv`, `monitoreo_resumen.csv` y `modelo_pd.json`.

La acción `.github/workflows/monitoreo_mensual.yml` corre el día 1 de cada mes (y a pedido) con los datos de ejemplo del repositorio y sube el reporte y las alertas como artefactos. Otra acción corre las pruebas en cada cambio.

## Documentación de decisiones

`docs/bitacora.md` registra las decisiones, incluidas las correcciones que hice después de ver resultados que no tenían sentido.

## Referencia

Yeh, I. C. y Lien, C. H. (2009). The comparisons of data mining techniques for the predictive accuracy of probability of default of credit card clients. Expert Systems with Applications, 36(2).

Licencia MIT.
