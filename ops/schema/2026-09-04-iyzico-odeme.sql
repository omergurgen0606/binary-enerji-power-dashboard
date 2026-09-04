-- Iyzico ödeme entegrasyonu: fatura bilgisi profili + ödeme kayıtları.
--
-- NEDEN organization_billing AYRI TABLO: Iyzico'nun "buyer" nesnesi kimlik
-- numarası, adres, telefon gibi alanlar istiyor -- bunlar organizations
-- tablosunda hiç yoktu (yalnızca id/name/created_at). Bir kez girilip
-- saklanması hem her ödemede yeniden sorulmasın diye hem de ileride e-Fatura
-- otomasyonu için aynı bilgi lazım olacağı için.
CREATE TABLE IF NOT EXISTS organization_billing (
    organization_id integer PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    contact_name    text NOT NULL,
    identity_number text NOT NULL,  -- şahıs: TC kimlik no: sirket: vergi no
    email           text NOT NULL,
    phone           text NOT NULL,
    address         text NOT NULL,
    city            text NOT NULL,
    country         text NOT NULL DEFAULT 'Turkey',
    zip_code        text,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    updated_by      text
);

-- NEDEN AYRI TABLO (subscription_events'e eklemek yerine): bu tablo Iyzico
-- ile aramızdaki durumu (token, ham yanıt, tamamlandı mı) tutuyor --
-- subscription_events salt-okunur bir denetim izi, buraya yazma mantığı
-- karışırsa ikisi de bozulur. "token" üzerinde UNIQUE olması callback'in
-- (Iyzico'nun ya da kullanıcının sayfayı yenilemesinin) AYNI ödemeyi iki kez
-- işleyip aboneliği iki kez uzatmasını engelliyor -- idempotency burada
-- kritik, gerçek para hareketi var.
CREATE TABLE IF NOT EXISTS iyzico_payments (
    id                      serial PRIMARY KEY,
    organization_id         integer NOT NULL REFERENCES organizations(id),
    token                   text NOT NULL UNIQUE,
    conversation_id         text NOT NULL,
    status                  text NOT NULL DEFAULT 'pending',  -- pending, success, failure
    months                  integer NOT NULL,
    device_count_at_purchase integer NOT NULL,
    device_price_at_purchase numeric NOT NULL,
    price                   numeric NOT NULL,
    iyzico_payment_id       text,
    raw_response            jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz
);

CREATE INDEX IF NOT EXISTS iyzico_payments_org_idx ON iyzico_payments (organization_id);
