"""Miniaturas diseñadas por Claude: Claude escribe una página HTML con el diseño y Edge la convierte en imagen.

Usa el programa `claude` de tu PC (tu plan, sin costo extra) y Microsoft Edge, que viene con Windows.
Usa la captura del juego, el logo, la fuente Cinzel y las fotos que pongas en recursos/imagenes.
Si tu idea pide imágenes que no están (logo de World of Warcraft, arte del Warrior, un jefe…), un Claude las busca
en cualquier página de WoW SIN acceso a tus archivos, el programa las baja (nunca de tu red local) y comprueba que
sean imágenes, y otro Claude SIN internet arma el diseño. Así nada de lo que lea en internet puede tocar tus claves.
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


def _preparar(carpeta, extras=()):
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
    archivos += list(extras)
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


# Sitios donde suele estar el mejor arte de WoW (se sugieren primero, pero sirve cualquier página pública)
SITIOS_SUGERIDOS = ("warcraft.wiki.gg", "wowhead.com (wow.zamimg.com)", "blizzard.com", "worldofwarcraft.blizzard.com",
                    "wowpedia (static.wikia.nocookie.net)", "upload.wikimedia.org", "wallpapers y artstation")
MAX_BYTES = 8 * 1024 * 1024


def _sitio_ok(url):
    """Cualquier página pública por https. Nunca la red de tu casa ni tu PC (router, 192.168…, localhost)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    u = urlparse(url or "")
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not host or host == "localhost" or host.endswith((".local", ".lan", ".home")):
        return False
    try:
        direcciones = {i[4][0] for i in socket.getaddrinfo(host, 443)}
    except OSError:
        return False
    for d in direcciones:
        ip = ipaddress.ip_address(d.split("%")[0])
        if not ip.is_global:
            return False
    return True


def recortar(ruta):
    """Saca el fondo de un personaje (necesita rembg: pip install rembg). Devuelve la ruta nueva o None."""
    try:
        from rembg import remove
    except ImportError:
        return None
    try:
        with Image.open(ruta) as im:
            sin_fondo = remove(im.convert("RGBA"))
        caja = sin_fondo.getbbox()
        if not caja:
            return None
        nueva = ruta.with_name(ruta.stem + "_recorte.png")
        sin_fondo.crop(caja).save(nueva)
        return nueva
    except Exception as e:  # noqa: BLE001
        print(f"[miniatura] No pude recortar {ruta.name}: {e}")
        return None


