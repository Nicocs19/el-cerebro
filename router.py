"""El router: convierte lo que dices en una Accion validada.

1. Si hay una orden esperando confirmación y dices "dale" o "cancela", se resuelve sin IA.
2. Si no, la IA local (Ollama) elige UNA herramienta y rellena sus campos.
3. herramientas.construir() valida todo y arma el resumen.
4. Si Ollama no responde, se usan los patrones fijos del MVP (anuncio y título).
"""
import datetime as dt
import json
import re
import time
import unicodedata

import requests

import config
import herramientas as H
import intenciones

CONFIRMA = re.compile(r"^(dale|si|sí|confirmo|confirma|publica(lo)?|manda(lo)?|ok|okay|adelante|hazlo|hacelo|listo|va)\b")
CANCELA = re.compile(r"^(no|cancela(lo)?|olvidalo|olvídalo|dejalo|déjalo|para|stop)\b")

RAIDS = ", ".join(H.RAIDS)
PIDE_ETIQUETA = re.compile(r"etiquet|mencion|everyone|arroba|@|avisando a|avisales|notific")


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return t.strip(" .,!¡¿?")


def es_confirmacion(texto):
    n = _norm(texto)
    if CONFIRMA.match(n) and len(n.split()) <= 4:
        return "confirmar"
    if CANCELA.match(n) and len(n.split()) <= 4:
        return "cancelar"
    return None


