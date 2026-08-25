#!/bin/bash
# Binary Enerji — basit sağlık kontrolü. Ana siteyi periyodik kontrol eder,
# arka arkaya 2 başarısız denemeden sonra uyarı e-postası gönderir, düzelince
# de haber verir. Bu VPS'in KENDİSİ üzerinde çalıştığı için VPS tamamen
# çökerse (ör. güç kesintisi) bu betik de çalışamaz — o senaryo için harici
# bir servis (UptimeRobot vb.) gerekir.
set -uo pipefail

URL="https://binaryenerji.com/"
STATE_FILE="/root/backups/.health_state"
COMPOSE_DIR="/root"
ALERT_EMAIL="wommit56@gmail.com"

cd "$COMPOSE_DIR" || exit 1
mkdir -p /root/backups

send_alert() {
  local subject="$1"
  local body="$2"
  local resend_key
  resend_key=$(docker compose exec -T api printenv RESEND_API_KEY 2>/dev/null | tr -d '\r')
  [ -z "$resend_key" ] && return
  curl -s -X POST 'https://api.resend.com/emails' \
    -H "Authorization: Bearer ${resend_key}" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys; print(json.dumps({'from':'Binary Enerji <no-reply@binaryenerji.com>','to':[sys.argv[1]],'subject':sys.argv[2],'text':sys.argv[3]}))" "$ALERT_EMAIL" "$subject" "$body")" \
    > /dev/null 2>&1
}

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL")
PREV_FAILS=$(cat "$STATE_FILE" 2>/dev/null || echo 0)

if [ "$HTTP_CODE" = "200" ]; then
  if [ "$PREV_FAILS" -ge 2 ]; then
    send_alert "✅ Binary Enerji: Site tekrar çalışıyor" "binaryenerji.com tekrar erişilebilir durumda ($(date -Iseconds))."
  fi
  echo 0 > "$STATE_FILE"
else
  NEW_FAILS=$((PREV_FAILS + 1))
  echo "$NEW_FAILS" > "$STATE_FILE"
  if [ "$NEW_FAILS" -eq 2 ]; then
    send_alert "🔴 Binary Enerji: Site erişilemiyor" "binaryenerji.com son 2 denemede yanıt vermedi (HTTP ${HTTP_CODE}), zaman: $(date -Iseconds).

Sunucuya bağlanıp kontrol edin: ssh binaryenerji, sonra 'docker compose ps' ve 'docker compose logs api --tail 50'"
  fi
fi
