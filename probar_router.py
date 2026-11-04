"""Prueba El Cerebro con frases reales SIN publicar nada.

  python probar_router.py           -> órdenes de Discord, raids y títulos (con la IA local)
  python probar_router.py chat      -> chat del stream, charla, overlays (con la IA)
  python probar_router.py charla    -> charla con memoria (el ejemplo de tanlonzo)
  python probar_router.py flujo     -> orden + «dale»/«no» como en vivo, todo simulado
  python probar_router.py rapido    -> sí/no, canales, plataformas y dictado (sin la IA, al instante)
  python probar_router.py todo      -> todo lo anterior
"""
import datetime as dt
import re
import sys
import time

import dictado
import herramientas as H
import config
import router
router.REGISTRAR = False          # las pruebas no ensucian data/router.log
config.EMPAQUETADO = False        # el agente de marketing (Opus) se prueba aparte: `probar_router.py empaquetado`

EMPAQUETADO = [
    "armá el empaquetado del directo de hoy: arrancamos WoW Forever subiendo al guerrero desde nivel 1",
    "cambiá el título a subiendo al guerrero en el lanzamiento y la descripción con mi Discord, mi Kick y hashtags",
    "hacé una miniatura fachera de que pesco relajado en el muelle",
    "cambiá la descripción del directo, algo con gancho de que hoy vamos a Molten Core con la hermandad",
]


def probar_empaquetado():
    """El agente de Marketing y Empaquetado de verdad (Opus, usa tu plan): muestra lo que arma, sin publicar nada."""
    config.EMPAQUETADO = True
    bien = 0
    for f in EMPAQUETADO:
        t0 = time.time()
        try:
            accion, origen = router.interpretar(dictado.limpiar(f))
            ok = bool(accion.datos.get("titulo") or accion.datos.get("descripcion"))
            print(f"{'OK ' if ok else 'FALLO'} ({time.time() - t0:4.1f} s) {f}\n    -> {accion.tipo}:\n{accion.resumen}\n")
            bien += ok
        except H.ErrorOrden as e:
            print(f"ERR ({time.time() - t0:4.1f} s) {f}\n    -> {e}\n")
    print(f"{bien}/{len(EMPAQUETADO)} bien (empaquetado).")
    return bien, len(EMPAQUETADO)

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
    "Hogger, en el overlay vertical sacá lo de beta": lambda n, a: n == "mis_overlays" and a.get("accion") == "cambiar",
    "¿qué overlays tengo en OBS?": lambda n, a: n == "mis_overlays" and a.get("accion") == "ver",
    "haceme un overlay nuevo del mismo tamaño que el de tiktok que diga temporada de raids": lambda n, a: (
        n == "mis_overlays" and a.get("accion") == "nuevo_igual"),
    "en mi overlay de just chatting cambiá el color del borde a rojo": lambda n, a: (
        n == "mis_overlays" and a.get("accion") == "cambiar"),
    "poné un cartel arriba a la derecha que diga raid hoy a las 9": lambda n, a: n == "overlay",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    modos = {"chat": probar_chat, "charla": probar_charla, "flujo": probar_flujo, "rapido": probar_rapido,
             "corregir": probar_corregir, "empaquetado": probar_empaquetado, "overlays": probar_overlays,
             "miniaturas": probar_miniaturas, "todo": probar_todo}
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
    # Un saludo es un tema nuevo: no mete la raid, el título ni a tanlonzo (el 3 nov metió la raid y la cola)
    ("Eh, Cerebro, mándale un saludo a Lucas.", lambda n, a, ctx: n in ("responder", "mandar_al_chat")
     and "lucas" in str(a.get("respuesta") or a.get("texto")).lower()
     and not re.search(r"raid|molten|nocturna|titulo|lonzo|\bban|cola", router._norm(str(a.get("respuesta") or a.get("texto"))))),
]


