# Binary Enerji — Güç İzleme Sistemi | Proje Dokümanı

**Amaç:** Bu dosya, projeyi başka bir AI asistanıyla veya geliştiriciyle devam ettirebilmek için hazırlanmış teknik devir teslim dokümanıdır. Sistem tamamen çalışır durumda ve uçtan uca tamamlanmıştır.

**Canlı adres:** https://binaryenerji.com

**⚠️ DEVAM EDEN İŞ (20 Ağustos 2026):** Tam register okuma + çoklu-cihaz mimarisi + mobil uygulamalar (bölüm 5.3-5.5) **tamamlandı**, WiFi kurulumu Android'de uçtan uca doğrulandı (iOS Apple Developer Program üyeliğini bekliyor). **İKİ AÇIK KONU VAR, İKİSİ DE YARIM KALDI:**
1. **🔴 ANL13'te akım/güç/reaktif/PF/THD/enerji endeksi tamamen tutarsız/rastgele** (bkz. **bölüm 5.6**) — kök neden bulunamadı, teşhis Serial Monitor çıktısı beklerken yarıda kesildi (kullanıcı konuyu değiştirdi). **Önce bunu bitirin.**
2. **İkinci cihaz markası desteği yazıldı ama flaşlanıp test edilmedi** (bkz. **bölüm 5.7**) — `/Users/omergurgen/Desktop/ESP32-ANL21/`, Grup ARGE'nin farklı bir modeli ("Dijital Çıkışlı Şebeke Analizörü", cihaz ID öneki `anl21-`), tamamen farklı bir register haritasıyla (32-bit + 64-bit). THVD/THID ayrımı bu vesileyle **sistem geneline** (backend+web+iOS+Android) eklendi ve deploy edildi.

Devam etmek için önce kullanıcıdan bölüm 5.6'daki Serial Monitor çıktısını isteyin, sonra bölüm 5.7'nin "Sıradaki adımlar"ına geçin.

**Son güncelleme:** 18 Ağustos 2026 — "Cihaz Ekle" formu eklendi, kullanıcılar kendi hesaplarına self-servis cihaz ekleyebiliyor (bkz. bölüm 5.2). Öncesinde şeffaf arka planlı bir logo eklendi (favicon + sayfa başlıkları), marka etiketi "BINARY ENERJİ" olarak güncellendi, giriş/üye ol ve "Cihazlarım" sayfaları mobil uyumlu hale getirildi (bkz. bölüm 7). Öncesinde girişten sonra herkes bir "Cihazlarım" ekranına düşecek şekilde değiştirildi; sahip oldukları cihazı seçip izliyorlar, cihazı olmayanlar boş bir liste görüyor (bkz. bölüm 5.2). Ondan önce kullanıcı girişi, kişisel bilgilerle üyelik, e-posta doğrulama (Resend) ve Google Sheets'e üyelik kaydı eklenmişti (bkz. bölüm 5.1); en başta VPS'teki üç servis (Mosquitto, TimescaleDB, FastAPI) Docker Compose altında birleştirilmişti (bkz. bölüm 5).

---

## 1. Proje Özeti

Grup Arge marka **ANL13 güç analizöründen** RS485/Modbus RTU protokolüyle okunan elektriksel veriler (gerilim, akım, güç, frekans — 3 faz), bir ESP32 üzerinden internete taşınıp bir VPS'te işlenerek, kendi domain'inde canlı bir web dashboard'da gösteriliyor.

## 2. Mimari (Uçtan Uca Veri Akışı)

```
[Grup Arge ANL13]
   │ RS485 / Modbus RTU (9600 baud, 8N1, slave ID: 1, fonksiyon kodu 03 - Holding Registers)
   │ (register 1004'ten başlayarak 23 register tek seferde okunuyor)
   ▼
[RS485-TTL Dönüştürücü (MAX485 tipi)]
   │ TX2(GPIO17)→DI, RX2(GPIO16)←RO, GPIO4→DE/RE, 3.3V/5V→VCC, GND→GND
   ▼
[ESP32 Dev Kit]
   │ WiFi üzerinden MQTT publish (JSON payload, ~2 saniyede bir)
   │ Topic: powermeter/anl13/live
   ▼
[VPS: Docker Compose (/root/docker-compose.yml)]
   │
   ├─ [mosquitto container]  (eclipse-mosquitto:2, port 1883, esp32user + şifreli, allow_anonymous false)
   │      ▼
   ├─ [api container]  (FastAPI, kendi Dockerfile'ından build edilir)
   │      ├─ MQTT'den dinleyen thread (auto-reconnect'li) → TimescaleDB'ye INSERT
   │      ├─ POST /register  (ad/soyad/kullanıcı adı/e-posta/telefon/şifre → hesap oluşturur, doğrulanmamış)
   │      │        ├─ Resend API ile doğrulama e-postası gönderir
   │      │        └─ Google Sheets'e (servis hesabıyla) bir satır ekler
   │      ├─ GET /verify?token=...  (e-postadaki linke tıklanınca hesabı doğrular)
   │      ├─ POST /login  (kullanıcı adı/şifre → JWT token, sadece doğrulanmış hesaplar)
   │      ├─ GET /devices  (JWT gerekli — kullanıcıya ait cihazların listesi, "Cihazlarım" ekranını besler)
   │      ├─ REST endpoint: GET /measurements?device_id=...&minutes=N  (JWT + o cihazın sahibi olma şartı, geçmiş veri sorgusu)
   │      └─ WebSocket endpoint: /ws/live?device_id=...  (JWT + cihaz sahipliği gerekli — ?token=..., sadece o cihazın canlı verisi)
   │      ▼
   └─ [timescaledb container]  (timescale/timescaledb:latest-pg16, kalıcı external Docker volume: timescale_data)
   ▼
[Nginx]  (VPS'te, native — Docker'a alınmadı, reverse proxy + SSL + statik dosya sunucusu)
   ├─ / → React dashboard (statik build, /var/www/dashboard)
   ├─ /api/ → 127.0.0.1:8000'e proxy (artık api container'ının publish ettiği port)
   └─ /ws/ → WebSocket proxy (aynı porta)
   ▼
[React Dashboard]  (Vite ile build edilmiş, Entes Enerji Doktoru tarzı tasarım)
   ▼
[Kullanıcı Tarayıcısı]  →  https://binaryenerji.com
```

**Not:** Üç servis (Mosquitto, TimescaleDB, FastAPI) artık Docker Compose ile yönetiliyor. Nginx buna dokunmadı — çünkü container'lar host'ta aynı portları (1883, 5432, 8000) publish ediyor, Nginx'in bakış açısından hangi sürecin o portu dinlediği şeffaf.

## 3. Donanım Detayları

- **Analizör:** Grup Arge ANL13
  - Slave ID: `1`
  - Baud rate: `9600`, `8N1`
  - Modbus fonksiyon kodu: `03` (Read Holding Registers)
  - Register bloğu: `1004`'ten başlayarak `23` register tek seferde okunuyor (1004–1026)
  - Register haritası kılavuzdan çıkarıldı: gerilim (×0.1), akım (×0.001), güç (×1), frekans (×0.01) — her faz için 6'şar register + nötr/hat gerilimleri
  - Kılavuz kaynağı: `https://www.gruparge.com/wp-content/uploads/2025/08/GUC-ANALIZORU-KULLANMA-KILAVUZU.pdf`
- **ESP32:** Standart ESP32 Dev Kit (WROOM-32 tipi)
  - Kullanılan kütüphaneler: `ModbusMaster`, `PubSubClient`
  - RS485 modülü bağlantı pinleri: RX2=GPIO16, TX2=GPIO17, DE/RE=GPIO4
  - MQTT broker adresi kod içinde `mqtt_server` değişkeninde tanımlı — **VPS'in IP'sine** ayarlı: `138.68.83.111`
  - MQTT bağlantısı kullanıcı adı/şifre ile yapılıyor (`esp32user` + belirlenen şifre)
  - **Önemli ders:** ESP32'nin bağlı olduğu WiFi ağı değişirse ya da router'ın kendi IP'si değişirse, bu durum MQTT broker'ı (VPS'te sabit IP) etkilemez — bu sorun sadece geliştirme aşamasında Mac'in local IP'si kullanılırken yaşanmıştı, artık VPS'in sabit IP'sine bağlı olduğu için kalıcı çözüldü.

## 4. VPS (Sunucu) Bilgileri

- **Sağlayıcı:** DigitalOcean
- **Bölge:** Frankfurt (fra1)
- **IP adresi:** `138.68.83.111`
- **İşletim sistemi:** Ubuntu 24.04 LTS
- **Plan:** Basic, 1GB RAM, 1 vCPU (~$6/ay)
- **Erişim:** `ssh root@138.68.83.111` (şifre kullanıcıda kayıtlı). **18 Ağustos 2026'dan itibaren AI asistanının kendi ortamında SSH key ile passwordless erişimi de var** — VPS'in `~/.ssh/authorized_keys`'ine `claude-code-binaryenerji` yorumlu bir ed25519 public key eklendi. AI tarafındaki private key `~/.ssh/binaryenerji_vps` yolunda, `~/.ssh/config`'e `Host binaryenerji` alias'ı eklendi (`ssh binaryenerji "komut"` ile şifresiz bağlanılabiliyor). **Not:** bu anahtar AI asistanının çalıştığı ortama (sandbox) özel — yeni bir sohbet/oturumda ortam sıfırlanmışsa anahtar da kaybolmuş olabilir, `ssh binaryenerji` çalışmıyorsa yeniden kurulum gerekir (yukarıdaki adımlar tekrarlanır: `ssh-keygen` + public key'i VPS'in authorized_keys'ine ekleme).
- **Not:** Kernel güncellemesi bekliyor uyarısı var (`Pending kernel upgrade`) — sorun çıkarmıyor ama isteğe bağlı `reboot` ile giderilebilir.

## 5. Kurulu Servisler ve Konfigürasyon (Docker Compose)

Üç servis de artık `/root/docker-compose.yml` altında tek noktadan yönetiliyor. Yönetim: `docker compose ps` / `logs -f <servis>` / `restart <servis>` / `up -d --build <servis>` (kodda değişiklik olduğunda).

**VPS'teki dosyalar (`/root/` altında):**
- `docker-compose.yml` — üç servisin tanımı
- `Dockerfile` — FastAPI backend image'ı (`python:3.11-slim` tabanlı)
- `requirements.txt` — `fastapi`, `uvicorn[standard]`, `paho-mqtt`, `psycopg2-binary`, `pyjwt`, `bcrypt`, `gspread`, `google-auth`, `resend`
- `api.py` — backend kodu
- `create_user.py` — elle dashboard kullanıcısı eklemek için CLI script, ikincil yöntem (bkz. 5.1)
- `google-service-account.json` — Google Sheets servis hesabı anahtarı, `api` container'ına bind-mount edilir (bkz. 5.1)
- `.env` (`chmod 600`, git'e girmez) — `POSTGRES_PASSWORD`, `MQTT_USER`, `MQTT_PASSWORD`, `JWT_SECRET`, `RESEND_API_KEY`, `RESEND_FROM`, `GOOGLE_SHEET_ID` gerçek değerleri burada

Yerel geliştirme kopyaları Mac'te `~/Desktop/power-dashboard/` altında aynı isimlerle duruyor (deploy: `scp` ile `/root/`'a kopyalanıp `docker compose up -d --build <servis>` çalıştırılıyor).

### 5.1 Kullanıcı Girişi ve Üyelik (Authentication & Registration)

Dashboard artık herkese açık değil — `binaryenerji.com`'a girildiğinde önce bir giriş/üye ol formu geliyor. Ayrı kullanıcı hesapları modeli seçildi (tek paylaşılan şifre değil), kayıt herkese açık ama e-posta doğrulaması zorunlu.

