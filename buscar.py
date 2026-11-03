"""Busca en internet para contestar preguntas, solo cuando la pregunta lo necesita.

1. Con el programa claude de tu PC (tu plan, sin costo extra): Claude busca en la web y contesta. Es lo más completo
   (noticias, parches, WoW). Corre SIN acceso a tus archivos ni a la PC: solo puede buscar y leer páginas.
2. Con OLLAMA_API_KEY (ollama.com, conectar_busqueda.bat; a algunas cuentas les pide plan pago): búsqueda web de
   Ollama + IA local.
3. Si no hay nada de eso: Wikipedia (español y si no, inglés) + IA local.
Tarda más que una charla normal (se avisa con «dejame buscar»), pero solo se usa cuando hace falta.
"""
import re
import time
from urllib.parse import quote, urlparse

import requests

import config

AGENTE = {"User-Agent": "ElCerebro/1.0 (asistente de voz para streaming)"}
_sesion = requests.Session()


def _ollama_web(pregunta, maximo):
    r = _sesion.post("https://ollama.com/api/web_search", json={"query": pregunta, "max_results": maximo},
                     headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}, timeout=15)
    if r.status_code in (401, 403):
        raise PermissionError("ollama.com no aceptó la clave de búsqueda (conectar_busqueda.bat)")
    if r.status_code == 402:
        raise PermissionError("ollama.com pide un plan pago para buscar con esta cuenta")
    r.raise_for_status()
    return [{"titulo": x.get("title") or "", "url": x.get("url") or "", "texto": x.get("content") or ""}
            for x in r.json().get("results") or []]


def _wikipedia(pregunta, maximo):
    for idioma in ("es", "en"):
        salida = _wikipedia_en(f"https://{idioma}.wikipedia.org", pregunta, maximo)
        if salida:
            return salida
    return []


def _wikipedia_en(base, pregunta, maximo):
    consulta = re.sub(r"^(que|qué|quien|quién|cual|cuál|como|cómo|cuando|cuándo|donde|dónde)\s+(es|son|fue|era)\s+", "",
                      pregunta.strip(" ¿?¡!"), flags=re.I)
    r = _sesion.get(f"{base}/w/api.php", headers=AGENTE, timeout=10, params={
        "action": "query", "list": "search", "srsearch": consulta, "srlimit": maximo, "format": "json"})
    r.raise_for_status()
    palabras = {w for w in re.findall(r"\w{4,}", consulta.lower())}
    salida = []
    for x in r.json().get("query", {}).get("search", [])[:maximo]:
        titulo = x["title"]
        try:
            s = _sesion.get(f"{base}/api/rest_v1/page/summary/{quote(titulo.replace(' ', '_'))}", headers=AGENTE, timeout=10)
            texto = s.json().get("extract", "") if s.ok else ""
        except requests.RequestException:
            texto = ""
        texto = texto or re.sub(r"<[^>]+>", "", x.get("snippet", ""))
        if palabras and not any(w in (titulo + " " + texto).lower() for w in palabras):
            continue                       # resultado que no tiene nada que ver con la pregunta
        salida.append({"titulo": titulo, "url": f"{base}/wiki/{quote(titulo.replace(' ', '_'))}", "texto": texto})
    return salida


def buscar(pregunta, maximo=4):
    """Lista de resultados {titulo, url, texto}. Usa la búsqueda de Ollama si hay clave; si no, Wikipedia."""
    if config.OLLAMA_API_KEY:
        try:
            return _ollama_web(pregunta, maximo)
        except Exception as e:  # noqa: BLE001
            print(f"[buscar] La búsqueda de ollama.com falló ({e}); pruebo con Wikipedia.")
    return _wikipedia(pregunta, min(maximo, 3))


def dominio(url):
    url = url or ""
    d = urlparse(url if "//" in url else f"https://{url}").netloc.lower()
    return d[4:] if d.startswith("www.") else d


INSTRUCCIONES = """Eres El Cerebro, el asistente gracioso del stream de Nicolas (Mr. H). Te hizo una pregunta y buscaste en internet.
Contestá en 1 a 3 frases cortas, para decir en voz alta, en español latino y con onda.
Usá SOLO lo que dicen los resultados. Si no alcanzan para contestar, decí que no encontraste ese dato. No inventes nada.
No leas links ni digas «según el resultado 2»: contalo natural. Números y fechas tal cual aparecen."""


