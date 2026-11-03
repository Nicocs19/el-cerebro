"""Cliente minimo de la API publica oficial de Kick (https://docs.kick.com)."""
import json
import time

import requests

import config

API = "https://api.kick.com/public/v1"
TOKEN_URL = "https://id.kick.com/oauth/token"


class KickError(RuntimeError):
    pass


class Kick:
    def __init__(self):
        self.tokens = None
        if config.KICK_TOKENS.exists():
            self.tokens = json.loads(config.KICK_TOKENS.read_text(encoding="utf-8"))

    # ---------- tokens ----------
    @staticmethod
    def guardar_tokens(data):
        data = dict(data)
        data["expires_at"] = time.time() + int(float(data.get("expires_in") or 3600))
        config.KICK_TOKENS.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def _refrescar(self):
        if not self.tokens or not self.tokens.get("refresh_token"):
            raise KickError("No hay sesion de Kick. Ejecuta conectar_kick.bat")
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": config.KICK_CLIENT_ID,
            "client_secret": config.KICK_CLIENT_SECRET,
            "refresh_token": self.tokens["refresh_token"],
        }, timeout=15)
        if r.status_code != 200:
            raise KickError(f"No se pudo renovar el token ({r.status_code}): {r.text[:300]}. "
                            "Vuelve a ejecutar conectar_kick.bat")
        nuevo = r.json()
        nuevo.setdefault("refresh_token", self.tokens["refresh_token"])
        self.tokens = self.guardar_tokens(nuevo)

    def _token(self):
        if not self.tokens:
            raise KickError("No hay sesion de Kick. Ejecuta conectar_kick.bat")
        if time.time() > self.tokens.get("expires_at", 0) - 120:
            self._refrescar()
        return self.tokens["access_token"]

    def _pedir(self, metodo, ruta, **kw):
        for intento in range(2):
            h = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
            r = requests.request(metodo, API + ruta, headers=h, timeout=15, **kw)
            if r.status_code == 401 and intento == 0:
                self._refrescar()
                continue
            if r.status_code == 403:
                raise KickError(f"Kick no dio permiso ({r.text[:200]}). Si era moderar o escribir en el chat, "
                                "doble clic en conectar_kick.bat para darle ese permiso.")
            if r.status_code >= 400:
                raise KickError(f"Kick respondio {r.status_code}: {r.text[:300]}")
            return r
        raise KickError("Kick rechazo el token dos veces")

    # ---------- canal ----------
    def canal(self):
        """Sin parametros devuelve el canal del usuario autorizado."""
        datos = self._pedir("GET", "/channels").json().get("data") or []
        if not datos:
            raise KickError("Kick no devolvio ningun canal")
        return datos[0]

    def titulo_actual(self):
        return self.canal().get("stream_title") or ""

    def cambiar_titulo(self, titulo, categoria_id=None):
        cuerpo = {"stream_title": titulo}
        cat = categoria_id or config.KICK_CATEGORY_ID
        if cat:
            cuerpo["category_id"] = int(cat)
        self._pedir("PATCH", "/channels", json=cuerpo)

    # ---------- permisos ----------
    def faltan_permisos(self, *scopes):
        """Permisos que el token de Kick no tiene (los tokens viejos sin lista no se pueden revisar: se intenta igual)."""
        dado = (self.tokens or {}).get("scope")
        if dado is None:
            return []
        dado = set(str(dado).replace(",", " ").split())
        return [s for s in scopes if s not in dado]

    def _exigir(self, *scopes):
        if self.faltan_permisos(*scopes):
            raise KickError("A El Cerebro le falta el permiso de Kick para moderar y escribir en el chat. "
                            "Doble clic en conectar_kick.bat (te guía paso a paso).")

    def mi_id(self):
        if not getattr(self, "_mi_id", None):
            self._mi_id = int(self.canal()["broadcaster_user_id"])
        return self._mi_id

    # ---------- usuarios ----------
    def usuario(self, nombre):
        """Busca un usuario de Kick por su nombre exacto (cada usuario tiene un canal con ese nombre)."""
        base = str(nombre or "").strip().lstrip("@").lower().replace(" ", "")
        if not base:
            return None
        for slug in dict.fromkeys([base, base.replace("_", "-")]):
            try:
                datos = self._pedir("GET", "/channels", params={"slug": slug}).json().get("data") or []
            except KickError:
                continue
            if datos and datos[0].get("broadcaster_user_id"):
                return {"id": int(datos[0]["broadcaster_user_id"]), "usuario": datos[0].get("slug") or slug}
        return None

    # ---------- moderación y chat ----------
    def banear(self, user_id, minutos=None, motivo=""):
        """Sin minutos es para siempre; con minutos es un silencio temporal (Kick admite de 1 minuto a 7 días)."""
        self._exigir("moderation:ban")
        cuerpo = {"broadcaster_user_id": self.mi_id(), "user_id": int(user_id)}
        if minutos:
            cuerpo["duration"] = max(1, min(10080, int(minutos)))
        if motivo:
            cuerpo["reason"] = str(motivo)[:100]
        self._pedir("POST", "/moderation/bans", json=cuerpo)

    def desbanear(self, user_id):
        self._exigir("moderation:ban")
        self._pedir("DELETE", "/moderation/bans", json={"broadcaster_user_id": self.mi_id(), "user_id": int(user_id)})

    def escribir(self, texto):
        """Escribe en el chat de tu canal con tu cuenta."""
        self._exigir("chat:write")
        r = self._pedir("POST", "/chat", json={"type": "user", "content": str(texto)[:500],
                                               "broadcaster_user_id": self.mi_id()})
        return ((r.json() or {}).get("data") or {}).get("message_id")
