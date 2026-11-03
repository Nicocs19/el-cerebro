"""YouTube Data API v3: título, descripción y miniatura del directo."""
import config

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YoutubeError(RuntimeError):
    pass


def credenciales():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not config.YOUTUBE_TOKEN.exists():
        raise YoutubeError("YouTube no está conectado. Ejecuta conectar_youtube.bat")
    c = Credentials.from_authorized_user_file(str(config.YOUTUBE_TOKEN), SCOPES)
    if not c.valid:
        if c.expired and c.refresh_token:
            try:
                c.refresh(Request())
            except Exception as e:  # noqa: BLE001
                raise YoutubeError(f"Google rechazó la renovación ({e}). Vuelve a ejecutar conectar_youtube.bat")
            config.YOUTUBE_TOKEN.write_text(c.to_json(), encoding="utf-8")
        else:
            raise YoutubeError("La sesión de YouTube caducó. Ejecuta conectar_youtube.bat")
    return c


class YouTube:
    def __init__(self):
        from googleapiclient.discovery import build
        self.api = build("youtube", "v3", credentials=credenciales(), cache_discovery=False)

    def canal(self):
        items = self.api.channels().list(part="snippet", mine=True).execute().get("items", [])
        return items[0]["snippet"]["title"] if items else None

    def directo_actual(self):
        """El directo en curso; si no hay, el próximo programado (incluye la emisión fija de 'Transmitir ahora')."""
        for estado in ("active", "upcoming"):
            r = self.api.liveBroadcasts().list(part="id,snippet,status", broadcastStatus=estado,
                                               broadcastType="all", maxResults=5).execute()
            if r.get("items"):
                return r["items"][0]
        return None

    def _video(self, video_id=None):
        vid = video_id or (self.directo_actual() or {}).get("id")
        if not vid:
            raise YoutubeError("No hay ningún directo activo ni programado en YouTube.")
        items = self.api.videos().list(part="snippet", id=vid).execute().get("items", [])
        if not items:
            raise YoutubeError("YouTube no encontró el vídeo del directo.")
        return vid, items[0]["snippet"]

    def titulo_actual(self):
        return self._video()[1]["title"]

    def cambiar_titulo(self, titulo, descripcion=None, video_id=None):
        vid, sn = self._video(video_id)
        anterior = sn["title"]
        titulo = titulo.replace("<", "").replace(">", "")[:100]
        nuevo = {"title": titulo, "categoryId": sn.get("categoryId") or config.YOUTUBE_CATEGORY_ID,
                 "description": sn.get("description", "") if descripcion is None else descripcion[:5000]}
        for k in ("tags", "defaultLanguage", "defaultAudioLanguage"):
            if sn.get(k):
                nuevo[k] = sn[k]
        self.api.videos().update(part="snippet", body={"id": vid, "snippet": nuevo}).execute()
        return anterior

    def subir_miniatura(self, ruta, video_id=None):
        from googleapiclient.http import MediaFileUpload
        vid, _ = self._video(video_id)
        self.api.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(ruta), mimetype="image/jpeg")).execute()
        return vid
