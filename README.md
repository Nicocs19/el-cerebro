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
| «Hazme una miniatura que diga primer boss caído, día 3» | Captura el juego en OBS (si está cerrado, usa el fondo de la guild) y crea YouTube, Kick y TikTok en `salida/miniaturas` |
| «Banea a pepe noventa y nueve» | Busca al más parecido en el chat de Kick y YouTube, te dice el nombre exacto y su último mensaje, y banea con tu «dale» |
| «Silenciá cinco minutos a shadow en Kick» | Timeout (10 minutos si no decís cuánto) |
| «Desbaneá a pepe» | Quita el ban (en YouTube, solo a los que baneó El Cerebro) |
| «Mandá al chat el link del Discord» | Escribe el enlace guardado en el chat de Kick y YouTube |
| «Guardá este enlace como tienda» (con el enlace copiado) | Lo agrega a `enlaces.txt` |
| «Poné un cartel arriba a la derecha que diga raid de Onyxia a las 10» | Claude diseña el overlay y aparece en tu escena de OBS donde dijiste; «movelo abajo», «ocultalo», «sacalo» |
| «Cambiá el título a Día 2 y hacé la miniatura que diga Día 2» | Título y, en segundo plano, miniatura diseñada por Claude |
| «Cerebro, decime algo» | Te contesta en voz alta; nunca publica nada por una charla |

Las miniaturas y los overlays los diseña Claude con el programa `claude` de tu PC (usa tu plan) y Edge los convierte en imagen. Para usar fotos tuyas (personajes, jefes), ponelas en `recursos/imagenes` con un nombre claro (`paladin.png`) y nombralas en tu idea. Si Claude no responde, sale la plantilla dorada de siempre. Mientras Claude diseña, podés seguir dándole órdenes.

## El Cerebro en pantalla y con voz

Cuando lo llamás aparece abajo a la derecha un cerebro con ojos: abre los ojos y salta con tu voz mientras escucha, mira para arriba y le salen burbujitas mientras piensa, mueve la boca cuando habla, pone ojos felices cuando sale bien y ojos en cruz si algo falla. El cartel con el texto aparece arriba de él, como un globo de diálogo, solo cuando hay algo para leer (la confirmación o el resultado).

El Cerebro te lee la confirmación («Raid de Onyxia, el viernes a las 9 de la noche, 20 cupos. ¿La publico?») y te avisa cuando está hecho. Si le hablás, le preguntás algo o le pedís un chiste, te contesta con la IA local de tu PC (gratis y sin límite) y no publica nada. Suena por la salida de audio normal, así que el stream también lo oye.

- Voz: ElevenLabs (`conectar_voz.bat` guarda la clave y te deja elegir voz, normal o de dibujito). Las frases repetidas quedan guardadas y no gastan créditos. Sin clave o sin créditos usa una voz local (Piper), gratis.
- Ajustes en `.env`: `VOZ_TONO` (0 = normal, 3 a 5 = dibujito), `ORBE_ESTILO` (`cerebro` u `orbe`), `CEREBRO_DISENO` (`gafas` o `clasico`), `CEREBRO_SIEMPRE`, `VOZ_RELLENO` (dice «a ver…» si la IA tarda), `ELEVEN_VOZ`, `VOZ_DISPOSITIVO` (`python cerebro.py --salidas` lista las salidas), `ORBE_POSICION`.
- Probar la voz: `python cerebro.py --decir "El Cerebro en línea"`.

## Chat del stream

- **Moderación:** El Cerebro escucha el chat de Kick mientras está abierto y lee el de YouTube en el momento, para encontrar al usuario aunque el dictado escriba el nombre "como suena". Si hay dos parecidos, pregunta a cuál. Nunca modera a moderadores ni a vos. Siempre pide «dale».
- **Enlaces:** `enlaces.txt` (al lado de `cerebro.py`), una línea por enlace: `discord = https://discord.gg/...`. Solo se mandan enlaces de esa lista.
- Kick necesita los permisos `chat:write` y `moderation:ban`: `conectar_kick.bat` te guía para marcarlos en tu app y guarda el número de la sala del chat.
- YouTube: banear cuesta 200 de las 10.000 unidades diarias gratis, escribir en el chat 20 y buscar al usuario 5.

## Personalidad, preguntas y juego

