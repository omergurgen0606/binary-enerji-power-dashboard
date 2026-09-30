"""GA1202 reaktif güç kontrol rölesi: parametre yazma doğrulaması, komutlar,
kategori görüntüleri.

Ağırlık bilerek YAZMA yolunda: okuma yanlışsa panelde yanlış sayı görünür,
ama yazma yanlışsa sahadaki bir kompanzasyon rölesinin ayarı bozulur ve
tesis reaktif ceza ödemeye başlar. Bu yüzden aralık dışı değerin, salt-okunur
alanın ve bilinmeyen anahtarın cihaza HİÇ ULAŞMADIĞI ayrı ayrı doğrulanıyor.
"""
import pytest
from fastapi import HTTPException

import api
from conftest import sahte_db_connect


@pytest.fixture
def role_cihazi(db, monkeypatch):
    """Bir röle (ga1202) ve ona erişebilen bir kullanıcı."""
    db.execute("INSERT INTO organizations (name) VALUES ('Röle Org') RETURNING id")
    org_id = db.fetchone()[0]
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('roleci', 'x', 'roleci@test.local', true)")
    db.execute("INSERT INTO org_members (organization_id, username, role) "
               "VALUES (%s, 'roleci', 'org_admin')", (org_id,))
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s, 'Merkez') RETURNING id",
               (org_id,))
    facility_id = db.fetchone()[0]
    db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
               "VALUES ('ga1202-aabbcc', 'Ana Kompanzasyon', 'roleci', %s)", (facility_id,))
    # Karşılaştırma için röle OLMAYAN bir cihaz da var.
    db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id) "
               "VALUES ('anl21-112233', 'Analizör', 'roleci', %s)", (facility_id,))
    monkeypatch.setattr(api, "db_connect", sahte_db_connect(db))
    return {"org_id": org_id, "device_id": "ga1202-aabbcc"}


@pytest.fixture
def gonderilen(monkeypatch):
    """publish_command'i yakalar -- gerçek cihaza hiçbir şey gitmesin."""
    kayit = []
    monkeypatch.setattr(api, "publish_command",
                        lambda device_id, register, value=1: kayit.append((device_id, register, value)))
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)
    return kayit


# ---------- Parametre yazma ----------

def test_gecerli_parametre_cihaza_gider(role_cihazi, gonderilen):
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="enduktif_limit", deger=12)
    api.relay_parametre_yaz(istek, user="roleci")
    assert gonderilen == [("ga1202-aabbcc", 357, 12)]


def test_aralik_disi_deger_cihaza_ULASMAZ(role_cihazi, gonderilen):
    # Endüktif Limit 1-50 arası; 99 geçersiz.
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="enduktif_limit", deger=99)
    with pytest.raises(HTTPException) as e:
        api.relay_parametre_yaz(istek, user="roleci")
    assert e.value.status_code == 400
    assert "1–50" in e.value.detail
    assert gonderilen == []


def test_salt_okunur_alan_yazilamaz(role_cihazi, gonderilen):
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="parametre_versiyonu", deger=3)
    with pytest.raises(HTTPException) as e:
        api.relay_parametre_yaz(istek, user="roleci")
    assert e.value.status_code == 400
    assert gonderilen == []


def test_bilinmeyen_parametre_reddedilir(role_cihazi, gonderilen):
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="uydurma_alan", deger=1)
    with pytest.raises(HTTPException) as e:
        api.relay_parametre_yaz(istek, user="roleci")
    assert e.value.status_code == 400
    assert gonderilen == []


def test_negatif_deger_ikiye_tumleyene_cevrilir(role_cihazi, gonderilen):
    """Ek Reaktif Güç L1 -5000 VAr: cihaz 16-bit işaretsiz register bekliyor."""
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="ek_reaktif_guc_l1", deger=-5000)
    api.relay_parametre_yaz(istek, user="roleci")
    assert gonderilen == [("ga1202-aabbcc", 370, 65536 - 5000)]


def test_role_olmayan_cihaza_role_parametresi_yazilamaz(role_cihazi, gonderilen):
    istek = api.RelayParamRequest(device_id="anl21-112233", anahtar="enduktif_limit", deger=12)
    with pytest.raises(HTTPException) as e:
        api.relay_parametre_yaz(istek, user="roleci")
    assert e.value.status_code == 400
    assert gonderilen == []


