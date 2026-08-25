import asyncio
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
    "dbname": "postgres",
    "user": "postgres",
    "password": os.environ["POSTGRES_PASSWORD"]
}

MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto")
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASSWORD = os.environ["MQTT_PASSWORD"]
DEVICE_CLAIM_SECRET = os.environ["DEVICE_CLAIM_SECRET"]

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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # auth Bearer-token oldugu icin (cookie degil) CORS zaten CSRF vektoru degildi,
    # ama "*" gereksiz yere genisti -- gercek origin'lere daraltildi. localhost:5173
    # yerel Vite dev server icin (bu API'ye karsi test ederken kullaniliyor).
    allow_origins=[SITE_URL, "http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
    conn = psycopg2.connect(**DB_CONFIG)
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

# ---------- Cihaz sahipliği ----------
def get_owned_devices(username: str) -> list[dict]:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT device_id, name FROM devices WHERE owner_username = %s ORDER BY id", (username,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"device_id": r[0], "name": r[1]} for r in rows]

def is_device_owner(username: str, device_id: str) -> bool:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM devices WHERE owner_username = %s AND device_id = %s", (username, device_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None

@app.get("/devices")
def list_devices(user: str = Depends(require_auth)):
    return get_owned_devices(user)

class AddDeviceRequest(BaseModel):
    device_id: str
    name: str
    claim_code: str

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
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO devices (device_id, name, owner_username) VALUES (%s, %s, %s)",
            (device_id, name, user),
        )
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Bu cihaz ID'si zaten kayıtlı")
    finally:
        cur.close()
        conn.close()
    return {"message": "Cihaz eklendi"}

@app.delete("/devices/{device_id}")
def remove_device(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    # Ölçüm geçmişi bilerek silinmiyor — sadece sahiplik kaldırılıyor. Cihaz veri
    # göndermeye devam ederse sahipsiz kalır, tekrar kurulum koduyla eklenebilir.
    cur.execute("DELETE FROM devices WHERE device_id = %s AND owner_username = %s", (device_id, user))
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
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("UPDATE devices SET name = %s WHERE device_id = %s AND owner_username = %s", (name, device_id, user))
    cur.close()
    conn.close()
    return {"message": "Cihaz adı güncellendi"}

def avatar_url_for(username: str, avatar_updated_at) -> str | None:
    if not avatar_updated_at:
        return None
    return f"/avatars/{username}.jpg?v={int(avatar_updated_at.timestamp())}"

@app.get("/me")
def get_me(user: str = Depends(require_auth)):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT first_name, last_name, username, email, phone, created_at, avatar_updated_at, is_verified, role "
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
    conn = psycopg2.connect(**DB_CONFIG)
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

    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO firmware_builds (device_type, version, filename, sha256, notes) VALUES (%s, %s, %s, %s, %s)",
        (device_type, version, filename, sha256, notes),
    )
    cur.close()
    conn.close()
    return {"message": "Firmware yüklendi", "version": version, "sha256": sha256}

