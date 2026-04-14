#!/bin/bash

cat <<'EOF' >/etc/logrotate.d/aura
/var/log/aura-monitor.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF

echo "Logrotate config installed: /etc/logrotate.d/aura"
