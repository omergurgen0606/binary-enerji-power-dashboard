#!/bin/bash
# Binary Enerji — aylık PDF enerji raporu gönderimi.
#
# Her ayın 1'inde çalışır ve BİR ÖNCEKİ ayın raporunu, raporu açık bırakmış
# ve e-postası doğrulanmış her kullanıcıya gönderir (kullanıcı başına tek
# e-posta, eriştiği her cihaz için bir PDF eki).
#
# HTTP yerine doğrudan modül fonksiyonunu çağırıyor: cron'a bir yönetici
# token'ı koymak zorunda kalmıyoruz. Manuel tetiklemek için panelden
# POST /admin/monthly-reports da var.
set -uo pipefail

COMPOSE_DIR="/root"
cd "$COMPOSE_DIR" || exit 1

# Argüman verilirse o dönemi gönderir: ./monthly_report.sh 2026 7
YEAR="${1:-}"
MONTH="${2:-}"

if [ -n "$YEAR" ] && [ -n "$MONTH" ]; then
  ARGS="year=$YEAR, month=$MONTH"
else
  ARGS=""
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] aylık rapor gönderimi başlıyor ($ARGS)"

docker compose exec -T api python -c "
import api
print(api.send_monthly_reports($ARGS))
"
STATUS=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] bitti (çıkış kodu $STATUS)"
exit $STATUS
