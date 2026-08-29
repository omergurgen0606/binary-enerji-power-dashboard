#!/bin/bash
# Let's Encrypt sertifikalarını mosquitto'nun okuyabileceği yere kopyalar.
#
# NEDEN KOPYA, BAĞLAMA DEĞİL: mosquitto konteynerde uid 1883 ile çalışıyor,
# /etc/letsencrypt/live/.../privkey.pem ise 0600 root. Dizini doğrudan bağlasak
# mosquitto özel anahtarı okuyamaz ve TLS dinleyicisi hiç açılmaz. Kopyalar
# 1883:1883 sahipliğiyle ve 0640 ile duruyor.
#
# Sertifika 90 günde bir yenileniyor; bu betik certbot'un renew hook'undan
# çağrılıyor (aşağıdaki kurulum notuna bakın), yoksa yenilemeden sonra
# mosquitto eski sertifikayı sunmaya devam eder ve cihazlar bir gün aniden
# bağlanamaz hale gelir.
set -euo pipefail

ALAN="binaryenerji.com"
KAYNAK="/etc/letsencrypt/live/$ALAN"
HEDEF="/etc/mosquitto/certs"

[ -d "$KAYNAK" ] || { echo "✗ sertifika dizini yok: $KAYNAK" >&2; exit 1; }

mkdir -p "$HEDEF"
cp "$KAYNAK/fullchain.pem" "$HEDEF/fullchain.pem"
cp "$KAYNAK/privkey.pem"   "$HEDEF/privkey.pem"

# mosquitto konteynerdeki uid/gid
chown 1883:1883 "$HEDEF/fullchain.pem" "$HEDEF/privkey.pem"
chmod 0644 "$HEDEF/fullchain.pem"
chmod 0640 "$HEDEF/privkey.pem"

echo "✓ sertifikalar $HEDEF içine kopyalandı"

# Yenilemeden sonra mosquitto'nun yeni sertifikayı alması için yeniden
# başlatılması gerekiyor. SIGHUP mosquitto 2'de sertifikayı yeniden okumuyor.
if docker ps --format '{{.Names}}' | grep -q mosquitto; then
    docker restart "$(docker ps -qf name=mosquitto)" >/dev/null
    echo "✓ mosquitto yeniden başlatıldı"
fi
