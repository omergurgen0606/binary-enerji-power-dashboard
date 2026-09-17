import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, BarChart, Bar, ComposedChart, ReferenceLine, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './index.css';

// Paket ortamdan bağımsız: aynı bundle hem üretimde hem staging'de çalışır ve
// her biri kendi API'sine gider. Sabit yazılsaydı staging bundle'ı üretim
// API'sini çağırırdı -- yani staging hiçbir şeyi izole etmezdi.
// Yerel geliştirmede (vite dev sunucusu) böyle bir /api yolu yok, üretime düşer.
// VITE_API_ORIGIN, yerel/staging bir API'ye karsi calismak icin kacis kapisi:
// tanimliysa her seyin onunde gelir. Tanimli degilse davranis eskisi gibi.
const API_ORIGIN = import.meta.env.VITE_API_ORIGIN
  || (import.meta.env.DEV ? 'https://binaryenerji.com' : window.location.origin);
const API_BASE = `${API_ORIGIN}/api`;
const WS_URL = `${API_ORIGIN.replace(/^http/, 'ws')}/ws/live`;

const PHASES = [
  { key: '1', color: 'var(--l1)', label: 'L1' },
  { key: '2', color: 'var(--l2)', label: 'L2' },
  { key: '3', color: 'var(--l3)', label: 'L3' },
];

const THEMES = [
  { id: 'klasik', name: 'Klasik', desc: 'Mevcut görünüm', swatches: ['#F4F6F9', '#C97A2B', '#1B7A72', '#4A5FC1'] },
  { id: 'olcu-cihazi', name: 'Ölçü Cihazı', desc: 'Koyu, teknik, enstrüman hissi', swatches: ['#0A0D10', '#E8A33D', '#4FD1C5', '#E8686B'] },
  { id: 'kontrol-panosu', name: 'Kontrol Panosu', desc: 'Endüstriyel pano/şalter hissi', swatches: ['#1C2024', '#FFB020', '#3ECF8E', '#5B8DEF'] },
  { id: 'marka-enerjisi', name: 'Marka Enerjisi', desc: 'Sıcak, davetkâr, markalı his', swatches: ['#F3F7F6', '#FF7A3D', '#0E4F4B', '#2DD4BF'] },
  { id: 'enerji-atlasi', name: 'Enerji Atlası', desc: 'Faz başına renkli, yuvarlak, canlı', swatches: ['#FBFAFF', '#FF6B4A', '#16C784', '#6C5CE7'] },
  { id: 'gundonumu', name: 'Gündönümü', desc: 'En sıcak ve cesur, gradyan vurgulu', swatches: ['#FFF7F0', '#FFB020', '#FF6B4A', '#E84393'] },
  { id: 'faz-portresi', name: 'Faz Portresi', desc: 'Fazör diyagramı, gerçek elektrik mühendisliği dili', swatches: ['#0A0E14', '#FFC857', '#2EC4B6', '#E85D75'] },
  { id: 'kadran-kumesi', name: 'Kadran Kümesi', desc: 'Analog ölçü aleti, pirinç ve fildişi', swatches: ['#1C1712', '#D9A35A', '#6B9080', '#A9433A'] },
];

const THEME_STORAGE_KEY = 'theme';
// Giris yapmadan davet baglantisina tiklayan kullanici, giris sonrasi davet
// sayfasina geri donsun diye token gecici olarak saklaniyor.
const PENDING_INVITE_KEY = 'pending_invite';

function ThemePicker({ theme, onChange }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
      {THEMES.map((t) => {
        const active = t.id === theme;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            style={{
              textAlign: 'left', cursor: 'pointer',
              background: 'var(--surface)',
              border: active ? '2px solid var(--accent)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: 12,
              display: 'flex', flexDirection: 'column', gap: 8,
            }}
          >
            <div style={{ display: 'flex', gap: 4 }}>
              {t.swatches.map((c, i) => (
                <span key={i} style={{ width: 16, height: 16, borderRadius: '50%', background: c, border: '1px solid rgba(0,0,0,0.08)' }} />
              ))}
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{t.name}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>{t.desc}</div>
            </div>
            {active && <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>✓ Seçili</span>}
          </button>
        );
      })}
    </div>
  );
}

function buildDecorativeWavePoints(cycleWidth, cycles, amplitude, baseline, phaseOffset = 0) {
  const pointsPerCycle = 24;
  const pts = [];
  for (let c = 0; c < cycles; c++) {
    for (let i = 0; i <= pointsPerCycle; i++) {
      const x = c * cycleWidth + (i / pointsPerCycle) * cycleWidth;
      const theta = (i / pointsPerCycle) * 2 * Math.PI + phaseOffset;
      const y = baseline + Math.sin(theta) * amplitude;
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
  }
  return pts.join(' ');
}

const WAVE_CYCLE_WIDTH = 140;
const WAVE_CYCLES = 6; // periyodik oldugu icin cift genislik dogal olarak sorunsuz donguleniyor
const WAVE_VIEW_WIDTH = WAVE_CYCLE_WIDTH * WAVE_CYCLES;

const inputStyle = {
  // fontSize 16: iOS Safari, 16px'ten küçük input'lara odaklanınca sayfayı otomatik yakınlaştırıyor
  padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)', fontSize: 16, width: '100%',
};

function AuthForm({ onLogin }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  function switchMode(next) {
    setMode(next);
    setError('');
    setNotice('');
    setPassword('');
    setConfirmPassword('');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setNotice('');

    if (mode === 'register') {
      if (!firstName.trim() || !lastName.trim()) return setError('Ad ve soyad zorunlu');
      if (username.trim().length < 3) return setError('Kullanıcı adı en az 3 karakter olmalı');
      if (!email.includes('@')) return setError('Geçerli bir e-posta girin');
      if (!phone.trim()) return setError('Telefon numarası zorunlu');
      if (password.length < 6) return setError('Şifre en az 6 karakter olmalı');
      if (password !== confirmPassword) return setError('Şifreler eşleşmiyor');
      if (!consent) return setError('Devam etmek için kişisel verilerin işlenmesini onaylamalısınız');
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        const res = await axios.post(`${API_BASE}/login`, { username, password });
        onLogin(res.data.token);
      } else {
        await axios.post(`${API_BASE}/register`, {
          first_name: firstName, last_name: lastName, username, email, phone, password,
        });
        setMode('login');
        setPassword('');
        setConfirmPassword('');
        setNotice('Kayıt başarılı! E-postanıza gönderilen doğrulama linkine tıklayıp giriş yapabilirsiniz.');
      }
    } catch (err) {
      if (err.response?.status === 409) setError('Bu kullanıcı adı veya e-posta zaten kayıtlı');
      else if (err.response?.status === 403) setError('Hesabınız henüz doğrulanmadı, e-postanızı kontrol edin');
      else if (err.response?.data?.detail) setError(err.response.data.detail);
      else setError(mode === 'login' ? 'Kullanıcı adı veya şifre hatalı' : 'Bir hata oluştu');
    } finally {
      setLoading(false);
    }
  }

  const wave1 = buildDecorativeWavePoints(WAVE_CYCLE_WIDTH, WAVE_CYCLES * 2, 22, 70, 0);
  const wave2 = buildDecorativeWavePoints(WAVE_CYCLE_WIDTH, WAVE_CYCLES * 2, 16, 78, 2.1);
  const wave3 = buildDecorativeWavePoints(WAVE_CYCLE_WIDTH, WAVE_CYCLES * 2, 27, 62, 4.2);

  return (
    <div className="auth-shell">
      <div className="auth-hero">
        <div className="auth-blob" style={{ width: 320, height: 320, top: -70, left: -70, background: 'var(--l1)' }} />
        <div className="auth-blob" style={{ width: 280, height: 280, bottom: -50, right: -50, background: 'var(--l3)', animationDelay: '4s' }} />
        <div className="auth-blob" style={{ width: 220, height: 220, top: '38%', left: '58%', background: 'var(--l2)', animationDelay: '8s' }} />

        <div style={{ position: 'relative', zIndex: 1, maxWidth: 420 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
            <img className="marka-logo" src="/logo.png" alt="" style={{ height: 30 }} />
            <span style={{ color: '#fff', fontSize: 13, fontWeight: 700, letterSpacing: 2 }}>BINARY ENERJİ</span>
          </div>
          <h1 style={{ color: '#fff', fontSize: 32, fontWeight: 700, lineHeight: 1.22, margin: '0 0 14px' }}>
            Faturanızın neresinden<br />kaybediyorsunuz?
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.68)', fontSize: 15, lineHeight: 1.55, margin: '0 0 26px', maxWidth: 370 }}>
            Reaktif ceza, güç aşımı ve puant tüketimi — sanayi elektrik faturasının
            en pahalı kalemleri. Analizör ölçer, panel kalem kalem gösterir ve
            ne yapmanız gerektiğini rakamla söyler.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            {[
              ['Reaktif ceza analizi', 'limiti ne kadar aştığınız, kaç kVAr kompanzasyon gerektiği'],
              ['Güç aşımı takibi', 'sözleşme gücünüzü hangi an, ne kadar aştığınız'],
              ['Puant / gündüz / gece kırılımı', 'pahalı saatlerdeki tüketiminiz ve kaydırma potansiyeli'],
              ['Aylık PDF rapor', 'e-posta ile gelen fatura dökümü ve öneriler'],
              ['Anlık alarm', 'e-posta ve telefon bildirimi'],
              ['Güç kalitesi (EN 50160)', 'gerilim, frekans ve harmonik değerlendirmesi'],
            ].map(([baslik, aciklama]) => (
              <div key={baslik} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%', background: 'var(--l2)',
                  flexShrink: 0, marginTop: 6,
                }} />
                <span style={{ fontSize: 13, lineHeight: 1.45 }}>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{baslik}</span>
                  <span style={{ color: 'rgba(255,255,255,0.6)' }}> — {aciklama}</span>
                </span>
              </div>
            ))}
          </div>
          <div style={{
            marginTop: 24, paddingTop: 18,
            borderTop: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.55)', fontSize: 12, lineHeight: 1.5, maxWidth: 370,
          }}>
            Gerilim, akım ve güç verileri saniyeler içinde; geçmiş tüketim ay ay,
            gün gün. ANL13 ve ANL21 analizörleriyle çalışır.
          </div>
        </div>

        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 140, overflow: 'hidden' }}>
          <svg
            className="auth-wave-track"
            viewBox={`0 0 ${WAVE_VIEW_WIDTH * 2} 140`}
            width="200%"
            height="140"
            preserveAspectRatio="none"
          >
            <polyline points={wave1} fill="none" stroke="var(--l1)" strokeWidth="2" opacity="0.45" />
            <polyline points={wave2} fill="none" stroke="var(--l2)" strokeWidth="2" opacity="0.5" />
            <polyline points={wave3} fill="none" stroke="var(--l3)" strokeWidth="2.5" opacity="0.6" />
          </svg>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px', background: 'var(--bg)' }}>
        <div style={{ width: '100%', maxWidth: 360 }}>
          <div className="auth-mobile-brand" style={{ alignItems: 'center', gap: 8, marginBottom: 24, justifyContent: 'center' }}>
            <img className="marka-logo" src="/logo.png" alt="Binary Enerji" style={{ height: 28 }} />
            <span style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1.5, fontWeight: 600 }}>BINARY ENERJİ</span>
          </div>
          <div style={{
            background: 'var(--surface)', borderRadius: "var(--radius-lg)", padding: 28,
            boxShadow: '0 20px 40px -12px rgba(11,31,58,0.18)',
          }}>
            <div style={{ display: 'flex', marginBottom: 20, borderRadius: "var(--radius-sm)", background: 'var(--bg)', padding: 4 }}>
              {[['login', 'Giriş Yap'], ['register', 'Üye Ol']].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => switchMode(key)}
                  style={{
                    flex: 1, padding: '8px 0', borderRadius: "var(--radius-xs)", border: 'none', cursor: 'pointer',
                    fontSize: 13, fontWeight: 600, transition: 'background 0.15s ease',
                    background: mode === key ? 'var(--surface)' : 'transparent',
                    color: mode === key ? 'var(--ink)' : 'var(--muted)',
                    boxShadow: mode === key ? '0 1px 2px rgba(11,31,58,0.08)' : 'none',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {mode === 'register' && (
                <div style={{ display: 'flex', gap: 12 }}>
                  <input
                    type="text"
                    placeholder="Ad"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    autoFocus
                    className="auth-input"
                    style={inputStyle}
                  />
                  <input
                    type="text"
                    placeholder="Soyad"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="auth-input"
                    style={inputStyle}
                  />
                </div>
              )}
              <input
                type="text"
                placeholder="Kullanıcı adı"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus={mode === 'login'}
                className="auth-input"
                style={inputStyle}
              />
              {mode === 'register' && (
                <>
                  <input
                    type="email"
                    placeholder="E-posta"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="auth-input"
                    style={inputStyle}
                  />
                  <input
                    type="tel"
                    placeholder="Telefon numarası"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="auth-input"
                    style={inputStyle}
                  />
                </>
              )}
              <input
                type="password"
                placeholder="Şifre"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="auth-input"
                style={inputStyle}
              />
              {mode === 'register' && (
                <>
                  <input
                    type="password"
                    placeholder="Şifre (tekrar)"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="auth-input"
                    style={inputStyle}
                  />
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                      style={{ marginTop: 2 }}
                    />
                    Ad, soyad, kullanıcı adı, e-posta ve telefon numaramın hesabımı oluşturmak ve doğrulamak amacıyla işlenmesini kabul ediyorum.
                  </label>
                </>
              )}
              {notice && <div style={{ color: 'var(--l2)', fontSize: 13 }}>{notice}</div>}
              {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
              <button type="submit" disabled={loading} className="auth-submit-btn" style={{
                padding: '11px 12px', borderRadius: "var(--radius-sm)", border: 'none',
                background: 'var(--l3)', color: '#fff', fontSize: 14, fontWeight: 600,
                cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.75 : 1,
              }}>
                {loading
                  ? (mode === 'login' ? 'Giriş yapılıyor...' : 'Hesap oluşturuluyor...')
                  : (mode === 'login' ? 'Giriş Yap' : 'Üye Ol')}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddDeviceForm({ token, compact, onAdded, onCancel }) {
  const [deviceId, setDeviceId] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [claimCode, setClaimCode] = useState('');
  const [facilityId, setFacilityId] = useState('');
  const [facilities, setFacilities] = useState(null); // null = henüz yüklenmedi
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token}` };
    axios.get(`${API_BASE}/organization`, { headers })
      .then((res) => {
        const { facilities: all, my_role, my_facility_ids } = res.data;
        // resolve_target_facility'deki "allowed" hesabıyla birebir aynı:
        // org_admin tüm tesisleri görür, diğer roller sadece atandığı tesisleri.
        const allowed = my_role === 'org_admin'
          ? all
          : all.filter((f) => my_facility_ids.includes(f.id));
        setFacilities(allowed);
        if (allowed.length === 1) setFacilityId(String(allowed[0].id));
      })
      .catch(() => setFacilities([])); // organizasyon yoksa (tek kullanıcı) sessizce boş geç
  }, [token]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (!deviceName.trim() || !deviceId.trim() || !claimCode.trim()) {
      return setError('Cihaz adı, cihaz ID\'si ve kurulum kodu zorunlu');
    }
    if (facilities && facilities.length > 1 && !facilityId) {
      return setError('Birden fazla tesisiniz var, cihazın ekleneceği tesisi seçin');
    }
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/devices`, {
        device_id: deviceId.trim(), name: deviceName.trim(), claim_code: claimCode.trim(),
        ...(facilityId ? { facility_id: Number(facilityId) } : {}),
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDeviceId('');
      setDeviceName('');
      setClaimCode('');
      onAdded();
    } catch (err) {
      if (err.response?.status === 409) setError('Bu cihaz ID\'si zaten kayıtlı');
      else setError(err.response?.data?.detail || 'Bir hata oluştu');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{
      display: 'flex', flexDirection: 'column', gap: 10,
      marginTop: compact ? 20 : 0, paddingTop: compact ? 20 : 0,
      borderTop: compact ? '1px solid var(--border)' : 'none',
    }}>
      <input
        type="text"
        placeholder="Cihaz adı (ör. ANL13)"
        value={deviceName}
        onChange={(e) => setDeviceName(e.target.value)}
        autoFocus
        style={inputStyle}
      />
      <input
        type="text"
        placeholder="Cihaz ID'si"
        value={deviceId}
        onChange={(e) => setDeviceId(e.target.value)}
        style={inputStyle}
      />
      <input
        type="text"
        placeholder="Kurulum kodu (cihaz etiketinde)"
        value={claimCode}
        onChange={(e) => setClaimCode(e.target.value)}
        style={inputStyle}
      />
      {facilities && facilities.length > 1 && (
        <select
          value={facilityId}
          onChange={(e) => setFacilityId(e.target.value)}
          style={inputStyle}
        >
          <option value="">Tesis seçin...</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
      )}
      {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" disabled={loading} style={{
          flex: 1, padding: '10px 12px', borderRadius: "var(--radius-sm)", border: 'none',
          background: 'var(--l3)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>
          {loading ? 'Ekleniyor...' : 'Cihaz Ekle'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} style={{
            padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)',
            background: 'none', color: 'var(--muted)', fontSize: 14, cursor: 'pointer',
          }}>
            Vazgeç
          </button>
        )}
      </div>
    </form>
  );
}

function formatJoinDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function Avatar({ url, username, size = 96 }) {
  const initial = (username || '?').charAt(0).toUpperCase();
  return url ? (
    <img
      src={`${API_BASE}${url}`}
      alt="Profil fotoğrafı"
      style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', border: '1px solid var(--border)' }}
    />
  ) : (
    <div style={{
      width: size, height: size, borderRadius: '50%', background: 'var(--l3)', color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.4, fontWeight: 700,
    }}>
      {initial}
    </div>
  );
}

// ---------- Push bildirimi ----------
// Tarayıcının abonelik anahtarları ham bayt; sunucuya base64url olarak
// gönderiliyor. VAPID açık anahtarı da tersine, base64url'den Uint8Array'e.
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((ch) => ch.charCodeAt(0)));
}

function arrayBufferToBase64Url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((b) => { binary += String.fromCharCode(b); });
  return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

const PUSH_SUPPORTED =
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'PushManager' in window &&
  'Notification' in window;

function PushToggle({ token }) {
  const [subscribed, setSubscribed] = useState(null); // null = kontrol ediliyor
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  useEffect(() => {
    let cancelled = false;
    if (!PUSH_SUPPORTED) { setSubscribed(false); return undefined; }
    navigator.serviceWorker.getRegistration('/sw.js')
      .then((reg) => (reg ? reg.pushManager.getSubscription() : null))
      .then((sub) => { if (!cancelled) setSubscribed(!!sub); })
      .catch(() => { if (!cancelled) setSubscribed(false); });
    return () => { cancelled = true; };
  }, []);

  async function enable() {
    setBusy(true); setError(''); setInfo('');
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setError(permission === 'denied'
          ? 'Bildirim izni reddedilmiş. Tarayıcı ayarlarından bu siteye izin vermeniz gerekiyor.'
          : 'Bildirim izni verilmedi.');
        return;
      }
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;

      const keyRes = await axios.get(`${API_BASE}/push/vapid-key`);
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyRes.data.public_key),
      });

      await axios.post(`${API_BASE}/push/subscribe`, {
        endpoint: sub.endpoint,
        p256dh: arrayBufferToBase64Url(sub.getKey('p256dh')),
        auth: arrayBufferToBase64Url(sub.getKey('auth')),
        user_agent: navigator.userAgent,
      }, { headers: { Authorization: `Bearer ${token}` } });

      setSubscribed(true);
      setInfo('Bildirimler açıldı. Alarm oluştuğunda bu tarayıcıya bildirim gelecek.');
    } catch (e) {
      setError(e.response?.data?.detail || 'Bildirimler açılamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true); setError(''); setInfo('');
    try {
      const reg = await navigator.serviceWorker.getRegistration('/sw.js');
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      if (sub) {
        await axios.post(`${API_BASE}/push/unsubscribe`, { endpoint: sub.endpoint },
          { headers: { Authorization: `Bearer ${token}` } });
        await sub.unsubscribe();
      }
      setSubscribed(false);
      setInfo('Bildirimler kapatıldı.');
    } catch {
      setError('Bildirimler kapatılamadı.');
    } finally {
      setBusy(false);
    }
  }

  // Sunucuyu hiç kullanmadan, doğrudan service worker'dan bildirim gösterir.
  // Bu görünüyorsa tarayıcı/işletim sistemi tarafı sağlamdır ve sorun teslimatta;
  // görünmüyorsa bildirimler işletim sistemi düzeyinde engellenmiştir.
  async function testLocal() {
    setBusy(true); setError(''); setInfo('');
    try {
      const reg = await navigator.serviceWorker.getRegistration('/sw.js');
      if (!reg) { setError('Service worker kayıtlı değil.'); return; }
      await reg.showNotification('Binary Enerji — yerel test', {
        body: 'Bu bildirim doğrudan tarayıcıdan gösterildi, sunucu kullanılmadı.',
        icon: '/logo.png',
        tag: 'yerel-test',
      });
      setInfo('Bildirim gösterildi. Ekranınızda görünmüyorsa sorun tarayıcı/işletim '
        + 'sistemi ayarlarında: macOS → Sistem Ayarları → Bildirimler → Chrome açık olmalı, '
        + 'Rahatsız Etmeyin kapalı olmalı.');
    } catch (e) {
      setError('Yerel bildirim gösterilemedi: ' + String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Anlık Bildirimler</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
        Alarm oluştuğunda bu tarayıcıya anında bildirim gönderilir — e-postayı beklemeden.
        Telefonda kullanmak için siteyi ana ekrana ekleyin.
      </div>

      {!PUSH_SUPPORTED ? (
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>
          Bu tarayıcı anlık bildirimleri desteklemiyor.
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={subscribed ? disable : enable}
            disabled={busy || subscribed === null}
            style={{
              padding: '8px 16px', borderRadius: 'var(--radius-xs)',
              border: subscribed ? '1px solid var(--border)' : 'none',
              background: subscribed ? 'var(--surface)' : 'var(--accent)',
              color: subscribed ? 'var(--muted)' : '#fff',
              fontSize: 12, fontWeight: 600,
              cursor: busy || subscribed === null ? 'default' : 'pointer',
            }}
          >
            {busy ? 'İşleniyor…'
              : subscribed === null ? 'Kontrol ediliyor…'
                : subscribed ? 'Bildirimleri kapat' : 'Bildirimleri aç'}
          </button>
          <span style={{ fontSize: 12, color: subscribed ? 'var(--accent)' : 'var(--muted)' }}>
            {subscribed === null ? '' : subscribed ? 'Bu tarayıcıda açık' : 'Kapalı'}
          </span>
          {subscribed && (
            <button type="button" onClick={testLocal} disabled={busy} style={{
              padding: '8px 14px', borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border)', background: 'var(--surface)',
              color: 'var(--muted)', fontSize: 12, fontWeight: 600,
              cursor: busy ? 'default' : 'pointer',
            }}>Test bildirimi göster</button>
          )}
        </div>
      )}

      {info && <div style={{ fontSize: 12, color: 'var(--accent)', marginTop: 8 }}>{info}</div>}
      {error && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>{error}</div>}
    </div>
  );
}

// ---------- KVKK: veri dışa aktarma ve hesap silme ----------
// KVKK madde 11, ilgili kişiye verilerinin akıbetini öğrenme ve silinmesini
// isteme hakkı veriyor. Bu bölüm o hakları e-posta yazışmasına gerek
// kalmadan kullanılabilir kılıyor.
function KvkkSection({ token, username }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [silmeAcik, setSilmeAcik] = useState(false);
  const [sifre, setSifre] = useState('');
  const [onay, setOnay] = useState('');

  async function disaAktar() {
    setBusy('export'); setError('');
    try {
      const res = await axios.get(`${API_BASE}/me/data-export`, {
        headers: { Authorization: `Bearer ${token}` }, responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${username}-kisisel-veriler.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('Veriler indirilemedi.');
    } finally {
      setBusy('');
    }
  }

  async function hesabiSil() {
    setBusy('delete'); setError('');
    try {
      await axios.post(`${API_BASE}/me/delete`, { password: sifre, confirm: onay },
        { headers: { Authorization: `Bearer ${token}` } });
      localStorage.removeItem('token');
      window.location.reload();
    } catch (e) {
      setError(e.response?.data?.detail || 'Hesap silinemedi.');
    } finally {
      setBusy('');
    }
  }

  const alan = {
    width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-xs)',
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--ink)', fontSize: 13, fontFamily: 'inherit', marginBottom: 8,
  };

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Kişisel Verileriniz</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
        KVKK kapsamında verilerinizin bir kopyasını indirebilir veya hesabınızı
        tamamen silebilirsiniz.
      </div>

      <button type="button" onClick={disaAktar} disabled={busy === 'export'} style={{
        padding: '8px 16px', borderRadius: 'var(--radius-xs)',
        border: '1px solid var(--border)', background: 'var(--surface)',
        color: 'var(--ink)', fontSize: 12, fontWeight: 600,
        cursor: busy ? 'default' : 'pointer',
      }}>
        {busy === 'export' ? 'Hazırlanıyor…' : 'Verilerimi indir'}
      </button>

      <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
        {!silmeAcik ? (
          <button type="button" onClick={() => setSilmeAcik(true)} style={{
            background: 'none', border: 'none', color: 'var(--danger)',
            fontSize: 12, fontWeight: 600, cursor: 'pointer', padding: 0,
            textDecoration: 'underline',
          }}>Hesabımı sil</button>
        ) : (
          <div>
            <div style={{
              fontSize: 12, color: 'var(--ink)', marginBottom: 12, padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 30%, var(--border))',
            }}>
              <b style={{ color: 'var(--danger)' }}>Bu işlem geri alınamaz.</b> Hesabınız ve
              kişisel verileriniz silinir. <b>Cihazlarınız ve ölçüm geçmişiniz silinmez</b> —
              organizasyona ait oldukları için sahiplikleri başka bir yöneticiye devredilir.
              Devredilecek başka yönetici yoksa silme yapılamaz.
            </div>
            <input style={alan} type="password" placeholder="Şifreniz"
                   value={sifre} onChange={(e) => setSifre(e.target.value)} />
            <input style={alan} placeholder={`Onaylamak için "${username}" yazın`}
                   value={onay} onChange={(e) => setOnay(e.target.value)} />
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button type="button" onClick={hesabiSil}
                      disabled={busy === 'delete' || onay !== username || !sifre}
                      style={{
                        padding: '8px 16px', borderRadius: 'var(--radius-xs)', border: 'none',
                        background: onay === username && sifre ? 'var(--danger)' : 'var(--border)',
                        color: '#fff', fontSize: 12, fontWeight: 600,
                        cursor: onay === username && sifre ? 'pointer' : 'default',
                      }}>
                {busy === 'delete' ? 'Siliniyor…' : 'Hesabımı kalıcı olarak sil'}
              </button>
              <button type="button" onClick={() => { setSilmeAcik(false); setSifre(''); setOnay(''); setError(''); }}
                      style={{
                        background: 'none', border: 'none', color: 'var(--muted)',
                        fontSize: 12, cursor: 'pointer', padding: 0,
                      }}>Vazgeç</button>
            </div>
          </div>
        )}
      </div>
      {error && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 10 }}>{error}</div>}
    </div>
  );
}

