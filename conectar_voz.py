"""Conecta la voz de El Cerebro con tu cuenta de ElevenLabs y te deja elegir la voz. Se ejecuta UNA vez."""
import re
import sys
import webbrowser

import numpy as np
import requests

import config
import guia
import jarvis

PAGINA = "https://elevenlabs.io/app/settings/api-keys"
BIBLIOTECA = "https://elevenlabs.io/app/voice-library"
OPCIONES = [("Daniel", "británico, serio"),
            ("George", "británico, cálido"),
            ("Brian", "americano, grave")]
PRUEBA = "¡Hola, Mister H! Raid de Onyxia, el viernes a las 9 de la noche. ¿La publico?"


def tocar(pcm, tono=None):
    import sounddevice as sd
    audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0 * config.VOZ_VOLUMEN
    audio = jarvis.cambiar_tono(audio, config.VOZ_TONO if tono is None else tono)
    disp = config.VOZ_DISPOSITIVO
    sd.play(audio, jarvis.ELEVEN_SR, device=int(disp) if disp.isdigit() else (disp or None))
    sd.wait()


def pedir_oculto(texto):
    """Como input(), pero muestra asteriscos: la clave no queda a la vista (ni en una captura)."""
    print(texto, end="", flush=True)
    try:
        import msvcrt
    except ImportError:
        import getpass
        return getpass.getpass("").strip()
    letras = []
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            print()
            break
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\x00", "\xe0"):         # flechas y teclas especiales
            msvcrt.getwch()
            continue
        if ch == "\b":
            if letras:
                letras.pop()
                print("\b \b", end="", flush=True)
            continue
        if ch == "\x16":                    # Ctrl+V que la ventana no pegó sola
            import pyperclip
            pegado = (pyperclip.paste() or "").strip()
            letras.extend(pegado)
            print("*" * len(pegado), end="", flush=True)
            continue
        letras.append(ch)
        print("*", end="", flush=True)
    clave = limpiar_clave("".join(letras))
    if not CLAVE.fullmatch(clave or ""):          # Enter solo, o se pegó algo raro: uso lo que copiaste
        copiada = del_portapapeles()
        if copiada:
            print("(Uso la clave que copiaste.)")
            return copiada
    return clave


CLAVE = re.compile(r"sk_[A-Za-z0-9]{20,}")


def del_portapapeles():
    try:
        import pyperclip
        m = CLAVE.search(limpiar_clave(pyperclip.paste() or ""))
        return m.group(0) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def limpiar_clave(texto):
    """Deja solo la clave: algunas ventanas agregan marcas invisibles al pegar (ESC[200~ … ESC[201~)."""
    t = re.sub(r"\x1b\[[0-9;]*[~A-Za-z]", "", texto or "")
    t = re.sub(r"\[?20[01]~", "", t)
    m = CLAVE.search(t)
    return m.group(0) if m else re.sub(r"[^A-Za-z0-9_\-]", "", t)


def pedir_clave():
    guia.paso(1, 3, f"""
Se abre ElevenLabs en tu navegador ({PAGINA}). Si no estás con tu sesión, iniciá sesión.
(Si no ves esa página: tocá tu perfil, abajo a la izquierda, y después «API Keys».)
Tocá «Create API Key» (crear clave). De nombre poné: El Cerebro.
Si ves un interruptor «Restrict Key», dejalo apagado. Tocá «Create» y copiá la clave con el botón de copiar.
No hagas este paso con el stream en vivo: la clave es privada.""")
    webbrowser.open(PAGINA)
    for _ in range(3):
        clave = pedir_oculto("Copiá la clave con el botón de copiar y apretá Enter acá\n"
                             "(o pegala con clic derecho; se ven asteriscos): ")
        if not clave or len(clave) < 20:
            print("No encontré la clave. Copiala con el botón de copiar de ElevenLabs y apretá Enter.")
            continue
        print("Probando la clave…")
        try:
            jarvis.sintetizar_eleven("Hola.", jarvis.VOCES_DE_SERIE["daniel"], clave)
        except PermissionError as e:
            print(f"❌ ElevenLabs no aceptó la clave ({e}; me llegaron {len(clave)} letras, una clave entera tiene 51).\n"
                  "   Creá otra clave y copiala con el botón de copiar apenas aparece.")
            continue
        except requests.HTTPError as e:
            print(f"❌ ElevenLabs rechazó el pedido ({e.response.status_code}: {jarvis.motivo_eleven(e.response)}).")
            continue
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"❌ No pude hablar con ElevenLabs ({type(e).__name__}). ¿Hay internet?")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"❌ Algo falló al probar la clave ({type(e).__name__}: {str(e)[:120]}).")
            continue
        guia.guardar_env(ELEVEN_API_KEY=clave)
        print("✅ Clave guardada.")
        return clave
    sys.exit("No se guardó nada. Volvé a abrir conectar_voz.bat cuando quieras.")


