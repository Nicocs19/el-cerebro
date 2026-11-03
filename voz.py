"""Grabacion del microfono y transcripcion local con faster-whisper."""
import glob
import os
import site
import threading
import time

import numpy as np
import sounddevice as sd

import config

SR = 16000
BLOQUE = 1600  # 0,1 s
PROMPT = ("Ordenes de un streamer en español: anuncio a mi guild, hermandad, Discord, Kick, YouTube, "
          "TikTok, título del stream, World of Warcraft, raid, mazmorra, guerrero, nivel.")


def _cuda_dlls_windows():
    """Hace visibles las DLL de CUDA/cuDNN instaladas con pip (nvidia-cublas/cudnn)."""
    if os.name != "nt":
        return
    rutas = site.getsitepackages() + [site.getusersitepackages()]
    for sp in rutas:
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _mic():
    if not config.MIC_DEVICE:
        return None
    return int(config.MIC_DEVICE) if config.MIC_DEVICE.isdigit() else config.MIC_DEVICE


class Transcriptor:
    def __init__(self):
        _cuda_dlls_windows()
        from faster_whisper import WhisperModel

        dispositivo = config.WHISPER_DEVICE
        if dispositivo in ("auto", "cuda"):
            try:
                print(f"Cargando Whisper '{config.WHISPER_MODEL}' en la GPU...")
                self.modelo = WhisperModel(config.WHISPER_MODEL, device="cuda",
                                           compute_type=config.WHISPER_COMPUTE)
                self._calentar()
                self.dispositivo = "cuda"
                return
            except Exception as e:  # noqa: BLE001
                if dispositivo == "cuda":
                    raise
                print(f"[aviso] GPU no disponible para Whisper ({e}). Uso CPU.")
        modelo_cpu = "small" if "large" in config.WHISPER_MODEL else config.WHISPER_MODEL
        print(f"Cargando Whisper '{modelo_cpu}' en CPU...")
        self.modelo = WhisperModel(modelo_cpu, device="cpu", compute_type="int8")
        self.dispositivo = "cpu"

    def _calentar(self):
        list(self.modelo.transcribe(np.zeros(SR, dtype=np.float32), language="es")[0])

    def transcribir(self, audio):
        segmentos, _ = self.modelo.transcribe(
            audio, language="es", beam_size=5, vad_filter=True,
            initial_prompt=PROMPT, condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segmentos).strip()


class Grabadora:
    """Graba hasta que dejas de hablar (silencio), llegas al maximo o pulsas otra vez."""

    def __init__(self):
        self.activa = False
        self._lock = threading.Lock()
        self._bloques = []
        self._stream = None

    def _callback(self, indata, frames, t, status):
        bloque = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(bloque ** 2)))
        ahora = time.time()
        with self._lock:
            self._bloques.append(bloque)
            if rms > config.VAD_THRESHOLD:
                self.hablo = True
                self.ultima_voz = ahora

    def empezar(self):
        self._bloques = []
        self.hablo = False
        self.inicio = self.ultima_voz = time.time()
        self._stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                      blocksize=BLOQUE, device=_mic(), callback=self._callback)
        self._stream.start()
        self.activa = True

    def debe_parar(self):
        ahora = time.time()
        if ahora - self.inicio > config.MAX_SECONDS:
            return True
        if self.hablo and ahora - self.ultima_voz > config.SILENCE_SECONDS:
            return True
        # 6 s sin decir nada: se cancela sola
        return not self.hablo and ahora - self.inicio > 6

    def parar(self):
        self.activa = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            audio = np.concatenate(self._bloques) if self._bloques else np.zeros(0, np.float32)
        return audio if self.hablo else np.zeros(0, np.float32)


def calibrar(segundos=8):
    print("Calibrando: quedate en silencio 3 s y luego habla normal...")
    def cb(indata, *a):
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        print(f"\rnivel {rms:.4f} " + "#" * min(60, int(rms * 1000)), end="", flush=True)
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=BLOQUE,
                        device=_mic(), callback=cb):
        time.sleep(segundos)
    print("\nPon VAD_THRESHOLD en .env algo por encima del nivel en silencio "
          "y claramente por debajo del nivel cuando hablas.")


def listar_micros():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"{i:3d}  {d['name']}")
