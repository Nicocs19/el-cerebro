"""Sonidos de aviso y voz de confirmacion (Windows)."""
import io
import math
import struct
import sys
import threading
import wave

import config

try:
    import winsound
except ImportError:  # no es Windows
    winsound = None

_SONIDOS = {
    "inicio": [(880, 120)],
    "fin": [(660, 120)],
    "ok": [(660, 90), (990, 140)],
    "error": [(300, 350)],
    "pregunta": [(880, 90), (880, 90), (1175, 160)],
}


# Sonidos suaves: tonos redondos (seno) bajitos y cortos, en vez de los pitidos de Windows
_SUAVES = {
    "inicio": [(784, 55), (1047, 70)],
    "error": [(392, 120), (330, 160)],
    "ok": [(880, 60), (1175, 80)],
    "pregunta": [(988, 70)],
    "fin": [(660, 50)],
}
_cache = {}


def _wav(notas, volumen, sr=22050):
    datos = []
    for freq, ms in notas:
        n, ataque = int(sr * ms / 1000), int(sr * 0.012)
        for i in range(n):
            env = min(1.0, i / ataque) * min(1.0, (n - i) / (n * 0.7))     # entra suave y se apaga suave
            datos.append(volumen * env * math.sin(2 * math.pi * freq * i / sr))
        datos.extend([0.0] * int(sr * 0.02))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32767)) for x in datos))
    return buf.getvalue()


def pitido(tipo):
    modo = config.SONIDOS if config.BEEPS else "nada"
    if modo == "nada" or winsound is None:
        return
    if modo == "suave" and config.JARVIS_VOZ and tipo in ("fin", "ok", "pregunta"):
        return                      # con voz ya te lo dice El Cerebro: solo suena al empezar a escucharte
    if modo == "pitidos":
        def _play():
            for freq, ms in _SONIDOS.get(tipo, []):
                winsound.Beep(freq, ms)
    else:
        notas = _SUAVES.get(tipo)
        if not notas:
            return
        clave = (tipo, config.SONIDO_VOLUMEN)
        if clave not in _cache:
            _cache[clave] = _wav(notas, max(0.0, min(1.0, config.SONIDO_VOLUMEN)))

        def _play():
            try:
                winsound.PlaySound(_cache[clave], winsound.SND_MEMORY)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=_play, daemon=True).start()


class Voz:
    def __init__(self):
        self.engine = None
        if not config.VOICE_FEEDBACK:
            return
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            for v in self.engine.getProperty("voices"):
                nombre = f"{v.name} {v.id}".lower()
                if "spanish" in nombre or "español" in nombre or "es-" in nombre:
                    self.engine.setProperty("voice", v.id)
                    break
            self.engine.setProperty("rate", 185)
        except Exception as e:  # noqa: BLE001
            print(f"[aviso] Voz de Windows no disponible: {e}")
            self.engine = None

    def decir(self, texto):
        print(f"  >> {texto}")
        if self.engine:
            try:
                self.engine.say(texto)
                self.engine.runAndWait()
            except Exception as e:  # noqa: BLE001
                print(f"[aviso] Error de voz: {e}", file=sys.stderr)
