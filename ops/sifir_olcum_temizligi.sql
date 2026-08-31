-- Ölçüm olmayan "sıfır" satırlarını temizler.
--
-- NEDEN: analizör Modbus'a başarıyla cevap verip her değeri sıfır döndürdüğünde
-- firmware bunu geçerli bir ölçüm sanıp yayınlıyordu. Panel 0.0 V'u gerçek
-- ölçüm gibi gösterdi, fatura ve enerji analizi de bu satırlar üzerinden
-- hesaplandı. Üretimde 74.194 kaydın 33.199'u (%45) böyleydi.
--
-- KRİTER firmware'deki kontrolle BİREBİR aynı (ESP32-ANL21.ino, olcumYok):
-- üç fazın gerilimi de sıfır VE frekans sıfır. Şebekede frekans asla sıfır
-- olmaz; bu bir ölçüm değil, "gerilim girişleri / akım trafoları bağlı değil"
-- halidir.
--
-- GÜVENLİ: bu koşulu sağlayıp da akım ya da güç taşıyan tek satır yok
-- (silmeden önce doğrulandı). Yani gerçek veri silinmiyor.
--
-- YEDEK: silmeden önce mutlaka alın --
--   ssh binaryenerji "docker exec \$(docker ps -qf name=timescaledb) \
--     psql -U postgres -d postgres -tAc \"COPY (SELECT * FROM measurements \
--     WHERE v1=0 AND v2=0 AND v3=0 AND f1=0) TO STDOUT WITH CSV HEADER\"" \
--     > sifir_olcumler_yedek.csv

BEGIN;

-- Silinecek satırları say (kayıt için)
SELECT count(*) AS silinecek_satir,
       min(time)::date AS ilk_gun,
       max(time)::date AS son_gun
FROM measurements
WHERE v1 = 0 AND v2 = 0 AND v3 = 0 AND f1 = 0;

DELETE FROM measurements
WHERE v1 = 0 AND v2 = 0 AND v3 = 0 AND f1 = 0;

COMMIT;

-- ÖNEMLİ: ham satırları silmek sürekli toplamaları GÜNCELLEMEZ. Bu adım
-- atlanırsa measurements_15min ve measurements_10min sahte veriyi taşımaya
-- devam eder, yani panel ve raporlar hâlâ yanlış gösterir.
--
-- refresh_continuous_aggregate bir işlem bloğunun içinde çalışamaz; bu yüzden
-- COMMIT'ten sonra ve ayrı ayrı çağrılıyor.
CALL refresh_continuous_aggregate('measurements_15min', '2026-08-01', '2026-09-01');
CALL refresh_continuous_aggregate('measurements_10min', '2026-08-01', '2026-09-01');

-- Kontrol: geriye sıfır satır kalmamalı, gerçek veri korunmuş olmalı.
SELECT count(*) FILTER (WHERE v1 = 0 AND v2 = 0 AND v3 = 0 AND f1 = 0) AS kalan_sifir,
       count(*) AS toplam_satir
FROM measurements;
