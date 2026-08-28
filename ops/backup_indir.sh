#!/bin/bash
# Binary Enerji — yedekleri sunucudan KENDİ BİLGİSAYARINA indirir.
#
# NEDEN: Sunucudaki /root/backups yedekleri, sunucunun kendisiyle birlikte
# kaybolur. Droplet silinirse, diski bozulursa veya hesap askıya alınırsa
# elinizde hiçbir şey kalmaz. Bu betik yedeği başka bir fiziksel yere —
# sizin bilgisayarınıza — kopyalar. Hiçbir bulut hesabı gerektirmez.
#
# Bulut yedeği (ops/backup_offsite.sh) kurulduğunda bu betik gereksiz olmaz:
# iki bağımsız kopya, tek kopyadan iyidir.
#
# KULLANIM:  ./ops/backup_indir.sh            (son yedeği indirir)
#            ./ops/backup_indir.sh --hepsi    (sunucudaki tüm yedekleri indirir)
set -euo pipefail

HOST="${BINARYENERJI_HOST:-binaryenerji}"
HEDEF="${BINARYENERJI_YEDEK_DIZINI:-$HOME/Desktop/BinaryEnerji-Yedekler}"
UZAK="/root/backups"

mkdir -p "$HEDEF"

if [ "${1:-}" = "--hepsi" ]; then
  echo "→ sunucudaki tüm yedekler indiriliyor"
  rsync -az --info=progress2 "$HOST:$UZAK/"*.gz "$HEDEF/"
else
  SON_DB=$(ssh "$HOST" "ls -t $UZAK/db_*.sql.gz 2>/dev/null | head -1")
  SON_UP=$(ssh "$HOST" "ls -t $UZAK/uploads_*.tar.gz 2>/dev/null | head -1")
  if [ -z "$SON_DB" ]; then
    echo "✗ sunucuda yedek bulunamadı" >&2
    exit 1
  fi
  echo "→ indiriliyor: $(basename "$SON_DB"), $(basename "$SON_UP")"
  rsync -az "$HOST:$SON_DB" "$HOST:$SON_UP" "$HEDEF/"
fi

# --- Doğrulama: indirilen dosya gerçekten açılabiliyor mu? ---
# Bozuk bir yedek, yedek olmamasından daha tehlikelidir: var sanırsınız.
EN_YENI=$(ls -t "$HEDEF"/db_*.sql.gz 2>/dev/null | head -1)
if [ -z "$EN_YENI" ]; then
  echo "✗ indirilen veritabanı yedeği bulunamadı" >&2
  exit 1
fi

if ! gzip -t "$EN_YENI" 2>/dev/null; then
  echo "✗ İNDİRİLEN YEDEK BOZUK: $EN_YENI" >&2
  exit 1
fi

SATIR=$(gzip -dc "$EN_YENI" | wc -l | tr -d ' ')
TABLO=$(gzip -dc "$EN_YENI" | grep -c "^CREATE TABLE" || true)
BOYUT=$(du -h "$EN_YENI" | cut -f1)

echo "✓ doğrulandı: $(basename "$EN_YENI")  ($BOYUT, $SATIR satır, $TABLO tablo)"
echo "  konum: $HEDEF"

if [ "$TABLO" -lt 10 ]; then
  echo "⚠ UYARI: yedekte yalnızca $TABLO tablo var, beklenenden az. Kontrol edin." >&2
  exit 1
fi