def sistema():
    """Instrucciones fijas. No cambian entre pedidos, así Ollama las reutiliza y contesta más rápido."""
    return f"""Eres El Cerebro, el asistente de streaming de Nicolas (Mr. H), GM de la hermandad "{config.NOMBRE_GUILD}" de World of Warcraft Forever.
Recibes órdenes dictadas por voz (pueden traer errores de transcripción) y SIEMPRE respondes llamando exactamente UNA herramienta.
Cada orden llega con la fecha y hora actual y el calendario de los próximos días.

Reglas:
- Fechas: en el campo fecha COPIA el día tal como lo dijo ("hoy", "mañana", "viernes", "sábado 14", "el 20 de noviembre"). No lo conviertas: el programa calcula la fecha exacta. Si corriges una orden pendiente y no cambia el día, copia el día de esa orden.
- Horas en 24 h. Para raids, bandas y eventos, "a las 9" sin más significa 21:00; "a las 9 de la mañana" es 09:00.
- No inventes datos (horas, premios, requisitos, cupos) que Nicolas no dijo, ni agregues canales, instrucciones o llamados a la acción que no pidió (nada de "anótense en #raids-signup" si no lo dijo). Si falta algo imprescindible (por ejemplo la fecha u hora de una raid), usa pedir_aclaracion.
- Textos públicos (anuncios, sorteos, encuestas): {config.TONO}. Corrige errores de dictado y redacta bien lo que dijo, con tildes correctas, y podés cerrar con una frase corta de ánimo, pero no inventes datos, canales, links ni instrucciones que Nicolas no dijo (nada de "anótense en #raids-signup" si no lo pidió).
- Títulos de stream: usa el texto que dictó, corregido, sin añadir nada. Respetá su jerga: "leveando al War del 1 al 10" queda así (no lo traduzcas ni lo cambies por otra palabra).
- Jerga de WoW: War = Warrior (guerrero), Pala = Paladín, Lock = Warlock, Hunter, Rogue, Priest, Mago, Druida, Chamán; levear o levelear = subir de nivel. El dictado a veces escribe mal esas palabras: "washer", "guasher" o "wor" junto a levear, subir o una clase es "War"; "leviando" es "leveando". Corregilas en lo que escribas.
- Si en la misma orden pide cambiar el juego o la categoría junto con el título, poné el juego en el campo juego. Si solo pide cambiar el juego ("poné World of Warcraft", "cambiá la categoría a Just Chatting"), usa cambiar_juego.
- Nombres de raids bien escritos: {RAIDS}. "Guild", "gil", "guil" o "hermandad" significan la hermandad.
- Roles que se pueden etiquetar: {", ".join(config.ROLES_MENCIONABLES)}. Etiqueta solo si lo pide o si es un anuncio de evento para toda la guild ("Eventos de la guild").
- Canales del Discord: {", ".join(config.CANALES_DISCORD) or "(los de siempre)"}. Deja el canal vacío salvo que nombre uno.
- Si Nicolas te habla a vos o charla ("Cerebro, decime algo", "hola", "¿me escuchás?", "contame un chiste", una pregunta cualquiera) y no pide publicar, mandar ni cambiar nada, usa responder (se dice en voz alta y se escucha en el stream). Ahí sos El Cerebro: un cerebro con gafas, medio pendejo, gracioso y buena onda, que habla como un pata latino; si te pide un chiste, hacé uno corto y medio cojudo; si te pregunta algo que sabés, contestá en 1 a 3 frases.
- Personalidad: si Nicolas te molesta, te bardea o te insulta en broma, ponete caliente (animo=picado) y devolvele un bardeo gracioso, picante, a él. Si te pide molestar, bardear o rostear al chat, hacé una joda de stream picante pero buena onda (animo=picado), y si hay gente del chat en la lista, nombrá a 1 a 3. Si te pide saludar al stream, a la gente o al chat, saludá con mucha energía (animo=feliz). Podés decir groserías suaves (cojudo, huevón, pendejo, boludo), pero NUNCA nada sobre raza, origen, sexo, orientación, religión, el físico o discapacidades, ni amenazas, ni nada que sea acoso.
- Escribir en el chat es otra cosa: solo si dice mandá, escribí o poné algo EN el chat ("mandá un saludo al chat") usa mandar_al_chat con el texto y enlace vacío.
- Preguntas que necesitan datos actuales o que no sabés seguro (noticias, resultados, precios, parches, estrenos, clima, quién ganó, datos puntuales de WoW o de alguien) -> buscar_en_internet. Charla, chistes y cultura general que cualquiera sabe (capitales, definiciones simples, historia conocida, cuentas) -> responder directo, SIN buscar. Solo publica en Discord si dice claramente que avises, publiques o mandes algo al Discord, a un canal o a la guild. Si dice "avisá en Discord" sin canal, usa mensaje_discord con canal general. Nunca preguntes el canal, a quién etiquetar ni un título: usá lo que dijo y lo de siempre.
- Si en la misma orden pide cambiar el título Y hacer la miniatura, usa cambiar_titulo_stream con los campos miniatura (el texto grande), miniatura_subtitulo y miniatura_idea (cómo la imagina: imágenes, logos, personajes, tal como lo dijo).
- El CHAT del stream (Kick y YouTube) no es el Discord. "Mandá al chat el link del discord" -> mandar_al_chat (el enlace se llama discord, pero va al chat del stream). "Avisá en Discord", "en general" o "a la guild" -> mensaje_discord o publicar_anuncio.
- Overlays: carteles o gráficos en la pantalla del stream (OBS) -> overlay. En descripcion poné lo que tiene que mostrar con los textos y datos EXACTOS que dijo, sin agregar nada.
- Moderación del chat: banear = para siempre; silenciar, timeout, mutear o castigar = un rato. En usuario COPIA el nombre tal como lo dijo (el programa busca al más parecido en el chat): no lo completes ni lo inventes. Nunca pongas enlaces en el texto: los enlaces salen de la lista guardada.

Ejemplos:
- "lanza un anuncio a la guild que hoy hacemos mazmorras a las 10" -> publicar_anuncio(titulo="Hoy hay mazmorras", texto="Esta noche a las 22:00 salimos de mazmorras con la hermandad. ⚔️", tipo="evento", mencionar="Eventos de la guild")
- "arma una raid de molten cor el viernes a las 9 con 20 cupos" -> crear_raid(nombre="Molten Core", fecha="viernes", hora="21:00", cupo=20)
- "banda de deadmines para mañana a las 6 de la tarde" -> crear_banda(nombre="Deadmines", fecha="mañana", hora="18:00", tanques=1, healers=1, dps=3)
- "cambia el título a día 1 subiendo guerrero" -> cambiar_titulo_stream(titulo="Día 1 subiendo guerrero", plataformas=["kick","youtube","tiktok"])
- "sortea un mes de juego entre los de la guild, dura dos días" -> crear_sorteo(premio="1 mes de juego", horas=48, ganadores=1)
- "cerebro, decime algo" -> responder(respuesta="¡Acá estoy, listo para pensar por los dos! ¿Qué hacemos hoy?")
- "avisa en el discord que en 10 minutos empiezo" -> mensaje_discord(texto="¡En 10 minutos arranco directo! Pasen 🔴", canal="general")
- "cambia el título a día 2 subiendo pícaro y haz la miniatura que diga día 2" -> cambiar_titulo_stream(titulo="Día 2 subiendo pícaro", plataformas=["kick","youtube","tiktok"], miniatura="Día 2")
- "cambiá el título a leviando al washer del 1 al 10 y haceme la miniatura con el logo de wow y el warrior que diga no me esperaba esto, los primeros niveles" -> cambiar_titulo_stream(titulo="Leveando al War del 1 al 10", plataformas=["kick","youtube","tiktok"], miniatura="No me esperaba esto", miniatura_subtitulo="Los primeros niveles", miniatura_idea="logo de WoW y el Warrior")
- "poné el juego world of warcraft" -> cambiar_juego(juego="World of Warcraft")
- "banea a pepe noventa y nueve" -> moderar_chat(accion="banear", usuario="pepe 99", plataformas=[])
- "silencia cinco minutos a shadow en kick" -> moderar_chat(accion="silenciar", usuario="shadow", minutos=5, plataformas=["kick"])
- "manda al chat el link del discord" -> mandar_al_chat(enlace="discord", texto="", plataformas=[])
- "guarda este enlace como instagram" -> guardar_enlace(nombre="instagram")
- "poné un cartel arriba a la izquierda que diga raid de molten core hoy a las 9" -> overlay(accion="crear", nombre="raid molten core", descripcion="Cartel que diga «Raid de Molten Core · Hoy 21:00»", posicion="arriba-izquierda", tamano="mediano")
- "sacá el cartel de la raid" -> overlay(accion="quitar", nombre="raid")
- "cerebro, sos un inútil" -> responder(respuesta="¿Inútil yo? Mirá quién habla, el que se pierde con el mapa abierto. ¡Andá a farmear, pendejo!", animo="picado")
- "molestá al chat" -> responder(respuesta="A ver chat, mucho lurkeo y poco follow. ¡Escriban algo, manga de vagos, que no muerdo!", animo="picado")
- "saludá al stream" -> responder(respuesta="¡Buenas buenas, gente linda del stream! Acá El Cerebro, el que piensa por Mister H. ¡Pónganse cómodos!", animo="feliz")
- "mandá un saludo al chat" -> mandar_al_chat(enlace="", texto="¡Hola chat! Bienvenidos al stream de Mr. H 👋", plataformas=[])
- "¿qué parche salió en wow forever?" -> buscar_en_internet(pregunta="Último parche de World of Warcraft Forever")
- "¿cuál es la capital de Francia?" -> responder(respuesta="París, obvio. Hasta un cerebro con gafas lo sabe.", animo="normal")
"""


