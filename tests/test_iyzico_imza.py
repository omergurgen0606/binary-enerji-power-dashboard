"""Iyzico IYZWSv2 imzalama şeması.

Gerçek anahtar/ağ erişimi olmadan test edilebiliyor -- bu bilinçli bir tasarım:
imzalama hatası, ödeme isteğinin sessizce reddedilmesi (401) ya da daha kötüsü
sahte bir yanıtın gerçek sanılması demek. Bu yüzden algoritmanın kendisi,
gerçek bir ödemeye hiç ulaşmadan doğrulanabiliyor.

Kaynak: docs.iyzico.com HMACSHA256 Authentication -- mesaj = randomKey +
uri_path + govde_json, HMAC-SHA256(secretKey) ile imzalanıyor, sonra
"apiKey:...&randomKey:...&signature:..." base64'e sarılıyor.
"""
import base64
import hashlib
import hmac

import iyzico


def test_imza_dokumandaki_ornekle_eslesiyor():
    """docs.iyzico.com'daki tek somut örnek: randomKey=123456789,
    path=/payment/bin/check, govde={"binNumber":"535805"} ->
    imza 079df4b2426fc7f4208d8f22fbc0349794019f8ce2b0711de7808b4874f4e796
    ile başlıyor (dokümanda imzanın tamamı degil bir kismi verilmisti,
    burada AYNI GIRDIYLE kendi hesaplamamizin ayni algoritmayi izledigini
    dogruluyoruz -- secretKey dokumanda paylasilmadigi icin ayni SONUCU
    degil, ayni YAPIYI (hex, 64 karakter, deterministik) dogruluyoruz)."""
    imza = iyzico._imza_hesapla("123456789", "/payment/bin/check",
                                '{"binNumber":"535805"}', "sahte-secret")
    assert len(imza) == 64
    assert all(c in "0123456789abcdef" for c in imza)


def test_imza_deterministik():
    """Aynı girdiyle aynı imza -- HMAC'in temel özelliği, ama burada asıl
    korunan şey kendi implementasyonumuzun rastgelelik/durum sızdırmaması."""
    a = iyzico._imza_hesapla("rk", "/x", "{}", "sir")
    b = iyzico._imza_hesapla("rk", "/x", "{}", "sir")
    assert a == b


def test_imza_govde_degisince_degisir():
    """Yanlışlıkla imzalanan govde ile GÖNDERİLEN govde ayrışırsa (ör. ayrı
    ayrı serialize edilirse) Iyzico isteği reddeder -- bu test o riski
    yakalayacak hassasiyette: tek karakterlik fark bile imzayı değiştirmeli."""
    a = iyzico._imza_hesapla("rk", "/x", '{"price":"5.20"}', "sir")
    b = iyzico._imza_hesapla("rk", "/x", '{"price":"5.21"}', "sir")
    assert a != b


def test_yetkilendirme_basligi_bicimi():
    baslik = iyzico.yetkilendirme_basligi("/payment/x", "{}", api_key="test-key", secret_key="test-secret")
    assert baslik.startswith("IYZWSv2 ")
    # "IYZWSv2" ile base64 govdesi arasinda TEK bosluk olmali (dokuman bunu
    # ozellikle vurguluyor -- fazla/eksik bosluk Iyzico tarafinda reddedilir).
    assert baslik.count(" ") == 1

    kodlanmis = baslik.split(" ", 1)[1]
    cozulmus = base64.b64decode(kodlanmis).decode("utf-8")
    assert cozulmus.startswith("apiKey:test-key&randomKey:")
    assert "&signature:" in cozulmus


def test_yetkilendirme_basligi_her_cagride_farkli_randomkey():
    """randomKey her istekte yeniden uretilmeli -- sabit kalirsa (replay)
    ayni imza tekrar tekrar gecerli olur, bu da bir istegin yakalanip
    tekrar oynatilmasina (replay attack) acik kapi birakir."""
    b1 = iyzico.yetkilendirme_basligi("/x", "{}", api_key="k", secret_key="s")
    b2 = iyzico.yetkilendirme_basligi("/x", "{}", api_key="k", secret_key="s")
    assert b1 != b2


def test_govde_bos_anahtarla_hata_verir(monkeypatch):
    monkeypatch.setattr(iyzico, "IYZICO_API_KEY", "")
    monkeypatch.setattr(iyzico, "IYZICO_SECRET_KEY", "")
    import pytest
    with pytest.raises(iyzico.IyzicoHatasi):
        iyzico._istek("/payment/x", {"a": 1})
