#!/bin/bash
# Binary Enerji — cihaz broker'a BAĞLANDIĞI AN OTA mesajını gönderir.
#
# NEDEN VAR: cihazlar temiz oturumla (clean session) bağlanıyor, yani o anda
# bağlı değillerse yayınlanan mesaj kuyruğa girmeden kayboluyor. Panelden
# tetiklenen OTA bunu 409 ile korumaya çalışıyor (api.py, trigger_ota) ama
# "çevrimiçi" bilgisi son duruma bakıyor; bağlantısı sık kopan bir cihazda
# mesaj yine boşluğa denk gelebiliyor.
#
# 2 Eylül 2026'da tam bu oldu: 1.0.3 OTA'sı gönderildi, cihaz dosyayı hiç
# indirmedi. Cihaz o sırada keepalive aşımından her ~40 saniyede bir düşüyordu
# (düzeltmenin kendisi de zaten buydu). Bu betik broker günlüğünü izleyip
# bağlantı kurulduğu anda yayınlıyor.
#
# Kullanım (VPS üzerinde):
#   ./ota_gonder.sh <device_id> <surum> <sha256>
#
# Sürüm ve sha256, firmware_builds tablosundaki kayıtla birebir aynı olmalı.
set -u

CIHAZ="${1:?kullanim: ota_gonder.sh <device_id> <surum> <sha256>}"
SURUM="${2:?surum gerekli}"
SHA="${3:?sha256 gerekli}"
BEKLEME_SN="${4:-180}"

PAYLOAD="{\"url\": \"https://binaryenerji.com/api/firmware-files/${CIHAZ%%-*}-${SURUM}.bin\", \"version\": \"${SURUM}\", \"sha256\": \"${SHA}\"}"

MQTT_PW=$(grep -m1 '^MQTT_PASSWORD=' /root/.env | cut -d= -f2-)
CID=$(docker ps -qf name=mosquitto)
[ -n "$CID" ] || { echo "✗ mosquitto konteyneri bulunamadı" >&2; exit 1; }

echo "→ $CIHAZ için $SURUM bekleniyor (en fazla ${BEKLEME_SN} sn)"
timeout "$BEKLEME_SN" docker logs -f --since 1s "$CID" 2>&1 | while read -r satir; do
  if echo "$satir" | grep -q "New client connected.*${CIHAZ}"; then
    echo "[$(date +%H:%M:%S)] cihaz bağlandı — OTA gönderiliyor"
    # Cihazın abonelikleri oturana kadar kısa bir an: connect ile subscribe
    # arasında yayınlanan mesaj yine kaybolur.
    sleep 1
    if docker exec "$CID" mosquitto_pub -h binaryenerji.com -p 8883 \
        --capath /etc/ssl/certs -u esp32user -P "$MQTT_PW" -q 1 \
        -t "powermeter/${CIHAZ}/ota" -m "$PAYLOAD"; then
      echo "✓ OTA gönderildi"
    else
      echo "✗ OTA gönderilemedi" >&2
    fi
    break
  fi
done

echo
echo "Cihazın dosyayı GERÇEKTEN indirdiğini doğrulayın — mesajın gitmesi yetmez:"
echo "  grep firmware-files /var/log/nginx/access.log | tail"
echo "İstemci 'ESP32-http-Update' olmalı ve boyut dosyanın tamamı kadar olmalı."
