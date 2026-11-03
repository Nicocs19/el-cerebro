"""Manda órdenes a Hogger a través de su buzón privado en Discord.

El Cerebro escribe en #cerebro con el token de Hogger (el autor es el propio
bot), Hogger ejecuta la orden en Google Cloud y responde al mensaje con un JSON.
Solo usa la API REST de Discord: no abre una segunda conexión del bot.
"""
import json
import time

import requests

import config

API = "https://discord.com/api/v10"
MARCA = "🧠 orden"


class HoggerError(RuntimeError):
    pass


class Hogger:
    def __init__(self):
        self._canal = None

    @staticmethod
    def disponible():
        return bool(config.HOGGER_TOKEN and config.HOGGER_GUILD_ID)

    def _h(self):
        return {"Authorization": f"Bot {config.HOGGER_TOKEN}",
                "User-Agent": "DiscordBot (https://github.com/Nicocs19/bot-guild, 2.0) ElCerebro"}

    def _pedir(self, metodo, ruta, **kw):
        for _ in range(3):
            r = requests.request(metodo, API + ruta, headers=self._h(), timeout=15, **kw)
            if r.status_code == 429:  # límite de Discord: esperar lo que pide
                time.sleep(float(r.json().get("retry_after", 1)) + 0.2)
                continue
            if r.status_code == 401:
                raise HoggerError("Discord rechazó el token de Hogger (HOGGER_TOKEN en .env).")
            if r.status_code >= 400:
                raise HoggerError(f"Discord respondió {r.status_code}: {r.text[:200]}")
            return r.json() if r.content else None
        raise HoggerError("Discord está limitando las peticiones; prueba en unos segundos.")

    def canal_buzon(self):
        if self._canal:
            return self._canal
        for c in self._pedir("GET", f"/guilds/{config.HOGGER_GUILD_ID}/channels"):
            if c.get("type") == 0 and c.get("name") == config.CANAL_CEREBRO:
                self._canal = c["id"]
                return self._canal
        raise HoggerError(f"No existe #{config.CANAL_CEREBRO} en el servidor. Actualiza Hogger o crea el canal privado.")

    def enviar(self, orden, espera=25):
        """Publica la orden y espera la respuesta de Hogger. Devuelve el dict de resultado."""
        if not self.disponible():
            raise HoggerError("Falta HOGGER_TOKEN o HOGGER_GUILD_ID en .env.")
        orden = {k: v for k, v in orden.items() if v not in (None, "")}
        contenido = f"{MARCA}\n```json\n{json.dumps(orden, ensure_ascii=False)}\n```"
        if len(contenido) > 2000:
            raise HoggerError("La orden es demasiado larga para Discord (máx. 2000 caracteres).")
        canal = self.canal_buzon()
        msg = self._pedir("POST", f"/channels/{canal}/messages",
                          json={"content": contenido, "allowed_mentions": {"parse": []}})
        limite = time.time() + espera
        while time.time() < limite:
            time.sleep(1.2)
            for m in self._pedir("GET", f"/channels/{canal}/messages", params={"after": msg["id"], "limit": 20}):
                if (m.get("message_reference") or {}).get("message_id") == msg["id"]:
                    return self._resultado(m["content"])
        raise HoggerError("Hogger no respondió en 25 s. ¿Está encendido en Google Cloud y actualizado con el buzón?")

    @staticmethod
    def _resultado(texto):
        try:
            bloque = texto.split("```json", 1)[1].split("```", 1)[0]
            return json.loads(bloque)
        except (IndexError, json.JSONDecodeError):
            return {"ok": texto.startswith("✅"), "resumen": texto.splitlines()[0][:200], "error": texto[:200]}

    def estado(self):
        return self.enviar({"accion": "estado"}, espera=15)
