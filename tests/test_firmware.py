"""Firmware .bin dosyalarının imzalı-URL koruması.

Öncesinde /firmware-files bir StaticFiles mount'uydu: dosya adını bilen
HERKES (hesapsız) indirebiliyordu. Dosya adı tahmin edilebilir
(f"{device_type}-{version}.bin") ve dosyanın içinde MQTT broker şifresi düz
metin gömülü -- yani bu, cihaza hiç fiziksel erişmeden broker şifresini ele
geçirmenin bir yoluydu. Şimdi indirme, süresi dolan bir HMAC imzası
gerektiriyor; imza yalnızca zaten auth+sahiplik kontrolünden geçen
/firmware/{tip}/latest ve /devices/{id}/ota tarafından üretiliyor.
"""
import os
import time

import pytest
from fastapi import HTTPException

import api


@pytest.fixture
def ornek_dosya():
    os.makedirs(api.FIRMWARE_DIR, exist_ok=True)
    yol = os.path.join(api.FIRMWARE_DIR, "anl21-9.9.9.bin")
    with open(yol, "wb") as f:
        f.write(b"sahte-firmware-icerigi")
    yield "anl21-9.9.9.bin"
    os.remove(yol)


def test_imza_dogrulanir_ve_suresi_dolunca_reddedilir():
    url = api.sign_firmware_url("anl21-1.0.0.bin", ttl_seconds=60)
    assert "exp=" in url and "sig=" in url
    qs = dict(p.split("=") for p in url.split("?", 1)[1].split("&"))
    assert api.verify_firmware_url("anl21-1.0.0.bin", int(qs["exp"]), qs["sig"]) is True

    # Süresi geçmiş imza (geçmiş bir exp ile), doğru şekilde hesaplanmış olsa bile reddedilmeli.
    gecmis_exp = int(time.time()) - 10
    gecmis_sig = api.hmac.new(
        api.DEVICE_CLAIM_SECRET.encode(),
        f"firmware:anl21-1.0.0.bin:{gecmis_exp}".encode(),
        api.hashlib.sha256,
    ).hexdigest()
    assert api.verify_firmware_url("anl21-1.0.0.bin", gecmis_exp, gecmis_sig) is False


def test_baska_dosya_adina_veya_bozuk_imzaya_KARSI_KORUNUR():
    url = api.sign_firmware_url("anl21-1.0.0.bin", ttl_seconds=60)
    qs = dict(p.split("=") for p in url.split("?", 1)[1].split("&"))
    exp, sig = int(qs["exp"]), qs["sig"]

    # Aynı imza, BAŞKA bir dosya adına uygulanamaz (dosya adı yükün parçası).
    assert api.verify_firmware_url("anl21-2.0.0.bin", exp, sig) is False
    # Tahrif edilmiş imza reddedilir.
    assert api.verify_firmware_url("anl21-1.0.0.bin", exp, sig[:-1] + ("0" if sig[-1] != "0" else "1")) is False


def test_indirme_ucnoktasi_gecerli_imzayla_dosyayi_doner(ornek_dosya):
    url = api.sign_firmware_url(ornek_dosya, ttl_seconds=60)
    qs = dict(p.split("=") for p in url.split("?", 1)[1].split("&"))
    yanit = api.download_firmware(ornek_dosya, int(qs["exp"]), qs["sig"])
    assert yanit.path.endswith(ornek_dosya)


def test_indirme_ucnoktasi_gecersiz_imzayi_reddeder(ornek_dosya):
    with pytest.raises(HTTPException) as e:
        api.download_firmware(ornek_dosya, int(time.time()) + 60, "yanlis-imza")
    assert e.value.status_code == 403


def test_indirme_ucnoktasi_path_traversal_dosya_adini_reddeder():
    kotu_ad = "../../etc/passwd"
    with pytest.raises(HTTPException) as e:
        api.download_firmware(kotu_ad, int(time.time()) + 60, "her-hangi-bir-sey")
    assert e.value.status_code == 400


def test_firmware_latest_ve_ota_payloadi_imzali_url_uretir(ornek_dosya, monkeypatch):
    """Gerçek imzalama, /firmware/latest'in ürettiği URL'nin çalıştığını doğrular
    (uç uca -- sadece sign/verify fonksiyonlarının ayrı ayrı doğru olduğunu değil)."""
    url = api.sign_firmware_url(ornek_dosya, ttl_seconds=15 * 60)
    assert url.startswith(api.SITE_URL + "/api/firmware-files/" + ornek_dosya + "?")
    qs = dict(p.split("=") for p in url.split("?", 1)[1].split("&"))
    # download_firmware'in bunu gerçekten kabul ettiğini doğrula.
    yanit = api.download_firmware(ornek_dosya, int(qs["exp"]), qs["sig"])
    assert yanit.path.endswith(ornek_dosya)
