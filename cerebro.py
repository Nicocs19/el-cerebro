"""EL CEREBRO v2: le hablas en lenguaje natural y ejecuta por ti.

Uso:
  python cerebro.py                    -> modo voz (teclas del .env)
  python cerebro.py --texto "..."      -> una orden escrita (pruebas o botones del Loupedeck)
  python cerebro.py --texto "..." --si -> igual, sin pedir confirmación
  python cerebro.py --simular          -> no publica nada, solo muestra lo que haría
  python cerebro.py --calibrar | --micros
"""
import argparse
import queue
import sys
import threading
import time

import config
import herramientas as H
import router
from acciones import Ejecutor, log
from avisos import pitido


class Cerebro:
    """La lógica: interpreta, pide confirmación y ejecuta. Corre en un solo hilo de trabajo."""

    def __init__(self, mostrar, simular=False):
        self.mostrar = mostrar          # mostrar(texto, tipo, segundos)
        self.ejecutor = Ejecutor(simular)
        self.pendiente = None           # Accion esperando "dale"
        self.pendiente_hasta = 0
        self.contexto = None            # orden incompleta mientras se responde una aclaración

    def manejar_texto(self, texto, auto_confirmar=False):
        texto = texto.strip()
        if not texto:
            return
        log(f"OÍDO: {texto}")
        if self.pendiente and time.time() > self.pendiente_hasta:
            self.pendiente = None
        r = router.es_confirmacion(texto)
        if r == "confirmar":
            return self.confirmar()
        if r == "cancelar":
            return self.cancelar()
        consulta = f"{self.contexto}. {texto}" if self.contexto else texto
        self.mostrar(f"«{texto}»\nPensando…", "info", 0)
        try:
            accion, origen = router.interpretar(consulta, self.pendiente)
        except H.ErrorOrden as e:
            self.contexto = None
            pitido("error")
            return self.mostrar(f"«{texto}»\n{e}", "error", 10)
        except Exception as e:  # noqa: BLE001
            self.contexto = None
            pitido("error")
            return self.mostrar(f"Error al interpretar: {e}", "error", 10)

        if accion.tipo == "aclaracion":
            self.contexto = consulta
            pitido("pregunta")
            return self.mostrar(accion.resumen + "\n(pulsa la tecla y responde)", "pregunta", 25)
        self.contexto = None
        if accion.confirmar and not auto_confirmar:
            self.pendiente = accion
            self.pendiente_hasta = time.time() + config.CONFIRMAR_SEGUNDOS
            pitido("pregunta")
            return self.mostrar(f"{accion.resumen}\n\n¿Publico? Di «dale» o pulsa {config.CONFIRM_HOTKEY.upper()}. "
                                "«Cancela» para descartar; también puedes corregir.", "pregunta",
                                config.CONFIRMAR_SEGUNDOS)
        self._ejecutar(accion)

    def confirmar(self):
        if not self.pendiente or time.time() > self.pendiente_hasta:
            self.pendiente = None
            return self.mostrar("No hay nada esperando confirmación.", "info", 4)
        accion, self.pendiente = self.pendiente, None
        self._ejecutar(accion)

    def cancelar(self):
        self.pendiente = None
        self.contexto = None
        pitido("fin")
        self.mostrar("Cancelado.", "info", 3)

    def _ejecutar(self, accion):
        self.mostrar(f"{accion.resumen}\nEjecutando…", "info", 0)
        try:
            resultado = self.ejecutor.ejecutar(accion)
        except Exception as e:  # noqa: BLE001
            log(f"ERROR: {e}")
            pitido("error")
            return self.mostrar(f"No se pudo: {e}", "error", 12)
        pitido("ok")
        self.mostrar(resultado, "ok", 8)


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
        self.cerebro = Cerebro(lambda t, tipo="info", s=6: self.ui.put((t, tipo, s)), simular)
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
                elif tipo == "confirmar":
                    self.cerebro.confirmar()
                elif tipo == "cancelar":
                    self.cerebro.cancelar()
                elif tipo == "precargar":
                    router.precargar()
            except Exception as e:  # noqa: BLE001
                self.ui.put((f"Error: {e}", "error", 10))
            finally:
                self.ocupado = False

    def _tick(self):
        try:
            while True:
                texto, tipo, segundos = self.ui.get_nowait()
                self.overlay.mostrar(texto, tipo, segundos)
        except queue.Empty:
            pass
        try:
            while True:
                ev = self.eventos.get_nowait()
                if ev == "hablar":
                    if self.grab.activa:
                        self._procesar()
                    elif self.ocupado:
                        self.overlay.mostrar("Espera, sigo con la orden anterior…", "info", 3)
                    else:
                        self.grab.empezar()
                        pitido("inicio")
                        self.overlay.mostrar("🎙 Escuchando…", "info", 0)
                elif ev in ("confirmar", "cancelar"):
                    self.tareas.put((ev, None))
        except queue.Empty:
            pass
        if self.grab.activa and self.grab.debe_parar():
            self._procesar()
        self.root.after(50, self._tick)

    def _procesar(self):
        pitido("fin")
        audio = self.grab.parar()
        if len(audio) < 16000 * 0.4:
            self.overlay.mostrar("No se oyó nada.", "info", 3)
            return
        self.ocupado = True
        self.overlay.mostrar("Transcribiendo…", "info", 0)
        self.tareas.put(("audio", audio))

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


def main():
    ap = argparse.ArgumentParser(description="El Cerebro v2")
    ap.add_argument("--texto", help="ejecuta esta orden escrita y sale")
    ap.add_argument("--si", action="store_true", help="con --texto: publica sin preguntar")
    ap.add_argument("--simular", action="store_true", help="no publica nada")
    ap.add_argument("--calibrar", action="store_true")
    ap.add_argument("--micros", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if a.micros or a.calibrar:
        import voz
        return voz.listar_micros() if a.micros else voz.calibrar()
    if a.texto:
        return modo_texto(a.texto, a.simular, a.si)
    try:
        App(simular=a.simular).correr()
    except KeyboardInterrupt:
        print("\nHasta luego.")


if __name__ == "__main__":
    sys.exit(main())
