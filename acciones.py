"""Ejecuta las acciones ya validadas y guarda lo necesario para poder deshacer."""
import datetime as dt
import json
import re
from pathlib import Path

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
        if self.simular:                 # simulando no se olvida cuál fue la última (si no, después no la podrías borrar)
            return f"[simulado] Borraría: {ultima.get('que', 'la última publicación')}"
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
                    cat = self.kick.buscar_categoria(accion.datos["juego"]) if accion.datos.get("juego") else None
                    if accion.datos.get("juego") and not cat:
                        fallos.append(f"juego: no encontré «{accion.datos['juego']}» en Kick")
                    self.kick.cambiar_titulo(titulo, cat["id"] if cat else None)
                    hechas.append(f"Kick (juego: {cat['name']})" if cat else "Kick")
                elif p == "youtube":
                    anteriores["youtube"] = self.yt.cambiar_titulo(titulo, accion.datos.get("descripcion"))
                    hechas.append("YouTube (con la descripción)" if accion.datos.get("descripcion") else "YouTube")
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

    def _juego(self, accion):
        nombre = accion.datos["juego"]
        if self.simular:
            return f"[simulado] Juego en Kick: {nombre}"
        cat = self.kick.buscar_categoria(nombre)
        if not cat:
            raise RuntimeError(f"No encontré el juego «{nombre}» en Kick. Decilo con el nombre completo.")
        self.kick.cambiar_categoria(cat["id"])
        return f"Juego cambiado en Kick a {cat['name']}. En YouTube y TikTok el juego se cambia a mano."

    def _consultar_titulo(self, accion):
        partes = []
        try:
            t = self.kick.titulo_actual()
            partes.append(f"Kick: «{t}»" if t else "Kick: no me devuelve el título (puede que tenga que estar en vivo)")
        except Exception as e:  # noqa: BLE001
            partes.append(f"Kick: no pude verlo ({e})")
        try:
            vid, sn = self.yt._video()
            desc = " ".join(str(sn.get("description") or "").split())
            partes.append(f"YouTube: «{sn.get('title', '')}»" + (f". Descripción: {desc[:160]}{'…' if len(desc) > 160 else ''}"
                                                                 if desc else ". Sin descripción"))
        except Exception as e:  # noqa: BLE001
            partes.append(f"YouTube: {e}")
        return "\n".join(partes)

    def _descripcion(self, accion):
        if self.simular:
            return f"[simulado] {accion.resumen.splitlines()[0]}"
        vid, sn = self.yt._video()
        self.estado["descripcion_anterior"] = {"youtube": sn.get("description", "")}
        self._guardar()
        self.yt.cambiar_titulo(sn["title"], accion.datos["descripcion"], video_id=vid)
        return "Descripción cambiada en YouTube. (Kick y TikTok no tienen descripción que se pueda cambiar.)"

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
        rutas = miniaturas.crear(d["titulo"], d.get("subtitulo", ""), idea=d.get("idea", ""), dicho=d.get("dicho", ""))
        quien = "diseñadas por Claude" if rutas.get("quien") == "Claude" else "con la plantilla dorada"
        msg = f"Miniaturas listas ({quien}) en {rutas['youtube'].parent}"
        if d.get("subir_youtube") and not self.simular:
            try:
                self.yt.subir_miniatura(rutas["youtube"])
                msg += " y subida a YouTube"
                import miniaturas_claude
                miniaturas_claude.anotar("subida", rutas["youtube"].parent)     # la «de ahora», para editarla después
            except Exception as e:  # noqa: BLE001
                msg += f". No la pude subir a YouTube ({str(e)[:120]}); quedó en la carpeta"
        return msg + "."

    def _editar_miniatura(self, accion):
        """Cambia solo lo que pediste en la miniatura de ahora; la subida a YouTube queda esperando tu «dale»."""
        import herramientas as H
        import miniaturas_claude
        d = accion.datos
        if self.simular:
            return f"[simulado] {accion.resumen}"
        r = miniaturas_claude.editar(d["cambio"], dicho=d.get("dicho", ""))
        abierta = miniaturas_claude.mostrar(r["comparacion"])
        mirala = "Te abrí «antes y ahora» para que la mires" if abierta else f"Mirala en {r['comparacion']}"
        if not d.get("subir_youtube"):
            return f"Listo, la cambié: {r['resumen'].rstrip('. ')}.\nQuedó en {r['carpeta']}. {mirala}."
        resumen = (f"Miniatura cambiada: {r['resumen'].rstrip('. ')}.\n(Partí de «{r['de']}». {mirala}; todavía no la subí.)")
        accion.siguiente = H.Accion("miniatura_subir", {"carpeta": r["carpeta"].name, "resumen": r["resumen"],
                                                        "abierta": abierta}, resumen, True)     # espera tu «dale»
        return "Listo, ya la cambié. Todavía no la subí a YouTube."

    def _miniatura_subir(self, accion):
        import miniaturas_claude
        d = accion.datos
        if self.simular:
            return f"[simulado] {accion.resumen.splitlines()[0]}"
        carpeta = config.SALIDA / "miniaturas" / Path(d["carpeta"]).name
        if not (carpeta / "youtube.jpg").exists():
            raise RuntimeError(f"No encuentro la miniatura cambiada ({carpeta.name}).")
        self.yt.subir_miniatura(carpeta / "youtube.jpg")
        miniaturas_claude.anotar("subida", carpeta)
        extra = miniaturas_claude.aprender_logo(carpeta)
        return f"Miniatura nueva subida a YouTube (las de Kick y TikTok están en {carpeta})." + (f" {extra}" if extra else "")

    # ------------------------------------------------ chat del stream
    def _moderar(self, accion):
        import moderacion
        resultado = moderacion.ejecutar(accion, self.kick, self._yt_si_hace_falta(accion), self.estado, self.simular)
        self._guardar()
        return resultado

    def _yt_si_hace_falta(self, accion):
        return self.yt if any(o["plataforma"] == "youtube" for o in accion.datos.get("objetivos", [])) else None

    def _chat(self, accion):
        texto, hechas, fallos = accion.datos["texto"], [], []
        for p in accion.datos["plataformas"]:
            try:
                if self.simular:
                    hechas.append(f"{p} (simulado)")
                elif p == "kick":
                    self.kick.escribir(texto)
                    hechas.append("Kick")
                elif p == "youtube":
                    self.yt.escribir(texto)
                    hechas.append("YouTube")
            except Exception as e:  # noqa: BLE001
                fallos.append(f"{p}: {e}")
        partes = (["Mandado al chat de " + " y ".join(hechas) + "."] if hechas else []) + \
                 (["Falló " + "; ".join(fallos)] if fallos else [])
        if not hechas:
            raise RuntimeError(" ".join(partes))
        return " ".join(partes)

    def _guardar_enlace(self, accion):
        import enlaces
        reemplazo = enlaces.guardar(accion.datos["nombre"], accion.datos["url"])
        return f"Enlace «{accion.datos['nombre']}» {'actualizado' if reemplazo else 'guardado'}."

    # ------------------------------------------------ overlays de OBS
    def _overlay(self, accion):
        import overlays
        d = accion.datos
        if self.simular:
            return f"[simulado] {accion.resumen.splitlines()[0]}"
        if d["accion"] == "crear":
            r = overlays.crear(d["nombre"], d["descripcion"], d["posicion"], d["tamano"])
            hecho = "diseñado por Claude" if r["quien"] == "Claude" else "con el cartel simple (Claude no respondió)"
            return f"Overlay «{d['nombre']}» en la escena {r['escena']}, {hecho}."
        if d["accion"] == "mover":
            overlays.mover(d["nombre"], d["posicion"])
            return f"Overlay movido a {d['posicion'].replace('-', ' ')}."
        if d["accion"] in ("ocultar", "mostrar"):
            overlays.mostrar(d["nombre"], d["accion"] == "mostrar")
            return "Overlay " + ("visible." if d["accion"] == "mostrar" else "oculto.")
        overlays.quitar(d["nombre"])
        return "Overlay quitado (el diseño queda guardado en la carpeta overlays)."

    # ------------------------------------------------ los overlays que ya tenés en OBS
    def _mis_overlays(self, accion):
        import herramientas as H
        import mis_overlays
        d = accion.datos
        if self.simular:
            return f"[simulado] {accion.resumen}"
        try:
            if d["accion"] == "ver":
                corta, detalle = mis_overlays.ver()
                return f"{corta}\n{detalle}"
            if d["accion"] == "volver":
                return mis_overlays.volver()
            if d["accion"] == "cambiar":
                p = mis_overlays.preparar_cambio(d["cual"], d["cambio"], d["lienzo"], dicho=d.get("dicho", ""))
                if p["tipo"] == "varios":
                    resumen = f"Cambio en {len(p['partes'])} overlays tuyos:\n" + "\n".join(
                        f"- «{q['fuente']}» ({q['lienzo']}, {q['escena']}): {q['resumen']}" for q in p["partes"])
                else:
                    resumen = f"Cambio en tu overlay «{p['fuente']}» ({p['lienzo']}, {p['escena']}):\n{p['resumen']}"
                if p.get("fallas"):
                    resumen += "\nOjo: " + "; ".join(p["fallas"]) + "."
            else:
                p = mis_overlays.preparar_nuevo(d["cual"], d["cambio"], d["lienzo"], d["reemplazar"],
                                                dicho=d.get("dicho", ""))
                resumen = f"{p['resumen']}, escena {p['escena']} del lienzo {p['lienzo']}.\n{d['cambio']}"
        except mis_overlays.Error as e:
            raise H.ErrorOrden(str(e))
        resumen += "\n(Guardo una copia del original y no toco tu cámara.)"
        if p.get("en_vivo"):
            resumen += "\nOjo: estás en vivo, al cargarlo se ve un segundito."
        accion.siguiente = H.Accion("overlay_aplicar", p, resumen, True)      # queda esperando tu «dale»
        return "Listo, ya lo tengo preparado. Todavía no cambié nada en OBS."

    def _overlay_aplicar(self, accion):
        import herramientas as H
        import mis_overlays
        if self.simular:
            return f"[simulado] {accion.resumen.splitlines()[0]}"
        try:
            return mis_overlays.aplicar(accion.datos)
        except mis_overlays.Error as e:
            raise H.ErrorOrden(str(e))

    def _respuesta(self, accion):
        return accion.datos["respuesta"]

    def _busqueda(self, accion):
        import buscar
        texto, fuente = buscar.contestar(accion.datos["pregunta"])
        return f"{texto}\n(Fuente: {fuente})" if fuente else texto

    def _aclaracion(self, accion):
        return accion.datos["pregunta"]
