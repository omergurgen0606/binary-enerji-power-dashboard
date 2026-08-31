"""Akım trafo oranı: cihaz tablo indeksi bildirir, oran değil.

Register 221 "Akım Trafo Tablosu"ndaki sırayı tutuyor (0-69), oranın kendisini
değil. Yazma yolu bunu biliyordu (oran -> indeks), okuma yolunda ters çevirim
yoktu. Sonuç: cihaz gerçekte 600/5 ile çalışırken panel "34" gösteriyordu --
cihaz kuran birini yanıltacak bir sayı.

Ölçümler bundan etkilenmiyordu: analizör CT'yi kendi içinde uygulayıp birincil
değerleri veriyor, oran yalnızca gösterim için tutuluyor.
"""
import api


def test_tablo_register_araligiyla_ayni_uzunlukta():
    """Register 0-69 belgelenmiş; tablo da tam 70 girdi olmalı.

    Kısa olsaydı geçerli indeksler 'aralık dışı' sayılırdı; uzun olsaydı
    cihazın asla üretemeyeceği değerler sunulurdu.
    """
    assert len(api.CT_RATIO_TABLE) == 70


def test_sahadaki_gercek_deger():
    """Panodaki analizör ekranı 'C.T.: 600/5' gösterirken register 34 döndü."""
    assert api.ct_ratio_from_index(34) == 600


def test_sinirlar():
    assert api.ct_ratio_from_index(0) == api.CT_RATIO_TABLE[0]
    assert api.ct_ratio_from_index(69) == api.CT_RATIO_TABLE[69]


def test_aralik_disi_tahmin_etmez():
    """Bilinmeyen indekste None dönmeli.

    Yanlış bir oran, eksik bir orandan daha kötü: panelde kendinden emin
    ama hatalı bir sayı görünürdü.
    """
    assert api.ct_ratio_from_index(70) is None
    assert api.ct_ratio_from_index(-1) is None
    assert api.ct_ratio_from_index(9999) is None


def test_bozuk_girdi_patlatmaz():
    """Cihazdan gelen veri her zaman temiz olmayabilir."""
    assert api.ct_ratio_from_index(None) is None
    assert api.ct_ratio_from_index("abc") is None
    assert api.ct_ratio_from_index("34") == 600  # sayısal metin kabul


def test_yazma_ve_okuma_ayni_tablodan_besleniyor():
    """Oran -> indeks -> oran gidiş dönüşü kimliği korumalı.

    İki yön ayrı tablolara dayansaydı zamanla birbirinden kayarlardı.
    """
    for oran in api.CT_RATIO_TABLE:
        idx = api.CT_RATIO_TABLE.index(oran)
        assert api.ct_ratio_from_index(idx) == oran
