"""Güç kalitesi (EN 50160) değerlendirmesi.

İki hata sınıfı korunuyor:
  1. Cihazın kapalı olduğu aralıkları gerilim ihlali saymak — her fişten
     çekilişte "gerilim sıfıra düştü" raporu üretirdi.
  2. Ölçülmemiş bir parametreyi "uygun değil" göstermek — veri yokluğu
     başarısızlık değildir.
"""
import api


def hazirla(db, satirlar):
    """measurements_10min'i geçici tabloyla gölgeler.

    Geçici tablo arama yolunda kalıcı olanın önüne geçtiği için
    power_quality_report GERÇEK sorgusuyla bu veriyi okur.
    """
    db.execute("""
        CREATE TEMP TABLE measurements_10min (
            device_id TEXT, bucket TIMESTAMPTZ, sample_count INT,
            avg_v1 DOUBLE PRECISION, min_v1 DOUBLE PRECISION, max_v1 DOUBLE PRECISION,
            avg_v2 DOUBLE PRECISION, min_v2 DOUBLE PRECISION, max_v2 DOUBLE PRECISION,
            avg_v3 DOUBLE PRECISION, min_v3 DOUBLE PRECISION, max_v3 DOUBLE PRECISION,
            avg_f DOUBLE PRECISION, min_f DOUBLE PRECISION, max_f DOUBLE PRECISION,
            avg_thvd1 DOUBLE PRECISION, max_thvd1 DOUBLE PRECISION,
            avg_thvd2 DOUBLE PRECISION, max_thvd2 DOUBLE PRECISION,
            avg_thvd3 DOUBLE PRECISION, max_thvd3 DOUBLE PRECISION
        )
    """)
    for i, (v, f, thd) in enumerate(satirlar):
        db.execute("""
            INSERT INTO measurements_10min VALUES
            ('d', now() - (%s * INTERVAL '10 minutes'), 100,
             %s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s, %s,%s, %s,%s)
        """, (len(satirlar) - i, v, v, v, v, v, v, v, v, v, f, f, f,
              thd, thd, thd, thd, thd, thd))
    db.execute("INSERT INTO device_settings (device_id, nominal_voltage) VALUES ('d', 230) "
               "ON CONFLICT (device_id) DO UPDATE SET nominal_voltage = 230")


def param(rapor, anahtar):
    return next(p for p in rapor["parameters"] if p["key"] == anahtar)


def test_kapali_cihaz_araliklari_ihlal_sayilmaz(db):
    """150 geçerli ölçüm + 50 "cihaz kapalı" (0 V / 0 Hz).
    Kapalı aralıklar sayılsaydı gerilim uygunluğu %75'e düşerdi."""
    hazirla(db, [(230.0, 50.0, 2.0)] * 150 + [(0.0, 0.0, 0.0)] * 50)
    r = api.power_quality_report("d", 2, db)
    assert r["intervals"]["gecerli"] == 150
    assert r["intervals"]["olcum_yok"] == 50
    assert param(r, "voltage")["value_pct"] == 100.0
    assert param(r, "voltage")["pass"] is True


def test_gerilim_bandi_disi_yakalanir(db):
    # 90 ölçüm bandın içinde, 60'ı dışında -> %60, gereken %95
    hazirla(db, [(230.0, 50.0, 2.0)] * 90 + [(190.0, 50.0, 2.0)] * 60)
    r = api.power_quality_report("d", 2, db)
    assert param(r, "voltage")["pass"] is False
    assert r["verdict"] == "uygun_degil"


def test_olculmeyen_parametre_kaldi_degil_olculmedi(db):
    """THD verisi yoksa pass None olmalı, False değil."""
    hazirla(db, [(230.0, 50.0, None)] * 150)
    r = api.power_quality_report("d", 2, db)
    assert param(r, "thd")["pass"] is None
    assert param(r, "thd")["value_pct"] is None
    # Ölçülmeyen parametre genel kararı "uygun değil" yapmamalı
    assert r["verdict"] != "uygun_degil"


def test_yetersiz_veri_uygunluk_beyan_etmez(db):
    """EN 50160 kesintisiz bir hafta bekliyor. Elde 10 ölçüm varken
    'uygun' demek yanıltıcı olur."""
    hazirla(db, [(230.0, 50.0, 2.0)] * 10)
    r = api.power_quality_report("d", 7, db)
    assert r["verdict"] == "yetersiz_veri"


def test_frekans_sinirlari(db):
    hazirla(db, [(230.0, 50.0, 2.0)] * 150)
    r = api.power_quality_report("d", 2, db)
    assert param(r, "frequency")["pass"] is True
    assert param(r, "frequency")["extra"]["min"] == 50.0


def test_degerlendirilmeyenler_gizlenmez(db):
    """Ölçülemeyen parametreler listelenmezse, kısmi bir değerlendirme
    tam sanılır."""
    hazirla(db, [(230.0, 50.0, 2.0)] * 150)
    r = api.power_quality_report("d", 2, db)
    etiketler = [x["label"] for x in r["not_assessed"]]
    assert len(etiketler) >= 4
    assert any("Flicker" in e for e in etiketler)


def test_en50160_sinirlari_beklenen_degerlerde():
    """Sınırlar sessizce değişirse rapor yanlış uygunluk beyan eder."""
    L = api.EN50160_LIMITS
    assert L["voltage_band_pct"] == (0.90, 1.10)       # Un ±%10
    assert L["voltage_band_required"] == 95.0
    assert L["voltage_abs_band_pct"] == (0.85, 1.10)   # +%10 / -%15
    assert L["frequency_band_hz"] == (49.5, 50.5)
    assert L["frequency_required"] == 99.5
    assert L["thd_limit_pct"] == 8.0
