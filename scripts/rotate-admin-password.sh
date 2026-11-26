#!/bin/bash
# Αλλαγή κωδικού του admin χρήστη ΜΙΑ φορά + αποθήκευση στο /root/aura-secrets.env (chmod 600).
# Ο κωδικός δεν περνά ποτέ ως όρισμα (δεν φαίνεται στο ps) — μόνο από stdin.
#
#   /root/aura-private-bootstrap/scripts/rotate-admin-password.sh
set -euo pipefail
SECRETS=/root/aura-secrets.env
EMAIL=${AURA_ADMIN_EMAIL:-valentinos@aura.com}

read -rsp "Νέος κωδικός για $EMAIL: " P1; echo
read -rsp "Ξανά: " P2; echo
[ "$P1" = "$P2" ] || { echo "Δεν ταιριάζουν"; exit 1; }
[ ${#P1} -ge 12 ] || { echo "Τουλάχιστον 12 χαρακτήρες"; exit 1; }

# bcrypt + UPDATE μέσα στο container· ο κωδικός μπαίνει από stdin
printf '%s' "$P1" | docker exec -i -e EMAIL="$EMAIL" aura-backend python3 -c '
import os, sys, bcrypt
from database.connection import SessionLocal
from sqlalchemy import text
pw = sys.stdin.read()
h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
db = SessionLocal()
n = db.execute(text("UPDATE users SET password_hash=:h WHERE email=:e"), {"h": h, "e": os.environ["EMAIL"]}).rowcount
db.commit(); db.close()
sys.exit(0 if n == 1 else f"UPDATE άγγιξε {n} γραμμές — αναμενόταν 1")
'

umask 077
{
  echo "# Aura secrets — μην μπαίνει σε git. Φορτώνεται με: set -a; . $SECRETS; set +a"
  echo "AURA_ADMIN_EMAIL='$EMAIL'"
  printf "AURA_ADMIN_PASSWORD='%s'\n" "${P1//\'/\'\\\'\'}"
} > "$SECRETS"
chmod 600 "$SECRETS"
echo "✅ Κωδικός άλλαξε, αποθηκεύτηκε στο $SECRETS ($(stat -c %a "$SECRETS"))"
