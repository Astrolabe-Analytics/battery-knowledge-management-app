import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './components/Toast';
import Layout from './components/Layout';
import Library from './pages/Library';
import PaperDetail from './pages/PaperDetail';
import Dashboard from './pages/Dashboard';
import Feed from './pages/Feed';
import Research from './pages/Research';
import Discover from './pages/Discover';
import Collections from './pages/Collections';
import CollectionDetail from './pages/CollectionDetail';
import History from './pages/History';
import Settings from './pages/Settings';
import Trash from './pages/Trash';
import Import from './pages/Import';

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Library />} />
            <Route path="paper/:filename" element={<PaperDetail />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="feed" element={<Feed />} />
            <Route path="research" element={<Research />} />
            <Route path="discover" element={<Discover />} />
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
