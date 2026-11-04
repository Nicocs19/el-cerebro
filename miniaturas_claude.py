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
oscuros, tipografía Cinzel (archivo Cinzel.ttf de la carpeta) para el título, contraste alto, texto enorme y legible en chico (es una miniatura de YouTube), composición limpia y épica.
Lo que hace que sus miniaturas funcionen: UNA idea fuerte; personaje o cara expresiva GRANDE (60% o más de la imagen);
título de 2 a 4 palabras, enorme, dorado biselado con borde oscuro y a veces UNA palabra de acento en otro color
(rojo fuego, verde vil, azul arcano); color fuerte con luz de fuego, magia o contraluz; fondo de escena con
desenfoque; chispas, brasas o rayos sutiles. Nada de marcos dobles ni cajas apagadas. El logo de la hermandad NO va
(sus miniaturas no lo llevan), salvo que la idea lo pida; el logo del juego sí, si está en los archivos."""


def edge():
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        ruta = os.path.join(base or "", "Microsoft", "Edge", "Application", "msedge.exe")
        if base and os.path.exists(ruta):
            return ruta
    return shutil.which("msedge") or shutil.which("chromium") or shutil.which("google-chrome")


LOGO_JUEGO = "logo_wow_forever.png"     # en recursos/: el logo OFICIAL de World of Warcraft: Forever (el juego de Mr. H)


def logo_fijo():
    """El logo oficial de WoW Forever guardado en recursos (lo pone Nicolas o queda el que aprobó con «dale»)."""
    ruta = config.RECURSOS / LOGO_JUEGO
    return ruta if ruta.exists() else None


def _preparar(carpeta, extras=()):
    """Copia a la carpeta lo que Claude puede usar y devuelve la lista para el pedido."""
    lista = []
    for origen, nombre in ((config.RECURSOS / "logo.jpg", "logo.jpg"), (config.RECURSOS / "Cinzel.ttf", "Cinzel.ttf"),
                           (config.RECURSOS / LOGO_JUEGO, LOGO_JUEGO)):
        if origen.exists():
            shutil.copy(origen, carpeta / nombre)
    imagenes = config.RECURSOS / "imagenes"
    archivos = [("captura.png", "captura del juego en OBS (o el fondo de la guild si el juego estaba cerrado)"),
                ("logo.jpg", "logo de la guild (cuadrado, fondo oscuro; solo si la idea lo pide, recortado en círculo)"),
                (LOGO_JUEGO, "logo OFICIAL de World of Warcraft: Forever, el juego de Mr. H. Si la idea pide el logo de "
                             "WoW o del juego, es ESTE (no otro)")]
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


LOGO_DEL_JUEGO = re.compile(r"\b(el |un |los )?logos?\b(\s+(oficial|nuevo|original))?(\s+(del?|de la)\s+)?"
                            r"(\s*(juego|wow|world of warcraft|warcraft))?(\s*:?\s*forever)?(\s*,?\s*(el |la )?(oficial|original))?",
                            re.I)


def necesita_agente(idea):
    if not (config.MINIATURA_AGENTE and idea):
        return False
    if logo_fijo():                       # el logo del juego ya está: solo se busca si pide otras imágenes
        idea = LOGO_DEL_JUEGO.sub(" ", idea)
    return bool(PIDE_IMAGENES.search(idea))


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


def tiene_transparencia(img):
    """True si la imagen ya viene sin fondo (al menos 8% de píxeles transparentes): no hace falta recortarla."""
    if img.mode != "RGBA":
        return False
    alfa = img.getchannel("A").resize((128, 128))
    transparentes = sum(alfa.histogram()[:20])
    return transparentes >= 0.08 * 128 * 128


def _limpiar(sin_fondo):
    """Saca los restos del recorte: lo semitransparente y las manchas sueltas lejos del personaje."""
    alfa = sin_fondo.getchannel("A").point(lambda a: 0 if a < 60 else a)
    try:                                        # si está numpy/scipy (vienen con rembg): queda solo la figura principal
        import numpy as np
        from scipy import ndimage
        a = np.array(alfa)
        partes, n = ndimage.label(a > 0)
        if n > 1:
            tamanos = ndimage.sum(np.ones_like(a), partes, range(1, n + 1))
            grande = tamanos.max()
            quedan = [i + 1 for i, t in enumerate(tamanos) if t >= 0.15 * grande]   # la figura y partes grandes (arma)
            a[~np.isin(partes, quedan)] = 0
            alfa = Image.fromarray(a)
    except ImportError:
        pass
    sin_fondo.putalpha(alfa)
    return sin_fondo


def recortar(ruta):
    """Saca el fondo de un personaje (necesita rembg: pip install rembg). Devuelve la ruta nueva o None.

    Si la imagen ya es un PNG sin fondo, no la toca (solo le recorta el borde vacío).
    """
    try:
        with Image.open(ruta) as im:
            img = im.convert("RGBA")
        if tiene_transparencia(img):
            sin_fondo = img
        else:
            try:
                from rembg import remove
            except ImportError:
                return None
            try:
                sin_fondo = remove(img, post_process_mask=True)
            except TypeError:
                sin_fondo = remove(img)
            sin_fondo = _limpiar(sin_fondo)
        caja = sin_fondo.getbbox()
        if not caja or (caja[2] - caja[0]) * (caja[3] - caja[1]) < 0.03 * img.width * img.height:
            return None                         # no quedó casi nada: el recorte no sirve
        nueva = ruta.with_name(ruta.stem + "_recorte.png")
        sin_fondo.crop(caja).save(nueva)
        return nueva
    except Exception as e:  # noqa: BLE001
        print(f"[miniatura] No pude recortar {ruta.name}: {e}")
        return None


LOGO_A_BUSCAR = """Si piden el logo de WoW o del juego, el que va es el logo OFICIAL de "World of Warcraft: Forever" (el juego que
juega Mr. H; Blizzard lo anunció en la BlizzCon 2026): las letras de World of Warcraft con la palabra FOREVER.
Buscalo en warcraft.wiki.gg, worldofwarcraft.blizzard.com, blizzard.com o en las noticias del anuncio, y antes de
elegirlo fijate que sea ese (el nombre del archivo, el texto de la página): que diga "Forever". Preferí un PNG grande
con fondo transparente. No sirven: el logo clásico sin Forever, el de otra expansión (Midnight, The War Within,
Dragonflight…), solo el ícono de la W ni uno hecho por fans. Solo si la idea pide el logo clásico o el de una
expansión, buscá ese. Si no encontrás el oficial de Forever, no pongas ningún logo. A ese logo ponele
"nombre": "logo_wow_forever"."""


def buscar_imagenes(idea, carpeta, dicho=""):
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
    logo = ("El logo del juego (World of Warcraft: Forever) ya lo tengo: NO busques logos de WoW." if logo_fijo()
            else LOGO_A_BUSCAR)
    dijo = f"\nLo que dijo Mr. H, palabra por palabra (dictado por voz, puede tener errores): «{dicho[:600]}»" if dicho else ""
    pedido = f"""Buscá imágenes para la miniatura de un directo de World of Warcraft: Forever. Idea: {idea}{dijo}
