#!/bin/bash
# Binary Enerji — cihaz-başına üretilen MQTT kimliklerini broker'a uygular.
#
# NEDEN AYRI BİR BETİK: api container'ının mosquitto'nun parola dosyasına
# erişimi yok, ve o hash formatını kendim taklit edip yazmak bir hatada
# PAYLAŞILAN kimlik bilgisini de bozup TÜM cihazların bağlantısını kesebilirdi.
# Bu betik gerçek mosquitto_passwd aracını kullanıyor -- format riski yok.
#
# device_mqtt_credentials tablosundaki applied=false satırları işler, her biri
# için mosquitto_passwd ile parola dosyasına ekler/günceller, sonra mosquitto'ya
# SIGHUP gönderip parola dosyasını yeniden okumasını sağlar (yeniden başlatma
# DEĞİL -- restart TÜM cihazların bağlantısını o an keserdi, SIGHUP kesmiyor,
# yalnızca dosyayı yeniden okumasını sağlıyor).
#
# ÖNEMLİ: mosquitto_passwd -c KULLANILMIYOR -- -c mevcut dosyanın TAMAMINI
# SİLİP yeniden oluşturur, yani paylaşılan "esp32user" kaydı da giderdi ve
# henüz kendi kimliğine geçmemiş TÜM cihazların bağlantısı o an kesilirdi.
# -c olmadan mosquitto_passwd -b, dosya zaten varsa sadece belirtilen
# kullanıcının satırını ekler/günceller.
#
# cron ile birkaç dakikada bir çalışıyor (bkz. crontab -l).
set -euo pipefail

TIMESCALE_CID=$(docker ps -qf name=timescaledb)
MOSQUITTO_CID=$(docker ps -qf name=mosquitto)
PASSWD_FILE=/etc/mosquitto/passwd

BEKLEYEN=$(docker exec -i "$TIMESCALE_CID" psql -U postgres -d postgres -tAc \
  "SELECT device_id, mqtt_username, mqtt_password FROM device_mqtt_credentials WHERE applied = false")

if [ -z "$BEKLEYEN" ]; then
  exit 0
fi

DEGISTI=0
while IFS='|' read -r device_id mqtt_username mqtt_password; do
  [ -z "$device_id" ] && continue
  echo "→ uygulanıyor: $device_id"
  docker exec "$MOSQUITTO_CID" mosquitto_passwd -b "$PASSWD_FILE" "$mqtt_username" "$mqtt_password"
  # device_id burada zaten API'nin kendi parametreli INSERT'inden gecmis bir
  # deger (bkz. api.py enroll_device_mqtt) -- yine de heredoc disina cikmiyor,
  # psql'e stdin uzerinden tek bir dogrudan SQL olarak veriliyor.
  docker exec -i "$TIMESCALE_CID" psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<SQL
UPDATE device_mqtt_credentials SET applied = true, applied_at = now() WHERE device_id = '$device_id';
SQL
  DEGISTI=1
done <<< "$BEKLEYEN"

if [ "$DEGISTI" = "1" ]; then
  # Yeniden başlatma DEĞİL, SIGHUP: mosquitto parola dosyasını yeniden okur,
  # MEVCUT bağlantıları kesmez -- restart tüm cihazların oturumunu düşürürdü.
  docker kill --signal=HUP "$MOSQUITTO_CID"
  echo "✓ mosquitto parola dosyasını yeniden okudu"
fi
