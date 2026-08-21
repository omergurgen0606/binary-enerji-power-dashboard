import { Fragment, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './index.css';

const API_BASE = 'https://binaryenerji.com/api';
const WS_URL = 'wss://binaryenerji.com/ws/live';

const PHASES = [
  { key: '1', color: 'var(--l1)', label: 'L1' },
  { key: '2', color: 'var(--l2)', label: 'L2' },
  { key: '3', color: 'var(--l3)', label: 'L3' },
];

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
  padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 16, width: '100%',
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
            <img src="/logo.png" alt="" style={{ height: 30 }} />
            <span style={{ color: '#fff', fontSize: 13, fontWeight: 700, letterSpacing: 2 }}>BINARY ENERJİ</span>
          </div>
          <h1 style={{ color: '#fff', fontSize: 34, fontWeight: 700, lineHeight: 1.25, margin: '0 0 16px' }}>
            Enerjinizi<br />gerçek zamanlı izleyin.
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: 15, lineHeight: 1.6, margin: '0 0 32px', maxWidth: 360 }}>
            Gerilim, akım ve güç verilerinizi saniyeler içinde görün; enerji tüketiminizi geçmişe dönük analiz edin.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              'Canlı gerilim, akım ve güç faktörü',
              'Saatlik tüketim / üretim raporları',
              'Cihaz bağlantı durumu anlık takip',
            ].map((t) => (
              <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--l2)', flexShrink: 0 }} />
                <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: 13 }}>{t}</span>
              </div>
            ))}
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
            <img src="/logo.png" alt="Binary Enerji" style={{ height: 28 }} />
            <span style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1.5, fontWeight: 600 }}>BINARY ENERJİ</span>
          </div>
          <div style={{
            background: 'var(--surface)', borderRadius: 16, padding: 28,
            boxShadow: '0 20px 40px -12px rgba(11,31,58,0.18)',
          }}>
            <div style={{ display: 'flex', marginBottom: 20, borderRadius: 8, background: 'var(--bg)', padding: 4 }}>
              {[['login', 'Giriş Yap'], ['register', 'Üye Ol']].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => switchMode(key)}
                  style={{
                    flex: 1, padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
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
                padding: '11px 12px', borderRadius: 8, border: 'none',
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
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (!deviceName.trim() || !deviceId.trim() || !claimCode.trim()) {
      return setError('Cihaz adı, cihaz ID\'si ve kurulum kodu zorunlu');
    }
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/devices`, {
        device_id: deviceId.trim(), name: deviceName.trim(), claim_code: claimCode.trim(),
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
      {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" disabled={loading} style={{
          flex: 1, padding: '10px 12px', borderRadius: 8, border: 'none',
          background: 'var(--l3)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>
          {loading ? 'Ekleniyor...' : 'Cihaz Ekle'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} style={{
            padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)',
            background: 'none', color: 'var(--muted)', fontSize: 14, cursor: 'pointer',
          }}>
            Vazgeç
          </button>
        )}
      </div>
    </form>
  );
}

function DeviceList({ devices, onSelect, onLogout, token, onDeviceAdded }) {
  const [showAddForm, setShowAddForm] = useState(devices.length === 0);

  return (
    <div className="centered-page" style={{ maxWidth: 420, padding: '0 24px' }}>
      <img src="/logo.png" alt="Binary Enerji" style={{ height: 32, display: 'block', margin: '0 auto 8px' }} />
      <div style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1, marginBottom: 4, textAlign: 'center' }}>BINARY ENERJİ</div>
      <h1 style={{ margin: '0 0 24px', fontSize: 22, fontWeight: 700, textAlign: 'center' }}>Cihazlarım</h1>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 24,
      }}>
        {devices.length === 0 && !showAddForm && (
          <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.5, textAlign: 'center', marginBottom: 16 }}>
            Hesabınıza bağlı bir cihaz bulunmuyor.
          </div>
        )}
        {devices.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {devices.map((d) => (
              <button
                key={d.device_id}
                onClick={() => onSelect(d)}
                className="device-row"
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '14px 16px', borderRadius: 8, border: '1px solid var(--border)',
                  background: 'var(--bg)', cursor: 'pointer', fontSize: 14, fontWeight: 600,
                  color: 'var(--ink)', textAlign: 'left',
                }}
              >
                {d.name}
                <span style={{ color: 'var(--muted)', fontWeight: 400 }}>İzle →</span>
              </button>
            ))}
          </div>
        )}
        {showAddForm ? (
          <AddDeviceForm
            token={token}
            compact={devices.length > 0}
            onAdded={() => { setShowAddForm(false); onDeviceAdded(); }}
            onCancel={devices.length > 0 ? () => setShowAddForm(false) : null}
          />
        ) : (
          <button onClick={() => setShowAddForm(true)} className="add-device-btn" style={{
            marginTop: devices.length > 0 ? 12 : 0, width: '100%', padding: '10px 12px', borderRadius: 8,
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
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
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
        <span style={{ fontWeight: 600, fontSize: 14, letterSpacing: 0.5 }}>{label}</span>
      </div>
      <div className="mono" style={{ fontSize: 28, fontWeight: 500 }}>
        {v != null ? v.toFixed(1) : '—'} <span style={{ fontSize: 14, color: 'var(--muted)' }}>V</span>
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
        borderRadius: 12, padding: '20px 24px', flex: 1, minWidth: 220,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
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
          background: 'var(--surface)', borderRadius: 12, padding: 24,
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
                  background: 'none', border: '1px solid var(--border)', borderRadius: 6,
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
      borderRadius: 12, padding: '16px 20px', flex: 1, minWidth: 280, height: 260,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
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
      borderRadius: 12, padding: 20, marginTop: 24,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
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
    <div style={{ display: 'flex', borderRadius: 8, background: 'var(--bg)', padding: 3 }}>
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          style={{
            padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer',
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
function StatsBlock({ title, data, suffix }) {
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
  return (
    <div style={{ flex: 1, minWidth: 260 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: 0.5, marginBottom: 10 }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {rows.map(([label, key, digits, unit]) => (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--muted)' }}>{label}</span>
            <span className="mono" style={{ fontWeight: 500 }}>{fmt(data?.[key], digits)} {unit}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatsSection({ stats }) {
  if (!stats) return null;
  return (
    <SectionCard title="Sistem Özeti (Toplam ve Ortalama)">
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
        <StatsBlock title="TÜKETİM (IMPORT)" data={stats} suffix="imp" />
        <StatsBlock title="ÜRETİM (EXPORT)" data={stats} suffix="exp" />
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
      padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)',
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
            padding: '6px 14px', borderRadius: 6, border: highRisk ? '1px solid var(--danger)' : '1px solid var(--border)',
            background: highRisk ? 'none' : 'var(--bg)', color: highRisk ? 'var(--danger)' : 'var(--ink)',
            fontSize: 12, fontWeight: 600, cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Gönderiliyor…' : highRisk ? (confirmOpen ? 'Vazgeç' : 'Uygula…') : 'Uygula'}
        </button>
      </div>
      {highRisk && confirmOpen && (
        <div style={{ background: 'var(--bg)', borderRadius: 6, padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
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
              padding: '8px 12px', borderRadius: 6, border: 'none',
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
      padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)',
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
            padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)',
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

function DeviceDashboard({ token, device, onBack, onLogout }) {
  const [connected, setConnected] = useState(false);
  const [lastMessageAt, setLastMessageAt] = useState(null);
  const [esp32Status, setEsp32Status] = useState(null); // 'online' | 'offline' | null (henüz bilinmiyor)
  const [esp32StatusChangedAt, setEsp32StatusChangedAt] = useState(null);
  const [latest, setLatest] = useState({});
  const [pulseKey, setPulseKey] = useState(0);
  const [clock, setClock] = useState(new Date());
  const [energy, setEnergy] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ctRatio, setCtRatio] = useState(null);
  const [hourlyModal, setHourlyModal] = useState(null); // { title, suffix } | null
  const [stats, setStats] = useState(null);
  const [peaks, setPeaks] = useState(null);
  const [demand, setDemand] = useState(null);
  const [harmonics, setHarmonics] = useState(null);
  const [deviceInfo, setDeviceInfo] = useState(null);
  const wsRef = useRef(null);

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
            <img src="/logo.png" alt="Binary Enerji" style={{ height: 16 }} />
            <span style={{ fontSize: 12, color: 'var(--muted)', letterSpacing: 1 }}>BINARY ENERJİ</span>
          </div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>{device.name}</h1>
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

      <StatsSection stats={stats} />
      <PeaksSection peaks={peaks} />
      <DemandSection demand={demand} />
      <HarmonicsSection harmonics={harmonics} />
      <DeviceInfoSection info={deviceInfo} />

      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 20, marginTop: 24,
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
            {deviceInfo ? (
              <>
                <span style={{ fontSize: 13, fontWeight: 600, marginTop: 8 }}>Cihaz Komutları</span>
                {DEVICE_COMMAND_LIST.map((cmd) => (
                  <CommandRow key={cmd.key} token={token} device={device} cmd={cmd} />
                ))}
              </>
            ) : (
              <div style={{
                padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Enerji/Tepe Sıfırlama, Fabrika Ayarları, Yeniden Başlatma</span>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  Bu işlemler cihazın ön panelinden yapılmalıdır — uzaktan güvenilir şekilde çalışmadığı için kaldırıldı. Panel menüleri: Enerji Sıfırlama (Ayarlar → Enerji Değerleri Silme), Tepe Değerleri (Ayarlar → Tepe Değerleri Resetleme), Fabrika Ayarları (Ayarlar → Fabrika Ayarları), Cihaz Resetleme (Ayarlar → Reset).
                </span>
              </div>
            )}
          </div>
        )}
      </div>

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
      © {new Date().getFullYear()} Binary Enerji · <a href="/gizlilik-politikasi" style={{ color: 'var(--muted)' }}>Gizlilik Politikası</a>
    </footer>
  );
}

function PrivacyPolicy() {
  return (
    <div className="centered-page" style={{ maxWidth: 640, padding: '0 24px' }}>
      <a href="/" style={{ fontSize: 12, color: 'var(--muted)', textDecoration: 'none' }}>← Binary Enerji'ye dön</a>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 32, marginTop: 16, lineHeight: 1.7, fontSize: 14,
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

export default function App() {
  if (typeof window !== 'undefined' && window.location.pathname === '/gizlilik-politikasi') {
    return <PrivacyPolicy />;
  }

  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [devices, setDevices] = useState(null); // null = yükleniyor
  const [selectedDevice, setSelectedDevice] = useState(null);

  function handleLogin(newToken) {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem('token');
    setToken(null);
    setDevices(null);
    setSelectedDevice(null);
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
  }, [token]);

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

  if (selectedDevice) {
    return (
      <>
        <DeviceDashboard
          token={token}
          device={selectedDevice}
          onBack={() => setSelectedDevice(null)}
          onLogout={handleLogout}
        />
        <Footer />
      </>
    );
  }

  return (
    <>
      <DeviceList
        devices={devices}
        onSelect={setSelectedDevice}
        onLogout={handleLogout}
        token={token}
        onDeviceAdded={refreshDevices}
      />
      <Footer />
    </>
  );
}
