# Seguridad

## Cómo reportar un problema

Si encuentras una vulnerabilidad, repórtala de forma privada desde la pestaña Security de este repositorio, con la opción "Report a vulnerability". Por favor no abras un issue público con los detalles.

## Alcance

Es un proyecto académico que corre en la computadora de quien lo usa o en una acción programada de GitHub. No tiene servidor, cuentas de usuario ni datos personales.

- Usa solo datos públicos (UCI) y deriva simulada. No contiene información de ningún banco ni de sus clientes.
- Al correr no descarga nada: la base viene en `datos/`. El código del análisis no hace llamadas de red ni usa subprocesos con shell; `ejecutar_todo.py` lanza los pasos con una lista de argumentos.
- El modelo se guarda como JSON, no como pickle, para que cargarlo no ejecute código.
- Los umbrales se leen con `yaml.safe_load` y se validan antes de usarse.
- El reporte HTML escapa todo texto que viene de los datos, no incluye JavaScript ni recursos externos y trae una política CSP que bloquea scripts, conexiones y formularios.
- Las dependencias están fijadas a una versión y Dependabot las revisa cada semana. Las acciones de GitHub están fijadas a un commit y los flujos piden solo permiso de lectura.