def test_baskasinin_cihazina_yazilamaz(role_cihazi, gonderilen, db):
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('yabanci', 'x', 'yabanci@test.local', true)")
    istek = api.RelayParamRequest(device_id="ga1202-aabbcc", anahtar="enduktif_limit", deger=12)
    with pytest.raises(HTTPException) as e:
        api.relay_parametre_yaz(istek, user="yabanci")
    assert e.value.status_code == 403
    assert gonderilen == []


# ---------- Komutlar ----------

def test_komut_dogru_register_ve_tetikle_gider(role_cihazi, gonderilen):
    istek = api.RelayKomutRequest(device_id="ga1202-aabbcc", komut="kademe_tanima_akilli")
    api.relay_komut(istek, user="roleci")
    assert gonderilen == [("ga1202-aabbcc", 9007, api.DEVICE_TRIGGER_VALUE)]


def test_bilinmeyen_komut_reddedilir(role_cihazi, gonderilen):
    istek = api.RelayKomutRequest(device_id="ga1202-aabbcc", komut="her_seyi_sil")
    with pytest.raises(HTTPException):
        api.relay_komut(istek, user="roleci")
    assert gonderilen == []


@pytest.fixture
def gercek_sifre(db, monkeypatch):
    """roleci'ye gerçek bir bcrypt hash'i ver; hız sınırı durumunu temiz başlat."""
    import bcrypt
    h = bcrypt.hashpw(b"dogru-sifre", bcrypt.gensalt(rounds=4)).decode()
    db.execute("UPDATE users SET password_hash = %s WHERE username = 'roleci'", (h,))
    monkeypatch.setattr(api, "_rate_limit_state", {})
    return "dogru-sifre"


@pytest.mark.parametrize("sifre", [None, "", "yanlis-sifre"])
def test_tehlikeli_komut_sifresiz_cihaza_ULASMAZ(role_cihazi, gonderilen, gercek_sifre, sifre):
    """Arayüzdeki "cihaz ID'sini yaz" onayı yalnızca istemcide; sızmış bir
    token'la API'ye doğrudan istek atan biri onu atlar. Sunucu şifre istemeli."""
    istek = api.RelayKomutRequest(device_id="ga1202-aabbcc", komut="fabrika_ayarlari", password=sifre)
    with pytest.raises(HTTPException) as e:
        api.relay_komut(istek, user="roleci")
    assert e.value.status_code == 403
    assert gonderilen == []


def test_tehlikeli_komut_dogru_sifreyle_gider(role_cihazi, gonderilen, gercek_sifre):
    istek = api.RelayKomutRequest(device_id="ga1202-aabbcc", komut="fabrika_ayarlari", password=gercek_sifre)
    api.relay_komut(istek, user="roleci")
    register = api.RELAY_KOMUTLARI["fabrika_ayarlari"][0]
    assert gonderilen == [("ga1202-aabbcc", register, api.DEVICE_TRIGGER_VALUE)]


def test_normal_komut_sifre_istemez(role_cihazi, gonderilen, gercek_sifre):
    istek = api.RelayKomutRequest(device_id="ga1202-aabbcc", komut="min_max_sil")
    api.relay_komut(istek, user="roleci")
    assert len(gonderilen) == 1


def test_tehlikeli_komut_sifre_denemesi_hiz_sinirli(role_cihazi, gonderilen, gercek_sifre):
    """Şifre bu uç noktadan tahmin edilemesin: saatte 5 deneme, sonra 429 --
    doğru şifre gelse bile."""
    for _ in range(5):
        with pytest.raises(HTTPException):
            api.relay_komut(api.RelayKomutRequest(
                device_id="ga1202-aabbcc", komut="cihaz_reset", password="yanlis"), user="roleci")
    with pytest.raises(HTTPException) as e:
        api.relay_komut(api.RelayKomutRequest(
            device_id="ga1202-aabbcc", komut="cihaz_reset", password=gercek_sifre), user="roleci")
    assert e.value.status_code == 429
    assert gonderilen == []


def test_hiz_siniri_iki_cihaz_tipinde_ortak(role_cihazi, gonderilen, gercek_sifre):
    """Analizör ve röle aynı şifre-deneme bütçesini paylaşmalı; yoksa her cihaz
    tipi saldırgana ayrı bir 5 denemelik hak verirdi."""
    for _ in range(5):
        with pytest.raises(HTTPException):
            api.yuksek_riskli_komut_sifresi_dogrula("roleci", "yanlis")
    with pytest.raises(HTTPException) as e:
        api.relay_komut(api.RelayKomutRequest(
            device_id="ga1202-aabbcc", komut="sifre_sifirla", password=gercek_sifre), user="roleci")
    assert e.value.status_code == 429