CLAUDE_PEDIDO = """Sos El Cerebro, el asistente gracioso del stream de Nicolas (Mr. H, streamer de World of Warcraft Forever).
Te preguntó: {pregunta}
Es en vivo y tiene que ser rápido: hacé UNA búsqueda con WebSearch y contestá con lo que diga. Usá WebFetch solo si
los resultados no alcanzan, y como mucho una página. Contestá en 1 a 3 frases cortas para decir en voz alta,
en español latino y con onda. Solo datos que encontraste; si no lo encontrás, decilo. Sin links ni markdown.
En la última línea poné: FUENTE: <dominio de donde sacaste el dato>"""


def _con_claude(pregunta):
    """Claude busca y contesta. Sin herramientas de archivos ni de la PC, en una carpeta vacía."""
    import subprocess
    import tempfile

    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO, buscar_claude
    exe = buscar_claude()
    if not exe:
        raise RuntimeError("no está el programa claude")
    comando = [exe, "-p", "--max-turns", "5", "--model", config.CLAUDE_MODELO_BUSQUEDA] + SOLO_ESTO
    comando += ["--disallowedTools"] + [h for h in SIN_HERRAMIENTAS if h not in ("WebFetch", "WebSearch")]
    comando += ["--allowedTools", "WebSearch", "WebFetch"]
    r = subprocess.run(comando, input=CLAUDE_PEDIDO.format(pregunta=pregunta), capture_output=True, text=True,
                       encoding="utf-8", timeout=120, cwd=tempfile.mkdtemp(prefix="cerebro_pregunta_"))
    salida = (r.stdout or "").strip()
    if r.returncode != 0 or not salida:
        raise RuntimeError(f"claude no contestó ({r.returncode}): {(r.stderr or '')[:150]}")
    m = re.search(r"^\s*FUENTE:\s*(.+)$", salida, re.M | re.I)
    fuente = dominio(m.group(1).strip()) or m.group(1).strip() if m else ""
    texto = re.sub(r"^\s*FUENTE:.*$", "", salida, flags=re.M | re.I).strip()
    texto = re.sub(r"[*_`#>]+", "", texto)
    return texto[:600], fuente[:60]


def contestar(pregunta):
    """(respuesta, fuente).

    Con clave de ollama.com (conectar_busqueda.bat) va primero la búsqueda rápida + IA local (unos segundos) y Claude
    queda de respaldo; sin clave, Claude busca (más completo, pero tarda 15 a 30 s) y si no, Wikipedia.
    """
    t0 = time.time()
    if config.OLLAMA_API_KEY and config.BUSQUEDA_RAPIDA_PRIMERO:
        try:
            resultados = [r for r in _ollama_web(pregunta, 4) if r.get("texto")]
            if resultados:
                texto, fuente = _resumir(pregunta, resultados)
                print(f"[buscar] búsqueda rápida en {time.time() - t0:.1f} s")
                if "no encontr" not in texto.lower():
                    return texto, fuente
        except Exception as e:  # noqa: BLE001
            print(f"[buscar] La búsqueda rápida falló ({e}).")
    if config.BUSCAR_CON_CLAUDE:
        try:
            texto, fuente = _con_claude(pregunta)
            print(f"[buscar] Claude contestó en {time.time() - t0:.1f} s")
            return texto, fuente
        except Exception as e:  # noqa: BLE001
            print(f"[buscar] Claude no pudo buscar ({e}); pruebo con la búsqueda simple.")
    resultados = [r for r in buscar(pregunta) if r.get("texto")]
    if not resultados:
        return "Busqué y no encontré nada sobre eso. Preguntame de otra forma.", ""
    texto, fuente = _resumir(pregunta, resultados)
    print(f"[buscar] {len(resultados)} resultados, respuesta en {time.time() - t0:.1f} s")
    return texto, fuente


def _resumir(pregunta, resultados):
    """La IA local arma la respuesta con los resultados (misma configuración que el router: no recarga el modelo)."""
    material = "\n\n".join(f"[{i + 1}] {r['titulo']} ({dominio(r['url'])}): {r['texto'][:1200]}"
                           for i, r in enumerate(resultados[:4]))
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": INSTRUCCIONES},
                     {"role": "user", "content": f"Pregunta: {pregunta}\n\nResultados de la búsqueda:\n{material}"}],
        "stream": False, "think": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0.3, "num_ctx": 8192},   # misma configuración que el router: no recarga el modelo
    }, timeout=60)
    r.raise_for_status()
    texto = (r.json().get("message", {}).get("content") or "").strip()
    return texto[:600] or "No pude armar la respuesta con lo que encontré.", dominio(resultados[0]["url"])


if __name__ == "__main__":  # prueba: python buscar.py "quién ganó el último mundial"
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = " ".join(sys.argv[1:]) or "¿Qué es World of Warcraft?"
    print(contestar(p))
