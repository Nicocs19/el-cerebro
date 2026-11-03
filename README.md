# El Cerebro

Asistente de voz para el streaming de Mr. H. Pulsas una tecla, hablas en lenguaje natural, y El Cerebro lo convierte en una orden validada y la ejecuta: anuncios, raids, sorteos y encuestas en Discord (a través de Hogger), títulos en Kick, YouTube y TikTok, y miniaturas con el estilo de The H's.

## Cómo funciona

1. **Voz:** Whisper `large-v3-turbo` transcribe en tu RTX 4080 (sin internet).
2. **Interpretación:** la IA local (`qwen3.5:9b` en Ollama) elige UNA herramienta y rellena sus campos. Recibe la fecha de hoy y el calendario, los roles y los canales del Discord.
3. **Validación:** `herramientas.py` revisa todo en Python (fechas futuras, cupos de 5 a 40, roles y canales que existen). El modelo solo propone.
4. **Confirmación:** lo que se publica en Discord te lo muestra en un cartel y espera tu «dale» (por voz o con Ctrl+Shift+F11). Puedes corregir: «mejor 25 cupos».
5. **Ejecución:** Discord va por el buzón privado `#cerebro` de Hogger, Kick y YouTube por sus API oficiales, y TikTok por el portapapeles.

Si Ollama no responde, usa patrones fijos para anuncios y títulos.

## Lo que entiende

| Dices | Hace |
|---|---|
| «Lanza un anuncio a la guild que esta noche hacemos mazmorras a las 10» | Redacta y publica un anuncio con la cabecera dorada |
| «Arma una raid de Molten Core el viernes a las 9 con 20 cupos» | Inscripción por clase y spec en #raids-signup |
| «Haz un sorteo de un mes de juego que dure dos días» | Sorteo con botón; el ganador sale solo |
| «Encuesta: qué día hacemos la raid, viernes, sábado o domingo» | Encuesta con resultados en vivo |
| «Arma una banda para Deadmines el sábado a las 6 de la tarde» | Evento con cupos de tanque, healer y DPS |
| «Cierra las inscripciones de la raid» | Cierra la última raid |
| «Borra lo último que publicaste» | Deshace la última publicación |
| «Cambia el título a Día 1 subiendo guerrero» | Kick y YouTube por API, TikTok al portapapeles |
| «Hazme una miniatura que diga primer boss caído, día 3» | Captura OBS y crea YouTube, Kick y TikTok en `salida/miniaturas` |

## Instalación (Windows 11)

1. Python 3.12, Git y Ollama instalados. Descarga el modelo: `ollama pull qwen3.5:9b`.
2. `git clone https://github.com/Nicocs19/el-cerebro C:\ElCerebro` y doble clic en `instalar.bat`.
3. Doble clic en `conectar_todo.bat`. Copia las claves de Hogger y de OBS al `.env` sin mostrarlas y actualiza Hogger en Google Cloud: hace copia de seguridad, reinicia y, si algo falla, vuelve solo a la versión anterior. El registro queda en `data/actualizar_hogger.log`.
4. Doble clic en `conectar_plataformas.bat`: te guía paso a paso para conectar Kick y YouTube (crea la app de Kick, activa la API de YouTube, recoge el `client_secret.json` de Descargas y abre las autorizaciones). También están por separado `conectar_kick.bat` y `conectar_youtube.bat`.
   Lo que queda en `.env`:
   - `HOGGER_TOKEN` y `HOGGER_GUILD_ID`: los mismos del `.env` de Hogger (los pone `conectar_todo.bat`).
   - `KICK_CLIENT_ID` y `KICK_CLIENT_SECRET`: de la app de kick.com/settings/developer (Redirect URL `http://localhost:8765/callback`, scopes `user:read channel:read channel:write`). Luego `conectar_kick.bat`.
   - YouTube: en Google Cloud, habilita "YouTube Data API v3", crea un ID de cliente OAuth de tipo "App de escritorio", descarga el JSON como `client_secret.json` en esta carpeta y ejecuta `conectar_youtube.bat`. Pon la pantalla de consentimiento en "En producción" para que la sesión no caduque cada 7 días.
   - OBS: Herramientas, Ajustes del servidor WebSocket, activar (la contraseña la copia `conectar_todo.bat`).
5. `diagnostico.bat` revisa cada pieza y te dice qué falta.
6. `iniciar.bat` arranca El Cerebro. Asigna Ctrl+Shift+F12 (hablar), F11 (dale) y F10 (cancelar) a botones del Loupedeck.

Actualizar: `actualizar.bat` (hace `git pull`). Actualizar solo Hogger en el servidor: `python actualizar_hogger.py`.

## Fechas

La IA copia el día tal como lo dijiste («viernes», «mañana», «el 15», «sábado 14») y la fecha exacta la calcula Python (`herramientas.resolver_dia`). Si la IA pone un día distinto del que dijiste, gana lo que dijiste. Si el número y el día no coinciden («sábado 13» cuando el 13 es viernes), te pregunta.

## Pruebas sin publicar

- `python probar_router.py`: pasa 12 frases por la IA local y muestra qué haría.
- `python cerebro.py --simular --texto "arma una raid de onyxia el sábado a las 8"`.

## Archivos

| Archivo | Para qué |
|---|---|
| `cerebro.py` | Programa principal: teclas, micrófono, cartel y flujo de confirmación |
| `router.py` | Prompt del sistema y llamada a Ollama con herramientas |
| `herramientas.py` | Esquemas de las herramientas y validación |
| `acciones.py` | Ejecuta cada acción y guarda lo necesario para deshacer |
| `hogger.py` | Buzón de órdenes de Hogger (API REST de Discord) |
| `kick.py`, `youtube.py`, `tiktok.py` | Plataformas |
| `miniaturas.py` | Miniaturas desde una captura de OBS |
| `voz.py`, `overlay.py`, `avisos.py` | Whisper, cartel flotante y pitidos |
| `diagnostico.py` | Revisión completa del sistema |
| `conectar_claves.py`, `actualizar_hogger.py`, `servidor/desplegar_hogger.sh` | Lo que hace `conectar_todo.bat` |
| `kick_auth.py`, `youtube_auth.py`, `guia.py` | Asistentes de `conectar_plataformas.bat` |

Secretos (`.env`, `client_secret.json`, `data/`) nunca se suben al repositorio.
