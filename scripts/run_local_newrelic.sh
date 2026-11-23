#!/usr/bin/env bash
# Prueba local de blacklist-ms con New Relic (Entrega 4 - eventos de desarrollo).
# Uso:  ./scripts/run_local_newrelic.sh [segundos_de_trafico]   (default 120)
# La License Key se toma de $NEW_RELIC_LICENSE_KEY, si no de Parameter Store
# (si tienes la AWS CLI configurada) y si no, se pide sin mostrarla en pantalla.
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-120}"
IMAGE=blacklist-ms:local
NAME=bl-local
PORT=5001

if [ -z "${NEW_RELIC_LICENSE_KEY:-}" ] && command -v aws >/dev/null 2>&1; then
  echo "==> Leyendo la License Key desde Parameter Store..."
  NEW_RELIC_LICENSE_KEY=$(aws ssm get-parameter --region us-east-2 \
    --name /blacklist-ms/NEW_RELIC_LICENSE_KEY --with-decryption \
    --query Parameter.Value --output text 2>/dev/null || true)
fi
if [ -z "${NEW_RELIC_LICENSE_KEY:-}" ]; then
  read -rsp "Pega tu New Relic License Key (no se mostrará): " NEW_RELIC_LICENSE_KEY; echo
fi
[ -n "$NEW_RELIC_LICENSE_KEY" ] || { echo "Falta la License Key"; exit 1; }

echo "==> Construyendo la imagen $IMAGE..."
docker build -t "$IMAGE" .

docker rm -f "$NAME" >/dev/null 2>&1 || true
echo "==> Iniciando el contenedor $NAME en el puerto $PORT..."
docker run -d -p "$PORT:5000" \
  -e DATABASE_URL=sqlite:////tmp/local.db \
  -e 'JWT_SECRET_KEY=local-secret-with-at-least-32-bytes!!' \
  -e NEW_RELIC_LICENSE_KEY="$NEW_RELIC_LICENSE_KEY" \
  -e NEW_RELIC_APP_NAME=blacklist-ms-local \
  --name "$NAME" "$IMAGE" >/dev/null

docker exec "$NAME" flask --app application init-db
TOKEN=$(docker exec "$NAME" flask --app application generate-token)

echo "==> Esperando a que la app responda..."
for _ in $(seq 1 30); do
  curl -fs "http://localhost:$PORT/ping" && echo && break
  sleep 1
done

echo "==> Generando tráfico durante ${DURATION}s para que New Relic reciba eventos..."
BASE_URL="http://localhost:$PORT" JWT_TOKEN="$TOKEN" \
  python3 scripts/stress_test.py --duration "$DURATION" --workers 5

echo "==> Logs del agente de New Relic:"
docker logs "$NAME" 2>&1 | grep -i "newrelic\|new relic" | tail -5 || true

cat <<MSG

Listo. En New Relic -> APM & Services busca "blacklist-ms-local" (puede tardar 1-2 minutos).
El contenedor sigue corriendo para que lo explores; detenlo con:  docker rm -f $NAME
MSG