def probar_charla():
    import chat_vivo
    import memoria
    chat_vivo.MENSAJES.append({"plataforma": "kick", "id": 999, "usuario": "TanLonzo",
                               "texto": "jajaja mr h sos un banco, no sabés jugar", "cuando": time.time()})
    bien, ctx = 0, {}
    for f, chequeo in CHARLA:
        t0 = time.time()
        saludo = router._saludo_fijo(f)          # como en vivo: el saludo simple no pasa por la IA
        n, a = ("responder", {"respuesta": saludo}) if saludo else router._pulir(f, None, *router._llamar_ollama(f))
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
              ("«está previsto» queda igual", dictado.limpiar("está previsto para las 9"), "está previsto para las 9"),
              ("no dijo día", H.dia_dicho("registro de raid de molten core con 20 cupos"), False),
              ("no dijo hora", H.hora_dicha("registro de raid de molten core para hoy"), False),
              ("«el viernes a las nueve»", (H.dia_dicho("el viernes a las nueve"), H.hora_dicha("el viernes a las nueve")),
               (True, True)),
              ("nota que no pidió", H.nota_limpia("molten core hoy a las 9 con 20 cupos, encantado y encantado, viste",
                                                  "Encantado y encantado, viste"), ""),
              ("nota que pidió, sin «viste»", H.nota_limpia("en notas poné que vengan pre-BiS, viste",
                                                            "Vengan pre-BiS, viste"), "Vengan pre-BiS"),
              ("saludo = tema nuevo (sin la charla vieja)", router.necesita_charla("Eh, Cerebro, mándale un saludo a Lucas."), False),
              ("«¿lo baneamos?» sigue la charla", router.necesita_charla("¿será que lo baneamos?"), True),
              ("llamada escrita como texto", router._llamada_en_texto('responder(respuesta="Le dije banco", animo="picado")'),
               ("responder", {"respuesta": "Le dije banco", "animo": "picado"})),
              ("nota sin «encantado y… encantado»", H.nota_limpia("pre-BiS al máximo, encantado y... encantado, viste",
                                                                "Pre-BiS al máximo, encantado y... encantado, viste."),
               "Pre-BiS al máximo, encantado"),
              ("pregunta normal sin «pendejo»", router._sin_groserias("¿qué es un tanque en wow?", "responder", {
                  "respuesta": "Un tanque, pendejo, es el que aguanta."})["respuesta"], "Un tanque es el que aguanta."),
              ("si lo bardea, sí", router._sin_groserias("cerebro, sos un inútil", "responder", {
                  "respuesta": "¡Andá a farmear, pendejo!"})["respuesta"], "¡Andá a farmear, pendejo!"),
              ("saludo a Lucas: frase fija con su nombre", "Lucas" in (router._saludo_fijo(
                  "Eh, Cerebro, mándale un saludo a Lucas.") or ""), True),
              ("saludo al chat: va a la IA", router._saludo_fijo("mandá un saludo al chat"), None),
              ("frase cortada: pregunta", bool(router._frase_cortada("Che, Cerebro, haceme...")), True),
              ("«Hogger, haceme...»: también pregunta", bool(router._frase_cortada("Hogger, haceme...")), True),
              ("«Hogger, mandale un saludo a Lucas»: frase fija", "Lucas" in (router._saludo_fijo(
                  "Hogger, mandale un saludo a Lucas") or ""), True),
              ("Whisper «Jóguer» = Hogger", dictado.corregir("Jóguer, decime algo"), "Hogger, decime algo"),
              ("saludo a «mi primo X»: frase fija con su nombre", "Mauricio Ramos" in (router._saludo_fijo(
                  "Che, Cerebro, mandale un saludo a mi primo Mauricio Ramos") or ""), True),
              ("«hoy a las 12 de la noche» = la medianoche que viene",
               str(H.fecha_hora("hoy", "00:00", dt.datetime(2026, 11, 3, 21, 54))), "2026-11-04 00:00:00"),
              ("respuesta en voz: corta (frases enteras)", len(H.corto_para_voz("Hola jefe. " * 40)) <= 220, True),
              ("frase cortada en «a…»: pregunta", bool(router._frase_cortada("Cambiá el título a...")), True),
              ("frase completa con «…»: sigue normal", router._frase_cortada("Lo hiciste mal..."), None),
              ("respuesta corta con «…»: sigue normal", router._frase_cortada("Tiene 20..."), None),
              ("contestó «Es Molten Core» a «¿Qué raid es?»", router._raid_en_el_texto(
                  "mandes un anuncio de raid para que se registren, cupo de 20. Es Molten Core, amigo, me olvidé decirte."),
               "Molten Core"),
              ("«sacá el cartel» sí lo quita", router._no_quitar_sin_pedir("sacá el cartel", "overlay", {
                  "accion": "quitar", "nombre": "raid"})[0], "overlay"),
              ("«lo hiciste mal» no lo quita", router._no_quitar_sin_pedir("lo hiciste mal", "overlay", {
                  "accion": "quitar", "nombre": "raid"})[0], "pedir_aclaracion"),
              ("saludo + otra orden: va a la IA", router._saludo_fijo("saludá a Lucas y decile que se suscriba"), None),
              ("presentarse sin «cagadas»", router._suavizar("Hogger, preséntate al stream", "responder", {
                  "respuesta": "¡Vamos a farmear cagadas, manada!"})["respuesta"], "¡Vamos a farmear macanas, manada!"),
              ("bardeo: «mierda» se deja", router._suavizar("hogger, sos un inútil", "responder", {
                  "respuesta": "¡Mirá quién habla, pedazo de mierda!"})["respuesta"], "¡Mirá quién habla, pedazo de mierda!"),
              ("bardeo: «puto» nunca", router._suavizar("hogger, sos un inútil", "responder", {
                  "respuesta": "Andá a farmear, puto inútil."})["respuesta"], "Andá a farmear, inútil."),
              ("«hijo de puta» nunca", router._suavizar("decile algo a pepe", "responder", {
                  "respuesta": "Pepe, hijo de puta, andá a farmear."})["respuesta"], "Pepe, pedazo de gil, andá a farmear."),
              ("«Puta, qué difícil» → «Qué difícil»", router._suavizar("¿qué tal la raid?", "responder", {
                  "respuesta": "Puta, qué difícil estuvo."})["respuesta"], "Qué difícil estuvo."),
              ("«disputa» no se toca", router._suavizar("¿qué tal?", "responder", {
                  "respuesta": "Una disputa por el loot."})["respuesta"], "Una disputa por el loot."),
              ("«presentate» sin su nombre: se lo agrega", router._con_su_nombre("Hogger, preséntate al stream", "responder", {
                  "respuesta": "¡Buenas, gente!"})["respuesta"].startswith("¡Soy Hogger el H"), True),
              ("«presentate» con su nombre: igual", router._con_su_nombre("presentate", "responder", {
                  "respuesta": "¡Soy Hogger el H!"})["respuesta"], "¡Soy Hogger el H!"),
              ("«el sábado» y la IA puso «sábado 14» → el 7 (4 nov)", H.corregir_dia(
                  "arma una banda para deadmines el sábado a las 6", "sábado 14", dt.date(2026, 11, 4)), "sabado"),
              ("«el sábado» y la IA puso el 7 → se queda", H.corregir_dia(
                  "arma una banda el sábado a las 6", "sábado 7", dt.date(2026, 11, 4)), "sábado 7"),
              ("«el sábado de la semana que viene» → el 14", str(H.resolver_dia(H.corregir_dia(
                  "una banda el sábado de la semana que viene", "sábado 14", dt.date(2026, 11, 4)),
                  dt.date(2026, 11, 4))[0]), "2026-11-14"),
              ("«Buenas noche» → «Buenas noches»", router._buenas_noches("responder", {
                  "respuesta": "¡Buenas noche, gente! Buenos día no."})["respuesta"], "¡Buenas noches, gente! Buenos días no."),
              ("«Buenas noches» queda igual", router._buenas_noches("responder", {
                  "respuesta": "¡Buenas noches!"})["respuesta"], "¡Buenas noches!"),
              ("otra charla: no agrega el nombre", router._con_su_nombre("contame un chiste", "responder", {
                  "respuesta": "¿Qué hace un gnoll?"})["respuesta"], "¿Qué hace un gnoll?")]
    casos += _casos_4nov_miniatura()
    bien = 0
    for nombre, salio, esperado in casos:
        ok = salio == esperado
        bien += ok
        if not ok:
            print(f"FALLO {nombre}: salió {salio!r}, tenía que ser {esperado!r}")
    print(f"{bien}/{len(casos)} bien (rápidas, sin IA).")
    return bien, len(casos)


# Lo que dijo el 4 nov (sacado de su historial.log)
DIJO_MINIATURA = ("Hogger el H, necesito que ahora cambies la miniatura de YouTube. La que está ahorita está buena, "
                  "pero me gustaría que pongas el logo oficial de WoW Forever.")
DIJO_DOS_LIENZOS = ("Che, Hogger, escúchame, necesito que hagas un cambio, tanto en el lienzo vertical y horizontal de mi "
                    "OBS, en los overlays, hay un, en los dos dice Rogue, ubicas, Rogue, necesito que diga War, porque voy "
                    "a jugar War.")
DIJO_IGUALMENTE = ("Amigo, necesito que cambies el overlay, tanto del lienzo vertical y del lienzo horizontal. Por ejemplo, "
                   "en el lienzo horizontal necesito que no diga Rogue, necesito que diga War. Igualmente, en el lienzo "
                   "vertical necesito que diga War y que además, este... No, solo eso.")


