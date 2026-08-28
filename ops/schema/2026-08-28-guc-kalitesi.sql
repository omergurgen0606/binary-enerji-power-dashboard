-- Güç kalitesi (EN 50160) raporu için 10 dakikalık özet + nominal gerilim.
--
-- NEDEN AYRI BIR OZET: measurements_15min guc asim (sozlesme gucu) cezasi icin
-- kuruldu ve 15 dakika o is icin DOGRU aralik. EN 50160 ise butun sinirlarini
-- 10 DAKIKALIK ortalamalar uzerinden tanimliyor. 15 dakikalik veriyle "EN 50160
-- raporu" demek olcum yontemini yanlis beyan etmek olurdu; iki ayri aralik
-- tutmanin maliyeti cihaz basina ~18 MB/yil, ihmal edilebilir.
--
-- Sadece standardin degerlendirdigi buyuklukler tutuluyor (gerilim, frekans,
-- gerilim harmonik bozulmasi) -- 15 dakikalik ozetin tamamini tekrarlamiyor.
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_10min
WITH (timescaledb.continuous) AS
SELECT
    device_id,
    time_bucket('10 minutes', time) AS bucket,
    count(*) AS sample_count,
    -- Gerilim: standart 10 dakikalik ORTALAMA degerleri degerlendiriyor;
    -- min/max ise dusme/yukselme olaylarini gormek icin.
    avg(v1) AS avg_v1, min(v1) AS min_v1, max(v1) AS max_v1,
    avg(v2) AS avg_v2, min(v2) AS min_v2, max(v2) AS max_v2,
    avg(v3) AS avg_v3, min(v3) AS min_v3, max(v3) AS max_v3,
    -- Frekans
    avg(f1) AS avg_f, min(f1) AS min_f, max(f1) AS max_f,
    -- Gerilim toplam harmonik bozulmasi (THD-V)
    avg(thvd1) AS avg_thvd1, max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2, max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3, max(thvd3) AS max_thvd3
FROM measurements
GROUP BY device_id, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('measurements_10min',
    start_offset => INTERVAL '1 day',
    end_offset   => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => true);

ALTER MATERIALIZED VIEW measurements_10min SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW measurements_10min SET (timescaledb.compress = true);
SELECT add_compression_policy('measurements_10min', compress_after => INTERVAL '30 days',
                              if_not_exists => true);

-- Nominal gerilim: EN 50160 sinirlari Un'e goreli (Un ±%10). Turkiye'de faz-notr
-- 230 V ama abonelik/trafo yapisina gore degisebildigi icin cihaz bazinda ayar.
ALTER TABLE device_settings
    ADD COLUMN IF NOT EXISTS nominal_voltage NUMERIC NOT NULL DEFAULT 230;
