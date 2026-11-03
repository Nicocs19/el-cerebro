"""Herramientas que la IA local puede usar.

Cada herramienta tiene tres partes:
  1. El esquema que ve el modelo (nombre, descripción y campos estrictos).
  2. La validación en Python: aquí se decide qué se ejecuta de verdad.
  3. Un resumen en español para confirmar antes de publicar.
El modelo solo propone; nada se publica sin pasar por la validación.
"""
import datetime as dt
import re
import unicodedata

import config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Nombres bien escritos de raids y mazmorras (Classic, TBC y WotLK). El dictado los escribe "como suenan"
# ("monte aijal", "molten cor"): se corrigen al más parecido de esta lista.
RAIDS = ["Molten Core", "Onyxia", "Blackwing Lair", "Zul'Gurub", "Ruinas de Ahn'Qiraj", "Templo de Ahn'Qiraj",
         "Naxxramas", "Karazhan", "Guarida de Gruul", "Guarida de Magtheridon", "Caverna Santuario Serpiente",
         "El Ojo", "Monte Hyjal", "Templo Oscuro", "Zul'Aman", "Meseta de La Fuente del Sol", "Ulduar",
         "Prueba del Cruzado", "Ciudadela de la Corona de Hielo", "Sagrario Rubí", "Cámara de Archavon",
         "El Santuario Obsidiana", "El Ojo de la Eternidad"]
MAZMORRAS = ["Deadmines", "Wailing Caverns", "Shadowfang Keep", "Blackfathom Deeps", "Stockade", "Gnomeregan",
             "Razorfen Kraul", "Razorfen Downs", "Scarlet Monastery", "Uldaman", "Zul'Farrak", "Maraudon",
             "Sunken Temple", "Blackrock Depths", "Lower Blackrock Spire", "Upper Blackrock Spire", "Dire Maul",
             "Stratholme", "Scholomance", "Ragefire Chasm"]


ALIAS = {"mc": "Molten Core", "bwl": "Blackwing Lair", "zg": "Zul'Gurub", "aq20": "Ruinas de Ahn'Qiraj",
         "aq40": "Templo de Ahn'Qiraj", "naxx": "Naxxramas", "kara": "Karazhan", "gruul": "Guarida de Gruul",
         "magtheridon": "Guarida de Magtheridon", "ssc": "Caverna Santuario Serpiente", "tk": "El Ojo",
         "hyjal": "Monte Hyjal", "hiyal": "Monte Hyjal", "aijal": "Monte Hyjal", "cima hyjal": "Monte Hyjal",
         "bt": "Templo Oscuro", "za": "Zul'Aman", "swp": "Meseta de La Fuente del Sol", "icc": "Ciudadela de la Corona de Hielo",
         "toc": "Prueba del Cruzado", "minas de la muerte": "Deadmines", "las minas de la muerte": "Deadmines",
         "vc": "Deadmines", "sm": "Scarlet Monastery", "monasterio escarlata": "Scarlet Monastery",
         "brd": "Blackrock Depths", "ubrs": "Upper Blackrock Spire", "lbrs": "Lower Blackrock Spire",
         "strat": "Stratholme", "scholo": "Scholomance", "dm": "Dire Maul", "la masacre": "Dire Maul"}


def nombre_conocido(nombre):
    """Corrige el nombre de una raid o mazmorra al más parecido de las listas (si se parece lo suficiente)."""
    import difflib
    limpio = str(nombre or "").strip()
    if not limpio:
        return limpio
    clave = _norm(re.sub(r"^(la |el )?(raid|banda|mazmorra) (de |del )?", "", limpio, flags=re.I))
    if clave in ALIAS:
        return ALIAS[clave]
    canon = {n.lower(): n for n in RAIDS + MAZMORRAS}
    m = difflib.get_close_matches(limpio.lower(), list(canon), n=1, cutoff=0.72)
    return canon[m[0]] if m else limpio


def raid_dicha(dicho, nombre):
    """¿Nicolas nombró esa raid? («molten cor», «MC», «onixia» cuentan). Si no, la IA la inventó y hay que preguntar."""
    import difflib
    n, canon = _norm(dicho), nombre_conocido(nombre)
    generico = r"\b(raids?|registros?|inscripci\w*|avisos?|eventos?|anuncios?|de|del|la|el|para|hoy|manana|guild|hermandad)\b"
    if not re.sub(generico, "", _norm(canon)).strip(" -'"):
        return False                     # «Registro de raid» no es el nombre de una raid
    if any(alias in n.split() and destino == canon for alias, destino in ALIAS.items()):
        return True
    sueltas = re.findall(r"[a-z0-9]+", n.replace("'", "").replace("’", ""))
    palabras = sueltas + [a + b for a, b in zip(sueltas, sueltas[1:])]        # «zul gurub» = «zulgurub»
    palabras = [w for w in palabras if len(w) >= 3]
    claves = [w for w in re.findall(r"[a-z0-9]+", _norm(canon).replace("'", "")) if len(w) >= 4
              and w not in ("raid", "guarida", "templo", "caverna", "meseta", "santuario", "ciudadela", "corona", "hielo")]
    return any(difflib.get_close_matches(c, palabras, n=1, cutoff=0.75) for c in claves or [_norm(canon)])


_MESES = r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
_HORA_NUM = r"(\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)"


def dia_dicho(dicho):
    """¿Dijo un día? («hoy», «el viernes», «mañana», «el 20 de noviembre», «14/11»)."""
    t = _norm(dicho)
    return bool(dia_en_texto(t) or _RE_DIA.search(t) or re.search(r"\bel \d{1,2}\b|\b\d{1,2} de " + _MESES + r"|\b\d{1,2}/\d{1,2}\b", t))


def hora_dicha(dicho):
    """¿Dijo una hora? («a las 9», «21:00», «9 de la noche», «a las nueve y media», «mediodía»)."""
    t = _norm(dicho)
    return bool(re.search(r"\ba (las|la) " + _HORA_NUM + r"\b|\b\d{1,2}:\d{2}\b|\b" + _HORA_NUM +
                          r" ?(am|pm|hs|horas|de la (noche|tarde|manana))\b|mediodia|medianoche", t))


PIDE_NOTA = re.compile(r"\bnotas?\b|requisit|\btrai?gan\b|\btraer\b|vengan|tienen que|tengan|minimo|obligatori|"
                       r"\bgear\b|pre-?bis|equip|consumible|pocion|flask|\bilvl\b|\bsolo (gente|nivel|los)|\bnivel \d")