- **Charla:** «saludá al stream», «contame un chiste», «molestá al chat» o bardearlo: contesta en voz (se escucha en el stream) sin publicar nada. Si lo molestás se pone caliente (cara roja con la vena). Bromas picantes pero nunca sobre raza, origen, sexo, orientación, religión, el físico o discapacidades.
- **Escribir en el chat:** solo si decís «mandá / escribí … en el chat», y siempre con «dale».
- **Buscar en internet:** solo cuando la pregunta lo necesita («¿qué parche salió en WoW?»): dice «dejame buscar», busca y resume en 1 a 3 frases con la fuente en pantalla. Sin cuenta usa Wikipedia; con `conectar_busqueda.bat` (cuenta gratis de ollama.com) busca en toda la web.
- **Título, juego y miniatura en una orden:** «cambiá el título a … , poné World of Warcraft y haceme la miniatura que diga …». Se confirma todo junto con «dale». El juego (categoría) solo se puede cambiar por voz en Kick.
- **Dictado de WoW:** `voz.py` tiene el vocabulario (War, Pala, Lock, leveando…) y una lista de correcciones (`CORRECCIONES`) para lo que Whisper escucha mal.
- **Miniaturas con imágenes tuyas:** poné PNG en `recursos\imagenes` con nombres claros (`logo_wow.png`, `warrior.png`): el diseño las usa cuando las nombrás en la idea.

## Instalación (Windows 11)

1. Python 3.12, Git y Ollama instalados. Descarga el modelo: `ollama pull qwen3.5:9b`.
2. `git clone https://github.com/Nicocs19/el-cerebro C:\ElCerebro` y doble clic en `instalar.bat`.
3. Doble clic en `conectar_todo.bat`. Copia las claves de Hogger y de OBS al `.env` sin mostrarlas y actualiza Hogger en Google Cloud: hace copia de seguridad, reinicia y, si algo falla, vuelve solo a la versión anterior. El registro queda en `data/actualizar_hogger.log`.
4. Doble clic en `conectar_plataformas.bat`: te guía paso a paso para conectar Kick y YouTube (crea la app de Kick, activa la API de YouTube, recoge el `client_secret.json` de Descargas y abre las autorizaciones). También están por separado `conectar_kick.bat` y `conectar_youtube.bat`.
   Lo que queda en `.env`:
   - `HOGGER_TOKEN` y `HOGGER_GUILD_ID`: los mismos del `.env` de Hogger (los pone `conectar_todo.bat`).
   - `KICK_CLIENT_ID` y `KICK_CLIENT_SECRET`: de la app de kick.com/settings/developer (Redirect URL `http://localhost:8765/callback`, scopes `user:read channel:read channel:write chat:write moderation:ban`). Luego `conectar_kick.bat`.
   - YouTube: en Google Cloud, habilita "YouTube Data API v3", crea un ID de cliente OAuth de tipo "App de escritorio", descarga el JSON como `client_secret.json` en esta carpeta y ejecuta `conectar_youtube.bat`. Pon la pantalla de consentimiento en "En producción" para que la sesión no caduque cada 7 días.
   - OBS: Herramientas, Ajustes del servidor WebSocket, activar (la contraseña la copia `conectar_todo.bat`).
5. `diagnostico.bat` revisa cada pieza y te dice qué falta.
6. `iniciar.bat` arranca El Cerebro. Asigna Ctrl+Shift+F12 (hablar), F11 (dale) y F10 (cancelar) a botones del Loupedeck.

Actualizar: `actualizar.bat` (hace `git pull`). Actualizar solo Hogger en el servidor: `python actualizar_hogger.py`.

## Fechas

La IA copia el día tal como lo dijiste («viernes», «mañana», «el 15», «sábado 14») y la fecha exacta la calcula Python (`herramientas.resolver_dia`). Si la IA pone un día distinto del que dijiste, gana lo que dijiste. Si el número y el día no coinciden («sábado 13» cuando el 13 es viernes), te pregunta.

## Pruebas sin publicar

- `python probar_router.py`: pasa 13 frases por la IA local y muestra qué haría.
- `python probar_router.py chat`: revisa que entienda las órdenes de moderación y enlaces (sin mandar nada).
- `python chat_vivo.py`: muestra lo que llega al chat de Kick.
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
| `jarvis.py`, `cerebrito.py`, `conectar_voz.py` | Voz, cerebro animado y configuración de la voz |
| `moderacion.py`, `chat_vivo.py`, `enlaces.py` | Moderación por voz, chat de Kick en vivo y enlaces |
| `overlays.py`, `miniaturas_claude.py` | Overlays de OBS y miniaturas diseñados por Claude |
| `diagnostico.py` | Revisión completa del sistema |
| `conectar_claves.py`, `actualizar_hogger.py`, `servidor/desplegar_hogger.sh` | Lo que hace `conectar_todo.bat` |
| `kick_auth.py`, `youtube_auth.py`, `guia.py` | Asistentes de `conectar_plataformas.bat` |

Secretos y datos personales (`.env`, `client_secret.json`, `data/`, `enlaces.txt`, `overlays/`) nunca se suben al repositorio.
