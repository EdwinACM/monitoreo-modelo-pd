# Bitácora de decisiones

Fecha de la corrida: 12 de noviembre de 2026. Semilla 42 en todos los pasos.

## Datos

1. Se usa la misma base de UCI que el proyecto de políticas de riesgo (30,000 clientes de tarjeta de Taiwán, abril a septiembre de 2005). Copié el CSV a `datos/` para que la acción de GitHub corra sin descargar nada. Con la variable de entorno `MONITOREO_DATOS` se puede apuntar a otro archivo con el mismo formato.
2. La base es un solo corte y no hay meses posteriores al desarrollo. Los "meses de monitoreo" son una simulación: ventanas de 2,000 clientes tomadas de una reserva, con recetas de deriva escritas en `paso2_ventanas.py`. Nada de lo que sale de ellas describe una cartera real.
3. Reparto al azar con semilla 42: 10,000 clientes para desarrollo, 5,000 para referencia y 15,000 de reserva. El modelo nunca ve la referencia ni la reserva.

## Modelo

4. Mismas cinco variables del proyecto de políticas, regresión logística con variables estandarizadas. Sexo, estado civil, educación y edad quedan fuera.
5. Se guarda como JSON (coeficientes, medias y escalas) y se puntúa con una función propia. Así no hay pickle y el modelo se puede leer directamente.
6. La línea base de Gini, KS y calibración se mide en la muestra de referencia y no en la de desarrollo, para no comparar contra una cifra optimista.

## Ventanas con deriva

7. Las ventanas sin cambio de mezcla se sacan primero y las que sesgan la mezcla al final. En la primera versión salían en orden, y la ventana de cambio de mezcla dejaba sin clientes de uso alto a las siguientes, que mostraban una deriva que yo no había pedido.
8. La primera versión del deterioro cambiaba la etiqueta de clientes elegidos al azar. Eso también destruía el orden de riesgo y el sistema pedía redesarrollar cuando el problema era de calibración. Ahora la probabilidad de cambio crece con los meses de atraso, que se parece más a un deterioro real.
9. Agregué una ventana de pérdida de poder (35% de las etiquetas sustituidas por un sorteo) para ejercitar el caso de redesarrollo.

## Métricas

10. PSI con los rangos de la referencia: deciles para variables continuas y un rango por valor cuando hay 12 valores distintos o menos. Los valores fuera del rango de referencia caen en el primer o el último rango. Las proporciones se acotan en 0.0001 para que el logaritmo exista.
11. CSI: el cambio de población de cada rango multiplicado por lo que ese rango aporta al logit del modelo. Está en unidades de logit y lleva signo. Se mide en valor absoluto para el semáforo.
12. AUC, Gini y KS con intervalo bootstrap percentil de 300 remuestras. La tasa de incumplimiento usa intervalo de Wilson.
13. Calibración: PD media predicha contra tasa observada, con prueba binomial global y por banda. Las bandas son quintiles de la PD en la referencia.
14. La primera versión rechazaba bandas con alfa de 0.05 sin corregir y el periodo M02, sin deriva, salía en ámbar. Con cinco bandas la falsa alarma ocurre en cerca de uno de cada cuatro meses, así que apliqué Bonferroni (alfa entre cinco).
15. Con esa corrección todavía se rechazaban las bandas 2 y 5 en la propia muestra de referencia (el modelo sobrestima la banda 2 y subestima la 5). Esa debilidad del modelo ya existía antes del monitoreo, así que el indicador cuenta solo las bandas que se rechazan ahora y no se rechazaban en la referencia.
16. La desviación de calibración solo cuenta cuando la prueba binomial global rechaza. Con 2,000 clientes una diferencia del 5% puede ser ruido.

## Semáforos y acciones

17. Los umbrales están en `config/umbrales.yaml`. PSI en 0.10 y 0.25 es el criterio habitual de la industria. Los demás (caída de Gini de 0.05 y 0.10, CSI de 0.05 y 0.15, cambio de rangos de 5 y 10 puntos) son decisiones mías, no estándares, y se ajustan al tamaño de la ventana. Se pueden cambiar sin tocar el código.
18. La acción se decide con reglas en orden (ver `semaforos.py`). Pocas variables en rojo hacen sospechar de la fuente de datos, que se revisa antes de tocar el modelo. Gini o KS en rojo piden redesarrollo, calibración en rojo con el orden conservado pide recalibrar, y un cambio de población sin pérdida de desempeño pide vigilar de cerca.
19. Para distinguir una ruptura de datos de un cambio de población cuento variables: rojo en una o dos es ruptura, en más es cambio de mezcla. La regla es sencilla y puede fallar; está en los límites del README.

## Reporte y acción programada

20. El reporte es un HTML sin JavaScript, con las gráficas como SVG en línea y una política CSP que prohíbe cargar recursos externos. Todo texto que viene de los datos pasa por `html.escape`.
21. La acción mensual corre el pipeline con los datos de ejemplo del repositorio y sube el reporte y el CSV de alertas como artefactos de la ejecución. No publica nada ni escribe en el repositorio.

## Cambios durante el análisis

22. Las decisiones 7, 8, 14 y 15 son correcciones hechas después de ver resultados que no tenían sentido. Las dejo escritas para que se vea qué cambió y por qué.
23. En la ventana de ruptura el CSI de `mora_sep` es 0.005 y su PSI es 0.271, así que el CSI no la detecta y el PSI sí. No investigué la causa. Conservo el CSI como indicador complementario.

## Cómo correrlo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/ejecutar_todo.py
python -m pytest
```