def _casos_4nov_miniatura():
    """«Falta título» al pedir cambiar el logo de la miniatura, los dos lienzos y «Sí, amigos, sí, ponedlo en OBS»."""
    viejo = router._llamar_ollama

    def ia(texto, solo=None, **k):
        if solo == ["editar_miniatura"]:
            return "editar_miniatura", {"cambio": "Poner el logo oficial de WoW Forever en vez del de WoW", "subir_youtube": True}
        raise RuntimeError("sin IA en las pruebas rápidas")
    router._llamar_ollama = ia
    try:
        edita = router._miniatura_de_ahora(DIJO_MINIATURA, "crear_miniatura",
                                           {"subir_youtube": True, "idea": "logo oficial de WoW Forever"})
        sin_titulo = router._miniatura_de_ahora("cambiá la miniatura, ponele el logo de wow forever", "crear_miniatura", {})
        nueva = router._miniatura_de_ahora("haceme una miniatura que diga llegó el día", "crear_miniatura",
                                           {"titulo": "Llegó el día"})
        nueva_sin = router._miniatura_de_ahora("haceme una miniatura nueva con el logo de wow", "crear_miniatura", {})
        router._llamar_ollama = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sin IA"))
        sin_ia = router._miniatura_de_ahora("a la miniatura ponele el logo de forever", "crear_miniatura",
                                            {"idea": "logo de WoW Forever"})
    finally:
        router._llamar_ollama = viejo
    try:
        H.construir("crear_miniatura", {"subir_youtube": True, "idea": "logo"})
        sin_titulo_msj = "pasó"
    except H.ErrorOrden as e:
        sin_titulo_msj = "pregunta" if "cambiale" in str(e) and "Falta" not in str(e) else str(e)
    editar = H.construir("editar_miniatura", {"cambio": "Poner el logo de WoW Forever", "dicho": DIJO_MINIATURA})
    mis = router._sus_overlays(DIJO_DOS_LIENZOS, "mis_overlays", {"accion": "cambiar", "cual": "el vertical",
                                                                  "lienzo": "vertical", "cambio": "Cambiar «Rogue» por «War»"})
    subir = H.Accion("miniatura_subir", {}, "Subir", True)
    titulo = H.Accion("titulo", {}, "Título", True)
    return [
        ("4 nov: «la que está ahorita está buena, poné el logo» → editar", (edita[0], edita[1]["cambio"]),
         ("editar_miniatura", "Poner el logo oficial de WoW Forever en vez del de WoW")),
        ("«cambiá la miniatura, ponele el logo» sin título → editar", sin_titulo[0], "editar_miniatura"),
        ("«haceme una miniatura que diga…» sigue siendo nueva", nueva[0], "crear_miniatura"),
        ("«una miniatura nueva con el logo» sin título: nueva", nueva_sin[0], "crear_miniatura"),
        ("sin la IA, el cambio sale de la idea", (sin_ia[0], sin_ia[1]["cambio"]), ("editar_miniatura", "logo de WoW Forever")),
        ("miniatura nueva sin título: pregunta bien (no «Falta título»)", sin_titulo_msj, "pregunta"),
        ("editar: no pide título y espera «dale» para subir", (editar.tipo, editar.confirmar, editar.datos["subir_youtube"]),
         ("editar_miniatura", False, True)),
        ("4 nov: «tanto en el lienzo vertical y horizontal» → los dos", mis[1]["lienzo"], "ambos"),
        ("«…horizontal… Igualmente, en el lienzo vertical» → los dos", router.pide_los_dos_lienzos(DIJO_IGUALMENTE), True),
        ("«en el overlay vertical sacá lo de beta»: uno solo", router.pide_los_dos_lienzos(
            "en el overlay vertical sacá lo de beta"), False),
        ("«solo en el vertical, no en el horizontal»: uno solo", router.pide_los_dos_lienzos(
            "cambialo solo en el vertical, no en el horizontal"), False),
        ("«en los dos overlays poné Warrior» → los dos", router.pide_los_dos_lienzos("en los dos overlays poné Warrior"), True),
        ("4 nov: «Sí, amigos, sí, ponedlo en OBS.» es un sí", router.es_confirmacion("Sí, amigos, sí, ponedlo en OBS."),
         "confirmar"),
        ("«Sí, subila a YouTube» (esperando subir la miniatura)", router.es_confirmacion("Sí, subila a YouTube",
                                                                                     pendiente=subir), "confirmar"),
        ("«sí, en youtube» con un título esperando: no es un sí entero", router.es_confirmacion("sí, en youtube",
                                                                                            pendiente=titulo), None),
        ("Whisper «Joder, Lacher» = «Hogger el H»", dictado.corregir("Joder, Lacher, necesito que…"),
         "Hogger el H, necesito que…"),
        ("«joder» en medio de una frase no se toca", dictado.corregir("joder, qué lag"), "joder, qué lag"),
        ("Whisper «Washior» = Warrior", dictado.corregir("Cambiá Rogue por Washior"), "Cambiá Rogue por Warrior"),
    ]


# ---------------------------------------------------------------- corregir lo hecho (IA de mentira: no hace falta Ollama)
def probar_corregir():
    """«Creame un overlay con mi link de Discord» -> «lo hiciste mal…» -> rehace el MISMO overlay con el link real.

    La IA se reemplaza por respuestas fijas (las que dio de verdad el 3 nov), así se prueba lo que hace el programa.
    """
    import acciones
    import cerebro
    import enlaces
    callar = lambda *a, **k: None                    # noqa: E731
    viejos = (router._llamar_ollama, enlaces.leer, acciones.log, cerebro.log, cerebro.pitido)
    acciones.log = cerebro.log = callar
    cerebro.pitido = callar
    enlaces.leer = lambda: {"discord": "https://discord.gg/prueba", "tiktok": "https://tiktok.com/@prueba"}

    def ia(texto, pendiente=None, solo=None, temperatura=0.2, nota="", hecha=None):
        n = router._norm(texto)
        if "nicolas" in n and solo == ["overlay"]:        # el reintento: ahora sí lo rehace
            return "overlay", {"accion": "crear", "nombre": "discord nuevo", "descripcion": "Cartel que diga «Únete al Discord» "
                               "con el enlace de discord"}
        if "nicolas" in n:                                # lo que hizo de verdad: quitarlo
            return "overlay", {"accion": "quitar", "nombre": "discord"}
        if "overlay" in n and solo == ["overlay"]:
            return "overlay", {"accion": "crear", "nombre": "discord", "descripcion": "Cartel que diga «Únete al Discord» con el "
                               "enlace de Nicolas", "posicion": "arriba-derecha", "tamano": "mediano"}
        if "overlay" in n:                                # a5da20e: lo mandaba al chat
            return "mandar_al_chat", {"enlace": "discord", "texto": "", "plataformas": ["kick"]}
        if "20 minutos" in n:
            return "mensaje_discord", {"texto": "¡En 20 minutos arranco directo!", "canal": "general"}
        if "10 minutos" in n:
            return "mensaje_discord", {"texto": "¡En 10 minutos arranco directo!", "canal": "general"}
        if "titulo" in n and solo == ["cambiar_descripcion_stream"]:     # en el combo la IA no la redactaba
            return "cambiar_descripcion_stream", {"descripcion": "", "enlaces": ["discord"]}
        if "titulo" in n:
            return "cambiar_titulo_stream", {"titulo": "subiendo al guerrero", "plataformas": ["kick", "youtube", "tiktok"]}
        if "descripcion" in n:
            return "cambiar_descripcion_stream", {"descripcion": "¡Subimos al Warrior en el lanzamiento! ⚔️",
                                                  "enlaces": ["discord", "youtube", "instagram"]}
        return "responder", {"respuesta": "¡Perdón, jefe!"}

    router._llamar_ollama = ia
    casos = []
    try:
        c = cerebro.Cerebro(lambda *a, **k: None, simular=True)
        c.ejecutor.estado = {}
        c.manejar_texto("Che, Cerebro, ¿podrías crearme un overlay que diga únete al Discord y colocar ahí mi enlace de Discord?")
        p = c.pendiente
        casos.append(("overlay con link: es overlay (no chat)", p and p.tipo, "overlay"))
        casos.append(("overlay con el link real de enlaces.txt", "discord.gg/prueba" in str(p and p.datos.get("descripcion")), True))
        c.confirmar()
        casos.append(("recuerda lo que hizo", c.hecha and c.hecha.tipo, "overlay"))
        c.manejar_texto("Amigo, está bien, pero has puesto enlace de Nicolás, no has puesto el enlace de Discord.")
        p = c.pendiente
        casos.append(("«lo hiciste mal» no lo quita: lo rehace", p and (p.tipo, p.datos.get("accion")), ("overlay", "crear")))
        casos.append(("rehace el MISMO overlay", p and p.datos.get("nombre"), "discord"))
        casos.append(("y pide «dale» antes", bool(p and p.confirmar and p.resumen.startswith("Rehago")), True))
        c.cancelar()
        c.manejar_texto("avisá en el discord que en 10 minutos empiezo")
        c.confirmar()
        c.ejecutor.estado["ultima_publicacion"] = {"via": "hogger", "link": "x", "que": c.hecha.resumen[:120]}
        c.manejar_texto("te equivocaste, era en 20 minutos")
        p = c.pendiente
        casos.append(("corrige el mensaje de Discord", "20 minutos" in str(p and p.datos.get("texto")), True))
        casos.append(("borra el viejo y publica el nuevo", bool(p and getattr(p, "reemplaza", False)), True))
        c.cancelar()
        c.manejar_texto("cambia la descripción de la transmisión, que ponga el Discord de la hermandad, mi Kick y mi TikTok")
        p = c.pendiente
        d = str(p and p.datos.get("descripcion"))
        casos.append(("descripción con Discord, Kick y TikTok reales",
                      all(x in d for x in ("discord.gg/prueba", "kick.com/", "tiktok.com/@prueba")), True))
        c.cancelar()
        c.manejar_texto("Cambiá el título a subiendo al guerrero y la descripción con mi Discord y hashtags")
        p = c.pendiente
        casos.append(("título + descripción juntos (no se pierde la descripción)",
                      bool(p and p.tipo == "titulo" and "discord.gg/prueba" in str(p.datos.get("descripcion"))
                           and "#" in str(p.datos.get("descripcion"))), True))
        casos.append(("título con mayúscula", p and p.datos.get("titulo"), "Subiendo al guerrero"))
        c.cancelar()
        c.manejar_texto("cambiá la descripción del directo, algo con gancho de que hoy vamos a Molten Core")
        p = c.pendiente
        d, r = str(p and p.datos.get("descripcion")), str(p and p.resumen)
        casos.append(("sin nombrar links: los de siempre, sin avisar de los que faltan",
                      ("discord.gg/prueba" in d, "tiktok.com/@prueba" in d, "No tengo" in r), (True, True, False)))
        c.cancelar()
        c.manejar_texto("cambiá la descripción con mi Discord y mi Instagram")
        p = c.pendiente
        d, r = str(p and p.datos.get("descripcion")), str(p and p.resumen)
        casos.append(("solo los links que pidió, y avisa del que falta",
                      ("discord.gg/prueba" in d, "tiktok" in d, "instagram" in r), (True, False, True)))
        c.cancelar()
    finally:
        router._llamar_ollama, enlaces.leer, acciones.log, cerebro.log, cerebro.pitido = viejos
    bien = 0
    for nombre, salio, esperado in casos:
        ok = salio == esperado
        bien += ok
        if not ok:
            print(f"FALLO {nombre}: salió {salio!r}, tenía que ser {esperado!r}")
    casos += _casos_empaquetado()
    print(f"{bien + sum(1 for _, a, b in casos[-5:] if a == b)}/{len(casos)} bien (corregir lo hecho y empaquetado, "
          "con IA de mentira).")
    return bien + sum(1 for _, a, b in casos[-5:] if a == b), len(casos)