Usá WebSearch y WebFetch para encontrar URLs DIRECTAS de archivos de imagen (png, jpg o webp) de cualquier página,
mientras sea de World of Warcraft y encaje con lo que pide la idea (arte, renders, logos, capturas, wallpapers).
Suele haber buen arte en: {", ".join(SITIOS_SUGERIDOS)}. Elegí imágenes grandes, nítidas y sin marca de agua.
En las wikis las páginas de clases, razas, jefes y logos tienen el arte: abrí la página con WebFetch y sacá la URL
del archivo.
Para un personaje o clase lo mejor es un RENDER de UN SOLO personaje, de cuerpo entero o medio cuerpo, en PNG con
fondo transparente (buscá cosas como "warrior render png", "transparent", arte de personaje recortado). Si no hay,
uno solo sobre fondo liso. Evitá escenas con varios personajes, paisajes detrás o el personaje chiquito.
{logo}
Máximo 4 (podés dar 2 opciones del personaje). Respondé SOLO con JSON, sin explicaciones:
[{{"nombre": "logo_wow_forever", "url": "https://…", "que": "logo oficial de World of Warcraft: Forever", "recortar": false}}]
Poné "recortar": true si es un personaje o criatura (el programa se fija solo si ya viene sin fondo)."""
    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO
    comando = [exe, "-p", "--max-turns", "20", "--model", config.CLAUDE_MODELO_REVISION or "sonnet"] + SOLO_ESTO
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
            if c.get("recortar") is True or tiene_transparencia(img):
                ya = tiene_transparencia(img)
                recorte = recortar(carpeta / archivo)
                if recorte:
                    archivo, que = recorte.name, que + (", PNG sin fondo" if ya else ", recortado sin fondo")
                    log.append(f"{'ya venía sin fondo' if ya else 'recortada'}: {archivo}")
            bajadas.append((archivo, f"{que} (imagen de {url.split('/')[2]})"))
        except Exception as e:  # noqa: BLE001
            log.append(f"no sirvió {url}: {e}")
        if len(bajadas) >= 4:
            break
    (carpeta / "agente.log").write_text("\n".join(log), encoding="utf-8")
    print(f"[miniatura] Imágenes bajadas: {', '.join(a for a, _ in bajadas) or 'ninguna'}")
    return bajadas


def _sin_tildes(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def _referencias(carpeta, titulo, idea, maximo=4):
    """Copia a la carpeta hasta 4 de tus miniaturas de ejemplo (las que más se parecen al pedido) para que las mire."""
    if not config.REFERENCIAS.is_dir():
        return []
    fotos = [f for f in config.REFERENCIAS.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    palabras = set(re.findall(r"\w{4,}", _sin_tildes(f"{titulo} {idea}")))

    def puntaje(f):
        return len(palabras & set(re.findall(r"\w{4,}", _sin_tildes(f.stem.replace("_", " "))))), f.stat().st_mtime

    elegidas = []
    for i, f in enumerate(sorted(fotos, key=puntaje, reverse=True)[:maximo], 1):
        destino = carpeta / f"referencia_{i}{f.suffix.lower()}"
        shutil.copy(f, destino)
        elegidas.append(f"- {destino.name}: «{f.stem.replace('_', ' ')}»")
    return elegidas


def disenar(carpeta, titulo, subtitulo, idea, dicho=""):
    from overlays import pedir_a_claude
    extras = []
    if necesita_agente(idea):
        try:
            extras = buscar_imagenes(idea, carpeta, dicho)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude buscar imágenes ({e}); la diseño con lo que hay.")
    guia = config.ESTILO_MINIATURAS.read_text(encoding="utf-8").strip() if config.ESTILO_MINIATURAS.exists() else ""
    estilo_propio = (f"Así son las miniaturas que más le gustan a Mr. H (sacado de sus ejemplos). Es la vara: la tuya "
                     f"tiene que estar a ese nivel o mejor:\n{guia[:4000]}\n"
                     "Si esa guía choca con las Reglas de abajo (por ejemplo -webkit-text-stroke o una letra que no está "
                     "en los archivos), mandan las Reglas: la única letra es Cinzel.ttf (gruesa: font-weight 900 y "
                     "sombras).\n\n") if guia else ""
    refs = _referencias(carpeta, titulo, idea, maximo=3)
    ejemplos = ("\nEjemplos de Mr. H (miniaturas suyas que le encantan). ANTES de diseñar, abrí cada una con Read y "
                "copiá su nivel: composición, tamaño del texto, colores, brillo y efectos. Son solo para mirar: NO las "
                "pongas en el diseño ni copies sus textos.\n" + "\n".join(refs) + "\n") if refs else ""
    pedido = f"""Diseñá la miniatura de un directo de Twitch/Kick/YouTube como UNA página HTML.
