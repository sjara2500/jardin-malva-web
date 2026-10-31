#!/usr/bin/env python3
"""Genera los imprimibles con QR de las fichas de cuidado.

Uso:  pip install reportlab segno pillow
      python3 herramientas/generar_tarjetas.py

Crea en imprimibles/:
- tarjetas-cuidados.pdf   Una hoja A4 por planta con 10 tarjetas iguales de 85 × 55 mm.
- tarjetas-surtidas.pdf   Una tarjeta de cada planta (10 por hoja), para el mesón o para revisar.
- cartel-cuidados-A5.pdf  Cartel para la caja con el QR del índice de fichas.
- qr/<planta>.svg y .png  Los códigos sueltos, por si se usan en otro diseño.

Imprimir al 100 % ("tamaño real", sin "ajustar a la página") y cortar por las marcas.
"""
import json
import sys
from pathlib import Path

import segno
from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "herramientas" / "fuentes"
SALIDA = RAIZ / "imprimibles"
ASSETS = RAIZ / "public" / "assets"

BOSQUE = HexColor("#263D32")
OLIVA = HexColor("#5C6752")
MALVA = HexColor("#7E6279")
MALVA_CLARO = HexColor("#B49AAF")
CARBON = HexColor("#292D28")
LINEA = HexColor("#C9C6BC")

for nombre, archivo in [("Cormorant", "CormorantGaramond-Medium.ttf"),
                        ("CormorantSB", "CormorantGaramond-SemiBold.ttf"),
                        ("CormorantIt", "CormorantGaramond-MediumItalic.ttf"),
                        ("DMSans", "DMSans-Regular.ttf"),
                        ("DMSansMd", "DMSans-Medium.ttf"),
                        ("Parisienne", "Parisienne-Regular.ttf")]:
    pdfmetrics.registerFont(TTFont(nombre, str(FUENTES / archivo)))

TW, TH = 85 * mm, 55 * mm          # tarjeta
COLS, FILAS = 2, 5                 # 10 por A4


def cargar():
    datos = json.loads((RAIZ / "datos" / "cuidados.json").read_text(encoding="utf-8"))
    return datos


def url_ficha(datos, slug):
    return f"{datos['sitio']}/cuidados/{slug}"


def url_indice(datos):
    return f"{datos['sitio']}/cuidados/"


def texto_mascotas(p):
    m = p.get("mascotas")
    if m is None:
        return None
    if m.get("corto", "").startswith("Levemente"):
        return "Levemente tóxica para mascotas"
    return "Tóxica para mascotas" if m["toxica"] else "No tóxica para mascotas"


# ---------------------------------------------------------------- utilidades de dibujo

def dibujar_qr(c, datos_qr, x, y, lado, color=BOSQUE):
    """QR vectorial (sin zona de silencio: el blanco alrededor lo pone el diseño)."""
    qr = segno.make(datos_qr, error="q", micro=False)
    filas = list(qr.matrix_iter(scale=1, border=0))
    n = len(filas)
    m = lado / n
    c.setFillColor(color)
    c.setStrokeColor(color)
    for fila_i, fila in enumerate(filas):
        j = 0
        while j < n:
            if fila[j]:
                k = j
                while k < n and fila[k]:
                    k += 1
                # se solapa una fracción para que no aparezcan líneas finas entre módulos
                c.rect(x + j * m, y + lado - (fila_i + 1) * m, (k - j) * m + 0.02, m + 0.02, stroke=0, fill=1)
                j = k
            else:
                j += 1
    return qr


def ancho(texto, fuente, tam):
    return pdfmetrics.stringWidth(texto, fuente, tam)


def ajustar(texto, fuente, tam_max, tam_min, ancho_max):
    """Mayor tamaño de letra en el que el texto cabe en una línea."""
    t = tam_max
    while t > tam_min and ancho(texto, fuente, t) > ancho_max:
        t -= 0.25
    return t


def partir(texto, fuente, tam, ancho_max):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if ancho(prueba, fuente, tam) <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def texto_espaciado(c, x, y, texto, fuente, tam, espacio, color, derecha=False):
    # El espaciado entre letras (Tc) queda en el estado gráfico: se aísla para que no
    # afecte a los textos que vienen después.
    c.saveState()
    c.setFillColor(color)
    to = c.beginText()
    to.setFont(fuente, tam)
    to.setCharSpace(espacio)
    w = ancho(texto, fuente, tam) + espacio * (len(texto) - 1)
    to.setTextOrigin(x - w if derecha else x, y)
    to.textOut(texto)
    c.drawText(to)
    c.restoreState()
    return w


