"""Herramientas que la IA local puede usar.

Cada herramienta tiene tres partes:
  1. El esquema que ve el modelo (nombre, descripción y campos estrictos).
  2. La validación en Python: aquí se decide qué se ejecuta de verdad.
  3. Un resumen en español para confirmar antes de publicar.
El modelo solo propone; nada se publica sin pasar por la validación.
"""
import datetime as dt
import re

import config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
PLATAFORMAS = ["kick", "youtube", "tiktok"]
NOMBRES = {"kick": "Kick", "youtube": "YouTube", "tiktok": "TikTok"}
TIPOS_ANUNCIO = ["aviso", "evento", "importante", "parche"]


class ErrorOrden(Exception):
    """La orden no se puede ejecutar tal cual; el mensaje se le muestra a Nicolas."""


class Accion:
    def __init__(self, tipo, datos, resumen, confirmar):
        self.tipo = tipo            # hogger, titulo, deshacer, consultar_titulo, restaurar_titulo, miniatura, aclaracion
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
    fecha = {"type": "string", "description": "Fecha AAAA-MM-DD, sacada del calendario del sistema"}
    hora = {"type": "string", "description": "Hora HH:MM en formato 24 h (las 9 de la noche = 21:00)"}
    return [
        _f("publicar_anuncio", "Publica un anuncio con el estilo de la guild en el Discord.", {
            "titulo": {"type": "string", "description": "Título corto y llamativo (máx. 80 caracteres)"},
            "texto": {"type": "string", "description": "Cuerpo del anuncio, bien redactado, sin inventar datos"},
            "tipo": {"type": "string", "enum": TIPOS_ANUNCIO, "description": "evento para quedadas y actividades, importante para cambios serios, parche para novedades del juego, aviso para el resto"},
            "mencionar": {"type": "string", "enum": menciones, "description": "A quién etiquetar. 'ninguno' si no lo pidió"},
            "canal": {"type": "string", "description": "Solo si nombró un canal concreto; si no, vacío"},
        }, ["titulo", "texto", "tipo", "mencionar"]),
        _f("crear_raid", "Crea la inscripción de una raid por clase y spec (estilo Raid-Helper).", {
            "nombre": {"type": "string", "description": "Nombre de la raid bien escrito, p. ej. Molten Core"},
            "fecha": fecha, "hora": hora,
            "cupo": {"type": "integer", "description": "Jugadores máximos, de 5 a 40. 20 si no lo dijo"},
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
        }, ["premio", "horas"]),
        _f("crear_encuesta", "Crea una encuesta con botones y resultados en vivo.", {
            "pregunta": {"type": "string"},
            "opciones": {"type": "array", "items": {"type": "string"}, "description": "Entre 2 y 5 opciones"},
            "horas": {"type": "integer", "description": "Duración en horas. 24 si no lo dijo"},
            "mencionar": {"type": "string", "enum": menciones},
        }, ["pregunta", "opciones"]),
        _f("mensaje_discord", "Manda un mensaje simple (sin formato de anuncio) a un canal.", {
            "texto": {"type": "string"},
            "canal": {"type": "string", "description": "Nombre del canal. general si no lo dijo"},
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
        }, ["titulo", "plataformas"]),
        _f("consultar_titulo", "Dice el título actual del directo en Kick.", {}, []),
        _f("restaurar_titulo", "Vuelve a poner el título anterior.", {}, []),
        _f("crear_miniatura", "Crea miniaturas con el estilo de la guild a partir de una captura de OBS.", {
            "titulo": {"type": "string", "description": "Texto grande, 2 a 6 palabras impactantes"},
            "subtitulo": {"type": "string", "description": "Texto chico opcional (p. ej. Día 1, Nivel 20-30)"},
            "subir_youtube": {"type": "boolean", "description": "true si pide ponerla en YouTube"},
        }, ["titulo"]),
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


def fecha_hora(fecha, hora, ahora=None):
    ahora = ahora or dt.datetime.now()
    try:
        d = dt.date.fromisoformat(str(fecha).strip())
    except ValueError:
        raise ErrorOrden(f"No entendí la fecha «{fecha}».")
    h, mi = _hora(hora)
    cuando = dt.datetime(d.year, d.month, d.day, h, mi)
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


def _canal(a):
    c = str(a.get("canal") or "").strip().lstrip("#").lower().replace(" ", "-")
    if not c:
        return None
    if config.CANALES_DISCORD and c not in config.CANALES_DISCORD:
        raise ErrorOrden(f"No existe el canal #{c}.")
    return c


def _mencion_txt(m):
    return "sin etiquetar a nadie" if not m else ("etiquetando a @everyone" if m == "everyone" else f"etiquetando a @{m}")


# ---------------------------------------------------------------- construir
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
                   f"«{orden['titulo']}»\n{orden['texto']}")
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_raid":
        cuando = fecha_hora(a.get("fecha"), a.get("hora"))
        orden = {"accion": "raid", "nombre": _txt(a, "nombre", 100), "fecha": cuando.strftime("%Y-%m-%d %H:%M"),
                 "cupo": _ent(a, "cupo", 5, 40, 20), "nota": _txt(a, "nota", 500, False),
                 "avisar": a.get("avisar", True) is not False}
        resumen = (f"Raid {orden['nombre']} el {fecha_legible(cuando)}, {orden['cupo']} cupos"
                   + (f". Nota: {orden['nota']}" if orden["nota"] else "")
                   + ("" if orden["avisar"] else ". Sin etiquetar"))
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_banda":
        cuando = fecha_hora(a.get("fecha"), a.get("hora"))
        orden = {"accion": "banda", "nombre": _txt(a, "nombre", 100),
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
                 "ganadores": _ent(a, "ganadores", 1, 20, 1), "descripcion": _txt(a, "descripcion", 1000, False)}
        dura = f"{horas:g} horas" if horas < 48 else f"{horas / 24:g} días"
        resumen = f"Sorteo de {orden['premio']}, {orden['ganadores']} ganador(es), dura {dura}"
        return Accion("hogger", orden, resumen, publica)

    if nombre == "crear_encuesta":
        ops = [str(o).strip()[:80] for o in (a.get("opciones") or []) if str(o).strip()]
        if not 2 <= len(ops) <= 5:
            raise ErrorOrden("La encuesta necesita entre 2 y 5 opciones.")
        orden = {"accion": "encuesta", "pregunta": _txt(a, "pregunta", 240), "opciones": ops,
                 "horas": _ent(a, "horas", 1, 720, 24), "mencionar": _mencion(a)}
        resumen = f"Encuesta «{orden['pregunta']}»: {' / '.join(ops)} ({orden['horas']} h)"
        return Accion("hogger", orden, resumen, publica)

    if nombre == "mensaje_discord":
        orden = {"accion": "mensaje", "texto": _txt(a, "texto", 1500), "canal": _canal(a) or "general"}
        return Accion("hogger", orden, f"Mensaje en #{orden['canal']}: {orden['texto']}", publica)

    if nombre == "cerrar_inscripciones":
        tipo = a.get("tipo") if a.get("tipo") in ("raid", "banda") else "raid"
        orden = {"accion": "cerrar", "tipo": tipo, "id": "ultimo", "cerrar": not a.get("reabrir")}
        verbo = "Cerrar" if orden["cerrar"] else "Reabrir"
        return Accion("hogger", orden, f"{verbo} inscripciones de la última {tipo}", todo)

    if nombre == "deshacer_ultima_publicacion":
        return Accion("deshacer", {}, "Borrar la última publicación del Cerebro en Discord", todo)

    if nombre == "cambiar_titulo_stream":
        titulo = _txt(a, "titulo", 100).rstrip(" .")
        plataformas = [p for p in (a.get("plataformas") or PLATAFORMAS) if p in PLATAFORMAS] or PLATAFORMAS
        return Accion("titulo", {"titulo": titulo, "plataformas": plataformas},
                      f"Título «{titulo}» en {', '.join(NOMBRES[p] for p in plataformas)}", todo)

    if nombre == "consultar_titulo":
        return Accion("consultar_titulo", {}, "Consultar el título de Kick", False)

    if nombre == "restaurar_titulo":
        return Accion("restaurar_titulo", {}, "Restaurar el título anterior", todo)

    if nombre == "crear_miniatura":
        d = {"titulo": _txt(a, "titulo", 60), "subtitulo": _txt(a, "subtitulo", 60, False),
             "subir_youtube": bool(a.get("subir_youtube"))}
        destino = " y subirla a YouTube" if d["subir_youtube"] else ""
        return Accion("miniatura", d, f"Miniatura «{d['titulo']}» {d['subtitulo']}{destino}".strip(),
                      d["subir_youtube"] and publica)

    if nombre == "pedir_aclaracion":
        return Accion("aclaracion", {"pregunta": _txt(a, "pregunta", 200)}, _txt(a, "pregunta", 200), False)

    raise ErrorOrden(f"La IA pidió una herramienta que no existe: {nombre}.")
