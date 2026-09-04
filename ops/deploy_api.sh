#!/bin/bash
# Binary Enerji — api.py'ı ÜRETİME dağıtır.
#
# Bugüne kadar üretime dağıtmak "scp + docker compose up" idi; hiçbir kapı
# yoktu. 28 Ağustos 2026'daki bağlantı havuzu hatası tam bu yoldan geçip
# 22 yazma uç noktasını sessizce bozdu. Bu betik iki kapı koyuyor:
#
#   1. Testler geçmeden dağıtım yok.
#   2. Dağıtımdan sonra /health doğrulanır -- ayakta mı, doğru veritabanında
#      mı, ortamını doğru tanıyor mu.
#
# Staging'i önce denemek için: ops/deploy_staging.sh
set -euo pipefail

HOST="${1:-binaryenerji}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [ "${TESTLERI_ATLA:-}" = "1" ]; then
  echo "⚠ testler ATLANDI (TESTLERI_ATLA=1) -- yalnızca acil geri alma için"
else
  echo "→ testler"
  "$REPO/ops/test_calistir.sh" "$HOST" | tail -3
fi

echo "→ api.py kopyalanıyor"
scp -q "$REPO/api.py" "$REPO/iyzico.py" "$REPO/Dockerfile" "$REPO/requirements.txt" "$HOST:/root/"
scp -q "$REPO/docker-compose.yml" "$HOST:/root/docker-compose.yml"

echo "→ üretim api yeniden kuruluyor"
ssh "$HOST" "cd /root && docker compose up -d --build api" 2>&1 | tail -3

echo "→ ayağa kalkması bekleniyor"
for _ in $(seq 1 30); do
  if ssh "$HOST" "curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1"; then break; fi
  sleep 2
done

SAGLIK=$(ssh "$HOST" "curl -s http://127.0.0.1:8000/health")
echo "  $SAGLIK"

echo "$SAGLIK" | grep -q '"ortam":"uretim"' \
  || { echo "✗ üretim kendini üretim olarak tanımıyor -- STAGING sızmış olabilir" >&2; exit 1; }
echo "$SAGLIK" | grep -q '"veritabani_erisimi":true' \
  || { echo "✗ üretim veritabanına ulaşamıyor" >&2; exit 1; }
echo "$SAGLIK" | grep -q '"veritabani":"postgres"' \
  || { echo "✗ üretim YANLIŞ VERİTABANINA bağlı" >&2; exit 1; }

echo "✓ üretim yayında"
