#!/bin/bash
# Binary Enerji — test paketini çalıştırır.
#
# İZOLASYON: Testler ÜRETİM veritabanına asla dokunmaz. Ayrı bir veritabanı
# (binaryenerji_test) kullanılıyor ve tests/conftest.py içindeki koruma,
# veritabanı adı beklenen değilse tüm oturumu durduruyor. Ayrıca her test
# kendi işleminde çalışıp geri alınıyor, yani testler birbirini de kirletmiyor.
set -euo pipefail

HOST="${1:-binaryenerji}"
TEST_DB="binaryenerji_test"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ test veritabanı hazırlanıyor ($TEST_DB)"
ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d postgres \
  -c \"DROP DATABASE IF EXISTS $TEST_DB\" -c \"CREATE DATABASE $TEST_DB\"" >/dev/null

echo "→ şema uygulanıyor"
ssh "$HOST" "docker exec -i \$(docker ps -qf name=timescaledb) psql -U postgres -d $TEST_DB -v ON_ERROR_STOP=1" \
  < "$REPO/ops/schema/00-baseline.sql" >/dev/null

# Şema kayması kontrolü: baseline üretimden geri kalırsa testler var olmayan
# tablolara karşı çalışır ve sessizce eksik kapsam üretir. Bugün tam bu oldu:
# audit_log üretimde vardı, baseline'da yoktu.
echo "→ şema kayması kontrolü"
URETIM=$(ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d postgres -t -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1\"" | tr -d ' ' | grep -v '^$' | sort)
TEST=$(ssh "$HOST" "docker exec \$(docker ps -qf name=timescaledb) psql -U postgres -d $TEST_DB -t -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1\"" | tr -d ' ' | grep -v '^$' | sort)
FARK=$(comm -23 <(echo "$URETIM") <(echo "$TEST"))
if [ -n "$FARK" ]; then
  echo "✗ ŞEMA KAYMASI: üretimde olup baseline'da olmayan tablolar:" >&2
  echo "$FARK" | sed 's/^/    /' >&2
  echo "  ops/schema/00-baseline.sql yeniden üretilmeli." >&2
  exit 1
fi
echo "  ✓ baseline üretimle aynı"

# ÇALIŞMA KOPYASI test edilir, yayındaki kod değil. Daha önce yalnızca
# tests/ kopyalanıyordu ve pytest konteynerdeki /app/api.py'a -- yani zaten
# yayınlanmış koda -- karşı koşuyordu; bu yüzden dağıtılmamış bir düzeltme
# doğrulanamıyor, dağıtılmamış bir hata da yakalanamıyordu. Bağlantı havuzu
# hatasında tam bu oldu.
#
# Kopya /app'e DEĞİL, ayrı bir dizine açılıyor: üretim konteynerinin çalışan
# kodu test yüzünden hiçbir zaman değişmemeli.
echo "→ çalışma kopyası konteynere alınıyor"
CID=$(ssh "$HOST" "docker ps -qf name=root-api")
RUNDIR=/tmp/binaryenerji-test
ssh "$HOST" "docker exec $CID sh -c 'rm -rf $RUNDIR && mkdir -p $RUNDIR'"
tar czf - -C "$REPO" tests api.py | ssh "$HOST" "docker exec -i $CID tar xzf - -C $RUNDIR"

echo "→ pytest"
ssh "$HOST" "docker exec -e POSTGRES_DB=$TEST_DB $CID sh -c '
  pip show pytest >/dev/null 2>&1 || pip install -q pytest
  cd $RUNDIR && python -m pytest tests -q --no-header -p no:cacheprovider
'"
