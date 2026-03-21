import { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './components/Toast';
import { checkAuth, setOnUnauthorized } from './services/api';
import Layout from './components/Layout';
import Login from './pages/Login';
import Library from './pages/Library';
import PaperDetail from './pages/PaperDetail';
import Dashboard from './pages/Dashboard';
import Feed from './pages/Feed';
import MobileFeed from './pages/MobileFeed';
import Research from './pages/Research';
import Discover from './pages/Discover';
import Collections from './pages/Collections';
import CollectionDetail from './pages/CollectionDetail';
import History from './pages/History';
import Settings from './pages/Settings';
import Trash from './pages/Trash';
import Import from './pages/Import';
import CitationGraph from './pages/CitationGraph';

export default function App() {
  const [authed, setAuthed] = useState(null); // null = loading

  const handleLogout = useCallback(() => setAuthed(false), []);

  useEffect(() => {
    setOnUnauthorized(handleLogout);

    // Check if auth is enabled and if we have a valid token
    checkAuth().then(data => {
      if (!data.auth_enabled) {
        setAuthed(true); // No password set — open access
      } else {
        // Auth enabled — check if we have a stored token
        setAuthed(!!localStorage.getItem('astrolabe_token'));
      }
    }).catch(() => setAuthed(true)); // Can't reach server — let routes fail naturally
  }, [handleLogout]);

  if (authed === null) return null; // Loading

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          {/* Standalone PWA feed — no sidebar */}
          <Route path="/app" element={<MobileFeed />} />

          <Route element={<Layout />}>
            <Route index element={<Library />} />
            <Route path="paper/:filename" element={<PaperDetail />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="feed" element={<Feed />} />
            <Route path="research" element={<Research />} />
            <Route path="discover" element={<Discover />} />
            <Route path="citations" element={<CitationGraph />} />
            <Route path="collections" element={<Collections />} />
            <Route path="collections/:id" element={<CollectionDetail />} />
            <Route path="history" element={<History />} />
            <Route path="settings" element={<Settings />} />
            <Route path="trash" element={<Trash />} />
            <Route path="import" element={<Import />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
