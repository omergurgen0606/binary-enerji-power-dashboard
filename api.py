import asyncio
import base64
import hashlib
import re
import hmac
import io
import json
import logging
import os
import secrets
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

import bcrypt
import gspread
import jwt
import paho.mqtt.client as mqtt
import psycopg2
import resend
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from openpyxl.styles import Font
from google.oauth2.service_account import Credentials
from PIL import Image
from pydantic import BaseModel

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "timescaledb"),
    "port": 5432,
    # Testler ayri bir veritabani kullanabilsin diye ortamdan okunuyor.
    # Uretimde tanimli degil, varsayilan "postgres".
    "dbname": os.environ.get("POSTGRES_DB", "postgres"),
    "user": "postgres",
    "password": os.environ["POSTGRES_PASSWORD"]
}

MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto")
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASSWORD = os.environ["MQTT_PASSWORD"]
DEVICE_CLAIM_SECRET = os.environ["DEVICE_CLAIM_SECRET"]

# ---------- Veritabanı bağlantı havuzu ----------
# Onceden her istek yeni bir baglanti aciyordu. Olculen sonuc: baglanti kurmak
# 22,7 ms suruyor, korumali her istek 2 baglanti aciyor ve panel bir acilista
# ~12-15 istek atiyor -- yani 25'lik max_connections siniri TEK kullaniciyla
# bile zorlaniyordu (30 es zamanli denemenin 6'si "too many clients" ile
# dusuyordu). Havuz hem bu tavani kaldiriyor hem de istek basina ~45 ms'lik
# baglanti kurma maliyetini siliyor.
#
# maxconn bilincli olarak DUSUK: her PostgreSQL backend'i ~8 MB tutuyor ve
# sunucuda 961 MB var. Amac daha fazla backend degil, DAHA AZ backend'i
# paylastirmak. Kalan kontenjan MQTT thread'inin uzun omurlu baglantisina,
# arka plan islerine ve yonetim erisimine birakiliyor.
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "12"))
# Havuz doluysa hemen hata vermek yerine kisa sure bekliyoruz: ani bir istek
# kumesinde birkac milisaniye beklemek, istegi dusurmekten iyidir.
DB_POOL_WAIT_SECONDS = 5.0

_db_pool = None
_db_pool_lock = threading.Lock()


def _get_db_pool():
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                from psycopg2 import pool as _pgpool
                _db_pool = _pgpool.ThreadedConnectionPool(1, DB_POOL_MAX, **DB_CONFIG)
    return _db_pool


class _PooledConnection:
    """psycopg2 baglantisi gibi davranan ince sarmalayici.

    close() baglantiyi kapatmak yerine havuza geri veriyor; boylece mevcut
    "conn = db_connect() ... cur.close(); conn.close()" desenindeki onlarca
    cagri yeri degistirilmeden calisiyor.
    """

    # Sarmalayicinin kendi alanlari. Bunun disindaki her sey asil baglantiya
    # gider -- ozellikle "autocommit".
    _KENDI_ALANLARI = frozenset({"_conn", "_pool", "_returned"})

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._returned = False

    def __getattr__(self, name):
        # Kendi alanlarimiz __init__ icinde yazildigi icin buraya dusmezler;
        # yine de duserlerse sonsuz ozyineleme yerine temiz hata verelim.
        if name in _PooledConnection._KENDI_ALANLARI:
            raise AttributeError(name)
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        # __getattr__ yalnizca OKUMAYI yakalar. Bu metot olmadan
        # "conn.autocommit = True" sarmalayicinin ustune yaziliyor, asil
        # baglanti autocommit=False kaliyor ve close() icindeki rollback
        # yazilan her seyi sessizce geri aliyordu.
        if name in _PooledConnection._KENDI_ALANLARI:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def close(self):
        if self._returned:
            return
        self._returned = True
        try:
            # Yarim kalan / hatayla kesilmis islem bir sonraki kullaniciya
            # kirli baglanti olarak gecmesin.
            self._conn.rollback()
        except Exception:
            pass
        try:
            # Havuzdaki baglanti yeniden kullanildigi icin, bir cagiranin
            # autocommit tercihi sonrakine miras kalmamali.
            if self._conn.autocommit:
                self._conn.autocommit = False
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception as e:
            logger.error("Baglanti havuza geri verilemedi: %s", e)


def db_connect():
    """Havuzdan bir baglanti alir. Havuz doluysa kisa sure bekler."""
    havuz = _get_db_pool()
    bitis = time.time() + DB_POOL_WAIT_SECONDS
    while True:
        try:
            return _PooledConnection(havuz.getconn(), havuz)
        except Exception:
            if time.time() >= bitis:
                logger.error("Baglanti havuzu doldu (maxconn=%s)", DB_POOL_MAX)
                raise HTTPException(
                    status_code=503,
                    detail="Sunucu şu anda yoğun, lütfen birkaç saniye sonra tekrar deneyin.")
            time.sleep(0.02)


def compute_claim_code(device_id: str) -> str:
    # Cihazi kutulama/etiketleme sirasinda generate_claim_code.py ile ayni
    # kod uretilir ve fiziksel etikete device_id'nin yanina yazilir. Boylece
    # "Cihaz Ekle" formunda sadece device_id bilmek yetmez, kutuyu/cihazi
    # elinde bulunduran kisi bu kodu da girmek zorundadir.
    digest = hmac.new(DEVICE_CLAIM_SECRET.encode(), device_id.strip().lower().encode(), hashlib.sha256).hexdigest()
    return digest[:6].upper()
# Topic'ler artik cihaz basina parametrik: powermeter/{device_id}/live vb.
# Ayni firmware her cihaza (marka farketmeksizin) yuklenebiliyor, her biri MAC'inden
# turettigi kendi device_id'siyle kendi topic'lerine yayin yapiyor/dinliyor.
MQTT_TOPIC_PREFIX = "powermeter"
MQTT_LIVE_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/live"
MQTT_ENERGY_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/energy"
MQTT_STATUS_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/status"
# ANL21 kapsamlı dashboard genişlemesi — Peak/Demand/Harmonics alt-topic'lere
# (/tuketim, /uretim, /akim, /gerilim) sahip, o yüzden 4 parçalı wildcard.
MQTT_STATS_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/stats"
MQTT_PEAKS_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/peaks/+"
MQTT_DEMAND_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/demand/+"
MQTT_HARMONICS_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/harmonics/+"
MQTT_INFO_WILDCARD = f"{MQTT_TOPIC_PREFIX}/+/info"

def live_topic(device_id: str) -> str:
    return f"{MQTT_TOPIC_PREFIX}/{device_id}/live"

def energy_topic(device_id: str) -> str:
    return f"{MQTT_TOPIC_PREFIX}/{device_id}/energy"

def status_topic(device_id: str) -> str:
    return f"{MQTT_TOPIC_PREFIX}/{device_id}/status"

def cmd_topic(device_id: str) -> str:
    return f"{MQTT_TOPIC_PREFIX}/{device_id}/cmd"

def device_id_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    return parts[1] if len(parts) == 3 else None


# Cihaz Özel Komutlar — Excel'deki "Komutlar" sayfası 0xAA55 (43605) tetik değerini
# dokümante ediyor (ANL13'te bu bilinmiyordu, o yüzden terk edilmişti — bkz. architecture.md 5.6).
# Register numaraları ANL13 ile birebir aynı, muhtemelen Grup ARGE'nin tüm ailesinde sabit.
DEVICE_TRIGGER_VALUE = 43605  # 0xAA55
DEVICE_COMMANDS = {
    "reset_energy": {"register": 9001, "value": DEVICE_TRIGGER_VALUE, "risk": "low"},
    "reset_peaks": {"register": 9002, "value": DEVICE_TRIGGER_VALUE, "risk": "low"},
    "reset_demand": {"register": 9003, "value": DEVICE_TRIGGER_VALUE, "risk": "low"},
    "reset_alarms": {"register": 9004, "value": DEVICE_TRIGGER_VALUE, "risk": "low"},
    "factory_reset": {"register": 9024, "value": DEVICE_TRIGGER_VALUE, "risk": "high"},
    "restart": {"register": 9025, "value": DEVICE_TRIGGER_VALUE, "risk": "low"},
    "reset_password": {"register": 9022, "value": DEVICE_TRIGGER_VALUE, "risk": "high"},
}

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

resend.api_key = os.environ["RESEND_API_KEY"]
RESEND_FROM = os.environ["RESEND_FROM"]

GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]

SITE_URL = "https://binaryenerji.com"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("binaryenerji")

# Staging, uretimle ayni kodu ve ayni MQTT akisini kullanir ama AYRI bir
# veritabanina yazar ve DIS DUNYAYA HICBIR SEY GONDERMEZ. Cikis noktalarini
# tek tek cagri yerlerinde degil, kaynaginda kapatiyoruz: yarin eklenecek yeni
# bir e-posta/bildirim cagrisi da otomatik olarak kapsanir, kimsenin
# "staging mi?" diye sormasi gerekmez.
IS_STAGING = os.environ.get("STAGING") == "1"

def _staging_eposta_yutucu(payload, *args, **kwargs):
    logger.info("[STAGING] e-posta gonderilmedi -> %s | %s",
                payload.get("to"), payload.get("subject"))
    return {"id": "staging-gonderilmedi"}


def _staging_korumalarini_uygula():
    """resend'in gonderim fonksiyonunu yutucuyla degistirir.

    Ayri bir fonksiyon olmasinin sebebi test edilebilirlik: korumanin
    gercekten baglandigini dogrulayan bir test yazilabilsin diye.
    """
    logger.warning("STAGING modu: e-posta, push bildirimi ve cihaz komutlari kapali")
    resend.Emails.send = _staging_eposta_yutucu


