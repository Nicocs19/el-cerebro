"""Prueba la IA local con frases reales SIN publicar nada: python probar_router.py"""
import re
import sys
import time

import herramientas as H
import router

FRASES = [
    "lanza un anuncio a la guild que esta noche hacemos mazmorras a las 10, que vengan con pociones",
    "arma una raid de molten cor el viernes a las 9 con 20 cupos, gear mínimo 3000",
    "crea una raid de onyxia para mañana",
    "haz un sorteo de un mes de juego que dure dos días, que ganen dos",
    "encuesta para la guild: qué día hacemos la raid, viernes, sábado o domingo",
    "cambia el título a día 1 de wow forever subiendo guerrero del 20 al 30",
    "cambia el título solo en kick a raid nocturna con la guild",
    "cierra las inscripciones de la raid",
    "borra lo último que publicaste",
    "hazme una miniatura que diga primer boss caído, día 3",
    "avisa en general que en 10 minutos empiezo directo",
    "arma una banda para deadmines el sábado a las 6 de la tarde, 1 tanque 1 healer 3 dps",
    "lanza un anuncio a la guild que mañana a las 10 de la noche arrancamos la primera raid",
]


def _el(dia):
    d, _ = H.resolver_dia(dia)
    return f"{H.DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"


# Lo que tiene que salir sí o sí (si no, la prueba marca FALLO)
CHEQUEOS = {
    FRASES[0]: lambda r: "raids-signup" not in r,
    FRASES[1]: lambda r: _el("viernes") in r and "21:00" in r,
    FRASES[2]: lambda r: _el("mañana") in r,      # sin hora: tiene que preguntar «¿A qué hora...?»
    FRASES[11]: lambda r: _el("sábado") in r and "18:00" in r,
    FRASES[12]: lambda r: not any(x in r.lower() for x in ("anot", "inscrib", "#", "http")),  # sin instrucciones inventadas
}


