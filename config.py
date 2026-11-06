"""Carga la configuración desde el archivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RECURSOS = BASE / "recursos"
SALIDA = BASE / "salida"
for _d in (DATA, SALIDA):
    _d.mkdir(exist_ok=True)
load_dotenv(BASE / ".env")


def _s(nombre, defecto=""):
    return (os.getenv(nombre) or defecto).strip()


def _b(nombre, defecto=False):
    return _s(nombre, str(defecto)).lower() in ("1", "true", "si", "sí", "yes", "on")


def _f(nombre, defecto):
    try:
        return float(_s(nombre, str(defecto)))
    except ValueError:
        return defecto


def _lista(nombre, defecto):
    return [x.strip() for x in _s(nombre, defecto).split(",") if x.strip()]


# --- Teclas ---
HOTKEY = _s("HOTKEY", "ctrl+shift+f12")            # hablar
CONFIRM_HOTKEY = _s("CONFIRM_HOTKEY", "ctrl+shift+f11")  # "dale" sin hablar
CANCEL_HOTKEY = _s("CANCEL_HOTKEY", "ctrl+shift+f10")    # cancelar lo pendiente
# publicaciones = pide "dale" antes de publicar en Discord; todo = también títulos; nada = ejecuta directo
CONFIRMAR = _s("CONFIRMAR", "publicaciones").lower()
CONFIRMAR_SEGUNDOS = _f("CONFIRMAR_SEGUNDOS", 60)
ESCUCHAR_RESPUESTA = _b("ESCUCHAR_RESPUESTA", True)    # después de «¿Lo publico?» te escucha solo, sin la tecla
RESPUESTA_SEGUNDOS = _f("RESPUESTA_SEGUNDOS", 5)       # cuánto espera tu «sí» o «no» antes de cerrar el micrófono

# --- Voz (Whisper local) ---
WHISPER_MODEL = _s("WHISPER_MODEL", "large-v3-turbo")
WHISPER_DEVICE = _s("WHISPER_DEVICE", "auto").lower()
WHISPER_COMPUTE = _s("WHISPER_COMPUTE", "int8_float16")
MIC_DEVICE = _s("MIC_DEVICE")
VAD_THRESHOLD = _f("VAD_THRESHOLD", 0.015)
SILENCE_SECONDS = _f("SILENCE_SECONDS", 1.1)
MAX_SECONDS = _f("MAX_SECONDS", 30)

# --- IA local (Ollama) ---
USE_OLLAMA = _b("USE_OLLAMA", True)
# 127.0.0.1 y no «localhost»: en Windows «localhost» prueba primero IPv6 y pierde 2 s en cada pedido.
OLLAMA_URL = _s("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/").replace("//localhost", "//127.0.0.1")
OLLAMA_MODEL = _s("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_KEEP_ALIVE = _s("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_CTX = int(_f("OLLAMA_CTX", 16384))                # memoria de trabajo de la IA (instrucciones + orden + respuesta)
OLLAMA_ESPERA_CARGA = int(_f("OLLAMA_ESPERA_CARGA", 300))  # segundos para cargar la IA al abrir (con WoW abierto tarda)
OLLAMA_API_KEY = _s("OLLAMA_API_KEY")                     # cuenta gratis de ollama.com: búsqueda web (conectar_busqueda.bat)
BUSCAR_INTERNET = _b("BUSCAR_INTERNET", True)             # buscar en internet cuando la pregunta lo necesita
BUSCAR_CON_CLAUDE = _b("BUSCAR_CON_CLAUDE", True)         # la búsqueda la hace Claude (tu plan) sin acceso a tus archivos
CLAUDE_MODELO_BUSQUEDA = _s("CLAUDE_MODELO_BUSQUEDA", "haiku")   # rápido para buscar y contestar
TONO = _s("TONO", "tono cercano y épico, como un GM de WoW hablándole a su hermandad; español con voseo como Hogger; "
                  "como mucho 2 emojis; frases cortas")

# --- La guild ---
NOMBRE_GUILD = _s("NOMBRE_GUILD", "The H's")
ROLES_MENCIONABLES = _lista("ROLES_MENCIONABLES", "Eventos de la guild,Llamado a bandas,Sorteos,En vivo,Videos nuevos")
CANALES_DISCORD = _lista("CANALES_DISCORD", "anuncios-guild,general,raids-signup,en-vivo,videos-nuevos,"
                                            "clips-y-memes,builds-y-guias,subidas-de-nivel")

# --- Hogger (bot de Discord en Google Cloud) ---
HOGGER_TOKEN = _s("HOGGER_TOKEN")
HOGGER_GUILD_ID = _s("HOGGER_GUILD_ID")
CANAL_CEREBRO = _s("CANAL_CEREBRO", "cerebro")

# --- Discord por webhook (respaldo si Hogger no está configurado) ---
DISCORD_WEBHOOK_URL = _s("DISCORD_WEBHOOK_URL")
DISCORD_MENTION = _s("DISCORD_MENTION")
DISCORD_NAME = _s("DISCORD_NAME")

# --- Kick ---
KICK_CLIENT_ID = _s("KICK_CLIENT_ID")
KICK_CLIENT_SECRET = _s("KICK_CLIENT_SECRET")
KICK_REDIRECT_URI = _s("KICK_REDIRECT_URI", "http://localhost:8765/callback")
KICK_CATEGORY_ID = _s("KICK_CATEGORY_ID")
KICK_CANAL = _s("KICK_CANAL", "misterache")              # tu canal (para el link de Kick en la descripción)
KICK_TOKENS = DATA / "kick_tokens.json"
# --- Chat del stream (moderación por voz y enlaces) ---
CHAT_KICK = _b("CHAT_KICK", True)                       # escuchar el chat de Kick para encontrar a quién moderar
KICK_CHATROOM_ID = _s("KICK_CHATROOM_ID")               # número de la sala del chat (conectar_kick.bat lo guarda solo)
KICK_PUSHER_KEY = _s("KICK_PUSHER_KEY", "34bf7a0ff419a2a775b9")   # Kick la cambió en oct 2026; se actualiza sola
KICK_PUSHER_CLUSTER = _s("KICK_PUSHER_CLUSTER", "us2")
SILENCIO_MINUTOS = int(_f("SILENCIO_MINUTOS", 10))      # «silenciá a X» sin decir cuánto
ENLACES = BASE / "enlaces.txt"                          # los enlaces que se pueden mandar al chat

# --- YouTube ---
YOUTUBE_CLIENT_SECRET = BASE / _s("YOUTUBE_CLIENT_SECRET", "client_secret.json")
YOUTUBE_TOKEN = DATA / "youtube_token.json"
YOUTUBE_CATEGORY_ID = _s("YOUTUBE_CATEGORY_ID", "20")  # 20 = Gaming

# --- TikTok LIVE Studio ---
TIKTOK_MODO = _s("TIKTOK_MODO", "portapapeles").lower()  # portapapeles | automatico

# --- Modo Jarvis: voz que te habla y orbe animado ---
JARVIS_VOZ = _b("JARVIS_VOZ", True)
JARVIS_ORBE = _b("JARVIS_ORBE", True)
NOMBRE_ASISTENTE = _s("NOMBRE_ASISTENTE", "Hogger el H")    # cómo se llama el asistente (en pantalla y en la charla)
JARVIS_SALUDO = _s("JARVIS_SALUDO", "¡Hogger el H en línea! La manada de The H's está lista.")
ELEVEN_API_KEY = _s("ELEVEN_API_KEY")                     # ElevenLabs (voz principal); vacío = solo voz local
ELEVEN_VOZ = _s("ELEVEN_VOZ", "Daniel")                    # nombre de la voz en tu cuenta o su ID
ELEVEN_MODELO = _s("ELEVEN_MODELO", "eleven_flash_v2_5")   # rápido y gasta la mitad de créditos
VOZ_MODELO = _s("VOZ_MODELO", "es_MX-claude-high")      # voz local de respaldo (Piper, rhasspy/piper-voices)
VOZ_DISPOSITIVO = _s("VOZ_DISPOSITIVO")                  # salida de audio (nombre o número); vacío = la predeterminada
VOZ_VELOCIDAD = _f("VOZ_VELOCIDAD", 1.1)
VOZ_EN_VIVO = _b("VOZ_EN_VIVO", True)                    # empieza a sonar mientras ElevenLabs genera el resto
VOZ_ESPERA_MAX = _f("VOZ_ESPERA_MAX", 3.5)               # si ElevenLabs no empieza en estos segundos, habla la voz local
# --- Memoria corta de la charla (solo en tu PC; se olvida sola y al cerrar El Cerebro) ---
MEMORIA = _b("MEMORIA", True)
MEMORIA_MINUTOS = _f("MEMORIA_MINUTOS", 10)           # cuánto se acuerda de lo que hablaron
MEMORIA_FRASES = int(_f("MEMORIA_FRASES", 12))        # cuántas frases (tuyas y de él) como máximo
BUSQUEDA_RAPIDA_PRIMERO = _b("BUSQUEDA_RAPIDA_PRIMERO", True)   # con clave de ollama.com, primero la rápida
VOZ_RELLENO = _b("VOZ_RELLENO", True)                     # dice «a ver…» si la IA tarda en contestar
VOZ_RELLENO_SEGUNDOS = _f("VOZ_RELLENO_SEGUNDOS", 3)
VOZ_RELLENO_PAUSA = _f("VOZ_RELLENO_PAUSA", 60)        # como mucho un «a ver…» por minuto
VOZ_VOLUMEN = _f("VOZ_VOLUMEN", 0.9)
ORBE_COLOR = _s("ORBE_COLOR", "jarvis").lower()           # solo para el estilo orbe: jarvis (celeste) o dorado
ORBE_ESTILO = _s("ORBE_ESTILO", "cerebro").lower()         # cerebro (con ojos) u orbe (la bolita)
CEREBRO_SIEMPRE = _b("CEREBRO_SIEMPRE", False)             # true = el cerebro queda siempre en pantalla
CEREBRO_DISENO = _s("CEREBRO_DISENO", "hogger").lower()    # hogger (el gnoll), gafas (el cerebro con gafas) o clasico
VOZ_TONO = _f("VOZ_TONO", 4)                              # semitonos: 0 = voz normal, 3 a 5 = voz de dibujito
ORBE_POSICION = _s("ORBE_POSICION", "arriba-derecha").lower()

# --- OBS (para las capturas de las miniaturas) ---
OBS_HOST = _s("OBS_HOST", "127.0.0.1").replace("localhost", "127.0.0.1")
OBS_PORT = int(_f("OBS_PORT", 4455))
OBS_PASSWORD = _s("OBS_PASSWORD")
# Escena o fuente de OBS para el fondo de las miniaturas (p. ej. la captura del juego). Vacío = lo que sale en directo.
OBS_FUENTE = _s("OBS_FUENTE")
MINIATURA_AGENTE = _b("MINIATURA_AGENTE", True)        # si la idea pide imágenes que no tenés, Claude las busca y las baja
MINIATURA_ESPERA = int(_f("MINIATURA_ESPERA", 600))      # segundos máximos para el agente de miniaturas
MINIATURA_REVISAR = _b("MINIATURA_REVISAR", True)      # un Claude mira cómo quedó y corrige si algo se tapa o se corta
MINIATURA_SUBIR_YOUTUBE = _b("MINIATURA_SUBIR_YOUTUBE", True)   # subir sola la miniatura al directo de YouTube
MINIATURA_CLAUDE = _b("MINIATURA_CLAUDE", True)        # las miniaturas las diseña Claude (si falla, plantilla dorada)
MINIATURA_MOSTRAR = _b("MINIATURA_MOSTRAR", True)      # al editar una miniatura, te abre «antes y ahora» antes del «dale»
OVERLAY_CLAUDE = _b("OVERLAY_CLAUDE", True)            # los overlays los diseña Claude (programa claude de tu PC)
OVERLAY_ESPERA = int(_f("OVERLAY_ESPERA", 480))         # segundos máximos esperando el diseño de Claude (Opus tarda más)
CLAUDE_MODELO = _s("CLAUDE_MODELO", "opus")             # modelo de Claude para diseñar miniaturas y overlays (el mejor)
CLAUDE_MODELO_REVISION = _s("CLAUDE_MODELO_REVISION", "sonnet")   # el que revisa la miniatura y busca imágenes (más rápido)
# Agente de Marketing y Empaquetado (empaquetado.py): título + texto de miniatura + arte + descripción para el clic
EMPAQUETADO = _b("EMPAQUETADO", True)
EMPAQUETAR_SIEMPRE = _b("EMPAQUETAR_SIEMPRE", False)    # true = también los títulos que dictás tal cual los optimiza
CLAUDE_MODELO_EMPAQUETADO = _s("CLAUDE_MODELO_EMPAQUETADO", "opus")
EMPAQUETADO_ESPERA = int(_f("EMPAQUETADO_ESPERA", 150))   # segundos máximos; si tarda más, queda lo de la IA local
# Enlaces que van en la descripción cuando no nombrás ninguno (si alguno no está guardado, se saltea sin avisar)
ENLACES_DE_SIEMPRE = _lista("ENLACES_DE_SIEMPRE", "discord,kick,tiktok")
LANZAMIENTO = _s("LANZAMIENTO", "2026-11-04")             # el día que sale WoW Forever (el agente no dice «salió» antes)
# Tus miniaturas favoritas: aprender_estilo.bat las copia en chico a recursos/referencias y escribe la guía de estilo
MINIATURAS_EJEMPLOS = _s("MINIATURAS_EJEMPLOS", r"E:\Biblioteca\Imagenes\Miniaturas YouTube")
REFERENCIAS = RECURSOS / "referencias"
ESTILO_MINIATURAS = RECURSOS / "estilo_miniaturas.md"
CLAUDE_EXE = _s("CLAUDE_EXE")                           # ruta a claude.exe si no se encuentra solo

# --- Respuesta ---
BEEPS = _b("BEEPS", True)                               # false = sin ningún sonido
SONIDOS = _s("SONIDOS", "suave").lower()                # suave (tonos bajitos), pitidos (los de antes) o nada
SONIDO_VOLUMEN = _f("SONIDO_VOLUMEN", 0.12)             # volumen de los sonidos suaves (0 a 1)
OVERLAY = _b("OVERLAY", True)
VOICE_FEEDBACK = _b("VOICE_FEEDBACK", False)
DRY_RUN = _b("DRY_RUN", False)