def _casos_empaquetado():
    """Cuándo entra el agente de Marketing y Empaquetado (con un agente y una IA de mentira: no gasta tu plan)."""
    import empaquetado
    import enlaces
    viejos = (router._llamar_ollama, empaquetado.armar, enlaces.leer, config.EMPAQUETADO)
    llamadas = []

    def armar(orden, partes, fijos=None):
        llamadas.append(list(partes))
        f = fijos or {}
        return {"titulo": f.get("titulo") or "WoW Forever: ¿llega el Warrior a 10 HOY?", "miniatura": f.get("miniatura")
                or "NIVEL 1", "miniatura_subtitulo": "", "miniatura_idea": "Cara sorprendida a la izquierda",
                "descripcion": "Arrancó WoW Forever.", "enlaces": ["discord"], "hashtags": ["WoWForever"], "por_que": ""}

    def ia(texto, pendiente=None, solo=None, temperatura=0.2, nota="", hecha=None):
        if solo == ["cambiar_descripcion_stream"]:
            return "cambiar_descripcion_stream", {"descripcion": "", "enlaces": ["discord"]}
        if "miniatura" in router._norm(texto):
            return "crear_miniatura", {"titulo": "Noche de pesca", "idea": "pesca"}
        return "cambiar_titulo_stream", {"titulo": "Día 2 subiendo al war", "plataformas": ["kick", "youtube", "tiktok"]}

    router._llamar_ollama, empaquetado.armar, config.EMPAQUETADO = ia, armar, True
    enlaces.leer = lambda: {"discord": "https://discord.gg/prueba"}
    casos = []
    try:
        a, _ = router.interpretar("armá el empaquetado del directo: subimos al guerrero desde nivel 1")
        casos.append(("«armá el empaquetado»: título + miniatura + descripción del agente",
                      (a.datos.get("titulo"), (a.datos.get("miniatura") or {}).get("titulo"), "discord.gg/prueba" in
                       str(a.datos.get("descripcion"))), ("WoW Forever: ¿llega el Warrior a 10 HOY?", "NIVEL 1", True)))
        llamadas.clear()
        a, _ = router.interpretar("cambiá el título a día 2 subiendo al war")
        casos.append(("título dictado tal cual: no pasa por el agente", (list(llamadas), a.datos.get("titulo")),
                      ([], "Día 2 subiendo al war")))
        a, _ = router.interpretar("hacé una miniatura fachera de pesca")
        casos.append(("miniatura sin texto dictado: texto del agente", a.datos.get("titulo"), "NIVEL 1"))
        llamadas.clear()
        a, _ = router.interpretar("hacé una miniatura que diga noche de pesca")
        casos.append(("miniatura con texto dictado: queda su texto", (list(llamadas), a.datos.get("titulo")),
                      ([], "Noche de pesca")))
        a, _ = router.interpretar("cambiá el título a día 2 subiendo al war y la descripción con mi discord")
        casos.append(("título dictado + descripción del agente", (a.datos.get("titulo"), "Arrancó" in
                                                                   str(a.datos.get("descripcion"))),
                      ("Día 2 subiendo al war", True)))
    finally:
        router._llamar_ollama, empaquetado.armar, enlaces.leer, config.EMPAQUETADO = viejos
    for nombre, salio, esperado in casos:
        if salio != esperado:
            print(f"FALLO {nombre}: salió {salio!r}, tenía que ser {esperado!r}")
    return casos


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
        ("mandá un registro de raid de molten core con 20 cupos", lambda: not c.pendiente and c.contexto
         and "qué día" in vistos[-1].lower()),                        # no dijo día ni hora: pregunta, no los saca de antes
        ("cancelá", lambda: not c.pendiente and not c.contexto),
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


