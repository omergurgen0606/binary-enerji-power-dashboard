-- Fatura analizi: uc zamanli tarife + sozlesme gucu (guc asim) alanlari.
--
-- Turkiye'de sanayi aboneliginde aktif enerji uc zaman diliminde farkli
-- fiyatlanir (gunduz/puant/gece) ve 15 dakikalik ortalama guc sozlesme gucunu
-- asarsa ayrica guc asim bedeli dogar. Reaktif cezada oldugu gibi saat
-- sinirlari, fiyatlar ve sozlesme gucu koda gomulmuyor -- tarifeye ve abone
-- grubuna gore degistigi ve donemsel guncellendigi icin cihaz bazinda ayar.
ALTER TABLE device_tariff
    -- Zaman dilimi baslangic saatleri (yerel saat, 0-23).
    -- Varsayilan: T1 gunduz 06-17, T2 puant 17-22, T3 gece 22-06.
    ADD COLUMN IF NOT EXISTS t1_start SMALLINT NOT NULL DEFAULT 6,
    ADD COLUMN IF NOT EXISTS t2_start SMALLINT NOT NULL DEFAULT 17,
    ADD COLUMN IF NOT EXISTS t3_start SMALLINT NOT NULL DEFAULT 22,
    -- Zaman dilimi birim fiyatlari (TL/kWh). Hepsi 0 ise zaman dilimli
    -- fiyatlandirma kapali sayilir ve mevcut tek fiyatli active_price kullanilir.
    ADD COLUMN IF NOT EXISTS t1_price NUMERIC NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS t2_price NUMERIC NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS t3_price NUMERIC NOT NULL DEFAULT 0,
    -- Sozlesme gucu (kW). NULL ise guc asim analizi yapilmaz.
    ADD COLUMN IF NOT EXISTS contract_power_kw NUMERIC,
    -- Asan kW basina bedel (TL/kW).
    ADD COLUMN IF NOT EXISTS demand_price NUMERIC NOT NULL DEFAULT 0;
