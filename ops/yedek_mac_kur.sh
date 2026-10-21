#!/bin/bash
# ops/yedek_mac_cek.sh'yi bu Mac'e arka plan görevi (launchd) olarak kurar:
# 3 saatte bir ve oturum her açıldığında çalışır. Tekrar çalıştırmak güvenli.
#
# Betik depodan değil kopyasından çalışıyor: depo başka bir dala geçerse ya da
# taşınırsa yedek görevi sessizce durmasın.
#
# Kaldırmak için:
#   launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.binaryenerji.yedek-cek.plist
set -euo pipefail

KAYNAK="$(cd "$(dirname "$0")" && pwd)/yedek_mac_cek.sh"
DIZIN="$HOME/Library/Application Support/BinaryEnerji"
BETIK="$DIZIN/yedek_mac_cek.sh"
ETIKET="com.binaryenerji.yedek-cek"
PLIST="$HOME/Library/LaunchAgents/$ETIKET.plist"

mkdir -p "$DIZIN" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$KAYNAK" "$BETIK"
chmod 755 "$BETIK"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ETIKET</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$BETIK</string></array>
  <key>StartInterval</key><integer>10800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/binaryenerji-yedek.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/binaryenerji-yedek.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✓ kuruldu: $ETIKET (3 saatte bir + oturum açılışında)"
echo "  yedekler: \$HOME/Desktop/BinaryEnerji-Yedekler/otomatik"
echo "  günlük:   \$HOME/Desktop/BinaryEnerji-Yedekler/otomatik/cekim.log"
