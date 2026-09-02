"""Cihazı tümüyle silme.

Silme, yarım yapıldığında en tehlikeli işlemdir: kullanıcı verisinin gittiğini
sanar, veri ise veritabanında durmaya devam eder. Buradaki testler iki şeyi
koruyor -- silmenin GERÇEKTEN her tabloyu kapsaması, ve silinen cihazın
verisinin geri gelmemesi.

Uç nokta fonksiyonları doğrudan çağrılıyor; TestClient httpx gerektiriyor ve
üretim imajına yalnızca test için bağımlılık eklemek istemedik.
"""
import bcrypt
import pytest
from fastapi import HTTPException

import api
from conftest import sahte_db_connect


# Silme kapsamı dışında kalması DOĞRU olan, device_id taşıyan tablolar.
# Bilinçli bir karar olarak burada duruyorlar; listede olmamaları unutkanlık
# değil. (devices'ın kendisi, tüm veri tabloları boşaldıktan sonra en sonda
# siliniyor.)
KAPSAM_DISI = {"devices"}


def test_liste_semayla_ortusuyor(db):
    """Şemadaki her device_id tablosu silme listesinde olmalı.

    Bu testin asıl işi geleceği korumak: yeni bir ölçüm tablosu eklenip
    CIHAZ_VERI_TABLOLARI güncellenmezse, silme o tabloyu atlar ve kimse fark
    etmez. O sessiz yarım-silme yerine bu test kırılır.
    """
    db.execute("""
        SELECT c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_name = c.table_name AND t.table_schema = c.table_schema
        WHERE c.column_name = 'device_id'
          AND c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
    """)
    semadaki = {r[0] for r in db.fetchall()} - KAPSAM_DISI
    listedeki = set(api.CIHAZ_VERI_TABLOLARI)

    eksik = semadaki - listedeki
    assert not eksik, (
        f"Bu tablolar device_id taşıyor ama silme listesinde yok: {sorted(eksik)}. "
        f"api.CIHAZ_VERI_TABLOLARI'na eklenmeli, yoksa cihaz silindiğinde verisi kalır."
    )

    fazla = listedeki - semadaki
    assert not fazla, f"Silme listesinde şemada olmayan tablo var: {sorted(fazla)}"


def test_alarm_tablolari_listede():
    """alarm_rules devices'tan CASCADE alıyor ama listede de olmalı.

    CASCADE yalnızca devices satırı silinirken çalışır. Liste, silme sırası
    değişse bile kuralın gitmesini garanti eder; ayrıca denetim kaydına yazılan
    satır sayımına da girer -- "kaç alarm kuralıyla birlikte silindi" sorusu
    sonradan cevaplanabilsin.
    """
    assert "alarm_rules" in api.CIHAZ_VERI_TABLOLARI
    assert "alarm_events" in api.CIHAZ_VERI_TABLOLARI


def test_surekli_toplamalar_atlanmiyor():
    """Ham satırı silmek sürekli toplamaları güncellemez -- yenileme şart."""
    assert set(api.CIHAZ_SUREKLI_TOPLAMALAR) == {
        "measurements_10min", "measurements_15min", "device_energy_hourly"
    }


# --------------------------------------------------------------------------
# Yetki ve onay
# --------------------------------------------------------------------------

class _SahteThread:
    """Sürekli toplam yenilemesi testte gerçekten çalışmasın.

    Yenileme kendi bağlantısını açıyor ve bu testin geri alınacak işlemini
    göremez; çalıştırılsa var olmayan bir aralığı boşuna yenilerdi.
    """
    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


