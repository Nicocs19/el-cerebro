"""El router: convierte lo que dices en una Accion validada.

1. Si hay una orden esperando confirmación y dices "dale" o "cancela", se resuelve sin IA.
2. Si no, la IA local (Ollama) elige UNA herramienta y rellena sus campos.
3. herramientas.construir() valida todo y arma el resumen.
4. Si Ollama no responde, se usan los patrones fijos del MVP (anuncio y título).
"""
import datetime as dt
import json
import re
import unicodedata

import requests

import config
import herramientas as H
import intenciones

CONFIRMA = re.compile(r"^(dale|si|sí|confirmo|confirma|publica(lo)?|manda(lo)?|ok|okay|adelante|hazlo|hacelo|listo|va)\b")
CANCELA = re.compile(r"^(no|cancela(lo)?|olvidalo|olvídalo|dejalo|déjalo|para|stop)\b")

RAIDS = "Molten Core, Onyxia, Blackwing Lair, Zul'Gurub, Ruinas de Ahn'Qiraj (AQ20), Templo de Ahn'Qiraj (AQ40), Naxxramas"


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


def sistema(pendiente=None, ahora=None):
    ahora = ahora or dt.datetime.now()
    texto = f"""Eres El Cerebro, el asistente de streaming de Nicolas (Mr. H), GM de la hermandad "{config.NOMBRE_GUILD}" de World of Warcraft Forever.
Recibes órdenes dictadas por voz (pueden traer errores de transcripción) y SIEMPRE respondes llamando exactamente UNA herramienta.

Ahora es {H.DIAS[ahora.weekday()]} {ahora:%Y-%m-%d %H:%M}. Calendario de los próximos días:
{H.calendario(ahora.date())}

Reglas:
- Fechas: convierte "hoy", "mañana", "el viernes", "el 15" a AAAA-MM-DD usando SOLO el calendario de arriba. Nunca una fecha pasada.
- Horas en 24 h. Para raids, bandas y eventos, "a las 9" sin más significa 21:00; "a las 9 de la mañana" es 09:00.
- No inventes datos (horas, premios, requisitos, cupos) que Nicolas no dijo. Si falta algo imprescindible (por ejemplo la fecha u hora de una raid), usa pedir_aclaracion.
- Textos públicos (anuncios, sorteos, encuestas): {config.TONO}. Corrige errores de dictado y redacta bien, pero respeta lo que quiso decir.
- Títulos de stream: usa el texto que dictó, corregido, sin añadir nada.
- Nombres de raids bien escritos: {RAIDS}. "Guild", "gil", "guil" o "hermandad" significan la hermandad.
- Roles que se pueden etiquetar: {", ".join(config.ROLES_MENCIONABLES)}. Etiqueta solo si lo pide o si es un anuncio de evento para toda la guild ("Eventos de la guild").
- Canales del Discord: {", ".join(config.CANALES_DISCORD) or "(los de siempre)"}. Deja el canal vacío salvo que nombre uno.

Ejemplos:
- "lanza un anuncio a la guild que hoy hacemos mazmorras a las 10" -> publicar_anuncio(titulo="Hoy hay mazmorras", texto="Esta noche a las 22:00 salimos de mazmorras con la hermandad. ¡Vengan preparados! ⚔️", tipo="evento", mencionar="Eventos de la guild")
- "arma una raid de molten cor el viernes a las 9 con 20 cupos" -> crear_raid(nombre="Molten Core", fecha=<viernes del calendario>, hora="21:00", cupo=20)
- "cambia el título a día 1 subiendo guerrero" -> cambiar_titulo_stream(titulo="Día 1 subiendo guerrero", plataformas=["kick","youtube","tiktok"])
- "sortea un mes de juego entre los de la guild, dura dos días" -> crear_sorteo(premio="1 mes de juego", horas=48, ganadores=1)
"""
    if pendiente:
        texto += (f"\nHay una orden ESPERANDO confirmación: {pendiente}. Si Nicolas la corrige (\"cámbiale la hora a las 10\", "
                  "\"mejor 25 cupos\"), vuelve a llamar la MISMA herramienta con todos los datos y la corrección aplicada.\n")
    return texto


def _llamar_ollama(texto, pendiente=None):
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": sistema(pendiente)}, {"role": "user", "content": texto}],
        "tools": H.esquemas(),
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
    print(f"[router] {origen}: {nombre} {json.dumps(args, ensure_ascii=False)}")
    return H.construir(nombre, args), origen


def precargar():
    """Carga el modelo en la GPU al arrancar para que la primera orden sea rápida."""
    try:
        requests.post(f"{config.OLLAMA_URL}/api/generate",
                      json={"model": config.OLLAMA_MODEL, "prompt": "", "keep_alive": config.OLLAMA_KEEP_ALIVE},
                      timeout=180)
        print(f"[router] {config.OLLAMA_MODEL} cargado.")
    except Exception as e:  # noqa: BLE001
        print(f"[router] No pude precargar {config.OLLAMA_MODEL}: {e}")
