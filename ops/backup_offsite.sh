#!/bin/bash
# Binary Enerji — yedekleri ŞİFRELEYİP bulut depolamaya yükler.
#
# NEDEN: /root/backups sunucunun kendisiyle birlikte kaybolur. Bu betik
# yedeği sunucudan bağımsız bir yere kopyalar.
#
# ŞİFRELEME ZORUNLU: yedek, kullanıcı e-postalarını ve bcrypt parola
# özetlerini içeriyor. Üçüncü tarafa şifresiz yüklemek kabul edilemez.
# gpg simetrik (AES256) kullanılıyor.
#
# ⚠ PAROLA SUNUCUDAN BAĞIMSIZ SAKLANMALI. Parola yalnızca sunucudaki
#   .env dosyasında dururken sunucu kaybolursa, buluttaki yedekler
#   AÇILAMAZ ve tüm bu iş boşa gider. Parolayı parola yöneticinize kaydedin.
#
# SAĞLAYICI: Backblaze B2 öneriliyor — DigitalOcean Spaces de çalışır ama
# aynı sağlayıcıda olmak riski ilişkilendirir: DO hesabınızda bir sorun
# olursa (faturalandırma, askıya alma) hem sunucu hem yedek etkilenir.
#
# GEREKEN AYARLAR (/root/.env):
#   BACKUP_PASSPHRASE=...        (şifreleme parolası)
#   BACKUP_REMOTE=b2:kova-adi    (rclone hedefi)
# ve rclone yapılandırması: rclone config
set -uo pipefail

BACKUP_DIR="/root/backups"
COMPOSE_DIR="/root"
ALERT_EMAIL="wommit56@gmail.com"
RETENTION_DAYS=90          # bulutta yerelden uzun tutuluyor; asıl arşiv orası
LOG="$BACKUP_DIR/offsite.log"

cd "$COMPOSE_DIR" || exit 1

# .env'i shell ile source ETMİYORUZ. Dosyada tırnaksız boşluk ve `<>` içeren
# değerler var (ör. RESEND_FROM="Binary Enerji <no-reply@...>"); `. /root/.env`
# bunlara takılıp sessizce yarım yükleniyor ve parola hiç okunmuyordu.
# docker compose kendi ayrıştırıcısını kullandığı için dosyanın kendisi sorunlu
# değil — sorun yalnızca shell ile okumakta.
env_oku() {
  grep -m1 "^$1=" /root/.env 2>/dev/null | cut -d= -f2-
}
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-$(env_oku BACKUP_PASSPHRASE)}"
BACKUP_REMOTE="${BACKUP_REMOTE:-$(env_oku BACKUP_REMOTE)}"

send_alert() {
  local subject="$1" body="$2" resend_key
  resend_key=$(docker compose exec -T api printenv RESEND_API_KEY 2>/dev/null | tr -d '\r')
  [ -z "$resend_key" ] && return
  curl -s -X POST 'https://api.resend.com/emails' \
    -H "Authorization: Bearer ${resend_key}" -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys; print(json.dumps({'from':'Binary Enerji <no-reply@binaryenerji.com>','to':[sys.argv[1]],'subject':sys.argv[2],'text':sys.argv[3]}))" "$ALERT_EMAIL" "$subject" "$body")" >/dev/null 2>&1
}

fail() {
  echo "$(date -Iseconds) OFFSITE FAILED: $1" >> "$LOG"
  send_alert "⚠️ Binary Enerji: Bulut yedeği başarısız" "Bulut yedeklemesi başarısız oldu.

Hata: $1
Zaman: $(date -Iseconds)

Sunucudaki yedekler etkilenmedi ama sunucu dışında kopya OLUŞMADI.
Kontrol: ssh binaryenerji, sonra 'cat /root/backups/offsite.log'"
  exit 1
}

