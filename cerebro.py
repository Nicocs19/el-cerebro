"""EL CEREBRO v2: le hablas en lenguaje natural y ejecuta por ti.

Uso:
  python cerebro.py                    -> modo voz (teclas del .env)
  python cerebro.py --texto "..."      -> una orden escrita (pruebas o botones del Loupedeck)
  python cerebro.py --texto "..." --si -> igual, sin pedir confirmación
  python cerebro.py --simular          -> no publica nada, solo muestra lo que haría
  python cerebro.py --calibrar | --micros
"""
import argparse
import datetime as dt
import faulthandler
import queue
import re
import sys
import threading
import time
import traceback

import config
import herramientas as H
import memoria
import router
from acciones import Ejecutor, log
from avisos import pitido


# Con el micrófono abierto solo, además del sí o el no, se acepta una corrección clara («no, a las 10», «mejor 25 cupos»)
CORRIGE = re.compile(r"^(no|si|nel|mejor|pero|cambi|pone|ponele|que sea|solo|sacale|agregale|corregi|en vez)\b|"
                     r"\b(a las \d|cupos|canal|en kick|en youtube|mañana|manana|hoy|el (lunes|martes|miercoles|jueves|"
                     r"viernes|sabado|domingo))\b")


class Cerebro:
    """La lógica: interpreta, pide confirmación y ejecuta. Corre en un solo hilo de trabajo."""

    def __init__(self, mostrar, simular=False, avisar=None, fondo=False, escuchar=None):
        self.fondo = fondo              # lo que tarda (diseños de Claude) sigue en segundo plano
        self.mostrar = mostrar          # mostrar(texto, tipo, segundos)
        self.avisar = avisar or (lambda evento, accion=None, detalle=None: None)   # modo Jarvis: voz y orbe
        self.escuchar = escuchar or (lambda: None)     # abre el micrófono solo para tu «sí» o «no»
        self.ejecutor = Ejecutor(simular)
        self.pendiente = None           # Accion esperando "dale"
        self.pendiente_hasta = 0
        self.contexto = None            # orden incompleta mientras se responde una aclaración
        self.ultimo_relleno = 0.0       # para no decir «a ver…» a cada rato

    def manejar_texto(self, texto, auto_confirmar=False, estricto=False):
        texto = texto.strip()
        if not texto:
            return
        log(f"OÍDO: {texto}")
        if self.pendiente and time.time() > self.pendiente_hasta:
            self.pendiente = None
        r = router.es_confirmacion(texto, estricto=estricto)
        if r == "confirmar" and (self.pendiente or not memoria.hay_charla(3)):
            memoria.anotar("Nicolas", texto)
            return self.confirmar()
        if r == "cancelar" and (self.pendiente or self.contexto or not memoria.hay_charla(3)):
            memoria.anotar("Nicolas", texto)
            return self.cancelar()
        # «dale, banealo» sin nada esperando, pero en medio de una charla: lo entiende la IA con la memoria
        # (si es banear, igual vuelve a pedir «dale» con el nombre a la vista)
        consulta = f"{self.contexto}. {texto}" if self.contexto else texto
        self.mostrar(f"«{texto}»\nPensando…", "info", 0)
        relleno = threading.Timer(config.VOZ_RELLENO_SEGUNDOS, self._relleno)
        if config.VOZ_RELLENO and time.time() - self.ultimo_relleno > config.VOZ_RELLENO_PAUSA:
            relleno.start()           # si la IA tarda mucho, dice «a ver…» (como mucho uno por minuto)
        error = None
        try:
            accion, origen = router.interpretar(consulta, self.pendiente)
        except Exception as e:  # noqa: BLE001
            error = e
        finally:
            relleno.cancel()
            memoria.anotar("Nicolas", texto)
        if error is not None:
            self.contexto = None
            pitido("error")
            if isinstance(error, H.ErrorOrden):
                log(f"NO SE PUDO: {error}")
                memoria.anotar("Vos", f"no se pudo: {error}")        # para que la próxima orden no repita el error
                self.avisar("pregunta", None, str(error))
                return self.mostrar(f"«{texto}»\n{error}", "error", 10)
            log(f"ERROR al interpretar: {error}")
            self.avisar("error", None, str(error))
            return self.mostrar(f"Error al interpretar: {error}", "error", 10)

        if (self.pendiente and accion.tipo == self.pendiente.tipo and accion.datos == self.pendiente.datos
                and router.tiene_afirmacion(texto)):
            log("Lo mismo que estaba esperando, con un «sí»: lo tomo como «dale».")
            return self.confirmar()

        if accion.tipo == "aclaracion":
            log(f"PREGUNTA: {accion.resumen}")
            memoria.anotar("Vos", f"le preguntaste: {accion.resumen}")
            self.contexto = consulta
            pitido("pregunta")
            self.avisar("pregunta", accion)
            self.mostrar(accion.resumen + "\n(respondé cuando termine de preguntar)", "pregunta", 25)
            self.escuchar()          # tu respuesta («a las 9», «el viernes») sin apretar la tecla
            return None
        self.contexto = None
        if accion.confirmar and not auto_confirmar:
            self.pendiente = accion
            self.pendiente_hasta = time.time() + config.CONFIRMAR_SEGUNDOS
            memoria.anotar("Vos", f"propusiste «{accion.resumen.splitlines()[0]}» y esperás su «dale» (todavía no se hizo)")
            pitido("pregunta")
            self.avisar("confirmar", accion)
            pregunta = "¿Lo hago?" if accion.tipo in ("moderar", "overlay", "titulo", "juego") else "¿Publico?"
            self.mostrar(f"{accion.resumen}\n\n{pregunta} Di «dale» o pulsa {config.CONFIRM_HOTKEY.upper()}. "
                         "«Cancela» para descartar; también puedes corregir.", "pregunta", config.CONFIRMAR_SEGUNDOS)
            self.escuchar()          # cuando termine de preguntar, te escucha solo (sin apretar la tecla)
            return None
        self._ejecutar(accion)

    def respuesta(self, texto):
        """Lo que dijiste con el micrófono abierto solo (después de «¿Lo publico?»): sí, no o una corrección."""
        texto = (texto or "").strip()
        if self.pendiente and time.time() > self.pendiente_hasta:
            self.pendiente = None
        if texto and self.contexto and not self.pendiente:
            return self.manejar_texto(texto)          # respuesta a «¿A qué hora es la raid?»
        if not texto or not self.pendiente:
            return None
        ban = self.pendiente.tipo == "moderar" and self.pendiente.datos.get("accion") == "banear"
        r = router.es_confirmacion(texto, estricto=ban)       # para banear, un «ya» o «bueno» suelto no alcanza
        if r or CORRIGE.search(router._norm(texto)):
            return self.manejar_texto(texto, estricto=ban)
        log(f"OÍDO (sin tecla, no era sí ni no; lo ignoro): {texto}")
        return self.mostrar(f"«{texto}»\nNo te entendí. Decí «dale» o «cancela» (o pulsá la tecla).", "pregunta", 8)

    def _relleno(self):
        self.ultimo_relleno = time.time()
        self.avisar("relleno")

    def confirmar(self):
        if not self.pendiente or time.time() > self.pendiente_hasta:
            self.pendiente = None
            return self.mostrar("No hay nada esperando confirmación.", "info", 4)
        accion, self.pendiente = self.pendiente, None
        log(f"CONFIRMADO: {accion.resumen.splitlines()[0]}")
        self._ejecutar(accion)

    def cancelar(self):
        if self.pendiente:
            log(f"CANCELADO: {self.pendiente.resumen.splitlines()[0]}")
            memoria.anotar("Vos", f"cancelaste «{self.pendiente.resumen.splitlines()[0]}» (no se hizo)")
        self.pendiente = None
        self.contexto = None
        pitido("fin")
        self.avisar("cancelado")
        self.mostrar("Cancelado.", "info", 3)

    @staticmethod
    def _tarda(accion):
        return accion.tipo == "miniatura" or (accion.tipo == "overlay" and accion.datos.get("accion") == "crear")

    def _ejecutar(self, accion, ejecutor=None):
        if self._tarda(accion):
            self.avisar("trabajando", accion)
            if self.fondo and ejecutor is None:
                self.mostrar(f"{accion.resumen}\nLo estoy diseñando (unos minutos). Te aviso; mientras, podés "
                             "seguir dándome órdenes.", "info", 10)
                threading.Thread(target=self._ejecutar, args=(accion, Ejecutor(self.ejecutor.simular)),
                                 daemon=True, name=f"diseño-{accion.tipo}").start()
                return
            self.mostrar(f"{accion.resumen}\nDiseñándolo (unos minutos)…", "info", 0)
        elif accion.tipo == "busqueda":
            self.avisar("buscando", accion)
            self.mostrar(f"{accion.resumen}\nBuscando…", "info", 0)
        else:
            self.mostrar(f"{accion.resumen}\nEjecutando…", "info", 0)
        sigue = threading.Timer(12, self.avisar, args=("buscando_mas",))
        if accion.tipo == "busqueda":
            sigue.start()             # si internet tarda, avisa que sigue buscando
        try:
            resultado = (ejecutor or self.ejecutor).ejecutar(accion)
        except Exception as e:  # noqa: BLE001
            sigue.cancel()
            log(f"ERROR: {e}")
            memoria.anotar("Vos", f"no pudiste hacer «{accion.resumen.splitlines()[0]}»: {e}")
            pitido("error")
            self.avisar("error", accion, str(e))
            return self.mostrar(f"No se pudo: {e}", "error", 12)
        sigue.cancel()
        if accion.tipo in ("respuesta", "busqueda"):
            memoria.anotar("Vos", f"dijiste en voz alta: {str(resultado).split(chr(10) + '(Fuente:')[0]}")
        else:
            memoria.anotar("Vos", f"hiciste: {str(resultado).splitlines()[0] if resultado else accion.resumen.splitlines()[0]}")
        pitido("ok")
        self.avisar("hecho", accion, resultado)
        self.mostrar(resultado, "ok", 8)
        m = accion.datos.get("miniatura") if accion.tipo == "titulo" else None
        if m:                        # «cambiá el título y haceme la miniatura»: ya se confirmó todo junto
            if isinstance(m, str):
                m = {"titulo": m, "subtitulo": "", "idea": ""}
            mini = H.Accion("miniatura", {**m, "subir_youtube": "youtube" in accion.datos["plataformas"]
                                          or config.MINIATURA_SUBIR_YOUTUBE},
                            f"Miniatura «{m['titulo']}»", False)
            self._ejecutar(mini)