HABLA_DEL_CHAT = re.compile(r"chat|gente|molest|bardea|bardi|rostea|jod|salud|vagos|lurk")


def gente_del_chat(maximo=8):
    """Los que escribieron hace poco en el chat de Kick (para que El Cerebro los nombre al bardear o saludar)."""
    try:
        import chat_vivo
        nombres = []
        for m in reversed(chat_vivo.recientes_kick(30)):
            if m["usuario"] and m["usuario"] not in nombres:
                nombres.append(m["usuario"])
        return nombres[:maximo]
    except Exception:  # noqa: BLE001
        return []


def contexto(pendiente=None, ahora=None, orden=""):
    """Lo que cambia en cada pedido: fecha, calendario y la orden pendiente (va con la orden, al final)."""
    ahora = ahora or dt.datetime.now()
    texto = (f"Ahora es {H.DIAS[ahora.weekday()]} {ahora:%Y-%m-%d %H:%M}. Calendario de los próximos días:\n"
             f"{H.calendario(ahora.date())}\n")
    if pendiente:
        texto += (f"\nHay una orden ESPERANDO confirmación: {pendiente}. Si Nicolas la corrige (\"cámbiale la hora a las 10\", "
                  "\"mejor 25 cupos\"), vuelve a llamar la MISMA herramienta con todos los datos y la corrección aplicada.\n")
    if orden and HABLA_DEL_CHAT.search(_norm(orden)):
        gente = gente_del_chat()
        texto += f"\nGente que escribió hace poco en el chat: {', '.join(gente)}.\n" if gente else ""
    return texto


