"""Analizörün geçersiz-ölçüm işaretlerinin (0xA0000000 vb.) ham sayı olarak
panele sızmaması.

Canlı sistemde ANL21'in Demand tablosunda "Görünür Güç" satırları
-1610612736 VA gösteriyordu: cihaz bu register'lar için gerçek değer yerine
0xA0000000 döndürüyor, firmware de onu ölçekleyip yayınlıyordu.
"""
import struct

import pytest

import api
from conftest import sahte_db_connect

A0 = -1610612736  # 0xA0000000, işaretli 32-bit


def f32(x):
    """Firmware alanları float; değer yayınlanmadan önce float32'ye yuvarlanıyor."""
    return struct.unpack("f", struct.pack("f", x))[0]


@pytest.mark.parametrize("deger", [
    float(A0),                 # ×1 (güç, VA)
    f32(A0 * 0.1),             # ×0.1 (gerilim, THD) -- float32 yuvarlamasıyla
    f32(A0 * 0.01),            # ×0.01 (frekans)
    f32(A0 * 0.001),           # ×0.001 (akım)
    round(f32(A0 * 0.1), 1),   # snprintf("%.1f") sonrası
    -2147483648.0,             # INT32_MIN
    f32(2147483647 * 0.1),     # INT32_MAX ×0.1
    float("nan"),
])
def test_gecersiz_isaretler_taninir(deger):
    assert api.gecersiz_olcum_mu(deger) is True


@pytest.mark.parametrize("deger", [
    229.4, -0.1, 0, 0.0, 18115.0, 162.242, -34635.0, 49.98, 35.8,
    1e7,         # 10 MW'lık bir tesisin gücü -- büyük ama geçerli
    None, "abc", True,
])
def test_gecerli_degerler_dokunulmaz(deger):
    assert api.gecersiz_olcum_mu(deger) is False


def test_temizleme_sirayi_ve_gecerlileri_korur():
    assert api.gecersizleri_temizle([230.1, float(A0), None, 5.4]) == [230.1, None, None, 5.4]


@pytest.fixture
def analizor(db, monkeypatch):
    db.execute("INSERT INTO organizations (name) VALUES ('Ölçüm Org') RETURNING id")
    org_id = db.fetchone()[0]
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('olcumcu', 'x', 'olcumcu@test.local', true)")
    db.execute("INSERT INTO org_members (organization_id, username, role) "
               "VALUES (%s, 'olcumcu', 'org_admin')", (org_id,))
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s, 'Merkez') RETURNING id",
               (org_id,))
    facility_id = db.fetchone()[0]
    db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
               "VALUES ('anl21-abcdef', 'Analizör', 'olcumcu', %s)", (facility_id,))
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    return "anl21-abcdef"


def test_demand_ucnoktasi_eski_bozuk_satiri_temizler(analizor, db):
    """Düzeltmeden ÖNCE yazılmış satırlar da temiz dönmeli -- panel son satırı gösteriyor."""
    db.execute("""
        INSERT INTO device_demand (device_id, direction, max_ds1, min_ds1, max_dp1, max_dv1)
        VALUES (%s, 'tuketim', %s, %s, 18115, 232.9)
    """, (analizor, float(A0), float(A0)))
    sonuc = api.get_demand(device_id=analizor, user="olcumcu")["tuketim"]
    assert sonuc["max_ds1"] is None and sonuc["min_ds1"] is None
    assert sonuc["max_dp1"] == 18115 and sonuc["max_dv1"] == pytest.approx(232.9)


def test_tepe_ucnoktasi_olcekli_isareti_temizler(analizor, db):
    db.execute("""
        INSERT INTO device_peaks (device_id, direction, max_vln1, min_vln1)
        VALUES (%s, 'tuketim', %s, 228.1)
    """, (analizor, f32(A0 * 0.1)))
    sonuc = api.get_peaks(device_id=analizor, user="olcumcu")["tuketim"]
    assert sonuc["max_vln1"] is None
    assert sonuc["min_vln1"] == pytest.approx(228.1)