# mini iconos de línea (en un cuadro de 2,8 mm)
def ico_sol(c, x, y, s):
    c.setLineWidth(0.45)
    cx, cy = x + s / 2, y + s / 2
    c.circle(cx, cy, s * 0.2, stroke=1, fill=0)
    import math
    for i in range(8):
        a = i * math.pi / 4
        c.line(cx + math.cos(a) * s * 0.32, cy + math.sin(a) * s * 0.32,
               cx + math.cos(a) * s * 0.47, cy + math.sin(a) * s * 0.47)


def ico_gota(c, x, y, s):
    c.setLineWidth(0.45)
    p = c.beginPath()
    cx = x + s / 2
    p.moveTo(cx, y + s * 0.98)
    p.curveTo(cx - s * 0.1, y + s * 0.75, cx - s * 0.36, y + s * 0.55, cx - s * 0.36, y + s * 0.36)
    p.curveTo(cx - s * 0.36, y + s * 0.12, cx - s * 0.18, y + s * 0.02, cx, y + s * 0.02)
    p.curveTo(cx + s * 0.18, y + s * 0.02, cx + s * 0.36, y + s * 0.12, cx + s * 0.36, y + s * 0.36)
    p.curveTo(cx + s * 0.36, y + s * 0.55, cx + s * 0.1, y + s * 0.75, cx, y + s * 0.98)
    c.drawPath(p, stroke=1, fill=0)


def ico_pata(c, x, y, s, relleno):
    c.setLineWidth(0.4)
    for dx, dy in [(0.18, 0.58), (0.38, 0.8), (0.62, 0.8), (0.82, 0.58)]:
        c.circle(x + s * dx, y + s * dy, s * 0.1, stroke=0, fill=1)
    c.ellipse(x + s * 0.28, y + s * 0.06, x + s * 0.72, y + s * 0.48, stroke=0, fill=1)


# ---------------------------------------------------------------- tarjeta

def tarjeta(c, datos, p, x0, y0):
    """Dibuja una tarjeta con su esquina inferior izquierda en (x0, y0)."""
    c.saveState()
    c.translate(x0, y0)
    # QR
    lado = 30 * mm
    qx, qy = 5 * mm, 15 * mm
    dibujar_qr(c, url_ficha(datos, p["slug"]), qx, qy, lado)
    c.setFillColor(OLIVA)
    c.setFont("DMSans", 5.4)
    # el texto queda a más de 4 módulos del código (zona de silencio)
    c.drawCentredString(qx + lado / 2, qy - 5.2 * mm, "Escanéame y aprende")
    c.drawCentredString(qx + lado / 2, qy - 7.6 * mm, "a cuidarla")

    # Columna de texto
    tx = 40 * mm
    tw = TW - tx - 4.5 * mm
    y = TH - 8.2 * mm
    texto_espaciado(c, tx, y, "CUIDADOS DE TU", "DMSansMd", 5.2, 0.9, MALVA)

    nombre = p["nombre"]
    tam = ajustar(nombre, "CormorantSB", 17, 13, tw)
    c.setFillColor(BOSQUE)
    if ancho(nombre, "CormorantSB", tam) <= tw:
        y -= 6.4 * mm
        c.setFont("CormorantSB", tam)
        c.drawString(tx, y, nombre)
    else:
        tam = 13.5
        lineas = partir(nombre, "CormorantSB", tam, tw)
        c.setFont("CormorantSB", tam)
        for i, l in enumerate(lineas[:2]):
            y -= (5.6 if i == 0 else 4.6) * mm
            c.drawString(tx, y, l)

    bot = p["botanico"].split(" (")[0]
    tb = ajustar(bot, "CormorantIt", 8.4, 6.6, tw)
    y -= 3.9 * mm
    c.setFillColor(OLIVA)
    c.setFont("CormorantIt", tb)
    c.drawString(tx, y, bot)

    y -= 2.6 * mm
    c.setStrokeColor(MALVA_CLARO)
    c.setLineWidth(0.4)
    c.line(tx, y, tx + 12 * mm, y)

    # Tres datos
    filas = [("sol", p["luz"]["corto"]), ("gota", p["riego"]["corto"])]
    tm = texto_mascotas(p)
    if tm:
        filas.append(("pata", tm))
    s = 2.7 * mm
    tamf = 6.3
    y -= 1.2 * mm
    for ic, t in filas:
        lineas = partir(t, "DMSans", tamf, tw - s - 1.6 * mm)
        alto = 3.3 * mm * len(lineas)
        y -= 3.5 * mm
        toxica = ic == "pata" and p.get("mascotas", {}).get("toxica")
        col = MALVA if toxica else BOSQUE
        c.setStrokeColor(col)
        c.setFillColor(col)
        if ic == "sol":
            ico_sol(c, tx, y - 0.55 * mm, s)
        elif ic == "gota":
            ico_gota(c, tx, y - 0.55 * mm, s)
        else:
            ico_pata(c, tx, y - 0.55 * mm, s, True)
        c.setFillColor(MALVA if toxica else CARBON)
        c.setFont("DMSansMd" if toxica else "DMSans", tamf)
        for i, l in enumerate(lineas):
            c.drawString(tx + s + 1.6 * mm, y - i * 2.9 * mm, l)
        y -= (len(lineas) - 1) * 2.9 * mm

    # Pie de marca
    texto_espaciado(c, TW - 4.5 * mm, 4.6 * mm, "JARDÍN MALVA", "CormorantSB", 7.2, 0.9, BOSQUE, derecha=True)
    c.setFillColor(OLIVA)
    c.setFont("DMSans", 5.2)
    c.drawRightString(TW - 4.5 * mm, 2.4 * mm, "jardinmalva.cl/cuidados")
    c.restoreState()