def nota_limpia(dicho, nota):
    """La nota solo si la pidió («en notas poné…», «que vengan con…»), y sin muletillas («viste», «o sea»)."""
    if _vacio(nota) or not PIDE_NOTA.search(_norm(dicho)):
        return ""
    n = re.sub(r"[\s,;¿]*\b(viste|o sea|tipo|y eso|nada mas|cachai|sabes|entendes|me entendes)\b\??[\s.,;]*$", "",
               str(nota).strip(), flags=re.I)
    n = re.sub(r"\b([\w'-]{3,})(?:\s*(?:,|y|e|o)?\s*(?:\.{2,3}|…)?\s*\1\b)+", r"\1", n, flags=re.I)  # «encantado y… encantado»
    n = re.sub(r"\s*(\.{2,3}|…)\s*", " ", n)
    return re.sub(r"\s{2,}", " ", n).strip(" ,;")


_NUM = r"(\d{1,2}|cinco|diez|quince|veinte|veinticinco|treinta|cuarenta)"
_PALABRA_CUPO = r"(cupos?|jugadores|personas|plazas|lugares|players|man)"
_NUMEROS = {"cinco": 5, "diez": 10, "quince": 15, "veinte": 20, "veinticinco": 25, "treinta": 30, "cuarenta": 40}


def cupos_dichos(dicho):
    """Los cupos que dijo («con 40 cupos», «cupo de 20», «raid de cuarenta personas») o None si no dijo."""
    n = _norm(dicho)
    m = re.search(_NUM + r"\s*" + _PALABRA_CUPO + r"\b", n) or re.search(r"\bcupos?\s*(?:de|para|:)?\s*" + _NUM + r"\b", n)
    if not m:
        return None
    v = m.group(1)
    return int(v) if v.isdigit() else _NUMEROS[v]


PLATAFORMAS = ["kick", "youtube", "tiktok"]
OVERLAY_POSICIONES = ["arriba-izquierda", "arriba", "arriba-derecha", "izquierda", "centro", "derecha",
                      "abajo-izquierda", "abajo", "abajo-derecha"]
NOMBRES = {"kick": "Kick", "youtube": "YouTube", "tiktok": "TikTok"}
TIPOS_ANUNCIO = ["aviso", "evento", "importante", "parche"]


class ErrorOrden(Exception):
    """La orden no se puede ejecutar tal cual; el mensaje se le muestra a Nicolas."""


class Accion:
    def __init__(self, tipo, datos, resumen, confirmar):
        self.tipo = tipo            # hogger, titulo, deshacer, consultar_titulo, restaurar_titulo, miniatura, moderar, chat, guardar_enlace, overlay, respuesta, busqueda, aclaracion
        self.datos = datos
        self.resumen = resumen
        self.confirmar = confirmar

    def __repr__(self):
        return f"Accion({self.tipo}, {self.datos})"


# ---------------------------------------------------------------- esquemas
def _f(nombre, descripcion, propiedades, requeridos):
    return {"type": "function", "function": {
        "name": nombre, "description": descripcion,
        "parameters": {"type": "object", "properties": propiedades, "required": requeridos}}}


