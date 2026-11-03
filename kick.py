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
