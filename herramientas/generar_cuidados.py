#!/usr/bin/env python3
"""Genera las fichas de cuidado de jardinmalva.cl/cuidados a partir de datos/cuidados.json.

Uso:  python3 herramientas/generar_cuidados.py

Crea (y sobrescribe) public/cuidados/: una página por planta, el índice con buscador,
la hoja de estilos y el script. Solo usa la biblioteca estándar de Python.

Reglas que el script hace cumplir:
- Cada slug publicado queda registrado en datos/slugs-publicados.txt. Si una ficha
  publicada desaparece de los datos, el script se detiene: hay QR impresos que
  apuntan a ella. Para retirar una planta, déjala en los datos (puedes cambiar
  textos), pero nunca borres la ficha ni cambies su slug.
- La toxicidad para mascotas solo se publica con su fuente (ASPCA).
"""
import hashlib
import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos" / "cuidados.json"
REGISTRO = RAIZ / "datos" / "slugs-publicados.txt"
SALIDA = RAIZ / "public" / "cuidados"

DIFICULTAD = {1: "Fácil", 2: "Cuidado medio", 3: "Pide atención"}
TIPO_TEXTO = {"interior": "Planta de interior", "exterior": "Flor y exterior"}


def e(texto):
    return html.escape(str(texto), quote=True)


def normalizar(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- datos

def cargar():
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    errores = []
    vistos = set()
    for i, p in enumerate(datos["plantas"]):
        ref = p.get("slug", f"#{i}")
        for campo in ("slug", "nombre", "botanico", "tipo", "resumen", "dificultad",
                      "luz", "riego", "temperatura", "abono", "trasplante", "alertas"):
            if campo not in p:
                errores.append(f"{ref}: falta el campo '{campo}'")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p.get("slug", "")):
            errores.append(f"{ref}: slug no válido (solo minúsculas, números y guiones)")
        if p.get("slug") in vistos:
            errores.append(f"{ref}: slug repetido")
        vistos.add(p.get("slug"))
        if p.get("tipo") not in datos["grupos"]:
            errores.append(f"{ref}: tipo desconocido '{p.get('tipo')}'")
        if p.get("dificultad") not in DIFICULTAD:
            errores.append(f"{ref}: dificultad debe ser 1, 2 o 3")
        riego = p.get("riego", {})
        if "estaciones" not in riego and not ("calor" in riego and "frio" in riego):
            errores.append(f"{ref}: el riego necesita 'calor' y 'frio' o 'estaciones'")
        m = p.get("mascotas")
        if m is not None:
            if not str(m.get("url", "")).startswith("https://www.aspca.org/"):
                errores.append(f"{ref}: la toxicidad necesita su fuente de la ASPCA")
            if not isinstance(m.get("toxica"), bool):
                errores.append(f"{ref}: 'mascotas.toxica' debe ser true o false")
        for a in p.get("alertas", []):
            if len(a) != 2:
                errores.append(f"{ref}: cada alerta es [señal, qué hacer]")
    publicados = []
    if REGISTRO.exists():
        publicados = [l.strip() for l in REGISTRO.read_text(encoding="utf-8").splitlines()
                      if l.strip() and not l.startswith("#")]
    faltan = [s for s in publicados if s not in vistos]
    if faltan:
        errores.append("Fichas publicadas que ya no están en los datos (hay QR impresos que "
                       "apuntan a ellas; devuélvelas): " + ", ".join(faltan))
    if errores:
        sys.exit("No se generó nada:\n- " + "\n- ".join(errores))
    nuevos = [p["slug"] for p in datos["plantas"] if p["slug"] not in publicados]
    return datos, publicados, nuevos


def url_ficha(datos, slug):
    return f"{datos['sitio']}/cuidados/{slug}"


def enlace_contacto(datos, planta=None):
    c = datos["contacto"]
    num = re.sub(r"\D", "", c.get("whatsapp", ""))
    if num:
        msg = "Hola Jardín Malva, tengo una consulta sobre mi " + (planta or "planta") + ": "
        return f"https://wa.me/{num}?text={quote(msg)}", "Escríbenos por WhatsApp", "whatsapp"
    return f"https://ig.me/m/{c['instagram']}", "Escríbenos por Instagram", "instagram"


def enlace_resena(datos):
    c = datos["contacto"]
    return c.get("resena") or c["maps"]


# ---------------------------------------------------------------- iconos

