import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchPapers, fetchFilters, fetchReactions, toggleReaction } from '../services/api';
import './MobileFeed.css';

const DOSE_SIZE = 10;
const QUICK_EMOJIS = ['🔋', '⚡', '💡'];
const SWIPE_THRESHOLD = 80; // px to trigger swipe action

// ── Streak / stats helpers ───────────────────────────────
function getToday() {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

function loadReadLog() {
  try {
    return JSON.parse(localStorage.getItem('feed-read-log') || '{}');
  } catch { return {}; }
}

function saveReadLog(log) {
  localStorage.setItem('feed-read-log', JSON.stringify(log));
}

function logPaperRead(filename) {
  const today = getToday();
  const log = loadReadLog();
  if (!log[today]) log[today] = [];
  if (!log[today].includes(filename)) log[today].push(filename);
  saveReadLog(log);
  return log;
}

function getTodayCount(log) {
  return (log[getToday()] || []).length;
}

function getStreak(log) {
  let streak = 0;
  const d = new Date();
  while (true) {
    const key = d.toISOString().slice(0, 10);
    if (log[key]?.length > 0) {
      streak++;
      d.setDate(d.getDate() - 1);
    } else break;
  }
  return streak;
}

function getStreakEmoji(streak) {
  if (streak >= 7) return '🔥🔥🔥';
  if (streak >= 3) return '🔥🔥';
  if (streak >= 1) return '🔥';
  return '💤';
}

// Chemistry → left-edge color band mapping
const CHEM_COLORS = {
  'LFP': '#16a34a',    // green
  'NMC': '#2563eb',    // blue
  'NCA': '#7c3aed',    // purple
  'LCO': '#ea580c',    // orange
  'LTO': '#0891b2',    // cyan
  'SIB': '#dc2626',    // red
  'Na-ion': '#dc2626', // red
  'Li-S': '#ca8a04',   // amber
  'SSB': '#be185d',    // pink
  'LMO': '#059669',    // emerald
  'Silicon': '#8b5cf6', // violet
};

function getChemColor(chemistries) {
  if (!chemistries?.length) return null;
  for (const chem of chemistries) {
    const upper = chem.toUpperCase();
    for (const [key, color] of Object.entries(CHEM_COLORS)) {
      if (upper.includes(key.toUpperCase())) return color;
    }
  }
  return '#64748b'; // slate fallback
}

function FeedCard({ paper, isExpanded, onToggle, reactions, onReact, onSwipeRight, onSwipeLeft, onShare, onOpenDetail, bookmarked, dismissed, isRead }) {
  const cardRef = useRef(null);
  const slotRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const addInputRef = useRef(null);
  const swipeRef = useRef({ startX: 0, startY: 0, swiping: false });
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [swipeAction, setSwipeAction] = useState(null);
  const [flyDirection, setFlyDirection] = useState(null); // 'left' | 'right' | null

  // Smoothly collapse the card slot, then call the callback
  const collapseAndRemove = useCallback((callback) => {
    const el = slotRef.current;
    if (el) {
      // Set explicit height so CSS can transition from it
      el.style.maxHeight = el.scrollHeight + 'px';
      el.style.overflow = 'hidden';
      void el.offsetHeight; // force reflow
      el.style.transition = 'max-height 0.3s ease-out, margin-bottom 0.3s ease-out';
      el.style.maxHeight = '0px';
      el.style.marginBottom = '0px';
      setTimeout(() => callback(), 320);
    } else {
      callback();
    }
  }, []);

  // Animate in when card enters viewport
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.05 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Swipe gesture handling
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;

    function onTouchStart(e) {
      swipeRef.current.startX = e.touches[0].clientX;
      swipeRef.current.startY = e.touches[0].clientY;
      swipeRef.current.swiping = false;
    }

    function onTouchMove(e) {
      const dx = e.touches[0].clientX - swipeRef.current.startX;
      const dy = e.touches[0].clientY - swipeRef.current.startY;
      // Only swipe if horizontal movement dominates
      if (!swipeRef.current.swiping && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        swipeRef.current.swiping = true;
      }
      if (swipeRef.current.swiping) {
        const clamped = Math.max(-120, Math.min(120, dx));
        setSwipeOffset(clamped);
        if (clamped > SWIPE_THRESHOLD) setSwipeAction('bookmark');
        else if (clamped < -SWIPE_THRESHOLD) setSwipeAction('dismiss');
        else setSwipeAction(null);
      }
    }

    function onTouchEnd() {
      let triggered = false;
      if (swipeRef.current.swiping) {
        if (swipeOffset > SWIPE_THRESHOLD) {
          navigator.vibrate?.(40);
          setFlyDirection('right');
          setTimeout(() => collapseAndRemove(() => onSwipeRight(paper.filename)), 350);
          triggered = true;
        } else if (swipeOffset < -SWIPE_THRESHOLD) {
          navigator.vibrate?.(40);
          setFlyDirection('left');
          setTimeout(() => collapseAndRemove(() => onSwipeLeft(paper.filename)), 350);
          triggered = true;
        }
      }
      if (!triggered) {
        setSwipeOffset(0);
        setSwipeAction(null);
      }
      swipeRef.current.swiping = false;
    }

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: true });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
    };
  }, [swipeOffset, paper.filename, onSwipeRight, onSwipeLeft, collapseAndRemove]);

  const handleTap = () => {
    if (swipeRef.current.swiping) return; // Don't toggle if we were swiping
    navigator.vibrate?.(30);
    const el = cardRef.current;
    if (el) {
      el.classList.remove('feed-card-tapped');
      void el.offsetWidth;
      el.classList.add('feed-card-tapped');
    }
    onToggle();
  };

  const summary = paper.ai_summary || '';
  const blurb = paper.feed_blurb || '';
  const displayText = isExpanded ? summary : (blurb || summary);
  const canExpand = summary && summary.length > 200 && !isExpanded;
  const truncated = canExpand ? displayText.slice(0, 200) + '…' : displayText;
  const chemColor = getChemColor(paper.chemistries);

  return (
    <div ref={slotRef} className="feed-card-slot">
    <article
      ref={cardRef}
      className={`feed-card ${visible ? 'feed-card-visible' : 'feed-card-hidden'} ${bookmarked ? 'feed-card-bookmarked' : ''} ${isRead ? 'feed-card-read' : 'feed-card-unread'} ${flyDirection ? `feed-card-fly-${flyDirection}` : ''} ${swipeAction ? `swipe-${swipeAction}` : ''}`}
      style={{
        ...(chemColor ? { '--chem-color': chemColor } : {}),
        ...(!flyDirection && swipeOffset ? { transform: `translateX(${swipeOffset}px) rotate(${swipeOffset * 0.05}deg)`, transition: 'none' } : {}),
      }}
      onClick={handleTap}
    >
      {/* Swipe indicator overlays */}
      {swipeAction === 'bookmark' && (
        <div className="swipe-overlay swipe-overlay-bookmark">{dismissed ? '↩ Restore' : '📌 Bookmark'}</div>
      )}
      {swipeAction === 'dismiss' && (
        <div className="swipe-overlay swipe-overlay-dismiss">{dismissed ? '↩ Restore' : '✕ Dismiss'}</div>
      )}
      {/* Unread dot */}
      {!isRead && <div className="feed-card-unread-dot" />}
      <div className="feed-card-header">
        <h2 className="feed-card-title">{paper.title || paper.filename}</h2>
        <div className="feed-card-meta">
          {paper.year && <span className="feed-card-year">{paper.year}</span>}
          {paper.journal && <span className="feed-card-journal">{paper.journal}</span>}
        </div>
        {Array.isArray(paper.authors) && paper.authors.length > 0 && (
          <div className="feed-card-authors">
            {paper.authors.slice(0, 3).join(', ')}
            {paper.authors.length > 3 && ` +${paper.authors.length - 3} more`}
          </div>
        )}
      </div>

      <div className={`feed-card-body ${isExpanded ? 'expanded' : ''}`}>
        <p className="feed-card-text">
          {isExpanded ? summary : truncated}
        </p>
        {canExpand && (
          <span className="feed-card-expand">Tap to read more</span>
        )}
        {isExpanded && summary.length > 200 && (
          <span className="feed-card-expand">Tap to collapse</span>
        )}
      </div>

      <div className="feed-card-tags">
        {bookmarked && <span className="feed-tag feed-tag-bookmarked">📌</span>}
        {(paper.chemistries || []).map(c => (
          <span key={c} className="feed-tag feed-tag-chem">{c}</span>
        ))}
        {(paper.topics || []).slice(0, 3).map(t => (
          <span key={t} className="feed-tag feed-tag-topic">{t}</span>
        ))}
      </div>

      <div className="feed-reactions" onClick={e => e.stopPropagation()}>
        {(() => {
          // Merge quick emojis + any extra emojis from existing reactions
          const extraEmojis = Object.keys(reactions || {}).filter(e => !QUICK_EMOJIS.includes(e));
          const allEmojis = [...QUICK_EMOJIS, ...extraEmojis];
          return allEmojis.map((emoji) => {
            const active = reactions?.[emoji];
            return (
              <button
                key={emoji}
                className={`reaction-btn ${active ? 'active' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.vibrate?.(20);
                  onReact(paper.filename, emoji);
                }}
              >
                <span className="reaction-emoji">{emoji}</span>
              </button>
            );
          });
        })()}
        <button
          className="reaction-btn reaction-add"
          onClick={(e) => {
            e.stopPropagation();
            addInputRef.current?.focus();
          }}
        >
          <span className="reaction-emoji">+</span>
        </button>
        <input
          ref={addInputRef}
          className="reaction-hidden-input"
          type="text"
          inputMode="text"
          onInput={(e) => {
            const val = e.target.value;
            const match = val.match(/(\p{Emoji_Presentation}|\p{Emoji}\uFE0F)/u);
            if (match) {
              onReact(paper.filename, match[0]);
              e.target.value = '';
              e.target.blur();
            }
          }}
        />
        {/* Action buttons — always visible */}
        <div className="feed-card-actions">
          <button
            className="feed-action-btn feed-action-share"
            onClick={(e) => {
              e.stopPropagation();
              onShare(paper);
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
            Share
          </button>
          <button
            className="feed-action-btn feed-action-detail"
            onClick={(e) => {
              e.stopPropagation();
              onOpenDetail(paper);
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            Details
          </button>
        </div>
      </div>
    </article>
    </div>
  );
}

export default function MobileFeed() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [allPapers, setAllPapers] = useState([]);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const [reactions, setReactions] = useState({});
  const [sortMode, setSortMode] = useState('random'); // 'random' | 'newest' | 'reacted' | 'bookmarked'
  const [bookmarks, setBookmarks] = useState(() => {
    try { return JSON.parse(localStorage.getItem('feed-bookmarks') || '[]'); } catch { return []; }
  });
  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(localStorage.getItem('feed-dismissed') || '[]'); } catch { return []; }
  });
  const [readLog, setReadLog] = useState(loadReadLog);
  const [detailPaper, setDetailPaper] = useState(null); // paper object for detail overlay
  const [deferredPrompt, setDeferredPrompt] = useState(null); // PWA install prompt

  // Daily dose: random subset
  const [dose, setDose] = useState([]);
  const [doseIndex, setDoseIndex] = useState(0);   // tracks which "page" of dose we're on
  const seenRef = useRef(new Set());                // track seen papers across refreshes

  // Filter state
  const [chemistry, setChemistry] = useState('');
  const [topic, setTopic] = useState('');
  const [yearFilter, setYearFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const sentinelRef = useRef(null);

  // Pull-to-refresh — uses refs + direct DOM to avoid re-renders during touch
  const [refreshing, setRefreshing] = useState(false);
  const pullRef = useRef(null);       // the pull-indicator DOM element
  const pullIconRef = useRef(null);   // the pull-icon wrapper
  const touchStartY = useRef(0);
  const pullDist = useRef(0);         // tracked as ref, not state
  const refreshingRef = useRef(false);

  // Keep ref in sync with state so touch handlers see latest value
  useEffect(() => { refreshingRef.current = refreshing; }, [refreshing]);

  const feedContainerRef = useRef(null);

  useEffect(() => {
    const el = feedContainerRef.current;
    if (!el) return;

    function onTouchStart(e) {
      if (el.scrollTop <= 0 && !refreshingRef.current) {
        touchStartY.current = e.touches[0].clientY;
      }
    }

    function onTouchMove(e) {
      if (!touchStartY.current || refreshingRef.current) return;
      const diff = e.touches[0].clientY - touchStartY.current;
      if (diff > 0 && el.scrollTop <= 0) {
        const d = Math.min(diff * 0.5, 80);
        pullDist.current = d;
        // Direct DOM updates — no React re-render
        const indicator = pullRef.current;
        const icon = pullIconRef.current;
        if (indicator) {
          indicator.style.height = d + 'px';
          indicator.style.opacity = Math.min(d / 60, 1);
          indicator.classList.add('active');
        }
        if (icon) {
          icon.classList.toggle('ready', d > 60);
        }
      } else if (diff < 0) {
        touchStartY.current = 0;
        pullDist.current = 0;
        if (pullRef.current) {
          pullRef.current.style.height = '0px';
          pullRef.current.style.opacity = '0';
          pullRef.current.classList.remove('active');
        }
      }
    }

    function onTouchEnd() {
      if (pullDist.current > 60 && !refreshingRef.current) {
        setRefreshing(true);
        navigator.vibrate?.(40);
        // Show spinner state
        if (pullRef.current) {
          pullRef.current.style.height = '48px';
          pullRef.current.style.opacity = '1';
          pullRef.current.classList.add('refreshing');
        }
      } else {
        if (pullRef.current) {
          pullRef.current.style.height = '0px';
          pullRef.current.style.opacity = '0';
          pullRef.current.classList.remove('active');
        }
      }
      pullDist.current = 0;
      touchStartY.current = 0;
    }

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: true });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
    };
  }, []);

  // When refreshing triggers, shuffle to new dose (not a full re-fetch)
  useEffect(() => {
    if (!refreshing) return;
    // Pick a fresh random dose from papers we haven't seen yet
    shuffleDose(allPapers);
    setRefreshing(false);
    if (pullRef.current) {
      pullRef.current.style.height = '0px';
      pullRef.current.style.opacity = '0';
      pullRef.current.classList.remove('active', 'refreshing');
    }
  }, [refreshing]);

  // Shuffle helper: pick DOSE_SIZE random papers, preferring unseen ones
  function shuffleDose(papers) {
    let pool = papers.filter(p => p.feed_blurb || p.ai_summary);

    // Apply filters
    if (chemistry) pool = pool.filter(p => (p.chemistries || []).includes(chemistry));
    if (topic) pool = pool.filter(p => (p.topics || []).includes(topic));
    if (yearFilter) pool = pool.filter(p => String(p.year) === yearFilter);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      pool = pool.filter(p =>
        (p.title || '').toLowerCase().includes(q) ||
        (p.ai_summary || '').toLowerCase().includes(q) ||
        (p.feed_blurb || '').toLowerCase().includes(q)
      );
    }

    // Prefer unseen papers
    const unseen = pool.filter(p => !seenRef.current.has(p.filename));
    const source = unseen.length >= DOSE_SIZE ? unseen : pool;

    // Fisher-Yates shuffle
    const shuffled = [...source];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }

    const picked = shuffled.slice(0, DOSE_SIZE);
    picked.forEach(p => seenRef.current.add(p.filename));
    setDose(picked);
    setDoseIndex(prev => prev + 1);
    setExpandedId(null);

    // Scroll to top
    feedContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  useEffect(() => {
    Promise.all([
      fetchPapers({ status: 'AI Summary', limit: 500 }),
      fetchFilters(),
      fetchReactions(),
    ])
      .then(([pd, fd, rd]) => {
        const papers = pd.papers || [];
        setAllPapers(papers);
        setFilters(fd);
        setReactions(rd || {});
        shuffleDose(papers);

        // Deep-link: if ?paper=filename is in URL, open that paper's detail
        const sharedPaper = searchParams.get('paper');
        if (sharedPaper) {
          const found = papers.find(p => p.filename === sharedPaper);
          if (found) {
            setDetailPaper(found);
            // Clean the URL so it doesn't re-trigger
            setSearchParams({}, { replace: true });
          }
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Re-shuffle when filters change
  useEffect(() => {
    if (allPapers.length) {
      seenRef.current.clear();
      shuffleDose(allPapers);
    }
  }, [chemistry, topic, yearFilter, searchQuery]);

  const totalFiltered = useMemo(() => {
    let pool = allPapers.filter(p => p.feed_blurb || p.ai_summary);
    if (chemistry) pool = pool.filter(p => (p.chemistries || []).includes(chemistry));
    if (topic) pool = pool.filter(p => (p.topics || []).includes(topic));
    if (yearFilter) pool = pool.filter(p => String(p.year) === yearFilter);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      pool = pool.filter(p =>
        (p.title || '').toLowerCase().includes(q) ||
        (p.ai_summary || '').toLowerCase().includes(q) ||
        (p.feed_blurb || '').toLowerCase().includes(q)
      );
    }
    return pool.length;
  }, [allPapers, chemistry, topic, yearFilter, searchQuery]);

  const years = useMemo(() => {
    const s = new Set(allPapers.map(p => String(p.year)).filter(y => y && y !== 'undefined'));
    return [...s].sort().reverse();
  }, [allPapers]);

  const handleReact = useCallback(async (filename, emoji) => {
    try {
      const result = await toggleReaction(filename, emoji);
      setReactions(prev => ({ ...prev, [filename]: result.reactions }));
    } catch (e) {
      console.error('Reaction failed:', e);
    }
  }, []);

  // Bookmark (swipe right)
  const handleBookmark = useCallback((filename) => {
    setBookmarks(prev => {
      const next = prev.includes(filename) ? prev.filter(f => f !== filename) : [...prev, filename];
      localStorage.setItem('feed-bookmarks', JSON.stringify(next));
      return next;
    });
  }, []);

  // Dismiss (swipe left) — removes from current dose
  const handleDismiss = useCallback((filename) => {
    setDismissed(prev => {
      const next = [...prev, filename];
      localStorage.setItem('feed-dismissed', JSON.stringify(next));
      return next;
    });
    // Only remove from dose in non-dismissed view (in dismissed view, let fly-off handle visual)
    setDose(prev => prev.filter(p => p.filename !== filename));
  }, []);

  // Restore a dismissed paper (un-dismiss)
  const handleRestore = useCallback((filename) => {
    setDismissed(prev => {
      const next = prev.filter(f => f !== filename);
      localStorage.setItem('feed-dismissed', JSON.stringify(next));
      return next;
    });
  }, []);

  // Toast state for share feedback
  const [toast, setToast] = useState(null);
  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  }, []);

  // Share — TikTok-style: share a link that opens just this paper
  const handleShare = useCallback(async (paper) => {
    const shareUrl = `${window.location.origin}/app?paper=${encodeURIComponent(paper.filename)}`;
    const text = paper.feed_blurb || paper.ai_summary?.slice(0, 200) || '';
    navigator.vibrate?.(20);

    // Try native share (mobile)
    if (navigator.share) {
      try {
        await navigator.share({
          title: paper.title,
          text: `${paper.title}\n\n${text}`,
          url: shareUrl,
        });
        return; // user completed or cancelled — either way, done
      } catch (err) {
        // AbortError = user cancelled, which is fine
        if (err.name === 'AbortError') return;
        // Other errors: fall through to clipboard
        console.warn('navigator.share failed:', err);
      }
    }

    // Fallback: clipboard
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareUrl);
        showToast('Link copied!');
        return;
      }
    } catch (err) {
      console.warn('clipboard.writeText failed:', err);
    }

    // Last resort: prompt with URL (works on any context)
    window.prompt('Copy this link:', shareUrl);
  }, [showToast]);

  // Detail overlay
  const handleOpenDetail = useCallback((paper) => {
    setDetailPaper(paper);
  }, []);

  // Track paper reads for streak
  const toggleExpand = useCallback((filename) => {
    setExpandedId(prev => {
      const next = prev === filename ? null : filename;
      if (next) {
        // Expanding = "reading" the paper
        const updated = logPaperRead(filename);
        setReadLog({ ...updated });
      }
      return next;
    });
  }, []);

  // Computed: which papers have been read (from all days in the log)
  const readPapers = useMemo(() => {
    const s = new Set();
    Object.values(readLog).forEach(arr => arr.forEach(f => s.add(f)));
    return s;
  }, [readLog]);

  // PWA install prompt
  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') setDeferredPrompt(null);
  }, [deferredPrompt]);

  // Computed streak values
  const todayCount = getTodayCount(readLog);
  const streak = getStreak(readLog);
  const streakEmoji = getStreakEmoji(streak);

  // Sort mode: apply to dose (or pull from allPapers for saved/dismissed)
  const sortedDose = useMemo(() => {
    if (sortMode === 'bookmarked') {
      // Show ALL bookmarked papers, not just current dose
      return allPapers.filter(p => bookmarks.includes(p.filename));
    }
    if (sortMode === 'dismissed') {
      // Show ALL dismissed papers so users can revisit
      return allPapers.filter(p => dismissed.includes(p.filename));
    }
    let d = [...dose];
    if (sortMode === 'newest') d.sort((a, b) => (b.year || 0) - (a.year || 0));
    else if (sortMode === 'reacted') {
      d.sort((a, b) => {
        const aCount = Object.keys(reactions[a.filename] || {}).length;
        const bCount = Object.keys(reactions[b.filename] || {}).length;
        return bCount - aCount;
      });
    }
    return d;
  }, [dose, sortMode, reactions, bookmarks, dismissed, allPapers]);

  const activeFilterCount = [chemistry, topic, yearFilter].filter(Boolean).length;

  if (loading) {
    return (
      <div className="mobile-feed">
        <div className="feed-loading">
          <div className="feed-loading-spinner" />
          <p>Loading papers\u2026</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mobile-feed" ref={feedContainerRef}>
      {/* Pull-to-refresh indicator */}
      <div
        ref={pullRef}
        className="pull-indicator"
        style={{ height: 0, opacity: 0 }}
      >
        <div ref={pullIconRef} className="pull-icon">
          {refreshing ? (
            <div className="feed-loading-spinner small" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          )}
        </div>
      </div>

      {/* Sticky header */}
      <header className="feed-header">
        <div className="feed-header-top">
          <h1 className="feed-logo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="2" y1="12" x2="22" y2="12"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
            Astrolabe
          </h1>
          <div className="feed-streak">
            <span className="streak-emoji">{streakEmoji}</span>
            <div className="streak-stats">
              <span className="streak-today">{todayCount} read today</span>
              <span className="streak-days">{streak} day{streak !== 1 ? 's' : ''} in a row</span>
            </div>
          </div>
        </div>

        {/* Sort presets */}
        <div className="feed-sort-bar">
          {[
            { key: 'random', label: '🎲 Random' },
            { key: 'newest', label: '🆕 Newest' },
            { key: 'reacted', label: '⚡ Reacted' },
            { key: 'bookmarked', label: `📌 Saved${bookmarks.length ? ` (${bookmarks.length})` : ''}` },
            { key: 'dismissed', label: `🙅 Dismissed${dismissed.length ? ` (${dismissed.length})` : ''}` },
          ].map(s => (
            <button
              key={s.key}
              className={`feed-sort-chip ${sortMode === s.key ? 'active' : ''}`}
              onClick={() => { navigator.vibrate?.(15); setSortMode(s.key); }}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="feed-search-row">
          <input
            type="search"
            className="feed-search"
            placeholder="Search papers…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
          <button
            className={`feed-filter-btn ${activeFilterCount > 0 ? 'active' : ''}`}
            onClick={() => { navigator.vibrate?.(20); setShowFilters(!showFilters); }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
            </svg>
            {activeFilterCount > 0 && <span className="feed-filter-badge">{activeFilterCount}</span>}
          </button>
        </div>

        {showFilters && (
          <div className="feed-filters">
            <select value={chemistry} onChange={e => setChemistry(e.target.value)}>
              <option value="">All Chemistries</option>
              {(filters.chemistries || []).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={topic} onChange={e => setTopic(e.target.value)}>
              <option value="">All Topics</option>
              {(filters.topics || []).map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <select value={yearFilter} onChange={e => setYearFilter(e.target.value)}>
              <option value="">All Years</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            {activeFilterCount > 0 && (
              <button className="feed-clear-filters" onClick={() => { setChemistry(''); setTopic(''); setYearFilter(''); }}>
                Clear filters
              </button>
            )}
          </div>
        )}
      </header>

      {/* PWA install banner */}
      {deferredPrompt && (
        <div className="feed-install-banner" onClick={handleInstall}>
          <span>📲 Install Astrolabe for quick access</span>
          <button className="feed-install-btn">Install</button>
        </div>
      )}

      {/* Card list */}
      <div className="feed-cards">
        {sortedDose.length === 0 ? (
          <div className="feed-empty">
            <p>{sortMode === 'bookmarked' ? 'No bookmarked papers yet. Swipe right on a card to bookmark!' : sortMode === 'dismissed' ? 'No dismissed papers. Swipe left on a card to dismiss it.' : 'No papers match your filters.'}</p>
          </div>
        ) : (
          <>
            {sortedDose.map(p => (
              <FeedCard
                key={p.filename}
                paper={p}
                isExpanded={expandedId === p.filename}
                onToggle={() => toggleExpand(p.filename)}
                reactions={reactions[p.filename]}
                onReact={handleReact}
                onSwipeRight={sortMode === 'dismissed' ? handleRestore : handleBookmark}
                onSwipeLeft={sortMode === 'dismissed' ? handleRestore : handleDismiss}
                onShare={handleShare}
                onOpenDetail={handleOpenDetail}
                bookmarked={bookmarks.includes(p.filename)}
                dismissed={dismissed.includes(p.filename)}
                isRead={readPapers.has(p.filename)}
              />
            ))}
            {sortMode === 'dismissed' && (
              <div className="feed-end">
                <p>Swipe right to restore papers</p>
              </div>
            )}
            {sortMode === 'bookmarked' && (
              <div className="feed-end">
                <p>{bookmarks.length} saved paper{bookmarks.length !== 1 ? 's' : ''}</p>
              </div>
            )}
            {sortMode !== 'bookmarked' && sortMode !== 'dismissed' && (
              <div className="feed-end">
                <p>Pull down for {DOSE_SIZE} more papers</p>
                <p className="feed-seen-count">{seenRef.current.size} of {totalFiltered} seen</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Paper detail overlay */}
      {detailPaper && (
        <div className="feed-detail-overlay" onClick={() => setDetailPaper(null)}>
          <div className="feed-detail-sheet" onClick={e => e.stopPropagation()}>
            <div className="feed-detail-header">
              <button className="feed-detail-close" onClick={() => setDetailPaper(null)}>✕</button>
              <h2 className="feed-detail-title">{detailPaper.title}</h2>
            </div>
            <div className="feed-detail-body">
              {detailPaper.year && <div className="feed-detail-row"><strong>Year:</strong> {detailPaper.year}</div>}
              {detailPaper.journal && <div className="feed-detail-row"><strong>Journal:</strong> {detailPaper.journal}</div>}
              {Array.isArray(detailPaper.authors) && detailPaper.authors.length > 0 && (
                <div className="feed-detail-row"><strong>Authors:</strong> {detailPaper.authors.join(', ')}</div>
              )}
              {detailPaper.doi && (
                <div className="feed-detail-row">
                  <strong>DOI:</strong>{' '}
                  <a href={`https://doi.org/${detailPaper.doi}`} target="_blank" rel="noopener noreferrer" className="feed-detail-link">
                    {detailPaper.doi}
                  </a>
                </div>
              )}
              {detailPaper.url && (
                <div className="feed-detail-row">
                  <a href={detailPaper.url} target="_blank" rel="noopener noreferrer" className="feed-detail-link feed-detail-pdf-btn">
                    📄 Open PDF / Source
                  </a>
                </div>
              )}
              {(detailPaper.chemistries || []).length > 0 && (
                <div className="feed-detail-row">
                  <strong>Chemistries:</strong> {detailPaper.chemistries.join(', ')}
                </div>
              )}
              {(detailPaper.topics || []).length > 0 && (
                <div className="feed-detail-row">
                  <strong>Topics:</strong> {detailPaper.topics.join(', ')}
                </div>
              )}
              <div className="feed-detail-summary">
                <strong>Full Summary</strong>
                <p>{detailPaper.ai_summary || 'No summary available.'}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className="feed-toast">{toast}</div>
      )}
    </div>
  );
}
