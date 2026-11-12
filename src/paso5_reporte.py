"""Paso 5. Reporte mensual en un solo archivo HTML, sin JavaScript ni recursos externos.

Todo texto que viene de los datos pasa por html.escape. La página trae una política CSP
que bloquea scripts, conexiones, formularios y cualquier carga externa."""
import argparse
import html

import pandas as pd

from comun import N_BANDAS, SALIDA, cargar_modelo, cargar_umbrales
from semaforos import AMBAR, ROJO, VERDE

CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
       "base-uri 'none'; form-action 'none'")

NOMBRES = {
    "psi_puntuacion": "PSI de la puntuación", "psi_variable_max": "PSI máximo de variables",
    "csi_abs_max": "CSI máximo (absoluto)", "caida_gini": "Caída del Gini",
    "caida_ks": "Caída del KS", "desv_calibracion": "Desviación de calibración",
    "bandas_rechazadas": "Bandas nuevas rechazadas", "desplazamiento_rangos_pp": "Cambio de rangos (pp)",
    "cambio_tasa_relativo": "Cambio de la tasa de incumplimiento",
}
RELATIVOS = {"desv_calibracion", "cambio_tasa_relativo"}
ENTEROS = {"bandas_rechazadas"}

SECCIONES = [("resumen", "Resumen"), ("semaforos", "Semáforos"), ("tendencia", "Tendencia"), ("cifras", "Cifras"),
             ("bandas", "Bandas"), ("variables", "Variables"), ("historial", "Historial")]

