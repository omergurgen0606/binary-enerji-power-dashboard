"""Bağlantı havuzu sarmalayıcısının yazma davranışı.

Bu testler gerçek bir hatadan doğdu: `_PooledConnection` yalnızca
`__getattr__` tanımlıyordu, `__setattr__` tanımlamıyordu. Python'da
`__getattr__` sadece OKUMAYI yakalar; `conn.autocommit = True` sarmalayıcı
nesnenin kendi `__dict__`'ine yazılıyor, asıl psycopg2 bağlantısı
`autocommit = False` kalıyordu. Sonra `close()` içindeki `rollback()`
yazılanları sessizce geri alıyordu.

Belirti aldatıcıydı: çevrimdışı alarmı her 60 saniyede bir e-posta/push
gönderiyordu ama `alarm_events` tablosunda tek satır vardı -- bildirim
sıradan Python koduydu, veritabanı yazımı ise geri alınıyordu, ve
`alarm_rules.is_active` mandalı hiç kilitlenemediği için döngü hiç
bitmiyordu. Aynı desen 22 yazma uç noktasında daha vardı.
"""
import api


class SahteBaglanti:
    """psycopg2 bağlantısının bu test için önemli olan yüzeyi."""

    def __init__(self):
        self.autocommit = False
        self.rollback_sayisi = 0

    def rollback(self):
        self.rollback_sayisi += 1


class SahteHavuz:
    def __init__(self):
        self.geri_verilenler = []

    def putconn(self, conn):
        self.geri_verilenler.append(conn)


def test_autocommit_asil_baglantiya_gecer():
    """conn.autocommit = True sarmalayıcıda kalmamalı.

    Hatanın tam kalbi: bu geçmezse yazma uç noktalarının tamamı sessizce
    geri alınır ve hiçbir hata görünmez.
    """
    asil = SahteBaglanti()
    conn = api._PooledConnection(asil, SahteHavuz())

    conn.autocommit = True

    assert asil.autocommit is True, (
        "autocommit sarmalayıcının üstüne yazıldı, asıl bağlantı hâlâ "
        "autocommit=False -- yazılan her şey close() içinde geri alınır"
    )


def test_autocommit_okundugunda_asil_degeri_verir():
    asil = SahteBaglanti()
    conn = api._PooledConnection(asil, SahteHavuz())
    conn.autocommit = True
    assert conn.autocommit is True

    asil.autocommit = False
    assert conn.autocommit is False


def test_sarmalayicinin_kendi_alanlari_asil_baglantiya_sizmaz():
    """_conn/_pool/_returned sarmalayıcıda kalmalı, yoksa sonsuz özyineleme."""
    asil = SahteBaglanti()
    havuz = SahteHavuz()
    conn = api._PooledConnection(asil, havuz)

    assert conn._conn is asil
    assert conn._pool is havuz
    assert not hasattr(asil, "_pool")


def test_havuza_geri_verirken_autocommit_sifirlanir():
    """Sonraki çağıran, öncekinin autocommit tercihini devralmamalı.

    Havuzdan gelen bağlantı yeniden kullanıldığı için, autocommit açık
    bırakılırsa işlem bekleyen bir çağıran farkında olmadan her ifadeyi
    anında commit eder.
    """
    asil = SahteBaglanti()
    havuz = SahteHavuz()
    conn = api._PooledConnection(asil, havuz)
    conn.autocommit = True

    conn.close()

    assert havuz.geri_verilenler == [asil]
    assert asil.autocommit is False, (
        "bağlantı havuza autocommit açık döndü -- sonraki çağıranın "
        "işlemi sessizce parçalanır"
    )


def test_close_iki_kez_cagrilinca_bir_kez_geri_verir():
    asil = SahteBaglanti()
    havuz = SahteHavuz()
    conn = api._PooledConnection(asil, havuz)

    conn.close()
    conn.close()

    assert len(havuz.geri_verilenler) == 1
