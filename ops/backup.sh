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

# Dosya boyutuna bakmak YETMİYOR: pg_dump hiç çalışmasa bile gzip ~20 baytlık
# geçerli bir dosya üretir ve eski "-s" kontrolü bunu başarılı yedek sayıyordu
# (Ekim 2026 Contabo taşınmasında bulundu -- olmayan binarysarj veritabanı her
# gece "başarıyla" yedekleniyor görünecekti). Artık pipe'ın çıkış kodu
# (pipefail ile pg_dump'ınki) ve dosyanın gerçekten bir dump olduğu kontrol
# ediliyor. İçerik kontrolü pipefail'siz bir alt kabukta: head erken kapanınca
# gzip SIGPIPE alır ve pipefail eşleşmiş bir grep'i bile başarısız sayardı.
dump_al() {  # $1 = veritabanı, $2 = hedef dosya
  docker compose exec -T timescaledb pg_dump -U postgres "$1" 2>>"$BACKUP_DIR/backup.log" | gzip > "$2" \
    && ( set +o pipefail; gzip -dc "$2" | head -c 4096 | grep -q "PostgreSQL database dump" )
}

dump_al postgres "$DB_FILE" || fail "pg_dump başarısız veya geçersiz çıktı (postgres)"

# Binary Şarj aynı Postgres sürecinde ayrı bir veritabanı. Sunucuda kurulu
# değilse atlanıyor ve logda açıkça "yok" yazıyor: "yok" ile "yedeklenemedi"
# farklı şeyler -- ilki hata e-postası üretmemeli, ikincisi üretmeli.
SARJ_VAR=$(docker compose exec -T timescaledb psql -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='binarysarj'" 2>/dev/null | tr -d '[:space:]')
if [ "$SARJ_VAR" = "1" ]; then
  dump_al binarysarj "$SARJ_DB_FILE" || fail "pg_dump başarısız veya geçersiz çıktı (binarysarj)"
else
  SARJ_DB_FILE=""
fi

if ! docker run --rm -v root_avatar_uploads:/data -v "$BACKUP_DIR":/backup alpine tar czf "/backup/uploads_${DATE}.tar.gz" -C /data . 2>/dev/null; then
  fail "uploads (avatar/firmware) yedeği başarısız"
fi

# "docker run -v ad:/data" olmayan bir birimi sessizce BOŞ olarak oluşturur;
# önce var olduğu doğrulanıyor, yoksa boş bir arşiv yedek sanılmasın.
if docker volume inspect binarysarj_sarj_media >/dev/null 2>&1; then
  if ! docker run --rm -v binarysarj_sarj_media:/data -v "$BACKUP_DIR":/backup alpine tar czf "/backup/sarj_media_${DATE}.tar.gz" -C /data . 2>/dev/null; then
    fail "binarysarj istasyon fotoğrafları yedeği başarısız"
  fi
else
  SARJ_MEDIA_FILE=""
fi

# 14 günden eski yedekleri temizle
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "sarj_media_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
SARJ_DB_SIZE=$([ -n "$SARJ_DB_FILE" ] && du -h "$SARJ_DB_FILE" | cut -f1 || echo "yok")
UP_SIZE=$(du -h "$UPLOADS_FILE" 2>/dev/null | cut -f1)
SARJ_MEDIA_SIZE=$([ -n "$SARJ_MEDIA_FILE" ] && du -h "$SARJ_MEDIA_FILE" 2>/dev/null | cut -f1 || echo "yok")
echo "$(date -Iseconds) BACKUP OK: db=${DB_SIZE} binarysarj=${SARJ_DB_SIZE} uploads=${UP_SIZE} sarj_media=${SARJ_MEDIA_SIZE}" >> "$BACKUP_DIR/backup.log"
