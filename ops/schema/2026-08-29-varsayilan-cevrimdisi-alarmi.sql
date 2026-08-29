-- Alarm kuralı olmayan cihazlara varsayılan çevrimdışı alarmı ekler.
--
-- NEDEN: alarm eklemeyi hatırlamak müşterinin işi olmamalı. İzleme ürününün
-- varsayılanı izlemek olmalı. Bu göç yazılırken üretimdeki üç cihazın ikisinde
-- çevrimdışı kuralı yoktu:
--   * ANL13          -> 9 gün 21 saattir sessiz, kimseye haber verilmedi
--   * anl 13 yeni    -> eklendiğinden beri HİÇ veri göndermemiş, yine sessizlik
-- Yani kademeli bildirim altyapısı bu cihazlarda hiç devreye girmiyordu, çünkü
-- izleyecek kural yoktu.
--
-- Idempotent: yalnızca çevrimdışı kuralı OLMAYAN cihazlara ekler. Var olan
-- kuralların eşiğine dokunmaz -- kullanıcının kendi ayarı korunur.
--
-- Not: bir kullanıcı çevrimdışı alarmını bilerek sildiyse bu göç onu geri
-- getirir. Tek seferlik ve kabul edilebilir bir yan etki: veri kaybını sessizce
-- yaşamaktansa silinebilir bir alarma sahip olmak yeğdir.
INSERT INTO alarm_rules (device_id, metric, phase, condition, offline_minutes)
SELECT d.device_id, 'offline', 'any', 'gt', 10
FROM devices d
WHERE NOT EXISTS (
    SELECT 1 FROM alarm_rules r
    WHERE r.device_id = d.device_id AND r.metric = 'offline'
);
