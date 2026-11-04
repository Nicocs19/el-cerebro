"""El asistente en pantalla: Hogger el H (un gnoll de dibujito) o el cerebro de antes, que reaccionan a lo que pasa.

Diseño «hogger» (CEREBRO_DISENO, el de siempre ahora): ver Cerebrito._dibujar_hogger.

Diseño «gafas» (el de siempre ahora): un cerebro relajado y medio bobo, con gafas redondas de colores,
ojos a media asta, dientes de conejo y colores que cambian despacito.
- quieto: se balancea tranquilo, con los ojos a media asta y la mirada perdida.
- escuchando: se baja las gafas y te mira con los ojos bien abiertos; le salen ondas con tu voz.
- pensando: ladea la cabeza, bizquea para arriba, saca la lengua y le salen burbujitas.
- hablando: mueve la boca (con los dientes de conejo) al ritmo de su voz.
- ok: ojos felices y estrellitas de colores.  error: ojos en espiral, mareado.
- oculto: se desvanece (vuelve a aparecer cuando lo llamás).
Con CEREBRO_DISENO=clasico vuelve el cerebro rosado sin gafas.

Se dibuja en una ventana transparente que no roba el foco ni los clics (no molesta al juego).
"""
import colorsys
import math
import random
import time

import config

CLAVE = "#010203"   # color que Windows vuelve transparente
ROSA, ROSA_CLARO, ROSA_OSCURO, CONTORNO = "#F59AB4", "#FFC4D3", "#D9708F", "#7A2943"
OJO, PUPILA, BOCA, LENGUA = "#FFFFFF", "#1B1B26", "#5B1024", "#FF6F8E"
MARCO = "#251A38"   # marco de las gafas
COLOR_ESTADO = {"escuchando": "#38E1FF", "pensando": "#E8C468", "hablando": "#F5D98B", "ok": "#4CE38A", "error": "#FF5A5A"}


