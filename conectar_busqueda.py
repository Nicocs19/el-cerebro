"""Conecta la búsqueda en internet de El Cerebro con una cuenta GRATIS de ollama.com. Se ejecuta UNA vez.

Sin esto, El Cerebro igual busca, pero solo en Wikipedia.
"""
import re
import sys
import webbrowser

import requests

import config
import guia

PAGINA = "https://ollama.com/settings/keys"


def limpiar(texto):
    t = re.sub(r"\x1b\[[0-9;]*[~A-Za-z]", "", texto or "")
    return re.sub(r"\s+", "", t)


def probar(clave):
    r = requests.post("https://ollama.com/api/web_search", json={"query": "World of Warcraft", "max_results": 1},
                      headers={"Authorization": f"Bearer {clave}"}, timeout=20)
    if r.status_code in (401, 403):
        raise PermissionError("ollama.com no aceptó la clave")
    r.raise_for_status()
    return r.json().get("results") or []


def pedir_clave():
    guia.paso(1, 2, f"""
Se abre ollama.com en tu navegador ({PAGINA}).
Si no tenés cuenta, creala (es gratis; podés entrar con tu cuenta de Google).
Tocá «Add API Key» (agregar clave). De nombre poné: El Cerebro.
Copiá la clave con el botón de copiar y volvé a esta ventana.
No hagas este paso con el stream en vivo: la clave es privada.""")
    webbrowser.open(PAGINA)
    import pyperclip
    for _ in range(3):
        input("Cuando la hayas copiado, apretá Enter acá (la leo de lo que copiaste)...")
        clave = limpiar(pyperclip.paste())
        if len(clave) < 20 or "/" in clave:
            print("No encontré la clave en lo que copiaste. Copiala con el botón de copiar y apretá Enter.")
            continue
        print("Probando la clave…")
        try:
            probar(clave)
        except PermissionError:
            print("❌ ollama.com no aceptó la clave. Creá otra y copiala apenas aparece.")
            continue
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"❌ No pude hablar con ollama.com ({type(e).__name__}). ¿Hay internet?")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"❌ Algo falló al probar la clave ({type(e).__name__}: {str(e)[:120]}).")
            continue
        guia.guardar_env(OLLAMA_API_KEY=clave)
        print("✅ Clave guardada.")
        return clave
    sys.exit("No se guardó nada. Volvé a abrir conectar_busqueda.bat cuando quieras.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("Vamos a darle a El Cerebro la búsqueda en internet de ollama.com (gratis).")
    if config.OLLAMA_API_KEY:
        try:
            probar(config.OLLAMA_API_KEY)
            print("✅ Ya tenés la búsqueda conectada y funciona.")
            return
        except Exception:  # noqa: BLE001
            print("La clave guardada ya no funciona: vamos a poner una nueva.")
    pedir_clave()
    guia.paso(2, 2, """
Listo: cuando le preguntes algo que hay que buscar («¿qué parche salió en WoW?»), El Cerebro
dice «dejame buscar», busca en internet y te contesta. Lo demás sigue igual de rápido.
Cerrá y volvé a abrir El Cerebro para que lo use.""")


if __name__ == "__main__":
    main()
