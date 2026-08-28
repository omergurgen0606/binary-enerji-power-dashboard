-- Alarm e-postasi tercihi.
--
-- Alarm e-postasi bugune kadar yalnizca cihaz sahibine gidiyordu; artik cihaza
-- erisimi olan herkese (tesis/bolum yoneticileri dahil) gidiyor. Bu, hic talep
-- etmemis kisilere e-posta hacmi getirdigi icin kapatma secenegi de sart.
-- Varsayilan acik: alarm, urunun en kritik bildirimi.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS alarm_email BOOLEAN NOT NULL DEFAULT true;
