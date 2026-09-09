#!/bin/bash
# Binary Enerji — günlük otomatik yedekleme (veritabanı + yüklenen dosyalar)
set -uo pipefail

BACKUP_DIR="/root/backups"
DATE=$(date +%Y-%m-%d_%H%M)
RETENTION_DAYS=14
COMPOSE_DIR="/root"
ALERT_EMAIL="wommit56@gmail.com"

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_DIR" || exit 1

DB_FILE="$BACKUP_DIR/db_${DATE}.sql.gz"
UPLOADS_FILE="$BACKUP_DIR/uploads_${DATE}.tar.gz"
# Binary Şarj aynı Postgres sürecinde AYRI bir veritabanı (binarysarj) —
# bellek tasarrufu için ikinci bir Postgres konteyneri açmak yerine paylaşımlı
# sürece eklendi (bkz. claude_code/infra/docker-compose.vps-shared.yml). Ayrı
# veritabanı olduğu için "pg_dump ... postgres" onu KAPSAMAZ; unutulursa
# Binary Şarj'ın istasyon/kullanıcı verisi hiç yedeklenmez.
SARJ_DB_FILE="$BACKUP_DIR/db_binarysarj_${DATE}.sql.gz"
# Operatörün yüklediği istasyon fotoğrafları ayrı bir Docker biriminde
# (binarysarj_sarj_media). Veritabanı yalnızca dosya YOLUNU tutuyor; birim
# yedeklenmezse geri yüklemeden sonra istasyonlar kırık görsellerle açılır.
SARJ_MEDIA_FILE="$BACKUP_DIR/sarj_media_${DATE}.tar.gz"

send_alert() {
  local subject="$1"
  local body="$2"
  local resend_key
  resend_key=$(docker compose exec -T api printenv RESEND_API_KEY 2>/dev/null | tr -d '\r')
  if [ -z "$resend_key" ]; then
    echo "$(date -Iseconds) UYARI E-POSTASI GONDERILEMEDI (RESEND_API_KEY bulunamadi): $subject" >> "$BACKUP_DIR/backup.log"
    return
  fi
  curl -s -X POST 'https://api.resend.com/emails' \
    -H "Authorization: Bearer ${resend_key}" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys; print(json.dumps({'from':'Binary Enerji <no-reply@binaryenerji.com>','to':[sys.argv[1]],'subject':sys.argv[2],'text':sys.argv[3]}))" "$ALERT_EMAIL" "$subject" "$body")" \
    > /dev/null 2>&1
}

fail() {
  echo "$(date -Iseconds) BACKUP FAILED: $1" >> "$BACKUP_DIR/backup.log"
  send_alert "⚠️ Binary Enerji: Yedekleme başarısız" "Otomatik yedekleme başarısız oldu.

Hata: $1
Zaman: $(date -Iseconds)

Sunucuya bağlanıp kontrol edin: ssh binaryenerji, sonra 'cat /root/backups/backup.log'"
  exit 1
}

docker compose exec -T timescaledb pg_dump -U postgres postgres 2>/dev/null | gzip > "$DB_FILE"
if [ ! -s "$DB_FILE" ]; then
  fail "pg_dump başarısız veya boş çıktı verdi"
fi

docker compose exec -T timescaledb pg_dump -U postgres binarysarj 2>/dev/null | gzip > "$SARJ_DB_FILE"
if [ ! -s "$SARJ_DB_FILE" ]; then
  fail "binarysarj pg_dump başarısız veya boş çıktı verdi"
fi

if ! docker run --rm -v root_avatar_uploads:/data -v "$BACKUP_DIR":/backup alpine tar czf "/backup/uploads_${DATE}.tar.gz" -C /data . 2>/dev/null; then
  fail "uploads (avatar/firmware) yedeği başarısız"
fi

if ! docker run --rm -v binarysarj_sarj_media:/data -v "$BACKUP_DIR":/backup alpine tar czf "/backup/sarj_media_${DATE}.tar.gz" -C /data . 2>/dev/null; then
  fail "binarysarj istasyon fotoğrafları yedeği başarısız"
fi

# 14 günden eski yedekleri temizle
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "sarj_media_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
SARJ_DB_SIZE=$(du -h "$SARJ_DB_FILE" | cut -f1)
UP_SIZE=$(du -h "$UPLOADS_FILE" 2>/dev/null | cut -f1)
SARJ_MEDIA_SIZE=$(du -h "$SARJ_MEDIA_FILE" 2>/dev/null | cut -f1)
echo "$(date -Iseconds) BACKUP OK: db=${DB_SIZE} binarysarj=${SARJ_DB_SIZE} uploads=${UP_SIZE} sarj_media=${SARJ_MEDIA_SIZE}" >> "$BACKUP_DIR/backup.log"