Título (texto grande, EXACTO): {titulo}
Subtítulo (texto chico, EXACTO; si está vacío no pongas nada): {subtitulo}
Idea de Mr. H: {idea or "ninguna en especial: elegí la composición que mejor venda el título"}
{f"Lo que dijo Mr. H, palabra por palabra (dictado por voz, puede tener errores; los textos de arriba mandan): «{dicho[:1200]}»" if dicho else ""}

{ESTILO}

{estilo_propio}Archivos que podés usar (están en la misma carpeta que el HTML, usalos con rutas relativas):
{_preparar(carpeta, extras)}
{ejemplos}
Objetivo: el máximo de clics (CTR). Pensá como el mejor diseñador de miniaturas de YouTube gaming:
- Se tiene que entender en 1 segundo y en chico (168x94 en el celular): UN foco, contraste brutal, nada de detalles finos.
- Jerarquía: 1) el protagonista con una emoción clara, 2) el texto, 3) el fondo. Máximo tres elementos.
- Dos colores saturados que choquen (fuego/arcano, oro/azul noche) sobre fondo oscuro; luz de contraluz o halo
  detrás del protagonista; el fondo desenfocado u oscurecido para que el primer plano salte.
- El texto, del lado opuesto a la cara y lejos de la esquina de abajo a la derecha (ahí YouTube pone la duración).
- Que se distinga de las miniaturas de al lado en la página de YouTube: bordes nítidos, recortes con contorno.

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
- El personaje principal es el protagonista: GRANDE, de 75% a 100% del alto en horizontal (puede salirse por abajo)
  y bien visible en vertical. Nada de personajes chiquitos.
