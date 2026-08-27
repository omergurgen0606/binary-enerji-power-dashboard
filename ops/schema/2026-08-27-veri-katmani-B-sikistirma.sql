-- Veri katmani olceklendirme -- ASAMA B: sikistirma + saklama politikalari
--
-- Asama A'daki ozet tablolari (device_energy_hourly, measurements_15min)
-- kurulmadan bu asama CALISTIRILMAMALI: ham veriyi silmeyi guvenli kilan sey
-- o ozetlerin gecmisi sonsuza kadar tutmasi.

-- ---------------------------------------------------------------------------
-- 1) Sikistirma
-- ---------------------------------------------------------------------------
-- segmentby = device_id: ayni cihazin satirlari bir arada sikistirilir, bu hem
-- sikistirma oranini yukseltir hem de "WHERE device_id = ..." sorgularinin
-- ilgisiz cihazlarin bloklarini hic acmadan gecmesini saglar.
ALTER TABLE measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'time DESC'
);
ALTER TABLE device_energy SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'time DESC'
);
ALTER TABLE device_stats SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'time DESC'
);
ALTER TABLE device_demand SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'time DESC'
);
ALTER TABLE device_harmonics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'time DESC'
);
-- device_peaks'te direction (tuketim/uretim) da ayirt edici, onu da segmentby'a
-- katiyoruz -- sorgular her zaman iki yonu ayri okuyor.
ALTER TABLE device_peaks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, direction',
    timescaledb.compress_orderby   = 'time DESC'
);

-- 7 gunden eski chunk'lar sikistirilsin. Ozet tablolarinin tazeleme penceresi
-- en fazla 3 gun geriye bakiyor, yani sikistirma hic tazelemenin onune gecmiyor.
SELECT add_compression_policy('measurements',     INTERVAL '7 days', if_not_exists => true);
SELECT add_compression_policy('device_energy',    INTERVAL '7 days', if_not_exists => true);
SELECT add_compression_policy('device_stats',     INTERVAL '7 days', if_not_exists => true);
SELECT add_compression_policy('device_peaks',     INTERVAL '7 days', if_not_exists => true);
SELECT add_compression_policy('device_demand',    INTERVAL '7 days', if_not_exists => true);
SELECT add_compression_policy('device_harmonics', INTERVAL '7 days', if_not_exists => true);

-- ---------------------------------------------------------------------------
-- 2) Saklama politikalari
-- ---------------------------------------------------------------------------
-- Bugun hicbir veriyi silmiyor (elimizde ~2 haftalik veri var) -- ileride
-- sinirsiz buyumeyi engellemek icin simdiden kuruluyor.
--
-- measurements: 2 sn'de bir kayit, cihaz basina ~5,3 GB/yil. 90 gunden eski
-- ham olcumler siliniyor; gecmis measurements_15min'de sonsuza kadar duruyor.
SELECT add_retention_policy('measurements', INTERVAL '90 days', if_not_exists => true);

-- device_energy: faturalama acisindan kritik oldugu icin daha temkinli.
-- Gecmis zaten device_energy_hourly'de tam dogrulukla tutuluyor.
SELECT add_retention_policy('device_energy', INTERVAL '180 days', if_not_exists => true);

-- Bu dordunden panel yalnizca EN SON satiri okuyor; gecmisleri ileride guc
-- kalitesi raporu icin lazim olabilir diye 1 yil tutuluyor (boyutlari kucuk).
SELECT add_retention_policy('device_stats',     INTERVAL '365 days', if_not_exists => true);
SELECT add_retention_policy('device_peaks',     INTERVAL '365 days', if_not_exists => true);
SELECT add_retention_policy('device_demand',    INTERVAL '365 days', if_not_exists => true);
SELECT add_retention_policy('device_harmonics', INTERVAL '365 days', if_not_exists => true);