CSS = """
:root{color-scheme:light dark;--fondo:#fff;--sup:#f5f5f7;--tinta:#1d1d1f;--suave:#6e6e73;--linea:rgba(0,0,0,.12);
--acento:#0071e3;--rojo:#d70015;--ambar:#b25000;--ambar-f:#ff9f0a;--verde:#1d7a3a;
--tv:rgba(29,122,58,.22);--ta:rgba(255,159,10,.30);--tr:rgba(215,0,21,.22);
--vidrio:rgba(255,255,255,.72);--expo:cubic-bezier(.16,1,.3,1);--gut:clamp(20px,5vw,48px);
--fuente:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue",Arial,sans-serif;
interpolate-size:allow-keywords}
@media (prefers-color-scheme:dark){:root{--fondo:#000;--sup:#1c1c1e;--tinta:#f5f5f7;--suave:#a1a1a6;
--linea:rgba(255,255,255,.16);--acento:#2997ff;--rojo:#ff453a;--ambar:#ff9f0a;--ambar-f:#ff9f0a;--verde:#30d158;
--tv:rgba(48,209,88,.24);--ta:rgba(255,159,10,.30);--tr:rgba(255,69,58,.30);--vidrio:rgba(0,0,0,.66)}}
*{box-sizing:border-box}
html{scroll-padding-top:96px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);font:1rem/1.55 var(--fuente);
-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
@media (prefers-color-scheme:dark){body{line-height:1.6;letter-spacing:.005em}}
::selection{background:var(--acento);color:#fff}
a{color:var(--acento);text-underline-offset:.2em}
a:focus-visible,summary:focus-visible{outline:2px solid var(--acento);outline-offset:3px;border-radius:6px}
*{scrollbar-color:var(--suave) transparent}
.col{max-width:1120px;margin:0 auto;padding-inline:var(--gut)}
h1,h2,h3{font-family:var(--fuente);text-wrap:balance}
h1{font-size:clamp(3.25rem,11.5vw,6rem);font-weight:700;letter-spacing:-.035em;line-height:1.02;margin:0 0 .28em}
h2{font-size:clamp(1.875rem,4.4vw,2.75rem);font-weight:700;letter-spacing:-.03em;line-height:1.08;margin:0 0 16px}
h3{font-size:1.1875rem;font-weight:600;letter-spacing:-.015em;margin:0 0 4px}
p{margin:0 0 12px}

/* barra de navegación */
.barra{position:fixed;inset:0 0 auto 0;z-index:10;background:var(--fondo);border-bottom:1px solid var(--linea)}
@supports ((-webkit-backdrop-filter:blur(1px)) or (backdrop-filter:blur(1px))){
.barra{background:var(--vidrio);-webkit-backdrop-filter:saturate(180%) blur(22px);backdrop-filter:saturate(180%) blur(22px)}}
.barra .col{display:flex;align-items:center;justify-content:space-between;gap:24px;min-height:52px}
.marca{color:var(--tinta);font-weight:600;font-size:.9375rem;letter-spacing:-.01em;text-decoration:none;white-space:nowrap}
.barra nav{display:flex;gap:4px;overflow-x:auto;min-width:0;max-width:calc(100% + 16px);scrollbar-width:none;margin-inline:-8px}
.barra nav::-webkit-scrollbar{display:none}
.barra nav a{color:var(--suave);font-size:.8125rem;font-weight:500;text-decoration:none;padding:8px;border-radius:8px;white-space:nowrap;transition:color .2s}
.barra nav a:hover{color:var(--tinta)}
@media (max-width:760px){.barra .col{width:100%;flex-direction:column;align-items:stretch;gap:0;padding-top:8px}
.marca{font-size:.875rem}.barra nav{margin-inline:-8px;padding-bottom:2px}}

/* portada */
.hero{position:relative;padding:clamp(150px,17vw,210px) 0 clamp(48px,8vw,96px);isolation:isolate}
.hero::before{content:"";position:absolute;inset:0;z-index:-1;opacity:.55;
background:radial-gradient(60% 70% at 88% -5%,var(--nt,transparent),transparent 72%)}
.hero.n-rojo{--nt:var(--tr)}.hero.n-ambar{--nt:var(--ta)}.hero.n-verde{--nt:var(--tv)}
.porque{font-size:clamp(1.25rem,2.4vw,1.75rem);line-height:1.35;letter-spacing:-.015em;max-width:34em;margin:0 0 28px;text-wrap:pretty}
.estado{display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px;margin:0 0 clamp(48px,8vw,88px)}
.estado .sub{margin:0;color:var(--suave);font-size:.9375rem;max-width:62ch}
.nivel-g{display:inline-flex;align-items:center;gap:8px;font-size:.8125rem;font-weight:600;padding:5px 14px 5px 11px;border-radius:999px;
border:1px solid currentColor;white-space:nowrap}
.nivel-g::before,.pt-n::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block;flex:none}
.verde{color:var(--verde)}.ambar{color:var(--ambar)}.rojo{color:var(--rojo)}

/* franja de cifras, rejilla asimetrica */
.cifras{display:grid;grid-template-columns:1.75fr 1fr 1fr 1fr;gap:0 clamp(20px,3vw,40px);margin:0;align-items:end}
.cifra{border-top:1px solid var(--tinta);padding-top:14px;margin:0}
.cifra dt{color:var(--suave);font-size:.8125rem;font-weight:600;margin:0 0 6px}
.cifra dd{margin:0}
.cifra .n{display:block;font-size:clamp(2.25rem,5.4vw,3.5rem);font-weight:600;letter-spacing:-.035em;line-height:1.05}
.cifra.mayor .n{font-size:clamp(3.5rem,9.5vw,6rem);font-weight:700;letter-spacing:-.04em;line-height:1}
.cifra .ref{display:block;color:var(--suave);font-size:.8125rem;margin-top:8px}
@media (max-width:760px){.cifras{grid-template-columns:1fr 1fr;gap:32px 24px}.cifra.mayor{grid-column:1/-1}}

/* secciones */
.sec{padding:clamp(56px,9vw,120px) 0 0;scroll-margin-top:72px}
.sec>.col{background:linear-gradient(var(--linea),var(--linea)) top/100% 1px no-repeat;padding-top:clamp(40px,6vw,72px)}
.cab p{color:var(--suave);font-size:1rem;max-width:56ch;margin:0 0 24px}
.dividida{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,8fr);gap:0 clamp(32px,5vw,72px);align-items:start}
.dividida .cab{position:sticky;top:96px}
@media (max-width:900px){.dividida{display:block}.dividida .cab{position:static}}
.nota{color:var(--suave);font-size:.875rem;max-width:80ch;margin:20px 0 0}

/* lista de semaforos */
.lista{list-style:none;margin:0;padding:0}
.ind{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr) 5.5rem;grid-template-areas:"n t v";gap:4px 28px;align-items:center;
padding:22px 0;border-bottom:1px solid var(--linea)}
.ind:first-child{padding-top:0}
.ind .n{grid-area:n}.ind .t{grid-area:t}.ind .v{grid-area:v;text-align:right}
.ind h3{font-size:1.0625rem;margin:0}
.ind .d{display:block;color:var(--suave);font-size:.875rem;line-height:1.4;margin-top:4px}
.ind .v b{display:block;font-size:1.75rem;font-weight:600;letter-spacing:-.03em;line-height:1.1}
.ind .v span{font-size:.8125rem;font-weight:600}
.pista{position:relative;height:50px;container-type:inline-size;margin-inline:8px}
.riel{position:absolute;inset:14px 0 auto 0;height:8px;border-radius:4px;
background:linear-gradient(90deg,var(--tv) calc(var(--a)*1%),var(--ta) calc(var(--a)*1%),var(--ta) calc(var(--r)*1%),var(--tr) calc(var(--r)*1%))}
.tk{position:absolute;top:10px;height:16px;width:1px;background:var(--suave)}
.tk.a{left:calc(var(--a)*1%)}.tk.r{left:calc(var(--r)*1%)}
.tl{position:absolute;top:29px;transform:translateX(-50%);font-size:.8125rem;color:var(--suave);white-space:nowrap}
.tl.a{left:calc(var(--a)*1%);color:var(--ambar)}.tl.r{left:calc(var(--r)*1%);color:var(--rojo)}
.mk{position:absolute;top:11px;left:0;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:var(--c);
border:2px solid var(--fondo);box-shadow:0 1px 3px rgba(0,0,0,.35);translate:calc(var(--v)*1cqw) 0}
.mk.verde{--c:var(--verde)}.mk.ambar{--c:var(--ambar-f)}.mk.rojo{--c:var(--rojo)}
.mk.rojo::after{content:"";position:absolute;inset:-6px;border-radius:50%;border:2px solid var(--rojo);opacity:0}
@media (max-width:640px){.ind{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"n v" "t t";gap:6px 16px;padding:20px 0}
.ind .v b{font-size:1.5rem}}
details{margin-top:8px}
summary{cursor:pointer;color:var(--acento);font-weight:600;padding:14px 0;list-style:none;display:flex;align-items:center;gap:10px}
summary::-webkit-details-marker{display:none}
summary::after{content:"";width:8px;height:8px;border:solid currentColor;border-width:0 2px 2px 0;transform:rotate(45deg) translateY(-2px);
transition:transform .35s var(--expo)}
details[open] summary::after{transform:rotate(-135deg) translate(-1px,-1px)}
@supports selector(::details-content){
details::details-content{block-size:0;overflow:clip;opacity:0;transition:block-size .5s var(--expo),opacity .35s ease,content-visibility .5s allow-discrete}
details[open]::details-content{block-size:auto;opacity:1}}

/* tablas, lineas finas */
.envoltura{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9375rem}
th,td{padding:12px 14px;border-bottom:1px solid var(--linea);text-align:right;vertical-align:top}
th{color:var(--suave);font-weight:600;font-size:.8125rem;border-bottom-color:var(--tinta);white-space:nowrap}
th:first-child,td:first-child{text-align:left;padding-left:0}th:last-child,td:last-child{padding-right:0}
td{white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr{transition:background-color .2s}
@media (hover:hover){tbody tr:hover{background:var(--sup)}}
td.nivel{font-weight:600}
.pt-n{display:inline-flex;align-items:center;gap:8px}
@media (max-width:640px){
.envoltura{overflow:visible}
table,tbody,tr,td{display:block}
thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
tr{padding:14px 0;border-bottom:1px solid var(--linea)}tbody tr:last-child{border-bottom:0}
td{display:flex;justify-content:space-between;gap:20px;border:0;padding:3px 0;white-space:normal;text-align:right}
td::before{content:attr(data-l);color:var(--suave);font-size:.8125rem;text-align:left;flex:none}
td:first-child{font-size:1.0625rem;font-weight:600;padding-bottom:6px}td:first-child::before{content:none}
td:empty{display:none}
th:first-child,td:first-child{padding-left:0}}

/* graficas fluidas: texto en HTML a 13 px, trazos en SVG sin escalar */
.graf{margin:0 0 clamp(48px,7vw,80px)}
.graf:last-child{margin-bottom:0}
.leyenda{display:flex;flex-wrap:wrap;gap:6px 24px;margin:0 0 20px;color:var(--suave);font-size:.8125rem}
.leyenda span{display:inline-flex;align-items:center;gap:8px}
.leyenda i{width:18px;height:3px;border-radius:2px;background:var(--c)}
.leyenda b{color:var(--tinta);font-weight:600}
.c-acento{--c:var(--acento)}.c-suave{--c:var(--suave)}.c-rojo{--c:var(--rojo)}.c-ambar{--c:var(--ambar-f)}
.plot{position:relative;height:clamp(230px,30vw,340px);margin:6px 0 44px 46px}
.plot>*{position:absolute}
.gl{left:0;right:0;height:1px;background:var(--linea)}
.ey,.ex,.um-t{font-size:.8125rem;line-height:1;color:var(--suave);white-space:nowrap}
.ey{right:100%;margin-right:10px;transform:translateY(-50%)}
.um-t.c-rojo{color:var(--rojo)}.um-t.c-ambar{color:var(--ambar)}.um-t.c-suave{color:var(--suave)}
.zona{left:0;right:0;background:var(--c);opacity:.14}
.zona.c-rojo{opacity:.10}
.um{left:0;right:0;height:0;border-top:1.5px dashed var(--c)}
.um-t{right:0;transform:translateY(calc(-100% - 6px));font-weight:600;
text-shadow:0 0 6px var(--fondo),0 0 3px var(--fondo)}
.lienzo{inset:0 18px}
.lienzo>*{position:absolute}
.trazos{inset:0;width:100%;height:100%;overflow:visible}
.trazos polyline{fill:none;stroke:var(--c);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
.ic{width:2px;margin-left:-1px;background:var(--c);opacity:.45;border-radius:1px}
.pt{width:9px;height:9px;margin:-4.5px 0 0 -4.5px;border-radius:50%;background:var(--c);border:2px solid var(--fondo);box-sizing:content-box;
transition:transform .25s var(--expo)}
.pt::before{content:"";position:absolute;inset:-9px}
.pt:hover{transform:scale(1.5)}
.pt::after{content:attr(data-v);position:absolute;left:50%;bottom:calc(100% + 8px);transform:translateX(-50%);padding:4px 8px;border-radius:8px;
background:var(--tinta);color:var(--fondo);font-size:.8125rem;font-weight:600;white-space:nowrap;display:none;pointer-events:none;z-index:3}
.pt:hover::after{display:block}
.pt.ult::after{left:auto;right:-6px;transform:none}
.ex{top:100%;margin-top:12px;transform:translateX(-50%)}
@media (max-width:640px){.plot{margin-left:42px;height:240px}.ex.salto{display:none}}

.cierre p{max-width:62ch;font-size:1.0625rem}
.pie{height:clamp(56px,9vw,120px)}

/* movimiento: solo si el usuario no pidio reducirlo; el contenido es visible por defecto */
@media (prefers-reduced-motion:no-preference){
html{scroll-behavior:smooth}
@keyframes sube{from{opacity:0;transform:translateY(22px);filter:blur(8px)}to{opacity:1;transform:none;filter:blur(0)}}
@keyframes rise{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
@keyframes pulso{0%{transform:scale(.7);opacity:.55}70%,100%{transform:scale(1.7);opacity:0}}
@keyframes pulsoc{0%{box-shadow:0 0 0 0 currentColor}70%,100%{box-shadow:0 0 0 7px transparent}}
@keyframes trazo{from{stroke-dashoffset:2400px}to{stroke-dashoffset:0}}
@keyframes entra{from{opacity:0;scale:.4}to{opacity:1;scale:1}}
@keyframes desliza{from{translate:0 0}}
@keyframes velo{from{opacity:0}}
.hero .e{animation:sube 1.05s var(--expo) both;animation-delay:calc(var(--d,0)*110ms)}
.nivel-g.rojo::before{animation:pulsoc 2.4s ease-out infinite}
.mk.rojo::after{animation:pulso 2.4s ease-out infinite}
.barra{animation:velo .8s ease both}
@supports (animation-timeline:view()){
.rev{animation:rise linear both;animation-timeline:view();animation-range:entry 0% entry 60%}
.ind .mk{animation:desliza linear both;animation-timeline:view();animation-range:entry 10% entry 90%}
.plot{view-timeline-name:--g}
.trazos polyline{stroke-dasharray:2400px;animation:trazo linear both;animation-timeline:--g;animation-range:entry 0% entry 85%}
.pt,.ic{animation:velo linear both;animation-timeline:--g;animation-range:entry 55% entry 100%}
}}

@media print{
:root{--fondo:#fff;--sup:#f5f5f7;--tinta:#000;--suave:#444;--linea:rgba(0,0,0,.25)}
*,*::before,*::after{animation:none!important;transition:none!important}
.barra{display:none}
.hero{padding-top:0}.hero::before{display:none}
.sec{padding-top:32px}
.col{max-width:none;padding-inline:0}
.dividida{display:block}.dividida .cab{position:static}
.graf,.ind,tr,.cifra{break-inside:avoid}
.pt::after{display:none}
details::details-content{block-size:auto;opacity:1;content-visibility:visible}
summary{color:var(--tinta)}
}
"""
CSS += "".join(f'body:has(#{i}:target) .barra nav a[href="#{i}"]{{color:var(--tinta)}}\n' for i, _ in SECCIONES)


