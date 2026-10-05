#!/usr/bin/env bash
# deploy.sh — CI-driven backend deploy for AURA on Hetzner.
#
# Εκτελείται αυτόματα από το GitHub Actions deploy.yml μετά από επιτυχές CI,
# ή χειροκίνητα: cd /root/aura-private-bootstrap && bash deploy.sh
#
# Pattern (hand-rolled, ΟΧΙ docker-compose — θα έχανε το aura_models volume):
#   1. Build νέα image
#   2. Stop τρέχον container
#   3. Promote (alpine cp για atomic swap)
#   4. Recreate container
#   5. Healthcheck
#   6. Prune παλιές images

set -euo pipefail

CONTAINER="aura-backend"
IMAGE="aura-backend:latest"
IMAGE_NEW="aura-backend:new"
ENV_FILE="/root/aura-backend.env"
NETWORK="aura-private-bootstrap_default"
PORT="8080"

echo "=== AURA Backend Deploy: $(date) ==="
echo "SHA: ${DEPLOY_SHA:-local}"

# 1. Build
echo "--- [1/6] Building image..."
docker build \
  --file backend/Dockerfile \
  --tag "$IMAGE_NEW" \
  backend/

# 2. Stop existing container (soft — αν δεν τρέχει, συνέχισε)
echo "--- [2/6] Stopping $CONTAINER..."
docker stop "$CONTAINER" 2>/dev/null || true
docker rm   "$CONTAINER" 2>/dev/null || true

# 3. Promote: tag new → latest (atomic swap)
echo "--- [3/6] Promoting image..."
docker tag "$IMAGE_NEW" "$IMAGE"
docker rmi "$IMAGE_NEW" 2>/dev/null || true

# 4. Recreate container
echo "--- [4/6] Starting container..."
docker run -d \
  --name "$CONTAINER" \
  --restart on-failure:10 \
  --network "$NETWORK" \
  --env-file "$ENV_FILE" \
  -p "${PORT}:${PORT}" \
  -v aura_models:/app/models \
  "$IMAGE"

# 5. Healthcheck (max 30s)
echo "--- [5/6] Healthcheck..."
for i in $(seq 1 15); do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "none")
  if [ "$STATUS" = "healthy" ] || [ "$STATUS" = "none" ]; then
    # Αν δεν έχει HEALTHCHECK στο Dockerfile, κάνε curl
    HTTP=$(curl -sf --max-time 5 "http://localhost:${PORT}/healthz" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
      echo "✅ Healthy (HTTP 200)"
      break
    fi
  fi
  echo "   waiting... ($i/15)"
  sleep 2
  if [ "$i" = "15" ]; then
    echo "❌ Healthcheck failed after 30s"
    docker logs --tail 50 "$CONTAINER"
    exit 1
  fi
done

# 6. Prune
echo "--- [6/6] Pruning old images..."
docker image prune -f

echo "=== Deploy complete: $(date) ==="