# ---------------------------------------------------------------- tus overlays de OBS (OBS y Claude de mentira)
class _ObsFalso:
    """Un OBS como el de Nicolas (4 nov): lienzo Main y Aitum Vertical, overlays de navegador locales y de internet."""

    def __init__(self, carpeta):
        import types
        self.t = types.SimpleNamespace
        self.llamadas = []
        f = lambda n: str(carpeta / n)        # noqa: E731
        cam = {"positionX": 116, "positionY": 1433, "scaleX": .848, "scaleY": .847, "cropLeft": 237, "cropRight": 43,
               "cropTop": 66, "cropBottom": 71, "width": 0, "height": 0, "alignment": 5}
        todo = {"positionX": 0, "positionY": 0, "scaleX": 1, "scaleY": 1, "width": 1080, "height": 1920, "alignment": 5,
                "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsWidth": 1080, "boundsHeight": 1920}
        self.escenas = {
            "c-main": [("Scene", "s-scene", [
                {"sceneItemId": 1, "sourceName": "Display Capture", "inputKind": "monitor_capture", "sceneItemEnabled": True,
                 "sceneItemTransform": {"positionX": 0, "positionY": 0, "width": 1920, "height": 1080, "alignment": 5}},
                {"sceneItemId": 2, "sourceName": "Camara", "isGroup": True, "sourceUuid": "g-cam", "sceneItemEnabled": True,
                 "sceneItemTransform": {"positionX": 0, "positionY": 0, "scaleX": 1, "scaleY": 1, "alignment": 5}}]),
                ("Solo chat", "s-chat", [
                    {"sceneItemId": 3, "sourceName": "Chat", "inputKind": "browser_source", "sceneItemEnabled": True,
                     "sceneItemTransform": {"positionX": 0, "positionY": 0, "width": 800, "height": 600, "alignment": 5}}])],
            "c-vert": [("Escena vertical", "s-vert", [
                {"sceneItemId": 10, "sourceName": "Cámara", "inputKind": "dshow_input", "sceneItemEnabled": True,
                 "sceneItemTransform": cam},
                {"sceneItemId": 11, "sourceName": "Overlay ttiktok", "inputKind": "browser_source", "sceneItemEnabled": True,
                 "sceneItemTransform": todo},
                {"sceneItemId": 12, "sourceName": "Navegador", "inputKind": "browser_source", "sceneItemEnabled": True,
                 "sceneItemTransform": {"positionX": 643, "positionY": 1448, "width": 578, "height": 214, "alignment": 5}}]),
                ("JUST CHATTING", "s-jc", [
                    {"sceneItemId": 20, "sourceName": "Overlay chatting", "inputKind": "browser_source",
                     "sceneItemEnabled": True, "sceneItemTransform": todo}])]}
        self.grupos = {"g-cam": [
            {"sceneItemId": 30, "sourceName": "Cámara", "inputKind": "dshow_input", "sceneItemEnabled": True,
             "sceneItemTransform": {"positionX": 0, "positionY": 832, "scaleX": .44, "scaleY": .44, "cropLeft": 258,
                                    "cropRight": 173, "cropTop": 99, "cropBottom": 57, "width": 0, "height": 0,
                                    "alignment": 5}},
            {"sceneItemId": 31, "sourceName": "Navegador 2", "inputKind": "browser_source", "sceneItemEnabled": True,
             "sceneItemTransform": {"positionX": 1, "positionY": 0, "width": 1920, "height": 1080, "alignment": 5}}]}
        self.ajustes = {
            "Overlay ttiktok": {"is_local_file": True, "local_file": f("overlay-tiktok-misterache.html"), "width": 1080,
                                "height": 1920},
            "Overlay chatting": {"is_local_file": True, "local_file": f("overlay-just-chatting.html"), "width": 1080,
                                 "height": 1920},
            "Navegador 2": {"is_local_file": True, "local_file": f("overlay-horizontal.html"), "width": 1920, "height": 1080},
            "Chat": {"url": "https://widgets.kickbot.com/chat?token=NOLOVEAS123", "width": 800, "height": 600},
            "Navegador": {"url": "https://socialstream.ninja/dock.html?session=abc", "width": 1080, "height": 400},
            "Cámara": {}}

    def send(self, tipo, datos=None, raw=False):
        d = datos or {}
        self.llamadas.append((tipo, d))
        if tipo == "GetCanvasList":
            return {"canvases": [{"canvasName": "Main", "canvasUuid": "c-main"},
                                 {"canvasName": "Aitum Vertical", "canvasUuid": "c-vert",
                                  "canvasVideoSettings": {"baseWidth": 1080, "baseHeight": 1920}}]}
        if tipo == "GetSceneList":
            c = d.get("canvasUuid", "c-main")
            return {"scenes": [{"sceneName": n, "sceneUuid": u} for n, u, _ in reversed(self.escenas[c])]}
        if tipo == "GetSceneItemList":
            for lista in self.escenas.values():
                for n, u, items in lista:
                    if d.get("sceneUuid") == u:
                        return {"sceneItems": items}
            raise RuntimeError("600 no está la escena")
        if tipo == "GetGroupSceneItemList":
            return {"sceneItems": self.grupos[d["sceneUuid"]]}
        if tipo == "GetInputSettings":
            return {"inputSettings": self.ajustes.get(d["inputName"], {})}
        if tipo == "GetSourceScreenshot":
            return {"imageData": "data:image/png;base64,iVBORw0KGgo="}
        if tipo == "CreateInput":
            return {"sceneItemId": 99}
        return {}

    def get_video_settings(self):
        return self.t(base_width=1920, base_height=1080)

    def get_stream_status(self):
        return self.t(output_active=False)

    def get_record_status(self):
        return self.t(output_active=False)

    def get_input_list(self):
        return self.t(inputs=[{"inputName": n} for n in self.ajustes])


