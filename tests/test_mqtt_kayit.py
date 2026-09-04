"""Cihaz-başına MQTT kaydı.

Broker'da tek paylaşılan kimlik bilgisi var ve topic izolasyonu yok -- bu
kimlik bilgisini elinde tutan biri her cihazın topic'ine yazabiliyordu. Çözüm
her cihazın kendi ürettiği kimliği bu uç noktayla kaydettirmesi. Buradaki
testler, kaydın yalnızca cihazın gerçek sahibi tarafından ve doğru biçimde
yapılabildiğini, ve parolanın hiçbir yerde (denetim kaydı dahil) sızmadığını
koruyor.

Uç nokta fonksiyonları doğrudan çağrılıyor; TestClient httpx gerektiriyor ve
üretim imajına yalnızca test için bağımlılık eklemek istemedik.
"""
import pytest
from fastapi import HTTPException

import api
from conftest import sahte_db_connect


@pytest.fixture
def sahip(db, monkeypatch):
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('kayitci', 'x', 'kayitci@test.local', true)")
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('anl21-test', 'Test Panosu', 'kayitci')")
    monkeypatch.setattr(api, "is_device_owner", lambda u, d: u == "kayitci")
    monkeypatch.setattr(api, "check_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    return {"device_id": "anl21-test"}


def _istek(kullanici_adi="anl21-test", sifre="a" * 48):
    return api.MqttEnrollRequest(username=kullanici_adi, password=sifre)


def test_gecerli_kayit_saklanir(sahip, db):
    sonuc = api.enroll_device_mqtt("anl21-test", _istek(), user="kayitci")
    assert "kayd" in sonuc["message"]

    db.execute("SELECT mqtt_username, mqtt_password, applied FROM device_mqtt_credentials "
               "WHERE device_id = 'anl21-test'")
    kullanici, sifre, uygulandi = db.fetchone()
    assert kullanici == "anl21-test"
    assert sifre == "a" * 48
    assert uygulandi is False, "yeni kayit applied=false ile baslamali -- host betigi uygulayacak"


def test_sahibi_olmayan_kayit_yapamaz(sahip, db):
    with pytest.raises(HTTPException) as e:
        api.enroll_device_mqtt("anl21-test", _istek(), user="baskasi")
    assert e.value.status_code == 403

    db.execute("SELECT count(*) FROM device_mqtt_credentials WHERE device_id = 'anl21-test'")
    assert db.fetchone()[0] == 0


def test_kullanici_adi_cihaz_kimligiyle_eslesmeli(sahip, db):
    """Cihaz KENDI device_id'sini kullanici adi olarak gonderiyor -- baska bir
    cihazin adina kayit yaptirmaya calisan istek reddedilmeli."""
    with pytest.raises(HTTPException) as e:
        api.enroll_device_mqtt("anl21-test", _istek(kullanici_adi="baska-cihaz"), user="kayitci")
    assert e.value.status_code == 400


def test_gecersiz_parola_bicimi_reddedilir(sahip, db):
    with pytest.raises(HTTPException) as e:
        api.enroll_device_mqtt("anl21-test", _istek(sifre="cok-kisa"), user="kayitci")
    assert e.value.status_code == 400


def test_ikinci_kayit_ilkinin_ustune_yazar_ve_yeniden_uygulanmayi_bekler(sahip, db):
    """Cihaz WiFi'sini sifirlayip yeniden kurulum akisindan gecerse -- ya da
    ayni cihaz bir sebeple ikinci kez enroll ederse -- eski kayit degil YENI
    kayit gecerli olmali, ve applied yeniden false'a donmeli ki host betigi
    yeni parolayi broker'a uygulasin."""
    api.enroll_device_mqtt("anl21-test", _istek(sifre="a" * 48), user="kayitci")
    db.execute("UPDATE device_mqtt_credentials SET applied = true WHERE device_id = 'anl21-test'")

    api.enroll_device_mqtt("anl21-test", _istek(sifre="b" * 48), user="kayitci")

    db.execute("SELECT mqtt_password, applied FROM device_mqtt_credentials WHERE device_id = 'anl21-test'")
    sifre, uygulandi = db.fetchone()
    assert sifre == "b" * 48
    assert uygulandi is False


def test_parola_denetim_kaydina_yazilmaz(sahip, db, monkeypatch):
    kayitlar = []
    monkeypatch.setattr(api, "audit",
                        lambda action, **kw: kayitlar.append((action, kw.get("detail"))))

    gizli_sifre = "deadbeef" * 6  # 48 hex karakter, gecerli bicim
    api.enroll_device_mqtt("anl21-test", _istek(sifre=gizli_sifre), user="kayitci")

    assert kayitlar, "denetim kaydi yazilmadi"
    hepsi = repr(kayitlar)
    assert gizli_sifre not in hepsi, "MQTT parolasi denetim kaydina sizdi"


def test_baska_cihaza_dokunmaz(sahip, db):
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('kalacak-cihaz', 'Diger', 'kayitci')")
    db.execute("INSERT INTO device_mqtt_credentials (device_id, mqtt_username, mqtt_password, applied) "
               "VALUES ('kalacak-cihaz', 'kalacak-cihaz', %s, true)", ("c" * 48,))

    api.enroll_device_mqtt("anl21-test", _istek(), user="kayitci")

    db.execute("SELECT mqtt_password, applied FROM device_mqtt_credentials WHERE device_id = 'kalacak-cihaz'")
    sifre, uygulandi = db.fetchone()
    assert sifre == "c" * 48
    assert uygulandi is True