@app.get("/admin/fleet")
def admin_fleet(user: str = Depends(require_admin)):
    """Uretici gorunumu: satilan/kurulan tum cihazlar, canli durumlari ve firmware
    dagilimi. Sahalik ariza tespiti icin 'ne zamandir susuyor' bilgisi kritik."""
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    check_rate_limit(f"ota:{user}", max_attempts=10, window_seconds=60 * 60)
    device_type = device_type_from_id(device_id)
    if not device_type:
        raise HTTPException(status_code=400, detail="Cihaz tipi belirlenemedi")

    conn = psycopg2.connect(**DB_CONFIG)
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
        conn = psycopg2.connect(**DB_CONFIG)
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
    """Cihaz sahibine e-posta gonderir. MQTT dongusunu bloklamamak icin ayri thread'de."""
    def _send():
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                SELECT u.email, d.name FROM devices d
                JOIN users u ON u.username = d.owner_username
                WHERE d.device_id = %s
            """, (device_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row or not row[0]:
                logger.warning("Alarm bildirimi gonderilemedi, e-posta yok: %s", device_id)
                return
            email, device_name = row
            resend.Emails.send({
                "from": RESEND_FROM,
                "to": [email],
                "subject": f"{subject} — {device_name}",
                "html": (
                    f"<p><b>{device_name}</b> cihazında alarm durumu:</p>"
                    f"<p style='font-size:15px'>{body}</p>"
                    f"<p><a href='{SITE_URL}'>Panoyu aç</a></p>"
                ),
            })
        except Exception as e:
            logger.error("Alarm e-postasi gonderilemedi (%s): %s", device_id, e)

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


def alarm_offline_watchdog():
    """Cihazlarin veri gondermeyi kesip kesmedigini periyodik olarak kontrol eder."""
    while True:
        time.sleep(60)
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                SELECT r.id, r.device_id, r.offline_minutes, r.is_active,
                       (SELECT max(time) FROM measurements m WHERE m.device_id = r.device_id)
                FROM alarm_rules r
                WHERE r.enabled AND r.metric = 'offline'
            """)
            for rule_id, device_id, minutes, is_active, last_seen in cur.fetchall():
                stale = last_seen is None or (
                    datetime.now(last_seen.tzinfo) - last_seen
                ) > timedelta(minutes=minutes)

                if stale and not is_active:
                    gecen = "hiç veri alınmadı" if last_seen is None else f"son veri: {last_seen:%d.%m.%Y %H:%M}"
                    message = f"Cihaz {minutes} dakikadır veri göndermiyor ({gecen})"
                    cur.execute("""
                        INSERT INTO alarm_events (rule_id, device_id, message) VALUES (%s, %s, %s)
                    """, (rule_id, device_id, message))
                    cur.execute("UPDATE alarm_rules SET is_active = true, last_triggered_at = now() WHERE id = %s", (rule_id,))
                    logger.info("ALARM (cevrimdisi) tetiklendi %s", device_id)
                    alarm_notify(device_id, "🔴 Cihaz çevrimdışı", message)

                elif not stale and is_active:
                    cur.execute("UPDATE alarm_events SET resolved_at = now() WHERE rule_id = %s AND resolved_at IS NULL", (rule_id,))
                    cur.execute("UPDATE alarm_rules SET is_active = false WHERE id = %s", (rule_id,))
                    logger.info("ALARM (cevrimdisi) cozuldu %s", device_id)
                    alarm_notify(device_id, "✅ Cihaz tekrar çevrimiçi", "Cihaz yeniden veri göndermeye başladı.")

            invalidate_alarm_cache()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error("Cevrimdisi alarm kontrolu hatasi: %s", e)


@app.get("/devices/{device_id}/alarm-rules")
def list_alarm_rules(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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

    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT password_hash, is_verified FROM users WHERE username = %s", (credentials.username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not bcrypt.checkpw(credentials.password.encode(), row[0].encode()):
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
    conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_measurements(device_id: str, minutes: int = 60, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_energy(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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

@app.get("/energy/hourly")
def get_energy_hourly(device_id: str, format: str = "json", days: int = 7, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    days = max(1, min(days, 90))
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        WITH hourly AS (
            SELECT
                time_bucket('1 hour', time) AS bucket,
                last(time, time) AS reading_time,
                last(active_wh_tuketim, time) AS active_tuketim,
                last(inductive_varh_tuketim, time) AS inductive_tuketim,
                last(capacitive_varh_tuketim, time) AS capacitive_tuketim,
                last(active_wh_uretim, time) AS active_uretim,
                last(inductive_varh_uretim, time) AS inductive_uretim,
                last(capacitive_varh_uretim, time) AS capacitive_uretim
            FROM device_energy
            WHERE device_id = %s AND time > now() - (%s * interval '1 day')
            GROUP BY bucket
        )
        SELECT
            bucket, reading_time,
            active_tuketim, active_tuketim - LAG(active_tuketim) OVER (ORDER BY bucket) AS delta_active_tuketim,
            inductive_tuketim, inductive_tuketim - LAG(inductive_tuketim) OVER (ORDER BY bucket) AS delta_inductive_tuketim,
            capacitive_tuketim, capacitive_tuketim - LAG(capacitive_tuketim) OVER (ORDER BY bucket) AS delta_capacitive_tuketim,
            active_uretim, active_uretim - LAG(active_uretim) OVER (ORDER BY bucket) AS delta_active_uretim,
            inductive_uretim, inductive_uretim - LAG(inductive_uretim) OVER (ORDER BY bucket) AS delta_inductive_uretim,
            capacitive_uretim, capacitive_uretim - LAG(capacitive_uretim) OVER (ORDER BY bucket) AS delta_capacitive_uretim
        FROM hourly
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
def get_stats(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_peaks(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_demand(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_harmonics(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
def get_info(device_id: str, user: str = Depends(require_auth)):
    if not is_device_owner(user, device_id):
        raise HTTPException(status_code=403, detail="Bu cihaza erişiminiz yok")
    conn = psycopg2.connect(**DB_CONFIG)
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
        conn = psycopg2.connect(**DB_CONFIG)
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
    conn = psycopg2.connect(**DB_CONFIG)
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

# ---------- WebSocket: Canlı veri ----------
connected_clients: list[tuple[WebSocket, str]] = []
device_status: dict[str, dict] = {}  # device_id -> {"status": "online"|"offline", "changed_at": iso}

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None, device_id: str | None = None):
    username = token and verify_token(token)
    if not username or not device_id or not is_device_owner(username, device_id):
        await websocket.close(code=1008)
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