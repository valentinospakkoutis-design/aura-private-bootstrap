#!/bin/bash
# Ενεργοποίηση paper trading για τον admin χρήστη. Idempotent.
# Credentials από /root/aura-secrets.env (βλ. rotate-admin-password.sh) — κανένας κωδικός σε git.
#
# Exit 0 μόνο αν: login 200, enable-paper 200, και paper_mode=true στη βάση μετά.
set -uo pipefail
SECRETS=/root/aura-secrets.env
DB=${AURA_DB_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -E '_db_1$|aura-postgres' | head -1)}

[ -r "$SECRETS" ] || { echo "❌ λείπει $SECRETS — τρέξε πρώτα rotate-admin-password.sh"; exit 1; }
set -a; . "$SECRETS"; set +a
: "${AURA_ADMIN_EMAIL:?}" "${AURA_ADMIN_PASSWORD:?}"

echo "Enabling paper trading for $AURA_ADMIN_EMAIL..."
BODY=$(python3 -c 'import json,os; print(json.dumps({"email":os.environ["AURA_ADMIN_EMAIL"],"password":os.environ["AURA_ADMIN_PASSWORD"]}))')
LOGIN=$(curl -s -w '\n%{http_code}' -X POST http://localhost:8080/api/v1/auth/login \
          -H 'Content-Type: application/json' --data-binary @- <<<"$BODY")
CODE=${LOGIN##*$'\n'}
[ "$CODE" = "200" ] || { echo "❌ login HTTP $CODE"; exit 1; }
TOKEN=$(printf '%s' "${LOGIN%$'\n'*}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8080/api/auto-trading/enable-paper \
         -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json')
[ "$CODE" = "200" ] || { echo "❌ enable-paper HTTP $CODE"; exit 1; }
echo "✅ enable-paper HTTP 200"

PAPER=$(docker exec "$DB" psql -U aura_user -d aura -tAc \
  "select s.config_overrides_json->>'paper_mode' from user_autopilot_settings s join users u on u.id=s.user_id where u.email='$AURA_ADMIN_EMAIL';")
[ "$PAPER" = "true" ] || { echo "❌ paper_mode στη βάση = '$PAPER'"; exit 1; }
echo "✅ paper_mode=true στη βάση"
