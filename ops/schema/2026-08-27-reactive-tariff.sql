-- Reaktif ceza analizi icin cihaz bazli tarife ayarlari.
-- Limitler ve birim fiyatlar mevzuata/tarifeye gore degistigi ve abone
-- grubuna gore farklilastigi icin kod icine gomulmuyor; musteri kendi
-- faturasindaki degerleri girebilsin diye cihaz bazinda tutuluyor.
CREATE TABLE IF NOT EXISTS device_tariff (
    device_id            TEXT PRIMARY KEY,
    inductive_limit_pct  NUMERIC     NOT NULL DEFAULT 20,
    capacitive_limit_pct NUMERIC     NOT NULL DEFAULT 15,
    reactive_price       NUMERIC     NOT NULL DEFAULT 0,   -- TL / kVArh
    active_price         NUMERIC     NOT NULL DEFAULT 0,   -- TL / kWh
    billing_mode         TEXT        NOT NULL DEFAULT 'full',  -- 'full' | 'excess'
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by           TEXT
);
