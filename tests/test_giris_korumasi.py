"""MQTT girişinde kayıtlı-cihaz koruması.

Bu koruma olmadan "cihazı sil" gerçek bir silme olamaz: cihaz hâlâ enerjiliyse
silindikten saniyeler sonra aynı satırları yeniden yazmaya başlar, kullanıcı da
silmenin çalışmadığını görür. İkinci faydası güvenlik tarafında -- broker
kimlik bilgisi tüm cihazlarda ortak olduğu için, kayıtlı olmayan bir device_id
ile yayın yapan herhangi bir cihaz veritabanına sınırsız yazabiliyordu.
"""
import pytest

import api
from conftest import sahte_db_connect


@pytest.fixture(autouse=True)
def temiz_onbellek():
    """Her test kendi önbelleğiyle başlasın: bu durum modül düzeyinde ve
    kalıcı, testler birbirinin kaydını görmemeli."""
    api._kayitli_cihazlar.clear()
    api._bilinmeyen_cihaz_son_kontrol.clear()
    yield
    api._kayitli_cihazlar.clear()
    api._bilinmeyen_cihaz_son_kontrol.clear()


def test_kayitli_cihaz_kabul_edilir(db, monkeypatch):
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('k1', 'x', 'k1@test.local', true)")
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('var-olan', 'Pano', 'k1')")
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))

    assert api.kayitli_cihaz_mi("var-olan") is True


def test_kayitsiz_cihaz_reddedilir(db, monkeypatch):
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    assert api.kayitli_cihaz_mi("hic-yok") is False


def test_kayitsiz_cihaz_her_mesajda_sorgu_actirmaz(db, monkeypatch):
    """Yayında kalan silinmiş bir cihaz saniyede bir sorgu açmamalı.

    Negatif önbellek olmasaydı, silinen ama hâlâ enerjili bir cihaz
    veritabanına sürekli yük bindirirdi -- silmenin cezası sunucuya kesilirdi.
    """
    sorgu_sayisi = {"n": 0}

    def sayan_baglanti():
        sorgu_sayisi["n"] += 1
        return sahte_db_connect(db)()

    monkeypatch.setattr(api, "db_connect", sayan_baglanti)

    for _ in range(5):
        assert api.kayitli_cihaz_mi("hic-yok") is False

    assert sorgu_sayisi["n"] == 1, f"5 mesaj için {sorgu_sayisi['n']} sorgu açıldı"


def test_kayitli_cihaz_da_tek_sorguda_onbellege_giriyor(db, monkeypatch):
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('k2', 'x', 'k2@test.local', true)")
    db.execute("INSERT INTO devices (device_id, name, owner_username) "
               "VALUES ('hizli', 'Pano', 'k2')")

    sorgu_sayisi = {"n": 0}

    def sayan_baglanti():
        sorgu_sayisi["n"] += 1
        return sahte_db_connect(db)()

    monkeypatch.setattr(api, "db_connect", sayan_baglanti)

    for _ in range(10):
        assert api.kayitli_cihaz_mi("hizli") is True

    assert sorgu_sayisi["n"] == 1


def test_veritabani_erisilemezse_veri_kabul_edilir(monkeypatch):
    """Emniyet yönü bilinçli: geçici bir arıza yüzünden gerçek ölçüm
    kaybetmek, birkaç fazla satırdan çok daha kötü."""
    def patlayan():
        raise RuntimeError("bağlantı yok")

    monkeypatch.setattr(api, "db_connect", patlayan)

    assert api.kayitli_cihaz_mi("bilinmeyen") is True


def test_silinen_cihaz_onbellekten_dusuyor():
    """Silme anında önbellek temizlenmezse, silinen cihaz pozitif önbellekte
    kalır ve verisi yazılmaya devam ederdi -- silme görünürde çalışmazdı."""
    api._kayitli_cihazlar.add("silinen")

    api.kayitli_cihaz_unut("silinen")

    assert "silinen" not in api._kayitli_cihazlar


def test_yeniden_eklenen_cihaz_beklemiyor():
    """Silinip tekrar eklenen cihazın verisi negatif önbellek süresi kadar
    beklememeli; ekleme önbelleği doğrudan güncelliyor."""
    api._bilinmeyen_cihaz_son_kontrol["geri-gelen"] = 9e9  # uzak gelecek

    api.kayitli_cihaz_ekle("geri-gelen")

    assert api.kayitli_cihaz_mi("geri-gelen") is True
    assert "geri-gelen" not in api._bilinmeyen_cihaz_son_kontrol
