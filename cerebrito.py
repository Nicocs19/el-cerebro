"""El asistente en pantalla: Hogger el H (un gnoll de dibujito) o el cerebro de antes, que reaccionan a lo que pasa.

Diseño «hogger» (CEREBRO_DISENO, el de siempre ahora): ver Cerebrito._dibujar_hogger.

Diseño «gafas» (el de antes): un cerebro relajado y medio bobo, con gafas redondas de colores,
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
        """Hogger el H: un gnoll de dibujito, jefe de la manada de The H's (diseño propio, no el modelo del juego).

        Como la foto de referencia: hiena gris parda con manchas negras, cresta a rayas, vincha con pinchos en la
        frente, sonrisa llena de dientes, hombrera dorada grande de un lado y una de hierro con anillos del otro,
        el hacha a tu izquierda y la maza asomando abajo a la derecha. La H de la hermandad va en el pecho.
        Las orejas se paran cuando te escucha y se caen si algo salió mal.
        """
        c = self.c
        c.delete("all")
        m = self.TAM / 2
        color = COLOR_ESTADO.get(estado, "#E8C468")
        animo = getattr(self, "animo", None)
        picado = bool(animo) and animo[0] == "picado" and time.time() < animo[1] and estado in ("hablando", "quieto", "oculto")
        pelo, pelo_luz, mancha, borde = "#B49C72", "#D2BE93", "#2B2016", "#24170C"
        if picado:                                            # se calentó: pelo rojizo
            pelo, pelo_luz, mancha = "#D06A48", "#EE9C78", "#5E1A10"
        hocico, nariz, boca = "#5A544E", "#120E0C", "#5B1020"
        oro, oro_luz, hierro, hierro_luz = "#D2A848", "#F3DE9E", "#4A4A53", "#6F7080"
        metal, plata, madera, cuero, tela = "#C3C9D1", "#E2E5EA", "#7A4E2A", "#2E2422", "#8A2222"

        grados = {"escuchando": 0.0, "pensando": 5 + 1.5 * math.sin(t * 2), "hablando": 2.5 * math.sin(t * 2.4),
                  "ok": 4 * math.sin(t * 5), "error": 5 * math.sin(t * 7)}.get(estado, 3 * math.sin(t * 0.8))
        salto = {"escuchando": 7 * n, "hablando": 4 * n}.get(estado, 0) + 2 * math.sin(t * 1.6)
        cx, cy = m, m + 5 - salto
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

        def pinchos(x0, y0, r, n_, largo, fill):              # pinchos alrededor de una bola (la maza)
            for k in range(n_):
                a = k * 2 * math.pi / n_ + 0.3
                base = [(x0 + r * math.cos(a + d), y0 + r * math.sin(a + d)) for d in (-0.32, 0.32)]
                poligono(base + [(x0 + (r + largo) * math.cos(a), y0 + (r + largo) * math.sin(a))], fill=fill,
                         outline=borde, width=2)

        # aura del estado (quieto no tiene)
        for i, a in enumerate((0.28, 0.18) if estado in COLOR_ESTADO else ()):
            r = (94 + i * 10 + 6 * n) * s
            c.create_oval(cx - r, cy - r * 0.85, cx + r, cy + r * 0.85, outline=_mezclar(color, a + 0.4 * n), width=3)

        esc[0] = s * 0.88
        # --- el hacha (a tu izquierda): mango de madera y hoja de metal con filo brillante
        abajo, arriba = (-66, 126), (-98, -8)
        linea([abajo, arriba], fill=borde, width=9, capstyle="round")
        linea([abajo, arriba], fill=madera, width=5, capstyle="round")
        for k in (0.62, 0.72):                                # tiras de cuero en el mango
            x, y = abajo[0] + (arriba[0] - abajo[0]) * k, abajo[1] + (arriba[1] - abajo[1]) * k
            linea([(x - 5, y - 2), (x + 5, y + 2)], fill=cuero, width=3)
        hoja = [(-99, -14), (-108, -22), (-120, -16), (-124, 2), (-118, 20), (-106, 26), (-92, 20)]
        poligono(hoja, fill=metal, outline=borde, width=3, joinstyle="round")
        linea([(-111, -19), (-121, -9), (-122, 4), (-116, 18), (-107, 23)], smooth=True, fill=plata, width=3)
        ovalo(-97, 4, 3, fill=cuero, outline="")

        # --- la maza (abajo a la derecha): mango y bola con pinchos
        linea([(70, 66), (90, 88)], fill=borde, width=9)
        linea([(70, 66), (90, 88)], fill=madera, width=5)
        pinchos(92, 92, 11, 7, 6, plata)
        ovalo(92, 92, 12, fill="#8E949E", outline=borde, width=3)
        ovalo(88, 87, 4.5, 3, fill=plata, outline="")

        # --- pecho de armadura oscura con trapo rojo, y la H de la hermandad
        poligono([(-44, 48), (44, 48), (58, 110), (-58, 110)], fill="#3A3230", outline=borde, width=3)
        poligono([(-54, 98), (54, 98), (58, 110), (-58, 110)], fill=tela, outline=borde, width=2)
        for x in (-26, 26):
            ovalo(x, 64, 3, fill=plata, outline="")
        ovalo(0, 80, 16, fill="#E8C468", outline="#6B4A12", width=3)
        ovalo(-5, 74, 5, 3, fill="#F8E7AE", outline="")
        mx, my = P(0, 80.5)
        c.create_text(mx, my, text="H", fill="#5A1A1A", font=("Georgia", max(8, int(13 * s)), "bold"), angle=-grados)

        # --- hombreras de metal (cúpula con borde y remaches, no de pan): de hierro con anillos a tu izquierda
        #     y la dorada grande a tu derecha, como en la foto
        def hombrera(x0, y0, rx, ry, fill, luz, anillos):
            arco = [(x0 + rx * math.cos(math.radians(a)), y0 + ry * math.sin(math.radians(a))) for a in range(180, 361, 10)]
            panza = [(x0 + rx * math.cos(math.radians(a)), y0 + 9 * math.sin(math.radians(a))) for a in range(15, 166, 15)]
            poligono(arco + panza, fill=fill, outline=borde, width=3)
            brillo = [(x0 + rx * 0.72 * math.cos(math.radians(a)), y0 - 4 + ry * 0.72 * math.sin(math.radians(a)))
                      for a in range(200, 271, 10)]
            linea(brillo, fill=luz, width=5, capstyle="round")
            abajo_ = [(x0 + (rx + 2) * math.cos(math.radians(a)), y0 + 17 * math.sin(math.radians(a)))
                      for a in range(0, 181, 15)]
            poligono(panza[::-1] + [(x0 - rx, y0)] + abajo_[::-1] + [(x0 + rx + 2, y0)], fill="#26221F", outline=borde,
                     width=2)
            for a in (25, 60, 90, 120, 155):
                x, y = x0 + (rx - 2) * math.cos(math.radians(a)), y0 + 13 * math.sin(math.radians(a))
                if anillos:
                    ovalo(x, y, 4, fill="", outline=plata, width=2)
                else:
                    ovalo(x, y, 2.6, fill=plata, outline="")

        hombrera(-66, 74, 32, 30, hierro, hierro_luz, True)
        ovalo(-74, 98, 10, 9, fill="#5A3B26", outline=borde, width=3)   # el puño que agarra el hacha
        for k in (-3, 1, 5):
            linea([(-81, 94 + k), (-69, 96 + k)], fill=borde, width=1)
        hombrera(66, 70, 42, 40, oro, oro_luz, False)
        ovalo(48, 44, 5, 3, fill="#FFFAEA", outline="")
        esc[0] = s

        # --- collar de cuero con remaches
        poligono([(-40, 34), (40, 34), (44, 50), (-44, 50)], fill=cuero, outline="#120C0A", width=3)
        for x in (-28, -10, 10, 28):
            ovalo(x, 42, 2.6, fill=plata, outline="")

        # --- orejas de gnoll, puntiagudas y hacia afuera: se paran cuando te escucha, se caen si algo salió mal
        tic = 6 * max(0.0, math.sin(t * 2.7)) ** 12
        punta = {"escuchando": (-66, -92), "error": (-88, -46), "pensando": (-78, -72),
                 "ok": (-72, -84)}.get(estado, (-77 - tic, -78 + tic))
        for lado in (-1, 1):
            px_, py_ = punta
            if estado == "pensando" and lado == 1:
                px_, py_ = -66, -90                        # una oreja más parada que la otra
            ext = [(-47, -34), (px_ * 0.6 - 24, py_ * 0.6 - 12), (px_, py_), (-26, -60)]
            inn = [(-44, -40), (px_ * 0.85 - 5, py_ * 0.85 - 4), (-31, -57)]
            poligono(ext if lado < 0 else espejo(ext), fill="#3E2C1C", outline=borde, width=3, joinstyle="round")
            poligono(inn if lado < 0 else espejo(inn), fill="#8E5E50", outline="", joinstyle="round")

        # --- cresta: mohicano de pelo parado con puntas, a rayas blancas y negras como la foto, que se mece
        v = 3 * math.sin(t * 1.9)
        sube = 4 if estado == "escuchando" else 0
        forma = [(-12, -56), (-16, -72), (-23, -86), (-15, -85), (-18, -100), (-8, -93), (-4, -110), (1, -98),
                 (8, -108), (10, -93), (19, -99), (15, -84), (22, -85), (15, -71), (12, -56)]
        cresta = [(x * 1.35 + v * (-56 - y) / 50, y - sube * (-56 - y) / 50) for x, y in forma]
        poligono(cresta, fill="#E6E2DA", outline="")
        for y0 in (-70, -81, -92, -103):                  # rayas negras finitas: pelo de cebra
            franja = _recortar(_recortar(cresta, y0 - 4.5, True), y0, False)
            if len(franja) >= 3:
                poligono(franja, fill="#2A2522", outline="")
        poligono(cresta, fill="", outline=borde, width=3, joinstyle="round")

        # --- cabeza: hiena gris parda con manchas negras y mechones en los cachetes
        for lado in (-1, 1):
            mechon = [(-44, -26), (-62, -14), (-49, -8), (-60, 4), (-44, 6), (-50, 16), (-34, 14)]
            poligono(mechon if lado < 0 else espejo(mechon), fill=pelo, outline=borde, width=3)
        ovalo(0, -15, 50, 50, fill=pelo, outline=borde, width=3)
        ovalo(-22, -56, 12, 4, fill=pelo_luz, outline="")
        for dx, dy, rx_, ry_ in ((-44, -14, 4, 4), (44, -12, 4.5, 4), (-38, 4, 3.5, 3.5), (38, 6, 4, 3), (-34, -4, 2.5, 2.5),
                                 (33, -4, 2.5, 2.5), (-44, 14, 3, 3), (44, 16, 3, 2.5), (-8, -63, 3, 2), (10, -62, 3, 2)):
            ovalo(dx, dy, rx_, ry_, fill=mancha, outline="")

        # --- vincha de cuero en la frente con pinchos de hueso
        def arriba_(x):
            return -62 + 22 * (x / 50) ** 2

        def abajo_(x):
            return -52 + 22 * (x / 48) ** 2
        xs = [-48 + 8 * k for k in range(13)]
        poligono([(x, arriba_(x)) for x in xs] + [(x, abajo_(x) + 1) for x in reversed(xs)], fill="#3B2C24",
                 outline="#120C0A", width=2)
        for x in (-40, -20, 0, 20, 40):
            y = (arriba_(x) + abajo_(x)) / 2 + 1
            largo = 24 if abs(x) == 40 else 17
            dx, dy = x, y + 15                               # apuntan hacia afuera de la cabeza
            d = math.hypot(dx, dy) or 1
            ux, uy = dx / d, dy / d
            base = [(x - uy * 7, y + ux * 7), (x + uy * 7, y - ux * 7)]
            poligono(base + [(x + ux * largo, y + uy * largo)], fill="#D9B465", outline=borde, width=2)
            ovalo(x, y, 2.6, fill=plata, outline="")

        # --- ojos ámbar con pupila de fiera
        self._mover_mirada(estado, t)
        ahora = time.time()
        if ahora > self.prox_parpadeo + 0.14:
            self.prox_parpadeo = ahora + random.uniform(2.5, 5.5)
        parpadea = estado not in ("ok", "error", "escuchando") and ahora >= self.prox_parpadeo
        for lado in (-1, 1):
            ox, oy = P(lado * 21, -20)
            grande = 1.2 if estado == "escuchando" else 1.0
            rx, ry = 10.5 * s * grande, 8 * s * grande
            if estado == "ok":                                   # ojos felices ^ ^
                c.create_arc(ox - rx, oy - ry * 0.4, ox + rx, oy + ry * 1.4, start=20, extent=140,
                             style="arc", outline=borde, width=4)
                continue
            if estado == "error":                                # ojos en espiral, mareado
                pts = []
                for k in range(26):
                    a = k * 0.6 + t * 8 * lado
                    rr = 1.2 + k * 0.34
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
                c.create_oval(px - 2.6 * s, py - 6.2 * s, px + 2.6 * s, py + 6.2 * s, fill=PUPILA, outline="")
            c.create_oval(px - 4, py - 5, px - 1, py - 2, fill="#FFFFFF", outline="")

        # --- cejas de fiera (debajo de la vincha)
        for lado in (-1, 1):
            if picado:
                linea([(lado * 34, -38), (lado * 9, -27)], fill="#2A170A", width=7, capstyle="round")
                continue
            alto = -32 - (5 if estado == "escuchando" else 0) - (2 * n if estado == "hablando" else 0)
            if estado == "pensando":
                alto += -4 if lado == 1 else 2
            caida = 3 if estado != "error" else -3
            linea([(lado * 32, alto - caida), (lado * 10, alto + caida)], fill="#2E1C0E", width=6, capstyle="round")

        # --- hocico gris, nariz y la sonrisa llena de dientes
        ovalo(0, 14, 31, 22, fill=hocico, outline=borde, width=3)
        ovalo(0, -2, 13, 12, fill=hocico, outline="")
        ovalo(0, 3, 11, 7, fill=nariz, outline="")
        ovalo(-4, 0, 3, 1.8, fill="#8F8F8F", outline="")
        by = 21
        diente = "#FFFDF2"
        if estado == "hablando":
            alto = 6 + 22 * n
            ovalo(0, by + alto / 2, 20 + 4 * n, alto / 2 + 2, fill=boca, outline=borde, width=3)
            if alto > 14:
                ovalo(0, by + alto - 3, 9, 4, fill="#E0607A", outline="")
            for x in (-13, -6.5, 0, 6.5, 13):
                poligono([(x - 3.2, by), (x + 3.2, by), (x, by + 6)], fill=diente, outline="")
            for x in (-10, 10):
                poligono([(x - 3, by + alto + 2), (x + 3, by + alto + 2), (x, by + alto - 5)], fill=diente, outline="")
        elif picado:                                              # gruñido: dientes apretados
            poligono([(-20, by - 2), (20, by - 2), (18, by + 10), (-18, by + 10)], fill=diente, outline=borde, width=2)
            linea([(-19, by + 4), (19, by + 4)], fill=borde, width=2)
            for x in (-12, -4, 4, 12):
                linea([(x, by - 2), (x, by + 10)], fill=borde, width=2)
        elif estado == "error":
            linea([(-16, by + 4), (-6, by - 1), (4, by + 4), (14, by - 1)], smooth=True, fill=diente, width=3)
        elif estado == "pensando":                                # boca de costado, un colmillo afuera
            linea([(-14, by + 2), (4, by + 4), (18, by - 2)], smooth=True, fill=diente, width=3, capstyle="round")
            poligono([(9, by + 2), (15, by + 1), (12, by + 9)], fill=diente, outline="")
        else:                                                     # sonrisa ancha llena de dientes (como la foto)
            grande = 3 if estado == "ok" else 0
            poligono([(-25, by - 4), (25, by - 4), (16, by + 9 + grande), (0, by + 12 + grande), (-16, by + 9 + grande)],
                     smooth=True, fill=boca, outline=borde, width=2)
            for x in (-17, -11, -5.5, 0, 5.5, 11, 17):            # fila de arriba
                largo = 7 if abs(x) == 17 else 4.5
                poligono([(x - 3, by - 3), (x + 3, by - 3), (x, by - 3 + largo)], fill=diente, outline="")
            for x in (-9, -3, 3, 9):                              # fila de abajo
                poligono([(x - 2.6, by + 9 + grande), (x + 2.6, by + 9 + grande), (x, by + 4 + grande)], fill=diente,
                         outline="")

        # --- extras de cada estado (por fuera de las orejas, el hacha y la maza)
        if picado:                                                # vapor de enojo
            for i in range(3):
                fase = (t * 1.4 + i / 3) % 1.0
                for lado in (-1, 1):
                    x, y = P(lado * (80 + 12 * fase), -44 - 40 * fase)
                    r = 4 + 6 * fase
                    c.create_oval(x - r, y - r, x + r, y + r, outline=_mezclar("#FFFFFF", 0.9 - 0.6 * fase), width=2)
        elif estado == "escuchando":                              # ondas de sonido que siguen tu voz
            for lado in (-1, 1):
                for i in range(3):
                    r = (8 + i * 10) * (0.7 + 0.5 * n)
                    x = cx + lado * 80 * s
                    c.create_arc(x - r, cy - 58 - r, x + r, cy - 58 + r, start=-40 if lado > 0 else 140, extent=80,
                                 style="arc", outline=_hsv(0.12 + i * 0.05, 0.6, 0.6 + 0.4 * n), width=3)
        elif estado == "pensando":                                # burbujitas que suben
            for i in range(3):
                fase = (t * 0.9 + i / 3) % 1.0
                r = 4 + 6 * fase
                x, y = cx + 82 + 7 * i, cy - 40 - 52 * fase
                c.create_oval(x - r, y - r, x + r, y + r, outline=_hsv(0.12 + i * 0.08, 0.6, 1.0), width=2)
        elif estado == "ok":                                      # estrellitas doradas que titilan a los costados
            for i, (dx, dy) in enumerate(((-98, -72), (98, -66), (-104, -42), (102, -24), (-80, -102), (80, -102))):
                brillo = 0.5 + 0.5 * math.sin(t * 6 + i * 1.7)
                _estrella(c, cx + dx, cy + dy, 4 + 4 * brillo, _hsv(0.11 + 0.05 * math.sin(i), 0.65, 1.0))
        elif estado == "quieto":
            for i, (dx, dy) in enumerate(((-96, -70), (96, -60), (100, -14))):
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


def _recortar(puntos, y0, debajo):
    """Recorta un polígono con una línea horizontal: se queda con lo que está debajo (y >= y0) o arriba."""
    dentro = (lambda p: p[1] >= y0) if debajo else (lambda p: p[1] <= y0)
    salida = []
    for i, p in enumerate(puntos):
        q = puntos[i - 1]
        if dentro(p):
            if not dentro(q):
                salida.append((q[0] + (p[0] - q[0]) * (y0 - q[1]) / (p[1] - q[1]), y0))
            salida.append(p)
        elif dentro(q):
            salida.append((q[0] + (p[0] - q[0]) * (y0 - q[1]) / (p[1] - q[1]), y0))
    return salida


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
