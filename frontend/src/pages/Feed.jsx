import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { fetchPapers, fetchFilters } from '../services/api';
import styles from './Feed.module.css';

export default function Feed() {
  const [papers, setPapers] = useState([]);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);

  const [chemistry, setChemistry] = useState('');
  const [topic, setTopic] = useState('');
  const [yearFilter, setYearFilter] = useState('');

  useEffect(() => {
    Promise.all([fetchPapers({ status: 'AI Summary', limit: 500 }), fetchFilters()])
      .then(([pd, fd]) => {
        setPapers(pd.papers || []);
        setFilters(fd);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const feed = useMemo(() => {
    let list = papers.filter(p => p.feed_blurb || p.ai_summary);
    if (chemistry) list = list.filter(p => (p.chemistries || []).includes(chemistry));
    if (topic) list = list.filter(p => (p.topics || []).includes(topic));
    if (yearFilter) list = list.filter(p => String(p.year) === yearFilter);
    // Most recently added first
    list.sort((a, b) => (b.date_added || '').localeCompare(a.date_added || ''));
    return list;
  }, [papers, chemistry, topic, yearFilter]);

  const years = useMemo(() => {
    const s = new Set(papers.map(p => String(p.year)).filter(Boolean));
    return [...s].sort().reverse();
  }, [papers]);

  if (loading) return <div className={styles.loading}>Loading feed…</div>;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Feed</h1>
        <p className={styles.subtitle}>Browse AI-generated summaries of your papers</p>
      </div>

      <div className={styles.filters}>
        <select className={styles.filterSelect} value={chemistry} onChange={e => setChemistry(e.target.value)}>
          <option value="">All Chemistries</option>
          {(filters.chemistries || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className={styles.filterSelect} value={topic} onChange={e => setTopic(e.target.value)}>
          <option value="">All Topics</option>
          {(filters.topics || []).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className={styles.filterSelect} value={yearFilter} onChange={e => setYearFilter(e.target.value)}>
          <option value="">All Years</option>
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {feed.length === 0 ? (
        <div className={styles.empty}>No papers with summaries match your filters.</div>
      ) : (
        <div className={styles.cardList}>
          {feed.map(p => (
            <div key={p.filename} className={styles.card}>
              <div className={styles.cardTitle}>
                <Link
                  to={`/paper/${encodeURIComponent(p.filename)}`}
                  className={styles.cardTitleLink}
                >
                  {p.title || p.filename}
                </Link>
              </div>
              <div className={styles.cardMeta}>
                <span>{Array.isArray(p.authors) ? p.authors.join(', ') : p.authors}</span>
                <span>{p.year}</span>
                <span>{p.journal}</span>
              </div>
              <div className={styles.blurb}>
                {p.feed_blurb || p.ai_summary}
              </div>
              <div className={styles.tags}>
                {(p.chemistries || []).map(c => <span key={c} className={styles.tag}>{c}</span>)}
                {(p.topics || []).map(t => <span key={t} className={styles.tag}>{t}</span>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
