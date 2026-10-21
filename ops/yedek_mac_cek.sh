#!/bin/bash
# Binary Enerji — sunucudaki gece yedeklerini BU MAC'e çeker (sunucu dışı kopya).
#
# NEDEN: Ekim 2026'da DigitalOcean sunucusu silindiğinde /root/backups'taki
# yedekler de onunla gitti; elde kalan tek kopya Mac'teki bir aylık eski bir
# yedekti. Sunucu Mac'e kendisi ulaşamadığı için (Mac modemin arkasında) kopyayı
# Mac çekiyor: launchd bunu birkaç saatte bir ve oturum her açıldığında
# çalıştırıyor. Kurulum: ops/yedek_mac_kur.sh
#
# Ne çekiliyor: veritabanları (Binary Enerji + Binary Şarj), yüklenen dosyalar,
# Şarj istasyon fotoğrafları ve ayar arşivi (.env dahil — GİZLİ; bu yüzden
# klasör 700, dosyalar 600). Mac'te 30 gün tutuluyor, sunucuda 14.
#
# Her başarılı çekimde sunucuya /root/backups/.son_mac_cekimi yazılıyor; haftalık
# yedek e-postası Mac 3 gündür çekmediyse uyarıyor.
set -uo pipefail

HOST="${BINARYENERJI_HOST:-binaryenerji}"
KOK="${BINARYENERJI_YEDEK_DIZINI:-$HOME/Desktop/BinaryEnerji-Yedekler}"
HEDEF="$KOK/otomatik"
SAKLA_GUN=30
LOG="$HEDEF/cekim.log"
SON_OK="$HEDEF/.son_basarili_cekim"

mkdir -p "$HEDEF" && chmod 700 "$HEDEF"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"; }
bildir() {
  osascript -e "display notification \"$1\" with title \"Binary Enerji yedek\" sound name \"Basso\"" \
    >/dev/null 2>&1 || true
}
saniye_once() { echo $(( $(date +%s) - $(stat -f %m "$1") )); }

# İnternet yokken (uçak modu, kapalı modem) her denemede bildirim göstermek
# gürültü olur ve gerçek uyarıların görmezden gelinmesine yol açar. Yalnızca son
# başarılı çekim 2 günden eskiyse uyarılıyor.
if ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" true 2>/dev/null; then
  log "ATLANDI: sunucuya ulaşılamadı"
  if [ -f "$SON_OK" ] && [ "$(saniye_once "$SON_OK")" -gt 172800 ]; then
    bildir "2 gündür sunucudan yedek çekilemedi. İnternet bağlantısını kontrol edin."
  fi
  exit 0
fi

ONCE=$(mktemp)
ls "$HEDEF" > "$ONCE"

# -a dosya zamanlarını korur: aşağıdaki "yedek güncel mi" kontrolü sunucudaki
# oluşturulma zamanına bakabilsin diye. (--chmod kullanılmıyor: macOS'un
# yerleşik rsync'i desteklemiyor; izinler aşağıda ayrıca ayarlanıyor.)
if ! rsync -a \
     --include='db_*.sql.gz' --include='uploads_*.tar.gz' \
     --include='sarj_media_*.tar.gz' --include='config_*.tar.gz' --exclude='*' \
     "$HOST:/root/backups/" "$HEDEF/" 2>>"$LOG"; then
  rm -f "$ONCE"
  log "HATA: rsync başarısız"
  bildir "Yedekler sunucudan çekilemedi (rsync hatası)."
  exit 1
fi

chmod 600 "$HEDEF"/*.gz 2>/dev/null || true

# Yeni gelen her dosya doğrulanıyor: bozuk bir kopya, kopya olmamasından
# tehlikelidir — var sanılır.
SORUN=""
YENI=0
for f in $(ls "$HEDEF" | grep -v -x -F -f "$ONCE" | grep -E '\.(sql|tar)\.gz$'); do
  YENI=$((YENI + 1))
  if ! gzip -t "$HEDEF/$f" 2>/dev/null; then SORUN="$SORUN $f"; continue; fi
  case "$f" in
    db_*)     ( set +o pipefail; gzip -dc "$HEDEF/$f" | head -c 4096 | grep -q "PostgreSQL database dump" ) \
                || SORUN="$SORUN $f" ;;
    config_*) tar tzf "$HEDEF/$f" 2>/dev/null | grep -qx "root/.env" || SORUN="$SORUN $f" ;;
  esac
done
rm -f "$ONCE"
if [ -n "$SORUN" ]; then
  log "HATA: bozuk ya da eksik dosya:$SORUN"
  bildir "Çekilen yedeklerde bozuk dosya var:$SORUN"
  exit 1
fi

# Sunucunun gece yedeği de çalışıyor mu? Çekim başarılı olsa da Mac'e her gün
# aynı eski dosya geliyorsa sorun sunucudadır.
EN_YENI=$(ls -t "$HEDEF"/db_[0-9]*.sql.gz 2>/dev/null | head -1)
if [ -z "$EN_YENI" ] || [ "$(saniye_once "$EN_YENI")" -gt 129600 ]; then
  log "UYARI: en yeni veritabanı yedeği 36 saatten eski ($(basename "${EN_YENI:-yok}"))"
  bildir "Sunucudaki en yeni yedek 36 saatten eski — gece yedeği çalışmıyor olabilir."
fi

find "$HEDEF" -maxdepth 1 -type f \
  \( -name 'db_*.sql.gz' -o -name 'uploads_*.tar.gz' -o -name 'sarj_media_*.tar.gz' -o -name 'config_*.tar.gz' \) \
  -mtime +"$SAKLA_GUN" -delete

touch "$SON_OK"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" 'date -Iseconds > /root/backups/.son_mac_cekimi' 2>/dev/null || true
log "OK: $YENI yeni dosya, klasörde $(ls "$HEDEF" | grep -c -E '\.(sql|tar)\.gz$') yedek, toplam $(du -sh "$HEDEF" | cut -f1)"
