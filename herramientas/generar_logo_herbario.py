#!/usr/bin/env python3
"""Logo de la guía de cuidados (submarca de Jardín Malva).

Dibuja un arco de invernadero, como los de la web, con una fronda prensada de
herbario y la flor malva de cinco pétalos, más el nombre en Cormorant Garamond y
"JARDÍN MALVA" en DM Sans. Las letras van convertidas en trazos: el SVG se ve igual
en cualquier sitio, sin depender de las fuentes.

No toca ni reproduce el logo oficial de Jardín Malva: es una marca aparte para
la guía, como Malva Atelier.

Uso:  python3 herramientas/generar_logo_herbario.py            (nombre: Herbario)
      python3 herramientas/generar_logo_herbario.py "Cuidario"  (otro nombre)

Genera en public/assets/:
  herbario-logo.svg          vertical, para fondos claros
  herbario-logo-claro.svg    vertical, para fondos verde bosque
  herbario-horizontal.svg    horizontal, para fondos claros
  herbario-emblema.svg       solo el arco (icono)
"""
import math
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "herramientas" / "fuentes"
SALIDA = RAIZ / "public" / "assets"

CLARO = {"arco": "#263D32", "arco2": "#A8B5A0", "tallo": "#263D32", "hoja": "#5C6752",
         "hoja2": "#707B60", "flor": "#B49AAF", "centro": "#F5F0E6", "nombre": "#263D32",
         "marca": "#6B5166", "linea": "#B49AAF"}
OSCURO = {"arco": "#F5F0E6", "arco2": "#A8B5A0", "tallo": "#F5F0E6", "hoja": "#A8B5A0",
          "hoja2": "#C3CDBC", "flor": "#C9B6C4", "centro": "#263D32", "nombre": "#F5F0E6",
          "marca": "#C9B6C4", "linea": "#C9B6C4"}


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


class Texto:
    """Convierte una línea de texto en un trazo SVG con espaciado entre letras."""

    def __init__(self, archivo):
        self.font = TTFont(FUENTES / archivo)
        self.cmap = self.font.getBestCmap()
        self.gs = self.font.getGlyphSet()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]
        os2 = self.font["OS/2"]
        self.alto_mayus = getattr(os2, "sCapHeight", 0) or self.upm * 0.65

    def ancho(self, txt, tam, espaciado):
        esc = tam / self.upm
        total = sum(self.hmtx[self.cmap[ord(c)]][0] * esc for c in txt)
        return total + espaciado * tam * (len(txt) - 1)

    def trazo(self, txt, tam, espaciado, x, base):
        """x: borde izquierdo; base: línea base (coordenadas SVG, y hacia abajo)."""
        esc = tam / self.upm
        pen = SVGPathPen(self.gs, ntos=f)
        for c in txt:
            g = self.cmap[ord(c)]
            tp = TransformPen(pen, (esc, 0, 0, -esc, x, base))
            self.gs[g].draw(tp)
            x += self.hmtx[g][0] * esc + espaciado * tam
        return pen.getCommands()


def hoja(px, py, ang, largo, ancho):
    """Folíolo en forma de lágrima que nace en (px, py) y apunta en el ángulo dado."""
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    tx, ty = px + dx * largo, py + dy * largo
    c1 = (px + dx * largo * .45 + nx * ancho, py + dy * largo * .45 + ny * ancho)
    c2 = (px + dx * largo * .45 - nx * ancho, py + dy * largo * .45 - ny * ancho)
    return (f"M{f(px)} {f(py)}Q{f(c1[0])} {f(c1[1])} {f(tx)} {f(ty)}"
            f"Q{f(c2[0])} {f(c2[1])} {f(px)} {f(py)}Z")


