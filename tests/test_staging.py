"""Staging ortamının dış dünyaya sızmadığını doğrular.

Staging, üretimle AYNI mosquitto'yu dinler ve AYNI kod tabanını çalıştırır;
farkı yalnızca ayrı bir veritabanına yazmasıdır. Bu, gerçekçi veriyle test
etmeyi mümkün kılar ama tehlikeli bir yakınlık da yaratır: korumalar
olmasaydı staging gerçek müşteriye e-posta atar, gerçek telefona bildirim
gönderir ve sahadaki gerçek cihaza Modbus komutu yazardı.

Bu yüzden korumalar bir yorum satırı değil, testle bağlanmış bir sözleşme.
"""
import pytest

import api


def test_komut_yayini_staging_de_reddedilir(monkeypatch):
    """En tehlikelisi bu: komut yayını gerçek donanıma gider.

    Okuma paylaşılabilir (staging aynı ölçümleri dinleyebilir), yazma asla.
    """
    monkeypatch.setattr(api, "IS_STAGING", True)

    with pytest.raises(api.HTTPException) as hata:
        api.publish_command("anl21-8085d8", register=9024, value=43605)

    assert hata.value.status_code == 503
    assert "gerçek cihaza" in hata.value.detail


def test_komut_yayini_uretimde_engellenmez(monkeypatch):
    """Koruma yalnızca staging'de devrede olmalı.

    Üretimde de engellenseydi cihaz komutları tamamen çalışmaz olurdu; bu
    test korumanın fazla geniş kurulmasına karşı.
    """
    monkeypatch.setattr(api, "IS_STAGING", False)
    cagrildi = {}

    class SahteIstemci:
        def __init__(self, *a, **k):
            cagrildi["olustu"] = True

        def username_pw_set(self, *a, **k):
            pass

        def connect(self, *a, **k):
            raise RuntimeError("baglanti denendi")

    monkeypatch.setattr(api.mqtt, "Client", SahteIstemci)

    # Staging koruması devrede olsaydı HTTPException alırdık ve MQTT
    # istemcisi hiç oluşturulmazdı.
    with pytest.raises(RuntimeError):
        api.publish_command("anl21-8085d8", register=9001)
    assert cagrildi.get("olustu") is True


def test_ota_tetikleme_staging_de_reddedilir(monkeypatch, db):
    """trigger_ota kendi mqtt.Client'ini ACIYOR, publish_command'i cagirmiyor --
    yani genel komut korumasi burayi kapsamiyordu. Staging'den "OTA tetikle"
    denemesi, ayni broker'i dinleyen GERCEK bir sahadaki cihaza firmware
    indirtebilirdi. Bu test, o ayri MQTT yolunun da staging'de kapali
    olduğunu doğruluyor -- publish_command'daki korumanın varlığı yeterli
    değil, her gerçek-cihaza-yazan yol ayrı ayrı kontrol edilmeli.
    """
    from conftest import sahte_db_connect

    db.execute("INSERT INTO organizations (name) VALUES ('OTA Test Org') RETURNING id")
    org_id = db.fetchone()[0]
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('ota_sahibi', 'x', 'ota_sahibi@test.local', true)")
    db.execute("INSERT INTO org_members (organization_id, username, role) "
               "VALUES (%s, 'ota_sahibi', 'org_admin')", (org_id,))
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s, 'Merkez') RETURNING id",
               (org_id,))
    facility_id = db.fetchone()[0]
    db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
               "VALUES ('anl21-aabbcc', 'Test Cihazı', 'ota_sahibi', %s)", (facility_id,))
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)
    monkeypatch.setattr(api, "IS_STAGING", True)

    cagrildi = {}

    class SahteIstemci:
        def __init__(self, *a, **k):
            cagrildi["olustu"] = True

    monkeypatch.setattr(api.mqtt, "Client", SahteIstemci)

    with pytest.raises(api.HTTPException) as hata:
        api.trigger_ota("anl21-aabbcc", user="ota_sahibi")

    assert hata.value.status_code == 503
    assert "gerçek cihaza" in hata.value.detail
    assert "olustu" not in cagrildi, "staging korumasi mqtt istemcisi olusturulmadan ONCE devreye girmeli"


def test_push_bildirimi_staging_de_gonderilmez(monkeypatch):
    """pywebpush import bile edilmemeli -- gönderim yolu hiç başlamamalı."""
    monkeypatch.setattr(api, "IS_STAGING", True)

    sonuc = api._push_send_one(
        sub_id=1, endpoint="https://ornek.test/push", p256dh="x", auth="y",
        payload={"title": "test"}, cur=None,
    )

    # cur=None verildi: gerçek gönderim yolu çalışsaydı imleçte patlardı.
    assert sonuc is True


def test_eposta_korumasi_gercekten_baglaniyor(monkeypatch):
    """Yutucunun tanımlı olması yetmez; resend'e bağlandığı doğrulanmalı."""
    gonderilenler = []

    class SahteEmails:
        @staticmethod
        def send(payload, *a, **k):
            gonderilenler.append(payload)
            return {"id": "gercekten-gonderildi"}

    monkeypatch.setattr(api.resend, "Emails", SahteEmails)

    api._staging_korumalarini_uygula()

    sonuc = api.resend.Emails.send({"to": ["musteri@ornek.test"],
                                    "subject": "Cihaz çevrimdışı"})

    assert gonderilenler == [], "staging'de gerçek e-posta gönderim yolu çağrıldı"
    assert sonuc["id"] == "staging-gonderilmedi"


def test_staging_bayragi_ortam_degiskeninden_okunur():
    """STAGING=1 dışındaki hiçbir değer staging sayılmamalı.

    Yanlış tarafa düşmek tehlikeli: staging sanılan bir üretim sessizce
    e-posta göndermeyi keser.
    """
    import os
    assert api.IS_STAGING == (os.environ.get("STAGING") == "1")
