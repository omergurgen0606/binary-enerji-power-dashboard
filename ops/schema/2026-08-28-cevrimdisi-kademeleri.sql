-- Çevrimdışı alarmı için kademeli bildirim.
--
-- Önceden tek bildirim gönderiliyordu: cihaz çevrimdışı olunca bir kez, sonra
-- sessizlik. Bir cihazın günlerce kapalı kalması ile on beş dakika kapalı
-- kalması arasında hiçbir fark hissedilmiyordu.
--
-- Artık kademeler var (15 dk, 1 saat, 6 saat, 12 saat, 1 gün, 1 hafta, 1 ay) ve
-- sonuncudan sonra susuluyor -- sonsuza kadar bildirim göndermek, bildirimlerin
-- tamamen yok sayılmasıyla sonuçlanır.
--
-- offline_stage: bu çevrimdışı döneminde kaç kademe bildirildi. Cihaz geri
-- gelince 0'a döner. Kaydın kendisi değil sayaç tutuluyor; böylece tek bir
-- çevrimdışı dönemi panelde tek bir aktif alarm olarak görünüyor.
ALTER TABLE alarm_rules
    ADD COLUMN IF NOT EXISTS offline_stage integer NOT NULL DEFAULT 0;
