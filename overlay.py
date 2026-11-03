"""Cartelito flotante (siempre encima, sin robar el foco al juego).

Muestra lo que el Cerebro escuchó, lo que va a hacer y si espera tu "dale".
Solo lo ves tú: no lo captures en OBS (captura la ventana del juego, no el escritorio).
"""
import tkinter as tk

import config

COLORES = {"info": "#E8C468", "ok": "#5BD17A", "error": "#FF6B6B", "pregunta": "#6FB7FF"}


class Overlay:
    def __init__(self, root):
        self.root = root
        self.activo = config.OVERLAY
        self._ocultar = None
        self.ancla = None          # función -> (x, y, ancho, alto) del cerebro: el cartel va arriba de él
        if not self.activo:
            return
        w = self.win = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        w.configure(bg="#14110C")
        marco = tk.Frame(w, bg="#14110C", highlightbackground="#C9A227", highlightthickness=2)
        marco.pack(fill="both", expand=True)
        self.titulo = tk.Label(marco, text="EL CEREBRO", bg="#14110C", fg="#E8C468",
                               font=("Segoe UI", 10, "bold"), anchor="w")
        self.titulo.pack(fill="x", padx=12, pady=(8, 0))
        self.texto = tk.Label(marco, text="", bg="#14110C", fg="#F2EAD8", font=("Segoe UI", 11),
                              justify="left", anchor="w", wraplength=420)
        self.texto.pack(fill="x", padx=12, pady=(2, 10))
        w.withdraw()
        self._sin_foco()

    def _sin_foco(self):
        """En Windows: la ventana no se activa al aparecer (no te saca del juego)."""
        try:
            import ctypes
            self.win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = -20, 0x08000000, 0x80, 0x8
            estilo = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                                estilo | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
        except Exception:  # noqa: BLE001  (no es Windows o falla: no pasa nada)
            pass

    def mostrar(self, texto, tipo="info", segundos=6, titulo="EL CEREBRO"):
        print(f"[{tipo}] {texto}")
        if not self.activo:
            return
        self.titulo.config(text=titulo, fg=COLORES.get(tipo, "#E8C468"))
        self.texto.config(text=texto)
        self.win.update_idletasks()
        ancho = max(320, min(460, self.texto.winfo_reqwidth() + 28))
        alto = self.win.winfo_reqheight()
        if self.ancla:              # como un globo de diálogo, justo arriba del cerebro
            bx, by, bw, _ = self.ancla()
            x = max(8, min(self.win.winfo_screenwidth() - ancho - 8, bx + bw - ancho))
            y = max(8, by - alto - 4)
        else:
            x, y = self.win.winfo_screenwidth() - ancho - 24, 24
        self.win.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.win.deiconify()
        self.win.lift()
        if self._ocultar:
            self.root.after_cancel(self._ocultar)
            self._ocultar = None
        if segundos:
            self._ocultar = self.root.after(int(segundos * 1000), self.ocultar)

    def ocultar(self):
        if self.activo:
            self.win.withdraw()
