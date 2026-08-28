"""Erişim kapsamı — bir müşterinin başkasının cihazını görmesi en ağır hata.

Bu kural sistemde tek bir SQL parçasında (_ACCESSIBLE_DEVICES_SQL) tanımlı ve
alarm e-postası, push, aylık rapor ve panel hepsi onu kullanıyor; dolayısıyla
buradaki bir regresyon aynı anda dört yerden sızdırır.
"""
from conftest import uye_ekle


def cihazlar(db, username):
    import api
    db.execute("SELECT device_id FROM (" + api._ACCESSIBLE_DEVICES_SQL + ") AS a ORDER BY device_id",
               (username,))
    return [r[0] for r in db.fetchall()]


def test_organizasyon_yoneticisi_hepsini_gorur(db, org):
    uye_ekle(db, org["org_id"], "patron", "org_admin")
    assert cihazlar(db, "patron") == ["cihaz-a", "cihaz-b", "cihaz-c"]


def test_tesis_yoneticisi_yalnizca_kendi_tesisini(db, org):
    uye_ekle(db, org["org_id"], "merkez_mudur", "facility_manager", tesisler=[org["merkez"]])
    assert cihazlar(db, "merkez_mudur") == ["cihaz-a", "cihaz-b"]   # Tesis B YOK


def test_bolum_yoneticisi_yalnizca_kendi_bolumunu(db, org):
    uye_ekle(db, org["org_id"], "pres_sef", "department_manager", bolumler=[org["pres"]])
    assert cihazlar(db, "pres_sef") == ["cihaz-c"]


def test_kapsamsiz_tesis_yoneticisi_hicbir_sey_gormez(db, org):
    # Rolü var ama hiçbir tesise atanmamış -> boş dönmeli, hepsini DEĞİL
    uye_ekle(db, org["org_id"], "atanmamis", "facility_manager")
    assert cihazlar(db, "atanmamis") == []


def test_baska_organizasyon_gormez(db, org):
    """En kritik durum: farklı müşteriler birbirini görmemeli."""
    db.execute("INSERT INTO organizations (name) VALUES ('Yabanci Org') RETURNING id")
    yabanci_org = db.fetchone()[0]
    uye_ekle(db, yabanci_org, "yabanci", "org_admin")
    assert cihazlar(db, "yabanci") == []


def test_uyeligi_olmayan_kullanici_hicbir_sey_gormez(db, org):
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('bagimsiz','x','bagimsiz@test.local',true)")
    assert cihazlar(db, "bagimsiz") == []


def test_bildirim_alicilari_ayni_kapsami_kullanir(db, org):
    """users_with_device_access, panelle aynı sonucu vermeli.

    Bu ikisi ayrışırsa alarm yanlış kişilere gider veya doğru kişilere gitmez.
    """
    import api
    uye_ekle(db, org["org_id"], "merkez_mudur", "facility_manager", tesisler=[org["merkez"]])
    uye_ekle(db, org["org_id"], "pres_sef", "department_manager", bolumler=[org["pres"]])
    uye_ekle(db, org["org_id"], "patron", "org_admin")

    assert sorted(api.users_with_device_access("cihaz-a", db)) == ["merkez_mudur", "patron"]
    assert sorted(api.users_with_device_access("cihaz-c", db)) == ["patron", "pres_sef"]


def test_cift_uyelikli_kullanici_tekrar_etmez(db, org):
    """Aynı kişi listede iki kez çıkarsa alarmı iki kez alır."""
    import api
    uye_ekle(db, org["org_id"], "patron", "org_admin")
    db.execute("INSERT INTO organizations (name) VALUES ('Ikinci Org') RETURNING id")
    ikinci = db.fetchone()[0]
    db.execute("INSERT INTO org_members (organization_id, username, role) VALUES (%s,'patron','org_admin')",
               (ikinci,))
    alicilar = api.users_with_device_access("cihaz-a", db)
    assert alicilar == ["patron"]
    assert len(alicilar) == len(set(alicilar))
