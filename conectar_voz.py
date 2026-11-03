"""Conecta la voz de Jarvis con tu cuenta de ElevenLabs y te deja elegir la voz. Se ejecuta UNA vez."""
import sys
import time
import webbrowser

import numpy as np

import config
import guia
import jarvis

PAGINA = "https://elevenlabs.io/app/settings/api-keys"
OPCIONES = [("Daniel", "británico, serio (el más parecido a Jarvis)"),
            ("George", "británico, cálido"),
            ("Brian", "americano, grave")]
PRUEBA = "Raid de Onyxia, el viernes a las 9 de la noche, 20 cupos. ¿La publico?"


def tocar(pcm):
    import sounddevice as sd
    audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0 * config.VOZ_VOLUMEN
    disp = config.VOZ_DISPOSITIVO
    sd.play(audio, jarvis.ELEVEN_SR, device=int(disp) if disp.isdigit() else (disp or None))
    sd.wait()


def pedir_clave():
    guia.paso(1, 3, f"""
Se abre ElevenLabs en tu navegador ({PAGINA}). Si no estás con tu sesión, iniciá sesión.
(Si no ves esa página: tocá tu perfil, abajo a la izquierda, y después «API Keys».)
Tocá «Create API Key» (crear clave). De nombre poné: El Cerebro.
Si ves un interruptor «Restrict Key», dejalo apagado. Tocá «Create» y copiá la clave con el botón de copiar.
No hagas este paso con el stream en vivo: la clave es privada.""")
    webbrowser.open(PAGINA)
    for _ in range(3):
        clave = input("Pegá la clave acá (clic derecho o Ctrl+V) y apretá Enter: ").strip()
        if not clave or " " in clave or len(clave) < 20:
            print("Eso no parece una clave de ElevenLabs. Probá de nuevo.")
            continue
        print("Probando la clave…")
        try:
            jarvis.sintetizar_eleven("Hola.", jarvis.VOCES_DE_SERIE["daniel"], clave)
        except PermissionError as e:
            print(f"❌ ElevenLabs no aceptó la clave ({e}).\n   Revisá que la copiaste entera, o creá otra.")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"❌ No pude hablar con ElevenLabs ({e}). ¿Hay internet?")
            continue
        guia.guardar_env(ELEVEN_API_KEY=clave)
        print("✅ Clave guardada.")
        return clave
    sys.exit("No se guardó nada. Volvé a abrir conectar_voz.bat cuando quieras.")


def elegir_voz(clave):
    guia.paso(2, 3, "Ahora vas a escuchar 3 voces diciendo lo mismo. Subí el volumen.")
    guia.esperar_enter("Apretá Enter para escucharlas...")
    for i, (nombre, como) in enumerate(OPCIONES, 1):
        print(f"   Voz {i}: {nombre} ({como})")
        try:
            tocar(jarvis.sintetizar_eleven(PRUEBA, jarvis.buscar_voz(nombre, clave), clave))
        except Exception as e:  # noqa: BLE001
            print(f"      (no pude reproducirla: {e})")
        time.sleep(0.4)
    while True:
        r = input("\n¿Cuál te gusta? Escribí 1, 2 o 3 (o «r» para escucharlas otra vez) y Enter: ").strip().lower()
        if r == "r":
            return elegir_voz(clave)
        if r in ("1", "2", "3", ""):
            nombre = OPCIONES[int(r or 1) - 1][0]
            guia.guardar_env(ELEVEN_VOZ=nombre)
            return nombre
        if len(r) > 3:  # el nombre de otra voz de su cuenta
            try:
                jarvis.buscar_voz(r, clave)
                guia.guardar_env(ELEVEN_VOZ=r)
                return r
            except Exception as e:  # noqa: BLE001
                print(f"No encontré esa voz ({e}).")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("Vamos a darle a Jarvis la voz de ElevenLabs (gasta muy pocos créditos: las frases repetidas no gastan).")
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
    nombre = elegir_voz(clave)
    guia.paso(3, 3, f"""
Listo: Jarvis va a hablar con la voz {nombre}.
Se escucha por tus parlantes o auriculares normales, así que tu stream también la oye
(si OBS captura el audio del escritorio).
Cerrá y volvé a abrir El Cerebro para que use la voz nueva.""")
    try:
        tocar(jarvis.sintetizar_eleven("Sistemas en línea. Listo para el stream.", jarvis.buscar_voz(nombre, clave), clave))
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