- Las armas, manos y bordes del personaje no tocan las cajas de texto ni el logo: dejá aire alrededor.
- Al personaje se le pueden cortar las piernas por abajo, pero nunca la cabeza ni el arma principal.
- En vertical (TikTok) va TODO lo de la horizontal: el logo también. Arriba logo, después el título, y el personaje
  grande llenando el resto; sin huecos vacíos grandes en el medio.
- Ninguna letra puede quedar cortada ni salirse de la pantalla, sobre todo en vertical (1080 de ancho): ahí el título
  va en 2 o 3 líneas, con tamaño en vw (font-size: min(13vw, …)), white-space: normal y sin cortar palabras.
  Dejá al menos 5% de margen a los costados.
- No agregues textos, fechas ni datos que no estén arriba.
Respondé solo con el HTML."""
    archivo = carpeta / "diseno.html"
    try:
        archivo.write_text(pedir_a_claude(pedido, carpeta, mirar=bool(refs)), encoding="utf-8")
    finally:
        for f in carpeta.glob("referencia_*"):          # los ejemplos no pueden terminar dentro de la miniatura
            f.unlink(missing_ok=True)
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

Revisá con ojo de diseñador, sé exigente:
- ¿algún logo o texto tapa la cara o la cabeza de un personaje?
- ¿hay letras cortadas o que se salen? ¿letras con rayas raras?
- ¿elementos pegados o superpuestos? ¿un arma o una mano toca una caja de texto o el logo?
- ¿quedaron restos del fondo original alrededor de un personaje recortado (manchas, rectángulos, bordes de otra
  imagen) o pedazos de otras figuras? Escondelos con mask-image (degradé), clip-path, object-position o achicando
  lo que se ve de esa imagen; si no hay forma, sacá esa imagen y resolvelo con diseño.
- en la horizontal, ¿el personaje principal es grande (al menos 75% del alto)? si es chico, agrandalo.
- ¿se le corta la cabeza o el arma principal? ¿en vertical falta el logo o queda un hueco vacío grande?
- ¿se lee bien en chico?
Si está todo bien respondé solo: OK
Si no, respondé SOLO el HTML completo corregido (mismos textos y las mismas imágenes o menos, solo arreglá los
problemas)."""
MANTENER = """
OJO: Mr. H pidió este cambio y le gusta todo lo demás: «{cambio}». Ese cambio se queda (no saques ni cambies esa imagen
o ese texto) y lo demás no se toca: arreglá solo lo que se tape, se corte o se superponga."""


