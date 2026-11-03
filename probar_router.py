"""Prueba la IA local con frases reales SIN publicar nada: python probar_router.py"""
import sys
import time

import herramientas as H
import router

FRASES = [
    "lanza un anuncio a la guild que esta noche hacemos mazmorras a las 10, que vengan con pociones",
    "arma una raid de molten cor el viernes a las 9 con 20 cupos, gear mínimo 3000",
    "crea una raid de onyxia para mañana",
    "haz un sorteo de un mes de juego que dure dos días, que ganen dos",
    "encuesta para la guild: qué día hacemos la raid, viernes, sábado o domingo",
    "cambia el título a día 1 de wow forever subiendo guerrero del 20 al 30",
    "cambia el título solo en kick a raid nocturna con la guild",
    "cierra las inscripciones de la raid",
    "borra lo último que publicaste",
    "hazme una miniatura que diga primer boss caído, día 3",
    "avisa en general que en 10 minutos empiezo directo",
    "arma una banda para deadmines el sábado a las 6 de la tarde, 1 tanque 1 healer 3 dps",
    "lanza un anuncio a la guild que mañana a las 10 de la noche arrancamos la primera raid",
]


def _el(dia):
    d, _ = H.resolver_dia(dia)
    return f"{H.DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"


# Lo que tiene que salir sí o sí (si no, la prueba marca FALLO)
CHEQUEOS = {
    FRASES[0]: lambda r: "raids-signup" not in r,
    FRASES[1]: lambda r: _el("viernes") in r and "21:00" in r,
    FRASES[2]: lambda r: _el("mañana") in r,      # sin hora: tiene que preguntar «¿A qué hora...?»
    FRASES[11]: lambda r: _el("sábado") in r and "18:00" in r,
    FRASES[12]: lambda r: not any(x in r.lower() for x in ("anot", "inscrib", "#", "http")),  # sin instrucciones inventadas
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    frases = sys.argv[1:] or FRASES
    fallos = 0
    for f in frases:
        t0 = time.time()
        try:
            accion, origen = router.interpretar(f)
            bien = CHEQUEOS.get(f, lambda r: True)(accion.resumen)
            fallos += not bien
            print(f"{'OK ' if bien else 'FALLO'} ({time.time() - t0:4.1f} s, {origen}) {f}\n    -> {accion.tipo}: {accion.resumen}\n")
        except H.ErrorOrden as e:
            fallos += 1
            print(f"ERR ({time.time() - t0:4.1f} s) {f}\n    -> {e}\n")
    print(f"{len(frases) - fallos}/{len(frases)} bien.")


if __name__ == "__main__":
    main()
