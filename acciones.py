"""Ejecuta las acciones ya validadas y guarda lo necesario para poder deshacer."""
import datetime as dt
import json
import re

import config
import discord_webhook
import tiktok
from hogger import Hogger
from kick import Kick

ESTADO = config.DATA / "estado.json"
HISTORIAL = config.DATA / "historial.log"


def log(linea):
    with HISTORIAL.open("a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {linea}\n")


def _limpiar_discord(texto):
    """Convierte <t:123:F> y <#id> de Discord en texto legible para el cartel."""
    texto = re.sub(r"<t:(\d+):\w>", lambda m: dt.datetime.fromtimestamp(int(m.group(1))).strftime("%d/%m %H:%M"), texto)
    return re.sub(r"<#\d+>", "Discord", texto)


class Ejecutor:
    def __init__(self, simular=False):
        self.simular = simular or config.DRY_RUN
        self.hogger = Hogger()
        self.kick = Kick()
        self._yt = None
        try:
            self.estado = json.loads(ESTADO.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self.estado = {}

    def _guardar(self):
        ESTADO.write_text(json.dumps(self.estado, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def yt(self):
        if self._yt is None:
            from youtube import YouTube
            self._yt = YouTube()
        return self._yt

    def ejecutar(self, accion):
        log(f"EJECUTAR {accion.tipo}: {json.dumps(accion.datos, ensure_ascii=False)}")
        metodo = getattr(self, f"_{accion.tipo}")
        resultado = metodo(accion)
        log(f"RESULTADO: {resultado}")
        return resultado

    # ------------------------------------------------ Discord
    def _hogger(self, accion):
        orden = accion.datos
        if self.simular:
            return f"[simulado] {accion.resumen}"
        if Hogger.disponible():
            res = self.hogger.enviar(orden)
            if not res.get("ok"):
                raise RuntimeError(res.get("error") or "Hogger no pudo hacerlo.")
            if res.get("link") and orden["accion"] != "cerrar":
                self.estado["ultima_publicacion"] = {"via": "hogger", "link": res["link"], "que": accion.resumen[:120]}
                self._guardar()
            return _limpiar_discord(res.get("resumen", "Hecho"))
        # Respaldo sin Hogger: solo texto por webhook
        if orden["accion"] in ("anuncio", "mensaje") and config.DISCORD_WEBHOOK_URL:
            texto = f"**{orden['titulo']}**\n{orden['texto']}" if orden["accion"] == "anuncio" else orden["texto"]
            msg_id = discord_webhook.enviar(texto)
            self.estado["ultima_publicacion"] = {"via": "webhook", "id": msg_id, "que": accion.resumen[:120]}
            self._guardar()
            return "Publicado en Discord por webhook (sin el estilo de Hogger)."
        raise RuntimeError("Para raids, sorteos y encuestas hace falta HOGGER_TOKEN en .env.")

    def _deshacer(self, accion):
        ultima = self.estado.get("ultima_publicacion")
        if not ultima:
            return "No tengo nada reciente que borrar."
        if not self.simular:
            if ultima["via"] == "hogger":
                res = self.hogger.enviar({"accion": "borrar", "link": ultima["link"]})
                if not res.get("ok"):
                    raise RuntimeError(res.get("error"))
            else:
                discord_webhook.borrar(ultima["id"])
        self.estado.pop("ultima_publicacion", None)
        self._guardar()
        return f"Borrado: {ultima.get('que', 'la última publicación')}"

    # ------------------------------------------------ títulos
    def _titulo(self, accion):
        titulo, plataformas = accion.datos["titulo"], accion.datos["plataformas"]
        hechas, fallos, anteriores = [], [], {}
        for p in plataformas:
            try:
                if self.simular:
                    hechas.append(f"{p} (simulado)")
                    continue
                if p == "kick":
                    anteriores["kick"] = self.kick.titulo_actual()
                    self.kick.cambiar_titulo(titulo)
                    hechas.append("Kick")
                elif p == "youtube":
                    anteriores["youtube"] = self.yt.cambiar_titulo(titulo)
                    hechas.append("YouTube")
                elif p == "tiktok":
                    hechas.append(f"TikTok ({tiktok.cambiar_titulo(titulo)})")
            except Exception as e:  # noqa: BLE001
                fallos.append(f"{p}: {e}")
        if anteriores:
            self.estado["titulos_anteriores"] = anteriores
            self._guardar()
        partes = []
        if hechas:
            partes.append("Título cambiado en " + ", ".join(hechas) + ".")
        if fallos:
            partes.append("Falló " + "; ".join(fallos))
        if not hechas:
            raise RuntimeError(" ".join(partes))
        return " ".join(partes)

    def _consultar_titulo(self, accion):
        return f"Kick: «{self.kick.titulo_actual()}»"

    def _restaurar_titulo(self, accion):
        anteriores = self.estado.get("titulos_anteriores") or {}
        if not anteriores:
            return "No tengo títulos anteriores guardados."
        hechas = []
        if not self.simular:
            if "kick" in anteriores:
                self.kick.cambiar_titulo(anteriores["kick"])
                hechas.append("Kick")
            if "youtube" in anteriores:
                self.yt.cambiar_titulo(anteriores["youtube"])
                hechas.append("YouTube")
        return f"Títulos restaurados en {', '.join(hechas) or 'nada'}."

    # ------------------------------------------------ miniaturas
    def _miniatura(self, accion):
        import miniaturas
        d = accion.datos
        rutas = miniaturas.crear(d["titulo"], d["subtitulo"])
        msg = f"Miniaturas listas en {rutas['youtube'].parent}"
        if d["subir_youtube"] and not self.simular:
            self.yt.subir_miniatura(rutas["youtube"])
            msg += " y subida a YouTube"
        return msg + "."

    def _aclaracion(self, accion):
        return accion.datos["pregunta"]
