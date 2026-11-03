"""Modo Jarvis: la voz que te habla (Piper, local y gratis) y el orbe animado que reacciona.

- Voz: frases cortas («Raid de Monte Hyjal, sábado 7 de noviembre a las 21. ¿La publico?», «Listo, publicado»).
  Suena en VOZ_DISPOSITIVO (por ejemplo tus auriculares) para que el stream no la escuche.
- Orbe: un círculo animado, siempre encima y sin robar el foco ni los clics. Escucha (sigue tu voz),
  piensa (gira), habla (sigue su propia voz) y destella verde o rojo al terminar.
"""
import datetime as dt
import math
import queue
import random
import re
import threading
import time

import numpy as np
import requests

import config

URL_VOZ = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/{familia}/{codigo}/{nombre}/{calidad}/"
           "{codigo}-{nombre}-{calidad}{ext}?download=true")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


# ------------------------------------------------------------------ texto para decir
def hora_hablada(h, mi=0):
    """21:00 -> «9 de la noche», 18:30 -> «6 y media de la tarde»."""
    h, mi = int(h), int(mi)
    sufijo = ("de la madrugada" if h < 6 else "de la mañana" if h < 12 else "del mediodía" if h == 12
              else "de la tarde" if h < 20 else "de la noche")
    h12 = h % 12 or 12
    minutos = {0: "", 15: " y cuarto", 30: " y media"}.get(mi, f" y {mi}")
    return f"{h12}{minutos} {sufijo}"


def para_voz(texto):
    """Deja el texto listo para leerlo en voz alta: sin emojis ni símbolos, con fechas y horas habladas."""
    t = str(texto or "")
    t = re.sub(r"[\U00010000-\U0010FFFF☀-➿️]", "", t)          # emojis
    t = re.sub(r"[«»\"*_`#@]", "", t)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})\b", lambda m: f"{int(m.group(1))} de {MESES[int(m.group(2)) - 1]}"
               if 1 <= int(m.group(2)) <= 12 else m.group(0), t)
    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda m: hora_hablada(m.group(1), m.group(2)), t)
    t = t.replace("-", " ")
    return re.sub(r"\s+", " ", t).strip()


