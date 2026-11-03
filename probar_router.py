"""Prueba El Cerebro con frases reales SIN publicar nada.

  python probar_router.py           -> órdenes de Discord, raids y títulos (con la IA local)
  python probar_router.py chat      -> chat del stream, charla, overlays (con la IA)
  python probar_router.py charla    -> charla con memoria (el ejemplo de tanlonzo)
  python probar_router.py flujo     -> orden + «dale»/«no» como en vivo, todo simulado
  python probar_router.py rapido    -> sí/no, canales, plataformas y dictado (sin la IA, al instante)
  python probar_router.py todo      -> todo lo anterior
"""
import re
import sys
import time

import dictado
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
    "mandá un aviso de write para registrarse a la raid de molten core de mañana a las 9 con 40 cupos",
    "Ya mira, lo apreté. Lanzá un registro de write sin app para onyxia el sábado a las 9",
    "avisá en el canal Rising Up que hoy a las 9 hacemos raid",
    "mandes un registro de raid para hoy a las 9 de la noche con 40 cupos y en notas pone que todos tienen que estar previstos",
    "mandá un registro de raid de molten core para mañana a las 9, 40 cupos, en notas poné que vengan pre bis",
    "aviso de raid molten core mañana a las 9 con 40 cupos",
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
    # Registro de raid = SIEMPRE crear_raid (el de Hogger con cupos), nunca un anuncio; lo que no dijo, lo pregunta
    FRASES[13]: lambda r: r.startswith("Raid Molten Core") and "21:00" in r and "40 cupos" in r,
    FRASES[14]: lambda r: r.startswith("¿Cuántos cupos") and "Onyxia" in r,
    FRASES[15]: lambda r: r.startswith("¿Qué raid es?"),
    FRASES[16]: lambda r: r.startswith("¿Qué raid es?"),               # no dijo qué raid: no inventa «Molten Core»
    FRASES[17]: lambda r: r.startswith("Raid Molten Core") and "40 cupos" in r and "pre-BiS" in r,
    FRASES[18]: lambda r: r.startswith("Raid Molten Core") and "40 cupos" in r,
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
    "manda el link de youtube a mi canal de kick": lambda n, a: n == "mandar_al_chat" and a.get("plataformas") == ["kick"],
    "mandá un saludo solo al chat de youtube": lambda n, a: n == "mandar_al_chat" and a.get("plataformas") == ["youtube"],
    "un aviso para la guild que hoy hacemos raid, en el canal donde hacen los registros": lambda n, a: n == "crear_raid",
    "mandá un registro de raid de onyxia para el sábado a las 9 con 20 cupos": lambda n, a: n == "crear_raid",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    modos = {"chat": probar_chat, "charla": probar_charla, "flujo": probar_flujo, "rapido": probar_rapido,
             "todo": probar_todo}
    if sys.argv[1:2] and sys.argv[1] in modos:
        bien, total = modos[sys.argv[1]]()
        return 0 if bien == total else 1
    return probar_general(sys.argv[1:])


def probar_general(frases=None):
    frases = frases or FRASES
    fallos = 0
    for f in frases:
        t0 = time.time()
        try:
            accion, origen = router.interpretar(dictado.limpiar(f))      # igual que en vivo: primero se arregla el dictado
            bien = CHEQUEOS.get(f, lambda r: True)(accion.resumen)
            fallos += not bien
            print(f"{'OK ' if bien else 'FALLO'} ({time.time() - t0:4.1f} s, {origen}) {f}\n    -> {accion.tipo}: {accion.resumen}\n")
        except H.ErrorOrden as e:
            fallos += 1
            print(f"ERR ({time.time() - t0:4.1f} s) {f}\n    -> {e}\n")
    print(f"{len(frases) - fallos}/{len(frases)} bien.")
    return len(frases) - fallos, len(frases)


def probar_chat():
    bien = 0
    for f, chequeo in FRASES_CHAT.items():
        t0 = time.time()
        d = dictado.limpiar(f)
        nombre, args = router._pulir(d, None, *router._llamar_ollama(d))
        ok = chequeo(nombre, args)
        bien += ok
        print(f"{'OK ' if ok else 'FALLO'} ({time.time() - t0:4.1f} s) {f}\n    -> {nombre} {args}\n")
    print(f"{bien}/{len(FRASES_CHAT)} bien (chat del stream).")
    return bien, len(FRASES_CHAT)


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
    return bien, len(CHARLA)


