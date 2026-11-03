"""Pitidos y voz de confirmacion (Windows)."""
import sys
import threading

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


def pitido(tipo):
    if not config.BEEPS or winsound is None:
        return
    def _play():
        for freq, ms in _SONIDOS.get(tipo, []):
            winsound.Beep(freq, ms)
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