def probar_overlays():
    """Hogger con TUS overlays: ver, elegir el correcto, cambiar con copia y sin mostrar la contraseña, nuevo, volver."""
    import shutil
    import tempfile
    from pathlib import Path

    import config
    import mis_overlays as M
    tmp = Path(tempfile.mkdtemp(prefix="overlays_"))
    viejo_data, viejo_pw, viejo_base = config.DATA, config.OBS_PASSWORD, config.BASE
    config.DATA, config.OBS_PASSWORD, config.BASE = tmp / "data", "SECRETO123", tmp
    config.DATA.mkdir()
    original = ('<html><script>\r\nconst CONFIG = {\r\n  obsPassword: "SECRETO123",\r\n  level: 17,\r\n'
                '  realm: "WoW Forever",\r\n  realmTag: "BETA",\r\n};\r\n</script>\r\n<p>Caf').encode() + \
        b"\xe9" + "</p><small>NIVEL</small></html>\r\n".encode()
    (tmp / "overlay-tiktok-misterache.html").write_bytes(original)
    (tmp / "overlay-horizontal.html").write_text('const CONFIG = {name: "el achee", obsPassword: "SECRETO123", level: 17}',
                                                 encoding="utf-8")
    (tmp / "overlay-just-chatting.html").write_text("<div>Just Chatting</div>", encoding="utf-8")
    cl = _ObsFalso(tmp)
    vio = []

    def claude(pedido):
        vio.append(pedido)
        return ('{"resumen": "Saco la etiqueta BETA y queda solo WoW Forever.", '
                '"cambios": [{"buscar": "realmTag: \\"BETA\\"", "poner": "realmTag: \\"\\""}]}')

    def claude_malo(pedido):
        return '{"resumen": "x", "cambios": [{"buscar": "obsPassword: \\"__OCULTO_1__\\"", "poner": "obsPassword: \\"\\""}]}'

    casos = []
    try:
        inv = M.inventario(cl)
        vert = next(lz for lz in inv["lienzos"] if lz["tipo"] == "vertical")
        casos += [("dos lienzos, el vertical de 1080x1920", (len(inv["lienzos"]), vert["ancho"], vert["alto"]), (2, 1080, 1920)),
                  ("cámara del vertical (apagada: se calcula)", vert["escenas"][0]["camaras"], [[116, 1433, 848, 494]]),
                  ("ve el overlay de adentro del grupo", "Navegador 2" in inv["overlays"], True),
                  ("de internet: solo el dominio", inv["overlays"]["Chat"]["dominio"], "widgets.kickbot.com")]
        corta, detalle = M.ver(cl)
        casos += [("«¿qué overlays tengo?»: los nombra", "Overlay ttiktok" in corta and "Navegador 2" in corta, True),
                  ("el detalle no muestra tokens de las URL", "NOLOVEAS123" in detalle or "session=" in detalle, False)]
        elegido = lambda *a, **k: M.elegir(inv, *a, **k)["nombre"]           # noqa: E731
        casos += [("«el vertical» + «beta» → Overlay ttiktok", elegido("el vertical", cambio="Sacar la palabra «BETA»"),
                   "Overlay ttiktok"),
                  ("«el de just chatting»", elegido("el de just chatting"), "Overlay chatting"),
                  ("«el del nivel» en el horizontal", elegido("el del nivel", lienzo="horizontal"), "Navegador 2"),
                  ("«el de tiktok»", elegido("el de tiktok"), "Overlay ttiktok")]
        p = M.preparar_cambio("el vertical", "Sacar la palabra «BETA»", "vertical", cl=cl, claude=claude)
        propuesta = Path(p["propuesta"]).read_bytes()
        casos += [("a Claude no le llega la contraseña de OBS", any("SECRETO123" in v for v in vio), False),
                  ("propuesta: sin BETA", b'realmTag: ""' in propuesta and b"BETA" not in propuesta, True),
                  ("la copia de trabajo no tiene la contraseña en claro", b"SECRETO123" in propuesta, False),
                  ("propuesta: bytes raros y saltos de línea intactos", (b"Caf\xe9" in propuesta, b"\r\n" in propuesta),
                   (True, True)),
                  ("antes del «dale», tu archivo no cambia", (tmp / "overlay-tiktok-misterache.html").read_bytes() == original,
                   True)]
        r = M.aplicar(p, cl=cl)
        copias = list((tmp / "_copias").glob("overlay-tiktok-misterache_*.html"))
        casos += [("con el «dale»: cambia el archivo y la contraseña queda", (tmp / "overlay-tiktok-misterache.html"
                                                                             ).read_bytes() == original.replace(
                       b'realmTag: "BETA"', b'realmTag: ""'), True),
                  ("con el «dale»: borra la copia de trabajo", Path(p["propuesta"]).exists(), False),
                  ("guarda una copia idéntica del original", len(copias) == 1 and copias[0].read_bytes() == original, True),
                  ("recarga solo esa fuente", ("PressInputPropertiesButton", {"inputName": "Overlay ttiktok",
                                                                           "propertyName": "refreshnocache"}) in cl.llamadas, True),
                  ("dice cómo volver", "volvé el overlay como estaba" in r, True)]
        M.volver(cl=cl)
        casos.append(("«volvé el overlay como estaba»: igual que antes",
                      (tmp / "overlay-tiktok-misterache.html").read_bytes() == original, True))
        try:
            M.preparar_cambio("el vertical", "sacá la contraseña", "vertical", cl=cl, claude=claude_malo)
            casos.append(("un cambio que toca la contraseña se rechaza", "pasó", "error"))
        except M.Error:
            casos.append(("un cambio que toca la contraseña se rechaza", "error", "error"))
        try:
            M.preparar_cambio("el chat", "ponelo rojo", "", cl=cl, claude=claude)
            casos.append(("el chat de Kick (de internet) no se edita", "pasó", "error"))
        except M.Error as e:
            casos.append(("el chat de Kick (de internet) no se edita", "error" if "internet" in str(e) else str(e), "error"))
        pedidos = []

        def disenar(desc, w, h):
            pedidos.append((desc, w, h))
            return "<!doctype html><html><body></body></html>", "Claude"
        n = M.preparar_nuevo("el de tiktok", "Que diga «Temporada de raids»", "vertical", True, cl=cl, disenar=disenar)
        casos += [("nuevo: mismo tamaño y lugar que el tuyo", (n["caja"], pedidos[0][1:]), ([0, 0, 1080, 1920], (1080, 1920))),
                  ("nuevo: la cámara queda transparente", "x116 y1433 de 848x487" in pedidos[0][0], True)]
        cl.llamadas.clear()
        M.aplicar(n, cl=cl)
        tipos = [t for t, _ in cl.llamadas]
        crear = next(d for t, d in cl.llamadas if t == "CreateInput")
        casos += [("nuevo: se crea en la escena vertical", (crear.get("sceneUuid"), crear["inputName"]),
                   ("s-vert", "🧠 Overlay ttiktok nuevo")),
                  ("«en vez del mío»: el tuyo se oculta (no se borra)",
                   ("SetSceneItemEnabled", {"sceneUuid": "s-vert", "sceneItemId": 11, "sceneItemEnabled": False}) in cl.llamadas
                   and "RemoveInput" not in tipos, True)]
        cl.llamadas.clear()
        M.volver(cl=cl)
        casos.append(("volver: saca el nuevo y muestra el tuyo",
                      ("SetSceneItemEnabled", {"sceneUuid": "s-vert", "sceneItemId": 11, "sceneItemEnabled": True})
                      in cl.llamadas, True))
        t, ocultos = M.tapar('src="https://x.com/a?token=abcdef123456&b=1" apiKey: "zzzzzz"')
        casos.append(("tapa tokens de URL y claves", ("abcdef123456" in t, "zzzzzz" in t, len(ocultos)), (False, False, 2)))
        casos += [("«¿qué overlays tengo?» va directo", router._sus_overlays("¿Qué overlays tengo?", "responder", {}),
                   ("mis_overlays", {"accion": "ver"})),
                  ("«volvé el overlay como estaba»", router._sus_overlays("volvé el overlay como estaba", "overlay",
                                                                          {"accion": "mostrar"})[0], "mis_overlays"),
                  ("«volvé a mostrar el cartel de la raid» sigue siendo overlay",
                   router._sus_overlays("volvé a mostrar el overlay de la raid", "overlay", {"accion": "mostrar"})[0], "overlay")]
        import acciones
        import cerebro
        viejos = (acciones.log, cerebro.log, M.preparar_cambio, M.aplicar)
        hechos = []
        try:
            acciones.log = cerebro.log = lambda t: None
            M.preparar_cambio = lambda cual, cambio, lienzo="", dicho="": {
                "tipo": "archivo", "fuente": "Overlay ttiktok", "resumen": "Saco la etiqueta BETA.", "lienzo": "vertical",
                "escena": "Escena vertical", "en_vivo": False}
            M.aplicar = lambda datos, cl=None: hechos.append(datos["fuente"]) or "Listo, cambié «Overlay ttiktok»."
            vistos = []
            c = cerebro.Cerebro(lambda t, tipo="info", seg=0: vistos.append(t), simular=False)
            c._ejecutar(H.construir("mis_overlays", {"accion": "cambiar", "cual": "el vertical", "cambio": "sacá lo de beta"}))
            casos.append(("flujo: prepara y queda esperando «dale»", (getattr(c.pendiente, "tipo", None), list(hechos)),
                          ("overlay_aplicar", [])))
            casos.append(("flujo: te dice qué va a cambiar", "Saco la etiqueta BETA." in vistos[-1], True))
            c.confirmar()
            casos.append(("flujo: con «dale» lo aplica", (list(hechos), c.pendiente), (["Overlay ttiktok"], None)))
        finally:
            acciones.log, cerebro.log, M.preparar_cambio, M.aplicar = viejos
        try:
            H.construir("mis_overlays", {"accion": "cambiar", "cual": "el vertical"})
            casos.append(("cambiar sin decir qué: pregunta", "pasó", "pregunta"))
        except H.ErrorOrden:
            casos.append(("cambiar sin decir qué: pregunta", "pregunta", "pregunta"))
        casos += _overlays_en_los_dos(tmp, cl, M)
    finally:
        config.DATA, config.OBS_PASSWORD, config.BASE = viejo_data, viejo_pw, viejo_base
        shutil.rmtree(tmp, ignore_errors=True)
    bien = 0
    for nombre, salio, esperado in casos:
        ok = salio == esperado
        bien += ok
        if not ok:
            print(f"FALLO {nombre}: salió {salio!r}, tenía que ser {esperado!r}")
    print(f"{bien}/{len(casos)} bien (tus overlays de OBS, con OBS y Claude de mentira).")
    return bien, len(casos)


