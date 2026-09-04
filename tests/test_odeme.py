"""Iyzico ödeme akışı: fatura bilgisi, tutar hesabı, checkout başlatma, geri
çağrı (callback) doğrulaması.

En kritik test grubu callback'te: tarayıcıdan/POST'tan gelen "başarılı"
bilgisine ASLA güvenilmiyor, Iyzico'nun kendi sunucusuna sorulan sonuç
geçerli -- burada sahte bir "başarılı" callback'in aboneliği AÇAMADIĞI, ve
gerçek bir başarılı ödemenin AYNI token ile İKİNCİ kez geldiğinde aboneliği
TEKRAR uzatmadığı (idempotency) doğrulanıyor.

Uç nokta fonksiyonları doğrudan çağrılıyor; TestClient httpx gerektiriyor ve
üretim imajına yalnızca test için bağımlılık eklemek istemedik.
"""
import asyncio
import json

import pytest
from fastapi import HTTPException

import api
from conftest import sahte_db_connect


@pytest.fixture
def org_ve_cihaz(db, monkeypatch):
    """1 organizasyon, 1 cihaz, cihaz fiyatı 500 TL/ay, dönem aylık."""
    db.execute("INSERT INTO organizations (name) VALUES ('Test Org') RETURNING id")
    org_id = db.fetchone()[0]
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('odeyen', 'x', 'odeyen@test.local', true)")
    db.execute("INSERT INTO org_members (organization_id, username, role) VALUES (%s, 'odeyen', 'org_admin')",
               (org_id,))
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s, 'Merkez') RETURNING id", (org_id,))
    facility_id = db.fetchone()[0]
    db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
               "VALUES ('cihaz-1', 'Pano', 'odeyen', %s)", (facility_id,))
    db.execute("""
        INSERT INTO subscriptions (organization_id, status, device_price, period, valid_until)
        VALUES (%s, 'trial', 500, 'monthly', now() + interval '10 days')
    """, (org_id,))
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    monkeypatch.setattr(api, "check_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)
    return {"org_id": org_id}


def _fatura_bilgisi(db, org_id):
    db.execute("""
        INSERT INTO organization_billing
            (organization_id, contact_name, identity_number, email, phone, address, city, country)
        VALUES (%s, 'Ömer Gürgen', '12345678901', 'omer@test.local', '5551112233', 'Test Adres', 'İstanbul', 'Turkey')
    """, (org_id,))


# --------------------------------------------------------------------------
# Fatura bilgisi
# --------------------------------------------------------------------------

def test_fatura_bilgisi_olmadan_404(org_ve_cihaz):
    with pytest.raises(HTTPException) as e:
        api.get_billing_profile(user="odeyen")
    assert e.value.status_code == 404


def test_fatura_bilgisi_kaydedilir_ve_okunur(org_ve_cihaz):
    payload = api.BillingProfileRequest(
        contact_name="Ömer Gürgen", identity_number="12345678901", email="omer@test.local",
        phone="5551112233", address="Test Adres", city="İstanbul",
    )
    api.set_billing_profile(payload, user="odeyen")

    sonuc = api.get_billing_profile(user="odeyen")
    assert sonuc["contact_name"] == "Ömer Gürgen"
    assert sonuc["identity_number"] == "12345678901"


def test_gecersiz_kimlik_no_reddedilir(org_ve_cihaz):
    payload = api.BillingProfileRequest(
        contact_name="Ömer Gürgen", identity_number="abc", email="omer@test.local",
        phone="5551112233", address="Test Adres", city="İstanbul",
    )
    with pytest.raises(HTTPException) as e:
        api.set_billing_profile(payload, user="odeyen")
    assert e.value.status_code == 400


def test_bos_alan_reddedilir(org_ve_cihaz):
    payload = api.BillingProfileRequest(
        contact_name="  ", identity_number="12345678901", email="omer@test.local",
        phone="5551112233", address="Test Adres", city="İstanbul",
    )
    with pytest.raises(HTTPException) as e:
        api.set_billing_profile(payload, user="odeyen")
    assert e.value.status_code == 400


# --------------------------------------------------------------------------
# Tutar hesabı
# --------------------------------------------------------------------------

def test_tutar_cihaz_sayisi_ile_carpiliyor(org_ve_cihaz, db):
    fiyat = api.get_subscription_price(user="odeyen")
    assert fiyat["device_count"] == 1
    assert fiyat["months"] == 1  # period='monthly'
    assert fiyat["price"] == 500.0


def test_yillik_donemde_12_ayla_carpiliyor(org_ve_cihaz, db):
    db.execute("UPDATE subscriptions SET period = 'yearly' WHERE organization_id = %s",
               (org_ve_cihaz["org_id"],))
    fiyat = api.get_subscription_price(user="odeyen")
    assert fiyat["months"] == 12
    assert fiyat["price"] == 500.0 * 12


def test_cihazsiz_organizasyon_odeme_yapamaz(org_ve_cihaz, db):
    db.execute("DELETE FROM devices")
    with pytest.raises(HTTPException) as e:
        api.get_subscription_price(user="odeyen")
    assert e.value.status_code == 400


# --------------------------------------------------------------------------
# Checkout başlatma
# --------------------------------------------------------------------------

def test_fatura_bilgisi_olmadan_checkout_baslamaz(org_ve_cihaz):
    with pytest.raises(HTTPException) as e:
        api.start_subscription_checkout(user="odeyen", request=None)
    assert e.value.status_code == 400


def test_checkout_iyzico_basarisiyla_kayit_olusturur(org_ve_cihaz, db, monkeypatch):
    _fatura_bilgisi(db, org_ve_cihaz["org_id"])
    monkeypatch.setattr(api.iyzico, "checkout_baslat",
                        lambda **kw: {"status": "success", "token": "sahte-token-1",
                                     "paymentPageUrl": "https://sandbox-api.iyzipay.com/x"})

    sonuc = api.start_subscription_checkout(user="odeyen", request=None)

    assert sonuc["token"] == "sahte-token-1"
    db.execute("SELECT status, months, price FROM iyzico_payments WHERE token = 'sahte-token-1'")
    durum, ay, fiyat = db.fetchone()
    assert durum == "pending"
    assert ay == 1
    assert float(fiyat) == 500.0


def test_checkout_iyzico_basarisiz_donerse_500e_yansimaz_502_doner(org_ve_cihaz, db, monkeypatch):
    """Iyzico tarafı hata verirse kullanıcıya 502 (üst sistemde sorun var)
    dönmeli, panelin kendi 500'ü değil -- ayrım destek/hata ayıklama için önemli."""
    _fatura_bilgisi(db, org_ve_cihaz["org_id"])
    monkeypatch.setattr(api.iyzico, "checkout_baslat",
                        lambda **kw: {"status": "failure", "errorMessage": "gecersiz kart"})

    with pytest.raises(HTTPException) as e:
        api.start_subscription_checkout(user="odeyen", request=None)
    assert e.value.status_code == 502


# --------------------------------------------------------------------------
# Callback -- en kritik kısım
# --------------------------------------------------------------------------

class _SahteForm(dict):
    """Request.form()'un async dönüşünü taklit ediyor."""
    pass


class _SahteRequest:
    def __init__(self, token):
        self._token = token

    async def form(self):
        return {"token": self._token}


def _callback_calistir(token):
    return asyncio.run(api.subscription_payment_callback(_SahteRequest(token)))


def _odeme_kaydi_olustur(db, org_id, token="tok-1", months=1):
    db.execute("""
        INSERT INTO iyzico_payments
            (organization_id, token, conversation_id, months, device_count_at_purchase,
             device_price_at_purchase, price)
        VALUES (%s, %s, 'conv-1', %s, 1, 500, 500)
    """, (org_id, token, months))


def test_gecersiz_token_hataya_yonlendirir(org_ve_cihaz):
    yanit = _callback_calistir("hic-olmayan-token")
    assert yanit.status_code == 302
    assert "durum=hata" in yanit.headers["location"]


def test_iyzico_dogrulamasi_basarisizsa_abonelik_ACILMAZ(org_ve_cihaz, db, monkeypatch):
    """Bu testin koruduğu şey: tarayıcı/callback POST'u ne derse desin,
    Iyzico'nun kendi sunucusu 'başarısız' diyorsa abonelik açılmıyor."""
    org_id = org_ve_cihaz["org_id"]
    _odeme_kaydi_olustur(db, org_id)
    monkeypatch.setattr(api.iyzico, "checkout_dogrula",
                        lambda token: {"status": "success", "paymentStatus": "FAILURE", "fraudStatus": 1})

    yanit = _callback_calistir("tok-1")

    assert "durum=basarisiz" in yanit.headers["location"]
    durum = subscription_durumu(db, org_id)
    assert durum["status"] == "trial", "başarısız ödeme aboneliği 'active' yapmamalı"


def test_fraud_supheli_odeme_abonelik_ACMAZ(org_ve_cihaz, db, monkeypatch):
    org_id = org_ve_cihaz["org_id"]
    _odeme_kaydi_olustur(db, org_id)
    monkeypatch.setattr(api.iyzico, "checkout_dogrula",
                        lambda token: {"status": "success", "paymentStatus": "SUCCESS",
                                      "fraudStatus": -1, "paymentId": "pid-1"})

    yanit = _callback_calistir("tok-1")

    assert "durum=basarisiz" in yanit.headers["location"]


def test_basarili_odeme_aboneligi_uzatir(org_ve_cihaz, db, monkeypatch):
    org_id = org_ve_cihaz["org_id"]
    _odeme_kaydi_olustur(db, org_id, months=1)
    monkeypatch.setattr(api.iyzico, "checkout_dogrula",
                        lambda token: {"status": "success", "paymentStatus": "SUCCESS",
                                      "fraudStatus": 1, "paymentId": "pid-1"})

    yanit = _callback_calistir("tok-1")

    assert "durum=basarili" in yanit.headers["location"]
    durum = subscription_durumu(db, org_id)
    assert durum["status"] == "active"
    assert durum["active"] is True


def test_ayni_token_ikinci_kez_aboneligi_TEKRAR_UZATMAZ(org_ve_cihaz, db, monkeypatch):
    """Idempotency: Iyzico callback'i tekrar gönderebilir (ağ hatası,
    yeniden deneme) ya da kullanıcı sonuç sayfasını yeniler. Aynı ödeme iki
    kez işlenirse müşteri ödemediği ayları bedava kazanırdı."""
    org_id = org_ve_cihaz["org_id"]
    _odeme_kaydi_olustur(db, org_id, months=1)
    monkeypatch.setattr(api.iyzico, "checkout_dogrula",
                        lambda token: {"status": "success", "paymentStatus": "SUCCESS",
                                      "fraudStatus": 1, "paymentId": "pid-1"})

    _callback_calistir("tok-1")
    ilk_bitis = subscription_durumu(db, org_id)["valid_until"]

    # Iyzico'yu ikinci cagrida hic aramamali (kayit zaten 'success') --
    # cagrilirsa test kendisi patlar (monkeypatch kaldirilmadi ama onemli
    # olan valid_until'in DEGISMEMESI).
    _callback_calistir("tok-1")
    ikinci_bitis = subscription_durumu(db, org_id)["valid_until"]

    assert ilk_bitis == ikinci_bitis, "aynı token ikinci kez aboneliği uzattı"


def test_baska_organizasyona_dokunmaz(org_ve_cihaz, db, monkeypatch):
    db.execute("INSERT INTO organizations (name) VALUES ('Diğer Org') RETURNING id")
    diger_org_id = db.fetchone()[0]
    db.execute("INSERT INTO subscriptions (organization_id, status, device_price, period, valid_until) "
               "VALUES (%s, 'trial', 100, 'monthly', now() + interval '10 days')", (diger_org_id,))

    org_id = org_ve_cihaz["org_id"]
    _odeme_kaydi_olustur(db, org_id)
    monkeypatch.setattr(api.iyzico, "checkout_dogrula",
                        lambda token: {"status": "success", "paymentStatus": "SUCCESS",
                                      "fraudStatus": 1, "paymentId": "pid-1"})

    _callback_calistir("tok-1")

    diger_durum = subscription_durumu(db, diger_org_id)
    assert diger_durum["status"] == "trial", "başka organizasyonun aboneliği etkilendi"


def subscription_durumu(db, org_id):
    return api.subscription_state(org_id, db)
