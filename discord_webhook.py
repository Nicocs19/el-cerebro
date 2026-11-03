"""Publica y borra anuncios en Discord mediante un webhook del canal."""
import requests

import config


def enviar(texto):
    """Publica el anuncio y devuelve el ID del mensaje (para poder borrarlo)."""
    if not config.DISCORD_WEBHOOK_URL:
        raise RuntimeError("Falta DISCORD_WEBHOOK_URL en .env")
    contenido = f"{config.DISCORD_MENTION}\n{texto}" if config.DISCORD_MENTION else texto
    payload = {
        "content": contenido[:2000],
        "allowed_mentions": {"parse": ["everyone", "roles", "users"]},
    }
    if config.DISCORD_NAME:
        payload["username"] = config.DISCORD_NAME
    r = requests.post(config.DISCORD_WEBHOOK_URL, params={"wait": "true"}, json=payload, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"Discord respondio {r.status_code}: {r.text[:300]}")
    return r.json()["id"]


def borrar(mensaje_id):
    r = requests.delete(f"{config.DISCORD_WEBHOOK_URL}/messages/{mensaje_id}", timeout=15)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Discord respondio {r.status_code}: {r.text[:300]}")
