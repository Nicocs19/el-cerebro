"""Los overlays que Nicolas YA TIENE en OBS (los suyos, no los 🧠 de Hogger), en el lienzo horizontal y en el vertical.

- ver(): qué overlays tiene en cada lienzo y escena, con su tamaño, de dónde salen y dónde está la cámara.
- preparar_cambio(): Claude (sin herramientas ni internet) propone cambios MÍNIMOS al archivo HTML del overlay
  («sacá lo de beta»). Se prueban sobre una copia y queda esperando «dale»: en OBS todavía no cambia nada.
- preparar_nuevo(): diseña uno nuevo (🧠) del mismo tamaño y en el mismo lugar que uno tuyo, con la cámara libre.
- aplicar(): con el «dale». Guarda una copia del original en <carpeta del overlay>/_copias, escribe el cambio y
  recarga solo esa fuente. Un overlay nuevo se agrega en la misma escena (el tuyo se oculta solo si dijiste «en vez de»).
- volver(): deshace el último cambio (vuelve la copia, o saca el nuevo y muestra el tuyo).

Seguridad:
- La contraseña de OBS (tus overlays la tienen escrita para el nivel) y cualquier token se tapan antes de pasarle el
  archivo a Claude, y un cambio que los toque se rechaza.
- El archivo se edita por bytes: lo que no se cambia queda idéntico (aunque tenga caracteres raros).
- Nunca se borra nada; las fuentes de internet (chat de Kick, Social Stream) no se editan.

En OBS (32 o más nuevo) cada lienzo tiene sus escenas: las escenas se piden con su lienzo (canvasUuid o sceneUuid) y
las fuentes son de todos.
"""
import base64
import datetime as dt
import difflib
import hashlib
import json
import re
import shutil
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import config
import overlays

CAMARAS = ("dshow_input", "av_capture_input", "v4l2_input", "macos_avcapture", "av_capture_input_v2")
NAVEGADOR = "browser_source"
TEXTOS = ("text_gdiplus", "text_gdiplus_v2", "text_gdiplus_v3", "text_ft2_source", "text_ft2_source_v2")
IMAGENES = ("image_source",)
VERTICAL = re.compile(r"\bvertical|\btiktok|\bcelular|\bmovil|\bshorts|\breels")
HORIZONTAL = re.compile(r"\bhorizontal|\bprincipal|\bpantalla grande|\byoutube\b|\bkick\b")
NO_CUENTAN = {"el", "la", "los", "las", "de", "del", "mi", "mis", "que", "en", "un", "una", "overlay", "overlays",
              "lienzo", "fuente", "escena", "tengo", "ya", "ese", "este", "al", "con", "y", "o", "lo", "le", "para"}
SINONIMOS = {"chatting": "just chatting", "tiktok": "ttiktok tiktok", "nivel": "nivel level", "horizontal": "horizontal"}
SECRETO = re.compile(r"""(\w*(?:pass(?:word)?|passwd|token|secret|api[_-]?key|apikey|clave|auth)\w*)(["']?\s*[:=]\s*)"""
                     r"""(["'`])([^"'`\r\n]{4,})(\3)""", re.I)
SECRETO_URL = re.compile(r"([?&](?:token|key|auth|access_token|apikey|api_key|password|pass)=)([^&\"'\s<>]{6,})", re.I)
OCULTO = re.compile(r"__OCULTO_\d+__")


class Error(RuntimeError):
    pass


# ----------------------------------------------------------------- OBS: lienzos, escenas y fuentes
def _pedir(cl, tipo, **datos):
    return cl.send(tipo, datos or None, raw=True) or {}


def _primero(cl, tipo, intentos):
    """Prueba la misma petición con distintas formas de nombrar la escena (uuid, o nombre + lienzo)."""
    ultimo = None
    for d in intentos:
        try:
            return _pedir(cl, tipo, **d)
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise ultimo or Error(f"OBS no respondió {tipo}")


def _tamano(d):
    """Busca baseWidth/baseHeight (o width/height) en lo que devuelve GetCanvasList, esté donde esté."""
    if not isinstance(d, dict):
        return 0, 0
    for a, b in (("baseWidth", "baseHeight"), ("canvasWidth", "canvasHeight"), ("width", "height")):
        if d.get(a) and d.get(b):
            return int(d[a]), int(d[b])
    for v in d.values():
        if isinstance(v, dict):
            w, h = _tamano(v)
            if w:
                return w, h
    return 0, 0


def lienzos(cl):
    try:
        lista = _pedir(cl, "GetCanvasList").get("canvases") or []
    except Exception:  # noqa: BLE001   OBS viejo: un solo lienzo
        lista = []
    out = []
    for c in lista:
        w, h = _tamano(c)
        out.append({"nombre": c.get("canvasName") or c.get("name") or "Main", "uuid": c.get("canvasUuid") or c.get("uuid"),
                    "ancho": w, "alto": h})
    if not out:
        out = [{"nombre": "Main", "uuid": None, "ancho": 0, "alto": 0}]
    for c in out:
        if not c["ancho"] and (c["nombre"] == "Main" or len(out) == 1):
            v = cl.get_video_settings()
            c["ancho"], c["alto"] = v.base_width, v.base_height
        if not c["ancho"]:                          # no lo dijo: el de Aitum es 1080x1920
            c["ancho"], c["alto"] = (1080, 1920) if "vert" in c["nombre"].lower() else (1920, 1080)
        c["tipo"] = "vertical" if c["alto"] > c["ancho"] else "horizontal"
    return out


