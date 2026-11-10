# -*- coding: utf-8 -*-
"""Primitivas para dibujar las vistas de diseño (renders) del portafolio.

Los PNG de cada proyecto NO son capturas de Power BI Desktop ni de Power Apps Studio: son renders del diseño
dibujados con Pillow a partir de los datos sintéticos del propio proyecto. Cada uno lleva su leyenda.

Uso básico:
    from lib_render import Lienzo, PAL
    c = Lienzo(1920, 1080, PAL["fondo"])
    c.caja(24, 112, 361, 190, fill=PAL["panel"], borde=PAL["borde"], r=8)
    c.texto(40, 130, "MOVIMIENTO", 14, PAL["texto"], bold=True)
    c.guardar("salida.png")
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
LOGO_BLANCO = RAIZ / "assets" / "logo_minera_demo_blanco.png"
LOGO_COLOR = RAIZ / "assets" / "logo_minera_demo_color.png"
ICONO = RAIZ / "assets" / "icono_minera_demo.png"

# Paleta de «Minera Demo» (assets/paleta.md) y colores de semáforo
PAL = {
    "azul_noche": "#1B2A41", "azul": "#4F9DDE", "violeta": "#7B61C9",
    "fondo": "#0F1B2D", "fondo_claro": "#F3F5F9", "panel": "#16263D", "panel2": "#1B2F4B", "borde": "#2A4262",
    "texto": "#E8EEF7", "texto2": "#9FB1C9", "texto_osc": "#1B2A41", "texto_osc2": "#5B6B82",
    "verde": "#3FCF8E", "ambar": "#F5A524", "rojo": "#F2655F", "gris": "#7C8DA6", "blanco": "#FFFFFF",
}

_FUENTES = {
    False: ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
    True: ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "ligera": ["segoeuil.ttf", "segoeui.ttf", "DejaVuSans.ttf"],
}
_cache = {}


def _fuente(px, bold=False):
    clave = (round(px), bold)
    if clave not in _cache:
        for nombre in _FUENTES[bold]:
            try:
                _cache[clave] = ImageFont.truetype(nombre, round(px))
                break
            except OSError:
                continue
        else:
            _cache[clave] = ImageFont.load_default()
    return _cache[clave]


def fmt(v, dec=0, miles=" "):
    """Número con coma decimal y separador de miles (formato es-CL)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", miles)


