"""Conecta El Cerebro con tu canal de YouTube (se ejecuta UNA vez)."""
import sys

import config
from youtube import SCOPES, YouTube


def main():
    if not config.YOUTUBE_CLIENT_SECRET.exists():
        sys.exit(f"Falta {config.YOUTUBE_CLIENT_SECRET.name}. Descárgalo de Google Cloud (ver README, paso YouTube).")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flujo = InstalledAppFlow.from_client_secrets_file(str(config.YOUTUBE_CLIENT_SECRET), SCOPES)
    cred = flujo.run_local_server(port=0, prompt="consent", access_type="offline",
                                  success_message="Listo, ya puedes cerrar esta pestaña y volver al Cerebro.")
    config.YOUTUBE_TOKEN.write_text(cred.to_json(), encoding="utf-8")
    yt = YouTube()
    print(f"\nConectado al canal de YouTube: {yt.canal()}")
    d = yt.directo_actual()
    print(f"Directo actual o programado: {d['snippet']['title']!r}" if d else "No hay directo activo ni programado ahora mismo.")


if __name__ == "__main__":
    main()