def emblema(c, ox=0, oy=0):
    """Arco de 96 × 128 con la fronda y la flor. Devuelve SVG (grupo) en (ox, oy)."""
    partes = [f'<g transform="translate({f(ox)} {f(oy)})">']
    # arco de invernadero con su segundo contorno, como los arcos de la web
    partes.append(f'<path d="M6 127V50A42 42 0 0 1 90 50V127Z" fill="none" stroke="{c["arco"]}" stroke-width="2.6" stroke-linejoin="round"/>')
    partes.append(f'<path d="M13 120V51A35 35 0 0 1 83 51V120Z" fill="none" stroke="{c["arco2"]}" stroke-width="1.2"/>')
    # tallo de la fronda: curva suave desde la flor hasta la punta
    p0, p1, p2 = (48, 108), (44, 70), (52, 24)
    partes.append(f'<path d="M{p0[0]} {p0[1]}Q{p1[0]} {p1[1]} {p2[0]} {p2[1]}" fill="none" stroke="{c["tallo"]}" stroke-width="1.7" stroke-linecap="round"/>')
    hojas = []
    n = 10
    for i in range(n):
        t = .13 + .82 * i / (n - 1)
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        tx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
        ty = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
        base = math.atan2(ty, tx)
        largo = 21 - 13.5 * (i / (n - 1)) ** 1.1
        ancho = largo * .31
        for lado in (-1, 1):
            hojas.append((hoja(x, y, base + lado * math.radians(54), largo, ancho), i % 2))
    for d, alt in hojas:
        partes.append(f'<path d="{d}" fill="{c["hoja2"] if alt else c["hoja"]}"/>')
    # folíolo terminal
    partes.append(f'<path d="{hoja(52, 25, math.radians(-78), 9, 3)}" fill="{c["hoja"]}"/>')
    # flor malva de cinco pétalos en la base
    cx, cy, r = 48, 110, 4.5
    for k in range(5):
        a = math.radians(-90 + k * 72)
        # pétalos separados por una línea fina, sin solaparse (flor simétrica)
        px, py = cx + math.cos(a) * 5.4, cy + math.sin(a) * 5.4
        partes.append(f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="3.1" ry="{r}" '
                      f'transform="rotate({f(k * 72)} {f(px)} {f(py)})" fill="{c["flor"]}"/>')
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="2.3" fill="{c["centro"]}"/>')
    partes.append("</g>")
    return "".join(partes)


def svg(ancho, alto, cuerpo, titulo):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(ancho)} {f(alto)}" '
            f'width="{f(ancho * 2)}" height="{f(alto * 2)}" role="img" aria-label="{titulo}">'
            f"<title>{titulo}</title>{cuerpo}</svg>\n")


def main():
    nombre = (sys.argv[1] if len(sys.argv) > 1 else "Herbario").upper()
    serif = Texto("CormorantGaramond-SemiBold.ttf")
    sans = Texto("DMSans-Medium.ttf")
    titulo = f"{nombre.capitalize()} · Jardín Malva"

    def bloque_texto(c, cx=None, x0=None, y0=0, tam=30):
        """Nombre + JARDÍN MALVA entre líneas. Centrado en cx o alineado a x0."""
        esp_n, tam_m, esp_m = .16, 7.2, .34
        an_n = serif.ancho(nombre, tam, esp_n)
        an_m = sans.ancho("JARDÍN MALVA", tam_m, esp_m)
        base_n = y0 + serif.alto_mayus * tam / serif.upm
        base_m = base_n + 16
        if cx is not None:
            xn, xm = cx - an_n / 2, cx - an_m / 2
        else:
            xn, xm = x0, x0 + (an_n - an_m) / 2
        trazos = [f'<path fill="{c["nombre"]}" d="{serif.trazo(nombre, tam, esp_n, xn, base_n)}"/>',
                  f'<path fill="{c["marca"]}" d="{sans.trazo("JARDÍN MALVA", tam_m, esp_m, xm, base_m)}"/>']
        ym = base_m - sans.alto_mayus * tam_m / sans.upm / 2
        izq, der = xn, xn + an_n
        trazos.append(f'<path d="M{f(izq)} {f(ym)}H{f(xm - 7)}M{f(xm + an_m + 7)} {f(ym)}H{f(der)}" '
                      f'stroke="{c["linea"]}" stroke-width=".9" stroke-linecap="round"/>')
        return "".join(trazos), an_n, base_m

    SALIDA.mkdir(parents=True, exist_ok=True)
    escritos = []
    for archivo, c in (("herbario-logo.svg", CLARO), ("herbario-logo-claro.svg", OSCURO)):
        texto, an_n, base_m = bloque_texto(c, cx=0, y0=0)
        ancho = max(an_n, 96) + 16
        cx = ancho / 2
        texto, an_n, base_m = bloque_texto(c, cx=cx, y0=142)
        cuerpo = emblema(c, cx - 48, 4) + texto
        (SALIDA / archivo).write_text(svg(ancho, base_m + 6, cuerpo, titulo), encoding="utf-8")
        escritos.append(archivo)
    # horizontal: emblema a la izquierda, texto a la derecha
    tam = 34
    texto, an_n, base_m = bloque_texto(CLARO, x0=112, y0=48, tam=tam)
    cuerpo = emblema(CLARO, 4, 2) + texto
    (SALIDA / "herbario-horizontal.svg").write_text(svg(112 + an_n + 6, 133, cuerpo, titulo), encoding="utf-8")
    escritos.append("herbario-horizontal.svg")
    (SALIDA / "herbario-emblema.svg").write_text(svg(96, 131, emblema(CLARO, 0, 2), titulo), encoding="utf-8")
    escritos.append("herbario-emblema.svg")
    print(f"OK: logo «{nombre}» →", ", ".join(f"public/assets/{a}" for a in escritos))


if __name__ == "__main__":
    main()