def marcas_corte(c, x0, y0, cols, filas):
    """Marcas de corte fuera de la zona impresa, en cada línea de corte."""
    c.setStrokeColor(HexColor("#8A8A8A"))
    c.setLineWidth(0.3)
    largo, sep = 5 * mm, 1.5 * mm
    xs = [x0 + i * TW for i in range(cols + 1)]
    ys = [y0 + j * TH for j in range(filas + 1)]
    top, der = ys[-1], xs[-1]
    for x in xs:
        c.line(x, y0 - sep, x, y0 - sep - largo)
        c.line(x, top + sep, x, top + sep + largo)
    for y in ys:
        c.line(x0 - sep, y, x0 - sep - largo, y)
        c.line(der + sep, y, der + sep + largo, y)


def hoja_tarjetas(c, datos, plantas, titulo_hoja):
    W, H = A4
    x0 = (W - COLS * TW) / 2
    y0 = (H - FILAS * TH) / 2
    for i, p in enumerate(plantas):
        col, fila = i % COLS, FILAS - 1 - i // COLS
        tarjeta(c, datos, p, x0 + col * TW, y0 + fila * TH)
    # líneas de guía muy claras entre tarjetas (quedan en el corte)
    c.setStrokeColor(HexColor("#E4E1D8"))
    c.setLineWidth(0.25)
    c.setDash(1, 2)
    for i in range(1, COLS):
        c.line(x0 + i * TW, y0, x0 + i * TW, y0 + FILAS * TH)
    for j in range(1, FILAS):
        c.line(x0, y0 + j * TH, x0 + COLS * TW, y0 + j * TH)
    c.setDash()
    marcas_corte(c, x0, y0, COLS, FILAS)
    c.setFillColor(HexColor("#8A8A8A"))
    c.setFont("DMSans", 6)
    c.drawString(x0, 3.5 * mm, f"{titulo_hoja} · Imprimir al 100 % (tamaño real) en cartulina blanca · Tarjetas de 85 × 55 mm")


def pdf_tarjetas(datos):
    ruta = SALIDA / "tarjetas-cuidados.pdf"
    c = canvas.Canvas(str(ruta), pagesize=A4)
    c.setTitle("Tarjetas de cuidados · Jardín Malva")
    c.setAuthor("Jardín Malva")
    for p in sorted(datos["plantas"], key=lambda p: p["nombre"]):
        hoja_tarjetas(c, datos, [p] * (COLS * FILAS), p["nombre"])
        c.bookmarkPage(p["slug"])
        c.addOutlineEntry(p["nombre"], p["slug"], level=0)
        c.showPage()
    c.save()
    return ruta


