"""Miniaturas con el estilo de The H's (dorado, Cinzel, logo) a partir de una captura de OBS.

Formatos:
  youtube.jpg  1280x720  (menos de 2 MB, se puede subir por API)
  kick.png     1920x1080 (Kick no permite subirla por API: queda lista en la carpeta)
  tiktok.jpg   1080x1920 (portada vertical para clips y vídeos)
"""
import base64
import datetime as dt
import io
import re
import unicodedata

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

import config

DORADO = (232, 196, 104)
DORADO_OSCURO = (150, 110, 30)
BLANCO = (255, 255, 255)
FORMATOS = {"youtube": (1280, 720, "jpg"), "kick": (1920, 1080, "png"), "tiktok": (1080, 1920, "jpg")}


class MiniaturaError(RuntimeError):
    pass


def captura_obs():
    """Captura la escena o fuente de OBS_FUENTE (p. ej. el juego); si está vacío, lo que sale en directo."""
    import obsws_python as obs
    try:
        cl = obs.ReqClient(host=config.OBS_HOST, port=config.OBS_PORT, password=config.OBS_PASSWORD, timeout=4)
    except Exception as e:  # noqa: BLE001
        raise MiniaturaError(f"No pude conectar con OBS ({e}). Activa el servidor WebSocket en OBS.")
    def foto(nombre):
        datos = cl.get_source_screenshot(nombre, "png", 1920, 1080, -1).image_data
        return Image.open(io.BytesIO(base64.b64decode(datos.split(",", 1)[1]))).convert("RGB")

    if config.OBS_FUENTE:
        # Solo el juego: la escena en vivo puede ser la captura de pantalla completa (Discord, chats, El Cerebro).
        try:
            img = foto(config.OBS_FUENTE)
        except Exception as e:  # noqa: BLE001
            raise MiniaturaError(f"OBS no me dio «{config.OBS_FUENTE}» ({e}).")
        if es_negra(img):
            raise MiniaturaError(f"«{config.OBS_FUENTE}» está en negro (¿el juego está cerrado?).")
        return img
    img = foto(cl.get_current_program_scene().current_program_scene_name)
    if es_negra(img):
        raise MiniaturaError("La captura de OBS está en negro.")
    return img


def es_negra(img):
    """True si la imagen es (casi) toda negra: fuente sin señal o juego cerrado."""
    return max(ImageStat.Stat(img.convert("L").resize((64, 36))).extrema[0]) < 12


def _fuente(tam, peso=800):
    for ruta in (config.RECURSOS / "Cinzel.ttf", "C:/Windows/Fonts/georgiab.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"):
        try:
            f = ImageFont.truetype(str(ruta), tam)
            try:
                f.set_variation_by_axes([peso])
            except Exception:  # noqa: BLE001
                pass
            return f
        except OSError:
            continue
    return ImageFont.load_default()


def _cubrir(img, w, h):
    escala = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * escala) + 1, int(img.height * escala) + 1), Image.LANCZOS)
    x0, y0 = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x0, y0, x0 + w, y0 + h))


def _lineas(draw, texto, fuente, ancho_max, maximo=3):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=fuente) > ancho_max and actual:
            lineas.append(actual)
            actual = p
        else:
            actual = prueba
    lineas.append(actual)
    return lineas if len(lineas) <= maximo else None


def _titulo_que_entra(draw, texto, tam, ancho_max, maximo=3):
    while tam > 30:
        f = _fuente(tam)
        lineas = _lineas(draw, texto, f, ancho_max, maximo)
        if lineas:
            return f, lineas
        tam -= 6
    f = _fuente(tam)
    return f, _lineas(draw, texto, f, ancho_max, 99)[:maximo]


def _logo(tam):
    ruta = config.RECURSOS / "logo.jpg"
    if not ruta.exists():
        return None, None
    logo = Image.open(ruta).convert("RGBA").resize((tam, tam), Image.LANCZOS)
    m = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(m).ellipse((0, 0, tam, tam), fill=255)
    return logo, m