- **Yöntem:** JWT (HS256), `.env`'deki `JWT_SECRET` ile imzalanıyor, 30 gün geçerli. Sunucu tarafında oturum durumu tutulmuyor.
- **Şifreler:** `bcrypt` ile hash'lenip Postgres'teki `users` tablosunda saklanıyor (düz metin hiçbir yerde yok).
- **Tablo şeması (güncel hali — 15 Ağustos 2026'da `email`, `phone` benzersizlik kısıtlarıyla genişletildi):**
  ```sql
  CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT now(),
      first_name TEXT,
      last_name TEXT,
      email TEXT UNIQUE,
      phone TEXT,
      is_verified BOOLEAN NOT NULL DEFAULT false,
      verification_token TEXT
  );
  ALTER TABLE users ADD CONSTRAINT users_phone_unique UNIQUE (phone);
  ```
  `username`, `email`, `phone` üçü de benzersiz — aynısıyla tekrar kayıt denenirse `409 Conflict` döner.

#### Üye olma akışı
1. Kullanıcı formu doldurur: **ad, soyad, kullanıcı adı, e-posta, telefon, şifre** + KVKK onay kutusu (işaretlenmeden gönderilemez)
2. `POST /register` — hesap `is_verified=false` ile oluşturulur, rastgele bir `verification_token` (`secrets.token_urlsafe(32)`) üretilir
3. **Resend** üzerinden doğrulama e-postası gönderilir (link: `https://binaryenerji.com/api/verify?token=...`)
4. Aynı istekte, kayıt bilgileri **Google Sheets**'e (servis hesabıyla) bir satır olarak eklenir — bu adım best-effort'tur (`try/except` ile sarmalı), Sheets'te bir sorun olsa bile kayıt işlemini bloklamaz
5. Kullanıcı e-postadaki linke tıklar → `GET /verify?token=...` hesabı `is_verified=true` yapar, basit bir onay HTML sayfası döner (ayrı bir frontend route'u yok, backend doğrudan HTML döndürüyor)
6. `POST /login` artık `is_verified` kontrolü yapıyor — doğrulanmamış hesap `403` alır ("e-postanızı kontrol edin" mesajıyla)

- **Eski yöntem hâlâ duruyor:** `create_user.py` CLI script'i (VPS'te `docker compose exec api python create_user.py <kullanici_adi>`, şifre `getpass` ile gizli sorulur) — artık asıl akış self-servis kayıt olduğu için ikincil, ama acil durumlarda (ör. e-posta servisi çalışmıyorsa) elle hesap açmak için hâlâ kullanılabilir. Bu yolla açılan hesaplar `is_verified` kontrolüne tabi değil çünkü `INSERT` sorgusunda bu alan hiç set edilmiyor (Postgres default'u `false` — **dikkat:** `create_user.py` ile açılan hesaplar da varsayılan olarak doğrulanmamış sayılır, elle `UPDATE users SET is_verified=true WHERE username=...` gerekir).

#### E-posta gönderimi: Resend (SMTP değil)
İlk denemede `smtplib` ile Gmail SMTP (465/587) kullanıldı ama **DigitalOcean VPS'lerde outbound SMTP portları varsayılan olarak tamamen kapalı** (spam önleme politikası) — bu yüzden istek süresiz askıda kaldı (bkz. bölüm 8). Çözüm: **Resend** (resend.com), e-postayı normal HTTPS (443) üzerinden bir API çağrısıyla gönderiyor, VPS'in port kısıtından hiç etkilenmiyor.
- `resend.api_key = os.environ["RESEND_API_KEY"]`, gönderim `resend.Emails.send({...})` ile
- **Domain doğrulaması yapıldı:** `binaryenerji.com`, Resend'e eklenip DKIM/SPF/DMARC DNS kayıtları hosting.com.tr DNS panelinize eklendi (bkz. bölüm 8 — panel bir MX kaydında değeri bozarak kaydediyordu, sonunda nokta (`.`) eklenerek çözüldü). Domain doğrulanmadan önce Resend "sandbox" modunda sadece hesabın kendi e-postasına (`binaryenerji@gmail.com`) gönderim yapabiliyordu; doğrulandıktan sonra `RESEND_FROM` `no-reply@binaryenerji.com` olarak güncellendi, artık herhangi bir adrese gönderim yapılabiliyor (Mailinator ile canlı test edildi, doğrulandı).

#### Google Sheets kaydı
- Servis hesabı: `binaryenerjimemberdata@project-742039f5-e6d6-4248-96b.iam.gserviceaccount.com` (Google Cloud projesi: "My First Project", org: `binaryenerji-org`)
- JSON anahtar dosyası VPS'te `/root/google-service-account.json`, container'a **bind-mount** ediliyor (image'a `COPY` edilmiyor — sır dosyası image layer'ına gömülmesin diye)
- Sheet ID: `10nuWUPWpoqJSO6HjtOExZJcv6Zm3SajCzomLH20_fgI` — Sheet, servis hesabı e-postasına **Düzenleyen (Editor)** olarak paylaşılmış olmalı
- **Dikkat:** Sheet'in 1. satırı Google'ın varsayılan placeholder başlıkları (`1. sütun, 2. sütun, ...`), gerçek başlıklar **2. satırda**: `AD SOYAD | KULLANICI ADI | E-POSTA | TELEFON | KAYIT TARİHİ`. Yeni satırlar `sheet.append_row(...)` ile ekleniyor.
- Google Cloud projesinde **"Google Sheets API" etkinleştirilmiş olmalı** (Enabled APIs & Services) — etkin değilse `403 Forbidden` döner, bu `gspread` içinde bir Python `PermissionError` olarak görünüyor (bkz. bölüm 8)

- **REST koruması:** `GET /measurements`, `require_auth` dependency'siyle korunuyor — `Authorization: Bearer <token>` header'ı yoksa/geçersizse `401`.
- **WebSocket koruması:** `/ws/live?token=<token>` — token `accept()`'ten önce doğrulanıyor, geçersizse bağlantı `close(code=1008)` ile reddediliyor. **Not:** Starlette, `accept()` çağrılmadan önce `close()` çağırdığında tarayıcı bunu `1008` değil `1006` (anormal kapanma) olarak görüyor — güvenlik davranışı doğru (bağlantı reddediliyor) ama frontend'de spesifik "1008 görürsen çıkış yaptır" mantığı bu yüzden fiilen tetiklenmiyor. Süresi dolan/geçersiz token, sayfa yeniden yüklendiğinde `/measurements`'ın `401` dönmesiyle zaten yakalanıp otomatik çıkış yaptırıyor.
- **Frontend:** Token `localStorage`'da tutuluyor, REST çağrılarına `Authorization` header'ı olarak, WS bağlantısına query param olarak ekleniyor. Detaylar için bkz. bölüm 7.

### 5.2 Cihaz Sahipliği ve "Cihazlarım" Ekranı (Device Ownership)

Fiziksel olarak tek bir ANL13 cihazı var, ama artık herkes üye olabildiği için canlı veriyi **sadece cihazın sahibi** görebiliyor. Giriş yaptıktan sonra herkes (cihazı olsun olmasın) önce bir **"Cihazlarım"** listesine düşüyor; kendi cihazına tıklayıp izliyor. Bu tasarım, ileride bir kullanıcının birden fazla cihaza sahip olabileceği senaryoyu da (altyapı olarak) destekliyor.

- **Tablo:** (bir kullanıcı birden fazla cihaza sahip olabilir, `owner_username` üzerinde benzersizlik kısıtı yok)
  ```sql
  CREATE TABLE devices (
      id SERIAL PRIMARY KEY,
      device_id TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      owner_username TEXT NOT NULL REFERENCES users(username),
      created_at TIMESTAMPTZ DEFAULT now()
  );
  INSERT INTO devices (device_id, name, owner_username) VALUES ('anl13_01', 'ANL13', 'omer');
  ```
  ANL13 cihazı `omer` hesabına bağlı (kullanıcının kendi ana hesabı). `device_id` (`anl13_01`), `mqtt_thread`'in `measurements` tablosuna INSERT ederken kullandığı sabit değerle aynı — artık `measurements` sorguları da bu `device_id`'ye göre filtreleniyor (bkz. aşağı).
- **Backend:**
  - `get_owned_devices(username)` — kullanıcıya ait tüm cihazları (`device_id`, `name`) listeler
  - `is_device_owner(username, device_id)` — belirli bir cihazın o kullanıcıya ait olup olmadığını kontrol eder
  - `GET /devices` — kullanıcının cihaz listesini döner (`[]` olabilir), "Cihazlarım" ekranını besler
  - `POST /devices` (15 Ağustos 2026, `AddDeviceRequest`: `device_id`, `name`) — giriş yapmış herhangi bir kullanıcı kendi hesabına yeni bir cihaz ekleyebilir, `owner_username` giriş yapan kullanıcı olarak set edilir. `devices.device_id` `UNIQUE` olduğu için başkasına ait bir ID girilirse (ör. `omer`'in `anl13_01`'i) `psycopg2.IntegrityError` yakalanıp `409 "Bu cihaz ID'si zaten kayıtlı"` döner — test edildi, başka bir hesabın cihazını "çalma" denemesi doğru şekilde reddediliyor.
  - `GET /measurements?device_id=...&minutes=N` — artık **zorunlu** `device_id` parametresi alıyor, `is_device_owner` ile doğrulanıyor, sorgu `WHERE device_id = %s` ile filtreleniyor. Sahiplik yoksa `403`.
  - `WS /ws/live?token=...&device_id=...` — aynı sahiplik kontrolü `accept()`'ten önce yapılıyor. `connected_clients` artık `(websocket, device_id)` çiftleri tutuyor; `broadcast(data, device_id)` sadece o cihazı izleyen bağlantılara veri gönderiyor (birden fazla cihaz olsa bile birbirlerinin verisini görmezler)
  - Bu kontroller sadece frontend'in ilgili endpoint'lere istek atmamasına değil, **doğrudan API çağrısıyla bypass edilemeyen bir savunma katmanına** dayanıyor (test edildi: sahiplik olmadan `403`/`close(1008)` dönüyor)
- **Frontend (`src/App.jsx`):**
  - `App` bileşeni girişten sonra `GET /devices` çağırır, sonucu `devices` state'inde tutar
  - `devices.length === 0` veya henüz bir cihaz seçilmemişse **`DeviceList`** bileşeni gösterilir ("Cihazlarım" başlığı, her cihaz için tıklanabilir bir kart; liste boşsa "Hesabınıza bağlı bir cihaz bulunmuyor..." mesajı)
  - Bir cihaza tıklanınca `selectedDevice` set edilir, **`DeviceDashboard`** bileşeni açılır — eski tek-cihazlı dashboard'un aynısı ama artık `device` prop'una göre `/measurements` ve `/ws/live` çağırıyor, header'da cihaz adı ve **"← Cihazlarım"** geri dönüş butonu var
  - `PhaseCard`, grafik, canlı/bağlantı göstergesi gibi görsel bileşenler değişmedi, sadece `DeviceDashboard` içine taşındı ve `device_id`'ye göre parametrik hale getirildi
  - **`AddDeviceForm` (15 Ağustos 2026):** "Cihaz adı" + "Cihaz ID'si" alanlarından oluşan basit bir form, `POST /devices`'ı çağırır. `DeviceList` içinde: hiç cihazı yoksa form otomatik açık geliyor; en az bir cihazı varsa "+ Cihaz Ekle" butonuyla açılıp kapanan (`Vazgeç` ile iptal edilebilen), ikinci/üçüncü cihaz eklemeye izin veren katlanır bir form olarak görünüyor. Başarılı eklemede `App`'teki `refreshDevices()` çağrılıp liste tazeleniyor.
- **Önemli sınırlama:** Form, girilen `device_id`'nin gerçek bir fiziksel cihaza (ESP32) karşılık geldiğini doğrulamıyor — sadece benzersizliğini kontrol ediyor. Şu an MQTT'ye veri gönderen tek fiziksel cihaz `anl13_01`; başka bir `device_id` ile eklenen "cihazlar" gerçek veri almaz, dashboard'da sürekli `—` gösterir (bkz. bölüm 9 — gerçek çoklu cihaz desteği için her ESP32'nin kendi benzersiz `device_id`'siyle yayın yapması gerekiyor, henüz o altyapı yok).

### 5.3 Tam Register Okuma + Yazma Komutları (17-18 Ağustos 2026 — okuma tarafı TAMAM, yazma komutlarından VAZGEÇİLDİ)

**Plan dosyası:** `/Users/omergurgen/.claude/plans/iridescent-napping-ocean.md` — tam tasarım kararları (kapsam sınırları, register haritası özeti) orada.

**Kaynak:** ANL13'ün resmi kullanım kılavuzu (`http://www.gruparge.com/wp-content/uploads/2025/08/GUC-ANALIZORU-KULLANMA-KILAVUZU.pdf`, 48 sayfa) — Modbus haritası (sayfa 34-48) ve panel menü açıklamaları (sayfa 1-33) tamamen okundu. PDF `/private/tmp/.../scratchpad/anl13_manual.pdf` altında, `pdftotext -layout` ile metne çevrilip aranabiliyor.

**✅ TAMAMLANAN VE DOĞRULANAN KISIM (okuma + deploy):**
- ESP32 firmware (`/Users/omergurgen/Desktop/ESP32-GA411321003940/ESP32-GA411321003940.ino`) yeni register'ları (Q/S/PF/THD, cos1027-1044 bloğu, enerji sayaçları 1404-1415) okuyup yayınlıyor, **cihaza yüklendi ve çalışıyor**.
- DB migration çalıştırıldı: `measurements` tablosuna yeni sütunlar eklendi (`v_neutral`/`i_neutral` — `vN`/`iN` Postgres'in `in` anahtar kelimesiyle çakıştığı için böyle adlandırıldı), `device_energy` hypertable'ı oluşturuldu (ilk denemede `id SERIAL PRIMARY KEY` partition sütununu içermediği için hata verdi, primary key kaldırılarak düzeltildi — `measurements` tablosunun deseniyle aynı).
- Backend (`api.py`) VPS'e deploy edildi: `GET /energy`, `POST /devices/{id}/command`, genişletilmiş `GET /measurements`.
- **İki gerçek prod-bug'ı bulunup düzeltildi:**
  1. `cos`/`pf` register'ları `×0.001` değil `×0.00001` ölçekliymiş (kılavuzda belirtilmemiş, gerçek veriyle ampirik olarak bulundu — `S=V×I` ve `P=S×PF` tutarlılığından).
  2. **PubSubClient'ın varsayılan 256 byte paket sınırı** genişletilmiş JSON payload'ı (~330+ byte) sessizce düşürüyordu — `mqttClient.setBufferSize(768)` ile çözüldü. Bu, saatlerce "veri neden DB'ye düşmüyor" arayışına yol açtı; kesin teşhis yöntemi: `docker compose exec mosquitto mosquitto_sub -t 'powermeter/anl13/live' -v` ile **broker seviyesinde** doğrudan dinlemek (API'yi bypass ederek).
  3. RS-485 hattında ardışık 2-3 Modbus isteği arasında toparlanma payı yoktu → ara sıra "Modbus okuma hatasi!" veriyordu → `.ino`'da art arda okumalar arasına `delay(30)` eklendi.
  4. `PYTHONUNBUFFERED=1` env değişkeni VPS'teki `docker-compose.yml`'e eklendi — Python `print()` çıktısı stdout'ta buffer'da bekleyip `docker compose logs`'a hiç düşmüyordu, bu da debug'ı çok zorlaştırıyordu. **Bu ayar kalıcı, gelecekte de faydalı.**
- **Frontend (`src/App.jsx`) tamamlandı ve deploy edildi:** `PhaseCard`'a Q/S/PF/THD eklendi, Nötr satırı eklendi, yeni "Toplam Enerji" bölümü (`GET /energy`, 30sn'de bir polling), yeni katlanır "Cihaz Ayarları" bölümü (5 komut butonu, `window.confirm` ile onay). Production'da (`https://binaryenerji.com`) görsel olarak doğrulandı — canlı değerler + enerji kartları + ayarlar paneli hepsi doğru render ediliyor.

**❌ TERK EDİLDİ — yazma komutları (18 Ağustos 2026, kesin karar):**
Enerji/Tepe/Demand Sıfırlama, Fabrika Ayarları, Cihazı Yeniden Başlatma komutları **cihazı fiilen etkilemiyor**, kök neden bulunamadı, kullanıcıyla birlikte özellikten vazgeçildi.

- Register numaraları (9001=Enerjileri Sıfırla, 9002=Tepe, 9003=Demand, 9024=Fabrika Ayarları, 9025=Restart) kılavuzla teyit edildi, doğru.
- Modbus yazma/okuma koruması (Y.ENg./O.ENg., register 208-211) kontrol edildi, **kapalı** (hepsi 0) — şifre/yetkilendirme sorunu değil.
- `api.py`'deki `publish_command()`'da gerçek bir bug bulunup düzeltildi: `client.connect()` sonrası `loop_start()` çağrılmıyordu, `publish()` soket'e yazılmadan `disconnect()` bağlantıyı kesiyordu. `loop_start()` + `wait_for_publish()` ile düzeltildi, debug print'lerle **API'nin mosquitto'ya güvenilir şekilde publish ettiği doğrulandı** — yani sorun API/MQTT tarafında değil.
- ESP32 tarafında da `onMqttMessage`'a 3 denemeli retry eklendi (RS-485 çakışması ihtimaline karşı, `.ino` satır ~150).
- Buna rağmen: `reset_energy` defalarca denendi, bazen `sonuc=OK` (Modbus yazma başarılı) bazen `sonuc=HATA` (bus çakışması) döndü, ama **`device_energy`'deki `active_wh_tuketim` sayacı hiçbir denemede sıfırlanmadı**. Kullanıcı ayrıca web arayüzünden `factory_reset` (9024) ve `restart` (9025) denemiş — bunlar da hep `sonuc=HATA` ile başarısız oldu, **cihaz hiç resetlenmedi/yeniden başlamadı, veri akışı kesintisiz devam etti** (güvenli, hasar yok).
- **Kök neden bulunamadı** — en olası açıklama: register'a yazılması gereken tetik değeri `1` değil, kılavuzda belgelenmeyen farklı bir değer/mekanizma (rising-edge, özel kod vb.) — üretici desteği olmadan çözülmesi zor görüldü.
- **Alınan aksiyon:** `src/App.jsx`'teki 5 komut butonu **kaldırıldı** (`DEVICE_COMMANDS`, `sendCommand`, ilgili state hepsi silindi), yerine kullanıcıyı cihazın fiziksel paneline yönlendiren bir bilgi notu kondu (panel menü karşılıkları: Enerji Sıfırlama → Ayarlar/Enerji Değerleri Silme, Tepe → Ayarlar/Tepe Değerleri Resetleme, Fabrika Ayarları → Ayarlar/Fabrika Ayarları, Reset → Ayarlar/Reset).
- Backend'deki `POST /devices/{id}/command` endpoint'i ve `DEVICE_COMMANDS` dict'i hâlâ kodda duruyor (CT oranı endpoint'iyle aynı mantık) — ileride üretici desteğiyle doğru tetik değeri bulunursa tekrar bağlanabilir.

**⚠️ ÖNEMLİ BULGU — Akım Trafo Oranı (register 214) doğrudan değer DEĞİL, bir tablo indeksi (18 Ağustos 2026):**
Kullanıcı web arayüzünden "100" yazıp kaydettiğinde, cihazın ön panelinde gerçek oran **2000/5** olarak değişti — yani register'a yazılan sayı ham CT oranı değil, cihazın dahili bir tabloya **index** olarak yorumlanıyor (kılavuzdaki "Table Index" etiketi bunu doğruluyor, daha önce göz ardı edilmişti). Index↔oran eşlemesi belgelenmemiş ve bilinmiyor.
- **Alınan aksiyon:** `src/App.jsx`'teki CT oranı "Değiştir" formu **kaldırıldı**, artık sadece salt-okunur `Index: X` gösteriyor + kullanıcıyı cihazın fiziksel panelinden değiştirmeye yönlendiren bir uyarı metni var (Ayarlar → Trafo → Akım Trafo Oranı, "C.t." ekranı — panel muhtemelen doğru/gerçek oranı gösterip ayarlıyor, index değil).
- Backend'deki `POST /devices/{id}/ct-ratio` endpoint'i hâlâ kodda duruyor (silinmedi) ama frontend'den artık çağrılmıyor — index tablosu bir şekilde bulunursa (üretici desteği, deneme/panel karşılaştırması vb.) tekrar kullanılabilir.
- **Kullanıcıya panelden gerçek/güncel CT oranını kontrol edip (harici trafo yoksa 5/5 olmalı) gerekirse panelden düzeltmesi söylendi** — web üzerinden yapılan yanlış yazımın etkisini geri almanın yolu budur.

**✅ DÜZELTİLDİ — kök neden aslında yanlış register'dı, index tablosu belgeliymiş (20 Ağustos 2026):**
Yukarıdaki "index↔oran eşlemesi bilinmiyor" tespiti yanlış çıktı. `sebeke-analizoru-modbus-haritasi.xlsx`'in "Parametreler" sayfası incelendi: **register 214 CT oranıyla ilgisiz** — "Okuma Koruma Biti" (0/1, salt-okunur). Gerçek CT oranı register'ı **221** ("Akım Trafo Oranı, Table Index", W/R, 0-69) ve aynı sayfada index↔gerçek-oran (X/5 A) eşleme tablosunun **tamamı** (70 satır, 0→5'ten 69→10000'e) belgeli.
- **Backend (`api.py`):** `CT_RATIO_REGISTER` 214→221, `CT_RATIO_TABLE` (70 değer) eklendi. `GET /devices/{id}/ct-ratio` artık DB'deki ham indeksi gerçek orana çevirip döndürüyor; `POST` gerçek oran değeri alıp (dropdown'dan, serbest sayı değil) indekse çevirip yazıyor — kullanıcı artık asla geçersiz/rastgele bir index yazamıyor.
- **Firmware:** ANL13 (`ESP32-GA411321003940.ino`) `readCtRatio()` 214→221 düzeltildi. ANL21'de CT oranı okuma hiç yoktu, register 221 ile eklendi (`ctRatio` global, `readCtRatio()`, `energy` topic payload'ına `ct_ratio` alanı, 30sn'lik enerji döngüsünde okunuyor). İkisi de derlendi (temiz), **henüz flaşlanmadı** — acil değil, kullanıcı uygun zamanda flaşlayabilir.
- **Frontend:** "Cihaz Ayarları"ndaki salt-okunur `Index: X` kutusu, 70 geçerli orandan (`X/5 A` etiketli) seçilen bir `<select>` + "Kaydet" butonuna dönüştürüldü (`CtRatioBox` bileşeni) — artık serbest metin girişi yok, sadece cihazın kabul ettiği geçerli değerler seçilebiliyor.
- **Not:** `device_settings.ct_ratio` DB sütunundaki mevcut değer (anl13 için 34) hâlâ **eski, yanlış register'dan (214) okunmuş** veri — firmware reflash edilip yeni `energy` payload'ı gelene kadar UI'da yanlış-ama-makul görünen bir oran gösterebilir (34→600/5 A gibi). Reflash sonrası otomatik güncellenir.

**✅ Tamamlanan ek özellikler (18 Ağustos 2026):**
- **ESP32'ye MQTT Last Will (LWT) eklendi:** cihaz bağlanırken broker'a "bağlantı anormal koparsa `powermeter/anl13/status` konusuna `offline` yayınla" talimatı veriyor (retained), başarılı bağlantıda kendisi `online` yayınlıyor. Backend bu konuyu dinleyip WS üzerinden anlık broadcast ediyor. Frontend'deki durum göstergesi artık **gerçek ESP32 bağlantı durumuna** göre 3 hâl alıyor: yeşil (bağlı + veri akıyor, çalışma süresi gösterir), sarı (bağlı ama veri akmıyor, son veri zamanı gösterir), kırmızı (bağlı değil, kopma zamanı gösterir) — daha önce bu sadece tarayıcının kendi WebSocket bağlantısını yansıtıyordu, ESP32'den bağımsızdı, bu yanlıştı ve düzeltildi.
- **Saatlik enerji dökümü:** yeni `GET /energy/hourly` endpoint'i (`time_bucket('1 hour', ...)` + TimescaleDB `last()` + `LAG()` ile saatlik artış hesaplıyor), Tüketim/Üretim enerji kartlarına tıklanınca açılan bir modal'da Aktif/Endüktif/Kapasitif için hem **Artış** hem **Endeks** (kümülatif okuma) sütunlarıyla, tarih/saat/dakika bazında listeleniyor (son 7 gün).
- **Footer + Gizlilik Politikası sayfası** eklendi (`/gizlilik-politikasi`, basit pathname kontrolüyle, router kütüphanesi yok — nginx zaten `try_files ... /index.html` ile SPA fallback yapıyor).
- **Gerilim & Akım Dalga Formu:** eski "Son 10 dk" trend grafiği kaldırılıp, her faz için `cosφ`'den hesaplanan faz farkıyla senkronize V/I sinüs eğrileri gösteren bir görselleştirmeyle değiştirildi (gerçek örneklenmiş dalga değil, RMS + faz açısından sentezlenmiş — bilgilendirici/pedagojik amaçlı, oscilloscope'un aksine).
- **Giriş ekranı yeniden tasarlandı:** iki panelli (koyu degrade "hero" + form kartı), animasyonlu sinüs dalgası dekorasyonu, mobilde tek sütuna düşüyor (`src/App.jsx` `AuthForm`, CSS `index.css`'te `.auth-*` sınıfları).

### 5.4 Çoklu Cihaz Mimarisi (18 Ağustos 2026 — seri üretime geçiş hazırlığı)

**Bağlam:** Kullanıcı farklı markalardan cihaz alıp kendi markasıyla (Binary Enerji) satmayı planlıyor ("seri üretim"). Eskiden tüm sistem TEK bir fiziksel cihaz (`device_id` her yerde hardcode) varsayımıyla kuruluydu. Bu bölüm, sisteme "her cihaz kendi kimliğiyle bağımsız çalışabilir" desteği eklendiğini belgeliyor.

**✅ Yapılanlar:**
- **ESP32 firmware artık her cihaz için AYNI** — cihaza özel hiçbir ayar/derleme gerekmiyor. `setup()` içinde `WiFi.macAddress()` ile cihazın kendi MAC'inden (WiFi bağlantısı kurulduktan SONRA okunuyor — bkz. aşağıdaki bug) benzersiz bir `device_id` türetiliyor (`anl13-xxxxxx` formatında, MAC'in son 3 baytı). Bu ID açılışta Serial'a basılıyor (`CIHAZ ID (etikete/kutuya yazin): ...`) — fabrikada/kurulumda etikete yazılması için.
- **MQTT topic'leri artık `powermeter/{device_id}/live|energy|status|cmd` şeklinde parametrik.** Backend wildcard abone oluyor (`powermeter/+/live` vb.) ve gelen mesajın gerçek `device_id`'sini topic'ten okuyor (`device_id_from_topic()`), artık hiçbir yerde hardcode device_id yok.
- **Gerçek bug bulunup düzeltildi — MQTT client ID çakışması:** Eski firmware'de MQTT client ID sabitti (`"esp32_powermeter"`). İki cihaz aynı client ID ile bağlanırsa broker birini sürekli düşürüp digerini bağlar (klasik MQTT hatası, seri üretimde HERKESİ etkilerdi). Artık her cihaz `deviceId.c_str()`'ı kendi client ID'si olarak kullanıyor — iki cihazın aynı anda, birbirini düşürmeden bağlı kalabildiği gerçek donanımla doğrulandı (`anl13-05bb00` adlı ikinci bir ESP32 ana cihazla aynı anda test edildi, mosquitto logunda çakışma yok).
- **Gerçek bug bulunup düzeltildi — MAC adresi bazen `00:00:00`:** `WiFi.mode(WIFI_STA)` sonrası hemen `WiFi.macAddress()` okumak bazen sıfır dönüyordu (donanım tam hazır olmadan okunuyor, ilk denemede `anl13-000000` çıktı). Çözüm: MAC'i `WiFi.begin()` + bağlantı kurulduktan SONRA okumak (o noktada kesinlikle geçerli).
- **Geriye dönük uyumluluk / geçiş:** Backend deploy edildiğinde eski (henüz reflash edilmemiş) firmware çalışan ana cihaz, sabit `powermeter/anl13/...` topic'lerine yayın yapmaya devam etti ve wildcard abonelik bunu sorunsuz yakaladı — **ama** meğer o topic ismi hep `"anl13"` imiş (`"anl13_01"` değil, backend'in eskiden INSERT'lerde hardcode ettiği isimle DB'deki gerçek MQTT topic ismi hiç eşleşmiyormuş, backend hep hardcode değeri yazdığı için bu tutarsızlık fark edilmemişti). Deploy sonrası veriler `"anl13"` adı altında düşmeye başlayınca, `devices`/`measurements`/`device_energy`/`device_settings` tablolarındaki tüm `"anl13_01"` kayıtları tek seferlik bir SQL migration ile `"anl13"`e yeniden adlandırıldı (`UPDATE ... SET device_id='anl13' WHERE device_id='anl13_01'` — 4 tablo, ~38 bin satır, veri kaybı olmadı). **Ders:** Bu tür bir device_id değişikliği/reflash yapılırken HER SEFERİNDE aynı migration deseni izlenmeli (eski ID → yeni ID, tüm ilgili tablolarda).
- **Cihaz Ekle güvenlik açığı kapatıldı (kurulum kodu):** Eskiden sadece `device_id` bilmek bir cihazı sahiplenmeye yetiyordu (tahmin edilebilir/paylaşılabilir bir string). Artık `POST /devices` bir `claim_code` alanı da istiyor; backend `hmac.new(DEVICE_CLAIM_SECRET, device_id, sha256)[:6]` ile kodu doğruluyor (`hmac.compare_digest` ile zamanlama saldırısına karşı korumalı). Kod, `device_id`'den DETERMİNİSTİK türetiliyor — ayrı bir DB kaydı gerekmiyor, `generate_claim_code.py <device_id>` scripti (api container içinde, `docker compose exec api python generate_claim_code.py <device_id>`) fabrikada/etiketleme sırasında kodu üretmek için kullanılıyor. `DEVICE_CLAIM_SECRET` VPS'teki `/root/.env`'de duruyor (rastgele 64 karakter hex, `docker-compose.yml`'in `api` servisine env olarak geçiliyor). Frontend'deki "Cihaz Ekle" formuna "Kurulum kodu" input'u eklendi. **Uçtan uca test edildi:** yanlış kod → 403 reddediliyor, doğru kod → kabul ediliyor (gerçek cihazla doğrulandı).
- **Devam eden test cihazı:** İkinci bir ESP32 (`anl13-05bb00`, gerçek ANL13'e RS-485 ile bağlı değil, sadece MQTT/mimari testi için) `devices` tablosuna "Yeni Anl13" adıyla eklendi — Modbus okuyamadığı için dashboard'da sürekli "Veri bekleniyor..." gösterecek, bağlantı durumu muhtemelen sarı ("Veri akışı yok") kalacak; bu üç-renkli durum sisteminin ilk gerçek-donanım testidir.

**⏸️ Henüz yapılmadı (sıradaki adımlar):**
1. **WiFi kurulum akışı — KOD YAZILDI (iki tarafta da), HENÜZ FLAŞLANIP TEST EDİLMEDİ (18 Ağustos 2026):** İlk denemede WiFiManager (tzapu) kütüphanesi kullanılmıştı (tarayıcı tabanlı captive-portal); kullanıcı mobil uygulama fikrine yönelince (**tıpkı Tuya gibi, tarayıcı yok**) bu **tamamen kaldırılıp yerine özel bir SoftAP + JSON API yazıldı** (bkz. bölüm 5.5, ayrıntılar orada). MAC okuma sağlam: `esp_read_mac(mac, ESP_MAC_WIFI_STA)` (donanımdan doğrudan okur, WiFi bağlı olmasını gerektirmez).
2. **Farklı marka/register haritası desteği** henüz yok — ESP32 firmware'i hâlâ sadece ANL13'ün Modbus register adreslerini biliyor. Farklı bir marka eklenecekse ya marka başına ayrı firmware (register adresleri `#define`), ya da backend'de "cihaz profili" kavramı gerekir.
3. **Per-device MQTT kimlik bilgileri yok** — tüm cihazlar hâlâ aynı paylaşılan `esp32user` MQTT kullanıcısını kullanıyor (client ID farklı olduğu için çakışma yok ama teorik olarak bir cihaz başka bir cihazın topic'ine yayın yapabilir/dinleyebilir, ACL ile kısıtlanmamış). Düşük öncelik — küçük ölçekte risk kabul edilebilir, hacim artarsa per-device credential + mosquitto ACL düşünülmeli.

### 5.5 Mobil Uygulama (19 Ağustos 2026 — iOS VE Android temel akışları ÇALIŞIYOR, WiFi kurulumu kod olarak hazır/gerçek cihaz testi bekliyor)

**Bağlam:** Kullanıcı, cihaz kurulumunu Tuya uygulaması gibi telefon üzerinden yapmak istiyor (WiFiManager'ın tarayıcı tabanlı captive portal'ı yerine). Kapsam netleştirildi: **tam kapsamlı uygulama** (kurulum + canlı izleme + tüm dashboard özellikleri, web sitesine ihtiyaç kalmayacak şekilde), **ayrı native kod tabanları** (iOS: Swift, Android: Kotlin — React Native değil).

**Önemli kısıtlama:** Bu AI asistanının ortamında gerçek bir iOS Simulator var (yazılan kod fiilen çalıştırılıp doğrulanabiliyor) ama **Android emülatörü/araç zinciri yok** — Android tarafı yazılabilir ama bu ortamda çalıştırılıp doğrulanamaz. Ayrıca Simulator'de **gerçek WiFi donanımı yok**, bu yüzden WiFi kurulum akışı (aşağıda) Simulator'de test edilemez, gerçek iPhone gerekir. Sıralama: **önce iOS** (mümkün olduğunca uçtan uca test edilebilir), **Android sonra** (iOS'ta kanıtlanmış tasarım/akış temel alınarak, ayrı bir aşamada, test için gerçek bir Android cihaz/emülatöre ihtiyaç olacak).

**Proje konumu:** `/Users/omergurgen/Desktop/BinaryEnerjiApp/` — XcodeGen ile üretilen (`project.yml` → `xcodegen generate` → `.xcodeproj`) bir SwiftUI projesi. `BinaryEnerji/Views/` altında `LoginView`, `DeviceListView` (+ içinde `AddDeviceView`), `DeviceDashboardView`, `WiFiProvisioningView`; `BinaryEnerji/Networking/` altında `APIClient` (REST) ve `LiveSocket` (WebSocket); `BinaryEnerji/Models/Models.swift`. Backend'in aynısını (`binaryenerji.com/api`, `wss://binaryenerji.com/ws/live`) kullanıyor, ayrı bir backend yok.

**Backend hazırlığı (tamamlandı, deploy edildi):**
- **`DELETE /devices/{device_id}`** — sadece sahiplik siliniyor, ölçüm geçmişi bilerek korunuyor.
- **`PATCH /devices/{device_id}`** — cihaz yeniden adlandırma.
- **`GET /me`** — kullanıcı profil bilgisi (mobil profil ekranı için hazır, henüz app'te kullanılmıyor).
- JWT süresi (`JWT_EXPIRY_DAYS = 30`) mobil için zaten uygun.

**✅ Doğrulanan (Simulator'de, gerçek hesap/cihaz verisiyle — 18 Ağustos 2026):** Giriş ekranı → Cihazlarım listesi (`GET /devices`, gerçek 2 cihaz göründü) → cihaz dashboard'u (WebSocket canlı veri: V/A/W/PF her faz için, frekans, 3 renkli durum rozeti "Canlı" yeşil doğru çalıştı, `GET /energy` ile Tüketim/Üretim kartları). Otomatik simulator dokunma/tıklama bu ortamda güvenilir çalışmadı (araç kısıtı, kod hatası değil) — doğrulama kullanıcının Simulator'de elle etkileşip ekran görüntüsü paylaşmasıyla yapıldı.

**WiFi kurulumu — mimari kararı ve kod (18 Ağustos 2026, henüz gerçek donanımla test edilmedi):**
- **Neden WiFiManager'dan vazgeçildi:** WiFiManager kendi HTML sayfasını sunuyor (tarayıcı açılması gerekiyor) — "tıpkı Tuya" isteğiyle uyuşmuyor, uygulamanın kendisi kurulumu sürmeli.
- **ESP32 tarafı (bölüm 5.4'teki `.ino`):** `WiFiManager` kütüphanesi tamamen kaldırıldı, yerine yerleşik `WebServer.h` + `Preferences.h` (ikisi de ESP32 core'da hazır, ekstra kütüphane kurulumu gerekmiyor) ile özel bir akış yazıldı. Açılışta kayıtlı WiFi varsa (`Preferences`, namespace `"wifi"`) ona bağlanmayı dener (15 sn); yoksa/başarısızsa kendi `BinaryEnerji-<device_id>` adında **şifresiz** bir AP açıp `GET /status` (`{"device_id":"..."}`) ve `POST /configure` (`{"ssid":"...","password":"..."}` alıp `Preferences`'a kaydeder, sonra yeni ağa bağlanmayı dener) endpoint'lerini sunuyor. Bağlanamazsa otomatik tekrar kurulum moduna dönüyor. BOOT tuşu basılıyken açılış, kayıtlı WiFi bilgisini siler (`prefs.clear()`).
  - **Bilinen v1 kısıtlaması:** Kurulum AP'si şifresiz — WiFi şifresi düz JSON olarak HTTP üzerinden (HTTPS değil) gönderiliyor. Fiziksel yakınlık gerektirdiği için (aynı Tuya/çoğu IoT cihazı gibi) kabul edilebilir bir v1 riski, ama not düşülüyor.
- **iOS tarafı:** Yeni `WiFiProvisioningView.swift` — `NEHotspotConfiguration(ssid:)` ile cihazın AP'sine programatik katılıyor (`NetworkExtension` framework), küçük bir SSID/şifre formu gösteriyor, `http://192.168.4.1/configure`'a JSON POST atıyor, başarılı olunca `NEHotspotConfigurationManager.shared.removeConfiguration(forSSID:)` ile AP bağlantısını bırakıyor. `DeviceListView.swift` içindeki `AddDeviceView`'a "Cihazı WiFi Ağına Bağla" butonu olarak bağlandı (cihaz ID'si girildikten sonra aktif oluyor, kurulum kodu adımından önce/bağımsız çalışabilir).
  - **Gereken proje ayarları (`project.yml`, uygulandı):** `NSLocalNetworkUsageDescription` (yerel ağ izni açıklaması), `NSAppTransportSecurity.NSAllowsLocalNetworking: true` (192.168.4.1'e düz HTTP izni — sadece yerel ağ istisnası, internet trafiğini zayıflatmıyor), `com.apple.developer.networking.HotspotConfiguration` entitlement'ı (yeni `.entitlements` dosyası, XcodeGen otomatik üretiyor).
  - **Simulator'de derleme doğrulandı** (`xcodebuild ... build` → **BUILD SUCCEEDED**) ama **gerçek işlevsellik test edilemedi** — Simulator'de gerçek WiFi radyosu yok, `NEHotspotConfiguration` gerçek bir cihaz gerektiriyor.

**✅ Profil ekranı + cihaz yeniden adlandırma (18 Ağustos 2026, tamamlandı, Simulator'de doğrulandı):** Yeni `ProfileView.swift` (`GET /me` verisini gösteriyor, "Çıkış Yap" artık burada) — `DeviceListView`'in sol üst köşesindeki yeni profil ikonundan açılıyor. Cihaz listesinde satırı sola kaydırınca "Ad Değiştir" aksiyonu çıkıyor (`PATCH /devices/{id}`, alert+TextField ile). Kullanıcı gerçek hesapla Simulator'de test edip onayladı.

**WiFi testi neden şu an duruyor:** Kullanıcı ESP32'yi flaşlayıp firmware'i tek başına doğruladı (bkz. aşağıdaki "Firmware doğrulaması" maddesi) ama uygulamayı fiziksel iPhone'a kurmaya çalışırken **`HotspotConfiguration` yetkisinin ücretsiz/personal Apple ID ile desteklenmediği** ortaya çıktı (Xcode hatası: *"Personal development teams... do not support the Hotspot capability"*). Kullanıcı Apple Developer Program'a ($99/yıl) üye olmaya karar verdi ama henüz üye olmadı — üye olunca WiFi testine kaldığımız yerden devam edilecek. Bu arada Android portuna geçildi.

**✅ Firmware doğrulaması (19 Ağustos 2026, gerçek ESP32'de):** Kullanıcı yeni `.ino`'yu `anl13-05bb00` kartına flaşladı. Serial Monitor çıktısı beklendiği gibi: `CIHAZ ID (etikete/kutuya yazin): anl13-05bb00` → `Kurulum AP'si acildi: BinaryEnerji-anl13-05bb00`. Telefonun sistem WiFi ayarlarından bu şifresiz ağa bağlanıp Safari'de `http://192.168.4.1/status` açıldığında `{"device_id":"anl13-05bb00"}` doğru döndü — yani **SoftAP + JSON API firmware tarafında tam çalışıyor**, sorun sadece Apple imzalama tarafında.

**✅ Android portu (19 Ağustos 2026, TAMAMLANDI ve doğrulandı):** Proje konumu `/Users/omergurgen/Desktop/BinaryEnerjiAndroid/` — Android Studio'nun "Empty Activity (Compose)" sihirbazıyla oluşturulan iskelet (`com.binaryenerji.app` paketi, Kotlin, minSdk 24, Compose BOM) üzerine iOS mimarisinin birebir karşılığı yazıldı: `model/Models.kt`, `network/ApiClient.kt` (OkHttp + kotlinx.serialization), `network/LiveSocket.kt` (OkHttp WebSocket), `network/TokenStore.kt` (`EncryptedSharedPreferences`, Keychain karşılığı), `ui/LoginScreen.kt`, `ui/DeviceListScreen.kt` (+ cihaz ekleme/yeniden adlandırma dialogları), `ui/DeviceDashboardScreen.kt`, `ui/ProfileScreen.kt`, `ui/WifiProvisioningScreen.kt`. Bu ortamda Gradle/Android SDK kurulu olmadığı için (iOS'taki `xcodebuild` gibi) kod derlenip test edilemedi — kullanıcı Android Studio'da derleyip üç hatayı sırayla bildirdi, hepsi düzeltildi:
  - XML yorumunda `--` kullanımı (`network_security_config.xml`) — XML spesifikasyonunda yorumlar içinde çift tire yasak, kaldırıldı.
  - `TopAppBar`/`SegmentedButton` gibi bazı Material3 bileşenleri deneysel (`@ExperimentalMaterial3Api`) — `LoginScreen`, `DeviceListScreen`, `DeviceDashboardScreen`'e `@OptIn` eklendi.
  - `ApiClient`'ta `token` property'sinin (`by mutableStateOf`, `private set`) otomatik ürettiği gizli `setToken` JVM metoduyla, elle yazılan `private fun setToken(...)` isim çakıştı ("Platform declaration clash") — fonksiyon `storeToken` olarak yeniden adlandırıldı.
  - Düzeltmelerden sonra emülatörde (Pixel 8) **giriş → cihaz listesi → canlı dashboard uçtan uca doğrulandı**, gerçek hesap/cihaz verisiyle (WebSocket canlı veri akıyor).
  - **iOS'tan mimari fark (bilinçli):** iOS'taki `NEHotspotConfiguration` (uygulama içinden AP'ye programatik katılma) Android'de API seviyesi/izin karmaşıklığı getiriyor (`WifiNetworkSpecifier`, min API 29, network binding). Onun yerine Android'deki `WifiProvisioningScreen` sistemin WiFi ayarlarını (`Settings.ACTION_WIFI_SETTINGS`) açıyor, kullanıcı elle bağlanıp uygulamaya dönüyor — tüm Android sürümlerinde çalışan, daha basit ve test edilmemiş exotic API riski taşımayan bir çözüm. Firmware tarafı (SoftAP + `/configure` JSON endpoint) iOS ile birebir aynı, bu yüzden Android'in WiFi kurulum testi de Apple Developer Program bağımlılığı olmadan, sadece ESP32 + Android telefonla yapılabilir.

**✅✅ WiFi kurulumu gerçek cihazda UÇTAN UCA DOĞRULANDI (19 Ağustos 2026, Android + gerçek ESP32):** Kullanıcı gerçek bir Xiaomi telefonda (MIUI — USB ile Yükleme izni ayrıca açılması gerekti, Geliştirici Seçenekleri'ndeki ayrı bir anahtar) tam akışı denedi: Cihaz Ekle → cihaz ID gir → "Cihazı WiFi Ağına Bağla" → sistem WiFi ayarlarından `BinaryEnerji-anl13-05bb00`'a bağlan → ev WiFi SSID/şifresini gönder.
  - **Karşılaşılan gerçek bug ve düzeltmesi:** İlk denemede "Cihaza ulaşılamadı" hatası alındı. Sebep: telefonun mobil verisi açıkken, Android interneti olmayan bir WiFi ağına (ESP32'nin AP'si) bağlı olsa bile uygulama trafiğini varsayılan olarak mobil veriye yönlendiriyor — `192.168.4.1` mobil veriden erişilemez. **Çözüm:** `WifiProvisioningScreen.kt`'e `ConnectivityManager.allNetworks` üzerinden WiFi transport'lu ağı bulup `OkHttpClient.Builder().socketFactory(network.socketFactory)` ile isteği o ağa özel olarak bağlayan bir `wifiBoundClient()` fonksiyonu eklendi — `WifiNetworkSpecifier`'ın programatik-katılma karmaşıklığına girmeden, sadece "hangi ağdan gönderiliyor" sorununu çözüyor.
  - **Sonuç:** `generate_claim_code.py` ile üretilen kurulum koduyla (`13E2FD`) cihaz hesaba eklendi, dashboard'da durum rozeti **sarı "Veri akışı yok"** gösterdi — bu ESP32'nin MQTT broker'a başarıyla bağlanıp "online" yayınladığını (yani **WiFi kurulumunun tam çalıştığını**) kanıtlıyor; sarı olmasının nedeni bu test kartının gerçek bir ANL13'e RS-485 ile bağlı olmaması (bilinen/beklenen durum, bkz. bölüm 5.4). Gerçek ANL13'e bağlı bir üretim cihazında bu yeşil "Canlı" olacaktır.
  - **Not — iOS tarafında da aynı mobil-veri sorunu potansiyel olarak var olabilir** ama iOS'ta henüz test edilmedi (Apple Developer Program bekleniyor); test sırasında benzer bir "cihaza ulaşılamadı" hatası çıkarsa, `URLSession` isteğini `NWPathMonitor`/`NEHotspotConfiguration`'ın döndürdüğü arayüze bağlamak gerekebilir — o zaman ele alınacak.

**⏸️ Sıradaki adımlar:**
1. **iOS'ta gerçek cihazda WiFi kurulum testi** — kullanıcı Apple Developer Program'a üye olunca: Xcode'da Team'i güncelleyip fiziksel iPhone'a tekrar kurulum, "Cihaz Ekle" → "Cihazı WiFi Ağına Bağla" akışı denenmeli. Android'de karşılaşılan mobil-veri/network-binding sorunu iOS'ta da çıkabilir (yukarıdaki not), çıkarsa aynı mantıkla (isteği doğru arayüze bağlama) çözülecek.
3. Google Play Developer hesabı ($25, tek seferlik) — Android'i yayınlamadan önce gerekecek, henüz alınmadı.

### 5.6 ⚠️ ÇÖZÜLMEDİ — ANL13'te Akım/Güç/Reaktif/PF/THD/Enerji Endeksi Tutarsız (19-20 Ağustos 2026)

**Bulgu:** Kullanıcı, cihazın ön panelindeki değerlerle (10 A) uygulamada görünen değeri (1.632 A) karşılaştırdı — **tamamen anlamsız/rastgele**. Sadece **gerilim (V) doğru**, geri kalan her şey (Akım, Güç, Reaktif, Görünür, PF, THD) yanlış. Ayrıca **enerji "endeksi" (kümülatif sayaç) sürekli artıp azalıyor** — kümülatif bir sayaç fiziksel olarak asla azalamayacağı için bu, tek okumadan diğerine bazen bozuk veri geldiğini gösteriyor.

**Teşhis (şimdiye kadar):**
- Değer, ESP32'nin JSON'ında zaten yanlış (`%.3f` formatlı "1.632" ESP32'den geldiği haliyle görünüyor, backend/web'de bozulmuyor) — sorun **firmware/Modbus okuma seviyesinde**, kod mantığında ya da RS-485 hattında.
- V doğru ama I/P/Q/S aynı Modbus cevabından (register 1004 bloğu) geliyor — CRC kontrolünden geçmiş bir cevapta sadece bazı alanların bozuk olması normalde beklenmez, bu yüzden basit bir register-offset hatasından çok **RS-485 hat güvenilirliği** (parazit, gevşek bağlantı, sonlandırma direnci, iki cihazın aynı hattı paylaşması) şüpheleniliyor.
- Kullanıcıdan Serial Monitor çıktısı ("Modbus okuma hatasi!" satırı çıkıyor mu, çıkmıyor mu) istendi ama henüz paylaşılmadı — **konuşma bu noktada yeni cihaz (bölüm 5.7) tanıtımına kaydığı için teşhis yarım kaldı.**

**Sonraki oturumda yapılacak:** Serial Monitor çıktısını alıp devam edin. RS-485 A/B kabloları, sonlandırma direnci ve ikinci test kartının (`anl13-05bb00`) aynı hatta fiziksel olarak bağlı olup olmadığı da kontrol edilmeli (kullanıcıya soruldu, yanıt henüz gelmedi).

### 5.7 İkinci Cihaz Markası Desteği — ANL21 "Dijital Çıkışlı Şebeke Analizörü" (Grup ARGE, 20 Ağustos 2026 — firmware yazıldı, HENÜZ FLAŞLANIP TEST EDİLMEDİ)

**Bağlam:** Kullanıcı artık ANL13 değil, aynı üretici (Grup ARGE) markalı farklı bir model ("Dijital Çıkışlı Şebeke Analizörü") izlemek istiyor — bölüm 5.4'te öngörülen "marka başına ayrı firmware" yaklaşımı ilk kez uygulanıyor.

**Doküman süreci:** Kullanıcının verdiği kullanma kılavuzu PDF'inde (gruparge.com) Modbus register haritası **yoktu** (sadece ön panel/menü anlatımı, 36 sayfa) — bu tespit edilip kullanıcıya bildirildi, kullanıcı ayrıca bir Excel dosyası (`sebeke-analizoru-modbus-haritasi.xlsx`) buldu, asıl harita oradan çıkarıldı.

**Yeni proje:** `/Users/omergurgen/Desktop/ESP32-ANL21/ESP32-ANL21.ino` (cihaz adı ANL21, cihaz ID öneki `anl21-`) — ANL13'ün WiFi kurulumu/MQTT/otomatik yeniden bağlanma altyapısı birebir taşındı (kanıtlanmış, değişmedi), sadece Modbus okuma tarafı bu cihaza özel yeniden yazıldı:
- **Register yapısı ANL13'ten tamamen farklı:** Tüm anlık değerler **Signed 32-bit** (2 register/alan, ANL13'te 16-bit tekliydi), enerji sayaçları **Unsigned 64-bit** (4 register/alan). Anlık değer bloğu 10050-10125 arası tek seferde (76 register) okunuyor; enerji "toplam" üçlüsü (Aktif/Endüktif/Kapasitif) Tüketim için 13020, Üretim için 13280'den okunuyor.
- **64-bit enerji, 32-bit'e indirgeniyor** (ESP32'de `%llu` printf desteği güvenilir değil, gerçekçi Wh değerleri zaten 32-bit'e sığar) — LSW çifti alınıyor, MSW çifti (hep 0 beklenir) atlanıyor.
- **THD burada ikiye ayrılıyor:** Bu cihaz THVD (gerilim) ve THID (akım) diye ayrı register'lar veriyor. Kullanıcı **ikisini de** istedi — bu yüzden **sistem genelinde** (firmware + backend `measurements` tablosu + web `PhaseCard` + iOS/Android `LiveMeasurement`/`PhaseCard`) yeni bir `thvd1/2/3` alanı eklendi, mevcut `thd1/2/3` (artık akım/THID) yanında. ANL13 `thvd` göndermediği için o cihazda bu alan hep NULL kalacak — geriye dönük uyumlu, ekstra migration ANL13 tarafını etkilemedi.
- **Backend/web/mobil deploy edildi** (`ALTER TABLE measurements ADD COLUMN thvd1/2/3`, `api.py` INSERT/SELECT güncellendi, web `PhaseCard`'a "THD (Akım) / THD (Gerilim)" satırı eklendi, iOS build **BUILD SUCCEEDED**, Android derleme bu ortamda test edilemedi ama aynı desen).

**⚠️ Doğrulanmamış / bilinmeyen 4 nokta (ilk gerçek flaşlamada kontrol edilmeli):**
1. **32-bit kelime sırası** (`WORDS_HIGH_FIRST`) — Excel'de belirtilmemiş, ANL13'teki gibi "absürt değer çıkarsa flip et" yaklaşımı.
2. **Modbus hızı** — Excel'den 19200 varsayıldı, cihazın Ayarlar > Modbus Ayarları ekranındaki gerçek değerle teyit edilmedi.
3. **Modbus adresi** — ANL13 gibi `1` varsayıldı, teyit edilmedi.
4. ~~Cihazın marka/model kısaltması~~ — **Tamamlandı**: cihaz adı **ANL21**, klasör/dosya `ESP32-ANL21`, cihaz ID öneki `anl21-`.

**Not:** Bölüm 5.6'daki ANL13 veri tutarsızlığı sorunu bu firmware'i etkilemiyor (ayrı, bağımsız bir cihaz/kod tabanı) ama aynı RS-485/Modbus okuma disiplinine bağlı olduğu için, ANL13'teki kök neden bulunursa burada da benzer bir hataya karşı dikkatli olunmalı.

### 5.8 ANL21 Kapsamlı Dashboard — Faz 1-4 Tamamlandı (20 Ağustos 2026)

Bölüm 5.7'nin devamı — yukarıdaki "flaşlanıp test edilmedi" notu artık **güncel değil**, o günden bu yana dört faz da tamamlandı:

- **Faz 1 (firmware):** ANL21'e Toplam/Ortalama, Tepe (Min/Max), Demand, Harmonikler (Akım+Gerilim), Cihaz Bilgisi blokları eklendi; Kademeler kapsam dışı bırakıldı (bu ANL21 birimi kompanzasyon rölesi değil). Gerçek donanımla defalarca flaşlanıp test edildi — Live/Totals'taki **ModbusMaster 64-register tampon sınırı bug'ı** (76/92/80 register'lık okumalar sessizce `0xFFFF` sentinel veriyordu) bulunup düzeltildi. Peak "Üretim" ve THVD/THID sub-okumalarında hâlâ ara sıra `0xA0000000` bozulma imzası var (kök neden bulunamadı, retry-wrapper mitigation'ı var ama test edilmedi) — düşük öncelikli, kullanıcı isteğiyle non-urgent bırakıldı.
- **Faz 2 (backend):** 5 yeni tablo (`device_stats/peaks/demand/harmonics`, `device_info`) + 5 yeni `GET` endpoint + MQTT wiring + `DEVICE_COMMANDS` genişletmesi (`0xAA55`/43605 tetik değeriyle — ANL13'ün `sonuc=HATA` deneyiminden farklı olarak bu değer ANL21 kılavuzunda belgeliydi). Deploy edildi, curl ile doğrulandı.
- **Faz 3 (web):** `src/App.jsx`'e `StatsSection`/`PeaksSection`/`DemandSection`/`HarmonicsSection` (Recharts bar chart)/`DeviceInfoSection` + gerçek çalışan "Cihaz Komutları" paneli (düşük risk tek tık, yüksek risk ad-yazma onayı) eklendi. Tüm yeni bölümler `deviceInfo != null` vb. ile gate'li, ANL13 dashboardu etkilenmedi. Production'da gerçek veriyle doğrulandı.
- **Akım Trafo Oranı düzeltmesi (aynı gün, ayrı bir keşif):** `CT_RATIO_REGISTER` **214 değil 221**'miş — 214 "Okuma Koruma Biti" (CT ile ilgisiz), 221 "Akım Trafo Oranı Table Index". Excel'in Parametreler sayfasında index↔gerçek-oran (X/5 A) tablosunun tamamı (70 satır) belgeliydi. `api.py`, ANL13 firmware (`readCtRatio`) ve yeni ANL21 firmware okuma desteği düzeltildi/eklendi; web'de salt-okunur "Index: X" yerine 70 geçerli değerden seçilen dropdown geldi. İki firmware de temiz derlendi, deploy bekliyor (acil değil).
- **Faz 4 (mobil):** iOS (`BinaryEnerjiApp`, SwiftUI) ve Android (`BinaryEnerjiAndroid`, Jetpack Compose) uygulamalarına aynı 5 bölüm + CT oranı dropdown'u + komut paneli eklendi (`DeviceDashboardSections.swift` / `DeviceDashboardSections.kt`, yeni modeller `Models.swift`/`Models.kt`'e, yeni endpoint çağrıları `APIClient.swift`/`ApiClient.kt`'e). **İki platform da temiz derlendi** (`xcodebuild` BUILD SUCCEEDED, `./gradlew assembleDebug` BUILD SUCCESSFUL — Android derlemesi için `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"` gerekti, sistemde ayrı bir JDK kurulu değil). Harmonik grafiği iOS'ta native `Charts` (iOS 16+), Android'de üçüncü parti bağımlılık eklemeden basit bir `Canvas` bar chart ile çizildi. **iOS Simulator'da görsel olarak doğrulandı (21 Ağustos 2026):** `iPhone 17 Pro` simulator'ünde build alınıp çalıştırıldı, kullanıcı kendi hesabıyla giriş yapıp "test anl21" cihazının dashboard'unu kontrol etti — çalışıyor. (Claude kimlik bilgilerini görmedi/girmedi, sadece paneli açıp kullanıcının girişini bekledi.)

**Android emulator'de de doğrulandı (21 Ağustos 2026), bir kazayla birlikte:** `Pixel_8` AVD'de APK kurulup çalıştırıldı. İlk denemede, emulator üzerinde ekran kaydırırken beklenmedik bir sistem "stylus/el yazısı" overlay'i tetiklendi ve arkasındaki "Cancel"a basmaya çalışan dokunuş aslında uygulamanın kendi "Fabrika Ayarlarına Dön" onay panelindeki (önceki bir oturumdan kalma, önceden doldurulmuş) "Onayla ve Gönder" butonuna denk geldi — **register 9024 (Fabrika Ayarlarına Dön, 0xAA55) `anl21-8085d8` cihazına gerçekten gönderildi** (API 200 döndü, MQTT publish başarılı loglandı). Kontrol edildi: cihaz o sırada ~6.5 saattir zaten MQTT'ye bağlı değildi, `publish_command()` QoS 0/retain=False ile yayınlıyor (mosquitto offline client için kuyruğa almıyor), yani komut muhtemelen hiç ulaşmadı — kullanıcı fiziksel cihazı kontrol edip ayarların/sayaçların bozulmadığını doğruladı. **Ders:** emulator'de swipe gibi jest tabanlı etkileşimlerden sonra (özellikle geri alınamaz aksiyonlara yakın ekranlarda) ekran görüntüsüyle doğrulamadan başka bir dokunuş yapılmayacak; ikinci denemede `uiautomator dump` ile kesin element sınırları kullanılarak ve "Cihaz Ayarları" paneline hiç dokunulmadan (zaten kazadan önceki ekran görüntüsünde doğru render olduğu görülmüştü) tüm yeni bölümler (Sistem Özeti/Tepe/Demand/Harmonik/Cihaz Bilgileri) güvenle doğrulandı.

**Faz 4 sonrası — güvenlik sertleştirmesi (21 Ağustos 2026):** Faz 2-4'te eklenen komut paneli, [[project-power-dashboard-security-notes]]'ta 20 Ağustos'ta bulunan iki açığı birbirine bağlıyordu: rate-limit'siz 6-hex claim-code brute force + sunucu tarafında risk seviyesi ayrımı olmayan komut endpoint'i — biri diğerini kolayca istismar edilebilir hale getiriyordu. İkisi de düzeltildi:
- `api.py`'e basit bellek-içi sliding-window rate limiter eklendi (`check_rate_limit()`, tek uvicorn process olduğu için Redis gerekmedi): `/login` 15/15dk/IP, `/register` 10/saat/IP, cihaz claim 10/saat/device_id (nginx'in `X-Real-IP` header'ı kullanılıyor).
- `POST /devices/{id}/command` artık yüksek riskli komutlar (`factory_reset`, `reset_password`) için hesap şifresinin yeniden girilmesini (bcrypt doğrulamalı) zorunlu kılıyor — çalınmış/sızmış bir JWT'nin (30 gün geçerli, iptal mekanizması yok) tek başına bu komutları çalıştırmasını da engelliyor. Bu da 5/saat/kullanıcı rate-limit'li.
- Web/iOS/Android'deki yüksek-risk onay paneline (cihaz adı yazma) bir şifre alanı daha eklendi, üçü de deploy/derleme ile doğrulandı; backend curl ile canlı test edildi (şifresiz/yanlış şifre → 403, rate limit → 429, düşük risk komutlar etkilenmedi).

**Aynı gün devamı — kalan 2 güvenlik bulgusu da kapatıldı:** Ayrıca 5 proje dizininin hepsinde (`power-dashboard`, iki mobil app, iki firmware) daha önce hiç olmayan `git init` + ilk commit yapıldı (bkz. [[project-power-dashboard-security-notes]]).
- **CORS daraltıldı**: `allow_origins=["*"]` → `[SITE_URL, "http://localhost:5173"]`, methods/headers de spesifik listeye indirildi. curl ile doğrulandı: izinli origin `Access-Control-Allow-Origin` alıyor, rastgele bir origin almıyor.
- **`POSTGRES_PASSWORD` rotasyonu**: `MQTT_PASSWORD` ile aynıydı — ve `MQTT_PASSWORD`'ün sadece `.env`'de değil, **her iki ESP32 firmware'inde de düz metin hardcoded** olduğu (`"esp32user"`/`"16256-Omer"`) fark edildi, yani sahadaki her cihazın flash'ından çıkarılabilir durumda. Bu yüzden DB şifresi bağımsız, yeni bir rastgele değere döndürüldü (MQTT_PASSWORD'e dokunulmadı — değiştirmek her iki cihazın da yeniden flaşlanmasını gerektirirdi). **Bu rotasyonu Claude değil, kullanıcı kendi VPS terminalinden yaptı** — harness'in auto-mode Bash sınıflandırıcısı `ALTER USER ... WITH PASSWORD` gibi kimlik bilgisi değiştiren komutları, sohbette açık onay verilmiş olsa bile engelliyor. Downtime'sız doğrulandı (`/devices` gerçek bir DB sorgusu gerektiriyor, 200 döndü).

### mosquitto (container: `root-mosquitto-1`)
- İmaj: `eclipse-mosquitto:2`
- Port: `1883` (host'a `0.0.0.0:1883` açık — ESP32 dışarıdan bağlanıyor)
- Config ve şifre dosyası **host'tan bind-mount** ediliyor (container'a kopyalanmıyor):
  - `/etc/mosquitto/conf.d/default.conf` → `/mosquitto/config/mosquitto.conf`
  - `/etc/mosquitto/passwd` → `/etc/mosquitto/passwd`
- `/etc/mosquitto/passwd` dosyasının sahipliği container içindeki `mosquitto` kullanıcısının UID/GID'siyle (`1883:1883`) eşleşecek şekilde `chown 1883:1883` + `chmod 700` yapıldı (bkz. bölüm 8 — bind-mount host/container arasında aynı inode olduğu için sahiplik host tarafında ayarlanmalı)
- Kullanıcı: `esp32user` (şifre `mosquitto_passwd` ile ayrıca belirlendi, `.env`'de de aynı şifre `MQTT_PASSWORD` olarak duruyor)
- Persistent veri/log için named volume: `mosquitto_data`, `mosquitto_log`

### timescaledb (container: `root-timescaledb-1`)
- İmaj: `timescale/timescaledb:latest-pg16`
- Port: `127.0.0.1:5432` (sadece loopback — sadece `api` container'ı internal Docker network üzerinden erişiyor, artık dışarıya açık değil)
- Kalıcı veri: Docker volume `timescale_data` — **`docker-compose.yml`'de `external: true` olarak tanımlı**, yani compose bu volume'ü asla silmez/yeniden oluşturmaz. Docker Compose'a geçmeden önce bu container tek başına `docker run` ile ayaktaydı; geçiş sırasında container silinip aynı volume ile compose altında yeniden oluşturuldu, **veri kaybı olmadı** (14.640 satır korundu, doğrulandı).
- Veritabanı: `postgres`, kullanıcı: `postgres`, şifre `.env`'deki `POSTGRES_PASSWORD` (gerçek değer VPS'te `/root/.env` içinde)
- **Not:** Postgres, `POSTGRES_PASSWORD` env değişkenini sadece volume boşken (ilk `initdb`) uygular — var olan `timescale_data` volume'ünde zaten bir şifre gömülü olduğu için compose'daki değer sadece dokümantasyon/tutarlılık amaçlı, gerçek kimlik doğrulama volume içindeki değeri kullanır.
- Tablo: `measurements` (hypertable, zaman kolonu: `time`)
  ```sql
  CREATE TABLE measurements (
      time TIMESTAMPTZ NOT NULL DEFAULT now(),
      device_id TEXT NOT NULL,
      v1 DOUBLE PRECISION, i1 DOUBLE PRECISION, p1 DOUBLE PRECISION, f1 DOUBLE PRECISION,
      v2 DOUBLE PRECISION, i2 DOUBLE PRECISION, p2 DOUBLE PRECISION,
      v3 DOUBLE PRECISION, i3 DOUBLE PRECISION, p3 DOUBLE PRECISION,
      vL12 DOUBLE PRECISION, vL23 DOUBLE PRECISION, vL31 DOUBLE PRECISION
  );
  SELECT create_hypertable('measurements', 'time');
  ```
- Bağlanma: `docker compose exec timescaledb psql -U postgres`

### api (container: `root-api-1`)
- `Dockerfile`'dan build edilir, `requirements.txt` + `api.py` + `create_user.py` image içine kopyalanır (üçü de `COPY` edilmeli — `create_user.py` sonradan eklendiğinde bir kere Dockerfile'a eklenmeyi unutup `docker compose exec api python create_user.py` "No such file" hatası verdi, bkz. bölüm 8)
- `google-service-account.json`, image'a kopyalanmaz, `docker-compose.yml`'de bind-mount edilir: `/root/google-service-account.json:/app/google-service-account.json:ro`
- Port: `127.0.0.1:8000` (Nginx aynı porta proxy yapıyor, değişmedi)
- Ortam değişkenleri (`docker-compose.yml` → `.env`'den): `DB_HOST=timescaledb`, `MQTT_BROKER=mosquitto`, `POSTGRES_PASSWORD`, `MQTT_USER`, `MQTT_PASSWORD`, `JWT_SECRET`, `RESEND_API_KEY`, `RESEND_FROM`, `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE=/app/google-service-account.json` — kod içinde artık hiçbir şifre hardcoded değil, hepsi `os.environ` ile okunuyor
- Endpoint'ler:
  - `POST /register` — ad/soyad/kullanıcı adı/e-posta/telefon/şifre alır, doğrulanmamış hesap açar, doğrulama e-postası + Sheets kaydı tetikler (auth yok)
  - `GET /verify?token=...` — hesabı doğrular, HTML onay sayfası döner (auth yok)
  - `POST /login` — kullanıcı adı/şifre + `is_verified` doğrulanır, JWT token döner (auth yok)
  - `GET /measurements?minutes=N` — son N dakikanın verisi (JSON array, **JWT gerekli**)
  - `WS /ws/live?token=...` — canlı veri yayını (MQTT'den gelen her mesaj tüm bağlı WebSocket istemcilerine push edilir, **JWT gerekli**)
- MQTT dinleyici (`mqtt_thread`), ayrı bir thread içinde çalışıyor, aynı process içinde hem DB'ye yazıyor hem WebSocket'e broadcast ediyor
- **Auto-reconnect:** `client.connect_async(...)` + `client.loop_forever(retry_first_connection=True)` kullanılıyor — broker (mosquitto container) API'den geç açılırsa veya bağlantı koparsa, thread çökmeden otomatik tekrar dener (bkz. bölüm 8 — daha önce tek seferlik `connect()` kullanılıyordu ve broker hazır değilken thread sessizce çöküyordu)
- Üç servis de aynı custom bridge network'te (`power_net`) — birbirlerini `timescaledb` / `mosquitto` servis adlarıyla buluyorlar

### Native systemd servisleri (artık kullanılmıyor, geri dönüş için duruyor)
- `mosquitto.service` ve `powerapi.service` — Docker Compose'a geçişte `systemctl stop` + `systemctl disable` edildi (silinmedi). Bir sorun çıkarsa `systemctl enable --now mosquitto powerapi` ile geri dönülebilir, ama bu durumda önce `docker compose down` ile container'ların portları (1883, 8000) serbest bırakması gerekir.
- `/etc/systemd/system/powerapi.service` dosyası hâlâ diskte duruyor, referans için:
  ```ini
  [Unit]
  Description=Power Monitor FastAPI Service
  After=network.target docker.service
  [Service]
  Type=simple
  User=root
  WorkingDirectory=/root
  ExecStart=/root/modbus_env/bin/uvicorn api:app --host 0.0.0.0 --port 8000
  Restart=always
  RestartSec=5
  [Install]
  WantedBy=multi-user.target
  ```

### Nginx (Reverse Proxy + Statik Sunucu + SSL)
- Config: `/etc/nginx/sites-available/dashboard` (symlink: `/etc/nginx/sites-enabled/dashboard`)
- Statik dashboard dosyaları: `/var/www/dashboard` (React `dist` build'inin içeriği, `www-data:www-data` sahipliğinde olmalı)
- SSL sertifikası: Let's Encrypt / Certbot ile kuruldu, otomatik yenileniyor (systemd timer: `certbot.timer`)
- Sertifika dosyaları: `/etc/letsencrypt/live/binaryenerji.com/`
- **Docker Compose'a geçişte değişmedi** — container'lar host'ta aynı portları (8000) publish ettiği için config aynı kaldı:
  ```nginx
  server {
      listen 80;
      server_name binaryenerji.com www.binaryenerji.com;
      return 301 https://$host$request_uri;
  }
  server {
      listen 443 ssl;
      server_name binaryenerji.com www.binaryenerji.com;
      ssl_certificate /etc/letsencrypt/live/binaryenerji.com/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/binaryenerji.com/privkey.pem;
      include /etc/letsencrypt/options-ssl-nginx.conf;
      ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
      root /var/www/dashboard;
      index index.html;
      location / {
          try_files $uri $uri/ /index.html;
      }
      location /api/ {
          proxy_pass http://127.0.0.1:8000/;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }
      location /ws/ {
          proxy_pass http://127.0.0.1:8000/ws/;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "upgrade";
          proxy_set_header Host $host;
      }
  }
  ```

## 6. Domain ve DNS

- **Domain:** `binaryenerji.com` (ve `www.binaryenerji.com`)
- **Sağlayıcı:** hosting.com.tr (nameserver: `p3.hosting.com.tr`, `p4.hosting.com.tr`)
- **DNS Zone kayıtları (A):**
  - `binaryenerji.com` → `138.68.83.111`
  - `www.binaryenerji.com` → `138.68.83.111`
- **Önemli ders:** Domain kaydı ile aynı gün DNS Zone Yönetimi'nde "Domain Park" özelliği açıkken A kayıtları çalışmıyordu (NS sorguları REFUSED/SERVFAIL dönüyordu). Hosting sağlayıcısı desteğiyle "Domain Park" kapatıldıktan sonra DNS birkaç saat içinde normal şekilde yayıldı.

## 7. Frontend (React Dashboard)

- **Konum (geliştirme):** Mac'te `~/Desktop/power-dashboard`
- **Framework:** React + Vite
- **Ana dosya:** `src/App.jsx` (`src/main.jsx` bunu import ediyor). Kökte eski/stale bir `App.jsx` kopyası vardı (dev-döneminden kalma yanlış IP'ler içeriyordu, build'e dahil değildi) — karışıklığa yol açtığı için silindi (13 Ağustos 2026).
- **Kullanılan kütüphaneler:** `axios` (REST istekleri), `recharts` (gerilim grafiği), native `WebSocket` (canlı veri)
- **Login/Üye Ol akışı (`src/App.jsx` içindeki `AuthForm` bileşeni):**
  - `localStorage`'da `token` yoksa `AuthForm` gösterilir — sekmeli: **Giriş Yap** / **Üye Ol**
  - Üye Ol modunda ad, soyad, kullanıcı adı, e-posta, telefon, şifre (+ tekrar) alanları ve KVKK onay checkbox'ı var; checkbox işaretlenmeden gönderilemez
  - `POST /register` başarılı olunca **otomatik giriş yapılmıyor** — "E-postanızı kontrol edin" mesajı gösterilip Giriş Yap moduna dönülüyor (hesap henüz doğrulanmadığı için token yok zaten)
  - Login `403` dönerse ("hesap doğrulanmadı") ayrı bir mesaj gösteriliyor, `401`den (yanlış şifre) farklı
  - Başarılı girişte token `localStorage`'a yazılır; `/measurements` çağrısına `Authorization: Bearer <token>` header'ı, WS bağlantısına `?token=<token>` query param'ı eklenir
  - `/measurements` `401` dönerse (token geçersiz/süresi dolmuş) otomatik olarak `localStorage` temizlenip giriş formuna dönülür
  - Header'da "Çıkış Yap" butonu — token'ı temizler
- **Bileşen yapısı (`src/App.jsx`):** `App` (üst seviye state: `token`, `devices`, `selectedDevice`) → giriş yoksa `AuthForm`, giriş varsa ve cihaz seçilmemişse `DeviceList` ("Cihazlarım"), bir cihaz seçilince `DeviceDashboard` (eski tek-cihazlı dashboard'un `device_id`'ye göre parametrik hali, `PhaseCard` ve grafiği içeriyor). Detaylar için bkz. bölüm 5.2.
- **Tasarım:** Entes Enerji Doktoru esintili, özgün palet:
  - Arka plan: `#F4F6F9`, kart: `#FFFFFF`, ana metin: `#0B1F3A`
  - Faz renkleri: L1 bakır `#C97A2B`, L2 teal `#1B7A72`, L3 indigo `#4A5FC1`
  - Tipografi: IBM Plex Sans (arayüz), IBM Plex Mono (sayısal okumalar)
  - Marka etiketi: tüm başlıklarda küçük harf "GRUP ARGE" yerine artık "BINARY ENERJİ" kullanılıyor (15 Ağustos 2026) — `Grup Arge` ismi sadece ANL13 analizörünün gerçek üreticisi olarak bölüm 1/3'te kalmaya devam ediyor
  - **Logo (15 Ağustos 2026):** Kullanıcının verdiği "10" şeklindeki logo `public/logo.png` olarak eklendi. Orijinal dosya JPG'ydi ve düz beyaz arka planı vardı — favicon/tab ikonunda bu beyazlık sayfa/tarayıcı arka planıyla karışıp logoyu görünmez kılıyordu. Yerel olarak (`/tmp/imgenv` içinde izole bir venv'e kurulan Pillow ile) beyaz piksel arka plan şeffaflaştırıldı, işaret sıkı bir şekilde kırpılıp biraz boşluklu kare bir tuvale ortalandı, PNG olarak kaydedildi. `index.html`'de `<link rel="icon" type="image/png" href="/logo.png" />` ile favicon olarak, `App.jsx`'te de `AuthForm`/`DeviceList`/`DeviceDashboard` başlıklarında "BINARY ENERJİ" yazısının yanında/üstünde `<img>` olarak kullanılıyor. **Not:** Tarayıcılar favicon'u agresif önbelleğe alır — değişiklik hemen görünmeyebilir, sekmeyi kapatıp yeniden açmak veya gizli pencere gerekebilir.
  - **"ANL13 Güç İzleme" başlığı kaldırıldı (15 Ağustos 2026):** Sistem artık çoklu cihaz destekliyor (bkz. bölüm 5.2), bu yüzden giriş ekranında cihaza özel bir başlık göstermek yanıltıcıydı. `AuthForm`'daki `<h1>ANL13 Güç İzleme</h1>` kaldırıldı, sadece logo + "BINARY ENERJİ" etiketi kaldı. Aynı sebeple tarayıcı sekmesi başlığı da (`index.html` `<title>`) "ANL13 · Güç İzleme"den **"Binary Enerji · Güç İzleme"**ye güncellendi. (Cihaz seçildikten sonraki `DeviceDashboard` ekranında cihazın kendi adı zaten `h1` olarak gösteriliyor — bkz. bölüm 5.2 — o kısımda değişiklik yok.)
- **Mobil uyumluluk (15 Ağustos 2026):**
  - `inputStyle`'daki `fontSize` 14'ten **16**'ya çıkarıldı — iOS Safari, 16px'ten küçük font'lu bir input'a odaklanınca sayfayı otomatik yakınlaştırıyor, bu App Store/web app kullanımında can sıkıcı bir davranış
  - `index.css`'e `.centered-page` class'ı eklendi (`AuthForm` ve `DeviceList`'in dış kapsayıcısında kullanılıyor): masaüstünde `margin: 100px auto`, `max-width: 480px` altında (mobil) `margin: 40px auto` — böylece formlar mobilde ekranın çok aşağısında başlamıyor
  - 320px genişliğe kadar test edildi (taşma yok, `* { box-sizing: border-box }` zaten global olarak tanımlıydı), `DeviceDashboard` (canlı veri kartları) `flexWrap: wrap` sayesinde zaten mobilde tek sütuna düşüyordu, ek değişiklik gerekmedi
  - `DeviceDashboard`'ın `<header>`'ına da `flexWrap: 'wrap', gap: 12` eklendi — sol blok (geri butonu/marka/cihaz adı) ve sağ blok (canlı durumu/saat/çıkış) kısa isimlerle (`ANL13`) yan yana sığıyordu ama uzun bir cihaz ismi veya çok dar bir ekranda sıkışabilirdi, önlem olarak eklendi (test: geçici bir test hesabı+cihaz açılıp 320px'de doğrulandı, sonra silindi)
- **Bağlantı adresleri (production, App.jsx içinde):**
  ```js
  const API_BASE = 'https://binaryenerji.com/api';
  const WS_URL = 'wss://binaryenerji.com/ws/live';
  ```
- **Deploy süreci:**
  1. `npm run build` (Mac'te, `power-dashboard` klasöründe) → `dist/` klasörü oluşur
  2. `scp -r dist/* root@138.68.83.111:/var/www/dashboard/` ile VPS'e kopyalanır
  3. Dosya sahipliği `www-data:www-data` olmalı (Nginx erişimi için)

## 8. Karşılaşılan Önemli Sorunlar ve Çözümleri (Gelecekte Faydalı Olabilir)

| Sorun | Çözüm |
|---|---|
| Apple Silicon Mac'te Arduino IDE `ctags` mimari hatası | Arduino IDE 2.x'e güncelleme / board paketini yeniden kurma |
| Arduino IDE fonksiyon prototip hatası (`struct` parametre) | Struct'ı global değişken yapıp fonksiyonu parametresiz kullanma |
| `mosquitto_sub` "Bad file descriptor" hatası | `ulimit` değil — gerçek sebep config dosyasının hiç var olmamasıydı, örnek dosyadan kopyalanıp `listener`/`allow_anonymous` eklendi |
| Mosquitto systemd "error" (exit 13) — **native servis** | `/etc/mosquitto/passwd` dosya sahipliği `mosquitto:mosquitto` olmalı, `chmod 640` |
| TimescaleDB `password authentication failed` | Docker'a verilen şifre ile `api.py`'daki şifre eşleşmiyordu, `ALTER USER postgres PASSWORD` ile senkronize edildi |
| Nginx 500 Internal Server Error | `/root` klasörüne `www-data`'nın erişimi yok — dosyalar `/var/www/dashboard`'a taşındı |
| Dashboard'da veri gelmiyor (VPS'e geçtikten sonra) | `App.jsx`'teki `API_BASE`/`WS_URL` hâlâ `localhost` gösteriyordu, güncellenip yeniden build edildi |
| HTTPS sayfada API verisi gelmiyor (mixed content) | Dashboard `https://` üzerinden, API `http://` üzerinden çalışıyordu — Nginx reverse proxy ile `/api` ve `/ws` aynı domain/HTTPS altına alındı |
| Domain DNS NS sorgusu REFUSED | Yeni kayıtlı domain'de "Domain Park" özelliği DNS zone servisini engelliyordu, destek ile kapatıldı |
| **Mosquitto container `Restarting (13)`** (Docker Compose geçişinde) | Host'tan bind-mount edilen `/etc/mosquitto/passwd`, container içindeki `mosquitto` kullanıcısı tarafından okunamıyordu (`Unable to open pwfile`). Acil çözüm: `chmod 644` (geçici, "world readable" uyarısı veriyordu). Kalıcı çözüm: container'ın gerçek UID/GID'sini (`docker compose exec mosquitto id -u/-g mosquitto` → `1883:1883`) host dosyasına `chown` edip `chmod 700` yapmak — bind-mount'ta host ve container aynı inode'u paylaştığı için sahiplik host tarafında container'ın UID'siyle eşleşmeli |
| **API container'da MQTT hiç bağlanmıyor, WebSocket'e veri düşmüyor** (Docker Compose geçişinde) | `api` container'ı, `mosquitto` container'ı henüz `Restarting (13)` durumundayken ayağa kalkmıştı; `mqtt_thread` içindeki tek seferlik `client.connect()` `ConnectionRefusedError` fırlattı ve **thread sessizce çöktü** (FastAPI'nin kendisi ayakta kaldığı için container "Up" görünüyordu, sorun fark edilmesi zor oldu). Çözüm: `client.connect_async()` + `client.loop_forever(retry_first_connection=True)` — broker geç açılsa da otomatik tekrar dener, thread çökmez. Mevcut çökmüş container için tek seferlik çözüm: `docker compose restart api` |
| `create_user.py`, container içinde "No such file or directory" | Dosya VPS'in `/root/`'una `scp` edildi ama `Dockerfile` sadece `api.py`'yi image'a kopyalıyordu, `create_user.py`'yi değil. `COPY api.py create_user.py .` olarak güncellenip image yeniden build edildi |
| WebSocket'i tokensız/geçersiz token'la kapatınca tarayıcıda kod `1008` değil `1006` görünüyor | Starlette, `accept()` çağrılmadan önce `close(code=1008)` çağrıldığında bu kodu tarayıcıya düzgün iletemiyor, tarayıcı bunu anormal kapanma (`1006`) olarak yorumluyor. Güvenlik davranışı etkilenmiyor (bağlantı yine reddediliyor), sadece frontend'deki koda-özel mantık (bkz. bölüm 7) bu senaryoda tetiklenmiyor — düşük öncelikli, kozmetik bir fark |
| `POST /register` isteği süresiz askıda kalıyor, hiç yanıt dönmüyor | `smtplib.SMTP_SSL` ile Gmail'e (465/587) bağlanmaya çalışıyordu — **DigitalOcean VPS'lerde outbound SMTP portları varsayılan olarak tamamen kapalı** (`</dev/tcp/smtp.gmail.com/465` ve `/587` ikisi de "engelli" döndü, anti-spam politikası). SMTP tamamen terk edilip **Resend** (HTTPS API üzerinden e-posta, port 443, hiç engellenmiyor) kullanılmaya başlandı |
| Resend ile gönderilen e-posta gelmiyor, ama `/register` `200 OK` dönüyor | Resend hesabı domain doğrulanana kadar **sandbox modunda** — sadece hesabın kendi e-postasına (Resend'e kayıt olurken kullanılan adrese) gönderim yapabiliyor, başka adreslere sessizce başarısız oluyor (loglarda "You can only send testing emails to your own email address" hatası görünüyor, HTTP çağrısı `502` ile bloklanıyor çünkü `send_verification_email` hata fırlatıyor). Çözüm: `resend.com/domains`'te domain doğrulaması yapmak (bkz. 5.1) |
| Google Cloud'da "Service account key creation is disabled" | Yeni projelerde otomatik uygulanan "Secure by Default" organizasyon politikası (`iam.disableServiceAccountKeyCreation`). Proje seviyesinde **Organization Policies** sayfasından "Override parent's policy" ile kapatıldı (proje sahibi olarak bu yetkiye sahip olundu, org-wide admin gerekmedi) |
| Google Sheets'e yazarken `PermissionError: PermissionError()` (mesaj boş) | Yanıltıcı bir hata — dosya izin sorunu değil (`cat` ile container içinden dosya okunabiliyordu, sahiplik/mod doğruydu). Gerçek sebep: Google Cloud projesinde **"Google Sheets API" etkinleştirilmemişti** — Sheets API'nin döndürdüğü `403 Forbidden`'ı `gspread` kütüphanesi Python'un yerleşik `PermissionError`'ına çeviriyor. "APIs & Services" → "Enable APIs and services" → "Google Sheets API" ile etkinleştirilince düzeldi. (Not: Sheet'in servis hesabıyla paylaşılmış olması **yetmiyor**, API'nin proje genelinde de etkin olması gerekiyor.) |
| Resend domain doğrulaması "DNS invalid" — SPF (MX+TXT) sürekli başarısız | hosting.com.tr DNS panelinde `send` MX kaydının **Değer** alanına girilen `feedback-smtp.ap-northeast-1.amazonses.com` değerinin sonuna panel otomatik olarak `.binaryenerji.com. send` gibi fazladan metin ekliyordu (kayıt silinip aynı şekilde yeniden eklense bile tekrarlanan bir panel davranışı). Değerin sonuna elle bir nokta (`.`) eklenerek (`feedback-smtp.ap-northeast-1.amazonses.com.`, standart DNS "tam adres" gösterimi) panelin otomatik tamamlama mantığı devre dışı bırakıldı, kayıt doğru kaydedildi |

## 9. Sonraki Adım Fikirleri (Henüz Yapılmadı)

- ~~Docker Compose ile tüm VPS servislerini tek dosyada yönetilebilir hale getirme~~ — **Tamamlandı (13 Ağustos 2026)**, bkz. bölüm 5
- ~~Kullanıcı girişi (login) ekleyip dashboard'ı sadece yetkili kişilere açma~~ — **Tamamlandı (13 Ağustos 2026)**, bkz. bölüm 5.1
- ~~Kişisel bilgilerle üyelik + e-posta doğrulama + Google Sheets kaydı~~ — **Tamamlandı (15 Ağustos 2026)**, bkz. bölüm 5.1
- ~~Cihaz sahipliği modeli (dashboard sadece cihaz sahibine açık, diğerleri "Cihaz Ekle" görür)~~ — **Tamamlandı (15 Ağustos 2026)**, bkz. bölüm 5.2
- ~~Gerçek çoklu cihaz desteği~~ — **Tamamlandı (18 Ağustos 2026)**, bkz. bölüm 5.4 (MAC tabanlı benzersiz `device_id`, parametrik MQTT topic'leri, kurulum kodu güvenliği)
- **Mobil uygulama (native iOS/Swift + Android/Kotlin, tam kapsamlı, Tuya benzeri)** — devam ediyor, bkz. bölüm 5.5. Android: tam akış + WiFi kurulumu gerçek cihazda doğrulandı. iOS: temel akış Simulator'de doğrulandı, WiFi kurulumu kod olarak hazır ama gerçek cihaz testi Apple Developer Program üyeliğine bağlı bekliyor. **Her iki platformda da artık pariteli** (19 Ağustos 2026): Reaktif/Görünür/THD + Nötr satırı + saatlik enerji tablosu (web'deki `HourlyEnergyModal` karşılığı), "Ekle" butonu WiFi kurulumu tamamlanmadan aktif olmuyor, özel uygulama ikonu (marka lacivert zemin + "1/0" işareti) ve web ile birebir aynı renk paleti.
- Enerji tüketimi (kWh) hesaplama, günlük/aylık raporlama
- ~~ESP32 bağlantı kopması durumunda otomatik yeniden bağlanma~~ — **Tamamlandı (19 Ağustos 2026)**: `.ino`'nun `loop()` fonksiyonu artık her döngüde `WiFi.status()` kontrol ediyor; kopukluk varsa `WiFi.reconnect()` deniyor, **3 dakikadan uzun** süre toparlanamazsa `ESP.restart()` ile kendini yeniden başlatıyor (WiFi yığını bazen sadece tam reboot ile kurtuluyor). Önceden sadece MQTT seviyesinde reconnect vardı, gerçek WiFi kopmaları (15 Ağustos'taki 67 dakikalık kesinti gibi) hiç fark edilmiyordu. **Flaşlanmadı, henüz gerçek donanımda test edilmedi** — kullanıcı müsait olduğunda flaşlayıp doğrulamalı.
- ~~Geçmiş veriyi CSV/Excel olarak dışa aktarma özelliği~~ — **Tamamlandı (19 Ağustos 2026), sadece web:** `GET /energy/hourly?device_id=...&format=xlsx` (aynı endpoint, `format` parametresiyle JSON yerine gerçek bir `.xlsx` dosyası döndürüyor — `openpyxl` ile üretiliyor, kalın başlık satırı + otomatik sütun genişliği, sayılar metin değil gerçek Excel numarası olarak yazılıyor). İlk denemede düz CSV yapılmıştı, kullanıcı "xlsx olarak indirsin" deyince `openpyxl` (`requirements.txt`'e eklendi) ile gerçek Excel formatına geçirildi. Saatlik Enerji modalına "Excel indir" butonu eklendi (`axios` ile `responseType: 'blob'`, sonra tarayıcıda indirme tetikleniyor). Mobil uygulamalara eklenmedi (istenirse ayrı bir iş).
- Güvenlik notu: TimescaleDB ve MQTT için şu an aynı şifre kullanılıyor (`.env`'deki `POSTGRES_PASSWORD` ve `MQTT_PASSWORD`) — istenirse ayrıştırılabilir
- SMS ile doğrulama (şu an sadece e-posta) — ücretli bir SMS sağlayıcı (Netgsm, Twilio vb.) hesabı gerektirir, bilinçli olarak yapılmadı
- Alarm eşikleri (gerilim/akım anormal değerlerde bildirim — e-posta/Telegram)

### 5.9 Hesap Sayfası + Profil Fotoğrafı (22 Ağustos 2026)

Kullanıcı, uygulama içinde hesap ikonuna tıklandığında ayrı bir sayfa açılmasını ve profil fotoğrafı yükleyebilmeyi istedi. Öncesinde web'de hesap sayfası hiç yoktu; iOS'ta `.sheet` (zaten sayfa gibi), Android'de ise sadece bir `AlertDialog` vardı (gerçek bir sayfa değildi) — üçü de salt-okunur, fotoğraf yok.

**Backend (`api.py`) — sıfırdan yeni altyapı, bu depoda daha önce hiç dosya yükleme yoktu:**
- `users` tablosuna `avatar_updated_at TIMESTAMPTZ` eklendi (migration, VPS'te uygulandı).
- `python-multipart` + `Pillow` yeni bağımlılık (`requirements.txt`).
- `POST /me/avatar`: JPEG/PNG/WEBP kabul ediyor (max 5MB), Pillow ile doğrulanıp merkezden kare kırpılıp 512x512'ye küçültülüyor, `{username}.jpg` olarak diske kaydediliyor.
- `AVATAR_DIR=/app/uploads/avatars`, `app.mount("/avatars", StaticFiles(...))` ile **kimlik doğrulama gerektirmeden** servis ediliyor (hassas veri değil, `<img>`/`AsyncImage`/`Image` kullanımını basitleştiriyor). nginx `/api/` prefix'ini strip ettiği için dışarıdan `https://binaryenerji.com/api/avatars/{username}.jpg` olarak erişiliyor.
- `docker-compose.yml`'e `avatar_uploads` adlı kalıcı volume eklendi (`/app/uploads`) — container rebuild'lerinde fotoğraflar kaybolmasın diye.
- `GET /me` artık `created_at` (üyelik tarihi) ve `avatar_url` da döndürüyor.
- Uçtan uca curl ile doğrulandı: yükleme, content-type reddi (resim olmayan dosya), statik servis, `GET /me`'nin güncellenmiş `avatar_url`'ü yansıtması.

**Web (`src/App.jsx`):** Yeni `AccountPage` bileşeni, mevcut state-machine navigasyon desenine uyularak (`selectedDevice` ile aynı desen) `showAccount` state'iyle tam sayfa açılıyor. `DeviceList` header'ına "Hesabım" linki eklendi. Avatar dairesel gösteriliyor (yoksa kullanıcı adının ilk harfi ile renkli placeholder), "Fotoğrafı Değiştir" gizli `<input type=file>`'ı tetikliyor, seçilince hemen `multipart/form-data` ile yükleniyor. Tarayıcıda gerçek veriyle doğrulandı.

**iOS (`ProfileView.swift`):** `PhotosUI.PhotosPicker` (iOS 16 uyumlu, ek izin gerektirmiyor) eklendi, seçilen fotoğraf JPEG'e çevrilip `APIClient.uploadAvatar` (elle inşa edilmiş multipart body, projede daha önce dosya yükleme yoktu) ile gönderiliyor. `AsyncImage` ile avatar gösteriliyor, üyelik tarihi eklendi. `BUILD SUCCEEDED`.

**Android (`ProfileScreen.kt`):** `ProfileDialog` (AlertDialog) tamamen kaldırılıp `ProfileScreen` (Scaffold + TopAppBar + geri oku) olarak yeniden yazıldı — `DeviceListScreen`'de `selectedDevice` ile aynı tam-sayfa-değiştirme deseniyle açılıyor, artık gerçekten "ayrı bir sayfa". Sistem Foto Seçici'si (`ActivityResultContracts.PickVisualMedia`, API 33+ için ek izin gerekmiyor) kullanıldı; proje Coil gibi bir resim yükleme kütüphanesi kullanmadığı için avatar, mevcut OkHttp client'ıyla manuel `BitmapFactory.decodeByteArray` ile yükleniyor. `BUILD SUCCESSFUL`, emulator'de gerçek veriyle (yüklenen test fotoğrafı dahil) görsel olarak doğrulandı.

**Güncelleme — fotoğraf seçme akışı sonradan gerçekten tıklanarak doğrulandı:** iOS Simulator'a `xcrun simctl addmedia` ile test fotoğrafı eklenip PhotosPicker'dan gerçekten seçildi, avatar anında güncellendi, `https://binaryenerji.com/api/avatars/omer.jpg` çekilerek sunucuda kalıcı olduğu kanıtlandı. Web'de native dosya seçici otomatikleştirilemedi (tarayıcı `input[type=file].value`'yi script'le doldurmaya izin vermiyor) ama uygulamanın kendi upload kodu, sayfa içinde gerçek bir `File`/`FormData` nesnesiyle tetiklenip aynı kod yolu (React onChange → axios → state güncelleme) uçtan uca doğrulandı.

**Hesap sayfası genişletmesi (22 Ağustos 2026, aynı gün devamı):** Kullanıcı "tüm detaylar" + şifre değiştirme istedi.
- Backend: `GET /me`'ye `is_verified` eklendi. Yeni `POST /me/password` (mevcut şifre bcrypt doğrulamalı, yeni şifre min 6 karakter, `pwchange:{user}` anahtarıyla 5/saat rate-limitli — curl ile hem kısa-şifre-reddi hem yanlış-mevcut-şifre-reddi doğrulandı, gerçek hesap şifresi hiç değiştirilmedi).
- Web: "E-posta Doğrulandı", "Bağlı Cihaz Sayısı" (App() zaten sahip olduğu `devices.length`'ten) alanları + 3 alanlı şifre değiştirme formu (mevcut/yeni/tekrar, client-side eşleşme kontrolü). Tarayıcıda gerçek tıklamalarla doğrulandı (eşleşmeyen şifre uyarısı, yanlış mevcut şifre hatası).
- iOS: `ProfileView`'a aynı alanlar + `PasswordChangeView` eklendi, cihaz sayısı `api.fetchDevices().count` ile ayrıca çekiliyor.
- Android: `ProfileScreen`'e aynı alanlar + `PasswordChangeSection` eklendi; ekran artık kaydırılabilir + `imePadding()` (yeni eklenen alanlarla klavye taşması yaşanmasın diye, komut panelindeki düzeltmeyle aynı desen). Emulator'de gerçek tıklamalarla uçtan uca doğrulandı (eşleşmeyen şifre uyarısı UI'da göründü, yanlış-şifre denemesi backend'e gerçekten ulaşıp `403` döndüğü sunucu loglarından teyit edildi).


### 5.10 Reaktif Ceza Analizi / Raporlama (27 Ağustos 2026)

Sanayi abonesinin faturasında en çok canını yakan kalem reaktif ceza; cihaz zaten
bunun için gereken kümülatif sayaçları (`device_energy`: aktif Wh, endüktif/kapasitif
VArh) topluyordu, bu iş o sayaçları bir rapora çeviriyor.

**Kural ve neden ayarlanabilir:** Türkiye'de reaktif bedel aylık toplamlar üzerinden
işler — çekilen endüktif ve verilen kapasitif reaktif enerji, tüketilen aktif enerjinin
belirli bir yüzdesini aşamaz; aşılırsa yaygın uygulamada sadece aşan kısım değil o ayki
reaktifin **tamamı** faturalanır. Limitler abone grubuna (kurulu güç ≥50 kW / <50 kW),
birim fiyatlar ise tarifeye göre değişiyor ve dönemsel güncelleniyor. Bu yüzden hiçbiri
koda gömülmedi: `device_tariff` tablosunda cihaz bazında tutuluyor, müşteri kendi
faturasındaki değerleri girerek kalibre ediyor. Hesaplama yöntemi de ("tamamı" /
"yalnızca aşan kısım") aynı şekilde bir ayar.

**Backend (`api.py`):**
- Yeni tablo `device_tariff` (`ops/schema/2026-08-27-reactive-tariff.sql`).
- `GET`/`PUT /devices/{id}/tariff` — ayarlar; `GET` yanıtı iki hazır limit setini
  (`over_50kw` %20/%15, `under_50kw` %33/%20) `presets` olarak da döndürüyor.
- `GET /reports/reactive?device_id=&period=monthly|daily&count=&format=json|xlsx`.
- Farklar `GREATEST(delta, 0)` ile kırpılıyor: cihaz sayacı sıfırlandığında negatif
  fark sahte devasa tüketim olarak okunmasın diye.
- Dönemler `Europe/Istanbul`'a göre gruplanıyor — faturalama ayı yereldir, UTC değil.
- Aşımı kapatacak kompanzasyon gücü tahmini: aşan kVArh / yük altında geçen saat sayısı.

**Web / iOS / Android:** Üçünde de "Reaktif Ceza Analizi" bölümü — Aylık/Günlük
geçişi, özet kartları (cezalı dönem sayısı, en yüksek oranlar, toplam ceza, önerilen
kompanzasyon), limit çizgili oran grafiği ve dönem tablosu; tarife formu her platformda
var, Excel indirme yalnızca web'de.

**Doğrulama:** Gerçek cihaz verisiyle (anl21-8085d8, %155.4 endüktif) Android'de
1,85 ₺/kVArh kaydedildi → 842 kVArh × 1,85 = **1.557,66 ₺** çıktı; aynı değer
paylaşılan ayardan iOS'ta da göründü. Günlük kırılım (528,55 + 1.029,10 ₺) aylık
toplamla tutuyor.

**İki platform-özel tuzak:** Swift Charts'ta `LineMark`'a `series:` verilmezse aynı
dönemdeki endüktif ve kapasitif noktalar tek seri sayılıp dikey bir çizgiyle
birleştiriliyor. Android'de grafik Canvas'a elle çizildiği için x ekseni etiketleri de
elle ekleniyor; 30 günlük görünümde üst üste binmesin diye seyreltiliyor.


### 5.11 Veri Katmanı Ölçeklendirme — Sıkıştırma, Özet Tabloları, Saklama (27 Ağustos 2026)

Sistemi ticari hale getirme turunda ilk ölçülen şey depolamaydı ve tek gerçek
**satış engeli** buradan çıktı.

**Sorun (ölçüldü, tahmin edilmedi):** `measurements` cihaz başına saatte ~1.580
satır alıyor (satır ~337 byte) → **~12,8 MB/gün/cihaz ≈ 4,7 GB/yıl/cihaz**.
Hiçbir tabloda sıkıştırma yoktu, hiçbir saklama politikası yoktu, yani büyüme
sınırsızdı. Sunucuda (961 MB RAM, 1 çekirdek, 24 GB disk) 17 GB boş alan vardı:

| Cihaz sayısı | Diskin dolma süresi (önce) |
|---|---|
| 3 | ~14 ay |
| 10 | ~4 ay |
| 50 | ~1 ay |

Dolduğunda PostgreSQL yazmayı reddeder ve veri toplama **sessizce** ölür.

**Çözüm üç parçalı:**

1. **Sürekli toplamalar (continuous aggregate)** — ham satırları atılabilir kılan
   şey bunlar, çünkü geçmişi sonsuza kadar bunlar tutuyor:
   - `device_energy_hourly` — `/energy/hourly` ve reaktif ceza raporunu besliyor.
   - `measurements_15min` — 15 dakikalık kova **bilinçli**: güç aşım (sözleşme
     gücü) cezası Türkiye'de 15 dakikalık ortalama güç üzerinden hesaplanır, ve
     gerilim/THD min-max'ları ileride güç kalitesi raporunda kullanılacak.
2. **Sıkıştırma** (`segmentby = device_id`) + **saklama** (measurements 90 gün,
   device_energy 180 gün, diğerleri 365 gün). Bugün hiçbir şey silmiyor;
   büyümeyi sınırlı tutmak için şimdiden kuruldu.
3. **Bileşik `(device_id, time DESC)` indeksleri** — tüm sorgular `device_id`
   filtreliyordu ama indeks sadece `time` üzerindeydi, yani her sorgu tüm
   cihazların satırlarını tarıyordu.

**Yakalanan iki tuzak (ikisi de doğrulama sayesinde):**

- **Saatlik özet başta sadece `last()` tutuyordu — bu yanlıştı.** Cihaz sayacı ön
  panelden sıfırlanabiliyor; sıfırlanan saatte `last(H) < last(H-1)` olduğu için
  fark negatif çıkıp sıfıra kırpılıyor ve **o saatin tüm tüketimi kayboluyordu**
  (ölçülen örnekte 380 Wh'lik gerçek tüketim 0 görünüyordu). Özet artık saat
  başına `first/last/max` üçünü birden tutuyor ve sıfırlanan saati
  `(max − first) + last` ile yeniden kuruyor.
- **`/energy/hourly` sıralaması sessizce tersine dönüyordu.** Gerçek zamanlı
  sürekli toplama görünümü + pencere fonksiyonu bir aradayken planlayıcı dıştaki
  `ORDER BY bucket DESC`'i düşürüyor. Sorgu alt sorguya sarılarak çözüldü.

**Doğrulama:** Özet tablosunun ham veriyi birebir ürettiği kontrol edildi —
46 saat karşılaştırıldı, **0 fark**, toplamlar Wh'ye kadar aynı (541.976 Wh);
chunk'lar sıkıştırıldıktan sonra da aynı sonuç. Reaktif rapor migrasyon öncesi
ve sonrası aynı rakamı veriyor (1.599,75 TL).

**Sonuç:** Ölçülen sıkıştırma oranı **4,4 kat** — yavaş değişen telemetride
görülen 10-20 kattan düşük, çünkü bunlar gerçekten gürültülü float ölçümler.
Saklama politikasıyla birlikte **sınırsız 4,7 GB/yıl/cihaz büyüme, sınırlı
~340 MB/cihaz sabit duruma** dönüyor. Sorgu tarafında `/reports/reactive`
tampon okuması 101 → 8 sayfaya düştü (12 kat), ve bu fark 12 aylık gerçek
veride çok daha büyük olacak.


### 5.12 Fatura Analizi — Üç Zamanlı Tarife + Güç Aşımı + Reaktif (27 Ağustos 2026)

Reaktif ceza tek başına faturanın üçte birini açıklıyordu. Türkiye'de sanayi
aboneliğinin **üç** para kalemi var ve cihaz üçü için de gereken veriyi zaten
topluyor — bu iş üçünü tek bir aylık dökümde birleştiriyor.

**Kalemler:**

1. **Üç zamanlı tarife (T1/T2/T3)** — varsayılan T1 gündüz 06-17, T2 puant
   17-22, T3 gece 22-06. Puant genelde gecenin ~3 katı olduğu için bir
   fabrikanın elindeki **en büyük tasarruf kaldıracı** yükü puanttan geceye
   kaydırmak. Rapor puant oranını ve kaydırmanın **tasarruf tavanını** veriyor;
   arayüzde bunun ulaşılabilir bir hedef değil, üst sınır olduğu açıkça yazıyor.
2. **Güç aşım bedeli** — 15 dakikalık ortalama güç sözleşme gücünü aşarsa.
   `measurements_15min` özeti bir önceki çalışmada tam da bu yüzden 15 dakikalık
   kovayla kurulmuştu. Tepenin **ne zaman** oluştuğu da dönüyor; genelde
   müşteri için rapordaki en eyleme dönük tek rakam bu.
3. **Reaktif ceza** — mevcut analizden alınıyor, yeniden hesaplanmıyor. Böylece
   iki rapor arasında tutarsızlık oluşamaz.

**Ayarlanabilirlik:** Reaktifte olduğu gibi dilim saatleri, birim fiyatlar,
sözleşme gücü ve aşım bedeli koda gömülmüyor — tarifeye ve abone grubuna göre
değişip dönemsel güncellendiği için müşteri kendi faturasından kalibre ediyor.
Üç dilim fiyatı da 0 bırakılırsa tek fiyatlı `active_price`'a düşüyor; sözleşme
gücü boş bırakılırsa güç aşım analizi hiç yapılmıyor.

**Endpoint:** `GET /reports/bill?device_id=&months=&format=json|xlsx`.
Şema: `device_tariff` tablosuna `t1/t2/t3_start`, `t1/t2/t3_price`,
`contract_power_kw`, `demand_price` sütunları eklendi.

**Doğrulama (gerçek cihaz verisiyle, üç platformda):** Dilim kırılımı bilinen
toplama kWh'ye kadar tutuyor (458,7 + 51,1 + 32,2 = 542,0); kalemler beyan
edilen toplama eşit (1.787,89 + 735,75 + 1.599,75 = 4.123,39); reaktif kalemi
tek başına çalışan reaktif raporuyla birebir aynı. Uç durumlar: fiyat/sözleşme
gücü girilmemiş cihaz sadece tüketim kırılımı gösteriyor, ters sıralı dilim
saatleri ve pozitif olmayan sözleşme gücü reddediliyor.

**Ticari not:** Test cihazında bu üçlü şunu ortaya çıkardı — faturanın
**%57'si ceza** (reaktif %39, güç aşımı %18). Ürünün satış argümanı tam olarak
bu tablo.

---

**Doküman oluşturulma tarihi:** 13 Ağustos 2026
**Son güncelleme:** 19 Ağustos 2026 — ESP32 WiFi kurulumu WiFiManager'dan özel SoftAP+JSON API'ye geçirildi; Android uygulaması sıfırdan yazılıp gerçek bir telefonda (Xiaomi/MIUI) hem temel akış (giriş/cihaz listesi/dashboard) hem de **Tuya tarzı uygulama-içi WiFi kurulumu gerçek bir ESP32 ile uçtan uca doğrulandı** (bir mobil-veri/network-binding bug'ı bulunup düzeltildi: `ConnectivityManager` ile isteği açıkça WiFi ağına bağlayan `wifiBoundClient()`); iOS tarafında fiziksel cihaza kurulum denenirken ücretsiz Apple ID'nin Hotspot Configuration yetkisini desteklemediği ortaya çıktı, kullanıcı Apple Developer Program'a üye olmaya karar verdi (henüz olmadı) — iOS'ta WiFi kurulumunun telefon testi buna bağlı bekliyor. Ardından "profesyonellik" turu: her iki mobil uygulamaya da özel uygulama ikonu (logo.png'deki "1/0" işaretinden Pillow ile üretilen, marka lacivert zeminli, kırpılmamış vektör-kalitede glif) ve web'deki `index.css` renk paletiyle (--l3 #4A5FC1 aksan, --danger/--warn/#22c55e durum renkleri) birebir eşleşen tema eklendi (Android: Material You dinamik renklendirme bilinçli olarak kapatıldı, marka kimliği her cihazda sabit kalsın diye). Web tarafında "Cihazlarım" liste satırlarına ve "+ Cihaz Ekle" butonuna hover geçişleri, dalga formu kartlarının boş durumuna ("Veri bekleniyor…") animasyonlu nokta göstergesi eklendi. Kullanıcı ayrıca Android'e (mobil uygulamanın kod tabanı içinde, bu oturumda) Reaktif/Görünür/THD alanlarını ve web'deki saatlik enerji tablosunun birebir karşılığını (`HourlyEnergyDialog`) ekledi — iOS'ta bu özellikler henüz yok, parite için sıradaki adım olabilir.
