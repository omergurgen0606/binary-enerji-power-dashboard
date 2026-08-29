"""Yeni cihaza kendiliğinden açılan çevrimdışı alarmı.

Bu, varsayımsal bir eksik değildi: üretimdeki üç cihazın ikisinde çevrimdışı
kuralı yoktu. Biri dokuz gündür sessizdi, diğeri eklendiğinden beri hiç veri
göndermemişti, ve sistem ikisi için de kimseye bir şey söylemedi. Kademeli
bildirim altyapısı o cihazlarda hiç devreye girmiyordu -- izleyecek kural yoktu.
"""
import api


def test_varsayilan_esik_firmware_toparlanmasindan_uzun():
    """Eşik, cihazın kendi kendine düzelme süresinden uzun olmalı.

    Firmware WiFi kopunca 3 dakika yeniden bağlanmayı dener, sonra kendini
    yeniden başlatır ve ~15 saniyede bağlanır. Eşik bundan kısa olsaydı,
    cihazın kendi düzelttiği her kesinti boş alarm üretirdi.
    """
    firmware_toparlanma_dk = 3 + 1  # yeniden bağlanma denemesi + reboot payı
    assert api.DEFAULT_OFFLINE_MINUTES > firmware_toparlanma_dk


def test_varsayilan_esik_tam_merdiveni_acar():
    """15'ten küçük olmalı, yoksa merdivenin ilk iki basamağı çakışır."""
    assert api.DEFAULT_OFFLINE_MINUTES < 15
    kademeler = api._offline_milestones(api.DEFAULT_OFFLINE_MINUTES)
    assert len(kademeler) == 8
    assert kademeler[0] == api.DEFAULT_OFFLINE_MINUTES
    assert kademeler[1] == 15


def test_alarmsiz_cihaza_kural_acilir(db):
    cur = db  # fixture imleç veriyor, bağlantı değil
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('alarmtest', 'x', 'alarmtest@example.com', true)")
    cur.execute("INSERT INTO devices (device_id, name, owner_username) "
                "VALUES ('yeni-cihaz', 'Yeni', 'alarmtest')")

    olusturuldu = api.ensure_offline_alarm('yeni-cihaz', cur)

    assert olusturuldu is True
    cur.execute("SELECT metric, phase, condition, offline_minutes, enabled, threshold "
                "FROM alarm_rules WHERE device_id = 'yeni-cihaz'")
    metric, phase, condition, dakika, enabled, threshold = cur.fetchone()
    assert metric == 'offline'
    assert dakika == api.DEFAULT_OFFLINE_MINUTES
    assert enabled is True
    assert threshold is None  # çevrimdışı kuralının eşik değeri olmaz


def test_ikinci_cagri_kural_acmaz(db):
    """Idempotent olmalı: geriye dönük tamamlama tekrar çalıştırılabilir."""
    cur = db  # fixture imleç veriyor, bağlantı değil
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('alarmtest2', 'x', 'alarmtest2@example.com', true)")
    cur.execute("INSERT INTO devices (device_id, name, owner_username) "
                "VALUES ('cihaz-2', 'İki', 'alarmtest2')")

    assert api.ensure_offline_alarm('cihaz-2', cur) is True
    assert api.ensure_offline_alarm('cihaz-2', cur) is False

    cur.execute("SELECT count(*) FROM alarm_rules WHERE device_id = 'cihaz-2'")
    assert cur.fetchone()[0] == 1


def test_kullanicinin_kendi_esigi_korunur(db):
    """Kullanıcı eşiği değiştirdiyse üzerine yazılmamalı."""
    cur = db  # fixture imleç veriyor, bağlantı değil
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('alarmtest3', 'x', 'alarmtest3@example.com', true)")
    cur.execute("INSERT INTO devices (device_id, name, owner_username) "
                "VALUES ('cihaz-3', 'Üç', 'alarmtest3')")
    cur.execute("INSERT INTO alarm_rules (device_id, metric, phase, condition, offline_minutes) "
                "VALUES ('cihaz-3', 'offline', 'any', 'gt', 45)")

    assert api.ensure_offline_alarm('cihaz-3', cur) is False

    cur.execute("SELECT offline_minutes FROM alarm_rules WHERE device_id = 'cihaz-3'")
    assert cur.fetchone()[0] == 45


def test_baska_tipte_alarmi_olan_cihaz_yine_de_cevrimdisi_alir(db):
    """Gerilim alarmı olması, çevrimdışı alarmı yerine geçmez.

    Üretimdeki anl21 cihazının hem gerilim hem çevrimdışı kuralı vardı;
    kontrol metric='offline' üzerinden yapılmazsa gerilim alarmı olan bir
    cihaz izlemesiz kalır.
    """
    cur = db  # fixture imleç veriyor, bağlantı değil
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('alarmtest4', 'x', 'alarmtest4@example.com', true)")
    cur.execute("INSERT INTO devices (device_id, name, owner_username) "
                "VALUES ('cihaz-4', 'Dört', 'alarmtest4')")
    cur.execute("INSERT INTO alarm_rules (device_id, metric, phase, condition, threshold) "
                "VALUES ('cihaz-4', 'voltage', 'any', 'gt', 250)")

    assert api.ensure_offline_alarm('cihaz-4', cur) is True

    cur.execute("SELECT count(*) FROM alarm_rules WHERE device_id = 'cihaz-4' AND metric = 'offline'")
    assert cur.fetchone()[0] == 1
