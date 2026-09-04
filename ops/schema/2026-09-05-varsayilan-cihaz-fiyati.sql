-- Standart fiyatlandırma: cihaz başına aylık 100 TL, yıllık peşin tahsilat
-- (period zaten 'yearly' varsayılan). Yeni kayıt olan organizasyonlar bu
-- değeri otomatik alır; mevcut organizasyonlara dokunulmadı (kullanıcı
-- talebiyle -- onlar hâlâ 0 TL'de, ayrıca fiyatlandırılacak).
ALTER TABLE subscriptions ALTER COLUMN device_price SET DEFAULT 100;
