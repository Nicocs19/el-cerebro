"""Busca en internet para contestar preguntas, solo cuando la pregunta lo necesita.

- Con OLLAMA_API_KEY (cuenta gratis de ollama.com, conectar_busqueda.bat) usa la búsqueda web de Ollama.
- Sin clave usa Wikipedia en español (gratis, sin cuenta): sirve para «quién es», «qué es», historia, etc.
Después la IA local resume lo encontrado en 1 a 3 frases para decirlo en voz alta, sin inventar.
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
    r.raise_for_status()
    return [{"titulo": x.get("title") or "", "url": x.get("url") or "", "texto": x.get("content") or ""}
            for x in r.json().get("results") or []]


def _wikipedia(pregunta, maximo):
    base = "https://es.wikipedia.org"
    r = _sesion.get(f"{base}/w/api.php", headers=AGENTE, timeout=10, params={
        "action": "query", "list": "search", "srsearch": pregunta, "srlimit": maximo, "format": "json"})
    r.raise_for_status()
    salida = []
    for x in r.json().get("query", {}).get("search", [])[:maximo]:
        titulo = x["title"]
        try:
            s = _sesion.get(f"{base}/api/rest_v1/page/summary/{quote(titulo.replace(' ', '_'))}", headers=AGENTE, timeout=10)
            texto = s.json().get("extract", "") if s.ok else ""
        except requests.RequestException:
            texto = ""
        texto = texto or re.sub(r"<[^>]+>", "", x.get("snippet", ""))
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
    d = urlparse(url or "").netloc.lower()
    return d[4:] if d.startswith("www.") else d


INSTRUCCIONES = """Eres El Cerebro, el asistente gracioso del stream de Nicolas (Mr. H). Te hizo una pregunta y buscaste en internet.
Contestá en 1 a 3 frases cortas, para decir en voz alta, en español latino y con onda.
Usá SOLO lo que dicen los resultados. Si no alcanzan para contestar, decí que no encontraste ese dato. No inventes nada.
No leas links ni digas «según el resultado 2»: contalo natural. Números y fechas tal cual aparecen."""


def contestar(pregunta):
    """(respuesta, fuente). Busca y la IA local resume lo encontrado."""
    t0 = time.time()
    resultados = [r for r in buscar(pregunta) if r.get("texto")]
    if not resultados:
        return "Busqué y no encontré nada sobre eso. Preguntame de otra forma.", ""
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
    print(f"[buscar] {len(resultados)} resultados, respuesta en {time.time() - t0:.1f} s")
    return texto[:600] or "No pude armar la respuesta con lo que encontré.", dominio(resultados[0]["url"])


if __name__ == "__main__":  # prueba: python buscar.py "quién ganó el último mundial"
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = " ".join(sys.argv[1:]) or "¿Qué es World of Warcraft?"
    for x in buscar(p):
        print("-", x["titulo"], dominio(x["url"]), x["texto"][:120].replace("\n", " "))
    print(contestar(p))
