"""Miniaturas diseñadas por Claude: Claude escribe una página HTML con el diseño y Edge la convierte en imagen.

Usa el programa `claude` de tu PC (tu plan, sin costo extra) y Microsoft Edge, que viene con Windows.
Claude solo puede usar las imágenes de la carpeta de la miniatura: la captura del juego, el logo, la fuente Cinzel
y las fotos que pongas en recursos/imagenes (por ejemplo paladin.png, elfa.png). No inventa ni descarga imágenes.
"""
import os
import shutil
import subprocess

from PIL import Image

import config
from miniaturas import FORMATOS

ESTILO = """Estilo de la hermandad The H's (World of Warcraft Forever): dorado #E8C468 / #F5D98B sobre negros y marrones muy
oscuros, tipografía Cinzel (archivo Cinzel.ttf de la carpeta) para el título, logo de la guild con brillo dorado,
contraste alto, texto enorme y legible en chico (es una miniatura de YouTube), composición limpia y épica."""


def edge():
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        ruta = os.path.join(base or "", "Microsoft", "Edge", "Application", "msedge.exe")
        if base and os.path.exists(ruta):
            return ruta
    return shutil.which("msedge") or shutil.which("chromium") or shutil.which("google-chrome")


def _preparar(carpeta):
    """Copia a la carpeta lo que Claude puede usar y devuelve la lista para el pedido."""
    lista = []
    for origen, nombre in ((config.RECURSOS / "logo.jpg", "logo.jpg"), (config.RECURSOS / "Cinzel.ttf", "Cinzel.ttf")):
        if origen.exists():
            shutil.copy(origen, carpeta / nombre)
    imagenes = config.RECURSOS / "imagenes"
    archivos = [("captura.png", "captura del juego en OBS (o el fondo de la guild si el juego estaba cerrado)"),
                ("logo.jpg", "logo de la guild (cuadrado, fondo oscuro: usalo recortado en círculo)")]
    if imagenes.is_dir():
        for f in sorted(imagenes.iterdir()):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                shutil.copy(f, carpeta / f.name)
                archivos.append((f.name, f"foto de recursos/imagenes ({f.stem.replace('_', ' ')})"))
    for nombre, que in archivos:
        try:
            with Image.open(carpeta / nombre) as im:
                lista.append(f"- {nombre}: {que}, {im.width}x{im.height}")
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(lista)


def disenar(carpeta, titulo, subtitulo, idea):
    from overlays import pedir_a_claude
    pedido = f"""Diseñá la miniatura de un directo de Twitch/Kick/YouTube como UNA página HTML.
Título (texto grande, EXACTO): {titulo}
Subtítulo (texto chico, EXACTO; si está vacío no pongas nada): {subtitulo}
Idea de Mr. H: {idea or "ninguna en especial: elegí la composición que mejor venda el título"}

{ESTILO}

Archivos que podés usar (están en la misma carpeta que el HTML, usalos con rutas relativas):
{_preparar(carpeta)}

Reglas:
- Un solo archivo HTML con el CSS adentro, sin JavaScript que dependa de internet y sin cargar nada de internet.
- La misma página se va a sacar en 1280x720 (horizontal) y en 1080x1920 (vertical, para TikTok): ocupá siempre el 100%
  de la ventana (width:100vw; height:100vh; sin bordes blancos ni barras) y adaptá la composición con
  @media (orientation: portrait).
- Si la idea pide algo que no está en los archivos (por ejemplo un personaje sin foto), resolvelo con diseño
  (siluetas, formas, texto, efectos CSS) usando la captura; no inventes rutas de imágenes.
- No agregues textos, fechas ni datos que no estén arriba.
Respondé solo con el HTML."""
    archivo = carpeta / "diseno.html"
    archivo.write_text(pedir_a_claude(pedido, carpeta), encoding="utf-8")
    return archivo


def foto(html, salida, w, h, escala=1.0):
    navegador = edge()
    if not navegador:
        raise RuntimeError("no encontré Microsoft Edge para convertir el diseño en imagen")
    perfil = config.DATA / "edge_miniaturas"
    perfil.mkdir(parents=True, exist_ok=True)
    subprocess.run([navegador, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    "--mute-audio", f"--user-data-dir={perfil}", f"--window-size={w},{h}",
                    f"--force-device-scale-factor={escala}", "--virtual-time-budget=5000",
                    f"--screenshot={salida}", html.as_uri()], capture_output=True, timeout=90)
    if not salida.exists():
        raise RuntimeError("Edge no sacó la imagen")
    with Image.open(salida) as im:
        img = im.convert("RGB")
    if img.size != (round(w * escala), round(h * escala)):
        img = img.resize((round(w * escala), round(h * escala)), Image.LANCZOS)
    return img


def crear(carpeta, titulo, subtitulo="", idea=""):
    html = disenar(carpeta, titulo, subtitulo, idea)
    rutas = {}
    for nombre, (w, h, ext) in FORMATOS.items():
        escala = 1.5 if (w, h) == (1920, 1080) else 1.0          # Kick: el diseño de 1280x720 en alta
        base_w, base_h = (1280, 720) if escala == 1.5 else (w, h)
        img = foto(html, carpeta / f"_{nombre}.png", base_w, base_h, escala)
        ruta = carpeta / f"{nombre}.{ext}"
        if ext == "jpg":
            img.save(ruta, "JPEG", quality=92, optimize=True)
        else:
            img.save(ruta, "PNG", optimize=True)
        (carpeta / f"_{nombre}.png").unlink(missing_ok=True)
        rutas[nombre] = ruta
    return rutas