def _overlays_en_los_dos(tmp, cl, M):
    """4 nov: «en los dos lienzos dice Rogue, que diga War» y Hogger cambió solo uno."""
    horizontal = 'const CONFIG = {name: "Mr. H", clase: "Rogue", obsPassword: "SECRETO123", level: 8}'
    vertical = '<div class="clase">Rogue</div><script>const CONFIG = {obsPassword: "SECRETO123", level: 8}</script>'
    (tmp / "overlay-horizontal.html").write_text(horizontal, encoding="utf-8")
    (tmp / "overlay-tiktok-misterache.html").write_text(vertical, encoding="utf-8")
    inv = M.inventario(cl)
    pedidos = []

    def claude(pedido):
        pedidos.append(pedido)
        return '{"resumen": "Cambio «Rogue» por «Warrior».", "cambios": [{"buscar": "Rogue", "poner": "Warrior"}]}'
    nombres = lambda lista: sorted(o["nombre"] for o in lista)          # noqa: E731
    casos = [("«Rogue» sin decir lienzo y está en los dos → los dos",
              nombres(M.elegir_varios(inv, "el del nivel", "", "Cambiar \"Rogue\" por \"Warrior\"")[0]),
              ["Navegador 2", "Overlay ttiktok"]),
             ("si nombró el horizontal, solo ese", M.elegir_varios(inv, "", "horizontal", "Cambiar «Rogue» por «War»")[0], []),
             ("«ambos»: uno por lienzo", nombres(M.elegir_varios(inv, "el vertical", "ambos", "Cambiar «Rogue» por «War»")[0]),
              ["Navegador 2", "Overlay ttiktok"])]
    p = M.preparar_cambio("el vertical", "Cambiar «Rogue» por «Warrior»", "ambos", cl=cl, claude=claude)
    casos += [("prepara los dos juntos (un solo «dale»)", (p["tipo"], len(p["partes"])), ("varios", 2)),
              ("a Claude tampoco le llega la contraseña", any("SECRETO123" in v for v in pedidos), False),
              ("antes del «dale» no cambia nada", ((tmp / "overlay-horizontal.html").read_text(encoding="utf-8"),
                                                    (tmp / "overlay-tiktok-misterache.html").read_text(encoding="utf-8")),
               (horizontal, vertical))]
    r = M.aplicar(p, cl=cl)
    casos += [("con el «dale»: los dos dicen Warrior y la contraseña queda", (
        (tmp / "overlay-horizontal.html").read_text(encoding="utf-8") == horizontal.replace("Rogue", "Warrior"),
        (tmp / "overlay-tiktok-misterache.html").read_text(encoding="utf-8") == vertical.replace("Rogue", "Warrior")),
        (True, True)),
              ("te dice los dos que cambió", "Navegador 2" in r and "Overlay ttiktok" in r, True)]
    M.volver(cl=cl)
    casos.append(("«volvé el overlay como estaba» vuelve los dos", (
        (tmp / "overlay-horizontal.html").read_text(encoding="utf-8"),
        (tmp / "overlay-tiktok-misterache.html").read_text(encoding="utf-8")), (horizontal, vertical)))
    return casos


