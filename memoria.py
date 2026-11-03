"""Memoria corta de la charla: lo último que hablaron Nicolas y El Cerebro.

Dura unos minutos (MEMORIA_MINUTOS) y solo vive en la memoria de la PC: si cerrás El Cerebro, se olvida.
Sirve para que entienda «lo», «él», «ese» o «¿lo baneamos?» sin repetirle todo, y para seguir una charla.
No sale de tu PC ni cuesta nada: se le pasa como texto a la IA local junto con cada orden.
"""
import re
import threading
import time
from collections import deque

import config

_lock = threading.Lock()
_charla = deque(maxlen=max(2, config.MEMORIA_FRASES))
_personas = {}                  # clave -> {usuario, plataforma, cuando}: gente del chat de la que se habló


def _vigentes(lista, minutos=None):
    limite = time.time() - 60 * (minutos if minutos is not None else config.MEMORIA_MINUTOS)
    return [x for x in lista if x["cuando"] >= limite]


def anotar(quien, texto):
    """quien = "Nicolas" o "Vos" (El Cerebro)."""
    texto = " ".join(str(texto or "").split())
    if not texto or not config.MEMORIA:
        return
    with _lock:
        _charla.append({"quien": quien, "texto": texto[:220], "cuando": time.time()})


def anotar_persona(usuario, plataforma):
    if not usuario or not config.MEMORIA:
        return
    with _lock:
        _personas[str(usuario).lower()] = {"usuario": usuario, "plataforma": plataforma, "cuando": time.time()}


def persona(minutos=None):
    """La última persona del chat de la que hablaron (o None si ya pasó mucho)."""
    with _lock:
        vivas = _vigentes(_personas.values(), minutos)
    return max(vivas, key=lambda p: p["cuando"]) if vivas else None


def frases(quien=None, minutos=None):
    """Lo último que dijo quien («Nicolas» o «Vos»), del más viejo al más nuevo."""
    with _lock:
        return [f["texto"] for f in _vigentes(_charla, minutos) if quien is None or f["quien"] == quien]


def hay_charla(minutos=3):
    with _lock:
        return bool(_vigentes(_charla, minutos))


def olvidar():
    with _lock:
        _charla.clear()
        _personas.clear()


def personas_en(orden, minimo=0.85):
    """La gente del chat de la que ya hablaron y que Nicolas vuelve a nombrar en esta orden («saludá a Lucas»)."""
    import moderacion
    palabras = re.findall(r"[\w@]+", str(orden or "").lower())
    trozos = {" ".join(palabras[i:i + n]) for n in (1, 2) for i in range(len(palabras) - n + 1)}
    trozos = {t for t in trozos if len(moderacion.clave(t)) >= 3}
    with _lock:
        vivas = _vigentes(_personas.values())
    return [p["usuario"] for p in vivas if max((moderacion.parecido(t, p["usuario"]) for t in trozos), default=0) >= minimo]


def para_la_ia(ultimas=None, sobre=None):
    """Texto para el final del pedido a la IA (no en las instrucciones fijas: así no se pierde la caché).

    ultimas = cuántas frases pasar (None = todas). sobre = [nombres]: solo lo que se habló de esa gente
    («saludá a Lucas» no tiene nada que ver con la raid de recién, salvo que Lucas haya estado en la charla).
    """
    import moderacion
    with _lock:
        frases = _vigentes(_charla)
        if ultimas:
            frases = frases[-ultimas:]
        gente = sorted(_vigentes(_personas.values()), key=lambda p: p["cuando"])
    if sobre is not None:
        claves = set()
        for n in sobre:                  # «Lucas_99»: también cuenta «Lucas» solo
            claves |= {c for c in [moderacion.clave(n)] + re.findall(r"[a-z]{4,}", moderacion.clave(n)) if len(c) >= 3}
        frases = [f for f in frases if any(c in moderacion.clave(f["texto"]) for c in claves)]
        gente = [p for p in gente if moderacion.clave(p["usuario"]) in claves]
        if not frases and not gente:
            return ""
    if not frases and not gente:
        return ""
    ahora = time.time()
    lineas = ["\nCharla reciente con Nicolas (de la más vieja a la más nueva). Usala SOLO para entender «lo», «él», «ese», "
              "«eso» y para seguir esa conversación, sin repetir lo que ya dijiste. Si la orden es un tema nuevo (un saludo, "
              "un chiste, otra pregunta), no traigas nada de acá:"] if frases else [""]
    for f in frases:
        hace = int((ahora - f["cuando"]) // 60)
        cuando = "recién" if hace < 1 else f"hace {hace} min"
        lineas.append(f"- {cuando}, {f['quien']}: {f['texto']}")
    if gente:
        lineas.append("Gente del chat de la que vienen hablando: " +
                      ", ".join(f"{p['usuario']} ({p['plataforma']})" for p in gente[-3:]) + ".")
    return "\n".join(lineas) + "\n"