class App:
    """La parte visible: teclas, micrófono, cartel. La lógica va en un hilo aparte."""

    def __init__(self, simular=False):
        import tkinter as tk

        from overlay import Overlay
        from voz import Grabadora, Transcriptor

        self.root = tk.Tk()
        self.root.withdraw()
        self.overlay = Overlay(self.root)
        self.ui = queue.Queue()
        self.tareas = queue.Queue()
        self.eventos = queue.Queue()
        self.voz = self.orbe = None
        if config.JARVIS_VOZ or config.JARVIS_ORBE:
            import jarvis
            self.voz = jarvis.Voz() if config.JARVIS_VOZ else None
            if self.voz and config.VOZ_RELLENO:
                self.voz.precalentar(jarvis.RELLENOS + jarvis.BUSCANDO + jarvis.BUSCANDO_MAS)   # «a ver…» listo para salir al instante
            if config.JARVIS_ORBE:
                if config.ORBE_ESTILO == "orbe":
                    self.orbe = jarvis.Orbe(self.root)
                else:
                    from cerebrito import Cerebrito
                    self.orbe = Cerebrito(self.root)
                    self.overlay.ancla = self.orbe.caja
                self.orbe.fuente = self._estado_orbe
        self.cerebro = Cerebro(lambda t, tipo="info", s=6: self.ui.put((t, tipo, s)), simular, self._avisar, fondo=True,
                               escuchar=self._pedir_respuesta)
        self.modo = "orden"              # "orden" (con la tecla) o "respuesta" (solo, después de una pregunta)
        self.esperar_respuesta = 0.0     # hasta cuándo espero que termine de preguntar para escucharte
        self.overlay.mostrar("Cargando Whisper…", "info", 0)
        self.root.update()
        self.stt = Transcriptor()
        self.grab = Grabadora()
        self.ocupado = False
        threading.Thread(target=self._trabajador, daemon=True).start()
        self._teclas()
        modelo = config.OLLAMA_MODEL if config.USE_OLLAMA else "patrones"
        self.overlay.mostrar(f"Listo. Whisper en {self.stt.dispositivo.upper()}, IA: {modelo}.\n"
                             f"Hablar: {config.HOTKEY.upper()} · Dale: {config.CONFIRM_HOTKEY.upper()} · "
                             f"Cancelar: {config.CANCEL_HOTKEY.upper()}", "ok", 8)
        if config.USE_OLLAMA:
            self.tareas.put(("precargar", None))
        try:  # escucha el chat de Kick para la moderación por voz
            import chat_vivo
            chat_vivo.empezar()
        except Exception as e:  # noqa: BLE001
            print(f"[chat] No pude escuchar el chat de Kick: {e}")
        self._avisar("saludo")

    def _avisar(self, evento, accion=None, detalle=None):
        """Modo Jarvis: lo dice en voz alta y hace destellar el orbe (se llama desde el hilo de trabajo)."""
        animo = accion.datos.get("animo") if accion is not None and evento == "hecho" else None
        if self.orbe and animo == "picado" and hasattr(self.orbe, "poner_animo"):
            self.orbe.poner_animo("picado", 12)           # cara de caliente mientras te contesta
        elif self.orbe and evento in ("hecho", "error", "cancelado"):
            self.orbe.destellar("error" if evento == "error" else "ok")
        if self.voz:
            import jarvis
            self.voz.decir(jarvis.frase(evento, accion, detalle))

    def _pedir_respuesta(self):
        """El Cerebro te preguntó algo («¿Lo publico?»): cuando termine de hablar, abre el micrófono unos segundos."""
        if config.ESCUCHAR_RESPUESTA:
            self.eventos.put("escuchar_respuesta")

    def _escuchar(self, modo):
        self.esperar_respuesta = 0.0
        self.modo = modo
        if modo == "respuesta":
            self.grab.empezar(espera=config.RESPUESTA_SEGUNDOS, maximo=10)
        else:
            self.grab.empezar()
        pitido("inicio")
        self._estado_txt("🎙 Escuchando…" if modo == "orden" else "🎙 Te escucho…")

    def _estado_txt(self, texto):
        """Estados de paso: con el cerebro en pantalla no hace falta el cartel (lo dice su cara)."""
        if self.orbe:
            self.overlay.ocultar()
        else:
            self.overlay.mostrar(texto, "info", 0)

    def _estado_orbe(self):
        """Qué muestra el orbe ahora: escuchando (sigue tu voz), pensando, hablando (sigue su voz) u oculto."""
        grab = getattr(self, "grab", None)          # el cerebro arranca antes que el micrófono
        if grab and grab.activa:
            return "escuchando", min(1.0, grab.nivel * 12)
        if self.voz and self.voz.hablando:
            return "hablando", min(1.0, self.voz.nivel)
        if self.ocupado:
            return "pensando", 0.4
        return "oculto", 0.0

    def _teclas(self):
        import keyboard
        ultima = {}

        def poner(ev):
            def f():
                if time.time() - ultima.get(ev, 0) > 0.4:
                    ultima[ev] = time.time()
                    self.eventos.put(ev)
            return f

        keyboard.add_hotkey(config.HOTKEY, poner("hablar"))
        keyboard.add_hotkey(config.CONFIRM_HOTKEY, poner("confirmar"))
        keyboard.add_hotkey(config.CANCEL_HOTKEY, poner("cancelar"))

    def _trabajador(self):
        while True:
            tipo, dato = self.tareas.get()
            try:
                if tipo == "audio":
                    t0 = time.time()
                    texto = self.stt.transcribir(dato)
                    print(f"(transcrito en {time.time() - t0:.1f} s): {texto}")
                    if texto:
                        self.cerebro.manejar_texto(texto)
                    else:
                        self.ui.put(("No te escuché bien.", "error", 4))
                elif tipo == "respuesta":
                    texto = self.stt.transcribir(dato)
                    print(f"(respuesta sin tecla): {texto}")
                    self.cerebro.respuesta(texto)
                elif tipo == "confirmar":
                    self.cerebro.confirmar()
                elif tipo == "cancelar":
                    self.cerebro.cancelar()
                elif tipo == "precargar":
                    router.precargar()
            except Exception as e:  # noqa: BLE001
                log(f"ERROR en {tipo}: {traceback.format_exc()}")
                self.ui.put((f"Error: {e}", "error", 10))
            finally:
                self.ocupado = False

    def _tick(self):
        try:
            self._tick_seguro()
        except Exception:  # noqa: BLE001
            log(f"ERROR en la pantalla: {traceback.format_exc()}")
            self.overlay.mostrar("Error interno (anotado en data/fallos.log). Sigo funcionando.", "error", 6)
        self.root.after(50, self._tick)

    def _tick_seguro(self):
        try:
            while True:
                texto, tipo, segundos = self.ui.get_nowait()
                if self.orbe and tipo == "info" and segundos == 0:
                    # «Escuchando…», «Pensando…», «Ejecutando…»: ya lo muestra el cerebro con la cara
                    print(f"[info] {texto}")
                    self.overlay.ocultar()
                    continue
                self.overlay.mostrar(texto, tipo, segundos)
        except queue.Empty:
            pass
        try:
            while True:
                ev = self.eventos.get_nowait()
                if ev == "hablar":
                    if self.grab.activa and self.modo == "respuesta" and not self.grab.hablo:
                        self.grab.parar()            # te escuchaba solo y apretaste: ahora es una orden normal
                        self._escuchar("orden")
                    elif self.grab.activa:
                        self.modo = "orden"          # apretaste para terminar: va como orden normal
                        self._procesar()
                    elif self.ocupado:
                        self.overlay.mostrar("Espera, sigo con la orden anterior…", "info", 3)
                    else:
                        if self.voz:
                            self.voz.callar()
                        self._escuchar("orden")
                elif ev == "escuchar_respuesta":
                    self.esperar_respuesta = time.time() + 30
                elif ev in ("confirmar", "cancelar"):
                    self.esperar_respuesta = 0.0
                    if self.grab.activa and self.modo == "respuesta":
                        self.grab.parar()            # contestaste con la tecla: ya no hace falta escucharte
                        self.modo = "orden"
                    self.tareas.put((ev, None))
        except queue.Empty:
            pass
        if self.grab.activa and self.grab.debe_parar():
            self._procesar()
        elif self.esperar_respuesta and not self.grab.activa:
            hay_pregunta = self.cerebro.pendiente or self.cerebro.contexto
            if time.time() > self.esperar_respuesta or not hay_pregunta:
                self.esperar_respuesta = 0.0
            elif not self.ocupado and (not self.voz or self.voz.callado()):
                self._escuchar("respuesta")      # ya terminó de preguntar: te escucho sin la tecla
        elif (config.USE_OLLAMA and not self.ocupado and not self.grab.activa
              and router.ULTIMO_USO[0] and time.time() - router.ULTIMO_USO[0] > 20 * 60):
            router.ULTIMO_USO[0] = time.time()       # cada 20 min sin órdenes: que Ollama no descargue el modelo
            self.tareas.put(("precargar", None))

    def _procesar(self):
        modo, self.modo = self.modo, "orden"
        if modo == "orden":
            pitido("fin")
        audio = self.grab.parar()
        if len(audio) < 16000 * 0.4:
            if modo == "orden":          # si te escuchaba solo y no dijiste nada, no molesta con carteles
                self.overlay.mostrar("No se oyó nada.", "info", 3)
            else:
                self.overlay.ocultar()
            return
        self.ocupado = True
        self._estado_txt("Transcribiendo…")
        self.tareas.put(("respuesta" if modo == "respuesta" else "audio", audio))

    def correr(self):
        self.root.after(50, self._tick)
        self.root.mainloop()