def esquemas():
    menciones = ["ninguno", "everyone"] + config.ROLES_MENCIONABLES
    fecha = {"type": "string", "description": "El día COPIADO tal como lo dijo: 'hoy', 'mañana', 'viernes', "
                                              "'sábado 14', 'el 20 de noviembre'. No calcules la fecha: la calcula el programa"}
    hora = {"type": "string", "description": "Hora HH:MM en formato 24 h (las 9 de la noche = 21:00)"}
    return [
        _f("publicar_anuncio", "Publica un anuncio con imagen y el estilo de la guild en el Discord. NO es para registros "
                               "de raid ni cupos: eso es crear_raid.", {
            "titulo": {"type": "string", "description": "Título corto y llamativo (máx. 80 caracteres)"},
            "texto": {"type": "string", "description": "Cuerpo del anuncio, bien redactado, sin inventar datos"},
            "tipo": {"type": "string", "enum": TIPOS_ANUNCIO, "description": "evento para quedadas y actividades, importante para cambios serios, parche para novedades del juego, aviso para el resto"},
            "mencionar": {"type": "string", "enum": menciones, "description": "A quién etiquetar. 'ninguno' si no lo pidió"},
            "canal": {"type": "string", "description": "Solo si nombró un canal concreto; si no, vacío"},
        }, ["titulo", "texto", "tipo", "mencionar"]),
        _f("crear_raid", "Abre el REGISTRO de una raid: el post de Hogger con cupos y botones para anotarse por clase y "
                         "spec (estilo Raid-Helper). Usala SIEMPRE que diga registro, inscripción, anotarse, sign up o "
                         "cupos de una raid, o «aviso de raid».", {
            "nombre": {"type": "string", "description": "Nombre de la raid bien escrito, p. ej. Molten Core"},
            "fecha": fecha, "hora": hora,
            "cupo": {"type": "integer", "description": "Jugadores máximos (5 a 40) que dijo; vacío si no lo dijo"},
            "nota": {"type": "string", "description": "Requisitos o detalles que dijo; vacío si nada"},
            "avisar": {"type": "boolean", "description": "Etiquetar al rol Llamado a bandas. true salvo que diga que no"},
        }, ["nombre", "fecha", "hora", "cupo"]),
        _f("crear_banda", "Crea un evento con cupos de tanque, healer y DPS (mazmorras, grupos chicos).", {
            "nombre": {"type": "string"}, "fecha": fecha, "hora": hora,
            "tanques": {"type": "integer"}, "healers": {"type": "integer"}, "dps": {"type": "integer"},
            "nota": {"type": "string"},
        }, ["nombre", "fecha", "hora"]),
        _f("crear_sorteo", "Crea un sorteo con botón para participar; el ganador sale solo al terminar.", {
            "premio": {"type": "string"},
            "horas": {"type": "number", "description": "Duración en horas (1 día = 24)"},
            "ganadores": {"type": "integer", "description": "Cuántos ganan. 1 si no lo dijo"},
            "descripcion": {"type": "string", "description": "Texto extra; vacío si nada"},
            "canal": {"type": "string", "description": "Solo si nombró un canal concreto; si no, vacío"},
        }, ["premio", "horas"]),
        _f("crear_encuesta", "Crea una encuesta con botones y resultados en vivo.", {
            "pregunta": {"type": "string"},
            "opciones": {"type": "array", "items": {"type": "string"}, "description": "Entre 2 y 5 opciones"},
            "horas": {"type": "integer", "description": "Duración en horas. 24 si no lo dijo"},
            "mencionar": {"type": "string", "enum": menciones, "description": "A quién etiquetar. 'ninguno' si no lo pidió"},
            "canal": {"type": "string", "description": "Solo si nombró un canal concreto; si no, vacío"},
        }, ["pregunta", "opciones"]),
        _f("mensaje_discord", "Manda un mensaje simple (sin formato de anuncio) a un canal del Discord. Solo si pide claramente mandarlo al Discord.", {
            "texto": {"type": "string"},
            "canal": {"type": "string", "description": "Nombre del canal. general si no lo dijo (no preguntes)"},
        }, ["texto"]),
        _f("cerrar_inscripciones", "Cierra (o reabre) las inscripciones de la última raid o banda.", {
            "tipo": {"type": "string", "enum": ["raid", "banda"]},
            "reabrir": {"type": "boolean", "description": "true solo si pide reabrir"},
        }, ["tipo"]),
        _f("deshacer_ultima_publicacion", "Borra lo último que El Cerebro publicó en Discord.", {}, []),
        _f("cambiar_titulo_stream", "Cambia el título del directo en las plataformas.", {
            "titulo": {"type": "string", "description": "El título exacto que pidió, corregido de errores de dictado (máx. 100)"},
            "plataformas": {"type": "array", "items": {"type": "string", "enum": PLATAFORMAS},
                            "description": "Las que nombró; las tres si no nombró ninguna"},
            "miniatura": {"type": "string", "description": "Solo si pidió también la miniatura: su texto grande (2 a 6 palabras); vacío si no"},
            "miniatura_subtitulo": {"type": "string", "description": "Texto chico de la miniatura si lo dijo; vacío si no"},
            "miniatura_idea": {"type": "string", "description": "Cómo imagina la miniatura (imágenes, logos, personajes, colores), tal como lo dijo; vacío si no"},
            "juego": {"type": "string", "description": "Solo si pidió también cambiar el juego o la categoría: el nombre del juego; vacío si no"},
        }, ["titulo", "plataformas"]),
        _f("cambiar_juego", "Cambia el juego (categoría) del directo en Kick.", {
            "juego": {"type": "string", "description": "Nombre del juego bien escrito, p. ej. World of Warcraft, Dead by Daylight, Just Chatting"},
        }, ["juego"]),
        _f("cambiar_descripcion_stream", "Cambia la DESCRIPCIÓN del directo de YouTube (el texto largo debajo del video), "
           "con los enlaces y hashtags que pida. Usala SIEMPRE que diga descripción.", {
            "descripcion": {"type": "string", "description": "Lo redactás vos: 2 a 4 frases con onda sobre lo que pidió, en "
                                                             "español latino, con emojis si queda bien y SIN enlaces"},
            "enlaces": {"type": "array", "items": {"type": "string"},
                        "description": "Nombres de los enlaces que pidió poner (discord, kick, tiktok, instagram…); vacío si no pidió"},
            "hashtags": {"type": "array", "items": {"type": "string"},
                         "description": "Si pidió hashtags: 3 a 6, sin # ni espacios (p. ej. WoWForever); vacío si no"},
        }, ["descripcion"]),
        _f("consultar_titulo", "Dice cómo está el directo: el título en Kick y en YouTube y la descripción de YouTube. "
           "Usala si pregunta qué título tiene o pide revisar su directo o emisión.", {}, []),
        _f("restaurar_titulo", "Vuelve a poner el título anterior.", {}, []),
        _f("crear_miniatura", "Crea miniaturas con el estilo de la guild a partir de una captura de OBS.", {
            "titulo": {"type": "string", "description": "Texto grande, 2 a 6 palabras impactantes"},
            "subtitulo": {"type": "string", "description": "Texto chico opcional (p. ej. Día 1, Nivel 20-30)"},
            "subir_youtube": {"type": "boolean", "description": "true si pide ponerla en YouTube"},
            "idea": {"type": "string", "description": "Cómo la imagina: composición, personajes, colores, efectos (tal como lo dijo); vacío si no dijo"},
        }, ["titulo"]),
        _f("moderar_chat", "Banea, silencia (timeout) o desbanea a alguien del chat del stream en Kick y/o YouTube.", {
            "accion": {"type": "string", "enum": ["banear", "silenciar", "desbanear"],
                       "description": "banear = para siempre; silenciar = un rato (timeout, mutear, castigar); desbanear = quitar el ban"},
            "usuario": {"type": "string", "description": "El nombre del usuario COPIADO tal como lo dijo, sin completarlo ni inventarlo"},
            "minutos": {"type": "integer", "description": "Solo para silenciar: cuántos minutos (1 hora = 60). 0 si no lo dijo"},
            "plataformas": {"type": "array", "items": {"type": "string", "enum": ["kick", "youtube"]},
                            "description": "Las que nombró; vacío si no nombró ninguna (se busca en las dos)"},
            "motivo": {"type": "string", "description": "El motivo si lo dijo; vacío si no"},
        }, ["accion", "usuario"]),
        _f("mandar_al_chat", "Escribe en el chat del stream (Kick y YouTube): un enlace guardado y/o un texto corto.", {
            "enlace": {"type": "string", "description": "Nombre del enlace que pidió (discord, instagram, tienda…); vacío si no pidió un enlace"},
            "texto": {"type": "string", "description": "Lo que pidió escribir, corregido; vacío si solo pidió el enlace"},
            "plataformas": {"type": "array", "items": {"type": "string", "enum": ["kick", "youtube"]},
                            "description": "Las que nombró; vacío si no nombró ninguna (va a las dos)"},
        }, ["enlace", "texto"]),
        _f("guardar_enlace", "Guarda el enlace que Nicolas tiene copiado con el nombre que dice, para mandarlo al chat después.", {
            "nombre": {"type": "string", "description": "Nombre corto para el enlace, p. ej. discord, instagram, tienda"},
        }, ["nombre"]),
        _f("overlay", "Crea, mueve, oculta, muestra o quita un overlay (cartel o gráfico) en la pantalla del stream en OBS.", {
            "accion": {"type": "string", "enum": ["crear", "mover", "ocultar", "mostrar", "quitar"]},
            "nombre": {"type": "string", "description": "Nombre corto para reconocerlo después, p. ej. raid molten core, redes, cuenta regresiva"},
            "descripcion": {"type": "string", "description": "Solo para crear: qué tiene que mostrar, con los textos EXACTOS que dijo"},
            "posicion": {"type": "string", "enum": OVERLAY_POSICIONES, "description": "Dónde va. arriba-derecha si no lo dijo"},
            "tamano": {"type": "string", "enum": ["chico", "mediano", "grande"], "description": "mediano si no lo dijo"},
        }, ["accion", "nombre"]),
        _f("responder", "Contesta en voz alta (se escucha en el stream) cuando Nicolas te habla a vos, charla, te molesta, te pide un chiste, saludar al stream, bardear al chat o te hace una pregunta que sabés, sin pedir publicar ni cambiar nada. No publica nada.", {
            "respuesta": {"type": "string", "description": "Lo que decís como El Cerebro: 1 a 3 frases cortas, graciosas y con onda, en español latino"},
            "animo": {"type": "string", "enum": ["normal", "picado", "feliz"],
                      "description": "picado si te molestan, te bardean o te piden bardear; feliz si te felicitan o saludás; si no, normal"},
        }, ["respuesta"]),
        _f("buscar_en_internet", "Busca en internet y contesta en voz alta. Solo para preguntas que necesitan datos actuales o que no sabés seguro: noticias, resultados, precios, parches, estrenos, clima, quién ganó, info puntual de WoW.", {
            "pregunta": {"type": "string", "description": "La pregunta, corregida y completa, para buscar"},
        }, ["pregunta"]),
        _f("pedir_aclaracion", "Úsala SOLO si falta un dato imprescindible o la orden no tiene sentido.", {
            "pregunta": {"type": "string", "description": "Pregunta corta para Nicolas"},
        }, ["pregunta"]),
    ]