def buscar_imagenes(idea, carpeta):
    """Claude busca en la web (sin acceso a archivos ni a la PC) y el programa baja y revisa las imágenes.

    Separado en dos para que nada de lo que lea en internet pueda tocar tus claves: el que busca no puede abrir
    archivos ni ejecutar nada, y lo que baja Python viene de páginas públicas (nunca tu red local) y tiene que ser
    una imagen de verdad.
    """
    import io
    import json
    import tempfile

    import requests

    from overlays import buscar_claude
    exe = buscar_claude()
    if not exe:
        raise RuntimeError("no está el programa claude en esta PC")
    pedido = f"""Buscá imágenes para la miniatura de un directo de World of Warcraft. Idea: {idea}
Usá WebSearch y WebFetch para encontrar URLs DIRECTAS de archivos de imagen (png, jpg o webp) de cualquier página,
mientras sea de World of Warcraft y encaje con lo que pide la idea (arte, renders, logos, capturas, wallpapers).
Suele haber buen arte en: {", ".join(SITIOS_SUGERIDOS)}. Elegí imágenes grandes, nítidas y sin marca de agua.
En las wikis las páginas de clases, razas, jefes y logos tienen el arte: abrí la página con WebFetch y sacá la URL
del archivo. Para un personaje o clase, preferí un
render o arte con fondo transparente (PNG). Si piden el logo, buscá el logo completo de World of Warcraft (con letras),
no solo el ícono. Máximo 4. Respondé SOLO con JSON, sin explicaciones:
[{{"nombre": "logo_wow", "url": "https://…", "que": "logo de World of Warcraft", "recortar": false}}]
Poné "recortar": true si es un personaje o criatura que NO tiene fondo transparente (hay que recortarlo)."""
    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO
    comando = [exe, "-p", "--max-turns", "20", "--model", config.CLAUDE_MODELO or "sonnet"] + SOLO_ESTO
    comando += ["--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h not in ("WebFetch", "WebSearch")]
    comando += ["--allowedTools", "WebSearch", "WebFetch"]
    vacia = tempfile.mkdtemp(prefix="cerebro_busca_")          # carpeta vacía: no hay nada que leer
    r = subprocess.run(comando, input=pedido, capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=vacia)
    log = [f"--- búsqueda ({r.returncode}) ---", r.stdout or "", r.stderr or ""]
    m = re.search(r"\[.*\]", r.stdout or "", re.S)
    try:
        candidatas = json.loads(m.group(0)) if m else []
    except ValueError:
        candidatas = []
    bajadas = []
    for c in candidatas[:6]:
        url, nombre = str(c.get("url") or ""), re.sub(r"[^a-z0-9_]+", "_", str(c.get("nombre") or "imagen").lower())[:30]
        if not _sitio_ok(url):
            log.append(f"descarto (no es una página pública por https): {url}")
            continue
        try:
            resp = requests.get(url, timeout=20, stream=True, headers={"User-Agent": "ElCerebro/1.0"})
            resp.raise_for_status()
            if not _sitio_ok(resp.url):                       # si redirigió a otro sitio, no sirve
                raise ValueError(f"redirigió a una dirección no permitida: {resp.url}")
            datos = resp.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(datos) > MAX_BYTES:
                raise ValueError("imagen demasiado grande")
            with Image.open(io.BytesIO(datos)) as im:
                im.load()
                img = im.convert("RGBA")
            if min(img.size) < 120:
                raise ValueError(f"muy chica ({img.width}x{img.height})")
            archivo = f"web_{nombre}.png"
            img.save(carpeta / archivo)
            que = re.sub(r"[^\w áéíóúñÁÉÍÓÚÑ,.()-]", "", str(c.get("que") or nombre))[:80]   # solo una descripción corta
            log.append(f"bajada: {archivo} <- {url}")
            if c.get("recortar") is True:
                recorte = recortar(carpeta / archivo)
                if recorte:
                    archivo, que = recorte.name, que + ", recortado sin fondo"
                    log.append(f"recortada: {archivo}")
            bajadas.append((archivo, f"{que} (imagen de {url.split('/')[2]})"))
        except Exception as e:  # noqa: BLE001
            log.append(f"no sirvió {url}: {e}")
        if len(bajadas) >= 4:
            break
    (carpeta / "agente.log").write_text("\n".join(log), encoding="utf-8")
    print(f"[miniatura] Imágenes bajadas: {', '.join(a for a, _ in bajadas) or 'ninguna'}")
    return bajadas


def disenar(carpeta, titulo, subtitulo, idea):
    from overlays import pedir_a_claude
    extras = []
    if necesita_agente(idea):
        try:
            extras = buscar_imagenes(idea, carpeta)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude buscar imágenes ({e}); la diseño con lo que hay.")
    pedido = f"""Diseñá la miniatura de un directo de Twitch/Kick/YouTube como UNA página HTML.
Título (texto grande, EXACTO): {titulo}
Subtítulo (texto chico, EXACTO; si está vacío no pongas nada): {subtitulo}
Idea de Mr. H: {idea or "ninguna en especial: elegí la composición que mejor venda el título"}

{ESTILO}

Archivos que podés usar (están en la misma carpeta que el HTML, usalos con rutas relativas):
{_preparar(carpeta, extras)}

Reglas:
- Un solo archivo HTML con el CSS adentro, sin JavaScript que dependa de internet y sin cargar nada de internet.
- La misma página se va a sacar en 1280x720 (horizontal) y en 1080x1920 (vertical, para TikTok): ocupá siempre el 100%
  de la ventana (width:100vw; height:100vh; sin bordes blancos ni barras) y adaptá la composición con
  @media (orientation: portrait).
- Si la idea pide algo que no está en los archivos (por ejemplo un personaje sin foto), resolvelo con diseño
  (siluetas, formas, texto, efectos CSS) usando la captura; no inventes rutas de imágenes.
- El logo y los textos nunca se tocan ni se superponen, tampoco en vertical: dejá aire entre ellos.
- Los logos y los textos NUNCA tapan la cara ni la cabeza de un personaje: ubicalos en otra zona.
- Para el borde de las letras NO uses -webkit-text-stroke (con la fuente Cinzel dibuja rayas dentro de las letras):
  usá text-shadow (varias sombras) o paint-order: stroke fill.
- Si una imagen tiene otras figuras o restos en los bordes, recortala con object-fit/object-position, overflow:hidden
  o una máscara (mask-image con degradé) para que se vea solo lo importante.
- Ninguna letra puede quedar cortada ni salirse de la pantalla, sobre todo en vertical (1080 de ancho): ahí el título
  va en 2 o 3 líneas, con tamaño en vw (font-size: min(13vw, …)), white-space: normal y sin cortar palabras.
  Dejá al menos 5% de margen a los costados.
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
                    "--host-resolver-rules=MAP * ~NOTFOUND",          # el diseño no sale a internet
                    f"--force-device-scale-factor={escala}", "--virtual-time-budget=5000",
                    f"--screenshot={salida}", html.as_uri()], capture_output=True, timeout=90)
    if not salida.exists():
        raise RuntimeError("Edge no sacó la imagen")
    with Image.open(salida) as im:
        img = im.convert("RGB")
    if img.size != (round(w * escala), round(h * escala)):
        img = img.resize((round(w * escala), round(h * escala)), Image.LANCZOS)
    return img


REVISION = """Sos el revisor de una miniatura de YouTube y TikTok. Abrí con Read las dos imágenes de esta carpeta:
_rev_youtube.png (1280x720) y _rev_tiktok.png (1080x1920). Son la foto de este HTML:

{html}

Revisá con ojo de diseñador: ¿algún logo o texto tapa la cara o la cabeza de un personaje? ¿hay letras cortadas o
que se salen? ¿elementos pegados o superpuestos? ¿restos de otras figuras en los bordes? ¿letras con rayas raras?
¿se lee bien en chico? Si está todo bien respondé solo: OK
Si no, respondé SOLO el HTML completo corregido (mismos textos y mismas imágenes, solo arreglá los problemas)."""


def revisar(carpeta, html):
    """Un Claude mira cómo quedó (solo puede leer esta carpeta, sin internet) y corrige si algo se tapa o se corta."""
    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO, buscar_claude
    exe = buscar_claude()
    if not exe:
        return False
    foto(html, carpeta / "_rev_youtube.png", 1280, 720)
    foto(html, carpeta / "_rev_tiktok.png", 1080, 1920)
    comando = [exe, "-p", "--max-turns", "6"] + SOLO_ESTO + (["--model", config.CLAUDE_MODELO] if config.CLAUDE_MODELO else [])
    comando += ["--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h != "Read"] + ["--allowedTools", "Read"]
    try:
        r = subprocess.run(comando, input=REVISION.format(html=html.read_text(encoding="utf-8")), capture_output=True,
                           text=True, encoding="utf-8", timeout=240, cwd=str(carpeta))
    finally:
        for f in ("_rev_youtube.png", "_rev_tiktok.png"):
            (carpeta / f).unlink(missing_ok=True)
    m = re.search(r"<!doctype html.*?</html>|<html.*?</html>", r.stdout or "", re.S | re.I)
    if not m:
        print("[miniatura] Revisión: está bien.")
        return False
    html.write_text(m.group(0), encoding="utf-8")
    print("[miniatura] Revisión: corregí el diseño.")
    return True


def crear(carpeta, titulo, subtitulo="", idea=""):
    html = disenar(carpeta, titulo, subtitulo, idea)
    if config.MINIATURA_REVISAR:
        try:
            revisar(carpeta, html)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude revisarla ({e}); queda la primera versión.")
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