ICONOS = {
    "luz": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "riego": '<path d="M12 3.2s-6 6.6-6 11a6 6 0 0 0 12 0c0-4.4-6-11-6-11Z"/>',
    "temp": '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z"/><path d="M12 15.5V9"/>',
    "pata": '<circle cx="6.2" cy="10.2" r="1.7"/><circle cx="9.6" cy="6.2" r="1.7"/><circle cx="14.4" cy="6.2" r="1.7"/><circle cx="17.8" cy="10.2" r="1.7"/><path d="M12 11.5c-2.6 0-5 3.2-5 5.6 0 1.6 1.2 2.4 2.6 2.4 1 0 1.6-.5 2.4-.5s1.4.5 2.4.5c1.4 0 2.6-.8 2.6-2.4 0-2.4-2.4-5.6-5-5.6Z"/>',
    "abono": '<path d="M12 21v-8"/><path d="M12 13c0-4 2.8-6.5 7-6.5 0 4-2.8 6.5-7 6.5Z"/><path d="M12 15.5c0-3.2-2.3-5.2-5.8-5.2 0 3.2 2.3 5.2 5.8 5.2Z"/>',
    "maceta": '<path d="M4 7h16v3H4Z"/><path d="M5.5 10h13l-1.6 10H7.1Z"/>',
    "hoja": '<path d="M5 19c0-8 5.5-14 15-14 0 9.5-6 15-14 15"/><path d="M5 19 13 11"/>',
    "alerta": '<path d="M10.3 4.2 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z"/><path d="M12 9.5v4M12 17h.01"/>',
    "dedo": '<path d="M9 11V5.5a1.5 1.5 0 0 1 3 0V11"/><path d="M12 10.5V9a1.5 1.5 0 0 1 3 0v2"/><path d="M15 10.5a1.5 1.5 0 0 1 3 0V15a6 6 0 0 1-6 6h-.6a6 6 0 0 1-4.6-2.2L4.6 16a1.6 1.6 0 0 1 2.4-2.1L9 15.5"/>',
    "check": '<path d="M5 12.5 10 17.5 19 7"/>',
    "flecha": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "atras": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    "estrella": '<path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8L3.5 9.7l5.9-.8Z"/>',
    "instagram": '<rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.2 6.8h.01"/>',
    "whatsapp": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M9.2 8.6c.2-.5.5-.6.8-.6h.5c.2 0 .4.1.5.4l.6 1.5c.1.2 0 .5-.1.6l-.5.6c.4.9 1.2 1.7 2.1 2.1l.6-.5c.2-.2.4-.2.6-.1l1.5.6c.2.1.4.3.4.5v.5c0 .3-.1.6-.6.8-.6.3-1.7.4-3.4-.6a8 8 0 0 1-2.6-2.6c-1-1.7-.9-2.8-.6-3.4Z"/>',
    "compartir": '<path d="M12 15V3.5M7.5 8 12 3.5 16.5 8"/><path d="M5 12v6.5A2 2 0 0 0 7 20.5h10a2 2 0 0 0 2-2V12"/>',
    "buscar": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    "mapa": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
}


def icono(nombre, clase=""):
    c = f' class="{clase}"' if clase else ""
    return (f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONOS[nombre]}</svg>')


# Ramita ilustrada (decorativa, con moderación)
RAMA = ('<svg class="rama" viewBox="0 0 200 260" fill="none" stroke="currentColor" stroke-width="1.4" '
        'stroke-linecap="round" aria-hidden="true">'
        '<path d="M150 255C140 190 120 130 70 20"/>'
        '<path d="M139 200c-26-4-46-20-52-46 26 2 46 20 52 46Z"/>'
        '<path d="M141 196c18-22 40-30 58-26-8 24-30 34-58 26Z"/>'
        '<path d="M118 140c-24-8-40-26-42-52 24 6 40 24 42 52Z"/>'
        '<path d="M121 137c14-24 34-36 54-36-4 26-26 40-54 36Z"/>'
        '<path d="M95 88c-20-12-30-32-28-56 22 10 32 30 28 56Z"/>'
        '<path d="M97 85c8-24 24-40 44-44 2 24-16 42-44 44Z"/>'
        '<path d="M139 200 113 170M141 196l26-12M118 140 92 108M121 137l24-20M95 88 80 56M97 85l20-26"/>'
        '</svg>')


# ---------------------------------------------------------------- estilos y script