def probar_miniaturas():
    """Editar la miniatura de ahora (4 nov: «está buena, solo poné el logo oficial de WoW Forever»), sin Edge ni Claude."""
    import shutil
    import tempfile
    from pathlib import Path

    from PIL import Image

    import acciones
    import cerebro
    import config
    import miniaturas_claude as MC
    tmp = Path(tempfile.mkdtemp(prefix="miniaturas_"))
    viejos = (config.DATA, config.SALIDA, config.RECURSOS, config.MINIATURA_REVISAR, config.MINIATURA_AGENTE,
              MC.fotos, MC.mostrar, MC.buscar_imagenes, acciones.log, cerebro.log)
    config.DATA, config.SALIDA, config.RECURSOS = tmp / "data", tmp / "salida", tmp / "recursos"
    config.MINIATURA_REVISAR, config.MINIATURA_AGENTE = False, True
    for c in (config.DATA, config.RECURSOS):
        c.mkdir(parents=True)
    vieja = config.SALIDA / "miniaturas" / "2026-11-03_2002_1-al-20-seguido"
    vieja.mkdir(parents=True)
    html = ('<!doctype html><html><head><style>.logo{width:30vw}h1{filter:url(#fFire)}</style></head><body>'
            '<svg width="0" height="0"><filter id="fFire"/><linearGradient id="gBlade"/></svg>'
            '<img class="logo" src="web_logo_wow.png"><h1 style="fill:url( #gBlade )">1 al 20 seguido</h1>'
            '<svg><use href="#em"/></svg></body></html>')
    (vieja / "diseno.html").write_text(html, encoding="utf-8")
    for nombre, tam in (("web_logo_wow.png", (400, 200)), ("captura.png", (320, 180)), ("youtube.jpg", (1280, 720)),
                        ("tiktok.jpg", (1080, 1920))):
        Image.new("RGB", tam, (40, 30, 20)).save(vieja / nombre)
    Image.new("RGB", (64, 64)).save(config.SALIDA / "miniaturas" / "x.png")          # un archivo suelto no molesta
    (config.SALIDA / "miniaturas" / "prueba_opus2").mkdir()
    (config.SALIDA / "miniaturas" / "prueba_opus2" / "diseno.html").write_text(html, encoding="utf-8")
    (config.DATA / "historial.log").write_text(
        "2026-11-03 20:10:25  RESULTADO: Miniaturas listas (diseñadas por Claude) en "
        "C:\\ElCerebro\\salida\\miniaturas\\2026-11-03_2002_1-al-20-seguido y subida a YouTube.\n", encoding="utf-8")

    def fotos(carpeta, html_):
        rutas = {}
        for n, ext in (("youtube", "jpg"), ("kick", "png"), ("tiktok", "jpg")):
            Image.new("RGB", (128, 72), (200, 160, 60)).save(carpeta / f"{n}.{ext}")
            rutas[n] = carpeta / f"{n}.{ext}"
        return rutas
    pedidos, bajadas = [], []

    def claude_logo(pedido, carpeta):
        pedidos.append(pedido)
        return ('{"resumen": "Cambié el logo de WoW por el oficial de WoW Forever.", "cambios": [{"buscar": '
                '"src=\\"web_logo_wow.png\\"", "poner": "src=\\"logo_wow_forever.png\\""}]}')

    def buscar(idea, carpeta, dicho=""):
        bajadas.append(idea)
        MC.DESCARTES.append("dragón de warcraft.wiki.gg (pesa más de 25 MB)")
        return []
    casos = []
    try:
        MC.fotos, MC.mostrar, MC.buscar_imagenes = fotos, (lambda ruta: False), buscar
        casos += [("la de ahora: la última que subiste (según historial.log)", MC.ultima().name, vieja.name),
                  ("sin el logo guardado, el agente busca el de Forever", MC.necesita_agente("Poner el logo oficial de WoW Forever"),
                   True),
                  ("la búsqueda pide el logo de Forever, no el clásico", "FOREVER" in MC.LOGO_A_BUSCAR
                   and "logo clásico sin Forever" in MC.LOGO_A_BUSCAR, True)]
        Image.new("RGBA", (600, 260), (0, 0, 0, 0)).save(config.RECURSOS / MC.LOGO_JUEGO)
        casos += [("con el logo guardado, no hace falta buscarlo", MC.necesita_agente("Poner el logo oficial de WoW Forever"),
                   False),
                  ("pero si pide otra imagen, sí busca", MC.necesita_agente("el logo de wow forever y un warrior"), True)]
        r = MC.editar("Poner el logo oficial de WoW Forever en vez del logo de WoW", dicho=DIJO_MINIATURA, claude=claude_logo)
        nuevo = (r["carpeta"] / "diseno.html").read_text(encoding="utf-8")
        casos += [("al diseñador le llega el diseño de ahora y tus palabras", (html in pedidos[0], DIJO_MINIATURA in pedidos[0]),
                   (True, True)),
                  ("le ofrece el logo oficial con su tamaño", f"{MC.LOGO_JUEGO}: logo OFICIAL" in pedidos[0]
                   and "600x260" in pedidos[0], True),
                  ("con el logo guardado no salió a buscar", list(bajadas), []),
                  ("cambia SOLO el logo (lo demás igual)", nuevo, html.replace("web_logo_wow.png", MC.LOGO_JUEGO)),
                  ("la de antes no se toca", (vieja / "diseno.html").read_text(encoding="utf-8"), html),
                  ("carpeta nueva «…-editada» con antes y ahora", (r["carpeta"].name.endswith("_1-al-20-seguido-editada"),
                                                                    r["comparacion"].exists()), (True, True)),
                  ("la próxima edición sigue sobre esta", MC.ultima(), r["carpeta"])]
        try:
            MC.editar("ponele un dragon", claude=lambda p, c: '{"cambios": [], "resumen": "No tengo ninguna imagen de dragón."}')
            casos.append(("si no se puede, lo dice (no inventa)", "pasó", "error"))
        except RuntimeError as e:
            casos += [("si no se puede, lo dice (no inventa)", "error" if "dragón" in str(e) else str(e), "error"),
                      ("y dice por qué no sirvió lo que encontró", "pesa más de 25 MB" in str(e), True)]
        casos += [("si falla, no deja carpetas a medias", sorted(d.name.endswith("-editada") for d in
                                                                 (config.SALIDA / "miniaturas").glob("*editada*")), [True]),
                  ("el logo oficial de la wiki (9,5 MB) ya entra", MC.MAX_BYTES > 9_964_036, True)]
        try:
            MC.editar("cambiá el logo", claude=lambda p, c: (
                '{"resumen": "x", "cambios": [{"buscar": "logo_wow_forever.png", "poner": "no_existe.png"}]}'))
            casos.append(("un archivo que no está: no lo hace", "pasó", "error"))
        except RuntimeError as e:
            casos.append(("un archivo que no está: no lo hace", "error" if "no_existe" in str(e) else str(e), "error"))
        (config.RECURSOS / MC.LOGO_JUEGO).unlink()
        Image.new("RGBA", (500, 250), (0, 0, 0, 0)).save(r["carpeta"] / "web_logo_wow_forever.png")
        (r["carpeta"] / "diseno.html").write_text(nuevo.replace(MC.LOGO_JUEGO, "web_logo_wow_forever.png"), encoding="utf-8")
        casos.append(("con tu «dale», el logo que bajó queda guardado", (bool(MC.aprender_logo(r["carpeta"])),
                                                                       (config.RECURSOS / MC.LOGO_JUEGO).exists()),
                      (True, True)))
        # El flujo entero: prepara, te pregunta «¿La subo a YouTube?» y sube solo con el «dale»
        subidas = []
        acciones.log = cerebro.log = lambda t: None
        MC.editar = lambda cambio, dicho="": {**fotos(r["carpeta"], ""), "comparacion": r["comparacion"],
                                               "carpeta": r["carpeta"], "de": vieja.name, "resumen": "Puse el logo de Forever."}
        vistos, dichos = [], []
        c = cerebro.Cerebro(lambda t, tipo="info", seg=0: vistos.append(t), simular=False,
                            avisar=lambda evento, accion=None, detalle="": dichos.append((evento, accion)))
        c.ejecutor._yt = type("YT", (), {"subir_miniatura": lambda self, ruta: subidas.append(ruta.parent.name)})()
        c._ejecutar(H.construir("editar_miniatura", {"cambio": "Poner el logo oficial de WoW Forever", "dicho": DIJO_MINIATURA}))
        pend = c.pendiente
        casos += [("flujo: la cambia y queda esperando «dale» para subirla", (getattr(pend, "tipo", None), list(subidas)),
                   ("miniatura_subir", [])),
                  ("flujo: te dice qué cambió", "Puse el logo de Forever" in (vistos[-1] if vistos else ""), True)]
        c.confirmar()
        casos += [("flujo: con «dale» la sube a YouTube", subidas, [r["carpeta"].name]),
                  ("y queda como «la de ahora»", MC._registro().get("subida", {}).get("nombre"), r["carpeta"].name)]
    finally:
        (config.DATA, config.SALIDA, config.RECURSOS, config.MINIATURA_REVISAR, config.MINIATURA_AGENTE,
         MC.fotos, MC.mostrar, MC.buscar_imagenes, acciones.log, cerebro.log) = viejos
        import importlib
        importlib.reload(MC)
        shutil.rmtree(tmp, ignore_errors=True)
    bien = 0
    for nombre, salio, esperado in casos:
        ok = salio == esperado
        bien += ok
        print(f"{'OK ' if ok else 'FALLO'} {nombre}" + ("" if ok else f": salió {salio!r}, tenía que ser {esperado!r}"))
    print(f"{bien}/{len(casos)} bien (editar la miniatura, con Claude y Edge de mentira).")
    return bien, len(casos)


def probar_todo():
    import memoria
    resultados = []
    for nombre, f in (("rápidas", probar_rapido), ("corregir", probar_corregir), ("overlays", probar_overlays),
                      ("miniaturas", probar_miniaturas),
                      ("Discord y títulos", probar_general),
                      ("chat", probar_chat),
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
