"""Overlays de OBS por voz: «poné un cartel arriba a la derecha que diga raid de Molten Core a las 9».

1. El diseño lo hace Claude (el programa `claude` de tu PC, con tu plan): una página HTML animada con el estilo
   de la guild y fondo transparente. Si Claude no está o tarda demasiado, se usa un cartel propio.
2. Se agrega a la escena de OBS como «Fuente de navegador» y se ubica donde dijiste.
Los overlays que crea El Cerebro llevan 🧠 delante del nombre: solo toca esos.
"""
import html
import json
import re
import shutil
import subprocess
import time
import unicodedata

import config

PREFIJO = "🧠 "
POSICIONES = ["arriba-izquierda", "arriba", "arriba-derecha", "izquierda", "centro", "derecha",
              "abajo-izquierda", "abajo", "abajo-derecha"]
TAMANOS = {"chico": (560, 140), "mediano": (760, 190), "grande": (1100, 260)}
MARGEN = 40

ESTILO = """Estilo de la hermandad The H's (World of Warcraft): dorado #E8C468 y #F5D98B sobre negro y marrón muy oscuro,
tipografía Cinzel (Google Fonts) para títulos e Inter para textos chicos, bordes dorados finos con brillo suave,
aspecto épico y elegante, legible a la distancia. Animaciones sutiles (entrada suave, brillo que recorre el borde);
nada que parpadee rápido."""


class OverlayError(RuntimeError):
    pass