_sesion = requests.Session()        # reusa la conexión con Ollama
ULTIMO_USO = [0.0]


def _llamar_ollama(texto, pendiente=None, solo=None):
    """(herramienta, argumentos) que eligió la IA. solo=[nombres] limita las herramientas (para completar combos)."""
    ULTIMO_USO[0] = time.time()
    herramientas = [h for h in H.esquemas() if h["function"]["name"] in solo] if solo else H.esquemas()
    r = _sesion.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": sistema()},
                     {"role": "user", "content": f"{contexto(pendiente, orden=texto)}\nOrden dictada por Nicolas: {texto}"}],
        "tools": herramientas,
        "stream": False,
        "think": False,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }, timeout=90)
    r.raise_for_status()
    msg = r.json().get("message", {})
    llamadas = msg.get("tool_calls") or []
    if not llamadas:
        contenido = (msg.get("content") or "").strip()
        return "pedir_aclaracion", {"pregunta": contenido[:200] or "No entendí la orden."}
    f = llamadas[0]["function"]
    args = f.get("arguments") or {}
    if isinstance(args, str):
        args = json.loads(args)
    return f["name"], args


PIDE_MINIATURA = re.compile(r"miniatura|portada|thumbnail")
PIDE_TITULO = re.compile(r"(cambi|pon|actualiz)\w*\b.*\btitulo|\btitulo\b.*\b(a|que diga)\b")
PIDE_JUEGO = re.compile(r"(cambi|pon)\w*\b.*\b(juego|categoria)")


def _completar_combo(texto, nombre, args):
    """«Cambiá el título y haceme la miniatura»: si la IA solo hizo una parte, le pide la otra por separado."""
    n = _norm(texto)
    try:
        if nombre == "cambiar_titulo_stream":
            if PIDE_MINIATURA.search(n) and H._vacio(args.get("miniatura")):
                otra, extra = _llamar_ollama(texto, solo=["crear_miniatura"])
                if otra == "crear_miniatura" and not H._vacio(extra.get("titulo")):
                    args = {**args, "miniatura": extra.get("titulo"), "miniatura_subtitulo": extra.get("subtitulo") or "",
                            "miniatura_idea": extra.get("idea") or ""}
                    print(f"[router] combo: también la miniatura {json.dumps(extra, ensure_ascii=False)}")
            if PIDE_JUEGO.search(n) and H._vacio(args.get("juego")):
                otra, extra = _llamar_ollama(texto, solo=["cambiar_juego"])
                if otra == "cambiar_juego" and not H._vacio(extra.get("juego")):
                    args = {**args, "juego": extra["juego"]}
        elif nombre == "crear_miniatura" and PIDE_TITULO.search(n):
            otra, extra = _llamar_ollama(texto, solo=["cambiar_titulo_stream"])
            if otra == "cambiar_titulo_stream" and not H._vacio(extra.get("titulo")):
                print("[router] combo: también el título")
                return otra, {**extra, "miniatura": args.get("titulo"), "miniatura_subtitulo": args.get("subtitulo") or "",
                              "miniatura_idea": args.get("idea") or ""}
    except Exception as e:  # noqa: BLE001
        print(f"[router] no pude completar la segunda parte de la orden: {e}")
    return nombre, args


