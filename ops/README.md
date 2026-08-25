# Operasyon betikleri

VPS'te (`/root/`) çalışan, `crontab -l` ile kurulu otomatik görevler. Buradaki kopyalar
sadece dokümantasyon/versiyon kontrolü içindir — asıl çalışan kopyalar VPS'in kendisinde.

## Kurulu cron görevleri

```
0 3 * * *     /root/backup.sh                  # her gün 03:00 — DB + uploads yedeği
*/15 * * * *  /root/healthcheck.sh              # her 15 dakikada bir — site erişilebilirlik kontrolü
0 8 * * 1     /root/backup_weekly_report.sh     # her Pazartesi 08:00 — haftalık durum e-postası
```

## backup.sh

- `timescaledb` konteynerinden `pg_dump` alır, gzip'ler, `/root/backups/db_TARIH.sql.gz` olarak kaydeder.
- `root_avatar_uploads` Docker volume'unu (avatar + firmware dosyaları) tar+gzip'ler.
- 14 günden eski yedekleri siler.
- Herhangi bir adım başarısız olursa Resend üzerinden uyarı e-postası gönderir.
- Log: `/root/backups/backup.log`

**Not:** Yedekler şu an sadece VPS'in kendi diskinde tutuluyor — VPS'in tamamı kaybolursa
(disk arızası, hesap silinmesi vb.) bu yedekler de kaybolur. Gerçek felaket kurtarma için
yedeklerin ayrıca VPS dışına (S3/Backblaze/e-posta vb.) kopyalanması gerekir — bu henüz
yapılmadı, bir sonraki adım olarak düşünülebilir.

## healthcheck.sh

- `https://binaryenerji.com/` adresine 15 dakikada bir istek atar.
- Art arda 2 başarısız denemeden sonra uyarı e-postası gönderir (tek seferlik kesintilerde
  gereksiz alarm vermemek için).
- Site düzelince "tekrar çalışıyor" e-postası gönderir.
- Durum: `/root/backups/.health_state`

**Sınırlama:** Bu betik VPS'in KENDİSİNDE çalışıyor — VPS tamamen çökerse (elektrik kesintisi,
sağlayıcı sorunu vb.) bu betik de çalışamaz, dolayısıyla o senaryoda uyarı gelmez. Gerçek
"dışarıdan" çalışma süresi izleme için UptimeRobot (ücretsiz) gibi harici bir servise
kaydolup `https://binaryenerji.com/` adresini izlettirmek gerekir.

## backup_weekly_report.sh

- Son 7 günün yedekleme geçmişini özetleyip e-posta olarak gönderir.
- Bu e-posta düzenli gelmezse (cron durmuş, sunucu erişilemez vb.) bu da başlı başına bir uyarı sinyalidir.

## Veritabanını geri yükleme (restore)

```bash
# Yerelde veya VPS'te, geri yüklenecek gz dosyasını bul:
ls -la /root/backups/db_*.sql.gz

# ÖNEMLİ: mevcut veriyi geri yüklemeden önce mutlaka taze bir yedek daha al.
# api container'ını durdur (veritabanına yazılmasını önlemek için):
cd /root && docker compose stop api

# Geri yükle (mevcut veritabanının ÜZERİNE yazar):
zcat /root/backups/db_2026-01-01_0300.sql.gz | docker compose exec -T timescaledb psql -U postgres -d postgres

# api'yi tekrar başlat:
docker compose start api
```

## Yüklenen dosyaları (avatar/firmware) geri yükleme

```bash
docker run --rm -v root_avatar_uploads:/data -v /root/backups:/backup alpine \
  sh -c "cd /data && tar xzf /backup/uploads_2026-01-01_0300.tar.gz"
```

## Alarm e-postaları nereye gidiyor?

Şu an tek bir adrese sabit: `wommit56@gmail.com` (betiklerin içinde `ALERT_EMAIL` değişkeni).
Değiştirmek için üç betikteki bu değişkeni güncelleyip VPS'e tekrar `scp` ile kopyalamak yeterli.
