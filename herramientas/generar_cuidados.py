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
import copy
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
LOTES = RAIZ / "datos" / "lotes"
SITIO = RAIZ / "public" / "sitio.html"
MASCOTAS = RAIZ / "public" / "mascotas.html"
SALIDA = RAIZ / "public" / "cuidados"

DIFICULTAD = {1: "Fácil", 2: "Cuidado medio", 3: "Pide atención"}

# Intensidad del color de los cuadros de "Lo esencial": cuánta luz, agua o calor
# necesita la planta (1 poca · 2 media · 3 mucha). Se deduce del texto corto de la
# ficha; si una ficha nueva trae un texto que no está aquí, el generador se detiene
# y pide añadirlo (o poner "nivel": 1, 2 o 3 dentro de luz, riego o temperatura).
NIVEL_TXT = {1: "baja", 2: "media", 3: "alta"}
NIVELES = {
    "luz": {
        1: ["Luz media, sin sol directo", "Luz media indirecta", "Luz media, tolera poca",
            "Poca o mucha luz", "Semisombra", "Sombra luminosa", "Semisombra o sombra"],
        2: ["Luz brillante indirecta", "Luz media a brillante", "Mucha luz indirecta",
            "Mucha luz, sin sol fuerte", "Mucha luz y lugar fresco", "Sol o semisombra",
            "Sol de mañana, sombra de tarde"],
        3: ["Luz brillante", "Mucha luz", "Mucha luz, junto a la ventana", "Pleno sol",
            "Sol directo, 6 h o más", "Sol directo, 5–6 h"],
    },
    "riego": {
        1: ["Cuando 3–5 cm estén secos", "Cuando 5 cm estén secos", "Con la tierra casi seca",
            "Cuando la tierra esté casi seca", "Con la mitad de la tierra seca",
            "Solo con la tierra seca", "Poco: deja secar entre riegos",
            "Inmersión con raíces plateadas", "Resiste la sequía"],
        2: ["Cuando 3 cm estén secos", "Cuando 2–3 cm estén secos", "Cuando 2 cm estén secos",
            "Deja secar la superficie", "Regular, sin encharcar", "Por el plato, sin mojar el centro",
            "Profundo, al pie y de mañana", "Remojo cuando la base esté seca",
            "Moderado, sin encharcar", "Profundo y espaciado"],
        3: ["Siempre levemente húmeda", "Siempre levemente húmedo", "Tierra levemente húmeda",
            "Tierra siempre levemente húmeda", "Tierra apenas húmeda", "Siempre húmedo",
            "Húmedo, sin mojar el centro", "Frecuente en verano", "Tierra siempre húmeda",
            "Abundante en verano"],
    },
    # temperatura: "Entre X y Y °C" se resuelve por la mínima (≤13 → 1, 14–16 → 2, ≥17 → 3)
    "temperatura": {
        1: ["Aguanta el invierno", "Resiste frío suave", "Fresca", "Fresca, de 10 a 18 °C",
            "Resiste heladas", "Resiste heladas fuertes"],
        2: ["Primavera a otoño", "Heladas suaves", "Protégela de las heladas"],
        3: [],
    },
}
NIVEL_DE = {campo: {txt: n for n, lista in tabla.items() for txt in lista}
            for campo, tabla in NIVELES.items()}


def nivel(p, campo):
    """1, 2 o 3 según cuánta luz, agua o calor necesita la planta; None si no se sabe."""
    d = p.get(campo, {})
    if d.get("nivel") in (1, 2, 3):
        return d["nivel"]
    corto = d.get("corto", "")
    if campo == "temperatura":
        m = re.fullmatch(r"Entre (\d+) y (\d+) °C", corto)
        if m:
            minima = int(m.group(1))
            return 1 if minima <= 13 else (2 if minima <= 16 else 3)
    return NIVEL_DE[campo].get(corto)
TIPO_TEXTO = {"interior": "Planta de interior", "exterior": "Flor y exterior"}
# Cómo se nombra cada categoría en la cabecera de la ficha (el índice usa datos["categorias"])
CATEGORIA_TEXTO = {"interior": "Planta de interior", "flores": "Flor y planta de temporada",
                   "aromaticas": "Aromática y huerto", "arbustos": "Arbusto o trepadora",
                   "frutales": "Frutal", "arboles": "Árbol", "coniferas": "Conífera",
                   "nativas": "Nativa de Chile", "suculentas": "Suculenta"}


def categoria(p):
    return p.get("categoria") or ("interior" if p["tipo"] == "interior" else "flores")


def e(texto):
    return html.escape(str(texto), quote=True)


