import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Download, RotateCcw, Moon, Sun, LogOut } from 'lucide-react';
import { fetchSettings, updateSettings, fetchBackups, createBackup, logout } from '../services/api';
import { useToast } from '../components/Toast';

export default function Settings() {
  const [settings, setSettings] = useState({});
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(() =>
    document.documentElement.getAttribute('data-theme') || 'light'
  );
  const toast = useToast();

  useEffect(() => {
    Promise.all([fetchSettings(), fetchBackups()])
      .then(([s, b]) => {
        setSettings(s);
        setBackups(b.backups || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    setTheme(next);
    localStorage.setItem('astro-theme', next);
  }

  async function handleBackup() {
    try {
      await createBackup();
      const b = await fetchBackups();
      setBackups(b.backups || []);
      toast.success('Backup created successfully');
    } catch (e) {
      toast.error('Failed to create backup');
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700, marginBottom: 24 }}>
        <SettingsIcon size={24} style={{ verticalAlign: 'middle', marginRight: 8 }} />
        Settings
      </h1>

      {/* Theme toggle */}
      <Section title="Appearance">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 'var(--astro-text-sm)' }}>Theme</span>
          <button
            onClick={toggleTheme}
            style={{
              padding: '8px 20px', border: '1px solid var(--astro-border)',
              borderRadius: 'var(--astro-radius)', background: 'var(--astro-surface)',
              color: 'var(--astro-text)', display: 'flex', alignItems: 'center', gap: 8,
              cursor: 'pointer',
            }}
          >
            {theme === 'dark' ? <><Sun size={14} /> Light</> : <><Moon size={14} /> Dark</>}
          </button>
        </div>
      </Section>

      {/* Library info */}
      <Section title="Library Info">
        <InfoRow label="Total papers" value={settings.total_papers ?? '—'} />
        <InfoRow label="AI Summary" value={settings.ai_summary ?? '—'} />
        <InfoRow label="Chunks in vector DB" value={settings.chunk_count ?? '—'} />
      </Section>

      {/* Backups */}
      <Section title="Backups">
        <button
          onClick={handleBackup}
          style={{
            padding: '8px 20px', background: 'var(--astro-primary)', color: '#fff',
            border: 'none', borderRadius: 'var(--astro-radius)', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16, cursor: 'pointer',
          }}
        >
          <Download size={14} /> Create Backup
        </button>

        {backups.length === 0 ? (
          <div style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-sm)' }}>No backups found.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {backups.map((b, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', background: 'var(--astro-bg-secondary)',
                  borderRadius: 'var(--astro-radius)', fontSize: 'var(--astro-text-sm)',
                }}
              >
                <span>{b.name || b.filename || b}</span>
                <span style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-xs)' }}>
                  {b.created_at || ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Account */}
      <Section title="Account">
        <button
          onClick={() => { logout(); window.location.reload(); }}
          style={{
            padding: '8px 20px', background: 'var(--astro-danger)', color: '#fff',
            border: 'none', borderRadius: 'var(--astro-radius)', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
          }}
        >
          <LogOut size={14} /> Sign Out
        </button>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div
      style={{
        background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
        borderRadius: 'var(--astro-radius-lg)', padding: 24, marginBottom: 16,
      }}
    >
      <h2 style={{ fontSize: 'var(--astro-text-lg)', fontWeight: 600, marginBottom: 16 }}>{title}</h2>
      {children}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 'var(--astro-text-sm)' }}>
      <span style={{ color: 'var(--astro-text-secondary)' }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{value}</span>
    </div>
  );
}
