"""Conecta El Cerebro con tu cuenta de Kick (OAuth 2.1 + PKCE). Se ejecuta UNA vez."""
import base64
import hashlib
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

import config
import guia
from kick import TOKEN_URL, Kick

SCOPES = "user:read channel:read channel:write"
DEVELOPER = "https://kick.com/settings/developer"


def crear_app():
    """Guía para crear la app de Kick (una sola vez) y guarda su Client ID y Client Secret."""
    print("Vamos a crear la «app» de Kick que le da permiso a El Cerebro para cambiar tu título.")
    guia.paso(1, 3, f"""
Se abre Kick en tu navegador ({DEVELOPER}). Si no estás con tu sesión, iniciá sesión.
Si Kick te pide activar la verificación en dos pasos (2FA), activala primero: Kick la exige para esto.""")
    webbrowser.open(DEVELOPER)
    guia.esperar_enter("Cuando veas la página «Developer» de Kick, apretá Enter acá...")
    guia.copiar(config.KICK_REDIRECT_URI)
    guia.paso(2, 3, f"""
Tocá «Create App» (crear app) y completá:
   Nombre (App name):          El Cerebro
   Descripción (Description):  Asistente de mi stream
   Redirect URL:               {config.KICK_REDIRECT_URI}
                               (ya está copiada: hacé clic en el campo y apretá Ctrl+V)
   Permisos (Scopes):          marcá los de leer usuario, leer canal y escribir/actualizar canal
                               (user:read, channel:read, channel:write). Si no sabés cuál es cuál, marcá todos.
Después guardá (Create / Save).""")
    guia.esperar_enter()
    guia.paso(3, 3, """
Kick te muestra el «Client ID» y el «Client Secret» de la app.
Copiá cada uno y pegalo acá (clic derecho o Ctrl+V), apretando Enter después de cada uno.
No hagas este paso con el stream en vivo: el Client Secret es privado.""")
    cid = input("Client ID: ").strip()
    secreto = input("Client Secret: ").strip()
    if not cid or not secreto or " " in cid or " " in secreto:
        sys.exit("❌ Eso no parece un Client ID o Client Secret. Volvé a abrir conectar_kick.bat.")
    guia.guardar_env(KICK_CLIENT_ID=cid, KICK_CLIENT_SECRET=secreto)
    print("✅ Guardado. Ahora falta autorizar la app con tu cuenta.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if not config.KICK_CLIENT_ID or not config.KICK_CLIENT_SECRET:
        crear_app()
    print("\nSe abre Kick para autorizar: tocá «Allow» / «Autorizar».")

    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    redirect = urlparse(config.KICK_REDIRECT_URI)
    resultado = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path != redirect.path:
                self.send_response(404)
                self.end_headers()
                return
            q = parse_qs(url.query)
            ok = q.get("state", [""])[0] == state and "code" in q
            resultado["code"] = q.get("code", [None])[0] if ok else None
            resultado["error"] = None if ok else (q.get("error", ["state invalido"])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Listo, ya podés cerrar esta pestaña y volver a la ventana negra." if ok else f"Error: {resultado['error']}"
            self.wfile.write(f"<h2>El Cerebro + Kick</h2><p>{msg}</p>".encode())
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", redirect.port or 80), Handler)
    url = "https://id.kick.com/oauth/authorize?" + urlencode({
        "response_type": "code",
        "client_id": config.KICK_CLIENT_ID,
        "redirect_uri": config.KICK_REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    print("Abriendo el navegador para autorizar en Kick...\nSi no se abre, copia esta URL:\n" + url)
    webbrowser.open(url)
    server.serve_forever()

    if not resultado.get("code"):
        sys.exit(f"Autorizacion cancelada o fallida: {resultado.get('error')}")

    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": config.KICK_CLIENT_ID,
        "client_secret": config.KICK_CLIENT_SECRET,
        "redirect_uri": config.KICK_REDIRECT_URI,
        "code_verifier": verifier,
        "code": resultado["code"],
    }, timeout=15)
    if r.status_code != 200:
        if r.status_code in (400, 401) and "client" in r.text.lower():
            guia.guardar_env(KICK_CLIENT_ID="", KICK_CLIENT_SECRET="")
            sys.exit("❌ Kick dice que el Client ID o el Client Secret no son correctos. Los borré: "
                     "volvé a abrir conectar_kick.bat y pegalos de nuevo.")
        sys.exit(f"Kick rechazo el codigo ({r.status_code}): {r.text[:300]}")
    Kick.guardar_tokens(r.json())

    canal = Kick().canal()
    print(f"\n✅ Kick conectado al canal: {canal.get('slug')}")
    print(f"Titulo actual: {canal.get('stream_title')!r}")
    cat = canal.get("category") or {}
    if cat:
        print(f"Categoria actual: {cat.get('name')} (id {cat.get('id')})")


if __name__ == "__main__":
    main()
