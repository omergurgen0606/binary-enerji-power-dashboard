#!/bin/bash
# Binary Enerji — haftalık yedekleme özeti e-postası.
# Bu e-posta düzenli gelmiyorsa (örn. cron durmuşsa) bu da bir uyarı sinyalidir.
set -uo pipefail

BACKUP_DIR="/root/backups"
ALERT_EMAIL="wommit56@gmail.com"
COMPOSE_DIR="/root"

cd "$COMPOSE_DIR" || exit 1

resend_key=$(docker compose exec -T api printenv RESEND_API_KEY 2>/dev/null | tr -d '\r')
if [ -z "$resend_key" ]; then
  exit 1
fi

LAST7=$(tail -n 50 "$BACKUP_DIR/backup.log" 2>/dev/null | awk -v d="$(date -d '7 days ago' -Iseconds)" '$0 > d' || tail -n 20 "$BACKUP_DIR/backup.log" 2>/dev/null)
OK_COUNT=$(echo "$LAST7" | grep -c "BACKUP OK" || true)
FAIL_COUNT=$(echo "$LAST7" | grep -c "BACKUP FAILED" || true)
LATEST_DB=$(ls -t "$BACKUP_DIR"/db_[0-9]*.sql.gz 2>/dev/null | head -1)
LATEST_SIZE=$(du -h "$LATEST_DB" 2>/dev/null | cut -f1)
LATEST_SARJ_DB=$(ls -t "$BACKUP_DIR"/db_binarysarj_*.sql.gz 2>/dev/null | head -1)
LATEST_SARJ_SIZE=$(du -h "$LATEST_SARJ_DB" 2>/dev/null | cut -f1)
DISK_FREE=$(df -h / | awk 'NR==2{print $4}')

BODY="Son 7 gün: ${OK_COUNT} başarılı, ${FAIL_COUNT} başarısız yedekleme.

Son yedek (power-dashboard): $(basename "$LATEST_DB" 2>/dev/null) (${LATEST_SIZE})
Son yedek (binarysarj): $(basename "$LATEST_SARJ_DB" 2>/dev/null) (${LATEST_SARJ_SIZE})
Disk boşta: ${DISK_FREE}

Bu bir haftalık otomatik durum e-postasıdır — her hafta gelmesi beklenir. Gelmemesi cron'un durduğunu gösterir.

---
$LAST7"

python3 -c "import json,sys; print(json.dumps({'from':'Binary Enerji <no-reply@binaryenerji.com>','to':[sys.argv[1]],'subject':sys.argv[2],'text':sys.argv[3]}))" \
  "$ALERT_EMAIL" "📋 Binary Enerji: Haftalık yedekleme durumu (${OK_COUNT} başarılı, ${FAIL_COUNT} hata)" "$BODY" > /tmp/_report_payload.json

curl -s -X POST 'https://api.resend.com/emails' \
  -H "Authorization: Bearer ${resend_key}" \
  -H 'Content-Type: application/json' \
  -d @/tmp/_report_payload.json > /dev/null 2>&1
rm -f /tmp/_report_payload.json
