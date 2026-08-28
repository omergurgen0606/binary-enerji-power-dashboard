-- Abonelik altyapisi.
--
-- MODEL: cihaz basina ucret, fatura/havale ile odenir, abonelik yonetici
-- panelinden ELLE aktive edilir. Turkiye'de sanayi B2B satisi agirlikla boyle
-- isliyor; kart entegrasyonu (iyzico/PayTR) hacim geldiginde bunun uzerine
-- eklenebilir -- bu yuzden sema odeme saglayicisindan bagimsiz tutuldu.
--
-- SURE BITIMI: veri toplama DURMAZ, yalnizca panel kilitlenir. Musterinin
-- gecmisini silmek/kaybetmek geri donusu degersiz kilar.

CREATE TABLE IF NOT EXISTS subscriptions (
    organization_id INTEGER     PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    -- 'trial' | 'active' | 'cancelled'. Suresi gecmis abonelik ayri bir durum
    -- olarak SAKLANMIYOR: gecerlilik her istekte valid_until ile hesaplaniyor,
    -- boylece bir zamanlanmis is calismadi diye musteri yanlislikla acik kalmaz.
    status          TEXT        NOT NULL DEFAULT 'trial',
    device_price    NUMERIC     NOT NULL DEFAULT 0,   -- cihaz basina, donem basina
    period          TEXT        NOT NULL DEFAULT 'yearly',  -- 'monthly' | 'yearly'
    valid_until     TIMESTAMPTZ,
    device_limit    INTEGER,                          -- NULL = sinirsiz
    note            TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      TEXT
);

-- Denetim izi: fatura bazli calisildigi icin "ne zaman, kime, kac cihaz icin,
-- ne kadara acildi" kaydi tahsilatla mutabakatin kendisi.
CREATE TABLE IF NOT EXISTS subscription_events (
    id              SERIAL      PRIMARY KEY,
    organization_id INTEGER     NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    action          TEXT        NOT NULL,   -- 'created' | 'activated' | 'extended' | 'cancelled' | 'updated'
    valid_until     TIMESTAMPTZ,
    device_count    INTEGER,
    device_price    NUMERIC,
    amount          NUMERIC,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT
);

CREATE INDEX IF NOT EXISTS subscription_events_org_idx
    ON subscription_events (organization_id, created_at DESC);

-- MEVCUT organizasyonlar kilitlenmesin: bu goc calistigi anda sistemi kullanan
-- organizasyonlar zaten musteri; deneme suresine dusurmek onlari disari atardi.
INSERT INTO subscriptions (organization_id, status, valid_until, note, updated_by)
SELECT o.id, 'active', now() + INTERVAL '10 years',
       'Abonelik altyapısı kurulmadan önce var olan organizasyon', 'migration'
FROM organizations o
ON CONFLICT (organization_id) DO NOTHING;
