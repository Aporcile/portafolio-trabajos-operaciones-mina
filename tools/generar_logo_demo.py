# -*- coding: utf-8 -*-
"""Genera los logos ficticios de "Minera Demo" (marca inventada, sin relación con ninguna empresa real).

Salida en assets/:
  logo_minera_demo_blanco.png   texto blanco sobre transparente (para fondos oscuros)
  logo_minera_demo_color.png    texto en azul medianoche sobre transparente (para fondos claros)
  icono_minera_demo.png         símbolo cuadrado 256x256

Uso:  python tools/generar_logo_demo.py
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "assets"
AZUL = (27, 42, 65, 255)       # #1B2A41 azul medianoche
CIELO = (79, 157, 222, 255)    # #4F9DDE azul cielo
BLANCO = (255, 255, 255, 255)


def fuente(nombre, tam):
    """Busca la fuente por nombre en las carpetas de fuentes del sistema (Windows o Linux)."""
    carpetas = [Path(os.environ.get("WINDIR", "")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu")]
    for carpeta in carpetas:
        try:
            return ImageFont.truetype(str(carpeta / nombre), tam)
        except OSError:
            continue
    return ImageFont.load_default()


def simbolo(d, x, y, s, relleno, acento):
    """Dos picos (rajo / montaña) dentro de una caja s x s."""
    d.polygon([(x, y + s), (x + s * 0.42, y), (x + s * 0.72, y + s)], fill=relleno)
    d.polygon([(x + s * 0.40, y + s), (x + s * 0.72, y + s * 0.34), (x + s, y + s)], fill=acento)


def logo(nombre, texto_color, acento):
    w, h = 1200, 320
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    simbolo(d, 20, 40, 240, texto_color, acento)
    ancho_max = w - 300 - 30
    tam = 150
    while tam > 40 and d.textlength("Minera Demo", font=fuente("segoeuib.ttf", tam)) > ancho_max:
        tam -= 4
    d.text((300, 40 + (150 - tam) // 3), "Minera Demo", font=fuente("segoeuib.ttf", tam), fill=texto_color)
    d.text((306, 215), "Operaciones Mina · datos simulados", font=fuente("segoeui.ttf", 52), fill=acento)
    im.save(SALIDA / nombre, optimize=True)


def icono():
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 255, 255), radius=48, fill=AZUL)
    simbolo(d, 48, 56, 160, BLANCO, CIELO)
    im.save(SALIDA / "icono_minera_demo.png", optimize=True)


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    logo("logo_minera_demo_blanco.png", BLANCO, CIELO)
    logo("logo_minera_demo_color.png", AZUL, CIELO)
    icono()
    print("Logos ficticios generados en", SALIDA)