def modo_texto(texto, simular, si):
    c = Cerebro(lambda t, tipo="info", s=0: print(f"[{tipo}] {t}"), simular)
    c.manejar_texto(texto, auto_confirmar=si)
    if c.pendiente:
        if input("\n¿Publico? [s/N] ").strip().lower() in ("s", "si", "sí", "dale"):
            c.confirmar()
        else:
            c.cancelar()


def registrar_fallos():
    """Todo error (también los que cierran el programa de golpe) queda en data/fallos.log."""
    archivo = open(config.DATA / "fallos.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    archivo.write(f"\n===== Arranque {dt.datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
    faulthandler.enable(archivo, all_threads=True)

    def anotar(tipo, valor, tb, hilo="principal"):
        texto = "".join(traceback.format_exception(tipo, valor, tb))
        archivo.write(f"[{dt.datetime.now():%H:%M:%S}] Error en hilo {hilo}:\n{texto}\n")
        print(texto, file=sys.stderr)

    sys.excepthook = anotar
    threading.excepthook = lambda a: anotar(a.exc_type, a.exc_value, a.exc_traceback, a.thread.name if a.thread else "?")
    return archivo


def main():
    ap = argparse.ArgumentParser(description="El Cerebro v2")
    ap.add_argument("--texto", help="ejecuta esta orden escrita y sale")
    ap.add_argument("--si", action="store_true", help="con --texto: publica sin preguntar")
    ap.add_argument("--simular", action="store_true", help="no publica nada")
    ap.add_argument("--calibrar", action="store_true")
    ap.add_argument("--micros", action="store_true")
    ap.add_argument("--salidas", action="store_true", help="lista las salidas de audio (para VOZ_DISPOSITIVO)")
    ap.add_argument("--decir", help="prueba la voz de Jarvis con este texto")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if a.salidas:
        import voz
        return voz.listar_salidas()
    if a.decir:
        import jarvis
        v = jarvis.Voz()
        v.decir(a.decir)
        time.sleep(0.5)
        while v.ocupada or v.hablando or not v._cola.empty():
            time.sleep(0.2)
        return None
    if a.micros or a.calibrar:
        import voz
        return voz.listar_micros() if a.micros else voz.calibrar()
    if a.texto:
        return modo_texto(a.texto, a.simular, a.si)
    fallos = registrar_fallos()
    try:
        App(simular=a.simular).correr()
    except KeyboardInterrupt:
        print("\nHasta luego.")
    except Exception:  # noqa: BLE001
        fallos.write(f"[{dt.datetime.now():%H:%M:%S}] El Cerebro se cerró por un error:\n{traceback.format_exc()}\n")
        raise


if __name__ == "__main__":
    sys.exit(main())
