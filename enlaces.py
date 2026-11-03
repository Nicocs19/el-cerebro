"""Los enlaces que El Cerebro puede mandar al chat (enlaces.txt, al lado de cerebro.py).

Una línea por enlace:   discord = https://discord.gg/...
Para agregar uno sin abrir el archivo: copiá el enlace y decí «guardá este enlace como discord».
Solo se mandan enlaces de esta lista: la IA no puede inventar uno.
"""
import difflib
import re
import unicodedata

import config

CABECERA = """# Enlaces que El Cerebro puede mandar al chat de Kick y YouTube.
# Una línea por enlace:   nombre = enlace
# Ejemplo:                discord = https://discord.gg/tu-invitacion
# También podés copiar un enlace y decirle a El Cerebro: «guardá este enlace como discord».
"""
_URL = re.compile(r"^https?://[^\s<>\"']{3,300}$", re.I)
_URL_EN_TEXTO = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(com|gg|tv|net|org|io|me|ly)\b\S*)", re.I)


def _clave(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"^(el |la |los |las )?(link|enlace|url)s? (de |del |a |al )?(la |el |mi )?", "", t.strip())
    return re.sub(r"[^a-z0-9]", "", t)


def leer():
    """{nombre: enlace} en el orden del archivo."""
    if not config.ENLACES.exists():
        config.ENLACES.write_text(CABECERA, encoding="utf-8")
    enlaces = {}
    for linea in config.ENLACES.read_text(encoding="utf-8-sig").splitlines():
        if linea.strip().startswith("#") or "=" not in linea:
            continue
        nombre, url = (x.strip() for x in linea.split("=", 1))
        if nombre and _URL.match(url):
            enlaces[nombre] = url
    return enlaces


def buscar(nombre):
    """(nombre, enlace) del más parecido a lo que dijiste, o None."""
    enlaces = leer()
    if not enlaces:
        return None
    claves = {_clave(n): n for n in enlaces}
    k = _clave(nombre)
    if k in claves:
        n = claves[k]
        return n, enlaces[n]
    for kk, n in claves.items():            # «el discord de la guild» -> discord
        if len(kk) >= 3 and (kk in k or k in kk):
            return n, enlaces[n]
    m = difflib.get_close_matches(k, list(claves), n=1, cutoff=0.7)
    return (claves[m[0]], enlaces[claves[m[0]]]) if m else None


def guardar(nombre, url):
    """Agrega o reemplaza un enlace. Devuelve True si reemplazó uno que ya estaba."""
    nombre = re.sub(r"[=#\n]", " ", str(nombre)).strip()[:40]
    if not nombre or not _URL.match(url):
        raise ValueError("Ese enlace no parece válido.")
    leer()  # crea el archivo si no está
    lineas = config.ENLACES.read_text(encoding="utf-8-sig").splitlines()
    k, reemplazo = _clave(nombre), False
    for i, linea in enumerate(lineas):
        if not linea.strip().startswith("#") and "=" in linea and _clave(linea.split("=", 1)[0]) == k:
            lineas[i] = f"{nombre} = {url}"
            reemplazo = True
            break
    else:
        lineas.append(f"{nombre} = {url}")
    config.ENLACES.write_text("\n".join(lineas).rstrip() + "\n", encoding="utf-8")
    return reemplazo


def del_portapapeles():
    """El enlace que copiaste (Ctrl+C)."""
    import pyperclip
    texto = (pyperclip.paste() or "").strip()
    if not _URL.match(texto):
        raise ValueError("No tenés un enlace copiado. Copiá el enlace (Ctrl+C) y volvé a pedírmelo.")
    return texto


def sin_enlaces_inventados(texto, permitidos=()):
    """Quita del texto cualquier enlace que no sea de la lista."""
    return re.sub(r"\s{2,}", " ", _URL_EN_TEXTO.sub(lambda m: m.group(0) if m.group(0) in permitidos else "", texto)).strip()
