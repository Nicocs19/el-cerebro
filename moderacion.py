"""Moderación por voz en Kick y YouTube: encuentra al usuario que nombraste y arma la orden.

El dictado escribe los nombres "como suenan" («pepe noventa y nueve», «chadou»), así que se comparan con los que
escribieron hace poco en el chat (Kick se escucha en vivo; YouTube se lee en el momento). Siempre se confirma el
nombre exacto con «dale» antes de banear.
"""
import difflib
import json
import re
import time
import unicodedata

import config
import herramientas as H

ACCIONES = ["banear", "silenciar", "desbanear"]
CHATS = ["kick", "youtube"]
_NUM = {"cero": "0", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6",
        "siete": "7", "ocho": "8", "nueve": "9", "diez": "10", "once": "11", "doce": "12", "veinte": "20",
        "treinta": "30", "cuarenta": "40", "cincuenta": "50", "sesenta": "60", "setenta": "70", "ochenta": "80",
        "noventa": "90", "cien": "100", "mil": "1000"}
_LEET = str.maketrans({"4": "a", "3": "e", "1": "i", "0": "o", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s"})
_SONIDOS = (("sh", "ch"), ("ph", "f"), ("th", "t"), ("ck", "c"), ("k", "c"), ("q", "c"), ("w", "u"), ("y", "i"),
            ("z", "s"), ("v", "b"), ("h", ""), ("x", "cs"))
ACEPTA = 0.6        # parecido mínimo para proponer a alguien
EMPATE = 0.06       # si otro está a menos de esto, se pregunta a cuál


def _texto_plano(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def _numeros(t):
    """«noventa y nueve» -> 99, «dos mil» -> 2000 (lo justo para nombres de usuario)."""
    palabras, salida, i = t.split(), [], 0
    while i < len(palabras):
        p = palabras[i]
        if p in _NUM:
            n = int(_NUM[p])
            if i + 2 < len(palabras) and palabras[i + 1] == "y" and palabras[i + 2] in _NUM and n >= 20:
                n += int(_NUM[palabras[i + 2]])
                i += 2
            elif i + 1 < len(palabras) and palabras[i + 1] == "mil":
                n *= 1000
                i += 1
            salida.append(str(n))
        else:
            salida.append(p)
        i += 1
    return " ".join(salida)


def clave(nombre):
    t = _texto_plano(nombre).strip().lstrip("@")
    t = re.sub(r"^(al |a la |a el |a |el |la |usuario |user )+", "", t)
    return re.sub(r"[^a-z0-9]", "", _numeros(t))


def _sonido(c):
    c = c.translate(_LEET)
    for a, b in _SONIDOS:
        c = c.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", c)


def parecido(dicho, usuario):
    a, b = clave(dicho), clave(usuario)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    sa, sb = _sonido(a), _sonido(b)
    if sa == sb:
        return 0.96
    s = max(difflib.SequenceMatcher(None, a, b).ratio(), difflib.SequenceMatcher(None, sa, sb).ratio())
    if len(sa) >= 3 and sa in sb:           # dijo una parte: «dark» -> xX_D4rk_Xx
        s = max(s, 0.78 + 0.17 * len(sa) / len(sb))
    return s


def _candidatos(mensajes):
    """Un candidato por persona, con su último mensaje (los mensajes vienen del más viejo al más nuevo)."""
    vistos = {}
    for i, m in enumerate(mensajes):
        vistos[(m["plataforma"], m["id"])] = {**m, "orden": i}
    return list(vistos.values())


def _mejores(dicho, candidatos):
    total = max(1, len(candidatos))
    puntuados = []
    for c in candidatos:
        s = parecido(dicho, c["usuario"])
        if s >= ACEPTA - 0.1:
            puntuados.append((s + 0.02 * c.get("orden", 0) / total, c))   # a igual parecido, el más reciente
    puntuados.sort(key=lambda x: -x[0])
    return puntuados


def _mensajes(plataforma, avisos):
    if plataforma == "kick":
        import chat_vivo
        if not chat_vivo.ESTADO["conectado"] and not chat_vivo.MENSAJES:
            avisos.append("no estoy escuchando el chat de Kick" + (f" ({chat_vivo.ESTADO['error']})"
                                                                  if chat_vivo.ESTADO.get("error") else ""))
        return chat_vivo.recientes_kick()
    from youtube import YouTube
    try:
        return [{**m, "plataforma": "youtube"} for m in YouTube().mensajes_recientes()]
    except Exception as e:  # noqa: BLE001
        avisos.append(f"YouTube: {e}")
        return []


def baneados():
    """Los que baneó o silenció El Cerebro (para poder desbanearlos por voz)."""
    try:
        return json.loads((config.DATA / "estado.json").read_text(encoding="utf-8")).get("baneados") or []
    except Exception:  # noqa: BLE001
        return []


def _buscar(dicho, plataformas, accion):
    """Lista de objetivos (uno por plataforma) o una Accion de aclaración si hay dudas."""
    avisos, objetivos, dudas = [], [], []
    for p in plataformas:
        if accion == "desbanear":
            cands = [{**b, "orden": i} for i, b in enumerate(baneados()) if b["plataforma"] == p]
        else:
            cands = _candidatos(_mensajes(p, avisos))
        mejores = _mejores(dicho, cands)
        if mejores and mejores[0][0] >= ACEPTA:
            s, elegido = mejores[0]
            if elegido.get("protegido"):
                raise H.ErrorOrden(f"{elegido['usuario']} es moderador (o sos vos) en {H.NOMBRES[p]}: no lo modero.")
            parecidos = [c["usuario"] for x, c in mejores[1:4] if x >= max(ACEPTA, s - EMPATE)
                         and clave(c["usuario"]) != clave(elegido["usuario"])]
            if parecidos:
                dudas.append((p, [elegido["usuario"]] + parecidos))
                continue
            objetivos.append({"plataforma": p, "id": elegido["id"], "usuario": elegido["usuario"],
                              "texto": str(elegido.get("texto") or "")[:120], "ban_id": elegido.get("ban_id"),
                              "seguro": s >= 0.85})
    if not objetivos and not dudas and "kick" in plataformas:
        # No escribió hace poco (o no escucho el chat): se busca su nombre exacto en Kick
        try:
            from kick import Kick
            u = Kick().usuario(_numeros(_texto_plano(dicho)))
        except Exception as e:  # noqa: BLE001
            avisos.append(f"Kick: {e}")
            u = None
        if u:
            objetivos.append({"plataforma": "kick", "id": u["id"], "usuario": u["usuario"], "ban_id": None,
                              "texto": "", "seguro": False, "fuera_del_chat": True})
    if dudas:
        partes = [f"en {H.NOMBRES[p]}: {' o '.join(n)}" for p, n in dudas]
        pregunta = f"¿A cuál? Encontré {'; '.join(partes)}."
        return None, H.Accion("aclaracion", {"pregunta": pregunta}, pregunta, False)
    if not objetivos:
        donde = " ni ".join(H.NOMBRES[p] for p in plataformas)
        extra = f" ({'; '.join(avisos)})" if avisos else ""
        que = "entre los que baneé en" if accion == "desbanear" else "en el chat de"
        raise H.ErrorOrden(f"No encontré a «{dicho}» {que} {donde}{extra}.")
    return objetivos, None


def construir(a):
    accion = a.get("accion") if a.get("accion") in ACCIONES else "silenciar"
    dicho = str(a.get("usuario") or "").strip()
    if not clave(dicho):
        raise H.ErrorOrden("¿A quién? No entendí el nombre del usuario.")
    plataformas = [p for p in (a.get("plataformas") or []) if p in CHATS] or CHATS
    minutos = None
    if accion == "silenciar":
        try:
            pedidos = int(float(a.get("minutos") or 0))
        except (TypeError, ValueError):
            pedidos = 0
        minutos = H._ent({"minutos": pedidos if pedidos > 0 else config.SILENCIO_MINUTOS}, "minutos", 1, 10080, 10)
    objetivos, aclaracion = _buscar(dicho, plataformas, accion)
    if aclaracion:
        return aclaracion
    datos = {"accion": accion, "minutos": minutos, "motivo": H._txt(a, "motivo", 100, False), "objetivos": objetivos}
    verbo = {"banear": "Banear para siempre a", "silenciar": f"Silenciar {minutos} min a", "desbanear": "Desbanear a"}[accion]
    lineas = []
    for o in objetivos:
        lineas.append(f"{verbo} {o['usuario']} en {H.NOMBRES[o['plataforma']]}")
        if o["texto"]:
            lineas.append(f"   último mensaje: «{o['texto']}»")
        if o.get("fuera_del_chat"):
            lineas.append("   (no lo vi en el chat reciente: es la cuenta de Kick que se llama así)")
        elif not o["seguro"]:
            lineas.append(f"   (es el más parecido a «{dicho}»: fijate que sea él)")
    return H.Accion("moderar", datos, "\n".join(lineas), True)


def ejecutar(accion, kick, yt, estado, simular=False):
    """Hace la moderación en cada plataforma. Devuelve el texto del resultado."""
    d = accion.datos
    hechos, fallos = [], []
    lista = estado.setdefault("baneados", [])
    for o in d["objetivos"]:
        p, nombre = o["plataforma"], o["usuario"]
        try:
            if simular:
                hechos.append(f"{nombre} en {H.NOMBRES[p]} (simulado)")
                continue
            if d["accion"] == "desbanear":
                if p == "kick":
                    kick.desbanear(o["id"])
                elif o.get("ban_id"):
                    yt.desbanear(o["ban_id"])
                else:
                    raise RuntimeError("en YouTube solo puedo desbanear a los que baneé yo")
                estado["baneados"] = lista = [b for b in lista if not (b["plataforma"] == p and b["id"] == o["id"])]
            else:
                minutos = d["minutos"] if d["accion"] == "silenciar" else None
                if p == "kick":
                    kick.banear(o["id"], minutos, d.get("motivo"))
                    ban_id = None
                else:
                    ban_id = yt.banear(o["id"], minutos * 60 if minutos else None)
                lista[:] = [b for b in lista if not (b["plataforma"] == p and b["id"] == o["id"])]
                lista.append({"plataforma": p, "id": o["id"], "usuario": nombre, "ban_id": ban_id,
                              "tipo": d["accion"], "cuando": time.strftime("%Y-%m-%d %H:%M")})
                del lista[:-100]
            hechos.append(f"{nombre} en {H.NOMBRES[p]}")
        except Exception as e:  # noqa: BLE001
            fallos.append(f"{H.NOMBRES[p]}: {e}")
    participio = {"banear": "Baneado", "silenciar": f"Silenciado {d['minutos']} min", "desbanear": "Desbaneado"}[d["accion"]]
    partes = []
    if hechos:
        partes.append(f"{participio}: {', '.join(hechos)}.")
    if fallos:
        partes.append("Falló " + "; ".join(fallos))
    if not hechos:
        raise RuntimeError(" ".join(partes))
    return " ".join(partes)
