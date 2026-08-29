"""Cihazın WiFi ağını uzaktan değiştirme.

Buradaki en büyük risk cihazı tamamen kaybetmek: yanlış bilgi girilirse cihaz
yeni ağa bağlanamaz, eskisini de unutmuşsa yerinde müdahale gerekir. Firmware
bu yüzden yeni bilgileri ancak BAŞARILI bağlantıdan sonra kaydediyor
(ESP32-ANL21.ino, handleWifiConfig). Buradaki testler komutun cihaza hangi
koşullarda gönderildiğini koruyor.

Uç nokta fonksiyonları doğrudan çağrılıyor; TestClient httpx gerektiriyor ve
üretim imajına yalnızca test için bağımlılık eklemek istemedik.
"""
import pytest
from fastapi import HTTPException

import api


@pytest.fixture
def cihaz_sahibi(monkeypatch):
    monkeypatch.setattr(api, "is_device_owner", lambda u, d: True)
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)


@pytest.fixture
def cevrimici():
    api.device_status["test-cihaz"] = {"status": "online", "changed_at": "x"}
    yield
    api.device_status.pop("test-cihaz", None)


def _istek(ssid="Fabrika", parola="gizli"):
    return api.WifiConfigRequest(ssid=ssid, password=parola)


def test_cevrimdisi_cihaza_gonderilmez(cihaz_sahibi, monkeypatch):
    """MQTT'de kuyruk yok: dinlemeyen cihaza giden mesaj kaybolur.

    Engellenmeseydi kullanıcı ayarın uygulandığını sanır, cihaz eski ağında
    kalırdı -- sessiz ve tespiti zor bir başarısızlık.
    """
    api.device_status.pop("test-cihaz", None)
    yayinlandi = []
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: yayinlandi.append(a))

    with pytest.raises(HTTPException) as e:
        api.set_device_wifi("test-cihaz", _istek(), user="omer")

    assert e.value.status_code == 409
    assert yayinlandi == [], "çevrimdışı cihaza komut yayınlandı"


def test_bos_ssid_reddedilir(cihaz_sahibi, cevrimici, monkeypatch):
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: None)
    with pytest.raises(HTTPException) as e:
        api.set_device_wifi("test-cihaz", _istek(ssid="   "), user="omer")
    assert e.value.status_code == 400


def test_asiri_uzun_alanlar_reddedilir(cihaz_sahibi, cevrimici, monkeypatch):
    """SSID 32, WPA parolası 63 karakterle sınırlı -- firmware tamponu da öyle."""
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: None)

    with pytest.raises(HTTPException) as e:
        api.set_device_wifi("test-cihaz", _istek(ssid="A" * 33), user="omer")
    assert e.value.status_code == 400

    with pytest.raises(HTTPException) as e2:
        api.set_device_wifi("test-cihaz", _istek(parola="P" * 64), user="omer")
    assert e2.value.status_code == 400


def test_cevrimici_cihaza_gonderilir(cihaz_sahibi, cevrimici, monkeypatch):
    yayinlandi = []
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: yayinlandi.append(a))

    sonuc = api.set_device_wifi("test-cihaz", _istek(), user="omer")

    assert yayinlandi == [("test-cihaz", "Fabrika", "gizli")]
    assert "message" in sonuc


def test_parola_denetim_kaydina_yazilmaz(cevrimici, monkeypatch):
    """Denetim kaydı SSID'yi tutar, parolayı ASLA."""
    monkeypatch.setattr(api, "is_device_owner", lambda u, d: True)
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: None)

    kayitlar = []
    monkeypatch.setattr(api, "audit",
                        lambda action, **kw: kayitlar.append((action, kw.get("detail"))))

    api.set_device_wifi("test-cihaz", _istek(parola="cok-gizli-parola"), user="omer")

    assert kayitlar, "denetim kaydı yazılmadı"
    hepsi = repr(kayitlar)
    assert "cok-gizli-parola" not in hepsi, "parola denetim kaydına sızdı"
    assert "Fabrika" in hepsi


def test_yeni_istek_onceki_sonucu_temizler(cihaz_sahibi, cevrimici, monkeypatch):
    """Eski sonuç durmasa da olmaz: kullanıcı bir önceki denemenin
    sonucuna bakıp yenisinin bittiğini sanabilir."""
    monkeypatch.setattr(api, "publish_wifi_config", lambda *a: None)
    api.device_wifi_result["test-cihaz"] = {"ok": False, "hata": "eski"}

    api.set_device_wifi("test-cihaz", _istek(), user="omer")

    assert api.device_wifi_result.get("test-cihaz") is None