@pytest.fixture
def sahip(db, monkeypatch):
    """Şifresi bilinen bir sahip + tek cihaz."""
    hash_ = bcrypt.hashpw(b"dogru-sifre", bcrypt.gensalt()).decode()
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('silen', %s, 'silen@test.local', true)", (hash_,))
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('silinecek', 'Pres Panosu', 'silen')")
    monkeypatch.setattr(api, "is_device_owner", lambda u, d: u == "silen")
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)
    monkeypatch.setattr(api, "check_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    monkeypatch.setattr(api.threading, "Thread", _SahteThread)
    return {"device_id": "silinecek", "name": "Pres Panosu"}


def _istek(sifre="dogru-sifre", onay="Pres Panosu"):
    return api.DeleteDeviceRequest(password=sifre, confirm=onay)


def test_yanlis_sifre_silmez(sahip, db):
    """Şifre şart: JWT 30 gün geçerli ve iptal edilemiyor, yani çalınan bir
    token tek başına aylarca birikmiş ölçüm geçmişini yok edememeli."""
    with pytest.raises(HTTPException) as e:
        api.delete_device("silinecek", _istek(sifre="yanlis"), user="silen")
    assert e.value.status_code == 403

    db.execute("SELECT count(*) FROM devices WHERE device_id = 'silinecek'")
    assert db.fetchone()[0] == 1, "şifre yanlışken cihaz silindi"


def test_yanlis_onay_metni_silmez(sahip, db):
    """Cihaz adını yazma adımı, yanlış cihazı silmeye karşı."""
    with pytest.raises(HTTPException) as e:
        api.delete_device("silinecek", _istek(onay="Baska Pano"), user="silen")
    assert e.value.status_code == 400

    db.execute("SELECT count(*) FROM devices WHERE device_id = 'silinecek'")
    assert db.fetchone()[0] == 1


def test_sahibi_olmayan_silemez(sahip, db):
    with pytest.raises(HTTPException) as e:
        api.delete_device("silinecek", _istek(), user="baskasi")
    assert e.value.status_code == 403

    db.execute("SELECT count(*) FROM devices WHERE device_id = 'silinecek'")
    assert db.fetchone()[0] == 1


def test_olmayan_cihaz_404(sahip):
    with pytest.raises(HTTPException) as e:
        api.delete_device("yok-boyle", _istek(), user="silen")
    assert e.value.status_code == 404


# --------------------------------------------------------------------------
# Silmenin kapsamı
# --------------------------------------------------------------------------

def test_silme_tum_tablolari_temizler(sahip, db):
    """Her tabloya birer satır koy, sil, hiçbirinin kalmadığını doğrula."""
    db.execute("INSERT INTO measurements (device_id, time, v1) VALUES ('silinecek', now(), 230)")
    db.execute("INSERT INTO device_energy (device_id, time, active_wh_tuketim) VALUES ('silinecek', now(), 100)")
    db.execute("INSERT INTO device_tariff (device_id) VALUES ('silinecek')")
    db.execute("INSERT INTO alarm_rules (device_id, metric, phase, condition, threshold) "
               "VALUES ('silinecek', 'voltage', 'any', 'gt', 250) RETURNING id")
    kural_id = db.fetchone()[0]
    db.execute("INSERT INTO alarm_events (rule_id, device_id, message) "
               "VALUES (%s, 'silinecek', 'test')", (kural_id,))

    sonuc = api.delete_device("silinecek", _istek(), user="silen")
    assert "silindi" in sonuc["message"]

    for tablo in api.CIHAZ_VERI_TABLOLARI:
        db.execute(f"SELECT count(*) FROM {tablo} WHERE device_id = 'silinecek'")
        assert db.fetchone()[0] == 0, f"{tablo} tablosunda satır kaldı"

    db.execute("SELECT count(*) FROM devices WHERE device_id = 'silinecek'")
    assert db.fetchone()[0] == 0


def test_baska_cihazin_verisi_korunur(sahip, db):
    """Silme WHERE device_id ile sınırlı olmalı -- en pahalı hata bu olurdu."""
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('kalacak', 'Diğer Pano', 'silen')")
    db.execute("INSERT INTO measurements (device_id, time, v1) VALUES ('kalacak', now(), 231)")
    db.execute("INSERT INTO measurements (device_id, time, v1) VALUES ('silinecek', now(), 230)")

    api.delete_device("silinecek", _istek(), user="silen")

    db.execute("SELECT count(*) FROM measurements WHERE device_id = 'kalacak'")
    assert db.fetchone()[0] == 1, "başka cihazın ölçümü silindi"
    db.execute("SELECT count(*) FROM devices WHERE device_id = 'kalacak'")
    assert db.fetchone()[0] == 1


def test_onizleme_sayilari_dogru(sahip, db):
    """Önizleme, kullanıcının onayladığı şeyin ta kendisi -- sayılar doğru olmalı."""
    db.execute("INSERT INTO measurements (device_id, time, v1) VALUES ('silinecek', now(), 230)")
    db.execute("INSERT INTO measurements (device_id, time, v1) VALUES ('silinecek', now(), 231)")
    db.execute("INSERT INTO device_energy (device_id, time, active_wh_tuketim) VALUES ('silinecek', now(), 5)")

    onizleme = api.delete_device_preview("silinecek", user="silen")

    assert onizleme["tablolar"]["measurements"] == 2
    assert onizleme["tablolar"]["device_energy"] == 1
    assert onizleme["toplam_satir"] == 3
    assert onizleme["son_veri"] is not None