# ---------------------------------------------------------------- utilidades
def calendario(hoy=None, dias=15):
    hoy = hoy or dt.date.today()
    filas = []
    for i in range(dias):
        d = hoy + dt.timedelta(days=i)
        etiqueta = "hoy" if i == 0 else "mañana" if i == 1 else ""
        filas.append(f"- {DIAS[d.weekday()]} {d.isoformat()}" + (f" ({etiqueta})" if etiqueta else ""))
    return "\n".join(filas)


def fecha_legible(d):
    return f"{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d} a las {d:%H:%M}"


def _hora(texto):
    t = str(texto or "").strip().lower().replace(".", ":").replace("hs", "").replace("h", ":").strip(": ")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\s?m|p\s?m)?", t)
    if not m:
        raise ErrorOrden(f"No entendí la hora «{texto}».")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) and m.group(3).replace(" ", "").startswith("p") and h < 12:
        h += 12
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ErrorOrden(f"La hora «{texto}» no existe.")
    return h, mi


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
_DIAS_N = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_RE_DIA = re.compile(r"\b(" + "|".join(_DIAS_N) + r")\b")
_RE_SEMANA_QUE_VIENE = re.compile(r"semana (que viene|proxima|siguiente)|proxima semana|otra semana")
_RE_MANANA = re.compile(r"(?<!la )\bmanana\b")        # "mañana", pero no "de la mañana"
_RE_HOY = re.compile(r"\b(hoy|esta noche|esta tarde|esta mañana|esta manana)\b")


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def resolver_dia(dia, hoy=None):
    """Convierte el día que dijo Nicolas en una fecha. Lo calcula Python, no la IA.

    Devuelve (fecha, por_nombre): por_nombre es True si vino de un nombre de día ("viernes"),
    para pasar a la semana siguiente si ese día es hoy y la hora ya pasó.
    """
    hoy = hoy or dt.date.today()
    t = _norm(dia)
    if not t:
        raise ErrorOrden("Falta el día.")
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), False
        except ValueError:
            raise ErrorOrden(f"La fecha «{dia}» no existe.")
    nombres = set(_RE_DIA.findall(t))
    if len(nombres) > 1:
        raise ErrorOrden(f"Nombraste varios días ({', '.join(sorted(nombres))}): ¿cuál?")
    nombre = nombres.pop() if nombres else None

    # número de día: "el 15", "15 de noviembre", "14/11"
    m = re.search(r"\b(\d{1,2})(?:\s*(?:de\s+)?(" + "|".join(MESES) + r")|\s*[/-]\s*(\d{1,2}))?\b", t)
    if m:
        num = int(m.group(1))
        mes = MESES.index(m.group(2)) + 1 if m.group(2) else int(m.group(3)) if m.group(3) else None
        anio = hoy.year
        try:
            if mes:
                d = dt.date(anio, mes, num)
                if d < hoy:
                    d = dt.date(anio + 1, mes, num)
            else:
                d = dt.date(anio, hoy.month, num) if num >= hoy.day else None
                if d is None:
                    sig = (hoy.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
                    d = dt.date(sig.year, sig.month, num)
        except ValueError:
            raise ErrorOrden(f"El día «{dia}» no existe.")
        if nombre and _DIAS_N[d.weekday()] != nombre:
            raise ErrorOrden(f"El {d.day:02d}/{d.month:02d} es {DIAS[d.weekday()]}, no {DIAS[_DIAS_N.index(nombre)]}: ¿qué día es?")
        return d, False

    if nombre:
        objetivo = _DIAS_N.index(nombre)
        if _RE_SEMANA_QUE_VIENE.search(t):
            lunes_sig = hoy + dt.timedelta(days=7 - hoy.weekday())
            return lunes_sig + dt.timedelta(days=objetivo), False
        return hoy + dt.timedelta(days=(objetivo - hoy.weekday()) % 7), True
    if "pasado manana" in t:
        return hoy + dt.timedelta(days=2), False
    if _RE_MANANA.search(t):
        return hoy + dt.timedelta(days=1), False
    if _RE_HOY.search(t):
        return hoy, False
    raise ErrorOrden(f"No entendí el día «{dia}».")


def dia_en_texto(texto):
    """El día que Nicolas dijo en la frase original, si es uno solo y claro (si no, None).

    Sirve para corregir a la IA si calculó mal: lo que dijo Nicolas manda.
    """
    t = _norm(texto)
    nombres = set(_RE_DIA.findall(t))
    if len(nombres) > 1:
        return None
    if nombres:
        nombre = nombres.pop()
        m = re.search(nombre + r"\s+(\d{1,2}(?:\s*[/-]\s*\d{1,2})?)\b", t)
        if m:
            return f"{nombre} {m.group(1)}"
        return nombre + (" de la semana que viene" if _RE_SEMANA_QUE_VIENE.search(t) else "")
    if "pasado manana" in t:
        return "pasado mañana"
    if _RE_MANANA.search(t):
        return "mañana"
    if _RE_HOY.search(t):
        return "hoy"
    return None


def corregir_dia(texto, fecha_ia, hoy=None):
    """Devuelve el día a usar: el de la IA, salvo que contradiga lo que Nicolas dijo en la frase."""
    dicho = dia_en_texto(texto)
    if not dicho:
        return fecha_ia
    d_dicho, solo_nombre = resolver_dia(dicho, hoy)
    try:
        d_ia, _ = resolver_dia(fecha_ia, hoy)
    except ErrorOrden:
        return dicho
    if solo_nombre:                       # dijo "el viernes": basta con que la IA haya puesto un viernes
        return fecha_ia if d_ia.weekday() == d_dicho.weekday() else dicho
    return fecha_ia if d_ia == d_dicho else dicho


_ACCION_INVENTADA = re.compile(r"anot|inscrib|apunt|registr|https?://|#\w", re.I)


_RE_HORA_DICHA = re.compile(r"\ba las (\d{1,2})(?::(\d{2})| y (media|cuarto))?(?: (?:de la )?(manana|tarde|noche|am|pm))?")


def hora_fiel(dicho, texto):
    """Dijiste «a las 10» y el texto dice 21:00: se pone la hora que dijiste (a las 10 = 22:00, salvo «de la mañana»)."""
    dichas = _RE_HORA_DICHA.findall(_norm(dicho))
    escritas = re.findall(r"\b(\d{1,2}):(\d{2})\b", texto)
    if len(dichas) != 1 or len(escritas) != 1:
        return texto
    h, mi, frac, parte = dichas[0]
    h = int(h)
    mi = int(mi) if mi else (30 if frac == "media" else 15 if frac == "cuarto" else 0)
    if h > 23 or mi > 59:
        return texto
    hh = h % 12 if parte in ("manana", "am") else (h + 12 if h <= 11 else h)
    if (int(escritas[0][0]), int(escritas[0][1])) in ((hh, mi), (h, mi)):
        return texto
    return re.sub(r"\b\d{1,2}:\d{2}\b", f"{hh:02d}:{mi:02d}", texto, count=1)


def texto_fiel(dicho, texto, quitar_hoy=False):
    """Arregla lo que el modelo agrega por su cuenta en textos públicos.

    - Si dijiste «mañana» y el texto dice «hoy» / «esta noche» (o al revés), se corrige al día que dijiste.
    - Quita las frases con instrucciones que no pediste («anótense», «inscríbanse», canales, links).
    - La hora es la que dijiste (hora_fiel).
    """
    d = _norm(dicho)
    t = str(texto or "")
    dijo_manana, dijo_hoy = bool(_RE_MANANA.search(d)), bool(_RE_HOY.search(d))
    if dijo_manana and not dijo_hoy:
        t = re.sub(r"\b[Ee]sta noche\b", lambda m: "Mañana por la noche" if m.group(0)[0] == "E" else "mañana por la noche", t)
        t = re.sub(r"\b[Hh]oy\b", lambda m: "Mañana" if m.group(0)[0] == "H" else "mañana", t)
    elif dijo_hoy and not dijo_manana:
        t = re.sub(r"(?<!de la )(?<!por la )\b[Mm]añana\b", lambda m: "Hoy" if m.group(0)[0] == "M" else "hoy", t)
    t = hora_fiel(dicho, t)
    if quitar_hoy and not dijo_hoy and not dijo_manana and not dia_en_texto(dicho):
        t = re.sub(r"\s*[·•\-–|,]?\s*\b[Hh]oy\b", "", t)       # no dijo ningún día: no se inventa «hoy»
    if not _ACCION_INVENTADA.search(d):
        frases = re.split(r"(?<=[.!?…])\s+", t)
        limpias = [f for f in frases if not _ACCION_INVENTADA.search(f)]
        if limpias:
            t = " ".join(limpias)
    return t.strip()


def fecha_hora(fecha, hora, ahora=None):
    ahora = ahora or dt.datetime.now()
    d, por_nombre = resolver_dia(fecha, ahora.date())
    h, mi = _hora(hora)
    cuando = dt.datetime(d.year, d.month, d.day, h, mi)
    if por_nombre and cuando < ahora:
        cuando += dt.timedelta(days=7)      # "el martes" dicho un martes a la noche = el martes que viene
    if cuando < ahora:
        raise ErrorOrden(f"El {fecha_legible(cuando)} ya pasó.")
    if cuando > ahora + dt.timedelta(days=120):
        raise ErrorOrden(f"El {fecha_legible(cuando)} está a más de 4 meses: revisa la fecha.")
    return cuando


def _txt(a, campo, maximo, obligatorio=True):
    v = re.sub(r"\s+\n", "\n", str(a.get(campo) or "")).strip()
    if obligatorio and not v:
        raise ErrorOrden(f"Falta {campo.replace('_', ' ')}.")
    return v[:maximo]


def _ent(a, campo, minimo, maximo, defecto):
    try:
        v = int(round(float(a.get(campo, defecto) if a.get(campo) not in (None, "") else defecto)))
    except (TypeError, ValueError):
        raise ErrorOrden(f"{campo} tiene que ser un número.")
    if not minimo <= v <= maximo:
        raise ErrorOrden(f"{campo} tiene que estar entre {minimo} y {maximo} (dijiste {v}).")
    return v


def _mencion(a):
    m = str(a.get("mencionar") or "ninguno").strip()
    if m.lower() in ("ninguno", "none", "", "nadie"):
        return None
    if m.lower() in ("everyone", "@everyone", "todos"):
        return "everyone"
    for rol in config.ROLES_MENCIONABLES:
        if rol.lower() == m.lower():
            return rol
    raise ErrorOrden(f"No conozco el rol «{m}».")


# Cómo lo dice Nicolas (o lo escribe Whisper) -> el canal del Discord
SINONIMOS_CANAL = [
    ("raids-signup", r"regist|inscri|anot|sign|sing|sain|sin ?ap|sin ?up|rising|signup"),
    ("anuncios-guild", r"anunci|aviso"),
    ("en-vivo", r"en ?vivo|directo|live"),
    ("videos-nuevos", r"video"),
    ("clips-y-memes", r"clip|meme"),
    ("builds-y-guias", r"build|guia"),
    ("subidas-de-nivel", r"nivel|level|subida"),
    ("general", r"general|charla"),
]


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def _compacto(t):
    return re.sub(r"[^a-z0-9]", "", sin_tildes(t))


def buscar_canal(dicho):
    """El canal del Discord que quiso decir («Raids Sin Up», «raidsingup», «registro») o None si no se parece a ninguno."""
    import difflib
    lista = config.CANALES_DISCORD
    c = str(dicho or "").strip().lstrip("#").lower().replace(" ", "-")
    if not c or not lista or c in lista:
        return c or None
    compactos = {_compacto(x): x for x in lista}
    k = _compacto(c)
    if k in compactos:
        return compactos[k]
    parecido = difflib.get_close_matches(k, list(compactos), n=1, cutoff=0.75)
    if parecido:
        return compactos[parecido[0]]
    for canal, patron in SINONIMOS_CANAL:
        if canal in lista and re.search(patron, sin_tildes(c).replace("-", " ")):
            return canal
    return None


def _canal(a, defecto=None):
    """El canal pedido, corregido. Si no existe ninguno parecido, va al de siempre (y el resumen lo dice)."""
    dicho = str(a.get("canal") or "").strip()
    if _vacio(dicho):
        return defecto
    return buscar_canal(dicho) or defecto


def _aviso_canal(a, canal):
    dicho = str(a.get("canal") or "").strip()
    if not _vacio(dicho) and not buscar_canal(dicho):
        return f"\n(No tengo un canal «{dicho}»: va {('a #' + canal) if canal else 'al de siempre'}.)"
    return ""


def _mencion_txt(m):
    return "sin etiquetar a nadie" if not m else ("etiquetando a @everyone" if m == "everyone" else f"etiquetando a @{m}")


def _vacio(v):
    return str(v or "").strip().lower() in ("", "none", "null")


def _falta_dia_u_hora(nombre, a):
    """Raid o banda sin raid, día, hora o cupos: se pregunta (sin inventar) y la respuesta completa la orden."""
    que = "la raid" if nombre == "crear_raid" else "la banda"
    de = f" de {str(a.get('nombre')).strip()}" if not _vacio(a.get("nombre")) else ""
    if nombre == "crear_raid" and _vacio(a.get("nombre")):
        p = "¿Qué raid es?"
    elif _vacio(a.get("fecha")):
        p = f"¿Qué día es {que}{de}?"
    elif _vacio(a.get("hora")):
        d, _ = resolver_dia(a.get("fecha"))
        p = f"¿A qué hora es {que}{de} del {DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}?"
    elif nombre == "crear_raid" and _vacio(a.get("cupo")):
        p = f"¿Cuántos cupos tiene {que}{de}?"
    else:
        return None
    return Accion("aclaracion", {"pregunta": p}, p, False)


# ---------------------------------------------------------------- construir
ICONOS_ENLACE = {"discord": "💬", "kick": "🟢", "tiktok": "🎵", "youtube": "▶️", "instagram": "📸", "insta": "📸",
                 "twitter": "🐦", "x": "🐦", "facebook": "📘", "tienda": "🛒", "twitch": "🟣", "whatsapp": "📱"}
ETIQUETAS_ENLACE = {"discord": f"Discord de la hermandad {config.NOMBRE_GUILD}", "kick": "Kick", "tiktok": "TikTok",
                    "youtube": "YouTube", "instagram": "Instagram", "insta": "Instagram", "twitter": "X (Twitter)",
                    "facebook": "Facebook", "tienda": "Tienda", "twitch": "Twitch", "whatsapp": "WhatsApp"}
_URL_SUELTA = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:com|gg|tv|net|org|io|me|ly)(?:/\S*)?)", re.I)