def _caja(tr, nativo=None):
    """Rectángulo (x, y, ancho, alto) que ocupa en el lienzo, con la escala, el recorte, los límites y la alineación."""
    w, h = float(tr.get("width") or 0), float(tr.get("height") or 0)
    if (not w or not h) and nativo:                 # fuente apagada (cámara): se calcula con su tamaño real
        w = max(0.0, nativo[0] - tr.get("cropLeft", 0) - tr.get("cropRight", 0)) * abs(tr.get("scaleX", 1) or 1)
        h = max(0.0, nativo[1] - tr.get("cropTop", 0) - tr.get("cropBottom", 0)) * abs(tr.get("scaleY", 1) or 1)
    if tr.get("boundsType") not in (None, "", "OBS_BOUNDS_NONE") and tr.get("boundsWidth"):
        w, h = float(tr["boundsWidth"]), float(tr["boundsHeight"])
    al = int(tr.get("alignment", 5))
    x, y = float(tr.get("positionX", 0)), float(tr.get("positionY", 0))
    x -= 0 if al & 1 else w if al & 2 else w / 2
    y -= 0 if al & 4 else h if al & 8 else h / 2
    return [round(x), round(y), round(w), round(h)]


def _ajustes(cl, nombre, cache):
    if nombre not in cache:
        try:
            cache[nombre] = _pedir(cl, "GetInputSettings", inputName=nombre).get("inputSettings") or {}
        except Exception:  # noqa: BLE001
            cache[nombre] = {}
    return cache[nombre]


