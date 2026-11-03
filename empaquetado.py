"""Agente de Marketing y Empaquetado: título, texto de miniatura, idea visual y descripción, pensados JUNTOS para el clic.

Es un Claude aparte (CLAUDE_MODELO_EMPAQUETADO, Opus) que hace solo esto. No tiene herramientas: ni internet, ni
archivos, ni programas. Recibe lo que dijiste y devuelve un JSON. El programa lo valida, pone los enlaces reales y te
lo muestra entero antes del «dale». Si tarda o falla, sigue lo que había armado la IA local: nunca te quedás sin nada.
"""
import datetime
import json
import re
import subprocess
import time

import config

PEDIDO = """Sos el especialista en Marketing y Empaquetado del canal de Mr. H. Tu única tarea: que el empaquetado del
directo (título + texto de la miniatura + arte + descripción) sea irresistible y consiga el máximo de clics, sin
arruinar la retención.

EL CANAL
- Mr. H (Nicolas), streamer de World of Warcraft en español latino. GM de la hermandad {guild}.
- Juega WoW Forever. {lanzamiento} En vivo en Kick (principal), YouTube y TikTok.
- Contenido: subir personajes (Warrior y otros), raids (Molten Core, Onyxia…), pesca relajada, novedades del juego,
  humor con la comunidad. El Cerebro es su asistente (un cerebro con gafas).

HOY ES {hoy}.
LO QUE PIDIÓ (dictado por voz, puede traer errores): «{orden}»
{fijos}
Armá: {partes}

CÓMO SE ARMA UN EMPAQUETADO QUE GANA
1. Una sola idea fuerte por directo. Miniatura y título cuentan la MISMA historia desde dos lados:
   la miniatura da la emoción (2 a 4 palabras) y el título agrega el contexto y la curiosidad.
   NUNCA repitan las mismas palabras.
2. Título (máximo 70 caracteres, ideal 45 a 60): lo importante en las primeras 4 o 5 palabras (WoW Forever, la
   clase, la raid). Un gancho psicológico claro: curiosidad (una pregunta abierta), un reto o apuesta, un número
   concreto, un contraste, o la urgencia del en vivo. Lenguaje de la comunidad de WoW. Una o dos palabras en
   MAYÚSCULAS como mucho, y cero o un emoji.
3. Clickbait táctico: podés exagerar la emoción, el riesgo y la apuesta. NUNCA mientas: nada de datos, premios,
   resultados, invitados, horarios, cantidad de gente o noticias que no estén en lo que dijo Mr. H. Lo que no dijo
   no lo afirmes: convertilo en pregunta («¿cae Ragnaros?»). Lo que promete el título tiene que pasar en el
   directo; si no, la gente se va y el canal pierde.
4. Texto de la miniatura: 2 a 4 palabras en MAYÚSCULAS, que se lean en el celular (168 px de ancho). Pueden llevar
   UNA palabra de acento. Subtítulo opcional de 1 a 3 palabras, solo si suma.
5. Idea visual (el pedido para el diseñador, que trabaja en HTML con la captura del juego, fotos de Mr. H y arte de
   WoW; NO genera ilustraciones). En 5 a 8 líneas concretas: protagonista (cara de Mr. H con una emoción exagerada
   o un personaje de WoW GRANDE, 60% o más del alto); fondo de escena y su desenfoque; dos colores saturados que
   choquen (fuego/arcano, oro/azul noche…); luz (contraluz, halo, brillo en los ojos); efectos (chispas, brasas,
   rayos, viñeta); dónde va el texto (del lado opuesto a la cara, sin tapar ojos ni boca, lejos de la esquina de
   abajo a la derecha donde YouTube pone la duración); qué imágenes usar (logo de WoW, arte de la clase o de la
   raid). Una sola idea; si hay duda, menos elementos.
6. Descripción: la primera línea es otro gancho (es lo único que se ve sin abrirla). Después 2 a 4 frases con onda
   sobre lo que va a pasar y una invitación a la comunidad (seguir, entrar al Discord). SIN enlaces ni URLs: el
   programa agrega abajo los que pidió Mr. H. Hashtags: 3 a 5, primero los más buscados (WoWForever,
   WorldOfWarcraft), sin #.
7. Nunca nada sobre raza, origen, sexo, orientación, religión, físico o discapacidades, ni ataques a personas.

Respondé SOLO con este JSON (sin texto antes ni después). Dejá "" en lo que no se pidió:
{{"titulo": "", "miniatura": "", "miniatura_subtitulo": "", "miniatura_idea": "", "descripcion": "",
  "hashtags": [], "por_que": "una frase: la idea y el gancho que elegiste"}}"""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def _fecha(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def _lanzamiento(hoy):
    """Para que no diga «¡Salió WoW Forever!» el día antes."""
    try:
        sale = datetime.date.fromisoformat(config.LANZAMIENTO)
    except ValueError:
        return ""
    if hoy < sale:
        return f"Sale el {_fecha(sale)}: TODAVÍA NO SALIÓ (decí «sale», «se viene», nunca «salió»)."
    if hoy == sale:
        return "Sale HOY: es el día del lanzamiento."
    return f"Salió el {_fecha(sale)}."

PARTES = {"titulo": "el TÍTULO del directo", "miniatura": "el TEXTO y la IDEA VISUAL de la miniatura",
          "descripcion": "la DESCRIPCIÓN de YouTube (con enlaces y hashtags)"}


class EmpaquetadoError(RuntimeError):
    pass


def armar(orden, partes, fijos=None):
    """{titulo, miniatura, miniatura_subtitulo, miniatura_idea, descripcion, enlaces, hashtags, por_que}.

    partes: qué armar ("titulo", "miniatura", "descripcion"). fijos: textos que Nicolas dictó tal cual y se respetan.
    """
    from overlays import SIN_HERRAMIENTAS, SOLO_ESTO, buscar_claude
    exe = buscar_claude()
    if not exe:
        raise EmpaquetadoError("no está el programa claude en esta PC")
    fijos = {k: v for k, v in (fijos or {}).items() if v}
    nombres = {"titulo": "título", "miniatura": "texto de la miniatura"}
    texto_fijos = ("Esto lo dictó Mr. H y va TAL CUAL (armá el resto alrededor, en sinergia):\n"
                   + "\n".join(f"- {nombres.get(k, k)}: «{v}»" for k, v in fijos.items()) + "\n") if fijos else ""
    hoy = datetime.date.today()
    pedido = PEDIDO.format(guild=config.NOMBRE_GUILD, orden=orden.strip(), fijos=texto_fijos, hoy=_fecha(hoy),
                           lanzamiento=_lanzamiento(hoy),
                           partes=", ".join(PARTES[p] for p in partes if p in PARTES) or PARTES["titulo"])
    comando = [exe, "-p", "--output-format", "json"] + SOLO_ESTO
    comando += ["--model", config.CLAUDE_MODELO_EMPAQUETADO or "opus", "--disallowedTools"] + SIN_HERRAMIENTAS
    t0 = time.time()
    r = subprocess.run(comando, input=pedido + "\nRespondé directo, sin herramientas.", capture_output=True,
                       text=True, encoding="utf-8", timeout=config.EMPAQUETADO_ESPERA)
    salida = r.stdout or ""
    try:
        salida = str(json.loads(salida).get("result") or "")
    except (ValueError, AttributeError):
        pass
    m = re.search(r"\{.*\}", salida, re.S)
    if r.returncode != 0 or not m:
        raise EmpaquetadoError(f"no devolvió el empaquetado ({r.returncode}): {(r.stderr or salida)[:200]}")
    try:
        datos = json.loads(m.group(0))
    except ValueError as e:
        raise EmpaquetadoError(f"JSON roto: {e}") from e
    limpio = {k: str(datos.get(k) or "").strip() for k in ("titulo", "miniatura", "miniatura_subtitulo",
                                                            "miniatura_idea", "descripcion", "por_que")}
    limpio["enlaces"] = [str(x) for x in (datos.get("enlaces") or []) if str(x).strip()][:6]
    limpio["hashtags"] = [str(x) for x in (datos.get("hashtags") or []) if str(x).strip()][:6]
    for k, v in fijos.items():                 # lo que dictó manda, aunque el agente lo haya «mejorado»
        limpio[k] = v
    print(f"[empaquetado] {config.CLAUDE_MODELO_EMPAQUETADO}: {time.time() - t0:.0f} s. {limpio['por_que']}")
    return limpio
