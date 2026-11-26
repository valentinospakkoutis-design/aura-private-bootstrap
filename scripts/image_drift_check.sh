#!/bin/bash
# Σύγκριση κώδικα: τι τρέχει μέσα στο aura-backend έναντι του repo στον host.
# Μόνο ανάγνωση. Δεν διορθώνει τίποτα — κάνει την απόκλιση ορατή.
#
# Cron (Δευτέρα 06:20 UTC):
#   20 6 * * 1 /root/aura-private-bootstrap/scripts/image_drift_check.sh >> /var/log/aura-drift.log 2>&1
#
# Exit 0 = καμία διαφορά σε κοινά αρχεία, 1 = υπάρχει διαφορά, 2 = σφάλμα.

set -u
REPO=/root/aura-private-bootstrap/backend
C=aura-backend
TS=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
export LC_ALL=C   # ίδια ταξινόμηση και στις δύο πλευρές — αλλιώς ψεύτικες διαφορές

list='find . -name "*.py" -not -path "./venv/*" -not -path "*/__pycache__/*" | LC_ALL=C sort | xargs md5sum'

img=$(docker exec "$C" sh -c "cd /app && $list" 2>/dev/null) || { echo "[$TS] ERROR container $C unreachable"; exit 2; }
host=$(cd "$REPO" && eval "$list")

# join στο path: πεδίο 2 = path
j() { echo "$1" | awk '{print $2, $1}' | sort; }
differs=$(join <(j "$img") <(j "$host") | awk '$2 != $3 {print $1}')
only_img=$(join -v1 <(j "$img") <(j "$host") | awk '{print $1}')
only_repo=$(join -v2 <(j "$img") <(j "$host") | awk '{print $1}')

if [ -z "$differs" ] && [ -z "$only_img" ]; then
    echo "[$TS] OK — κοινά αρχεία ταυτίζονται ($(echo "$only_repo" | grep -c .) αρχεία μόνο στο repo, αδρανή)"
    exit 0
fi

echo "[$TS] DRIFT — ο κώδικας που τρέχει δεν είναι ο κώδικας του repo"
[ -n "$differs" ]  && { echo "  ΔΙΑΦΕΡΟΥΝ (τρέχει άλλη έκδοση):"; echo "$differs"  | sed 's/^/    /'; }
[ -n "$only_img" ] && { echo "  ΜΟΝΟ ΣΤΟ CONTAINER:";             echo "$only_img" | sed 's/^/    /'; }
[ -n "$only_repo" ] && echo "  μόνο στο repo (αδρανή μέχρι rebuild): $(echo "$only_repo" | grep -c .) αρχεία"
echo "[$TS] DRIFT detected" >&2
exit 1
