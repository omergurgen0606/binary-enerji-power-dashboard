-- Denetim kaydı + KVKK (veri dışa aktarma / hesap silme).

-- ---------------------------------------------------------------------------
-- Denetim kaydı
-- ---------------------------------------------------------------------------
-- actor'da users'a FK YOK ve bu bilincli: denetim izinin varlik sebebi,
-- kullanici silinse bile "kim yapti" sorusunu cevaplayabilmek. FK olsaydi
-- kullanici silindiginde iz de silinir ya da silmeyi engellerdi.
--
-- KVKK ile celiskisi yok: hesap silindiginde actor anonimlestiriliyor
-- (silinmis-kullanici-N), kayit kaliyor ama kisiyle iliskilendirilemiyor.
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL   PRIMARY KEY,
    at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor           TEXT,
    organization_id INTEGER,
    action          TEXT        NOT NULL,
    entity_type     TEXT,
    entity_id       TEXT,
    detail          JSONB,
    ip              TEXT
);

-- Organizasyon yoneticisi kendi kaydini zaman sirasiyla okuyor.
CREATE INDEX IF NOT EXISTS audit_log_org_idx ON audit_log (organization_id, at DESC);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx ON audit_log (actor, at DESC);

-- ---------------------------------------------------------------------------
-- KVKK: silme talebi izi
-- ---------------------------------------------------------------------------
-- Silinen hesabin KENDISI degil, silme TALEBININ yerine getirildigi kaydi.
-- Kisisel veri icermiyor (kullanici adi hash'leniyor); amaci "talep geldi ve
-- karsilandi" diyebilmek.
CREATE TABLE IF NOT EXISTS deletion_requests (
    id           BIGSERIAL   PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_hash    TEXT        NOT NULL,
    note         TEXT
);
