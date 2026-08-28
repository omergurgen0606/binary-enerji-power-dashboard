"""Saatlik enerji artışı — sayaç sıfırlanmasına dayanıklılık.

Bu hesap bugün bir kez yanlıştı: yalnızca last() saklandığında, sayacın
sıfırlandığı saatin TÜM tüketimi kayboluyordu (ölçülen bir örnekte 380 Wh
gerçek tüketim 0 görünüyordu). Test o davranışın geri gelmesini engelliyor.
"""
import api


def hazirla(db):
    """device_energy_hourly özetiyle aynı şekle sahip geçici tablo.

    Sürekli toplama TimescaleDB'ye özel; test edilen şey SQL ifadesinin
    kendisi olduğu için düz bir tablo yeterli ve daha net.
    """
    db.execute("""
        CREATE TEMP TABLE ozet (
            device_id TEXT, bucket TIMESTAMPTZ,
            first_active_tuketim BIGINT, active_wh_tuketim BIGINT, max_active_tuketim BIGINT
        )
    """)


def delta_topla(db, satirlar):
    """Verilen saatlik kovalar için toplam artışı, üretimdeki SQL ile hesaplar."""
    db.execute("DELETE FROM ozet")
    for i, (ilk, son, enb) in enumerate(satirlar):
        db.execute("INSERT INTO ozet VALUES ('d', now() - (%s * INTERVAL '1 hour'), %s, %s, %s)",
                   (len(satirlar) - i, ilk, son, enb))
    # Pencere fonksiyonu yalnızca iç sorguda tanımlı; dış SUM sadece topluyor.
    db.execute(f"""
        SELECT COALESCE(SUM(d), 0) FROM (
            SELECT {api._hourly_delta_sql('active_tuketim', 'active_wh_tuketim')} AS d
            FROM ozet WINDOW w AS (ORDER BY bucket)
        ) t
    """)
    return db.fetchone()[0]


def test_normal_artis(db):
    hazirla(db)
    # (ilk, son, max) — saatler: 100->110, 110->125
    assert delta_topla(db, [(100, 110, 110), (110, 125, 125)]) == 25


def test_saatler_arasi_bosluk_da_sayilir(db):
    hazirla(db)
    # 1. saat 100->110 biter, 2. saat 115'ten baslar: aradaki 5 kaybolmamali
    assert delta_topla(db, [(100, 110, 110), (115, 125, 125)]) == 25


def test_sayac_sifirlanan_saat_kaybolmaz(db):
    """En kritik durum. Sayaç saat içinde 1000'e kadar çıkıp 0'a dönüyor,
    sonra 124'e geliyor. Gerçek tüketim: (1000-900) + 124 = 224."""
    hazirla(db)
    assert delta_topla(db, [(900, 124, 1000)]) == 224


def test_sifirlama_oncesi_ve_sonrasi_birlikte(db):
    hazirla(db)
    # 1. saat normal (100->200), 2. saatte sifirlama: (500-200) + 50 = 350
    # toplam: 100 + 350 = 450
    assert delta_topla(db, [(100, 200, 200), (200, 50, 500)]) == 450


def test_geriye_giden_sayac_negatif_uretmez(db):
    """Gürültü ya da yeniden bağlanma yüzünden sayaç geri düşerse,
    negatif tüketim değil sıfır/pozitif üretilmeli."""
    hazirla(db)
    sonuc = delta_topla(db, [(100, 100, 100), (90, 95, 95)])
    assert sonuc >= 0
