-- Cihaz-başına MQTT kimliği: enrollment kaydı ve broker'a uygulama kuyruğu.
--
-- NEDEN: broker'da tek bir paylaşılan kimlik bilgisi var, allow_anonymous
-- false + password_file dışında hiçbir topic izolasyonu (acl_file) yok. Bu
-- kimlik bilgisini elinde tutan biri her cihazın topic'ine yazabiliyor --
-- sahte ölçüm yayınlamak, /cmd üzerinden yetkisiz Modbus register yazdırmak
-- dahil. Gerçek çözüm her cihazın kendi rastgele ürettiği, hiçbir firmware
-- imajında ortak olmayan bir kimlik kullanması.
--
-- Backend bu tabloyu SADECE KAYIT için kullanıyor -- mosquitto'nun parola
-- dosyasına doğrudan yazmıyor. Nedeni: api container'ının o dosyaya erişimi
-- yok, ve hash formatını kendim taklit edip yazmak (mosquitto_passwd aracını
-- kullanmadan) bir hata durumunda PAYLAŞILAN kimlik bilgisini de bozup TÜM
-- cihazların bağlantısını kesebilirdi. Gerçek yazma işlemi host'ta
-- ops/mosquitto_kayit_uygula.sh betiği ile, mosquitto_passwd aracının
-- kendisi kullanılarak yapılıyor (applied=false satırları periyodik olarak
-- işleyip true'ya çeviriyor).
CREATE TABLE IF NOT EXISTS device_mqtt_credentials (
    device_id   text PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
    mqtt_username text NOT NULL,
    mqtt_password text NOT NULL,
    applied     boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    applied_at  timestamptz
);