class Cerebrito:
    TAM = 230

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
        self.x, self.y = self._ubicar()
        self.win.update_idletasks()
        self._sin_foco_ni_clics()
        self.fuente = None              # función -> (estado, nivel 0..1)
        self.alpha = 0.0
        self.n = 0.0
        self.destello = None
        self.t0 = time.time()
        self.mirada = [0.0, 0.0]        # hacia dónde miran las pupilas (-1..1)
        self.mirada_obj = [0.0, 0.0]
        self.prox_mirada = 0.0
        self.prox_parpadeo = time.time() + 2
        self.gafas_y = 0.0              # cuánto se bajó las gafas (para mirarte por encima)
        self.parpado = 0.45             # qué tan cerrados tiene los ojos (0 abiertos, 1 cerrados)
        self.animo = None               # ("picado", hasta): cara de caliente mientras contesta
        root.after(33, self._paso)

    # ------------------------------------------------------------ ventana
    def _ubicar(self):
        sw, sh, t = self.win.winfo_screenwidth(), self.win.winfo_screenheight(), self.TAM
        pos = {"abajo-derecha": (sw - t - 20, sh - t - 70), "abajo-izquierda": (20, sh - t - 70),
               "arriba-derecha": (sw - t - 20, 20), "arriba-izquierda": (20, 20),
               "abajo-centro": ((sw - t) // 2, sh - t - 70)}
        x, y = pos.get(config.ORBE_POSICION, pos["abajo-derecha"])
        self.win.geometry(f"{t}x{t}+{x}+{y}")
        return x, y

    def caja(self):
        """(x, y, ancho, alto) en pantalla, para poner el cartel al lado."""
        return self.x, self.y, self.TAM, self.TAM

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

    def poner_animo(self, tipo, segundos=10):
        self.animo = (tipo, time.time() + segundos)

    def _paso(self):
        try:
            self._dibujar()
        except Exception as e:  # noqa: BLE001
            print(f"[cerebro] {e}")
        self.c.after(33, self._paso)

    # ------------------------------------------------------------ dibujo
    def _estado(self):
        estado, nivel = self.fuente() if self.fuente else ("oculto", 0.0)
        if self.destello and time.time() - self.destello[1] < 1.6:
            estado, nivel = self.destello[0], 0.5
        if config.CEREBRO_SIEMPRE and estado == "oculto":
            estado = "quieto"
        return estado, nivel

    def _dibujar(self):
        estado, nivel = self._estado()
        ahora = time.time()
        objetivo = 0.0 if estado == "oculto" else 0.97
        self.alpha += (objetivo - self.alpha) * 0.2
        if abs(self.alpha - objetivo) > 0.005:
            self.win.attributes("-alpha", max(0.0, min(1.0, self.alpha)))
        if self.alpha < 0.02 and estado == "oculto":
            self.c.delete("all")
            return
        self.n += (min(1.0, nivel) - self.n) * 0.35
        self.dibujar(estado, ahora - self.t0, self.n)

    def _mover_mirada(self, estado, t):
        ahora = time.time()
        if estado == "pensando":
            self.mirada_obj = [0.7 * math.cos(t * 3), -0.6 + 0.3 * math.sin(t * 3)]   # ojos que dan vueltas
        elif estado == "hablando":
            self.mirada_obj = [0.15 * math.sin(t * 1.3), 0.1]
        elif estado == "escuchando":
            self.mirada_obj = [0.55, -0.35]                                         # mira al cartel
        elif ahora > self.prox_mirada:
            self.mirada_obj = [random.uniform(-0.8, 0.8), random.uniform(-0.5, 0.5)]
            self.prox_mirada = ahora + random.uniform(1.2, 3.0)
        for i in (0, 1):
            self.mirada[i] += (self.mirada_obj[i] - self.mirada[i]) * 0.25

    def dibujar(self, estado, t, n):
        if config.CEREBRO_DISENO == "clasico":
            self._dibujar_clasico(estado, t, n)
        elif config.CEREBRO_DISENO == "gafas":
            self._dibujar_gafas(estado, t, n)
        else:
            self._dibujar_hogger(estado, t, n)

    # ------------------------------------------------------------ Hogger el H
    def _dibujar_hogger(self, estado, t, n):
        """Hogger el H: un gnoll de dibujito, jefe de la manada de The H's.

        Hiena con manchas, cresta a rayas blancas y negras, orejas que se paran cuando te escucha, hocico oscuro
        con colmillos, collar con pinchos y la medalla de la H, hombreras de bronce. Diseño propio (no es el
        modelo del juego).
        """
        c = self.c
        c.delete("all")
        m = self.TAM / 2
        color = COLOR_ESTADO.get(estado, "#E8C468")
        arcoiris = t / 24.0
        animo = getattr(self, "animo", None)
        picado = bool(animo) and animo[0] == "picado" and time.time() < animo[1] and estado in ("hablando", "quieto", "oculto")
        pelo, pelo_luz, mancha, borde = "#C99B5B", "#E2BE84", "#5E3B1C", "#2E1C0C"
        if picado:                                            # se calentó: pelo rojizo
            pelo, pelo_luz, mancha = "#D9714E", "#F0A27E", "#6E1E12"
        hocico, nariz, boca = "#463C36", "#120E0C", "#5B1020"
        bronce, bronce_luz, metal, tela = "#A9772F", "#D8AE5E", "#E6E0D0", "#7A2020"

        grados = {"escuchando": 0.0, "pensando": 7 + 2 * math.sin(t * 2), "hablando": 2.5 * math.sin(t * 2.4),
                  "ok": 4 * math.sin(t * 5), "error": 6 * math.sin(t * 7)}.get(estado, 3 * math.sin(t * 0.8))
        salto = {"escuchando": 8 * n, "hablando": 4 * n}.get(estado, 0) + 2 * math.sin(t * 1.6)
        cx, cy = m, m + 9 - salto
        if picado:
            grados = 3 * math.sin(t * 9)
            cx += random.uniform(-1.5, 1.5)
        s = 1.0 + (0.04 * n if estado == "escuchando" else 0)
        th = math.radians(grados)
        co, si = math.cos(th), math.sin(th)
        esc = [s]                                             # el cuerpo un poco más chico que la cabeza

        def P(dx, dy):
            k = esc[0]
            return cx + k * (dx * co - dy * si), cy + k * (dx * si + dy * co)

        def ovalo(dx, dy, rx, ry=None, **kw):
            x, y = P(dx, dy)
            ry = rx if ry is None else ry
            k = esc[0]
            return c.create_oval(x - rx * k, y - ry * k, x + rx * k, y + ry * k, **kw)

        def linea(puntos, **kw):
            return c.create_line(*[v for p in puntos for v in P(*p)], **kw)

        def poligono(puntos, **kw):
            return c.create_polygon(*[v for p in puntos for v in P(*p)], **kw)

        def espejo(puntos):
            return [(-x, y) for x, y in puntos]

        # aura del estado (quieto no tiene)
        for i, a in enumerate((0.28, 0.18) if estado in COLOR_ESTADO else ()):
            r = (92 + i * 10 + 6 * n) * s
            c.create_oval(cx - r, cy - r * 0.85, cx + r, cy + r * 0.85, outline=_mezclar(color, a + 0.4 * n), width=3)

        # --- cuerpo: pecho de tela roja, hombreras de bronce con un pincho
        esc[0] = s * 0.92
        poligono([(-42, 54), (42, 54), (58, 104), (-58, 104)], fill=tela, outline=borde, width=3)
        for lado in (-1, 1):
            poligono([(lado * 60, 56), (lado * 76, 56), (lado * 88, 30)], fill=metal, outline=borde, width=2)
            ovalo(lado * 68, 80, 34, 25, fill=bronce, outline=borde, width=3)
            ovalo(lado * 66, 74, 25, 15, fill=bronce_luz, outline="")
            ovalo(lado * 60, 69, 9, 4, fill="#F3D99A", outline="")
            linea([(lado * 38, 90), (lado * 68, 99), (lado * 98, 90)], smooth=True, fill=borde, width=3)
            for rx_, ry_ in ((50, 86), (86, 86)):
                ovalo(lado * rx_, ry_, 3, fill="#3A2A1A", outline="")
        esc[0] = s * 1.1

        # --- collar de cuero con pinchos y la medalla de la H
        poligono([(-48, 38), (48, 38), (52, 60), (-52, 60)], fill="#2B2220", outline="#120C0A", width=3)
        for x in (-40, -22, 22, 40):
            lado = -1 if x < 0 else 1
            poligono([(x - 6, 40), (x + 6, 40), (x + lado * 5, 22)], fill=metal, outline=borde, width=2)
        ovalo(0, 50, 15, fill="#E8C468", outline="#6B4A12", width=3)
        mx, my = P(0, 50.5)
        c.create_text(mx, my, text="H", fill="#5A1A1A", font=("Georgia", int(15 * s), "bold"), angle=-grados)

        # --- orejas: paradas cuando te escucha, caídas si algo salió mal, con un tic de vez en cuando
        tic = 6 * max(0.0, math.sin(t * 2.7)) ** 12
        punta = {"escuchando": (-56, -104), "error": (-86, -60), "pensando": (-70, -90),
                 "ok": (-62, -98)}.get(estado, (-66 - tic, -94 + tic))
        for lado in (-1, 1):
            px_, py_ = punta
            if estado == "pensando" and lado == 1:
                px_, py_ = -60, -100                       # una oreja más parada que la otra
            ext = [(-46, -42), (px_, py_), (-18, -60)]
            inn = [(-40, -46), (px_ * 0.85 - 4, py_ * 0.88), (-24, -58)]
            poligono(ext if lado < 0 else espejo(ext), fill="#4E3720", outline=borde, width=3)
            poligono(inn if lado < 0 else espejo(inn), fill="#B9786A", outline="")

        # --- cresta a rayas (blanco, negro y gris) que se mece
        vaiven = 3 * math.sin(t * 1.9)
        for i, x in enumerate((-27, 27, -18, 18, -9, 9, 0)):
            alto = -98 + abs(x) * 0.8 - (8 if estado == "escuchando" else 0)
            punta_x = x * 1.6 + vaiven * (1 + abs(x) / 27)
            poligono([(x - 8, -46), (x + 8, -46), (punta_x, alto)], fill=("#E3E0D8", "#1C1A1A", "#8E8A84")[i % 3],
                     outline=borde, width=2)

        # --- cabeza: hiena con manchas y mechones en los cachetes
        for lado in (-1, 1):
            mechon = [(-44, -26), (-62, -14), (-49, -8), (-60, 4), (-44, 6), (-50, 16), (-34, 14)]
            poligono(mechon if lado < 0 else espejo(mechon), fill=pelo, outline=borde, width=3)
        ovalo(0, -12, 50, 46, fill=pelo, outline=borde, width=3)
        ovalo(-20, -40, 16, 8, fill=pelo_luz, outline="")
        for dx, dy, rx_, ry_ in ((-28, -38, 5, 4), (-12, -46, 4, 3), (12, -46, 5, 3.5), (28, -38, 4, 3.5),
                                 (-38, -16, 4, 4), (38, -14, 4.5, 4), (-34, 6, 3, 3), (34, 8, 3.5, 3)):
            ovalo(dx, dy, rx_, ry_, fill=mancha, outline="")

        # --- ojos ámbar con pupila de fiera
        self._mover_mirada(estado, t)
        ahora = time.time()
        if ahora > self.prox_parpadeo + 0.14:
            self.prox_parpadeo = ahora + random.uniform(2.5, 5.5)
        parpadea = estado not in ("ok", "error", "escuchando") and ahora >= self.prox_parpadeo
        for lado in (-1, 1):
            ox, oy = P(lado * 21, -20)
            grande = 1.25 if estado == "escuchando" else 1.0
            rx, ry = 11 * s * grande, 8.5 * s * grande
            if estado == "ok":                                   # ojos felices ^ ^
                c.create_arc(ox - rx, oy - ry * 0.4, ox + rx, oy + ry * 1.4, start=20, extent=140,
                             style="arc", outline=borde, width=4)
                continue
            if estado == "error":                                # ojos en espiral, mareado
                pts = []
                for k in range(26):
                    a = k * 0.6 + t * 8 * lado
                    rr = 1.2 + k * 0.36
                    pts += [ox + rr * s * math.cos(a), oy + rr * s * math.sin(a)]
                c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill="#F4E3B0", outline=borde, width=2)
                c.create_line(*pts, fill=borde, width=2, smooth=True)
                continue
            if parpadea:
                c.create_line(ox - rx, oy + 1, ox + rx, oy + 1, fill=borde, width=4, capstyle="round")
                continue
            c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill="#FF5A3C" if picado else "#F4C430",
                          outline=borde, width=2)
            px = ox + self.mirada[0] * rx * 0.45
            py = oy + self.mirada[1] * ry * 0.35
            if estado == "escuchando":                           # pupila redonda y grande: atento
                c.create_oval(px - 5 * s, py - 5 * s, px + 5 * s, py + 5 * s, fill=PUPILA, outline="")
            else:                                                # pupila de fiera
                c.create_oval(px - 2.6 * s, py - 6.5 * s, px + 2.6 * s, py + 6.5 * s, fill=PUPILA, outline="")
            c.create_oval(px - 4, py - 5, px - 1, py - 2, fill="#FFFFFF", outline="")

        # --- cejas de fiera
        for lado in (-1, 1):
            if picado:
                linea([(lado * 36, -40), (lado * 9, -27)], fill="#2A170A", width=7, capstyle="round")
                continue
            alto = -33 - (7 if estado == "escuchando" else 0) - (3 * n if estado == "hablando" else 0)
            if estado == "pensando":
                alto += -6 if lado == 1 else 2
            caida = 4 if estado != "error" else -4
            linea([(lado * 34, alto - caida), (lado * 10, alto + caida)], fill="#3A2614", width=6, capstyle="round")

        # --- hocico oscuro, nariz y boca con colmillos
        ovalo(0, 14, 31, 22, fill=hocico, outline=borde, width=3)
        ovalo(0, -2, 13, 12, fill=hocico, outline="")
        ovalo(0, 3, 11, 7, fill=nariz, outline="")
        ovalo(-4, 0, 3, 1.8, fill="#8F8F8F", outline="")
        by = 21
        if estado == "hablando":
            alto = 6 + 22 * n
            ovalo(0, by + alto / 2, 20 + 4 * n, alto / 2 + 2, fill=boca, outline=borde, width=3)
            if alto > 14:
                ovalo(0, by + alto - 3, 9, 4, fill="#E0607A", outline="")
            for x in (-13, -6.5, 0, 6.5, 13):
                poligono([(x - 3.2, by), (x + 3.2, by), (x, by + 6)], fill="#FFFDF2", outline="")
            for x in (-10, 10):
                poligono([(x - 3, by + alto + 2), (x + 3, by + alto + 2), (x, by + alto - 5)], fill="#FFFDF2", outline="")
        elif picado:                                              # gruñido: dientes apretados
            poligono([(-20, by - 2), (20, by - 2), (18, by + 10), (-18, by + 10)], fill="#FFFDF2", outline=borde, width=2)
            linea([(-19, by + 4), (19, by + 4)], fill=borde, width=2)
            for x in (-12, -4, 4, 12):
                linea([(x, by - 2), (x, by + 10)], fill=borde, width=2)
        elif estado == "ok":                                      # sonrisa grande con colmillos
            poligono([(-24, by - 4), (24, by - 4), (14, by + 12), (0, by + 15), (-14, by + 12)], smooth=True,
                     fill=boca, outline=borde, width=3)
            for x in (-14, -7, 0, 7, 14):
                poligono([(x - 3.2, by - 3), (x + 3.2, by - 3), (x, by + 3)], fill="#FFFDF2", outline="")
        elif estado == "error":
            linea([(-16, by + 4), (-6, by - 1), (4, by + 4), (14, by - 1)], smooth=True, fill="#FFFDF2", width=3)
        elif estado == "pensando":                                # boca de costado, un colmillo afuera
            linea([(-14, by + 2), (4, by + 4), (18, by - 2)], smooth=True, fill="#FFFDF2", width=3, capstyle="round")
            poligono([(9, by + 2), (15, by + 1), (12, by + 9)], fill="#FFFDF2", outline="")
        else:                                                     # sonrisa canchera con colmillos
            linea([(-20, by), (-8, by + 6), (8, by + 6), (22, by - 3)], smooth=True, fill="#FFFDF2", width=3,
                  capstyle="round")
            for x in (-11, 11):
                poligono([(x - 3, by + 3), (x + 3, by + 3), (x, by + 11)], fill="#FFFDF2", outline="")

        # --- extras de cada estado
        if picado:                                                # vapor de enojo
            for i in range(3):
                fase = (t * 1.4 + i / 3) % 1.0
                for lado in (-1, 1):
                    x, y = P(lado * (58 + 10 * fase), -50 - 36 * fase)
                    r = 4 + 7 * fase
                    c.create_oval(x - r, y - r, x + r, y + r, outline=_mezclar("#FFFFFF", 0.9 - 0.6 * fase), width=2)
        elif estado == "escuchando":                              # ondas de sonido que siguen tu voz
            for lado in (-1, 1):
                for i in range(3):
                    r = (18 + i * 12) * (0.6 + n)
                    x = cx + lado * 102 * s
                    c.create_arc(x - r, cy - 20 - r, x + r, cy - 20 + r, start=-40 if lado > 0 else 140, extent=80,
                                 style="arc", outline=_hsv(0.12 + i * 0.05, 0.6, 0.6 + 0.4 * n), width=3)
        elif estado == "pensando":                                # burbujitas que suben
            for i in range(3):
                fase = (t * 0.9 + i / 3) % 1.0
                r = 5 + 6 * fase
                x, y = cx + 70 + 10 * i, cy - 80 - 30 * fase
                c.create_oval(x - r, y - r, x + r, y + r, outline=_hsv(0.12 + i * 0.08, 0.6, 1.0), width=2)
        elif estado == "ok":                                      # estrellitas doradas
            for i in range(5):
                ang = t * 2 + i * 2 * math.pi / 5
                x, y = cx + 100 * math.cos(ang), cy - 20 + 76 * math.sin(ang)
                _estrella(c, x, y, 7, _hsv(0.11 + 0.05 * math.sin(i), 0.65, 1.0))
        elif estado == "quieto":
            for i, (dx, dy) in enumerate(((-92, -70), (94, -56), (-96, 20))):
                brillo = 0.5 + 0.5 * math.sin(t * 1.3 + i * 2.1)
                if brillo > 0.35:
                    _estrella(c, cx + dx, cy + dy, 2 + 4 * brillo, _hsv(0.12 + i * 0.03, 0.45, 1.0))

    # ------------------------------------------------------------ diseño con gafas
    def _dibujar_gafas(self, estado, t, n):
        c = self.c
        c.delete("all")
        m = self.TAM / 2
        color = COLOR_ESTADO.get(estado, "#E8C468")
        arcoiris = t / 24.0                                   # los colores dan la vuelta cada 24 s
        piel = _hsv(0.86 + 0.09 * math.sin(t * 0.22), 0.36, 1.0)
        piel_luz = _hsv(0.86 + 0.09 * math.sin(t * 0.22), 0.14, 1.0)
        pliegue = _hsv(0.86 + 0.09 * math.sin(t * 0.22), 0.55, 0.80)
        borde = _hsv(0.80 + 0.06 * math.sin(t * 0.22), 0.70, 0.36)
        animo = getattr(self, "animo", None)
        picado = bool(animo) and animo[0] == "picado" and time.time() < animo[1] and estado in ("hablando", "quieto", "oculto")
        if picado:                                            # se puso caliente: rojo y con la vena hinchada
            piel, piel_luz, pliegue, borde = "#FF8A80", "#FFC9C2", "#E0524A", "#741818"

        # balanceo: tranquilo y lento quieto, atento escuchando, ladeado pensando
        grados = {"escuchando": 0.0, "pensando": 9 + 2 * math.sin(t * 2), "hablando": 3 * math.sin(t * 2.4),
                  "ok": 4 * math.sin(t * 5), "error": 7 * math.sin(t * 7)}.get(estado, 6 * math.sin(t * 0.8))
        salto = {"escuchando": 10 * n, "hablando": 4 * n}.get(estado, 0) + 3 * math.sin(t * 1.6)
        cx, cy = m, m + 8 - salto
        if picado:
            grados = 4 * math.sin(t * 9)
            cx += random.uniform(-1.5, 1.5)
        s = 1.0 + (0.05 * n if estado == "escuchando" else 0)
        th = math.radians(grados)
        co, si = math.cos(th), math.sin(th)

        def P(dx, dy):
            return cx + s * (dx * co - dy * si), cy + s * (dx * si + dy * co)

        def ovalo(dx, dy, rx, ry=None, **kw):
            x, y = P(dx, dy)
            ry = rx if ry is None else ry
            return c.create_oval(x - rx * s, y - ry * s, x + rx * s, y + ry * s, **kw)

        def linea(puntos, **kw):
            return c.create_line(*[v for p in puntos for v in P(*p)], **kw)

        def poligono(puntos, **kw):
            return c.create_polygon(*[v for p in puntos for v in P(*p)], **kw)

        def arco(dx, dy, rx, ry, start, extent, **kw):
            x, y = P(dx, dy)
            return c.create_arc(x - rx * s, y - ry * s, x + rx * s, y + ry * s, start=start - grados, extent=extent, **kw)

        # aura del estado (quieto no tiene)
        for i, a in enumerate((0.28, 0.18) if estado in COLOR_ESTADO else ()):
            r = (90 + i * 10 + 6 * n) * s
            c.create_oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8, outline=_mezclar(color, a + 0.4 * n), width=3)

        # cuerpo: lóbulos (primero el contorno, después el relleno), brillo y pliegues
        lobulos = [(-50, -18, 40), (-20, -42, 42), (20, -42, 42), (50, -18, 40), (-48, 20, 34), (48, 20, 34),
                   (0, 6, 62), (-22, 30, 34), (22, 30, 34)]
        for dx, dy, r in lobulos:
            ovalo(dx, dy, r + 5, fill=borde, outline="")
        for dx, dy, r in lobulos:
            ovalo(dx, dy, r, fill=piel, outline="")
        ovalo(-46, -60, 15, 10, fill=piel_luz, outline="")
        linea([(0, -80), (-4, -62), (3, -48)], smooth=True, fill=pliegue, width=4)
        for dx, dy, rx, ry, ini, ext in ((-55, -50, 18, 15, 20, 140), (-38, -48, 20, 15, 200, 120),
                                         (55, -50, 18, 15, 20, 140), (38, -48, 20, 15, 220, 120),
                                         (-12, -66, 17, 15, 200, 140), (18, -66, 17, 15, 200, 140),
                                         (-70, 20, 14, 17, 90, 160), (70, 20, 14, 17, 290, 160)):
            arco(dx, dy, rx, ry, ini, ext, style="arc", outline=pliegue, width=3)

        # gafas: se las baja cuando te escucha, para mirarte por encima
        obj_y = 15.0 if estado == "escuchando" else (4.0 if estado == "pensando" else 0.0)
        self.gafas_y += (obj_y - self.gafas_y) * 0.25
        gy = self.gafas_y
        lentes = [(-31, 1 + gy, _hsv(arcoiris, 0.30, 1.0)), (31, -2 + gy, _hsv(arcoiris + 0.45, 0.30, 1.0))]
        for lado, (lx, ly, _) in zip((-1, 1), lentes):              # patillas
            linea([(lx + lado * 25, ly - 6), (lado * 82, ly - 16)], fill=MARCO, width=6, capstyle="round")
        for lx, ly, tinte in lentes:                                 # vidrio de color
            ovalo(lx, ly, 26, 24, fill=tinte, outline="")

        # ojos (detrás del vidrio): a media asta quieto, bien abiertos escuchando
        self._mover_mirada(estado, t)
        ahora = time.time()
        if ahora > self.prox_parpadeo + 0.16:                # parpadeo lento cada 3 a 6 segundos
            self.prox_parpadeo = ahora + random.uniform(3.0, 6.0)
        parpadea = estado not in ("ok", "error", "escuchando") and ahora >= self.prox_parpadeo
        obj_p = {"escuchando": 0.0, "pensando": 0.18, "hablando": 0.32}.get(estado, 0.52 + 0.05 * math.sin(t * 0.7))
        if picado:
            obj_p = 0.30
        self.parpado += ((1.0 if parpadea else obj_p) - self.parpado) * (0.6 if parpadea else 0.2)
        abierto = 1.15 if estado == "escuchando" else 1.0
        ojos_y = -2 + (gy * 0.25 if estado == "escuchando" else 0)
        for lado in (-1, 1):
            ox, oy = P(lado * 31, ojos_y)
            rx, ry = 15 * s * abierto, 17 * s * abierto
            if estado == "ok":                                   # ojos felices ^ ^
                c.create_arc(ox - rx, oy - ry * 0.3, ox + rx, oy + ry * 1.3, start=20, extent=140,
                             style="arc", outline=borde, width=5)
                continue
            if estado == "error":                                # ojos en espiral, mareado
                pts = []
                for k in range(34):
                    a = k * 0.55 + t * 8 * lado
                    rr = 1.5 + k * 0.42
                    pts += [ox + rr * s * math.cos(a), oy + rr * s * math.sin(a)]
                c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill=OJO, outline=borde, width=2)
                c.create_line(*pts, fill=borde, width=3, smooth=True)
                continue
            c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill=OJO, outline=borde, width=2)
            # mirada medio perdida: cada pupila mira un poquito para su lado
            bizco = {"pensando": (-0.55 * lado, -0.55)}.get(estado, (0.12 * lado, 0.05 * lado) if estado == "quieto" else (0, 0))
            if picado:
                bizco = (-0.2 * lado - self.mirada[0], 0.1 - self.mirada[1])   # te mira fijo, con bronca
            px = ox + (self.mirada[0] + bizco[0]) * rx * 0.45
            py = oy + (self.mirada[1] + bizco[1]) * ry * 0.45 + (3 if estado == "quieto" else 0)
            rp = (8.5 if estado == "escuchando" else 5.5 if picado else 7) * s
            c.create_oval(px - rp, py - rp, px + rp, py + rp, fill=PUPILA, outline="")
            c.create_oval(px - rp * 0.5 - 2, py - rp * 0.6 - 2, px - rp * 0.5 + 2, py - rp * 0.6 + 2, fill=OJO, outline="")
            f = max(0.0, min(1.0, self.parpado))
            if f > 0.96:                                         # ojo cerrado
                c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill=piel, outline=borde, width=2)
                c.create_line(ox - rx, oy + 2, ox + rx, oy + 2, fill=borde, width=3)
            elif f > 0.02:                                       # párpado caído
                h = max(-0.99, min(0.99, 1 - 2 * f))
                a0 = math.degrees(math.asin(h))
                c.create_arc(ox - rx, oy - ry, ox + rx, oy + ry, start=a0, extent=180 - 2 * a0, style="chord",
                             fill=piel, outline=borde, width=3)

        # marco de las gafas, puente y brillo del vidrio
        for lx, ly, _ in lentes:
            ovalo(lx, ly, 26, 24, outline=MARCO, width=6)
            linea([(lx - 15, ly - 9), (lx - 8, ly - 16)], fill="#FFFFFF", width=3, capstyle="round")
            linea([(lx - 16, ly - 1), (lx - 14, ly - 3)], fill="#FFFFFF", width=3, capstyle="round")
        arco(0, -2 + gy, 9, 7, 20, 140, style="arc", outline=MARCO, width=5)

        # cejas por encima de las gafas: una más alta que la otra (cara de «¿eh?»)
        for lado in (-1, 1):
            alto = -36 - (10 if estado == "escuchando" else 0) - (6 if lado == 1 and estado != "error" else 0)
            if estado == "pensando":
                alto += 4 * lado
            if estado == "hablando":
                alto -= 3 * n
            if picado:                                           # cejas en V, enojado
                linea([(lado * 46, -44), (lado * 16, -31)], fill=borde, width=7, capstyle="round")
                continue
            linea([(lado * 31 - 13, alto + 2), (lado * 31, alto - 3), (lado * 31 + 13, alto + 1)],
                  smooth=True, fill=borde, width=5, capstyle="round")

        # boca con dientes de conejo, corrida un poquito para un costado
        bx, by = 5, 44
        if picado and estado != "hablando":                      # dientes apretados
            poligono([(bx - 17, by - 5), (bx + 17, by - 5), (bx + 17, by + 8), (bx - 17, by + 8)],
                     fill="#FFFDF5", outline=borde, width=3)
            linea([(bx - 17, by + 1), (bx + 17, by + 1)], fill=borde, width=2)
            for k in (-8, 0, 8):
                linea([(bx + k, by - 5), (bx + k, by + 8)], fill=borde, width=2)
        elif estado == "hablando":
            alto = 5 + 20 * n
            ovalo(bx, by + alto / 2 - 4, 17 + 5 * n, alto / 2 + 2, fill=BOCA, outline=borde, width=3)
            if alto > 12:
                ovalo(bx, by + alto - 6, 9, 4, fill=LENGUA, outline="")
            self._dientes(poligono, bx, by - 4, borde)
        elif estado == "ok":
            poligono([(bx - 24, by - 6), (bx + 26, by - 8), (bx + 14, by + 12), (bx, by + 15), (bx - 14, by + 10)],
                     smooth=True, fill=BOCA, outline=borde, width=3)
            self._dientes(poligono, bx, by - 6, borde)
        elif estado == "error":
            linea([(bx - 16, by + 4), (bx - 6, by - 2), (bx + 4, by + 4), (bx + 14, by - 2)], smooth=True,
                  fill=borde, width=4)
        elif estado == "pensando":                               # lengua afuera, concentrado
            linea([(bx - 14, by), (bx + 2, by + 3), (bx + 16, by - 2)], smooth=True, fill=borde, width=4,
                  capstyle="round")
            ovalo(bx + 13, by + 6, 7, 8, fill=LENGUA, outline=borde, width=2)
            linea([(bx + 13, by + 2), (bx + 13, by + 9)], fill=_mezclar(LENGUA, 0.7), width=2)
        else:                                                    # sonrisa floja
            poligono([(bx - 22, by - 5), (bx + 25, by - 9), (bx + 15, by + 6), (bx, by + 9), (bx - 13, by + 4)],
                     smooth=True, fill=BOCA, outline=borde, width=3)
            self._dientes(poligono, bx, by - 6, borde)

        # extras de cada estado, todos de colores
        if picado:                                               # vena de enojo que late (como en los dibujos)
            vx, vy = P(60, -64)
            k = 1.0 + 0.25 * abs(math.sin(t * 6))
            for sx, sy, ini in ((1, 1, 90), (1, -1, 180), (-1, 1, 0), (-1, -1, 270)):
                ax, ay = vx + sx * 8 * k, vy + sy * 8 * k
                c.create_arc(ax - 7 * k, ay - 7 * k, ax + 7 * k, ay + 7 * k, start=ini, extent=90, style="arc",
                             outline="#E8202A", width=4)
        elif estado == "escuchando":                               # ondas de sonido que siguen tu voz
            for lado in (-1, 1):
                for i in range(3):
                    r = (18 + i * 12) * (0.6 + n)
                    x = cx + lado * 100 * s
                    c.create_arc(x - r, cy - r, x + r, cy + r, start=-40 if lado > 0 else 140, extent=80,
                                 style="arc", outline=_hsv(arcoiris + i * 0.18, 0.55, 0.6 + 0.4 * n), width=3)
        elif estado == "pensando":                               # burbujitas que suben
            for i in range(3):
                fase = (t * 0.9 + i / 3) % 1.0
                r = 5 + 6 * fase
                x, y = cx + 62 + 10 * i, cy - 72 - 40 * fase
                c.create_oval(x - r, y - r, x + r, y + r, outline=_hsv(arcoiris + i * 0.3, 0.6, 1.0), width=2)
        elif estado == "ok":                                     # estrellitas de colores
            for i in range(5):
                ang = t * 2 + i * 2 * math.pi / 5
                x, y = cx + 97 * math.cos(ang), cy - 10 + 72 * math.sin(ang)
                _estrella(c, x, y, 7, _hsv(arcoiris + i / 5, 0.6, 1.0))
        elif estado == "quieto":                                 # un par de destellitos tranquilos
            for i, (dx, dy) in enumerate(((-88, -62), (90, -48), (78, 64))):
                brillo = 0.5 + 0.5 * math.sin(t * 1.3 + i * 2.1)
                if brillo > 0.35:
                    _estrella(c, cx + dx, cy + dy, 2 + 4 * brillo, _hsv(arcoiris + i * 0.33, 0.45, 1.0))

    @staticmethod
    def _dientes(poligono, bx, by, borde):
        for x0 in (bx - 7, bx):
            poligono([(x0, by), (x0 + 7, by), (x0 + 7, by + 8), (x0, by + 8)], fill="#FFFDF5", outline=borde, width=2)

    # ------------------------------------------------------------ diseño clásico
    def _dibujar_clasico(self, estado, t, n):
        c = self.c
        c.delete("all")
        m = self.TAM / 2
        color = COLOR_ESTADO.get(estado, "#E8C468")
        # rebote: respira quieto, salta con tu voz, se mece al hablar
        salto = {"escuchando": 10 * n, "hablando": 4 * n}.get(estado, 0) + 3 * math.sin(t * 2.2)
        cx, cy = m, m + 8 - salto
        s = 1.0 + (0.06 * n if estado == "escuchando" else 0)

        # aura del estado (quieto no tiene)
        for i, a in enumerate((0.28, 0.18) if estado in COLOR_ESTADO else ()):
            r = (88 + i * 10 + 6 * n) * s
            c.create_oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8, outline=_mezclar(color, a + 0.4 * n), width=3)

        # cuerpo del cerebro: lóbulos superpuestos (primero el contorno, después el relleno)
        lobulos = [(-50, -18, 40), (-20, -42, 42), (20, -42, 42), (50, -18, 40), (-48, 20, 34), (48, 20, 34),
                   (0, 6, 62), (-22, 30, 34), (22, 30, 34)]
        for dx, dy, r in lobulos:
            r2 = (r + 5) * s
            c.create_oval(cx + dx * s - r2, cy + dy * s - r2, cx + dx * s + r2, cy + dy * s + r2, fill=CONTORNO, outline="")
        for dx, dy, r in lobulos:
            r2 = r * s
            c.create_oval(cx + dx * s - r2, cy + dy * s - r2, cx + dx * s + r2, cy + dy * s + r2, fill=ROSA, outline="")
        # brillo y circunvoluciones
        c.create_oval(cx - 62 * s, cy - 70 * s, cx - 30 * s, cy - 48 * s, fill=ROSA_CLARO, outline="")
        c.create_line(cx, cy - 80 * s, cx - 4 * s, cy - 55 * s, cx + 3 * s, cy - 38 * s, smooth=True, fill=ROSA_OSCURO, width=4)
        for x0, y0, x1, y1, ini, ext in ((-75, -55, -35, -20, 20, 140), (-58, -15, -18, 15, 200, 120),
                                         (35, -55, 75, -20, 20, 140), (18, -15, 58, 15, 220, 120),
                                         (-30, -75, 5, -45, 200, 140), (0, -75, 35, -45, 200, 140),
                                         (-82, 0, -55, 35, 90, 160), (55, 0, 82, 35, 290, 160)):
            c.create_arc(cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s, start=ini, extent=ext,
                         style="arc", outline=ROSA_OSCURO, width=3)

        # ojos
        self._mover_mirada(estado, t)
        ahora = time.time()
        if ahora > self.prox_parpadeo + 0.13:                # parpadea cada 2,5 a 5,5 segundos
            self.prox_parpadeo = ahora + random.uniform(2.5, 5.5)
        cerrado = estado not in ("ok", "error", "escuchando") and ahora >= self.prox_parpadeo
        abierto = 1.25 if estado == "escuchando" else 1.0
        for lado in (-1, 1):
            ox, oy = cx + lado * 30 * s, cy + 2 * s
            rx, ry = 20 * s, 23 * s * abierto
            if estado == "ok":                               # ojos felices ^ ^
                c.create_arc(ox - rx, oy - ry * 0.4, ox + rx, oy + ry * 1.2, start=20, extent=140,
                             style="arc", outline=CONTORNO, width=5)
                continue
            if estado == "error":                            # ojos en cruz
                k = 12 * s
                c.create_line(ox - k, oy - k, ox + k, oy + k, fill=CONTORNO, width=5)
                c.create_line(ox - k, oy + k, ox + k, oy - k, fill=CONTORNO, width=5)
                continue
            if cerrado:
                c.create_line(ox - rx, oy, ox + rx, oy, fill=CONTORNO, width=4)
                continue
            c.create_oval(ox - rx - 3, oy - ry - 3, ox + rx + 3, oy + ry + 3, fill=CONTORNO, outline="")
            c.create_oval(ox - rx, oy - ry, ox + rx, oy + ry, fill=OJO, outline="")
            px, py = ox + self.mirada[0] * rx * 0.5, oy + self.mirada[1] * ry * 0.5
            rp = (9 if estado != "escuchando" else 11) * s
            c.create_oval(px - rp, py - rp, px + rp, py + rp, fill=PUPILA, outline="")
            c.create_oval(px - rp * 0.15 - 4, py - rp * 0.55 - 3, px - rp * 0.15 + 2, py - rp * 0.55 + 3, fill=OJO, outline="")

        # cejas
        for lado in (-1, 1):
            ox, oy = cx + lado * 30 * s, cy - 28 * s * (1.1 if estado == "escuchando" else 1)
            if estado == "pensando":         # fruncidas
                c.create_line(ox - 14 * s * lado * -1, oy - 6, ox + 14 * s * lado * -1, oy + 4, fill=CONTORNO, width=5,
                              capstyle="round")
            elif estado == "error":
                c.create_line(ox - 14 * s, oy + 3, ox + 14 * s, oy - 3 * lado, fill=CONTORNO, width=5, capstyle="round")
            else:
                alza = 8 if estado in ("escuchando", "ok") else 3
                c.create_line(ox - 14 * s, oy, ox, oy - alza, ox + 14 * s, oy, smooth=True, fill=CONTORNO, width=5,
                              capstyle="round")

        # boca
        bx, by = cx, cy + 38 * s
        if estado == "hablando":
            alto = (4 + 22 * n) * s
            ancho = (16 + 6 * n) * s
            c.create_oval(bx - ancho, by - alto / 2, bx + ancho, by + alto / 2, fill=BOCA, outline=CONTORNO, width=3)
            if alto > 10:
                c.create_oval(bx - ancho * 0.55, by, bx + ancho * 0.55, by + alto / 2 - 1, fill=LENGUA, outline="")
        elif estado == "ok":
            c.create_arc(bx - 22 * s, by - 18 * s, bx + 22 * s, by + 14 * s, start=200, extent=140, style="chord",
                         fill=BOCA, outline=CONTORNO, width=3)
        elif estado == "error":
            c.create_line(bx - 16 * s, by + 4, bx - 6 * s, by - 3, bx + 6 * s, by + 4, bx + 16 * s, by - 3,
                          fill=CONTORNO, width=4, smooth=True)
        elif estado == "pensando":
            c.create_line(bx - 8 * s, by + 2, bx + 12 * s, by - 3, fill=CONTORNO, width=4, capstyle="round")
        else:
            c.create_arc(bx - 14 * s, by - 12 * s, bx + 14 * s, by + 8 * s, start=210, extent=120, style="arc",
                         outline=CONTORNO, width=4)

        # extras de cada estado
        if estado == "escuchando":                       # ondas de sonido que siguen tu voz
            for lado in (-1, 1):
                for i in range(3):
                    r = (18 + i * 12) * (0.6 + n)
                    x = cx + lado * 98 * s
                    c.create_arc(x - r, cy - r, x + r, cy + r, start=-40 if lado > 0 else 140, extent=80,
                                 style="arc", outline=_mezclar(color, 0.4 + 0.6 * n), width=3)
        elif estado == "pensando":                       # burbujitas que suben
            for i in range(3):
                fase = (t * 0.9 + i / 3) % 1.0
                r = 5 + 6 * fase
                x, y = cx + 62 + 10 * i, cy - 70 - 40 * fase
                c.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2)
        elif estado == "ok":                             # estrellitas
            for i in range(5):
                ang = t * 2 + i * 2 * math.pi / 5
                x, y = cx + 95 * math.cos(ang), cy - 10 + 70 * math.sin(ang)
                _estrella(c, x, y, 7, color)


def _estrella(c, x, y, r, color):
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts += [x + rr * math.cos(a), y - rr * math.sin(a)]
    c.create_polygon(pts, fill=color, outline="")


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return "#%02x%02x%02x" % tuple(max(4, int(x * 255)) for x in (r, g, b))


def _mezclar(color, factor):
    """Oscurece un color hacia negro (factor 0 = negro, 1 = el color)."""
    factor = max(0.0, min(1.0, factor))
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(2, int(v * factor)) for v in (r, g, b))
