#!/bin/bash
# Actualiza Hogger en el servidor de Google Cloud de forma segura:
#   1. revisa el zip nuevo sin tocar nada,  2. hace copia de seguridad de la carpeta del bot,
#   3. copia el código nuevo (nunca .env ni datos.json),  4. reinicia y vigila 60 s,
#   5. si algo falla, vuelve sola a la versión anterior.
# Lo llama actualizar_hogger.py desde la PC:  bash desplegar_hogger.sh /tmp/Hogger_bot.zip
set -u
ZIP="${1:-/tmp/Hogger_bot.zip}"
fin() { echo "RESULTADO: $1"; rm -rf "${TMP:-/nonexistent}"; exit "${2:-0}"; }

DIR=$(systemctl show -p WorkingDirectory --value hogger 2>/dev/null)
DUENO=$(systemctl show -p User --value hogger 2>/dev/null)
if [ -z "$DIR" ] || [ ! -f "$DIR/bot.py" ]; then fin "ERROR no encuentro la carpeta de Hogger (servicio hogger, carpeta '$DIR'). No toqué nada." 2; fi
[ -f "$ZIP" ] || fin "ERROR no llegó el zip al servidor. No toqué nada." 2
command -v unzip >/dev/null || sudo apt-get install -y -qq unzip >/dev/null
echo "Carpeta de Hogger: $DIR (usuario ${DUENO:-root})"

# 1. Revisar el zip nuevo aparte
TMP=$(mktemp -d)
unzip -oq "$ZIP" -d "$TMP" || fin "ERROR el zip está dañado. No toqué nada." 3
NUEVO="$TMP/bot"
[ -f "$NUEVO/bot.py" ] || fin "ERROR el zip no trae bot/bot.py. No toqué nada." 3
rm -f "$NUEVO/.env" "$NUEVO/datos.json"
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$NUEVO/bot.py" "$NUEVO/config.py" || fin "ERROR el código nuevo tiene errores. No toqué nada." 3
rm -rf "$NUEVO/__pycache__"

# 2. Copia de seguridad
RESPALDO="${DIR}_respaldo_$(date +%Y%m%d_%H%M%S)"
sudo cp -a "$DIR" "$RESPALDO" || fin "ERROR no pude hacer la copia de seguridad. No toqué nada." 4
echo "Copia de seguridad: $RESPALDO"

restaurar() {
  echo "Algo salió mal: vuelvo a la versión anterior..."
  (cd "$NUEVO" && find . -type f) | while read -r f; do
    if [ -e "$RESPALDO/$f" ]; then sudo cp -a "$RESPALDO/$f" "$DIR/$f"; else sudo rm -f "$DIR/$f"; fi
  done
  sudo systemctl restart hogger
  sleep 10
  echo "Hogger después de restaurar: $(systemctl is-active hogger)"
}

# 3. Código nuevo
sudo cp -r "$NUEVO/." "$DIR/"
[ -n "$DUENO" ] && sudo chown -R "$DUENO": "$DIR"
if ! cmp -s "$NUEVO/requirements.txt" "$RESPALDO/requirements.txt"; then
  echo "Instalando dependencias nuevas..."
  sudo -u "${DUENO:-root}" "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt" || { restaurar; fin "RESTAURADO no se pudieron instalar las dependencias nuevas" 5; }
fi

# 4. Reiniciar y vigilar
REINICIOS_ANTES=$(systemctl show -p NRestarts --value hogger)
DESDE=$(date '+%Y-%m-%d %H:%M:%S')
echo "Reiniciando Hogger..."
sudo systemctl restart hogger
ESTADO="esperando"
for i in $(seq 1 12); do
  sleep 5
  LOG=$(sudo journalctl -u hogger --since "$DESDE" --no-pager -o cat 2>/dev/null)
  if echo "$LOG" | grep -q "Traceback"; then ESTADO="error"; break; fi
  if [ "$(systemctl show -p NRestarts --value hogger)" != "$REINICIOS_ANTES" ]; then ESTADO="error"; break; fi
  if echo "$LOG" | grep -qE "está en línea|connected to Gateway"; then ESTADO="ok"; sleep 5; break; fi
done
[ "$ESTADO" = "esperando" ] && [ "$(systemctl is-active hogger)" = "active" ] && ESTADO="ok"
[ "$(systemctl is-active hogger)" = "active" ] || ESTADO="error"

LOG=$(sudo journalctl -u hogger --since "$DESDE" --no-pager -o cat 2>/dev/null)
echo "----- últimas líneas de Hogger -----"
echo "$LOG" | tail -n 25
echo "------------------------------------"
if [ "$ESTADO" != "ok" ]; then
  restaurar
  fin "RESTAURADO Hogger no arrancó bien con la versión nueva; quedó la anterior" 6
fi
rm -f "$ZIP"
if echo "$LOG" | grep -q "No pude crear #"; then
  fin "OK_SIN_CANAL Hogger actualizado y en línea, pero no pudo crear #cerebro (falta el permiso Gestionar canales)"
fi
fin "OK Hogger actualizado y en línea"