if IS_STAGING:
    _staging_korumalarini_uygula()
    # Staging'de uretilen bir token uretimde GECERLI OLMAMALI. Ayni sirri
    # paylassalardi staging'de acilan bir oturum uretim panelini de acardi.
    # Ayri bir ortam degiskeni yerine turetiyoruz: eklemeyi unutmak mumkun degil.
    JWT_SECRET = hashlib.sha256(("staging:" + JWT_SECRET).encode()).hexdigest()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # auth Bearer-token oldugu icin (cookie degil) CORS zaten CSRF vektoru degildi,
    # ama "*" gereksiz yere genisti -- gercek origin'lere daraltildi. localhost:5173
    # yerel Vite dev server icin (bu API'ye karsi test ederken kullaniliyor).
    allow_origins=[SITE_URL, "http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # HTTPException'lar (401/403/404 vb.) bunun disinda, kendi normal akisinda kalir --
    # bu sadece beklenmeyen (gercek bug/kesinti) hatalari net bir sekilde loglar ki
    # "docker compose logs api | grep 'UNHANDLED ERROR'" ile kolayca bulunabilsin.
    logger.error(
        "UNHANDLED ERROR %s %s -> %s: %s\n%s",
        request.method, request.url.path, type(exc).__name__, exc,
        traceback.format_exc(),
    )
    return Response(content='{"detail":"Sunucu hatası"}', status_code=500, media_type="application/json")

# Kullanıcı profil fotoğrafları -- kimlik doğrulama gerektirmeyen, herkese açık
# statik servis (basit <img>/AsyncImage kullanımı için, hassas veri içermiyor).
AVATAR_DIR = os.environ.get("AVATAR_DIR", "/app/uploads/avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=AVATAR_DIR), name="avatars")

# Firmware .bin dosyalari -- avatarlarla ayni gerekce ile kimlik dogrulamasiz
# servis ediliyor (ESP32'nin dogrudan indirebilmesi icin, cihazda JWT/login
# mekanizmasi yok). Yukleme (POST) ise admin-only.
FIRMWARE_DIR = os.environ.get("FIRMWARE_DIR", "/app/uploads/firmware")
os.makedirs(FIRMWARE_DIR, exist_ok=True)
app.mount("/firmware-files", StaticFiles(directory=FIRMWARE_DIR), name="firmware-files")

# Cihazi bir bagimsiz ariza mi yoksa "hic kurulmamis" mi diye ayirt edebilmek icin
# esikler: bu sureden uzun sessiz kalan cihaz filo panelinde uyari olarak gosterilir.
FLEET_STALE_MINUTES = 10
FLEET_DEAD_HOURS = 24

main_loop = None  # asyncio event loop referansı, MQTT thread'inden erişmek için

# ---------- Basit bellek-içi rate limiter (tek uvicorn process, worker yok) ----------
# claim-code/login/register brute force'unu ve yüksek riskli komut şifre denemelerini
# sınırlamak için -- ayrı bir servis (Redis vb.) gerektirmeyecek kadar basit tutuldu.
_rate_limit_state: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()

def check_rate_limit(key: str, max_attempts: int, window_seconds: int):
    now = time.monotonic()
    with _rate_limit_lock:
        attempts = [t for t in _rate_limit_state.get(key, []) if now - t < window_seconds]
        if len(attempts) >= max_attempts:
            raise HTTPException(status_code=429, detail="Çok fazla deneme yapıldı, lütfen daha sonra tekrar deneyin.")
        attempts.append(now)
        _rate_limit_state[key] = attempts

def client_ip(request: Request) -> str:
    # nginx `proxy_set_header X-Real-IP $remote_addr` ile gerçek istemci IP'sini set ediyor.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

# ---------- Auth: JWT oluşturma/doğrulama ----------
def create_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        return None

def require_auth(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Yetkisiz")
    username = verify_token(authorization.removeprefix("Bearer "))
    if not username:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    return username


def get_user_role(username: str) -> str:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "user"


def require_admin(user: str = Depends(require_auth)) -> str:
    """Uretici/yonetici yetkisi gerektiren uc noktalar icin. Rol users.role
    sutunundan okunuyor -- daha once tek kullanici adi koda gomuluydu."""
    if get_user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için yönetici yetkisi gerekiyor")
    return user

# ---------- Cihaz erişimi (Organizasyon → Tesis → Bölüm) ----------
# Yetki modeli kapsam-tabanli: rol "ne yapabilirsin"i degil "neyi gorebilirsin"i
# belirliyor (Entes Enerji Doktoru'nun modeliyle ayni eksende).
#   org_admin          -> organizasyonun tum cihazlari
#   facility_manager   -> sadece atandigi tesislerin cihazlari
#   department_manager -> sadece atandigi bolumlerin cihazlari
#
# Not: devices.owner_username hala duruyor ama artik yetki icin KULLANILMIYOR --
# sadece "bu cihazi kim kaydetti" kaydi olarak tutuluyor.
ORG_ROLES = ("org_admin", "facility_manager", "department_manager")

# Bir kullanicinin erisebildigi cihazlari veren tek sorgu. Hem listeleme hem de
# tekil erisim kontrolu bunun uzerinden yurur ki iki yerde ayrisip guvenlik acigi
# olusturmasin.
_ACCESSIBLE_DEVICES_SQL = """
    SELECT d.device_id, d.name, d.facility_id, d.department_id,
           f.name AS facility_name, dep.name AS department_name,
           f.organization_id
    FROM devices d
    JOIN facilities f ON f.id = d.facility_id
    JOIN org_members m ON m.organization_id = f.organization_id
    LEFT JOIN departments dep ON dep.id = d.department_id
    WHERE m.username = %s
      AND (
        m.role = 'org_admin'
        OR (m.role = 'facility_manager'
            AND d.facility_id IN (SELECT facility_id FROM member_facilities WHERE member_id = m.id))
        OR (m.role = 'department_manager'
            AND d.department_id IS NOT NULL
            AND d.department_id IN (SELECT department_id FROM member_departments WHERE member_id = m.id))
      )
"""


def get_owned_devices(username: str) -> list[dict]:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(_ACCESSIBLE_DEVICES_SQL + " ORDER BY f.name, dep.name NULLS FIRST, d.id", (username,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "device_id": r[0], "name": r[1],
            "facility_id": r[2], "department_id": r[3],
            "facility_name": r[4], "department_name": r[5],
        }
        for r in rows
    ]


def is_device_owner(username: str, device_id: str) -> bool:
    """Isim geriye donuk uyumluluk icin korundu; artik 'sahiplik' degil
    'kapsam icinde erisim' anlamina geliyor."""
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM (" + _ACCESSIBLE_DEVICES_SQL + ") AS accessible WHERE device_id = %s",
        (username, device_id),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def users_with_device_access(device_id: str, cur) -> list[str]:
    """Cihazi gorebilen kullanici adlari.

    Kapsam _ACCESSIBLE_DEVICES_SQL'den geliyor ama o sorgu tek bir kullanici
    adi bagliyor ve korelasyonlu alt sorguya cevrilemiyor; sorguyu kopyalayip
    degistirmek yerine kullanici basina cagiriyoruz. Boylece bildirim kapsami
    (alarm e-postasi, push, aylik rapor) panelde gorulen kapsamdan ayrisamaz.
    """
    # DISTINCT: bir kullanicinin birden fazla organizasyon uyeligi olabilir ve
    # o durumda ayni kisi listeye iki kez girip alarmi iki kez alirdi.
    cur.execute("SELECT DISTINCT username FROM org_members")
    out = []
    for (username,) in cur.fetchall():
        cur.execute(
            "SELECT 1 FROM (" + _ACCESSIBLE_DEVICES_SQL + ") AS accessible WHERE device_id = %s",
            (username, device_id),
        )
        if cur.fetchone():
            out.append(username)
    return out


def get_membership(username: str) -> dict | None:
    """Kullanicinin organizasyon uyeligi + kapsami."""
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.organization_id, m.role, o.name
        FROM org_members m JOIN organizations o ON o.id = m.organization_id
        WHERE m.username = %s
    """, (username,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    member_id, org_id, role, org_name = row
    cur.execute("SELECT facility_id FROM member_facilities WHERE member_id = %s", (member_id,))
    facility_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT department_id FROM member_departments WHERE member_id = %s", (member_id,))
    department_ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {
        "member_id": member_id, "organization_id": org_id, "role": role,
        "organization_name": org_name,
        "facility_ids": facility_ids, "department_ids": department_ids,
    }


def require_org_admin(user: str = Depends(require_auth)) -> str:
    """Organizasyon yapisini ve uyeleri yonetmek icin. Tesis/bolum sorumlulari
    kendi kapsamlarindaki cihazlari yonetir ama organizasyon yapisina dokunamaz."""
    m = get_membership(user)
    if not m or m["role"] != "org_admin":
        raise HTTPException(status_code=403, detail="Bu işlem için organizasyon yöneticisi olmanız gerekiyor")
    return user

@app.get("/devices")
def list_devices(user: str = Depends(require_auth)):
    return get_owned_devices(user)

class AddDeviceRequest(BaseModel):
    device_id: str
    name: str
    claim_code: str
    facility_id: int | None = None
    department_id: int | None = None

@app.post("/devices")
def add_device(payload: AddDeviceRequest, user: str = Depends(require_auth)):
    device_id = payload.device_id.strip()
    name = payload.name.strip()
    claim_code = payload.claim_code.strip().upper()
    if not device_id or not name or not claim_code:
        raise HTTPException(status_code=400, detail="Cihaz adı, cihaz ID'si ve kurulum kodu zorunlu")
    # claim_code 6 hex karakter (24 bit) -- IP değil device_id başına sınırlanıyor, çünkü
    # asıl kısıtlanacak kaynak bu: bir device_id için saatte 10 denemeyle 16.7M'lik uzayı
    # taramak pratikte imkansız hale geliyor (bkz. architecture.md güvenlik notları).
    check_rate_limit(f"claim:{device_id}", max_attempts=10, window_seconds=60 * 60)
    if not hmac.compare_digest(claim_code, compute_claim_code(device_id)):
        raise HTTPException(status_code=403, detail="Kurulum kodu hatalı — cihaz etiketindeki kodu kontrol edin")

    membership = get_membership(user)
    if not membership:
        raise HTTPException(status_code=403, detail="Bir organizasyona bağlı değilsiniz")
    if membership["role"] == "department_manager":
        raise HTTPException(status_code=403, detail="Bölüm sorumluları cihaz ekleyemez")

    # Abonelik cihaz limiti. Cihaz basina ucretlendirildigi icin, satilandan
    # fazla cihaz eklenmesini burada engelliyoruz. Limit NULL ise sinirsiz.
    _sub_conn = db_connect()
    _sub_cur = _sub_conn.cursor()
    try:
        _state = subscription_state(membership["organization_id"], _sub_cur)
        if _state["device_limit"] is not None:
            _sub_cur.execute("""
                SELECT count(*) FROM devices d
                JOIN facilities f ON f.id = d.facility_id
                WHERE f.organization_id = %s
            """, (membership["organization_id"],))
            if _sub_cur.fetchone()[0] >= _state["device_limit"]:
                raise HTTPException(
                    status_code=402,
                    detail=f"Abonelik cihaz limitiniz ({_state['device_limit']}) doldu. "
                           f"Daha fazla cihaz eklemek için bizimle iletişime geçin.")
    finally:
        _sub_cur.close()
        _sub_conn.close()

    facility_id = resolve_target_facility(membership, payload.facility_id)
    department_id = payload.department_id
    if department_id is not None and not department_belongs_to(department_id, facility_id):
        raise HTTPException(status_code=400, detail="Seçilen bölüm bu tesise ait değil")

    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO devices (device_id, name, owner_username, facility_id, department_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (device_id, name, user, facility_id, department_id),
        )
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Bu cihaz ID'si zaten kayıtlı")
    finally:
        cur.close()
        conn.close()
    audit("device.add", actor=user, organization_id=membership["organization_id"],
          entity_type="device", entity_id=device_id, detail={"ad": name})
    return {"message": "Cihaz eklendi"}


def resolve_target_facility(membership: dict, requested_facility_id: int | None) -> int:
    """Cihazin hangi tesise ekleneceğini belirler ve kullanicinin o tesise
    yetkisi olduğunu doğrular. Tek tesisli (küçük müşteri) durumda seçim
    gerekmeden otomatik çözülür."""
    conn = db_connect()
    cur = conn.cursor()
    if membership["role"] == "org_admin":
        cur.execute(
            "SELECT id FROM facilities WHERE organization_id = %s ORDER BY id",
            (membership["organization_id"],),
        )
        allowed = [r[0] for r in cur.fetchall()]
    else:
        allowed = membership["facility_ids"]
    cur.close()
    conn.close()

    if not allowed:
        raise HTTPException(status_code=400, detail="Cihaz eklenebilecek bir tesis yok, önce tesis oluşturun")
    if requested_facility_id is None:
        if len(allowed) > 1:
            raise HTTPException(status_code=400, detail="Birden fazla tesisiniz var, cihazın ekleneceği tesisi seçin")
        return allowed[0]
    if requested_facility_id not in allowed:
        raise HTTPException(status_code=403, detail="Bu tesise cihaz ekleme yetkiniz yok")
    return requested_facility_id


def department_belongs_to(department_id: int, facility_id: int) -> bool:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM departments WHERE id = %s AND facility_id = %s", (department_id, facility_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None

@app.delete("/devices/{device_id}")
def remove_device(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    # Ölçüm geçmişi bilerek silinmiyor — sadece kayıt kaldırılıyor. Cihaz veri
    # göndermeye devam ederse sahipsiz kalır, tekrar kurulum koduyla eklenebilir.
    # Erişim zaten yukarıda is_device_owner ile doğrulandı.
    cur.execute("DELETE FROM devices WHERE device_id = %s", (device_id,))
    cur.close()
    conn.close()
    return {"message": "Cihaz kaldırıldı"}

class RenameDeviceRequest(BaseModel):
    name: str

@app.patch("/devices/{device_id}")
def rename_device(device_id: str, payload: RenameDeviceRequest, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Cihaz adı boş olamaz")
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("UPDATE devices SET name = %s WHERE device_id = %s", (name, device_id))
    cur.close()
    conn.close()
    return {"message": "Cihaz adı güncellendi"}

def avatar_url_for(username: str, avatar_updated_at) -> str | None:
    if not avatar_updated_at:
        return None
    return f"/avatars/{username}.jpg?v={int(avatar_updated_at.timestamp())}"

@app.get("/me")
def get_me(user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT first_name, last_name, username, email, phone, created_at, avatar_updated_at, "
        "is_verified, role, monthly_report, alarm_email "
        "FROM users WHERE username = %s",
        (user,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return {
        "first_name": row[0], "last_name": row[1], "username": row[2], "email": row[3], "phone": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "avatar_url": avatar_url_for(row[2], row[6]),
        "is_verified": row[7],
        "role": row[8],
        "monthly_report": row[9],
        "alarm_email": row[10],
    }

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/me/password")
def change_password(payload: ChangePasswordRequest, user: str = Depends(require_auth)):
    # Sifre brute-force'unu sinirlamak icin ayni rate limiter -- 5 deneme/saat/kullanici.
    check_rate_limit(f"pwchange:{user}", max_attempts=5, window_seconds=60 * 60)
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 6 karakter olmalı")
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (user,))
    row = cur.fetchone()
    if not row or not bcrypt.checkpw(payload.current_password.encode(), row[0].encode()):
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Mevcut şifre hatalı")
    new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode()
    cur.execute("UPDATE users SET password_hash = %s WHERE username = %s", (new_hash, user))
    cur.close()
    conn.close()
    audit("account.password_change", actor=user)
    return {"message": "Şifre güncellendi"}


class ChangeEmailRequest(BaseModel):
    password: str
    email: str


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/me/email")
def change_email(payload: ChangeEmailRequest, user: str = Depends(require_auth)):
    # E-posta degisikligi bir hesap-kurtarma vektoru oldugu icin mevcut sifre
    # zorunlu; ayrica yeni adres, dogrulama linkine tiklanana kadar kaydedilmez
    # (pending_email). Boylece yanlis/baskasinin adresi yazilsa bile hesabin
    # gercek e-postasi degismez.
    check_rate_limit(f"emailchange:{user}", max_attempts=5, window_seconds=60 * 60)
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi girin")

    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (user,))
    row = cur.fetchone()
    if not row or not bcrypt.checkpw(payload.password.encode(), row[0].encode()):
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Şifre hatalı")

    cur.execute("SELECT 1 FROM users WHERE lower(email) = %s AND username <> %s", (email, user))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Bu e-posta adresi başka bir hesapta kayıtlı")

    token = secrets.token_urlsafe(32)
    cur.execute(
        "UPDATE users SET pending_email = %s, pending_email_token = %s WHERE username = %s",
        (email, token, user),
    )
    cur.close()
    conn.close()

    verify_url = f"{SITE_URL}/api/verify-email-change?token={token}"
    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": [email],
            "subject": "Binary Enerji — E-posta Adresi Doğrulama",
            "html": (
                f"<p>Binary Enerji hesabınızın e-posta adresini bu adres olarak "
                f"güncellemek için <a href='{verify_url}'>tıklayın</a>.</p>"
                f"<p style='color:#666;font-size:13px'>Bu isteği siz yapmadıysanız bu e-postayı yok sayın; "
                f"hesabınızda hiçbir değişiklik olmaz.</p>"
            ),
        })
    except Exception as e:
        logger.error("E-posta degisiklik dogrulamasi gonderilemedi: %s", e)
        raise HTTPException(status_code=502, detail="Doğrulama e-postası gönderilemedi, lütfen tekrar deneyin")

    return {"message": f"Doğrulama bağlantısı {email} adresine gönderildi. Onayladıktan sonra geçerli olacak."}


@app.get("/verify-email-change", response_class=HTMLResponse)
def verify_email_change(token: str):
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET email = pending_email, is_verified = true,
            pending_email = NULL, pending_email_token = NULL
        WHERE pending_email_token = %s AND pending_email IS NOT NULL
        RETURNING email
    """, (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return HTMLResponse("<h2>Geçersiz veya süresi dolmuş doğrulama linki.</h2>", status_code=400)
    return HTMLResponse(
        f"<h2>E-posta adresiniz güncellendi.</h2><p>{row[0]}</p>"
        f'<a href="{SITE_URL}">Panoya dön</a>'
    )


ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024

@app.post("/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: str = Depends(require_auth)):
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Sadece JPEG, PNG veya WEBP resim yükleyebilirsiniz")
    contents = await file.read()
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Resim en fazla 5 MB olabilir")
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
        img = Image.open(io.BytesIO(contents))  # verify() sonrasi dosya tekrar acilmali
        img = img.convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz resim dosyası")

    # Merkezden kare kirp, 512x512'ye kucult -- tum istemcilerde tutarli avatar boyutu.
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((512, 512), Image.LANCZOS)
    img.save(os.path.join(AVATAR_DIR, f"{user}.jpg"), "JPEG", quality=85)

    now = datetime.utcnow()
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar_updated_at = %s WHERE username = %s", (now, user))
    cur.close()
    conn.close()
    return {"avatar_url": avatar_url_for(user, now)}

# ---------- OTA: firmware yukleme/servis/tetikleme ----------
VALID_DEVICE_TYPES = {"anl13", "anl21"}

def device_type_from_id(device_id: str) -> str | None:
    for t in VALID_DEVICE_TYPES:
        if device_id.startswith(t + "-"):
            return t
    return None

@app.post("/admin/firmware")
async def upload_firmware(
    file: UploadFile = File(...),
    device_type: str = Form(...),
    version: str = Form(...),
    notes: str = Form(""),
    user: str = Depends(require_admin),
):
    if device_type not in VALID_DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Geçersiz cihaz tipi: {device_type}")
    if not re.match(r"^[a-zA-Z0-9_.-]{1,32}$", version):
        raise HTTPException(status_code=400, detail="Geçersiz sürüm formatı")

    contents = await file.read()
    if len(contents) < 1000 or len(contents) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Geçersiz veya çok büyük .bin dosyası")

    sha256 = hashlib.sha256(contents).hexdigest()
    filename = f"{device_type}-{version}.bin"
    with open(os.path.join(FIRMWARE_DIR, filename), "wb") as f:
        f.write(contents)

    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO firmware_builds (device_type, version, filename, sha256, notes) VALUES (%s, %s, %s, %s, %s)",
        (device_type, version, filename, sha256, notes),
    )
    cur.close()
    conn.close()
    return {"message": "Firmware yüklendi", "version": version, "sha256": sha256}

# ---------- Organizasyon yapısı ve üyeler ----------

class FacilityRequest(BaseModel):
    name: str

class DepartmentRequest(BaseModel):
    facility_id: int
    name: str

class MemberRoleRequest(BaseModel):
    role: str
    facility_ids: list[int] = []
    department_ids: list[int] = []


@app.get("/organization")
def get_organization(user: str = Depends(require_auth)):
    """Kullanicinin organizasyonu: tesisler, bolumler, uyeler ve kendi kapsami."""
    membership = get_membership(user)
    if not membership:
        raise HTTPException(status_code=404, detail="Bir organizasyona bağlı değilsiniz")
    org_id = membership["organization_id"]

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM facilities WHERE organization_id = %s ORDER BY name", (org_id,))
    facilities = [{"id": r[0], "name": r[1], "departments": []} for r in cur.fetchall()]
    by_id = {f["id"]: f for f in facilities}

    if facilities:
        cur.execute(
            "SELECT id, facility_id, name FROM departments WHERE facility_id = ANY(%s) ORDER BY name",
            (list(by_id.keys()),),
        )
        for dep_id, fac_id, dep_name in cur.fetchall():
            by_id[fac_id]["departments"].append({"id": dep_id, "name": dep_name})

    # Cihaz sayilari -- hangi tesis/bolum dolu, gorsel olarak onemli
    cur.execute("""
        SELECT d.facility_id, d.department_id, count(*)
        FROM devices d JOIN facilities f ON f.id = d.facility_id
        WHERE f.organization_id = %s GROUP BY d.facility_id, d.department_id
    """, (org_id,))
    device_counts = [{"facility_id": r[0], "department_id": r[1], "count": r[2]} for r in cur.fetchall()]

    members = []
    if membership["role"] == "org_admin":
        cur.execute("""
            SELECT m.id, m.username, m.role, u.first_name, u.last_name, u.email
            FROM org_members m JOIN users u ON u.username = m.username
            WHERE m.organization_id = %s ORDER BY m.role, m.username
        """, (org_id,))
        rows = cur.fetchall()
        for member_id, username, role, first, last, email in rows:
            cur.execute("SELECT facility_id FROM member_facilities WHERE member_id = %s", (member_id,))
            fids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT department_id FROM member_departments WHERE member_id = %s", (member_id,))
            dids = [r[0] for r in cur.fetchall()]
            members.append({
                "member_id": member_id, "username": username, "role": role,
                "full_name": " ".join(x for x in [first, last] if x) or None,
                "email": email, "facility_ids": fids, "department_ids": dids,
            })
    cur.close()
    conn.close()

    return {
        "organization": {"id": org_id, "name": membership["organization_name"]},
        "my_role": membership["role"],
        "my_facility_ids": membership["facility_ids"],
        "my_department_ids": membership["department_ids"],
        "facilities": facilities,
        "device_counts": device_counts,
        "members": members,
    }


@app.post("/organization/facilities")
def create_facility(payload: FacilityRequest, user: str = Depends(require_org_admin)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tesis adı boş olamaz")
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO facilities (organization_id, name) VALUES (%s, %s) RETURNING id",
        (membership["organization_id"], name),
    )
    facility_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"id": facility_id, "name": name}


@app.delete("/organization/facilities/{facility_id}")
def delete_facility(facility_id: int, user: str = Depends(require_org_admin)):
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM facilities WHERE id = %s AND organization_id = %s",
        (facility_id, membership["organization_id"]),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Tesis bulunamadı")
    # Icinde cihaz varken silmeyi engelle -- cihazlar sahipsiz kalirdi.
    cur.execute("SELECT count(*) FROM devices WHERE facility_id = %s", (facility_id,))
    if cur.fetchone()[0] > 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Bu tesiste cihazlar var, önce onları taşıyın veya kaldırın")
    cur.execute("DELETE FROM facilities WHERE id = %s", (facility_id,))
    cur.close()
    conn.close()
    return {"message": "Tesis silindi"}


@app.post("/organization/departments")
def create_department(payload: DepartmentRequest, user: str = Depends(require_org_admin)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bölüm adı boş olamaz")
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM facilities WHERE id = %s AND organization_id = %s",
        (payload.facility_id, membership["organization_id"]),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Tesis bulunamadı")
    cur.execute(
        "INSERT INTO departments (facility_id, name) VALUES (%s, %s) RETURNING id",
        (payload.facility_id, name),
    )
    dep_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"id": dep_id, "name": name, "facility_id": payload.facility_id}


@app.delete("/organization/departments/{department_id}")
def delete_department(department_id: int, user: str = Depends(require_org_admin)):
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM departments dep JOIN facilities f ON f.id = dep.facility_id
        WHERE dep.id = %s AND f.organization_id = %s
    """, (department_id, membership["organization_id"]))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Bölüm bulunamadı")
    # Bolum silinince cihazlar tesise geri duser, sahipsiz kalmaz.
    cur.execute("UPDATE devices SET department_id = NULL WHERE department_id = %s", (department_id,))
    cur.execute("DELETE FROM departments WHERE id = %s", (department_id,))
    cur.close()
    conn.close()
    return {"message": "Bölüm silindi"}


class MoveDeviceRequest(BaseModel):
    facility_id: int
    department_id: int | None = None


@app.patch("/devices/{device_id}/location")
def move_device(device_id: str, payload: MoveDeviceRequest, user: str = Depends(require_org_admin)):
    """Cihazi baska tesise/bolume tasi."""
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM facilities WHERE id = %s AND organization_id = %s",
        (payload.facility_id, membership["organization_id"]),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Tesis bulunamadı")
    if payload.department_id is not None and not department_belongs_to(payload.department_id, payload.facility_id):
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Seçilen bölüm bu tesise ait değil")
    cur.execute(
        "UPDATE devices SET facility_id = %s, department_id = %s WHERE device_id = %s",
        (payload.facility_id, payload.department_id, device_id),
    )
    cur.close()
    conn.close()
    return {"message": "Cihaz taşındı"}


class InviteRequest(BaseModel):
    email: str
    role: str
    facility_ids: list[int] = []
    department_ids: list[int] = []


INVITE_VALID_DAYS = 7


@app.post("/organization/invites")
def create_invite(payload: InviteRequest, user: str = Depends(require_org_admin)):
    if payload.role not in ORG_ROLES:
        raise HTTPException(status_code=400, detail="Geçersiz rol")
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi girin")
    check_rate_limit(f"invite:{user}", max_attempts=20, window_seconds=60 * 60)

    membership = get_membership(user)
    org_id = membership["organization_id"]

    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()

    # Zaten uye mi?
    cur.execute("""
        SELECT 1 FROM org_members m JOIN users u ON u.username = m.username
        WHERE m.organization_id = %s AND lower(u.email) = %s
    """, (org_id, email))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Bu e-posta zaten organizasyonun üyesi")

    # Kapsam id'lerini bu organizasyona ait olanlarla sinirla -- baska bir
    # organizasyonun tesis id'si gonderilerek yetki sizmasi olmasin.
    cur.execute("SELECT id FROM facilities WHERE organization_id = %s", (org_id,))
    valid_facilities = {r[0] for r in cur.fetchall()}
    cur.execute("""
        SELECT dep.id FROM departments dep JOIN facilities f ON f.id = dep.facility_id
        WHERE f.organization_id = %s
    """, (org_id,))
    valid_departments = {r[0] for r in cur.fetchall()}
    facility_ids = [i for i in payload.facility_ids if i in valid_facilities]
    department_ids = [i for i in payload.department_ids if i in valid_departments]

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_VALID_DAYS)
    # Ayni adrese bekleyen davet varsa yenisiyle degistir
    cur.execute(
        "DELETE FROM org_invites WHERE organization_id = %s AND lower(email) = %s AND accepted_at IS NULL",
        (org_id, email),
    )
    cur.execute("""
        INSERT INTO org_invites (organization_id, email, role, facility_ids, department_ids,
                                 token, invited_by, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (org_id, email, payload.role, facility_ids, department_ids, token, user, expires_at))
    invite_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    org_name = membership["organization_name"]
    role_label = {
        "org_admin": "Organizasyon Yöneticisi",
        "facility_manager": "Tesis Sorumlusu",
        "department_manager": "Bölüm Sorumlusu",
    }.get(payload.role, payload.role)
    invite_url = f"{SITE_URL}/davet?token={token}"
    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": [email],
            "subject": f"{org_name} sizi Binary Enerji'ye davet etti",
            "html": (
                f"<p><b>{org_name}</b> organizasyonuna <b>{role_label}</b> olarak davet edildiniz.</p>"
                f"<p><a href='{invite_url}'>Daveti kabul et</a></p>"
                f"<p style='color:#666;font-size:13px'>Bu bağlantı {INVITE_VALID_DAYS} gün geçerlidir. "
                f"Hesabınız yoksa önce üye olmanız istenecek — davetin gönderildiği "
                f"<b>{email}</b> adresiyle kaydolun.</p>"
            ),
        })
    except Exception as e:
        logger.error("Davet e-postasi gonderilemedi: %s", e)
        raise HTTPException(status_code=502, detail="Davet e-postası gönderilemedi, lütfen tekrar deneyin")

    return {"id": invite_id, "email": email, "expires_at": expires_at.isoformat()}


@app.get("/organization/invites")
def list_invites(user: str = Depends(require_org_admin)):
    membership = get_membership(user)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, email, role, created_at, expires_at
        FROM org_invites
        WHERE organization_id = %s AND accepted_at IS NULL
        ORDER BY created_at DESC
    """, (membership["organization_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    now = datetime.now(timezone.utc)
    return [
        {
            "id": r[0], "email": r[1], "role": r[2],
            "created_at": r[3].isoformat(),
            "expires_at": r[4].isoformat(),
            "expired": r[4] < now,
        }
        for r in rows
    ]


@app.delete("/organization/invites/{invite_id}")
def cancel_invite(invite_id: int, user: str = Depends(require_org_admin)):
    membership = get_membership(user)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM org_invites WHERE id = %s AND organization_id = %s",
        (invite_id, membership["organization_id"]),
    )
    deleted = cur.rowcount
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Davet bulunamadı")
    return {"message": "Davet iptal edildi"}


@app.get("/invites/{token}")
def preview_invite(token: str):
    """Davet baglantisinin acilis sayfasi icin -- giris yapilmadan once
    'hangi organizasyon, hangi rol' gosterilebilsin diye."""
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.email, i.role, i.expires_at, i.accepted_at, o.name
        FROM org_invites i JOIN organizations o ON o.id = i.organization_id
        WHERE i.token = %s
    """, (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Davet bulunamadı")
    email, role, expires_at, accepted_at, org_name = row
    return {
        "organization_name": org_name,
        "email": email,
        "role": role,
        "expired": expires_at < datetime.now(timezone.utc),
        "accepted": accepted_at is not None,
    }


class AcceptInviteRequest(BaseModel):
    token: str


@app.post("/organization/invites/accept")
def accept_invite(payload: AcceptInviteRequest, user: str = Depends(require_auth)):
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        SELECT id, organization_id, email, role, facility_ids, department_ids, expires_at, accepted_at
        FROM org_invites WHERE token = %s
    """, (payload.token,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Davet bulunamadı")
    invite_id, org_id, invite_email, role, facility_ids, department_ids, expires_at, accepted_at = row
    if accepted_at is not None:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Bu davet zaten kullanılmış")
    if expires_at < datetime.now(timezone.utc):
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Davetin süresi dolmuş, yöneticinizden yeni davet isteyin")

    # Davet e-postaya bagli: bagi baskasina iletilse bile kullanilamasin.
    cur.execute("SELECT lower(email) FROM users WHERE username = %s", (user,))
    user_email = (cur.fetchone() or [None])[0]
    if not user_email or user_email != invite_email.lower():
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=403,
            detail=f"Bu davet {invite_email} adresine gönderilmiş. Lütfen o adresle kayıtlı hesapla giriş yapın.",
        )

    # Kullanicinin mevcut uyeligi: kayit sirasinda herkese otomatik bir kisisel
    # organizasyon aciliyor. O organizasyon bos ise (cihaz yok, tek uye) davet
    # kabul edilirken guvenle birakilabilir. Dolu ise veri kaybi riski var, reddet.
    cur.execute("SELECT id, organization_id FROM org_members WHERE username = %s", (user,))
    existing = cur.fetchone()
    if existing:
        old_member_id, old_org_id = existing
        if old_org_id == org_id:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Zaten bu organizasyonun üyesisiniz")
        cur.execute("""
            SELECT (SELECT count(*) FROM devices d JOIN facilities f ON f.id = d.facility_id
                    WHERE f.organization_id = %s),
                   (SELECT count(*) FROM org_members WHERE organization_id = %s)
        """, (old_org_id, old_org_id))
        device_count, member_count = cur.fetchone()
        if device_count > 0 or member_count > 1:
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="Halihazırda cihazları olan bir organizasyondasınız. Daveti kabul etmek için "
                       "önce mevcut organizasyonunuzdan ayrılmanız gerekir.",
            )
        # Bos kisisel organizasyon -- uyeligi ve organizasyonu temizle
        cur.execute("DELETE FROM org_members WHERE id = %s", (old_member_id,))
        cur.execute("DELETE FROM organizations WHERE id = %s", (old_org_id,))

    cur.execute(
        "INSERT INTO org_members (organization_id, username, role) VALUES (%s, %s, %s) RETURNING id",
        (org_id, user, role),
    )
    member_id = cur.fetchone()[0]
    for fid in (facility_ids or []):
        cur.execute(
            "INSERT INTO member_facilities (member_id, facility_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (member_id, fid),
        )
    for did in (department_ids or []):
        cur.execute(
            "INSERT INTO member_departments (member_id, department_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (member_id, did),
        )
    cur.execute("UPDATE org_invites SET accepted_at = now() WHERE id = %s", (invite_id,))
    cur.execute("SELECT name FROM organizations WHERE id = %s", (org_id,))
    org_name = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"message": f"{org_name} organizasyonuna katıldınız", "organization_name": org_name}


@app.patch("/organization/members/{member_id}")
def update_member(member_id: int, payload: MemberRoleRequest, user: str = Depends(require_org_admin)):
    if payload.role not in ORG_ROLES:
        raise HTTPException(status_code=400, detail="Geçersiz rol")
    membership = get_membership(user)
    org_id = membership["organization_id"]

    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT username FROM org_members WHERE id = %s AND organization_id = %s", (member_id, org_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Üye bulunamadı")

    # Son org_admin kendini dusuremesin -- organizasyon yonetimsiz kalirdi.
    if row[0] == user and payload.role != "org_admin":
        cur.execute(
            "SELECT count(*) FROM org_members WHERE organization_id = %s AND role = 'org_admin'",
            (org_id,),
        )
        if cur.fetchone()[0] <= 1:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Organizasyondaki son yönetici rolünü değiştiremez")

    cur.execute("UPDATE org_members SET role = %s WHERE id = %s", (payload.role, member_id))
    cur.execute("DELETE FROM member_facilities WHERE member_id = %s", (member_id,))
    cur.execute("DELETE FROM member_departments WHERE member_id = %s", (member_id,))

    if payload.role == "facility_manager":
        for fid in payload.facility_ids:
            cur.execute(
                "INSERT INTO member_facilities (member_id, facility_id) SELECT %s, id FROM facilities "
                "WHERE id = %s AND organization_id = %s ON CONFLICT DO NOTHING",
                (member_id, fid, org_id),
            )
    elif payload.role == "department_manager":
        for did in payload.department_ids:
            cur.execute(
                "INSERT INTO member_departments (member_id, department_id) "
                "SELECT %s, dep.id FROM departments dep JOIN facilities f ON f.id = dep.facility_id "
                "WHERE dep.id = %s AND f.organization_id = %s ON CONFLICT DO NOTHING",
                (member_id, did, org_id),
            )

    cur.close()
    conn.close()
    audit("member.update", actor=user, organization_id=membership["organization_id"],
          entity_type="member", entity_id=member_id, detail={"yeni_rol": payload.role})
    return {"message": "Üye güncellendi"}


@app.delete("/organization/members/{member_id}")
def remove_member(member_id: int, user: str = Depends(require_org_admin)):
    membership = get_membership(user)
    org_id = membership["organization_id"]
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM org_members WHERE id = %s AND organization_id = %s", (member_id, org_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Üye bulunamadı")
    if row[1] == "org_admin":
        cur.execute("SELECT count(*) FROM org_members WHERE organization_id = %s AND role = 'org_admin'", (org_id,))
        if cur.fetchone()[0] <= 1:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Organizasyondaki son yönetici çıkarılamaz")
    cur.execute("DELETE FROM org_members WHERE id = %s", (member_id,))
    cur.close()
    conn.close()
    audit("member.remove", actor=user, organization_id=membership["organization_id"],
          entity_type="member", entity_id=member_id)
    return {"message": "Üye çıkarıldı"}


# ---------- Abonelik ----------
# Cihaz basina ucretli, fatura/havale ile odenen, yonetici panelinden ELLE
# aktive edilen abonelik. Odeme saglayicisi entegrasyonu yok -- sema ondan
# bagimsiz tutuldu ki ileride iyzico/PayTR eklendiginde bu katman degismesin.
#
# SURE BITTIGINDE veri toplama DURMAZ: MQTT akisi ve alarm degerlendirmesi
# etkilenmiyor, yalnizca panelin veri ucnoktalari kilitleniyor. Musterinin
# gecmisini kaybettirmek geri donusu degersiz kilardi.

TRIAL_DAYS = 30
# Bitise bu kadar kala arayuz uyari gostersin.
SUBSCRIPTION_WARN_DAYS = 14
SUBSCRIPTION_STATUSES = ("trial", "active", "cancelled")


def _subscription_row(organization_id: int, cur) -> dict | None:
    cur.execute("""
        SELECT status, device_price, period, valid_until, device_limit, note, updated_at
        FROM subscriptions WHERE organization_id = %s
    """, (organization_id,))
    r = cur.fetchone()
    if not r:
        return None
    return {"status": r[0], "device_price": float(r[1]), "period": r[2],
            "valid_until": r[3], "device_limit": r[4], "note": r[5], "updated_at": r[6]}


def subscription_state(organization_id: int, cur) -> dict:
    """Aboneligin ETKIN durumu.

    'expired' veritabaninda saklanmiyor, her istekte valid_until'den
    hesaplaniyor: zamanlanmis bir is calismadi diye suresi dolmus bir abonelik
    yanlislikla acik kalmasin.
    """
    row = _subscription_row(organization_id, cur)
    if row is None:
        # Aboneligi hic olusturulmamis organizasyon (ornegin gocten once
        # kalmis bir kayit) -- kilitlemek yerine deneme suresi veriyoruz.
        return {"status": "none", "active": False, "valid_until": None,
                "days_left": None, "device_price": 0.0, "period": "yearly",
                "device_limit": None, "note": None, "warn": False}

    now = datetime.now(timezone.utc)
    valid_until = row["valid_until"]
    suresi_var = valid_until is not None and valid_until > now

    if row["status"] == "cancelled":
        etkin = "cancelled"
    elif not suresi_var:
        etkin = "expired"
    else:
        etkin = row["status"]  # 'trial' veya 'active'

    days_left = None
    if valid_until is not None:
        days_left = max(0, (valid_until - now).days)

    return {
        "status": etkin,
        "active": etkin in ("trial", "active"),
        "valid_until": valid_until,
        "days_left": days_left,
        "device_price": row["device_price"],
        "period": row["period"],
        "device_limit": row["device_limit"],
        "note": row["note"],
        "warn": etkin in ("trial", "active") and days_left is not None
                and days_left <= SUBSCRIPTION_WARN_DAYS,
    }


def ensure_subscription(organization_id: int, cur, created_by: str = "system"):
    """Yeni organizasyona deneme aboneligi acar. Zaten varsa hicbir sey yapmaz.

    RETURNING ile gercekten olusturulup olusturulmadigini ayirt ediyoruz:
    aksi halde her yonetici guncellemesinde denetim izine sahte bir 'created'
    kaydi dusuyordu ve iz, tahsilat mutabakati icin guvenilmez hale geliyordu.
    """
    cur.execute("""
        INSERT INTO subscriptions (organization_id, status, valid_until, updated_by)
        VALUES (%s, 'trial', now() + (%s * INTERVAL '1 day'), %s)
        ON CONFLICT (organization_id) DO NOTHING
        RETURNING valid_until
    """, (organization_id, TRIAL_DAYS, created_by))
    row = cur.fetchone()
    if row is None:
        return
    cur.execute("""
        INSERT INTO subscription_events (organization_id, action, valid_until, note, created_by)
        VALUES (%s, 'created', %s, %s, %s)
    """, (organization_id, row[0], f"{TRIAL_DAYS} günlük deneme", created_by))


def require_subscription(user: str = Depends(require_auth)) -> str:
    """Panelin VERI ucnoktalarini korur.

    Bilincli olarak korunmayanlar: /me, /devices, /organization, /subscription
    ve kimlik dogrulama. Kilitli musteri de neden kilitli oldugunu gorebilmeli
    ve cihaz listesi bos bir ekranla karsilasmamali.
    """
    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT organization_id FROM org_members WHERE username = %s LIMIT 1", (user,))
        row = cur.fetchone()
        if not row:
            return user  # organizasyonu olmayan kullanici -- erisim zaten bos doner
        state = subscription_state(row[0], cur)
    finally:
        cur.close()
        conn.close()
    if not state["active"]:
        raise HTTPException(
            status_code=402,
            detail="Aboneliğiniz sona erdi. Verileriniz korunuyor; erişimi yeniden "
                   "açmak için bizimle iletişime geçin.",
        )
    return user


@app.get("/subscription")
def get_subscription(user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT organization_id FROM org_members WHERE username = %s LIMIT 1", (user,))
        row = cur.fetchone()
        if not row:
            return {"status": "none", "active": False}
        state = subscription_state(row[0], cur)
        cur.execute("""
            SELECT count(*) FROM devices d
            JOIN facilities f ON f.id = d.facility_id
            WHERE f.organization_id = %s
        """, (row[0],))
        state["device_count"] = cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()
    return state


# ---------- Yönetici: abonelik yönetimi ----------

class SubscriptionUpdate(BaseModel):
    status: str = "active"
    months: int | None = None       # valid_until'i bugunden itibaren uzatir
    valid_until: str | None = None  # ya da dogrudan tarih (ISO)
    device_price: float | None = None
    period: str | None = None
    device_limit: int | None = None
    note: str | None = None


@app.get("/admin/subscriptions")
def admin_list_subscriptions(user: str = Depends(require_admin)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.id, o.name,
               count(DISTINCT d.device_id) AS cihaz,
               count(DISTINCT m.username) AS uye
        FROM organizations o
        LEFT JOIN facilities f ON f.organization_id = o.id
        LEFT JOIN devices d ON d.facility_id = f.id
        LEFT JOIN org_members m ON m.organization_id = o.id
        GROUP BY o.id, o.name ORDER BY o.name
    """)
    orgs = cur.fetchall()
    out = []
    for org_id, name, cihaz, uye in orgs:
        state = subscription_state(org_id, cur)
        out.append({
            "organization_id": org_id, "name": name,
            "device_count": cihaz, "member_count": uye,
            **{k: v for k, v in state.items() if k != "warn"},
            # Fatura tutari: cihaz sayisi x birim fiyat.
            "amount": round(cihaz * state["device_price"], 2),
        })
    cur.close()
    conn.close()
    return out


@app.put("/admin/subscriptions/{organization_id}")
def admin_update_subscription(organization_id: int, payload: SubscriptionUpdate,
                              user: str = Depends(require_admin)):
    if payload.status not in SUBSCRIPTION_STATUSES:
        raise HTTPException(status_code=400, detail="Geçersiz abonelik durumu")
    if payload.period is not None and payload.period not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Geçersiz dönem")
    if payload.months is not None and not 1 <= payload.months <= 120:
        raise HTTPException(status_code=400, detail="Süre 1 ile 120 ay arasında olmalı")
    if payload.device_price is not None and payload.device_price < 0:
        raise HTTPException(status_code=400, detail="Birim fiyat negatif olamaz")
    if payload.device_limit is not None and payload.device_limit < 0:
        raise HTTPException(status_code=400, detail="Cihaz limiti negatif olamaz")

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM organizations WHERE id = %s", (organization_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Organizasyon bulunamadı")

    ensure_subscription(organization_id, cur, user)
    mevcut = _subscription_row(organization_id, cur) or {}

    # Uzatma, kalan sureyi YAKMAZ: hala gecerliyse mevcut bitis tarihinin
    # uzerine ekleniyor, dolmussa bugunden baslatiliyor.
    yeni_bitis = None
    if payload.valid_until:
        try:
            yeni_bitis = datetime.fromisoformat(payload.valid_until.replace("Z", "+00:00"))
        except ValueError:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Geçersiz tarih")
    elif payload.months:
        now = datetime.now(timezone.utc)
        temel = mevcut.get("valid_until")
        baslangic = temel if (temel and temel > now) else now
        yeni_bitis = baslangic + timedelta(days=30 * payload.months)

    alanlar = ["status = %s", "updated_at = now()", "updated_by = %s"]
    degerler = [payload.status, user]
    for kolon, deger in (("device_price", payload.device_price),
                         ("period", payload.period),
                         ("device_limit", payload.device_limit),
                         ("note", payload.note),
                         ("valid_until", yeni_bitis)):
        if deger is not None:
            alanlar.insert(0, f"{kolon} = %s")
            degerler.insert(0, deger)
    degerler.append(organization_id)
    cur.execute(f"UPDATE subscriptions SET {', '.join(alanlar)} WHERE organization_id = %s",
                degerler)

    cur.execute("""
        SELECT count(DISTINCT d.device_id) FROM devices d
        JOIN facilities f ON f.id = d.facility_id WHERE f.organization_id = %s
    """, (organization_id,))
    cihaz = cur.fetchone()[0]
    guncel = _subscription_row(organization_id, cur)
    cur.execute("""
        INSERT INTO subscription_events
            (organization_id, action, valid_until, device_count, device_price, amount, note, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (organization_id,
          "cancelled" if payload.status == "cancelled" else ("extended" if yeni_bitis else "updated"),
          guncel["valid_until"], cihaz, guncel["device_price"],
          round(cihaz * guncel["device_price"], 2), payload.note, user))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Abonelik güncellendi"}


@app.get("/admin/subscriptions/{organization_id}/events")
def admin_subscription_events(organization_id: int, user: str = Depends(require_admin)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT action, valid_until, device_count, device_price, amount, note, created_at, created_by
        FROM subscription_events WHERE organization_id = %s
        ORDER BY created_at DESC LIMIT 50
    """, (organization_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"action": r[0], "valid_until": r[1], "device_count": r[2], "device_price": float(r[3] or 0),
             "amount": float(r[4] or 0), "note": r[5], "created_at": r[6], "created_by": r[7]}
            for r in rows]


