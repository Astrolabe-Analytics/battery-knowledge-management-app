import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from 'recharts';
import { BarChart3, Library, FileText, Sparkles, Database, BookCheck } from 'lucide-react';
import { fetchPaperStats, fetchChartData } from '../services/api';
import styles from './Dashboard.module.css';

const COLORS = [
  '#2563eb', '#7c3aed', '#db2777', '#ea580c', '#16a34a',
  '#0891b2', '#4f46e5', '#c026d3', '#ca8a04', '#dc2626',
  '#059669', '#6366f1', '#e11d48', '#d97706', '#0d9488',
];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [charts, setCharts] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchPaperStats(), fetchChartData()])
      .then(([s, c]) => { setStats(s); setCharts(c); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className={styles.loading}>Loading dashboard…</div>;

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>
        <BarChart3 size={24} /> Dashboard
      </h1>

      {/* Stat cards */}
      {stats && (
        <div className={styles.statGrid}>
          <StatCard icon={Library} label="Total Papers" value={stats.total_papers} color="var(--astro-primary)" />
          <StatCard icon={Sparkles} label="AI Summary" value={stats.ai_summary} color="var(--astro-success)" />
          <StatCard icon={FileText} label="Complete" value={stats.complete} color="#7c3aed" />
          <StatCard icon={BookCheck} label="Metadata Only" value={stats.metadata_only} color="var(--astro-warning)" />
          <StatCard icon={Database} label="Chunks" value={stats.chunk_count?.toLocaleString()} color="#0891b2" />
        </div>
      )}

      {charts && (
        <div className={styles.chartGrid}>
          {/* Papers by Year */}
          {charts.by_year?.length > 0 && (
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>Papers by Year</h3>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={charts.by_year}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--astro-border)" />
                  <XAxis dataKey="name" fontSize={12} stroke="var(--astro-text-muted)" />
                  <YAxis fontSize={12} stroke="var(--astro-text-muted)" />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--astro-surface)',
                      border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)',
                      fontSize: 'var(--astro-text-sm)',
                    }}
                  />
                  <Area type="linear" dataKey="count" stroke="#2563eb" fill="#dbeafe" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Chemistry distribution */}
          {charts.by_chemistry?.length > 0 && (
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>By Chemistry</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={charts.by_chemistry} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--astro-border)" />
                  <XAxis type="number" fontSize={12} stroke="var(--astro-text-muted)" />
                  <YAxis
                    dataKey="name" type="category" width={120} fontSize={11}
                    stroke="var(--astro-text-muted)" tick={{ fill: 'var(--astro-text-secondary)' }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--astro-surface)',
                      border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)',
                      fontSize: 'var(--astro-text-sm)',
                    }}
                  />
                  <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Topic distribution */}
          {charts.by_topic?.length > 0 && (
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>By Topic</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={charts.by_topic} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--astro-border)" />
                  <XAxis type="number" fontSize={12} stroke="var(--astro-text-muted)" />
                  <YAxis
                    dataKey="name" type="category" width={140} fontSize={11}
                    stroke="var(--astro-text-muted)" tick={{ fill: 'var(--astro-text-secondary)' }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--astro-surface)',
                      border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)',
                      fontSize: 'var(--astro-text-sm)',
                    }}
                  />
                  <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Paper type pie chart */}
          {charts.by_type?.length > 0 && (
            <div className={styles.chartCard}>
              <h3 className={styles.chartTitle}>By Paper Type</h3>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={charts.by_type}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    labelLine={false}
                    fontSize={11}
                  >
                    {charts.by_type.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'var(--astro-surface)',
                      border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)',
                      fontSize: 'var(--astro-text-sm)',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statIcon} style={{ color }}>
        <Icon size={20} />
      </div>
      <div>
        <div className={styles.statValue}>{value ?? '—'}</div>
        <div className={styles.statLabel}>{label}</div>
      </div>
    </div>
  );
}