def componer(fondo, titulo, subtitulo, w, h):
    vertical = h > w
    img = ImageEnhance.Contrast(ImageEnhance.Color(_cubrir(fondo, w, h)).enhance(1.25)).enhance(1.1).convert("RGBA")
    # velo oscuro donde va el texto
    velo = Image.new("RGBA", (w, h))
    vd = ImageDraw.Draw(velo)
    for i in range(h if not vertical else h // 2):
        if vertical:  # arriba oscuro para el título
            a = int(210 * (1 - i / (h / 2)))
            vd.line([(0, i), (w, i)], fill=(8, 6, 4, a))
        else:  # abajo oscuro
            y = h - 1 - i
            a = int(225 * max(0.0, 1 - i / (h * 0.62)))
            vd.line([(0, y), (w, y)], fill=(8, 6, 4, a))
    img = Image.alpha_composite(img, velo)
    d = ImageDraw.Draw(img)
    k = w / 1280 if not vertical else w / 1080
    borde = int(12 * k)
    d.rounded_rectangle((borde, borde, w - borde, h - borde), radius=int(26 * k), outline=DORADO + (235,), width=max(3, int(5 * k)))

    # logo
    t = int((150 if vertical else 120) * k)
    logo, mascara = _logo(t)
    if logo:
        lx, ly = (w - t) // 2 if vertical else int(34 * k), int(34 * k) if not vertical else int(70 * k)
        brillo = Image.new("RGBA", (w, h))
        ImageDraw.Draw(brillo).ellipse((lx - 18 * k, ly - 18 * k, lx + t + 18 * k, ly + t + 18 * k), fill=DORADO + (120,))
        img = Image.alpha_composite(img, brillo.filter(ImageFilter.GaussianBlur(int(14 * k))))
        d = ImageDraw.Draw(img)
        d.ellipse((lx - 5 * k, ly - 5 * k, lx + t + 5 * k, ly + t + 5 * k), outline=DORADO, width=max(3, int(5 * k)))
        img.paste(logo, (lx, ly), mascara)

    # título grande (blanco con borde negro y sombra dorada)
    margen = int(56 * k)
    ancho_txt = w - 2 * margen
    f, lineas = _titulo_que_entra(d, titulo.upper(), int((120 if vertical else 104) * k), ancho_txt)
    alto_linea = int(f.size * 1.08)
    bloque = alto_linea * len(lineas)
    fs = _fuente(int((52 if vertical else 44) * k), 700)
    if vertical:
        y = int(300 * k)
    else:
        y = h - margen - bloque - (int(fs.size * 1.6) if subtitulo else 0)
    for linea in lineas:
        lw = d.textlength(linea, font=f)
        x = (w - lw) / 2 if vertical else margen
        d.text((x + 4 * k, y + 6 * k), linea, font=f, fill=DORADO_OSCURO + (200,))
        d.text((x, y), linea, font=f, fill=BLANCO, stroke_width=max(3, int(6 * k)), stroke_fill=(0, 0, 0))
        y += alto_linea
    # subtítulo en cinta dorada
    if subtitulo:
        st = subtitulo.upper()
        sw = d.textlength(st, font=fs)
        pad = int(18 * k)
        x = (w - sw) / 2 if vertical else margen
        y += int((26 if vertical else 10) * k)
        d.rounded_rectangle((x - pad, y - pad // 2, x + sw + pad, y + fs.size + pad), radius=int(12 * k), fill=DORADO + (245,))
        d.text((x, y), st, font=fs, fill=(25, 18, 8))
    return img.convert("RGB")


def _slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "miniatura"


def crear(titulo, subtitulo="", fondo=None, idea="", dicho=""):
    """Crea las tres miniaturas y devuelve {formato: ruta, "quien": "Claude" | "plantilla"}.

    Si está el programa claude, el diseño lo hace Claude (HTML que Edge convierte en imagen) siguiendo tu idea;
    si no, o si falla, se usa la plantilla dorada de siempre.
    """
    if fondo is None:
        try:
            fondo = captura_obs()
        except MiniaturaError as e:
            print(f"[miniatura] {e} Uso el fondo por defecto.")
        except ImportError:
            print("[miniatura] Falta obsws-python; uso el fondo por defecto.")
    if fondo is None:
        fondo = Image.open(config.RECURSOS / "fondo_anuncio.jpg").convert("RGB")
    carpeta = config.SALIDA / "miniaturas" / f"{dt.datetime.now():%Y-%m-%d_%H%M}_{_slug(titulo)}"
    carpeta.mkdir(parents=True, exist_ok=True)
    fondo.save(carpeta / "captura.png")
    if config.MINIATURA_CLAUDE:
        try:
            import miniaturas_claude
            rutas = miniaturas_claude.crear(carpeta, titulo, subtitulo, idea, dicho)
            rutas["quien"] = "Claude"
            return rutas
        except Exception as e:  # noqa: BLE001
            print(f"[miniatura] Claude no pudo diseñarla ({e}); uso la plantilla.")
    rutas = {}
    for nombre, (w, h, ext) in FORMATOS.items():
        img = componer(fondo, titulo, subtitulo, w, h)
        ruta = carpeta / f"{nombre}.{ext}"
        if ext == "jpg":
            img.save(ruta, "JPEG", quality=92, optimize=True)
        else:
            img.save(ruta, "PNG", optimize=True)
        rutas[nombre] = ruta
    rutas["quien"] = "plantilla"
    return rutas
