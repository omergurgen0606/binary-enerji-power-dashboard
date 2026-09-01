"""Tarifenin doğrulanıp doğrulanmadığı bayrağı.

Sistem şimdiye kadar ikiliydi: ya gerçek fiyat vardı ya hiç ₺ yoktu. Bu boşluk
gerçek bir hataya yol açtı -- geliştirme sırasında girilen uydurma rakamlar
panelde günlerce gerçek fatura tutarı gibi durdu ve kimse fark etmedi.

Bayrak, üçüncü bir durumu mümkün kılıyor: rakamlar var ama doğrulanmadı, ve
tutar gösteren her yer bunu açıkça söylüyor.
"""
import api


def _tarife_yaz(cur, device_id, **kw):
    alanlar = {
        "inductive_limit_pct": 20.0, "capacitive_limit_pct": 15.0,
        "reactive_price": 0.0, "active_price": 0.0, "billing_mode": "full",
        "t1_start": 6, "t2_start": 17, "t3_start": 22,
        "t1_price": 0.0, "t2_price": 0.0, "t3_price": 0.0,
        "contract_power_kw": None, "demand_price": 0.0,
        "tariff_verified": False, "tariff_source": None,
    }
    alanlar.update(kw)
    sutunlar = ", ".join(alanlar)
    yer = ", ".join(["%s"] * len(alanlar))
    cur.execute(
        f"INSERT INTO device_tariff (device_id, {sutunlar}) VALUES (%s, {yer})",
        (device_id, *alanlar.values()),
    )


def _cihaz(cur, device_id):
    cur.execute("INSERT INTO users (username, password_hash, email, is_verified) "
                "VALUES (%s, 'x', %s, true)", (device_id, f"{device_id}@example.com"))
    cur.execute("INSERT INTO devices (device_id, name, owner_username) "
                "VALUES (%s, %s, %s)", (device_id, device_id, device_id))


def test_varsayilan_dogrulanmamis(db):
    """Yeni bir tarife kanıt olmadan doğrulanmış sayılmamalı."""
    _cihaz(db, "tv-1")
    _tarife_yaz(db, "tv-1", t1_price=4.0)
    t = api._read_tariff("tv-1", db)
    assert t["tariff_verified"] is False


def test_dogrulanmis_bayrak_okunuyor(db):
    _cihaz(db, "tv-2")
    _tarife_yaz(db, "tv-2", t1_price=4.0, tariff_verified=True,
                tariff_source="Fatura, Ağustos 2026")
    t = api._read_tariff("tv-2", db)
    assert t["tariff_verified"] is True
    assert t["tariff_source"] == "Fatura, Ağustos 2026"


def test_kaynak_metni_korunuyor(db):
    """Bir sayıya bakıp nereden geldiğini bilememek, sayının kendisinden
    daha tehlikeli -- kaynak metni kaybolmamalı."""
    _cihaz(db, "tv-3")
    kaynak = "yaklaşık — EPDK genel üç zamanlı, Nisan 2026"
    _tarife_yaz(db, "tv-3", t1_price=4.38, tariff_source=kaynak)
    assert api._read_tariff("tv-3", db)["tariff_source"] == kaynak


def test_tarifesiz_cihaz_dogrulanmamis_sayilir(db):
    """Kaydı olmayan cihaz da doğrulanmış görünmemeli."""
    _cihaz(db, "tv-4")
    t = api._read_tariff("tv-4", db)
    assert t["configured"] is False
    assert t["tariff_verified"] is False
