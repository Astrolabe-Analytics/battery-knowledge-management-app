import { NavLink, Outlet } from 'react-router-dom';
import {
  BookOpen,
  Search,
  Rss,
  Compass,
  Settings,
  FolderOpen,
  Clock,
  BarChart3,
  Trash2,
  Plus,
} from 'lucide-react';
import CommandPalette from './CommandPalette';
import styles from './Layout.module.css';

const navItems = [
  { section: 'Library' },
  { to: '/', icon: BookOpen, label: 'Papers' },
  { to: '/dashboard', icon: BarChart3, label: 'Dashboard' },
  { to: '/collections', icon: FolderOpen, label: 'Collections' },
  { to: '/import', icon: Plus, label: 'Import' },
  { section: 'Discover' },
  { to: '/research', icon: Search, label: 'Research' },
  { to: '/feed', icon: Rss, label: 'Feed' },
  { to: '/discover', icon: Compass, label: 'Discover' },
  { section: 'System' },
  { to: '/history', icon: Clock, label: 'History' },
  { to: '/trash', icon: Trash2, label: 'Trash' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Layout() {
  return (
    <>
      <CommandPalette />
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <Compass size={22} /> Astrolabe
        </div>

        <nav className={styles.nav}>
          {navItems.map((item, i) =>
            item.section ? (
              <div key={i} className={styles.navLabel}>{item.section}</div>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  isActive ? styles.linkActive : styles.link
                }
              >
                <item.icon size={18} />
                {item.label}
              </NavLink>
            )
          )}
        </nav>

        <div className={styles.footer}>
          <div className={styles.shortcutHint}>
            <Search size={12} /> <kbd>Ctrl+K</kbd> Search
          </div>
          Astrolabe Paper DB
        </div>
      </aside>

      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </>
  );
}