def _cuando_raid(fecha):
    try:
        d = dt.datetime.strptime(fecha, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return ""
    from herramientas import DIAS
    return f"{DIAS[d.weekday()]} {d.day}/{d.month} a las {d.hour}:{d.minute:02d}"


_PLAT = {"kick": "Kick", "youtube": "YouTube", "tiktok": "TikTok"}


def _nombre_hablado(usuario):
    """«xX_Pepe99_Xx» -> «Pepe 99»: para que la voz lo diga entendible."""
    base = str(usuario).lstrip("@")
    t = re.sub(r"^[xX]{1,3}[_\-.]+|[_\-.]+[xX]{1,3}$", "", base).strip("_-.") or base
    t = re.sub(r"[_\-.]+", " ", t)
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    t = re.sub(r"(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])", " ", t)
    return t.strip()


RELLENOS = ("A ver, a ver…", "Mmm…", "Ya, un toque…", "Ajá, dejame ver…")
BUSCANDO = ("Dejame buscar…", "Ya te lo busco…", "Un toque, lo busco en internet…")


def frase(evento, accion=None, detalle=None):
    """Lo que dice Jarvis en cada momento. Corto: el detalle completo está en el cartel."""
    d = accion.datos if accion is not None else {}
    tipo = accion.tipo if accion is not None else ""
    if evento == "saludo":
        return config.JARVIS_SALUDO
    if evento == "pregunta":
        return detalle or (accion.resumen if accion else "")
    if evento == "relleno":
        return random.choice(RELLENOS)
    if evento == "buscando":
        return random.choice(BUSCANDO)
    if evento == "cancelado":
        return "Cancelado."
    if evento == "trabajando":
        return "Lo diseño y te aviso." if tipo == "miniatura" else "Lo estoy diseñando. Dame un minuto."
    if evento == "error":
        return "Uy, no pude. Te dejo el detalle en pantalla."
    if evento == "confirmar":
        a = d.get("accion")
        if a == "raid":
            return f"Raid de {d.get('nombre')}, {_cuando_raid(d.get('fecha'))}, {d.get('cupo')} cupos. ¿La publico?"
        if a == "banda":
            cuando = re.sub(r"\s(\d{1,2}:\d{2})$", r" a las \1", str(d.get("cuando", "")).lower())
            return f"Banda de {d.get('nombre')}, {cuando}. ¿La publico?"
        if a == "anuncio":
            return f"Anuncio listo: {d.get('titulo')}. ¿Lo publico?"
        if a == "sorteo":
            return f"Sorteo de {d.get('premio')}. ¿Lo publico?"
        if a == "encuesta":
            return f"Encuesta: {d.get('pregunta')} ¿La publico?"
        if a == "mensaje":
            return f"Mensaje para {d.get('canal')}. ¿Lo mando?"
        if tipo == "moderar":
            verbo = {"banear": "¿Baneo a", "silenciar": f"¿Silencio {d.get('minutos')} minutos a",
                     "desbanear": "¿Desbaneo a"}.get(d.get("accion"), "¿Moderar a")
            quienes = " y ".join(f"{_nombre_hablado(o['usuario'])} en {_PLAT.get(o['plataforma'], o['plataforma'])}"
                                 for o in d.get("objetivos", []))
            return f"{verbo} {quienes}?"
        if tipo == "chat":
            return "¿Lo mando al chat?"
        if tipo == "overlay":
            return f"Overlay {d.get('nombre')}, {str(d.get('posicion', '')).replace('-', ' ')}. ¿Lo diseño?"
        if tipo == "titulo":
            extra = (" Con el juego " + d["juego"] + "." if d.get("juego") else "") + (" Y te hago la miniatura." if d.get("miniatura") else "")
            return f"Título: {d.get('titulo')}.{extra} ¿Lo cambio?"
        if tipo == "juego":
            return f"Juego {d.get('juego')} en Kick. ¿Lo cambio?"
        primera = (accion.resumen if accion else "").splitlines()[0] if accion else ""
        return f"{primera}. ¿Confirmás?"
    if evento == "hecho":
        if tipo == "hogger":
            a = d.get("accion")
            return {"cerrar": "Listo, inscripciones cerradas." if d.get("cerrar", True) else "Listo, inscripciones abiertas.",
                    "borrar": "Borrado."}.get(a, "Listo, publicado.")
        if tipo == "titulo":
            extra = " El de TikTok te lo dejé copiado." if "tiktok" in d.get("plataformas", []) else ""
            return "Título cambiado." + extra + (" Ahora te diseño la miniatura." if d.get("miniatura") else "")
        if tipo == "juego":
            return "Juego cambiado en Kick." if "Falló" not in str(detalle or "") else "No pude cambiar el juego."
        if tipo == "deshacer":
            return "Listo, lo borré."
        if tipo == "restaurar_titulo":
            return "Volví al título anterior."
        if tipo in ("consultar_titulo", "respuesta"):
            return str(detalle or "")
        if tipo == "busqueda":
            return str(detalle or "").split("\n(Fuente:")[0]
        if tipo == "miniatura":
            return "Miniaturas listas." + (" Ya está en YouTube." if "subida a YouTube" in str(detalle or "") else "")
        if tipo == "moderar":
            if "Falló" in str(detalle or ""):
                return "Hecho a medias. Te dejo el detalle en pantalla."
            return {"banear": "Listo, baneado.", "silenciar": "Listo, silenciado.",
                    "desbanear": "Listo, desbaneado."}.get(d.get("accion"), "Listo.")
        if tipo == "chat":
            return "Mandado al chat." if "Falló" not in str(detalle or "") else "Mandado a medias. Mirá la pantalla."
        if tipo == "overlay":
            a = d.get("accion")
            return {"crear": "Overlay listo en pantalla.", "mover": "Movido.", "ocultar": "Oculto.",
                    "mostrar": "Ahí está.", "quitar": "Quitado."}.get(a, "Listo.")
        if tipo == "guardar_enlace":
            return f"Enlace de {d.get('nombre')} guardado."
        return "Listo."
    return ""


# ------------------------------------------------------------------ voz
ELEVEN_API = "https://api.elevenlabs.io/v1"
ELEVEN_SR = 24000


# Voces de serie de ElevenLabs (por si la clave no tiene permiso para listar voces)
VOCES_DE_SERIE = {"daniel": "onwK4e9ZLuTAKqWW03F9", "george": "JBFqnCBsd6RMkjVDRZzb", "brian": "nPczCjzI2devNBz1zQrb",
                  "adam": "pNInz6obpgDQGcFmaJgB"}


def _factor_tono(semitonos=None):
    return 2 ** (float(config.VOZ_TONO if semitonos is None else semitonos or 0) / 12)


def _velocidad_base():
    """Se genera más lento en la medida en que después se sube el tono, así la voz de dibujito no queda apurada."""
    return config.VOZ_VELOCIDAD / _factor_tono()


def cambiar_tono(audio, semitonos):
    """Sube (o baja) el tono: voz de dibujito. Acelera en la misma medida (por eso se genera más lento)."""
    if not float(semitonos or 0) or not len(audio):
        return audio
    f = _factor_tono(semitonos)
    indices = np.arange(0, len(audio) - 1, f)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def buscar_voz(nombre, clave=None):
    """El voice_id de una voz por su nombre (de tu cuenta o de las de serie) o directamente su ID."""
    if re.fullmatch(r"[A-Za-z0-9]{20}", nombre):
        return nombre
    try:
        r = requests.get(f"{ELEVEN_API}/voices", headers={"xi-api-key": clave or config.ELEVEN_API_KEY}, timeout=15)
        if r.ok:
            for x in r.json().get("voices", []):
                if x.get("name", "").lower().startswith(nombre.lower()):
                    return x["voice_id"]
    except requests.RequestException:
        pass
    if nombre.lower() in VOCES_DE_SERIE:
        return VOCES_DE_SERIE[nombre.lower()]
    raise RuntimeError(f"no encontré la voz «{nombre}» en tu cuenta de ElevenLabs")


def sintetizar_eleven(texto, voz_id, clave=None, velocidad=None):
    """Audio PCM 24 kHz (bytes) de ElevenLabs. Lanza RuntimeError con el motivo si no se puede."""
    r = requests.post(
        f"{ELEVEN_API}/text-to-speech/{voz_id}",
        params={"output_format": f"pcm_{ELEVEN_SR}"},
        headers={"xi-api-key": clave or config.ELEVEN_API_KEY},
        json={"text": texto, "model_id": config.ELEVEN_MODELO, "language_code": "es",
              "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                                 "speed": max(0.7, min(1.2, velocidad or _velocidad_base()))}},
        timeout=20)
    if r.status_code != 200:
        texto = r.text.lower()
        if r.status_code in (401, 402, 403) or any(p in texto for p in ("invalid_api_key", "authentication", "quota")):
            raise PermissionError(f"ElevenLabs dijo {r.status_code}: {motivo_eleven(r)}")
    r.raise_for_status()
    return r.content


def motivo_eleven(r):
    """El motivo que da ElevenLabs, corto y sin datos privados (p. ej. «API key is invalid.»)."""
    try:
        d = r.json().get("detail")
        if isinstance(d, dict):
            return d.get("message") or d.get("code") or str(d)[:150]
        return str(d)[:150]
    except Exception:  # noqa: BLE001
        if "<html" in r.text.lower():
            return "pedido mal armado (la clave llegó con letras raras)"
        return r.text[:150]


class Voz:
    """Habla en un hilo propio. decir() no bloquea; callar() corta lo que esté diciendo.

    Usa ElevenLabs si hay ELEVEN_API_KEY (las frases ya dichas quedan guardadas y no gastan créditos otra vez)
    y Piper local como respaldo, o siempre si no hay clave.
    """

    def __init__(self):
        self.piper = None
        self.nivel = 0.0          # volumen de lo que está diciendo ahora (para el orbe)
        self.hablando = False
        self.ocupada = False      # generando o diciendo una frase
        self._cola = queue.Queue()
        self._eleven_ok = bool(config.ELEVEN_API_KEY)
        self._voz_id = None
        self.cache = config.DATA / "voz_cache"
        threading.Thread(target=self._hilo, daemon=True, name="voz").start()

    # --- ElevenLabs
    def _eleven_voz(self):
        if self._voz_id:
            return self._voz_id
        v = config.ELEVEN_VOZ
        if re.fullmatch(r"[A-Za-z0-9]{20}", v):
            self._voz_id = v
            return v
        self._voz_id = buscar_voz(v)
        return self._voz_id

    def _eleven(self, texto):
        import hashlib
        clave = hashlib.sha1(f"{config.ELEVEN_VOZ}|{config.ELEVEN_MODELO}|{_velocidad_base():.3f}|{texto}".encode()).hexdigest()
        archivo = self.cache / f"{clave}.pcm"
        if not archivo.exists():
            try:
                pcm = sintetizar_eleven(texto, self._eleven_voz(), velocidad=_velocidad_base())
            except PermissionError as e:
                self._eleven_ok = False
                raise RuntimeError(f"{e} (¿clave o créditos?); sigo con la voz local") from e
            self.cache.mkdir(parents=True, exist_ok=True)
            archivo.write_bytes(pcm)
        audio = np.frombuffer(archivo.read_bytes(), dtype="<i2").astype(np.float32) / 32768.0
        return audio * config.VOZ_VOLUMEN, ELEVEN_SR

    # --- Piper (local)
    def _ruta_modelo(self):
        return config.DATA / "voces" / f"{config.VOZ_MODELO}.onnx"

    def _descargar(self):
        codigo, nombre, calidad = config.VOZ_MODELO.rsplit("-", 2)
        familia = codigo.split("_")[0]
        destino = self._ruta_modelo()
        destino.parent.mkdir(parents=True, exist_ok=True)
        for ext in (".onnx.json", ".onnx"):
            url = URL_VOZ.format(familia=familia, codigo=codigo, nombre=nombre, calidad=calidad, ext=ext)
            print(f"[voz] Descargando {config.VOZ_MODELO}{ext}...")
            r = requests.get(url, timeout=120, stream=True)
            r.raise_for_status()
            final = destino.with_name(destino.name.replace(".onnx", ext))
            tmp = final.with_name(final.name + ".part")
            with tmp.open("wb") as f:
                for parte in r.iter_content(1 << 16):
                    f.write(parte)
            tmp.replace(final)

    def _piper(self, texto):
        from piper import PiperVoice, SynthesisConfig
        if self.piper is None:
            if not self._ruta_modelo().exists():
                self._descargar()
            self.piper = PiperVoice.load(str(self._ruta_modelo()))
            print(f"[voz] Voz local {config.VOZ_MODELO} lista.")
        cfg = SynthesisConfig(length_scale=1.0 / max(0.4, _velocidad_base()), volume=config.VOZ_VOLUMEN)
        partes = [c.audio_float_array for c in self.piper.synthesize(texto, syn_config=cfg)]
        return (np.concatenate(partes) if partes else np.zeros(0, np.float32)), self.piper.config.sample_rate

    def _sintetizar(self, texto):
        if self._eleven_ok:
            try:
                return self._eleven(texto)
            except Exception as e:  # noqa: BLE001
                print(f"[voz] ElevenLabs falló ({e}); uso la voz local.")
        return self._piper(texto)

    # --- uso
    def precalentar(self, frases):
        """Deja frases fijas ya generadas (en segundo plano) para que salgan al instante."""
        def hilo():
            for f in frases:
                try:
                    if self._eleven_ok:
                        self._eleven(para_voz(f))
                except Exception as e:  # noqa: BLE001
                    print(f"[voz] No pude preparar «{f}»: {e}")
                    return
        threading.Thread(target=hilo, daemon=True, name="voz-precalentar").start()

    def decir(self, texto):
        texto = para_voz(texto)
        if texto:
            self._cola.put(texto)

    def callar(self):
        try:
            while True:
                self._cola.get_nowait()
        except queue.Empty:
            pass
        if self.hablando:
            import sounddevice as sd
            sd.stop()
            self.hablando = False
            self.nivel = 0.0

    def _hilo(self):
        import sounddevice as sd
        dispositivo = config.VOZ_DISPOSITIVO
        dispositivo = int(dispositivo) if dispositivo.isdigit() else (dispositivo or None)
        if not self._eleven_ok:
            try:
                self._piper("hola")          # deja la voz local cargada (y descargada la primera vez)
            except Exception as e:  # noqa: BLE001
                print(f"[voz] No pude preparar la voz local ({e}).")
        while True:
            texto = self._cola.get()
            self.ocupada = True
            try:
                audio, sr = self._sintetizar(texto)
                if not len(audio):
                    continue
                audio = cambiar_tono(audio, config.VOZ_TONO)
                paso = max(1, sr // 30)               # envolvente cada 1/30 s para que el orbe siga la voz
                env = [float(np.sqrt(np.mean(audio[i:i + paso] ** 2))) for i in range(0, len(audio), paso)]
                t0 = time.time()
                self.hablando = True
                sd.play(audio, sr, device=dispositivo)
                fin = t0 + len(audio) / sr
                while self.hablando and time.time() < fin:
                    i = int((time.time() - t0) * 30)
                    self.nivel = env[min(i, len(env) - 1)] * 3
                    time.sleep(1 / 60)
                sd.wait()
            except Exception as e:  # noqa: BLE001
                print(f"[voz] No pude hablar: {e}")
            finally:
                self.hablando = False
                self.nivel = 0.0
                self.ocupada = not self._cola.empty()


# ------------------------------------------------------------------ orbe
PALETAS = {
    "jarvis": {"escuchando": "#38E1FF", "pensando": "#E8C468", "hablando": "#5AB8FF", "ok": "#4CE38A", "error": "#FF5A5A"},
    "dorado": {"escuchando": "#E8C468", "pensando": "#FFB347", "hablando": "#F5D98B", "ok": "#4CE38A", "error": "#FF5A5A"},
}
CLAVE = "#010203"   # color que Windows vuelve transparente


def _mezclar(color, factor):
    """Oscurece un color hacia negro (factor 0 = negro, 1 = el color)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(2, int(c * factor)) for c in (r, g, b))


class Orbe:
    TAM = 220

    def __init__(self, root):
        import tkinter as tk
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=CLAVE)
        try:
            self.win.attributes("-transparentcolor", CLAVE)
        except tk.TclError:
            pass
        self.win.attributes("-alpha", 0.0)
        self.c = tk.Canvas(self.win, width=self.TAM, height=self.TAM, bg=CLAVE, highlightthickness=0)
        self.c.pack()
        self._ubicar()
        self.win.update_idletasks()
        self._sin_foco_ni_clics()
        self.paleta = PALETAS.get(config.ORBE_COLOR, PALETAS["jarvis"])
        self.fuente = None          # función -> (estado, nivel 0..1)
        self.alpha = 0.0
        self.n = 0.0
        self.destello = None
        self.t0 = time.time()
        root.after(33, self._paso)

    def _ubicar(self):
        sw, sh, t = self.win.winfo_screenwidth(), self.win.winfo_screenheight(), self.TAM
        pos = {"abajo-derecha": (sw - t - 30, sh - t - 80), "abajo-izquierda": (30, sh - t - 80),
               "arriba-derecha": (sw - t - 30, 130), "arriba-izquierda": (30, 30),
               "abajo-centro": ((sw - t) // 2, sh - t - 80)}
        x, y = pos.get(config.ORBE_POSICION, pos["abajo-derecha"])
        self.win.geometry(f"{t}x{t}+{x}+{y}")

    def _sin_foco_ni_clics(self):
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # NOACTIVATE | TOOLWINDOW | LAYERED | TRANSPARENT (los clics lo atraviesan)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x00000080 | 0x00080000 | 0x00000020)
        except Exception:  # noqa: BLE001
            pass

    def destellar(self, tipo):
        self.destello = (tipo, time.time())

    def _paso(self):
        try:
            self._dibujar()
        except Exception as e:  # noqa: BLE001
            print(f"[orbe] {e}")
        self.c.after(33, self._paso)

    def _dibujar(self):
        estado, nivel = self.fuente() if self.fuente else ("oculto", 0.0)
        ahora = time.time()
        if self.destello and ahora - self.destello[1] < 1.3:
            estado, nivel = self.destello[0], 0.6
        objetivo = 0.0 if estado == "oculto" else 0.93
        self.alpha += (objetivo - self.alpha) * 0.18
        if abs(self.alpha - objetivo) > 0.005:
            self.win.attributes("-alpha", max(0.0, min(1.0, self.alpha)))
        if self.alpha < 0.02 and estado == "oculto":
            self.c.delete("all")
            return
        t = ahora - self.t0
        if estado == "pensando":
            nivel = 0.35 + 0.15 * math.sin(t * 5)
        self.n += (min(1.0, nivel) - self.n) * 0.35
        color = self.paleta.get(estado, self.paleta["escuchando"])
        giro = {"pensando": 260, "escuchando": 70, "hablando": 120}.get(estado, 40)
        c, m, n = self.c, self.TAM / 2, self.n
        c.delete("all")
        # anillo exterior y marcas que laten con el volumen
        c.create_oval(m - 100, m - 100, m + 100, m + 100, outline=_mezclar(color, 0.35), width=2)
        for i in range(48):
            ang = math.radians(i * 7.5 + t * giro * 0.15)
            largo = 3 + 16 * n * abs(math.sin(t * 7 + i * 0.9))
            r1, r2 = 88, 88 + largo
            c.create_line(m + r1 * math.cos(ang), m + r1 * math.sin(ang), m + r2 * math.cos(ang), m + r2 * math.sin(ang),
                          fill=_mezclar(color, 0.55 + 0.45 * n), width=2)
        # arcos que giran
        for radio, ancho, extension, sentido in ((78, 4, 110, 1), (66, 3, 70, -1.6), (55, 2, 150, 2.2)):
            inicio = (t * giro * sentido) % 360
            c.create_arc(m - radio, m - radio, m + radio, m + radio, start=inicio, extent=extension,
                         style="arc", outline=color, width=ancho)
            c.create_arc(m - radio, m - radio, m + radio, m + radio, start=inicio + 180, extent=extension / 2,
                         style="arc", outline=_mezclar(color, 0.5), width=ancho)
        # núcleo que crece con la voz
        r = 18 + 26 * n
        c.create_oval(m - r - 8, m - r - 8, m + r + 8, m + r + 8, fill=_mezclar(color, 0.25), outline="")
        c.create_oval(m - r, m - r, m + r, m + r, fill=_mezclar(color, 0.6), outline=color, width=2)
        c.create_oval(m - r * 0.45, m - r * 0.45, m + r * 0.45, m + r * 0.45, fill=color, outline="")