CSS = r"""
@font-face{font-family:"Cormorant Garamond";src:url(/assets/fonts/cormorant.woff2) format("woff2");font-weight:400 600;font-style:normal;font-display:swap}
@font-face{font-family:"Cormorant Garamond";src:url(/assets/fonts/cormorant-italic.woff2) format("woff2");font-weight:400 600;font-style:italic;font-display:swap}
@font-face{font-family:"DM Sans";src:url(/assets/fonts/dmsans.woff2) format("woff2");font-weight:400 500;font-style:normal;font-display:swap}
@font-face{font-family:"Parisienne";src:url(/assets/fonts/parisienne.woff2) format("woff2");font-weight:400;font-style:normal;font-display:swap}
:root{
  --bosque:#263D32;--bosque-2:#2F4A3C;--oliva:#707B60;--oliva-osc:#5C6752;
  --salvia:#A8B5A0;--crema:#F5F0E6;--blanco:#FCFAF6;--carbon:#292D28;
  --malva:#B49AAF;--malva-osc:#7E6279;--malva-claro:#C9B6C4;
  --linea:rgba(41,45,40,.14);--r:12px;--ease:cubic-bezier(.22,.7,.2,1);
  --f-display:"Cormorant Garamond","Cormorant",Georgia,"Times New Roman",serif;
  --f-body:"DM Sans","Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
  --f-script:"Parisienne","Snell Roundhand","Apple Chancery",cursive;
  color-scheme:light;
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--blanco);color:var(--carbon);font:400 1.0625rem/1.65 var(--f-body);-webkit-font-smoothing:antialiased;overflow-x:clip}
img{max-width:100%;display:block}
a{color:inherit}
:focus-visible{outline:2px solid var(--malva-osc);outline-offset:3px;border-radius:6px}
[hidden]{display:none!important}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.wrap{width:100%;max-width:880px;margin-inline:auto;padding-left:max(20px,env(safe-area-inset-left,0px));padding-right:max(20px,env(safe-area-inset-right,0px))}
.eyebrow{margin:0;font:500 .74rem/1.4 var(--f-body);letter-spacing:.2em;text-transform:uppercase;color:var(--malva-osc)}
h1,h2,h3{margin:0;font-family:var(--f-display);font-weight:500;color:var(--bosque);text-wrap:balance}
h1{font-size:clamp(2.7rem,9vw,4.2rem);line-height:1.02;letter-spacing:.005em}
h2{font-size:clamp(1.75rem,5vw,2.2rem);line-height:1.12}
h3{font-size:1.2rem;line-height:1.3}
p{margin:0}
.muted{color:var(--oliva-osc)}
.script{font-family:var(--f-script);font-size:clamp(1.45rem,4.6vw,1.8rem);line-height:1.2;color:var(--oliva-osc)}

/* Botones */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.6em;min-height:50px;padding:0 1.4em;border-radius:999px;border:1px solid transparent;font:500 1rem/1.1 var(--f-body);text-decoration:none;text-align:center;cursor:pointer;transition:background-color .25s var(--ease),color .25s var(--ease),border-color .25s var(--ease)}
.btn svg{width:1.2em;height:1.2em;flex:none}
.btn-pri{background:var(--bosque);color:var(--blanco)}
.btn-pri:hover{background:var(--bosque-2)}
.btn-sec{border-color:var(--bosque);color:var(--bosque);background:transparent}
.btn-sec:hover{background:rgba(38,61,50,.07)}

/* Cabecera y pie */
.top{position:sticky;top:0;z-index:20;background:rgba(252,250,246,.94);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--linea)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:14px;min-height:62px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;font:500 1.06rem/1 var(--f-display);letter-spacing:.14em;text-transform:uppercase;color:var(--bosque);white-space:nowrap}
.brand img{width:38px;height:38px}
.top-link{display:inline-flex;align-items:center;gap:6px;font-size:.92rem;color:var(--oliva-osc);text-decoration:none;white-space:nowrap}
.top-link svg{width:18px;height:18px}
.top-link:hover{color:var(--bosque)}
@media (max-width:370px){.top .brand span{display:none}}
.foot{background:var(--bosque);color:var(--salvia);padding:36px 0 44px;font-size:.92rem}
.foot .wrap{display:grid;gap:12px;justify-items:start}
.foot .brand{color:var(--crema)}
.foot .script{color:var(--malva-claro);font-size:1.4rem}
.foot a{color:var(--crema)}
.foot nav{display:flex;flex-wrap:wrap;gap:6px 18px}

/* Portada de la ficha */
.hero{position:relative;overflow:hidden;background:var(--crema);padding:clamp(30px,7vw,60px) 0 clamp(34px,7vw,60px)}
.hero .wrap{position:relative;display:grid;gap:12px}
.rama{position:absolute;right:-34px;top:-34px;width:clamp(120px,28vw,220px);height:auto;color:var(--malva);opacity:.42;pointer-events:none}
@media (min-width:880px){.rama{right:calc((100vw - 880px)/2 - 30px);top:-20px;opacity:.5}}
.hero h1,.hero .bot,.hero .alias{max-width:calc(100% - 70px)}
.bot{font:italic 500 1.28rem/1.3 var(--f-display);color:var(--oliva-osc)}
.alias{font-size:.95rem;color:var(--oliva-osc)}
.lead{max-width:44ch;font-size:1.08rem;margin-top:6px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.chip{display:inline-flex;align-items:center;gap:9px;min-height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--linea);background:var(--blanco);font-size:.9rem;color:var(--bosque)}
.dots{display:inline-flex;gap:4px}
.dots i{width:7px;height:7px;border-radius:50%;background:var(--salvia)}
.dots i.on{background:var(--bosque)}
.hero .script{margin-top:10px}

/* Lo esencial */
.esencial{padding:26px 0 8px}
.tiles{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.tile{display:grid;gap:6px;align-content:start;padding:16px 14px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea)}
.tile .ico{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:var(--crema);color:var(--bosque);margin-bottom:4px}
.tile .ico svg{width:21px;height:21px}
.tile .lbl{font:500 .7rem/1.3 var(--f-body);letter-spacing:.17em;text-transform:uppercase;color:var(--malva-osc)}
.tile .val{font:500 1.2rem/1.22 var(--f-display);color:var(--bosque);overflow-wrap:anywhere}
.tile.aviso{background:rgba(180,154,175,.12);border-color:rgba(126,98,121,.3)}
.tile.aviso .ico{background:rgba(180,154,175,.28);color:var(--malva-osc)}
@media (min-width:760px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}}

/* Secciones */
.sec{padding:clamp(28px,5vw,40px) 0}
.sec+.sec{border-top:1px solid var(--linea)}
.sec .wrap{display:grid;gap:14px}
.sec-t{display:flex;align-items:center;gap:12px}
.sec-t svg{width:26px;height:26px;color:var(--oliva);flex:none}
.sec p{max-width:62ch}
.estaciones{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:2px}
.est{padding:14px;border-radius:var(--r);background:var(--crema)}
.est b{display:block;font:500 .7rem/1.35 var(--f-body);letter-spacing:.15em;text-transform:uppercase;color:var(--malva-osc);margin-bottom:4px}
.est span{font:500 1.14rem/1.25 var(--f-display);color:var(--bosque)}
@media (max-width:420px){.estaciones{grid-template-columns:1fr}}
.nota{font-size:.9rem;color:var(--oliva-osc)}
.dedo{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:start;padding:16px;border-radius:var(--r);border:1px dashed rgba(112,123,96,.55)}
.dedo svg{width:30px;height:30px;color:var(--malva-osc)}
.dedo p{font-size:.97rem}
.datos{margin:0;display:grid;border-top:1px solid var(--linea)}
.datos div{display:grid;grid-template-columns:minmax(110px,26%) 1fr;gap:14px;padding:14px 0;border-bottom:1px solid var(--linea)}
.datos dt{display:flex;gap:8px;align-items:flex-start;font:500 .72rem/1.9 var(--f-body);letter-spacing:.16em;text-transform:uppercase;color:var(--malva-osc)}
.datos dd{margin:0}
@media (max-width:520px){.datos div{grid-template-columns:1fr;gap:2px}}
.puntos{margin:0;padding:0;list-style:none;display:grid;gap:10px}
.puntos li{display:grid;grid-template-columns:auto 1fr;gap:10px}
.puntos li svg{width:20px;height:20px;margin-top:3px;color:var(--oliva)}
.alertas{margin:0;padding:0;list-style:none;display:grid;gap:10px}
.alertas li{display:grid;gap:4px;padding:14px 16px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea);border-left:3px solid var(--malva)}
.alertas b{font-weight:500;color:var(--bosque)}
.alertas span{color:var(--carbon);font-size:.98rem}
.pet{display:grid;grid-template-columns:1fr auto;gap:6px 14px;padding:18px 12px 0 18px;border-radius:var(--r);background:var(--crema);overflow:hidden}
.pet img{grid-column:2;grid-row:1/span 2;align-self:end;width:72px;height:auto;margin-bottom:-24px}
.pet div{display:grid;gap:8px;padding-bottom:18px;align-self:center}
@media (min-width:640px){.pet img{width:96px}}
.pet.toxica{background:rgba(180,154,175,.15);border:1px solid rgba(126,98,121,.3)}
.pet .estado{display:inline-flex;align-items:center;gap:8px;font-weight:500;color:var(--bosque)}
.pet.toxica .estado{color:var(--malva-osc)}
.pet .estado svg{width:20px;height:20px}
.pet .fuente{font-size:.86rem;color:var(--oliva-osc)}
.pasos{margin:0;padding:0;list-style:none;counter-reset:p;display:grid;gap:12px}
.pasos li{counter-increment:p;display:grid;grid-template-columns:auto 1fr;gap:12px}
.pasos li::before{content:counter(p);width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--bosque);color:var(--crema);font:500 .85rem/1 var(--f-body);margin-top:1px}

/* Cierre */
.cierre{background:var(--bosque);color:var(--crema);padding:clamp(40px,8vw,64px) 0}
.cierre .wrap{display:grid;gap:14px;justify-items:center;text-align:center}
.cierre h2{color:var(--crema)}
.cierre p{max-width:42ch;color:var(--salvia)}
.cierre .acciones{display:grid;gap:10px;width:min(100%,380px);margin-top:8px}
.cierre .btn-pri{background:var(--crema);color:var(--bosque)}
.cierre .btn-pri:hover{background:#fff}
.cierre .btn-sec{border-color:rgba(245,240,230,.55);color:var(--crema)}
.cierre .btn-sec:hover{background:rgba(245,240,230,.08)}
.aviso-copia{font-size:.88rem;color:var(--malva-claro);min-height:1.3em}

/* Índice */
.buscador{position:relative;margin-top:14px;max-width:520px}
.buscador svg{position:absolute;left:16px;top:50%;width:20px;height:20px;transform:translateY(-50%);color:var(--oliva)}
.buscador input{width:100%;min-height:52px;padding:0 16px 0 46px;border-radius:999px;border:1px solid rgba(41,45,40,.28);background:var(--blanco);font:400 1rem var(--f-body);color:var(--carbon)}
.buscador input:focus{outline:2px solid var(--malva-osc);outline-offset:2px}
.grupo{display:grid;gap:12px}
.grupo+.grupo{margin-top:30px}
.lista{list-style:none;margin:0;padding:0;display:grid;gap:10px}
@media (min-width:640px){.lista{grid-template-columns:repeat(2,minmax(0,1fr))}}
.lista a{display:grid;grid-template-columns:1fr auto;gap:4px 12px;align-items:center;height:100%;padding:16px 18px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea);text-decoration:none;transition:border-color .2s}
.lista a:hover{border-color:var(--bosque)}
.lista .n{font:500 1.3rem/1.2 var(--f-display);color:var(--bosque)}
.lista .b{grid-column:1;font:italic 500 1.02rem/1.3 var(--f-display);color:var(--oliva-osc)}
.lista .r{grid-column:1;font-size:.86rem;color:var(--oliva-osc)}
.lista svg{grid-row:1/span 3;grid-column:2;width:22px;height:22px;color:var(--oliva)}
.vacio{padding:18px;border-radius:var(--r);background:var(--crema)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important}}
@media print{.top,.cierre,.foot,.rama,[data-compartir]{display:none!important}body{font-size:11pt}.sec{padding:10px 0}}
"""

