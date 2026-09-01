-- Tarifenin doğrulanıp doğrulanmadığını ve rakamların nereden geldiğini tutar.
--
-- NEDEN: sistem şimdiye kadar ikiliydi -- ya gerçek fiyat vardı ya hiç ₺ yoktu.
-- Arası olmadığı için, faturası henüz elinde olmayan bir müşteri ya ürünü hiç
-- kullanamıyor ya da yaklaşık rakam girip panelin bunları kesin tutar gibi
-- göstermesine razı oluyordu.
--
-- Bu boşluk gerçek bir hataya yol açtı: geliştirme sırasında girilen uydurma
-- rakamlar panelde günlerce gerçek fatura tutarı gibi durdu ve kimse fark
-- etmedi. İşaret olsaydı görünürdü.
--
-- tariff_source serbest metin: "Fatura, Ağustos 2026" ya da "yaklaşık -- EPDK
-- genel üç zamanlı, Nisan 2026" gibi. Bir sayıya bakıp nereden geldiğini
-- bilememek, sayının kendisinden daha tehlikeli.
ALTER TABLE device_tariff
    ADD COLUMN IF NOT EXISTS tariff_verified boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS tariff_source text;

-- Mevcut kayıtlar doğrulanmamış sayılır: hiçbiri fatura görülerek girilmedi.
UPDATE device_tariff SET tariff_verified = false WHERE tariff_verified IS NULL;