def e(valor) -> str:
    return html.escape(str(valor), quote=True)


def num(v: float, nombre: str = "") -> str:
    if nombre in ENTEROS:
        return f"{int(v)}"
    if nombre in RELATIVOS:
        return f"{v:.1%}"
    if nombre == "desplazamiento_rangos_pp":
        return f"{v:.1f}"
    return f"{v:.3f}"


def clase_nivel(nivel: str) -> str:
    return "ambar" if nivel == AMBAR else nivel


def sello(nivel: str) -> str:
    return f'<span class="nivel-g {e(clase_nivel(nivel))}">Semáforo {e(nivel)}</span>'


def celda_nivel(nivel: str) -> str:
    return f'<td class="nivel {e(clase_nivel(nivel))}"><span class="pt-n">{e(nivel)}</span></td>'


def tabla(encabezados: list[str], filas: list[list[str]]) -> str:
    """Las celdas ya vienen escapadas o son HTML propio (celda_nivel). Cada celda lleva su
    encabezado en data-l para que en pantallas angostas la fila se apile sin desplazamiento."""
    th = "".join(f"<th>{e(h)}</th>" for h in encabezados)
    cuerpo = "".join(
        "<tr>" + "".join(c.replace("<td", f'<td data-l="{e(h)}"', 1) for c, h in zip(f, encabezados)) + "</tr>"
        for f in filas)
    return f'<div class="envoltura rev"><table><thead><tr>{th}</tr></thead><tbody>{cuerpo}</tbody></table></div>'