JS = r"""
(function(){
  var d = document;
  // Compartir la ficha (o copiar el enlace si el teléfono no puede compartir)
  var aviso = d.querySelector('[data-aviso]');
  Array.prototype.forEach.call(d.querySelectorAll('[data-compartir]'), function(b){
    var datos = {title: d.title, url: location.origin + location.pathname};
    if (!navigator.share && !(navigator.clipboard && window.isSecureContext)) return;
    b.hidden = false;
    b.addEventListener('click', function(){
      if (navigator.share) { navigator.share(datos).catch(function(){}); return; }
      navigator.clipboard.writeText(datos.url).then(function(){
        if (aviso) aviso.textContent = 'Enlace copiado. Pégalo donde quieras.';
      }, function(){});
    });
  });
  // Buscador del índice
  var q = d.querySelector('[data-buscar]');
  if (q) {
    var items = Array.prototype.slice.call(d.querySelectorAll('[data-q]'));
    var grupos = Array.prototype.slice.call(d.querySelectorAll('[data-grupo]'));
    var vacio = d.querySelector('[data-vacio]');
    var norm = function(s){ return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); };
    var filtrar = function(){
      var t = norm(q.value.trim()), n = 0;
      items.forEach(function(li){ var ok = !t || li.getAttribute('data-q').indexOf(t) > -1; li.hidden = !ok; if (ok) n++; });
      grupos.forEach(function(g){ g.hidden = !g.querySelector('[data-q]:not([hidden])'); });
      if (vacio) vacio.hidden = n > 0;
    };
    q.addEventListener('input', filtrar);
    filtrar();
  }
})();
"""


