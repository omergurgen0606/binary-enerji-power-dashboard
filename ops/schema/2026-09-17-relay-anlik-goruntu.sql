-- GA1202 (reaktif güç kontrol rölesi) için kategori bazlı anlık görüntü tablosu.
--
-- NEDEN JSONB VE NEDEN TEK TABLO:
--
-- Rölenin register haritası ~300 alan (Anlık, Toplam/Ortalama, Tepe, Enerji,
-- Kademeler, ~105 parametre). Her kategori için ayrı tablo + alan başına sütun
-- açmak (device_stats/device_peaks'teki mevcut desen) burada altı tablo ve
-- 300'den fazla sütun demekti; üstelik alanların bir kısmı gerçek donanımla
-- HENÜZ DOĞRULANMADI (bkz. ESP32-GA1202/README.md), yani her düzeltme bir
-- migration gerektirirdi. JSONB, doğrulama turu bitene kadar şemayı dondurmadan
-- veriyi saklamayı sağlıyor; panel zaten "gelen ne varsa kart olarak göster"
-- mantığında.
--
-- NEDEN ZAMAN SERİSİ DEĞİL: bu kategoriler kartlarda ANLIK değer olarak
-- gösteriliyor ve bir kısmı (parametreler, tepe değerleri) zaten cihazın kendi
-- biriktirdiği kümülatif/statik veri. Canlı ölçümün geçmişi (V/I/P/Q/F) eskisi
-- gibi `measurements` tablosuna yazılmaya devam ediyor -- grafikler ve alarmlar
-- oradan besleniyor. 2 saniyede bir JSONB satırı biriktirmek (günde ~43 bin
-- satır/cihaz) hiçbir sorguya cevap vermeden disk yerdi.
CREATE TABLE IF NOT EXISTS relay_snapshots (
    device_id   TEXT        NOT NULL,
    -- live | kademeler | toplam | tepe_tuketim | tepe_uretim |
    -- enerji_tuketim | enerji_uretim | parametreler
    kategori    TEXT        NOT NULL,
    data        JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, kategori)
);

-- Cihaz silindiğinde görüntüleri de gitsin: silinen bir cihazın verisi panelde
-- hayalet olarak kalmamalı (devices tablosuna FK yok çünkü cihaz kaydı
-- kullanıcı sahipliğiyle ilgili, veri akışı ondan bağımsız başlayabiliyor --
-- bu yüzden temizlik uygulama tarafında, delete_device içinde yapılıyor).
CREATE INDEX IF NOT EXISTS relay_snapshots_device_idx ON relay_snapshots (device_id);
