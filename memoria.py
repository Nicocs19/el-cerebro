"""Memoria corta de la charla: lo último que hablaron Nicolas y El Cerebro.

Dura unos minutos (MEMORIA_MINUTOS) y solo vive en la memoria de la PC: si cerrás El Cerebro, se olvida.
Sirve para que entienda «lo», «él», «ese» o «¿lo baneamos?» sin repetirle todo, y para seguir una charla.
No sale de tu PC ni cuesta nada: se le pasa como texto a la IA local junto con cada orden.
"""
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


def para_la_ia(ultimas=None):
    """Texto para el final del pedido a la IA (no en las instrucciones fijas: así no se pierde la caché).

    ultimas = cuántas frases pasar (None = todas las vigentes).
    """
    with _lock:
        frases = _vigentes(_charla)
        if ultimas:
            frases = frases[-ultimas:]
        gente = sorted(_vigentes(_personas.values()), key=lambda p: p["cuando"])
    if not frases and not gente:
        return ""
    ahora = time.time()
    lineas = ["\nCharla reciente con Nicolas (de la más vieja a la más nueva). Usala para entender «lo», «él», «ese», "
              "«eso» y para seguir la conversación, sin repetir lo que ya dijiste:"] if frases else [""]
    for f in frases:
        hace = int((ahora - f["cuando"]) // 60)
        cuando = "recién" if hace < 1 else f"hace {hace} min"
        lineas.append(f"- {cuando}, {f['quien']}: {f['texto']}")
    if gente:
        lineas.append("Gente del chat de la que vienen hablando: " +
                      ", ".join(f"{p['usuario']} ({p['plataforma']})" for p in gente[-3:]) + ".")
    return "\n".join(lineas) + "\n"
