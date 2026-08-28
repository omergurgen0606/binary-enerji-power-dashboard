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

echo "→ testler kopyalanıyor"
CID=$(ssh "$HOST" "docker ps -qf name=root-api")
tar czf - -C "$REPO" tests | ssh "$HOST" "docker exec -i $CID tar xzf - -C /app"

echo "→ pytest"
ssh "$HOST" "docker exec -e POSTGRES_DB=$TEST_DB $CID sh -c '
  pip show pytest >/dev/null 2>&1 || pip install -q pytest
  cd /app && python -m pytest tests -q --no-header -p no:cacheprovider
'"