def revisar(carpeta, html, mantener=""):
    """Un Claude mira cómo quedó (solo puede leer esta carpeta, sin internet) y corrige si algo se tapa o se corta."""
    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO, buscar_claude
    exe = buscar_claude()
    if not exe:
        return False
    foto(html, carpeta / "_rev_youtube.png", 1280, 720)
    foto(html, carpeta / "_rev_tiktok.png", 1080, 1920)
    modelo = config.CLAUDE_MODELO_REVISION or config.CLAUDE_MODELO
    comando = [exe, "-p", "--max-turns", "6"] + SOLO_ESTO + (["--model", modelo] if modelo else [])
    comando += ["--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h != "Read"] + ["--allowedTools", "Read(./**)"]
    try:
        pedido = REVISION.format(html=html.read_text(encoding="utf-8")) + (MANTENER.format(cambio=mantener) if mantener else "")
        r = subprocess.run(comando, input=pedido, capture_output=True,
                           text=True, encoding="utf-8", timeout=360, cwd=str(carpeta))
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


def crear(carpeta, titulo, subtitulo="", idea="", dicho=""):
    html = disenar(carpeta, titulo, subtitulo, idea, dicho)
    if config.MINIATURA_REVISAR:
        try:
            revisar(carpeta, html)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude revisarla ({e}); queda la primera versión.")
    return fotos(carpeta, html)


def fotos(carpeta, html):
    """Los tres formatos (YouTube, Kick y TikTok) a partir del diseño."""
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


# ----------------------------------------------------------------- editar la que ya está
# El 4 nov pidió «la miniatura que está ahorita está buena, solo poné el logo oficial de WoW Forever» y Hogger
# contestó «Falta título»: solo sabía hacer miniaturas nuevas. Esto toma el diseño de la última y cambia solo eso.
REGISTRO = "miniaturas.json"
NO_SE_COPIAN = {"youtube.jpg", "kick.png", "tiktok.jpg", "comparacion.jpg", "agente.log", "cambio.json"}
EDITAR = """Sos el diseñador de las miniaturas de Mr. H (streamer de World of Warcraft: Forever, hermandad The H's). Esta
miniatura de YouTube y TikTok YA ESTÁ HECHA y le gusta. Es este HTML (diseno.html); antes_youtube.jpg (1280x720) y
antes_tiktok.jpg (1080x1920) son la foto de cómo se ve hoy:

<<<
{html}
>>>

Mr. H pidió este cambio: {cambio}
{dicho}
Hacé SOLO ese cambio. Todo lo demás queda IGUAL: textos, letras, colores, posiciones, tamaños, imágenes y efectos.
- Si cambia una imagen por otra (por ejemplo un logo), la nueva va en el MISMO lugar y con un tamaño parecido. Ajustá
  ancho y alto a la proporción de la imagen nueva (con object-fit: contain) para que no se deforme, y que no tape
  textos, caras ni la cabeza de un personaje, tampoco en vertical (@media (orientation: portrait)).
- Si la imagen vieja ya no se usa, sacá su <img> o su url(): que no quede de las dos.
- Usá solo estos archivos (están en la misma carpeta, con rutas relativas). antes_*.jpg son solo para mirar: no van
  en el diseño.
{archivos}
- Si el cambio pide algo que no está en los archivos (por ejemplo un logo que no se pudo bajar), no lo inventes:
  devolvé "cambios" vacío y explicá por qué en "resumen".
- Antes de responder, abrí con Read antes_youtube.jpg{mirar} para ver cómo está y dónde va el cambio.
- Sin JavaScript que cargue cosas, sin nada de internet.
Respondé SOLO con JSON, sin explicaciones:
{{"cambios": [{{"buscar": "un pedazo EXACTO del HTML, que esté una sola vez (copialo al pie de la letra)",
"poner": "cómo queda ese pedazo"}}], "resumen": "qué cambiaste, en una frase corta en español (se dice en voz alta)"}}"""


def _registro():
    import json
    try:
        return json.loads((config.DATA / REGISTRO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def anotar(que, carpeta):
    """que = "subida" (la que está en YouTube) o "editada" (la última que cambié, esperando tu «dale»)."""
    import json
    import time
    r = _registro()
    r[que] = {"nombre": carpeta.name, "cuando": time.time()}
    config.DATA.mkdir(parents=True, exist_ok=True)
    (config.DATA / REGISTRO).write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")


def _subida_segun_historial():
    """«Miniaturas listas (…) en C:\\…\\miniaturas\\2026-11-03_2002_x y subida a YouTube.»: las de antes del registro."""
    try:
        lineas = (config.DATA / "historial.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for linea in reversed(lineas):
        m = re.search(r"Miniaturas listas .*? en (\S+?) y subida a YouTube", linea)
        if m:
            return re.split(r"[\\/]", m.group(1))[-1]
    return ""


def ultima():
    """La carpeta de la miniatura «de ahora»: la última que cambié (si todavía no la subiste y es de las últimas 3
    horas, para seguir retocándola), si no la que está en YouTube, y si no hay registro la más nueva."""
    import time
    base = config.SALIDA / "miniaturas"
    r = _registro()
    sub, edi = r.get("subida") or {}, r.get("editada") or {}
    nombre_sub = sub.get("nombre") or _subida_segun_historial()
    if edi.get("nombre") and edi.get("cuando", 0) > sub.get("cuando", 0) and time.time() - edi["cuando"] < 3 * 3600 \
            and (base / edi["nombre"] / "diseno.html").exists():
        return base / edi["nombre"]
    if nombre_sub and (base / nombre_sub).is_dir():
        return base / nombre_sub
    if not base.is_dir():
        return None
    hechas = sorted(d for d in base.iterdir() if (d / "diseno.html").exists() and re.match(r"\d{4}-\d{2}-\d{2}_", d.name))
    return hechas[-1] if hechas else None


def _imagenes_del_html(html):
    refs = re.findall(r"""(?:src|href)\s*=\s*["']([^"'#]+)["']|url\(\s*["']?([^"')]+)["']?\s*\)""", html)
    return {a or b for a, b in refs if (a or b) and not re.match(r"(data|https?|about|blob):", a or b, re.I)}


def _lista_archivos(carpeta, html, extras):
    """Los archivos que puede usar: los de siempre, los que bajó el agente y los que ya usa el diseño."""
    lista = _preparar(carpeta, extras)
    usados = _imagenes_del_html(html)
    for f in sorted(carpeta.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and f.name not in lista and \
                not f.name.startswith("antes_") and f.name in usados:
            try:
                with Image.open(f) as im:
                    lista += f"\n- {f.name}: imagen que ya usa el diseño, {im.width}x{im.height}"
            except Exception:  # noqa: BLE001
                pass
    return lista


def _json(texto):
    import json
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        raise RuntimeError("el diseñador no devolvió los cambios")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise RuntimeError(f"el diseñador devolvió algo que no entiendo ({e})")


def comparar(antes, despues, salida):
    """Una sola imagen con la de antes y la nueva, una al lado de la otra, para mirarla antes del «dale»."""
    from PIL import ImageDraw
    from miniaturas import _fuente
    w, h = 960, 540
    lienzo = Image.new("RGB", (w * 2 + 30, h + 70), (16, 12, 8))
    d = ImageDraw.Draw(lienzo)
    for i, (ruta, rotulo) in enumerate(((antes, "ANTES"), (despues, "AHORA"))):
        x = 10 + i * (w + 10)
        if ruta and ruta.exists():
            with Image.open(ruta) as im:
                lienzo.paste(im.convert("RGB").resize((w, h), Image.LANCZOS), (x, 60))
        d.text((x, 12), rotulo, font=_fuente(36), fill=(232, 196, 104))
    lienzo.save(salida, "JPEG", quality=90)
    return salida


def editar(cambio, dicho="", vieja=None, claude=None):
    """Copia la miniatura de ahora a una carpeta nueva y cambia SOLO lo que pidió. Nada se sube todavía.

    Devuelve {"youtube", "kick", "tiktok", "comparacion", "carpeta", "de", "resumen"}.
    claude(pedido, carpeta) -> texto: para las pruebas (si no, el Claude de tu PC, que solo puede leer esa carpeta).
    """
    import datetime as dt
    import json
    from mis_overlays import Error as ErrorCambio, aplicar_cambios
    vieja = vieja or ultima()
    if not vieja:
        raise RuntimeError("No encuentro ninguna miniatura hecha para editar. Pedime una nueva con su título.")
    if not (vieja / "diseno.html").exists():
        raise RuntimeError(f"La miniatura de ahora ({vieja.name}) la hice con la plantilla, no tiene diseño para "
                           "editar. Pedime una nueva con su título y la idea.")
    raiz = re.sub(r"(-editada\d*)+$", "", re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4,6}_", "", vieja.name))[:40] or "miniatura"
    sello = f"{dt.datetime.now():%Y-%m-%d_%H%M%S}"
    nueva, i = config.SALIDA / "miniaturas" / f"{sello}_{raiz}-editada", 2
    while nueva.exists():
        nueva, i = config.SALIDA / "miniaturas" / f"{sello}_{raiz}-editada{i}", i + 1
    nueva.mkdir(parents=True)
    for f in vieja.iterdir():
        if f.is_file() and f.name not in NO_SE_COPIAN and not f.name.startswith(("_", "antes_", "referencia_")):
            shutil.copy2(f, nueva / f.name)
    for formato in ("youtube", "tiktok"):
        if (vieja / f"{formato}.jpg").exists():
            shutil.copy2(vieja / f"{formato}.jpg", nueva / f"antes_{formato}.jpg")
    html_viejo = (nueva / "diseno.html").read_text(encoding="utf-8")
    extras = []
    if necesita_agente(cambio):
        try:
            extras = buscar_imagenes(cambio, nueva, dicho)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude buscar imágenes ({e}); la edito con lo que hay.")
    archivos = _lista_archivos(nueva, html_viejo, extras)
    nuevas = [a for a, _ in extras] + ([LOGO_JUEGO] if (nueva / LOGO_JUEGO).exists() and LOGO_JUEGO not in html_viejo
                                       and re.search(r"logo", cambio, re.I) else [])
    pedido = EDITAR.format(
        html=html_viejo, cambio=cambio, archivos=archivos,
        dicho=(f"Lo que dijo, palabra por palabra (dictado por voz, puede tener errores; manda el cambio de arriba): "
               f"«{dicho[:1200]}»\n") if dicho and dicho != cambio else "",
        mirar="".join(f" y {a}" for a in nuevas[:2]))
    if claude:
        respuesta = claude(pedido, nueva)
    else:
        from overlays import _correr_claude
        r, respuesta = _correr_claude(pedido, nueva, mirar=True)
        if r.returncode != 0:
            raise RuntimeError(f"Claude no pudo editarla ({r.returncode}): {(r.stderr or respuesta or '')[:200]}")
    j = _json(respuesta)
    resumen = str(j.get("resumen") or cambio).strip()[:300]
    if not j.get("cambios"):
        falta = (" Si tenés el logo en PNG, guardalo como recursos\\logo_wow_forever.png y pedímelo de nuevo."
                 if re.search(r"logo", cambio, re.I) and not logo_fijo() else "")
        raise RuntimeError(f"No la pude cambiar: {resumen.rstrip('.')}.{falta}")
    try:
        html_nuevo = aplicar_cambios(html_viejo, j["cambios"])
    except ErrorCambio as e:
        raise RuntimeError(f"No pude aplicar el cambio en el diseño: {e}")
    faltan = [a for a in _imagenes_del_html(html_nuevo) if not (nueva / a).exists()]
    if faltan:
        raise RuntimeError(f"El diseño nuevo usa archivos que no están ({', '.join(faltan[:3])}): no lo hago.")
    html = nueva / "diseno.html"
    html.write_text(html_nuevo, encoding="utf-8")
    if config.MINIATURA_REVISAR and not claude:
        try:
            revisar(nueva, html, mantener=cambio)
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] No pude revisarla ({e}); queda como la cambié.")
    rutas = fotos(nueva, html)
    rutas["comparacion"] = comparar(nueva / "antes_youtube.jpg", rutas["youtube"], nueva / "comparacion.jpg")
    (nueva / "cambio.json").write_text(json.dumps({"de": vieja.name, "cambio": cambio, "dicho": dicho,
                                                   "resumen": resumen}, indent=2, ensure_ascii=False), encoding="utf-8")
    anotar("editada", nueva)
    rutas.update(carpeta=nueva, de=vieja.name, resumen=resumen)
    return rutas


def aprender_logo(carpeta):
    """Si la miniatura que aprobaste («dale») usa el logo de Forever que bajó el agente, queda como logo fijo."""
    if logo_fijo():
        return ""
    html = (carpeta / "diseno.html").read_text(encoding="utf-8") if (carpeta / "diseno.html").exists() else ""
    for f in sorted(carpeta.glob("web_logo_wow_forever*.png"), key=lambda x: "_recorte" not in x.name):
        if f.name in _imagenes_del_html(html):
            config.RECURSOS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, config.RECURSOS / LOGO_JUEGO)
            return "Guardé ese logo de WoW Forever para las próximas miniaturas."
    return ""


def mostrar(ruta):
    """Te abre la imagen (en Windows, con el visor de fotos) para que la mires antes del «dale»."""
    if not config.MINIATURA_MOSTRAR or os.name != "nt":
        return False
    try:
        os.startfile(str(ruta))          # noqa: S606 (es tu propia imagen, en tu PC)
        return True
    except OSError as e:
        print(f"[miniatura] No pude abrir {ruta}: {e}")
        return False
