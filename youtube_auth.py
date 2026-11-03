"""Conecta El Cerebro con tu canal de YouTube (se ejecuta UNA vez): python youtube_auth.py

Si todavía no existe client_secret.json, guía paso a paso para crearlo en Google Cloud
(activa la API de YouTube solo y recoge el archivo descargado de la carpeta Descargas).
"""
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import config
import guia
from youtube import SCOPES, YouTube


def proyecto_gcloud(gc):
    try:
        out = subprocess.run([gc, "config", "get-value", "project"], capture_output=True, text=True, timeout=60).stdout
        return out.strip().splitlines()[-1].strip() if out.strip() else ""
    except Exception:  # noqa: BLE001
        return ""


def activar_api(gc, proyecto):
    print("Activando la API de YouTube en Google Cloud...")
    r = subprocess.run([gc, "services", "enable", "youtube.googleapis.com", f"--project={proyecto}"],
                       capture_output=True, text=True, timeout=300)
    print("✅ API de YouTube activada." if r.returncode == 0 else
          "⚠️  No pude activarla sola; en el paso 1 te digo cómo.")
    return r.returncode == 0


def buscar_descargado(desde):
    carpetas = [Path.home() / "Downloads", Path.home() / "Descargas", Path.home() / "Desktop", config.BASE]
    candidatos = []
    for c in carpetas:
        if c.exists():
            candidatos += [f for f in c.glob("client_secret*.json") if f.stat().st_mtime >= desde]
    return max(candidatos, key=lambda f: f.stat().st_mtime) if candidatos else None


def crear_client_secret():
    inicio = time.time() - 5
    gc = guia.gcloud()
    proyecto = proyecto_gcloud(gc) if gc else ""
    api_ok = activar_api(gc, proyecto) if proyecto else False
    q = f"?project={proyecto}" if proyecto else ""
    print("\nVamos a crear el permiso para que El Cerebro cambie el título de tus directos en YouTube.")
    print("Se hace una sola vez, en la página de Google Cloud donde ya tenés a Hogger.")

    guia.copiar("El Cerebro")
    extra = "" if api_ok else (f"\nAntes: abrí https://console.cloud.google.com/apis/library/youtube.googleapis.com{q} "
                               "y tocá «Habilitar».")
    guia.paso(1, 4, f"""
Se abre Google Cloud. Si te pide la cuenta, usá la de Hogger.{extra}
Si ves el botón «Comenzar» (Get started), tocálo y completá:
   Nombre de la app:          El Cerebro   (ya está copiado: Ctrl+V)
   Correo de asistencia:      el tuyo
   Público (Audience):        Externo (External)
   Información de contacto:   tu correo
   Aceptá la política y tocá «Crear».
Si en vez de «Comenzar» ves un resumen, ya estaba hecho: seguí al paso 2.""")
    webbrowser.open(f"https://console.cloud.google.com/auth/overview{q}")
    guia.esperar_enter()

    guia.paso(2, 4, """
Ahora se abre «Público» (Audience). Tocá «Publicar app» (Publish app) y confirmá.
Así la conexión no se corta cada 7 días. Si ya dice «En producción», está listo.""")
    webbrowser.open(f"https://console.cloud.google.com/auth/audience{q}")
    guia.esperar_enter()

    guia.paso(3, 4, """
Ahora se abre «Crear cliente». Completá:
   Tipo de aplicación:   App de escritorio (Desktop app)
   Nombre:               El Cerebro
Tocá «Crear». En la ventana que aparece, tocá «Descargar JSON».
Yo lo busco solo en tu carpeta Descargas: no tenés que moverlo.""")
    webbrowser.open(f"https://console.cloud.google.com/auth/clients/create{q}")
    print("Esperando el archivo descargado (hasta 10 minutos)...")
    for _ in range(300):
        archivo = buscar_descargado(inicio)
        if archivo:
            break
        time.sleep(2)
    else:
        sys.exit("❌ No vi el archivo descargado. Volvé a abrir conectar_youtube.bat y repetí el paso 3.")
    time.sleep(1)
    shutil.move(str(archivo), str(config.YOUTUBE_CLIENT_SECRET))
    print(f"✅ Archivo recibido y guardado como {config.YOUTUBE_CLIENT_SECRET.name}.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if not config.YOUTUBE_CLIENT_SECRET.exists():
        crear_client_secret()
    guia.paso(4, 4, """
Se abre Google para dar el permiso:
   1. Elegí la cuenta de tu CANAL de YouTube (si tenés varios canales, elegí el del stream).
   2. Si dice «Google no verificó esta app»: tocá «Configuración avanzada» y después «Ir a El Cerebro».
      Es normal: la app es tuya y solo la usás vos.
   3. Tocá «Continuar» / «Permitir».""")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flujo = InstalledAppFlow.from_client_secrets_file(str(config.YOUTUBE_CLIENT_SECRET), SCOPES)
    cred = flujo.run_local_server(port=0, prompt="consent", access_type="offline",
                                  success_message="Listo, ya podés cerrar esta pestaña y volver a la ventana negra.")
    config.YOUTUBE_TOKEN.write_text(cred.to_json(), encoding="utf-8")
    yt = YouTube()
    print(f"\n✅ YouTube conectado al canal: {yt.canal()}")
    d = yt.directo_actual()
    print(f"Directo actual o programado: {d['snippet']['title']!r}" if d else "No hay directo activo ni programado ahora mismo.")


if __name__ == "__main__":
    main()
