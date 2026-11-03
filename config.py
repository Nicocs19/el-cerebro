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

# --- Voz (Whisper local) ---
WHISPER_MODEL = _s("WHISPER_MODEL", "large-v3-turbo")
WHISPER_DEVICE = _s("WHISPER_DEVICE", "auto").lower()
WHISPER_COMPUTE = _s("WHISPER_COMPUTE", "int8_float16")
MIC_DEVICE = _s("MIC_DEVICE")
VAD_THRESHOLD = _f("VAD_THRESHOLD", 0.015)
SILENCE_SECONDS = _f("SILENCE_SECONDS", 1.5)
MAX_SECONDS = _f("MAX_SECONDS", 30)

# --- IA local (Ollama) ---
USE_OLLAMA = _b("USE_OLLAMA", True)
OLLAMA_URL = _s("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = _s("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_KEEP_ALIVE = _s("OLLAMA_KEEP_ALIVE", "30m")
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
KICK_TOKENS = DATA / "kick_tokens.json"

# --- YouTube ---
YOUTUBE_CLIENT_SECRET = BASE / _s("YOUTUBE_CLIENT_SECRET", "client_secret.json")
YOUTUBE_TOKEN = DATA / "youtube_token.json"
YOUTUBE_CATEGORY_ID = _s("YOUTUBE_CATEGORY_ID", "20")  # 20 = Gaming

# --- TikTok LIVE Studio ---
TIKTOK_MODO = _s("TIKTOK_MODO", "portapapeles").lower()  # portapapeles | automatico

# --- OBS (para las capturas de las miniaturas) ---
OBS_HOST = _s("OBS_HOST", "localhost")
OBS_PORT = int(_f("OBS_PORT", 4455))
OBS_PASSWORD = _s("OBS_PASSWORD")
# Escena o fuente de OBS para el fondo de las miniaturas (p. ej. la captura del juego). Vacío = lo que sale en directo.
OBS_FUENTE = _s("OBS_FUENTE")

# --- Respuesta ---
BEEPS = _b("BEEPS", True)
OVERLAY = _b("OVERLAY", True)
VOICE_FEEDBACK = _b("VOICE_FEEDBACK", False)
DRY_RUN = _b("DRY_RUN", False)
