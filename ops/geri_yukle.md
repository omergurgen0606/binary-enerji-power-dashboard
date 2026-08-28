# Yedekten Geri Dönme

## Bulut yedeğini açma

Buluttaki dosyalar `gpg` ile şifreli. Parola **sunucuda değil**, parola
yöneticinizde olmalı — sunucu kaybolduğunda parolayı da kaybederseniz
yedekler işe yaramaz.

```bash
rclone copy b2:kova-adi/db_2026-08-28_0300.sql.gz.gpg .
gpg --decrypt --output db.sql.gz db_2026-08-28_0300.sql.gz.gpg
gzip -t db.sql.gz          # önce bütünlüğü doğrula
```

## Veritabanını geri yükleme

```bash
gzip -dc db.sql.gz | docker compose exec -T timescaledb psql -U postgres postgres
```

> Geri yükleme mevcut veriyi **üzerine yazar**. Önce çalışan sistemin
> yedeğini alın.

## Yüklenen dosyalar (avatar/firmware)

```bash
docker run --rm -v root_avatar_uploads:/data -v "$PWD":/backup alpine \
  tar xzf /backup/uploads_2026-08-28_0300.tar.gz -C /data
```

## Yedeğin gerçekten sağlam olduğunu kontrol etme

Yedeği hiç denemeden "yedeğim var" demek en yaygın hatadır.

```bash
gzip -dc db.sql.gz | grep -c "^CREATE TABLE"    # ~39 tablo bekleniyor
gzip -dc db.sql.gz | wc -l                       # ~80.000+ satır
```
