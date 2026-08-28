"""Çevrimdışı alarmının kademeli bildirim mantığı.

Önceden tek bildirim vardı: cihaz çevrimdışı olunca bir kez, sonra sessizlik.
Bir cihazın on beş dakika kapalı kalmasıyla üç gün kapalı kalması arasında
hiçbir fark hissedilmiyordu.

Buradaki iki tehlike birbirinin zıddı ve ikisi de gerçek: aynı kademeyi
tekrar tekrar bildirmek (bildirimlerin tamamen yok sayılmasıyla biter) ve
bir kademeyi hiç bildirmemek.
"""
import api


def test_kademe_merdiveni_kuralin_esiginden_baslar():
    """İlk kademe kuralın kendi eşiği; daha küçük kademeler anlamsız."""
    assert api._offline_milestones(2) == [2, 15, 60, 360, 720, 1440, 10080, 43200]
    assert api._offline_milestones(60) == [60, 360, 720, 1440, 10080, 43200]


def test_esikle_cakisan_kademe_tekrarlanmaz():
    """Kural 15 dakikaysa 'çevrimdışı oldu' ile '15 dakikadır' aynı andır.

    İkisi ayrı kademe sayılsaydı kullanıcı aynı anda iki bildirim alırdı.
    """
    kademeler = api._offline_milestones(15)
    assert kademeler == [15, 60, 360, 720, 1440, 10080, 43200]
    assert kademeler.count(15) == 1


def test_sure_metni():
    assert api._offline_sure_metni(15) == "15 dakikadır"
    assert api._offline_sure_metni(60) == "1 saattir"
    assert api._offline_sure_metni(360) == "6 saattir"
    assert api._offline_sure_metni(720) == "12 saattir"
    assert api._offline_sure_metni(1440) == "1 gündür"
    assert api._offline_sure_metni(10080) == "1 haftadır"
    assert api._offline_sure_metni(43200) == "1 aydır"


def test_esik_asilmadan_bildirim_yok():
    karar = api._offline_karar(gecen_dk=5, offline_minutes=15, stage=0)
    assert karar["bildir"] is False
    assert karar["kademe"] == 0


def test_her_kademe_bir_kez_bildirilir():
    """Aynı kademede ikinci kez çağrılmak yeni bildirim üretmemeli.

    Gözcü dakikada bir çalışıyor; bu koruma olmasaydı 1 saatlik kademe
    60 kez bildirilirdi.
    """
    ilk = api._offline_karar(gecen_dk=70, offline_minutes=15, stage=1)
    assert ilk["bildir"] is True
    assert ilk["sure"] == "1 saattir"

    tekrar = api._offline_karar(gecen_dk=70, offline_minutes=15, stage=ilk["kademe"])
    assert tekrar["bildir"] is False

    # Bir sonraki kademeye kadar hâlâ sessiz
    assert api._offline_karar(gecen_dk=300, offline_minutes=15, stage=2)["bildir"] is False


def test_merdiven_bastan_sona():
    """Sekiz kademeli kuralda her eşikte tam bir bildirim çıkmalı."""
    stage = 0
    bildirilen = []
    for dk in [2, 15, 60, 360, 720, 1440, 10080, 43200]:
        karar = api._offline_karar(gecen_dk=dk, offline_minutes=2, stage=stage)
        assert karar["bildir"] is True, f"{dk} dakikada bildirim çıkmadı"
        bildirilen.append(karar["sure"])
        stage = karar["kademe"]

    assert bildirilen == [
        "2 dakikadır", "15 dakikadır", "1 saattir", "6 saattir",
        "12 saattir", "1 gündür", "1 haftadır", "1 aydır",
    ]


def test_son_kademeden_sonra_susulur():
    """Kullanıcının açık isteği: 1 aydan sonra bildirim gönderme."""
    son = api._offline_karar(gecen_dk=43200, offline_minutes=15, stage=6)
    assert son["bildir"] is True
    assert son["son_mu"] is True

    stage = son["kademe"]
    # Aylarca kapalı kalsa bile artık sessiz
    for dk in [50000, 100000, 500000]:
        assert api._offline_karar(gecen_dk=dk, offline_minutes=15, stage=stage)["bildir"] is False


def test_atlanan_kademeler_tek_bildirim_uretir():
    """Sunucu bir gün kapalı kalıp açılırsa altı bildirim birden gitmemeli.

    Ulaşılan en yüksek kademe için tek bildirim çıkar.
    """
    karar = api._offline_karar(gecen_dk=1500, offline_minutes=15, stage=0)
    assert karar["bildir"] is True
    assert karar["sure"] == "1 gündür"
    assert karar["kademe"] == 5  # 15, 60, 360, 720, 1440 geçildi

    # Ve arkasından tekrar bildirim çıkmaz
    assert api._offline_karar(gecen_dk=1500, offline_minutes=15,
                              stage=karar["kademe"])["bildir"] is False


def test_cihaz_geri_gelince_merdiven_sifirlanir():
    """Kademe sıfırlandıktan sonra sonraki kesinti baştan bildirilmeli.

    Sıfırlanmasaydı ikinci kesinti sessiz geçerdi -- daha kötüsü, uzun
    süre çalışmış bir cihaz bir daha hiç alarm üretmezdi.
    """
    stage = 5
    # Veri geldi: geçen süre eşiğin altına düştü
    assert api._offline_karar(gecen_dk=1, offline_minutes=15, stage=stage)["kademe"] == 0

    # Gözcü stage'i 0'a çeker; yeni kesinti baştan bildirilir
    yeni = api._offline_karar(gecen_dk=20, offline_minutes=15, stage=0)
    assert yeni["bildir"] is True
    assert yeni["kademe"] == 1  # merdivenin ilk basamağından başlıyor
    assert yeni["sure"] == "20 dakikadır"


def test_mesaj_kademe_etiketini_degil_gercek_sureyi_soyler():
    """Bildirim zamanını kademe belirler, metni gerçek geçen süre.

    Kademe etiketi kullanılsaydı 5,7 saattir kapalı bir cihaz için mesaj
    "1 saattir" derdi -- 360 dakika kademesi henüz geçilmediği için. Sayı
    yanlış olmamalı; sadece ne zaman bildirileceğini kademe belirlemeli.
    """
    karar = api._offline_karar(gecen_dk=341, offline_minutes=15, stage=1)
    assert karar["bildir"] is True
    assert karar["kademe"] == 2          # 15 ve 60 geçildi, 360 henüz değil
    assert karar["sure"] == "5 saattir"  # ama metin gerçeği söylüyor
