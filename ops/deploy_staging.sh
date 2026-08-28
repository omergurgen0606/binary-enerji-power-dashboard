#!/bin/bash
# Binary Enerji — staging'e dağıt.
#
# NEDEN VAR: 28 Ağustos 2026'da bağlantı havuzu hatası doğrudan üretime gitti
# ve 22 yazma uç noktası sessizce yazdıklarını atmaya başladı. Kimse fark
# etmedi çünkü hata yalnızca gerçek bir çalışan süreçte görünüyordu. Staging,
# aynı sınıftan bir sonraki hatanın müşteriye ulaşmadan görülebileceği yer.
#
# Staging üretimle AYNI mosquitto akışını dinler (gerçek cihaz verisi) ama
# AYRI bir veritabanına yazar ve dış dünyaya hiçbir şey göndermez -- e-posta,
# push bildirimi ve cihaz komutları api.py içindeki STAGING=1 ile kapalı
# (bkz. tests/test_staging.py). Token sırrı da türetilerek ayrılır, yani
# staging oturumu üretim panelini açmaz.
set -euo pipefail

HOST="${1:-binaryenerji}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
STAGING_DB="binaryenerji_staging"
STAGING_URL="https://binaryenerji.com:8443"

echo "→ staging veritabanı hazırlanıyor ($STAGING_DB)"
VAR=$(ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d postgres -tAc \
  \"SELECT 1 FROM pg_database WHERE datname='$STAGING_DB'\"" | tr -d ' ')
if [ "$VAR" != "1" ]; then
  echo "  veritabanı yok, oluşturuluyor ve şema uygulanıyor"
  ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d postgres \
    -c \"CREATE DATABASE $STAGING_DB\"" >/dev/null
  ssh "$HOST" "docker exec -i \$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB -v ON_ERROR_STOP=1" \
    < "$REPO/ops/schema/00-baseline.sql" >/dev/null
else
  echo "  mevcut"
fi

echo "→ nginx staging bloğu"
scp -q "$REPO/ops/nginx-staging.conf" "$HOST:/etc/nginx/sites-available/dashboard-staging"
ssh "$HOST" "ln -sf /etc/nginx/sites-available/dashboard-staging /etc/nginx/sites-enabled/dashboard-staging && \
  mkdir -p /var/www/dashboard-staging && nginx -t >/dev/null 2>&1 && systemctl reload nginx"
ssh "$HOST" "ufw allow 8443/tcp >/dev/null 2>&1 || true"

echo "→ api ve compose kopyalanıyor"
scp -q "$REPO/api.py" "$HOST:/root/api.py"
scp -q "$REPO/docker-compose.yml" "$HOST:/root/docker-compose.yml"

# SADECE staging servisi ayağa kalkar. Üretim api'sine dokunulmaz: staging'e
# dağıtmanın üretimi yeniden başlatması, staging'in var olma amacına aykırı.
echo "→ api-staging başlatılıyor (üretim api'sine dokunulmuyor)"
ssh "$HOST" "cd /root && docker compose up -d --build api-staging" 2>&1 | tail -3

echo "→ web bundle (staging)"
cd "$REPO"
npx vite build >/dev/null 2>&1
rsync -a --delete dist/ "$HOST:/var/www/dashboard-staging/"

echo "→ duman testi"
SAGLIK=$(ssh "$HOST" "curl -sk $STAGING_URL/api/health")
echo "  $SAGLIK"

# Ortamın kendini doğru tanıdığını doğrula. Bu kontrol olmadan, staging'e
# dağıttığını sanıp üretime dağıtmak sessizce mümkün.
echo "$SAGLIK" | grep -q '"ortam":"staging"' \
  || { echo "✗ staging kendini staging olarak tanımıyor -- STAGING=1 geçmemiş" >&2; exit 1; }
echo "$SAGLIK" | grep -q "\"veritabani\":\"$STAGING_DB\"" \
  || { echo "✗ staging YANLIŞ VERİTABANINA bağlı -- üretim verisine yazıyor olabilir" >&2; exit 1; }
echo "$SAGLIK" | grep -q '"veritabani_erisimi":true' \
  || { echo "✗ staging veritabanına ulaşamıyor" >&2; exit 1; }

# Üretimin bu dağıtımdan etkilenmediğini de doğrula.
URETIM=$(ssh "$HOST" "curl -s http://127.0.0.1:8000/health")
echo "$URETIM" | grep -q '"ortam":"uretim"' \
  || { echo "✗ ÜRETİM staging moduna geçmiş -- derhal geri alın" >&2; exit 1; }

echo "✓ staging yayında: $STAGING_URL"
echo "  üretim etkilenmedi: $URETIM"