# Bulut hedefi henüz yapılandırılmamışsa SESSİZCE çık. Hata sayılsaydı,
# kurulum tamamlanana kadar her gece bir uyarı e-postası giderdi ve o
# uyarılar gerçek bir arıza olduğunda görmezden gelinir hale gelirdi.
if [ -z "${BACKUP_REMOTE:-}" ]; then
  echo "$(date -Iseconds) OFFSITE ATLANDI: BACKUP_REMOTE tanımlı değil (kurulum bekliyor)" >> "$LOG"
  exit 0
fi
[ -z "${BACKUP_PASSPHRASE:-}" ] && fail "BACKUP_PASSPHRASE tanımlı değil (/root/.env)"

# db_*.sql.gz iki farklı veritabanının yedeğini eşleştirir (power-dashboard
# VE binarysarj — bkz. backup.sh). "en son değişen TEK dosya" alınsaydı
# ikisinden biri sessizce buluta hiç yüklenmezdi; bu yüzden iki grup AYRI
# AYRI en-son'u alınıyor. `db_[0-9]*` yalnızca tarihle başlayanları (kendi
# veritabanımız) eşler, `db_binarysarj_*` öbürünü.
SON_DB=$(ls -t "$BACKUP_DIR"/db_[0-9]*.sql.gz 2>/dev/null | head -1)
SON_SARJ_DB=$(ls -t "$BACKUP_DIR"/db_binarysarj_*.sql.gz 2>/dev/null | head -1)
SON_UP=$(ls -t "$BACKUP_DIR"/uploads_*.tar.gz 2>/dev/null | head -1)
[ -z "$SON_DB" ] && fail "yüklenecek veritabanı yedeği bulunamadı"
[ -z "$SON_SARJ_DB" ] && fail "yüklenecek binarysarj veritabanı yedeği bulunamadı"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

for DOSYA in "$SON_DB" "$SON_SARJ_DB" "$SON_UP"; do
  [ -z "$DOSYA" ] && continue
  AD=$(basename "$DOSYA")
  # Yüklemeden ÖNCE bütünlük kontrolü: bozuk bir dosyayı buluta taşımak,
  # "yedeğim var" yanılsaması üretir.
  gzip -t "$DOSYA" 2>/dev/null || fail "$AD bozuk (gzip doğrulaması geçmedi)"
  gpg --batch --yes --symmetric --cipher-algo AES256 \
      --passphrase "$BACKUP_PASSPHRASE" \
      --output "$TMP/${AD}.gpg" "$DOSYA" 2>/dev/null || fail "$AD şifrelenemedi"
done

rclone copy "$TMP" "$BACKUP_REMOTE/" --no-traverse 2>>"$LOG" || fail "rclone yükleme başarısız"

# Yüklenen dosyalar gerçekten karşı tarafta mı?
UZAK_LISTE=$(rclone lsf "$BACKUP_REMOTE/" 2>/dev/null)
YUKLENEN=$(basename "$SON_DB").gpg
YUKLENEN_SARJ=$(basename "$SON_SARJ_DB").gpg
echo "$UZAK_LISTE" | grep -qx "$YUKLENEN" \
  || fail "yükleme sonrası doğrulama başarısız: $YUKLENEN uzak tarafta görünmüyor"
echo "$UZAK_LISTE" | grep -qx "$YUKLENEN_SARJ" \
  || fail "yükleme sonrası doğrulama başarısız: $YUKLENEN_SARJ uzak tarafta görünmüyor"

# Buluttaki eski yedekleri temizle
rclone delete "$BACKUP_REMOTE/" --min-age "${RETENTION_DAYS}d" 2>>"$LOG" || true

BOYUT=$(du -sh "$TMP" | cut -f1)
echo "$(date -Iseconds) OFFSITE OK: $YUKLENEN + $YUKLENEN_SARJ (+uploads), toplam ${BOYUT}, hedef ${BACKUP_REMOTE}" >> "$LOG"