def _nativo_camara(ajustes):
    m = re.match(r"(\d+)x(\d+)", str(ajustes.get("resolution") or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (1280, 720)


def inventario(cl=None):
    """Todo lo que hay en OBS: lienzos, escenas, fuentes con su caja, y los overlays (navegador, texto o imagen)."""
    cl = cl or overlays._obs()
    cache, salida, sus = {}, [], {}
    for lz in lienzos(cl):
        con_lienzo = {"canvasUuid": lz["uuid"]} if lz["uuid"] else {}
        escenas = _pedir(cl, "GetSceneList", **con_lienzo).get("scenes") or []
        lz["escenas"] = []
        for e in reversed(escenas):                 # OBS las da de abajo hacia arriba
            esc = {"nombre": e.get("sceneName"), "uuid": e.get("sceneUuid"), "fuentes": [], "camaras": []}
            items = _primero(cl, "GetSceneItemList", ([{"sceneUuid": esc["uuid"]}] if esc["uuid"] else []) +
                             [{"sceneName": esc["nombre"], **con_lienzo}]).get("sceneItems") or []
            pila = [(it, None) for it in items]
            while pila:
                it, grupo = pila.pop(0)
                tr = it.get("sceneItemTransform") or {}
                tipo = it.get("inputKind") or ("grupo" if it.get("isGroup") else it.get("sourceType") or "")
                nombre = it.get("sourceName")
                nativo = _nativo_camara(_ajustes(cl, nombre, cache)) if tipo in CAMARAS else None
                caja = _caja(tr, nativo)
                if grupo:                           # dentro de un grupo: relativo al grupo
                    gx, gy, sx, sy = grupo
                    caja = [round(gx + caja[0] * sx), round(gy + caja[1] * sy), round(caja[2] * sx), round(caja[3] * sy)]
                if it.get("isGroup"):
                    hijos = _primero(cl, "GetGroupSceneItemList", ([{"sceneUuid": it["sourceUuid"]}] if it.get("sourceUuid")
                                                                   else []) + [{"sceneName": nombre}]).get("sceneItems") or []
                    pos = (float(tr.get("positionX", 0)), float(tr.get("positionY", 0)),
                           float(tr.get("scaleX", 1) or 1), float(tr.get("scaleY", 1) or 1))
                    pila += [(h, pos) for h in hijos]
                    continue
                f = {"nombre": nombre, "tipo": tipo, "caja": caja, "visible": bool(it.get("sceneItemEnabled", True)),
                     "id": it.get("sceneItemId"), "en_grupo": bool(grupo)}
                esc["fuentes"].append(f)
                if tipo in CAMARAS:
                    esc["camaras"].append(caja)
                if tipo in (NAVEGADOR,) + TEXTOS + IMAGENES:
                    a = _ajustes(cl, nombre, cache)
                    o = sus.setdefault(nombre, _ficha(nombre, tipo, a))
                    o["donde"].append({"lienzo": lz["tipo"], "lienzo_nombre": lz["nombre"], "lienzo_uuid": lz["uuid"],
                                       "ancho_lienzo": lz["ancho"], "alto_lienzo": lz["alto"], "escena": esc["nombre"],
                                       "escena_uuid": esc["uuid"], "id": f["id"], "caja": caja, "visible": f["visible"],
                                       "en_grupo": f["en_grupo"]})
            lz["escenas"].append(esc)
        salida.append(lz)
    for o in sus.values():                          # las cámaras de cada escena donde está
        for d in o["donde"]:
            d["camaras"] = next((e["camaras"] for lz in salida for e in lz["escenas"]
                                 if e["uuid"] == d["escena_uuid"] and e["nombre"] == d["escena"]), [])
    return {"lienzos": salida, "overlays": sus}


def _ficha(nombre, tipo, a):
    archivo, dominio = None, ""
    if tipo == NAVEGADOR:
        if a.get("is_local_file") and a.get("local_file"):
            archivo = a["local_file"]
        else:
            dominio = urlparse(str(a.get("url") or "")).netloc        # nunca la URL entera (suelen llevar tokens)
            if str(a.get("url") or "").startswith("file:///"):
                archivo = str(a["url"])[8:]
    elif tipo in IMAGENES:
        archivo = a.get("file")
    return {"nombre": nombre, "tipo": tipo, "archivo": archivo, "dominio": dominio, "de_hogger": nombre.startswith(overlays.PREFIJO),
            "ancho": int(a.get("width") or 0), "alto": int(a.get("height") or 0),
            "texto": a.get("text") if tipo in TEXTOS else None, "donde": []}


# ----------------------------------------------------------------- ver
def _zona(caja, W, H):
    x, y, w, h = caja
    if w * h >= 0.85 * W * H:
        return "toda la pantalla"
    cx, cy = x + w / 2, y + h / 2
    fila = "arriba" if cy < H / 3 else "abajo" if cy > 2 * H / 3 else ""
    col = "a la izquierda" if cx < W / 3 else "a la derecha" if cx > 2 * W / 3 else ""
    return " ".join(p for p in (fila, col) if p) or "al centro"


def _de_donde(o):
    if o["tipo"] in TEXTOS:
        return f"texto «{(o['texto'] or '')[:40]}»"
    if o["archivo"]:
        return f"tu archivo {Path(str(o['archivo']).replace(chr(92), '/')).name}"
    return f"de {o['dominio'] or 'internet'}"


def ver(cl=None):
    """(lo que dice en voz alta, el detalle para la pantalla)."""
    inv = inventario(cl)
    lineas, cortas = [], []
    for lz in inv["lienzos"]:
        lineas.append(f"Lienzo {lz['tipo']} ({lz['ancho']}x{lz['alto']}):")
        nombres = []
        for e in lz["escenas"]:
            partes = []
            for f in e["fuentes"]:
                o = inv["overlays"].get(f["nombre"])
                if not o:
                    continue
                nombres.append(f["nombre"])
                oculto = "" if f["visible"] else ", oculto"
                partes.append(f"«{f['nombre']}» ({_de_donde(o)}, {f['caja'][2]}x{f['caja'][3]}, "
                              f"{_zona(f['caja'], lz['ancho'], lz['alto'])}{oculto})")
            for c in e["camaras"]:
                partes.append(f"cámara en x{c[0]} y{c[1]}, {c[2]}x{c[3]}")
            if partes:
                lineas.append(f"- {e['nombre']}: " + "; ".join(partes))
        propios = [n for n in dict.fromkeys(nombres) if not n.startswith(overlays.PREFIJO)]
        locales = [n for n in propios if inv["overlays"][n]["archivo"]]
        de_internet = len(propios) - len(locales)
        if propios:
            cortas.append(f"en el {lz['tipo']}, " + (", ".join(locales[:4]) or "ninguno tuyo") +
                          (f" y {de_internet} de internet" if de_internet else ""))
    corta = ("Tenés " + "; ".join(cortas) + ". Te dejo el detalle en pantalla.") if cortas else "No encontré overlays en tu OBS."
    return corta, "\n".join(lineas)


# ----------------------------------------------------------------- cuál
def _slug(t):
    """Minúsculas, sin tildes y sin signos (sin cortar el largo: sirve para buscar adentro de un archivo)."""
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _palabras(t):
    return [p for p in _slug(t).split() if p not in NO_CUENTAN and len(p) > 1]


def _leer(archivo):
    try:
        return Path(archivo).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return ""


def elegir(inv, cual="", lienzo="", cambio="", editable=True):
    """El overlay del que habla: por el lienzo, el nombre, el archivo, la escena o lo que dice adentro («beta»)."""
    todos = [o for o in inv["overlays"].values() if not o["de_hogger"]] or list(inv["overlays"].values())
    if not todos:
        raise Error("No encontré overlays en tu OBS.")
    lz = lienzo or ("vertical" if VERTICAL.search(_slug(cual)) else "horizontal" if HORIZONTAL.search(_slug(cual)) else "")
    if lz:
        todos = [o for o in todos if any(d["lienzo"] == lz for d in o["donde"])] or todos
    pide = _palabras(cual)
    citas = [_slug(c) for c in re.findall(r"[«\"“']([^»\"”']+)[»\"”']", cambio)] + _palabras(cambio)

    def puntaje(o):
        claves = _slug(" ".join([o["nombre"], Path(str(o["archivo"] or "").replace("\\", "/")).stem, o["dominio"]] +
                                [d["escena"] for d in o["donde"]]))
        claves += " " + " ".join(SINONIMOS.get(p, "") for p in claves.split())
        p = sum(3 for w in pide if w in claves)
        p += sum(1 for w in pide for k in claves.split() if len(w) > 3 and difflib.SequenceMatcher(None, w, k).ratio() > 0.8)
        if o["archivo"] and citas:
            contenido = _slug(_leer(o["archivo"]))
            p += sum(2 for c in citas if len(c) > 3 and c in contenido)
        if o["tipo"] in TEXTOS and citas:
            p += sum(2 for c in citas if c in _slug(o["texto"] or ""))
        if editable and (o["archivo"] or o["tipo"] in TEXTOS):
            p += 1
        if any(d["visible"] for d in o["donde"]):
            p += 0.5
        return p

    orden = sorted(todos, key=puntaje, reverse=True)
    if len(orden) > 1 and puntaje(orden[0]) == puntaje(orden[1]):
        opciones = ", ".join(f"«{o['nombre']}» ({o['donde'][0]['lienzo']}, {o['donde'][0]['escena']})" for o in orden[:4])
        raise Error(f"¿Cuál overlay? Tenés {opciones}.")
    return orden[0]


# ----------------------------------------------------------------- tapar lo privado
def tapar(texto):
    """(texto con la contraseña de OBS y los tokens tapados, {marca: valor}) para mostrárselo a Claude."""
    ocultos = {}

    def marca(valor):
        for k, v in ocultos.items():
            if v == valor:
                return k
        k = f"__OCULTO_{len(ocultos) + 1}__"
        ocultos[k] = valor
        return k
    pw = str(config.OBS_PASSWORD or "")
    if len(pw) >= 4 and pw in texto:
        texto = texto.replace(pw, marca(pw))
    texto = SECRETO.sub(lambda m: m.group(0) if OCULTO.fullmatch(m.group(4)) else
                        m.group(1) + m.group(2) + m.group(3) + marca(m.group(4)) + m.group(5), texto)
    texto = SECRETO_URL.sub(lambda m: m.group(0) if OCULTO.fullmatch(m.group(2)) else m.group(1) + marca(m.group(2)), texto)
    return texto, ocultos


def destapar(texto, ocultos):
    for k, v in ocultos.items():
        if k not in texto:
            raise Error("El cambio tocaba la contraseña o un dato privado del overlay: no lo hago.")
        texto = texto.replace(k, v)
    return texto


# ----------------------------------------------------------------- cambiar uno tuyo
def _carpeta_trabajo():
    c = config.DATA / "overlays_editados"
    c.mkdir(parents=True, exist_ok=True)
    return c


def _json_de(texto):
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise Error("Claude no devolvió los cambios.")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise Error(f"Claude devolvió algo que no entiendo ({e}).")


def aplicar_cambios(texto, cambios):
    """Aplica [{buscar, poner}] al texto tapado. Cada «buscar» tiene que estar UNA sola vez; si no, nada se cambia.

    texto puede tener caracteres raros (bytes que no son UTF-8): Claude los vio como «�» y un cambio que los incluya
    se rechaza, así esos bytes quedan intactos.
    """
    real = texto
    vis = re.sub("[\udc80-\udcff]", "�", real)                 # lo que vio Claude (mismo largo)
    hechos = 0
    for c in cambios or []:
        buscar, poner = str(c.get("buscar") or ""), str(c.get("poner") or "")
        if not buscar or buscar == poner:
            continue
        if "�" in buscar or "�" in poner:
            raise Error("El cambio tocaba caracteres que no se pueden leer bien del archivo: no lo hago.")
        if vis.count(buscar) != 1 and "\r\n" in vis and vis.count(buscar.replace("\n", "\r\n")) == 1:
            buscar, poner = buscar.replace("\n", "\r\n"), poner.replace("\n", "\r\n")
        veces = vis.count(buscar)
        if veces != 1:
            raise Error(f"No pude ubicar bien una parte del cambio ({'no está' if veces == 0 else 'está repetida'}): "
                        f"«{buscar[:60]}»")
        if OCULTO.search(buscar) and set(OCULTO.findall(buscar)) - set(OCULTO.findall(poner)):
            raise Error("El cambio tocaba la contraseña o un dato privado del overlay: no lo hago.")
        p = vis.index(buscar)
        real = real[:p] + poner + real[p + len(buscar):]
        vis = vis[:p] + poner + vis[p + len(buscar):]
        hechos += 1
    if not hechos:
        raise Error("No había nada que cambiar.")
    return real


def _en_vivo(cl):
    try:
        return bool(cl.get_stream_status().output_active) or bool(cl.get_record_status().output_active)
    except Exception:  # noqa: BLE001
        return False


AMBOS = "ambos"                  # «en los dos lienzos»: el horizontal y el vertical


def _cita(cambio):
    """Lo que hay que cambiar: lo primero entre comillas («Rogue» en «Cambiar "Rogue" por "War"»)."""
    m = re.findall(r"[«\"“']([^»\"”']{2,})[»\"”']", cambio or "")
    return _slug(m[0]) if m else ""


def _contenido(o):
    if o["archivo"] and Path(str(o["archivo"])).suffix.lower() in (".html", ".htm"):
        return _slug(_leer(o["archivo"]))
    if o["tipo"] in TEXTOS:
        return _slug(o["texto"] or "")
    return ""


def _con_cita(inv, cita, lz=""):
    """Tus overlays (de ese lienzo) que tienen adentro ese texto, sin repetir el mismo archivo."""
    if not cita:
        return []
    patron = re.compile(rf"(?<![a-z0-9]){re.escape(cita)}(?![a-z0-9])")
    vistos, hay = set(), []
    for o in inv["overlays"].values():
        if o["de_hogger"] or (lz and not any(d["lienzo"] == lz for d in o["donde"])):
            continue
        clave = str(o["archivo"] or o["nombre"])
        if clave not in vistos and patron.search(_contenido(o)):
            vistos.add(clave)
            hay.append(o)
    return hay


def elegir_varios(inv, cual="", lienzo="", cambio=""):
    """Los overlays a cambiar de una: si pidió los dos lienzos, o si lo que quiere cambiar («Rogue») está en
    overlays de los dos lienzos y no dijo cuál. Devuelve (overlays, lienzos donde no encontré ninguno).

    El 4 nov pidió «en los dos dice Rogue, que diga War» y Hogger cambió solo el vertical.
    """
    cita = _cita(cambio)
    if lienzo != AMBOS:
        if lienzo or VERTICAL.search(_slug(cual)) or HORIZONTAL.search(_slug(cual)) or not cita:
            return [], []
        hay = _con_cita(inv, cita)
        en = {d["lienzo"] for o in hay for d in o["donde"]}
        return (hay[:4], []) if len(hay) > 1 and len(en) > 1 else ([], [])
    elegidos, faltan = [], []
    for lz in ("horizontal", "vertical"):
        hay = _con_cita(inv, cita, lz)
        if not hay:
            try:
                o = elegir(inv, cual, lz, cambio)
                hay = [o] if any(d["lienzo"] == lz for d in o["donde"]) else []
            except Error:
                hay = []
        nuevos = [o for o in hay if str(o["archivo"] or o["nombre"]) not in
                  {str(e["archivo"] or e["nombre"]) for e in elegidos}]
        if not hay:
            faltan.append(lz)
        elegidos += nuevos
    if not elegidos:
        raise Error("No encontré cuál de tus overlays cambiar en los lienzos.")
    return elegidos[:4], faltan


def preparar_cambio(cual, cambio, lienzo="", cl=None, claude=None, dicho=""):
    """Arma el cambio en una copia (nada cambia en OBS) y devuelve los datos para el «dale».

    lienzo="ambos" (o lo que quiere cambiar está en overlays de los dos lienzos): prepara todos juntos.
    """
    cl = cl or overlays._obs()
    inv = inventario(cl)
    varios, faltan = elegir_varios(inv, cual, lienzo, cambio)
    if len(varios) > 1:
        partes, fallas = [], []
        for o in varios:
            try:
                partes.append(_preparar_uno(o, cambio, cl, claude, dicho))
            except Error as e:
                fallas.append(f"«{o['nombre']}»: {e}")
        fallas += [f"en el lienzo {lz} no encontré cuál cambiar" for lz in faltan]
        if len(partes) == 1:
            partes[0]["fallas"] = fallas
            return partes[0]
        if not partes:
            raise Error("; ".join(fallas) or "No pude preparar el cambio.")
        return {"tipo": "varios", "partes": partes, "fallas": fallas,
                "fuente": " y ".join(f"«{p['fuente']}»" for p in partes),
                "resumen": partes[0]["resumen"], "lienzo": " y ".join(dict.fromkeys(p["lienzo"] for p in partes)),
                "escena": ", ".join(dict.fromkeys(p["escena"] for p in partes)),
                "en_vivo": any(p["en_vivo"] for p in partes)}
    if varios:
        o = varios[0]
    else:
        o = elegir(inv, cual, "" if lienzo == AMBOS else lienzo, cambio)
    p = _preparar_uno(o, cambio, cl, claude, dicho)
    if faltan:
        p["fallas"] = [f"en el lienzo {lz} no encontré cuál cambiar" for lz in faltan]
    return p


def _preparar_uno(o, cambio, cl, claude=None, dicho=""):
    d = next((x for x in o["donde"] if x["visible"]), o["donde"][0])
    if o["tipo"] in TEXTOS:
        nuevo = _pedir_cambios(o, cambio, o["texto"] or "", d, claude, dicho)
        return {"tipo": "texto", "fuente": o["nombre"], "texto_antes": o["texto"] or "", "texto": nuevo["texto"],
                "resumen": nuevo["resumen"], "lienzo": d["lienzo"], "escena": d["escena"], "en_vivo": _en_vivo(cl)}
    if not o["archivo"]:
        if o["tipo"] in IMAGENES:
            raise Error(f"«{o['nombre']}» es una imagen: esa no la puedo cambiar por dentro. Te puedo hacer uno nuevo "
                        "del mismo tamaño y en el mismo lugar.")
        raise Error(f"«{o['nombre']}» viene de internet ({o['dominio'] or 'otra página'}): ese no lo puedo cambiar desde "
                    "acá. Te puedo hacer uno nuevo del mismo tamaño y en el mismo lugar.")
    archivo = Path(o["archivo"])
    if not archivo.exists():
        raise Error(f"No encuentro el archivo de «{o['nombre']}» ({archivo.name}).")
    if archivo.suffix.lower() not in (".html", ".htm"):
        raise Error(f"«{o['nombre']}» es un archivo {archivo.suffix}: por ahora solo cambio overlays HTML.")
    crudo = archivo.read_bytes()
    texto = crudo.decode("utf-8", "surrogateescape")
    tapado, ocultos = tapar(texto)
    propuesta = _pedir_cambios(o, cambio, tapado, d, claude, dicho)
    nuevo_tapado = aplicar_cambios(tapado, propuesta["cambios"])
    destapar(nuevo_tapado, ocultos)                  # que se pueda destapar; se destapa recién con el «dale»
    _limpiar_propuestas()
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    copia_nueva = _carpeta_trabajo() / f"{archivo.stem}_{sello}_propuesta{archivo.suffix}"
    copia_nueva.write_bytes(nuevo_tapado.encode("utf-8", "surrogateescape"))   # sin la contraseña en claro
    return {"tipo": "archivo", "fuente": o["nombre"], "archivo": str(archivo), "propuesta": str(copia_nueva),
            "sha_antes": hashlib.sha1(crudo).hexdigest(), "resumen": propuesta["resumen"], "lienzo": d["lienzo"],
            "escena": d["escena"], "en_vivo": _en_vivo(cl)}


def _limpiar_propuestas(horas=2):
    """Las propuestas viejas (cambios que no se aplicaron) se borran: son copias de trabajo de Hogger."""
    limite = time.time() - horas * 3600
    for f in _carpeta_trabajo().glob("*_propuesta.*"):
        try:
            if f.stat().st_mtime < limite:
                f.unlink()
        except OSError:
            pass


def _pedir_cambios(o, cambio, contenido, d, claude=None, dicho=""):
    camaras = "; ".join(f"x{c[0]} y{c[1]} de {c[2]}x{c[3]}" for c in d.get("camaras") or []) or "no hay cámara en esa escena"
    es_texto = o["tipo"] in TEXTOS
    pedido = f"""Sos el editor de overlays de OBS de Mister H (streamer de World of Warcraft, guild The H's).
Este overlay YA ESTÁ en su stream: fuente «{o['nombre']}», en la escena «{d['escena']}» del lienzo {d['lienzo']}
({d['ancho_lienzo']}x{d['alto_lienzo']}), ocupa {d['caja'][2]}x{d['caja'][3]} en x{d['caja'][0]} y{d['caja'][1]}.
La cámara en esa escena: {camaras}.
Nicolas pidió: «{cambio}»{f"  (lo que dijo, tal cual: «{dicho}»)" if dicho and dicho != cambio else ""}

Devolvé SOLO un JSON, sin explicaciones:
""" + ('{"resumen": "qué cambiás, en una frase corta y simple para Nicolas", "texto": "el texto nuevo completo"}'
       if es_texto else
       '{"resumen": "qué cambiás, en una frase corta y simple para Nicolas", '
       '"cambios": [{"buscar": "texto EXACTO del archivo, que aparezca UNA sola vez", "poner": "lo que va en su lugar"}]}') + """
Reglas:
- Cambiá lo MÍNIMO para cumplir el pedido. No reescribas el archivo ni cambies el estilo, los tamaños o las animaciones
  si no lo pidió. Si hace falta para que no quede un hueco feo (p. ej. una etiqueta vacía), arreglalo con lo mínimo.
- «buscar» copia el archivo al pie de la letra (espacios incluidos) y tiene que aparecer una sola vez: incluí un poco
  de contexto. Varios cambios chicos mejor que uno grande.
- No toques nada que diga __OCULTO_ (son datos privados), ni la conexión a OBS, ni CONFIG.level, ni localStorage,
  ni lo que maneja el nivel: si cambia, se pierde el nivel guardado.
- No achiques ni tapes el hueco de la cámara, salvo que lo pida.
- Los textos que dictó van EXACTOS. No inventes datos, fechas ni enlaces.
- Lo dictó por voz: si el pedido trae palabras repetidas o raras del dictado (p. ej. «Mr. HMR espacio H» quiere
  decir «Mr. H»), quedate con lo que tiene sentido; ante la duda, lo más corto y simple.
- Nada nuevo que cargue cosas de internet (solo Google Fonts).
- Si no se puede hacer con este archivo, devolvé {"resumen": "por qué no se puede", "cambios": []}.

""" + ("Texto actual:\n" if es_texto else "Archivo:\n") + "<<<\n" + re.sub("[\udc80-\udcff]", "�", contenido) + "\n>>>"
    respuesta = (claude or _claude)(pedido)
    j = _json_de(respuesta)
    j["resumen"] = str(j.get("resumen") or cambio).strip()[:300]
    if es_texto:
        if not str(j.get("texto") or "").strip():
            raise Error(j["resumen"] or "No pude armar el texto nuevo.")
        j["texto"] = str(j["texto"])[:2000]
    elif not j.get("cambios"):
        raise Error(f"No lo pude cambiar: {j['resumen']}")
    return j


def _claude(pedido):
    c = config.BASE / "overlays" / "_editor"
    c.mkdir(parents=True, exist_ok=True)
    return overlays.preguntar_a_claude(pedido, c)


# ----------------------------------------------------------------- uno nuevo igual de tamaño y lugar
def preparar_nuevo(cual, que, lienzo="", reemplazar=False, nombre="", cl=None, disenar=None, dicho=""):
    cl = cl or overlays._obs()
    inv = inventario(cl)
    o = elegir(inv, cual, lienzo, "", editable=False)
    d = next((x for x in o["donde"] if (not lienzo or x["lienzo"] == lienzo) and x["visible"]), o["donde"][0])
    x, y, w, h = d["caja"]
    x, y = max(0, x), max(0, y)
    w, h = min(w, d["ancho_lienzo"] - x), min(h, d["alto_lienzo"] - y)
    if w < 50 or h < 30:
        raise Error(f"«{o['nombre']}» es muy chico o está fuera de pantalla para copiarle el tamaño.")
    huecos = []
    for c in d.get("camaras") or []:                # la cámara, en coordenadas del overlay nuevo
        cx0, cy0 = max(c[0], x), max(c[1], y)
        cx1, cy1 = min(c[0] + c[2], x + w), min(c[1] + c[3], y + h)
        if cx1 > cx0 and cy1 > cy0:
            huecos.append((cx0 - x, cy0 - y, cx1 - cx0, cy1 - cy0))
    hueco_txt = "; ".join(f"x{a} y{b} de {c}x{e}" for a, b, c, e in huecos)
    if dicho and dicho != que:
        que = f"{que} (lo que dijo Nicolas, tal cual: «{dicho}»)"
    descripcion = (f"{que}\nVa en el mismo lugar que «{o['nombre']}» (escena «{d['escena']}» del lienzo {d['lienzo']}, "
                   f"{d['ancho_lienzo']}x{d['alto_lienzo']}).")
    if huecos:
        descripcion += (f"\nLa CÁMARA ocupa {hueco_txt} (en píxeles de este overlay): ese rectángulo tiene que quedar "
                        "100% TRANSPARENTE, sin nada encima. Podés ponerle un marco alrededor, por fuera.")
    pagina, quien = (disenar or overlays.disenar)(descripcion, w, h)
    nombre = (nombre or f"{o['nombre']} nuevo").strip()[:40]
    archivo = overlays.carpeta() / f"{overlays._slug(nombre)}.html"
    archivo.write_text(pagina, encoding="utf-8")
    return {"tipo": "nuevo", "fuente": overlays.nombre_obs(nombre), "archivo": str(archivo), "ref": o["nombre"],
            "ref_id": d["id"], "escena": d["escena"], "escena_uuid": d["escena_uuid"], "lienzo": d["lienzo"],
            "lienzo_uuid": d["lienzo_uuid"], "caja": [x, y, w, h], "reemplazar": bool(reemplazar), "quien": quien,
            "resumen": f"Overlay nuevo de {w}x{h} en el lugar de «{o['nombre']}»" + (
                " (el tuyo lo oculto, no lo borro)" if reemplazar else " (el tuyo queda como está)"),
            "en_vivo": _en_vivo(cl)}


# ----------------------------------------------------------------- aplicar y volver (con el «dale»)
REGISTRO = "overlays_cambios.json"


def _registro():
    try:
        return json.loads((config.DATA / REGISTRO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _guardar_registro(r):
    (config.DATA / REGISTRO).write_text(json.dumps(r[-20:], indent=2, ensure_ascii=False), encoding="utf-8")


def _escena_args(datos):
    return ([{"sceneUuid": datos["escena_uuid"]}] if datos.get("escena_uuid") else []) + \
        [{"sceneName": datos["escena"], **({"canvasUuid": datos["lienzo_uuid"]} if datos.get("lienzo_uuid") else {})}]


def _recargar(cl, fuente):
    try:
        _pedir(cl, "PressInputPropertiesButton", inputName=fuente, propertyName="refreshnocache")
    except Exception as e:  # noqa: BLE001
        print(f"[mis overlays] no pude recargar «{fuente}»: {e}")


def _captura(cl, fuente, ancho, alto):
    """Foto SOLO de esa fuente (nunca de la pantalla), para el registro."""
    try:
        k = min(1.0, 960 / max(ancho, alto, 1))
        r = _pedir(cl, "GetSourceScreenshot", sourceName=fuente, imageFormat="png",
                   imageWidth=max(8, int(ancho * k)), imageHeight=max(8, int(alto * k)))
        datos = str(r.get("imageData") or "").split(",", 1)[-1]
        ruta = _carpeta_trabajo() / f"{overlays._slug(fuente)}_despues.png"
        ruta.write_bytes(base64.b64decode(datos))
        return str(ruta)
    except Exception as e:  # noqa: BLE001
        print(f"[mis overlays] no pude sacar la foto de «{fuente}»: {e}")
        return ""


def aplicar(datos, cl=None, grupo=None):
    cl = cl or overlays._obs()
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if datos["tipo"] == "varios":
        return _aplicar_varios(datos, cl, sello)
    reg = _registro()
    junto = {"grupo": grupo} if grupo else {}            # los de un mismo «dale» se deshacen juntos
    if datos["tipo"] == "texto":
        _pedir(cl, "SetInputSettings", inputName=datos["fuente"], inputSettings={"text": datos["texto"]}, overlay=True)
        reg.append({"tipo": "texto", "fuente": datos["fuente"], "texto_antes": datos["texto_antes"], "cuando": sello,
                    "resumen": datos["resumen"], **junto})
        _guardar_registro(reg)
        return f"Listo, cambié «{datos['fuente']}»: {datos['resumen'].rstrip('. ')}."
    if datos["tipo"] == "archivo":
        orig = Path(datos["archivo"])
        actual = orig.read_bytes()
        if hashlib.sha1(actual).hexdigest() != datos["sha_antes"]:
            raise Error("El archivo del overlay cambió desde que preparé el cambio. Pedímelo de nuevo.")
        _, ocultos = tapar(actual.decode("utf-8", "surrogateescape"))      # las mismas marcas que vio Claude
        propuesta = Path(datos["propuesta"])
        nuevo = destapar(propuesta.read_bytes().decode("utf-8", "surrogateescape"), ocultos)
        copias = orig.parent / "_copias"
        copias.mkdir(exist_ok=True)
        copia = copias / f"{orig.stem}_{sello}{orig.suffix}"
        shutil.copy2(orig, copia)                   # el original, siempre
        orig.write_bytes(nuevo.encode("utf-8", "surrogateescape"))
        try:
            propuesta.unlink()                      # ya no hace falta la copia de trabajo
        except OSError:
            pass
        _recargar(cl, datos["fuente"])
        inv = inventario(cl)["overlays"]
        for nombre, otro in inv.items():          # otra fuente con el mismo archivo (p. ej. en el otro lienzo)
            if nombre != datos["fuente"] and str(otro.get("archivo") or "") == str(orig):
                _recargar(cl, nombre)
        time.sleep(2.5)
        o = inv.get(datos["fuente"]) or {}
        caja = (o.get("donde") or [{}])[0].get("caja") or [0, 0, o.get("ancho") or 1080, o.get("alto") or 1920]
        foto = _captura(cl, datos["fuente"], caja[2], caja[3])
        reg.append({"tipo": "archivo", "fuente": datos["fuente"], "archivo": str(orig), "copia": str(copia),
                    "cuando": sello, "resumen": datos["resumen"], "foto": foto, **junto})
        _guardar_registro(reg)
        return (f"Listo, cambié «{datos['fuente']}»: {datos['resumen'].rstrip('. ')}. El original quedó en {copia}. "
                "Si no te gusta, decime «volvé el overlay como estaba».")
    if datos["tipo"] == "nuevo":
        return _poner_nuevo(cl, datos, reg, sello)
    raise Error("No sé qué cambio era ese.")


def _aplicar_varios(datos, cl, sello):
    hechos, fallas = [], []
    for p in datos["partes"]:
        try:
            aplicar(p, cl, grupo=sello)
            hechos.append(f"«{p['fuente']}» ({p['lienzo']})")
        except Error as e:
            fallas.append(f"«{p['fuente']}»: {e}")
    if not hechos:
        raise Error("; ".join(fallas))
    texto = f"Listo, cambié {' y '.join(hechos)}: {datos['resumen'].rstrip('. ')}."
    if fallas:
        texto += " No pude con " + "; ".join(fallas) + "."
    return texto + " Los originales quedaron en _copias. Si no te gusta, decime «volvé el overlay como estaba»."


def _poner_nuevo(cl, datos, reg, sello):
    x, y, w, h = datos["caja"]
    ajustes = {"is_local_file": True, "local_file": datos["archivo"], "width": int(w), "height": int(h),
               "reroute_audio": False, "shutdown": False, "restart_when_active": True}
    existentes = {i["inputName"] for i in cl.get_input_list().inputs}
    item = None
    if datos["fuente"] in existentes:
        _pedir(cl, "SetInputSettings", inputName=datos["fuente"], inputSettings=ajustes, overlay=True)
        _recargar(cl, datos["fuente"])
        for args in _escena_args(datos):
            try:
                item = _pedir(cl, "GetSceneItemId", sourceName=datos["fuente"], **args).get("sceneItemId")
                break
            except Exception:  # noqa: BLE001
                pass
        if item is None:
            item = _primero(cl, "CreateSceneItem", [{**a, "sourceName": datos["fuente"]} for a in _escena_args(datos)]
                            ).get("sceneItemId")
    else:
        item = _primero(cl, "CreateInput", [{**a, "inputName": datos["fuente"], "inputKind": NAVEGADOR,
                                             "inputSettings": ajustes, "sceneItemEnabled": True}
                                            for a in _escena_args(datos)]).get("sceneItemId")
    _primero(cl, "SetSceneItemTransform", [{**a, "sceneItemId": item, "sceneItemTransform": {
        "positionX": x, "positionY": y, "alignment": 5, "scaleX": 1.0, "scaleY": 1.0, "rotation": 0.0,
        "boundsType": "OBS_BOUNDS_NONE", "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0}}
        for a in _escena_args(datos)])
    _primero(cl, "SetSceneItemEnabled", [{**a, "sceneItemId": item, "sceneItemEnabled": True} for a in _escena_args(datos)])
    oculte = False
    if datos.get("reemplazar") and datos.get("ref_id") is not None:
        _primero(cl, "SetSceneItemEnabled", [{**a, "sceneItemId": datos["ref_id"], "sceneItemEnabled": False}
                                             for a in _escena_args(datos)])
        oculte = True
    reg.append({"tipo": "nuevo", "fuente": datos["fuente"], "item": item, "ref": datos["ref"], "ref_id": datos["ref_id"],
                "oculte": oculte, "escena": datos["escena"], "escena_uuid": datos.get("escena_uuid"),
                "lienzo_uuid": datos.get("lienzo_uuid"), "cuando": sello, "resumen": datos["resumen"]})
    _guardar_registro(reg)
    return (f"Listo, puse «{datos['fuente'][len(overlays.PREFIJO):]}» en la escena {datos['escena']}"
            + (f" y oculté «{datos['ref']}» (no lo borré)." if oculte else ".")
            + " Si no te gusta, decime «volvé el overlay como estaba».")


def volver(cl=None):
    """Deshace el último cambio (si fueron varios con un mismo «dale», todos)."""
    reg = _registro()
    if not reg:
        raise Error("No tengo ningún cambio de overlay para deshacer.")
    cl = cl or overlays._obs()
    grupo = reg[-1].get("grupo")
    if not grupo:
        return _volver_uno(reg, cl)
    textos = []
    while reg and reg[-1].get("grupo") == grupo:
        textos.append(_volver_uno(reg, cl))
        reg = _registro()
    if len(textos) == 1:
        return textos[0]
    nombres = [m.group(1) for m in (re.search(r"«([^»]+)»", t) for t in textos) if m]
    return f"Listo, {' y '.join(f'«{n}»' for n in nombres)} volvieron a como estaban."


def _volver_uno(reg, cl):
    c = reg[-1]
    if c["tipo"] == "archivo":
        orig, copia = Path(c["archivo"]), Path(c["copia"])
        if not copia.exists():
            raise Error(f"No encuentro la copia del original ({copia}).")
        sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(orig, orig.parent / "_copias" / f"{orig.stem}_{sello}_antes_de_volver{orig.suffix}")
        shutil.copy2(copia, orig)
        _recargar(cl, c["fuente"])
        texto = f"Listo, «{c['fuente']}» volvió a como estaba."
    elif c["tipo"] == "texto":
        _pedir(cl, "SetInputSettings", inputName=c["fuente"], inputSettings={"text": c["texto_antes"]}, overlay=True)
        texto = f"Listo, «{c['fuente']}» volvió a como estaba."
    else:
        _primero(cl, "SetSceneItemEnabled", [{**a, "sceneItemId": c["item"], "sceneItemEnabled": False}
                                             for a in _escena_args(c)])
        if c.get("oculte"):
            _primero(cl, "SetSceneItemEnabled", [{**a, "sceneItemId": c["ref_id"], "sceneItemEnabled": True}
                                                 for a in _escena_args(c)])
        texto = f"Listo, saqué el overlay nuevo de la escena {c['escena']}" + (
            f" y volví a mostrar «{c['ref']}»." if c.get("oculte") else ".")
    reg.pop()
    _guardar_registro(reg)
    return texto