def huella(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------- piezas comunes

def cabeza(datos, titulo, descripcion, ruta, v_css):
    robots = "" if datos.get("indexar") else '\n<meta name="robots" content="noindex">'
    url = datos["sitio"] + ruta
    return f"""<!doctype html>
<html lang="es-CL">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">{robots}
<meta name="theme-color" content="#263D32">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="article">
<meta property="og:locale" content="es_CL">
<meta property="og:site_name" content="Jardín Malva">
<meta property="og:url" content="{e(url)}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta property="og:image" content="{e(datos['sitio'])}/assets/og.jpg">
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/cormorant.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/dmsans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/cuidados/cuidados.css?v={v_css}">
</head>
<body>
"""


def cabecera(enlace_indice=True):
    derecha = (f'<a class="top-link" href="/cuidados/">{icono("hoja")}Todas las fichas</a>'
               if enlace_indice else "")
    return f"""<header class="top">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Jardín Malva, inicio"><img src="/assets/logo-128.webp" width="38" height="38" alt=""><span>Jardín Malva</span></a>
    {derecha}
  </div>
</header>
"""


def pie(datos, v_js):
    c = datos["contacto"]
    return f"""<footer class="foot">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Jardín Malva, inicio"><img src="/assets/logo-128.webp" width="38" height="38" alt="" loading="lazy"><span>Jardín Malva</span></a>
    <p class="script">cultivar, cuidar y vivir más lento</p>
    <p>Vivero boutique · {e(c['direccion'])}</p>
    <nav aria-label="Enlaces">
      <a href="/cuidados/">Todas las fichas de cuidado</a>
      <a href="{e(c['maps'])}" target="_blank" rel="noopener">Cómo llegar</a>
      <a href="https://www.instagram.com/{e(c['instagram'])}/" target="_blank" rel="noopener">@{e(c['instagram'])}</a>
    </nav>
  </div>
</footer>
<script src="/cuidados/cuidados.js?v={v_js}" defer></script>
</body>
</html>
"""


def cierre(datos, nombre_planta=None, titulo=None, texto=None, compartir=True):
    href, etiqueta, ico = enlace_contacto(datos, nombre_planta)
    resena = enlace_resena(datos)
    ig = datos["contacto"]["instagram"]
    titulo = titulo or f"¿Dudas con tu {nombre_planta or 'planta'}?"
    texto = texto or "Escríbenos y te ayudamos. Y si te gustó tu visita, una reseña nos ayuda muchísimo."
    boton_compartir = (f'\n      <button class="btn btn-sec" type="button" data-compartir hidden>{icono("compartir")}Compartir esta ficha</button>'
                       if compartir else "")
    return f"""<section class="cierre" aria-labelledby="t-cierre">
  <div class="wrap">
    <h2 id="t-cierre">{e(titulo)}</h2>
    <p>{e(texto)}</p>
    <div class="acciones">
      <a class="btn btn-pri" href="{e(href)}" target="_blank" rel="noopener">{icono(ico)}{e(etiqueta)}</a>
      <a class="btn btn-sec" href="{e(resena)}" target="_blank" rel="noopener">{icono("estrella")}Déjanos tu reseña en Google</a>
      <a class="btn btn-sec" href="https://www.instagram.com/{e(ig)}/" target="_blank" rel="noopener">{icono("instagram")}Muéstranos dónde quedó</a>{boton_compartir}
    </div>
    <p class="aviso-copia" data-aviso aria-live="polite"></p>
  </div>
</section>
"""


def mascotas_corto(m):
    if m is None:
        return None
    if m.get("corto"):
        return m["corto"]
    return "Tóxica: fuera de su alcance" if m["toxica"] else "No tóxica"


# ---------------------------------------------------------------- ficha

def pagina_planta(datos, p, v_css, v_js):
    nombre = p["nombre"]
    titulo = f"Cómo cuidar tu {nombre} · Jardín Malva"
    desc = f"Cuidados de {nombre} ({p['botanico']}): luz, riego, abono y señales de alerta. {p['resumen']}"
    m = p.get("mascotas")
    tipo_txt = TIPO_TEXTO[p["tipo"]]
    alias = ""
    if p.get("alias"):
        alias = f'\n    <p class="alias">Otros nombres: {e(", ".join(p["alias"]))}</p>'
    dots = "".join(f'<i class="on"></i>' if i < p["dificultad"] else "<i></i>" for i in range(3))

    tiles = [
        ("luz", "Luz", p["luz"]["corto"], ""),
        ("riego", "Riego", p["riego"]["corto"], ""),
        ("temp", "Temperatura", p["temperatura"]["corto"], ""),
    ]
    if m is not None:
        tiles.append(("pata", "Mascotas", mascotas_corto(m), " aviso" if m["toxica"] else ""))
    tiles_html = "\n".join(
        f'      <li class="tile{cl}"><span class="ico">{icono(ic)}</span><span class="lbl">{e(lb)}</span><span class="val">{e(v)}</span></li>'
        for ic, lb, v, cl in tiles)

    r = p["riego"]
    est = r.get("estaciones") or [["Primavera y verano", r["calor"]], ["Otoño e invierno", r["frio"]]]
    est_html = "\n".join(f'      <div class="est"><b>{e(a)}</b><span>{e(b)}</span></div>' for a, b in est)

    filas = [("abono", "Abono", p["abono"]), ("maceta", "Trasplante", p["trasplante"])]
    if p.get("variedades"):
        filas.append(("hoja", "Variedades", p["variedades"]))
    filas_html = "\n".join(f'      <div><dt>{e(lb)}</dt><dd>{e(t)}</dd></div>' for ic, lb, t in filas)

    consejos_html = ""
    if p.get("consejos"):
        items = "\n".join(f'      <li>{icono("check")}<span>{e(c)}</span></li>' for c in p["consejos"])
        consejos_html = f"""<section class="sec" aria-labelledby="t-consejos">
  <div class="wrap">
    <div class="sec-t">{icono("hoja")}<h2 id="t-consejos">Consejos de la casa</h2></div>
    <ul class="puntos">
{items}
    </ul>
  </div>
</section>
"""

    alertas = "\n".join(f'      <li><b>{e(a)}</b><span>{e(b)}</span></li>' for a, b in p["alertas"])

    mascota_html = ""
    if m is not None:
        cl = " toxica" if m["toxica"] else ""
        estado = "Ojo con tus mascotas" if m["toxica"] else "Buena noticia para tus mascotas"
        ic = "alerta" if m["toxica"] else "check"
        extra = (" Mejor ubicarla fuera de su alcance y, si notas síntomas después de una mordida, llama a tu veterinario."
                 if m["toxica"] else "")
        mascota_html = f"""<section class="sec" aria-labelledby="t-pet">
  <div class="wrap">
    <div class="sec-t">{icono("pata")}<h2 id="t-pet">Si tienes mascotas</h2></div>
    <div class="pet{cl}">
      <div>
        <p class="estado">{icono(ic)}{e(estado)}</p>
        <p>{e(m['texto'])}{e(extra)}</p>
        <p class="fuente">Fuente: <a href="{e(m['url'])}" target="_blank" rel="noopener">ASPCA, lista de plantas tóxicas y no tóxicas</a> (en inglés).</p>
      </div>
      <img src="/assets/petunia-240.webp" width="240" height="588" loading="lazy" decoding="async" alt="Petunia, la anfitriona ilustrada de Jardín Malva">
    </div>
  </div>
</section>
"""

    primeros = "\n".join(f"      <li><span>{e(t)}</span></li>" for t in datos["primeros_dias"][p["tipo"]])

    cuerpo = f"""{cabecera()}
<main>
<section class="hero" aria-labelledby="t-planta">
  {RAMA}
  <div class="wrap">
    <p class="eyebrow">Ficha de cuidados · {e(tipo_txt)}</p>
    <h1 id="t-planta">{e(nombre)}</h1>
    <p class="bot">{e(p['botanico'])}</p>{alias}
    <p class="lead">{e(p['resumen'])}</p>
    <div class="chips"><span class="chip"><span class="dots" aria-hidden="true">{dots}</span>{e(DIFICULTAD[p['dificultad']])}</span></div>
  </div>
</section>

<section class="esencial" aria-labelledby="t-esencial">
  <div class="wrap">
    <p class="eyebrow" id="t-esencial">Lo esencial</p>
    <ul class="tiles">
{tiles_html}
    </ul>
  </div>
</section>

<section class="sec" aria-labelledby="t-riego">
  <div class="wrap">
    <div class="sec-t">{icono("riego")}<h2 id="t-riego">Riego</h2></div>
    <p>{e(r['texto'])}</p>
    <div class="estaciones">
{est_html}
    </div>
    <p class="nota">Frecuencias orientativas: dependen de la luz, la maceta y la temperatura de tu casa. Antes de regar, haz siempre la prueba del dedo.</p>
    <div class="dedo">{icono("dedo")}<p><strong>La prueba del dedo.</strong> Mete el dedo en la tierra unos 3 cm. Si sale seco, riega hasta que el agua salga por los agujeros de abajo y bota la que quede en el plato. Si sale húmedo, espera.</p></div>
  </div>
</section>

<section class="sec" aria-labelledby="t-luz">
  <div class="wrap">
    <div class="sec-t">{icono("luz")}<h2 id="t-luz">Luz y lugar</h2></div>
    <p>{e(p['luz']['texto'])}</p>
    <p>{e(p['temperatura']['texto'])}</p>
  </div>
</section>

<section class="sec" aria-labelledby="t-anio">
  <div class="wrap">
    <div class="sec-t">{icono("abono")}<h2 id="t-anio">Durante el año</h2></div>
    <dl class="datos">
{filas_html}
    </dl>
  </div>
</section>

{consejos_html}<section class="sec" aria-labelledby="t-alertas">
  <div class="wrap">
    <div class="sec-t">{icono("alerta")}<h2 id="t-alertas">Si ves esto…</h2></div>
    <ul class="alertas">
{alertas}
    </ul>
  </div>
</section>

{mascota_html}<section class="sec" aria-labelledby="t-primeros">
  <div class="wrap">
    <div class="sec-t">{icono("maceta")}<h2 id="t-primeros">Tus primeros días juntos</h2></div>
    <ol class="pasos">
{primeros}
    </ol>
  </div>
</section>
</main>

{cierre(datos, nombre)}"""
    return cabeza(datos, titulo, desc, f"/cuidados/{p['slug']}", v_css) + cuerpo + pie(datos, v_js)


# ---------------------------------------------------------------- índice

def pagina_indice(datos, v_css, v_js):
    titulo = "Cuidados de tus plantas · Jardín Malva"
    desc = "Fichas de cuidado de las plantas de Jardín Malva: luz, riego, abono y si son seguras para tus mascotas."
    grupos = []
    for tipo, nombre_grupo in datos["grupos"].items():
        plantas = sorted((p for p in datos["plantas"] if p["tipo"] == tipo), key=lambda p: normalizar(p["nombre"]))
        if not plantas:
            continue
        items = []
        for p in plantas:
            q = normalizar(" ".join([p["nombre"], p["botanico"], *p.get("alias", [])]))
            items.append(
                f'      <li data-q="{e(q)}"><a href="/cuidados/{e(p["slug"])}">'
                f'<span class="n">{e(p["nombre"])}</span><span class="b">{e(p["botanico"])}</span>'
                f'<span class="r">{e(p["luz"]["corto"])} · {e(DIFICULTAD[p["dificultad"]])}</span>{icono("flecha")}</a></li>')
        grupos.append(f"""  <div class="grupo" data-grupo>
    <h2>{e(nombre_grupo)}</h2>
    <ul class="lista">
{chr(10).join(items)}
    </ul>
  </div>""")
    cuerpo = f"""{cabecera(enlace_indice=False)}
<main>
<section class="hero" aria-labelledby="t-indice">
  {RAMA}
  <div class="wrap">
    <p class="eyebrow">Fichas de cuidado</p>
    <h1 id="t-indice">Cuidados de tus plantas</h1>
    <p class="lead">Escanea el código de tu tarjeta o busca tu planta aquí. Luz, riego y todo lo que necesita para crecer contigo.</p>
    <label class="buscador"><span class="sr">Buscar planta</span>{icono("buscar")}<input type="search" placeholder="Busca tu planta: monstera, lavanda…" autocomplete="off" data-buscar></label>
  </div>
</section>
<section class="sec">
  <div class="wrap">
{chr(10).join(grupos)}
    <p class="vacio" data-vacio hidden>No encontramos esa planta. Escríbenos y te ayudamos con sus cuidados.</p>
  </div>
</section>
</main>

{cierre(datos, titulo="¿No encuentras tu planta?", texto="Escríbenos con su nombre o una foto y te contamos cómo cuidarla.", compartir=False)}"""
    return cabeza(datos, titulo, desc, "/cuidados/", v_css) + cuerpo + pie(datos, v_js)


# ---------------------------------------------------------------- principal

def main():
    datos, publicados, nuevos = cargar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    css = CSS.strip() + "\n"
    js = JS.strip() + "\n"
    (SALIDA / "cuidados.css").write_text(css, encoding="utf-8")
    (SALIDA / "cuidados.js").write_text(js, encoding="utf-8")
    v_css, v_js = huella(css), huella(js)
    esperados = {"index.html", "cuidados.css", "cuidados.js"}
    for p in datos["plantas"]:
        (SALIDA / f"{p['slug']}.html").write_text(pagina_planta(datos, p, v_css, v_js), encoding="utf-8")
        esperados.add(f"{p['slug']}.html")
    (SALIDA / "index.html").write_text(pagina_indice(datos, v_css, v_js), encoding="utf-8")
    sobrantes = [f.name for f in SALIDA.iterdir() if f.name not in esperados]
    if nuevos:
        cab = "" if REGISTRO.exists() else ("# Fichas publicadas en jardinmalva.cl/cuidados/<slug>.\n"
                                             "# Hay QR impresos que apuntan a ellas: no las borres ni las renombres.\n")
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(cab + "".join(s + "\n" for s in nuevos))
    print(f"OK: {len(datos['plantas'])} fichas + índice en {SALIDA.relative_to(RAIZ)}/")
    if nuevos:
        print("Nuevas fichas registradas:", ", ".join(nuevos))
    if sobrantes:
        print("Aviso: archivos en public/cuidados/ que no genera este script:", ", ".join(sobrantes))
    print("Indexación en buscadores:", "sí" if datos.get("indexar") else "no (noindex)")


if __name__ == "__main__":
    main()
