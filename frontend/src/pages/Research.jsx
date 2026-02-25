import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Search } from 'lucide-react';
import { askQuestion, fetchHistory, fetchCollections } from '../services/api';
import styles from './Research.module.css';

export default function Research() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [collections, setCollections] = useState([]);
  const [collectionId, setCollectionId] = useState('');

  useEffect(() => {
    Promise.all([fetchHistory({ limit: 20 }), fetchCollections()])
      .then(([hd, cd]) => {
        setHistory(hd.queries || []);
        setCollections(cd.collections || []);
      })
      .catch(console.error);
  }, []);

  async function handleAsk(e) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setAnswer(null);
    setSources([]);
    try {
      const opts = {};
      if (collectionId) opts.collection_id = Number(collectionId);
      const res = await askQuestion(question, opts);
      setAnswer(res.answer || '');
      setSources(res.sources || []);
      // refresh history
      fetchHistory({ limit: 20 })
        .then(data => setHistory(data.queries || []))
        .catch(console.error);
    } catch (err) {
      setAnswer('Error: ' + err.message);
    }
    setLoading(false);
  }

  function replayQuestion(q) {
    setQuestion(q);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Research</h1>
        <p className={styles.subtitle}>Ask questions about your paper library using AI</p>
      </div>

      {collections.length > 0 && (
        <div className={styles.scopeBar}>
          <label className={styles.scopeLabel}>Scope:</label>
          <select
            className={styles.scopeSelect}
            value={collectionId}
            onChange={e => setCollectionId(e.target.value)}
          >
            <option value="">All Papers</option>
            {collections.map(c => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.paper_count ?? 0})
              </option>
            ))}
          </select>
        </div>
      )}

      <form className={styles.form} onSubmit={handleAsk}>
        <input
          className={styles.input}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask a question about your papers…"
        />
        <button className={styles.askBtn} type="submit" disabled={loading}>
          {loading ? 'Thinking…' : <><Search size={14} /> Ask</>}
        </button>
      </form>

      {/* Answer */}
      {answer && (
        <div className={styles.answerCard}>
          <div className={styles.answerLabel}><Sparkles size={16} /> Answer</div>
          <div className={styles.answerText}>{answer}</div>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <>
          <div className={styles.sourcesTitle}>Sources ({sources.length})</div>
          <div className={styles.sourceList}>
            {sources.map((s, i) => (
              <div key={i} className={styles.sourceCard}>
                <div
                  className={styles.sourceHeader}
                  onClick={() => s.filename && navigate(`/paper/${encodeURIComponent(s.filename)}`)}
                >
                  {s.title || s.filename || `Source ${i + 1}`}
                </div>
                <div className={styles.sourceSnippet}>
                  {(s.text || s.content || '').slice(0, 300)}…
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Recent queries */}
      {history.length > 0 && (
        <div className={styles.historySection}>
          <div className={styles.historyTitle}>Recent Questions</div>
          {history.map(h => (
            <div
              key={h.id}
              className={styles.historyItem}
              onClick={() => replayQuestion(h.question)}
            >
              <div className={styles.historyQuestion}>{h.question}</div>
              <div className={styles.historyMeta}>
                {h.timestamp} · {h.num_sources} sources
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