# ---------------------------------------------------------------- sin IA: al instante
SI_NO = {
    "Dale.": "confirmar", "Daleh.": "confirmar", "Dalee.": "confirmar", "Sí": "confirmar", "Sí, dale": "confirmar",
    "claro": "confirmar", "de una": "confirmar", "bueno": "confirmar", "sale": "confirmar", "Dali.": "confirmar",
    "Dalle.": "confirmar", "Bale.": "confirmar", "Simandalo, dale.": "confirmar", "Eh, sí, mandalo, cerebro.": "confirmar",
    "Claro que sí": "confirmar", "Ya, dale": "confirmar", "Siii": "confirmar", "Okey": "confirmar", "publícalo": "confirmar",
    "no": "cancelar", "nel": "cancelar", "mejor no": "cancelar", "No, cancelá todo": "cancelar", "Olvídalo": "cancelar",
    "Claro que no": "cancelar", "Ya no": "cancelar", "Nada, déjalo": "cancelar",
    "no, a las 10": None, "sí, pero solo en kick": None, "no sé": None, "manda al chat el link del discord": None,
    "mejor a las 10": None, "hola": None, "la raid es hoy": None,
}
CANALES = {"Rising Up": "raids-signup", "Raidsingup": "raids-signup", "Raids Sin Up": "raids-signup",
           "registro": "raids-signup", "anuncios": "anuncios-guild", "en vivo": "en-vivo", "memes": "clips-y-memes",
           "guías": "builds-y-guias", "general": "general", "cualquiera": None}
PLATAFORMAS = {"manda el link de youtube a mi canal de kick": ["kick"], "mandá un saludo al chat": [],
               "cambia el título solo en kick a raid nocturna": ["kick"], "mandá al chat de kick y youtube": ["kick", "youtube"],
               "mandá al chat mi link de youtube": []}
DICTADO = {"Zul'Aman, Zul'Aman, Zul'Aman, Zul'Aman, Zul'Aman, Zul'Aman.": "",
           "mandá un aviso de write para registrarse": "mandá un aviso de raid para registrarse",
           "para el canal Rising Up": "para el canal raids-signup", "Gracias por ver el video": "",
           "dale dale dale": "dale"}


def probar_rapido():
    casos = []
    casos += [(f"sí/no «{t}»", router.es_confirmacion(t), e) for t, e in SI_NO.items()]
    casos += [("banear con «ya» solo (no alcanza)", router.es_confirmacion("ya", estricto=True), None),
              ("banear con «dale»", router.es_confirmacion("dale", estricto=True), "confirmar")]
    casos += [(f"canal «{t}»", H.buscar_canal(t), e) for t, e in CANALES.items()]
    casos += [(f"plataformas «{t}»", router.plataformas_dichas(t), e) for t, e in PLATAFORMAS.items()]
    casos += [(f"dictado «{t[:40]}»", dictado.limpiar(t), e) for t, e in DICTADO.items()]
    casos += [("sin «sí» en el mensaje", router.quitar_afirmacion("Simandalo https://discord.gg/x"), "https://discord.gg/x")]
    casos += [("no inventa la raid", H.raid_dicha("mandes un registro de raid para hoy con 40 cupos", "Molten Core"), False),
              ("«molten cor» es Molten Core", H.raid_dicha("registro de molten cor", "Molten Core"), True),
              ("«zul gurub» es Zul'Gurub", H.raid_dicha("registro de zul gurub", "Zul'Gurub"), True),
              ("«con 40 cupos»", H.cupos_dichos("hoy a las 9 con 40 cupos"), 40),
              ("sin cupos", H.cupos_dichos("hoy a las 9"), None),
              ("«estar previstos» = pre-BiS", dictado.limpiar("tienen que estar previstos"), "tienen que estar pre-BiS"),
              ("«está previsto» queda igual", dictado.limpiar("está previsto para las 9"), "está previsto para las 9")]
    bien = 0
    for nombre, salio, esperado in casos:
        ok = salio == esperado
        bien += ok
        if not ok:
            print(f"FALLO {nombre}: salió {salio!r}, tenía que ser {esperado!r}")
    print(f"{bien}/{len(casos)} bien (rápidas, sin IA).")
    return bien, len(casos)