@app.get("/admin/fleet")
def admin_fleet(user: str = Depends(require_admin)):
    """Uretici gorunumu: satilan/kurulan tum cihazlar, canli durumlari ve firmware
    dagilimi. Sahalik ariza tespiti icin 'ne zamandir susuyor' bilgisi kritik."""
    conn = db_connect()
    cur = conn.cursor()
    # Cihaz basina son olcum zamanini tek sorguda al -- her cihaz icin ayri
    # sorgu atmak filo buyudukce N+1'e donusurdu.
    cur.execute("""
        SELECT d.device_id, d.name, d.owner_username, d.created_at,
               s.fw_version, s.ct_ratio,
               m.last_seen,
               (SELECT count(*) FROM alarm_rules r WHERE r.device_id = d.device_id AND r.is_active) AS active_alarms
        FROM devices d
        LEFT JOIN device_settings s ON s.device_id = d.device_id
        LEFT JOIN (
            SELECT device_id, max(time) AS last_seen FROM measurements GROUP BY device_id
        ) m ON m.device_id = d.device_id
        ORDER BY d.created_at DESC NULLS LAST, d.id DESC
    """)
    rows = cur.fetchall()

    cur.execute("""
        SELECT s.fw_version, count(*) FROM devices d
        LEFT JOIN device_settings s ON s.device_id = d.device_id
        GROUP BY s.fw_version ORDER BY count(*) DESC
    """)
    firmware_rows = cur.fetchall()
    cur.close()
    conn.close()

    now = datetime.now(timezone.utc)
    devices = []
    counts = {"online": 0, "stale": 0, "dead": 0, "never": 0}
    for device_id, name, owner, created_at, fw, ct_ratio, last_seen, active_alarms in rows:
        if last_seen is None:
            status, minutes_silent = "never", None
        else:
            minutes_silent = (now - last_seen).total_seconds() / 60
            if minutes_silent <= FLEET_STALE_MINUTES:
                status = "online"
            elif minutes_silent <= FLEET_DEAD_HOURS * 60:
                status = "stale"
            else:
                status = "dead"
        counts[status] += 1
        devices.append({
            "device_id": device_id,
            "name": name,
            "owner": owner,
            "device_type": device_type_from_id(device_id),
            "claimed_at": created_at.isoformat() if created_at else None,
            "fw_version": fw,
            "ct_ratio": ct_ratio,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "minutes_silent": round(minutes_silent) if minutes_silent is not None else None,
            "status": status,
            "active_alarms": active_alarms,
        })

    return {
        "total": len(devices),
        "counts": counts,
        "firmware_distribution": [
            {"version": v or "(bilinmiyor)", "count": c} for v, c in firmware_rows
        ],
        "devices": devices,
    }


