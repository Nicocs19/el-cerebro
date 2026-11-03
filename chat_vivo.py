"""Escucha el chat de Kick mientras El Cerebro está abierto.

Sirve para la moderación por voz: cuando decís «banea a pepe», se busca a quién se parece más entre los que
escribieron hace poco (el dictado escribe los nombres "como suenan"). Solo lee el chat.

Kick publica su chat por un canal público (Pusher). Para conectarse hace falta el número de la sala del chat:
conectar_kick.bat lo pide una vez (con tu navegador) y queda en data/kick_chatroom.json, o se pone a mano en .env
como KICK_CHATROOM_ID.
"""
import collections
import json
import re
import threading
import time

import requests

import config

MENSAJES = collections.deque(maxlen=1000)     # lo último del chat de Kick
ESTADO = {"conectado": False, "error": None, "sala": None, "desde": None}
CACHE = config.DATA / "kick_chatroom.json"


def url_canal(slug):
    return f"https://kick.com/api/v2/channels/{slug}"


def sala_en_texto(texto):
    """Saca el número de la sala del chat del texto de la página de kick.com (lo que copiás con Ctrl+A, Ctrl+C)."""
    try:
        return int(json.loads(texto)["chatroom"]["id"])
    except Exception:  # noqa: BLE001
        m = re.search(r'"chatroom"\s*:\s*\{[^{}]*?"id"\s*:\s*(\d+)', texto or "")
        return int(m.group(1)) if m else None


def guardar_sala(slug, sala):
    CACHE.write_text(json.dumps({"slug": slug, "id": int(sala)}), encoding="utf-8")


def sala_guardada(slug):
    if config.KICK_CHATROOM_ID:
        return int(config.KICK_CHATROOM_ID)
    try:
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if c.get("slug") == slug and c.get("id"):
            return int(c["id"])
    except Exception:  # noqa: BLE001
        pass
    return None


def sala_de_chat(slug):
    sala = sala_guardada(slug)
    if sala:
        return sala
    try:  # a veces kick.com responde directo; si no, conectar_kick.bat la pide con el navegador
        r = requests.get(url_canal(slug), headers={"Accept": "application/json"}, timeout=15)
        sala = sala_en_texto(r.text) if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        sala = None
    if not sala:
        raise RuntimeError("falta el número del chat de Kick: doble clic en conectar_kick.bat")
    guardar_sala(slug, sala)
    return sala


CLAVE_PUSHER = config.DATA / "kick_pusher.json"


def _url_pusher(clave, cluster):
    return f"wss://ws-{cluster}.pusher.com/app/{clave}?protocol=7&client=js&version=8.4.0&flash=false"


def clave_pusher(renovar=False):
    """(clave, cluster) del chat de Kick. Kick la cambia a veces: si deja de servir, se le pregunta la actual."""
    if not renovar:
        try:
            c = json.loads(CLAVE_PUSHER.read_text(encoding="utf-8"))
            return c["clave"], c["cluster"]
        except Exception:  # noqa: BLE001
            return config.KICK_PUSHER_KEY, config.KICK_PUSHER_CLUSTER
    try:
        r = requests.post("https://web.kick.com/api/v1/realtime/connection", json={"accepted_providers": ["pusher"]},
                          headers={"Accept": "application/json"}, timeout=15)
        for c in ((r.json() or {}).get("data") or {}).get("connections") or []:
            cred = c.get("credentials") or {}
            if cred.get("app_key") and cred.get("cluster"):
                CLAVE_PUSHER.write_text(json.dumps({"clave": cred["app_key"], "cluster": cred["cluster"]}), encoding="utf-8")
                print(f"[chat] Kick usa ahora la clave de chat {cred['app_key']} ({cred['cluster']}).")
                return cred["app_key"], cred["cluster"]
    except Exception as e:  # noqa: BLE001
        print(f"[chat] No pude preguntarle a Kick la clave nueva del chat ({e}).")
    return None


