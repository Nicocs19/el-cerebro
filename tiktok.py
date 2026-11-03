"""TikTok LIVE: no existe API oficial para el título del directo.

Modo "portapapeles" (por defecto): deja el título copiado para pegarlo en
TikTok LIVE Studio con Ctrl+V. El modo "automatico" (escribirlo en la ventana
de Live Studio) se activa cuando esté calibrado con tu versión de Live Studio.
"""
import config


class TiktokError(RuntimeError):
    pass


def copiar(texto):
    try:
        import pyperclip
        pyperclip.copy(texto)
        return True
    except Exception:  # noqa: BLE001
        return False


def cambiar_titulo(titulo):
    if config.TIKTOK_MODO == "automatico":
        raise TiktokError("El modo automático de Live Studio todavía no está calibrado; usa TIKTOK_MODO=portapapeles.")
    if not copiar(titulo):
        raise TiktokError("No pude copiar el título al portapapeles.")
    return "copiado: pégalo en Live Studio con Ctrl+V"