def pdf_surtidas(datos):
    ruta = SALIDA / "tarjetas-surtidas.pdf"
    c = canvas.Canvas(str(ruta), pagesize=A4)
    c.setTitle("Tarjetas de cuidados surtidas · Jardín Malva")
    c.setAuthor("Jardín Malva")
    plantas = sorted(datos["plantas"], key=lambda p: p["nombre"])
    paginas = [plantas[i:i + COLS * FILAS] for i in range(0, len(plantas), COLS * FILAS)]
    for n, grupo in enumerate(paginas, 1):
        hoja_tarjetas(c, datos, grupo, f"Surtidas {n}/{len(paginas)}")
        c.showPage()
    c.save()
    return ruta


# ---------------------------------------------------------------- cartel A5

def pdf_cartel(datos):
    ruta = SALIDA / "cartel-cuidados-A5.pdf"
    W, H = A5
    c = canvas.Canvas(str(ruta), pagesize=A5)
    c.setTitle("Cartel fichas de cuidado · Jardín Malva")
    c.setAuthor("Jardín Malva")
    # marco fino
    c.setStrokeColor(MALVA_CLARO)
    c.setLineWidth(0.6)
    c.roundRect(8 * mm, 8 * mm, W - 16 * mm, H - 16 * mm, 4 * mm, stroke=1, fill=0)
    # emblema oficial (versión publicada en la web)
    logo = Image.open(ASSETS / "logo-petfriendly-640.webp").convert("RGBA")
    d = 30 * mm
    c.drawImage(ImageReader(logo), (W - d) / 2, H - 14 * mm - d, d, d, mask="auto")
    y = H - 14 * mm - d - 10 * mm
    w = ancho("FICHAS DE CUIDADO", "DMSansMd", 8) + 1.6 * 16
    texto_espaciado(c, (W - w) / 2, y, "FICHAS DE CUIDADO", "DMSansMd", 8, 1.6, MALVA)
    c.setFillColor(BOSQUE)
    c.setFont("Cormorant", 27)
    for i, l in enumerate(["Cada planta tiene", "su ficha de cuidados"]):
        c.drawCentredString(W / 2, y - 11 * mm - i * 10 * mm, l)
    y = y - 11 * mm - 10 * mm - 9 * mm
    c.setFillColor(CARBON)
    c.setFont("DMSans", 10)
    for i, l in enumerate(["Escanea el código y busca la tuya:", "luz, riego y si es tóxica para tus mascotas."]):
        c.drawCentredString(W / 2, y - i * 5 * mm, l)
    lado = 52 * mm
    qy = y - 5 * mm - 8 * mm - lado
    dibujar_qr(c, url_indice(datos), (W - lado) / 2, qy, lado)
    c.setFillColor(BOSQUE)
    c.setFont("DMSansMd", 10)
    c.drawCentredString(W / 2, qy - 7 * mm, "jardinmalva.cl/cuidados")
    c.setFillColor(OLIVA)
    c.setFont("Parisienne", 15)
    c.drawCentredString(W / 2, 14 * mm, "cultivar, cuidar y vivir más lento")
    pet = Image.open(ASSETS / "petunia-400.webp").convert("RGBA")
    ph = 46 * mm
    pw = ph * pet.width / pet.height
    c.drawImage(ImageReader(pet), W - pw - 13 * mm, 20 * mm, pw, ph, mask="auto")
    c.showPage()
    c.save()
    return ruta


# ---------------------------------------------------------------- QR sueltos

def qr_sueltos(datos):
    carpeta = SALIDA / "qr"
    carpeta.mkdir(parents=True, exist_ok=True)
    pares = [(p["slug"], url_ficha(datos, p["slug"])) for p in datos["plantas"]]
    pares.append(("indice", url_indice(datos)))
    for slug, url in pares:
        qr = segno.make(url, error="q", micro=False)
        qr.save(carpeta / f"{slug}.svg", kind="svg", dark="#263D32", light="#FFFFFF", scale=10, border=4,
                title=url)
        qr.save(carpeta / f"{slug}.png", kind="png", dark="#263D32", light="#FFFFFF", scale=24, border=4)
    return carpeta, len(pares)


def main():
    datos = cargar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    for f in (pdf_tarjetas(datos), pdf_surtidas(datos), pdf_cartel(datos)):
        print("OK:", f.relative_to(RAIZ))
    carpeta, n = qr_sueltos(datos)
    print(f"OK: {n} códigos QR en {carpeta.relative_to(RAIZ)}/")


if __name__ == "__main__":
    sys.exit(main())
