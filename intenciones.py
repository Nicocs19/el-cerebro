"""Convierte lo que dices en una orden. Primero patrones (rapido, sin GPU); IA local opcional."""
import json
import re
import unicodedata

import requests

import config


def _norm(texto):
    """Minusculas y sin tildes, conservando la misma longitud que el original."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto.lower())


def _limpiar(texto, quitar_punto=False):
    texto = texto.strip().strip("\"'«»“”").strip()
    texto = re.sub(r"^[\s,:;.\-]+", "", texto)
    if quitar_punto:
        texto = texto.rstrip(" .")
    return texto[:1].upper() + texto[1:] if texto else texto


GUILD = r"(?:guild|guil|gild|guilt|hermandad|gremio|discord|clan)"
ANUNCIO = r"\b(?:anuncio|anuncia|anunciale|anunciales|avisa|avisale|aviso|comunicado)\b"


def _plataformas(n):
    p = [x for x in ("kick", "youtube", "tiktok") if x in n.replace("you tube", "youtube").replace("tik tok", "tiktok")]
    return p or ["kick", "youtube", "tiktok"]


def por_patrones(texto):
    n = _norm(texto)

    # Deshacer
    if re.search(r"\b(?:borra|elimina|quita)\w*\b.*\b(?:anuncio|mensaje)\b", n):
        return {"accion": "borrar_anuncio"}
    if re.search(r"\b(?:deshaz|restaura|recupera|vuelve)\w*\b.*\btitulo", n):
        return {"accion": "restaurar_titulo"}
    if re.search(r"\b(?:que|cual|dime)\b.*\btitulo\b", n) and not re.search(r"\b(?:cambia|pon|actualiza)", n):
        return {"accion": "consultar_titulo"}

    # Titulo
    m = re.search(r"\btitulos?\b", n)
    if m and re.search(r"\b(?:cambia|cambiale|pon|ponle|actualiza|modifica|titulo\w* (?:a|por))", n):
        resto_n = n[m.end():]
        sep = re.search(r":|\b(?:a|por|que diga|que sea)\b[\s:,]*", resto_n)
        if sep:
            titulo = texto[m.end() + sep.end():]
            plataformas = _plataformas(n[: m.end() + sep.start()])
            titulo = _limpiar(titulo, quitar_punto=True)
            if titulo:
                return {"accion": "titulo", "texto": titulo, "plataformas": plataformas}

    # Anuncio
    m = re.search(ANUNCIO, n)
    if m:
        resto_n = n[m.end():]
        g = re.search(GUILD + r"\b[\s,:;.\-]*(?:que diga|diciendo|que dice|que)?[\s,:;\-]*", resto_n)
        dos_puntos = resto_n.find(":")
        if dos_puntos != -1 and (not g or dos_puntos < g.start()):
            corte = m.end() + dos_puntos + 1
        elif g:
            corte = m.end() + g.end()
        else:
            d = re.search(r"[:,]|\b(?:que diga|diciendo)\b", resto_n)
            corte = m.end() + (d.end() if d else 0)
        mensaje = _limpiar(texto[corte:])
        if mensaje:
            return {"accion": "anuncio", "texto": mensaje}

    return None


_SISTEMA = """Eres el router de ordenes de un streamer. Convierte la frase en JSON.
Acciones posibles:
- "anuncio": publicar un anuncio en el Discord de la hermandad. "texto" = el mensaje exacto a publicar.
- "titulo": cambiar el titulo del directo. "texto" = el nuevo titulo exacto. "plataformas" = lista entre kick, youtube, tiktok (todas si no dice cual).
- "borrar_anuncio", "restaurar_titulo", "consultar_titulo".
- "desconocida": si no es ninguna de las anteriores.
No inventes texto: copia literalmente lo que el usuario quiere publicar."""

_ESQUEMA = {
    "type": "object",
    "properties": {
        "accion": {"type": "string", "enum": ["anuncio", "titulo", "borrar_anuncio",
                                               "restaurar_titulo", "consultar_titulo", "desconocida"]},
        "texto": {"type": "string"},
        "plataformas": {"type": "array", "items": {"type": "string", "enum": ["kick", "youtube", "tiktok"]}},
    },
    "required": ["accion"],
}


def por_ollama(texto):
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": config.OLLAMA_MODEL,
            "messages": [{"role": "system", "content": _SISTEMA}, {"role": "user", "content": texto}],
            "format": _ESQUEMA,
            "stream": False,
            "think": False,
            "keep_alive": config.keep_alive(),
            "options": {"temperature": 0, "num_ctx": config.OLLAMA_CTX},     # igual que el router: no recarga
        }, timeout=60)
        r.raise_for_status()
        data = json.loads(r.json()["message"]["content"])
    except Exception as e:  # noqa: BLE001
        print(f"[ollama] no disponible: {e}")
        return None
    if data.get("accion") in (None, "desconocida"):
        return None
    if data["accion"] in ("anuncio", "titulo") and not data.get("texto"):
        return None
    if data["accion"] == "titulo":
        data["texto"] = _limpiar(data["texto"], quitar_punto=True)
        data["plataformas"] = data.get("plataformas") or ["kick", "youtube", "tiktok"]
    return data


def interpretar(texto):
    orden = por_patrones(texto)
    if orden is None and config.USE_OLLAMA:
        orden = por_ollama(texto)
    return orden or {"accion": "desconocida", "texto": texto}
