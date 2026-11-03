"""Aprende el estilo de tus miniaturas favoritas. Se corre una vez, y de nuevo cuando agregues ejemplos.

1. Copia en chico (768 px) tus ejemplos de MINIATURAS_EJEMPLOS a recursos/referencias.
   Tus originales no se tocan.
2. Un Claude (Opus) mira esas copias y escribe la guía recursos/estilo_miniaturas.md.
   No tiene internet y solo puede leer esa carpeta.
3. Cada miniatura nueva usa la guía y mira 3 o 4 de esos ejemplos (los que más se parecen a lo que pediste).

Uso:  python aprender_estilo.py                -> la carpeta de MINIATURAS_EJEMPLOS (.env)
      python aprender_estilo.py "D:\\otra\\carpeta"
"""
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

import config
from overlays import SIN_HERRAMIENTAS, SOLO_ESTO, buscar_claude

EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")
MAXIMO = 16

PEDIDO = """En esta carpeta hay {n} miniaturas de YouTube que hizo Mr. H, un streamer de World of Warcraft (hermandad
The H's). Le encantan. Archivos: {lista}

Abrí CADA una con Read y miralas bien. Después escribí una guía de estilo para el diseñador que va a hacer sus
miniaturas nuevas (en HTML y CSS, con fotos y capturas que ya existen, sin generar ilustraciones). Que se pueda
seguir al pie de la letra. En español, máximo 45 líneas, sin introducción:
- Composición: dónde va el personaje o la cara y qué tamaño tiene, dónde va el texto y dónde el logo.
- Texto: cuántas palabras, tamaño, tipo de letra (gruesa, fina, biselada), colores, borde y sombra, palabra de acento.
- Color y luz: paletas, contrastes, brillos, fuego o magia, fondos.
- Efectos que se repiten: chispas, rayos, desenfoque, viñeta.
- Qué NO hacer (lo que nunca aparece en sus miniaturas).
- Si hay tipos distintos (directo, pesca, raid, novedades), una línea por tipo con lo que cambia.
Respondé solo con la guía."""


def copiar(origen, destino):
    """Copias en chico de los ejemplos más nuevos. Devuelve los nombres."""
    destino.mkdir(parents=True, exist_ok=True)
    fotos = sorted((f for f in origen.rglob("*") if f.suffix.lower() in EXTENSIONES),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:MAXIMO]
    nombres = []
    for f in fotos:
        try:
            with Image.open(f) as im:
                im = im.convert("RGB")
                im.thumbnail((768, 768))
                nombre = (re.sub(r"[^\w-]+", "_", f.stem).strip("_")[:60] or "ejemplo") + ".jpg"
                im.save(destino / nombre, "JPEG", quality=86)
                nombres.append(nombre)
        except Exception as e:  # noqa: BLE001
            print(f"  (no pude abrir {f.name}: {e})")
    return nombres


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    origen = Path(sys.argv[1] if len(sys.argv) > 1 else config.MINIATURAS_EJEMPLOS)
    if not origen.is_dir():
        print(f"No encuentro la carpeta {origen}. Poné la ruta en MINIATURAS_EJEMPLOS (.env) o pasala al correrlo.")
        return 1
    nombres = copiar(origen, config.REFERENCIAS)
    if not nombres:
        print(f"No hay imágenes (jpg, png o webp) en {origen}.")
        return 1
    print(f"Copié {len(nombres)} ejemplos a {config.REFERENCIAS}. Ahora Claude los mira (unos minutos)…")
    exe = buscar_claude()
    if not exe:
        print("No está el programa claude en esta PC.")
        return 1
    comando = [exe, "-p", "--max-turns", str(len(nombres) + 6), "--model", config.CLAUDE_MODELO or "opus"] + SOLO_ESTO
    comando += ["--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h != "Read"] + ["--allowedTools", "Read(./**)"]
    r = subprocess.run(comando, input=PEDIDO.format(n=len(nombres), lista=", ".join(nombres)), capture_output=True,
                       text=True, encoding="utf-8", timeout=900, cwd=str(config.REFERENCIAS))
    guia = (r.stdout or "").strip()
    if r.returncode != 0 or len(guia) < 200:
        print(f"Claude no devolvió la guía ({r.returncode}): {(r.stderr or guia)[:300]}")
        return 1
    config.ESTILO_MINIATURAS.write_text(guia + "\n", encoding="utf-8")
    print(f"\nListo: guía en {config.ESTILO_MINIATURAS}\n")
    print(guia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
