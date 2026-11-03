"""Actualiza Hogger en el servidor de Google Cloud con la última versión del repo bot-guild.

Lo ejecuta Nicolas con doble clic en conectar_todo.bat (o: python actualizar_hogger.py).
Sube el zip y servidor/desplegar_hogger.sh a la VM, y ese script hace copia de seguridad,
actualiza, reinicia y vuelve solo a la versión anterior si algo falla.
Todo queda anotado en data/actualizar_hogger.log.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_BOT = BASE / "_bot-guild"
URL_BOT = "https://github.com/Nicocs19/bot-guild"
VM = os.getenv("GCP_VM", "hogger")
LOG = BASE / "data" / "actualizar_hogger.log"


def escribir(texto):
    print(texto, end="", flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(texto)


def buscar_gcloud():
    encontrado = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if encontrado:
        return encontrado
    # recién instalado: puede que esta ventana todavía no lo tenga en el PATH
    for base in (os.getenv("LOCALAPPDATA"), os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles")):
        ruta = Path(base or "") / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"
        if base and ruta.exists():
            return str(ruta)
    return None


def correr(args, mostrar=True, cwd=None):
    """Corre un comando, muestra su salida en vivo y la guarda en el log. Devuelve (código, salida)."""
    if mostrar:
        escribir(f"\n$ {' '.join(str(a) for a in args)}\n")
    p = subprocess.Popen([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", cwd=cwd)
    salida = []
    for ch in iter(lambda: p.stdout.read(1), ""):
        salida.append(ch)
        if mostrar:
            escribir(ch)
    return p.wait(), "".join(salida)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    LOG.parent.mkdir(exist_ok=True)
    escribir(f"\n===== Actualizar Hogger {dt.datetime.now():%Y-%m-%d %H:%M} =====\n")

    gcloud = buscar_gcloud()
    git = shutil.which("git")
    if not gcloud or not git:
        escribir("❌ Falta " + ("gcloud" if not gcloud else "git") + " en esta PC.\nRESULTADO: ERROR\n")
        return 1

    escribir("📥 Bajando la última versión de Hogger...\n")
    if (REPO_BOT / ".git").exists():
        codigo, _ = correr([git, "-C", REPO_BOT, "pull", "--ff-only"])
    else:
        codigo, _ = correr([git, "clone", "--depth", "1", URL_BOT, REPO_BOT])
    zip_ = REPO_BOT / "Hogger_bot.zip"
    if codigo or not zip_.exists():
        escribir("❌ No pude bajar Hogger_bot.zip de GitHub.\nRESULTADO: ERROR\n")
        return 1

    _, proyecto = correr([gcloud, "config", "get-value", "project"], mostrar=False)
    proyecto = proyecto.strip().splitlines()[-1].strip() if proyecto.strip() else ""
    proyecto = os.getenv("GCP_PROYECTO") or proyecto
    _, lista = correr([gcloud, "compute", "instances", "list", f"--project={proyecto}",
                       f"--filter=name={VM}", "--format=json"], mostrar=False)
    try:
        zonas = [m["zone"].rsplit("/", 1)[-1] for m in json.loads(lista[lista.index("["):])]
    except ValueError:
        zonas = []
    zona = os.getenv("GCP_ZONA") or (zonas[0] if zonas else "")
    if not proyecto or not zona:
        escribir(f"❌ No encuentro la máquina «{VM}» en Google Cloud (proyecto «{proyecto}»).\n"
                 "   ¿Iniciaste sesión con la cuenta correcta? (gcloud auth login)\nRESULTADO: ERROR\n")
        return 1
    escribir(f"☁️  Servidor: {VM} ({zona}, proyecto {proyecto})\n")

    # Los dos archivos van juntos en una carpeta temporal y se suben por nombre (gcloud confunde "C:" con un servidor).
    # El script del servidor tiene que ir con saltos de línea de Linux.
    tmp = Path(tempfile.mkdtemp())
    shutil.copy2(zip_, tmp / "Hogger_bot.zip")
    (tmp / "desplegar_hogger.sh").write_bytes(
        (BASE / "servidor" / "desplegar_hogger.sh").read_bytes().replace(b"\r\n", b"\n"))
    comunes = [f"--zone={zona}", f"--project={proyecto}", "--quiet", "--strict-host-key-checking=no"]

    escribir("📤 Subiendo la versión nueva al servidor (la primera vez crea una llave de acceso, tarda un poco)...\n")
    codigo, _ = correr([gcloud, "compute", "scp", "Hogger_bot.zip", "desplegar_hogger.sh", f"{VM}:/tmp/", *comunes],
                       cwd=tmp)
    if codigo:
        escribir("❌ No pude subir los archivos al servidor. Hogger sigue como estaba.\nRESULTADO: ERROR\n")
        return 1

    escribir("🔄 Actualizando Hogger (con copia de seguridad)...\n")
    codigo, salida = correr([gcloud, "compute", "ssh", VM, *comunes,
                             "--command=sudo bash /tmp/desplegar_hogger.sh /tmp/Hogger_bot.zip"])
    shutil.rmtree(tmp, ignore_errors=True)
    if "RESULTADO: OK" in salida:
        escribir("\n✅ Hogger actualizado y en línea.\n")
        return 0
    if "RESULTADO:" not in salida:
        escribir("\n❌ Se cortó la conexión con el servidor antes de terminar.\nRESULTADO: ERROR\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
