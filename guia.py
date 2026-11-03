"""Ayudas para los asistentes de conexión (Kick, YouTube): pasos claros, portapapeles y .env."""
import re
import shutil
import subprocess
import os
from pathlib import Path

import config


def paso(n, total, texto):
    print(f"\n━━━━━━━━ Paso {n} de {total} ━━━━━━━━\n{texto.strip()}\n")


def copiar(texto):
    """Pone un texto en el portapapeles de Windows (para pegarlo con Ctrl+V)."""
    try:
        subprocess.run("clip", input=texto, text=True, check=True, shell=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def esperar_enter(texto="Cuando termines, apretá Enter acá..."):
    input(f"👉 {texto}")


def esperar_enter_oculto(texto="Apretá Enter acá..."):
    """Espera Enter SIN mostrar lo que se escriba o pegue: si pegás una clave acá, no queda a la vista."""
    print(f"👉 {texto}", end="", flush=True)
    try:
        import msvcrt
    except ImportError:
        import getpass
        getpass.getpass("")
        return
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            print()
            return
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()


def guardar_env(**valores):
    """Cambia o agrega CLAVE=valor en el .env sin tocar lo demás y actualiza config."""
    ruta = config.BASE / ".env"
    texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    for clave, valor in valores.items():
        patron = re.compile(rf"^{re.escape(clave)}=.*$", re.M)
        if patron.search(texto):
            texto = patron.sub(lambda _, v=valor, c=clave: f"{c}={v}", texto, count=1)
        else:
            texto = texto.rstrip("\n") + f"\n{clave}={valor}\n"
        setattr(config, clave, valor)
    ruta.write_text(texto, encoding="utf-8")


def gcloud():
    encontrado = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if encontrado:
        return encontrado
    for base in (os.getenv("LOCALAPPDATA"), os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles")):
        ruta = Path(base or "") / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"
        if base and ruta.exists():
            return str(ruta)
    return None