# ---------------------------------------------------------------- flujo completo, simulado
def probar_flujo():
    """Orden + respuesta como en vivo (sin tecla), con el Cerebro en modo simulado: no publica nada."""
    import acciones
    import cerebro
    import chat_vivo
    import memoria
    callar = lambda *a, **k: None                    # noqa: E731
    acciones.log = cerebro.log = lambda t: print(f"    [log] {t}")      # no ensucia historial.log
    cerebro.pitido = callar
    chat_vivo.MENSAJES.append({"plataforma": "kick", "id": 998, "usuario": "TanLonzo", "texto": "sos un banco",
                               "cuando": time.time()})
    vistos = []
    c = cerebro.Cerebro(lambda t, tipo="info", s=0: vistos.append(str(t)), simular=True)

    def pendiente(tipo, **datos):
        p = c.pendiente
        return bool(p) and p.tipo == tipo and all(p.datos.get(k) == v for k, v in datos.items())

    def hecho():
        return not c.pendiente and any("simulado" in v for v in vistos[-2:])

    pasos = [
        ("mandá un saludo al chat de kick", lambda: pendiente("chat", plataformas=["kick"])),
        ("Daleh.", hecho),
        ("mandá un aviso de write para registrarse a la raid de onyxia del sábado a las 9 con 40 cupos",
         lambda: pendiente("hogger", accion="raid", nombre="Onyxia", cupo=40)),
        ("mejor no", lambda: not c.pendiente),
        ("mandes un registro de raid para mañana a las 9 de la noche con 40 cupos", lambda: not c.pendiente and c.contexto
         and "qué raid" in vistos[-1].lower()),                       # no dijo qué raid: pregunta, no inventa
        ("molten core", lambda: pendiente("hogger", accion="raid", nombre="Molten Core", cupo=40)),
        ("no", lambda: not c.pendiente),
        ("cambiá el título solo en kick a raid nocturna con la guild", lambda: pendiente("titulo", plataformas=["kick"])),
        ("Simandalo, dale.", hecho),
        ("banea a tanlonzo", lambda: pendiente("moderar", accion="banear")),
        ("ya", lambda: pendiente("moderar", accion="banear")),            # para banear, «ya» solo no alcanza
        ("sí, dale, banealo", hecho),
        ("avisá en el discord que en 10 minutos arranco", lambda: pendiente("hogger", accion="mensaje")),
        ("no, mejor que sea en 20 minutos", lambda: pendiente("hogger", accion="mensaje")
         and "20" in str(c.pendiente.datos.get("texto"))),
        ("de una", hecho),
    ]
    bien = 0
    for f, chequeo in pasos:
        t0 = time.time()
        d = dictado.limpiar(f)
        if c.pendiente or c.contexto:
            c.respuesta(d)               # como en vivo: después de «¿Lo publico?» o «¿Qué raid?» te escucha sin tecla
        else:
            c.manejar_texto(d)
        ok = chequeo()
        bien += ok
        estado = f"esperando «dale»: {c.pendiente.resumen.splitlines()[0]}" if c.pendiente else (vistos[-1] if vistos else "")
        print(f"{'OK ' if ok else 'FALLO'} ({time.time() - t0:4.1f} s) {f}\n    -> {estado}\n")
    memoria.olvidar()
    print(f"{bien}/{len(pasos)} bien (flujo completo, simulado).")
    return bien, len(pasos)


def probar_todo():
    import memoria
    resultados = []
    for nombre, f in (("rápidas", probar_rapido), ("Discord y títulos", probar_general), ("chat", probar_chat),
                      ("flujo", probar_flujo), ("charla", probar_charla)):
        print(f"\n========== {nombre} ==========")
        memoria.olvidar()
        resultados.append((nombre, *f()))
    print("\n========== RESUMEN ==========")
    for nombre, bien, total in resultados:
        print(f"{'OK ' if bien == total else 'FALLO'} {nombre}: {bien}/{total}")
    return sum(b for _, b, _ in resultados), sum(t for _, _, t in resultados)


if __name__ == "__main__":
    sys.exit(main())
