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

# --- Kaynak eşikleri ---
# Sunucu tek çekirdek / 961 MB. Ölçülen darboğaz artık DİSK: cihaz başına
# ~340 MB kararlı durum, ~16 GB boş alanla ~47 cihaz. Bu uyarılar sınıra
# çarpmadan ÖNCE haber vermek için; "disk doldu, veri toplama durdu" ile
# öğrenmek en kötü senaryo.
DISK_WARN_PCT=80
MEM_WARN_PCT=90
RES_STATE="/root/backups/.resource_state"

check_resources() {
  local disk_pct mem_pct swap_used prev
  disk_pct=$(df / | awk 'NR==2 {gsub("%","",$5); print $5}')
  mem_pct=$(free | awk '/^Mem:/ {printf "%d", ($2-$7)/$2*100}')
  swap_used=$(free -m | awk '/^Swap:/ {print $3}')
  prev=$(cat "$RES_STATE" 2>/dev/null || echo "ok")

  local msg=""
  [ "$disk_pct" -ge "$DISK_WARN_PCT" ] && msg="${msg}Disk kullanımı %${disk_pct}. Dolduğunda PostgreSQL yazmayı reddeder ve veri toplama durur.
"
  [ "$mem_pct" -ge "$MEM_WARN_PCT" ] && msg="${msg}Bellek kullanımı %${mem_pct} (swap kullanımı: ${swap_used} MB).
"

  if [ -n "$msg" ]; then
    if [ "$prev" = "ok" ]; then
      send_alert "⚠️ Binary Enerji: Sunucu kaynak uyarısı" "$msg
Sunucu: ssh binaryenerji — 'df -h', 'free -m', 'docker stats --no-stream'"
      echo "uyarildi" > "$RES_STATE"
    fi
  else
    [ "$prev" != "ok" ] && send_alert "✅ Binary Enerji: Sunucu kaynakları normale döndü" "Disk %${disk_pct}, bellek %${mem_pct}."
    echo "ok" > "$RES_STATE"
  fi
}

check_resources

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
