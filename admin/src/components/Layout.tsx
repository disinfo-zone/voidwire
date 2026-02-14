import { useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/readings', label: 'Readings' },
  { to: '/sources', label: 'Sources' },
  { to: '/templates', label: 'Templates' },
  { to: '/dictionary', label: 'Dictionary' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/events', label: 'Events' },
  { to: '/threads', label: 'Threads' },
  { to: '/signals', label: 'Signals' },
  { to: '/llm', label: 'LLM Config' },
  { to: '/settings', label: 'Settings' },
  { to: '/backup', label: 'Backups' },
  { to: '/audit', label: 'Audit Log' },
];

const themeIcons: Record<string, string> = {
  light: '\u2600',
  dark: '\u263E',
  system: '\u25D0',
};

const themeOrder: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];

export default function Layout() {
  const { logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function cycleTheme() {
    const idx = themeOrder.indexOf(theme);
    setTheme(themeOrder[(idx + 1) % themeOrder.length]);
  }

  function handleNavClick() {
    setSidebarOpen(false);
  }

  return (
    <div className="min-h-screen flex">
      {/* Mobile hamburger */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-3 left-3 z-40 md:hidden p-2 rounded bg-surface-raised border border-text-ghost text-text-primary"
        aria-label="Open menu"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 4.5h12M3 9h12M3 13.5h12" />
        </svg>
      </button>

      {/* Backdrop */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-56 bg-surface-raised border-r border-text-ghost flex flex-col
        transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0 md:static md:z-auto
      `}>
        <div className="p-4 border-b border-text-ghost flex justify-between items-center">
          <div>
            <h1 className="text-xs font-mono tracking-widest text-accent uppercase">
              VOIDWIRE
            </h1>
            <p className="text-xs text-text-muted mt-1">Admin</p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden text-text-muted hover:text-text-primary text-lg"
            aria-label="Close menu"
          >
            &times;
          </button>
        </div>
        <nav className="flex-1 p-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={handleNavClick}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm ${
                  isActive
                    ? 'bg-void text-accent'
                    : 'text-text-secondary hover:text-text-primary hover:bg-void/50'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-text-ghost flex items-center justify-between">
          <button
            onClick={logout}
            className="text-xs text-text-muted hover:text-text-primary"
          >
            Sign out
          </button>
          <button
            onClick={cycleTheme}
            className="text-sm text-text-muted hover:text-text-primary"
            title={`Theme: ${theme}`}
          >
            {themeIcons[theme]}
          </button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-8 overflow-auto pt-14 md:pt-8">
        <Outlet />
      </main>
    </div>
  );
}