def descripcion_completa(a):
    """(texto, faltan): lo que redactó la IA + los enlaces reales (de enlaces.txt; nunca inventados) + los hashtags."""
    import enlaces
    texto = _URL_SUELTA.sub("", _txt(a, "descripcion", 3000, False)).strip()
    texto = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", texto))
    lineas, faltan, vistos = [], [], set()
    for n in a.get("enlaces") or []:
        k = sin_tildes(n).strip().lstrip("@#").split()[-1] if str(n).strip() else ""
        if not k or k in vistos:
            continue
        vistos.add(k)
        hallado = enlaces.buscar(k)
        url = hallado[1] if hallado else (f"https://kick.com/{config.KICK_CANAL}" if k == "kick" and config.KICK_CANAL else "")
        if not url:
            faltan.append(k)
            continue
        lineas.append(f"{ICONOS_ENLACE.get(k, '🔗')} {ETIQUETAS_ENLACE.get(k, k.capitalize())}: {url}")
    tags = []
    for h in a.get("hashtags") or []:
        t = re.sub(r"[^\w]", "", sin_tildes(h) if not str(h).isascii() else str(h))
        if t and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    partes = [texto] + (["\n".join(lineas)] if lineas else []) + ([" ".join("#" + t for t in tags[:8])] if tags else [])
    return "\n\n".join(p for p in partes if p), faltan