@app.get("/firmware/{device_type}/latest")
def get_latest_firmware(device_type: str, user: str = Depends(require_auth)):
    if device_type not in VALID_DEVICE_TYPES:
        raise HTTPException(status_code=400, detail="Geçersiz cihaz tipi")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT version, filename, sha256, uploaded_at FROM firmware_builds "
        "WHERE device_type = %s ORDER BY uploaded_at DESC LIMIT 1",
        (device_type,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {
        "version": row[0],
        "url": f"{SITE_URL}/api/firmware-files/{row[1]}",
        "sha256": row[2],
        "uploaded_at": row[3].isoformat(),
    }

@app.get("/devices/{device_id}/firmware")
def get_device_firmware(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    device_type = device_type_from_id(device_id)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT fw_version FROM device_settings WHERE device_id = %s", (device_id,))
    row = cur.fetchone()
    current_version = row[0] if row else None
    latest = None
    if device_type:
        cur.execute(
            "SELECT version FROM firmware_builds WHERE device_type = %s ORDER BY uploaded_at DESC LIMIT 1",
            (device_type,),
        )
        latest_row = cur.fetchone()
        latest = latest_row[0] if latest_row else None
    cur.close()
    conn.close()
    return {
        "current_version": current_version,
        "latest_version": latest,
        "update_available": bool(latest and latest != current_version),
    }

@app.post("/devices/{device_id}/ota")
def trigger_ota(device_id: str, user: str = Depends(require_auth)):
    audit("device.ota", actor=user, entity_type="device", entity_id=device_id)
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    check_rate_limit(f"ota:{user}", max_attempts=10, window_seconds=60 * 60)
    device_type = device_type_from_id(device_id)
    if not device_type:
        raise HTTPException(status_code=400, detail="Cihaz tipi belirlenemedi")

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT version, filename, sha256 FROM firmware_builds WHERE device_type = %s ORDER BY uploaded_at DESC LIMIT 1",
        (device_type,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Bu cihaz tipi için yüklenmiş firmware yok")

    version, filename, sha256 = row
    payload = json.dumps({
        "url": f"{SITE_URL}/api/firmware-files/{filename}",
        "version": version,
        "sha256": sha256,
    })
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        connected_evt = threading.Event()
        client.on_connect = lambda c, u, f, rc, p=None: connected_evt.set()
        client.connect(MQTT_BROKER, 1883, 10)
        client.loop_start()
        connected_evt.wait(timeout=5)
        client.publish(f"{MQTT_TOPIC_PREFIX}/{device_id}/ota", payload)
        time.sleep(0.3)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print("OTA tetikleme hatasi:", e)
        raise HTTPException(status_code=502, detail="OTA komutu cihaza gönderilemedi")
    return {"message": "OTA güncellemesi tetiklendi", "version": version}

# ---------- Alarm sistemi ----------
# metric -> (measurement payload alan oneki, birim, insan-okur ad, ondalik basamak)
ALARM_METRICS = {
    "voltage":   ("v",   "V",  "Gerilim", 1),
    "current":   ("i",   "A",  "Akım", 3),
    "power":     ("p",   "W",  "Aktif Güç", 0),
    "pf":        ("pf",  "",   "Güç Faktörü", 2),
    "frequency": ("f",   "Hz", "Frekans", 2),
    "thd":       ("thd", "%",  "THD (Akım)", 2),
}
ALARM_PHASES = {"L1": "1", "L2": "2", "L3": "3"}
# Esik civarinda salinim yapan degerlerde surekli tetikle/coz dongusune (ve e-posta
# spamine) girmemek icin, alarm ancak deger esikten %2 uzaklasinca "cozuldu" sayilir.
ALARM_DEADBAND = 0.02

class AlarmRuleRequest(BaseModel):
    metric: str
    phase: str = "any"
    condition: str = "gt"
    threshold: float | None = None
    offline_minutes: int | None = None


def alarm_rule_label(metric: str, phase: str, condition: str, threshold, offline_minutes) -> str:
    if metric == "offline":
        return f"Cihaz {offline_minutes} dakikadır veri göndermiyor"
    _, unit, name, digits = ALARM_METRICS[metric]
    yon = "üstünde" if condition == "gt" else "altında"
    faz = "herhangi bir faz" if phase == "any" else phase
    esik = f"{threshold:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{threshold:.0f}"
    return f"{name} ({faz}) {esik} {unit} {yon}".replace("  ", " ")


# Kurallar her canli mesajda (cihaz basina ~2 saniyede bir) degerlendiriliyor; her
# seferinde DB'ye gitmemek icin kisa omurlu bir onbellek tutuluyor. Kural
# eklendiginde/silindiginde invalidate_alarm_cache() ile aninda tazeleniyor.
_alarm_cache = {"rules": {}, "loaded_at": 0.0}
_alarm_cache_lock = threading.Lock()
ALARM_CACHE_TTL = 30.0


def invalidate_alarm_cache():
    with _alarm_cache_lock:
        _alarm_cache["loaded_at"] = 0.0


def get_alarm_rules(device_id: str):
    with _alarm_cache_lock:
        fresh = (time.time() - _alarm_cache["loaded_at"]) < ALARM_CACHE_TTL
        if fresh:
            return _alarm_cache["rules"].get(device_id, [])
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, device_id, metric, phase, condition, threshold, offline_minutes, is_active
            FROM alarm_rules WHERE enabled
        """)
        by_device = {}
        for r in cur.fetchall():
            by_device.setdefault(r[1], []).append({
                "id": r[0], "device_id": r[1], "metric": r[2], "phase": r[3],
                "condition": r[4], "threshold": r[5], "offline_minutes": r[6], "is_active": r[7],
            })
        cur.close()
        conn.close()
    except Exception as e:
        logger.error("Alarm kurallari yuklenemedi: %s", e)
        return []
    with _alarm_cache_lock:
        _alarm_cache["rules"] = by_device
        _alarm_cache["loaded_at"] = time.time()
    return by_device.get(device_id, [])


def _set_rule_active(rule_id: int, active: bool):
    with _alarm_cache_lock:
        for rules in _alarm_cache["rules"].values():
            for r in rules:
                if r["id"] == rule_id:
                    r["is_active"] = active


def alarm_notify(device_id: str, subject: str, body: str):
    """Alarmi e-posta ve push ile duyurur. MQTT dongusunu bloklamamak icin
    ayri thread'de.

    Iki kanal da AYNI kapsama gidiyor: cihaza erisimi olan herkes. (E-posta
    eskiden yalnizca cihaz sahibine gidiyordu -- organizasyon hiyerarsisinden
    onceki davranistan kalmaydi ve tesis/bolum yoneticileri alarmlari hic
    gormuyordu.)

    Alicilara ayri ayri gonderiliyor, tek e-postada coklu alici olarak degil:
    ayni organizasyondaki kisilerin adreslerini birbirine gostermeye gerek yok.
    """
    def _send():
        device_name = device_id
        try:
            conn = db_connect()
            cur = conn.cursor()
            cur.execute("SELECT name FROM devices WHERE device_id = %s", (device_id,))
            row = cur.fetchone()
            if row:
                device_name = row[0]

            izinli = users_with_device_access(device_id, cur)
            alicilar = []
            if izinli:
                cur.execute("""
                    SELECT email FROM users
                    WHERE username = ANY(%s) AND alarm_email = true AND is_verified = true
                      AND email IS NOT NULL AND email <> ''
                """, (izinli,))
                alicilar = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()

            if not alicilar:
                logger.warning("Alarm e-postasi icin alici yok: %s", device_id)
            for email in alicilar:
                try:
                    resend.Emails.send({
                        "from": RESEND_FROM,
                        "to": [email],
                        "subject": f"{subject} — {device_name}",
                        "html": (
                            f"<p><b>{device_name}</b> cihazında alarm durumu:</p>"
                            f"<p style='font-size:15px'>{body}</p>"
                            f"<p><a href='{SITE_URL}'>Panoyu aç</a></p>"
                            f"<p style='font-size:12px;color:#6B7A90'>Bu e-postayı almak "
                            f"istemiyorsanız hesap sayfanızdan alarm e-postalarını kapatabilirsiniz.</p>"
                        ),
                    })
                except Exception as e:
                    # Bir alicinin basarisiz olmasi digerlerini engellemesin.
                    logger.error("Alarm e-postasi gonderilemedi (%s): %s", email, e)
        except Exception as e:
            logger.error("Alarm e-posta akisi hatasi (%s): %s", device_id, e)

        # Push, e-postadan bagimsiz: e-posta gonderimi patlasa bile bildirim
        # gitmeli (ve tersi).
        try:
            push_notify(device_id, f"{subject} — {device_name}", body)
        except Exception as e:
            logger.error("Alarm push bildirimi gonderilemedi (%s): %s", device_id, e)

    threading.Thread(target=_send, daemon=True).start()


def _alarm_values(metric: str, phase: str, data: dict):
    """Canli payload'dan (faz_adi, deger) ciftlerini cikarir."""
    prefix = ALARM_METRICS[metric][0]
    phases = ALARM_PHASES.items() if phase == "any" else [(phase, ALARM_PHASES[phase])]
    out = []
    for label, idx in phases:
        value = data.get(f"{prefix}{idx}")
        if isinstance(value, (int, float)):
            out.append((label, float(value)))
    return out


def _crosses(condition: str, value: float, threshold: float) -> bool:
    return value > threshold if condition == "gt" else value < threshold


def _recovered(condition: str, value: float, threshold: float) -> bool:
    band = abs(threshold) * ALARM_DEADBAND or 0.01
    return value < (threshold - band) if condition == "gt" else value > (threshold + band)


def evaluate_alarms(device_id: str, data: dict, cur):
    """Her canli olcum mesajinda cagrilir; esik asimlarini tetikler/cozer."""
    for rule in get_alarm_rules(device_id):
        if rule["metric"] == "offline":
            continue  # ayri watchdog thread'i tarafindan degerlendiriliyor
        try:
            values = _alarm_values(rule["metric"], rule["phase"], data)
        except KeyError:
            continue
        if not values:
            continue

        threshold = rule["threshold"]
        breached = [(p, v) for p, v in values if _crosses(rule["condition"], v, threshold)]

        if breached and not rule["is_active"]:
            phase_label, value = max(breached, key=lambda pv: abs(pv[1] - threshold))
            _, unit, name, digits = ALARM_METRICS[rule["metric"]]
            message = (
                f"{name} ({phase_label}): {value:.{digits}f} {unit} — "
                f"eşik {threshold:.{digits}f} {unit} {'üstünde' if rule['condition'] == 'gt' else 'altında'}"
            )
            cur.execute("""
                INSERT INTO alarm_events (rule_id, device_id, trigger_value, message)
                VALUES (%s, %s, %s, %s)
            """, (rule["id"], device_id, value, message))
            cur.execute("UPDATE alarm_rules SET is_active = true, last_triggered_at = now() WHERE id = %s", (rule["id"],))
            _set_rule_active(rule["id"], True)
            logger.info("ALARM tetiklendi %s: %s", device_id, message)
            alarm_notify(device_id, "🔴 Alarm", message)

        elif rule["is_active"] and all(_recovered(rule["condition"], v, threshold) for _, v in values):
            cur.execute("""
                UPDATE alarm_events SET resolved_at = now()
                WHERE rule_id = %s AND resolved_at IS NULL
            """, (rule["id"],))
            cur.execute("UPDATE alarm_rules SET is_active = false WHERE id = %s", (rule["id"],))
            _set_rule_active(rule["id"], False)
            _, unit, name, digits = ALARM_METRICS[rule["metric"]]
            logger.info("ALARM normale dondu %s: %s", device_id, name)
            alarm_notify(device_id, "✅ Alarm normale döndü", f"{name} tekrar normal aralıkta.")


# Cevrimdisi kademeleri (son veriden bu yana gecen dakika). Cihaz her kademeyi
# gectiginde BIR bildirim gonderilir; sonuncudan sonra susulur. Sonsuza kadar
# bildirim gondermek, bildirimlerin tamamen yok sayilmasiyla biter.
OFFLINE_ESCALATION_MINUTES = [15, 60, 360, 720, 1440, 10080, 43200]


def _offline_milestones(offline_minutes: int) -> list[int]:
    """Bu kural icin bildirim gonderilecek dakika esikleri.

    Ilk esik kuralin kendi `offline_minutes` degeri -- cihazi cevrimdisi
    saymadan once beklenen sure. Bundan kucuk kademeler atlanir, esit olan
    tekrarlanmaz: kural 15 dakikaysa "cevrimdisi oldu" ile "15 dakikadir
    cevrimdisi" ayni andir ve iki kez bildirilmemelidir.
    """
    return sorted({offline_minutes} | {m for m in OFFLINE_ESCALATION_MINUTES if m > offline_minutes})


def _offline_sure_metni(dakika: int) -> str:
    if dakika < 60:
        return f"{dakika} dakikadır"
    if dakika < 1440:
        saat = dakika // 60
        return f"{saat} saattir"
    if dakika < 10080:
        return f"{dakika // 1440} gündür"
    if dakika < 43200:
        return f"{dakika // 10080} haftadır"
    return f"{dakika // 43200} aydır"


def _offline_karar(gecen_dk: int, offline_minutes: int, stage: int) -> dict:
    """Kademe karari -- sonsuz dongunun disinda, test edilebilir olsun diye.

    stage: bu cevrimdisi doneminde kac kademe bildirildi.
    """
    kademeler = _offline_milestones(offline_minutes)
    gecilen = sum(1 for m in kademeler if gecen_dk >= m)
    if gecilen == 0 or gecilen <= stage:
        # gecilen <= stage: bu kademe zaten bildirildi. Son kademeden sonra da
        # hep buraya dusulur -- "1 aydan sonra sus" davranisi buradan geliyor.
        return {"bildir": False, "kademe": gecilen, "toplam": len(kademeler)}
    return {
        "bildir": True,
        "kademe": gecilen,
        "toplam": len(kademeler),
        # Bildirim ZAMANINI kademe belirler, ama metin GERCEK gecen sureyi
        # soyler. Kademe etiketi kullanilsaydi 5,7 saattir kapali bir cihaz
        # icin "1 saattir" yazardi -- 360 dakika kademesi henuz gecilmedigi icin.
        "sure": _offline_sure_metni(gecen_dk),
        "son_mu": gecilen == len(kademeler),
    }


def alarm_offline_watchdog():
    """Cihazlarin veri gondermeyi kesip kesmedigini periyodik olarak kontrol eder."""
    while True:
        time.sleep(60)
        try:
            conn = db_connect()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                SELECT r.id, r.device_id, r.offline_minutes, r.is_active, r.offline_stage,
                       r.created_at,
                       (SELECT max(time) FROM measurements m WHERE m.device_id = r.device_id)
                FROM alarm_rules r
                WHERE r.enabled AND r.metric = 'offline'
            """)
            simdi = datetime.now(timezone.utc)
            for rule_id, device_id, minutes, is_active, stage, created_at, last_seen in cur.fetchall():
                # Cihaz hic veri gondermediyse kuralin olusturulma zamani referans
                # alinir. Yoksa "son veri yok" sonsuz sure demek olur ve yeni
                # eklenen bir cihaza aninda "1 aydir cevrimdisi" bildirimi gider.
                referans = last_seen or created_at
                gecen_dk = int((simdi - referans).total_seconds() // 60)
                karar = _offline_karar(gecen_dk, minutes, stage)
                gecilen = karar["kademe"]

                if gecilen == 0:
                    if is_active:
                        cur.execute("UPDATE alarm_events SET resolved_at = now() "
                                    "WHERE rule_id = %s AND resolved_at IS NULL", (rule_id,))
                        cur.execute("UPDATE alarm_rules SET is_active = false, offline_stage = 0 "
                                    "WHERE id = %s", (rule_id,))
                        logger.info("ALARM (cevrimdisi) cozuldu %s", device_id)
                        alarm_notify(device_id, "✅ Cihaz tekrar çevrimiçi",
                                     "Cihaz yeniden veri göndermeye başladı.")
                    continue

                if not karar["bildir"]:
                    continue

                sure = karar["sure"]
                gecmis = "hiç veri alınmadı" if last_seen is None else f"son veri: {last_seen:%d.%m.%Y %H:%M}"
                message = f"Cihaz {sure} veri göndermiyor ({gecmis})"

                # Kademeler yeni kayit ACMAZ: tek bir cevrimdisi donemi panelde tek
                # aktif alarm olarak gorunmeli, rozet 7 gostermemeli. Karar
                # `stage`e degil ACIK KAYDIN VARLIGINA bakiyor -- stage 0 olup da
                # acik kayit bulunan bir durum gercekten yasandi (goc sonrasi:
                # is_active=true, offline_stage=0) ve ikinci bir kayit acilmisti.
                cur.execute("UPDATE alarm_events SET message = %s "
                            "WHERE rule_id = %s AND resolved_at IS NULL", (message, rule_id))
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO alarm_events (rule_id, device_id, message) "
                                "VALUES (%s, %s, %s)", (rule_id, device_id, message))

                cur.execute("UPDATE alarm_rules SET is_active = true, offline_stage = %s, "
                            "last_triggered_at = now() WHERE id = %s", (gecilen, rule_id))

                son_mu = karar["son_mu"]
                logger.info("ALARM (cevrimdisi) kademe %s/%s %s", gecilen, karar["toplam"], device_id)
                alarm_notify(
                    device_id, "🔴 Cihaz çevrimdışı",
                    message + ("\n\nBu son hatırlatma — bu cihaz için yeniden çevrimiçi "
                               "olana kadar başka bildirim gönderilmeyecek." if son_mu else ""),
                )

            invalidate_alarm_cache()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error("Cevrimdisi alarm kontrolu hatasi: %s", e)


@app.get("/health")
def health():
    """Dağıtım doğrulaması için: hangi ortam, hangi veritabanı, ayakta mı.

    Kimlik doğrulaması istemez ama hassas hiçbir şey de açmaz -- sürüm veya
    sır değil, yalnızca ortamın kendini doğru tanıyıp tanımadığı. Staging'e
    dağıttığını sanıp üretime dağıtmak bu uç nokta olmadan sessizce mümkün.
    """
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        db_ok = True
    except Exception as e:
        logger.error("Saglik kontrolu: veritabanina ulasilamadi: %s", e)
        db_ok = False
    return {
        "ortam": "staging" if IS_STAGING else "uretim",
        "veritabani": DB_CONFIG.get("dbname"),
        "veritabani_erisimi": db_ok,
        "dis_bildirimler": "kapali" if IS_STAGING else "acik",
    }


@app.get("/devices/{device_id}/alarm-rules")
def list_alarm_rules(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, metric, phase, condition, threshold, offline_minutes, enabled, is_active, last_triggered_at
        FROM alarm_rules WHERE device_id = %s ORDER BY id
    """, (device_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0], "metric": r[1], "phase": r[2], "condition": r[3],
            "threshold": r[4], "offline_minutes": r[5], "enabled": r[6],
            "is_active": r[7],
            "last_triggered_at": r[8].isoformat() if r[8] else None,
            "label": alarm_rule_label(r[1], r[2], r[3], r[4], r[5]),
        }
        for r in rows
    ]


@app.post("/devices/{device_id}/alarm-rules")
def create_alarm_rule(device_id: str, req: AlarmRuleRequest, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")

    if req.metric == "offline":
        if not req.offline_minutes or not (1 <= req.offline_minutes <= 1440):
            raise HTTPException(status_code=400, detail="Süre 1-1440 dakika arasında olmalı")
        threshold, offline_minutes = None, req.offline_minutes
    else:
        if req.metric not in ALARM_METRICS:
            raise HTTPException(status_code=400, detail="Geçersiz ölçüm tipi")
        if req.phase not in ("any", *ALARM_PHASES):
            raise HTTPException(status_code=400, detail="Geçersiz faz")
        if req.condition not in ("gt", "lt"):
            raise HTTPException(status_code=400, detail="Geçersiz koşul")
        if req.threshold is None:
            raise HTTPException(status_code=400, detail="Eşik değeri gerekli")
        threshold, offline_minutes = req.threshold, None

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM alarm_rules WHERE device_id = %s", (device_id,))
    if cur.fetchone()[0] >= 20:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Bir cihaz için en fazla 20 alarm kuralı tanımlanabilir")
    cur.execute("""
        INSERT INTO alarm_rules (device_id, metric, phase, condition, threshold, offline_minutes)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """, (device_id, req.metric, req.phase, req.condition, threshold, offline_minutes))
    rule_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    invalidate_alarm_cache()
    return {"id": rule_id, "label": alarm_rule_label(req.metric, req.phase, req.condition, threshold, offline_minutes)}


@app.patch("/alarm-rules/{rule_id}")
def update_alarm_rule(rule_id: int, enabled: bool, user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT device_id FROM alarm_rules WHERE id = %s", (rule_id,))
    row = cur.fetchone()
    if not row or not is_device_owner(user, row[0]):
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Bu kurala erişiminiz yok")
    # Kural kapatilirken aktif alarm durumu da sifirlanir, aksi halde tekrar
    # acildiginda "zaten aktif" sanilip yeni bildirim gonderilmez.
    cur.execute("UPDATE alarm_rules SET enabled = %s, is_active = false WHERE id = %s", (enabled, rule_id))
    conn.commit()
    cur.close()
    conn.close()
    invalidate_alarm_cache()
    return {"message": "Güncellendi"}


@app.delete("/alarm-rules/{rule_id}")
def delete_alarm_rule(rule_id: int, user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT device_id FROM alarm_rules WHERE id = %s", (rule_id,))
    row = cur.fetchone()
    if not row or not is_device_owner(user, row[0]):
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Bu kurala erişiminiz yok")
    cur.execute("DELETE FROM alarm_rules WHERE id = %s", (rule_id,))
    conn.commit()
    cur.close()
    conn.close()
    invalidate_alarm_cache()
    return {"message": "Silindi"}


@app.get("/devices/{device_id}/alarm-events")
def list_alarm_events(device_id: str, limit: int = 50, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    limit = max(1, min(limit, 200))
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, rule_id, triggered_at, resolved_at, trigger_value, message
        FROM alarm_events WHERE device_id = %s ORDER BY triggered_at DESC LIMIT %s
    """, (device_id, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0], "rule_id": r[1],
            "triggered_at": r[2].isoformat() if r[2] else None,
            "resolved_at": r[3].isoformat() if r[3] else None,
            "trigger_value": r[4], "message": r[5],
        }
        for r in rows
    ]

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    phone: str
    password: str

# ---------- E-posta doğrulama + Google Sheets kaydı ----------
def send_verification_email(to_email: str, token: str):
    verify_url = f"{SITE_URL}/api/verify?token={token}"
    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Binary Enerji - Hesap Doğrulama",
            "html": f'<p>Hesabınızı doğrulamak için <a href="{verify_url}">tıklayın</a>.</p>',
        })
    except Exception as e:
        print("E-posta gonderme hatasi:", e)
        raise HTTPException(status_code=502, detail="Doğrulama e-postası gönderilemedi, lütfen daha sonra tekrar deneyin")

def append_to_google_sheet(c: RegisterRequest):
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        sheet = gspread.authorize(creds).open_by_key(GOOGLE_SHEET_ID).sheet1
        sheet.append_row([
            c.first_name, c.last_name, c.username, c.email, c.phone,
            datetime.utcnow().isoformat(),
        ])
    except Exception as e:
        print(f"Google Sheets yazma hatasi: {type(e).__name__}: {e!r}")

@app.post("/login")
def login(credentials: LoginRequest, request: Request):
    check_rate_limit(f"login:{client_ip(request)}", max_attempts=15, window_seconds=15 * 60)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT password_hash, is_verified FROM users WHERE username = %s", (credentials.username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not bcrypt.checkpw(credentials.password.encode(), row[0].encode()):
        audit("auth.login_failed", actor=credentials.username, request=request,
              detail={"sebep": "hatalı kimlik bilgisi"})
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")
    if not row[1]:
        raise HTTPException(status_code=403, detail="Hesabınız henüz doğrulanmadı, e-postanızı kontrol edin")
    return {"token": create_token(credentials.username)}

@app.post("/register")
def register(credentials: RegisterRequest, request: Request):
    check_rate_limit(f"register:{client_ip(request)}", max_attempts=10, window_seconds=60 * 60)
    if len(credentials.username) < 3:
        raise HTTPException(status_code=400, detail="Kullanıcı adı en az 3 karakter olmalı")
    if len(credentials.password) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalı")
    if "@" not in credentials.email:
        raise HTTPException(status_code=400, detail="Geçersiz e-posta adresi")

    password_hash = bcrypt.hashpw(credentials.password.encode(), bcrypt.gensalt()).decode()
    token = secrets.token_urlsafe(32)
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO users
               (username, password_hash, first_name, last_name, email, phone, verification_token, is_verified)
               VALUES (%s, %s, %s, %s, %s, %s, %s, false)""",
            (credentials.username, password_hash, credentials.first_name, credentials.last_name,
             credentials.email, credentials.phone, token),
        )
        # Her yeni kullanici kendi organizasyonunun yoneticisi olarak baslar ve
        # varsayilan bir "Merkez" tesisi alir. Boylece tek cihazli kucuk musteri
        # hiyerarsiyi hic gormeden calismaya devam eder; cok tesisli musteri ise
        # ustune tesis/bolum ekler.
        full_name = " ".join(x for x in [credentials.first_name, credentials.last_name] if x).strip()
        cur.execute(
            "INSERT INTO organizations (name) VALUES (%s) RETURNING id",
            (f"{full_name or credentials.username} Organizasyonu",),
        )
        org_id = cur.fetchone()[0]
        cur.execute("INSERT INTO facilities (organization_id, name) VALUES (%s, 'Merkez')", (org_id,))
        cur.execute(
            "INSERT INTO org_members (organization_id, username, role) VALUES (%s, %s, 'org_admin')",
            (org_id, credentials.username),
        )
        # Yeni organizasyon deneme suresiyle basliyor -- kayit olan kisi
        # satis surecini beklemeden sistemi kullanabilsin.
        ensure_subscription(org_id, cur, credentials.username)
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı, e-posta veya telefon numarası zaten kayıtlı")
    finally:
        cur.close()
        conn.close()

    send_verification_email(credentials.email, token)
    append_to_google_sheet(credentials)
    return {"message": "Kayıt başarılı, e-postanızı kontrol edip hesabınızı doğrulayın"}

@app.get("/verify", response_class=HTMLResponse)
def verify_email(token: str):
    conn = db_connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_verified = true, verification_token = NULL WHERE verification_token = %s RETURNING username",
        (token,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return HTMLResponse(
            "<h2>Geçersiz veya süresi dolmuş doğrulama linki.</h2>", status_code=400
        )
    return HTMLResponse(
        f"<h2>E-posta doğrulandı, giriş yapabilirsiniz.</h2>"
        f'<a href="{SITE_URL}">Dashboard\'a git</a>'
    )

# ---------- REST: Geçmiş veri sorgusu ----------
@app.get("/measurements")
def get_measurements(device_id: str, minutes: int = 60, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    since = datetime.utcnow() - timedelta(minutes=minutes)
    cur.execute("""
        SELECT time, v1, i1, p1, q1, s1, f1, cos1, pf1, thd1, thvd1,
               v2, i2, p2, q2, s2, f2, cos2, pf2, thd2, thvd2,
               v3, i3, p3, q3, s3, f3, cos3, pf3, thd3, thvd3,
               v_neutral, i_neutral
        FROM measurements
        WHERE time > %s AND device_id = %s
        ORDER BY time ASC
    """, (since, device_id))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["time", "v1", "i1", "p1", "q1", "s1", "f1", "cos1", "pf1", "thd1", "thvd1",
               "v2", "i2", "p2", "q2", "s2", "f2", "cos2", "pf2", "thd2", "thvd2",
               "v3", "i3", "p3", "q3", "s3", "f3", "cos3", "pf3", "thd3", "thvd3",
               "vN", "iN"]
    return [dict(zip(columns, row)) for row in rows]

# ---------- REST: Toplam enerji sayaçları ----------
@app.get("/energy")
def get_energy(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT active_wh_tuketim, inductive_varh_tuketim, capacitive_varh_tuketim,
               active_wh_uretim, inductive_varh_uretim, capacitive_varh_uretim, time
        FROM device_energy
        WHERE device_id = %s
        ORDER BY time DESC LIMIT 1
    """, (device_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    columns = ["active_wh_tuketim", "inductive_varh_tuketim", "capacitive_varh_tuketim",
               "active_wh_uretim", "inductive_varh_uretim", "capacitive_varh_uretim", "time"]
    return dict(zip(columns, row))

# ---------- Saatlik enerji ozeti (device_energy_hourly) ----------
# Ham device_energy'de saniyeler mertebesinde kayit var; saatlik artislar
# TimescaleDB surekli toplamasinda (device_energy_hourly) onceden hesaplaniyor.
# Boylece hem sorgular ham veriyi taramiyor hem de 180 gunluk saklama suresi
# dolup ham kayitlar silindiginde gecmis raporlar bozulmuyor.
#
# Ozet, her saat icin first/last/max ucusunu birden tutuyor. Nedeni: cihaz
# sayaci on panelden sifirlanabiliyor. Duz "last - onceki last" farki,
# sifirlamanin oldugu saatte buyuk negatif cikip sifira kirpiliyor ve o saatin
# TUM tuketimi kayboluyor (olculen bir ornekte 380 Wh'lik gercek tuketim 0
# gorunuyordu). Asagidaki formul o saati de dogru hesapliyor:
#     saat ici artis  : last - first            (normal saat)
#                     : (max - first) + last    (saat icinde sifirlanmissa;
#                                                sayacin ~0'a dondugu varsayilir)
#     saatler arasi   : GREATEST(first - onceki last, 0)
# Pencere fonksiyonu icin sorguda "WINDOW w AS (ORDER BY bucket)" tanimli olmali.
_ENERGY_COLUMNS = [
    # (ozetteki kisa ad, kumulatif sutun adi)
    ("active_tuketim", "active_wh_tuketim"),
    ("inductive_tuketim", "inductive_varh_tuketim"),
    ("capacitive_tuketim", "capacitive_varh_tuketim"),
    ("active_uretim", "active_wh_uretim"),
    ("inductive_uretim", "inductive_varh_uretim"),
    ("capacitive_uretim", "capacitive_varh_uretim"),
]


def _hourly_delta_sql(short: str, full: str) -> str:
    return (
        f"(GREATEST(first_{short} - LAG({full}) OVER w, 0)"
        f" + CASE WHEN {full} >= first_{short} THEN {full} - first_{short}"
        f" ELSE (max_{short} - first_{short}) + {full} END)"
    )


@app.get("/energy/hourly")
def get_energy_hourly(device_id: str, format: str = "json", days: int = 7, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    days = max(1, min(days, 90))
    conn = db_connect()
    cur = conn.cursor()
    select_parts = ", ".join(
        f"{full} AS {short}, {_hourly_delta_sql(short, full)} AS delta_{short}"
        for short, full in _ENERGY_COLUMNS
    )
    # Alt sorguya sarmak zorunlu: gercek zamanli surekli toplama gorunumu ile
    # pencere fonksiyonu bir arada oldugunda planlayici dis "ORDER BY bucket DESC"i
    # dusuruyor ve sonuc artan sirada donuyordu (arayuz en yeniyi basta bekliyor).
    cur.execute(f"""
        SELECT * FROM (
            SELECT bucket, reading_time, {select_parts}
            FROM device_energy_hourly
            WHERE device_id = %s AND bucket > now() - (%s * interval '1 day')
            WINDOW w AS (ORDER BY bucket)
        ) t
        ORDER BY bucket DESC
    """, (device_id, days))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["bucket", "reading_time",
               "active_tuketim", "delta_active_tuketim",
               "inductive_tuketim", "delta_inductive_tuketim",
               "capacitive_tuketim", "delta_capacitive_tuketim",
               "active_uretim", "delta_active_uretim",
               "inductive_uretim", "delta_inductive_uretim",
               "capacitive_uretim", "delta_capacitive_uretim"]

    if format == "xlsx":
        def kwh(wh):
            return round(wh / 1000, 3) if wh is not None else None

        wb = Workbook()
        ws = wb.active
        ws.title = "Saatlik Enerji"

        headers = [
            "Tarih", "Saat",
            "Aktif Artış (kWh)", "Aktif Endeks (kWh)",
            "Endüktif Artış (kVArh)", "Endüktif Endeks (kVArh)",
            "Kapasitif Artış (kVArh)", "Kapasitif Endeks (kVArh)",
            "Aktif Artış - Üretim (kWh)", "Aktif Endeks - Üretim (kWh)",
            "Endüktif Artış - Üretim (kVArh)", "Endüktif Endeks - Üretim (kVArh)",
            "Kapasitif Artış - Üretim (kVArh)", "Kapasitif Endeks - Üretim (kVArh)",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        for row in rows:
            r = dict(zip(columns, row))
            reading_time = r["reading_time"]
            ws.append([
                reading_time.strftime("%d.%m.%Y") if reading_time else "",
                reading_time.strftime("%H:%M") if reading_time else "",
                kwh(r["delta_active_tuketim"]), kwh(r["active_tuketim"]),
                kwh(r["delta_inductive_tuketim"]), kwh(r["inductive_tuketim"]),
                kwh(r["delta_capacitive_tuketim"]), kwh(r["capacitive_tuketim"]),
                kwh(r["delta_active_uretim"]), kwh(r["active_uretim"]),
                kwh(r["delta_inductive_uretim"]), kwh(r["inductive_uretim"]),
                kwh(r["delta_capacitive_uretim"]), kwh(r["capacitive_uretim"]),
            ])

        for i, header in enumerate(headers, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(12, len(header) * 0.9)

        buffer = io.BytesIO()
        wb.save(buffer)
        filename = f"{device_id}-saatlik-enerji.xlsx"
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return [dict(zip(columns, row)) for row in rows]

# ---------- REST: Toplam ve Ortalama Değerler (ANL21) ----------
STATS_COLUMNS = [
    "p_active_imp", "p_reactive_imp", "p_inductive_imp", "p_capacitive_imp", "p_apparent_imp",
    "p_active_exp", "p_reactive_exp", "p_inductive_exp", "p_capacitive_exp", "p_apparent_exp",
    "avg_current_imp", "avg_active_power_imp", "avg_cos_imp", "avg_tan_imp", "avg_pf_imp",
    "avg_current_exp", "avg_active_power_exp", "avg_cos_exp", "avg_tan_exp", "avg_pf_exp",
    "avg_voltage_ln", "avg_voltage_ll", "avg_frequency", "avg_thid", "avg_thvd",
]
# Firmware statsPayload JSON alan adlari (camelCase) — STATS_COLUMNS ile ayni sirada.
STATS_JSON_KEYS = [
    "pActiveImp", "pReactiveImp", "pInductiveImp", "pCapacitiveImp", "pApparentImp",
    "pActiveExp", "pReactiveExp", "pInductiveExp", "pCapacitiveExp", "pApparentExp",
    "avgCurrentImp", "avgActivePowerImp", "avgCosImp", "avgTanImp", "avgPfImp",
    "avgCurrentExp", "avgActivePowerExp", "avgCosExp", "avgTanExp", "avgPfExp",
    "avgVoltageLN", "avgVoltageLL", "avgFrequency", "avgThid", "avgThvd",
]

@app.get("/stats")
def get_stats(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT time, {', '.join(STATS_COLUMNS)}
        FROM device_stats WHERE device_id = %s ORDER BY time DESC LIMIT 1
    """, (device_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return dict(zip(["time"] + STATS_COLUMNS, row))

# ---------- REST: Tepe (Min/Max) Değerleri (ANL21) ----------
PEAKS_COLUMNS = [
    "min_vln1", "min_vln2", "min_vln3", "min_vn", "max_vln1", "max_vln2", "max_vln3", "max_vn",
    "min_vll1", "min_vll2", "min_vll3", "max_vll1", "max_vll2", "max_vll3",
    "min_i1", "min_i2", "min_i3", "min_in", "max_i1", "max_i2", "max_i3", "max_in",
    "min_p1", "min_p2", "min_p3", "max_p1", "max_p2", "max_p3",
    "min_q1", "min_q2", "min_q3", "max_q1", "max_q2", "max_q3",
    "min_s1", "min_s2", "min_s3", "max_s1", "max_s2", "max_s3",
    "min_thvd1", "min_thvd2", "min_thvd3", "max_thvd1", "max_thvd2", "max_thvd3",
    "min_thid1", "min_thid2", "min_thid3", "max_thid1", "max_thid2", "max_thid3",
    "min_freq", "max_freq", "min_v_unbal", "max_v_unbal", "min_i_unbal", "max_i_unbal",
]
# Firmware buildPeakJson alan adlari (camelCase) — PEAKS_COLUMNS ile ayni sirada.
PEAKS_JSON_KEYS = [
    "minVln1", "minVln2", "minVln3", "minVn", "maxVln1", "maxVln2", "maxVln3", "maxVn",
    "minVll1", "minVll2", "minVll3", "maxVll1", "maxVll2", "maxVll3",
    "minI1", "minI2", "minI3", "minIn", "maxI1", "maxI2", "maxI3", "maxIn",
    "minP1", "minP2", "minP3", "maxP1", "maxP2", "maxP3",
    "minQ1", "minQ2", "minQ3", "maxQ1", "maxQ2", "maxQ3",
    "minS1", "minS2", "minS3", "maxS1", "maxS2", "maxS3",
    "minThvd1", "minThvd2", "minThvd3", "maxThvd1", "maxThvd2", "maxThvd3",
    "minThid1", "minThid2", "minThid3", "maxThid1", "maxThid2", "maxThid3",
    "minFreq", "maxFreq", "minVUnbal", "maxVUnbal", "minIUnbal", "maxIUnbal",
]

@app.get("/peaks")
def get_peaks(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT ON (direction) direction, time, {', '.join(PEAKS_COLUMNS)}
        FROM device_peaks WHERE device_id = %s ORDER BY direction, time DESC
    """, (device_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["direction", "time"] + PEAKS_COLUMNS
    return {r[0]: dict(zip(columns, r)) for r in rows}

# ---------- REST: Demand Değerleri (ANL21) ----------
DEMAND_COLUMNS = [
    "max_dv1", "max_dv2", "max_dv3", "min_dv1", "min_dv2", "min_dv3",
    "max_di1", "max_di2", "max_di3", "min_di1", "min_di2", "min_di3",
    "max_dp1", "max_dp2", "max_dp3", "min_dp1", "min_dp2", "min_dp3",
    "max_dq1", "max_dq2", "max_dq3", "min_dq1", "min_dq2", "min_dq3",
    "max_ds1", "max_ds2", "max_ds3", "min_ds1", "min_ds2", "min_ds3",
    "max_dthvd1", "max_dthvd2", "max_dthvd3", "min_dthvd1", "min_dthvd2", "min_dthvd3",
    "max_dthid1", "max_dthid2", "max_dthid3", "min_dthid1", "min_dthid2", "min_dthid3",
]
# Firmware buildDemandJson alan adlari (camelCase) — DEMAND_COLUMNS ile ayni sirada.
DEMAND_JSON_KEYS = [
    "maxDV1", "maxDV2", "maxDV3", "minDV1", "minDV2", "minDV3",
    "maxDI1", "maxDI2", "maxDI3", "minDI1", "minDI2", "minDI3",
    "maxDP1", "maxDP2", "maxDP3", "minDP1", "minDP2", "minDP3",
    "maxDQ1", "maxDQ2", "maxDQ3", "minDQ1", "minDQ2", "minDQ3",
    "maxDS1", "maxDS2", "maxDS3", "minDS1", "minDS2", "minDS3",
    "maxDThvd1", "maxDThvd2", "maxDThvd3", "minDThvd1", "minDThvd2", "minDThvd3",
    "maxDThid1", "maxDThid2", "maxDThid3", "minDThid1", "minDThid2", "minDThid3",
]

@app.get("/demand")
def get_demand(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT ON (direction) direction, time, {', '.join(DEMAND_COLUMNS)}
        FROM device_demand WHERE device_id = %s ORDER BY direction, time DESC
    """, (device_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["direction", "time"] + DEMAND_COLUMNS
    return {r[0]: dict(zip(columns, r)) for r in rows}

# ---------- REST: Harmonik Spektrumu (ANL21) ----------
HARMONICS_ORDERS = list(range(3, 32, 2))  # 3,5,...,31
HARMONICS_COLUMNS = ["thd1", "thd2", "thd3"] + [
    f"h{n}_l{p}" for n in HARMONICS_ORDERS for p in (1, 2, 3)
]

@app.get("/harmonics")
def get_harmonics(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT ON (signal_type) signal_type, time, {', '.join(HARMONICS_COLUMNS)}
        FROM device_harmonics WHERE device_id = %s ORDER BY signal_type, time DESC
    """, (device_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["signal_type", "time"] + HARMONICS_COLUMNS
    return {r[0]: dict(zip(columns, r)) for r in rows}

# ---------- REST: Cihaz Bilgileri (ANL21, statik) ----------
INFO_COLUMNS = [
    "seri_no", "urun_id", "kart_id", "sistem_versiyon", "ulke_kodu", "firma_kodu",
    "besleme_tipi", "ekran_tipi", "keyboard_tipi", "kutu_tipi", "klemens_tipi",
    "connections", "storage",
]

@app.get("/info")
def get_info(device_id: str, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT {', '.join(INFO_COLUMNS)}, updated_at FROM device_info WHERE device_id = %s
    """, (device_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return dict(zip(INFO_COLUMNS + ["updated_at"], row))

# ---------- REST: Cihaza yazma komutu gönder ----------
class DeviceCommandRequest(BaseModel):
    command: str
    password: str | None = None  # sadece "risk": "high" komutlar için zorunlu

def publish_command(device_id: str, register: int, value: int = 1):
    if IS_STAGING:
        # Staging uretimle AYNI mosquitto'yu dinliyor; komut yayinlarsa gercek
        # sahadaki cihaza gider. Okuma paylasilabilir, yazma asla.
        logger.warning("[STAGING] cihaz komutu engellendi: %s register=%s", device_id, register)
        raise HTTPException(
            status_code=503,
            detail="Staging ortamından gerçek cihaza komut gönderilemez.")
    connected_evt = threading.Event()

    def on_connect(c, userdata, flags, rc, properties=None):
        print("publish_command: on_connect rc=", rc)
        connected_evt.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    print("publish_command: connecting to", MQTT_BROKER)
    client.connect(MQTT_BROKER, 1883, 10)
    client.loop_start()
    try:
        if not connected_evt.wait(timeout=5):
            print("publish_command: CONNACK icin zaman asimi!")
        topic = cmd_topic(device_id)
        payload = json.dumps({"register": register, "value": value})
        print("publish_command: publishing", topic, payload)
        info = client.publish(topic, payload)
        print("publish_command: publish rc=", info.rc, "mid=", info.mid)
        published = info.wait_for_publish(timeout=5)
        print("publish_command: is_published=", info.is_published())
    finally:
        client.loop_stop()
        client.disconnect()

@app.post("/devices/{device_id}/command")
def send_device_command(device_id: str, payload: DeviceCommandRequest, user: str = Depends(require_auth)):
    audit("device.command", actor=user, entity_type="device", entity_id=device_id,
          detail={"komut": payload.command})
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    cmd = DEVICE_COMMANDS.get(payload.command)
    if not cmd:
        raise HTTPException(status_code=400, detail="Geçersiz komut")
    # Yüksek riskli (geri alınamaz) komutlar sadece cihaz sahipliğiyle değil, hesap
    # şifresinin yeniden girilmesiyle de doğrulanıyor -- JWT 30 gün geçerli ve iptal
    # mekanizması yok, bu da çalınan/sızan bir token'ın tek başına factory_reset/
    # reset_password çalıştırmasını engelliyor (bkz. architecture.md güvenlik notları).
    if cmd["risk"] == "high":
        check_rate_limit(f"highrisk:{user}", max_attempts=5, window_seconds=60 * 60)
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = %s", (user,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not payload.password or not row or not bcrypt.checkpw(payload.password.encode(), row[0].encode()):
            raise HTTPException(status_code=403, detail="Bu işlem için hesap şifrenizi doğru girmelisiniz")
    try:
        publish_command(device_id, cmd["register"], cmd["value"])
    except Exception as e:
        print("Komut gonderme hatasi:", e)
        raise HTTPException(status_code=502, detail="Komut cihaza gönderilemedi")
    return {"message": "Komut gönderildi"}

# Register 221 = "Akım Trafo Oranı (Table Index)" (Parametreler sayfası, W/R, 0-69).
# ONEMLI: eskiden 214 kullaniliyordu, bu register aslinda "Okuma Koruma Biti" (0/1,
# CT orani ile ilgisiz) -- yanlis register'di, 20 Ağustos 2026'da Excel'deki
# Parametreler sayfasi incelenerek duzeltildi. Firmware register'a INDEKS yazar/okur
# (0-69), asagidaki tablo o indeksi gercek orana (X/5 A) cevirir -- tablo da ayni
# sayfadan ("*2* Akım Trafo Tablosu (X/5 A)").
CT_RATIO_REGISTER = 221
CT_RATIO_TABLE = [
    5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100, 120, 125, 130, 150, 160, 175,
    180, 200, 225, 240, 250, 300, 330, 350, 360, 400, 450, 500, 520, 550, 600, 630, 650,
    700, 730, 750, 800, 900, 1000, 1100, 1200, 1250, 1400, 1500, 1600, 1800, 2000, 2200,
    2400, 2500, 2600, 3000, 3200, 3500, 3600, 4000, 4500, 5000, 5500, 6000, 6500, 7000,
    7500, 8000, 8500, 10000,
]

class CtRatioRequest(BaseModel):
    value: int  # gerçek oran (X/5 A), CT_RATIO_TABLE'daki değerlerden biri olmalı

@app.get("/devices/{device_id}/ct-ratio")
def get_ct_ratio(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT ct_ratio, updated_at FROM device_settings WHERE device_id = %s", (device_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or row[0] is None:
        return {"ct_ratio": None, "updated_at": None}
    idx = row[0]
    ratio = CT_RATIO_TABLE[idx] if 0 <= idx < len(CT_RATIO_TABLE) else None
    return {"ct_ratio": ratio, "updated_at": row[1]}

@app.post("/devices/{device_id}/ct-ratio")
def set_ct_ratio(device_id: str, payload: CtRatioRequest, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    if payload.value not in CT_RATIO_TABLE:
        raise HTTPException(status_code=400, detail="Geçersiz oran değeri")
    idx = CT_RATIO_TABLE.index(payload.value)
    try:
        publish_command(device_id, CT_RATIO_REGISTER, idx)
    except Exception as e:
        print("CT orani gonderme hatasi:", e)
        raise HTTPException(status_code=502, detail="Komut cihaza gönderilemedi")
    return {"message": "Akım trafo oranı gönderildi"}

@app.get("/ct-ratio-table")
def get_ct_ratio_table(user: str = Depends(require_auth)):
    return CT_RATIO_TABLE

# ---------- Reaktif ceza analizi ----------
# Turkiye'de reaktif enerji bedeli aylik toplamlar uzerinden hesaplanir:
# sebekeden cekilen endüktif reaktif enerji ile sebekeye verilen kapasitif
# reaktif enerji, tuketilen aktif enerjinin belirli bir yuzdesini asamaz.
# Limit asilirsa reaktif enerji faturaya yansir -- yaygin uygulamada sadece
# asan kisim degil, o ay cekilen reaktif enerjinin TAMAMI faturalandirilir
# (billing_mode = 'full'). Oranlar, birim fiyatlar ve bu hesaplama yontemi
# tarifeye/abone grubuna gore degistigi ve donemsel guncellendigi icin koda
# gomulmuyor: musteri kendi faturasindaki degerleri girerek kalibre eder.
TARIFF_PRESETS = {
    # Kompanzasyon yukumlusu abone (kurulu guc >= 50 kW)
    "over_50kw": {"inductive_limit_pct": 20.0, "capacitive_limit_pct": 15.0},
    # Kucuk abone (kurulu guc < 50 kW)
    "under_50kw": {"inductive_limit_pct": 33.0, "capacitive_limit_pct": 20.0},
}
TARIFF_DEFAULTS = {
    "inductive_limit_pct": 20.0,
    "capacitive_limit_pct": 15.0,
    "reactive_price": 0.0,
    "active_price": 0.0,
    "billing_mode": "full",
    # Uc zamanli tarife: T1 gunduz 06-17, T2 puant 17-22, T3 gece 22-06.
    "t1_start": 6,
    "t2_start": 17,
    "t3_start": 22,
    "t1_price": 0.0,
    "t2_price": 0.0,
    "t3_price": 0.0,
    # Sozlesme gucu (kW) ve asan kW basina bedel.
    "contract_power_kw": None,
    "demand_price": 0.0,
}
BILLING_MODES = ("full", "excess")
# Faturalama donemi yerel aya gore isler, UTC'ye gore degil.
BILLING_TZ = "Europe/Istanbul"

# Tek e-postaya eklenecek azami rapor sayisi -- cok cihazli musteride
# e-postanin boyutu kontrolden cikmasin diye.
MONTHLY_REPORT_MAX_DEVICES = 10

# Zaman dilimi etiketleri -- istemcilerde de ayni sirayla gosteriliyor.
TOU_LABELS = {"t1": "Gündüz", "t2": "Puant", "t3": "Gece"}


class TariffRequest(BaseModel):
    inductive_limit_pct: float
    capacitive_limit_pct: float
    reactive_price: float
    active_price: float
    billing_mode: str
    t1_start: int = 6
    t2_start: int = 17
    t3_start: int = 22
    t1_price: float = 0.0
    t2_price: float = 0.0
    t3_price: float = 0.0
    contract_power_kw: float | None = None
    demand_price: float = 0.0


def _read_tariff(device_id: str, cur) -> dict:
    cur.execute("""
        SELECT inductive_limit_pct, capacitive_limit_pct, reactive_price,
               active_price, billing_mode, updated_at,
               t1_start, t2_start, t3_start, t1_price, t2_price, t3_price,
               contract_power_kw, demand_price
        FROM device_tariff WHERE device_id = %s
    """, (device_id,))
    row = cur.fetchone()
    if not row:
        return {**TARIFF_DEFAULTS, "updated_at": None, "configured": False}
    return {
        "inductive_limit_pct": float(row[0]),
        "capacitive_limit_pct": float(row[1]),
        "reactive_price": float(row[2]),
        "active_price": float(row[3]),
        "billing_mode": row[4],
        "updated_at": row[5],
        "t1_start": int(row[6]),
        "t2_start": int(row[7]),
        "t3_start": int(row[8]),
        "t1_price": float(row[9]),
        "t2_price": float(row[10]),
        "t3_price": float(row[11]),
        "contract_power_kw": float(row[12]) if row[12] is not None else None,
        "demand_price": float(row[13]),
        "configured": True,
    }


def _reactive_buckets(device_id: str, unit: str, since, cur) -> list[dict]:
    """Saatlik enerji ozetinden donem bazli tuketim farklari.

    Ham device_energy yerine device_energy_hourly surekli toplamasindan
    okuyor: hem sorgu on-hesaplanmis veriyi tariyor hem de ham kayitlar
    saklama suresi dolunca silindiginde gecmis raporlar bozulmuyor.
    Sayac sifirlamasi _hourly_delta_sql icinde ele aliniyor.
    """
    cur.execute(f"""
        WITH deltas AS (
            SELECT
                (bucket AT TIME ZONE %s) AS local_time,
                {_hourly_delta_sql("active_tuketim", "active_wh_tuketim")} AS d_active,
                {_hourly_delta_sql("inductive_tuketim", "inductive_varh_tuketim")} AS d_inductive,
                {_hourly_delta_sql("capacitive_tuketim", "capacitive_varh_tuketim")} AS d_capacitive
            FROM device_energy_hourly
            WHERE device_id = %s AND bucket >= %s
            WINDOW w AS (ORDER BY bucket)
        )
        SELECT date_trunc(%s, local_time) AS bucket,
               SUM(d_active) / 1000.0,
               SUM(d_inductive) / 1000.0,
               SUM(d_capacitive) / 1000.0,
               -- Kovalar zaten saatlik oldugu icin "yuk altinda gecen saat"
               -- dogrudan tuketim goren kova sayisi.
               COUNT(*) FILTER (WHERE d_active > 0)
        FROM deltas
        GROUP BY bucket
        ORDER BY bucket ASC
    """, (BILLING_TZ, device_id, since, unit))
    return [
        {
            "bucket": r[0],
            "active_kwh": float(r[1] or 0),
            "inductive_kvarh": float(r[2] or 0),
            "capacitive_kvarh": float(r[3] or 0),
            "load_hours": int(r[4] or 0),
        }
        for r in cur.fetchall()
    ]


def _analyze_bucket(row: dict, tariff: dict) -> dict:
    active = row["active_kwh"]
    ind = row["inductive_kvarh"]
    cap = row["capacitive_kvarh"]
    ind_limit = tariff["inductive_limit_pct"]
    cap_limit = tariff["capacitive_limit_pct"]

    ind_pct = (ind / active * 100) if active > 0 else None
    cap_pct = (cap / active * 100) if active > 0 else None

    # Limite karsilik gelen kVArh tavani -- asim bunun uzerinden hesaplanir.
    ind_allowed = active * ind_limit / 100
    cap_allowed = active * cap_limit / 100
    ind_excess = max(ind - ind_allowed, 0.0)
    cap_excess = max(cap - cap_allowed, 0.0)

    ind_over = active > 0 and ind_excess > 0
    cap_over = active > 0 and cap_excess > 0

    if tariff["billing_mode"] == "excess":
        billed_ind = ind_excess
        billed_cap = cap_excess
    else:
        # Limit asildiginda reaktif enerjinin tamami faturalanir.
        billed_ind = ind if ind_over else 0.0
        billed_cap = cap if cap_over else 0.0

    penalty_cost = (billed_ind + billed_cap) * tariff["reactive_price"]
    active_cost = active * tariff["active_price"]

    # Asimi kapatmak icin gereken kompanzasyon gucu (kaba tahmin):
    # asan kVArh, yuk altinda gecen saat sayisina bolunur.
    hours = row["load_hours"]
    suggested_kvar = round(ind_excess / hours, 1) if ind_over and hours > 0 else None

    return {
        **row,
        "inductive_pct": round(ind_pct, 1) if ind_pct is not None else None,
        "capacitive_pct": round(cap_pct, 1) if cap_pct is not None else None,
        "inductive_over": ind_over,
        "capacitive_over": cap_over,
        "inductive_excess_kvarh": round(ind_excess, 2),
        "capacitive_excess_kvarh": round(cap_excess, 2),
        "billed_inductive_kvarh": round(billed_ind, 2),
        "billed_capacitive_kvarh": round(billed_cap, 2),
        "penalty_cost": round(penalty_cost, 2),
        "active_cost": round(active_cost, 2),
        "suggested_kvar": suggested_kvar,
        "active_kwh": round(active, 2),
        "inductive_kvarh": round(ind, 2),
        "capacitive_kvarh": round(cap, 2),
    }


@app.get("/devices/{device_id}/tariff")
def get_tariff(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = db_connect()
    cur = conn.cursor()
    tariff = _read_tariff(device_id, cur)
    cur.close()
    conn.close()
    return {**tariff, "presets": TARIFF_PRESETS}


@app.put("/devices/{device_id}/tariff")
def set_tariff(device_id: str, payload: TariffRequest, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    if payload.billing_mode not in BILLING_MODES:
        raise HTTPException(status_code=400, detail="Geçersiz hesaplama yöntemi")
    for name, value in (("Endüktif limit", payload.inductive_limit_pct),
                        ("Kapasitif limit", payload.capacitive_limit_pct)):
        if not 0 < value <= 100:
            raise HTTPException(status_code=400, detail=f"{name} 0 ile 100 arasında olmalı")
    for name, value in (("Reaktif birim fiyat", payload.reactive_price),
                        ("Aktif birim fiyat", payload.active_price),
                        ("Gündüz birim fiyat", payload.t1_price),
                        ("Puant birim fiyat", payload.t2_price),
                        ("Gece birim fiyat", payload.t3_price),
                        ("Güç aşım birim bedeli", payload.demand_price)):
        if value < 0:
            raise HTTPException(status_code=400, detail=f"{name} negatif olamaz")
    for name, value in (("Gündüz başlangıcı", payload.t1_start),
                        ("Puant başlangıcı", payload.t2_start),
                        ("Gece başlangıcı", payload.t3_start)):
        if not 0 <= value <= 23:
            raise HTTPException(status_code=400, detail=f"{name} 0 ile 23 arasında olmalı")
    # Dilimler gun icinde artan sirada olmali, yoksa saat->dilim eslemesi
    # bosluk/cakisma uretir.
    if not payload.t1_start < payload.t2_start < payload.t3_start:
        raise HTTPException(
            status_code=400,
            detail="Zaman dilimleri artan sırada olmalı (gündüz < puant < gece)")
    if payload.contract_power_kw is not None and payload.contract_power_kw <= 0:
        raise HTTPException(status_code=400, detail="Sözleşme gücü sıfırdan büyük olmalı")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO device_tariff (device_id, inductive_limit_pct, capacitive_limit_pct,
                                   reactive_price, active_price, billing_mode,
                                   t1_start, t2_start, t3_start,
                                   t1_price, t2_price, t3_price,
                                   contract_power_kw, demand_price,
                                   updated_at, updated_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
        ON CONFLICT (device_id) DO UPDATE SET
            inductive_limit_pct = EXCLUDED.inductive_limit_pct,
            capacitive_limit_pct = EXCLUDED.capacitive_limit_pct,
            reactive_price = EXCLUDED.reactive_price,
            active_price = EXCLUDED.active_price,
            billing_mode = EXCLUDED.billing_mode,
            t1_start = EXCLUDED.t1_start,
            t2_start = EXCLUDED.t2_start,
            t3_start = EXCLUDED.t3_start,
            t1_price = EXCLUDED.t1_price,
            t2_price = EXCLUDED.t2_price,
            t3_price = EXCLUDED.t3_price,
            contract_power_kw = EXCLUDED.contract_power_kw,
            demand_price = EXCLUDED.demand_price,
            updated_at = now(),
            updated_by = EXCLUDED.updated_by
    """, (device_id, payload.inductive_limit_pct, payload.capacitive_limit_pct,
          payload.reactive_price, payload.active_price, payload.billing_mode,
          payload.t1_start, payload.t2_start, payload.t3_start,
          payload.t1_price, payload.t2_price, payload.t3_price,
          payload.contract_power_kw, payload.demand_price, user))
    conn.commit()
    cur.close()
    conn.close()
    audit("tariff.update", actor=user, entity_type="device", entity_id=device_id,
          detail={"reaktif_fiyat": payload.reactive_price,
                  "sozlesme_gucu": payload.contract_power_kw})
    return {"message": "Tarife ayarları kaydedildi"}


@app.get("/reports/reactive")
def reactive_report(device_id: str, period: str = "monthly", count: int = 12,
                    format: str = "json", user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    if period not in ("monthly", "daily"):
        raise HTTPException(status_code=400, detail="Geçersiz dönem")

    if period == "monthly":
        count = max(1, min(count, 36))
        unit = "month"
        since = datetime.now(timezone.utc) - timedelta(days=31 * count)
    else:
        count = max(1, min(count, 180))
        unit = "day"
        since = datetime.now(timezone.utc) - timedelta(days=count)

    conn = db_connect()
    cur = conn.cursor()
    tariff = _read_tariff(device_id, cur)
    buckets = _reactive_buckets(device_id, unit, since, cur)
    cur.close()
    conn.close()

    rows = [_analyze_bucket(b, tariff) for b in buckets][-count:]

    penalized = [r for r in rows if r["inductive_over"] or r["capacitive_over"]]
    summary = {
        "period_count": len(rows),
        "penalized_count": len(penalized),
        "total_active_kwh": round(sum(r["active_kwh"] for r in rows), 2),
        "total_inductive_kvarh": round(sum(r["inductive_kvarh"] for r in rows), 2),
        "total_capacitive_kvarh": round(sum(r["capacitive_kvarh"] for r in rows), 2),
        "total_penalty_cost": round(sum(r["penalty_cost"] for r in rows), 2),
        "total_active_cost": round(sum(r["active_cost"] for r in rows), 2),
        "worst_inductive_pct": max((r["inductive_pct"] for r in rows if r["inductive_pct"] is not None), default=None),
        "worst_capacitive_pct": max((r["capacitive_pct"] for r in rows if r["capacitive_pct"] is not None), default=None),
        "max_suggested_kvar": max((r["suggested_kvar"] for r in rows if r["suggested_kvar"] is not None), default=None),
    }

    if format == "xlsx":
        return _reactive_xlsx(device_id, period, rows, summary, tariff)

    return {"device_id": device_id, "period": period, "tariff": tariff,
            "rows": rows, "summary": summary}


def _reactive_xlsx(device_id: str, period: str, rows: list[dict],
                   summary: dict, tariff: dict) -> Response:
    wb = Workbook()
    ws = wb.active
    ws.title = "Reaktif Analiz"

    mode_label = ("Limit aşılırsa reaktifin tamamı" if tariff["billing_mode"] == "full"
                  else "Yalnızca aşan kısım")
    for label, value in (
        ("Cihaz", device_id),
        ("Rapor tarihi", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("Endüktif limit", f"%{tariff['inductive_limit_pct']:g}"),
        ("Kapasitif limit", f"%{tariff['capacitive_limit_pct']:g}"),
        ("Reaktif birim fiyat", f"{tariff['reactive_price']:g} TL/kVArh"),
        ("Hesaplama yöntemi", mode_label),
    ):
        ws.append([label, value])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])

    headers = ["Dönem", "Aktif (kWh)", "Endüktif (kVArh)", "Kapasitif (kVArh)",
               "Endüktif %", "Kapasitif %", "Durum", "Aşım (kVArh)",
               "Faturalanan Reaktif (kVArh)", "Ceza (TL)", "Önerilen Komp. (kVAr)"]
    header_row = ws.max_row + 1
    ws.append(headers)
    for cell in ws[header_row]:
        cell.font = Font(bold=True)

    fmt = "%m.%Y" if period == "monthly" else "%d.%m.%Y"
    for r in rows:
        if r["inductive_over"] and r["capacitive_over"]:
            durum = "Endüktif + Kapasitif aşım"
        elif r["inductive_over"]:
            durum = "Endüktif aşım"
        elif r["capacitive_over"]:
            durum = "Kapasitif aşım"
        else:
            durum = "Limit içinde"
        ws.append([
            r["bucket"].strftime(fmt),
            r["active_kwh"], r["inductive_kvarh"], r["capacitive_kvarh"],
            r["inductive_pct"], r["capacitive_pct"], durum,
            round(r["inductive_excess_kvarh"] + r["capacitive_excess_kvarh"], 2),
            round(r["billed_inductive_kvarh"] + r["billed_capacitive_kvarh"], 2),
            r["penalty_cost"], r["suggested_kvar"],
        ])

    total_row = ws.max_row + 1
    ws.append(["TOPLAM", summary["total_active_kwh"], summary["total_inductive_kvarh"],
               summary["total_capacitive_kvarh"], None, None,
               f"{summary['penalized_count']} / {summary['period_count']} dönemde aşım",
               None, None, summary["total_penalty_cost"], None])
    for cell in ws[total_row]:
        cell.font = Font(bold=True)

    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=header_row, column=i).column_letter].width = max(14, len(header) * 1.1)

    buffer = io.BytesIO()
    wb.save(buffer)
    filename = f"{device_id}-reaktif-analiz.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# ---------- Fatura analizi: zaman dilimi + guc asim + reaktif ----------
# Sanayi aboneliginde fatura uc ayri kalemden sisiyor ve ucu de bu cihazin
# zaten topladigi veriden hesaplanabiliyor:
#   1) Aktif enerji, uc zaman diliminde farkli fiyattan (gunduz/puant/gece).
#      Puant genelde gecenin ~3 kati; bir fabrikanin elindeki en buyuk tasarruf
#      kaldiraci yuku puanttan geceye kaydirmak.
#   2) Guc asim bedeli: 15 dakikalik ortalama guc sozlesme gucunu asarsa.
#   3) Reaktif ceza (yukarida).
# Bu endpoint ucunu tek bir aylik dokumde birlestiriyor.


def _tou_buckets(device_id: str, tariff: dict, since, cur) -> dict:
    """Ay bazinda zaman dilimi (T1/T2/T3) kirilimli aktif tuketim.

    device_energy_hourly ozetinden okuyor; her saatin YEREL saatine bakip
    hangi dilime dustugunu belirliyor. Saat sinirlari tarifeden geliyor.
    """
    cur.execute(f"""
        WITH deltas AS (
            SELECT
                (bucket AT TIME ZONE %s) AS local_time,
                {_hourly_delta_sql("active_tuketim", "active_wh_tuketim")} AS d_active
            FROM device_energy_hourly
            WHERE device_id = %s AND bucket >= %s
            WINDOW w AS (ORDER BY bucket)
        )
        SELECT
            date_trunc('month', local_time) AS ay,
            SUM(d_active) FILTER (
                WHERE EXTRACT(HOUR FROM local_time) >= %s
                  AND EXTRACT(HOUR FROM local_time) <  %s) / 1000.0 AS t1_kwh,
            SUM(d_active) FILTER (
                WHERE EXTRACT(HOUR FROM local_time) >= %s
                  AND EXTRACT(HOUR FROM local_time) <  %s) / 1000.0 AS t2_kwh,
            SUM(d_active) FILTER (
                WHERE EXTRACT(HOUR FROM local_time) <  %s
                   OR EXTRACT(HOUR FROM local_time) >= %s) / 1000.0 AS t3_kwh
        FROM deltas
        GROUP BY ay
    """, (BILLING_TZ, device_id, since,
          tariff["t1_start"], tariff["t2_start"],
          tariff["t2_start"], tariff["t3_start"],
          tariff["t1_start"], tariff["t3_start"]))
    return {
        r[0]: {"t1_kwh": float(r[1] or 0), "t2_kwh": float(r[2] or 0), "t3_kwh": float(r[3] or 0)}
        for r in cur.fetchall()
    }


def _demand_buckets(device_id: str, since, cur) -> dict:
    """Ay bazinda tepe talep (15 dakikalik ortalama gucun aylik maksimumu).

    15 dakika keyfi degil: guc asim bedeli bu aralik uzerinden hesaplanir.
    measurements_15min surekli toplamasi zaten bu araliga gore kuruldu.
    Tepenin NE ZAMAN olustugu da donuyor -- musteri icin en eyleme donuk bilgi
    genelde bu ("tepe guc 14 Agustos 15:45'te olustu").
    """
    cur.execute("""
        WITH m AS (
            SELECT (bucket AT TIME ZONE %s) AS local_time, avg_total_p, avg_total_s
            FROM measurements_15min
            WHERE device_id = %s AND bucket >= %s
        ),
        siralanmis AS (
            SELECT date_trunc('month', local_time) AS ay, local_time, avg_total_p, avg_total_s,
                   ROW_NUMBER() OVER (PARTITION BY date_trunc('month', local_time)
                                      ORDER BY avg_total_p DESC) AS sira
            FROM m
        )
        SELECT ay, avg_total_p / 1000.0 AS peak_kw, avg_total_s / 1000.0 AS peak_kva, local_time
        FROM siralanmis WHERE sira = 1
    """, (BILLING_TZ, device_id, since))
    return {
        r[0]: {"peak_kw": round(float(r[1] or 0), 2),
               "peak_kva": round(float(r[2] or 0), 2),
               "peak_time": r[3]}
        for r in cur.fetchall()
    }


def _analyze_bill_month(bucket, tou: dict, demand: dict, reactive: dict | None,
                        tariff: dict) -> dict:
    t1, t2, t3 = tou["t1_kwh"], tou["t2_kwh"], tou["t3_kwh"]
    total_kwh = t1 + t2 + t3

    # Uc zamanli fiyat girilmemisse tek fiyatli active_price'a dusuyoruz.
    tou_enabled = any(tariff[k] > 0 for k in ("t1_price", "t2_price", "t3_price"))
    if tou_enabled:
        t1_cost = t1 * tariff["t1_price"]
        t2_cost = t2 * tariff["t2_price"]
        t3_cost = t3 * tariff["t3_price"]
    else:
        t1_cost = t1 * tariff["active_price"]
        t2_cost = t2 * tariff["active_price"]
        t3_cost = t3 * tariff["active_price"]
    active_cost = t1_cost + t2_cost + t3_cost

    # Puant orani ve teorik tasarruf tavani: puantta tuketilen enerjinin
    # tamami gece tarifesinde tuketilseydi ne kadar az odenirdi. Ulasilabilir
    # bir hedef degil, ust sinir -- arayuzde de oyle etiketleniyor.
    puant_pct = round(t2 / total_kwh * 100, 1) if total_kwh > 0 else None
    max_shift_saving = round(t2 * max(tariff["t2_price"] - tariff["t3_price"], 0), 2) if tou_enabled else 0.0

    # Guc asim
    peak = demand or {}
    contract = tariff["contract_power_kw"]
    peak_kw = peak.get("peak_kw")
    overrun_kw = None
    demand_cost = 0.0
    if contract is not None and peak_kw is not None:
        overrun_kw = round(max(peak_kw - contract, 0.0), 2)
        demand_cost = round(overrun_kw * tariff["demand_price"], 2)

    reactive_cost = reactive["penalty_cost"] if reactive else 0.0

    return {
        "bucket": bucket,
        "t1_kwh": round(t1, 2), "t2_kwh": round(t2, 2), "t3_kwh": round(t3, 2),
        "t1_cost": round(t1_cost, 2), "t2_cost": round(t2_cost, 2), "t3_cost": round(t3_cost, 2),
        "active_kwh": round(total_kwh, 2),
        "active_cost": round(active_cost, 2),
        "puant_pct": puant_pct,
        "max_shift_saving": max_shift_saving,
        "peak_kw": peak_kw,
        "peak_kva": peak.get("peak_kva"),
        "peak_time": peak.get("peak_time"),
        "contract_power_kw": contract,
        "overrun_kw": overrun_kw,
        "demand_cost": demand_cost,
        "reactive_cost": round(reactive_cost, 2),
        "inductive_pct": reactive["inductive_pct"] if reactive else None,
        "capacitive_pct": reactive["capacitive_pct"] if reactive else None,
        "reactive_over": bool(reactive and (reactive["inductive_over"] or reactive["capacitive_over"])),
        "total_cost": round(active_cost + demand_cost + reactive_cost, 2),
    }


@app.get("/reports/bill")
def bill_report(device_id: str, months: int = 12, format: str = "json",
                user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    months = max(1, min(months, 36))
    since = datetime.now(timezone.utc) - timedelta(days=31 * months)

    conn = db_connect()
    cur = conn.cursor()
    tariff = _read_tariff(device_id, cur)
    tou = _tou_buckets(device_id, tariff, since, cur)
    demand = _demand_buckets(device_id, since, cur)
    # Reaktif kalemini mevcut analizden aliyoruz -- ayni hesabi ikinci kez
    # yazmamak icin; boylece iki rapor arasinda tutarsizlik olusamaz.
    reactive_rows = {
        r["bucket"]: r
        for r in (_analyze_bucket(b, tariff)
                  for b in _reactive_buckets(device_id, "month", since, cur))
    }
    cur.close()
    conn.close()

    rows = [
        _analyze_bill_month(ay, tou[ay], demand.get(ay), reactive_rows.get(ay), tariff)
        for ay in sorted(tou.keys())
    ][-months:]

    priced = tariff["active_price"] > 0 or any(
        tariff[k] > 0 for k in ("t1_price", "t2_price", "t3_price"))
    summary = {
        "month_count": len(rows),
        "priced": priced,
        "tou_enabled": any(tariff[k] > 0 for k in ("t1_price", "t2_price", "t3_price")),
        "total_kwh": round(sum(r["active_kwh"] for r in rows), 2),
        "total_active_cost": round(sum(r["active_cost"] for r in rows), 2),
        "total_demand_cost": round(sum(r["demand_cost"] for r in rows), 2),
        "total_reactive_cost": round(sum(r["reactive_cost"] for r in rows), 2),
        "total_cost": round(sum(r["total_cost"] for r in rows), 2),
        "total_shift_saving": round(sum(r["max_shift_saving"] for r in rows), 2),
        "t1_kwh": round(sum(r["t1_kwh"] for r in rows), 2),
        "t2_kwh": round(sum(r["t2_kwh"] for r in rows), 2),
        "t3_kwh": round(sum(r["t3_kwh"] for r in rows), 2),
        "peak_kw": max((r["peak_kw"] for r in rows if r["peak_kw"] is not None), default=None),
        "overrun_months": sum(1 for r in rows if (r["overrun_kw"] or 0) > 0),
    }
    if summary["total_kwh"] > 0:
        summary["puant_pct"] = round(summary["t2_kwh"] / summary["total_kwh"] * 100, 1)
    else:
        summary["puant_pct"] = None

    if format == "xlsx":
        return _bill_xlsx(device_id, rows, summary, tariff)

    return {"device_id": device_id, "tariff": tariff, "rows": rows, "summary": summary}


def _bill_xlsx(device_id: str, rows: list[dict], summary: dict, tariff: dict) -> Response:
    wb = Workbook()
    ws = wb.active
    ws.title = "Fatura Analizi"

    for label, value in (
        ("Cihaz", device_id),
        ("Rapor tarihi", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("Gündüz", f"{tariff['t1_start']:02d}:00-{tariff['t2_start']:02d}:00 · {tariff['t1_price']:g} TL/kWh"),
        ("Puant", f"{tariff['t2_start']:02d}:00-{tariff['t3_start']:02d}:00 · {tariff['t2_price']:g} TL/kWh"),
        ("Gece", f"{tariff['t3_start']:02d}:00-{tariff['t1_start']:02d}:00 · {tariff['t3_price']:g} TL/kWh"),
        ("Sözleşme gücü", f"{tariff['contract_power_kw']:g} kW" if tariff["contract_power_kw"] else "girilmedi"),
        ("Güç aşım bedeli", f"{tariff['demand_price']:g} TL/kW"),
    ):
        ws.append([label, value])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])

    headers = ["Ay", "Gündüz (kWh)", "Puant (kWh)", "Gece (kWh)", "Toplam (kWh)",
               "Puant %", "Aktif Bedel (TL)",
               "Tepe Güç (kW)", "Tepe Zamanı", "Sözleşme (kW)", "Aşım (kW)", "Güç Aşım (TL)",
               "Endüktif %", "Kapasitif %", "Reaktif Ceza (TL)",
               "TOPLAM (TL)", "Puant→Gece Tasarruf Tavanı (TL)"]
    header_row = ws.max_row + 1
    ws.append(headers)
    for cell in ws[header_row]:
        cell.font = Font(bold=True)

    for r in rows:
        ws.append([
            r["bucket"].strftime("%m.%Y"),
            r["t1_kwh"], r["t2_kwh"], r["t3_kwh"], r["active_kwh"],
            r["puant_pct"], r["active_cost"],
            r["peak_kw"], r["peak_time"].strftime("%d.%m.%Y %H:%M") if r["peak_time"] else None,
            r["contract_power_kw"], r["overrun_kw"], r["demand_cost"],
            r["inductive_pct"], r["capacitive_pct"], r["reactive_cost"],
            r["total_cost"], r["max_shift_saving"],
        ])

    total_row = ws.max_row + 1
    ws.append(["TOPLAM", summary["t1_kwh"], summary["t2_kwh"], summary["t3_kwh"],
               summary["total_kwh"], summary["puant_pct"], summary["total_active_cost"],
               summary["peak_kw"], None, None, None, summary["total_demand_cost"],
               None, None, summary["total_reactive_cost"],
               summary["total_cost"], summary["total_shift_saving"]])
    for cell in ws[total_row]:
        cell.font = Font(bold=True)

    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=header_row, column=i).column_letter].width = max(13, len(header) * 1.05)

    buffer = io.BytesIO()
    wb.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{device_id}-fatura-analizi.xlsx"'},
    )


# ---------- Aylik PDF raporu ----------
# Panel, musterinin acmayi hatirlamasi gereken bir yer. Rapor ise her ayin
# basinda kutusuna dusuyor: donemin faturasi kalem kalem, tasarruf firsatlari
# ve alarm ozeti. Icerik zaten /reports/bill'de hesaplaniyor -- burada ikinci
# bir hesap yok, ayni fonksiyonlar cagriliyor ki panel ile rapor arasinda
# tutarsizlik olusamasin.

REPORT_FONT = "DejaVuSans"
REPORT_FONT_BOLD = "DejaVuSans-Bold"
_FONTS_REGISTERED = False

TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _ensure_report_fonts():
    """reportlab'in yerlesik Helvetica'si Latin-1; Turkce g/s/i harflerini
    basamiyor. DejaVu imajda kurulu (Dockerfile), bir kez kaydediyoruz."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    base = "/usr/share/fonts/truetype/dejavu"
    pdfmetrics.registerFont(TTFont(REPORT_FONT, f"{base}/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont(REPORT_FONT_BOLD, f"{base}/DejaVuSans-Bold.ttf"))
    _FONTS_REGISTERED = True


LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
_logo_cache: dict[bool, object] = {}


def _logo_reader(white: bool = False):
    """Marka isareti. Koyu baslik seridinde kullanmak icin alfa kanali
    korunarak RGB beyaza cevriliyor. Dosya yoksa rapor logosuz uretiliyor --
    logo eksikligi raporu bozmamali."""
    if white in _logo_cache:
        return _logo_cache[white]
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        img = Image.open(LOGO_PATH).convert("RGBA")
        if white:
            alpha = img.split()[3]
            solid = Image.new("L", img.size, 255)
            img = Image.merge("RGBA", (solid, solid, solid, alpha))
        reader = ImageReader(img)
    except Exception as e:
        logger.warning("Rapor logosu yuklenemedi: %s", e)
        reader = None
    _logo_cache[white] = reader
    return reader


def _month_bounds(year: int, month: int):
    """Yerel ay siniri. Faturalama ayi yereldir, UTC degil -- bu yuzden yerel
    ayin ilk ani hesaplanip UTC'ye cevriliyor."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(BILLING_TZ)
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _previous_month(today: datetime | None = None) -> tuple[int, int]:
    today = today or datetime.now(timezone.utc)
    year, month = today.year, today.month
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _report_device_info(device_id: str, cur) -> dict:
    cur.execute("""
        SELECT d.name, f.name, dep.name, o.name
        FROM devices d
        LEFT JOIN facilities f ON f.id = d.facility_id
        LEFT JOIN departments dep ON dep.id = d.department_id
        LEFT JOIN organizations o ON o.id = f.organization_id
        WHERE d.device_id = %s
    """, (device_id,))
    row = cur.fetchone()
    if not row:
        return {"name": device_id, "facility": None, "department": None, "organization": None}
    return {"name": row[0], "facility": row[1], "department": row[2], "organization": row[3]}


def _report_alarm_summary(device_id: str, start, end, cur) -> list[dict]:
    cur.execute("""
        SELECT message, count(*), max(triggered_at),
               count(*) FILTER (WHERE resolved_at IS NULL)
        FROM alarm_events
        WHERE device_id = %s AND triggered_at >= %s AND triggered_at < %s
        GROUP BY message ORDER BY count(*) DESC LIMIT 8
    """, (device_id, start, end))
    return [{"message": r[0], "count": r[1], "last": r[2], "open": r[3]} for r in cur.fetchall()]


def _report_daily_kwh(device_id: str, start, end, cur) -> list[tuple]:
    """Ay icindeki gunluk aktif tuketim -- rapordaki cubuk grafik icin."""
    cur.execute(f"""
        WITH deltas AS (
            SELECT (bucket AT TIME ZONE %s) AS local_time,
                   {_hourly_delta_sql("active_tuketim", "active_wh_tuketim")} AS d_active
            FROM device_energy_hourly
            WHERE device_id = %s AND bucket >= %s AND bucket < %s
            WINDOW w AS (ORDER BY bucket)
        )
        SELECT date_trunc('day', local_time)::date, SUM(d_active) / 1000.0
        FROM deltas GROUP BY 1 ORDER BY 1
    """, (BILLING_TZ, device_id, start, end))
    return [(r[0], float(r[1] or 0)) for r in cur.fetchall()]


def _report_recommendations(row: dict | None, reactive: dict | None, tariff: dict) -> list[str]:
    """Rapordaki 'ne yapmali' bolumu. Sadece veriden dogrudan cikan, sayisal
    olarak desteklenen oneriler -- genel tavsiye yazmiyoruz."""
    tips: list[str] = []
    if not row:
        return tips

    # Fiyat girilmemisse tutar cumleleri "0.00 TL" diye anlamsiz cikiyor;
    # o durumda sadece fiziksel buyukluklerden bahsediyoruz.
    if reactive and reactive.get("suggested_kvar"):
        ceza = (f" Bu dönem reaktif ceza {row['reactive_cost']:,.2f} ₺."
                if tariff["reactive_price"] > 0 else "")
        tips.append(
            f"Endüktif reaktif oranı %{reactive['inductive_pct']} ile "
            f"%{tariff['inductive_limit_pct']:g} limitinin üzerinde. Aşımı kapatmak için "
            f"yaklaşık {reactive['suggested_kvar']} kVAr kompanzasyon gerekiyor.{ceza}"
        )
    if (row.get("overrun_kw") or 0) > 0:
        peak_txt = row["peak_time"].strftime("%d.%m.%Y %H:%M") if row.get("peak_time") else "—"
        bedel = (f", {row['demand_cost']:,.2f} ₺ bedel"
                 if tariff["demand_price"] > 0 else "")
        tips.append(
            f"Tepe güç {row['peak_kw']} kW, sözleşme gücü {row['contract_power_kw']:g} kW — "
            f"{row['overrun_kw']} kW aşım{bedel}. "
            f"Tepe {peak_txt} anında oluştu; o saatteki yüklerin bir kısmı kaydırılabilirse "
            f"aşım tamamen ortadan kalkabilir."
        )
    if row.get("max_shift_saving", 0) > 0:
        tips.append(
            f"Tüketimin %{row['puant_pct']}'i puant saatlerinde. Bu tüketimin tamamı gece "
            f"tarifesine kaysaydı {row['max_shift_saving']:,.2f} ₺ daha az ödenirdi — bu "
            f"ulaşılabilir bir hedef değil, tasarruf tavanı; kaydırılabilen yük kadarı gerçekleşir."
        )
    if not tips:
        tips.append("Bu dönemde ceza doğuran bir aşım tespit edilmedi.")
    return tips


def build_monthly_pdf(device_id: str, year: int, month: int) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.platypus import Paragraph

    _ensure_report_fonts()
    start, end = _month_bounds(year, month)

    conn = db_connect()
    cur = conn.cursor()
    info = _report_device_info(device_id, cur)
    tariff = _read_tariff(device_id, cur)
    tou = _tou_buckets(device_id, tariff, start, cur)
    demand = _demand_buckets(device_id, start, cur)
    reactive_rows = {
        r["bucket"]: r
        for r in (_analyze_bucket(b, tariff)
                  for b in _reactive_buckets(device_id, "month", start, cur))
    }
    daily = _report_daily_kwh(device_id, start, end, cur)
    alarms = _report_alarm_summary(device_id, start, end, cur)
    cur.close()
    conn.close()

    key = next((k for k in tou if k.year == year and k.month == month), None)
    row = None
    if key is not None:
        row = _analyze_bill_month(key, tou[key], demand.get(key), reactive_rows.get(key), tariff)
    reactive = reactive_rows.get(key) if key is not None else None

    # --- Marka paleti (web'deki "klasik" tema ile ayni) ---
    INK = colors.HexColor("#0B1F3A")
    MUTED = colors.HexColor("#64748B")
    BORDER = colors.HexColor("#E2E8F0")
    BG = colors.HexColor("#F4F6F9")
    AMBER = colors.HexColor("#C97A2B")
    TEAL = colors.HexColor("#1B7A72")
    INDIGO = colors.HexColor("#4A5FC1")
    DANGER = colors.HexColor("#C23B3B")
    WARN = colors.HexColor("#C98A1A")

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    W, H = A4
    L = 16 * mm            # sol kenar
    R = W - 16 * mm        # sag kenar
    CW = R - L             # icerik genisligi

    def money(v):
        return f"{v:,.2f} ₺".replace(",", " ")

    def kwh(v):
        return f"{v:,.1f}".replace(",", " ")

    # ---------------- Başlık şeridi ----------------
    band_h = 40 * mm
    c.setFillColor(INK)
    c.rect(0, H - band_h, W, band_h, stroke=0, fill=1)
    # Alt kenara ince marka cizgisi
    c.setFillColor(AMBER)
    c.rect(0, H - band_h, W, 1.4 * mm, stroke=0, fill=1)

    logo = _logo_reader(white=True)
    if logo is not None:
        c.drawImage(logo, L, H - 20 * mm, width=11 * mm, height=11 * mm, mask="auto")
    c.setFillColor(colors.white)
    c.setFont(REPORT_FONT_BOLD, 9)
    c.drawString(L + 14 * mm, H - 14.5 * mm, "BINARY ENERJİ")
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.55))
    c.setFont(REPORT_FONT, 7.5)
    c.drawString(L + 14 * mm, H - 18.5 * mm, "Güç İzleme ve Enerji Analizi")

    c.setFillColor(colors.white)
    c.setFont(REPORT_FONT_BOLD, 19)
    c.drawString(L, H - 32 * mm, "Aylık Enerji Raporu")

    c.setFont(REPORT_FONT_BOLD, 12)
    c.drawRightString(R, H - 14.5 * mm, info["name"])
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.6))
    c.setFont(REPORT_FONT, 8)
    yer = " · ".join(x for x in (info["organization"], info["facility"], info["department"]) if x)
    c.drawRightString(R, H - 19 * mm, yer or device_id)
    c.setFillColor(AMBER)
    c.setFont(REPORT_FONT_BOLD, 13)
    c.drawRightString(R, H - 31 * mm, f"{TR_MONTHS[month - 1]} {year}")

    y = H - band_h - 12 * mm

    if row is None:
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 11)
        c.drawString(L, y, "Bu dönemde cihazdan veri alınmadı.")
        _report_footer(c, W, L, R, INK, MUTED, AMBER)
        c.save()
        return buf.getvalue()

    priced = tariff["active_price"] > 0 or any(
        tariff[k] > 0 for k in ("t1_price", "t2_price", "t3_price"))

    # Sayfa tasmasi olursa devam sayfasi acabilmek icin gereken baglam.
    ctx = {"W": W, "H": H, "L": L, "R": R, "INK": INK, "MUTED": MUTED, "AMBER": AMBER,
           "device_name": info["name"], "period": f"{TR_MONTHS[month - 1]} {year}"}

    # ---------------- Öne çıkan rakam ----------------
    ceza_toplam = row["demand_cost"] + row["reactive_cost"]
    if priced:
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 8.5)
        c.drawString(L, y, "TAHMİNİ TOPLAM FATURA")
        c.setFillColor(INK)
        c.setFont(REPORT_FONT_BOLD, 30)
        c.drawString(L, y - 12 * mm, money(row["total_cost"]))
        if ceza_toplam > 0:
            pay = ceza_toplam / row["total_cost"] * 100 if row["total_cost"] else 0
            c.setFillColor(DANGER)
            c.setFont(REPORT_FONT_BOLD, 9.5)
            c.drawString(L, y - 17.5 * mm,
                         f"Bunun {money(ceza_toplam)}'si (%{pay:.0f}) ceza kalemi.")
    else:
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 8.5)
        c.drawString(L, y, "DÖNEM TÜKETİMİ")
        c.setFillColor(INK)
        c.setFont(REPORT_FONT_BOLD, 30)
        c.drawString(L, y - 12 * mm, f"{kwh(row['active_kwh'])} kWh")

    # Sağdaki küçük göstergeler
    # Etiketler dogrudan buyuk harfle yaziliyor: Python'un upper()'i Turkce
    # i -> İ donusumunu yapmiyor, "Tüketim".upper() "TÜKETIM" veriyor.
    chips = [
        ("TÜKETİM", f"{kwh(row['active_kwh'])} kWh", INK),
        ("TEPE GÜÇ", f"{row['peak_kw']:.1f} kW" if row["peak_kw"] is not None else "—",
         DANGER if (row.get("overrun_kw") or 0) > 0 else INK),
        ("PUANT ORANI", f"%{row['puant_pct']}" if row["puant_pct"] is not None else "—",
         DANGER if (row["puant_pct"] or 0) > 25 else INK),
    ]
    chip_w = 30 * mm
    cx = R - len(chips) * chip_w
    for label, val, col in chips:
        c.setFillColor(BG)
        c.roundRect(cx, y - 17 * mm, chip_w - 3 * mm, 15 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 7)
        c.drawString(cx + 3 * mm, y - 6.5 * mm, label)
        c.setFillColor(col)
        c.setFont(REPORT_FONT_BOLD, 11)
        c.drawString(cx + 3 * mm, y - 13 * mm, val)
        cx += chip_w
    y -= 24 * mm

    # ---------------- Fatura bileşimi çubuğu ----------------
    if priced and row["total_cost"] > 0:
        parts = [
            ("Aktif enerji", row["active_cost"], AMBER),
            ("Güç aşımı", row["demand_cost"], WARN),
            ("Reaktif ceza", row["reactive_cost"], DANGER),
        ]
        parts = [p for p in parts if p[1] > 0]
        bar_h = 7 * mm
        x = L
        for _, tutar, col in parts:
            seg = CW * (tutar / row["total_cost"])
            c.setFillColor(col)
            c.rect(x, y - bar_h, seg, bar_h, stroke=0, fill=1)
            x += seg
        y -= bar_h + 6 * mm
        lx = L
        for label, tutar, col in parts:
            pct = tutar / row["total_cost"] * 100
            c.setFillColor(col)
            c.circle(lx + 1.4 * mm, y + 1.2 * mm, 1.4 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont(REPORT_FONT_BOLD, 8)
            c.drawString(lx + 4.5 * mm, y + 2.2 * mm, f"{label} · %{pct:.0f}")
            c.setFillColor(MUTED)
            c.setFont(REPORT_FONT, 8)
            c.drawString(lx + 4.5 * mm, y - 1.8 * mm, money(tutar))
            lx += CW / len(parts)
        y -= 9 * mm

    # ---------------- Fatura dökümü ----------------
    y = _section_title(c, "Fatura Dökümü", L, y, INK, AMBER)

    kalemler = [
        ("Gündüz", f"{tariff['t1_start']:02d}:00–{tariff['t2_start']:02d}:00",
         f"{kwh(row['t1_kwh'])} kWh", row["t1_cost"], False),
        ("Puant", f"{tariff['t2_start']:02d}:00–{tariff['t3_start']:02d}:00",
         f"{kwh(row['t2_kwh'])} kWh"
         + (f"  (%{row['puant_pct']})" if row["puant_pct"] is not None else ""),
         row["t2_cost"], (row["puant_pct"] or 0) > 25),
        ("Gece", f"{tariff['t3_start']:02d}:00–{tariff['t1_start']:02d}:00",
         f"{kwh(row['t3_kwh'])} kWh", row["t3_cost"], False),
    ]
    if row.get("overrun_kw") is not None:
        kalemler.append((
            "Güç aşımı", f"sözleşme {tariff['contract_power_kw']:g} kW",
            f"tepe {row['peak_kw']:.1f} kW"
            + (f"  →  +{row['overrun_kw']:.1f} kW" if row["overrun_kw"] > 0 else "  →  aşım yok"),
            row["demand_cost"], row["overrun_kw"] > 0))
    if reactive:
        kalemler.append((
            "Reaktif ceza",
            f"limit %{tariff['inductive_limit_pct']:g} / %{tariff['capacitive_limit_pct']:g}",
            f"endüktif %{reactive['inductive_pct']} · kapasitif %{reactive['capacitive_pct']}",
            row["reactive_cost"], row["reactive_cost"] > 0))

    rh = 8 * mm
    for i, (label, alt, detay, tutar, vurgu) in enumerate(kalemler):
        if i % 2 == 0:
            c.setFillColor(BG)
            c.rect(L, y - rh + 2.5 * mm, CW, rh, stroke=0, fill=1)
        if vurgu:
            c.setFillColor(DANGER)
            c.rect(L, y - rh + 2.5 * mm, 1 * mm, rh, stroke=0, fill=1)
        c.setFillColor(DANGER if vurgu else INK)
        c.setFont(REPORT_FONT_BOLD, 9)
        c.drawString(L + 4 * mm, y, label)
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 6.8)
        c.drawString(L + 4 * mm, y - 3.6 * mm, alt)
        c.setFillColor(INK)
        c.setFont(REPORT_FONT, 8.5)
        c.drawString(L + 38 * mm, y, detay)
        if priced:
            c.setFillColor(DANGER if vurgu else INK)
            c.setFont(REPORT_FONT_BOLD, 10)
            c.drawRightString(R - 3 * mm, y, money(tutar))
        y -= rh

    c.setFillColor(INK)
    c.roundRect(L, y - 6 * mm, CW, 10 * mm, 1.5 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(REPORT_FONT_BOLD, 10)
    c.drawString(L + 4 * mm, y - 2.6 * mm, "TOPLAM")
    c.setFont(REPORT_FONT, 8.5)
    c.drawString(L + 38 * mm, y - 2.6 * mm, f"{kwh(row['active_kwh'])} kWh")
    if priced:
        c.setFont(REPORT_FONT_BOLD, 12)
        c.drawRightString(R - 3 * mm, y - 3 * mm, money(row["total_cost"]))
    y -= 14 * mm

    if not priced:
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 8)
        c.drawString(L, y, "Tutarlar için panelden tarife bilgilerinizi girin; "
                           "bu rapor tüketim kırılımını gösteriyor.")
        y -= 7 * mm

    # ---------------- Günlük tüketim ----------------
    y = _page_break(c, ctx, y, 45)
    y = _section_title(c, "Günlük Tüketim", L, y, INK, INDIGO)
    chart_h = 24 * mm
    panel_top = y + 3 * mm
    c.setFillColor(BG)
    c.roundRect(L, panel_top - chart_h - 9 * mm, CW, chart_h + 9 * mm, 2 * mm, stroke=0, fill=1)
    base = panel_top - chart_h - 4 * mm
    if daily:
        peak = max(v for _, v in daily) or 1.0
        # Yatay kılavuz çizgileri
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.4)
        for f in (0.5, 1.0):
            c.line(L + 3 * mm, base + chart_h * f, R - 3 * mm, base + chart_h * f)
        bw = (CW - 6 * mm) / max(len(daily), 1)
        for i, (gun, val) in enumerate(daily):
            h = (val / peak) * chart_h if peak > 0 else 0
            c.setFillColor(AMBER if val > 0 else BORDER)
            c.rect(L + 3 * mm + i * bw + bw * 0.2, base, bw * 0.6, max(h, 0.3), stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.7)
        c.line(L + 3 * mm, base, R - 3 * mm, base)
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 6.5)
        c.drawString(L + 3 * mm, base - 4 * mm, daily[0][0].strftime("%d.%m"))
        c.drawRightString(R - 3 * mm, base - 4 * mm, daily[-1][0].strftime("%d.%m"))
        c.drawRightString(R - 3 * mm, base + chart_h + 1.5 * mm, f"en yüksek gün: {kwh(peak)} kWh")
    else:
        c.setFillColor(MUTED)
        c.setFont(REPORT_FONT, 9)
        c.drawString(L + 4 * mm, base + chart_h / 2, "Bu dönemde günlük tüketim verisi yok.")
    y = base - 10 * mm

    # ---------------- Öneriler ----------------
    y = _page_break(c, ctx, y, 30)
    y = _section_title(c, "Bu Dönemde Dikkat Edilmesi Gerekenler", L, y, INK, TEAL)
    tip_style = ParagraphStyle("tip", fontName=REPORT_FONT, fontSize=8.5,
                               leading=12, textColor=INK)
    for tip in _report_recommendations(row, reactive, tariff):
        para = Paragraph(tip, tip_style)
        _, ph = para.wrap(CW - 8 * mm, 40 * mm)
        y = _page_break(c, ctx, y, ph / mm + 6)
        c.setFillColor(TEAL)
        c.rect(L, y - ph + 1 * mm, 1 * mm, ph + 1 * mm, stroke=0, fill=1)
        para.drawOn(c, L + 5 * mm, y - ph + 1 * mm)
        y -= ph + 4 * mm

    # ---------------- Alarm özeti ----------------
    y -= 2 * mm
    y = _page_break(c, ctx, y, 20)
    y = _section_title(c, "Alarm Özeti", L, y, INK, DANGER)
    if alarms:
        c.setFont(REPORT_FONT, 8.5)
        for a in alarms:
            y = _page_break(c, ctx, y, 10)
            c.setFillColor(DANGER if a["open"] else colors.HexColor("#94A3B8"))
            c.circle(L + 1.5 * mm, y + 1 * mm, 1.2 * mm, stroke=0, fill=a["open"])
            if not a["open"]:
                c.setStrokeColor(colors.HexColor("#94A3B8"))
                c.setLineWidth(0.6)
                c.circle(L + 1.5 * mm, y + 1 * mm, 1.2 * mm, stroke=1, fill=0)
            c.setFillColor(INK if a["open"] else MUTED)
            c.drawString(L + 5 * mm, y, a["message"][:76])
            c.setFillColor(MUTED)
            c.setFont(REPORT_FONT, 7.5)
            c.drawRightString(R, y, f"{a['count']} kez" + (" · sürüyor" if a["open"] else ""))
            c.setFont(REPORT_FONT, 8.5)
            y -= 6 * mm
    else:
        c.setFillColor(TEAL)
        c.setFont(REPORT_FONT, 8.5)
        c.drawString(L, y, "Bu dönemde alarm oluşmadı.")

    _report_footer(c, W, L, R, INK, MUTED, AMBER)
    c.save()
    return buf.getvalue()


# Alt bilgi seridinin ustunde birakilan guvenli bosluk (mm).
REPORT_BOTTOM_MARGIN = 22


def _page_break(c, ctx, y, needed_mm: float):
    """Kalan yer yetmiyorsa yeni sayfa acar ve yeni y konumunu doner.

    Rapor icerigi (alarm sayisi, oneri uzunlugu) donemden doneme degistigi
    icin sabit yerlesim guvenli degil -- ilk tasarimda alarm ozeti sayfaya
    sigmayip sessizce kesilmisti. Artik kesilmek yerine tasiyor.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    if y - needed_mm * mm > REPORT_BOTTOM_MARGIN * mm:
        return y

    _report_footer(c, ctx["W"], ctx["L"], ctx["R"], ctx["INK"], ctx["MUTED"], ctx["AMBER"])
    c.showPage()

    W, H, L, R = ctx["W"], ctx["H"], ctx["L"], ctx["R"]
    band = 16 * mm
    c.setFillColor(ctx["INK"])
    c.rect(0, H - band, W, band, stroke=0, fill=1)
    c.setFillColor(ctx["AMBER"])
    c.rect(0, H - band, W, 1 * mm, stroke=0, fill=1)
    logo = _logo_reader(white=True)
    if logo is not None:
        c.drawImage(logo, L, H - 11.5 * mm, width=6 * mm, height=6 * mm, mask="auto")
    c.setFillColor(colors.white)
    c.setFont(REPORT_FONT_BOLD, 8)
    c.drawString(L + 8 * mm, H - 9.5 * mm, "BINARY ENERJİ")
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.6))
    c.setFont(REPORT_FONT, 7.5)
    c.drawRightString(R, H - 9.5 * mm,
                      f"{ctx['device_name']} · {ctx['period']}")
    return H - band - 12 * mm


def _section_title(c, text: str, L, y, ink, accent):
    """Renkli kucuk aksan cubugu + baslik. Yeni y konumunu doner."""
    from reportlab.lib.units import mm
    c.setFillColor(accent)
    c.rect(L, y - 0.5 * mm, 3.5 * mm, 3.5 * mm, stroke=0, fill=1)
    c.setFillColor(ink)
    c.setFont(REPORT_FONT_BOLD, 11)
    c.drawString(L + 6 * mm, y, text)
    return y - 9 * mm


def _report_footer(c, W, L, R, ink, muted, accent):
    from reportlab.lib.units import mm
    c.setFillColor(ink)
    c.rect(0, 0, W, 14 * mm, stroke=0, fill=1)
    c.setFillColor(accent)
    c.rect(0, 14 * mm, W, 0.8 * mm, stroke=0, fill=1)
    logo = _logo_reader(white=True)
    if logo is not None:
        c.drawImage(logo, L, 4.5 * mm, width=5.5 * mm, height=5.5 * mm, mask="auto")
    from reportlab.lib import colors as _c
    c.setFillColor(_c.white)
    c.setFont(REPORT_FONT_BOLD, 7.5)
    c.drawString(L + 7.5 * mm, 6.5 * mm, "BINARY ENERJİ")
    c.setFillColor(_c.Color(1, 1, 1, alpha=0.55))
    c.setFont(REPORT_FONT, 6.5)
    c.drawString(L + 7.5 * mm, 3.5 * mm, "binaryenerji.com")
    c.drawRightString(R, 5 * mm,
                      "Tutarlar panelde girilen tarife bilgilerine göre hesaplanmış "
                      "tahminlerdir; resmî fatura yerine geçmez.")


@app.get("/reports/monthly-pdf")
def monthly_pdf(device_id: str, year: int | None = None, month: int | None = None,
                user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    if year is None or month is None:
        year, month = _previous_month()
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="Geçersiz ay")
    if not 2020 <= year <= datetime.now(timezone.utc).year + 1:
        raise HTTPException(status_code=400, detail="Geçersiz yıl")
    try:
        pdf = build_monthly_pdf(device_id, year, month)
    except Exception as e:
        logger.error("Aylik rapor uretilemedi (%s %s-%s): %s", device_id, year, month, e)
        raise HTTPException(status_code=500, detail="Rapor oluşturulamadı")
    filename = f"{device_id}-{year}-{month:02d}-enerji-raporu.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class MonthlyReportPref(BaseModel):
    enabled: bool


class AlarmEmailPref(BaseModel):
    enabled: bool


@app.post("/me/alarm-email")
def set_alarm_email_pref(payload: AlarmEmailPref, user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET alarm_email = %s WHERE username = %s", (payload.enabled, user))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Alarm e-postası tercihi güncellendi", "enabled": payload.enabled}


@app.post("/me/monthly-report")
def set_monthly_report_pref(payload: MonthlyReportPref, user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET monthly_report = %s WHERE username = %s", (payload.enabled, user))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Aylık rapor tercihi güncellendi", "enabled": payload.enabled}


def send_monthly_reports(year: int | None = None, month: int | None = None) -> dict:
    """Aylik raporlari uretip e-posta ile gonderir. Ayin 1'inde cron tetikler.

    Kullanici basina TEK e-posta gonderiliyor, erisebildigi her cihaz icin bir
    PDF ekiyle -- cihaz basina ayri e-posta cok cihazli musteride spam olurdu.
    Erisim kapsami _ACCESSIBLE_DEVICES_SQL uzerinden cozuluyor; bu sorgu tum
    sistemde tek yerde tanimli oldugu icin rapor kapsami ile panelde gorulen
    kapsam ayrisamaz.
    """
    if year is None or month is None:
        year, month = _previous_month()

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, email FROM users
        WHERE monthly_report = true AND is_verified = true
          AND email IS NOT NULL AND email <> ''
    """)
    recipients = cur.fetchall()

    sent = 0
    skipped = 0
    failed = 0
    for username, email in recipients:
        cur.execute(_ACCESSIBLE_DEVICES_SQL, (username,))
        devices = [(r[0], r[1]) for r in cur.fetchall()][:MONTHLY_REPORT_MAX_DEVICES]
        if not devices:
            skipped += 1
            continue

        attachments = []
        names = []
        for dev_id, dev_name in devices:
            try:
                pdf = build_monthly_pdf(dev_id, year, month)
            except Exception as e:
                logger.error("Aylik rapor uretilemedi (%s): %s", dev_id, e)
                continue
            attachments.append({
                "filename": f"{dev_name}-{year}-{month:02d}.pdf".replace("/", "-"),
                "content": base64.b64encode(pdf).decode(),
            })
            names.append(dev_name)

        if not attachments:
            skipped += 1
            continue

        donem = f"{TR_MONTHS[month - 1]} {year}"
        baslik = names[0] if len(names) == 1 else f"{len(names)} cihaz"
        try:
            resend.Emails.send({
                "from": RESEND_FROM,
                "to": [email],
                "subject": f"{donem} Enerji Raporu — {baslik}",
                "html": (
                    f"<p><b>{donem}</b> dönemine ait enerji raporunuz ekte.</p>"
                    f"<p>Rapor şunları içeriyor: faturanın kalem kalem dökümü "
                    f"(zaman dilimleri, güç aşımı, reaktif ceza), günlük tüketim grafiği, "
                    f"bu dönemde dikkat edilmesi gerekenler ve alarm özeti.</p>"
                    f"<p>Cihazlar: {', '.join(names)}</p>"
                    f"<p><a href='{SITE_URL}'>Panoyu aç</a></p>"
                    f"<p style='font-size:12px;color:#6B7A90'>Bu e-postayı almak istemiyorsanız "
                    f"hesap sayfanızdan aylık raporu kapatabilirsiniz.</p>"
                ),
                "attachments": attachments,
            })
            sent += 1
        except Exception as e:
            logger.error("Aylik rapor e-postasi gonderilemedi (%s): %s", username, e)
            failed += 1

    cur.close()
    conn.close()
    result = {"year": year, "month": month, "sent": sent, "skipped": skipped, "failed": failed}
    logger.info("Aylik rapor gonderimi: %s", result)
    return result


@app.post("/admin/monthly-reports")
def trigger_monthly_reports(year: int | None = None, month: int | None = None,
                            user: str = Depends(require_admin)):
    return send_monthly_reports(year, month)

# ---------- Push bildirimi ----------
# Alarmlar bugune kadar yalnizca e-posta ile gidiyordu; gerilim alarmi gibi
# zamana duyarli bir olayda e-posta cok yavas kalabiliyor. Bu katman abonelik
# kaydini ve gonderimi tasima-bagimsiz tutuyor: su an sadece Web Push var ama
# native FCM/APNs eklendiginde push_subscriptions tablosuna yeni bir transport
# satiri olarak katilacak, dagitim mantigi degismeyecek.

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:no-reply@binaryenerji.com")
PUSH_ENABLED = bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)

# Ust uste bu kadar basarisiz gonderimden sonra abonelik silinir. Tarayici
# aboneligi iptal ettiginde push servisi 404/410 doner; onlari zaten aninda
# siliyoruz, bu sayac gecici olmayan diger hatalar icin.
PUSH_MAX_FAILURES = 5


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@app.get("/push/vapid-key")
def push_vapid_key():
    """Tarayicinin abone olurken kullanacagi acik anahtar. Kimlik dogrulama
    gerekmiyor -- acik anahtar zaten herkese acik olmak uzere tasarlanmis."""
    if not PUSH_ENABLED:
        raise HTTPException(status_code=503, detail="Push bildirimi yapılandırılmamış")
    return {"public_key": VAPID_PUBLIC_KEY}


@app.post("/push/subscribe")
def push_subscribe(payload: PushSubscriptionRequest, user: str = Depends(require_auth)):
    if not PUSH_ENABLED:
        raise HTTPException(status_code=503, detail="Push bildirimi yapılandırılmamış")
    conn = db_connect()
    cur = conn.cursor()
    # Ayni endpoint baska bir hesaba aitse ona devrediyoruz: kullanici ayni
    # tarayicida hesap degistirdiginde eski hesaba bildirim gitmemeli.
    cur.execute("""
        INSERT INTO push_subscriptions (username, transport, endpoint, p256dh, auth, user_agent)
        VALUES (%s, 'webpush', %s, %s, %s, %s)
        ON CONFLICT (endpoint) DO UPDATE SET
            username = EXCLUDED.username,
            p256dh = EXCLUDED.p256dh,
            auth = EXCLUDED.auth,
            user_agent = EXCLUDED.user_agent,
            failure_count = 0
    """, (user, payload.endpoint, payload.p256dh, payload.auth,
          (payload.user_agent or "")[:200]))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Bildirimler açıldı"}


@app.post("/push/unsubscribe")
def push_unsubscribe(payload: PushUnsubscribeRequest, user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s AND username = %s",
                (payload.endpoint, user))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Bildirimler kapatıldı"}


@app.get("/push/subscriptions")
def push_list_subscriptions(user: str = Depends(require_auth)):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, transport, user_agent, created_at, last_success
        FROM push_subscriptions WHERE username = %s ORDER BY created_at DESC
    """, (user,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "transport": r[1], "user_agent": r[2],
             "created_at": r[3], "last_success": r[4]} for r in rows]


def _push_recipients(device_id: str, cur) -> list[tuple]:
    """Cihaza erisebilen kullanicilarin push abonelikleri.

    Kapsam _ACCESSIBLE_DEVICES_SQL uzerinden cozuluyor -- bildirimi kimin
    alacagi ile panelde cihazi kimin gordugu ayrisamasin diye. (Alarm
    E-POSTASI hala yalnizca cihaz sahibine gidiyor; bu, organizasyon
    hiyerarsisinden onceki davranis ve ayrica ele alinmali.)
    """
    izinli = users_with_device_access(device_id, cur)
    if not izinli:
        return []
    cur.execute("""
        SELECT id, endpoint, p256dh, auth FROM push_subscriptions
        WHERE transport = 'webpush' AND username = ANY(%s)
    """, (izinli,))
    return cur.fetchall()


def _push_send_one(sub_id: int, endpoint: str, p256dh: str, auth: str,
                   payload: dict, cur) -> bool:
    if IS_STAGING:
        logger.info("[STAGING] push bildirimi gonderilmedi (abonelik %s)", sub_id)
        return True
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info={"endpoint": endpoint,
                               "keys": {"p256dh": p256dh, "auth": auth}},
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=10,
        )
        cur.execute("UPDATE push_subscriptions SET last_success = now(), failure_count = 0 "
                    "WHERE id = %s", (sub_id,))
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        # 404/410: tarayici aboneligi iptal etmis, kalici olarak gecersiz.
        if status in (404, 410):
            cur.execute("DELETE FROM push_subscriptions WHERE id = %s", (sub_id,))
            logger.info("Gecersiz push aboneligi silindi (%s)", status)
        else:
            cur.execute("UPDATE push_subscriptions SET failure_count = failure_count + 1 "
                        "WHERE id = %s", (sub_id,))
            cur.execute("DELETE FROM push_subscriptions WHERE id = %s AND failure_count >= %s",
                        (sub_id, PUSH_MAX_FAILURES))
            logger.warning("Push gonderilemedi (%s): %s", status, e)
        return False
    except Exception as e:
        logger.error("Push gonderim hatasi: %s", e)
        return False


def push_notify(device_id: str, title: str, body: str, tag: str | None = None) -> int:
    """Cihaza erisimi olan herkese push gonderir. Kac gonderim basarili
    oldugunu doner. Alarm akisini bloklamamasi icin cagiran taraf ayri bir
    thread'de calistirmali."""
    if not PUSH_ENABLED:
        return 0
    sent = 0
    try:
        conn = db_connect()
        cur = conn.cursor()
        payload = {"title": title, "body": body, "url": SITE_URL,
                   "tag": tag or f"alarm-{device_id}"}
        for sub_id, endpoint, p256dh, auth in _push_recipients(device_id, cur):
            if _push_send_one(sub_id, endpoint, p256dh, auth, payload, cur):
                sent += 1
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error("Push bildirimi gonderilemedi (%s): %s", device_id, e)
    return sent

# ---------- Güç kalitesi (EN 50160) ----------
# EN 50160, kamu dagitim sebekesinden saglanan gerilimin ozelliklerini tanimlar.
# Butun sinirlarini 10 DAKIKALIK ortalama degerler uzerinden ve normalde bir
# HAFTALIK gozlem penceresinde degerlendirir -- bu yuzden rapor measurements_10min
# ozetinden okuyor (15 dakikalik ozet guc asimi icindir, buraya uymaz).
#
# ASAGIDAKI SINIRLAR STANDARDIN BENIM KODLAMAM. Resmi bir uygunluk belgesi
# degildir; musteri kendi sebeke isletmecisinin sartlariyla teyit etmeli.
#
# DEGERLENDIRILMEYENLER (cihaz olcmedigi icin): flicker (Plt), tek tek harmonik
# mertebeleri, gerilim dengesizligi (negatif bilesen), gerilim dusme/kesinti
# olay sayimlari. Rapor bunlari acikca "degerlendirilmedi" diye listeliyor ki
# eksiklik sessizce "uygun" gibi gorunmesin.

EN50160_LIMITS = {
    # Gerilim: 10 dk ortalamalarin %95'i Un ±%10 icinde, %100'u +%10/-%15 icinde.
    "voltage_band_pct": (0.90, 1.10),
    "voltage_band_required": 95.0,
    "voltage_abs_band_pct": (0.85, 1.10),
    # Frekans (senkron bagli sebeke): %99,5'i 50 Hz ±%1; %100'u +%4/-%6.
    "frequency_band_hz": (49.5, 50.5),
    "frequency_required": 99.5,
    "frequency_abs_band_hz": (47.0, 52.0),
    # Gerilim toplam harmonik bozulmasi: 10 dk ortalamalarin %95'i <= %8.
    "thd_limit_pct": 8.0,
    "thd_required": 95.0,
}

# Cihazin gercekten olcum yaptigi kovalari ayirt etmek icin. Besleme kesildiginde
# de cihaz kapatildiginda da frekans ve gerilim sifira dusuyor; ikisini birbirinden
# ayirt edemiyoruz, bu yuzden bu kovalar istatistige katilmiyor ve raporda ayrica
# "olcum yok" olarak gosteriliyor.
PQ_MIN_FREQUENCY = 45.0
PQ_MAX_FREQUENCY = 55.0
PQ_MIN_VOLTAGE = 50.0

PQ_NOT_ASSESSED = [
    ("Flicker (Plt)", "cihaz flickermetre içermiyor"),
    ("Tek tek harmonik mertebeleri", "geçmişe dönük mertebe verisi tutulmuyor"),
    ("Gerilim dengesizliği (negatif bileşen)", "cihaz negatif bileşeni raporlamıyor"),
    ("Gerilim düşmesi / kesinti olay sayımları", "10 dk ortalama çözünürlüğü olay sayımına yetmiyor"),
]


def _pq_nominal_voltage(device_id: str, cur) -> float:
    cur.execute("SELECT nominal_voltage FROM device_settings WHERE device_id = %s", (device_id,))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 230.0


def _pq_intervals(device_id: str, since, cur) -> list[dict]:
    cur.execute("""
        SELECT bucket, avg_v1, avg_v2, avg_v3, min_v1, min_v2, min_v3,
               max_v1, max_v2, max_v3, avg_f, min_f, max_f,
               avg_thvd1, avg_thvd2, avg_thvd3
        FROM measurements_10min
        WHERE device_id = %s AND bucket >= %s
        ORDER BY bucket
    """, (device_id, since))
    out = []
    for r in cur.fetchall():
        volt = [r[1], r[2], r[3]]
        freq = r[10]
        gecerli = (
            freq is not None and PQ_MIN_FREQUENCY <= freq <= PQ_MAX_FREQUENCY
            and any(v is not None and v >= PQ_MIN_VOLTAGE for v in volt)
        )
        out.append({
            "bucket": r[0], "v": volt, "v_min": [r[4], r[5], r[6]], "v_max": [r[7], r[8], r[9]],
            "f": freq, "f_min": r[11], "f_max": r[12],
            "thvd": [r[13], r[14], r[15]],
            "gecerli": gecerli,
        })
    return out


def _pq_pct(sayac: int, toplam: int) -> float | None:
    return round(sayac / toplam * 100, 2) if toplam else None


def power_quality_report(device_id: str, days: int, cur) -> dict:
    un = _pq_nominal_voltage(device_id, cur)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = _pq_intervals(device_id, since, cur)
    gecerli = [r for r in rows if r["gecerli"]]
    n = len(gecerli)

    lo95, hi95 = (un * EN50160_LIMITS["voltage_band_pct"][0],
                  un * EN50160_LIMITS["voltage_band_pct"][1])
    lo100, hi100 = (un * EN50160_LIMITS["voltage_abs_band_pct"][0],
                    un * EN50160_LIMITS["voltage_abs_band_pct"][1])
    f_lo, f_hi = EN50160_LIMITS["frequency_band_hz"]
    fa_lo, fa_hi = EN50160_LIMITS["frequency_abs_band_hz"]
    thd_limit = EN50160_LIMITS["thd_limit_pct"]

    def faz_degerleri(anahtar):
        return [[r[anahtar][i] for r in gecerli if r[anahtar][i] is not None] for i in range(3)]

    parametreler = []

    # --- Gerilim ---
    volt_ok = sum(1 for r in gecerli
                  if all(v is None or lo95 <= v <= hi95 for v in r["v"]))
    volt_abs_ok = sum(1 for r in gecerli
                      if all(v is None or lo100 <= v <= hi100 for v in r["v"]))
    faz_v = faz_degerleri("v")
    # pass = None -> "olculmedi". Veri yoklugunu basarisizlik gibi gostermek
    # yaniltici olurdu; arayuz bu ucuncu durumu ayri gosteriyor.
    def gecti(sayac, toplam, gereken):
        if not toplam:
            return None
        return _pq_pct(sayac, toplam) >= gereken

    parametreler.append({
        "key": "voltage",
        "label": "Gerilim",
        "limit": f"Un ±%10 ({lo95:.0f}–{hi95:.0f} V), ölçümlerin %95'i",
        "value_pct": _pq_pct(volt_ok, n),
        "required_pct": EN50160_LIMITS["voltage_band_required"],
        "pass": gecti(volt_ok, n, EN50160_LIMITS["voltage_band_required"]),
        "extra": {
            "mutlak_limit": f"{lo100:.0f}–{hi100:.0f} V, ölçümlerin %100'ü",
            "mutlak_pct": _pq_pct(volt_abs_ok, n),
            "mutlak_pass": (volt_abs_ok == n) if n else None,
            "faz_min": [round(min(v), 1) if v else None for v in faz_v],
            "faz_max": [round(max(v), 1) if v else None for v in faz_v],
        },
    })

    # --- Frekans ---
    frek = [r["f"] for r in gecerli if r["f"] is not None]
    frek_ok = sum(1 for f in frek if f_lo <= f <= f_hi)
    frek_abs_ok = sum(1 for f in frek if fa_lo <= f <= fa_hi)
    parametreler.append({
        "key": "frequency",
        "label": "Frekans",
        "limit": f"{f_lo}–{f_hi} Hz, ölçümlerin %99,5'i",
        "value_pct": _pq_pct(frek_ok, len(frek)),
        "required_pct": EN50160_LIMITS["frequency_required"],
        "pass": gecti(frek_ok, len(frek), EN50160_LIMITS["frequency_required"]),
        "extra": {
            "mutlak_limit": f"{fa_lo}–{fa_hi} Hz, ölçümlerin %100'ü",
            "mutlak_pct": _pq_pct(frek_abs_ok, len(frek)),
            "mutlak_pass": (frek_abs_ok == len(frek)) if frek else None,
            "min": round(min(frek), 3) if frek else None,
            "max": round(max(frek), 3) if frek else None,
        },
    })

    # --- Gerilim harmonik bozulmasi ---
    thd_var = [r for r in gecerli if any(t is not None for t in r["thvd"])]
    thd_ok = sum(1 for r in thd_var
                 if all(t is None or t <= thd_limit for t in r["thvd"]))
    faz_thd = faz_degerleri("thvd")
    parametreler.append({
        "key": "thd",
        "label": "Gerilim Harmonik Bozulması (THD-V)",
        "limit": f"≤ %{thd_limit:g}, ölçümlerin %95'i",
        "value_pct": _pq_pct(thd_ok, len(thd_var)),
        "required_pct": EN50160_LIMITS["thd_required"],
        "pass": gecti(thd_ok, len(thd_var), EN50160_LIMITS["thd_required"]),
        "extra": {
            "faz_max": [round(max(t), 2) if t else None for t in faz_thd],
            "olculen_aralik": len(thd_var),
        },
    })

    # Veri yetersizse "uygun" demek yaniltici olur -- EN 50160 bir haftalik
    # pencere ongoruyor, elimizde daha azi varsa bunu acikca soyluyoruz.
    beklenen_kova = days * 24 * 6
    kapsama = _pq_pct(n, beklenen_kova) or 0.0
    yeterli = n >= 100 and kapsama >= 50.0

    olculebilir = [p for p in parametreler if p["pass"] is not None]
    if not yeterli or not olculebilir:
        verdict = "yetersiz_veri"
    elif all(p["pass"] for p in olculebilir):
        verdict = "uygun"
    else:
        verdict = "uygun_degil"

    return {
        "device_id": device_id,
        "days": days,
        "nominal_voltage": un,
        "intervals": {
            "toplam": len(rows),
            "gecerli": n,
            "olcum_yok": len(rows) - n,
            "beklenen": beklenen_kova,
            "kapsama_pct": kapsama,
        },
        "parameters": parametreler,
        "not_assessed": [{"label": a, "reason": b} for a, b in PQ_NOT_ASSESSED],
        "verdict": verdict,
    }


@app.get("/reports/power-quality")
def get_power_quality(device_id: str, days: int = 7, user: str = Depends(require_subscription)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    days = max(1, min(days, 90))
    conn = db_connect()
    cur = conn.cursor()
    try:
        return power_quality_report(device_id, days, cur)
    finally:
        cur.close()
        conn.close()


class NominalVoltageRequest(BaseModel):
    nominal_voltage: float


@app.post("/devices/{device_id}/nominal-voltage")
def set_nominal_voltage(device_id: str, payload: NominalVoltageRequest,
                        user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    if not 50 <= payload.nominal_voltage <= 1000:
        raise HTTPException(status_code=400, detail="Nominal gerilim 50 ile 1000 V arasında olmalı")
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO device_settings (device_id, nominal_voltage, updated_at)
        VALUES (%s, %s, now())
        ON CONFLICT (device_id) DO UPDATE SET nominal_voltage = EXCLUDED.nominal_voltage,
                                              updated_at = now()
    """, (device_id, payload.nominal_voltage))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Nominal gerilim kaydedildi"}

# ---------- Denetim kaydı ----------
# "Kim, ne zaman, neyi değiştirdi." Kurumsal müşterinin sorduğu ilk sorulardan
# biri; ayrıca bir yanlışlık olduğunda geriye dönüp bakılacak tek yer.
#
# Denetim yazımı ASLA asıl işlemi düşürmemeli: bir kayıt tutulamadı diye
# müşterinin cihaz eklemesi başarısız olamaz. Bu yüzden her çağrı kendi
# try bloğunda ve hata yalnızca log'a düşüyor.

def audit(action: str, actor: str | None = None, organization_id: int | None = None,
          entity_type: str | None = None, entity_id: str | None = None,
          detail: dict | None = None, request: Request | None = None,
          cur=None) -> None:
    """Denetim kaydı yazar.

    cur verilirse ÇAĞIRANIN işlemine katılır -- kayıt ile işlem birlikte
    commit olur, yani "yapıldı ama kaydedilmedi" durumu oluşmaz. Verilmezse
    kendi bağlantısını açar.
    """
    ip = None
    if request is not None:
        try:
            ip = (request.headers.get("x-real-ip")
                  or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                  or (request.client.host if request.client else None))
        except Exception:
            ip = None

    sql = """
        INSERT INTO audit_log (actor, organization_id, action, entity_type, entity_id, detail, ip)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    degerler = (actor, organization_id, action, entity_type,
                str(entity_id) if entity_id is not None else None,
                json.dumps(detail, ensure_ascii=False) if detail else None, ip)
    try:
        if cur is not None:
            cur.execute(sql, degerler)
            return
        conn = db_connect()
        c = conn.cursor()
        try:
            c.execute(sql, degerler)
            conn.commit()
        finally:
            c.close()
            conn.close()
    except Exception as e:
        # Denetim kaydı tutulamadı diye asıl işlem düşmemeli.
        logger.error("Denetim kaydı yazılamadı (%s): %s", action, e)


def _actor_org(username: str, cur) -> int | None:
    cur.execute("SELECT organization_id FROM org_members WHERE username = %s LIMIT 1", (username,))
    row = cur.fetchone()
    return row[0] if row else None


AUDIT_LABELS = {
    "device.add": "Cihaz eklendi",
    "device.remove": "Cihaz silindi",
    "device.rename": "Cihaz adı değiştirildi",
    "device.move": "Cihaz taşındı",
    "device.command": "Cihaza komut gönderildi",
    "device.ota": "Firmware güncellemesi başlatıldı",
    "device.ct_ratio": "Akım trafo oranı değiştirildi",
    "tariff.update": "Tarife ayarları değiştirildi",
    "alarm_rule.create": "Alarm kuralı eklendi",
    "alarm_rule.delete": "Alarm kuralı silindi",
    "alarm_rule.toggle": "Alarm kuralı açıldı/kapatıldı",
    "facility.create": "Tesis eklendi",
    "facility.delete": "Tesis silindi",
    "department.create": "Bölüm eklendi",
    "department.delete": "Bölüm silindi",
    "member.update": "Üye yetkisi değiştirildi",
    "member.remove": "Üye çıkarıldı",
    "invite.create": "Davet gönderildi",
    "invite.accept": "Davet kabul edildi",
    "invite.cancel": "Davet iptal edildi",
    "account.email_change": "E-posta değişikliği talep edildi",
    "account.password_change": "Şifre değiştirildi",
    "account.export": "Kişisel veriler dışa aktarıldı",
    "account.delete": "Hesap silindi",
    "subscription.update": "Abonelik güncellendi",
    "auth.login_failed": "Başarısız giriş denemesi",
}


@app.get("/organization/audit")
def get_audit_log(limit: int = 100, user: str = Depends(require_auth)):
    """Organizasyonun denetim kaydı. Yalnızca organizasyon yöneticisi.

    Kapsam organizasyona göre: bir müşteri başka müşterinin kaydını göremez.
    """
    membership = get_membership(user)
    if not membership or membership["role"] != "org_admin":
        raise HTTPException(status_code=403, detail="Bu kaydı yalnızca organizasyon yöneticisi görebilir")
    limit = max(1, min(limit, 500))
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT at, actor, action, entity_type, entity_id, detail, ip
        FROM audit_log WHERE organization_id = %s ORDER BY at DESC LIMIT %s
    """, (membership["organization_id"], limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "at": r[0], "actor": r[1], "action": r[2],
        "label": AUDIT_LABELS.get(r[2], r[2]),
        "entity_type": r[3], "entity_id": r[4], "detail": r[5], "ip": r[6],
    } for r in rows]


# ---------- KVKK: veri dışa aktarma ve hesap silme ----------
# KVKK madde 11, ilgili kişiye verilerinin akıbetini öğrenme, düzeltilmesini
# ve silinmesini isteme hakkı veriyor. Bu iki uç nokta o hakları e-posta
# yazışmasına gerek kalmadan kullanılabilir kılıyor.

@app.get("/me/data-export")
def export_my_data(user: str = Depends(require_auth), request: Request = None):
    """Kullanıcıya ait kişisel verilerin tamamı, makine okunur biçimde.

    Cihaz ÖLÇÜM verisi buraya dahil edilmiyor: o veri kişiye değil
    organizasyona ait ve milyonlarca satır olabiliyor. Panelden Excel olarak
    zaten indirilebiliyor.
    """
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, first_name, last_name, email, phone, created_at,
               is_verified, role, monthly_report, alarm_email, avatar_updated_at
        FROM users WHERE username = %s
    """, (user,))
    u = cur.fetchone()
    if not u:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    veri = {
        "hesap": {
            "kullanici_adi": u[0], "ad": u[1], "soyad": u[2], "eposta": u[3],
            "telefon": u[4], "kayit_tarihi": u[5].isoformat() if u[5] else None,
            "eposta_dogrulandi": u[6], "rol": u[7],
            "aylik_rapor_tercihi": u[8], "alarm_eposta_tercihi": u[9],
            "profil_fotografi_var": u[10] is not None,
        },
    }

    cur.execute("""
        SELECT o.name, m.role FROM org_members m
        JOIN organizations o ON o.id = m.organization_id WHERE m.username = %s
    """, (user,))
    veri["organizasyon_uyelikleri"] = [{"organizasyon": r[0], "rol": r[1]} for r in cur.fetchall()]

    cur.execute("SELECT device_id, name, created_at FROM devices WHERE owner_username = %s", (user,))
    veri["kayitli_cihazlar"] = [
        {"cihaz_id": r[0], "ad": r[1], "eklenme": r[2].isoformat() if r[2] else None}
        for r in cur.fetchall()]

    cur.execute("SELECT transport, user_agent, created_at FROM push_subscriptions WHERE username = %s", (user,))
    veri["bildirim_abonelikleri"] = [
        {"tur": r[0], "cihaz": r[1], "olusturma": r[2].isoformat() if r[2] else None}
        for r in cur.fetchall()]

    cur.execute("""
        SELECT at, action, entity_type, entity_id FROM audit_log
        WHERE actor = %s ORDER BY at DESC LIMIT 1000
    """, (user,))
    veri["islem_gecmisi"] = [
        {"zaman": r[0].isoformat(), "islem": AUDIT_LABELS.get(r[1], r[1]),
         "nesne_turu": r[2], "nesne": r[3]} for r in cur.fetchall()]

    veri["aciklama"] = (
        "Bu dosya KVKK kapsamındaki kişisel verilerinizi içerir. Cihaz ölçüm "
        "verileri organizasyona ait olduğu için burada yer almaz; panelden "
        "Excel olarak indirilebilir."
    )
    veri["olusturma_zamani"] = datetime.now(timezone.utc).isoformat()

    org_id = _actor_org(user, cur)
    cur.close()
    conn.close()
    audit("account.export", actor=user, organization_id=org_id, request=request)

    return Response(
        content=json.dumps(veri, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{user}-kisisel-veriler.json"'},
    )


class DeleteAccountRequest(BaseModel):
    password: str
    confirm: str   # kullanıcı adını yazarak onaylama


@app.post("/me/delete")
def delete_my_account(payload: DeleteAccountRequest, user: str = Depends(require_auth),
                      request: Request = None):
    """Hesabı ve kişisel verileri siler (KVKK madde 11).

    Cihazlar SILINMEZ: organizasyona ait donanım kayıtları ve ölçüm geçmişi
    kişisel veri değil. Sahiplik aynı organizasyondaki başka bir yöneticiye
    devredilir; devredilecek kimse yoksa silme reddedilir ve kullanıcıya önce
    devretmesi söylenir -- sessizce cihazları öksüz bırakmak veya müşterinin
    verisini silmek kabul edilemez.

    Denetim kaydı SILINMEZ, anonimleştirilir: izin varlık sebebi kullanıcı
    silinse de "ne oldu" sorusunu cevaplayabilmek.
    """
    if payload.confirm.strip() != user:
        raise HTTPException(status_code=400, detail="Onay için kullanıcı adınızı doğru yazmalısınız")
    check_rate_limit(f"delete:{user}", max_attempts=5, window_seconds=60 * 60)

    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash FROM users WHERE username = %s", (user,))
        row = cur.fetchone()
        if not row or not bcrypt.checkpw(payload.password.encode(), row[0].encode()):
            raise HTTPException(status_code=403, detail="Şifre hatalı")

        org_id = _actor_org(user, cur)

        cur.execute("SELECT count(*) FROM devices WHERE owner_username = %s", (user,))
        cihaz_sayisi = cur.fetchone()[0]
        devralan = None
        if cihaz_sayisi:
            cur.execute("""
                SELECT m.username FROM org_members m
                WHERE m.organization_id = %s AND m.role = 'org_admin' AND m.username <> %s
                ORDER BY m.id LIMIT 1
            """, (org_id, user))
            r = cur.fetchone()
            if not r:
                raise HTTPException(
                    status_code=409,
                    detail=f"Hesabınıza kayıtlı {cihaz_sayisi} cihaz var ve devredilecek başka bir "
                           f"organizasyon yöneticisi yok. Önce bir yönetici davet edin, sonra silin.")
            devralan = r[0]
            cur.execute("UPDATE devices SET owner_username = %s WHERE owner_username = %s",
                        (devralan, user))

        # Denetim izi kalsın ama kişiyle ilişkilendirilemesin.
        anonim = f"silinmiş-kullanıcı-{abs(hash(user)) % 100000}"
        cur.execute("UPDATE audit_log SET actor = %s WHERE actor = %s", (anonim, user))

        cur.execute("INSERT INTO deletion_requests (user_hash, note) VALUES (%s, %s)",
                    (hashlib.sha256(user.encode()).hexdigest(),
                     f"cihaz devri: {devralan}" if devralan else "cihaz yok"))

        audit("account.delete", actor=anonim, organization_id=org_id,
              detail={"devredilen_cihaz": cihaz_sayisi, "devralan": devralan},
              request=request, cur=cur)

        # org_members, push_subscriptions, org_invites CASCADE ile gidiyor.
        cur.execute("DELETE FROM users WHERE username = %s", (user,))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error("Hesap silme hatasi (%s): %s", user, e)
        raise HTTPException(status_code=500, detail="Hesap silinemedi")
    finally:
        cur.close()
        conn.close()

    return {"message": "Hesabınız ve kişisel verileriniz silindi."}

# ---------- WebSocket: Canlı veri ----------
connected_clients: list[tuple[WebSocket, str]] = []
device_status: dict[str, dict] = {}  # device_id -> {"status": "online"|"offline", "changed_at": iso}

def _websocket_subscription_ok(username: str) -> bool:
    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT organization_id FROM org_members WHERE username = %s LIMIT 1", (username,))
        row = cur.fetchone()
        if not row:
            return True  # organizasyonu yok -- erisim zaten bos
        return subscription_state(row[0], cur)["active"]
    except Exception as e:
        # Abonelik kontrolu patlarsa musteriyi disari atmiyoruz: yanlis
        # pozitif bir kilit, gecici bir sizintidan daha kotu.
        logger.error("WebSocket abonelik kontrolu hatasi (%s): %s", username, e)
        return True
    finally:
        cur.close()
        conn.close()


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None, device_id: str | None = None):
    username = token and verify_token(token)
    if not username or not device_id or not is_device_owner(username, device_id):
        await websocket.close(code=1008)
        return
    # Canli veri akisi da abonelige tabi -- Depends() WebSocket'te REST'teki
    # gibi calismadigi icin kontrol elle yapiliyor. Bu unutulursa suresi dolmus
    # musteri panelin en degerli parcasini kullanmaya devam eder.
    if not _websocket_subscription_ok(username):
        await websocket.close(code=1008, reason="Abonelik sona erdi")
        return
    await websocket.accept()
    connected_clients.append((websocket, device_id))
    status = device_status.get(device_id)
    if status:
        await websocket.send_json({"type": "status", "esp32_status": status["status"], "changed_at": status["changed_at"]})
    try:
        while True:
            await websocket.receive_text()  # istemciden bağlantıyı canlı tutmak için
    except WebSocketDisconnect:
        connected_clients.remove((websocket, device_id))

async def broadcast(data: dict, device_id: str):
    dead = []
    for client, watched_device_id in connected_clients:
        if watched_device_id != device_id:
            continue
        try:
            await client.send_json(data)
        except Exception:
            dead.append((client, watched_device_id))
    for d in dead:
        connected_clients.remove(d)

# ---------- MQTT: Ayrı thread'de dinle, DB'ye yaz + WS'e push et ----------
def mqtt_thread():
    # Uzun omurlu, autocommit baglanti -- havuza GIRMIYOR:
    # havuzdan bir baglantiyi sonsuza kadar tutmak havuzu daraltirdi.
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    def on_connect(client, userdata, flags, rc, properties=None):
        print("MQTT broker'a baglanildi, rc:", rc)
        client.subscribe(MQTT_LIVE_WILDCARD)
        client.subscribe(MQTT_ENERGY_WILDCARD)
        client.subscribe(MQTT_STATUS_WILDCARD)
        client.subscribe(MQTT_STATS_WILDCARD)
        client.subscribe(MQTT_PEAKS_WILDCARD)
        client.subscribe(MQTT_DEMAND_WILDCARD)
        client.subscribe(MQTT_HARMONICS_WILDCARD)
        client.subscribe(MQTT_INFO_WILDCARD)

    def handle_status(device_id: str, payload: str):
        status = payload.strip()
        changed_at = datetime.utcnow().isoformat() + "Z"
        device_status[device_id] = {"status": status, "changed_at": changed_at}
        if main_loop:
            asyncio.run_coroutine_threadsafe(
                broadcast({"type": "status", "esp32_status": status, "changed_at": changed_at}, device_id),
                main_loop,
            )

    def handle_live(device_id: str, data: dict):
        cur.execute("""
            INSERT INTO measurements
            (device_id, v1, i1, p1, q1, s1, f1, cos1, pf1, thd1, thvd1,
             v2, i2, p2, q2, s2, f2, cos2, pf2, thd2, thvd2,
             v3, i3, p3, q3, s3, f3, cos3, pf3, thd3, thvd3,
             v_neutral, i_neutral, vL12, vL23, vL31)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s)
        """, (
            device_id,
            data.get("v1"), data.get("i1"), data.get("p1"), data.get("q1"), data.get("s1"),
            data.get("f1"), data.get("cos1"), data.get("pf1"), data.get("thd1"), data.get("thvd1"),
            data.get("v2"), data.get("i2"), data.get("p2"), data.get("q2"), data.get("s2"),
            data.get("f2"), data.get("cos2"), data.get("pf2"), data.get("thd2"), data.get("thvd2"),
            data.get("v3"), data.get("i3"), data.get("p3"), data.get("q3"), data.get("s3"),
            data.get("f3"), data.get("cos3"), data.get("pf3"), data.get("thd3"), data.get("thvd3"),
            data.get("vN"), data.get("iN"), data.get("vL12"), data.get("vL23"), data.get("vL31"),
        ))
        # WebSocket istemcilerine push et (ana event loop'a köprü)
        if main_loop:
            asyncio.run_coroutine_threadsafe(broadcast(data, device_id), main_loop)
        # Alarm kurallarini degerlendir. Hata olursa olcum akisini bozmasin diye
        # ayri try blogunda -- alarm sistemi cokse bile veri toplama devam etmeli.
        try:
            evaluate_alarms(device_id, data, cur)
        except Exception as e:
            logger.error("Alarm degerlendirme hatasi (%s): %s", device_id, e)

    def handle_energy(device_id: str, data: dict):
        cur.execute("""
            INSERT INTO device_energy
            (device_id, active_wh_tuketim, inductive_varh_tuketim, capacitive_varh_tuketim,
             active_wh_uretim, inductive_varh_uretim, capacitive_varh_uretim)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            device_id,
            data.get("active_wh_tuketim"), data.get("inductive_varh_tuketim"), data.get("capacitive_varh_tuketim"),
            data.get("active_wh_uretim"), data.get("inductive_varh_uretim"), data.get("capacitive_varh_uretim"),
        ))
        if data.get("ct_ratio") is not None or data.get("fw_version") is not None:
            cur.execute("""
                INSERT INTO device_settings (device_id, ct_ratio, fw_version, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (device_id) DO UPDATE SET
                    ct_ratio = COALESCE(EXCLUDED.ct_ratio, device_settings.ct_ratio),
                    fw_version = COALESCE(EXCLUDED.fw_version, device_settings.fw_version),
                    updated_at = now()
            """, (device_id, data.get("ct_ratio"), data.get("fw_version")))

    def handle_stats(device_id: str, data: dict):
        values = [data.get(k) for k in STATS_JSON_KEYS]
        placeholders = ", ".join(["%s"] * len(STATS_COLUMNS))
        cur.execute(
            f"INSERT INTO device_stats (device_id, {', '.join(STATS_COLUMNS)}) VALUES (%s, {placeholders})",
            (device_id, *values),
        )

    def handle_peaks(device_id: str, direction: str, data: dict):
        values = [data.get(k) for k in PEAKS_JSON_KEYS]
        placeholders = ", ".join(["%s"] * len(PEAKS_COLUMNS))
        cur.execute(
            f"INSERT INTO device_peaks (device_id, direction, {', '.join(PEAKS_COLUMNS)}) VALUES (%s, %s, {placeholders})",
            (device_id, direction, *values),
        )

    def handle_demand(device_id: str, direction: str, data: dict):
        values = [data.get(k) for k in DEMAND_JSON_KEYS]
        placeholders = ", ".join(["%s"] * len(DEMAND_COLUMNS))
        cur.execute(
            f"INSERT INTO device_demand (device_id, direction, {', '.join(DEMAND_COLUMNS)}) VALUES (%s, %s, {placeholders})",
            (device_id, direction, *values),
        )

    def handle_harmonics(device_id: str, signal_type: str, data: dict):
        # Harmonik JSON alan adlari (thd1, h3_l1, ...) DB sutun adlariyla birebir ayni.
        values = [data.get(k) for k in HARMONICS_COLUMNS]
        placeholders = ", ".join(["%s"] * len(HARMONICS_COLUMNS))
        cur.execute(
            f"INSERT INTO device_harmonics (device_id, signal_type, {', '.join(HARMONICS_COLUMNS)}) VALUES (%s, %s, {placeholders})",
            (device_id, signal_type, *values),
        )

    def handle_info(device_id: str, data: dict):
        # Cihaz bilgisi statik -- retained mesaj, tek satir/cihaz upsert.
        values = [data.get(k) for k in INFO_COLUMNS]
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in INFO_COLUMNS)
        cur.execute(
            f"""INSERT INTO device_info (device_id, {', '.join(INFO_COLUMNS)}, updated_at)
                VALUES (%s, {', '.join(['%s'] * len(INFO_COLUMNS))}, now())
                ON CONFLICT (device_id) DO UPDATE SET {set_clause}, updated_at = now()""",
            (device_id, *values),
        )

    def on_message(client, userdata, msg):
        try:
            # Peak/Demand/Harmonics topic'leri 4 parcali (.../peaks/tuketim vb.),
            # digerleri (live/energy/status/stats/info) 3 parcali.
            parts = msg.topic.split("/")
            if len(parts) == 4:
                device_id, category, subtype = parts[1], parts[2], parts[3]
                data = json.loads(msg.payload.decode())
                if category == "peaks":
                    handle_peaks(device_id, subtype, data)
                elif category == "demand":
                    handle_demand(device_id, subtype, data)
                elif category == "harmonics":
                    handle_harmonics(device_id, subtype, data)
                return

            device_id = device_id_from_topic(msg.topic)
            if not device_id:
                return
            if msg.topic.endswith("/status"):
                handle_status(device_id, msg.payload.decode())
                return
            data = json.loads(msg.payload.decode())
            if msg.topic.endswith("/live"):
                handle_live(device_id, data)
            elif msg.topic.endswith("/energy"):
                handle_energy(device_id, data)
            elif msg.topic.endswith("/stats"):
                handle_stats(device_id, data)
            elif msg.topic.endswith("/info"):
                handle_info(device_id, data)
        except Exception as e:
            print("Hata:", e)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(MQTT_BROKER, 1883, 60)
    # retry_first_connection=True: broker henüz ayakta değilse (ör. container sıralaması)
    # ilk bağlantıyı da otomatik olarak tekrar dener, thread çökmez
    client.loop_forever(retry_first_connection=True)

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_event_loop()
    threading.Thread(target=mqtt_thread, daemon=True).start()
    threading.Thread(target=alarm_offline_watchdog, daemon=True).start()