def td(v) -> str:
    return f"<td>{e(v)}</td>"


def fila_semaforo(f) -> str:
    """Un indicador con su mini escala: verde hasta el umbral ámbar, ámbar hasta el rojo y rojo después.
    El rojo cae siempre a dos tercios de la pista; el valor se ubica en la misma escala."""
    cl = clase_nivel(f.nivel)
    tope = f.umbral_rojo * 1.5
    pa = f.umbral_ambar / tope * 100
    pv = min(max(f.valor, 0.0) / tope * 100, 100.0)
    return (f'<li class="ind rev"><div class="n"><h3>{e(NOMBRES.get(f.indicador, f.indicador))}</h3>'
            f'<span class="d">{e(f.descripcion)}</span></div>'
            f'<div class="t"><div class="pista" role="img" aria-label="{e(NOMBRES.get(f.indicador, f.indicador))}: '
            f'{e(num(f.valor, f.indicador))}; ámbar desde {e(num(f.umbral_ambar, f.indicador))}, '
            f'rojo desde {e(num(f.umbral_rojo, f.indicador))}" style="--a:{pa:.2f};--r:66.67;--v:{pv:.2f}">'
            f'<div class="riel"></div><i class="tk a"></i><i class="tk r"></i>'
            f'<span class="tl a">{e(num(f.umbral_ambar, f.indicador))}</span>'
            f'<span class="tl r">{e(num(f.umbral_rojo, f.indicador))}</span>'
            f'<i class="mk {e(cl)}"></i></div></div>'
            f'<div class="v"><b>{e(num(f.valor, f.indicador))}</b><span class="{e(cl)}">{e(f.nivel)}</span></div></li>')


