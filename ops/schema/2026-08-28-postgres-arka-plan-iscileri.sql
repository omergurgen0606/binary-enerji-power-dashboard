-- TimescaleDB arka plan isci ayarlari.
--
-- SORUN: Onceki gun 16 politika (6 sikistirma + 6 saklama + 2 tazeleme +
-- 2 ozet sikistirma) ayni anda olusturulunca hepsi ayni saniyede calismaya
-- kalkti ve log'a su dustu:
--     WARNING: failed to launch job 1003 "Columnstore Policy [1003]":
--              failed to start a background worker
-- Nedeni: timescaledb.max_background_workers = 16 (varsayilan) iken
-- max_worker_processes = 8 idi. TimescaleDB'nin sarti:
--     max_worker_processes >= timescaledb.max_background_workers
--                             + max_parallel_workers + 1
-- yani 8 >= 16 + 8 + 1 saglanmiyordu. Isler yeniden denenip basarili oldu,
-- ama bu sessizce tekrar edecek ve cihaz sayisi artinca sikistirma/saklama
-- politikalari fark edilmeden geri kalacakti.
--
-- COZUM: Tek cekirdekli / 961 MB RAM'li bu sunucuya gore olceklendirildi.
-- Paralel sorgu tek cekirdekte cogunlukla ek yuk oldugu icin dusuruldu.
-- Hepsi postmaster seviyesinde -- uygulandiktan sonra RESTART gerekiyor:
--     docker compose restart timescaledb && docker compose restart api
ALTER SYSTEM SET max_worker_processes = 16;              -- 8 + 2 + 1 + pay
ALTER SYSTEM SET timescaledb.max_background_workers = 8; -- isler zamana yayili
ALTER SYSTEM SET max_parallel_workers = 2;               -- tek cekirdek
ALTER SYSTEM SET max_parallel_workers_per_gather = 1;
