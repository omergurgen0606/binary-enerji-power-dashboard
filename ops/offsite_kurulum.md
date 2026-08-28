# Sunucu Dışı Yedekleme — Kurulum

Her şey hazır; eksik olan tek şey bir bulut depolama hesabı. O gelene kadar
`backup_offsite.sh` her gece sessizce atlıyor (hata e-postası atmıyor).

## Neden Backblaze B2 (DigitalOcean Spaces değil)

Spaces de çalışır ama **aynı sağlayıcıda** olmak riski ilişkilendirir: DO
hesabınızda bir sorun çıkarsa (faturalandırma, askıya alma, silme) hem sunucu
hem yedek aynı anda gider. B2 bağımsız bir sağlayıcı ve bu yedek hacminde
(günde ~5,5 MB, 90 gün ≈ 500 MB) ücreti ayda birkaç kuruş.

## 1. B2 hesabı ve kova

1. backblaze.com → B2 Cloud Storage → ücretsiz hesap
2. **Create a Bucket** → ad: `binaryenerji-yedek` → **Private**
3. **App Keys** → *Add a New Application Key* → yalnızca bu kovaya erişim
4. Çıkan `keyID` ve `applicationKey` değerlerini not alın
   (applicationKey bir daha gösterilmez)

## 2. Sunucuda rclone yapılandırması

```bash
ssh binaryenerji
rclone config
```

- `n` (new remote) → ad: `b2`
- storage: `b2` (Backblaze B2)
- `account`: keyID
- `key`: applicationKey
- gerisi varsayılan → `q` ile çık

Test:

```bash
rclone lsd b2:
```

## 3. Hedefi tanımla

```bash
echo 'BACKUP_REMOTE=b2:binaryenerji-yedek' >> /root/.env
/root/backup_offsite.sh          # elle bir kez çalıştır
tail -2 /root/backups/offsite.log
rclone lsf b2:binaryenerji-yedek # dosyalar orada mı
```

## 4. ⚠ Şifreleme parolasını sunucudan çıkarın

Yedekler `gpg` (AES256) ile şifreli. Parola `/root/YEDEK-PAROLASI-SAKLA.txt`
dosyasında ve `/root/.env` içinde.

**Parolayı parola yöneticinize kaydedin, sonra o dosyayı silin:**

```bash
cat /root/YEDEK-PAROLASI-SAKLA.txt     # kopyalayın
rm /root/YEDEK-PAROLASI-SAKLA.txt
```

Parola yalnızca sunucuda kalırsa ve sunucu kaybolursa, buluttaki yedekler
**açılamaz** ve bu işin tamamı boşa gider.

## Geri dönme

`ops/geri_yukle.md`

## İkinci katman: kendi bilgisayarınıza indirme

Buluttan bağımsız, hiçbir hesap gerektirmeyen ikinci kopya:

```bash
./ops/backup_indir.sh            # son yedeği indirir + doğrular
./ops/backup_indir.sh --hepsi    # tüm yedekleri indirir
```

İki bağımsız kopya, tek kopyadan iyidir.