def grafica(titulo: str, explica: str, periodos: list[str], series: list[tuple], lineas: list[tuple] = (),
            ymin: float = 0.0, ymax: float | None = None, formato: str = "{:.2f}",
            intervalos: dict | None = None, zonas: list[tuple] = ()) -> str:
    """Gráfica fluida. series: (nombre, valores, color). Las líneas son SVG sin escalar el trazo y todo el
    texto va en HTML a 13 px, así se lee igual a 375 px que a 1280 px. zonas: (desde, hasta, color)."""
    valores = [v for _, vs, _ in series for v in vs] + [l[0] for l in lineas]
    if intervalos:
        valores += [v for par in intervalos.values() for v in par]
    tope = ymax if ymax is not None else max(valores) * 1.1 or 1.0
    rango = (tope - ymin) or 1.0
    n = len(periodos)

    def px(i):
        return 100 * i / max(1, n - 1)

    def py(v):
        return 100 * (1 - (min(max(v, ymin), tope) - ymin) / rango)

    plot = []
    for k in range(5):
        v = ymin + rango * k / 4
        plot.append(f'<i class="gl" style="top:{py(v):.2f}%"></i>'
                    f'<span class="ey" style="top:{py(v):.2f}%">{e(formato.format(v))}</span>')
    for desde, hasta, color in zonas:
        plot.append(f'<i class="zona c-{e(color)}" style="top:{py(hasta):.2f}%;height:{py(desde) - py(hasta):.2f}%"></i>')
    for valor, etiqueta, color in lineas:
        plot.append(f'<i class="um c-{e(color)}" style="top:{py(valor):.2f}%"></i>'
                    f'<span class="um-t c-{e(color)}" style="top:{py(valor):.2f}%">{e(etiqueta)}</span>')
    lienzo = []
    for nombre, vs, color in series:
        puntos = " ".join(f"{px(i):.2f},{py(v):.2f}" for i, v in enumerate(vs))
        lienzo.append(f'<svg class="trazos c-{e(color)}" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
                      f'<polyline points="{puntos}" pathLength="1"/></svg>')
        if intervalos and nombre in intervalos:
            for i, (lo, hi) in enumerate(zip(*intervalos[nombre])):
                lienzo.append(f'<i class="ic c-{e(color)}" style="left:{px(i):.2f}%;top:{py(hi):.2f}%;height:{py(lo) - py(hi):.2f}%"></i>')
        for i, v in enumerate(vs):
            ult = " ult" if i == len(vs) - 1 else ""
            lienzo.append(f'<i class="pt{ult} c-{e(color)}" style="left:{px(i):.2f}%;top:{py(v):.2f}%" '
                          f'data-v="{e(periodos[i])}: {e(formato.format(v))}"></i>')
    paso = 1 if n <= 6 else 2
    for i, p in enumerate(periodos):
        extra = " salto" if i % paso and i != n - 1 else ""
        lienzo.append(f'<span class="ex{extra}" style="left:{px(i):.2f}%">{e(p)}</span>')
    plot.append(f'<div class="lienzo">{"".join(lienzo)}</div>')
    leyenda = "".join(f'<span class="c-{e(c)}"><i></i>{e(nm)} <b>{e(formato.format(vs[-1]) if "%" in formato else f"{vs[-1]:.3f}")}</b></span>' for nm, vs, c in series)
    resumen = "; ".join(f"{nm}: " + ", ".join(f"{p} {formato.format(v)}" for p, v in zip(periodos, vs)) for nm, vs, _ in series)
    return (f'<figure class="graf rev" style="margin-inline:0"><div class="cab"><h3>{e(titulo)}</h3><p>{e(explica)}</p></div>'
            f'<div class="leyenda">{leyenda}</div>'
            f'<div class="plot" role="img" aria-label="{e(titulo)}. {e(resumen)}">{"".join(plot)}</div></figure>')


