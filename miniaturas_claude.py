"""Miniaturas diseñadas por Claude: Claude escribe una página HTML con el diseño y Edge la convierte en imagen.

Usa el programa `claude` de tu PC (tu plan, sin costo extra) y Microsoft Edge, que viene con Windows.
Usa la captura del juego, el logo, la fuente Cinzel y las fotos que pongas en recursos/imagenes.
Si tu idea pide imágenes que no están (logo de World of Warcraft, arte del Warrior, un jefe…), Claude trabaja como
agente: las busca en fuentes oficiales (Blizzard, Wikimedia), las baja a la carpeta de la miniatura, las mira y arma
el diseño. Tarda un par de minutos y corre en segundo plano.
"""
import os
import re
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


PIDE_IMAGENES = re.compile(r"logo|recorte|imagen|imagenes|foto|personaje|arte|oficial|render|warrior|guerrero|pala|"
                           r"paladin|hunter|cazador|rogue|picaro|priest|sacerdote|mago|mage|lock|brujo|druida|druid|"
                           r"chaman|shaman|jefe|boss|ragnaros|onyxia|zona|montura|dragon", re.I)


def necesita_agente(idea):
    return bool(config.MINIATURA_AGENTE and idea and PIDE_IMAGENES.search(idea))


AGENTE = """
Trabajás como agente, en esta carpeta y solo en esta carpeta:
1. Si la idea pide imágenes que no están en la lista (logo oficial de World of Warcraft, arte de una clase como el
   Warrior, un jefe, una zona…), buscalas con WebSearch/WebFetch y bajalas acá con curl, por ejemplo:
   curl -sL -o logo_wow.png "https://…". Solo fuentes oficiales de Blizzard (blizzard.com, worldofwarcraft.blizzard.com,
   news.blizzard.com) o Wikimedia Commons para logos. Nada de fan art de otros artistas ni imágenes con marca de agua.
   Máximo 4 imágenes, PNG, JPG o WEBP. Abrí cada una con Read para comprobar que es la imagen correcta y se ve bien;
   si una no sirve, buscá otra. Preferí PNG con fondo transparente para los recortes.
2. Escribí el diseño completo en el archivo diseno.html (herramienta Write), con rutas relativas a las imágenes de
   esta carpeta. No cargues nada de internet desde el HTML.
3. No toques nada fuera de esta carpeta. Al terminar respondé solo: LISTO"""


def _con_agente(pedido, carpeta):
    from overlays import buscar_claude
    exe = buscar_claude()
    if not exe:
        raise RuntimeError("no está el programa claude en esta PC")
    comando = [exe, "-p", "--max-turns", "40"] + (["--model", config.CLAUDE_MODELO] if config.CLAUDE_MODELO else [])
    comando += ["--allowedTools", "WebSearch", "WebFetch", "Read", "Write", "Edit", "Bash(curl:*)", "Bash(curl.exe:*)"]
    archivo = carpeta / "diseno.html"
    archivo.unlink(missing_ok=True)
    r = subprocess.run(comando, input=pedido, capture_output=True, text=True, encoding="utf-8",
                       timeout=config.MINIATURA_ESPERA, cwd=str(carpeta))
    (carpeta / "agente.log").write_text((r.stdout or "") + "\n--- errores ---\n" + (r.stderr or ""), encoding="utf-8")
    if not archivo.exists() or "<html" not in archivo.read_text(encoding="utf-8", errors="ignore").lower():
        raise RuntimeError(f"el agente no dejó el diseño ({r.returncode}): {(r.stderr or r.stdout or '')[:200]}")
    bajadas = [f.name for f in carpeta.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    print(f"[miniatura] El agente terminó. Imágenes en la carpeta: {', '.join(bajadas)}")
    return archivo


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
- El logo y los textos nunca se tocan ni se superponen, tampoco en vertical: dejá aire entre ellos.
- No agregues textos, fechas ni datos que no estén arriba.
Respondé solo con el HTML."""
    if necesita_agente(idea):
        try:
            return _con_agente(pedido.replace("Respondé solo con el HTML.", AGENTE)
                               .replace("- Si la idea pide algo que no está en los archivos", "- Si aun así falta algo"), carpeta)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] El agente no pudo ({e}); la diseño con lo que hay en la carpeta.")
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
