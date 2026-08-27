-- Veri katmani olceklendirme -- ASAMA A: indeksler + surekli toplamalar
--
-- Sorun: measurements tablosu cihaz basina ~14,6 MB/gun buyuyor (2 sn'de bir
-- kayit, satir ~337 byte) -- yilda ~5,3 GB/cihaz. Sunucuda 17 GB bos alan var,
-- yani 10 cihazda disk ~4 ayda, 50 cihazda ~3 haftada dolar ve PostgreSQL
-- yazmayi reddedince veri toplama sessizce olur.
--
-- Bu asama tamamen EKLEMELI: hicbir veri silinmiyor, hicbir sorgu bozulmuyor.
-- Ham veriyi guvenle silebilmemizin on kosulu olan ozet tablolarini kuruyor.

-- ---------------------------------------------------------------------------
-- 1) Bilesik indeksler
-- ---------------------------------------------------------------------------
-- Tum sorgular "WHERE device_id = ... AND time > ..." seklinde; mevcut tek
-- indeks sadece (time) uzerinde oldugu icin cok cihazli kurulumda her sorgu
-- ilgisiz cihazlarin satirlarini da tariyor.
CREATE INDEX IF NOT EXISTS measurements_device_time_idx     ON measurements     (device_id, time DESC);
CREATE INDEX IF NOT EXISTS device_energy_device_time_idx    ON device_energy    (device_id, time DESC);
CREATE INDEX IF NOT EXISTS device_stats_device_time_idx     ON device_stats     (device_id, time DESC);
CREATE INDEX IF NOT EXISTS device_peaks_device_time_idx     ON device_peaks     (device_id, time DESC);
CREATE INDEX IF NOT EXISTS device_demand_device_time_idx    ON device_demand    (device_id, time DESC);
CREATE INDEX IF NOT EXISTS device_harmonics_device_time_idx ON device_harmonics (device_id, time DESC);

-- ---------------------------------------------------------------------------
-- 2) Chunk araligi: 7 gun -> 1 gun (measurements)
-- ---------------------------------------------------------------------------
-- Sadece YENI chunk'lari etkiler. 1 gunluk chunk hem sikistirma hem saklama
-- politikasini daha ince taneli yapiyor; 961 MB RAM'li sunucuda aktif chunk'in
-- kucuk kalmasi da onemli.
SELECT set_chunk_time_interval('measurements', INTERVAL '1 day');