def seccion(id_: str, contenido: str, clase: str = "") -> str:
    return f'<section class="sec" id="{e(id_)}"><div class="col {e(clase)}">{contenido}</div></section>'


def generar_html(resumen: pd.DataFrame, evaluaciones: pd.DataFrame, periodos: pd.DataFrame,
                 variables: pd.DataFrame, bandas: pd.DataFrame, modelo: dict, cfg: dict,
                 periodo: str, descripcion: dict | None = None) -> str:
    """Arma la página del periodo elegido, con el historial de todos los anteriores."""
    descripcion = descripcion or {}
    r = resumen[resumen["periodo"] == periodo].iloc[0]
    p = periodos[periodos["periodo"] == periodo].iloc[0]
    ev = evaluaciones[evaluaciones["periodo"] == periodo]
    ref = modelo["referencia"]
    hasta = list(resumen["periodo"]).index(periodo) + 1
    hist = resumen.iloc[:hasta]
    nombres = list(hist["periodo"])
    ind = cfg["indicadores"]

    ev_ord = ev.assign(_o=ev["nivel"].map({ROJO: 0, AMBAR: 1, VERDE: 2})).sort_values("_o", kind="stable")
    atencion = [fila_semaforo(f) for f in ev_ord.itertuples() if f.nivel != VERDE]
    en_verde = [fila_semaforo(f) for f in ev_ord.itertuples() if f.nivel == VERDE]
    bloque_ind = (f'<ul class="lista">{"".join(atencion)}</ul>' if atencion
                  else '<p class="rev">Ningún indicador está en rojo ni en ámbar.</p>')
    if en_verde:
        abierto = "" if atencion else " open"
        bloque_ind += (f'<details{abierto}><summary>Indicadores en verde ({len(en_verde)})</summary>'
                       f'<ul class="lista">{"".join(en_verde)}</ul></details>')

    g_psi = grafica("PSI por periodo", "Qué tanto cambió la población o la puntuación frente a la referencia; más alto, más cambio.", nombres,
                    [("Puntuación", list(hist["psi_puntuacion"]), "acento"),
                     ("Variable con más cambio", list(hist["psi_variable_max"]), "suave")],
                    lineas=[(ind["psi_puntuacion"]["ambar"], "ámbar", "ambar"),
                            (ind["psi_puntuacion"]["rojo"], "rojo", "rojo")],
                    ymax=max(0.4, float(hist["psi_variable_max"].max()) * 1.05),
                    zonas=[(ind["psi_puntuacion"]["ambar"], ind["psi_puntuacion"]["rojo"], "ambar"),
                           (ind["psi_puntuacion"]["rojo"], max(0.4, float(hist["psi_variable_max"].max()) * 1.05), "rojo")])
    g_gini = grafica("Gini con intervalo", "Capacidad del modelo para ordenar a buenos y malos pagadores; la barra vertical es el intervalo de confianza.", nombres,
                     [("Gini", list(hist["gini"]), "acento")],
                     lineas=[(ref["gini"], "referencia", "suave"),
                             (ref["gini"] - ind["caida_gini"]["rojo"], "rojo", "rojo")],
                     ymin=0.0, ymax=0.7,
                     zonas=[(ref["gini"] - ind["caida_gini"]["rojo"], ref["gini"] - ind["caida_gini"]["ambar"], "ambar"),
                            (0.0, ref["gini"] - ind["caida_gini"]["rojo"], "rojo")],
                     intervalos={"Gini": (list(hist["gini_inf"]), list(hist["gini_sup"]))})
    g_tasa = grafica("PD predicha y tasa observada", "Calibración: si lo que el modelo predice se parece a lo que realmente ocurrió.", nombres,
                     [("Observada", list(hist["tasa_incumplimiento"]), "rojo"),
                      ("Predicha", list(hist["pd_media"]), "acento")],
                     ymin=0.0, ymax=max(0.4, float(hist["tasa_incumplimiento"].max()) * 1.1),
                     formato="{:.0%}")

    b = bandas[bandas["periodo"] == periodo].sort_values("banda")
    filas_b = []
    for f in b.itertuples():
        marca = "rechazada" if f.rechaza_nueva else ("rechazada desde la referencia" if f.rechaza_en_ref else "")
        filas_b.append([td(f"B{f.banda}"), td(f"{f.clientes:,}"), td(f"{f.peso_ref:.1%}"), td(f"{f.peso_periodo:.1%}"),
                        td(f"{f.pd_predicha:.1%}"), td(f"{f.tasa_observada:.1%}"),
                        td(f"{f.obs_inf:.1%} a {f.obs_sup:.1%}"), td(f"{f.valor_p:.3f}"), td(marca)])

    v = variables[variables["periodo"] == periodo].sort_values("psi", ascending=False)
    u_psi = ind["psi_variable_max"]
    filas_v = []
    for f in v.itertuples():
        niv = ROJO if f.psi >= u_psi["rojo"] else (AMBAR if f.psi >= u_psi["ambar"] else VERDE)
        filas_v.append([td(f.variable), td(f"{f.psi:.3f}"), td(f"{f.csi:+.3f}"),
                        td(f"{f.media_ref:.3f}"), td(f"{f.media_periodo:.3f}"), celda_nivel(niv)])

    filas_h = []
    for q in periodos.iloc[:hasta].itertuples():
        filas_h.append([td(q.periodo), td(q.escenario), celda_nivel(q.semaforo), td(q.accion),
                        td(q.indicadores_rojos), td(q.indicadores_ambar)])

    def con_ic(v, lo, hi):
        return f"{v:.3f} ({lo:.3f} a {hi:.3f})"

    filas_cifras = [
        [td("Clientes"), td(f"{int(r.clientes):,}"), td(f"{ref['n']:,}")],
        [td("Incumplimientos"), td(f"{int(r.incumplen):,}"), td(f"{round(ref['n'] * ref['tasa_incumplimiento']):,}")],
        [td("Tasa observada"), td(f"{r.tasa_incumplimiento:.1%} ({r.tasa_inf:.1%} a {r.tasa_sup:.1%})"),
         td(f"{ref['tasa_incumplimiento']:.1%}")],
        [td("PD predicha media"), td(f"{r.pd_media:.1%}"), td(f"{ref['pd_media']:.1%}")],
        [td("AUC"), td(con_ic(r.auc, r.auc_inf, r.auc_sup)), td(con_ic(ref["auc"], ref["auc_inf"], ref["auc_sup"]))],
        [td("Gini"), td(con_ic(r.gini, r.gini_inf, r.gini_sup)), td(con_ic(ref["gini"], ref["gini_inf"], ref["gini_sup"]))],
        [td("KS"), td(con_ic(r.ks, r.ks_inf, r.ks_sup)), td(con_ic(ref["ks"], ref["ks_inf"], ref["ks_sup"]))],
    ]

    d_txt = descripcion.get(periodo, "")
    cl = clase_nivel(p.semaforo)

    def cifra(etq, valor, ref_txt, mayor=False, d=0):
        return (f'<div class="cifra{" mayor" if mayor else ""} e" style="--d:{d}"><dt>{e(etq)}</dt>'
                f'<dd><span class="n">{e(valor)}</span><span class="ref">Referencia {e(ref_txt)}</span></dd></div>')

    rg, rk = f"{ref['gini']:.3f}", f"{ref['ks']:.3f}"
    rt, rp = f"{ref['tasa_incumplimiento']:.1%}", f"{ref['pd_media']:.1%}"
    g_, k_ = f"{r.gini:.3f}", f"{r.ks:.3f}"
    t_, m_ = f"{r.tasa_incumplimiento:.1%}", f"{r.pd_media:.1%}"
    nav = "".join(f'<a href="#{i}">{e(t)}</a>' for i, t in SECCIONES)
    barra = (f'<header class="barra"><div class="col"><a class="marca" href="#resumen">'
             f'Monitoreo del modelo de PD: {e(periodo)}</a><nav aria-label="Secciones">{nav}</nav></div></header>')

    hero = (f'<section class="hero n-{e(cl)}" id="resumen"><div class="col">'
            f'<h1 class="e">{e(p.accion)}</h1>'
            f'<p class="porque e" style="--d:1">{e(p.motivo)}</p>'
            f'<div class="estado e" style="--d:2">{sello(p.semaforo)}'
            f'<p class="sub">Escenario simulado: {e(p.escenario)}. {e(d_txt)} Datos públicos de UCI con deriva inducida; '
            f'no hay información de ningún banco.</p></div>'
            f'<dl class="cifras">'
            f'{cifra("Gini", g_, rg, True, 3)}'
            f'{cifra("KS", k_, rk, d=4)}'
            f'{cifra("Tasa observada", t_, rt, d=5)}'
            f'{cifra("PD predicha media", m_, rp, d=6)}'
            f'</dl></div></section>')

    s_sem = seccion("semaforos", f"""
<div class="cab"><h2>Semáforos del periodo</h2>
<p>PSI mide cuánto se movió la distribución frente a la referencia. CSI reparte ese movimiento por variable.
KS y Gini miden qué tan bien separa el modelo a quienes incumplen de quienes no. La calibración compara la PD predicha con la tasa que ocurrió.</p>
<p>En cada escala, las marcas señalan dónde empieza el ámbar y el rojo, y el punto es el valor del periodo.</p></div>
<div>{bloque_ind}</div>""", "dividida")

    s_ten = seccion("tendencia", f"""
<div class="cab"><h2>Tendencia</h2></div>
{g_psi}{g_gini}{g_tasa}""")

    s_cif = seccion("cifras", f"""
<div class="cab"><h2>Cifras contra la referencia</h2></div>
<div>{tabla(["Medida", "Periodo", "Referencia"], filas_cifras)}
<p class="nota rev">AUC es la probabilidad de que el modelo asigne más riesgo a un cliente que incumple que a uno que no.
La referencia son {ref['n']:,} clientes que el modelo no vio en el entrenamiento.
Los intervalos del AUC, el Gini y el KS son bootstrap de {int(cfg['intervalo_bootstrap'] * 100)}%; el de la tasa es de Wilson.</p></div>""", "dividida")

    s_ban = seccion("bandas", f"""
<div class="cab"><h2>Calibración y estabilidad de rangos por banda de PD</h2></div>
{tabla(["Banda", "Clientes", "Peso en referencia", "Peso en el periodo", "PD predicha", "Tasa observada", "Intervalo de la tasa", "Valor p binomial", "Resultado"], filas_b)}
<p class="nota rev">Las {N_BANDAS} bandas son quintiles de la PD en la muestra de referencia. La prueba binomial compara los incumplimientos observados con la PD media predicha de la banda;
rechaza con valor p menor que {cfg['alfa_binomial'] / N_BANDAS:.3f} (alfa {cfg['alfa_binomial']} entre {N_BANDAS} bandas).
Prueba global del periodo: valor p {r.p_binomial_global:.3f}. Bandas con orden de riesgo invertido respecto a la anterior: {int(r.bandas_orden_invertido)}.</p>""")

    s_var = seccion("variables", f"""
<div class="cab"><h2>Estabilidad de las variables</h2></div>
{tabla(["Variable", "PSI", "CSI", "Media en desarrollo", "Media en el periodo", "Nivel del PSI"], filas_v)}
<p class="nota rev">El CSI está en unidades de logit: cuánto movió el cambio de población a la puntuación del modelo, con signo.</p>""")

    s_his = seccion("historial", f"""
<div class="cab"><h2>Historial</h2></div>
{tabla(["Periodo", "Escenario", "Semáforo", "Acción", "Rojos", "Ámbar"], filas_h)}""")

    s_leer = seccion("leer", f"""
<div class="cab"><h2>Cómo leerlo</h2></div>
<div class="cierre"><p class="rev">El modelo es una regresión logística con cinco variables de comportamiento, entrenada con {int(modelo.get('n_desarrollo', 0)):,} clientes.
Los rangos de PSI y CSI se fijaron con la muestra de referencia. Un PSI menor a {ind['psi_puntuacion']['ambar']} se considera estable, entre {ind['psi_puntuacion']['ambar']} y {ind['psi_puntuacion']['rojo']} merece atención y mayor a {ind['psi_puntuacion']['rojo']} es un cambio importante.</p>
<p class="rev">Los meses M01 a M06 son simulados: se arman reordenando clientes de la base con recetas de deriva documentadas en el README. Sirven para comprobar que el sistema detecta lo que se le inyecta, no para decir algo de una cartera real.</p></div>""", "dividida")

    cuerpo = barra + "<main>" + hero + s_sem + s_ten + s_cif + s_ban + s_var + s_his + s_leer + '<div class="pie"></div></main>'
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{e(CSP)}">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Monitoreo del modelo de PD {e(periodo)}</title><style>{CSS}</style></head>'
            f'<body>{cuerpo}</body></html>')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--periodo", help="Periodo del reporte (por defecto, el último).")
    args = ap.parse_args()
    cfg, modelo = cargar_umbrales(), cargar_modelo()
    resumen = pd.read_csv(SALIDA / "monitoreo_metricas.csv")
    periodo = args.periodo or resumen["periodo"].iloc[-1]
    if periodo not in set(resumen["periodo"]):
        raise SystemExit(f"El periodo {periodo!r} no existe. Opciones: {', '.join(resumen['periodo'])}")
    from paso2_ventanas import ESCENARIOS
    pagina = generar_html(
        resumen, pd.read_csv(SALIDA / "monitoreo_semaforos.csv"), pd.read_csv(SALIDA / "monitoreo_resumen.csv"),
        pd.read_csv(SALIDA / "monitoreo_variables.csv"), pd.read_csv(SALIDA / "monitoreo_bandas.csv"),
        modelo, cfg, periodo, {x["periodo"]: x["descripcion"] for x in ESCENARIOS})
    destino = SALIDA / "reporte_mensual.html"
    destino.write_text(pagina, encoding="utf-8")
    print(f"Reporte de {periodo} escrito en {destino.relative_to(destino.parents[1])} ({len(pagina) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
