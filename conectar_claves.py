"""Copia las claves de Hogger y de OBS al .env de El Cerebro, sin mostrarlas nunca.

Lo ejecuta Nicolas con doble clic en conectar_todo.bat (o: python conectar_claves.py [ruta del .env de Hogger]).
- Hogger: lee DISCORD_TOKEN y GUILD_ID del .env del bot en esta PC y comprueba con Discord que funcionan.
- OBS: lee la contraseña del servidor WebSocket de la configuración de OBS.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"
API = "https://discord.com/api/v10"
CANDIDATOS = [Path(r"E:\Proyecto Mr. H\Bot Discord\Hogger_bot\bot\.env")]
BUSCAR_EN = [Path(r"E:\Proyecto Mr. H")]


def leer_env(ruta):
    vals = {}
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            vals[k.strip().upper()] = v.strip().strip('"').strip("'")
    return vals


def poner(texto, clave, valor):
    """Cambia CLAVE=... en el texto del .env, o la agrega al final."""
    patron = re.compile(rf"^{re.escape(clave)}=.*$", re.M)
    if patron.search(texto):
        return patron.sub(lambda _: f"{clave}={valor}", texto, count=1)
    return texto.rstrip("\n") + f"\n{clave}={valor}\n"


def discord(token, ruta):
    r = requests.get(API + ruta, headers={"Authorization": f"Bot {token}"}, timeout=15)
    return r.status_code, (r.json() if r.content else {})


def _rutas():
    yield from (Path(a) for a in sys.argv[1:])
    yield from CANDIDATOS
    for carpeta in BUSCAR_EN:          # solo se busca si las rutas conocidas fallan
        if carpeta.exists():
            yield from carpeta.rglob(".env")


def buscar_hogger():
    vistos = set()
    for ruta in _rutas():
        if ruta in vistos or not ruta.is_file():
            continue
        vistos.add(ruta)
        vals = leer_env(ruta)
        token = vals.get("DISCORD_TOKEN") or vals.get("HOGGER_TOKEN") or ""
        if len(token) < 50:
            continue
        estado, yo = discord(token, "/users/@me")
        if estado == 200:
            return token, (vals.get("GUILD_ID") or vals.get("HOGGER_GUILD_ID") or "").strip(), yo.get("username", "?"), ruta
        print(f"   (la clave de {ruta} ya no sirve: Discord respondió {estado})")
    return None


def elegir_servidor(token, guild_id):
    estado, servidores = discord(token, "/users/@me/guilds")
    if estado != 200 or not servidores:
        return None, None
    if guild_id:
        for s in servidores:
            if s["id"] == guild_id:
                return s["id"], s["name"]
    if len(servidores) == 1:
        return servidores[0]["id"], servidores[0]["name"]
    print("   Hogger está en varios servidores:")
    for i, s in enumerate(servidores, 1):
        print(f"     {i}. {s['name']}")
    n = input("   Escribí el número del servidor de la guild y Enter: ").strip()
    s = servidores[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(servidores) else servidores[0]
    return s["id"], s["name"]


def obs():
    ruta = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
    if not ruta.is_file():
        return None
    c = json.loads(ruta.read_text(encoding="utf-8"))
    if not c.get("server_enabled", False):
        print("   ⚠️  El servidor WebSocket de OBS está apagado: en OBS, Herramientas > Ajustes del servidor WebSocket > Activar.")
    clave = c.get("server_password", "") if c.get("auth_required", True) else ""
    return clave, int(c.get("server_port", 4455))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if not ENV.exists():
        print("❌ No encuentro el archivo .env de El Cerebro. Ejecutá primero instalar.bat.")
        return 1
    texto = ENV.read_text(encoding="utf-8")
    bien = True

    print("🔑 Hogger (Discord)...")
    h = buscar_hogger()
    if not h:
        print("❌ No encontré una clave de Hogger que funcione en esta PC.")
        bien = False
    else:
        token, guild_id, nombre, ruta = h
        gid, gnombre = elegir_servidor(token, guild_id)
        if not gid:
            print("❌ La clave funciona, pero no encuentro el servidor de la guild.")
            bien = False
        else:
            texto = poner(texto, "HOGGER_TOKEN", token)
            texto = poner(texto, "HOGGER_GUILD_ID", gid)
            print(f"✅ Hogger conectado: bot «{nombre}», servidor «{gnombre}» (clave tomada de {ruta.parent}).")

    print("🎥 OBS...")
    o = obs()
    if o is None:
        print("⚠️  No encontré la configuración de OBS (¿está instalado?). Las miniaturas no podrán sacar captura.")
    else:
        clave, puerto = o
        texto = poner(texto, "OBS_PASSWORD", clave)
        texto = poner(texto, "OBS_PORT", str(puerto))
        print(f"✅ OBS conectado (puerto {puerto}).")

    ENV.write_text(texto, encoding="utf-8")
    print("💾 Guardado en .env (las claves no se muestran ni se suben a internet).")
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
