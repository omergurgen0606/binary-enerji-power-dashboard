"""Test altyapısı ortak kurulumu.

GÜVENLİK: Testler ÜRETİM veritabanına asla dokunmamalı. Bunu yorumla değil,
kodla garanti ediyoruz: aşağıdaki koruma, veritabanı adı beklenen test adı
değilse tüm oturumu durduruyor. Yanlış yapılandırılmış bir test çalıştırması
production'a yazmak yerine hiç başlamıyor.
"""
import os
import sys
import pytest

TEST_DB_NAME = "binaryenerji_test"

# api.py import edilirken bu değişkenler zorunlu. Testte gerçek değerlere
# ihtiyaç yok; hiçbiri dış servise çağrı yapmıyor (import anında).
os.environ.setdefault("POSTGRES_PASSWORD", os.environ.get("TEST_DB_PASSWORD", "test"))
os.environ.setdefault("MQTT_USER", "test")
os.environ.setdefault("MQTT_PASSWORD", "test")
os.environ.setdefault("DEVICE_CLAIM_SECRET", "test-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("RESEND_API_KEY", "test")
os.environ.setdefault("RESEND_FROM", "test <no-reply@example.com>")
os.environ.setdefault("GOOGLE_SHEET_ID", "test")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_FILE", "/dev/null")
os.environ.setdefault("SITE_URL", "http://test.local")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402


def pytest_sessionstart(session):
    """Üretim veritabanına bağlanma ihtimalini oturum başında kes."""
    ad = api.DB_CONFIG.get("dbname")
    if ad != TEST_DB_NAME:
        pytest.exit(
            f"GÜVENLİK DURDURMASI: testler '{ad}' veritabanına bağlanmak üzereydi, "
            f"beklenen '{TEST_DB_NAME}'. Üretim verisine dokunmamak için durduruldu.",
            returncode=2,
        )


@pytest.fixture
def db():
    """Her test kendi işleminde çalışır ve sonunda GERİ ALINIR.

    Testler birbirinin verisini görmez ve hiçbir test kalıcı iz bırakmaz --
    sıralamaya bağlı, kırılgan testlerin en yaygın kaynağı budur.
    """
    import psycopg2
    conn = psycopg2.connect(**api.DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    yield cur
    conn.rollback()
    cur.close()
    conn.close()


@pytest.fixture
def org(db):
    """Test organizasyonu: 2 tesis, 1 bölüm, 3 cihaz.

        Merkez  -> cihaz-a, cihaz-b
        Tesis B -> Pres Hattı -> cihaz-c
    """
    db.execute("INSERT INTO organizations (name) VALUES ('Test Org') RETURNING id")
    org_id = db.fetchone()[0]
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s,'Merkez') RETURNING id", (org_id,))
    merkez = db.fetchone()[0]
    db.execute("INSERT INTO facilities (organization_id, name) VALUES (%s,'Tesis B') RETURNING id", (org_id,))
    tesis_b = db.fetchone()[0]
    db.execute("INSERT INTO departments (facility_id, name) VALUES (%s,'Pres Hattı') RETURNING id", (tesis_b,))
    pres = db.fetchone()[0]

    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES ('sahip','x','sahip@test.local',true)")
    for dev, fac, dep in (("cihaz-a", merkez, None), ("cihaz-b", merkez, None), ("cihaz-c", tesis_b, pres)):
        db.execute("INSERT INTO devices (device_id, name, owner_username, facility_id, department_id) "
                   "VALUES (%s, %s, 'sahip', %s, %s)", (dev, dev, fac, dep))
    return {"org_id": org_id, "merkez": merkez, "tesis_b": tesis_b, "pres": pres}


def uye_ekle(db, org_id, username, role, tesisler=(), bolumler=()):
    """Test kullanıcısı + organizasyon üyeliği oluşturur."""
    db.execute("INSERT INTO users (username, password_hash, email, is_verified) "
               "VALUES (%s,'x',%s,true) ON CONFLICT (username) DO NOTHING",
               (username, f"{username}@test.local"))
    db.execute("INSERT INTO org_members (organization_id, username, role) VALUES (%s,%s,%s) RETURNING id",
               (org_id, username, role))
    uye_id = db.fetchone()[0]
    for t in tesisler:
        db.execute("INSERT INTO member_facilities (member_id, facility_id) VALUES (%s,%s)", (uye_id, t))
    for b in bolumler:
        db.execute("INSERT INTO member_departments (member_id, department_id) VALUES (%s,%s)", (uye_id, b))
    return uye_id


# ---------------------------------------------------------------------------
# Uç nokta testleri için: gerçek SQL, testin kendi işlemi içinde
# ---------------------------------------------------------------------------

class _SahteImlec:
    """Testin imlecini aynen kullanır ama close() çağrısını yutar.

    Uç nokta fonksiyonları finally bloğunda cur.close() çağırıyor. Sarmalanmasa
    testin imleci ilk çağrıda kapanır ve doğrulama satırları
    "cursor already closed" ile patlar.
    """
    def __init__(self, cur):
        self._cur = cur

    def close(self):
        pass

    def __getattr__(self, ad):
        return getattr(self._cur, ad)


class _SahteBaglanti:
    """db_connect() yerine geçer: uç nokta gerçek SQL'i gerçek şemaya karşı
    çalıştırsın, ama commit yutulsun.

    Böylece conftest'in "her test geri alınır" koruması geçerli kalıyor --
    gerçek bir bağlantı açılsaydı test kalıcı iz bırakırdı.
    """
    def __init__(self, cur):
        self._imlec = _SahteImlec(cur)

    def cursor(self):
        return self._imlec

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def sahte_db_connect(cur):
    """monkeypatch.setattr(api, "db_connect", sahte_db_connect(db)) için."""
    return lambda: _SahteBaglanti(cur)
