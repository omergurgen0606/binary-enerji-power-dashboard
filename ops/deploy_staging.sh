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

# Şema kayması: staging bir kez kurulup sonra üretime göç uygulanırsa staging
# geride kalır ve uygulama orada eksik sütunla patlar -- test paketindeki aynı
# kontrolün staging karşılığı. Sütun düzeyinde bakılıyor, tablo düzeyinde değil:
# kaymanın bu sefer geldiği yer yeni bir tablo değil, yeni bir SÜTUNDU.
echo "→ şema kayması kontrolü (üretim ↔ staging)"
# Yalnizca TEMEL TABLOLAR karsilastiriliyor. Sürekli toplamalar (measurements_15min
# gibi TimescaleDB materialized view'lari) staging'de yok ve bu kontrolü sürekli
# kirmiyor olmalari gerekiyor -- uygulamanin YAZDIGI yer tablolar; eksik bir
# sütun orada patlar, eksik bir rollup yalnizca daha yavas sorgu demek.
SEMA_SQL="SELECT c.table_name||'.'||c.column_name FROM information_schema.columns c JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name WHERE c.table_schema='public' AND t.table_type='BASE TABLE' ORDER BY 1"
U_SEMA=$(ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d postgres -tAc \"$SEMA_SQL\"" | sort)
S_SEMA=$(ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB -tAc \"$SEMA_SQL\"" | sort)
EKSIK=$(comm -23 <(echo "$U_SEMA") <(echo "$S_SEMA"))
if [ -n "$EKSIK" ]; then
  echo "✗ ŞEMA KAYMASI: üretimde olup staging'de olmayan sütunlar:" >&2
  echo "$EKSIK" | sed 's/^/    /' >&2
  echo "  İlgili göçü staging'e de uygulayın:" >&2
  echo "    ssh $HOST \"docker exec -i \\\$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB\" < ops/schema/<goc>.sql" >&2
  exit 1
fi
echo "  ✓ staging üretimle aynı"

echo "→ nginx staging bloğu"
scp -q "$REPO/ops/nginx-staging.conf" "$HOST:/etc/nginx/sites-available/dashboard-staging"
ssh "$HOST" "ln -sf /etc/nginx/sites-available/dashboard-staging /etc/nginx/sites-enabled/dashboard-staging && \
  mkdir -p /var/www/dashboard-staging && nginx -t >/dev/null 2>&1 && systemctl reload nginx"
ssh "$HOST" "ufw allow 8443/tcp >/dev/null 2>&1 || true"

echo "→ api ve compose kopyalanıyor"
scp -q "$REPO/api.py" "$REPO/iyzico.py" "$REPO/Dockerfile" "$REPO/requirements.txt" "$HOST:/root/"
scp -q "$REPO/docker-compose.yml" "$HOST:/root/docker-compose.yml"

# SADECE staging servisi ayağa kalkar. Üretim api'sine dokunulmaz: staging'e
# dağıtmanın üretimi yeniden başlatması, staging'in var olma amacına aykırı.
echo "→ api-staging başlatılıyor (üretim api'sine dokunulmuyor)"
ssh "$HOST" "cd /root && docker compose up -d --build api-staging" 2>&1 | tail -3

# Konteynerin hazir olmasini bekle. Bu olmadan duman testi henuz acilmamis
# servise gidiyor, nginx hata sayfasi donuyor ve dagitim "staging kendini
# tanimiyor" diye YANLIS sekilde basarisiz oluyordu -- gercek bir sorun yokken.
echo "→ ayağa kalkması bekleniyor"
for _ in $(seq 1 30); do
  if ssh "$HOST" "curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1"; then break; fi
  sleep 2
done

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

# Broker'in hala ayakta oldugunu dogrula. Bu betik TUM docker-compose.yml'i
# kopyaliyor, yani yalnizca api-staging'i degil butun yigini etkileyebiliyor.
# Bir kez tam olarak bu oldu: sunucuda elle yapilmis TLS yapilandirmasi
# (8883 + sertifika baglamasi) depodaki kopya tarafindan geri alindi. Konteyner
# calismaya devam ettigi icin hicbir sey belli olmadi -- ta ki mosquitto bir
# sonraki yeniden baslatmada sertifikayi bulamayip cokme dongusune girene kadar.
# Sessiz bir mayin; bu kontrol onu dagitim aninda gorunur kiliyor.
echo "→ broker kontrolü"
BROKER=$(ssh "$HOST" "docker ps --filter name=mosquitto --format '{{.Status}}'")
echo "$BROKER" | grep -q '^Up' \
  || { echo "✗ mosquitto ayakta değil ($BROKER) -- compose kopyalanınca bozulmuş olabilir" >&2; exit 1; }
echo "  ✓ broker ayakta: $BROKER"

# Üretimin bu dağıtımdan etkilenmediğini de doğrula.
URETIM=$(ssh "$HOST" "curl -s http://127.0.0.1:8000/health")
echo "$URETIM" | grep -q '"ortam":"uretim"' \
  || { echo "✗ ÜRETİM staging moduna geçmiş -- derhal geri alın" >&2; exit 1; }

echo "✓ staging yayında: $STAGING_URL"
echo "  üretim etkilenmedi: $URETIM"
