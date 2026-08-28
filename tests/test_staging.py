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