class Lienzo:
    """Lienzo con supersampling (dibuja a ss× y reduce al guardar) para bordes suaves."""

    def __init__(self, w, h, fondo, ss=2):
        self.w, self.h, self.ss = w, h, ss
        self.im = Image.new("RGB", (w * ss, h * ss), fondo)
        self.d = ImageDraw.Draw(self.im, "RGBA")

    # ---- formas -----------------------------------------------------------------------------------------------
    def caja(self, x, y, w, h, fill=None, borde=None, r=0, ancho=1):
        s = self.ss
        box = [x * s, y * s, (x + w) * s - 1, (y + h) * s - 1]
        if r:
            self.d.rounded_rectangle(box, r * s, fill=fill, outline=borde, width=ancho * s if borde else 0)
        else:
            self.d.rectangle(box, fill=fill, outline=borde, width=ancho * s if borde else 0)

    def linea(self, p, color, ancho=1):
        s = self.ss
        self.d.line([(px * s, py * s) for px, py in p], fill=color, width=max(1, round(ancho * s)), joint="curve")

    def elipse(self, cx, cy, rx, ry=None, fill=None, borde=None, ancho=1):
        s, ry = self.ss, (ry if ry is not None else rx)
        self.d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=fill, outline=borde,
                       width=ancho * s if borde else 0)

    def poligono(self, pts, fill=None, borde=None):
        s = self.ss
        self.d.polygon([(px * s, py * s) for px, py in pts], fill=fill, outline=borde)

    def arco(self, cx, cy, r, a0, a1, color, ancho=8):
        """Arco de circunferencia (grados, 0° = derecha, sentido horario)."""
        s = self.ss
        self.d.arc([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], a0, a1, fill=color, width=ancho * s)

    # ---- texto ------------------------------------------------------------------------------------------------
    def texto(self, x, y, txt, tam, color, bold=False, ancla="la"):
        """ancla PIL: l/m/r (horizontal) + a/m/s (vertical). Ej.: 'la' arriba-izq, 'mm' centro, 'rs' base-der."""
        self.d.text((x * self.ss, y * self.ss), str(txt), font=_fuente(tam * self.ss, bold), fill=color, anchor=ancla)

    def ancho_texto(self, txt, tam, bold=False):
        return self.d.textlength(str(txt), font=_fuente(tam * self.ss, bold)) / self.ss

    # ---- imágenes ---------------------------------------------------------------------------------------------
    def pegar(self, ruta, x, y, w=None, h=None):
        img = Image.open(ruta).convert("RGBA")
        if w or h:
            k = (w / img.width) if w else (h / img.height)
            img = img.resize((round(img.width * k * self.ss), round(img.height * k * self.ss)), Image.LANCZOS)
        else:
            img = img.resize((img.width * self.ss, img.height * self.ss), Image.LANCZOS)
        self.im.paste(img, (x * self.ss, y * self.ss), img)

    # ---- gráficos de apoyo --------------------------------------------------------------------------------------
    def barras(self, x, y, w, h, valores, color, fondo_eje=None, sep=0.35, max_v=None, etiquetas=None, tam=10,
               color_txt="#9FB1C9", color_lista=None):
        """Columnas verticales. valores: lista de números. color_lista: color por barra (opcional)."""
        n = len(valores)
        mx = max_v or (max(valores) or 1)
        ancho = w / n
        bw = ancho * (1 - sep)
        for i, v in enumerate(valores):
            bh = h * (v / mx)
            bx = x + i * ancho + (ancho - bw) / 2
            self.caja(bx, y + h - bh, bw, bh, fill=(color_lista[i] if color_lista else color), r=min(3, bw / 3))
            if etiquetas:
                self.texto(bx + bw / 2, y + h + 4, etiquetas[i], tam, color_txt, ancla="ma")

    def serie(self, x, y, w, h, valores, color, min_v=None, max_v=None, ancho=2, relleno=None):
        """Línea de una serie dentro de la caja (x, y, w, h). relleno: color RGBA opcional bajo la línea."""
        mn = min(valores) if min_v is None else min_v
        mx = max(valores) if max_v is None else max_v
        rng = (mx - mn) or 1
        n = len(valores)
        pts = [(x + w * i / max(1, n - 1), y + h - h * (v - mn) / rng) for i, v in enumerate(valores)]
        if relleno:
            self.poligono(pts + [(x + w, y + h), (x, y + h)], fill=relleno)
        self.linea(pts, color, ancho)

    def dona(self, cx, cy, r, partes, ancho=14, fondo="#223552"):
        """partes: [(valor, color)...]; empieza a las 12 h y sigue el sentido horario."""
        total = sum(v for v, _ in partes) or 1
        self.arco(cx, cy, r, 0, 360, fondo, ancho)
        ang = -90.0
        for v, col in partes:
            fin = ang + 360 * v / total
            self.arco(cx, cy, r, ang, fin, col, ancho)
            ang = fin

    def guardar(self, ruta, leyenda=None, color_leyenda="#9FB1C9", cuantizar=False):
        """Reduce a tamaño final y guarda. leyenda: texto pequeño al pie derecho (p. ej. 'Render con datos sintéticos').
        cuantizar=True reduce a una paleta adaptativa de 256 colores (PNG ~3× más liviano; míralo antes de conservarlo)."""
        if leyenda:
            self.texto(self.w - 16, self.h - 8, leyenda, 11, color_leyenda, ancla="rs")
        out = self.im.resize((self.w, self.h), Image.LANCZOS) if self.ss != 1 else self.im
        if cuantizar:
            out = out.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        out.save(ruta, "PNG", optimize=True)
        return ruta