-- ---------------------------------------------------------------------------
-- 3) device_energy_hourly -- saatlik enerji endeksleri
-- ---------------------------------------------------------------------------
-- Sayaclar kumulatif oldugu icin saatlik ozet yeterli; aradaki ~120 kayit
-- atilabilir. /energy/hourly ve reaktif ceza raporu bugun bu hesabi her
-- istekte ham veri uzerinde yapiyor -- artik hazir gelecek.
--
-- NEDEN first/last/max UCUSU BIRDEN:
-- Sadece last() saklamak yetmiyor. Cihaz sayaci panelden sifirlanabiliyor
-- (anl13'te iki kez oldu). Sifirlamanin oldugu saatte last(H) < last(H-1)
-- oldugu icin fark negatif cikip sifira kirpiliyor ve O SAATIN TUM TUKETIMI
-- kayboluyor -- olculen ornekte 380 Wh'lik gercek tuketim 0 olarak gorunuyordu.
-- first ve max ile o saat de dogru hesaplanabiliyor:
--     normal saat  : delta = last(H) - first(H)
--     sifirlanan   : delta = (max(H) - first(H)) + last(H)
--     saatler arasi: + GREATEST(first(H) - last(H-1), 0)
-- (Sifirlanan saatteki formul, sayacin ~0'a dondugu varsayimina dayanir --
--  enerji silme komutunun yaptigi sey budur.)
-- Cihaz basina ~1,8 MB/yil; sonsuza kadar saklanir.
CREATE MATERIALIZED VIEW IF NOT EXISTS device_energy_hourly
WITH (timescaledb.continuous) AS
SELECT
    device_id,
    time_bucket('1 hour', time) AS bucket,
    last(time, time) AS reading_time,

    first(active_wh_tuketim, time) AS first_active_tuketim,
    last(active_wh_tuketim, time)  AS active_wh_tuketim,
    max(active_wh_tuketim)         AS max_active_tuketim,

    first(inductive_varh_tuketim, time) AS first_inductive_tuketim,
    last(inductive_varh_tuketim, time)  AS inductive_varh_tuketim,
    max(inductive_varh_tuketim)         AS max_inductive_tuketim,

    first(capacitive_varh_tuketim, time) AS first_capacitive_tuketim,
    last(capacitive_varh_tuketim, time)  AS capacitive_varh_tuketim,
    max(capacitive_varh_tuketim)         AS max_capacitive_tuketim,

    first(active_wh_uretim, time) AS first_active_uretim,
    last(active_wh_uretim, time)  AS active_wh_uretim,
    max(active_wh_uretim)         AS max_active_uretim,

    first(inductive_varh_uretim, time) AS first_inductive_uretim,
    last(inductive_varh_uretim, time)  AS inductive_varh_uretim,
    max(inductive_varh_uretim)         AS max_inductive_uretim,

    first(capacitive_varh_uretim, time) AS first_capacitive_uretim,
    last(capacitive_varh_uretim, time)  AS capacitive_varh_uretim,
    max(capacitive_varh_uretim)         AS max_capacitive_uretim
FROM device_energy
GROUP BY device_id, bucket
WITH NO DATA;

-- ---------------------------------------------------------------------------
-- 4) measurements_15min -- 15 dakikalik ozet
-- ---------------------------------------------------------------------------
-- 15 dakika bilincli bir secim: Turkiye'de guc asim (sozlesme gucu) cezasi
-- 15 dakikalik ortalama guc uzerinden hesaplanir, dolayisiyla bu ozet hem
-- uzun donem gecmisi hem de ilerideki demand analizi icin dogrudan kullanilir.
-- Gerilim/THD min-max'lari da guc kalitesi raporu icin burada tutuluyor.
-- Cihaz basina ~12 MB/yil; sonsuza kadar saklanir.
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_15min
WITH (timescaledb.continuous) AS
SELECT
    device_id,
    time_bucket('15 minutes', time) AS bucket,
    count(*) AS sample_count,
    -- Toplam guclar (guc asim analizi icin). COALESCE: tek faz NULL ise
    -- toplamin tamami NULL olmasin.
    avg(COALESCE(p1,0) + COALESCE(p2,0) + COALESCE(p3,0)) AS avg_total_p,
    max(COALESCE(p1,0) + COALESCE(p2,0) + COALESCE(p3,0)) AS max_total_p,
    avg(COALESCE(q1,0) + COALESCE(q2,0) + COALESCE(q3,0)) AS avg_total_q,
    avg(COALESCE(s1,0) + COALESCE(s2,0) + COALESCE(s3,0)) AS avg_total_s,
    -- Gerilim (guc kalitesi / EN 50160)
    avg(v1) AS avg_v1, min(v1) AS min_v1, max(v1) AS max_v1,
    avg(v2) AS avg_v2, min(v2) AS min_v2, max(v2) AS max_v2,
    avg(v3) AS avg_v3, min(v3) AS min_v3, max(v3) AS max_v3,
    -- Akim
    avg(i1) AS avg_i1, max(i1) AS max_i1,
    avg(i2) AS avg_i2, max(i2) AS max_i2,
    avg(i3) AS avg_i3, max(i3) AS max_i3,
    avg(i_neutral) AS avg_i_neutral, max(i_neutral) AS max_i_neutral,
    -- Frekans
    avg(f1) AS avg_f, min(f1) AS min_f, max(f1) AS max_f,
    -- Guc faktoru
    avg(pf1) AS avg_pf1, avg(pf2) AS avg_pf2, avg(pf3) AS avg_pf3,
    -- Harmonik bozulma
    avg(thd1) AS avg_thd1, max(thd1) AS max_thd1,
    avg(thd2) AS avg_thd2, max(thd2) AS max_thd2,
    avg(thd3) AS avg_thd3, max(thd3) AS max_thd3,
    avg(thvd1) AS avg_thvd1, max(thvd1) AS max_thvd1,
    avg(thvd2) AS avg_thvd2, max(thvd2) AS max_thvd2,
    avg(thvd3) AS avg_thvd3, max(thvd3) AS max_thvd3
FROM measurements
GROUP BY device_id, bucket
WITH NO DATA;

-- ---------------------------------------------------------------------------
-- 5) Otomatik tazeleme politikalari
-- ---------------------------------------------------------------------------
-- end_offset kadar bir gecikme var ama TimescaleDB varsayilan olarak
-- "real-time aggregation" yapiyor: sorgu, materyalize edilmis kisim ile
-- henuz materyalize olmamis ham veriyi birlestirip donuyor. Yani panelde
-- anlik veri kaybi olmuyor.
SELECT add_continuous_aggregate_policy('device_energy_hourly',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => true);

SELECT add_continuous_aggregate_policy('measurements_15min',
    start_offset => INTERVAL '1 day',
    end_offset   => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => true);

-- ---------------------------------------------------------------------------
-- 6) Gercek zamanli birlestirme (real-time aggregation)
-- ---------------------------------------------------------------------------
-- TimescaleDB'nin yeni surumlerinde varsayilan materialized_only = true, yani
-- sorgu YALNIZCA materyalize edilmis veriyi gorur. Tazeleme is'i saatte bir
-- calistigi icin panelde son 1-2 saat eksik gorunurdu. false yapinca sorgu,
-- materyalize kismi ile henuz materyalize olmamis ham veriyi birlestirip
-- donuyor -- panel anlik kaliyor. Ham veri saklama politikasiyla silindiginde
-- birlestirilecek ham kisim kalmaz ve sorgu sadece ozetten okur; yani gecmis
-- kaybolmaz.
ALTER MATERIALIZED VIEW device_energy_hourly SET (timescaledb.materialized_only = false);
ALTER MATERIALIZED VIEW measurements_15min   SET (timescaledb.materialized_only = false);