def normalizar(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- datos

# Campos que identifican a una planta y nunca se heredan de su base
IDENTIDAD = {"slug", "nombre", "alias", "botanico", "resumen", "codigo", "variedades", "base", "lote"}
FUSIONABLES = {"luz", "riego", "temperatura", "mascotas"}


def resolver(p, perfiles, por_slug, pila=()):
    """Devuelve la planta con los cuidados heredados de su 'base' (perfil u otra ficha)."""
    base_id = p.get("base")
    if not base_id:
        return dict(p)
    if base_id in pila:
        raise ValueError(f"{p.get('slug')}: herencia circular ({' → '.join(pila + (base_id,))})")
    if base_id in perfiles:
        base = dict(perfiles[base_id])
    elif base_id in por_slug:
        base = resolver(por_slug[base_id], perfiles, por_slug, pila + (base_id,))
    else:
        raise ValueError(f"{p.get('slug')}: la base '{base_id}' no existe")
    r = {k: copy.deepcopy(v) for k, v in base.items() if k not in IDENTIDAD}
    for k, v in p.items():
        if k in FUSIONABLES and isinstance(v, dict) and isinstance(r.get(k), dict):
            if k == "riego" and "estaciones" in v:
                r[k] = {kk: vv for kk, vv in r[k].items() if kk not in ("calor", "frio")}
            if k == "mascotas":
                r[k] = dict(v)  # la toxicidad se reemplaza entera, nunca se mezcla
            else:
                r[k] = {**r[k], **v}
        elif k == "consejos_extra":
            r["consejos"] = list(v) + r.get("consejos", [])
        elif k == "alertas_extra":
            r["alertas"] = list(v) + r.get("alertas", [])
        else:
            r[k] = copy.deepcopy(v)
    r.pop("consejos_extra", None)
    r.pop("alertas_extra", None)
    return r


def cargar():
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    errores = []
    perfiles = dict(datos.get("perfiles", {}))
    crudas = [dict(p, lote=None) for p in datos["plantas"]]
    datos["equivalencias"] = {}
    datos["lotes"] = {}
    for f in sorted(LOTES.glob("*.json")):
        lote = json.loads(f.read_text(encoding="utf-8"))
        nombre_lote = lote.get("lote", f.stem)
        datos["lotes"][f.stem] = {"nombre": nombre_lote, "slugs": []}
        for k, v in lote.get("perfiles", {}).items():
            if k in perfiles:
                errores.append(f"{f.name}: perfil '{k}' repetido")
            perfiles[k] = v
        for p in lote.get("plantas", []):
            crudas.append(dict(p, lote=f.stem))
            datos["lotes"][f.stem]["slugs"].append(p.get("slug"))
        for cod, slug in lote.get("equivalencias", {}).items():
            datos["equivalencias"][cod] = slug
            datos["lotes"][f.stem]["slugs"].append(slug)
    por_slug = {p.get("slug"): p for p in crudas}
    plantas = []
    for p in crudas:
        try:
            plantas.append(resolver(p, perfiles, por_slug))
        except ValueError as ex:
            errores.append(str(ex))
    datos["plantas"] = plantas
    # códigos del Tomo I: los de las equivalencias se asignan a la ficha existente
    for cod, slug in datos["equivalencias"].items():
        if slug in por_slug:
            for p in plantas:
                if p["slug"] == slug:
                    p.setdefault("codigo", cod)
        else:
            errores.append(f"equivalencia {cod}: la ficha '{slug}' no existe")
    vistos, codigos = set(), set()
    for i, p in enumerate(plantas):
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
        if p.get("codigo"):
            if p["codigo"] in codigos:
                errores.append(f"{ref}: código {p['codigo']} repetido")
            codigos.add(p["codigo"])
        if p.get("tipo") not in datos["grupos"]:
            errores.append(f"{ref}: tipo desconocido '{p.get('tipo')}'")
        elif categoria(p) not in datos["categorias"]:
            errores.append(f"{ref}: categoría desconocida '{p.get('categoria')}'")
        if p.get("dificultad") not in DIFICULTAD:
            errores.append(f"{ref}: dificultad debe ser 1, 2 o 3")
        riego = p.get("riego", {})
        if "estaciones" not in riego and not ("calor" in riego and "frio" in riego):
            errores.append(f"{ref}: el riego necesita 'calor' y 'frio' o 'estaciones'")
        for campo in ("luz", "riego", "temperatura"):
            if not all(p.get(campo, {}).get(k) for k in ("corto", "texto")):
                errores.append(f"{ref}: '{campo}' necesita 'corto' y 'texto'")
            elif nivel(p, campo) is None:
                errores.append(f"{ref}: no sé qué intensidad de color darle a {campo} "
                               f"«{p[campo]['corto']}»: añádelo a NIVELES en este script o pon "
                               f"\"nivel\": 1, 2 o 3 dentro de '{campo}'")
        m = p.get("mascotas")
        if m is not None:
            if m.get("toxica") not in (True, False, None):
                errores.append(f"{ref}: 'mascotas.toxica' debe ser true, false o null (sin dato)")
            if m.get("toxica") is not None and not str(m.get("url", "")).startswith("https://www.aspca.org/"):
                errores.append(f"{ref}: la toxicidad necesita su fuente de la ASPCA")
            if not m.get("texto"):
                errores.append(f"{ref}: 'mascotas' necesita 'texto'")
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
    nuevos = [p["slug"] for p in plantas if p["slug"] not in publicados]
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
    # globo de conversación con una hoja dentro: "pregúntanos por esta planta"
    "consulta": '<path d="M6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H12l-4.6 3.6V16h-.9A2.5 2.5 0 0 1 4 13.5v-7A2.5 2.5 0 0 1 6.5 4Z"/><path d="M8.8 12.8c0-2.9 2.1-4.8 6.2-5 0 3.6-2.2 5.5-5.1 5.4"/><path d="M8.8 12.8 12 9.9"/>',
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
  --malva:#B49AAF;--malva-osc:#7E6279;--malva-claro:#C9B6C4;--malva-txt:#6B5166;
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
/* ¿Aún no la tienes? Consulta de stock por Instagram */
.stock-box{margin-top:16px}
.stock{display:inline-flex;align-items:center;gap:12px;max-width:100%;min-height:52px;padding:7px 16px 7px 7px;border-radius:999px;background:var(--blanco);border:1px solid rgba(126,98,121,.35);color:var(--bosque);text-decoration:none;transition:border-color .25s var(--ease),background-color .25s var(--ease)}
.stock:hover{border-color:var(--malva-txt);background:#FBF8FA}
.stock-ico{width:38px;height:38px;flex:none;border-radius:50%;display:grid;place-items:center;background:#EEE4EC;color:var(--malva-txt)}
.stock-ico svg{width:23px;height:23px}
.stock-txt{display:grid;gap:1px;line-height:1.25;min-width:0}
.stock-txt b{font:500 .98rem/1.25 var(--f-body)}
.stock-txt span{font-size:.86rem;color:var(--oliva-osc)}
.stock-fl{width:17px;height:17px;flex:none;color:var(--malva-txt);transition:transform .25s var(--ease)}
.stock:hover .stock-fl{transform:translateX(3px)}
.stock-aviso{margin-top:8px;font-size:.86rem;color:var(--oliva-osc)}
.stock-aviso:empty{display:none}
.chip{display:inline-flex;align-items:center;gap:9px;min-height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--linea);background:var(--blanco);font-size:.9rem;color:var(--bosque)}
.dots{display:inline-flex;gap:4px}
.dots i{width:7px;height:7px;border-radius:50%;background:var(--salvia)}
.dots i.on{background:var(--bosque)}
.hero .script{margin-top:10px}

/* Lo esencial */
.esencial{padding:26px 0 8px}
.tiles{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.tile{position:relative;display:grid;gap:6px;align-content:start;padding:16px 14px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea)}
.tile .ico{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:rgba(252,250,246,.72);color:var(--bosque);margin-bottom:4px}
.tile .ico svg{width:21px;height:21px}
.tile .lbl{font:500 .7rem/1.3 var(--f-body);letter-spacing:.17em;text-transform:uppercase;color:var(--malva-txt)}
.tile .val{font:500 1.2rem/1.22 var(--f-display);color:var(--bosque);overflow-wrap:anywhere}
/* Intensidad según cuánta luz, agua o calor necesita (n1 poca · n2 media · n3 mucha) */
.nv{display:inline-flex;gap:4px}
.nv i{width:7px;height:7px;border-radius:50%;background:rgba(38,61,50,.16)}
.tile .nv{position:absolute;top:18px;right:14px}
.luz{--tono:#9A7428}.luz.n1{background:#FAF3DE;border-color:#EFE2BA}.luz.n2{background:#F6EBCB;border-color:#EADBAE}.luz.n3{background:#F0DEAA;border-color:#E3CE90}
.riego{--tono:#4F7D96}.riego.n1{background:#EEF4F6;border-color:#DAE6EB}.riego.n2{background:#DFEBF1;border-color:#C8DCE6}.riego.n3{background:#CCDFEA;border-color:#B4CEDD}
.temperatura{--tono:#9C5A3E}.temperatura.n1{background:#F9F0EA;border-color:#EEDFD5}.temperatura.n2{background:#F4E2D6;border-color:#E8CFBF}.temperatura.n3{background:#EDD0BE;border-color:#E0BCA6}
.tile .nv i.on{background:var(--tono)}
.leyenda{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:.86rem;color:var(--oliva-osc)}
.leyenda .nv i.on{background:var(--oliva)}
/* Mascotas: verde suave si la ASPCA la da como no tóxica, rojo suave si es tóxica, neutro sin dato */
.tile.pet-ok{background:#E3EFDE;border-color:#C5D9BC}
.tile.pet-ok .ico{color:#2F5A2E}
.tile.pet-tox{background:#F7E2DF;border-color:#EAC6C0}
.tile.pet-tox .ico{color:#8A3A33}
.tile.pet-sd{background:var(--crema);border:1px dashed rgba(112,123,96,.55)}
.vh{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
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
.pet:not(.toxica):not(.sindato){background:#E3EFDE;border:1px solid #C5D9BC}
.pet.toxica{background:#F7E2DF;border:1px solid #EAC6C0}
.pet .estado{display:inline-flex;align-items:center;gap:8px;font-weight:500;color:#2F5A2E}
.pet.toxica .estado{color:#8A3A33}
.pet.sindato .estado{color:var(--bosque)}
.pet.sindato{background:var(--blanco);border:1px dashed rgba(112,123,96,.55)}
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
.cuenta{margin-top:10px;font-size:.9rem;color:var(--oliva-osc)}
.accesos ul{list-style:none;margin:0 0 30px;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.accesos a{display:inline-flex;align-items:center;gap:7px;min-height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--linea);background:var(--blanco);color:var(--bosque);font-size:.9rem;text-decoration:none;transition:border-color .2s}
.accesos a:hover{border-color:var(--bosque)}
.accesos span{font-size:.8rem;color:var(--malva-txt)}
.grupo{display:grid;gap:12px;scroll-margin-top:80px}
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
  // ¿Aún no la tienes?: copia la consulta para pegarla en Instagram
  Array.prototype.forEach.call(d.querySelectorAll('[data-stock]'), function(a){
    a.addEventListener('click', function(){
      var av = a.parentNode.querySelector('[data-stock-aviso]');
      if (!(navigator.clipboard && window.isSecureContext)) return;
      navigator.clipboard.writeText(a.getAttribute('data-stock')).then(function(){
        if (av) av.textContent = 'Copiamos tu consulta: pégala en el chat de Instagram.';
      }, function(){});
    });
  });
  // Buscador del índice
  var q = d.querySelector('[data-buscar]');
  if (q) {
    var items = Array.prototype.slice.call(d.querySelectorAll('[data-q]'));
    var grupos = Array.prototype.slice.call(d.querySelectorAll('[data-grupo]'));
    var vacio = d.querySelector('[data-vacio]');
    var accesos = d.querySelector('[data-accesos]');
    var norm = function(s){ return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); };
    var filtrar = function(){
      var ps = norm(q.value.trim()).split(/\s+/).filter(Boolean), n = 0;
      items.forEach(function(li){
        var h = li.getAttribute('data-q');
        var ok = ps.every(function(w){ return h.indexOf(w) > -1; });
        li.hidden = !ok; if (ok) n++;
      });
      grupos.forEach(function(g){ g.hidden = !g.querySelector('[data-q]:not([hidden])'); });
      if (vacio) vacio.hidden = n > 0;
      if (accesos) accesos.hidden = ps.length > 0;
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


def alias_visibles(p):
    """Los alias sirven al buscador; en la ficha se muestran solo los que aportan:
    fuera los que repiten el nombre botánico o una variedad ya nombrada abajo."""
    nom, bot, var = normalizar(p["nombre"]), normalizar(p["botanico"]), normalizar(p.get("variedades", ""))

    def en(t, texto):
        return bool(t) and re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", texto) is not None

    vistos, salida = set(), []
    for a in p.get("alias", []):
        n = normalizar(a)
        resto = n.split(" ", 1)[1] if " " in n else ""
        if (n in vistos or n == nom or en(n, bot) or en(n, var) or en(resto, var)
                or n.startswith(nom + " ")):
            continue
        vistos.add(n)
        salida.append(a)
    return salida


def boton_stock(datos, nombre):
    """Botón para quien aún no tiene la planta: abre los mensajes de Instagram y copia
    una consulta lista para pegar (Instagram no permite dejar el texto escrito)."""
    ig = datos["contacto"]["instagram"]
    msj = f"Hola, Jardín Malva. ¿Tienen {nombre} en stock?"
    return (f'<div class="stock-box"><a class="stock" href="https://ig.me/m/{e(ig)}" target="_blank" rel="noopener" '
            f'data-stock="{e(msj)}"><span class="stock-ico">{icono("consulta")}</span>'
            f'<span class="stock-txt"><b>¿Aún no la tienes?</b><span>Consulta el stock por Instagram</span></span>'
            f'{icono("flecha", "stock-fl")}</a>'
            f'<p class="stock-aviso" data-stock-aviso aria-live="polite"></p></div>')


def mascotas_corto(m):
    if m is None:
        return None
    if m.get("corto"):
        return m["corto"]
    if m["toxica"] is None:
        return "Sin dato verificado"
    return "Tóxica: fuera de su alcance" if m["toxica"] else "No tóxica"


# ---------------------------------------------------------------- ficha

def pagina_planta(datos, p, v_css, v_js):
    nombre = p["nombre"]
    titulo = f"Cómo cuidar tu {nombre} · Jardín Malva"
    desc = f"Cuidados de {nombre} ({p['botanico']}): luz, riego, abono y señales de alerta. {p['resumen']}"
    m = p.get("mascotas")
    tipo_txt = CATEGORIA_TEXTO[categoria(p)]
    alias = ""
    visibles = alias_visibles(p)
    if visibles:
        alias = f'\n    <p class="alias">Otros nombres: {e(", ".join(visibles))}</p>'
    dots = "".join(f'<i class="on"></i>' if i < p["dificultad"] else "<i></i>" for i in range(3))

    def tile_nivel(ic, campo, lb, que):
        n = nivel(p, campo)
        puntos = "".join('<i class="on"></i>' if i < n else "<i></i>" for i in range(3))
        return (f'      <li class="tile {campo} n{n}"><span class="ico">{icono(ic)}</span>'
                f'<span class="nv" aria-hidden="true">{puntos}</span>'
                f'<span class="lbl">{e(lb)}</span><span class="val">{e(p[campo]["corto"])}</span>'
                f'<span class="vh">Necesidad de {que}: {NIVEL_TXT[n]}.</span></li>')

    tiles = [tile_nivel("luz", "luz", "Luz", "luz"),
             tile_nivel("riego", "riego", "Riego", "agua"),
             tile_nivel("temp", "temperatura", "Temperatura", "calor")]
    if m is not None:
        cl = {True: "pet-tox", False: "pet-ok", None: "pet-sd"}[m["toxica"]]
        tiles.append(f'      <li class="tile {cl}"><span class="ico">{icono("pata")}</span>'
                     f'<span class="lbl">Mascotas</span><span class="val">{e(mascotas_corto(m))}</span></li>')
    tiles_html = "\n".join(tiles)

    r = p["riego"]
    nota_riego = ("Frecuencias orientativas: dependen de la luz, la maceta y la temperatura de tu casa. "
                  "Antes de regar, haz siempre la prueba del dedo." if p["tipo"] == "interior" else
                  "Frecuencias orientativas: dependen del sol, del suelo, del viento y de si está en maceta o en "
                  "el jardín. Antes de regar, haz siempre la prueba del dedo.")
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
        tox = m["toxica"]
        cl = " toxica" if tox else (" sindato" if tox is None else "")
        estado = {True: "Ojo con tus mascotas", False: "Buena noticia para tus mascotas",
                  None: "Sin dato verificado"}[tox]
        ic = {True: "alerta", False: "check", None: "pata"}[tox]
        extra = {True: " Mejor ubicarla fuera de su alcance y, si notas síntomas después de una mordida, llama a tu veterinario.",
                 False: "",
                 None: " Mientras no haya un dato verificado, mejor ubicarla fuera de su alcance."}[tox]
        fuente = (f'<p class="fuente">Fuente: <a href="{e(m["url"])}" target="_blank" rel="noopener">ASPCA, '
                  f'lista de plantas tóxicas y no tóxicas</a> (en inglés).</p>' if m.get("url") and "/nyc/" not in m["url"] else
                  f'<p class="fuente">Fuente: <a href="{e(m["url"])}" target="_blank" rel="noopener">ASPCA</a>.</p>' if m.get("url") else
                  '<p class="fuente">Consultamos la <a href="https://www.aspca.org/pet-care/aspca-poison-control/toxic-and-non-toxic-plants" target="_blank" rel="noopener">lista de la ASPCA</a> (en inglés).</p>')
        mascota_html = f"""<section class="sec" aria-labelledby="t-pet">
  <div class="wrap">
    <div class="sec-t">{icono("pata")}<h2 id="t-pet">Si tienes mascotas</h2></div>
    <div class="pet{cl}">
      <div>
        <p class="estado">{icono(ic)}{e(estado)}</p>
        <p>{e(m['texto'])}{e(extra)}</p>
        {fuente}
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
    {boton_stock(datos, nombre)}
  </div>
</section>

<section class="esencial" aria-labelledby="t-esencial">
  <div class="wrap">
    <p class="eyebrow" id="t-esencial">Lo esencial</p>
    <ul class="tiles">
{tiles_html}
    </ul>
    <p class="leyenda"><span class="nv" aria-hidden="true"><i class="on"></i><i class="on"></i><i></i></span>Cuanto más intenso el color, más luz, agua o calor necesita.</p>
  </div>
</section>

<section class="sec" aria-labelledby="t-riego">
  <div class="wrap">
    <div class="sec-t">{icono("riego")}<h2 id="t-riego">Riego</h2></div>
    <p>{e(r['texto'])}</p>
    <div class="estaciones">
{est_html}
    </div>
    <p class="nota">{e(nota_riego)}</p>
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
    grupos, accesos = [], []
    for cat, nombre_grupo in datos["categorias"].items():
        plantas = sorted((p for p in datos["plantas"] if categoria(p) == cat), key=lambda p: normalizar(p["nombre"]))
        if not plantas:
            continue
        accesos.append(f'<li><a href="#cat-{cat}">{e(nombre_grupo)} <span>{len(plantas)}</span></a></li>')
        items = []
        for p in plantas:
            q = normalizar(" ".join([p["nombre"], p["botanico"], *p.get("alias", []), p.get("variedades", "")]))
            items.append(
                f'      <li data-q="{e(q)}"><a href="/cuidados/{e(p["slug"])}">'
                f'<span class="n">{e(p["nombre"])}</span><span class="b">{e(p["botanico"])}</span>'
                f'<span class="r">{e(p["luz"]["corto"])} · {e(DIFICULTAD[p["dificultad"]])}</span>{icono("flecha")}</a></li>')
        grupos.append(f"""  <div class="grupo" data-grupo id="cat-{cat}">
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
    <p class="lead">Busca tu planta por su nombre: luz, riego y todo lo que necesita para crecer contigo.</p>
    <label class="buscador"><span class="sr">Buscar planta</span>{icono("buscar")}<input type="search" placeholder="Busca tu planta: monstera, lavanda…" autocomplete="off" data-buscar></label>
    <p class="cuenta">{len(datos["plantas"])} fichas. Busca por nombre común, científico o variedad.</p>
  </div>
</section>
<section class="sec">
  <div class="wrap">
    <nav class="accesos" aria-label="Categorías" data-accesos><ul>{"".join(accesos)}</ul></nav>
{chr(10).join(grupos)}
    <p class="vacio" data-vacio hidden>No encontramos esa planta. Escríbenos y te ayudamos con sus cuidados.</p>
  </div>
</section>
</main>

{cierre(datos, titulo="¿No encuentras tu planta?", texto="Escríbenos con su nombre o una foto y te contamos cómo cuidarla.", compartir=False)}"""
    return cabeza(datos, titulo, desc, "/cuidados/", v_css) + cuerpo + pie(datos, v_js)


# ---------------------------------------------------------------- plantas para casas con mascotas

# Nombre y nombre botánico de los grupos de variedades que comparten ficha base
GRUPOS_LISTA = {
    "calathea": ("Calatheas", "Goeppertia (antes Calathea)"),
    "peperomia": ("Peperomias", "Peperomia spp."),
    "maranta": ("Marantas", "Maranta leuconeura"),
    "hypoestes": ("Hypoestes", "Hypoestes phyllostachya"),
}
MARCA_INI = "<!-- PLANTAS-MASCOTAS:INICIO · lo genera herramientas/generar_cuidados.py, no editar a mano -->"
MARCA_FIN = "<!-- PLANTAS-MASCOTAS:FIN -->"


def familias_no_toxicas(datos):
    """Agrupa las plantas no tóxicas (ASPCA) por su ficha o perfil raíz. Devuelve {tipo: [familia]}."""
    por_slug = {p["slug"]: p for p in datos["plantas"]}

    def raiz(p):
        vistos = set()
        while p.get("base") and p["base"] in por_slug and p["slug"] not in vistos:
            vistos.add(p["slug"])
            p = por_slug[p["base"]]
        return p.get("base") or p["slug"]

    familias = {}
    for p in datos["plantas"]:
        m = p.get("mascotas")
        if not m or m.get("toxica") is not False:
            continue
        familias.setdefault(raiz(p), []).append(p)
    salida = {}
    for clave, miembros in familias.items():
        miembros.sort(key=lambda p: (p.get("base") is not None, normalizar(p["nombre"])))
        if len(miembros) > 1:
            titulo, bot = GRUPOS_LISTA.get(clave, (por_slug.get(clave, miembros[0])["nombre"], miembros[0]["botanico"]))
        else:
            titulo, bot = miembros[0]["nombre"], miembros[0]["botanico"]
        tipo = miembros[0]["tipo"]
        salida.setdefault(tipo, []).append({"id": clave, "titulo": titulo, "botanico": bot,
                                            "miembros": miembros, "luz": miembros[0]["luz"]["corto"]})
    for tipo in salida:
        salida[tipo].sort(key=lambda f: normalizar(f["titulo"]))
    return salida


def contar(familias):
    return sum(len(f["miembros"]) for fs in familias.values() for f in fs)


CSS_MASCOTAS = r"""
.m-hero{background:var(--crema);padding:clamp(30px,7vw,64px) 0}
.m-hero .wrap{display:grid;gap:clamp(28px,5vw,56px);align-items:center}
.m-hero-txt{display:grid;gap:12px;min-width:0}
.m-hero .lead{max-width:40ch}
.m-hero figure{margin:0;justify-self:center;width:min(78%,300px)}
.m-hero figure img{width:100%;height:auto;aspect-ratio:360/560;object-fit:cover;border-radius:999px 999px var(--r) var(--r);box-shadow:0 22px 48px rgba(38,61,50,.18)}
.m-hero figcaption{margin-top:10px;font-size:.88rem;color:var(--oliva-osc);text-align:center}
@media (min-width:820px){.m-hero .wrap{grid-template-columns:1.2fr .8fr}.m-hero figure{justify-self:end}}
.criterios{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.criterios li{display:grid;grid-template-columns:auto 1fr;gap:14px;padding:16px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea)}
.criterios svg{width:24px;height:24px;color:var(--malva-osc);margin-top:2px}
.criterios b{display:block;font:500 1.15rem/1.3 var(--f-display);color:var(--bosque);margin-bottom:2px}
.criterios span{font-size:.97rem}
@media (min-width:820px){.criterios{grid-template-columns:repeat(3,minmax(0,1fr))}}
.familias{list-style:none;margin:0;padding:0;display:grid;gap:12px}
@media (min-width:640px){.familias{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:980px){.familias{grid-template-columns:repeat(3,minmax(0,1fr))}}
.fam{display:grid;gap:6px;align-content:start;padding:18px;border-radius:var(--r);background:var(--blanco);border:1px solid var(--linea);scroll-margin-top:80px}
.fam:target{border-color:var(--malva-osc);box-shadow:0 0 0 3px rgba(180,154,175,.25)}
.fam h3{font-size:1.35rem}
.fam h3 a{text-decoration:none}
.fam h3 a:hover{text-decoration:underline}
.fam .b{font:italic 500 1.02rem/1.3 var(--f-display);color:var(--oliva-osc)}
.fam .l{display:flex;align-items:center;gap:6px;font-size:.88rem;color:var(--oliva-osc)}
.fam .l svg{width:16px;height:16px;flex:none}
.fam .ok{display:inline-flex;align-items:center;gap:6px;justify-self:start;margin-top:4px;padding:3px 10px;border-radius:999px;background:rgba(168,181,160,.28);font-size:.8rem;color:var(--bosque)}
.fam .ok svg{width:14px;height:14px}
.vars{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.vars a{display:inline-flex;align-items:center;min-height:34px;padding:0 12px;border-radius:999px;border:1px solid var(--linea);font-size:.88rem;color:var(--bosque);text-decoration:none}
.vars a:hover{border-color:var(--bosque)}
.fam>.ver{justify-self:start;margin-top:6px;font-size:.92rem;color:var(--bosque)}
.nota-fuente{font-size:.9rem;color:var(--oliva-osc)}
"""


def pagina_mascotas(datos, v_css, v_js):
    fams = familias_no_toxicas(datos)
    n = contar(fams)
    titulo = "Plantas para casas con perros y gatos · Jardín Malva"
    desc = (f"{n} plantas de Jardín Malva que la ASPCA clasifica como no tóxicas para perros y gatos. "
            "Vivero pet friendly en San Pedro de la Paz.")
    c = datos["contacto"]
    href, etiqueta, ico = enlace_contacto(datos)
    grupos_html = []
    for tipo, nombre_grupo in datos["grupos"].items():
        if tipo not in fams:
            continue
        tarjetas = []
        for f in fams[tipo]:
            ms = f["miembros"]
            if len(ms) == 1:
                cuerpo = (f'<h3><a href="/cuidados/{e(ms[0]["slug"])}">{e(f["titulo"])}</a></h3>'
                          f'<p class="b">{e(f["botanico"])}</p>'
                          f'<p class="l">{icono("luz")}{e(f["luz"])}</p>'
                          f'<p class="ok">{icono("check")}No tóxica · ASPCA</p>'
                          f'<a class="ver" href="/cuidados/{e(ms[0]["slug"])}">Cómo cuidarla</a>')
            else:
                vars_html = "".join(f'<li><a href="/cuidados/{e(m["slug"])}">{e(m["nombre"])}</a></li>' for m in ms)
                cuerpo = (f'<h3>{e(f["titulo"])}</h3>'
                          f'<p class="b">{e(f["botanico"])}</p>'
                          f'<p class="l">{icono("luz")}{e(f["luz"])}</p>'
                          f'<p class="ok">{icono("check")}No tóxicas · ASPCA</p>'
                          f'<ul class="vars" aria-label="Variedades de {e(f["titulo"])}">{vars_html}</ul>')
            tarjetas.append(f'      <li class="fam" id="{e(f["id"])}">{cuerpo}</li>')
        grupos_html.append(f"""  <div class="grupo">
    <h2>{e(nombre_grupo)}</h2>
    <ul class="familias">
{chr(10).join(tarjetas)}
    </ul>
  </div>""")
    robots = "" if datos.get("indexar") else '\n<meta name="robots" content="noindex">'
    cuerpo = f"""<!doctype html>
<html lang="es-CL">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(titulo)}</title>
<meta name="description" content="{e(desc)}">{robots}
<meta name="theme-color" content="#263D32">
<link rel="canonical" href="{e(datos['sitio'])}/mascotas">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_CL">
<meta property="og:site_name" content="Jardín Malva">
<meta property="og:url" content="{e(datos['sitio'])}/mascotas">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(datos['sitio'])}/assets/og.jpg">
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/cormorant.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/dmsans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/cuidados/cuidados.css?v={v_css}">
<style>{CSS_MASCOTAS.strip()}</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Jardín Malva, inicio"><img src="/assets/logo-128.webp" width="38" height="38" alt=""><span>Jardín Malva</span></a>
    <a class="top-link" href="/cuidados/">{icono("hoja")}Fichas de cuidado</a>
  </div>
</header>
<main>
<section class="m-hero" aria-labelledby="t-masc">
  <div class="wrap">
    <div class="m-hero-txt">
      <p class="eyebrow">Pet friendly</p>
      <h1 id="t-masc">Plantas para casas con perros y gatos</h1>
      <p class="script">ellos también viven aquí</p>
      <p class="lead">En Jardín Malva los perros son parte del equipo. Estas son las {n} plantas de nuestras fichas de cuidado que la ASPCA clasifica como no tóxicas para perros y gatos.</p>
      <p class="nota-fuente">La disponibilidad cambia con la temporada: pregúntanos antes de venir.</p>
    </div>
    <figure>
      <img src="/assets/perros-poster.webp" width="360" height="646" decoding="async" alt="Uno de los perros del vivero corriendo entre los mesones de plantas">
      <figcaption>Uno de los dueños de casa, de ronda por el vivero.</figcaption>
    </figure>
  </div>
</section>

<section class="sec" aria-labelledby="t-crit">
  <div class="wrap">
    <h2 id="t-crit">Cómo armamos esta lista</h2>
    <ul class="criterios">
      <li>{icono("check")}<span><b>Solo con fuente</b>Cada planta figura como no tóxica para perros y gatos en la lista de la ASPCA, la principal referencia en intoxicaciones de mascotas de Estados Unidos.</span></li>
      <li>{icono("pata")}<span><b>No tóxica no es comestible</b>Si la mastican, cualquier planta puede caerles pesada al estómago. Mejor que no se la coman.</span></li>
      <li>{icono("alerta")}<span><b>Sin dato, no entra</b>Las plantas que la ASPCA no ha evaluado no aparecen aquí, aunque parezcan inofensivas.</span></li>
    </ul>
  </div>
</section>

<section class="sec" aria-label="Plantas no tóxicas para perros y gatos">
  <div class="wrap">
{chr(10).join(grupos_html)}
    <p class="nota-fuente">Fuente: <a href="https://www.aspca.org/pet-care/aspca-poison-control/toxic-and-non-toxic-plants" target="_blank" rel="noopener">ASPCA, lista de plantas tóxicas y no tóxicas</a> (en inglés). ¿Tu planta no está aquí? <a href="/cuidados/">Busca su ficha de cuidados</a>: cada una dice si es tóxica, no tóxica o si no hay dato.</p>
  </div>
</section>
</main>

<section class="cierre" aria-labelledby="t-cierre">
  <div class="wrap">
    <h2 id="t-cierre">Ven con tu perro</h2>
    <p>En el vivero son bienvenidos. Te ayudamos a elegir plantas para tu casa y tus mascotas.</p>
    <div class="acciones">
      <a class="btn btn-pri" href="{e(c['maps'])}" target="_blank" rel="noopener">{icono("mapa")}Cómo llegar</a>
      <a class="btn btn-sec" href="{e(href)}" target="_blank" rel="noopener">{icono(ico)}{e(etiqueta)}</a>
    </div>
  </div>
</section>
"""
    return cuerpo + pie(datos, v_js)


def bloque_sitio(datos):
    fams = familias_no_toxicas(datos)
    n = contar(fams)
    # primero las del inventario actual (con código), luego las de más variedades
    todas = sorted((f for fs in fams.values() for f in fs),
                   key=lambda f: (not any(m.get("codigo") for m in f["miembros"]), -len(f["miembros"]), normalizar(f["titulo"])))
    chips = "".join(f'<li><a href="/mascotas#{e(f["id"])}">{e(f["titulo"])}</a></li>' for f in todas[:8])
    return (f'{MARCA_INI}\n'
            f'        <div class="pet-plantas reveal">\n'
            f'          <h3>Plantas para casas con mascotas</h3>\n'
            f'          <p>{n} plantas que la ASPCA clasifica como no tóxicas para perros y gatos, con sus cuidados.</p>\n'
            f'          <ul class="pet-chips">{chips}</ul>\n'
            f'          <a class="btn btn-sec" href="/mascotas">Ver la lista completa</a>\n'
            f'        </div>\n'
            f'        {MARCA_FIN}')


def actualizar_sitio(datos):
    if not SITIO.exists():
        return "no existe sitio.html"
    html_sitio = SITIO.read_text(encoding="utf-8")
    i, f = html_sitio.find(MARCA_INI), html_sitio.find(MARCA_FIN)
    if i < 0 or f < 0:
        return "sitio.html no tiene las marcas PLANTAS-MASCOTAS (no se tocó)"
    nuevo = html_sitio[:i] + bloque_sitio(datos) + html_sitio[f + len(MARCA_FIN):]
    if nuevo != html_sitio:
        SITIO.write_text(nuevo, encoding="utf-8")
        return "bloque de mascotas actualizado"
    return "bloque de mascotas sin cambios"


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
    MASCOTAS.write_text(pagina_mascotas(datos, v_css, v_js), encoding="utf-8")
    estado_sitio = actualizar_sitio(datos)
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
    print(f"OK: /mascotas con {contar(familias_no_toxicas(datos))} plantas no tóxicas · sitio.html: {estado_sitio}")
    print("Indexación en buscadores:", "sí" if datos.get("indexar") else "no (noindex)")


if __name__ == "__main__":
    main()