def _agregar(datos, mi_id):
    autor = datos.get("sender") or {}
    insignias = {(b or {}).get("type") for b in ((autor.get("identity") or {}).get("badges") or [])}
    if not autor.get("id") or int(autor["id"]) == mi_id:
        return
    MENSAJES.append({"plataforma": "kick", "id": int(autor["id"]), "usuario": autor.get("username") or autor.get("slug") or "",
                     "texto": datos.get("content") or "", "cuando": time.time(),
                     "protegido": bool(insignias & {"broadcaster", "moderator"})})


class OyenteKick(threading.Thread):
    """Hilo que mantiene la conexión al chat de Kick y se reconecta solo si se corta."""

    def __init__(self):
        super().__init__(daemon=True, name="chat-kick")

    def run(self):
        espera = 5
        while True:
            try:
                self._conectar()
                espera = 5
            except Exception as e:  # noqa: BLE001
                ESTADO.update(conectado=False, error=str(e)[:200])
                print(f"[chat] Kick: {e}")
            time.sleep(espera)
            espera = min(espera * 2, 300)

    def _conectar(self):
        import websocket  # websocket-client

        from kick import Kick
        canal = Kick().canal()
        mi_id = int(canal.get("broadcaster_user_id") or 0)
        sala = sala_de_chat(canal["slug"])
        ws = websocket.create_connection(_url_pusher(*clave_pusher()), timeout=30)
        try:
            ws.send(json.dumps({"event": "pusher:subscribe", "data": {"auth": "", "channel": f"chatrooms.{sala}.v2"}}))
            while True:
                try:
                    crudo = ws.recv()
                except websocket.WebSocketTimeoutException:
                    ws.send(json.dumps({"event": "pusher:ping", "data": {}}))
                    continue
                if not crudo:
                    raise ConnectionError("Kick cerró la conexión del chat")
                m = json.loads(crudo)
                ev = m.get("event", "")
                if ev == "pusher:ping":
                    ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                elif ev == "pusher_internal:subscription_succeeded":
                    ESTADO.update(conectado=True, error=None, sala=sala, desde=time.time())
                    print(f"[chat] Escuchando el chat de Kick ({canal['slug']}).")
                elif ev == "pusher:error":
                    datos = m.get("data") or {}
                    if isinstance(datos, str):
                        datos = json.loads(datos or "{}")
                    if datos.get("code") == 4001 and clave_pusher(renovar=True):
                        raise ConnectionError("Kick cambió la clave del chat; me reconecto con la nueva")
                    raise ConnectionError(f"Kick no deja leer el chat ({datos.get('message') or datos}). "
                                          "Moderar sigue funcionando con el nombre exacto.")
                elif ev == "App\\Events\\ChatMessageEvent":
                    datos = m.get("data")
                    _agregar(json.loads(datos) if isinstance(datos, str) else (datos or {}), mi_id)
        finally:
            ESTADO["conectado"] = False
            ws.close()


_oyente = None


def empezar():
    """Arranca el oyente de Kick una sola vez (si Kick está conectado)."""
    global _oyente
    if _oyente is None and config.CHAT_KICK and config.KICK_TOKENS.exists():
        _oyente = OyenteKick()
        _oyente.start()
    return _oyente


def recientes_kick(minutos=90):
    limite = time.time() - minutos * 60
    return [m for m in list(MENSAJES) if m["cuando"] >= limite]


if __name__ == "__main__":  # prueba: python chat_vivo.py  (muestra lo que llega al chat de Kick)
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    empezar()
    visto = 0
    while True:
        time.sleep(1)
        todos = list(MENSAJES)
        for m in todos[visto:]:
            print(f"{m['usuario']}: {m['texto']}")
        visto = len(todos)
        if not ESTADO["conectado"] and ESTADO["error"]:
            print("…", ESTADO["error"])
            time.sleep(4)
