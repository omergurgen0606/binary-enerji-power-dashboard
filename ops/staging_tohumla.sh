#!/bin/bash
# Binary Enerji — staging veritabanını üretimin hesap/yapı verisiyle doldurur.
#
# NEDEN GEREKLİ: staging şemadan sıfır kurulduğu için içinde hiç kullanıcı yok,
# ve staging'de e-posta kapalı olduğundan normal kayıt akışı da işlemez —
# doğrulama linki hiçbir zaman gelmez. Tohumlamadan staging'e giriş yapmak
# imkânsız, dolayısıyla mobil build varyantları da işe yaramaz.
#
# NE KOPYALANIR: kullanıcılar, organizasyon/tesis/departman yapısı, cihazlar,
# tarifeler, alarm kuralları, abonelikler. Yani panelin çalışması için gereken
# her şey.
#
# NE KOPYALANMAZ:
#   - Ölçüm/zaman serisi tabloları (measurements, device_energy, device_stats,
#     device_peaks, device_demand, device_harmonics). Devasa olabilirler ve
#     staging zaten aynı MQTT akışını dinleyip kendi verisini biriktiriyor.
#   - alarm_events, audit_log, org_invites, push_subscriptions,
#     subscription_events, deletion_requests. Bunlar ortama özgü geçmiş;
#     kopyalanırsa staging'de üretimin olay geçmişi varmış gibi görünür.
#
# NOT: users tablosu şifre özetlerini de taşır. Aynı kişinin kendi verisi ve
# aynı sunucuda kalıyor; staging'in token sırrı ayrı olduğu için staging'de
# açılan oturum üretim panelini açmaz.
set -euo pipefail

HOST="${1:-binaryenerji}"
STAGING_DB="binaryenerji_staging"

TABLOLAR="users organizations org_members facilities departments \
member_facilities member_departments devices device_tariff device_settings \
device_info alarm_rules subscriptions firmware_builds"

VIRGULLU=$(echo $TABLOLAR | tr ' ' ',')
DUMP_ARGS=""
for t in $TABLOLAR; do DUMP_ARGS="$DUMP_ARGS -t $t"; done

echo "→ hedef doğrulanıyor"
ORTAM=$(ssh "$HOST" "curl -s http://127.0.0.1:8001/health")
echo "$ORTAM" | grep -q "\"veritabani\":\"$STAGING_DB\"" \
  || { echo "✗ 8001 portundaki servis $STAGING_DB'ye bağlı değil, durduruldu" >&2; exit 1; }

# Yanlışlıkla üretime yazmaya karşı son kapı: hedef adı sabit ve kontrol ediliyor.
if [ "$STAGING_DB" = "postgres" ]; then
  echo "✗ hedef üretim veritabanı, durduruldu" >&2; exit 1
fi

echo "→ staging'deki mevcut yapı verisi temizleniyor"
ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB -v ON_ERROR_STOP=1 \
  -c \"TRUNCATE $VIRGULLU CASCADE\"" >/dev/null

echo "→ üretimden kopyalanıyor"
ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) sh -c '
  pg_dump -U postgres -d postgres --data-only $DUMP_ARGS \
    | psql -U postgres -d $STAGING_DB -v ON_ERROR_STOP=1 \
        -c \"SET session_replication_role = replica\" -f - \
  ' " >/dev/null

# Diziler kopyalanan satırların gerisinde kalırsa staging'de yeni kayıt açmak
# birincil anahtar çakışmasıyla patlar. Hepsini sahibi sütunun maksimumuna çek.
echo "→ diziler hizalanıyor"
ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB -v ON_ERROR_STOP=1 -c \"
DO \\\$\\\$
DECLARE r record; m bigint;
BEGIN
  FOR r IN
    SELECT s.relname AS seq, t.relname AS tbl, a.attname AS col
    FROM pg_class s
    JOIN pg_depend d ON d.objid = s.oid AND d.classid = 'pg_class'::regclass
                    AND d.refclassid = 'pg_class'::regclass
    JOIN pg_class t ON t.oid = d.refobjid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
    JOIN pg_namespace n ON n.oid = s.relnamespace
    -- Yalnizca public: TimescaleDB'nin _timescaledb_catalog dizileri de bu
    -- sorguya takiliyor ve arama yolunda olmadiklari icin patlatiyorlardi.
    WHERE s.relkind = 'S' AND n.nspname = 'public'
  LOOP
    EXECUTE format('SELECT COALESCE(max(%I),0) FROM public.%I', r.col, r.tbl) INTO m;
    EXECUTE format('SELECT setval(%L, GREATEST(%s,1))', r.seq, m);
  END LOOP;
END \\\$\\\$;\"" >/dev/null

echo "→ sonuç"
ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d $STAGING_DB -c \"
SELECT (SELECT count(*) FROM users) AS kullanici,
       (SELECT count(*) FROM devices) AS cihaz,
       (SELECT count(*) FROM organizations) AS organizasyon,
       (SELECT count(*) FROM alarm_rules) AS alarm_kurali,
       (SELECT count(*) FROM measurements) AS olcum_staging_kendi;\""

echo "✓ staging tohumlandı — üretim şifrenizle giriş yapabilirsiniz"
