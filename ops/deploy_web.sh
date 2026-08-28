#!/bin/bash
# Binary Enerji — web panelini yayına alır.
#
# DİKKAT: Hedef /var/www/dashboard. Eski /root/dist yolu terk edildi çünkü
# nginx'i çalıştıran www-data kullanıcısı /root altını okuyamıyor (500 hatası
# veriyordu). Bu betik, yanlış dizine deploy edip "yayınlandı" sanmayı
# önlemek için var: kopyalamadan sonra canlı sitenin gerçekten yeni build'i
# sunduğunu doğruluyor.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${1:-binaryenerji}"
TARGET="/var/www/dashboard"
SITE="https://binaryenerji.com"

cd "$REPO_DIR"

echo "→ build alınıyor"
npm run build >/dev/null

BUNDLE="$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' dist/index.html | head -1)"
echo "→ üretilen bundle: $BUNDLE"

echo "→ $HOST:$TARGET dizinine kopyalanıyor"
rsync -az dist/ "$HOST:$TARGET/"
ssh "$HOST" "chown -R www-data:www-data $TARGET"

echo "→ doğrulanıyor"
LIVE="$(curl -s "$SITE/" | grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' | head -1)"
if [ "$LIVE" = "$BUNDLE" ]; then
  echo "✓ yayında: $LIVE"
else
  echo "✗ canlı site hâlâ $LIVE sunuyor (beklenen $BUNDLE)" >&2
  exit 1
fi
