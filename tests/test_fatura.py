"""Fatura hesabı — paranın hesaplandığı yer, en kritik test kümesi.

Burada bir regresyon müşteriye yanlış tutar göstermek demek.
"""
import api


def tarife(**degisiklik):
    t = {
        "inductive_limit_pct": 20.0, "capacitive_limit_pct": 15.0,
        "reactive_price": 2.0, "active_price": 0.0, "billing_mode": "full",
        "t1_start": 6, "t2_start": 17, "t3_start": 22,
        "t1_price": 3.0, "t2_price": 5.0, "t3_price": 1.0,
        "contract_power_kw": 100.0, "demand_price": 50.0,
    }
    t.update(degisiklik)
    return t


def kova(aktif=1000.0, endkt=100.0, kapst=50.0, saat=10):
    return {"bucket": None, "active_kwh": aktif, "inductive_kvarh": endkt,
            "capacitive_kvarh": kapst, "load_hours": saat}


# ---------- Reaktif ceza ----------

def test_limit_icindeyse_ceza_yok():
    # 1000 kWh'nin %20'si = 200; 100 kVArh limitin altında
    r = api._analyze_bucket(kova(endkt=100, kapst=50), tarife())
    assert r["inductive_over"] is False
    assert r["capacitive_over"] is False
    assert r["penalty_cost"] == 0.0


def test_limit_asilinca_tamami_faturalanir():
    # billing_mode='full': limit aşılırsa REAKTİFİN TAMAMI faturalanır,
    # yalnızca aşan kısım değil. Türkiye'deki yaygın uygulama bu.
    r = api._analyze_bucket(kova(aktif=1000, endkt=250, kapst=0), tarife())
    assert r["inductive_over"] is True
    assert r["billed_inductive_kvarh"] == 250.0      # tamamı
    assert r["penalty_cost"] == 500.0               # 250 * 2.0


def test_yalnizca_asan_kisim_modu():
    # Aynı veri, 'excess' modunda: sadece limiti aşan 50 kVArh faturalanır
    r = api._analyze_bucket(kova(aktif=1000, endkt=250, kapst=0),
                            tarife(billing_mode="excess"))
    assert r["billed_inductive_kvarh"] == 50.0      # 250 - 200
    assert r["penalty_cost"] == 100.0               # 50 * 2.0


def test_limitin_tam_ustunde_ceza_yok():
    # Sınırda: tam limit kadar tüketim aşım SAYILMAMALI
    r = api._analyze_bucket(kova(aktif=1000, endkt=200, kapst=0), tarife())
    assert r["inductive_over"] is False
    assert r["penalty_cost"] == 0.0


def test_kompanzasyon_onerisi_yuk_saatine_bolunur():
    # Aşım 50 kVArh, 10 saat yük -> 5 kVAr
    r = api._analyze_bucket(kova(aktif=1000, endkt=250, kapst=0, saat=10), tarife())
    assert r["suggested_kvar"] == 5.0


def test_tuketim_yoksa_oran_hesaplanmaz():
    # Sıfıra bölme değil, None dönmeli
    r = api._analyze_bucket(kova(aktif=0, endkt=0, kapst=0, saat=0), tarife())
    assert r["inductive_pct"] is None
    assert r["inductive_over"] is False


# ---------- Fatura dökümü ----------

def test_kalemler_toplama_esit():
    """Rapordaki en temel tutarlılık: kalemlerin toplamı beyan edilen toplam."""
    reaktif = api._analyze_bucket(kova(aktif=1000, endkt=250, kapst=0), tarife())
    r = api._analyze_bill_month(
        None,
        {"t1_kwh": 600.0, "t2_kwh": 300.0, "t3_kwh": 100.0},
        {"peak_kw": 130.0, "peak_kva": 140.0, "peak_time": None},
        reaktif, tarife())
    assert round(r["active_cost"] + r["demand_cost"] + r["reactive_cost"], 2) == r["total_cost"]


def test_zaman_dilimi_fiyatlari_ayri_uygulanir():
    r = api._analyze_bill_month(
        None, {"t1_kwh": 600.0, "t2_kwh": 300.0, "t3_kwh": 100.0},
        None, None, tarife())
    assert r["t1_cost"] == 1800.0   # 600 * 3
    assert r["t2_cost"] == 1500.0   # 300 * 5
    assert r["t3_cost"] == 100.0    # 100 * 1
    assert r["active_kwh"] == 1000.0


def test_dilim_fiyati_yoksa_tek_fiyata_duser():
    t = tarife(t1_price=0, t2_price=0, t3_price=0, active_price=4.0)
    r = api._analyze_bill_month(
        None, {"t1_kwh": 600.0, "t2_kwh": 300.0, "t3_kwh": 100.0}, None, None, t)
    assert r["active_cost"] == 4000.0   # 1000 * 4


def test_guc_asimi_sadece_asan_kw_uzerinden():
    r = api._analyze_bill_month(
        None, {"t1_kwh": 100.0, "t2_kwh": 0.0, "t3_kwh": 0.0},
        {"peak_kw": 130.0, "peak_kva": 0, "peak_time": None}, None, tarife())
    assert r["overrun_kw"] == 30.0      # 130 - 100
    assert r["demand_cost"] == 1500.0   # 30 * 50


def test_sozlesme_gucu_altindaysa_asim_yok():
    r = api._analyze_bill_month(
        None, {"t1_kwh": 100.0, "t2_kwh": 0.0, "t3_kwh": 0.0},
        {"peak_kw": 80.0, "peak_kva": 0, "peak_time": None}, None, tarife())
    assert r["overrun_kw"] == 0.0
    assert r["demand_cost"] == 0.0


def test_sozlesme_gucu_girilmemisse_asim_hesaplanmaz():
    t = tarife(contract_power_kw=None)
    r = api._analyze_bill_month(
        None, {"t1_kwh": 100.0, "t2_kwh": 0.0, "t3_kwh": 0.0},
        {"peak_kw": 999.0, "peak_kva": 0, "peak_time": None}, None, t)
    assert r["overrun_kw"] is None
    assert r["demand_cost"] == 0.0


def test_puant_kaydirma_tasarrufu_tavani():
    # Puanttaki 300 kWh gece tarifesine kaysaydı: 300 * (5 - 1) = 1200
    r = api._analyze_bill_month(
        None, {"t1_kwh": 600.0, "t2_kwh": 300.0, "t3_kwh": 100.0}, None, None, tarife())
    assert r["max_shift_saving"] == 1200.0
    assert r["puant_pct"] == 30.0


# ---------- Öneriler ----------

def test_fiyat_girilmemisse_oneride_tutar_yazilmaz():
    """0.00 TL yazmak, tarife girilmemiş müşteriye anlamsız görünür."""
    t = tarife(reactive_price=0, demand_price=0, t1_price=0, t2_price=0, t3_price=0)
    reaktif = api._analyze_bucket(kova(aktif=1000, endkt=250, kapst=0), t)
    r = api._analyze_bill_month(
        None, {"t1_kwh": 600.0, "t2_kwh": 300.0, "t3_kwh": 100.0},
        {"peak_kw": 130.0, "peak_kva": 0, "peak_time": None}, reaktif, t)
    metin = " ".join(api._report_recommendations(r, reaktif, t))
    assert "₺" not in metin
    assert "kVAr" in metin          # fiziksel büyüklükler yine söylenmeli
