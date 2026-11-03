"""Grabacion del microfono y transcripcion local con faster-whisper."""
import glob
import os
import re
import site
import threading
import time
import unicodedata

import numpy as np
import sounddevice as sd

import config

SR = 16000
BLOQUE = 1600  # 0,1 s
PROMPT = ("Órdenes de un streamer gamer en español: anuncio a mi guild, hermandad, Discord, Kick, YouTube, "
          "TikTok, título del stream, miniatura, World of Warcraft, WoW Forever, Cerebro, Hogger, Mr. H. "
          "Leveando al War del 1 al 10, subiendo el Pala, el Hunter, el Rogue, el Priest, el Lock, el Mago, "
          "el Druida, el Chamán; farmear, tanquear, healer, DPS, raid, mazmorra, nivel. Raids: Molten Core, "
          "Onyxia, Blackwing Lair, Zul'Gurub, Naxxramas, Karazhan, Gruul, Magtheridon, Monte Hyjal, Templo Oscuro, "
          "Zul'Aman, Ulduar. Mazmorras: Deadmines, Stratholme, Scholomance.")
PALABRAS_CLAVE = "War Warrior leveando WoW Forever Hogger Cerebro Kick miniatura raid"

# Lo que Whisper suele escuchar mal en jerga de WoW -> lo que dijiste (se aplica a todo lo transcrito)
CORRECCIONES = [
    (r"\b(levi|libi|lebi|leb)(ando|ar|o|eo)\b", r"leve\2"),
    (r"\b(washer|guasher|guacher|wacher|guar|guor|wor)\b", "War"),
    (r"\bwarrior\b", "Warrior"),
    (r"\bwow forever\b|\bguau forever\b|\bbow forever\b", "WoW Forever"),
    (r"\b(previces|previs|previ ?bis|pre ?bis|pribis|prebís)\b", "pre-BiS"),
]


def corregir(texto):
    for patron, cambio in CORRECCIONES:
        texto = re.sub(patron, cambio, texto, flags=re.IGNORECASE)
    return texto
VOZ_MINIMA = 3  # bloques de 0,1 s por encima del umbral para contar como voz (un clic de teclado no alcanza)

# Frases que Whisper "escucha" en el silencio o el ruido (aprendidas de subtítulos de YouTube)
_ALUCINACION = re.compile(
    r"^(gracias( a todos)?( por (ver|mirar|su atencion|tu atencion|vernos))?( (el|este) video)?"
    r"|.*amara\.org.*|subtitulos? (realizados? )?por.*|(no olvides )?suscrib\w*( al canal)?|(y )?dale like.*"
    r"|hasta (la proxima|luego|pronto)|nos vemos( en el (proximo|siguiente) video)?|chau|adios|musica|aplausos|risas|)$")


def es_alucinacion(texto):
    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .")
    return bool(_ALUCINACION.fullmatch(t))


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
        opciones = dict(language="es", beam_size=5, vad_filter=True, initial_prompt=PROMPT,
                        condition_on_previous_text=False)
        try:
            segmentos, _ = self.modelo.transcribe(audio, hotwords=PALABRAS_CLAVE, **opciones)
        except TypeError:          # faster-whisper viejo, sin hotwords
            segmentos, _ = self.modelo.transcribe(audio, **opciones)
        # Se descartan los trozos que Whisper mismo marca como "probablemente no es voz"
        partes = [s.text.strip() for s in segmentos
                  if not (s.no_speech_prob > 0.6 and s.avg_logprob < -0.8) and s.compression_ratio < 2.4]
        texto = " ".join(partes).strip()
        if texto and es_alucinacion(texto):
            print(f"(descarto «{texto}»: es ruido, no una orden)")
            return ""
        return corregir(texto)


class Grabadora:
    """Graba hasta que dejas de hablar (silencio), llegas al maximo o pulsas otra vez."""

    def __init__(self):
        self.activa = False
        self.nivel = 0.0
        self._lock = threading.Lock()
        self._bloques = []
        self._stream = None

    def _callback(self, indata, frames, t, status):
        bloque = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(bloque ** 2)))
        ahora = time.time()
        with self._lock:
            self._bloques.append(bloque)
            self.nivel = rms
            if rms > config.VAD_THRESHOLD:
                self.bloques_voz += 1
                self.ultima_voz = ahora
                if self.bloques_voz >= VOZ_MINIMA:
                    self.hablo = True

    def empezar(self):
        self._bloques = []
        self.hablo = False
        self.bloques_voz = 0
        self.nivel = 0.0
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


def listar_salidas():
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            print(f"{i:3d}  {d['name']}")


def listar_micros():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"{i:3d}  {d['name']}")
