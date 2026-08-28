"""Denetim kaydı ve KVKK hakları.

Hesap silme, veri kaybettirebilecek tek uç nokta: müşterinin cihaz kayıtlarını
ve ölçüm geçmişini öksüz bırakmamalı. Buradaki testler tam olarak onu koruyor.
"""
import json
import psycopg2
import pytest
from fastapi import HTTPException

import api
from conftest import uye_ekle


@pytest.fixture
def kalici_org():
    """delete_my_account kendi bağlantısını açıp commit ettiği için bu testler
    fixture'ın geri alınan işlemini kullanamıyor; kendi verisini kurup
    sonunda temizliyor."""
    conn = psycopg2.connect(**api.DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("INSERT INTO organizations (name) VALUES ('Silme Testi') RETURNING id")
    org_id = cur.fetchone()[0]
    cur.execute("INSERT INTO facilities (organization_id, name) VALUES (%s,'Merkez') RETURNING id", (org_id,))
    tesis = cur.fetchone()[0]
    sifre = api.bcrypt.hashpw(b"parola123", api.bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('silinecek', %s, 'silinecek@test.local', true)", (sifre,))
    cur.execute("INSERT INTO org_members (organization_id, username, role) VALUES (%s,'silinecek','org_admin')",
                (org_id,))
    cur.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
                "VALUES ('silme-cihaz','Cihaz','silinecek',%s)", (tesis,))
    yield {"org_id": org_id, "tesis": tesis, "cur": cur}
    for sql, p in (("DELETE FROM devices WHERE device_id='silme-cihaz'", ()),
                   ("DELETE FROM audit_log WHERE organization_id=%s", (org_id,)),
                   ("DELETE FROM org_members WHERE organization_id=%s", (org_id,)),
                   ("DELETE FROM users WHERE username IN ('silinecek','devralan')", ()),
                   ("DELETE FROM facilities WHERE organization_id=%s", (org_id,)),
                   ("DELETE FROM organizations WHERE id=%s", (org_id,))):
        try:
            cur.execute(sql, p)
        except Exception:
            pass
    cur.close(); conn.close()


# ---------- Denetim kaydı ----------

def test_denetim_kaydi_yazilir(db, org):
    uye_ekle(db, org["org_id"], "patron", "org_admin")
    api.audit("device.add", actor="patron", organization_id=org["org_id"],
              entity_type="device", entity_id="cihaz-a", detail={"ad": "Test"}, cur=db)
    db.execute("SELECT action, actor, entity_id, detail FROM audit_log WHERE actor='patron'")
    r = db.fetchone()
    assert r[0] == "device.add" and r[2] == "cihaz-a" and r[3] == {"ad": "Test"}


def test_denetim_kaydi_organizasyona_gore_ayrilir(db, org):
    """Bir müşteri başka müşterinin denetim kaydını görmemeli."""
    db.execute("INSERT INTO organizations (name) VALUES ('Yabanci') RETURNING id")
    yabanci = db.fetchone()[0]
    api.audit("device.add", actor="ben", organization_id=org["org_id"], entity_id="benim", cur=db)
    api.audit("device.add", actor="o", organization_id=yabanci, entity_id="onun", cur=db)
    db.execute("SELECT entity_id FROM audit_log WHERE organization_id = %s", (org["org_id"],))
    assert [r[0] for r in db.fetchall()] == ["benim"]


def test_denetim_yazimi_asil_islemi_dusurmez(db):
    """Denetim kaydı tutulamadı diye müşterinin işlemi başarısız olamaz."""
    class BozukCursor:
        def execute(self, *a, **k):
            raise RuntimeError("kasten bozuk")
    api.audit("device.add", actor="x", cur=BozukCursor())   # exception FIRLATMAMALI


# ---------- KVKK: dışa aktarma ----------

def test_disa_aktarma_sifre_ozetini_icermez(db, org):
    """Kişisel veri dışa aktarımı, kimlik doğrulama sırrı sızdırmamalı."""
    uye_ekle(db, org["org_id"], "patron", "org_admin")
    db.connection.commit()
    try:
        r = api.export_my_data(user="patron")
        govde = r.body.decode()
        assert "password" not in govde.lower()
        assert "hash" not in govde.lower()
        v = json.loads(govde)
        assert v["hesap"]["kullanici_adi"] == "patron"
        assert "organizasyon_uyelikleri" in v
    finally:
        db.execute("DELETE FROM org_members WHERE username='patron'")
        db.execute("DELETE FROM users WHERE username='patron'")
        db.connection.commit()


# ---------- KVKK: hesap silme ----------

def test_devredilecek_yonetici_yoksa_silme_reddedilir(kalici_org):
    """Cihazları öksüz bırakmaktansa silmeyi reddet."""
    with pytest.raises(HTTPException) as e:
        api.delete_my_account(
            api.DeleteAccountRequest(password="parola123", confirm="silinecek"),
            user="silinecek")
    assert e.value.status_code == 409
    kalici_org["cur"].execute("SELECT count(*) FROM users WHERE username='silinecek'")
    assert kalici_org["cur"].fetchone()[0] == 1     # hesap SILINMEDI


def test_silmede_cihaz_sahipligi_devredilir(kalici_org):
    cur = kalici_org["cur"]
    sifre = api.bcrypt.hashpw(b"x", api.bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('devralan', %s, 'devralan@test.local', true)", (sifre,))
    cur.execute("INSERT INTO org_members (organization_id, username, role) "
                "VALUES (%s,'devralan','org_admin')", (kalici_org["org_id"],))

    api.delete_my_account(
        api.DeleteAccountRequest(password="parola123", confirm="silinecek"), user="silinecek")

    cur.execute("SELECT count(*) FROM users WHERE username='silinecek'")
    assert cur.fetchone()[0] == 0                       # hesap silindi
    cur.execute("SELECT owner_username FROM devices WHERE device_id='silme-cihaz'")
    assert cur.fetchone()[0] == "devralan"              # cihaz KAYBOLMADI


def test_yanlis_onay_ve_sifre_reddedilir(kalici_org):
    for sifre, onay, kod in (("parola123", "yanlis-ad", 400), ("yanlis", "silinecek", 403)):
        with pytest.raises(HTTPException) as e:
            api.delete_my_account(
                api.DeleteAccountRequest(password=sifre, confirm=onay), user="silinecek")
        assert e.value.status_code == kod


def test_silmede_denetim_izi_anonimlesir_ama_kalir(kalici_org):
    """İz silinirse 'ne oldu' sorusu cevapsız kalır; kalırsa KVKK sorunu olur.
    Çözüm: kayıt kalır, kişiyle ilişkisi kesilir."""
    cur = kalici_org["cur"]
    api.audit("device.add", actor="silinecek", organization_id=kalici_org["org_id"],
              entity_id="silme-cihaz")
    sifre = api.bcrypt.hashpw(b"x", api.bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES ('devralan', %s, 'devralan@test.local', true)", (sifre,))
    cur.execute("INSERT INTO org_members (organization_id, username, role) "
                "VALUES (%s,'devralan','org_admin')", (kalici_org["org_id"],))

    api.delete_my_account(
        api.DeleteAccountRequest(password="parola123", confirm="silinecek"), user="silinecek")

    cur.execute("SELECT count(*) FROM audit_log WHERE actor='silinecek'")
    assert cur.fetchone()[0] == 0                          # kullanıcı adı kalmadı
    cur.execute("SELECT count(*) FROM audit_log WHERE organization_id=%s AND actor LIKE 'silinmiş%%'",
                (kalici_org["org_id"],))
    assert cur.fetchone()[0] >= 1                          # ama kayıt duruyor