def elegir_tono(voz_id, clave):
    """Voz de dibujito (más aguda y graciosa) o normal."""
    print("   Así suena normal…")
    tocar(jarvis.sintetizar_eleven(PRUEBA, voz_id, clave, velocidad=config.VOZ_VELOCIDAD), 0)
    print("   …y así de dibujito:")
    tocar(jarvis.sintetizar_eleven(PRUEBA, voz_id, clave, velocidad=config.VOZ_VELOCIDAD / 2 ** (4 / 12)), 4)
    r = input("\n¿Cuál querés? Escribí n (normal) o d (dibujito) y Enter: ").strip().lower()
    guia.guardar_env(VOZ_TONO="0" if r.startswith("n") else "4")


def tus_voces(clave):
    """Tus voces de ElevenLabs (las que agregaste de la biblioteca primero) y las de serie al final."""
    lista = []
    try:
        r = requests.get(f"{jarvis.ELEVEN_API}/voices", headers={"xi-api-key": clave}, timeout=15)
        voces = r.json().get("voices", []) if r.ok else []
    except requests.RequestException:
        voces = []
    for v in voces:
        if v.get("category") == "premade":
            continue
        et = v.get("labels") or {}
        como = ", ".join(x for x in (et.get("accent"), et.get("language"), et.get("gender"), et.get("description")) if x)
        lista.append((v.get("name", "?"), v["voice_id"], como or "tuya"))
    for nombre, como in OPCIONES:
        lista.append((nombre, jarvis.VOCES_DE_SERIE[nombre.lower()], f"de serie, {como}, habla español con acento"))
    return lista


def elegir_voz(clave):
    guia.paso(2, 3, f"""
Elegí la voz. Se abre la biblioteca de voces de ElevenLabs ({BIBLIOTECA}).
   1. Filtrá «Language: Spanish» (y si querés un acento: Latin American, Peruvian, Mexican, Spain…).
   2. Escuchalas con ▶ y en las que te gusten tocá «Add to my voices» (el +). Podés agregar varias.
Cuando termines (o si ya las agregaste), volvé acá.""")
    webbrowser.open(BIBLIOTECA)
    guia.esperar_enter("Apretá Enter para ver tus voces...")
    while True:
        voces = tus_voces(clave)
        print()
        for i, (nombre, _, como) in enumerate(voces, 1):
            print(f"   {i}. {nombre}  ({como})")
        r = input("\nEscribí el número de una voz para escucharla (o «a» para actualizar la lista) y Enter: ").strip().lower()
        if r == "a" or not r.isdigit() or not 1 <= int(r) <= len(voces):
            continue
        nombre, voz_id, _ = voces[int(r) - 1]
        try:
            tocar(jarvis.sintetizar_eleven(PRUEBA, voz_id, clave, velocidad=config.VOZ_VELOCIDAD), 0)
        except Exception as e:  # noqa: BLE001
            print(f"   (no pude reproducirla: {e})")
            continue
        if input(f"¿Te quedás con «{nombre}»? Escribí s (sí) o n (seguir escuchando) y Enter: ").strip().lower().startswith("s"):
            guia.guardar_env(ELEVEN_VOZ=voz_id)
            return nombre, voz_id


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("Vamos a darle a El Cerebro la voz de ElevenLabs (gasta muy pocos créditos: las frases repetidas no gastan).")
    clave = config.ELEVEN_API_KEY
    if clave:
        try:
            jarvis.sintetizar_eleven("Hola.", jarvis.VOCES_DE_SERIE["daniel"], clave)
            print("✅ Ya tenés la clave de ElevenLabs guardada y funciona.")
        except Exception:  # noqa: BLE001
            print("La clave guardada ya no funciona: vamos a poner una nueva.")
            clave = None
    if not clave:
        clave = pedir_clave()
    nombre, voz_id = elegir_voz(clave)
    try:
        elegir_tono(voz_id, clave)
    except Exception as e:  # noqa: BLE001
        print(f"(no pude reproducir la prueba: {e})")
    guia.paso(3, 3, f"""
Listo: El Cerebro va a hablar con la voz {nombre}.
Se escucha por tus parlantes o auriculares normales, así que tu stream también la oye
(si OBS captura el audio del escritorio).
Cerrá y volvé a abrir El Cerebro para que use la voz nueva.""")
    try:
        tocar(jarvis.sintetizar_eleven("¡El Cerebro en línea! Listo para pensar por los dos.", voz_id, clave))
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