def construir(nombre, a):
    """Valida los argumentos del modelo y devuelve la Accion a ejecutar."""
    a = a or {}
    publica = config.CONFIRMAR in ("publicaciones", "todo")
    todo = config.CONFIRMAR == "todo"

    if nombre == "publicar_anuncio":
        tipo = a.get("tipo") if a.get("tipo") in TIPOS_ANUNCIO else "aviso"
        orden = {"accion": "anuncio", "titulo": _txt(a, "titulo", 120), "texto": _txt(a, "texto", 1500),
                 "tipo": tipo, "mencionar": _mencion(a), "canal": _canal(a)}
        donde = f"#{orden['canal']}" if orden["canal"] else "el canal de anuncios"
        resumen = (f"Anuncio ({tipo}) en {donde}, {_mencion_txt(orden['mencionar'])}:\n"
                   f"«{orden['titulo']}»\n{orden['texto']}" + _aviso_canal(a, orden["canal"]))
        return Accion("hogger", orden, resumen, publica)

    if nombre in ("crear_raid", "crear_banda"):
        falta = _falta_dia_u_hora(nombre, a)
        if falta:
            return falta

    if nombre == "crear_raid":
        cuando = fecha_hora(a.get("fecha"), a.get("hora"))
        orden = {"accion": "raid", "nombre": nombre_conocido(_txt(a, "nombre", 100)), "fecha": cuando.strftime("%Y-%m-%d %H:%M"),
                 "cupo": _ent(a, "cupo", 5, 40, 20), "nota": _txt(a, "nota", 500, False),
                 "avisar": a.get("avisar", True) is not False}
        resumen = (f"Raid {orden['nombre']} el {fecha_legible(cuando)}, {orden['cupo']} cupos"
                   + (f". Nota: {orden['nota']}" if orden["nota"] else "")
                   + ("" if orden["avisar"] else ". Sin etiquetar"))
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_banda":
        cuando = fecha_hora(a.get("fecha"), a.get("hora"))
        orden = {"accion": "banda", "nombre": nombre_conocido(_txt(a, "nombre", 100)),
                 "cuando": f"{DIAS[cuando.weekday()].capitalize()} {cuando:%d/%m %H:%M}",
                 "tanques": _ent(a, "tanques", 0, 40, 1), "healers": _ent(a, "healers", 0, 40, 1),
                 "dps": _ent(a, "dps", 0, 40, 3), "nota": _txt(a, "nota", 500, False)}
        resumen = (f"Banda {orden['nombre']} el {fecha_legible(cuando)}: {orden['tanques']} tanque, "
                   f"{orden['healers']} healer, {orden['dps']} DPS")
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_sorteo":
        try:
            horas = float(a.get("horas") or 24)
        except (TypeError, ValueError):
            raise ErrorOrden("La duración del sorteo tiene que ser un número de horas.")
        if not 0.05 <= horas <= 720:
            raise ErrorOrden("El sorteo tiene que durar entre 3 minutos y 30 días.")
        orden = {"accion": "sorteo", "premio": _txt(a, "premio", 200), "horas": horas,
                 "ganadores": _ent(a, "ganadores", 1, 20, 1), "descripcion": _txt(a, "descripcion", 1000, False),
                 "canal": _canal(a)}
        dura = f"{horas:g} horas" if horas < 48 else f"{horas / 24:g} días"
        donde = f"#{orden['canal']}" if orden["canal"] else "el canal de sorteos"
        resumen = f"Sorteo de {orden['premio']} en {donde}, {orden['ganadores']} ganador(es), dura {dura}" + _aviso_canal(a, orden["canal"])
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_encuesta":
        ops = [str(o).strip()[:80] for o in (a.get("opciones") or []) if str(o).strip()]
        if not 2 <= len(ops) <= 5:
            raise ErrorOrden("La encuesta necesita entre 2 y 5 opciones.")
        orden = {"accion": "encuesta", "pregunta": _txt(a, "pregunta", 240), "opciones": ops,
                 "horas": _ent(a, "horas", 1, 720, 24), "mencionar": _mencion(a), "canal": _canal(a)}
        donde = f"#{orden['canal']}" if orden["canal"] else "el canal de encuestas"
        resumen = (f"Encuesta en {donde}, {_mencion_txt(orden['mencionar'])}: «{orden['pregunta']}»: "
                   f"{' / '.join(ops)} ({orden['horas']} h)" + _aviso_canal(a, orden["canal"]))
        return Accion("hogger", orden, resumen, publica)

    if nombre == "mensaje_discord":
        orden = {"accion": "mensaje", "texto": _txt(a, "texto", 1500), "canal": _canal(a, "general")}
        return Accion("hogger", orden, f"Mensaje en #{orden['canal']}: {orden['texto']}" + _aviso_canal(a, orden["canal"]),
                      publica)

    if nombre == "cerrar_inscripciones":
        tipo = a.get("tipo") if a.get("tipo") in ("raid", "banda") else "raid"
        orden = {"accion": "cerrar", "tipo": tipo, "id": "ultimo", "cerrar": not a.get("reabrir")}
        verbo = "Cerrar" if orden["cerrar"] else "Reabrir"
        return Accion("hogger", orden, f"{verbo} inscripciones de la última {tipo}", todo)

    if nombre == "deshacer_ultima_publicacion":
        return Accion("deshacer", {}, "Borrar la última publicación del Cerebro en Discord", todo)

    if nombre == "cambiar_titulo_stream":
        titulo = _txt(a, "titulo", 100).rstrip(" .")
        titulo = titulo[0].upper() + titulo[1:]          # «subiendo al guerrero…» -> «Subiendo al guerrero…»
        plataformas = [p for p in (a.get("plataformas") or PLATAFORMAS) if p in PLATAFORMAS] or PLATAFORMAS
        mini = None
        if not _vacio(a.get("miniatura")):
            mini = {"titulo": _txt(a, "miniatura", 60), "subtitulo": _txt(a, "miniatura_subtitulo", 60, False),
                    "idea": _txt(a, "miniatura_idea", 1500, False)}
            # El diseñador sabe el título del directo: la miniatura lo complementa, no lo repite
            mini["idea"] = (mini["idea"] + f"\n(El título del directo es «{titulo}»: la miniatura lo complementa, no lo "
                            "repite.)").strip()
        juego = "" if _vacio(a.get("juego")) else _txt(a, "juego", 80, False)
        resumen = f"Título «{titulo}» en {', '.join(NOMBRES[p] for p in plataformas)}"
        descripcion = None
        if not _vacio(a.get("descripcion")):          # «cambiá el título y la descripción»: van juntos a YouTube
            descripcion, faltan = descripcion_completa(a)
            if "youtube" not in plataformas:
                plataformas = plataformas + ["youtube"]
                resumen = f"Título «{titulo}» en {', '.join(NOMBRES[p] for p in plataformas)}"
            resumen += f"\nDescripción de YouTube:\n{descripcion}"
            if faltan:
                resumen += f"\n(No tengo guardado tu link de {', '.join(faltan)}.)"
        if juego:
            resumen += f"\nJuego en Kick: {juego}"
        if mini:
            resumen += f"\nMiniatura «{mini['titulo']}»" + (f" · {mini['subtitulo']}" if mini["subtitulo"] else "")
            idea_dicha = mini["idea"].split("\n(El título del directo es")[0].strip()
            resumen += (f"\nArte: {idea_dicha[:300]}" if a.get("_empaquetado") else f" ({idea_dicha})") if idea_dicha else ""
            resumen += " y la subo a YouTube" if "youtube" in plataformas or config.MINIATURA_SUBIR_YOUTUBE else ""
        # El título se ve en público: se confirma con «dale» igual que lo de Discord (salvo CONFIRMAR=nada)
        datos = {"titulo": titulo, "plataformas": plataformas, "miniatura": mini, "juego": juego}
        if descripcion:
            datos["descripcion"] = descripcion
        return Accion("titulo", datos, resumen, publica)

    if nombre == "cambiar_descripcion_stream":
        texto, faltan = descripcion_completa(a)
        aviso = (f"\n(No tengo guardado tu link de {', '.join(faltan)}: copialo y decí «guardá este enlace como "
                 f"{faltan[0]}».)" if faltan else "")
        return Accion("descripcion", {"descripcion": texto}, f"Descripción del directo de YouTube:\n{texto}{aviso}", publica)

    if nombre == "cambiar_juego":
        j = _txt(a, "juego", 80)
        return Accion("juego", {"juego": j}, f"Juego del directo en Kick: {j}", publica)

    if nombre == "consultar_titulo":
        return Accion("consultar_titulo", {}, "Ver cómo está el directo (títulos y descripción)", False)

    if nombre == "restaurar_titulo":
        return Accion("restaurar_titulo", {}, "Restaurar el título anterior", todo)

    if nombre == "crear_miniatura":
        d = {"titulo": _txt(a, "titulo", 60), "subtitulo": _txt(a, "subtitulo", 60, False),
             "subir_youtube": bool(a.get("subir_youtube")) or config.MINIATURA_SUBIR_YOUTUBE, "idea": _txt(a, "idea", 1500, False)}
        destino = " y subirla a YouTube" if d["subir_youtube"] else ""
        resumen = f"Miniatura «{d['titulo']}» {d['subtitulo']}{destino}".strip()
        if a.get("_empaquetado"):
            resumen += f"\nArte: {d['idea'][:300]}"
        return Accion("miniatura", d, resumen, d["subir_youtube"] and publica)

    if nombre == "moderar_chat":
        import moderacion
        return moderacion.construir(a)

    if nombre == "mandar_al_chat":
        import enlaces
        plataformas = [p for p in (a.get("plataformas") or []) if p in ("kick", "youtube")] or ["kick", "youtube"]
        enlace = None
        if not _vacio(a.get("enlace")):
            enlace = enlaces.buscar(a["enlace"])
            if not enlace:
                tengo = ", ".join(enlaces.leer()) or "ninguno todavía"
                raise ErrorOrden(f"No tengo guardado el enlace «{a['enlace']}». Tengo: {tengo}. "
                                 "Para guardarlo: copialo y decí «guardá este enlace como …».")
        texto = enlaces.sin_enlaces_inventados(_txt(a, "texto", 400, False), [enlace[1]] if enlace else [])
        if enlace:
            texto = f"{texto} {enlace[1]}" if texto else f"{enlace[0].capitalize()}: {enlace[1]}"
        if not texto:
            raise ErrorOrden("¿Qué mando al chat?")
        return Accion("chat", {"texto": texto, "plataformas": plataformas},
                      f"Mandar al chat de {' y '.join(NOMBRES[p] for p in plataformas)}:\n«{texto}»", publica)

    if nombre == "guardar_enlace":
        import enlaces
        n = _txt(a, "nombre", 40)
        try:
            url = enlaces.del_portapapeles()
        except ValueError as e:
            raise ErrorOrden(str(e))
        ya = enlaces.buscar(n)
        extra = f" (reemplaza el que tenía: {ya[1]})" if ya and enlaces._clave(ya[0]) == enlaces._clave(n) else ""
        return Accion("guardar_enlace", {"nombre": n, "url": url}, f"Guardar el enlace «{n}»: {url}{extra}", False)

    if nombre == "overlay":
        acc = a.get("accion") if a.get("accion") in ("crear", "mover", "ocultar", "mostrar", "quitar") else "crear"
        d = {"accion": acc, "nombre": _txt(a, "nombre", 40),
             "posicion": a.get("posicion") if a.get("posicion") in OVERLAY_POSICIONES else "arriba-derecha",
             "tamano": a.get("tamano") if a.get("tamano") in ("chico", "mediano", "grande") else "mediano"}
        lugar = d["posicion"].replace("-", " ")
        if acc == "crear":
            d["descripcion"] = _txt(a, "descripcion", 600, False) or d["nombre"]
            return Accion("overlay", d, f"Overlay «{d['nombre']}» ({d['tamano']}, {lugar}):\n{d['descripcion']}", publica)
        if acc == "mover":
            return Accion("overlay", d, f"Mover el overlay «{d['nombre']}» a {lugar}", False)
        verbo = {"ocultar": "Ocultar", "mostrar": "Mostrar", "quitar": "Quitar"}[acc]
        return Accion("overlay", d, f"{verbo} el overlay «{d['nombre']}»", False)

    if nombre == "responder":
        r = re.sub(r"""\s*["']?\s*,\s*animo\s*[=:].*$""", "", _txt(a, "respuesta", 600), flags=re.I).strip() or "…"
        animo = a.get("animo") if a.get("animo") in ("picado", "feliz") else "normal"
        return Accion("respuesta", {"respuesta": r, "animo": animo}, r, False)

    if nombre == "buscar_en_internet":
        p = _txt(a, "pregunta", 300)
        if not config.BUSCAR_INTERNET:
            raise ErrorOrden("La búsqueda en internet está apagada (BUSCAR_INTERNET=false).")
        return Accion("busqueda", {"pregunta": p}, f"Buscando en internet: {p}", False)

    if nombre == "pedir_aclaracion":
        return Accion("aclaracion", {"pregunta": _txt(a, "pregunta", 200)}, _txt(a, "pregunta", 200), False)

    raise ErrorOrden(f"La IA pidió una herramienta que no existe: {nombre}.")