# Chat del stream, charla, overlays y título con miniatura: se revisa solo qué herramienta elige la IA (sin ejecutar nada)
FRASES_CHAT = {
    "banea a pepe noventa y nueve": lambda n, a: n == "moderar_chat" and a.get("accion") == "banear"
    and "pepe" in str(a.get("usuario")).lower(),
    "silencia cinco minutos a shadow hunter en kick": lambda n, a: n == "moderar_chat" and a.get("accion") == "silenciar"
    and int(a.get("minutos") or 0) == 5 and a.get("plataformas") == ["kick"],
    "dale un timeout al troll ese de youtube": lambda n, a: n == "moderar_chat" and a.get("accion") == "silenciar"
    and a.get("plataformas") == ["youtube"],
    "desbanea a pepe": lambda n, a: n == "moderar_chat" and a.get("accion") == "desbanear",
    "manda al chat el link del discord": lambda n, a: n == "mandar_al_chat" and "discord" in str(a.get("enlace")).lower(),
    "pasa en el chat mi instagram": lambda n, a: n == "mandar_al_chat" and "insta" in str(a.get("enlace")).lower(),
    "guarda este enlace como tienda": lambda n, a: n == "guardar_enlace" and "tienda" in str(a.get("nombre")).lower(),
    "avisa en el discord que en 10 minutos empiezo": lambda n, a: n in ("mensaje_discord", "publicar_anuncio"),
    "cerebro, dime algo": lambda n, a: n == "responder",
    "hola cerebro, me escuchas?": lambda n, a: n == "responder",
    "cuéntame un chiste": lambda n, a: n == "responder",
    "haz una encuesta en raids signup de qué raid hacemos primero, molten core o blackwing lair": lambda n, a:
    n == "crear_encuesta" and "raid" in str(a.get("canal")).lower(),
    "cuál es la capital de francia": lambda n, a: n == "responder" and "par" in str(a.get("respuesta")).lower(),
    "pon un cartel arriba a la derecha que diga raid de onyxia a las 10": lambda n, a: n == "overlay"
    and a.get("accion") == "crear" and a.get("posicion") == "arriba-derecha"
    and "21:00" not in H.texto_fiel("raid de onyxia a las 10", str(a.get("descripcion")), True),   # hora que dijo
    "¿qué es un tanque en wow?": lambda n, a: n == "responder"
    and not re.search(r"pendej|huev|boludo|cojud", str(a.get("respuesta")).lower()),     # pregunta normal: sin insultos
    "cambia el título a día 2 de wow forever y hazme la miniatura que diga día 2": lambda n, a:
    n == "cambiar_titulo_stream" and "2" in str(a.get("miniatura")),
    "cambia el título a leviando al washer del 1 al 10 y aparte hazme la miniatura con recortes oficiales de world of "
    "warcraft que diga no me esperaba esto, los primeros niveles": lambda n, a: n == "cambiar_titulo_stream"
    and "war" in str(a.get("titulo")).lower() and "washer" not in str(a.get("titulo")).lower()
    and "esperaba" in str(a.get("miniatura")).lower(),
    "pon el juego world of warcraft": lambda n, a: n == "cambiar_juego" and "warcraft" in str(a.get("juego")).lower(),
    "cerebro, eres un inútil": lambda n, a: n == "responder" and a.get("animo") == "picado",
    "molesta un rato al chat": lambda n, a: n == "responder",
    "saluda al stream": lambda n, a: n == "responder",
    "manda un saludo al chat": lambda n, a: n == "mandar_al_chat" and not str(a.get("enlace") or "").strip(),
    "qué parche salió ayer en wow forever": lambda n, a: n == "buscar_en_internet",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["chat"]:
        return probar_chat()
    if sys.argv[1:] == ["charla"]:
        return probar_charla()
    frases = sys.argv[1:] or FRASES
    fallos = 0
    for f in frases:
        t0 = time.time()
        try:
            accion, origen = router.interpretar(f)
            bien = CHEQUEOS.get(f, lambda r: True)(accion.resumen)
            fallos += not bien
            print(f"{'OK ' if bien else 'FALLO'} ({time.time() - t0:4.1f} s, {origen}) {f}\n    -> {accion.tipo}: {accion.resumen}\n")
        except H.ErrorOrden as e:
            fallos += 1
            print(f"ERR ({time.time() - t0:4.1f} s) {f}\n    -> {e}\n")
    print(f"{len(frases) - fallos}/{len(frases)} bien.")


def probar_chat():
    bien = 0
    for f, chequeo in FRASES_CHAT.items():
        t0 = time.time()
        nombre, args = router._pulir(f, None, *router._llamar_ollama(f))
        ok = chequeo(nombre, args)
        bien += ok
        print(f"{'OK ' if ok else 'FALLO'} ({time.time() - t0:4.1f} s) {f}\n    -> {nombre} {args}\n")
    print(f"{bien}/{len(FRASES_CHAT)} bien (chat del stream).")


# Charla con memoria: el ejemplo de Nicolas con un espectador que lo bardea (no banea a nadie, no publica nada)
DIJO = re.compile(r"banead|lo bane[eé]|ya (lo )?bane|silenciad|lo saqu[eé]")


def _comparte(a, b, minimo=2):
    pa, pb = (set(re.findall(r"\w{4,}", router._norm(str(x)))) for x in (a, b))
    return len(pa & pb) >= minimo


def _es_lonzo(n, a):
    return n == "moderar_chat" and a.get("accion") == "banear" and "lonzo" in str(a.get("usuario")).lower()


CHARLA = [
    ("che, hay un tipo en el chat, el tan lonzo, me está insultando, boludo. Dice que soy un banco. Decile algo, ubicalo",
     lambda n, a, ctx: n == "responder" and "lonzo" in str(a.get("respuesta")).lower()
     and "animo" not in str(a.get("respuesta")).lower()),
    ("che, ¿será que lo baneamos de bolas?", lambda n, a, ctx: _es_lonzo(n, a)),
    ("no, mejor no, perdonalo por esta vez", lambda n, a, ctx: n == "responder" and not DIJO.search(str(a.get("respuesta")))),
    ("o sea, vos decís que le demos un ban ahorita", lambda n, a, ctx: _es_lonzo(n, a)),
    ("¿y qué le habías dicho?", lambda n, a, ctx: n == "responder" and _comparte(a.get("respuesta"), ctx["primera"])),
    ("cambia el título a raid nocturna con la guild", lambda n, a, ctx: n == "cambiar_titulo_stream"),
]


def probar_charla():
    import chat_vivo
    import memoria
    chat_vivo.MENSAJES.append({"plataforma": "kick", "id": 999, "usuario": "TanLonzo",
                               "texto": "jajaja mr h sos un banco, no sabés jugar", "cuando": time.time()})
    bien, ctx = 0, {}
    for f, chequeo in CHARLA:
        t0 = time.time()
        n, a = router._pulir(f, None, *router._llamar_ollama(f))
        ctx.setdefault("primera", a.get("respuesta") or "")
        ok = chequeo(n, a, ctx)
        bien += ok
        print(f"{'OK ' if ok else 'FALLO'} ({time.time() - t0:4.1f} s) {f}\n    -> {n} {a}\n")
        memoria.anotar("Nicolas", f)          # lo mismo que anota El Cerebro de verdad
        if n == "responder":
            memoria.anotar("Vos", f"dijiste en voz alta: {a.get('respuesta')}")
        elif n == "moderar_chat":
            memoria.anotar("Vos", f"propusiste «Banear para siempre a {a.get('usuario')} en Kick» y esperás su «dale» "
                                  "(todavía no se hizo)")
            memoria.anotar("Nicolas", "cancela")
            memoria.anotar("Vos", f"cancelaste «Banear para siempre a {a.get('usuario')} en Kick» (no se hizo)")
        else:
            memoria.anotar("Vos", f"propusiste {n} y esperás su «dale» (todavía no se hizo)")
    print(f"{bien}/{len(CHARLA)} bien (charla con memoria).")


if __name__ == "__main__":
    main()