def _por_patrones(texto):
    o = intenciones.por_patrones(texto)
    if not o:
        return None
    if o["accion"] == "anuncio":
        return "publicar_anuncio", {"titulo": "Aviso de la guild", "texto": o["texto"], "tipo": "aviso", "mencionar": "ninguno"}
    if o["accion"] == "titulo":
        return "cambiar_titulo_stream", {"titulo": o["texto"], "plataformas": o["plataformas"]}
    mapa = {"borrar_anuncio": "deshacer_ultima_publicacion", "restaurar_titulo": "restaurar_titulo",
            "consultar_titulo": "consultar_titulo"}
    return mapa[o["accion"]], {}


def interpretar(texto, pendiente=None):
    """Devuelve (Accion, origen). Lanza H.ErrorOrden si la orden no se puede ejecutar."""
    origen = "ia"
    llamada = None
    if config.USE_OLLAMA:
        try:
            llamada = _llamar_ollama(texto, pendiente.datos if pendiente else None)
        except Exception as e:  # noqa: BLE001
            print(f"[router] Ollama no respondió ({e}); uso patrones fijos.")
    if llamada is None:
        origen = "patrones"
        llamada = _por_patrones(texto)
        if llamada is None:
            raise H.ErrorOrden("No entendí la orden (y la IA local no está disponible).")
    nombre, args = llamada
    if origen == "ia":
        nombre, args = _completar_combo(texto, nombre, args)
    if nombre in ("crear_raid", "crear_banda"):
        # Lo que dijo Nicolas manda: si nombró un día claro, se usa ese aunque la IA haya puesto otro.
        fecha = H.corregir_dia(texto, args.get("fecha"))
        if fecha != args.get("fecha"):
            print(f"[router] la IA puso «{args.get('fecha')}», pero dijiste «{fecha}»: uso lo tuyo")
            args = {**args, "fecha": fecha}
    if nombre in ("crear_encuesta", "crear_sorteo") and not PIDE_ETIQUETA.search(_norm(texto)):
        args = {**args, "mencionar": "ninguno"}          # en encuestas y sorteos se etiqueta solo si lo pidió
    if nombre in ("publicar_anuncio", "mensaje_discord", "overlay"):
        # Lo que dijo Nicolas manda: mismo día, sin «hoy» inventado y sin instrucciones que no pidió
        args = {**args, **{k: H.texto_fiel(texto, args[k], quitar_hoy=nombre == "overlay")
                           for k in ("titulo", "texto", "descripcion") if args.get(k)}}
    print(f"[router] {origen}: {nombre} {json.dumps(args, ensure_ascii=False)}")
    return H.construir(nombre, args), origen


def precargar():
    """Carga el modelo en la GPU con la MISMA configuración que las órdenes y deja leídas las instrucciones.

    Así la primera orden no espera a que el modelo se cargue (ni se recargue con otra configuración).
    El Cerebro lo repite cada tanto mientras está abierto para que Ollama no lo descargue.
    """
    t0 = time.time()
    try:
        _llamar_ollama("hola")
        print(f"[router] {config.OLLAMA_MODEL} listo ({time.time() - t0:.1f} s).")
    except Exception as e:  # noqa: BLE001
        print(f"[router] No pude precargar {config.OLLAMA_MODEL}: {e}")