// ---------- Denetim kaydı ----------
function AuditLog({ token }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API_BASE}/organization/audit?limit=100`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => setRows(res.data))
      .catch((e) => setError(e.response?.status === 403
        ? 'Denetim kaydını yalnızca organizasyon yöneticisi görebilir.'
        : 'Denetim kaydı yüklenemedi.'));
  }, [token]);

  if (error) return <div style={{ fontSize: 12, color: 'var(--muted)' }}>{error}</div>;
  if (rows === null) return <div style={{ fontSize: 12, color: 'var(--muted)' }}>Yükleniyor…</div>;
  if (rows.length === 0) return <div style={{ fontSize: 12, color: 'var(--muted)' }}>Henüz kayıt yok.</div>;

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 560 }}>
        <thead>
          <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px' }}>Zaman</th>
            <th style={{ padding: '6px 8px' }}>Kim</th>
            <th style={{ padding: '6px 8px' }}>İşlem</th>
            <th style={{ padding: '6px 8px' }}>Nesne</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
              <td className="mono" style={{ padding: '6px 8px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                {new Date(r.at).toLocaleString('tr-TR', {
                  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </td>
              <td style={{ padding: '6px 8px', fontWeight: 500 }}>{r.actor || '—'}</td>
              <td style={{ padding: '6px 8px' }}>{r.label}</td>
              <td className="mono" style={{ padding: '6px 8px', color: 'var(--muted)' }}>
                {r.entity_id || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// E-posta tercihi anahtarı — aylık rapor ve alarm e-postası aynı desende,
// tek bileşen kullanılıyor ki metin ve davranış ayrışmasın.
function EmailPrefToggle({ token, path, enabled, title, description, onLabel, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function toggle() {
    setBusy(true); setError('');
    try {
      await axios.post(`${API_BASE}${path}`, { enabled: !enabled },
        { headers: { Authorization: `Bearer ${token}` } });
      onChanged();
    } catch {
      setError('Tercih kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>{description}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button type="button" onClick={toggle} disabled={busy} style={{
          padding: '8px 16px', borderRadius: 'var(--radius-xs)',
          border: enabled ? '1px solid var(--border)' : 'none',
          background: enabled ? 'var(--surface)' : 'var(--accent)',
          color: enabled ? 'var(--muted)' : '#fff',
          fontSize: 12, fontWeight: 600, cursor: busy ? 'default' : 'pointer',
        }}>
          {busy ? 'Kaydediliyor…' : enabled ? 'Kapat' : 'Aç'}
        </button>
        <span style={{ fontSize: 12, color: enabled ? 'var(--accent)' : 'var(--muted)' }}>
          {enabled ? onLabel : 'Kapalı'}
        </span>
        {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      </div>
    </div>
  );
}

function AccountPage({ token, onBack, onLogout, deviceCount, theme, onThemeChange, subscription }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef(null);

  function fetchProfile() {
    axios.get(`${API_BASE}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => setProfile(res.data)).catch(() => setError('Hesap bilgileri yüklenemedi.'));
  }

  useEffect(fetchProfile, [token]);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    setUploadError('');
    const form = new FormData();
    form.append('file', file);
    axios.post(`${API_BASE}/me/avatar`, form, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      setProfile((p) => ({ ...p, avatar_url: res.data.avatar_url }));
    }).catch((err) => {
      setUploadError(err.response?.data?.detail || 'Fotoğraf yüklenemedi.');
    }).finally(() => setUploading(false));
  }

  const fullName = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ') || '—';

  return (
    <div className="centered-page" style={{ maxWidth: 420, padding: '0 24px' }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
        cursor: 'pointer', padding: 0, marginBottom: 16,
      }}>
        ← Cihazlarım
      </button>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 24,
      }}>
        {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
        {!error && !profile && <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center' }}>Yükleniyor…</div>}
        {profile && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, marginBottom: 20 }}>
              <Avatar url={profile.avatar_url} username={profile.username} />
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                style={{
                  background: 'none', border: 'none', color: 'var(--l3)', fontSize: 12,
                  fontWeight: 600, cursor: uploading ? 'default' : 'pointer', padding: 0,
                }}
              >
                {uploading ? 'Yükleniyor…' : 'Fotoğrafı Değiştir'}
              </button>
              {uploadError && <div style={{ fontSize: 11, color: 'var(--danger)' }}>{uploadError}</div>}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <AccountField label="Ad Soyad" value={fullName} />
              <AccountField label="Kullanıcı Adı" value={profile.username} />
              <AccountField label="E-posta" value={profile.email || '—'} />
              <AccountField label="Telefon" value={profile.phone || '—'} />
              <AccountField label="Üyelik Tarihi" value={formatJoinDate(profile.created_at)} />
              <AccountField label="E-posta Doğrulandı" value={profile.is_verified ? 'Evet' : 'Hayır'} />
              <AccountField label="Bağlı Cihaz Sayısı" value={String(deviceCount ?? 0)} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <PushToggle token={token} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <SubscriptionCard subscription={subscription} token={token} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <EmailPrefToggle
                token={token} path="/me/alarm-email" enabled={profile.alarm_email}
                title="Alarm E-postaları"
                description="Erişiminiz olan cihazlarda alarm oluştuğunda e-posta gönderilir."
                onLabel="Açık" onChanged={fetchProfile}
              />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <EmailPrefToggle
                token={token} path="/me/monthly-report" enabled={profile.monthly_report}
                title="Aylık Enerji Raporu"
                description="Her ayın başında, bir önceki dönemin fatura dökümünü, tasarruf fırsatlarını ve alarm özetini içeren PDF raporu e-posta ile gönderilir."
                onLabel="Açık — her ayın 1'inde gönderilecek" onChanged={fetchProfile}
              />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <EmailChangeForm token={token} currentEmail={profile.email} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <PasswordChangeForm token={token} />
            </div>

            <div style={{ borderTop: '1px solid var(--border)', marginTop: 20, paddingTop: 20 }}>
              <KvkkSection token={token} username={profile.username} />
            </div>

            <button onClick={onLogout} className="logout-link" style={{
              marginTop: 24, background: 'none', border: 'none', color: 'var(--muted)',
              fontSize: 12, cursor: 'pointer', textDecoration: 'underline', padding: 0,
            }}>
              Çıkış Yap
            </button>
          </>
        )}
      </div>

      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 24, marginTop: 16,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>Görünüm</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>
          Panonun renk, yazı tipi ve şekil dilini değiştir.
        </div>
        <ThemePicker theme={theme} onChange={onThemeChange} />
      </div>
    </div>
  );
}

function EmailChangeForm({ token, currentEmail }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const res = await axios.post(`${API_BASE}/me/email`, { email, password }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessage({ ok: true, text: res.data.message });
      setEmail('');
      setPassword('');
    } catch (err) {
      setMessage({ ok: false, text: err.response?.data?.detail || 'E-posta güncellenemedi.' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>E-posta Adresi</div>
        <button type="button" onClick={() => setOpen((o) => !o)} style={{
          background: 'none', border: 'none', color: 'var(--accent)', fontSize: 12,
          cursor: 'pointer', textDecoration: 'underline', padding: 0,
        }}>
          {open ? 'Vazgeç' : (currentEmail ? 'Değiştir' : 'Ekle')}
        </button>
      </div>
      {!currentEmail && !open && (
        <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 6 }}>
          Hesabınızda e-posta adresi kayıtlı değil — alarm bildirimleri gönderilemez.
        </div>
      )}
      {open && (
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            Yeni adrese bir doğrulama bağlantısı gönderilir; siz onaylayana kadar hesabınızın
            e-postası değişmez.
          </span>
          <input
            type="email" placeholder="yeni@eposta.com" value={email} required
            onChange={(e) => setEmail(e.target.value)} style={inputStyle}
          />
          <input
            type="password" placeholder="Mevcut şifreniz" value={password} required
            onChange={(e) => setPassword(e.target.value)} style={inputStyle}
          />
          <button type="submit" disabled={loading} style={{
            padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
            background: 'var(--l3)', color: '#fff', fontSize: 13, fontWeight: 600,
            cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.6 : 1,
          }}>
            {loading ? 'Gönderiliyor…' : 'Doğrulama Bağlantısı Gönder'}
          </button>
        </form>
      )}
      {message && (
        <div style={{ fontSize: 11, marginTop: 8, color: message.ok ? 'var(--l2)' : 'var(--danger)' }}>
          {message.text}
        </div>
      )}
    </div>
  );
}

function PasswordChangeForm({ token }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null); // { ok: bool, text: string } | null

  const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;
  const canSubmit = currentPassword && newPassword.length >= 6 && newPassword === confirmPassword && !loading;

  function submit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setMessage(null);
    axios.post(`${API_BASE}/me/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      setMessage({ ok: true, text: 'Şifreniz güncellendi.' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    }).catch((err) => {
      setMessage({ ok: false, text: err.response?.data?.detail || 'Şifre güncellenemedi.' });
    }).finally(() => setLoading(false));
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>Şifre Değiştir</div>
      <input
        type="password"
        value={currentPassword}
        onChange={(e) => setCurrentPassword(e.target.value)}
        placeholder="Mevcut şifre"
        style={inputStyle}
      />
      <input
        type="password"
        value={newPassword}
        onChange={(e) => setNewPassword(e.target.value)}
        placeholder="Yeni şifre (en az 6 karakter)"
        style={inputStyle}
      />
      <input
        type="password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        placeholder="Yeni şifre (tekrar)"
        style={inputStyle}
      />
      {mismatch && <div style={{ fontSize: 11, color: 'var(--danger)' }}>Şifreler eşleşmiyor.</div>}
      {message && (
        <div style={{ fontSize: 11, color: message.ok ? 'var(--l2)' : 'var(--danger)' }}>{message.text}</div>
      )}
      <button
        type="submit"
        disabled={!canSubmit}
        style={{
          padding: '9px 12px', borderRadius: "var(--radius-sm)", border: 'none',
          background: 'var(--l3)', color: '#fff', fontSize: 13, fontWeight: 600,
          cursor: canSubmit ? 'pointer' : 'default', opacity: canSubmit ? 1 : 0.5,
        }}
      >
        {loading ? 'Güncelleniyor…' : 'Şifreyi Güncelle'}
      </button>
    </form>
  );
}

function AccountField({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

// ---------- Cihaz Filosu (yönetici görünümü) ----------
const FLEET_STATUS = {
  online: { label: 'Çevrimiçi', color: 'var(--l2)' },
  stale: { label: 'Veri yok', color: 'var(--warn)' },
  dead: { label: 'Sessiz', color: 'var(--danger)' },
  never: { label: 'Hiç bağlanmadı', color: 'var(--muted)' },
};

function formatSilence(minutes) {
  if (minutes == null) return '—';
  if (minutes < 60) return `${minutes} dk`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} sa`;
  return `${Math.floor(hours / 24)} gün`;
}

// ---------- Abonelik ----------
const SUB_LABELS = {
  trial: 'Deneme Sürümü',
  active: 'Aktif',
  expired: 'Süresi Doldu',
  cancelled: 'İptal Edildi',
  none: 'Abonelik Yok',
};

function formatSubDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('tr-TR', { day: '2-digit', month: 'long', year: 'numeric' });
}

// Panelin üstünde görünen şerit. Sadece dikkat gerektiren durumlarda çıkar:
// aktif ve süresi bol olan abonelikte hiçbir şey göstermiyoruz.
function SubscriptionBanner({ subscription }) {
  if (!subscription) return null;
  const { status, active, days_left: daysLeft, valid_until: validUntil, warn } = subscription;
  if (active && !warn) return null;

  const kritik = !active;
  const renk = kritik ? 'var(--danger)' : 'var(--warn)';
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 'var(--radius-sm)', marginBottom: 16,
      background: `color-mix(in srgb, ${renk} 10%, transparent)`,
      border: `1px solid color-mix(in srgb, ${renk} 40%, var(--border))`,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: renk, marginBottom: 4 }}>
        {kritik ? 'Aboneliğiniz sona erdi' : `Aboneliğiniz ${daysLeft} gün sonra sona eriyor`}
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink)' }}>
        {kritik
          ? 'Cihazlarınız veri göndermeye devam ediyor ve geçmişiniz korunuyor — yalnızca panel erişimi kapalı. Yeniden açmak için bizimle iletişime geçin.'
          : `Bitiş tarihi: ${formatSubDate(validUntil)}. Kesintisiz devam için yenilemeniz yeterli.`}
      </div>
      {status === 'trial' && active && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
          Deneme sürümünü kullanıyorsunuz.
        </div>
      )}
    </div>
  );
}

function SubscriptionCard({ subscription, token }) {
  if (!subscription) return null;
  const { status, active, valid_until: validUntil, device_count: deviceCount,
          device_limit: deviceLimit, device_price: devicePrice, period } = subscription;
  const renk = active ? 'var(--accent)' : 'var(--danger)';

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Abonelik</div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <ReactiveStat label="Durum" value={SUB_LABELS[status] || status} danger={!active} />
        <ReactiveStat label="Geçerlilik" value={formatSubDate(validUntil)} />
        <ReactiveStat
          label="Cihaz"
          value={deviceLimit ? `${deviceCount} / ${deviceLimit}` : String(deviceCount ?? '—')}
          hint={deviceLimit ? 'limit' : 'limitsiz'}
        />
        {devicePrice > 0 && (
          <ReactiveStat
            label="Ücret"
            value={money(deviceCount * devicePrice)}
            hint={`${money(devicePrice)} × ${deviceCount} cihaz · ${period === 'monthly' ? 'aylık' : 'yıllık'}`}
          />
        )}
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10, lineHeight: 1.5 }}>
        Abonelik sona erse bile cihazlarınız veri göndermeye devam eder ve geçmişiniz silinmez;
        yalnızca panel erişimi kapanır.
      </div>
      <div style={{ fontSize: 11, color: renk, marginTop: 6, fontWeight: 600 }}>
        {active ? 'Erişiminiz açık.' : 'Panel erişimi kapalı.'}
      </div>
      {token && <PaymentSection token={token} />}
    </div>
  );
}

const BILLING_FIELDS = [
  { key: 'contact_name', label: 'Ad Soyad / Yetkili', placeholder: 'Ömer Gürgen' },
  { key: 'identity_number', label: 'TC Kimlik No / Vergi No', placeholder: '10-11 haneli' },
  { key: 'email', label: 'E-posta', placeholder: 'fatura@sirket.com' },
  { key: 'phone', label: 'Telefon', placeholder: '5xx xxx xx xx' },
  { key: 'address', label: 'Adres', placeholder: 'Fatura adresi' },
  { key: 'city', label: 'Şehir', placeholder: 'İstanbul' },
];

// Iyzico'nun "buyer" nesnesi kimlik no, adres, telefon istiyor -- bunlar
// organizations tablosunda hiç yoktu. Bir kez girilip saklanıyor, her
// ödemede yeniden sorulmuyor.
function BillingProfileForm({ token, onSaved }) {
  const [form, setForm] = useState({ contact_name: '', identity_number: '', email: '',
                                     phone: '', address: '', city: '', country: 'Turkey' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${API_BASE}/subscription/billing`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setForm((f) => ({ ...f, ...res.data })))
      .catch(() => {}); // 404: henuz girilmemis, bos formla basliyoruz
  }, [token]);

  async function kaydet() {
    setSaving(true);
    setError(null);
    try {
      await axios.put(`${API_BASE}/subscription/billing`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Kaydedilemedi');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      background: 'var(--bg)', borderRadius: 'var(--radius-xs)', padding: 12,
      display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8,
    }}>
      <span style={{ fontSize: 12, fontWeight: 600 }}>Fatura Bilgileri</span>
      <span style={{ fontSize: 11, color: 'var(--muted)' }}>
        Ödeme sağlayıcımız Iyzico, ödemeyi işleyebilmek için bu bilgileri istiyor. Bir kez girip
        saklıyoruz, bir daha sorulmuyor.
      </span>
      {BILLING_FIELDS.map((f) => (
        <input
          key={f.key}
          type="text"
          value={form[f.key] || ''}
          placeholder={f.placeholder}
          onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
          style={{ ...inputStyle, fontSize: 13, padding: '7px 10px' }}
        />
      ))}
      {error && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{error}</span>}
      <button
        type="button"
        onClick={kaydet}
        disabled={saving}
        style={{
          padding: '8px 12px', borderRadius: 'var(--radius-xs)', border: 'none',
          background: 'var(--l3)', color: '#fff', fontSize: 12, fontWeight: 700,
          cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
        }}
      >
        {saving ? 'Kaydediliyor…' : 'Kaydet'}
      </button>
    </div>
  );
}

// Fatura bilgisi eksikse önce onu istiyor, varsa doğrudan tutarı gösterip
// Iyzico'nun ödeme sayfasına yönlendiriyor. Kart bilgisi hiçbir zaman bu
// sayfaya (ya da backend'imize) dokunmuyor -- Iyzico'nun kendi barındırdığı
// formunda kalıyor.
function PaymentSection({ token }) {
  const [price, setPrice] = useState(null);
  const [billingMissing, setBillingMissing] = useState(false);
  const [showBillingForm, setShowBillingForm] = useState(false);
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState(null);

  function fiyatiYukle() {
    axios.get(`${API_BASE}/subscription/price`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setPrice(res.data))
      .catch(() => setPrice(null));
    axios.get(`${API_BASE}/subscription/billing`, { headers: { Authorization: `Bearer ${token}` } })
      .then(() => setBillingMissing(false))
      .catch(() => setBillingMissing(true));
  }

  useEffect(fiyatiYukle, [token]);

  async function ode() {
    if (billingMissing) {
      setShowBillingForm(true);
      return;
    }
    setPaying(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/subscription/checkout`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      window.location.href = res.data.paymentPageUrl;
    } catch (err) {
      setError(err.response?.data?.detail || 'Ödeme başlatılamadı');
      setPaying(false);
    }
  }

  return (
    <div style={{ borderTop: '1px solid var(--border)', marginTop: 12, paddingTop: 12 }}>
      {price && (
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
          Ödenecek tutar: <strong style={{ color: 'var(--ink)' }}>{money(price.price)}</strong>
          {' '}({price.device_count} cihaz × {money(price.device_price)} × {price.months} ay)
        </div>
      )}
      {error && <div style={{ fontSize: 11, color: 'var(--danger)', marginBottom: 8 }}>{error}</div>}
      <button
        type="button"
        onClick={ode}
        disabled={paying}
        style={{
          padding: '9px 16px', borderRadius: 'var(--radius-xs)', border: 'none',
          background: 'var(--l2)', color: '#fff', fontSize: 13, fontWeight: 700,
          cursor: paying ? 'default' : 'pointer', opacity: paying ? 0.6 : 1,
        }}
      >
        {paying ? 'Yönlendiriliyor…' : 'Şimdi Öde'}
      </button>
      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6 }}>
        Ödeme Iyzico'nun güvenli sayfasında yapılır, kart bilgileriniz bize hiç ulaşmaz.
      </div>
      {showBillingForm && (
        <BillingProfileForm token={token} onSaved={() => { setShowBillingForm(false); fiyatiYukle(); }} />
      )}
    </div>
  );
}

// Yönetici paneli: fatura/havale ile çalışıldığı için abonelikler elle açılıyor.
function AdminSubscriptions({ token }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [duzenlenen, setDuzenlenen] = useState(null);

  function load() {
    axios.get(`${API_BASE}/admin/subscriptions`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setRows(res.data))
      .catch(() => setError('Abonelikler yüklenemedi.'));
  }
  useEffect(load, [token]);

  if (error) return <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>;
  if (rows === null) return <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>;

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 720 }}>
        <thead>
          <tr style={{ color: 'var(--muted)', textAlign: 'right' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Organizasyon</th>
            <th style={{ padding: '6px 8px' }}>Durum</th>
            <th style={{ padding: '6px 8px' }}>Geçerlilik</th>
            <th style={{ padding: '6px 8px' }}>Cihaz</th>
            <th style={{ padding: '6px 8px' }}>Birim</th>
            <th style={{ padding: '6px 8px' }}>Tutar</th>
            <th style={{ padding: '6px 8px' }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.organization_id} style={{ borderTop: '1px solid var(--border)' }}>
              <td style={{ padding: '7px 8px', fontWeight: 500 }}>{r.name}</td>
              <td style={{
                padding: '7px 8px', textAlign: 'right', fontWeight: 600,
                color: r.active ? 'var(--accent)' : 'var(--danger)',
              }}>{SUB_LABELS[r.status] || r.status}</td>
              <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>
                {formatSubDate(r.valid_until)}
              </td>
              <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>
                {r.device_limit ? `${r.device_count}/${r.device_limit}` : r.device_count}
              </td>
              <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>
                {r.device_price > 0 ? money(r.device_price) : '—'}
              </td>
              <td className="mono" style={{ padding: '7px 8px', textAlign: 'right', fontWeight: 600 }}>
                {r.amount > 0 ? money(r.amount) : '—'}
              </td>
              <td style={{ padding: '7px 8px', textAlign: 'right' }}>
                <button type="button" onClick={() => setDuzenlenen(r)} style={{
                  padding: '4px 10px', borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border)', background: 'var(--surface)',
                  color: 'var(--muted)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                }}>Düzenle</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {duzenlenen && (
        <SubscriptionEditor
          token={token} row={duzenlenen}
          onClose={() => setDuzenlenen(null)}
          onSaved={() => { setDuzenlenen(null); load(); }}
        />
      )}
    </div>
  );
}

