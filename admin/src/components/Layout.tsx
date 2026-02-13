import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/readings', label: 'Readings' },
  { to: '/sources', label: 'Sources' },
  { to: '/templates', label: 'Templates' },
  { to: '/dictionary', label: 'Dictionary' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/events', label: 'Events' },
  { to: '/settings', label: 'Settings' },
  { to: '/audit', label: 'Audit Log' },
];

export default function Layout() {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-surface-raised border-r border-text-ghost flex flex-col">
        <div className="p-4 border-b border-text-ghost">
          <h1 className="text-xs font-mono tracking-widest text-accent uppercase">
            VOIDWIRE
          </h1>
          <p className="text-xs text-text-muted mt-1">Admin</p>
        </div>
        <nav className="flex-1 p-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
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
        <div className="p-4 border-t border-text-ghost">
          <button
            onClick={logout}
            className="text-xs text-text-muted hover:text-text-primary"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
