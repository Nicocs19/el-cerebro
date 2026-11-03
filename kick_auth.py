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
from kick import TOKEN_URL, Kick

SCOPES = "user:read channel:read channel:write"


def main():
    if not config.KICK_CLIENT_ID or not config.KICK_CLIENT_SECRET:
        sys.exit("Rellena KICK_CLIENT_ID y KICK_CLIENT_SECRET en .env primero.")

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
            msg = "Listo, ya puedes cerrar esta pestana." if ok else f"Error: {resultado['error']}"
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
        sys.exit(f"Kick rechazo el codigo ({r.status_code}): {r.text[:300]}")
    Kick.guardar_tokens(r.json())

    canal = Kick().canal()
    print(f"\nConectado al canal: {canal.get('slug')}")
    print(f"Titulo actual: {canal.get('stream_title')!r}")
    cat = canal.get("category") or {}
    if cat:
        print(f"Categoria actual: {cat.get('name')} (id {cat.get('id')})")


if __name__ == "__main__":
    main()
