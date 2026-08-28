"""Abonelik durumu — kilit yanlış çalışırsa ya müşteri haksız kilitlenir
ya da ödemeyen müşteri kullanmaya devam eder."""
import api


def abonelik(db, org_id, **alanlar):
    varsayilan = {"status": "active", "valid_until": "now() + INTERVAL '30 days'"}
    varsayilan.update(alanlar)
    db.execute(f"""INSERT INTO subscriptions (organization_id, status, valid_until)
                   VALUES (%s, %s, {varsayilan['valid_until']})""",
               (org_id, varsayilan["status"]))


def test_gecerli_abonelik_aktif(db, org):
    abonelik(db, org["org_id"])
    d = api.subscription_state(org["org_id"], db)
    assert d["status"] == "active" and d["active"] is True


def test_suresi_dolmus_kilitler(db, org):
    abonelik(db, org["org_id"], valid_until="now() - INTERVAL '1 day'")
    d = api.subscription_state(org["org_id"], db)
    assert d["status"] == "expired" and d["active"] is False


def test_deneme_suresi_aktif_sayilir(db, org):
    abonelik(db, org["org_id"], status="trial")
    d = api.subscription_state(org["org_id"], db)
    assert d["status"] == "trial" and d["active"] is True


def test_iptal_suresi_dolmamis_olsa_bile_kapali(db, org):
    """İptal, kalan süreye bakılmaksızın erişimi kapatmalı."""
    abonelik(db, org["org_id"], status="cancelled", valid_until="now() + INTERVAL '300 days'")
    d = api.subscription_state(org["org_id"], db)
    assert d["status"] == "cancelled" and d["active"] is False


def test_aboneligi_hic_olmayan_organizasyon(db, org):
    d = api.subscription_state(org["org_id"], db)
    assert d["status"] == "none" and d["active"] is False


def test_bitise_yaklasinca_uyari_bayragi(db, org):
    abonelik(db, org["org_id"], valid_until="now() + INTERVAL '5 days'")
    assert api.subscription_state(org["org_id"], db)["warn"] is True


def test_suresi_bolca_olan_uyarmaz(db, org):
    abonelik(db, org["org_id"], valid_until="now() + INTERVAL '200 days'")
    assert api.subscription_state(org["org_id"], db)["warn"] is False


def test_gecmis_tarih_veritabaninda_active_yazsa_bile_kilitler(db, org):
    """'expired' saklanmıyor, valid_until'den hesaplanıyor. Zamanlanmış bir iş
    çalışmazsa bile süresi geçmiş abonelik açık kalmamalı."""
    abonelik(db, org["org_id"], status="active", valid_until="now() - INTERVAL '400 days'")
    assert api.subscription_state(org["org_id"], db)["active"] is False
