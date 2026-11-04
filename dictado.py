"""Arreglos al texto que escribe Whisper, antes de que lo lea la IA (sin micrófono: se puede probar en cualquier PC).

- corregir(): palabras de WoW y del Discord que Whisper escucha mal («write» = raid, «sin app» = sign up…).
- quitar_repeticiones(): «Zul'Aman, Zul'Aman, Zul'Aman…» (Whisper a veces se queda en bucle).
- es_alucinacion(): frases que Whisper «escucha» en el silencio («Gracias por ver el video»).
"""
import re
import unicodedata

# Lo que Whisper suele escuchar mal -> lo que dijiste (se aplica a todo lo transcrito)
CORRECCIONES = [
    (r"\b(levi|libi|lebi|leb)(ando|ar|o|eo)\b", r"leve\2"),
    (r"\b(washer|guasher|guacher|wacher|guar|guor|wor)\b", "War"),
    (r"\bwarrior\b", "Warrior"),
    # «Hogger el H» al principio: Whisper escribió «Joder, Lacher» (4 nov)
    (r"^(\W*)(?:j[oó]der|hogger|hoger|j[oó]ger|j[oó]guer)[,\s]+(?:lacher|la cher|lache|el ache|el hache)\b", r"\1Hogger el H"),
    (r"\b(washior|guashior|wachior|guarior|guorior|wuarior)\b", "Warrior"),
    # el nombre del asistente: «Hoger», «Jóger», «Jogger», «Joguer», «Hoguer» (no «ogro»: es palabra de WoW)
    (r"\b(hoger|hogguer|hoguer|j[oó]ger|j[oó]gger|j[oó]guer|oguer|hógger)\b", "Hogger"),
    (r"\bwow forever\b|\bguau forever\b|\bbow forever\b", "WoW Forever"),
    (r"\b(previces|previs|previ ?bis|pre ?bis|pribis|prebís)\b", "pre-BiS"),
    # «tienen que estar previstos» en una raid = pre-BiS (solo pegado a estar/venir/ir: «previsto» también es palabra normal)
    (r"\b(estar|esten|estén|vengan|venir|ir|vayan|tener|tengan|con|equipo|gear)\s+(previstos?|previstas?)\b", r"\1 pre-BiS"),
    # El canal de registro de raids del Discord: «Rising Up», «Raidsingup», «Raids Sin Up», «write sin app»…
    (r"\brising[ -]?up\b", "raids-signup"),
    (r"\b(raids?|raits?|writes?|wrights?|reids?)[ -]?(sign|sain|sing|sin|zain|sein)[ -]?(up|ap|app|op|amp)\b",
     "raids-signup"),
    (r"\b(sain|sing|zain|sein)[ -]?(up|ap|app|op)\b", "sign up"),
    # «raid» dicho en inglés: Whisper escribe «write», «wright», «rait» o «reid»
    (r"\b(write|wright|rait|reid)(s)?\b", r"raid\2"),
]


def corregir(texto):
    for patron, cambio in CORRECCIONES:
        texto = re.sub(patron, cambio, texto, flags=re.IGNORECASE)
    return texto


_REPETIDO = re.compile(r"(?<![\w'’])([\w'’]+(?:\s+[\w'’]+){0,3}?)(?:[\s,.;:!?¡¿…-]+\1(?![\w'’])){2,}", re.IGNORECASE)


def quitar_repeticiones(texto):
    """«Zul'Aman, Zul'Aman, Zul'Aman, Zul'Aman» -> «Zul'Aman». Devuelve (texto, cuántas veces se repetía lo peor)."""
    peor = [1]

    def uno(m):
        veces = len(re.findall(r"(?<![\w'’])" + re.escape(m.group(1)) + r"(?![\w'’])", m.group(0), re.IGNORECASE))
        peor[0] = max(peor[0], veces)
        return m.group(1)

    limpio = _REPETIDO.sub(uno, texto)
    return re.sub(r"\s+", " ", limpio).strip(), peor[0]


# Frases que Whisper "escucha" en el silencio o el ruido (aprendidas de subtítulos de YouTube)
_ALUCINACION = re.compile(
    r"^(gracias( a todos)?( por (ver|mirar|su atencion|tu atencion|vernos))?( (el|este) video)?"
    r"|.*amara\.org.*|subtitulos? (realizados? )?por.*|(no olvides )?suscrib\w*( al canal)?|(y )?dale like.*"
    r"|hasta (la proxima|luego|pronto)|nos vemos( en el (proximo|siguiente) video)?|chau|adios|musica|aplausos|risas|)$")


def es_alucinacion(texto):
    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .")
    return bool(_ALUCINACION.fullmatch(t))


def limpiar(texto):
    """Todo junto: lo que devuelve "" es ruido y no se manda como orden."""
    texto = (texto or "").strip()
    if not texto or es_alucinacion(texto):
        return ""
    texto, veces = quitar_repeticiones(texto)
    if veces >= 5 and len(texto.split()) <= 4:
        return ""                   # Whisper en bucle («Zul'Aman» ×10) sin una orden alrededor: es ruido
    return corregir(texto)