function SubscriptionEditor({ token, row, onClose, onSaved }) {
  const [form, setForm] = useState({
    status: row.active ? row.status : 'active',
    months: 12,
    device_price: row.device_price || 0,
    period: row.period || 'yearly',
    device_limit: row.device_limit ?? '',
    note: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const field = {
    width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-xs)',
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--ink)', fontSize: 13, fontFamily: 'inherit',
  };
  const labelStyle = { fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 };

  async function save() {
    setSaving(true); setError('');
    try {
      await axios.put(`${API_BASE}/admin/subscriptions/${row.organization_id}`, {
        status: form.status,
        months: form.status === 'cancelled' ? null : Number(form.months),
        device_price: Number(form.device_price),
        period: form.period,
        device_limit: form.device_limit === '' ? null : Number(form.device_limit),
        note: form.note || null,
      }, { headers: { Authorization: `Bearer ${token}` } });
      onSaved();
    } catch (e) {
      setError(e.response?.data?.detail || 'Kaydedilemedi.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      marginTop: 16, padding: 16, borderRadius: 'var(--radius-sm)',
      border: '1px dashed var(--border)', background: 'var(--bg)',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{row.name}</div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
        {row.device_count} cihaz · Süre uzatma mevcut bitiş tarihinin üzerine eklenir,
        kalan süre yanmaz.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        <div>
          <label style={labelStyle}>Durum</label>
          <select style={field} value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="active">Aktif</option>
            <option value="trial">Deneme</option>
            <option value="cancelled">İptal</option>
          </select>
        </div>
        {form.status !== 'cancelled' && (
          <div>
            <label style={labelStyle}>Süre uzatma (ay)</label>
            <input style={field} type="number" min="1" max="120" value={form.months}
                   onChange={(e) => setForm({ ...form, months: e.target.value })} />
          </div>
        )}
        <div>
          <label style={labelStyle}>Cihaz başına ücret (₺)</label>
          <input style={field} type="number" step="0.01" value={form.device_price}
                 onChange={(e) => setForm({ ...form, device_price: e.target.value })} />
        </div>
        <div>
          <label style={labelStyle}>Dönem</label>
          <select style={field} value={form.period}
                  onChange={(e) => setForm({ ...form, period: e.target.value })}>
            <option value="yearly">Yıllık</option>
            <option value="monthly">Aylık</option>
          </select>
        </div>
        <div>
          <label style={labelStyle}>Cihaz limiti (boş = limitsiz)</label>
          <input style={field} type="number" min="0" value={form.device_limit}
                 onChange={(e) => setForm({ ...form, device_limit: e.target.value })} />
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label style={labelStyle}>Not (fatura no, mutabakat vb.)</label>
          <input style={field} value={form.note}
                 onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
        <button type="button" onClick={save} disabled={saving} style={{
          padding: '8px 16px', borderRadius: 'var(--radius-xs)', border: 'none',
          background: 'var(--accent)', color: '#fff', fontSize: 12, fontWeight: 600,
          cursor: saving ? 'default' : 'pointer',
        }}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button>
        <button type="button" onClick={onClose} style={{
          padding: '8px 16px', borderRadius: 'var(--radius-xs)',
          border: '1px solid var(--border)', background: 'var(--surface)',
          color: 'var(--muted)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
        }}>Vazgeç</button>
        {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      </div>
    </div>
  );
}

function FleetPage({ token, onBack }) {
  const [fleet, setFleet] = useState(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');

  function refresh() {
    axios.get(`${API_BASE}/admin/fleet`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setFleet(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Filo bilgisi alınamadı.'));
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [token]);

  const shown = fleet ? fleet.devices.filter((d) => filter === 'all' || d.status === filter) : [];
  const problemCount = fleet ? (fleet.counts.stale + fleet.counts.dead + fleet.counts.never) : 0;

  return (
    <div className="centered-page" style={{ maxWidth: 900, padding: '0 24px' }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
        cursor: 'pointer', padding: 0, marginBottom: 16,
      }}>
        ← Cihazlarım
      </button>
      <h1 style={{ margin: '0 0 4px', fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700 }}>Cihaz Filosu</h1>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>
        Sisteme kayıtlı tüm cihazlar, canlı durumları ve firmware dağılımı.
      </div>

      {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
      {!error && !fleet && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}

      {fleet && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
            <FleetStat label="Toplam" value={fleet.total} onClick={() => setFilter('all')} active={filter === 'all'} />
            {Object.entries(FLEET_STATUS).map(([key, def]) => (
              <FleetStat
                key={key} label={def.label} value={fleet.counts[key]} color={def.color}
                onClick={() => setFilter(key)} active={filter === key}
              />
            ))}
          </div>

          {problemCount > 0 && filter === 'all' && (
            <div style={{
              fontSize: 12, padding: '10px 12px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--warn)', color: 'var(--ink)', marginBottom: 16,
              background: 'color-mix(in srgb, var(--warn) 8%, var(--surface))',
            }}>
              {problemCount} cihaz veri göndermiyor — sahada arıza, elektrik kesintisi veya WiFi sorunu olabilir.
            </div>
          )}

          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 16, overflowX: 'auto',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 620 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {/* Durum ve son veri en kritik bilgiler, dar ekranda sağa taşıp
                      kesilmesinler diye bilinçli olarak sola alındı. */}
                  {['Cihaz', 'Durum', 'Son Veri', 'Firmware', 'Tip', 'Sahip'].map((h) => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 8px', color: 'var(--muted)',
                      fontWeight: 600, fontSize: 11,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((d) => {
                  const def = FLEET_STATUS[d.status];
                  return (
                    <tr key={d.device_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px' }}>
                        <div style={{ fontWeight: 500 }}>{d.name}</div>
                        <div className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{d.device_id}</div>
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: def.color, flexShrink: 0 }} />
                          <span style={{ fontSize: 12 }}>{def.label}</span>
                        </span>
                        {d.active_alarms > 0 && (
                          <span style={{
                            marginLeft: 8, fontSize: 10, fontWeight: 700, color: '#fff',
                            background: 'var(--danger)', padding: '2px 6px', borderRadius: 100,
                          }}>
                            {d.active_alarms} alarm
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '8px', color: 'var(--muted)' }}>
                        {d.last_seen ? `${formatSilence(d.minutes_silent)} önce` : '—'}
                      </td>
                      <td className="mono" style={{ padding: '8px' }}>{d.fw_version || '—'}</td>
                      <td style={{ padding: '8px', color: 'var(--muted)' }}>{d.device_type || '—'}</td>
                      <td style={{ padding: '8px', color: 'var(--muted)' }}>{d.owner}</td>
                    </tr>
                  );
                })}
                {shown.length === 0 && (
                  <tr><td colSpan={6} style={{ padding: 16, textAlign: 'center', color: 'var(--muted)' }}>
                    Bu durumda cihaz yok.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: 16,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Firmware Dağılımı</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {fleet.firmware_distribution.map((f) => (
                <div key={f.version} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }}>
                  <span className="mono" style={{ minWidth: 96 }}>{f.version}</span>
                  <div style={{ flex: 1, height: 8, background: 'var(--bg)', borderRadius: 100, overflow: 'hidden' }}>
                    <div style={{
                      width: `${(f.count / fleet.total) * 100}%`, height: '100%',
                      background: 'var(--l3)',
                    }} />
                  </div>
                  <span style={{ color: 'var(--muted)', minWidth: 56, textAlign: 'right' }}>
                    {f.count} cihaz
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: 20, marginTop: 24,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Abonelikler</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
              Abonelikler fatura/havale ile ödendiği için buradan elle açılır. Her değişiklik
              denetim kaydına yazılır.
            </div>
            <AdminSubscriptions token={token} />
          </div>
        </>
      )}
      <Footer />
    </div>
  );
}

function FleetStat({ label, value, color, onClick, active }) {
  return (
    <button type="button" onClick={onClick} style={{
      background: active ? 'var(--surface)' : 'transparent',
      border: `1px solid ${active ? (color || 'var(--accent)') : 'var(--border)'}`,
      borderRadius: 'var(--radius-sm)', padding: '10px 12px', cursor: 'pointer',
      textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 2,
    }}>
      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{label}</span>
      <span className="mono" style={{ fontSize: 20, fontWeight: 600, color: color || 'var(--ink)' }}>{value}</span>
    </button>
  );
}

// ---------- Davet kabul sayfası (/davet?token=...) ----------
function InvitePage({ token, onLogin }) {
  const inviteToken = new URLSearchParams(window.location.search).get('token');
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!inviteToken) {
      setError('Davet bağlantısı geçersiz.');
      return;
    }
    axios.get(`${API_BASE}/invites/${inviteToken}`)
      .then((res) => setInvite(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Davet bulunamadı.'));
  }, [inviteToken]);

  async function accept() {
    setBusy(true);
    setError('');
    try {
      const res = await axios.post(`${API_BASE}/organization/invites/accept`,
        { token: inviteToken }, { headers: { Authorization: `Bearer ${token}` } });
      setResult(res.data.message);
    } catch (err) {
      setError(err.response?.data?.detail || 'Davet kabul edilemedi.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="centered-page" style={{ maxWidth: 460, padding: '0 24px' }}>
      <img className="marka-logo" src="/logo.png" alt="Binary Enerji" style={{ height: 32, display: 'block', margin: '0 auto 8px' }} />
      <div style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1, marginBottom: 20, textAlign: 'center' }}>
        BINARY ENERJİ
      </div>

      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)', padding: 24,
      }}>
        {result ? (
          <>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{result}</div>
            <a href="/cihazlar" style={{ fontSize: 13, color: 'var(--accent)' }}>Cihazlarıma git →</a>
          </>
        ) : error ? (
          <>
            <div style={{ fontSize: 13, color: 'var(--danger)', lineHeight: 1.6 }}>{error}</div>
            <a href="/" style={{ fontSize: 13, color: 'var(--muted)', display: 'inline-block', marginTop: 12 }}>
              Ana sayfaya dön
            </a>
          </>
        ) : !invite ? (
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>
        ) : invite.accepted ? (
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu davet daha önce kullanılmış.</div>
        ) : invite.expired ? (
          <div style={{ fontSize: 13, color: 'var(--danger)' }}>
            Davetin süresi dolmuş. Yöneticinizden yeni bir davet isteyin.
          </div>
        ) : (
          <>
            <h1 style={{ margin: '0 0 6px', fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700 }}>
              {invite.organization_name}
            </h1>
            <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 18 }}>
              Bu organizasyona <b style={{ color: 'var(--ink)' }}>{ORG_ROLE_LABELS[invite.role] || invite.role}</b> olarak
              davet edildiniz.
              <br />
              <span style={{ fontSize: 12 }}>Davet adresi: {invite.email}</span>
            </div>

            {token ? (
              <button type="button" disabled={busy} onClick={accept} style={{
                width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
                background: 'var(--l3)', color: '#fff', fontSize: 14, fontWeight: 600,
                cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
              }}>
                {busy ? 'Kabul ediliyor…' : 'Daveti Kabul Et'}
              </button>
            ) : (
              <>
                <div style={{
                  fontSize: 12, color: 'var(--muted)', lineHeight: 1.6,
                  padding: 12, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
                  marginBottom: 12,
                }}>
                  Daveti kabul etmek için önce <b>{invite.email}</b> adresiyle kayıtlı hesabınıza giriş yapın.
                  Hesabınız yoksa o adresle üye olun.
                </div>
                {/* Davet bağlantısını saklıyoruz ki giriş sonrası kullanıcı elle
                    e-postaya dönmek zorunda kalmasın. */}
                <button
                  type="button"
                  onClick={() => {
                    sessionStorage.setItem(PENDING_INVITE_KEY, inviteToken);
                    window.location.href = '/';
                  }}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
                    background: 'var(--l3)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  Giriş Yap / Üye Ol
                </button>
              </>
            )}
          </>
        )}
      </div>
      <Footer />
    </div>
  );
}

// ---------- Organizasyon yönetimi ----------
const ORG_ROLE_LABELS = {
  org_admin: 'Organizasyon Yöneticisi',
  facility_manager: 'Tesis Sorumlusu',
  department_manager: 'Bölüm Sorumlusu',
};

const ORG_ROLE_HELP = {
  org_admin: 'Tüm organizasyona erişir, tesis/bölüm ve üye yönetimi yapabilir.',
  facility_manager: 'Sadece atandığı tesislerin cihazlarını görür ve yönetir.',
  department_manager: 'Sadece atandığı bölümlerin cihazlarını görür ve yönetir.',
};

function OrganizationPage({ token, onBack }) {
  const [org, setOrg] = useState(null);
  const [error, setError] = useState('');
  const [newFacility, setNewFacility] = useState('');
  const [newDepartment, setNewDepartment] = useState({});
  const [busy, setBusy] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  function refresh() {
    axios.get(`${API_BASE}/organization`, { headers })
      .then((res) => setOrg(res.data))
      .catch((err) => setError(err.response?.data?.detail || 'Organizasyon bilgisi alınamadı.'));
  }

  useEffect(refresh, [token]);

  function deviceCount(facilityId, departmentId) {
    if (!org) return 0;
    return org.device_counts
      .filter((c) => c.facility_id === facilityId && (departmentId === undefined || c.department_id === departmentId))
      .reduce((sum, c) => sum + c.count, 0);
  }

  async function call(fn, errText) {
    setBusy(true);
    setError('');
    try {
      await fn();
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || errText);
    } finally {
      setBusy(false);
    }
  }

  const isOrgAdmin = org?.my_role === 'org_admin';

  return (
    <div className="centered-page" style={{ maxWidth: 720, padding: '0 24px' }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
        cursor: 'pointer', padding: 0, marginBottom: 16,
      }}>
        ← Cihazlarım
      </button>

      {error && <div style={{ fontSize: 13, color: 'var(--danger)', marginBottom: 12 }}>{error}</div>}
      {!org && !error && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}

      {org && (
        <>
          <h1 style={{ margin: '0 0 4px', fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700 }}>
            {org.organization.name}
          </h1>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>
            Rolünüz: {ORG_ROLE_LABELS[org.my_role]}
          </div>

          {/* Tesisler ve bölümler */}
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: 20, marginBottom: 16,
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Tesisler ve Bölümler</div>

            {org.facilities.length === 0 && (
              <div style={{ fontSize: 13, color: 'var(--muted)' }}>Henüz tesis yok.</div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {org.facilities.map((f) => (
                <div key={f.id} style={{
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 12,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>{f.name}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>{deviceCount(f.id)} cihaz</span>
                    {isOrgAdmin && (
                      <button type="button" disabled={busy} onClick={() => call(
                        () => axios.delete(`${API_BASE}/organization/facilities/${f.id}`, { headers }),
                        'Tesis silinemedi.',
                      )} style={{
                        background: 'none', border: 'none', color: 'var(--danger)', fontSize: 11,
                        cursor: 'pointer', textDecoration: 'underline', padding: 0,
                      }}>Sil</button>
                    )}
                  </div>

                  {f.departments.length > 0 && (
                    <div style={{ marginTop: 10, paddingLeft: 12, borderLeft: '2px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {f.departments.map((dep) => (
                        <div key={dep.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                          <span style={{ flex: 1 }}>{dep.name}</span>
                          <span style={{ color: 'var(--muted)', fontSize: 11 }}>{deviceCount(f.id, dep.id)} cihaz</span>
                          {isOrgAdmin && (
                            <button type="button" disabled={busy} onClick={() => call(
                              () => axios.delete(`${API_BASE}/organization/departments/${dep.id}`, { headers }),
                              'Bölüm silinemedi.',
                            )} style={{
                              background: 'none', border: 'none', color: 'var(--danger)', fontSize: 11,
                              cursor: 'pointer', textDecoration: 'underline', padding: 0,
                            }}>Sil</button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {isOrgAdmin && (
                    <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                      <input
                        placeholder="Yeni bölüm adı"
                        value={newDepartment[f.id] || ''}
                        onChange={(e) => setNewDepartment({ ...newDepartment, [f.id]: e.target.value })}
                        style={{ ...inputStyle, fontSize: 12, padding: '6px 10px' }}
                      />
                      <button
                        type="button"
                        disabled={busy || !(newDepartment[f.id] || '').trim()}
                        onClick={() => call(async () => {
                          await axios.post(`${API_BASE}/organization/departments`,
                            { facility_id: f.id, name: newDepartment[f.id].trim() }, { headers });
                          setNewDepartment({ ...newDepartment, [f.id]: '' });
                        }, 'Bölüm eklenemedi.')}
                        style={{
                          padding: '6px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
                          background: 'var(--bg)', color: 'var(--ink)', fontSize: 12, fontWeight: 600,
                          cursor: 'pointer', whiteSpace: 'nowrap',
                        }}
                      >
                        Bölüm Ekle
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {isOrgAdmin && (
              <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
                <input
                  placeholder="Yeni tesis adı"
                  value={newFacility}
                  onChange={(e) => setNewFacility(e.target.value)}
                  style={{ ...inputStyle, fontSize: 13 }}
                />
                <button
                  type="button"
                  disabled={busy || !newFacility.trim()}
                  onClick={() => call(async () => {
                    await axios.post(`${API_BASE}/organization/facilities`, { name: newFacility.trim() }, { headers });
                    setNewFacility('');
                  }, 'Tesis eklenemedi.')}
                  style={{
                    padding: '8px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
                    background: 'var(--bg)', color: 'var(--ink)', fontSize: 13, fontWeight: 600,
                    cursor: 'pointer', whiteSpace: 'nowrap',
                  }}
                >
                  Tesis Ekle
                </button>
              </div>
            )}
          </div>

          {/* Üyeler */}
          {isOrgAdmin && (
            <div style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: 20,
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Üyeler</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
                Rol, üyenin hangi cihazları göreceğini belirler.
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {org.members.map((m) => (
                  <MemberRow
                    key={m.member_id} member={m} org={org} headers={headers}
                    busy={busy} onChanged={refresh} onError={setError}
                  />
                ))}
              </div>

              <InviteSection org={org} headers={headers} onError={setError} />
            </div>
          )}

          {isOrgAdmin && (
            <div style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: 20, marginTop: 24,
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Denetim Kaydı</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
                Organizasyonunuzda kim, ne zaman, neyi değiştirdi. Son 100 işlem.
              </div>
              <AuditLog token={token} />
            </div>
          )}
        </>
      )}
      <Footer />
    </div>
  );
}

function InviteSection({ org, headers, onError }) {
  const [invites, setInvites] = useState([]);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('facility_manager');
  const [facilityIds, setFacilityIds] = useState([]);
  const [departmentIds, setDepartmentIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState('');

  const allDepartments = org.facilities.flatMap((f) =>
    f.departments.map((d) => ({ ...d, facilityName: f.name })));

  function refresh() {
    axios.get(`${API_BASE}/organization/invites`, { headers })
      .then((res) => setInvites(res.data)).catch(() => {});
  }

  useEffect(refresh, []);

  async function send() {
    setBusy(true);
    setSent('');
    try {
      await axios.post(`${API_BASE}/organization/invites`, {
        email: email.trim(), role, facility_ids: facilityIds, department_ids: departmentIds,
      }, { headers });
      setSent(`Davet ${email.trim()} adresine gönderildi.`);
      setEmail('');
      setFacilityIds([]);
      setDepartmentIds([]);
      setOpen(false);
      refresh();
    } catch (err) {
      onError(err.response?.data?.detail || 'Davet gönderilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id) {
    try {
      await axios.delete(`${API_BASE}/organization/invites/${id}`, { headers });
      refresh();
    } catch (err) {
      onError(err.response?.data?.detail || 'Davet iptal edilemedi.');
    }
  }

  function toggle(list, setList, id) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  return (
    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
      {invites.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginBottom: 8 }}>
            Bekleyen Davetler
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {invites.map((inv) => (
              <div key={inv.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, flexWrap: 'wrap' }}>
                <span style={{ flex: 1, minWidth: 160 }}>{inv.email}</span>
                <span style={{ color: 'var(--muted)' }}>{ORG_ROLE_LABELS[inv.role]}</span>
                {inv.expired && <span style={{ color: 'var(--danger)', fontSize: 11 }}>süresi doldu</span>}
                <button type="button" onClick={() => cancel(inv.id)} style={{
                  background: 'none', border: 'none', color: 'var(--danger)', fontSize: 11,
                  cursor: 'pointer', textDecoration: 'underline', padding: 0,
                }}>İptal</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {sent && <div style={{ fontSize: 12, color: 'var(--l2)', marginBottom: 10 }}>{sent}</div>}

      {open ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <input
            type="email" placeholder="davet@eposta.com" value={email}
            onChange={(e) => setEmail(e.target.value)} style={{ ...inputStyle, fontSize: 13 }}
          />
          <select value={role} onChange={(e) => setRole(e.target.value)}
            style={{ ...inputStyle, fontSize: 13, padding: '8px 10px' }}>
            {Object.entries(ORG_ROLE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{ORG_ROLE_HELP[role]}</div>

          {role === 'facility_manager' && org.facilities.map((f) => (
            <label key={f.id} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
              <input type="checkbox" checked={facilityIds.includes(f.id)}
                onChange={() => toggle(facilityIds, setFacilityIds, f.id)} />
              {f.name}
            </label>
          ))}

          {role === 'department_manager' && (
            allDepartments.length === 0
              ? <div style={{ fontSize: 11, color: 'var(--muted)' }}>Önce bir tesise bölüm ekleyin.</div>
              : allDepartments.map((d) => (
                <label key={d.id} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="checkbox" checked={departmentIds.includes(d.id)}
                    onChange={() => toggle(departmentIds, setDepartmentIds, d.id)} />
                  {d.facilityName} · {d.name}
                </label>
              ))
          )}

          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" disabled={busy || !email.trim()} onClick={send} style={{
              padding: '8px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
              background: 'var(--bg)', color: 'var(--ink)', fontSize: 13, fontWeight: 600,
              cursor: (busy || !email.trim()) ? 'default' : 'pointer', opacity: (busy || !email.trim()) ? 0.5 : 1,
            }}>
              {busy ? 'Gönderiliyor…' : 'Davet Gönder'}
            </button>
            <button type="button" onClick={() => setOpen(false)} style={{
              padding: '8px 14px', border: 'none', background: 'none',
              color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
            }}>
              Vazgeç
            </button>
          </div>
        </div>
      ) : (
        <button type="button" onClick={() => setOpen(true)} style={{
          padding: '8px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          background: 'var(--bg)', color: 'var(--ink)', fontSize: 13, fontWeight: 600, cursor: 'pointer',
        }}>
          + Üye Davet Et
        </button>
      )}
    </div>
  );
}

function MemberRow({ member, org, headers, busy, onChanged, onError }) {
  const [editing, setEditing] = useState(false);
  const [role, setRole] = useState(member.role);
  const [facilityIds, setFacilityIds] = useState(member.facility_ids);
  const [departmentIds, setDepartmentIds] = useState(member.department_ids);
  const [saving, setSaving] = useState(false);

  const allDepartments = org.facilities.flatMap((f) =>
    f.departments.map((d) => ({ ...d, facilityName: f.name })));

  const scopeSummary = member.role === 'org_admin'
    ? 'Tüm organizasyon'
    : member.role === 'facility_manager'
      ? (member.facility_ids.length
        ? org.facilities.filter((f) => member.facility_ids.includes(f.id)).map((f) => f.name).join(', ')
        : 'Henüz tesis atanmadı')
      : (member.department_ids.length
        ? allDepartments.filter((d) => member.department_ids.includes(d.id)).map((d) => d.name).join(', ')
        : 'Henüz bölüm atanmadı');

  async function save() {
    setSaving(true);
    try {
      await axios.patch(`${API_BASE}/organization/members/${member.member_id}`, {
        role, facility_ids: facilityIds, department_ids: departmentIds,
      }, { headers });
      setEditing(false);
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || 'Üye güncellenemedi.');
    } finally {
      setSaving(false);
    }
  }

  function toggle(list, setList, id) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{member.full_name || member.username}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{member.email || member.username}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12 }}>{ORG_ROLE_LABELS[member.role]}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{scopeSummary}</div>
        </div>
        <button type="button" onClick={() => setEditing((e) => !e)} style={{
          background: 'none', border: 'none', color: 'var(--accent)', fontSize: 11,
          cursor: 'pointer', textDecoration: 'underline', padding: 0,
        }}>
          {editing ? 'Vazgeç' : 'Düzenle'}
        </button>
      </div>

      {editing && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <select value={role} onChange={(e) => setRole(e.target.value)}
            style={{ ...inputStyle, fontSize: 13, padding: '8px 10px' }}>
            {Object.entries(ORG_ROLE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{ORG_ROLE_HELP[role]}</div>

          {role === 'facility_manager' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {org.facilities.map((f) => (
                <label key={f.id} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="checkbox" checked={facilityIds.includes(f.id)}
                    onChange={() => toggle(facilityIds, setFacilityIds, f.id)} />
                  {f.name}
                </label>
              ))}
            </div>
          )}

          {role === 'department_manager' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {allDepartments.length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>Önce bir tesise bölüm ekleyin.</div>
              )}
              {allDepartments.map((d) => (
                <label key={d.id} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="checkbox" checked={departmentIds.includes(d.id)}
                    onChange={() => toggle(departmentIds, setDepartmentIds, d.id)} />
                  {d.facilityName} · {d.name}
                </label>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" disabled={saving || busy} onClick={save} style={{
              padding: '6px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
              background: 'var(--bg)', color: 'var(--ink)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              {saving ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
            <button type="button" disabled={saving} onClick={async () => {
              if (!window.confirm(`${member.username} organizasyondan çıkarılsın mı?`)) return;
              try {
                await axios.delete(`${API_BASE}/organization/members/${member.member_id}`, { headers });
                onChanged();
              } catch (err) {
                onError(err.response?.data?.detail || 'Üye çıkarılamadı.');
              }
            }} style={{
              padding: '6px 14px', borderRadius: 'var(--radius-xs)', border: 'none',
              background: 'none', color: 'var(--danger)', fontSize: 12, cursor: 'pointer',
            }}>
              Organizasyondan Çıkar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Cihazları Tesis → Bölüm kırılımıyla gösterir. Tek tesisli ve bölümsüz
// (küçük müşteri) durumda hiyerarşi hiç gösterilmez, düz liste olarak kalır —
// böylece tek cihazlı kullanıcı bu yapıyı hiç görmez.
function DeviceRow({ device, onSelect }) {
  return (
    <button
      onClick={() => onSelect(device)}
      className="device-row"
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
        background: 'var(--bg)', cursor: 'pointer', fontSize: 14, fontWeight: 600,
        color: 'var(--ink)', textAlign: 'left', width: '100%',
      }}
    >
      {device.name}
      <span style={{ color: 'var(--muted)', fontWeight: 400 }}>İzle →</span>
    </button>
  );
}

function DeviceGroups({ devices, onSelect }) {
  const facilities = [...new Set(devices.map((d) => d.facility_name).filter(Boolean))];
  const hasDepartments = devices.some((d) => d.department_name);
  const flat = facilities.length <= 1 && !hasDepartments;

  if (flat) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {devices.map((d) => <DeviceRow key={d.device_id} device={d} onSelect={onSelect} />)}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {facilities.map((facility) => {
        const inFacility = devices.filter((d) => d.facility_name === facility);
        const departments = [...new Set(inFacility.map((d) => d.department_name).filter(Boolean))];
        const unassigned = inFacility.filter((d) => !d.department_name);
        return (
          <div key={facility}>
            <div style={{
              fontSize: 11, fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase',
              color: 'var(--muted)', marginBottom: 8,
            }}>
              {facility}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {unassigned.map((d) => <DeviceRow key={d.device_id} device={d} onSelect={onSelect} />)}
              {departments.map((dep) => (
                <div key={dep} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)', paddingLeft: 2 }}>{dep}</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 10, borderLeft: '2px solid var(--border)' }}>
                    {inFacility.filter((d) => d.department_name === dep).map((d) => (
                      <DeviceRow key={d.device_id} device={d} onSelect={onSelect} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DeviceList({ devices, onSelect, onLogout, onOpenAccount, onOpenFleet, onOpenOrganization, isAdmin, token, onDeviceAdded, subscription, onBackToHub }) {
  const [showAddForm, setShowAddForm] = useState(devices.length === 0);

  return (
    <div className="centered-page" style={{ maxWidth: 420, padding: '0 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: -8 }}>
        <button onClick={onBackToHub} style={{
          background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
          cursor: 'pointer', padding: 4,
        }}>← Binary Enerji</button>
        <div style={{ display: 'flex', gap: 12 }}>
          {isAdmin && (
            <button onClick={onOpenFleet} style={{
              background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
              cursor: 'pointer', padding: 4, textDecoration: 'underline',
            }}>
              Cihaz Filosu
            </button>
          )}
          <button onClick={onOpenOrganization} style={{
            background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
            cursor: 'pointer', padding: 4, textDecoration: 'underline',
          }}>
            Organizasyon
          </button>
          <button onClick={onOpenAccount} style={{
            background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
            cursor: 'pointer', padding: 4, textDecoration: 'underline',
          }}>
            Hesabım
          </button>
        </div>
      </div>
      <img className="marka-logo" src="/logo.png" alt="Binary Enerji" style={{ height: 32, display: 'block', margin: '0 auto 8px' }} />
      <div style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1, marginBottom: 4, textAlign: 'center' }}>BINARY ENERJİ</div>
      <h1 style={{ margin: '0 0 24px', fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, textAlign: 'center' }}>Cihazlarım</h1>
      <SubscriptionBanner subscription={subscription} />
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 24,
      }}>
        {devices.length === 0 && !showAddForm && (
          <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.5, textAlign: 'center', marginBottom: 16 }}>
            Hesabınıza bağlı bir cihaz bulunmuyor.
          </div>
        )}
        {devices.length > 0 && <DeviceGroups devices={devices} onSelect={onSelect} />}
        {showAddForm ? (
          <AddDeviceForm
            token={token}
            compact={devices.length > 0}
            onAdded={() => { setShowAddForm(false); onDeviceAdded(); }}
            onCancel={devices.length > 0 ? () => setShowAddForm(false) : null}
          />
        ) : (
          <button onClick={() => setShowAddForm(true)} className="add-device-btn" style={{
            marginTop: devices.length > 0 ? 12 : 0, width: '100%', padding: '10px 12px', borderRadius: "var(--radius-sm)",
            border: '1px dashed var(--border)', background: 'none', color: 'var(--muted)',
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>
            + Cihaz Ekle
          </button>
        )}
        <button onClick={onLogout} className="logout-link" style={{
          marginTop: 20, background: 'none', border: 'none', color: 'var(--muted)',
          fontSize: 12, cursor: 'pointer', textDecoration: 'underline', padding: 0,
        }}>
          Çıkış Yap
        </button>
      </div>
    </div>
  );
}

function Metric({ label, value, digits, unit }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>{label}</div>
      <div className="mono" style={{ fontSize: 15 }}>{value != null ? value.toFixed(digits) : '—'} {unit}</div>
    </div>
  );
}

function PhaseCard({ label, color, v, i, p, q, s, pf, thd, thvd, pulse }) {
  return (
    <div style={{
      background: `color-mix(in srgb, ${color} var(--card-tint), var(--surface))`,
      border: '1px solid var(--border)',
      borderTop: '3px solid var(--card-accent)',
      borderRadius: "var(--radius-md)",
      boxShadow: 'var(--shadow-card)',
      padding: '20px 24px',
      flex: 1,
      minWidth: 200,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{
          width: 10, height: 10, borderRadius: '50%', background: color,
          boxShadow: pulse ? `0 0 0 4px ${color}33` : 'none',
          transition: 'box-shadow 0.3s ease',
        }} />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 14, letterSpacing: 0.5 }}>{label}</span>
      </div>
      <div className="mono value-readout" style={{ fontSize: 28, fontWeight: 500, color: `color-mix(in srgb, ${color} var(--value-tint, 0%), var(--ink))` }}>
        {v != null ? v.toFixed(1) : '—'} <span style={{ fontSize: 14, color: 'var(--muted)', textShadow: 'none' }}>V</span>
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 10, flexWrap: 'wrap', rowGap: 10 }}>
        <Metric label="AKIM" value={i} digits={3} unit="A" />
        <Metric label="GÜÇ" value={p} digits={0} unit="W" />
        <Metric label="REAKTİF" value={q} digits={0} unit="VAR" />
        <Metric label="GÖRÜNÜR" value={s} digits={0} unit="VA" />
        <Metric label="PF" value={pf} digits={2} unit="" />
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 12 }}>
        {thvd != null ? (
          <>THD (Akım): {thd != null ? thd.toFixed(2) : '—'}% · THD (Gerilim): {thvd.toFixed(2)}%</>
        ) : (
          <>THD: {thd != null ? thd.toFixed(2) : '—'}%</>
        )}
      </div>
    </div>
  );
}

function formatDuration(ms) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}sa ${m}dk ${s}sn`;
  if (m > 0) return `${m}dk ${s}sn`;
  return `${s}sn`;
}

function formatKwh(wh) {
  if (wh == null) return '—';
  return (wh / 1000).toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function EnergyCard({ title, data, suffix, onClick }) {
  const active = data?.[`active_wh_${suffix}`];
  const inductive = data?.[`inductive_varh_${suffix}`];
  const capacitive = data?.[`capacitive_varh_${suffix}`];
  return (
    <div
      onClick={onClick}
      className={onClick ? 'dash-card' : undefined}
      style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderTop: '3px solid var(--card-accent)',
        borderRadius: "var(--radius-md)", boxShadow: 'var(--shadow-card)',
        padding: '20px 24px', flex: 1, minWidth: 220,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 14 }}>{title}</div>
        {onClick && <span style={{ fontSize: 11, color: 'var(--muted)' }}>Saatlik detay →</span>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Aktif Enerji</span>
          <span className="mono" style={{ fontSize: 14, fontWeight: 500 }}>{formatKwh(active)} kWh</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Endüktif Reaktif</span>
          <span className="mono" style={{ fontSize: 14, fontWeight: 500 }}>{formatKwh(inductive)} kVArh</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Kapasitif Reaktif</span>
          <span className="mono" style={{ fontSize: 14, fontWeight: 500 }}>{formatKwh(capacitive)} kVArh</span>
        </div>
      </div>
    </div>
  );
}

const ENERGY_METRICS = [
  { key: 'active', label: 'Aktif' },
  { key: 'inductive', label: 'Endüktif' },
  { key: 'capacitive', label: 'Kapasitif' },
];

function formatKwhDelta(wh) {
  if (wh == null) return '—';
  return (wh / 1000).toLocaleString('tr-TR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function HourlyEnergyModal({ token, device, title, suffix, onClose }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    axios.get(`${API_BASE}/energy/hourly?device_id=${device.device_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      setRows(res.data);
    }).catch(() => {
      setError('Saatlik veriler yüklenemedi.');
    });
  }, [device.device_id]);

  async function downloadXlsx() {
    setDownloading(true);
    try {
      const res = await axios.get(`${API_BASE}/energy/hourly?device_id=${device.device_id}&format=xlsx`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${device.device_id}-saatlik-enerji.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Excel dosyası indirilemedi.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(11,31,58,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 100,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--surface)', borderRadius: "var(--radius-md)", padding: 24,
          maxWidth: 760, width: '100%', maxHeight: '80vh', display: 'flex', flexDirection: 'column',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{title} — Saatlik Enerji</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {rows && rows.length > 0 && (
              <button
                onClick={downloadXlsx}
                disabled={downloading}
                className="add-device-btn"
                style={{
                  background: 'none', border: '1px solid var(--border)', borderRadius: "var(--radius-xs)",
                  color: 'var(--muted)', fontSize: 12, fontWeight: 600, cursor: downloading ? 'default' : 'pointer',
                  padding: '6px 10px',
                }}
              >
                {downloading ? 'İndiriliyor…' : 'Excel indir'}
              </button>
            )}
            <button onClick={onClose} style={{
              background: 'none', border: 'none', color: 'var(--muted)', fontSize: 20, cursor: 'pointer', padding: 0, lineHeight: 1,
            }}>×</button>
          </div>
        </div>
        <div style={{ overflow: 'auto', flex: 1 }}>
          {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
          {!error && rows === null && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor...</div>}
          {!error && rows !== null && rows.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>Henüz veri yok.</div>
          )}
          {!error && rows !== null && rows.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 640 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th rowSpan={2} style={{ textAlign: 'left', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11, verticalAlign: 'bottom' }}>Tarih</th>
                  <th rowSpan={2} style={{ textAlign: 'left', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11, verticalAlign: 'bottom' }}>Saat</th>
                  {ENERGY_METRICS.map((m) => (
                    <th key={m.key} colSpan={2} style={{ textAlign: 'center', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11, borderLeft: '1px solid var(--border)' }}>{m.label}</th>
                  ))}
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {ENERGY_METRICS.map((m) => (
                    <Fragment key={m.key}>
                      <th style={{ textAlign: 'right', padding: '4px', color: 'var(--muted)', fontWeight: 600, fontSize: 10, borderLeft: '1px solid var(--border)' }}>Artış</th>
                      <th style={{ textAlign: 'right', padding: '4px', color: 'var(--muted)', fontWeight: 600, fontSize: 10 }}>Endeks</th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const t = new Date(row.reading_time);
                  return (
                    <tr key={row.reading_time} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="mono" style={{ padding: '6px 4px' }}>{t.toLocaleDateString('tr-TR')}</td>
                      <td className="mono" style={{ padding: '6px 4px' }}>{t.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</td>
                      {ENERGY_METRICS.map((m) => (
                        <Fragment key={m.key}>
                          <td className="mono" style={{ padding: '6px 4px', textAlign: 'right', fontWeight: 500, borderLeft: '1px solid var(--border)' }}>
                            {formatKwhDelta(row[`delta_${m.key}_${suffix}`])}
                          </td>
                          <td className="mono" style={{ padding: '6px 4px', textAlign: 'right', color: 'var(--muted)' }}>
                            {formatKwh(row[`${m.key}_${suffix}`])}
                          </td>
                        </Fragment>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function buildWaveform(vRms, iRms, cosPhi, q) {
  if (vRms == null || iRms == null) return [];
  const vPeak = vRms * Math.sqrt(2);
  const iPeak = iRms * Math.sqrt(2);
  const clamped = cosPhi == null ? 1 : Math.min(1, Math.max(-1, cosPhi));
  const phi = Math.acos(clamped);
  // Endüktif yükte akım gerilimin gerisinde kalır, kapasitifte önüne geçer
  const signedPhi = (q ?? 0) < 0 ? -phi : phi;
  const steps = 120;
  const points = [];
  for (let k = 0; k <= steps; k++) {
    const theta = (k / steps) * 4 * Math.PI; // 2 tam periyot
    points.push({
      deg: Math.round((theta * 180) / Math.PI),
      v: vPeak * Math.sin(theta),
      i: iPeak * Math.sin(theta - signedPhi),
    });
  }
  return points;
}

function WaveformCard({ label, color, v, i, cosPhi, q }) {
  const data = buildWaveform(v, i, cosPhi, q);
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: "var(--radius-md)", boxShadow: 'var(--shadow-card)',
      padding: '16px 20px', flex: 1, minWidth: 280, height: 260,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 13 }}>{label}</span>
      </div>
      {data.length === 0 ? (
        <div className="waveform-empty">
          <div className="waveform-empty-dots">
            <span /><span /><span />
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Veri bekleniyor…</div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="88%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="deg"
              tick={{ fontSize: 10, fill: 'var(--muted)' }}
              tickFormatter={(d) => `${d}°`}
              ticks={[0, 180, 360, 540, 720]}
            />
            <YAxis yAxisId="v" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={36} />
            <YAxis yAxisId="i" orientation="right" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={36} />
            <Tooltip
              labelFormatter={(d) => `${d}°`}
              formatter={(val, name) => [val.toFixed(name === 'v' ? 1 : 3), name === 'v' ? 'V' : 'A']}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} formatter={(value) => (value === 'v' ? 'Gerilim' : 'Akım')} />
            <Line yAxisId="v" type="monotone" dataKey="v" stroke={color} dot={false} strokeWidth={2} name="v" />
            <Line yAxisId="i" type="monotone" dataKey="i" stroke={color} strokeDasharray="5 3" dot={false} strokeWidth={2} name="i" />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function SectionCard({ title, right, children }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderTop: '3px solid var(--card-accent)',
      borderRadius: "var(--radius-md)", boxShadow: 'var(--shadow-card)',
      padding: 20, marginTop: 24,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 14 }}>{title}</div>
        {right}
      </div>
      {children}
    </div>
  );
}

function fmt(v, digits = 1) {
  return v != null ? v.toFixed(digits) : '—';
}

function TabToggle({ options, value, onChange }) {
  return (
    <div style={{ display: 'flex', borderRadius: "var(--radius-sm)", background: 'var(--bg)', padding: 3 }}>
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          style={{
            padding: '6px 14px', borderRadius: "var(--radius-xs)", border: 'none', cursor: 'pointer',
            fontSize: 12, fontWeight: 600, transition: 'background 0.15s ease',
            background: value === key ? 'var(--surface)' : 'transparent',
            color: value === key ? 'var(--ink)' : 'var(--muted)',
            boxShadow: value === key ? '0 1px 2px rgba(11,31,58,0.08)' : 'none',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ---------- Sistem Özeti (Toplam ve Ortalama Değerler) ----------
const STATS_GAUGE_RANGE = {
  p_active: [0, 2000], p_reactive: [0, 2000], p_inductive: [0, 2000], p_capacitive: [0, 2000], p_apparent: [0, 2000],
  avg_current: [0, 10], avg_active_power: [0, 2000], avg_cos: [0, 1], avg_tan: [-2, 2], avg_pf: [0, 1],
};

function StatsBlock({ title, data, suffix, theme }) {
  const rows = [
    ['Toplam Aktif Güç', `p_active_${suffix}`, 0, 'W'],
    ['Toplam Reaktif Güç', `p_reactive_${suffix}`, 0, 'VAr'],
    ['Toplam Endüktif Güç', `p_inductive_${suffix}`, 0, 'VAr'],
    ['Toplam Kapasitif Güç', `p_capacitive_${suffix}`, 0, 'VAr'],
    ['Toplam Görünür Güç', `p_apparent_${suffix}`, 0, 'VA'],
    ['Ortalama Akım', `avg_current_${suffix}`, 3, 'A'],
    ['Ortalama Aktif Güç', `avg_active_power_${suffix}`, 0, 'W'],
    ['Ortalama Cos φ', `avg_cos_${suffix}`, 3, ''],
    ['Ortalama Tan φ', `avg_tan_${suffix}`, 2, ''],
    ['Ortalama Pf', `avg_pf_${suffix}`, 3, ''],
  ];

  if (theme === 'kadran-kumesi') {
    return (
      <div style={{ flex: 1, minWidth: 320 }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: 0.5, marginBottom: 10 }}>{title}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(96px, 1fr))', gap: 10 }}>
          {rows.map(([label, key, , unit]) => {
            const baseKey = key.replace(`_${suffix}`, '');
            const [min, max] = STATS_GAUGE_RANGE[baseKey] || [0, 100];
            return <AnalogGauge key={key} value={data?.[key]} min={min} max={max} label={label.replace('Toplam ', '').replace('Ortalama ', '')} unit={unit} size={100} />;
          })}
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, minWidth: 260 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: 0.5, marginBottom: 10 }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {rows.map(([label, key, digits, unit]) => (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--muted)' }}>{label}</span>
            <span className="mono value-readout" style={{ fontWeight: 500 }}>{fmt(data?.[key], digits)} {unit}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const TREND_RANGES = [['7', '7 Gün'], ['30', '30 Gün'], ['90', '90 Gün']];

function aggregateDaily(rows) {
  const byDay = {};
  for (const row of rows) {
    if (!row.reading_time) continue;
    const day = row.reading_time.slice(0, 10);
    if (!byDay[day]) byDay[day] = { day, tuketim: 0, uretim: 0 };
    byDay[day].tuketim += Math.max(0, row.delta_active_tuketim || 0) / 1000;
    byDay[day].uretim += Math.max(0, row.delta_active_uretim || 0) / 1000;
  }
  return Object.values(byDay)
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((d) => {
      const [, m, dd] = d.day.split('-');
      return { ...d, label: `${dd}.${m}`, tuketim: Math.round(d.tuketim * 100) / 100, uretim: Math.round(d.uretim * 100) / 100 };
    });
}

function TrendSection({ token, device }) {
  const [range, setRange] = useState('7');
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError('');
    axios.get(`${API_BASE}/energy/hourly?device_id=${device.device_id}&days=${range}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => { if (!cancelled) setRows(res.data); })
      .catch(() => { if (!cancelled) setError('Trend verileri yüklenemedi.'); });
    return () => { cancelled = true; };
  }, [device.device_id, range, token]);

  const chartData = rows ? aggregateDaily(rows) : [];
  const totalTuketim = chartData.reduce((s, d) => s + d.tuketim, 0);
  const totalUretim = chartData.reduce((s, d) => s + d.uretim, 0);

  return (
    <SectionCard title="Enerji Trendi" right={<TabToggle options={TREND_RANGES} value={range} onChange={setRange} />}>
      {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
      {!error && rows === null && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}
      {!error && rows !== null && chartData.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu aralıkta henüz veri yok.</div>
      )}
      {!error && chartData.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} width={40} />
              <Tooltip formatter={(val) => `${val} kWh`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="tuketim" name="Tüketim" fill="var(--l1)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="uretim" name="Üretim" fill="var(--l2)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 24, marginTop: 12, fontSize: 12, color: 'var(--muted)' }}>
            <span>Toplam Tüketim: <b className="mono" style={{ color: 'var(--ink)' }}>{totalTuketim.toFixed(1)} kWh</b></span>
            <span>Toplam Üretim: <b className="mono" style={{ color: 'var(--ink)' }}>{totalUretim.toFixed(1)} kWh</b></span>
          </div>
        </>
      )}
    </SectionCard>
  );
}

function StatsSection({ stats, theme }) {
  if (!stats) return null;
  return (
    <SectionCard title="Sistem Özeti (Toplam ve Ortalama)">
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
        <StatsBlock title="TÜKETİM (IMPORT)" data={stats} suffix="imp" theme={theme} />
        <StatsBlock title="ÜRETİM (EXPORT)" data={stats} suffix="exp" theme={theme} />
      </div>
      <div style={{ display: 'flex', gap: 24, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', flexWrap: 'wrap', fontSize: 13 }}>
        <div><span style={{ color: 'var(--muted)' }}>Ort. Gerilim (LN): </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(stats.avg_voltage_ln)} V</span></div>
        <div><span style={{ color: 'var(--muted)' }}>Ort. Gerilim (LL): </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(stats.avg_voltage_ll)} V</span></div>
        <div><span style={{ color: 'var(--muted)' }}>Ort. Frekans: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(stats.avg_frequency, 2)} Hz</span></div>
        <div><span style={{ color: 'var(--muted)' }}>Ort. THID: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(stats.avg_thid)}%</span></div>
        <div><span style={{ color: 'var(--muted)' }}>Ort. THVD: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(stats.avg_thvd)}%</span></div>
      </div>
    </SectionCard>
  );
}

// ---------- Tepe (Min/Max) Değerleri ----------
const PEAK_ROWS = [
  ['Gerilim (LN) 1', 'vln1', 0.1, 'V'], ['Gerilim (LN) 2', 'vln2', 0.1, 'V'], ['Gerilim (LN) 3', 'vln3', 0.1, 'V'], ['Nötr Gerilim', 'vn', 0.1, 'V'],
  ['Gerilim (LL) 1', 'vll1', 0.1, 'V'], ['Gerilim (LL) 2', 'vll2', 0.1, 'V'], ['Gerilim (LL) 3', 'vll3', 0.1, 'V'],
  ['Akım 1', 'i1', 3, 'A'], ['Akım 2', 'i2', 3, 'A'], ['Akım 3', 'i3', 3, 'A'], ['Nötr Akım', 'in', 3, 'A'],
  ['Aktif Güç 1', 'p1', 0, 'W'], ['Aktif Güç 2', 'p2', 0, 'W'], ['Aktif Güç 3', 'p3', 0, 'W'],
  ['Reaktif Güç 1', 'q1', 0, 'VAr'], ['Reaktif Güç 2', 'q2', 0, 'VAr'], ['Reaktif Güç 3', 'q3', 0, 'VAr'],
  ['Görünür Güç 1', 's1', 0, 'VA'], ['Görünür Güç 2', 's2', 0, 'VA'], ['Görünür Güç 3', 's3', 0, 'VA'],
  ['THVD 1', 'thvd1', 0.1, '%'], ['THVD 2', 'thvd2', 0.1, '%'], ['THVD 3', 'thvd3', 0.1, '%'],
  ['THID 1', 'thid1', 0.1, '%'], ['THID 2', 'thid2', 0.1, '%'], ['THID 3', 'thid3', 0.1, '%'],
  ['Frekans', 'freq', 0.01, 'Hz'], ['Gerilim Dengesizliği', 'v_unbal', 0, '%'], ['Akım Dengesizliği', 'i_unbal', 0, '%'],
];

function MinMaxTable({ rows, data }) {
  return (
    <div style={{ overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 420 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={{ textAlign: 'left', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Alan</th>
            <th style={{ textAlign: 'right', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Min</th>
            <th style={{ textAlign: 'right', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Max</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, key, digits, unit]) => {
            const digitPlaces = digits < 1 ? String(digits).split('.')[1]?.length ?? 2 : digits;
            return (
              <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '5px 4px', color: 'var(--muted)' }}>{label}</td>
                <td className="mono" style={{ padding: '5px 4px', textAlign: 'right', fontWeight: 500 }}>
                  {fmt(data?.[keyToMin(key)], digitPlaces)} {unit}
                </td>
                <td className="mono" style={{ padding: '5px 4px', textAlign: 'right', fontWeight: 500 }}>
                  {fmt(data?.[keyToMax(key)], digitPlaces)} {unit}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function keyToMin(key) { return `min_${key}`; }
function keyToMax(key) { return `max_${key}`; }

function PeaksSection({ peaks }) {
  const [tab, setTab] = useState('tuketim');
  if (!peaks || (!peaks.tuketim && !peaks.uretim)) return null;
  const data = peaks[tab];
  return (
    <SectionCard
      title="Tepe (Min/Max) Değerleri"
      right={<TabToggle options={[['tuketim', 'Tüketim'], ['uretim', 'Üretim']]} value={tab} onChange={setTab} />}
    >
      {data ? (
        <MinMaxTable rows={PEAK_ROWS} data={data} />
      ) : (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu yön için henüz veri yok.</div>
      )}
    </SectionCard>
  );
}

// ---------- Demand Değerleri ----------
const DEMAND_ROWS = [
  ['Gerilim 1', 'v1', 0.1, 'V'], ['Gerilim 2', 'v2', 0.1, 'V'], ['Gerilim 3', 'v3', 0.1, 'V'],
  ['Akım 1', 'i1', 3, 'A'], ['Akım 2', 'i2', 3, 'A'], ['Akım 3', 'i3', 3, 'A'],
  ['Aktif Güç 1', 'p1', 0, 'W'], ['Aktif Güç 2', 'p2', 0, 'W'], ['Aktif Güç 3', 'p3', 0, 'W'],
  ['Reaktif Güç 1', 'q1', 0, 'VAr'], ['Reaktif Güç 2', 'q2', 0, 'VAr'], ['Reaktif Güç 3', 'q3', 0, 'VAr'],
  ['Görünür Güç 1', 's1', 0, 'VA'], ['Görünür Güç 2', 's2', 0, 'VA'], ['Görünür Güç 3', 's3', 0, 'VA'],
  ['THVD 1', 'thvd1', 0.1, '%'], ['THVD 2', 'thvd2', 0.1, '%'], ['THVD 3', 'thvd3', 0.1, '%'],
  ['THID 1', 'thid1', 0.1, '%'], ['THID 2', 'thid2', 0.1, '%'], ['THID 3', 'thid3', 0.1, '%'],
];

function DemandMinMaxTable({ data }) {
  return (
    <div style={{ overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 420 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={{ textAlign: 'left', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Alan</th>
            <th style={{ textAlign: 'right', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Min Demand</th>
            <th style={{ textAlign: 'right', padding: '6px 4px', color: 'var(--muted)', fontWeight: 600, fontSize: 11 }}>Max Demand</th>
          </tr>
        </thead>
        <tbody>
          {DEMAND_ROWS.map(([label, key, digits, unit]) => {
            const digitPlaces = digits < 1 ? String(digits).split('.')[1]?.length ?? 2 : digits;
            return (
              <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '5px 4px', color: 'var(--muted)' }}>{label}</td>
                <td className="mono" style={{ padding: '5px 4px', textAlign: 'right', fontWeight: 500 }}>
                  {fmt(data?.[`min_d${key}`], digitPlaces)} {unit}
                </td>
                <td className="mono" style={{ padding: '5px 4px', textAlign: 'right', fontWeight: 500 }}>
                  {fmt(data?.[`max_d${key}`], digitPlaces)} {unit}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DemandSection({ demand }) {
  const [tab, setTab] = useState('tuketim');
  if (!demand || (!demand.tuketim && !demand.uretim)) return null;
  const data = demand[tab];
  return (
    <SectionCard
      title="Demand Değerleri"
      right={<TabToggle options={[['tuketim', 'Tüketim'], ['uretim', 'Üretim']]} value={tab} onChange={setTab} />}
    >
      {data ? (
        <DemandMinMaxTable data={data} />
      ) : (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu yön için henüz veri yok.</div>
      )}
    </SectionCard>
  );
}

// ---------- Harmonik Spektrumu ----------
const HARMONIC_ORDERS = [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31];

function HarmonicsSection({ harmonics }) {
  const [tab, setTab] = useState('akim');
  if (!harmonics || (!harmonics.akim && !harmonics.gerilim)) return null;
  const data = harmonics[tab];
  const chartData = HARMONIC_ORDERS.map((n) => ({
    order: `${n}.`,
    L1: data?.[`h${n}_l1`] ?? 0,
    L2: data?.[`h${n}_l2`] ?? 0,
    L3: data?.[`h${n}_l3`] ?? 0,
  }));
  return (
    <SectionCard
      title="Harmonik Spektrumu"
      right={<TabToggle options={[['akim', 'Akım'], ['gerilim', 'Gerilim']]} value={tab} onChange={setTab} />}
    >
      {data ? (
        <>
          <div style={{ display: 'flex', gap: 24, marginBottom: 12, fontSize: 13 }}>
            <div><span style={{ color: 'var(--muted)' }}>THD 1: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(data.thd1)}%</span></div>
            <div><span style={{ color: 'var(--muted)' }}>THD 2: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(data.thd2)}%</span></div>
            <div><span style={{ color: 'var(--muted)' }}>THD 3: </span><span className="mono" style={{ fontWeight: 500 }}>{fmt(data.thd3)}%</span></div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="order" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} width={36} unit="%" />
              <Tooltip formatter={(val) => `${val}%`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="L1" fill="var(--l1)" />
              <Bar dataKey="L2" fill="var(--l2)" />
              <Bar dataKey="L3" fill="var(--l3)" />
            </BarChart>
          </ResponsiveContainer>
        </>
      ) : (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu sinyal tipi için henüz veri yok.</div>
      )}
    </SectionCard>
  );
}

// ---------- Cihaz Bilgileri ----------
const DEVICE_INFO_ROWS = [
  ['Seri No', 'seri_no'], ['Ürün ID', 'urun_id'], ['Kart ID', 'kart_id'], ['Sistem Versiyonu', 'sistem_versiyon'],
  ['Ülke Kodu', 'ulke_kodu'], ['Firma Kodu', 'firma_kodu'], ['Besleme Tipi', 'besleme_tipi'],
  ['Ekran Tipi', 'ekran_tipi'], ['Klavye Tipi', 'keyboard_tipi'], ['Kutu Tipi', 'kutu_tipi'],
  ['Klemens Tipi', 'klemens_tipi'], ['Bağlantılar', 'connections'], ['Hafıza', 'storage'],
];

function DeviceInfoSection({ info }) {
  if (!info) return null;
  return (
    <SectionCard title="Cihaz Bilgileri">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
        {DEVICE_INFO_ROWS.map(([label, key]) => (
          <div key={key} style={{ fontSize: 13 }}>
            <div style={{ color: 'var(--muted)', fontSize: 11 }}>{label}</div>
            <div className="mono" style={{ fontWeight: 500 }}>{info[key] ?? '—'}</div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ---------- Alarmlar ----------
// backend'deki ALARM_METRICS ile birebir aynı (bkz. api.py)
const ALARM_METRIC_LIST = [
  { key: 'voltage', label: 'Gerilim', unit: 'V', step: '0.1', placeholder: '250' },
  { key: 'current', label: 'Akım', unit: 'A', step: '0.001', placeholder: '100' },
  { key: 'power', label: 'Aktif Güç', unit: 'W', step: '1', placeholder: '20000' },
  { key: 'pf', label: 'Güç Faktörü', unit: '', step: '0.01', placeholder: '0.90' },
  { key: 'frequency', label: 'Frekans', unit: 'Hz', step: '0.01', placeholder: '49.5' },
  { key: 'thd', label: 'THD (Akım)', unit: '%', step: '0.1', placeholder: '8' },
  { key: 'offline', label: 'Cihaz çevrimdışı', unit: 'dakika', step: '1', placeholder: '15' },
];

// ---------- Güç Kalitesi (EN 50160) ----------
const PQ_RANGES = [['7', '1 Hafta'], ['30', '30 Gün'], ['90', '90 Gün']];

const PQ_VERDICTS = {
  uygun: { label: 'Uygun', color: 'var(--accent)' },
  uygun_degil: { label: 'Uygun Değil', color: 'var(--danger)' },
  yetersiz_veri: { label: 'Yetersiz Veri', color: 'var(--muted)' },
};

function PqParam({ p }) {
  const durum = p.pass === null
    ? { text: 'Ölçülmedi', color: 'var(--muted)' }
    : p.pass
      ? { text: 'Uygun', color: 'var(--accent)' }
      : { text: 'Uygun değil', color: 'var(--danger)' };

  return (
    <div style={{
      padding: '12px 14px', borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${durum.color}`,
      background: 'var(--bg)', marginBottom: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{p.label}</div>
        <div style={{ fontSize: 12, fontWeight: 600, color: durum.color }}>{durum.text}</div>
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>{p.limit}</div>
      {p.value_pct != null && (
        <div style={{ fontSize: 12, marginTop: 6 }} className="mono">
          Ölçümlerin <b style={{ color: durum.color }}>%{p.value_pct}</b>'i limit içinde
          <span style={{ color: 'var(--muted)' }}> (gereken %{p.required_pct})</span>
        </div>
      )}
      {p.extra?.faz_min && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }} className="mono">
          Faz aralıkları: {p.extra.faz_min.map((v, i) =>
            `L${i + 1} ${v ?? '—'}–${p.extra.faz_max[i] ?? '—'} V`).join('  ·  ')}
        </div>
      )}
      {p.extra?.min != null && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }} className="mono">
          Aralık: {p.extra.min}–{p.extra.max} Hz
        </div>
      )}
      {p.extra?.faz_max && !p.extra?.faz_min && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }} className="mono">
          En yüksek: {p.extra.faz_max.map((v, i) => `L${i + 1} %${v ?? '—'}`).join('  ·  ')}
        </div>
      )}
    </div>
  );
}

function PowerQualitySection({ token, device }) {
  const [days, setDays] = useState('7');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setData(null); setError('');
    axios.get(`${API_BASE}/reports/power-quality?device_id=${device.device_id}&days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setError('Güç kalitesi raporu yüklenemedi.'); });
    return () => { cancelled = true; };
  }, [device.device_id, days, token]);

  const verdict = data ? PQ_VERDICTS[data.verdict] : null;

  return (
    <SectionCard
      title="Güç Kalitesi (EN 50160)"
      right={<TabToggle options={PQ_RANGES} value={days} onChange={setDays} />}
    >
      {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
      {!error && data === null && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}

      {!error && data && (
        <>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
            padding: '12px 14px', marginBottom: 14, borderRadius: 'var(--radius-sm)',
            background: `color-mix(in srgb, ${verdict.color} 8%, transparent)`,
            border: `1px solid color-mix(in srgb, ${verdict.color} 30%, var(--border))`,
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>DEĞERLENDİRME</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: verdict.color }}>{verdict.label}</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }} className="mono">
              {data.intervals.gecerli} geçerli ölçüm aralığı
              {data.intervals.olcum_yok > 0 && ` · ${data.intervals.olcum_yok} aralıkta ölçüm yok`}
              <br />Dönem kapsaması %{data.intervals.kapsama_pct} · Nominal gerilim {data.nominal_voltage} V
            </div>
          </div>

          {data.verdict === 'yetersiz_veri' && (
            <div style={{
              fontSize: 12, color: 'var(--muted)', marginBottom: 14, padding: '10px 12px',
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
            }}>
              EN 50160 değerlendirmesi normalde <b>bir haftalık kesintisiz</b> ölçüme dayanır.
              Bu dönemde yeterli ölçüm yok, bu yüzden aşağıdaki sonuçlar <b>uygunluk beyanı
              değil</b>, yalnızca eldeki verinin özetidir.
            </div>
          )}

          {data.parameters.map((p) => <PqParam key={p.key} p={p} />)}

          <div style={{
            marginTop: 14, padding: '10px 12px', borderRadius: 'var(--radius-sm)',
            border: '1px dashed var(--border)', fontSize: 11, color: 'var(--muted)',
          }}>
            <b>Bu rapor resmî bir uygunluk belgesi değildir.</b> Ölçümler 10 dakikalık
            ortalamalar üzerinden EN 50160'ın tanımladığı yönteme göre yapılır, ancak
            standardın bazı parametreleri bu cihazla ölçülemiyor ve değerlendirmeye
            girmiyor:
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              {data.not_assessed.map((x) => (
                <li key={x.label}>{x.label} — <i>{x.reason}</i></li>
              ))}
            </ul>
          </div>
        </>
      )}
    </SectionCard>
  );
}

// ---------- Fatura Analizi (zaman dilimi + güç aşımı + reaktif) ----------
function monthLabel(bucket) {
  return new Date(bucket).toLocaleDateString('tr-TR', { month: 'short', year: 'numeric' });
}

function BillSection({ token, device }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [pdfMonth, setPdfMonth] = useState('');
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null); setError('');
    axios.get(`${API_BASE}/reports/bill?device_id=${device.device_id}&months=12`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setError('Fatura analizi yüklenemedi.'); });
    return () => { cancelled = true; };
  }, [device.device_id, token]);

  // Tarife kaydedildikten sonra sessiz tazeleme: data'yı null'a çekmiyoruz ki
  // TariffForm unmount olup "Kaydedildi." mesajı görülmeden kaybolmasın.
  async function reloadSilently() {
    try {
      const res = await axios.get(`${API_BASE}/reports/bill?device_id=${device.device_id}&months=12`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch {
      // Tarife zaten kaydedildi; sadece tazeleme başarısız oldu.
    }
  }

  async function downloadXlsx() {
    setDownloading(true);
    try {
      const res = await axios.get(
        `${API_BASE}/reports/bill?device_id=${device.device_id}&months=12&format=xlsx`,
        { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${device.device_id}-fatura-analizi.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('Excel indirilemedi.');
    } finally {
      setDownloading(false);
    }
  }

  // Aylik PDF raporu: e-posta ile gonderilenin aynisi, istenen ay icin.
  async function downloadPdf(bucket) {
    const d = new Date(bucket);
    const year = d.getFullYear();
    const month = d.getMonth() + 1;
    setPdfBusy(true);
    setPdfMonth(bucket);
    try {
      const res = await axios.get(
        `${API_BASE}/reports/monthly-pdf?device_id=${device.device_id}&year=${year}&month=${month}`,
        { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${device.device_id}-${year}-${String(month).padStart(2, '0')}-enerji-raporu.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('PDF raporu indirilemedi.');
    } finally {
      setPdfBusy(false);
      setPdfMonth('');
    }
  }

  const rows = data?.rows || [];
  const tariff = data?.tariff;
  const summary = data?.summary;
  const priced = summary?.priced;

  const chartData = rows.map((r) => ({
    label: monthLabel(r.bucket),
    Gündüz: r.t1_kwh,
    Puant: r.t2_kwh,
    Gece: r.t3_kwh,
    tepe: r.peak_kw,
  }));

  return (
    <SectionCard
      title="Fatura Analizi"
      right={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="button" onClick={downloadXlsx} disabled={downloading || rows.length === 0} style={{
            padding: '6px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
            background: 'var(--surface)', color: 'var(--muted)', fontSize: 12, fontWeight: 600,
            cursor: downloading || rows.length === 0 ? 'default' : 'pointer',
          }}>{downloading ? 'İndiriliyor…' : 'Excel indir'}</button>
          <button type="button" onClick={() => setSettingsOpen((o) => !o)} style={{
            padding: '6px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
            background: 'var(--surface)', color: 'var(--muted)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}>Tarife {settingsOpen ? '▲' : '▼'}</button>
        </div>
      }
    >
      {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
      {!error && data === null && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}
      {!error && data && rows.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu aralıkta enerji verisi yok.</div>
      )}

      {!error && data && rows.length > 0 && (
        <>
          {/* Faturanın kalem kalem dökümü — asıl anlatılmak istenen şey bu */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
            {priced && (
              <ReactiveStat
                label="Toplam tahmini fatura"
                value={money(summary.total_cost)}
                hint={`${summary.month_count} ay · ${summary.total_kwh.toLocaleString('tr-TR')} kWh`}
              />
            )}
            {priced && (
              <ReactiveStat label="Aktif enerji" value={money(summary.total_active_cost)}
                hint={summary.total_cost > 0
                  ? `faturanın %${(summary.total_active_cost / summary.total_cost * 100).toFixed(0)}'i` : null} />
            )}
            {priced && (
              <ReactiveStat label="Güç aşım bedeli" value={money(summary.total_demand_cost)}
                hint={`${summary.overrun_months} ayda aşım`}
                danger={summary.total_demand_cost > 0} />
            )}
            {priced && (
              <ReactiveStat label="Reaktif ceza" value={money(summary.total_reactive_cost)}
                danger={summary.total_reactive_cost > 0} />
            )}
            <ReactiveStat
              label="Puant oranı"
              value={summary.puant_pct != null ? `%${summary.puant_pct}` : '—'}
              hint="pahalı dilimdeki tüketim"
              danger={summary.puant_pct > 25}
            />
            {summary.peak_kw != null && (
              <ReactiveStat
                label="En yüksek tepe güç"
                value={`${summary.peak_kw} kW`}
                hint={tariff.contract_power_kw ? `sözleşme ${tariff.contract_power_kw} kW` : 'sözleşme gücü girilmedi'}
                danger={tariff.contract_power_kw != null && summary.peak_kw > tariff.contract_power_kw}
              />
            )}
          </div>

          {priced && <TarifeDogrulanmadiUyarisi tariff={tariff} />}

          {!priced && (
            <div style={{
              fontSize: 12, color: 'var(--muted)', marginBottom: 16, padding: '10px 12px',
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
            }}>
              Fatura tutarlarını görebilmek için <b>Tarife</b> bölümünden faturanızdaki birim fiyatları
              ve sözleşme gücünüzü girin. Tüketim kırılımı fiyat girilmeden de çalışır.
            </div>
          )}

          {summary.tou_enabled && summary.total_shift_saving > 0 && (
            <div style={{
              fontSize: 12, marginBottom: 16, padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid color-mix(in srgb, var(--accent) 40%, var(--border))',
              background: 'color-mix(in srgb, var(--accent) 6%, transparent)',
            }}>
              Puanttaki tüketimin <b>tamamı</b> gece tarifesine kaysaydı bu dönemde{' '}
              <b className="mono">{money(summary.total_shift_saving)}</b> daha az ödenirdi. Bu ulaşılabilir bir
              hedef değil, tasarruf <b>tavanı</b> — yükün ne kadarını kaydırabildiğinize göre bunun bir kısmı gerçekleşir.
            </div>
          )}

          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
              <YAxis yAxisId="kwh" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={50} />
              <YAxis yAxisId="kw" orientation="right" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={45}
                     tickFormatter={(v) => `${v}kW`} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }}
                       formatter={(val, name) => (name === 'tepe' ? `${val} kW` : `${val} kWh`)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar yAxisId="kwh" dataKey="Gece" stackId="e" fill="var(--l3)" />
              <Bar yAxisId="kwh" dataKey="Gündüz" stackId="e" fill="var(--l1)" />
              <Bar yAxisId="kwh" dataKey="Puant" stackId="e" fill="var(--danger)" radius={[4, 4, 0, 0]} />
              {tariff.contract_power_kw != null && (
                <ReferenceLine yAxisId="kw" y={tariff.contract_power_kw} stroke="var(--accent)"
                               strokeDasharray="4 4" />
              )}
              <Line yAxisId="kw" type="monotone" dataKey="tepe" name="tepe" stroke="var(--accent)"
                    strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
            Çubuklar aylık tüketimin zaman dilimlerine dağılımı; çizgi 15 dakikalık ortalamaya göre tepe güç.
            {tariff.contract_power_kw != null && ' Kesikli çizgi sözleşme gücü — üstüne çıkan aylarda güç aşım bedeli doğar.'}
          </div>

          <div style={{ overflowX: 'auto', marginTop: 16 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 820 }}>
              <thead>
                <tr style={{ color: 'var(--muted)', textAlign: 'right' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Ay</th>
                  <th style={{ padding: '6px 8px' }}>Gündüz</th>
                  <th style={{ padding: '6px 8px' }}>Puant</th>
                  <th style={{ padding: '6px 8px' }}>Gece</th>
                  <th style={{ padding: '6px 8px' }}>Tepe Güç</th>
                  <th style={{ padding: '6px 8px' }}>Aşım</th>
                  {priced && <th style={{ padding: '6px 8px' }}>Aktif</th>}
                  {priced && <th style={{ padding: '6px 8px' }}>Güç Aşım</th>}
                  {priced && <th style={{ padding: '6px 8px' }}>Reaktif</th>}
                  {priced && <th style={{ padding: '6px 8px' }}>Toplam</th>}
                  <th style={{ padding: '6px 8px' }}>Rapor</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].reverse().map((r) => (
                  <tr key={r.bucket} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '7px 8px', fontWeight: 500 }}>{monthLabel(r.bucket)}</td>
                    <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>{r.t1_kwh}</td>
                    <td className="mono" style={{
                      padding: '7px 8px', textAlign: 'right',
                      color: r.puant_pct > 25 ? 'var(--danger)' : 'var(--ink)',
                    }}>{r.t2_kwh}{r.puant_pct != null && <span style={{ color: 'var(--muted)' }}> (%{r.puant_pct})</span>}</td>
                    <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>{r.t3_kwh}</td>
                    <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>
                      {r.peak_kw != null ? `${r.peak_kw} kW` : '—'}
                    </td>
                    <td className="mono" style={{
                      padding: '7px 8px', textAlign: 'right',
                      color: (r.overrun_kw || 0) > 0 ? 'var(--danger)' : 'var(--muted)',
                      fontWeight: (r.overrun_kw || 0) > 0 ? 600 : 400,
                    }}>{r.overrun_kw != null ? (r.overrun_kw > 0 ? `+${r.overrun_kw} kW` : '—') : '—'}</td>
                    {priced && <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>{money(r.active_cost)}</td>}
                    {priced && <td className="mono" style={{
                      padding: '7px 8px', textAlign: 'right',
                      color: r.demand_cost > 0 ? 'var(--danger)' : 'var(--muted)',
                    }}>{r.demand_cost > 0 ? money(r.demand_cost) : '—'}</td>}
                    {priced && <td className="mono" style={{
                      padding: '7px 8px', textAlign: 'right',
                      color: r.reactive_cost > 0 ? 'var(--danger)' : 'var(--muted)',
                    }}>{r.reactive_cost > 0 ? money(r.reactive_cost) : '—'}</td>}
                    {priced && <td className="mono" style={{ padding: '7px 8px', textAlign: 'right', fontWeight: 600 }}>
                      {money(r.total_cost)}
                    </td>}
                    <td style={{ padding: '7px 8px', textAlign: 'right' }}>
                      <button type="button" onClick={() => downloadPdf(r.bucket)}
                              disabled={pdfBusy}
                              style={{
                                padding: '4px 10px', borderRadius: 'var(--radius-xs)',
                                border: '1px solid var(--border)', background: 'var(--surface)',
                                color: 'var(--muted)', fontSize: 11, fontWeight: 600,
                                cursor: pdfBusy ? 'default' : 'pointer', whiteSpace: 'nowrap',
                              }}>
                        {pdfBusy && pdfMonth === r.bucket ? '…' : 'PDF'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {rows.some((r) => r.peak_time) && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10 }}>
              Son dönemin tepe gücü{' '}
              <b className="mono" style={{ color: 'var(--ink)' }}>
                {new Date(rows[rows.length - 1].peak_time).toLocaleString('tr-TR',
                  { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </b>{' '}
              anında oluştu.
            </div>
          )}
        </>
      )}

      {settingsOpen && tariff && (
        <TariffForm token={token} device={device} tariff={tariff} onSaved={reloadSilently} />
      )}
    </SectionCard>
  );
}

// ---------- Reaktif Ceza Analizi ----------
const REACTIVE_PERIODS = [['monthly', 'Aylık'], ['daily', 'Günlük']];

function money(v) {
  if (v == null) return '—';
  return v.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₺';
}

function periodLabel(bucket, period) {
  const d = new Date(bucket);
  return period === 'monthly'
    ? d.toLocaleDateString('tr-TR', { month: 'short', year: 'numeric' })
    : d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });
}

function ReactiveStat({ label, value, hint, danger }) {
  return (
    <div style={{
      flex: '1 1 150px', minWidth: 150, padding: '12px 14px',
      borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
      background: danger ? 'color-mix(in srgb, var(--danger) 8%, var(--surface))' : 'var(--bg)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>{label}</div>
      <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: danger ? 'var(--danger)' : 'var(--ink)' }}>{value}</div>
      {hint && <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>{hint}</div>}
    </div>
  );
}

function TariffForm({ token, device, tariff, onSaved }) {
  const [form, setForm] = useState({
    inductive_limit_pct: tariff.inductive_limit_pct,
    capacitive_limit_pct: tariff.capacitive_limit_pct,
    reactive_price: tariff.reactive_price,
    active_price: tariff.active_price,
    billing_mode: tariff.billing_mode,
    t1_start: tariff.t1_start,
    t2_start: tariff.t2_start,
    t3_start: tariff.t3_start,
    t1_price: tariff.t1_price,
    t2_price: tariff.t2_price,
    t3_price: tariff.t3_price,
    contract_power_kw: tariff.contract_power_kw ?? '',
    demand_price: tariff.demand_price,
    tariff_verified: tariff.tariff_verified ?? false,
    tariff_source: tariff.tariff_source ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
    setMsg('');
  }

  function applyPreset(name) {
    const p = tariff.presets?.[name];
    if (p) setForm((f) => ({ ...f, ...p }));
    setMsg('');
  }

  async function save() {
    setSaving(true); setError(''); setMsg('');
    try {
      await axios.put(`${API_BASE}/devices/${device.device_id}/tariff`, {
        inductive_limit_pct: Number(form.inductive_limit_pct),
        capacitive_limit_pct: Number(form.capacitive_limit_pct),
        reactive_price: Number(form.reactive_price),
        active_price: Number(form.active_price),
        billing_mode: form.billing_mode,
        t1_start: Number(form.t1_start),
        t2_start: Number(form.t2_start),
        t3_start: Number(form.t3_start),
        t1_price: Number(form.t1_price),
        t2_price: Number(form.t2_price),
        t3_price: Number(form.t3_price),
        // Bos birakilirsa sozlesme gucu "girilmedi" demek -- 0 degil null.
        contract_power_kw: form.contract_power_kw === '' ? null : Number(form.contract_power_kw),
        demand_price: Number(form.demand_price),
        tariff_verified: !!form.tariff_verified,
        tariff_source: form.tariff_source.trim() || null,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setMsg('Kaydedildi.');
      onSaved();
    } catch (e) {
      setError(e.response?.data?.detail || 'Kaydedilemedi.');
    } finally {
      setSaving(false);
    }
  }

  const field = {
    width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-xs)',
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--ink)', fontSize: 13, fontFamily: 'inherit',
  };
  const labelStyle = { fontSize: 11, color: 'var(--muted)', display: 'block', marginBottom: 4 };

  return (
    <div style={{
      marginTop: 16, padding: 16, borderRadius: 'var(--radius-sm)',
      border: '1px dashed var(--border)', background: 'var(--bg)',
    }}>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
        Limitler ve birim fiyatlar tarifeye göre değişir. Faturanızdaki değerleri girerek hesabı kendi
        aboneliğinize göre kalibre edin.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--muted)', alignSelf: 'center' }}>Hazır limitler:</span>
        <button type="button" onClick={() => applyPreset('over_50kw')} style={{
          padding: '5px 10px', fontSize: 11, borderRadius: 'var(--radius-xs)',
          border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--ink)', cursor: 'pointer',
        }}>≥ 50 kW (%20 / %15)</button>
        <button type="button" onClick={() => applyPreset('under_50kw')} style={{
          padding: '5px 10px', fontSize: 11, borderRadius: 'var(--radius-xs)',
          border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--ink)', cursor: 'pointer',
        }}>&lt; 50 kW (%33 / %20)</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
        <div>
          <label style={labelStyle}>Endüktif limit (%)</label>
          <input style={field} type="number" step="0.1" value={form.inductive_limit_pct}
                 onChange={(e) => set('inductive_limit_pct', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Kapasitif limit (%)</label>
          <input style={field} type="number" step="0.1" value={form.capacitive_limit_pct}
                 onChange={(e) => set('capacitive_limit_pct', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Reaktif birim fiyat (₺/kVArh)</label>
          <input style={field} type="number" step="0.0001" value={form.reactive_price}
                 onChange={(e) => set('reactive_price', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Aktif birim fiyat (₺/kWh)</label>
          <input style={field} type="number" step="0.0001" value={form.active_price}
                 onChange={(e) => set('active_price', e.target.value)} />
        </div>
        <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 4 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>Üç Zamanlı Tarife</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            Üç fiyatı da 0 bırakırsanız tek fiyatlı aktif birim fiyat kullanılır.
          </div>
        </div>
        <div>
          <label style={labelStyle}>Gündüz başlangıcı (saat)</label>
          <input style={field} type="number" min="0" max="23" value={form.t1_start}
                 onChange={(e) => set('t1_start', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Puant başlangıcı (saat)</label>
          <input style={field} type="number" min="0" max="23" value={form.t2_start}
                 onChange={(e) => set('t2_start', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Gece başlangıcı (saat)</label>
          <input style={field} type="number" min="0" max="23" value={form.t3_start}
                 onChange={(e) => set('t3_start', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Gündüz fiyatı (₺/kWh)</label>
          <input style={field} type="number" step="0.0001" value={form.t1_price}
                 onChange={(e) => set('t1_price', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Puant fiyatı (₺/kWh)</label>
          <input style={field} type="number" step="0.0001" value={form.t2_price}
                 onChange={(e) => set('t2_price', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Gece fiyatı (₺/kWh)</label>
          <input style={field} type="number" step="0.0001" value={form.t3_price}
                 onChange={(e) => set('t3_price', e.target.value)} />
        </div>

        <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 4 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>Güç Aşımı</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            Sözleşme gücünü boş bırakırsanız güç aşım analizi yapılmaz.
          </div>
        </div>
        <div>
          <label style={labelStyle}>Sözleşme gücü (kW)</label>
          <input style={field} type="number" step="0.1" placeholder="girilmedi" value={form.contract_power_kw}
                 onChange={(e) => set('contract_power_kw', e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Güç aşım bedeli (₺/kW)</label>
          <input style={field} type="number" step="0.0001" value={form.demand_price}
                 onChange={(e) => set('demand_price', e.target.value)} />
        </div>

        <div style={{ gridColumn: '1 / -1' }}>
          <label style={labelStyle}>Ceza hesaplama yöntemi</label>
          <select style={field} value={form.billing_mode} onChange={(e) => set('billing_mode', e.target.value)}>
            <option value="full">Limit aşılırsa reaktifin tamamı faturalanır</option>
            <option value="excess">Yalnızca limiti aşan kısım faturalanır</option>
          </select>
        </div>
      </div>

      <label style={{
        display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 16,
        fontSize: 12, lineHeight: 1.5, cursor: 'pointer',
      }}>
        <input
          type="checkbox"
          checked={!!form.tariff_verified}
          onChange={(e) => set('tariff_verified', e.target.checked)}
          style={{ marginTop: 2 }}
        />
        <span>
          <b>Bu rakamlar faturadan doğrulandı.</b> İşaretlenmezse panel, PDF rapor ve
          aylık e-posta “tutarlar tahminidir” uyarısı gösterir.
        </span>
      </label>
      <input
        value={form.tariff_source}
        onChange={(e) => set('tariff_source', e.target.value)}
        placeholder="Rakamların kaynağı (ör. Fatura, Ağustos 2026)"
        maxLength={120}
        style={{
          marginTop: 8, width: '100%', boxSizing: 'border-box', padding: '7px 9px',
          borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
          background: 'var(--bg)', color: 'var(--ink)', fontSize: 12,
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
        <button type="button" onClick={save} disabled={saving} style={{
          padding: '8px 16px', borderRadius: 'var(--radius-xs)', border: 'none',
          background: 'var(--accent)', color: '#fff', fontSize: 12, fontWeight: 600,
          cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
        }}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button>
        {msg && <span style={{ fontSize: 12, color: 'var(--accent)' }}>{msg}</span>}
        {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
      </div>
    </div>
  );
}

function ReactiveSection({ token, device }) {
  const [period, setPeriod] = useState('monthly');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null); setError('');
    const count = period === 'monthly' ? 12 : 30;
    axios.get(`${API_BASE}/reports/reactive?device_id=${device.device_id}&period=${period}&count=${count}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setError('Reaktif analiz yüklenemedi.'); });
    return () => { cancelled = true; };
  }, [device.device_id, period, token]);

  // Tarife kaydedildikten sonra raporu tazelemek icin ayri, "sessiz" bir
  // yeniden yukleme -- data'yi once null'a cekmiyor. Aksi halde tum bolum
  // aninda "Yukleniyor..." haline donup TariffForm unmount oluyor ve
  // "Kaydedildi." mesaji goruluremeden kayboluyor.
  async function reloadSilently() {
    const count = period === 'monthly' ? 12 : 30;
    try {
      const res = await axios.get(`${API_BASE}/reports/reactive?device_id=${device.device_id}&period=${period}&count=${count}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch {
      // Tarife zaten kaydedildi -- sadece rapor tazeleme basarisiz oldu,
      // eski veriler ekranda kalmaya devam etsin.
    }
  }

  async function downloadXlsx() {
    setDownloading(true);
    try {
      const count = period === 'monthly' ? 12 : 30;
      const res = await axios.get(
        `${API_BASE}/reports/reactive?device_id=${device.device_id}&period=${period}&count=${count}&format=xlsx`,
        { headers: { Authorization: `Bearer ${token}` }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${device.device_id}-reaktif-analiz.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('Excel indirilemedi.');
    } finally {
      setDownloading(false);
    }
  }

  const rows = data?.rows || [];
  const tariff = data?.tariff;
  const summary = data?.summary;
  const chartData = rows.map((r) => ({
    label: periodLabel(r.bucket, period),
    aktif: r.active_kwh,
    endPct: r.inductive_pct,
    kapPct: r.capacitive_pct,
  }));
  const hasPrice = tariff && tariff.reactive_price > 0;

  return (
    <SectionCard
      title="Reaktif Ceza Analizi"
      right={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <TabToggle options={REACTIVE_PERIODS} value={period} onChange={setPeriod} />
          <button type="button" onClick={downloadXlsx} disabled={downloading || rows.length === 0} style={{
            padding: '6px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
            background: 'var(--surface)', color: 'var(--muted)', fontSize: 12, fontWeight: 600,
            cursor: downloading || rows.length === 0 ? 'default' : 'pointer',
          }}>{downloading ? 'İndiriliyor…' : 'Excel indir'}</button>
          <button type="button" onClick={() => setSettingsOpen((o) => !o)} style={{
            padding: '6px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
            background: 'var(--surface)', color: 'var(--muted)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}>Tarife {settingsOpen ? '▲' : '▼'}</button>
        </div>
      }
    >
      {error && <div style={{ fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
      {!error && data === null && <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>}

      {!error && data && rows.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Bu aralıkta enerji verisi yok.</div>
      )}

      {!error && data && rows.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
            <ReactiveStat
              label="Cezalı dönem"
              value={`${summary.penalized_count} / ${summary.period_count}`}
              hint={period === 'monthly' ? 'ay' : 'gün'}
              danger={summary.penalized_count > 0}
            />
            <ReactiveStat
              label="En yüksek endüktif"
              value={summary.worst_inductive_pct != null ? `%${summary.worst_inductive_pct}` : '—'}
              hint={`limit %${tariff.inductive_limit_pct}`}
              danger={summary.worst_inductive_pct > tariff.inductive_limit_pct}
            />
            <ReactiveStat
              label="En yüksek kapasitif"
              value={summary.worst_capacitive_pct != null ? `%${summary.worst_capacitive_pct}` : '—'}
              hint={`limit %${tariff.capacitive_limit_pct}`}
              danger={summary.worst_capacitive_pct > tariff.capacitive_limit_pct}
            />
            {hasPrice && (
              <ReactiveStat
                label="Toplam ceza"
                value={money(summary.total_penalty_cost)}
                hint={summary.total_active_cost > 0
                  ? `aktif bedelin %${(summary.total_penalty_cost / summary.total_active_cost * 100).toFixed(1)}'i`
                  : null}
                danger={summary.total_penalty_cost > 0}
              />
            )}
            {summary.max_suggested_kvar != null && (
              <ReactiveStat
                label="Önerilen kompanzasyon"
                value={`${summary.max_suggested_kvar} kVAr`}
                hint="aşımı kapatmak için"
              />
            )}
          </div>

          {!hasPrice && (
            <div style={{
              fontSize: 12, color: 'var(--muted)', marginBottom: 16, padding: '10px 12px',
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
            }}>
              Ceza tutarını görebilmek için <b>Tarife</b> bölümünden faturanızdaki reaktif birim fiyatı girin.
            </div>
          )}

          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
              <YAxis yAxisId="kwh" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={45} />
              <YAxis yAxisId="pct" orientation="right" tick={{ fontSize: 10, fill: 'var(--muted)' }} width={40}
                     tickFormatter={(v) => `%${v}`} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
                formatter={(val, name) => (name === 'Aktif' ? `${val} kWh` : `%${val}`)}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar yAxisId="kwh" dataKey="aktif" name="Aktif" fill="var(--l3)" radius={[4, 4, 0, 0]} />
              <ReferenceLine yAxisId="pct" y={tariff.inductive_limit_pct} stroke="var(--danger)"
                             strokeDasharray="4 4" />
              <ReferenceLine yAxisId="pct" y={tariff.capacitive_limit_pct} stroke="var(--l2)"
                             strokeDasharray="4 4" />
              <Line yAxisId="pct" type="monotone" dataKey="endPct" name="Endüktif %" stroke="var(--danger)"
                    strokeWidth={2} dot={{ r: 2 }} connectNulls />
              <Line yAxisId="pct" type="monotone" dataKey="kapPct" name="Kapasitif %" stroke="var(--l2)"
                    strokeWidth={2} dot={{ r: 2 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
            Kesikli çizgiler limitleri gösterir — çizginin üstündeki dönemlerde reaktif bedel doğar.
          </div>

          <div style={{ overflowX: 'auto', marginTop: 16 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 640 }}>
              <thead>
                <tr style={{ color: 'var(--muted)', textAlign: 'right' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Dönem</th>
                  <th style={{ padding: '6px 8px' }}>Aktif (kWh)</th>
                  <th style={{ padding: '6px 8px' }}>Endüktif</th>
                  <th style={{ padding: '6px 8px' }}>Kapasitif</th>
                  <th style={{ padding: '6px 8px' }}>Aşım (kVArh)</th>
                  {hasPrice && <th style={{ padding: '6px 8px' }}>Ceza</th>}
                </tr>
              </thead>
              <tbody>
                {[...rows].reverse().map((r) => {
                  const over = r.inductive_over || r.capacitive_over;
                  const excess = r.inductive_excess_kvarh + r.capacitive_excess_kvarh;
                  return (
                    <tr key={r.bucket} style={{
                      borderTop: '1px solid var(--border)',
                      background: over ? 'color-mix(in srgb, var(--danger) 6%, transparent)' : 'transparent',
                    }}>
                      <td style={{ padding: '7px 8px', fontWeight: 500 }}>{periodLabel(r.bucket, period)}</td>
                      <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>{r.active_kwh}</td>
                      <td className="mono" style={{
                        padding: '7px 8px', textAlign: 'right',
                        color: r.inductive_over ? 'var(--danger)' : 'var(--ink)',
                        fontWeight: r.inductive_over ? 600 : 400,
                      }}>{r.inductive_pct != null ? `%${r.inductive_pct}` : '—'}</td>
                      <td className="mono" style={{
                        padding: '7px 8px', textAlign: 'right',
                        color: r.capacitive_over ? 'var(--danger)' : 'var(--ink)',
                        fontWeight: r.capacitive_over ? 600 : 400,
                      }}>{r.capacitive_pct != null ? `%${r.capacitive_pct}` : '—'}</td>
                      <td className="mono" style={{ padding: '7px 8px', textAlign: 'right' }}>
                        {excess > 0 ? excess.toFixed(1) : '—'}
                      </td>
                      {hasPrice && (
                        <td className="mono" style={{
                          padding: '7px 8px', textAlign: 'right',
                          color: r.penalty_cost > 0 ? 'var(--danger)' : 'var(--muted)',
                        }}>{r.penalty_cost > 0 ? money(r.penalty_cost) : '—'}</td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {settingsOpen && tariff && (
        <TariffForm token={token} device={device} tariff={tariff} onSaved={reloadSilently} />
      )}
    </SectionCard>
  );
}

function formatAlarmTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function AlarmsSection({ token, device }) {
  const [rules, setRules] = useState(null);
  const [events, setEvents] = useState([]);
  const [adding, setAdding] = useState(false);
  const [metric, setMetric] = useState('voltage');
  const [phase, setPhase] = useState('any');
  const [condition, setCondition] = useState('gt');
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };
  const isOffline = metric === 'offline';
  const metricDef = ALARM_METRIC_LIST.find((m) => m.key === metric);

  function refresh() {
    axios.get(`${API_BASE}/devices/${device.device_id}/alarm-rules`, { headers })
      .then((res) => setRules(res.data)).catch(() => setRules([]));
    axios.get(`${API_BASE}/devices/${device.device_id}/alarm-events?limit=20`, { headers })
      .then((res) => setEvents(res.data)).catch(() => {});
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [device.device_id]);

  async function addRule() {
    setBusy(true);
    setToast(null);
    try {
      const body = isOffline
        ? { metric: 'offline', offline_minutes: Number(value) }
        : { metric, phase, condition, threshold: Number(value) };
      await axios.post(`${API_BASE}/devices/${device.device_id}/alarm-rules`, body, { headers });
      setValue('');
      setAdding(false);
      refresh();
    } catch (err) {
      setToast({ ok: false, text: err.response?.data?.detail || 'Alarm eklenemedi.' });
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 5000);
    }
  }

  async function toggleRule(rule) {
    try {
      await axios.patch(`${API_BASE}/alarm-rules/${rule.id}?enabled=${!rule.enabled}`, {}, { headers });
      refresh();
    } catch {
      setToast({ ok: false, text: 'Güncellenemedi.' });
    }
  }

  async function deleteRule(rule) {
    if (!window.confirm(`"${rule.label}" alarmı silinsin mi?`)) return;
    try {
      await axios.delete(`${API_BASE}/alarm-rules/${rule.id}`, { headers });
      refresh();
    } catch {
      setToast({ ok: false, text: 'Silinemedi.' });
    }
  }

  const activeCount = (rules || []).filter((r) => r.is_active).length;

  return (
    <SectionCard
      title="Alarmlar"
      right={activeCount > 0 ? (
        <span style={{
          fontSize: 11, fontWeight: 700, color: '#fff', background: 'var(--danger)',
          padding: '3px 9px', borderRadius: 100,
        }}>
          {activeCount} aktif
        </span>
      ) : null}
    >
      {rules === null ? (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Yükleniyor…</div>
      ) : rules.length === 0 ? (
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>
          Henüz alarm tanımlanmadı. Eşik aşımı veya cihazın veri göndermeyi kesmesi durumunda
          e-posta ile uyarı almak için alarm ekleyin.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {rules.map((rule) => (
            <div key={rule.id} style={{
              display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
              padding: '9px 12px', borderRadius: 'var(--radius-sm)',
              border: `1px solid ${rule.is_active ? 'var(--danger)' : 'var(--border)'}`,
              background: rule.is_active ? 'color-mix(in srgb, var(--danger) 8%, var(--surface))' : 'transparent',
              opacity: rule.enabled ? 1 : 0.55,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: rule.is_active ? 'var(--danger)' : (rule.enabled ? 'var(--l2)' : 'var(--muted)'),
              }} />
              <span style={{ fontSize: 13, flex: 1, minWidth: 180 }}>{rule.label}</span>
              {rule.is_active && (
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger)' }}>ŞU AN AKTİF</span>
              )}
              <button type="button" onClick={() => toggleRule(rule)} style={{
                background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                color: 'var(--muted)', textDecoration: 'underline', padding: 0,
              }}>
                {rule.enabled ? 'Duraklat' : 'Etkinleştir'}
              </button>
              <button type="button" onClick={() => deleteRule(rule)} style={{
                background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                color: 'var(--danger)', textDecoration: 'underline', padding: 0,
              }}>
                Sil
              </button>
            </div>
          ))}
        </div>
      )}

      {adding ? (
        <div style={{
          marginTop: 12, padding: 12, borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select value={metric} onChange={(e) => setMetric(e.target.value)}
              style={{ ...inputStyle, width: 'auto', padding: '6px 10px', fontSize: 13 }}>
              {ALARM_METRIC_LIST.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
            {!isOffline && (
              <>
                <select value={phase} onChange={(e) => setPhase(e.target.value)}
                  style={{ ...inputStyle, width: 'auto', padding: '6px 10px', fontSize: 13 }}>
                  <option value="any">Herhangi bir faz</option>
                  <option value="L1">L1</option>
                  <option value="L2">L2</option>
                  <option value="L3">L3</option>
                </select>
                <select value={condition} onChange={(e) => setCondition(e.target.value)}
                  style={{ ...inputStyle, width: 'auto', padding: '6px 10px', fontSize: 13 }}>
                  <option value="gt">üstünde</option>
                  <option value="lt">altında</option>
                </select>
              </>
            )}
            <input
              type="number" step={metricDef?.step} value={value}
              placeholder={metricDef?.placeholder}
              onChange={(e) => setValue(e.target.value)}
              style={{ ...inputStyle, width: 110, padding: '6px 10px', fontSize: 13 }}
            />
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>{metricDef?.unit}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" disabled={busy || value === ''} onClick={addRule} style={{
              padding: '6px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
              background: 'var(--bg)', color: 'var(--ink)', fontSize: 12, fontWeight: 600,
              cursor: (busy || value === '') ? 'default' : 'pointer', opacity: (busy || value === '') ? 0.5 : 1,
            }}>
              {busy ? 'Ekleniyor…' : 'Alarmı Ekle'}
            </button>
            <button type="button" onClick={() => { setAdding(false); setValue(''); }} style={{
              padding: '6px 14px', borderRadius: 'var(--radius-xs)', border: 'none',
              background: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer',
            }}>
              Vazgeç
            </button>
          </div>
        </div>
      ) : (
        <button type="button" onClick={() => setAdding(true)} style={{
          marginTop: 12, padding: '6px 14px', borderRadius: 'var(--radius-xs)',
          border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--ink)',
          fontSize: 12, fontWeight: 600, cursor: 'pointer', width: 'fit-content',
        }}>
          + Alarm Ekle
        </button>
      )}

      {toast && (
        <div style={{ fontSize: 11, marginTop: 8, color: toast.ok ? 'var(--l2)' : 'var(--danger)' }}>{toast.text}</div>
      )}

      {events.length > 0 && (
        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginBottom: 8 }}>Son Alarmlar</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {events.map((ev) => (
              <div key={ev.id} style={{ display: 'flex', gap: 10, fontSize: 12, flexWrap: 'wrap' }}>
                <span className="mono" style={{ color: 'var(--muted)', minWidth: 96 }}>
                  {formatAlarmTime(ev.triggered_at)}
                </span>
                <span style={{ flex: 1, minWidth: 200 }}>{ev.message}</span>
                <span style={{ fontSize: 11, color: ev.resolved_at ? 'var(--l2)' : 'var(--danger)', fontWeight: 600 }}>
                  {ev.resolved_at ? `çözüldü ${formatAlarmTime(ev.resolved_at)}` : 'devam ediyor'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ---------- Cihaz Ayarları: yazma komutları ----------
const DEVICE_COMMAND_LIST = [
  { key: 'reset_energy', label: 'Enerji Sayaçlarını Sıfırla', risk: 'low' },
  { key: 'reset_peaks', label: 'Tepe Değerlerini Sıfırla', risk: 'low' },
  { key: 'reset_demand', label: 'Demand Değerlerini Sıfırla', risk: 'low' },
  { key: 'reset_alarms', label: 'Alarmları Sıfırla', risk: 'low' },
  { key: 'restart', label: 'Cihazı Yeniden Başlat', risk: 'low' },
  { key: 'factory_reset', label: 'Fabrika Ayarlarına Dön', risk: 'high' },
  { key: 'reset_password', label: 'Sistem Şifresini Sıfırla', risk: 'high' },
];

function CommandRow({ token, device, cmd, onDone }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null); // { ok: bool, text: string } | null
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [password, setPassword] = useState('');

  async function send() {
    setLoading(true);
    setToast(null);
    try {
      const body = { command: cmd.key };
      if (cmd.risk === 'high') body.password = password;
      await axios.post(`${API_BASE}/devices/${device.device_id}/command`, body, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setToast({ ok: true, text: 'Komut gönderildi.' });
      onDone?.();
    } catch (err) {
      setToast({ ok: false, text: err.response?.data?.detail || 'Komut gönderilemedi.' });
    } finally {
      setLoading(false);
      setConfirmOpen(false);
      setConfirmText('');
      setPassword('');
      setTimeout(() => setToast(null), 4000);
    }
  }

  const highRisk = cmd.risk === 'high';

  return (
    <div style={{
      padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>
          {cmd.label} {highRisk && <span style={{ color: 'var(--danger)', fontSize: 11, fontWeight: 700 }}>· GERİ ALINAMAZ</span>}
        </span>
        <button
          type="button"
          disabled={loading}
          onClick={() => (highRisk ? setConfirmOpen((o) => !o) : send())}
          style={{
            padding: '6px 14px', borderRadius: "var(--radius-xs)", border: highRisk ? '1px solid var(--danger)' : '1px solid var(--border)',
            background: highRisk ? 'none' : 'var(--bg)', color: highRisk ? 'var(--danger)' : 'var(--ink)',
            fontSize: 12, fontWeight: 600, cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Gönderiliyor…' : highRisk ? (confirmOpen ? 'Vazgeç' : 'Uygula…') : 'Uygula'}
        </button>
      </div>
      {highRisk && confirmOpen && (
        <div style={{ background: 'var(--bg)', borderRadius: "var(--radius-xs)", padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--danger)', lineHeight: 1.5 }}>
            Bu işlem geri alınamaz. Onaylamak için cihazın adını (<strong>{device.name}</strong>) ve hesap şifrenizi aşağıya yazın.
          </span>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={device.name}
            style={{ ...inputStyle, fontSize: 13, padding: '7px 10px' }}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Hesap şifreniz"
            style={{ ...inputStyle, fontSize: 13, padding: '7px 10px' }}
          />
          <button
            type="button"
            disabled={confirmText !== device.name || !password || loading}
            onClick={send}
            style={{
              padding: '8px 12px', borderRadius: "var(--radius-xs)", border: 'none',
              background: 'var(--danger)', color: '#fff', fontSize: 12, fontWeight: 700,
              cursor: (confirmText !== device.name || !password || loading) ? 'default' : 'pointer',
              opacity: (confirmText !== device.name || !password || loading) ? 0.5 : 1,
            }}
          >
            {loading ? 'Gönderiliyor…' : 'Onayla ve Gönder'}
          </button>
        </div>
      )}
      {toast && (
        <span style={{ fontSize: 11, color: toast.ok ? 'var(--l2)' : 'var(--danger)' }}>{toast.text}</span>
      )}
    </div>
  );
}

// Register 221 = Akım Trafo Oranı (Table Index) -- indeks↔gerçek oran (X/5 A) eşlemesi,
// backend'deki CT_RATIO_TABLE ile birebir aynı (kaynak: Parametreler sayfası, "*2* Akım Trafo Tablosu").
const CT_RATIO_TABLE = [
  5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100, 120, 125, 130, 150, 160, 175,
  180, 200, 225, 240, 250, 300, 330, 350, 360, 400, 450, 500, 520, 550, 600, 630, 650,
  700, 730, 750, 800, 900, 1000, 1100, 1200, 1250, 1400, 1500, 1600, 1800, 2000, 2200,
  2400, 2500, 2600, 3000, 3200, 3500, 3600, 4000, 4500, 5000, 5500, 6000, 6500, 7000,
  7500, 8000, 8500, 10000,
];

// ---------- Cihazı tümüyle sil ----------
//
// Ayarların en altında, kendi çerçevesinde duruyor: yanlışlıkla tıklanacak bir
// yerde değil, ama aranınca bulunacak yerde. Onay iki adımlı (cihaz adı +
// hesap şifresi) ve önce SİLİNECEK OLAN GÖSTERİLİYOR -- kullanıcı "cihazı sil"
// ifadesine değil, "146.203 ölçüm, 42 gün" sayısına bakarak onaylıyor.
function DeleteDeviceBox({ token, device, onDeleted }) {
  const [acik, setAcik] = useState(false);
  const [onizleme, setOnizleme] = useState(null);
  const [onayAdi, setOnayAdi] = useState('');
  const [sifre, setSifre] = useState('');
  const [siliniyor, setSiliniyor] = useState(false);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    if (!acik) return;
    let iptal = false;
    axios.get(`${API_BASE}/devices/${device.device_id}/delete-preview`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => { if (!iptal) setOnizleme(res.data); })
      .catch(() => { if (!iptal) setOnizleme(null); });
    return () => { iptal = true; };
  }, [acik, device.device_id, token]);

  async function sil() {
    setSiliniyor(true);
    setHata(null);
    try {
      await axios.post(`${API_BASE}/devices/${device.device_id}/delete`,
        { password: sifre, confirm: onayAdi.trim() },
        { headers: { Authorization: `Bearer ${token}` } });
      // Cihaz listesi yenilenince seçili cihaz kaybolur ve panel kendiliğinden
      // listeye döner -- ayrıca yönlendirme yapmaya gerek yok.
      onDeleted?.();
    } catch (err) {
      setHata(err.response?.data?.detail || 'Cihaz silinemedi.');
      setSiliniyor(false);
    }
  }

  const hazir = onayAdi.trim() === device.name && sifre && !siliniyor;

  return (
    <div style={{
      marginTop: 16, padding: '12px 14px', borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--danger)', display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--danger)' }}>Cihazı Tümüyle Sil</span>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            Cihaz ve tüm ölçüm geçmişi kalıcı olarak silinir. Geri alınamaz.
          </span>
        </div>
        <button
          type="button"
          onClick={() => { setAcik((o) => !o); setHata(null); }}
          style={{
            padding: '6px 14px', borderRadius: 'var(--radius-xs)',
            border: '1px solid var(--danger)', background: 'none', color: 'var(--danger)',
            fontSize: 12, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          {acik ? 'Vazgeç' : 'Sil…'}
        </button>
      </div>

      {acik && (
        <div style={{ background: 'var(--bg)', borderRadius: 'var(--radius-xs)', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {onizleme ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>Silinecek veriler</span>
              <span style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6 }}>
                <strong style={{ color: 'var(--ink)' }}>{onizleme.toplam_satir.toLocaleString('tr-TR')}</strong> kayıt
                {onizleme.gun_sayisi > 0 && <> · <strong style={{ color: 'var(--ink)' }}>{onizleme.gun_sayisi}</strong> günlük geçmiş</>}
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 12px', marginTop: 4 }}>
                {Object.entries(onizleme.tablolar)
                  .filter(([, n]) => n > 0)
                  .map(([tablo, n]) => (
                    <span key={tablo} style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {TABLO_ADLARI[tablo] || tablo}: {n.toLocaleString('tr-TR')}
                    </span>
                  ))}
              </div>
            </div>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Silinecek veriler hesaplanıyor…</span>
          )}

          <span style={{ fontSize: 11, color: 'var(--danger)', lineHeight: 1.5 }}>
            Onaylamak için cihazın adını (<strong>{device.name}</strong>) ve hesap şifrenizi yazın.
          </span>
          <input
            type="text"
            value={onayAdi}
            onChange={(e) => setOnayAdi(e.target.value)}
            placeholder={device.name}
            style={{ ...inputStyle, fontSize: 13, padding: '7px 10px' }}
          />
          <input
            type="password"
            value={sifre}
            onChange={(e) => setSifre(e.target.value)}
            placeholder="Hesap şifreniz"
            style={{ ...inputStyle, fontSize: 13, padding: '7px 10px' }}
          />
          <button
            type="button"
            disabled={!hazir}
            onClick={sil}
            style={{
              padding: '9px 12px', borderRadius: 'var(--radius-xs)', border: 'none',
              background: 'var(--danger)', color: '#fff', fontSize: 12, fontWeight: 700,
              cursor: hazir ? 'pointer' : 'default', opacity: hazir ? 1 : 0.5,
            }}
          >
            {siliniyor ? 'Siliniyor…' : 'Cihazı ve tüm geçmişini sil'}
          </button>
          {hata && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{hata}</span>}
        </div>
      )}
    </div>
  );
}

// Önizlemedeki tablo adları teknik; kullanıcı "device_peaks" değil "tepe
// değerleri" görmeli.
const TABLO_ADLARI = {
  measurements: 'Ölçümler',
  device_energy: 'Enerji kayıtları',
  device_stats: 'Sistem özeti',
  device_peaks: 'Tepe değerleri',
  device_demand: 'Demand',
  device_harmonics: 'Harmonikler',
  device_info: 'Cihaz bilgisi',
  device_settings: 'Ayarlar',
  device_tariff: 'Tarife',
  alarm_events: 'Alarm kayıtları',
  alarm_rules: 'Alarm kuralları',
};

function WifiBox({ token, device, connected }) {
  const [ssid, setSsid] = useState('');
  const [pass, setPass] = useState('');
  const [acik, setAcik] = useState(false);
  const [durum, setDurum] = useState(null); // 'gonderiliyor' | 'bekleniyor' | null
  const [toast, setToast] = useState(null);

  async function gonder() {
    setDurum('gonderiliyor');
    setToast(null);
    try {
      await axios.post(`${API_BASE}/devices/${device.device_id}/wifi`,
        { ssid: ssid.trim(), password: pass },
        { headers: { Authorization: `Bearer ${token}` } });
      setPass('');
      setDurum('bekleniyor');
      sonucuBekle();
    } catch (err) {
      setDurum(null);
      setToast({ ok: false, text: err.response?.data?.detail || 'Gönderilemedi.' });
    }
  }

  // Cihaz ag degistirirken baglantisi kopuyor; sonuc ancak yeniden baglandiginda
  // gelebiliyor. Bu yuzden bir sure yoklamak gerekiyor -- tek seferlik istek
  // her zaman "henuz sonuc yok" doner.
  function sonucuBekle() {
    const bitis = Date.now() + 90000;
    const timer = setInterval(async () => {
      try {
        const res = await axios.get(`${API_BASE}/devices/${device.device_id}/wifi`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.data?.ok === true) {
          clearInterval(timer);
          setDurum(null);
          setToast({ ok: true, text: 'Cihaz yeni ağa bağlandı.' });
        } else if (res.data?.ok === false) {
          clearInterval(timer);
          setDurum(null);
          setToast({ ok: false, text: res.data.hata || 'Bağlanamadı, cihaz eski ağına döndü.' });
        }
      } catch { /* yoklama basarisiz olabilir, devam */ }
      if (Date.now() > bitis) {
        clearInterval(timer);
        setDurum(null);
        setToast({ ok: false, text: 'Cihazdan yanıt gelmedi. Yeni ağa bağlanamadıysa eski ağına dönmüş olmalı.' });
      }
    }, 5000);
  }

  return (
    <div style={{
      padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <button onClick={() => setAcik((o) => !o)} style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%',
        background: 'none', border: 'none', cursor: 'pointer', padding: 0,
        fontSize: 13, fontWeight: 600, color: 'var(--ink)',
      }}>
        <span>WiFi Ağını Değiştir</span>
        <span style={{ color: 'var(--muted)' }}>{acik ? '▲' : '▼'}</span>
      </button>

      {acik && (
        <>
          <span style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
            Cihaz yeni ağa bağlanmayı dener. <b>Bağlanamazsa eski ağına geri döner</b> — yeni
            bilgiler yalnızca bağlantı kurulduktan sonra kaydedilir. Cihaz bu sırada
            bir-iki dakika çevrimdışı görünür.
          </span>

          {!connected && (
            <span style={{ fontSize: 11, color: 'var(--warn)' }}>
              Cihaz şu anda çevrimdışı. WiFi ayarı yalnızca bağlı bir cihaza gönderilebilir.
            </span>
          )}

          <input
            value={ssid}
            onChange={(e) => setSsid(e.target.value)}
            placeholder="Ağ adı (SSID)"
            maxLength={32}
            style={{
              padding: '7px 9px', borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border)', background: 'var(--bg)',
              color: 'var(--ink)', fontSize: 13,
            }}
          />
          <input
            type="password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            placeholder="Parola (açık ağ için boş bırakın)"
            maxLength={63}
            style={{
              padding: '7px 9px', borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border)', background: 'var(--bg)',
              color: 'var(--ink)', fontSize: 13,
            }}
          />
          <button
            onClick={gonder}
            disabled={!connected || !ssid.trim() || durum !== null}
            style={{
              alignSelf: 'flex-start', padding: '7px 14px', borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border)', cursor: (!connected || !ssid.trim() || durum) ? 'not-allowed' : 'pointer',
              background: 'var(--surface)', color: 'var(--ink)', fontSize: 13,
              opacity: (!connected || !ssid.trim() || durum) ? 0.5 : 1,
            }}
          >
            {durum === 'bekleniyor' ? 'Cihaz bağlanıyor…' : durum ? 'Gönderiliyor…' : 'Gönder'}
          </button>

          {toast && (
            <span style={{ fontSize: 12, color: toast.ok ? 'var(--accent)' : 'var(--danger)' }}>
              {toast.text}
            </span>
          )}
        </>
      )}
    </div>
  );
}

// Tarife faturadan doğrulanmadıysa, tutar gösteren HER yerde bunu açıkça söyle.
// Bu boşluk gerçek bir hataya yol açtı: geliştirme sırasında girilen uydurma
// rakamlar panelde günlerce gerçek fatura tutarı gibi durdu. Sayının kendisinden
// çok, nereden geldiğini bilememek tehlikeli.
function TarifeDogrulanmadiUyarisi({ tariff }) {
  if (!tariff || tariff.tariff_verified) return null;
  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-start',
      fontSize: 12, marginBottom: 14, padding: '9px 12px',
      borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--warn)', color: 'var(--ink)',
    }}>
      <span aria-hidden="true">⚠</span>
      <span>
        <b>Tarife doğrulanmadı — tutarlar tahminidir.</b>{' '}
        {tariff.tariff_source ? <>Kaynak: {tariff.tariff_source}. </> : null}
        Faturanızdaki gerçek birim fiyatları <b>Tarife</b> bölümünden girip
        “faturadan doğrulandı” işaretini koyduğunuzda bu uyarı kalkar.
      </span>
    </div>
  );
}

function CtRatioBox({ token, device, ctRatio, onSaved }) {
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (ctRatio != null) setSelected(String(ctRatio));
  }, [ctRatio]);

  const dirty = selected !== '' && Number(selected) !== ctRatio;

  async function save() {
    setLoading(true);
    setToast(null);
    try {
      await axios.post(`${API_BASE}/devices/${device.device_id}/ct-ratio`, { value: Number(selected) }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setToast({ ok: true, text: 'Gönderildi. Cihazdan onay birkaç saniye içinde gelecek.' });
      onSaved?.();
    } catch (err) {
      setToast({ ok: false, text: err.response?.data?.detail || 'Gönderilemedi.' });
    } finally {
      setLoading(false);
      setTimeout(() => setToast(null), 5000);
    }
  }

  return (
    <div style={{
      padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Akım Trafo Oranı</span>
        <span className="mono" style={{ fontSize: 13, color: 'var(--muted)' }}>
          {ctRatio != null ? `${ctRatio}/5 A` : '—'}
        </span>
      </div>
      <span style={{ fontSize: 11, color: 'var(--muted)' }}>
        Bu değer cihazın harici akım trafosunun gerçek oranıyla eşleşmelidir (harici trafo yoksa 5/5 A). Yanlış değer, tüm akım/güç/enerji ölçümlerinin yanlış ölçeklenmesine yol açar.
      </span>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          style={{ ...inputStyle, width: 'auto', padding: '6px 10px', fontSize: 13 }}
        >
          {ctRatio == null && <option value="">Seçin…</option>}
          {CT_RATIO_TABLE.map((v) => (
            <option key={v} value={v}>{v}/5 A</option>
          ))}
        </select>
        <button
          type="button"
          disabled={!dirty || loading}
          onClick={save}
          style={{
            padding: '6px 14px', borderRadius: "var(--radius-xs)", border: '1px solid var(--border)',
            background: 'var(--bg)', color: 'var(--ink)', fontSize: 12, fontWeight: 600,
            cursor: (!dirty || loading) ? 'default' : 'pointer', opacity: (!dirty || loading) ? 0.5 : 1,
          }}
        >
          {loading ? 'Gönderiliyor…' : 'Kaydet'}
        </button>
      </div>
      {toast && (
        <span style={{ fontSize: 11, color: toast.ok ? 'var(--l2)' : 'var(--danger)' }}>{toast.text}</span>
      )}
    </div>
  );
}

function FirmwareBox({ token, device, firmware, onUpdated }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  if (!firmware || !firmware.latest_version) return null;

  const { current_version, latest_version, update_available } = firmware;

  async function update() {
    setLoading(true);
    setToast(null);
    try {
      await axios.post(`${API_BASE}/devices/${device.device_id}/ota`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setToast({ ok: true, text: 'Güncelleme cihaza gönderildi. Cihaz birkaç dakika içinde yeniden başlayıp yeni sürüme geçecek.' });
      onUpdated?.();
    } catch (err) {
      setToast({ ok: false, text: err.response?.data?.detail || 'Güncelleme gönderilemedi.' });
    } finally {
      setLoading(false);
      setTimeout(() => setToast(null), 8000);
    }
  }

  return (
    <div style={{
      padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Firmware Sürümü</span>
        <span className="mono" style={{ fontSize: 13, color: 'var(--muted)' }}>
          {current_version || '—'}{update_available ? ` → ${latest_version}` : ''}
        </span>
      </div>
      {update_available ? (
        <>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            Yeni bir sürüm mevcut. Güncelleme sırasında cihaz kısa süreliğine yeniden başlayacak, ölçüm ve komutlar bu sürede kesintiye uğrayabilir.
          </span>
          <button
            type="button"
            disabled={loading}
            onClick={update}
            style={{
              padding: '6px 14px', borderRadius: "var(--radius-xs)", border: '1px solid var(--border)',
              background: 'var(--bg)', color: 'var(--ink)', fontSize: 12, fontWeight: 600,
              cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.5 : 1, width: 'fit-content',
            }}
          >
            {loading ? 'Gönderiliyor…' : 'Güncelle'}
          </button>
        </>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>Cihaz güncel.</span>
      )}
      {toast && (
        <span style={{ fontSize: 11, color: toast.ok ? 'var(--l2)' : 'var(--danger)' }}>{toast.text}</span>
      )}
    </div>
  );
}

/* ---------- Yön H: analog kadran ---------- */
const GAUGE_TICKS = [
  [18, 88, 26, 88], [22.7, 64.3, 30.1, 67.3], [36.2, 44.2, 41.8, 49.8], [56.3, 30.7, 59.3, 38.1],
  [80, 26, 80, 34], [103.7, 30.7, 100.7, 38.1], [123.8, 44.2, 118.2, 49.8], [137.3, 64.3, 129.9, 67.3], [142, 88, 134, 88],
];

function gaugeNeedlePoint(value, min, max, len) {
  const f = Math.max(0, Math.min(1, max > min ? (value - min) / (max - min) : 0));
  const angle = Math.PI - f * Math.PI;
  return { x: 80 + len * Math.cos(angle), y: 88 - len * Math.sin(angle) };
}

function AnalogGauge({ value, min, max, label, unit, size = 130, big = false }) {
  const needle = gaugeNeedlePoint(value ?? min, min, max, big ? 52 : 46);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size * 0.64} viewBox="0 0 160 100">
        <path d="M 18 88 A 62 62 0 0 1 142 88" fill="none" stroke="var(--accent)" strokeOpacity="0.55" strokeWidth={big ? 16 : 12} />
        <circle cx="80" cy="60" r="52" fill="var(--gauge-face)" />
        <circle cx="80" cy="60" r="52" fill="none" stroke="var(--gauge-ink)" strokeOpacity="0.25" strokeWidth="1" />
        <g stroke="var(--gauge-ink)" strokeWidth={big ? 1.6 : 1.3} opacity="0.75">
          {GAUGE_TICKS.map((t, idx) => (
            <line key={idx} x1={t[0]} y1={t[1]} x2={t[2]} y2={t[3]} />
          ))}
        </g>
        <text x="12" y="98" fontFamily="var(--font-mono)" fontSize="8" fill="var(--gauge-ink)">{fmt(min, 0)}</text>
        <text x="70" y="20" fontFamily="var(--font-mono)" fontSize="8" fill="var(--gauge-ink)">{fmt((min + max) / 2, 0)}</text>
        <text x="122" y="98" fontFamily="var(--font-mono)" fontSize="8" fill="var(--gauge-ink)">{fmt(max, 0)}</text>
        <line x1="80" y1="88" x2={needle.x} y2={needle.y} stroke="var(--gauge-needle)" strokeWidth={big ? 2.6 : 2.1} strokeLinecap="round" />
        <circle cx="80" cy="88" r={big ? 6 : 5} fill="var(--accent)" stroke="var(--gauge-ink)" strokeOpacity="0.3" strokeWidth="1.2" />
      </svg>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: big ? 12.5 : 11, color: 'var(--muted)', marginTop: 4, textAlign: 'center' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: big ? 15 : 13, color: 'var(--ink)' }}>
        {value != null ? fmt(value, Math.abs(max - min) > 100 ? 0 : 1) : '—'}{unit ? ` ${unit}` : ''}
      </div>
    </div>
  );
}

function GaugeCluster({ latest, firmware }) {
  const totalP = (latest.p1 ?? 0) + (latest.p2 ?? 0) + (latest.p3 ?? 0);
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-card)',
      padding: '26px 28px', marginBottom: 28,
    }}>
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', justifyContent: 'space-around' }}>
        <AnalogGauge value={totalP} min={0} max={2000} label="TOPLAM AKTİF GÜÇ" unit="W" size={180} big />
        <AnalogGauge value={latest.v1} min={200} max={240} label="L1" unit="V" size={130} />
        <AnalogGauge value={latest.v2} min={200} max={240} label="L2" unit="V" size={130} />
        <AnalogGauge value={latest.v3} min={200} max={240} label="L3" unit="V" size={130} />
      </div>
      <div style={{
        display: 'flex', gap: 22, marginTop: 22, paddingTop: 18,
        borderTop: '1px solid var(--border)', flexWrap: 'wrap', fontSize: 12.5, color: 'var(--muted)',
      }}>
        <span>Frekans: <b style={{ color: 'var(--ink)', fontFamily: 'var(--font-mono)' }}>{fmt(latest.f1, 2)} Hz</b></span>
        <span>Nötr: <b style={{ color: 'var(--ink)', fontFamily: 'var(--font-mono)' }}>{fmt(latest.vN, 1)} V</b></span>
        {firmware && <span>Firmware: <b style={{ color: 'var(--ink)', fontFamily: 'var(--font-mono)' }}>{firmware.current_version ?? '—'}</b></span>}
      </div>
    </div>
  );
}

/* ---------- Yön F: fazör diyagramı ---------- */
function phasorPoint(angleDeg, radius, cx = 110, cy = 110) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
}

const PHASOR_PHASES = [
  { key: '1', label: 'L1', color: 'var(--l1)', angle: -90 },
  { key: '2', label: 'L2', color: 'var(--l2)', angle: 30 },
  { key: '3', label: 'L3', color: 'var(--l3)', angle: 150 },
];

function PhasorStat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 4 }}>{label}</div>
      <div className="mono" style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{value}</div>
    </div>
  );
}

function PhasorDiagram({ latest, energy, firmware }) {
  const VREF = 250, IREF = 10;
  const totalP = (latest.p1 ?? 0) + (latest.p2 ?? 0) + (latest.p3 ?? 0);
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-card)',
      padding: '28px 32px', marginBottom: 28,
    }}>
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center' }}>
        <svg width="240" height="240" viewBox="0 0 220 220">
          <circle cx="110" cy="110" r="85" fill="none" stroke="var(--border)" strokeWidth="1" />
          <circle cx="110" cy="110" r="56" fill="none" stroke="var(--border)" strokeWidth="1" />
          <circle cx="110" cy="110" r="28" fill="none" stroke="var(--border)" strokeWidth="1" />
          {PHASOR_PHASES.map((ph) => {
            const v = latest[`v${ph.key}`] ?? 0;
            const i = latest[`i${ph.key}`] ?? 0;
            const pf = latest[`pf${ph.key}`];
            const phi = pf != null ? (Math.acos(Math.max(-1, Math.min(1, pf))) * 180) / Math.PI : 0;
            const rV = 85 * Math.max(0.12, Math.min(1, v / VREF));
            const rI = 62 * Math.max(0.08, Math.min(1, i / IREF));
            const tipV = phasorPoint(ph.angle, rV);
            const tipI = phasorPoint(ph.angle + phi, rI);
            return (
              <g key={ph.key}>
                <line x1="110" y1="110" x2={tipI.x} y2={tipI.y} stroke={ph.color} strokeWidth="1.4" strokeDasharray="3 3" opacity="0.55" />
                <line x1="110" y1="110" x2={tipV.x} y2={tipV.y} stroke={ph.color} strokeWidth="2.6" strokeLinecap="round" />
                <circle cx={tipV.x} cy={tipV.y} r="4.5" fill={ph.color} />
              </g>
            );
          })}
          <circle cx="110" cy="110" r="4" fill="var(--ink)" />
        </svg>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 190 }}>
          {PHASOR_PHASES.map((ph) => (
            <div key={ph.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: ph.color, flexShrink: 0 }} />
              <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.4 }}>
                <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--ink)' }}>{ph.label}</span>
                {'  '}<span className="mono" style={{ fontWeight: 700, color: 'var(--ink)' }}>{fmt(latest[`v${ph.key}`], 1)} V</span>
                <br />{fmt(latest[`i${ph.key}`], 3)} A · cos φ {fmt(latest[`pf${ph.key}`], 2)}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 24, marginTop: 24, paddingTop: 18, borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
        <PhasorStat label="Toplam Güç" value={`${fmt(totalP, 0)} W`} />
        <PhasorStat label="Bugün" value={formatKwh(energy?.active_wh_tuketim ?? 0)} />
        <PhasorStat label="Frekans" value={`${fmt(latest.f1, 2)} Hz`} />
        {firmware && <PhasorStat label="Firmware" value={firmware.current_version ?? '—'} />}
      </div>
    </div>
  );
}

// ======================= GA1202 Reaktif Güç Kontrol Rölesi =======================
//
// Röle, güç analizörüyle AYNI ölçüm çekirdeğini paylaşıyor (V/I/P/Q/S/F) --
// o yüzden "Canlı" sekmesi olduğu gibi çalışıyor. Buradaki bölümler rölenin
// FARKLI olan tarafı: kompanzasyon kademeleri, SVC, ve cihazın ~105 ayarı.

const RELAY_PREFIX = 'ga1202';
const isRelayDevice = (deviceId) => (deviceId || '').startsWith(`${RELAY_PREFIX}-`);

/** Röle kategorilerini çeker; WebSocket'ten canlı güncelleme de alır. */
function useRelayData(token, deviceId) {
  const [snapshots, setSnapshots] = useState({});
  const [tanimlar, setTanimlar] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  const yenile = useCallback(async () => {
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const res = await axios.get(`${API_BASE}/relay/snapshots?device_id=${encodeURIComponent(deviceId)}`, { headers });
      setSnapshots(res.data || {});
    } catch {
      /* erişim/ağ hatası: kartlar "veri bekleniyor" gösterir */
    } finally {
      setYukleniyor(false);
    }
  }, [token, deviceId]);

  useEffect(() => {
    yenile();
    // Parametreler 5 dakikada bir, tepe değerleri dakikada bir yayınlanıyor;
    // 20 saniyelik yoklama ikisini de makul sürede yakalar. WebSocket push'u
    // zaten anlık geliyor, bu yalnızca emniyet ağı (sayfa arkada kalıp
    // soket düşerse kartlar yine de tazelenir).
    const t = setInterval(yenile, 20000);
    return () => clearInterval(t);
  }, [yenile]);

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token}` };
    axios.get(`${API_BASE}/relay/tanimlar`, { headers })
      .then((r) => setTanimlar(r.data))
      .catch(() => setTanimlar(null));
  }, [token]);

  // Backend her yeni kategori mesajında WebSocket'e de itiyor.
  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}?token=${token}&device_id=${encodeURIComponent(deviceId)}`);
    ws.onmessage = (event) => {
      const mesaj = JSON.parse(event.data);
      if (mesaj.type !== 'relay_snapshot') return;
      setSnapshots((onceki) => ({
        ...onceki,
        [mesaj.kategori]: { data: mesaj.data, updated_at: new Date().toISOString() },
      }));
    };
    return () => ws.close();
  }, [token, deviceId]);

  return { snapshots, tanimlar, yukleniyor, yenile };
}

function RelayStat({ etiket, deger, birim, vurgu }) {
  return (
    <div style={{
      background: 'var(--bg)', borderRadius: 'var(--radius-sm)', padding: '10px 12px',
      minWidth: 130, flex: '1 1 130px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>{etiket}</div>
      <div className="mono" style={{
        fontSize: 16, fontWeight: 600, color: vurgu || 'var(--ink)',
      }}>
        {deger}{birim ? <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>{birim}</span> : null}
      </div>
    </div>
  );
}

function RelayVeriYok({ ne }) {
  return (
    <div style={{ fontSize: 13, color: 'var(--muted)' }}>
      {ne} verisi henüz gelmedi — cihaz bu bloğu okuyup gönderdiğinde burada görünecek.
    </div>
  );
}

const bitAcikMi = (deger, index) => Number.isFinite(deger) && ((deger >> index) & 1) === 1;

/** Kompanzasyon: rölenin asıl işi. Tek bakışta "hangi kademe devrede". */
function RelayKompanzasyon({ snapshots, tanimlar }) {
  const kademeler = snapshots.kademeler?.data;
  const live = snapshots.live?.data;
  if (!kademeler) return <SectionCard title="Kompanzasyon"><RelayVeriYok ne="Kademe" /></SectionCard>;

  const durumAdi = tanimlar?.cihaz_durumlari?.[kademeler.cihaz_durumu] ?? `Bilinmiyor (${kademeler.cihaz_durumu})`;
  const kompanzasyonda = kademeler.cihaz_durumu === 3;

  // Cihaz yapılandırılmamışken bu alan anlamsız büyük değerler dönebiliyor
  // (sahada 32786 görüldü). Listeyi ona göre çizmek yüzlerce boş kutu demek.
  const hamSayi = kademeler.kademe_sayisi;
  const kademeSayisi = Number.isFinite(hamSayi) && hamSayi >= 0 && hamSayi <= 32 ? hamSayi : null;
  const detaylar = Array.isArray(kademeler.kademeler) ? kademeler.kademeler : [];

  return (
    <SectionCard
      title="Kompanzasyon"
      right={
        <span style={{
          fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
          background: kompanzasyonda ? 'rgba(34,197,94,0.12)' : 'var(--bg)',
          color: kompanzasyonda ? '#16a34a' : 'var(--muted)',
        }}>
          {durumAdi}
        </span>
      }
    >
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <RelayStat etiket="Kademe Sayısı" deger={kademeSayisi ?? '—'} />
        <RelayStat etiket="Kondansatör Gücü L1" deger={fmt(kademeler.toplam_kondansator_guc_l1, 0)} birim="VAr" />
        <RelayStat etiket="Kondansatör Gücü L2" deger={fmt(kademeler.toplam_kondansator_guc_l2, 0)} birim="VAr" />
        <RelayStat etiket="Kondansatör Gücü L3" deger={fmt(kademeler.toplam_kondansator_guc_l3, 0)} birim="VAr" />
        {live && <RelayStat etiket="Hedef Cos φ (L1)" deger={fmt(live.hedef_cos_l1, 3)} />}
      </div>

      {kademeSayisi === null && (
        <div style={{
          fontSize: 12, color: 'var(--warn)', background: 'rgba(245,158,11,0.10)',
          borderRadius: 'var(--radius-sm)', padding: '8px 10px', marginBottom: 14,
        }}>
          Cihaz kademe sayısı olarak beklenmeyen bir değer bildiriyor ({String(hamSayi)}).
          Kademeler büyük olasılıkla henüz tanıtılmamış — “Ayarlar” sekmesindeki
          “Kademe Tanıma Başlat” komutuyla tanıtabilirsiniz.
        </div>
      )}

      {kademeSayisi > 0 && (
        <>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>Kademe durumları</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
            {Array.from({ length: kademeSayisi }, (_, i) => {
              const acik = bitAcikMi(kademeler.kademe_durumlari, i);
              const hatali = bitAcikMi(kademeler.hatali_kademe_durumu, i);
              const iptal = bitAcikMi(kademeler.kademe_iptal_durumu, i);
              const renk = hatali ? 'var(--danger)' : iptal ? 'var(--warn)' : acik ? '#22c55e' : 'var(--border)';
              const baslik = hatali ? 'Arızalı' : iptal ? 'İptal' : acik ? 'Devrede' : 'Devre dışı';
              return (
                <div key={i} title={`Kademe ${i + 1}: ${baslik}`} style={{
                  width: 42, height: 42, borderRadius: 'var(--radius-sm)',
                  border: `2px solid ${renk}`,
                  background: acik && !hatali && !iptal ? 'rgba(34,197,94,0.12)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 600, color: renk === 'var(--border)' ? 'var(--muted)' : renk,
                }}>
                  {i + 1}
                </div>
              );
            })}
          </div>
        </>
      )}

      {detaylar.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
                {['Kademe', 'Güç L1', 'Güç L2', 'Güç L3', 'Çalışma', 'Anahtarlama'].map((h) => (
                  <th key={h} style={{ padding: '6px 8px', fontWeight: 500, borderBottom: '1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detaylar.map((k, i) => (
                <tr key={i}>
                  <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{i + 1}</td>
                  <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{fmt(k.guc_l1, 0)}</td>
                  <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{fmt(k.guc_l2, 0)}</td>
                  <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{fmt(k.guc_l3, 0)}</td>
                  <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{formatDuration((k.calisma_suresi || 0) * 1000)}</td>
                  <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{k.anahtarlama_sayisi ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

/** Cihazın kendi sağlığı: sıcaklık, pil, besleme, SVC, jeneratör. */
function RelayCihazDurumu({ snapshots }) {
  const live = snapshots.live?.data;
  if (!live) return null;
  return (
    <SectionCard title="Röle Durumu">
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <RelayStat etiket="Sıcaklık" deger={fmt(live.sicaklik, 1)} birim="°C"
          vurgu={live.sicaklik > 70 ? 'var(--danger)' : undefined} />
        <RelayStat etiket="Pil Gerilimi" deger={fmt(live.pil_gerilimi, 3)} birim="V"
          vurgu={live.pil_gerilimi < 2.5 ? 'var(--warn)' : undefined} />
        <RelayStat etiket="İç Besleme" deger={fmt(live.cihaz_ic_besleme, 0)} birim="mV" />
        <RelayStat etiket="SVC Durumu" deger={live.svc_durum ?? '—'} />
        <RelayStat etiket="Jeneratör" deger={live.jenerator_durumu === 1 ? 'Devrede' : live.jenerator_durumu === 0 ? 'Devre dışı' : '—'} />
      </div>
    </SectionCard>
  );
}

const TOPLAM_SATIRLARI = [
  ['Toplam Aktif Güç', 'p_toplam', 0, 'W'],
  ['Toplam Reaktif Güç', 'q_toplam', 0, 'VAr'],
  ['Toplam Endüktif Güç', 'ql_toplam', 0, 'VAr'],
  ['Toplam Kapasitif Güç', 'qc_toplam', 0, 'VAr'],
  ['Toplam Görünür Güç', 's_toplam', 0, 'VA'],
  ['Ortalama Akım', 'i_ort', 0, 'A'],
  ['Ortalama Aktif Güç', 'p_ort', 0, 'W'],
  ['Ortalama Cos φ', 'cos_ort', 3, ''],
  ['Ortalama Tan φ', 'tan_ort', 3, ''],
  ['Ortalama PF', 'pf_ort', 3, ''],
];

function RelayToplam({ snapshots }) {
  const [yon, setYon] = useState('tuketim');
  const d = snapshots.toplam?.data;
  return (
    <SectionCard
      title="Toplam ve Ortalama Değerler"
      right={<TabToggle options={[['tuketim', 'Tüketim'], ['uretim', 'Üretim']]} value={yon} onChange={setYon} />}
    >
      {!d ? <RelayVeriYok ne="Toplam/ortalama" /> : (
        <>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
            {TOPLAM_SATIRLARI.map(([etiket, anahtar, basamak, birim]) => (
              <RelayStat key={anahtar} etiket={etiket} deger={fmt(d[`${anahtar}_${yon}`], basamak)} birim={birim} />
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>Yöne bağlı olmayanlar</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <RelayStat etiket="Ortalama Gerilim (L-N)" deger={fmt(d.v_ort_ln, 1)} birim="V" />
            <RelayStat etiket="Ortalama Gerilim (L-L)" deger={fmt(d.v_ort_ll, 1)} birim="V" />
            <RelayStat etiket="Ortalama Frekans" deger={fmt(d.f_ort, 2)} birim="Hz" />
            <RelayStat etiket="Ortalama THDI" deger={fmt(d.thdi_ort, 1)} birim="%" />
            <RelayStat etiket="Ortalama THDV" deger={fmt(d.thdv_ort, 1)} birim="%" />
          </div>
        </>
      )}
    </SectionCard>
  );
}

// [başlık, kök, ekler, ondalık, birim, negatifOlabilir]
const TEPE_GRUPLARI = [
  ['Gerilim (L-N)', 'v_ln', ['1', '2', '3'], 1, 'V', false],
  ['Gerilim (L-L)', 'v_ll', ['12', '23', '31'], 1, 'V', false],
  ['Akım', 'i', ['1', '2', '3'], 0, 'A', false],
  ['Aktif Güç', 'p', ['1', '2', '3'], 0, 'W', true],
  ['Reaktif Güç', 'q', ['1', '2', '3'], 0, 'VAr', true],
  ['Görünür Güç', 's', ['1', '2', '3'], 0, 'VA', false],
  ['THDV', 'thdv', ['1', '2', '3'], 1, '%', false],
  ['THDI', 'thdi', ['1', '2', '3'], 1, '%', false],
];

/** Cihaz, henüz tepe kaydı yokken sayaçları "boş" işaretçilerle döndürüyor:
 *  min tarafı INT32_MAX, max tarafı INT32_MIN, bazı alanlarda -1. Bunları ham
 *  göstermek panelde "-2147483648 A" gibi bir değer demek olurdu -- kullanıcı
 *  bunu ölçüm sanır. Henüz veri yoksa "—" daha dürüst. */
function tepeFmt(v, basamak, negatifOlabilir) {
  if (v == null || Math.abs(v) >= 2e9) return '—';
  if (!negatifOlabilir && v < 0) return '—';
  return fmt(v, basamak);
}

function RelayTepe({ snapshots }) {
  const [yon, setYon] = useState('tuketim');
  const d = snapshots[`tepe_${yon}`]?.data;
  return (
    <SectionCard
      title="Tepe Değerleri (Min / Max)"
      right={<TabToggle options={[['tuketim', 'Tüketim'], ['uretim', 'Üretim']]} value={yon} onChange={setYon} />}
    >
      {!d ? <RelayVeriYok ne="Tepe değeri" /> : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
                {['Büyüklük', 'Faz', 'Min', 'Max'].map((h) => (
                  <th key={h} style={{ padding: '6px 8px', fontWeight: 500, borderBottom: '1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TEPE_GRUPLARI.flatMap(([baslik, kok, ekler, basamak, birim, negatifOlabilir]) =>
                ekler.map((ek, idx) => (
                  <tr key={`${kok}-${ek}`}>
                    <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', color: idx === 0 ? 'var(--ink)' : 'var(--muted)' }}>
                      {idx === 0 ? baslik : ''}
                    </td>
                    <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{ek}</td>
                    <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>
                      {tepeFmt(d[`${kok}_min_${ek}`], basamak, negatifOlabilir)} {birim}
                    </td>
                    <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>
                      {tepeFmt(d[`${kok}_max_${ek}`], basamak, negatifOlabilir)} {birim}
                    </td>
                  </tr>
                ))
              )}
              <tr>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Frekans</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>—</td>
                <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{tepeFmt(d.f_min, 2, false)} Hz</td>
                <td className="mono" style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{tepeFmt(d.f_max, 2, false)} Hz</td>
              </tr>
              <tr>
                <td style={{ padding: '6px 8px' }}>Dengesizlik (V / I)</td>
                <td style={{ padding: '6px 8px' }}>—</td>
                <td className="mono" style={{ padding: '6px 8px' }}>{tepeFmt(d.v_dengesizlik_min, 1, false)} / {tepeFmt(d.i_dengesizlik_min, 1, false)} %</td>
                <td className="mono" style={{ padding: '6px 8px' }}>{tepeFmt(d.v_dengesizlik_max, 1, false)} / {tepeFmt(d.i_dengesizlik_max, 1, false)} %</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

const ENERJI_SATIRLARI = [
  ['Toplam Aktif', 'aktif_toplam', 'kWh'],
  ['Toplam Endüktif', 'enduktif_toplam', 'kVArh'],
  ['Toplam Kapasitif', 'kapasitif_toplam', 'kVArh'],
  ['Aktif L1', 'aktif_l1', 'kWh'], ['Aktif L2', 'aktif_l2', 'kWh'], ['Aktif L3', 'aktif_l3', 'kWh'],
  ['Endüktif L1', 'enduktif_l1', 'kVArh'], ['Endüktif L2', 'enduktif_l2', 'kVArh'], ['Endüktif L3', 'enduktif_l3', 'kVArh'],
  ['Kapasitif L1', 'kapasitif_l1', 'kVArh'], ['Kapasitif L2', 'kapasitif_l2', 'kVArh'], ['Kapasitif L3', 'kapasitif_l3', 'kVArh'],
];

function RelayEnerji({ snapshots }) {
  const [yon, setYon] = useState('tuketim');
  const d = snapshots[`enerji_${yon}`]?.data;
  return (
    <SectionCard
      title="Enerji Sayaçları"
      right={<TabToggle options={[['tuketim', 'Tüketim'], ['uretim', 'Üretim']]} value={yon} onChange={setYon} />}
    >
      {!d ? <RelayVeriYok ne="Enerji" /> : (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {ENERJI_SATIRLARI.map(([etiket, anahtar, birim]) => (
            <RelayStat key={anahtar} etiket={etiket} deger={fmt(d[anahtar], 0)} birim={birim} />
          ))}
        </div>
      )}
    </SectionCard>
  );
}

/** Ayarlar: ~105 parametre, gruplanmış; yazılabilir olanlar düzenlenebilir. */
function RelayAyarlar({ token, deviceId, snapshots, tanimlar, onYenile }) {
  const [duzenlenen, setDuzenlenen] = useState(null); // anahtar
  const [taslak, setTaslak] = useState('');
  const [mesaj, setMesaj] = useState(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const degerler = snapshots.parametreler?.data;

  if (!tanimlar) return <SectionCard title="Ayarlar"><RelayVeriYok ne="Tanım" /></SectionCard>;

  const gruplar = [...new Set(tanimlar.parametreler.map((p) => p.grup))];

  async function kaydet(p) {
    const sayi = Number(taslak);
    if (!Number.isFinite(sayi)) return setMesaj({ hata: true, metin: 'Geçerli bir sayı girin' });
    setKaydediliyor(true);
    setMesaj(null);
    try {
      const res = await axios.post(`${API_BASE}/relay/parametre`,
        { device_id: deviceId, anahtar: p.anahtar, deger: Math.round(sayi) },
        { headers: { Authorization: `Bearer ${token}` } });
      setMesaj({ metin: res.data.message });
      setDuzenlenen(null);
      // Cihaz yazmadan hemen sonra parametreleri yeniden yayınlıyor; kısa
      // bir gecikmeyle çekmek yeni değeri yakalamaya yetiyor.
      setTimeout(onYenile, 2500);
    } catch (err) {
      setMesaj({ hata: true, metin: err.response?.data?.detail || 'Gönderilemedi' });
    } finally {
      setKaydediliyor(false);
    }
  }

  return (
    <>
      <RelayKomutlar token={token} deviceId={deviceId} tanimlar={tanimlar} />
      {gruplar.map((grup) => (
        <SectionCard key={grup} title={`Ayarlar — ${grup}`}>
          {!degerler && <div style={{ marginBottom: 10 }}><RelayVeriYok ne="Parametre" /></div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
            {tanimlar.parametreler.filter((p) => p.grup === grup).map((p) => {
              const ham = degerler?.[p.anahtar];
              const etiketli = p.secenekler?.[ham];
              const duzenlemede = duzenlenen === p.anahtar;
              return (
                <div key={p.anahtar} style={{
                  background: 'var(--bg)', borderRadius: 'var(--radius-sm)', padding: '10px 12px',
                }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                    {p.etiket}
                    {!p.yazilabilir && <span title="Salt okunur" style={{ marginLeft: 5 }}>🔒</span>}
                  </div>
                  {duzenlemede ? (
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input
                        type="number"
                        value={taslak}
                        onChange={(e) => setTaslak(e.target.value)}
                        autoFocus
                        style={{ ...inputStyle, padding: '6px 8px', fontSize: 13, width: 90 }}
                      />
                      <button onClick={() => kaydet(p)} disabled={kaydediliyor} style={{
                        padding: '6px 10px', borderRadius: 'var(--radius-xs)', border: 'none',
                        background: 'var(--l3)', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                      }}>{kaydediliyor ? '…' : 'Yaz'}</button>
                      <button onClick={() => setDuzenlenen(null)} style={{
                        padding: '6px 8px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)',
                        background: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer',
                      }}>✕</button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                      <span className="mono" style={{ fontSize: 15, fontWeight: 600 }}>
                        {etiketli ?? (ham ?? '—')}
                        {!etiketli && p.birim && p.birim !== 'index' && (
                          <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 3 }}>{p.birim}</span>
                        )}
                      </span>
                      {p.yazilabilir && degerler && (
                        <button
                          onClick={() => { setDuzenlenen(p.anahtar); setTaslak(String(ham ?? '')); setMesaj(null); }}
                          style={{
                            background: 'none', border: 'none', color: 'var(--l3)', fontSize: 11,
                            cursor: 'pointer', textDecoration: 'underline', padding: 0,
                          }}
                        >Değiştir</button>
                      )}
                    </div>
                  )}
                  {duzenlemede && (
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
                      Aralık: {p.min} – {p.max}{p.birim && p.birim !== 'index' ? ` ${p.birim}` : ''}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {mesaj && (
            <div style={{ marginTop: 10, fontSize: 12, color: mesaj.hata ? 'var(--danger)' : '#16a34a' }}>
              {mesaj.metin}
            </div>
          )}
        </SectionCard>
      ))}
    </>
  );
}

/** Yazma komutları. Geri dönüşü olmayanlar için cihaz adı yazdırarak çift onay. */
function RelayKomutlar({ token, deviceId, tanimlar }) {
  const [calisan, setCalisan] = useState(null);
  const [mesaj, setMesaj] = useState(null);
  const [onayBekleyen, setOnayBekleyen] = useState(null);
  const [onayMetni, setOnayMetni] = useState('');

  async function calistir(komut) {
    setCalisan(komut.anahtar);
    setMesaj(null);
    try {
      const res = await axios.post(`${API_BASE}/relay/komut`,
        { device_id: deviceId, komut: komut.anahtar },
        { headers: { Authorization: `Bearer ${token}` } });
      setMesaj({ metin: res.data.message });
    } catch (err) {
      setMesaj({ hata: true, metin: err.response?.data?.detail || 'Komut gönderilemedi' });
    } finally {
      setCalisan(null);
      setOnayBekleyen(null);
      setOnayMetni('');
    }
  }

  const normal = tanimlar.komutlar.filter((k) => !k.tehlikeli);
  const tehlikeli = tanimlar.komutlar.filter((k) => k.tehlikeli);

  return (
    <SectionCard title="Komutlar">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {normal.map((k) => (
          <button key={k.anahtar} onClick={() => calistir(k)} disabled={calisan === k.anahtar} style={{
            padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
            background: 'var(--surface)', color: 'var(--ink)', fontSize: 12, fontWeight: 600,
            cursor: calisan ? 'default' : 'pointer',
          }}>
            {calisan === k.anahtar ? 'Gönderiliyor…' : k.etiket}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--danger)', fontWeight: 600, marginBottom: 8 }}>
          Geri alınamaz işlemler
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {tehlikeli.map((k) => (
            <button key={k.anahtar} onClick={() => { setOnayBekleyen(k); setOnayMetni(''); setMesaj(null); }} style={{
              padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)',
              background: 'none', color: 'var(--danger)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              {k.etiket}
            </button>
          ))}
        </div>
        {onayBekleyen && (
          <div style={{
            marginTop: 12, padding: 12, borderRadius: 'var(--radius-sm)',
            background: 'rgba(239,68,68,0.08)', border: '1px solid var(--danger)',
          }}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              <strong>{onayBekleyen.etiket}</strong> — bu işlem geri alınamaz ve cihazın
              çalışmasını kesintiye uğratabilir. Onaylamak için cihaz ID’sini yazın:
              <span className="mono" style={{ marginLeft: 4 }}>{deviceId}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                value={onayMetni}
                onChange={(e) => setOnayMetni(e.target.value)}
                placeholder={deviceId}
                style={{ ...inputStyle, padding: '7px 9px', fontSize: 13, maxWidth: 220 }}
              />
              <button
                onClick={() => calistir(onayBekleyen)}
                disabled={onayMetni.trim() !== deviceId || calisan}
                style={{
                  padding: '7px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
                  background: onayMetni.trim() === deviceId ? 'var(--danger)' : 'var(--border)',
                  color: '#fff', fontSize: 12, fontWeight: 600,
                  cursor: onayMetni.trim() === deviceId ? 'pointer' : 'default',
                }}
              >Onayla ve Çalıştır</button>
              <button onClick={() => setOnayBekleyen(null)} style={{
                padding: '7px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
                background: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer',
              }}>Vazgeç</button>
            </div>
          </div>
        )}
      </div>

      {mesaj && (
        <div style={{ marginTop: 12, fontSize: 12, color: mesaj.hata ? 'var(--danger)' : '#16a34a' }}>
          {mesaj.metin}
        </div>
      )}
    </SectionCard>
  );
}

function RelayBolumleri({ token, deviceId, tab }) {
  const { snapshots, tanimlar, yenile } = useRelayData(token, deviceId);
  if (tab === 'kompanzasyon') {
    return (
      <>
        <RelayKompanzasyon snapshots={snapshots} tanimlar={tanimlar} />
        <RelayCihazDurumu snapshots={snapshots} />
        <RelayToplam snapshots={snapshots} />
      </>
    );
  }
  if (tab === 'olcum') {
    return (
      <>
        <RelayTepe snapshots={snapshots} />
        <RelayEnerji snapshots={snapshots} />
      </>
    );
  }
  if (tab === 'ayarlar') {
    return (
      <RelayAyarlar token={token} deviceId={deviceId} snapshots={snapshots}
        tanimlar={tanimlar} onYenile={yenile} />
    );
  }
  return null;
}

const DASHBOARD_TABS = [
  { key: 'canli', label: 'Canlı' },
  { key: 'fatura', label: 'Fatura' },
  { key: 'analiz', label: 'Analiz' },
  { key: 'alarm', label: 'Alarmlar' },
  { key: 'cihaz', label: 'Cihaz' },
];

// Röle farklı bir ürün: fatura/analiz sekmeleri onun verisine dayanmıyor,
// yerine kompanzasyona özel sekmeler geliyor. "Canlı" ortak çünkü ölçüm
// çekirdeği aynı.
const RELAY_DASHBOARD_TABS = [
  { key: 'canli', label: 'Canlı' },
  { key: 'kompanzasyon', label: 'Kompanzasyon' },
  { key: 'olcum', label: 'Tepe & Enerji' },
  { key: 'ayarlar', label: 'Ayarlar' },
  { key: 'alarm', label: 'Alarmlar' },
  { key: 'cihaz', label: 'Cihaz' },
];

function DashboardTabs({ active, onChange, alarmCount, relay }) {
  return (
    <nav className="dash-tabs">
      {(relay ? RELAY_DASHBOARD_TABS : DASHBOARD_TABS).map((t) => (
        <button
          key={t.key}
          className="dash-tab"
          onClick={() => onChange(t.key)}
          aria-current={t.key === active ? 'page' : undefined}
        >
          {t.label}
          {t.key === 'alarm' && alarmCount > 0 && (
            <span className="dash-tab-badge" title={`${alarmCount} çözülmemiş alarm`}>
              {alarmCount}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}

function DeviceDashboard({ token, device, tab, onTabChange, onBack, onLogout, theme, subscription, onDeviceDeleted }) {
  const [connected, setConnected] = useState(false);
  const [lastMessageAt, setLastMessageAt] = useState(null);
  const [esp32Status, setEsp32Status] = useState(null); // 'online' | 'offline' | null (henüz bilinmiyor)
  const [esp32StatusChangedAt, setEsp32StatusChangedAt] = useState(null);
  const [latest, setLatest] = useState({});
  const [pulseKey, setPulseKey] = useState(0);
  const [clock, setClock] = useState(new Date());
  const [energy, setEnergy] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [ctRatio, setCtRatio] = useState(null);
  const [hourlyModal, setHourlyModal] = useState(null); // { title, suffix } | null
  const [stats, setStats] = useState(null);
  const [peaks, setPeaks] = useState(null);
  const [demand, setDemand] = useState(null);
  const [harmonics, setHarmonics] = useState(null);
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [firmware, setFirmware] = useState(null);
  const [alarmCount, setAlarmCount] = useState(0);
  const wsRef = useRef(null);

  function selectTab(next) {
    // Sekme artık URL'de tutuluyor; kaynak App'teki route.
    onTabChange(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Alarm rozeti: sekme kapaliyken de cozulmemis alarm sayisi gorunmeli
  useEffect(() => {
    let cancelled = false;
    function fetchAlarmCount() {
      axios.get(`${API_BASE}/devices/${device.device_id}/alarm-events?limit=200`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          if (!cancelled) setAlarmCount(res.data.filter((e) => !e.resolved_at).length);
        })
        .catch(() => { /* rozet kritik degil, sessizce gecs */ });
    }
    fetchAlarmCount();
    const timer = setInterval(fetchAlarmCount, 30000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [device.device_id, token]);

  async function fetchFirmware() {
    try {
      const res = await axios.get(`${API_BASE}/devices/${device.device_id}/firmware`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setFirmware(res.data);
    } catch {
      // sessizce yoksay
    }
  }

  async function fetchCtRatio() {
    try {
      const res = await axios.get(`${API_BASE}/devices/${device.device_id}/ct-ratio`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCtRatio(res.data.ct_ratio);
    } catch {
      // sessizce yoksay, panelde "—" gösterilecek
    }
  }

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    function fetchEnergy() {
      axios.get(`${API_BASE}/energy?device_id=${device.device_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((res) => { if (!cancelled) setEnergy(res.data); }).catch(() => {});
    }
    fetchEnergy();
    const timer = setInterval(fetchEnergy, 30000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [device.device_id]);

  useEffect(() => {
    fetchCtRatio();
    const timer = setInterval(fetchCtRatio, 30000);
    return () => clearInterval(timer);
  }, [device.device_id]);

  useEffect(() => {
    fetchFirmware();
    const timer = setInterval(fetchFirmware, 30000);
    return () => clearInterval(timer);
  }, [device.device_id]);

  useEffect(() => {
    let cancelled = false;
    const headers = { Authorization: `Bearer ${token}` };
    function poll() {
      axios.get(`${API_BASE}/stats?device_id=${device.device_id}`, { headers })
        .then((res) => { if (!cancelled) setStats(res.data); }).catch(() => {});
      axios.get(`${API_BASE}/peaks?device_id=${device.device_id}`, { headers })
        .then((res) => { if (!cancelled) setPeaks(res.data); }).catch(() => {});
      axios.get(`${API_BASE}/demand?device_id=${device.device_id}`, { headers })
        .then((res) => { if (!cancelled) setDemand(res.data); }).catch(() => {});
      axios.get(`${API_BASE}/harmonics?device_id=${device.device_id}`, { headers })
        .then((res) => { if (!cancelled) setHarmonics(res.data); }).catch(() => {});
      axios.get(`${API_BASE}/info?device_id=${device.device_id}`, { headers })
        .then((res) => { if (!cancelled) setDeviceInfo(res.data); }).catch(() => {});
    }
    poll();
    const timer = setInterval(poll, 30000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [device.device_id, token]);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}?token=${token}&device_id=${device.device_id}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = (event) => {
      setConnected(false);
      if (event.code === 1008) onLogout();
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'status') {
        setEsp32Status(data.esp32_status);
        setEsp32StatusChangedAt(data.changed_at ? new Date(data.changed_at) : new Date());
        return;
      }
      setLatest(data);
      setPulseKey((k) => k + 1);
      setLastMessageAt(new Date());
    };
    return () => ws.close();
  }, [device.device_id]);

  const DATA_STALE_MS = 6000;
  const isStale = !lastMessageAt || (clock.getTime() - lastMessageAt.getTime()) > DATA_STALE_MS;

  let statusColor, statusLabel, statusDetail;
  if (esp32Status !== 'online') {
    statusColor = 'var(--danger)';
    statusLabel = 'Bağlantı yok';
    statusDetail = esp32StatusChangedAt ? `Kopma: ${esp32StatusChangedAt.toLocaleTimeString('tr-TR')}` : null;
  } else if (isStale) {
    statusColor = 'var(--warn)';
    statusLabel = 'Veri akışı yok';
    statusDetail = lastMessageAt ? `Son veri: ${lastMessageAt.toLocaleTimeString('tr-TR')}` : null;
  } else {
    statusColor = '#22c55e';
    statusLabel = 'Canlı';
    statusDetail = esp32StatusChangedAt ? formatDuration(clock.getTime() - esp32StatusChangedAt.getTime()) : null;
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 28 }}>
        <div>
          <button onClick={onBack} style={{
            background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
            cursor: 'pointer', padding: 0, marginBottom: 8,
          }}>
            ← Cihazlarım
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <img className="marka-logo" src="/logo.png" alt="Binary Enerji" style={{ height: 16 }} />
            <span style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1 }}>BINARY ENERJİ</span>
          </div>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700 }}>{device.name}</h1>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end', fontSize: 13 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor }} />
            <span style={{ color: statusColor, fontWeight: 600 }}>{statusLabel}</span>
          </div>
          {statusDetail && (
            <div className="mono" style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{statusDetail}</div>
          )}
          <div className="mono" style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>
            {clock.toLocaleTimeString('tr-TR')}
          </div>
          <button onClick={onLogout} className="logout-link" style={{
            marginTop: 6, background: 'none', border: 'none', color: 'var(--muted)',
            fontSize: 12, cursor: 'pointer', textDecoration: 'underline', padding: 0,
          }}>
            Çıkış Yap
          </button>
        </div>
      </header>

      <SubscriptionBanner subscription={subscription} />

      <DashboardTabs active={tab} onChange={selectTab} alarmCount={alarmCount} relay={isRelayDevice(device.device_id)} />

      {isRelayDevice(device.device_id) && (
        <RelayBolumleri token={token} deviceId={device.device_id} tab={tab} />
      )}

      {tab === 'canli' && (
        <>
        {theme === 'faz-portresi' ? (
          <PhasorDiagram latest={latest} energy={energy} firmware={firmware} />
        ) : theme === 'kadran-kumesi' ? (
          <GaugeCluster latest={latest} firmware={firmware} />
        ) : (
          <>
            <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
              {PHASES.map((ph) => (
                <PhaseCard
                  key={ph.key}
                  label={ph.label}
                  color={ph.color}
                  v={latest[`v${ph.key}`]}
                  i={latest[`i${ph.key}`]}
                  p={latest[`p${ph.key}`]}
                  q={latest[`q${ph.key}`]}
                  s={latest[`s${ph.key}`]}
                  pf={latest[`pf${ph.key}`]}
                  thd={latest[`thd${ph.key}`]}
                  thvd={latest[`thvd${ph.key}`]}
                  pulse={pulseKey}
                />
              ))}
            </div>

            <div style={{ display: 'flex', gap: 32, marginBottom: 24, fontSize: 14, flexWrap: 'wrap' }}>
              <div>
                <span style={{ color: 'var(--muted)' }}>Frekans: </span>
                <span className="mono" style={{ fontWeight: 500 }}>{latest.f1 != null ? latest.f1.toFixed(2) : '—'} Hz</span>
              </div>
              <div>
                <span style={{ color: 'var(--muted)' }}>Nötr: </span>
                <span className="mono" style={{ fontWeight: 500 }}>
                  {latest.vN != null ? latest.vN.toFixed(1) : '—'} V, {latest.iN != null ? latest.iN.toFixed(3) : '—'} A
                </span>
              </div>
            </div>
          </>
        )}

        <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>Gerilim &amp; Akım Dalga Formu</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {PHASES.map((ph) => (
            <WaveformCard
              key={ph.key}
              label={ph.label}
              color={ph.color}
              v={latest[`v${ph.key}`]}
              i={latest[`i${ph.key}`]}
              cosPhi={latest[`cos${ph.key}`]}
              q={latest[`q${ph.key}`]}
            />
          ))}
        </div>

        <div style={{ fontSize: 13, color: 'var(--muted)', margin: '24px 0 12px' }}>Toplam Enerji</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <EnergyCard title="Tüketim" data={energy} suffix="tuketim" onClick={() => setHourlyModal({ title: 'Tüketim', suffix: 'tuketim' })} />
          <EnergyCard title="Üretim" data={energy} suffix="uretim" onClick={() => setHourlyModal({ title: 'Üretim', suffix: 'uretim' })} />
        </div>

        </>
      )}

      {tab === 'fatura' && (
        <>
          <BillSection token={token} device={device} />
          <ReactiveSection token={token} device={device} />
          <DemandSection demand={demand} />
          <TrendSection token={token} device={device} />
        </>
      )}

      {tab === 'analiz' && (
        <>
          <StatsSection stats={stats} theme={theme} />
          <PowerQualitySection token={token} device={device} />
          <HarmonicsSection harmonics={harmonics} />
          <PeaksSection peaks={peaks} />
        </>
      )}

      {tab === 'alarm' && <AlarmsSection token={token} device={device} />}

      {tab === 'cihaz' && (
        <>
          <DeviceInfoSection info={deviceInfo} />

        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: "var(--radius-md)", padding: 20, marginTop: 24,
        }}>
          <button
            onClick={() => setSettingsOpen((o) => !o)}
            style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 13, color: 'var(--muted)', padding: 0,
            }}
          >
            <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Cihaz Ayarları</span>
            <span>{settingsOpen ? '▲' : '▼'}</span>
          </button>
          {settingsOpen && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <CtRatioBox token={token} device={device} ctRatio={ctRatio} onSaved={fetchCtRatio} />
            <WifiBox token={token} device={device} connected={esp32Status === 'online'} />
              <FirmwareBox token={token} device={device} firmware={firmware} onUpdated={fetchFirmware} />
              {deviceInfo ? (
                <>
                  <span style={{ fontSize: 13, fontWeight: 600, marginTop: 8 }}>Cihaz Komutları</span>
                  {DEVICE_COMMAND_LIST.map((cmd) => (
                    <CommandRow key={cmd.key} token={token} device={device} cmd={cmd} />
                  ))}
                </>
              ) : (
                <div style={{
                  padding: '10px 12px', borderRadius: "var(--radius-sm)", border: '1px solid var(--border)',
                  display: 'flex', flexDirection: 'column', gap: 4,
                }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>Enerji/Tepe Sıfırlama, Fabrika Ayarları, Yeniden Başlatma</span>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                    Bu işlemler cihazın ön panelinden yapılmalıdır — uzaktan güvenilir şekilde çalışmadığı için kaldırıldı. Panel menüleri: Enerji Sıfırlama (Ayarlar → Enerji Değerleri Silme), Tepe Değerleri (Ayarlar → Tepe Değerleri Resetleme), Fabrika Ayarları (Ayarlar → Fabrika Ayarları), Cihaz Resetleme (Ayarlar → Reset).
                  </span>
                </div>
              )}
              <DeleteDeviceBox token={token} device={device} onDeleted={onDeviceDeleted} />
            </div>
          )}
        </div>

        </>
      )}

      {hourlyModal && (
        <HourlyEnergyModal
          token={token}
          device={device}
          title={hourlyModal.title}
          suffix={hourlyModal.suffix}
          onClose={() => setHourlyModal(null)}
        />
      )}
    </div>
  );
}

function Footer() {
  return (
    <footer style={{ textAlign: 'center', padding: '32px 16px 20px', fontSize: 12, color: 'var(--muted)' }}>
      © {new Date().getFullYear()} Binary Enerji ·{' '}
      <a href="/gizlilik-politikasi" style={{ color: 'var(--muted)' }}>Gizlilik Politikası</a> ·{' '}
      <a href="/kullanim-sartlari" style={{ color: 'var(--muted)' }}>Kullanım Şartları</a>
    </footer>
  );
}

// Iyzico odeme sonrasi tarayiciyi buraya yonlendiriyor (bkz. api.py,
// subscription_payment_callback). Durum backend'in KENDI dogruladigi sonuca
// gore ?durum= parametresiyle geliyor -- bu sayfa hicbir sey dogrulamiyor,
// sadece o kararı gösteriyor.
const PAYMENT_RESULT_COPY = {
  basarili: { baslik: 'Ödeme alındı', renk: 'var(--accent)',
             metin: 'Aboneliğiniz uzatıldı. Panele dönebilirsiniz.' },
  basarisiz: { baslik: 'Ödeme başarısız', renk: 'var(--danger)',
              metin: 'Kartınızdan tahsilat yapılamadı. Farklı bir kartla tekrar deneyebilirsiniz.' },
  hata: { baslik: 'Bir sorun oluştu', renk: 'var(--danger)',
         metin: 'Ödeme durumunu doğrulayamadık. Kartınızdan çekim yapıldıysa birkaç dakika içinde abonelik durumunuz güncellenecektir; devam ederse bizimle iletişime geçin.' },
};

function PaymentResultPage() {
  const durum = new URLSearchParams(window.location.search).get('durum');
  const bilgi = PAYMENT_RESULT_COPY[durum] || PAYMENT_RESULT_COPY.hata;

  return (
    <div className="centered-page" style={{ maxWidth: 420, padding: '0 24px' }}>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 32, textAlign: 'center',
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: bilgi.renk, marginBottom: 10 }}>
          {bilgi.baslik}
        </div>
        <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 20 }}>
          {bilgi.metin}
        </div>
        <a href="/hesabim" style={{
          display: 'inline-block', padding: '9px 18px', borderRadius: "var(--radius-xs)",
          background: 'var(--l3)', color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none',
        }}>
          Panele Dön
        </a>
      </div>
    </div>
  );
}

function PrivacyPolicy() {
  return (
    <div className="centered-page" style={{ maxWidth: 640, padding: '0 24px' }}>
      <a href="/" style={{ fontSize: 12, color: 'var(--muted)', textDecoration: 'none' }}>← Binary Enerji'ye dön</a>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 32, marginTop: 16, lineHeight: 1.7, fontSize: 14,
      }}>
        <h1 style={{ fontSize: 20, marginTop: 0 }}>Gizlilik Politikası</h1>
        <p style={{ color: 'var(--muted)', fontSize: 12 }}>Son güncelleme: 17 Ağustos 2026</p>

        <h2 style={{ fontSize: 15 }}>1. Veri Sorumlusu</h2>
        <p>Binary Enerji, 6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") kapsamında veri sorumlusu sıfatıyla, aşağıda açıklanan kişisel verileri işlemektedir.</p>

        <h2 style={{ fontSize: 15 }}>2. Toplanan Veriler</h2>
        <p>Hesap oluşturma sırasında ad, soyad, kullanıcı adı, e-posta adresi ve telefon numaranız toplanır. Platforma bağladığınız cihazlara ait ölçüm verileri (gerilim, akım, güç, enerji tüketimi vb.) hesabınızla ilişkilendirilerek saklanır.</p>

        <h2 style={{ fontSize: 15 }}>3. Verilerin İşlenme Amacı</h2>
        <p>Toplanan veriler; hesabınızın oluşturulması, e-posta adresinizin doğrulanması, hizmetin sunulması ve cihazlarınıza ait ölçüm verilerinin size gösterilmesi amacıyla işlenir.</p>

        <h2 style={{ fontSize: 15 }}>4. Üçüncü Taraflarla Paylaşım</h2>
        <p>Doğrulama e-postaları Resend altyapısı üzerinden gönderilir. Kayıt bilgileriniz iç kayıt tutma amacıyla Google E-Tablolar'da saklanabilir. Verileriniz pazarlama amacıyla üçüncü taraflarla paylaşılmaz veya satılmaz.</p>

        <h2 style={{ fontSize: 15 }}>5. Veri Güvenliği</h2>
        <p>Şifreniz geri döndürülemez şekilde (hash'lenerek) saklanır. Verileriniz, yetkisiz erişime karşı makul teknik ve idari önlemlerle korunur.</p>

        <h2 style={{ fontSize: 15 }}>6. Haklarınız</h2>
        <p>KVKK'nın 11. maddesi uyarınca; verilerinizin işlenip işlenmediğini öğrenme, işlenmişse buna ilişkin bilgi talep etme, verilerinizin düzeltilmesini veya silinmesini isteme haklarına sahipsiniz. Taleplerinizi hesabınızla ilişkili e-posta adresi üzerinden bize iletebilirsiniz.</p>
      </div>
      <Footer />
    </div>
  );
}

function TermsOfService() {
  return (
    <div className="centered-page" style={{ maxWidth: 640, padding: '0 24px' }}>
      <a href="/" style={{ fontSize: 12, color: 'var(--muted)', textDecoration: 'none' }}>← Binary Enerji'ye dön</a>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: "var(--radius-md)", padding: 32, marginTop: 16, lineHeight: 1.7, fontSize: 14,
      }}>
        <h1 style={{ fontSize: 20, marginTop: 0 }}>Kullanım Şartları</h1>
        <p style={{ color: 'var(--muted)', fontSize: 12 }}>Son güncelleme: 25 Ağustos 2026</p>

        <h2 style={{ fontSize: 15 }}>1. Taraflar ve Kabul</h2>
        <p>Bu Kullanım Şartları ("Şartlar"), Binary Enerji tarafından sunulan web panosu, mobil uygulamalar (iOS/Android) ve bunlarla birlikte çalışan ölçüm cihazlarından ("Hizmet") faydalanan kullanıcıyı ("Kullanıcı", "siz") bağlar. Hesap oluşturarak veya Hizmeti kullanarak bu Şartları kabul etmiş sayılırsınız. Kabul etmiyorsanız Hizmeti kullanmamalısınız.</p>

        <h2 style={{ fontSize: 15 }}>2. Hizmetin Tanımı</h2>
        <p>Binary Enerji, elektrik panolarına bağlanan donanım cihazlarından (gerilim, akım, güç, enerji tüketimi vb.) toplanan ölçüm verilerini kullanıcıya web ve mobil uygulamalar üzerinden gösteren bir izleme hizmetidir. Hizmet; cihaz yönetimi, canlı veri görüntüleme, geçmiş veri raporlama ve cihaza uzaktan komut/güncelleme gönderme gibi işlevleri içerir.</p>

        <h2 style={{ fontSize: 15 }}>3. Güvenlik Cihazı Değildir</h2>
        <p>Hizmet yalnızca <strong>izleme ve bilgilendirme</strong> amaçlıdır; bir koruma, alarm veya güvenlik sistemi olarak tasarlanmamıştır. Elektrik tesisatınızın güvenliği, sigortalanması ve yürürlükteki elektrik güvenliği mevzuatına uygunluğu tamamen sizin ve/veya yetkili bir elektrikçinin sorumluluğundadır. Binary Enerji, Hizmet üzerinden gelen (veya geciken/gelmeyen) veri veya bildirimlere dayanılarak alınan kararlardan doğacak maddi/bedeni zararlardan sorumlu tutulamaz.</p>

        <h2 style={{ fontSize: 15 }}>4. Hesap Sorumluluğu</h2>
        <p>Hesap bilgilerinizin (kullanıcı adı, şifre) gizliliğinden ve hesabınız üzerinden gerçekleştirilen tüm işlemlerden siz sorumlusunuz. Şüpheli bir erişim fark ederseniz derhal bize bildirmelisiniz. Doğru ve güncel bilgi vermek Kullanıcı'nın yükümlülüğündedir.</p>

        <h2 style={{ fontSize: 15 }}>5. Kabul Edilebilir Kullanım</h2>
        <p>Hizmeti yalnızca yasal amaçlarla ve size ait veya kullanma yetkiniz olan cihazlar için kullanabilirsiniz. Hizmete yetkisiz erişim sağlamak, güvenlik önlemlerini aşmaya çalışmak, başka kullanıcıların cihazlarına izinsiz erişmeye çalışmak veya Hizmeti kötüye kullanmak yasaktır. Özellikle "Fabrika Ayarlarına Dön" ve "Sistem Şifresini Sıfırla" gibi geri alınamaz cihaz komutları kendi sorumluluğunuzdadır.</p>

        <h2 style={{ fontSize: 15 }}>6. Hizmetin Sürekliliği</h2>
        <p>Hizmetin kesintisiz veya hatasız çalışacağı garanti edilmez. Bakım, güncelleme, internet/altyapı sorunları veya mücbir sebepler nedeniyle Hizmet geçici olarak kullanılamayabilir. Binary Enerji, makul çaba göstererek Hizmeti sürdürmeyi hedefler ancak kesinti süresine ilişkin bir taahhütte bulunmaz.</p>

        <h2 style={{ fontSize: 15 }}>7. Kablosuz Firmware Güncellemeleri (OTA)</h2>
        <p>Kullanıcı, cihazına kablosuz olarak firmware güncellemesi ("Güncelle" butonu) gönderebilir. Güncelleme sırasında cihaz kısa süreliğine yeniden başlar ve bu sürede ölçüm/komut işlevleri kesintiye uğrayabilir. Güncellemenin bir ağ kesintisi veya beklenmeyen bir donanım arızası nedeniyle tamamlanamaması riski bulunur; Binary Enerji makul güvenlik önlemlerini (otomatik geri alma dahil) uygular ancak sıfır risk taahhüt etmez.</p>

        <h2 style={{ fontSize: 15 }}>8. Fikri Mülkiyet</h2>
        <p>Hizmete ait yazılım, tasarım, marka ve içerikler Binary Enerji'ye veya lisans verenlerine aittir. Bu Şartlar size Hizmeti kullanmanız için sınırlı, münhasır olmayan, devredilemez bir kullanım hakkı tanır; başka bir mülkiyet hakkı vermez.</p>

        <h2 style={{ fontSize: 15 }}>9. Sorumluluğun Sınırlandırılması</h2>
        <p>Yürürlükteki mevzuatın izin verdiği azami ölçüde, Binary Enerji; Hizmetin kullanımından veya kullanılamamasından doğan dolaylı, arızi veya sonuç niteliğindeki zararlardan (kar kaybı, veri kaybı, iş kaybı dahil) sorumlu tutulamaz. Bu Şartlar tüketici hukukundan doğan vazgeçilemez haklarınızı sınırlamaz.</p>

        <h2 style={{ fontSize: 15 }}>10. Fesih</h2>
        <p>Hesabınızı istediğiniz zaman kapatabilirsiniz. Binary Enerji, bu Şartların ihlali halinde hesabınızı askıya alma veya sonlandırma hakkını saklı tutar.</p>

        <h2 style={{ fontSize: 15 }}>11. Değişiklikler</h2>
        <p>Bu Şartlar zaman zaman güncellenebilir. Önemli değişiklikler Hizmet üzerinden veya e-posta yoluyla duyurulur. Güncellemeden sonra Hizmeti kullanmaya devam etmeniz, yeni Şartları kabul ettiğiniz anlamına gelir.</p>

        <h2 style={{ fontSize: 15 }}>12. Uygulanacak Hukuk</h2>
        <p>Bu Şartlar Türkiye Cumhuriyeti kanunlarına tabidir. Bu Şartlardan doğan uyuşmazlıklarda Türkiye mahkemeleri ve icra daireleri yetkilidir.</p>

        <h2 style={{ fontSize: 15 }}>13. İletişim</h2>
        <p>Sorularınız için hesabınızla ilişkili e-posta adresi üzerinden bize ulaşabilirsiniz.</p>
      </div>
      <Footer />
    </div>
  );
}

// ---------- Gezinme / URL ----------
//
// Gezinme durumu daha önce yalnızca React state'indeydi ve URL'ye hiç
// yansımıyordu; bu yüzden tarayıcının geri tuşu bir seviye yukarı çıkmak
// yerine siteden tamamen çıkıyordu. Artık URL tek doğruluk kaynağı: geri/ileri
// kendiliğinden çalışıyor, sayfa yenilenince bulunduğunuz yer korunuyor ve
// bir cihazın bağlantısı paylaşılabiliyor.
// Binary Enerji artik iki urunun ortak girisi: enerji izleme (Cihazlarim) ve
// elektrikli arac sarj agi (Binary Sarj). Giristen sonra kullanici once burada
// hangi urune gidecegini seciyor.
function HomeHub({ deviceCount, token, onOpenDevices, onOpenAccount, onLogout }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function openBinarySarj() {
    setBusy(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/sso/binary-sarj`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      // Devir bileti URL fragment'inda tasiniyor. Fragment sunucuya hic
      // gonderilmez -- boylece bilet ne erisim loglarina ne de bir sonraki
      // isteğin Referer basligina duser.
      window.location.href = `${res.data.url}#bilet=${encodeURIComponent(res.data.handoff_token)}`;
    } catch (err) {
      setError(err.response?.status === 503
        ? 'Binary Şarj bağlantısı bu ortamda henüz etkin değil.'
        : 'Binary Şarj açılamadı. Lütfen tekrar deneyin.');
      setBusy(false);
    }
  }

  const kart = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-card)',
    padding: 24,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    cursor: 'pointer',
    textAlign: 'left',
    font: 'inherit',
    color: 'inherit',
    width: '100%',
  };

  return (
    <div className="centered-page" style={{ maxWidth: 720, padding: '0 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginBottom: -8 }}>
        <button onClick={onOpenAccount} style={{
          background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
          cursor: 'pointer', padding: 4, textDecoration: 'underline',
        }}>Hesabım</button>
        <button onClick={onLogout} style={{
          background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12,
          cursor: 'pointer', padding: 4, textDecoration: 'underline',
        }}>Çıkış</button>
      </div>

      <h1 style={{
        margin: '0 0 6px', fontFamily: 'var(--font-display)', fontSize: 22,
        fontWeight: 700, textAlign: 'center',
      }}>Binary Enerji</h1>
      <p style={{ margin: '0 0 24px', textAlign: 'center', color: 'var(--muted)', fontSize: 14 }}>
        Hangi ürünle devam etmek istersiniz?
      </p>

      <div style={{
        display: 'grid', gap: 14,
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      }}>
        <button type="button" onClick={onOpenDevices} style={kart}>
          <span style={{ fontSize: 30, lineHeight: 1 }}>📟</span>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>
            Cihazlarım
          </span>
          <span style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6 }}>
            Enerji ölçerlerinizin canlı verisi, tüketim geçmişi, alarmlar ve raporlar.
          </span>
          <span style={{ fontSize: 12.5, color: 'var(--accent)', fontWeight: 600, marginTop: 4 }}>
            {deviceCount === 0
              ? 'Henüz cihaz eklenmemiş →'
              : `${deviceCount} cihaz →`}
          </span>
        </button>

        <button type="button" onClick={openBinarySarj} disabled={busy} style={{
          ...kart,
          opacity: busy ? 0.6 : 1,
          cursor: busy ? 'progress' : 'pointer',
        }}>
          <span style={{ fontSize: 30, lineHeight: 1 }}>⚡</span>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>
            Binary Şarj
          </span>
          <span style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6 }}>
            Elektrikli araç şarj ağı: istasyon haritası, rota planlayıcı, şarj geçmişi
            ve evdeki şarjınız.
          </span>
          <span style={{ fontSize: 12.5, color: 'var(--accent)', fontWeight: 600, marginTop: 4 }}>
            {busy ? 'Açılıyor…' : 'Şarj ağına git →'}
          </span>
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 14, fontSize: 13, color: 'var(--danger)',
          background: 'var(--surface)', border: '1px solid var(--danger)',
          borderRadius: 'var(--radius-md)', padding: 12, lineHeight: 1.6,
        }}>{error}</div>
      )}

      <p style={{ marginTop: 22, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
        Tek hesap, iki ürün — Binary Şarj'a geçerken tekrar giriş yapmanız gerekmez.
      </p>
    </div>
  );
}


function parseRoute(pathname) {
  if (pathname === '/odeme') return { ad: 'odeme' };
  if (pathname === '/gizlilik-politikasi') return { ad: 'gizlilik' };
  if (pathname === '/kullanim-sartlari') return { ad: 'sartlar' };
  if (pathname.startsWith('/davet')) return { ad: 'davet' };
  if (pathname === '/hesabim') return { ad: 'hesabim' };
  if (pathname === '/filo') return { ad: 'filo' };
  if (pathname === '/organizasyon') return { ad: 'organizasyon' };
  if (pathname === '/cihazlar') return { ad: 'liste' };
  const eslesme = pathname.match(/^\/cihaz\/([^/]+)(?:\/([^/]+))?\/?$/);
  if (eslesme) {
    return {
      ad: 'cihaz',
      deviceId: decodeURIComponent(eslesme[1]),
      // Röle sekmeleri (kompanzasyon/olcum/ayarlar) de geçerli: cihaz tipine
      // göre ayrı iki liste var, URL doğrulaması ikisini birden kabul etmeli --
      // yoksa röle sekmesine tıklamak sessizce "canli"ye geri düşüyor.
      sekme: eslesme[2] && [...DASHBOARD_TABS, ...RELAY_DASHBOARD_TABS].some((t) => t.key === eslesme[2])
        ? eslesme[2] : 'canli',
    };
  }
  // Bilinmeyen yollar ve kok yol ortak girise duser.
  return { ad: 'hub' };
}

function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.pathname));

  useEffect(() => {
    // Geri/ileri tuşları buradan yakalanıyor.
    const onPop = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // replace=true geçmişe yeni kayıt eklemez. Sekme değişimlerinde bu
  // kullanılıyor: yoksa panelden çıkmak için geriye altı kez basmak gerekirdi.
  function navigate(path, { replace = false } = {}) {
    if (replace) window.history.replaceState(null, '', path);
    else window.history.pushState(null, '', path);
    setRoute(parseRoute(path));
  }

  return [route, navigate];
}


export default function App() {
  const [route, navigate] = useRoute();
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [devices, setDevices] = useState(null); // null = yükleniyor
  const [subscription, setSubscription] = useState(null);
  const [role, setRole] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_STORAGE_KEY) || 'klasik');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  function handleLogin(newToken) {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    const pending = sessionStorage.getItem(PENDING_INVITE_KEY);
    if (pending) {
      sessionStorage.removeItem(PENDING_INVITE_KEY);
      window.location.href = `/davet?token=${encodeURIComponent(pending)}`;
    }
  }

  function handleLogout() {
    localStorage.removeItem('token');
    setToken(null);
    setDevices(null);
    setRole(null);
    navigate('/');
  }

  function refreshDevices() {
    axios.get(`${API_BASE}/devices`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      setDevices(res.data);
    }).catch((err) => {
      if (err.response?.status === 401) handleLogout();
    });
  }

  useEffect(() => {
    if (!token) return;
    refreshDevices();
    // Rol, "Cihaz Filosu" bağlantısının gösterilip gösterilmeyeceğini belirliyor.
    // Asıl yetki kontrolü backend'de (require_admin) -- bu sadece görünürlük.
    axios.get(`${API_BASE}/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setRole(res.data.role))
      .catch(() => {});
    axios.get(`${API_BASE}/subscription`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setSubscription(res.data))
      .catch(() => {});
  }, [token]);

  const selectedDevice = route.ad === 'cihaz' && devices
    ? devices.find((d) => d.device_id === route.deviceId)
    : null;

  // Geçersiz cihaz bağlantısı (silinmiş cihaz, yanlış yazılmış URL) sayfayı boş
  // bırakmasın -- listeye dönülüyor.
  useEffect(() => {
    if (route.ad === 'cihaz' && devices && !selectedDevice) {
      navigate('/cihazlar', { replace: true });
    }
  }, [route.ad, route.deviceId, devices, selectedDevice]);

  if (route.ad === 'odeme') return <PaymentResultPage />;
  if (route.ad === 'gizlilik') return <PrivacyPolicy />;
  if (route.ad === 'sartlar') return <TermsOfService />;
  if (route.ad === 'davet') return <InvitePage token={localStorage.getItem('token')} />;

  if (!token) {
    return (
      <>
        <AuthForm onLogin={handleLogin} />
        <Footer />
      </>
    );
  }

  if (devices === null) {
    return null;
  }

  if (route.ad === 'hub') {
    return (
      <>
        <HomeHub
          deviceCount={devices?.length ?? 0}
          token={token}
          onOpenDevices={() => navigate('/cihazlar')}
          onOpenAccount={() => navigate('/hesabim')}
          onLogout={handleLogout}
        />
        <Footer />
      </>
    );
  }

  // Filo, organizasyon ve cihaz panelinden "geri", ortak girise degil cihaz
  // listesine doner -- kullanici oraya listeden gelmisti.
  if (route.ad === 'filo') {
    return <FleetPage token={token} onBack={() => navigate('/cihazlar')} />;
  }

  if (route.ad === 'organizasyon') {
    return <OrganizationPage token={token} onBack={() => navigate('/cihazlar')} />;
  }

  if (route.ad === 'hesabim') {
    return (
      <>
        <AccountPage
          token={token}
          onBack={() => navigate('/cihazlar')}
          onLogout={handleLogout}
          deviceCount={devices?.length}
          theme={theme}
          onThemeChange={setTheme}
          subscription={subscription}
        />
        <Footer />
      </>
    );
  }

  if (selectedDevice) {
    return (
      <>
        <DeviceDashboard
          token={token}
          device={selectedDevice}
          tab={route.sekme}
          onTabChange={(t) => {
            try { localStorage.setItem('dash-tab', t); } catch { /* gizli sekme; yoksay */ }
            // replace: sekme geçişleri geçmişe yığılmasın, geri panelden çıksın.
            navigate(`/cihaz/${encodeURIComponent(selectedDevice.device_id)}/${t}`, { replace: true });
          }}
          onBack={() => navigate('/cihazlar')}
          onLogout={handleLogout}
          theme={theme}
          subscription={subscription}
          onDeviceDeleted={refreshDevices}
        />
        <Footer />
      </>
    );
  }

  return (
    <>
      <DeviceList
        onBackToHub={() => navigate('/')}
        devices={devices}
        onSelect={(device) => {
          let sonSekme = 'canli';
          try { sonSekme = localStorage.getItem('dash-tab') || 'canli'; } catch { /* yoksay */ }
          navigate(`/cihaz/${encodeURIComponent(device.device_id)}/${sonSekme}`);
        }}
        onLogout={handleLogout}
        onOpenAccount={() => navigate('/hesabim')}
        onOpenFleet={() => navigate('/filo')}
        onOpenOrganization={() => navigate('/organizasyon')}
        isAdmin={role === 'admin'}
        token={token}
        onDeviceAdded={refreshDevices}
        subscription={subscription}
      />
      <Footer />
    </>
  );
}