def test_tum_tehlikeli_komutlar_sunucuda_korunuyor(role_cihazi, gonderilen, gercek_sifre):
    """Tabloya ileride eklenecek her tehlikeli komut da otomatik korunmalı."""
    tehlikeliler = [k for k, v in api.RELAY_KOMUTLARI.items() if v[3]]
    assert tehlikeliler, "tehlikeli komut listesi boş olmamalı"
    for k in tehlikeliler:
        with pytest.raises(HTTPException) as e:
            api.relay_komut(api.RelayKomutRequest(device_id="ga1202-aabbcc", komut=k), user="roleci")
        assert e.value.status_code == 403
    assert gonderilen == []


def test_analizor_yuksek_riskli_komutu_da_ayni_korumada(role_cihazi, gonderilen, gercek_sifre):
    """Analizör uç noktası da ortak doğrulamayı kullanıyor -- şifresiz geçmez,
    doğru şifreyle gider, düşük riskli komut şifre istemez."""
    with pytest.raises(HTTPException) as e:
        api.send_device_command("anl21-112233", api.DeviceCommandRequest(command="factory_reset"), user="roleci")
    assert e.value.status_code == 403
    assert gonderilen == []

    api.send_device_command("anl21-112233",
                            api.DeviceCommandRequest(command="factory_reset", password=gercek_sifre), user="roleci")
    api.send_device_command("anl21-112233", api.DeviceCommandRequest(command="reset_demand"), user="roleci")
    assert [g[1] for g in gonderilen] == [api.DEVICE_COMMANDS["factory_reset"]["register"],
                                          api.DEVICE_COMMANDS["reset_demand"]["register"]]


def test_tehlikeli_komutlar_isaretli():
    """Panel bu bayrağa bakıp çift onay istiyor; bayrak düşerse onay da düşer."""
    for anahtar in ("fabrika_ayarlari", "cihaz_reset", "sifre_sifirla"):
        assert api.RELAY_KOMUTLARI[anahtar][3] is True
    assert api.RELAY_KOMUTLARI["min_max_sil"][3] is False


# ---------- Kategori görüntüleri ----------

def test_snapshot_okuma_yalnizca_erisimi_olana(role_cihazi, db, monkeypatch):
    monkeypatch.setattr(api, "audit", lambda *a, **k: None)
    db.execute("""INSERT INTO relay_snapshots (device_id, kategori, data)
                  VALUES ('ga1202-aabbcc', 'kademeler', '{"kademe_sayisi": 6}')""")
    sonuc = api.relay_snapshots(device_id="ga1202-aabbcc", user="roleci")
    assert sonuc["kademeler"]["data"]["kademe_sayisi"] == 6

    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('yabanci2', 'x', 'yabanci2@test.local', true)")
    with pytest.raises(HTTPException) as e:
        api.relay_snapshots(device_id="ga1202-aabbcc", user="yabanci2")
    assert e.value.status_code == 403


def test_tanimlar_panelin_ihtiyaci_olan_alanlari_verir():
    tanimlar = api.relay_tanimlar(user="roleci")
    assert tanimlar["parametreler"], "parametre listesi boş olmamalı"
    ornek = next(p for p in tanimlar["parametreler"] if p["anahtar"] == "asiri_sicaklik_degeri")
    assert ornek["etiket"] and ornek["birim"] == "°C"
    assert ornek["min"] == 40 and ornek["max"] == 90 and ornek["yazilabilir"] is True
    # Salt okunur alanlar da listede -- panel onları gösterip düzenlemeyi kapatıyor.
    assert any(p["yazilabilir"] is False for p in tanimlar["parametreler"])
    assert tanimlar["cihaz_durumlari"][3] == "Kompanzasyonda"


def test_role_topic_oneki_ayrisir():
    """Röleye 'powermeter/' önekiyle komut gitseydi cihaz duymazdı."""
    assert api.cmd_topic("ga1202-aabbcc") == "relay/ga1202-aabbcc/cmd"
    assert api.cmd_topic("anl21-112233") == "powermeter/anl21-112233/cmd"
