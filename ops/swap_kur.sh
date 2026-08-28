#!/bin/bash
# Binary Enerji — takas (swap) alanı kurar.
#
# NEDEN: Sunucuda 961 MB RAM var ve HİÇ swap yok. Bu haliyle tek bir bellek
# sıçraması (büyük bir rapor, eşzamanlı istek kümesi, TimescaleDB bakım işi)
# doğrudan OOM killer'ı tetikler ve büyük ihtimalle en çok bellek tutan süreci
# — yani PostgreSQL'i — öldürür. Veri toplama durur.
#
# Swap performans çözümü DEĞİL, çökme sigortası: normal çalışmada neredeyse
# hiç kullanılmaz (swappiness düşük tutuluyor), ama tepe anında sistemi
# öldürmek yerine yavaşlatır.
set -euo pipefail

SWAPFILE="/swapfile"
SIZE="2G"

if swapon --show | grep -q "$SWAPFILE"; then
  echo "swap zaten kurulu:"
  swapon --show
  exit 0
fi

echo "→ $SIZE swap dosyası oluşturuluyor"
fallocate -l "$SIZE" "$SWAPFILE" || dd if=/dev/zero of="$SWAPFILE" bs=1M count=2048
chmod 600 "$SWAPFILE"
mkswap "$SWAPFILE" >/dev/null
swapon "$SWAPFILE"

# Yeniden başlatmada da açık kalsın
grep -q "^$SWAPFILE" /etc/fstab || echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab

# Veritabanı sunucusunda swap'a erken kaçmak istemiyoruz: swap burada bir
# performans katmanı değil, son çare. 10 = "gerçekten gerekmedikçe kullanma".
sysctl -w vm.swappiness=10 >/dev/null
grep -q "^vm.swappiness" /etc/sysctl.conf || echo "vm.swappiness=10" >> /etc/sysctl.conf

echo "→ tamam"
free -m
swapon --show
