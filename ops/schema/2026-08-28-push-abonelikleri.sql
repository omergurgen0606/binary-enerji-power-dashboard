-- Push bildirimi abonelikleri.
--
-- transport sutunu bilincli olarak genel: bugun yalnizca 'webpush' kullaniliyor
-- ama native FCM (Android) ve APNs (iOS) ayni tabloya eklenecek. Boylece alarm
-- gonderim yolu tek bir yerde kalir, tasima katmani degistiginde dagitim
-- mantigi yeniden yazilmaz.
--
-- endpoint: Web Push icin push servisinin URL'i; FCM/APNs icin cihaz token'i.
-- p256dh/auth: yalnizca Web Push'un sifreleme anahtarlari, digerlerinde NULL.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id            SERIAL PRIMARY KEY,
    username      TEXT        NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    transport     TEXT        NOT NULL DEFAULT 'webpush',
    endpoint      TEXT        NOT NULL,
    p256dh        TEXT,
    auth          TEXT,
    user_agent    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_success  TIMESTAMPTZ,
    failure_count INTEGER     NOT NULL DEFAULT 0,
    UNIQUE (endpoint)
);

CREATE INDEX IF NOT EXISTS push_subscriptions_user_idx
    ON push_subscriptions (username);