def _slug(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "overlay"


def carpeta():
    c = config.BASE / "overlays"
    c.mkdir(exist_ok=True)
    return c


# ----------------------------------------------------------------- diseño
def _cartel_propio(texto, w, h):
    """Respaldo sin Claude: cartel dorado con entrada suave."""
    t = html.escape(texto)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&display=swap" rel="stylesheet">
<style>
html,body{{margin:0;width:{w}px;height:{h}px;background:transparent;overflow:hidden}}
.c{{box-sizing:border-box;position:absolute;inset:8px;display:flex;align-items:center;justify-content:center;
padding:0 32px;border:3px solid #E8C468;border-radius:18px;background:linear-gradient(180deg,rgba(20,14,8,.92),rgba(8,6,4,.92));
box-shadow:0 0 24px rgba(232,196,104,.45),inset 0 0 18px rgba(232,196,104,.15);animation:in 1s ease-out both}}
.t{{font-family:Cinzel,Georgia,serif;font-weight:900;color:#F5D98B;font-size:{max(22, int(h * 0.26))}px;text-align:center;
line-height:1.1;text-shadow:0 2px 0 #000,0 0 14px rgba(232,196,104,.6)}}
.c:after{{content:"";position:absolute;inset:-3px;border-radius:18px;background:linear-gradient(110deg,transparent 40%,
rgba(255,240,190,.55) 50%,transparent 60%) 0 0/250% 100%;mix-blend-mode:screen;animation:luz 4s linear infinite;pointer-events:none}}
@keyframes in{{from{{opacity:0;transform:translateY(12px) scale(.97)}}to{{opacity:1;transform:none}}}}
@keyframes luz{{from{{background-position:150% 0}}to{{background-position:-150% 0}}}}
</style></head><body><div class="c"><div class="t">{t}</div></div></body></html>"""


def buscar_claude():
    """El programa claude (Claude Code): CLAUDE_EXE, el PATH, la instalación aparte o el de la app de escritorio."""
    import glob
    import os
    if config.CLAUDE_EXE and os.path.exists(config.CLAUDE_EXE):
        return config.CLAUDE_EXE
    encontrado = shutil.which("claude") or shutil.which("claude.exe") or shutil.which("claude.cmd")
    if encontrado:
        return encontrado
    for ruta in (os.path.expanduser(r"~\.local\bin\claude.exe"), os.path.expandvars(r"%APPDATA%\npm\claude.cmd")):
        if os.path.exists(ruta):
            return ruta
    # La app de escritorio de Claude trae su propio claude.exe en una carpeta con la versión: se usa el más nuevo
    base = os.path.expandvars(r"%LOCALAPPDATA%\Claude-Data")
    candidatos = glob.glob(os.path.join(base, "*", "claude-code", "*", "*", "claude.exe")) + \
        glob.glob(os.path.join(base, "*", "claude-code", "*", "claude.exe"))
    return max(candidatos, key=os.path.getmtime) if candidatos else None


SIN_HERRAMIENTAS = ["Bash", "PowerShell", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
                    "WebFetch", "WebSearch", "Task", "Agent"]
SOLO_ESTO = ["--strict-mcp-config"]      # sin conectores (Notion, Drive…): cada Claude usa solo lo que se le da


def pedir_a_claude(pedido, carpeta_trabajo, mirar=False):
    """Le pasa el pedido a Claude (por la entrada, así no se rompen las comillas) y devuelve el HTML que responde.

    mirar=True: puede ABRIR (solo leer) las imágenes de su carpeta de trabajo, p. ej. tus miniaturas de ejemplo.
    Nunca tiene internet, ni escribe, ni corre programas.
    """
    r, salida = _correr_claude(pedido, carpeta_trabajo, mirar)
    m = re.search(r"<!doctype html.*?</html>|<html.*?</html>", salida, re.S | re.I)
    if r.returncode != 0 or not m:
        raise RuntimeError(f"Claude no devolvió HTML ({r.returncode}): {(r.stderr or r.stdout or '')[:200]}")
    return m.group(0)


def preguntar_a_claude(pedido, carpeta_trabajo):
    """Como pedir_a_claude, sin herramientas, pero devuelve el texto tal cual (p. ej. un JSON)."""
    r, salida = _correr_claude(pedido, carpeta_trabajo, False)
    if r.returncode != 0 or not salida.strip():
        raise RuntimeError(f"Claude no respondió ({r.returncode}): {(r.stderr or '')[:200]}")
    return salida


def _correr_claude(pedido, carpeta_trabajo, mirar=False):
    exe = buscar_claude()
    if not exe:
        raise RuntimeError("no está el programa claude en esta PC")
    comando = [exe, "-p"] + SOLO_ESTO + (["--model", config.CLAUDE_MODELO] if config.CLAUDE_MODELO else [])
    if mirar:
        comando += ["--max-turns", "12", "--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h != "Read"]
        comando += ["--allowedTools", "Read(./**)"]               # solo su carpeta
    else:
        comando += ["--disallowedTools"] + SIN_HERRAMIENTAS      # el diseñador no toca internet ni archivos
        pedido += "\nRespondé directo, sin usar herramientas ni abrir archivos: acá tenés todo lo que necesitás."
    comando += ["--output-format", "json"]                  # para saber cuánto tardó y si abrió los ejemplos
    t0 = time.time()
    r = subprocess.run(comando, input=pedido, capture_output=True, text=True, encoding="utf-8",
                       timeout=config.OVERLAY_ESPERA, cwd=str(carpeta_trabajo))
    salida = r.stdout or ""
    try:
        datos = json.loads(salida)
        salida = str(datos.get("result") or "")
        print(f"[diseño] {config.CLAUDE_MODELO}: {time.time() - t0:.0f} s, {datos.get('num_turns')} turnos"
              + (" (miró los ejemplos)" if mirar and (datos.get("num_turns") or 1) > 1 else ""))
    except (ValueError, AttributeError):
        pass
    return r, salida


def disenar(descripcion, w, h):
    """Devuelve (html, quien): lo diseña Claude y, si no se puede, el cartel propio."""
    if config.OVERLAY_CLAUDE:
        pedido = f"""Diseñá un overlay para OBS (Fuente de navegador) de {w}x{h} píxeles.
Lo que tiene que mostrar: {descripcion}
{ESTILO}
Reglas:
- Un solo archivo HTML completo, con el CSS y el JS adentro. Fondo transparente (html y body con background: transparent).
- Ocupa exactamente {w}x{h} px, sin barras de desplazamiento.
- Usá EXACTAMENTE los textos y datos que te pido; no inventes fechas, horas, enlaces ni datos.
- Solo se puede cargar la fuente de Google Fonts; nada más de internet.
- Si es una cuenta regresiva, que llegue a 0 y se quede en 0.
Respondé solo con el HTML, sin explicaciones."""
        try:
            return pedir_a_claude(pedido, carpeta()), "Claude"
        except subprocess.TimeoutExpired:
            print("[overlay] Claude tardó demasiado; uso el cartel propio.")
        except Exception as e:  # noqa: BLE001
            print(f"[overlay] No pude usar Claude ({e}); uso el cartel propio.")
    return _cartel_propio(_texto_corto(descripcion), w, h), "plantilla"


def _texto_corto(descripcion):
    """Para el cartel propio: lo que va entre comillas o después de «que diga»."""
    m = re.search(r"[«\"“]([^»\"”]+)[»\"”]", descripcion) or re.search(r"(?:que diga|diciendo|con el texto)\s*:?\s*(.+)$",
                                                                       descripcion, re.I)
    return (m.group(1) if m else descripcion).strip()[:90]


# ----------------------------------------------------------------- OBS
def _obs():
    import obsws_python as obs
    try:
        return obs.ReqClient(host=config.OBS_HOST, port=config.OBS_PORT, password=config.OBS_PASSWORD, timeout=5)
    except Exception as e:  # noqa: BLE001
        raise OverlayError(f"No pude conectar con OBS ({e}). ¿Está abierto?")


def _escena(cl, escena=None):
    if escena:
        nombres = [s["sceneName"] for s in cl.get_scene_list().scenes]
        for n in nombres:
            if _slug(n) == _slug(escena):
                return n
        raise OverlayError(f"No hay ninguna escena «{escena}» en OBS. Tenés: {', '.join(nombres)}.")
    return cl.get_current_program_scene().current_program_scene_name


def _lugar(cl, posicion, w, h):
    v = cl.get_video_settings()
    W, H = v.base_width, v.base_height
    fila, col = "centro", "centro"
    if posicion.startswith("arriba"):
        fila = "arriba"
    elif posicion.startswith("abajo"):
        fila = "abajo"
    if posicion.endswith("izquierda"):
        col = "izquierda"
    elif posicion.endswith("derecha"):
        col = "derecha"
    x = {"izquierda": MARGEN, "centro": (W - w) // 2, "derecha": W - w - MARGEN}[col]
    y = {"arriba": MARGEN, "centro": (H - h) // 2, "abajo": H - h - MARGEN}[fila]
    return max(0, x), max(0, y)


def _ubicar(cl, escena, nombre, posicion, w, h):
    item = cl.get_scene_item_id(escena, nombre).scene_item_id
    x, y = _lugar(cl, posicion, w, h)
    cl.set_scene_item_transform(escena, item, {"positionX": x, "positionY": y, "alignment": 5,
                                               "scaleX": 1.0, "scaleY": 1.0, "rotation": 0.0})
    return item


def nombre_obs(nombre):
    return PREFIJO + str(nombre).strip()[:40]


def crear(nombre, descripcion, posicion="arriba-derecha", tamano="mediano", escena=None):
    w, h = TAMANOS.get(tamano, TAMANOS["mediano"])
    cl = _obs()
    esc = _escena(cl, escena)
    pagina, quien = disenar(descripcion, w, h)
    archivo = carpeta() / f"{_slug(nombre)}.html"
    archivo.write_text(pagina, encoding="utf-8")
    fuente = nombre_obs(nombre)
    ajustes = {"is_local_file": True, "local_file": str(archivo), "width": w, "height": h,
               "reroute_audio": False, "shutdown": False, "restart_when_active": True}
    existentes = {i["inputName"] for i in cl.get_input_list().inputs}
    if fuente in existentes:            # ya estaba: se actualiza y se vuelve a ubicar
        cl.set_input_settings(fuente, ajustes, True)
        try:
            cl.get_scene_item_id(esc, fuente)
        except Exception:  # noqa: BLE001
            cl.create_scene_item(esc, fuente, True)
        cl.press_input_properties_button(fuente, "refreshnocache")
    else:
        cl.create_input(esc, fuente, "browser_source", ajustes, True)
    _ubicar(cl, esc, fuente, posicion, w, h)
    return {"fuente": fuente, "escena": esc, "archivo": str(archivo), "quien": quien}


def _buscar(cl, nombre):
    """El overlay de El Cerebro cuyo nombre más se parece."""
    import difflib
    nuestros = [i["inputName"] for i in cl.get_input_list().inputs if i["inputName"].startswith(PREFIJO)]
    if not nuestros:
        raise OverlayError("No hay carteles que haya puesto yo. Si hablás de los tuyos, decime «mi overlay vertical» o «mi overlay horizontal».")
    claves = {_slug(n[len(PREFIJO):]): n for n in nuestros}
    k = _slug(nombre)
    if k in claves:
        return claves[k]
    for kk, n in claves.items():
        if k and (k in kk or kk in k):
            return n
    m = difflib.get_close_matches(k, list(claves), n=1, cutoff=0.5)
    if not m:
        raise OverlayError(f"No encontré el overlay «{nombre}». Tengo: {', '.join(n[len(PREFIJO):] for n in nuestros)}.")
    return claves[m[0]]


def lista():
    cl = _obs()
    return [i["inputName"][len(PREFIJO):] for i in cl.get_input_list().inputs if i["inputName"].startswith(PREFIJO)]


def mover(nombre, posicion, escena=None):
    cl = _obs()
    fuente = _buscar(cl, nombre)
    esc = _escena(cl, escena)
    s = cl.get_input_settings(fuente).input_settings
    _ubicar(cl, esc, fuente, posicion, int(s.get("width", 760)), int(s.get("height", 190)))
    return fuente


def mostrar(nombre, visible=True, escena=None):
    cl = _obs()
    fuente = _buscar(cl, nombre)
    esc = _escena(cl, escena)
    cl.set_scene_item_enabled(esc, cl.get_scene_item_id(esc, fuente).scene_item_id, bool(visible))
    return fuente


def quitar(nombre):
    """Lo saca de OBS (el diseño queda guardado en la carpeta overlays)."""
    cl = _obs()
    fuente = _buscar(cl, nombre)
    cl.remove_input(fuente)
    return fuente
