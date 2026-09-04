"""Iyzico Checkout Form entegrasyonu -- imzalama, istek gönderme, sonuç doğrulama.

Ayrı dosyada: imzalama mantığı kendi başına (gerçek ağ çağrısı olmadan) test
edilebilir olmalı, ve api.py zaten çok büyük.

Kaynak: https://docs.iyzico.com (Checkout Form, HMACSHA256 Authentication).
Test ortamı (sandbox) ile üretim arasındaki TEK fark taban URL -- kendi
merchant hesabınızın sandbox API anahtarlarını IYZICO_API_KEY/
IYZICO_SECRET_KEY olarak, taban URL'i IYZICO_BASE_URL olarak .env'e
eklemeniz yeterli (varsayılan sandbox'a işaret ediyor).
"""
import base64
import hashlib
import hmac
import json
import os
import uuid

import requests

IYZICO_BASE_URL = os.environ.get("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com")
IYZICO_API_KEY = os.environ.get("IYZICO_API_KEY", "")
IYZICO_SECRET_KEY = os.environ.get("IYZICO_SECRET_KEY", "")


class IyzicoHatasi(Exception):
    pass


def _imza_hesapla(random_key: str, uri_path: str, govde_json: str, secret_key: str) -> str:
    mesaj = random_key + uri_path + govde_json
    return hmac.new(secret_key.encode("utf-8"), mesaj.encode("utf-8"), hashlib.sha256).hexdigest()


def yetkilendirme_basligi(uri_path: str, govde_json: str, api_key: str = None, secret_key: str = None) -> str:
    """IYZWSv2 Authorization başlığını üretir.

    api_key/secret_key parametreleri TESTTE gerçek anahtar olmadan bu
    fonksiyonu doğrulayabilmek için var -- normal çağrılarda modül
    seviyesindeki IYZICO_API_KEY/IYZICO_SECRET_KEY kullanılır.
    """
    api_key = api_key or IYZICO_API_KEY
    secret_key = secret_key or IYZICO_SECRET_KEY
    random_key = uuid.uuid4().hex
    imza = _imza_hesapla(random_key, uri_path, govde_json, secret_key)
    ham = f"apiKey:{api_key}&randomKey:{random_key}&signature:{imza}"
    kodlanmis = base64.b64encode(ham.encode("utf-8")).decode("ascii")
    return f"IYZWSv2 {kodlanmis}"


def _istek(uri_path: str, govde: dict) -> dict:
    if not IYZICO_API_KEY or not IYZICO_SECRET_KEY:
        raise IyzicoHatasi("IYZICO_API_KEY / IYZICO_SECRET_KEY tanımlı değil")
    # Imzalanan govde ile GONDERILEN govde birebir AYNI bayt dizisi olmali --
    # ikisi ayrı ayrı serialize edilirse (ör. requests'in kendi json= parametresi
    # kullanılırsa) araya giren whitespace/anahtar sırası farkı imzayı bozar.
    govde_json = json.dumps(govde, separators=(",", ":"), ensure_ascii=False)
    basliklar = {
        "Authorization": yetkilendirme_basligi(uri_path, govde_json),
        "Content-Type": "application/json",
    }
    yanit = requests.post(IYZICO_BASE_URL + uri_path, data=govde_json.encode("utf-8"),
                          headers=basliklar, timeout=15)
    yanit.raise_for_status()
    return yanit.json()


def checkout_baslat(*, conversation_id: str, price: float, callback_url: str,
                    buyer: dict, billing_address: dict, basket_items: list) -> dict:
    """CF-Initialize: ödeme sayfası oluşturur, {token, paymentPageUrl, ...} döner."""
    fiyat = f"{price:.2f}"
    govde = {
        "locale": "tr",
        "conversationId": conversation_id,
        "price": fiyat,
        "paidPrice": fiyat,
        "currency": "TRY",
        "basketId": conversation_id,
        "paymentGroup": "SUBSCRIPTION",
        "callbackUrl": callback_url,
        "buyer": buyer,
        "billingAddress": billing_address,
        "basketItems": basket_items,
    }
    return _istek("/payment/iyzipos/checkoutform/initialize/auth/ecom", govde)


def checkout_dogrula(token: str) -> dict:
    """CF-Retrieve: callback'te gelen token'ı sunucu tarafında doğrular.

    ASLA tarayıcıdan gelen "ödeme başarılı" bilgisine güvenilmiyor -- bu
    çağrı Iyzico'nun kendi sunucusuna sorup GERÇEK durumu alıyor.
    """
    return _istek("/payment/iyzipos/checkoutform/auth/ecom/detail",
                  {"locale": "tr", "token": token})
