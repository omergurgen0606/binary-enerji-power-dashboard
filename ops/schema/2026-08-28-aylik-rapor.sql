-- Aylik PDF raporu e-posta tercihi.
-- Varsayilan acik: rapor urunun sundugu tekrarlayan degerin kendisi, kullanici
-- istemezse kapatabilsin diye devre disi birakma secenegi.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS monthly_report BOOLEAN NOT NULL DEFAULT true;
