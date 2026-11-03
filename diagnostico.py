"""Diagnóstico de El Cerebro: revisa cada pieza y dice qué falta. python diagnostico.py"""
import json
import shutil
import subprocess
import sys
import time

import requests

import config

OK, MAL, AVISO = "✅", "❌", "⚠️ "
resultados = []


def check(nombre):
    def deco(f):
        def envoltura():
            try:
                estado, detalle = f()
            except Exception as e:  # noqa: BLE001
                estado, detalle = MAL, f"{type(e).__name__}: {e}"
            resultados.append((estado, nombre, detalle))
            print(f"{estado} {nombre}: {detalle}", flush=True)
        return envoltura
    return deco


@check("Python")
def python():
    v = sys.version_info
    return (OK if (3, 10) <= v[:2] <= (3, 13) else AVISO), sys.version.split()[0]


@check("GPU NVIDIA")
def gpu():
    if not shutil.which("nvidia-smi"):
        return AVISO, "nvidia-smi no está en el PATH"
    out = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
                          "--format=csv,noheader"], capture_output=True, text=True, timeout=15).stdout.strip()
    return OK, out


@check("Whisper (faster-whisper)")
def whisper():
    import ctranslate2
    import faster_whisper  # noqa: F401
    from voz import _cuda_dlls_windows
    _cuda_dlls_windows()
    n = ctranslate2.get_cuda_device_count()
    return (OK if n else AVISO), f"modelo {config.WHISPER_MODEL}, GPUs CUDA visibles: {n}" + ("" if n else " (irá por CPU)")


@check("Micrófono")
def micro():
    import sounddevice as sd
    d = sd.query_devices(kind="input")
    return OK, f"{d['name']} (umbral de voz {config.VAD_THRESHOLD})"


@check("Ollama (IA local)")
def ollama():
    if not config.USE_OLLAMA:
        return AVISO, "desactivado (USE_OLLAMA=false): se usan patrones fijos"
    modelos = [m["name"] for m in requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json().get("models", [])]
    if config.OLLAMA_MODEL not in modelos and f"{config.OLLAMA_MODEL}:latest" not in modelos:
        return MAL, f"falta {config.OLLAMA_MODEL}. Ejecuta: ollama pull {config.OLLAMA_MODEL}. Tienes: {', '.join(modelos) or 'ninguno'}"
    import router
    t0 = time.time()
    accion, _ = router.interpretar("arma una raid de molten core el viernes a las 9 con 20 cupos")
    return OK, f"{config.OLLAMA_MODEL} responde en {time.time() - t0:.1f} s -> {accion.resumen}"


@check("Hogger (buzón en Discord)")
def hogger():
    from hogger import Hogger
    if not Hogger.disponible():
        return AVISO, "sin HOGGER_TOKEN/HOGGER_GUILD_ID: solo anuncios por webhook"
    h = Hogger()
    yo = h._pedir("GET", "/users/@me")
    h.canal_buzon()
    res = h.estado()
    raids = len(res.get("raids", []))
    return OK, f"{yo['username']} responde desde el servidor; #{config.CANAL_CEREBRO} OK; {raids} raid(s) próximas"


@check("Discord por webhook (respaldo)")
def webhook():
    if not config.DISCORD_WEBHOOK_URL:
        return AVISO, "no configurado (opcional si Hogger funciona)"
    r = requests.get(config.DISCORD_WEBHOOK_URL, timeout=10)
    return (OK if r.ok else MAL), (f"canal {r.json().get('channel_id')}" if r.ok else f"HTTP {r.status_code}")


@check("Kick")
def kick():
    from kick import Kick
    if not config.KICK_TOKENS.exists():
        return AVISO, "no conectado: ejecuta conectar_kick.bat"
    c = Kick().canal()
    return OK, f"canal {c.get('slug')}, título «{c.get('stream_title')}»"


@check("YouTube")
def youtube():
    if not config.YOUTUBE_TOKEN.exists():
        return AVISO, "no conectado: ejecuta conectar_youtube.bat"
    from youtube import YouTube
    yt = YouTube()
    d = yt.directo_actual()
    return OK, f"canal {yt.canal()}; " + (f"directo «{d['snippet']['title']}»" if d else "sin directo activo ni programado")


@check("OBS (capturas para miniaturas)")
def obs():
    from miniaturas import captura_obs
    img = captura_obs()
    return OK, f"captura de la escena en vivo {img.size[0]}x{img.size[1]}"


@check("TikTok LIVE Studio")
def tiktok():
    return AVISO if config.TIKTOK_MODO != "automatico" else OK, f"modo {config.TIKTOK_MODO}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("=== Diagnóstico de El Cerebro ===\n")
    for f in (python, gpu, whisper, micro, ollama, hogger, webhook, kick, youtube, obs, tiktok):
        f()
    malos = [r for r in resultados if r[0] == MAL]
    print(f"\n{len(resultados) - len(malos)}/{len(resultados)} sin errores.")
    (config.DATA / "diagnostico.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
